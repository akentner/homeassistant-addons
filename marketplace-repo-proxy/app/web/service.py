"""Service layer of the management page: token-free options, repository overview, Sync now, build version, access.

The GUI keeps only non-secret options: `GuiConfig.options` always has `github_token == ""` (D-07). Sync state comes from
`/data/status.json` (single writer `sync`, atomic replace, no lock needed; D-17) and the optional registration state
from the isolated reader in `app.web.registration` (D-19). The add-on version is read once at start from the file the
image build writes (D-30); no Supervisor call and no environment variable are involved.

Access (MRP-14): `/data/access.json` is written only through `AccessStore` (D-09, D-10). Every read goes through
`read_entries_safe` (never renames the file, WR-04), and every write first runs it inside the same store lock, so an
unreadable file is refused instead of replaced by a file holding only the new user. The list never carries a hash or a
URL; store URLs are built with `app.urls.store_urls` only for the add, URL and rotate responses (D-16), never logged.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import socket
import time
from pathlib import Path
from typing import Any, Callable

from app.access import HASH_RE, RESERVED_USERS, SOURCES, USER_RE, AccessError, AccessStore
from app.accessread import read_entries_safe
from app.jsonio import atomic_write_json
from app.logsetup import mask_hashes
from app.options import Options, RepoSpec, load_options, parse_repository
from app.paths import Paths
from app.status import BRANCH_SOURCES, STATUS_CODES, read_status
from app.urls import store_urls
from app.web.admin_ui import ApiError
from app.web.registration import REGISTRATION_STATES, read_registration

LOG = logging.getLogger("mrp.gui")

VERSION_FILE = Path("/opt/marketplace-repo-proxy/BUILD_VERSION")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-[0-9]+$")
_VERSION_MAX = 32
DETAIL_MAX = 200
_SYNC_TEXT_FIELDS = ("state", "last_started", "last_finished", "next_due", "reason")
_ROW_TEXT_FIELDS = ("last_attempt", "last_success", "last_change", "head")


def read_build_version(path: Path = VERSION_FILE) -> str | None:
    """The full add-on version (`X.Y.Z-N`) written at build time, or None: never a guessed or partial version."""
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if len(text) > _VERSION_MAX or not _VERSION_RE.fullmatch(text):
        return None
    return text


@dataclasses.dataclass(frozen=True)
class GuiConfig:
    options: Options  # github_token is always "" here
    hostname: str
    version: str | None = None


def load_gui_config(paths: Paths, hostname: str | None = None, version_file: Path = VERSION_FILE) -> GuiConfig:
    """Options without the credential (OptionsError propagates), host name and build version, read once at start."""
    options = load_options(paths.options_file)
    safe = dataclasses.replace(options, github_token="")
    del options
    return GuiConfig(safe, hostname or socket.gethostname(), read_build_version(version_file))


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _label(value: Any) -> str:
    """A user label for a log line: only labels that pass USER_RE (no control characters, no hash-like junk)."""
    return value if isinstance(value, str) and USER_RE.fullmatch(value) else "<invalid>"


def _repo_label(value: str) -> str:
    """An unconfigured repository for a log line: only a valid `owner/repo`."""
    try:
        parse_repository(value)
    except (TypeError, ValueError):
        return "<invalid>"
    return value


def _matches(entry: dict[str, Any], key: str, user: str) -> bool:
    """Stored repository equal to `key` case-insensitively, user label exact (same rule as AccessStore)."""
    repository = entry.get("repository")
    return isinstance(repository, str) and repository.lower() == key and entry.get("user") == user


def _protected(entry: dict[str, Any], user: str) -> bool:
    """System users (Phase 2's `local`) and reserved labels belong to the add-on, never to the GUI (D-13)."""
    return entry.get("source") == "system" or user.lower() in RESERVED_USERS


def _check_confirm(user: str, confirm: Any) -> None:
    """Type-to-confirm (D-12, R-04): the exact label, compared byte for byte; no trimming, no case folding."""
    if not isinstance(confirm, str) or not isinstance(user, str) or confirm != user:
        raise ApiError("confirmation_required", "type the user label to confirm")


def _check_not_protected(entry: dict[str, Any], user: str) -> None:
    if _protected(entry, user):
        raise ApiError("protected", "system users are managed by the add-on")


def _user_row(entry: dict[str, Any]) -> dict[str, Any]:
    """Label, source, created and the protected flag; never the hash."""
    user, source = entry["user"], entry.get("source")
    return {
        "user": user,
        "source": source if source in SOURCES else None,
        "created": _text(entry.get("created")),
        "protected": _protected(entry, user),
    }


class GuiService:
    def __init__(
        self,
        paths: Paths,
        config: GuiConfig,
        clock: Callable[[], float] = time.time,
        registration: Callable[[Paths], dict | None] = read_registration,
    ) -> None:
        self.paths = paths
        self.config = config
        self.clock = clock
        self.registration = registration

    def _registrations(self) -> dict | None:
        try:
            result = self.registration(self.paths)
        except Exception as exc:  # noqa: BLE001 - a broken reader means "no data", never a failed overview
            LOG.error("registration reader failed (%s)", type(exc).__name__)
            return None
        return result if isinstance(result, dict) else None

    @staticmethod
    def _registration_value(value: Any) -> dict[str, str] | None:
        if not isinstance(value, dict) or value.get("state") not in REGISTRATION_STATES:
            return None
        result = {"state": value["state"]}
        detail = value.get("detail")
        if isinstance(detail, str):
            result["detail"] = mask_hashes(detail)[:DETAIL_MAX]
        return result

    def _sync(self, doc: dict | None) -> dict[str, Any]:
        raw = doc.get("sync") if doc is not None else None
        raw = raw if isinstance(raw, dict) else {}
        sync: dict[str, Any] = {key: _text(raw.get(key)) for key in _SYNC_TEXT_FIELDS}
        interval = raw.get("interval_minutes")
        valid = isinstance(interval, int) and not isinstance(interval, bool)
        sync["interval_minutes"] = interval if valid else self.config.options.sync_interval
        sync["requested"] = self.paths.trigger_file.exists()
        return sync

    @staticmethod
    def _entries(doc: dict | None) -> list[dict]:
        entries = doc.get("repositories") if doc is not None else None
        return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []

    def overview(self) -> dict[str, Any]:
        doc = read_status(self.paths)
        entries = self._entries(doc)
        registrations = self._registrations()
        rows: list[dict[str, Any]] = []
        for spec in self.config.options.repositories:
            entry = next(
                (e for e in entries if isinstance(e.get("repository"), str) and e["repository"].lower() == spec.key),
                {},
            )
            branch_source = entry.get("branch_source")
            status = entry.get("status")
            addons = entry.get("addons")
            row: dict[str, Any] = {
                "repository": spec.slug,
                "branch": entry["branch"] if isinstance(entry.get("branch"), str) else spec.branch,
                "branch_source": branch_source if branch_source in BRANCH_SOURCES else None,
                "status": status if status in STATUS_CODES else None,
                "message": entry["message"] if isinstance(entry.get("message"), str) else "",
            }
            row.update({key: _text(entry.get(key)) for key in _ROW_TEXT_FIELDS})
            row["addons"] = [a for a in addons if isinstance(a, str)] if isinstance(addons, list) else []
            row["registration"] = self._registration_value(registrations.get(spec.key)) if registrations else None
            rows.append(row)
        return {
            "now_ms": int(self.clock() * 1000),
            "status_available": doc is not None,
            "sync": self._sync(doc),
            "repositories": rows,
        }

    # --- access (MRP-14) --------------------------------------------------------------------------------------------

    def _store(self) -> AccessStore:
        return AccessStore(self.paths)

    def _spec(self, repository: Any) -> RepoSpec | None:
        """The configured spec for `owner/repo`, matched case-insensitively and without trimming."""
        if not isinstance(repository, str):
            return None
        wanted = repository.lower()
        return next((spec for spec in self.config.options.repositories if spec.key == wanted), None)

    def _require_spec(self, repository: Any) -> RepoSpec:
        spec = self._spec(repository)
        if spec is None:
            raise AccessError("repository_unknown")
        return spec

    def _urls(self, spec: RepoSpec, hash_: str) -> dict[str, str]:
        return store_urls(self.config.options, self.config.hostname, spec.owner, spec.name, hash_)

    def access_list(self) -> dict[str, Any]:
        """Configured repositories in options order (active), then unconfigured ones found in access.json (inactive).

        `AccessUnavailable` propagates (503 access_unavailable); the file is never renamed. No hash, no URL.
        """
        entries = read_entries_safe(self._store())
        groups: dict[str, dict[str, Any]] = {
            spec.key: {"repository": spec.slug, "active": True, "users": []}
            for spec in self.config.options.repositories
        }
        inactive: dict[str, dict[str, Any]] = {}
        for entry in entries:
            repository, user = entry.get("repository"), entry.get("user")
            if not isinstance(repository, str) or not isinstance(user, str):
                continue
            try:
                parse_repository(repository)
            except (TypeError, ValueError):
                continue
            key = repository.lower()
            group = groups.get(key)
            if group is None:
                group = inactive.setdefault(key, {"repository": repository, "active": False, "users": []})
            group["users"].append(_user_row(entry))
        rows = list(groups.values()) + [inactive[key] for key in sorted(inactive)]
        for row in rows:
            row["users"].sort(key=lambda u: u["user"])
        return {"now_ms": int(self.clock() * 1000), "repositories": rows}

    def add_user(self, repository: str, user: Any) -> dict[str, Any]:
        """New entry with source "gui" and a new random hash; the response carries its store URLs (D-08, D-16)."""
        spec = self._require_spec(repository)
        store = self._store()
        with store.locked():
            read_entries_safe(store)  # an unreadable file is refused, never replaced (03-RESEARCH Pitfall 2)
            entry = store.add(spec.slug, user, source="gui", specs=self.config.options.repositories)
        LOG.info("gui: added user %s to %s", _label(entry["user"]), spec.slug)
        return {
            "repository": spec.slug,
            "user": entry["user"],
            "source": entry["source"],
            "created": entry["created"],
            "urls": self._urls(spec, entry["hash"]),
        }

    def user_urls(self, repository: str, user: str) -> dict[str, str]:
        """Store URLs of one user of a configured repository (on demand only, never in the list, never logged)."""
        spec = self._require_spec(repository)
        entries = read_entries_safe(self._store())
        entry = next((e for e in entries if _matches(e, spec.key, user)), None)
        if entry is None:
            raise AccessError("user_unknown")
        hash_ = entry.get("hash")
        if not isinstance(hash_, str) or not HASH_RE.fullmatch(hash_):
            raise AccessError("invalid_hash")
        return self._urls(spec, hash_)

    def revoke_user(self, repository: str, user: str, confirm: Any) -> None:
        """Remove the entry and its link in one locked operation (D-09, D-11); unconfigured repositories too (as the CLI).

        The URL answers 404 from the next request on. System users are refused with `protected` (D-13).
        """
        spec = self._spec(repository)
        target = spec.slug if spec is not None else repository
        _check_confirm(user, confirm)
        store = self._store()
        with store.locked():
            entries = read_entries_safe(store)
            entry = next((e for e in entries if _matches(e, target.lower(), user)), None)
            if entry is None:
                raise AccessError("user_unknown")
            _check_not_protected(entry, user)
            if not store.revoke(target, user, specs=self.config.options.repositories):
                raise AccessError("user_unknown")
        LOG.info("gui: revoked user %s from %s", _label(user), spec.slug if spec is not None else _repo_label(target))

    def rotate_user(self, repository: str, user: str, confirm: Any) -> dict[str, Any]:
        """A new random hash for an existing (repository, user): revoke + add inside ONE store lock (D-10, D-11).

        Every check runs before the first write. A concurrent locked reader never sees the user missing; git clients
        see the old link go before the new one exists, never both. When `add` fails after the revoke, the old hash is
        re-added and the error re-raised. `created` is reset, `source` kept, unknown fields of the entry are dropped. A
        process crash between the two writes leaves the user without access (fail closed); recovery is a new add.
        """
        spec = self._require_spec(repository)
        _check_confirm(user, confirm)
        specs = self.config.options.repositories
        store = self._store()
        with store.locked():
            entries = read_entries_safe(store)
            entry = next((e for e in entries if _matches(e, spec.key, user)), None)
            if entry is None:
                raise AccessError("user_unknown")
            _check_not_protected(entry, user)
            source = entry.get("source")
            if source not in SOURCES or not USER_RE.fullmatch(user):
                raise AccessError("invalid_user")  # validated BEFORE the revoke: add() must not fail afterwards
            old_hash = entry.get("hash")
            store.revoke(spec.slug, user, specs=specs)
            try:
                new = store.add(spec.slug, user, source=source, specs=specs)
            except Exception:
                if isinstance(old_hash, str) and HASH_RE.fullmatch(old_hash):
                    store.add(spec.slug, user, source=source, hash_=old_hash, specs=specs)
                raise
        LOG.info("gui: rotated user %s of %s", _label(user), spec.slug)
        return {
            "repository": spec.slug,
            "user": new["user"],
            "source": new["source"],
            "created": new["created"],
            "urls": self._urls(spec, new["hash"]),
        }

    def meta(self) -> dict[str, Any]:
        return {"version": self.config.version}

    def request_sync(self) -> dict[str, Any]:
        """Create the Phase 1 trigger file (same as `mrp sync`); the sync service starts a full cycle within a second."""
        if not self.paths.run_dir.is_dir():
            self.paths.run_dir.mkdir(parents=True, exist_ok=True)
            self.paths.run_dir.chmod(0o700)
        atomic_write_json(self.paths.trigger_file, {})
        LOG.info("gui: sync requested")
        return {"requested": True}
