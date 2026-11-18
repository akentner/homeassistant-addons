"""Access store for /data/access.json (MRP-04, contract D-20) and the symlink tree that authorizes clones (D-06).

Document: {"schema": 1, "entries": [{"repository", "user", "hash", "created", "source"}]}. `AccessStore` is the only
writer API (CLI now, GUI and API in one process later). Every read, and every read-modify-write, holds one lock
(process RLock plus flock on /run/marketplace-repo-proxy/access.lock) and replaces the file atomically. Unknown
top-level keys and entry fields are preserved. A corrupt file is renamed to access.json.corrupt and the store starts
empty (fail closed); a newer schema is refused and never written. No hash is ever logged.
"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import logging
import os
import re
import secrets
import shutil
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
RESERVED_USERS = frozenset({"local"})  # Phase 2's system user; only source "system" may use these labels

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


def _matches(entry: dict[str, Any], repository: str, user: str) -> bool:
    """Repository case-insensitive, user label exact."""
    value = entry.get("repository")
    return isinstance(value, str) and value.lower() == repository.lower() and entry.get("user") == user


def _sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    repository, user = entry.get("repository"), entry.get("user")
    return (repository.lower() if isinstance(repository, str) else "", user if isinstance(user, str) else "")


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
                os.fchmod(fd, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX)
                _HELD.depth = 1
                yield
            finally:
                _HELD.depth = 0
                os.close(fd)

    def load(self) -> dict[str, Any]:
        """The document as stored; call under `locked()` (the corrupt-file rename must not race a writer)."""
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
        # content-free on purpose: the file holds hashes
        self.log.error("access.json is corrupt; moved to access.json.corrupt, starting with no users")
        try:
            os.replace(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            pass
        return _empty()

    def entries(self) -> list[dict[str, Any]]:
        with self.locked():
            return list(self.load()["entries"])

    def get(self, repository: str, user: str) -> dict[str, Any] | None:
        """A copy of the entry for (repository, user), or None."""
        if not isinstance(repository, str) or not isinstance(user, str):
            return None
        with self.locked():
            for entry in self.load()["entries"]:
                if _matches(entry, repository, user):
                    return copy.deepcopy(entry)
        return None

    def list_entries(self, repository: str | None = None) -> list[dict[str, Any]]:
        """Copies of all entries (or those of one repository), sorted by repository (case-insensitive) and user."""
        with self.locked():
            entries = self.load()["entries"]
        if repository is not None:
            wanted = repository.lower()
            entries = [
                e for e in entries if isinstance(e.get("repository"), str) and e["repository"].lower() == wanted
            ]
        return [copy.deepcopy(e) for e in sorted(entries, key=_sort_key)]

    def add(
        self,
        repository: str,
        user: str,
        source: str = "cli",
        hash_: str | None = None,
        specs: Iterable[RepoSpec] | None = None,
    ) -> dict[str, Any]:
        """Append one entry (re-reads the file under the lock); unknown keys and fields are kept untouched.

        With `specs`, the symlink tree is reconciled inside the same lock.
        """
        try:
            parse_repository(repository)
        except (TypeError, ValueError):
            raise AccessError("repository_unknown") from None
        if not isinstance(user, str) or not USER_RE.fullmatch(user):
            raise AccessError("invalid_user")
        if source not in SOURCES:
            raise AccessError("invalid_source")
        if user.lower() in RESERVED_USERS and source != "system":
            raise AccessError("user_reserved")
        if hash_ is not None and (not isinstance(hash_, str) or not HASH_RE.fullmatch(hash_)):
            raise AccessError("invalid_hash")
        with self.locked():
            doc = self.load()
            entries = doc["entries"]
            if any(_matches(e, repository, user) for e in entries):
                raise AccessError("user_exists")
            used = {e.get("hash") for e in entries}
            if hash_ is None:
                hash_ = new_hash()
                while hash_ in used:
                    hash_ = new_hash()
            elif hash_ in used:
                raise AccessError("hash_conflict")
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
            if specs is not None:
                reconcile_tree(entries, specs, self.paths, self.log)
            return dict(entry)

    def revoke(self, repository: str, user: str, specs: Iterable[RepoSpec] | None = None) -> bool:
        """Remove the entry and its symlink in one locked operation (D-06: 404 at the next request).

        Returns False, writing nothing, when no entry matches. With `specs`, the tree is also reconciled.
        """
        if not isinstance(repository, str) or not isinstance(user, str):
            return False
        with self.locked():
            doc = self.load()
            removed = [e for e in doc["entries"] if _matches(e, repository, user)]
            if not removed:
                return False
            doc["entries"] = [e for e in doc["entries"] if not _matches(e, repository, user)]
            atomic_write_json(self.paths.access_file, doc)
            for entry in removed:
                _unlink_hash(self.paths.access_root, entry.get("hash"))
            if specs is not None:
                reconcile_tree(doc["entries"], specs, self.paths, self.log)
            return True

    def reconcile(self, specs: Iterable[RepoSpec]) -> int:
        with self.locked():
            return reconcile_tree(self.load()["entries"], specs, self.paths, self.log)


def _unlink_hash(root: Path, hash_: Any) -> None:
    """Unlink every `{root}/*/*/{hash}` symlink; real directories only, never a glob built from file content."""
    if not isinstance(hash_, str) or not HASH_RE.fullmatch(hash_) or not root.is_dir():
        return
    for owner in root.iterdir():
        if owner.is_symlink() or not owner.is_dir():
            continue
        for repo in owner.iterdir():
            if repo.is_symlink() or not repo.is_dir():
                continue
            candidate = repo / hash_
            if candidate.is_symlink():
                candidate.unlink()


def _log_label(value: Any, valid: bool) -> str:
    return value if valid else "<invalid>"


def _ensure_dir(directory: Path) -> None:
    """A real directory with mode 0711 (anything else at that path is removed first)."""
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        directory.unlink()
    directory.mkdir(exist_ok=True)
    os.chmod(directory, 0o711)  # explicit: mkdir modes are umask-bound


def reconcile_tree(
    entries: Iterable[dict[str, Any]], specs: Iterable[RepoSpec], paths: Paths, log: logging.Logger
) -> int:
    """Make the symlink tree under access_root equal to the valid entries of configured repositories.

    Link paths use the configured owner/repo case and only hashes matching HASH_RE. Skipped entries stay in the file;
    their log line names repository and user only, never the hash.
    """
    configured = {spec.key: spec for spec in specs}
    want: dict[Path, Path] = {}
    for entry in entries:
        repository, user, hash_ = entry.get("repository"), entry.get("user"), entry.get("hash")
        try:
            parse_repository(repository)  # type: ignore[arg-type]
            repo_ok = True
        except (TypeError, ValueError):
            repo_ok = False
        user_ok = isinstance(user, str) and bool(USER_RE.fullmatch(user))
        label = (_log_label(repository, repo_ok), _log_label(user, user_ok))
        if not repo_ok:
            log.warning("access entry for %s/%s skipped: invalid repository", *label)
            continue
        spec = configured.get(repository.lower())
        if spec is None:
            log.debug("access entry for %s/%s skipped: repository not configured", *label)
            continue
        if not isinstance(hash_, str) or not HASH_RE.fullmatch(hash_):
            log.warning("access entry for %s/%s skipped: invalid hash", *label)
            continue
        target = paths.repo_dir(spec.owner, spec.name).absolute()
        want[paths.link_path(spec.owner, spec.name, hash_)] = target

    root = paths.access_root
    root.parent.mkdir(parents=True, exist_ok=True)
    _ensure_dir(root)
    for link, target in want.items():
        for directory in (link.parent.parent, link.parent):
            _ensure_dir(directory)
        if link.is_symlink() and os.readlink(link) == str(target):
            continue
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
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
