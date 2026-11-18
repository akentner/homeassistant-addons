"""Access store for /data/access.json (MRP-04, contract D-20) and the symlink tree that authorizes clones (D-06).

Document: {"schema": 1, "entries": [{"repository", "user", "hash", "created", "source"}]}. Every read-modify-write
holds one lock (process RLock plus flock on /run/marketplace-repo-proxy/access.lock) and replaces the file atomically.
Unknown top-level keys and entry fields are preserved. A corrupt file is renamed to access.json.corrupt and the store
starts empty (fail closed); a newer schema is refused and never written. No hash is ever logged.
"""

from __future__ import annotations

import contextlib
import fcntl
import logging
import os
import re
import secrets
import threading
from pathlib import Path
from typing import Any, Iterable, Iterator

from app.jsonio import atomic_write_json, read_json, utc_timestamp
from app.options import RepoSpec, parse_repository
from app.paths import Paths

SCHEMA = 1
HASH_RE = re.compile(r"^[0-9a-f]{32}$")
USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SOURCES = ("gui", "api", "system", "cli")
RESERVED_USERS: frozenset[str] = frozenset()  # RED stub

LOG = logging.getLogger("mrp.access")
_THREAD_LOCK = threading.RLock()
_HELD = threading.local()  # lock depth per thread: a nested locked() must not flock a second fd (would deadlock)


class AccessError(ValueError):
    """Domain error with a stable code (CLI prints it, the Phase 4 API maps it)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AccessSchemaError(AccessError):
    """access.json carries a schema version this code does not know."""


def new_hash() -> str:
    """128 random bits from the OS CSPRNG as 32 lowercase hex (D-05)."""
    return secrets.token_hex(16)


def _empty() -> dict[str, Any]:
    return {"schema": SCHEMA, "entries": []}


def _valid_shape(doc: Any) -> bool:
    if not isinstance(doc, dict) or not isinstance(doc.get("schema"), int) or isinstance(doc.get("schema"), bool):
        return False
    entries = doc.get("entries")
    return isinstance(entries, list) and all(isinstance(e, dict) for e in entries)


class AccessStore:
    def __init__(self, paths: Paths, log: logging.Logger | None = None) -> None:
        self.paths = paths
        self.log = log or LOG

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        """Exclusive across threads and processes; reentrant within one thread."""
        with _THREAD_LOCK:
            depth = getattr(_HELD, "depth", 0)
            if depth:
                _HELD.depth = depth + 1
                try:
                    yield
                finally:
                    _HELD.depth = depth
                return
            self.paths.lock_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(self.paths.lock_file, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                _HELD.depth = 1
                yield
            finally:
                _HELD.depth = 0
                os.close(fd)

    def load(self) -> dict[str, Any]:
        path = self.paths.access_file
        try:
            doc = read_json(path)
        except (OSError, ValueError):
            doc = False  # marker: present but unreadable or invalid
        if doc is None:
            return _empty()
        if _valid_shape(doc):
            if doc["schema"] > SCHEMA:
                raise AccessSchemaError("schema_unsupported")
            return doc
        self.log.error("access.json is corrupt; moved to access.json.corrupt, starting with no users")
        try:
            os.replace(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            pass
        return _empty()

    def entries(self) -> list[dict[str, Any]]:
        return list(self.load()["entries"])

    def add(
        self,
        repository: str,
        user: str,
        source: str = "cli",
        hash_: str | None = None,
        specs: Iterable[RepoSpec] | None = None,
    ) -> dict[str, Any]:
        """Append one entry (re-reads the file under the lock); unknown keys and fields are kept untouched."""
        try:
            parse_repository(repository)
        except (TypeError, ValueError):
            raise AccessError("repository_unknown") from None
        if not isinstance(user, str) or not USER_RE.match(user):
            raise AccessError("invalid_user")
        if source not in SOURCES:
            raise AccessError("invalid_source")
        if hash_ is not None and (not isinstance(hash_, str) or not HASH_RE.match(hash_)):
            raise AccessError("invalid_hash")
        with self.locked():
            doc = self.load()
            entries = doc["entries"]
            if any(
                isinstance(e.get("repository"), str)
                and e["repository"].lower() == repository.lower()
                and e.get("user") == user
                for e in entries
            ):
                raise AccessError("user_exists")
            used = {e.get("hash") for e in entries}
            if hash_ is None:
                hash_ = new_hash()
                while hash_ in used:
                    hash_ = new_hash()
            elif hash_ in used:
                raise AccessError("invalid_hash")
            entry = {
                "repository": repository,
                "user": user,
                "hash": hash_,
                "created": utc_timestamp(),
                "source": source,
            }
            entries.append(entry)
            self.paths.access_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.paths.access_file, doc)
            return dict(entry)

    def get(self, repository: str, user: str) -> dict[str, Any] | None:  # RED stub
        return None

    def list_entries(self, repository: str | None = None) -> list[dict[str, Any]]:  # RED stub
        return []

    def revoke(self, repository: str, user: str, specs: Iterable[RepoSpec] | None = None) -> bool:  # RED stub
        return False

    def reconcile(self, specs: Iterable[RepoSpec]) -> int:
        with self.locked():
            return reconcile_tree(self.entries(), specs, self.paths, self.log)


def reconcile_tree(
    entries: Iterable[dict[str, Any]], specs: Iterable[RepoSpec], paths: Paths, log: logging.Logger
) -> int:
    """Make the symlink tree under access_root equal to the entries of configured repositories."""
    configured = {spec.key: spec for spec in specs}
    want: dict[Path, Path] = {}
    for entry in entries:
        repository = entry.get("repository")
        user = entry.get("user")
        hash_ = entry.get("hash")
        spec = configured.get(repository.lower()) if isinstance(repository, str) else None
        if spec is None:
            continue
        if not isinstance(hash_, str) or not HASH_RE.match(hash_):
            log.warning("skipping access entry with invalid hash: %s / %s", repository, user)
            continue
        target = paths.repo_dir(spec.owner, spec.name).absolute()
        want[paths.link_path(spec.owner, spec.name, hash_)] = target

    root = paths.access_root
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o711)
    for link, target in want.items():
        for directory in (link.parent.parent, link.parent):
            directory.mkdir(exist_ok=True)
            os.chmod(directory, 0o711)
        if link.is_symlink() and os.readlink(link) == str(target):
            continue
        tmp = link.with_name(f".{link.name}.tmp")
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        tmp.symlink_to(target)
        os.replace(tmp, link)  # atomic swap: a valid user never sees a missing link

    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames + dirnames:
            path = Path(dirpath) / name
            if (path.is_symlink() or path.is_file()) and path not in want:
                path.unlink()
        # never descend into hash links (they point at repositories)
        dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink() and (Path(dirpath) / d).is_dir()]
    return len(want)
