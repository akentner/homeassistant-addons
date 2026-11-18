"""/data/supervisor.json: the store registration contract read by the Phase 3 GUI (D-10, D-28, D-29).

Single writer: the sync process. Every write is an atomic replace with mode 0600. The file holds store slugs and
masked URLs only, never a full access hash, a full store URL or a token.

Phase 3 interface (D-29): top-level `repositories`, one object per configured repository in options order, then one
per unconfigured repository whose store repository is still recorded (`configured: false`). Each object starts with
`repository`, `registration` (exactly one of REGISTRATION_STATES, D-28) and an optional `message` from fixed templates.
Callers report facts (`in_store`, `error`); `registration` and `message` are recomputed from them on every write, so no
code path can store another value or free text.

`reload` records the last `POST /store/reload` (MRP-09, D-08): `last_requested` (UTC), `last_result` (`ok`, `failed` or
None), `pending` (a reload is still owed; survives a restart) and a masked `message`. The caller masks Supervisor text
with `app.supervisor.mask_text`; this module masks every 32-hex run again with `app.gitops.sanitize` (the masker
`mask_text` builds on) and never imports the client module (only registration and sync may, see test_supervisor).

`leftovers` lists store repositories the proxy registered and could not remove (MRP-10, D-09, D-10): `repository`,
`store_slug`, `user` (the access label that serves it, or None), `masked_url`, `since`, `reason` (one of
LEFTOVER_REASONS), a masked `message` and `revoked`. A repository with a leftover has the registration `leftover` (D-28).
`requests` keeps the results of the last MAX_REQUESTS operator requests (`id`, `action`, `repository`, `result`,
`code`, `finished`); `mrp local` waits for its id there.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Iterable, Sequence

from app.gitops import sanitize
from app.jsonio import atomic_write_json, read_json, utc_timestamp
from app.options import RepoSpec
from app.paths import Paths

SCHEMA = 1
REGISTRATION_STATES = ("registered", "missing", "leftover", "error")
ERROR_CODES = ("add_rejected", "store_list_unavailable", "timeout", "unreachable", "token_missing", "internal_error")
UNSAFE_MESSAGE_RE = re.compile(r"https?://|/repo/|[0-9a-fA-F]{32}|github_pat_|gh[pousr]_|Bearer ")
MESSAGE_FALLBACK = "Details are in the add-on log"
MESSAGE_LIMIT = 200
_HEX32_RE = re.compile(r"[0-9a-fA-F]{32}")
RELOAD_RESULTS = (None, "ok", "failed")
LEFTOVER_REASONS = ("in_use", "error", "interrupted", "orphaned")
REQUEST_RESULTS = ("done", "refused", "failed", "rejected")
MAX_REQUESTS = 20
_SLUG_RE = re.compile(r"[0-9a-f]{8}")
_UNSET: Any = object()

_ERROR_MESSAGES = {
    "add_rejected": "The Supervisor rejected the store URL (HTTP {status})",
    "store_list_unavailable": "Store list unavailable (HTTP {status})",
    "timeout": "The Supervisor did not answer in time",
    "unreachable": "The Supervisor is unreachable",
    "token_missing": "No Supervisor token in the add-on environment",
    "internal_error": "Internal error; see the add-on log",
}


def registration_value(*, in_store: bool, error: str | None, configured: bool, has_leftover: bool) -> str:
    """The D-28 value from four facts; first match wins: error > leftover > registered > missing."""
    if error:
        return "error"
    if has_leftover or (not configured and in_store):
        return "leftover"
    if in_store:
        return "registered"
    return "missing"


def registration_message(
    value: str,
    *,
    error: str | None,
    error_status: int | None,
    register_local: bool,
    configured: bool,
    leftover_reasons: Sequence[str],
) -> str | None:
    """Fixed English text for a registration value (D-29); never built from Supervisor text."""
    if value == "missing":
        if not register_local:
            return "Registration is turned off (register_local: false)"
        return "Not in the store yet; added after the next successful sync"
    if value == "leftover":
        reasons = sorted({r for r in leftover_reasons if isinstance(r, str) and r})
        if not configured or not reasons:
            return "No longer configured; its store repository is still listed"
        count = len(list(leftover_reasons))
        noun = "repository" if count == 1 else "repositories"
        return f"{count} old store {noun} left ({', '.join(reasons)}); see mrp local status"
    if value == "error":
        template = _ERROR_MESSAGES.get(error or "", _ERROR_MESSAGES["internal_error"])
        status = error_status if isinstance(error_status, int) and not isinstance(error_status, bool) else "?"
        return template.format(status=status)
    return None


def safe_message(text: str | None) -> str | None:
    """One line of at most MESSAGE_LIMIT characters; anything URL-, hash- or token-like becomes MESSAGE_FALLBACK."""
    if not isinstance(text, str):
        return None
    line = " ".join(text.split())
    if not line:
        return None
    if UNSAFE_MESSAGE_RE.search(line):
        return MESSAGE_FALLBACK
    if len(line) > MESSAGE_LIMIT:
        line = line[: MESSAGE_LIMIT - 1] + "…"
    return line


def read_supervisor_state(paths: Paths) -> dict | None:
    """The current document, or None when it is missing, unreadable or not a JSON object."""
    try:
        doc = read_json(paths.supervisor_state_file)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _new_entry(repository: str, configured: bool = True) -> dict[str, Any]:
    return {
        "repository": repository,
        "configured": configured,
        "in_store": False,
        "error": None,
        "error_status": None,
        "store_slug": None,
        "masked_url": "",
        "registered_at": None,
        "last_checked": None,
    }


def _carry(entry: dict[str, Any], old: dict) -> None:
    """Copy facts of the previous file, ignoring values of the wrong type; never `registration` or `message`."""
    if isinstance(old.get("in_store"), bool):
        entry["in_store"] = old["in_store"]
    if old.get("error") in ERROR_CODES:
        entry["error"] = old["error"]
        if _is_int(old.get("error_status")):
            entry["error_status"] = old["error_status"]
    if isinstance(old.get("store_slug"), str):
        entry["store_slug"] = old["store_slug"]
    masked = old.get("masked_url")
    if isinstance(masked, str) and not _HEX32_RE.search(masked):  # never carry a full hash
        entry["masked_url"] = masked
    for key in ("registered_at", "last_checked"):
        if isinstance(old.get(key), str):
            entry[key] = old[key]


def _reload_section(old: Any) -> dict[str, Any]:
    """The reload section of the previous file, ignoring values of the wrong type; the message is masked again."""
    section: dict[str, Any] = {"last_requested": None, "last_result": None, "pending": False, "message": ""}
    if not isinstance(old, dict):
        return section
    if isinstance(old.get("last_requested"), str):
        section["last_requested"] = old["last_requested"]
    if old.get("last_result") in RELOAD_RESULTS:
        section["last_result"] = old["last_result"]
    if isinstance(old.get("pending"), bool):
        section["pending"] = old["pending"]
    if isinstance(old.get("message"), str):
        section["message"] = sanitize(old["message"])
    return section


def _dict_list(value: Any) -> list[dict] | None:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return copy.deepcopy(value)
    return None


def _masked_url(value: Any) -> str:
    return value if isinstance(value, str) and not _HEX32_RE.search(value) else ""


def _leftover(old: Any) -> dict[str, Any] | None:
    """A carried leftover with typed fields only, or None when it names no repository or no valid store slug."""
    if not isinstance(old, dict) or not isinstance(old.get("repository"), str):
        return None
    slug = old.get("store_slug")
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        return None
    user = old.get("user")
    return {
        "repository": old["repository"],
        "store_slug": slug,
        "user": user if isinstance(user, str) and not _HEX32_RE.search(user) else None,
        "masked_url": _masked_url(old.get("masked_url")),
        "since": old["since"] if isinstance(old.get("since"), str) else None,
        "reason": old["reason"] if old.get("reason") in LEFTOVER_REASONS else "error",
        "message": sanitize(old["message"]) if isinstance(old.get("message"), str) else "",
        "revoked": old.get("revoked") is True,
    }


class SupervisorStateWriter:
    """Owns supervisor.json for one sync process; seeded from the previous file and written once at construction."""

    def __init__(self, paths: Paths, *, hostname: str, register_local: bool, specs: Iterable[RepoSpec]) -> None:
        self._paths = paths
        previous = read_supervisor_state(paths) or {}
        old_hostname = previous.get("hostname")
        self.previous_hostname: str | None = old_hostname if isinstance(old_hostname, str) else None
        old_entries: dict[str, dict] = {}
        if isinstance(previous.get("repositories"), list):
            for item in previous["repositories"]:
                if isinstance(item, dict) and isinstance(item.get("repository"), str):
                    old_entries.setdefault(item["repository"].lower(), item)

        self._entries: dict[str, dict[str, Any]] = {}
        for spec in specs:
            entry = _new_entry(spec.slug)
            old = old_entries.get(spec.key)
            if old is not None:
                _carry(entry, old)
            self._entries[spec.key] = entry
        for key, old in old_entries.items():
            if key in self._entries or not isinstance(old.get("store_slug"), str):
                continue
            entry = _new_entry(old["repository"], configured=False)
            _carry(entry, old)
            self._entries[key] = entry

        self._doc: dict[str, Any] = {
            "schema": SCHEMA,
            "updated": None,
            "register_local": bool(register_local),
            "hostname": hostname,
            "supervisor": {"last_contact": None, "last_status": None, "last_error": None},
            "reload": _reload_section(previous.get("reload")),
            "repositories": [],
            "leftovers": [],
            "requests": (_dict_list(previous.get("requests")) or [])[-MAX_REQUESTS:],
        }
        carried = previous.get("leftovers")
        for old in carried if isinstance(carried, list) else []:
            item = _leftover(old)
            if item is not None and all(o["store_slug"] != item["store_slug"] for o in self._doc["leftovers"]):
                self._doc["leftovers"].append(item)
        self._write()

    def _leftovers_of(self, key: str) -> list[dict]:
        return [
            item
            for item in self._doc["leftovers"]
            if isinstance(item.get("repository"), str) and item["repository"].lower() == key
        ]

    def _render(self, key: str, entry: dict[str, Any]) -> dict[str, Any]:
        leftovers = self._leftovers_of(key)
        value = registration_value(
            in_store=bool(entry["in_store"]),
            error=entry["error"],
            configured=bool(entry["configured"]),
            has_leftover=bool(leftovers),
        )
        message = safe_message(
            registration_message(
                value,
                error=entry["error"],
                error_status=entry["error_status"],
                register_local=self._doc["register_local"],
                configured=bool(entry["configured"]),
                leftover_reasons=[str(item.get("reason") or "") for item in leftovers],
            )
        )
        rendered: dict[str, Any] = {"repository": entry["repository"], "registration": value}
        if message is not None:
            rendered["message"] = message
        rendered.update({k: v for k, v in entry.items() if k != "repository"})
        return rendered

    def _write(self) -> None:
        """The only write path: recompute every `registration` and `message`, then replace the file atomically."""
        self._doc["updated"] = utc_timestamp()
        self._doc["repositories"] = [self._render(key, entry) for key, entry in self._entries.items()]
        self._paths.supervisor_state_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._paths.supervisor_state_file, self._doc)

    def snapshot(self) -> dict:
        """Deep copy of the document as last written."""
        return copy.deepcopy(self._doc)

    def repository(self, repository: str) -> dict | None:
        """The rendered object of one repository (as last written), or None."""
        wanted = repository.lower()
        for item in self._doc["repositories"]:
            if item["repository"].lower() == wanted:
                return copy.deepcopy(item)
        return None

    def set_repository(
        self,
        repository: str,
        *,
        in_store: bool,
        error: str | None = None,
        error_status: int | None = None,
        store_slug: str | None = None,
        masked_url: str = "",
        configured: bool = True,
    ) -> None:
        """Record the facts of one check or add; `error` is None or a code from ERROR_CODES."""
        if error is not None and error not in ERROR_CODES:
            raise ValueError(f"unknown error code: {error}")
        key = repository.lower()
        entry = self._entries.get(key)
        if entry is None:
            entry = self._entries[key] = _new_entry(repository, configured=configured)
        now = utc_timestamp()
        if in_store and (not entry["in_store"] or entry["store_slug"] != store_slug):
            entry["registered_at"] = now
        entry.update(
            {
                "configured": bool(configured),
                "in_store": bool(in_store),
                "error": error,
                "error_status": error_status if error is not None and _is_int(error_status) else None,
                "store_slug": store_slug,
                "masked_url": masked_url,
                "last_checked": now,
            }
        )
        self._write()

    def set_contact(self, status: int, error: str | None) -> None:
        """Result of the last Supervisor contact attempt (`status` 0: no HTTP answer); `error` is masked text."""
        self._doc["supervisor"] = {"last_contact": utc_timestamp(), "last_status": status, "last_error": error}
        self._write()

    def reload_state(self) -> dict:
        """Copy of the `reload` section as last written."""
        return copy.deepcopy(self._doc["reload"])

    def set_reload(
        self,
        *,
        last_requested: str | None = _UNSET,
        last_result: str | None = _UNSET,
        pending: bool = _UNSET,
        message: str = _UNSET,
    ) -> None:
        """Update the given fields of the `reload` section; `message` is masked Supervisor text, masked again here."""
        if last_result is not _UNSET and last_result not in RELOAD_RESULTS:
            raise ValueError(f"unknown reload result: {last_result}")
        section = self._doc["reload"]
        if last_requested is not _UNSET:
            section["last_requested"] = last_requested if isinstance(last_requested, str) else None
        if last_result is not _UNSET:
            section["last_result"] = last_result
        if pending is not _UNSET:
            section["pending"] = bool(pending)
        if message is not _UNSET:
            section["message"] = sanitize(message) if isinstance(message, str) else ""
        self._write()

    # --- leftovers and operator requests (MRP-10) -------------------------------------------------------------------

    def leftovers(self, repository: str | None = None) -> list[dict]:
        """Copies of all leftovers, or of one repository's (case-insensitive)."""
        items = self._doc["leftovers"] if repository is None else self._leftovers_of(repository.lower())
        return copy.deepcopy(items)

    def add_leftover(
        self,
        *,
        repository: str,
        store_slug: str,
        user: str | None,
        masked_url: str,
        reason: str,
        message: str = "",
        revoked: bool = False,
    ) -> None:
        """Record (or replace, keeping `since`) the leftover of one store slug; `message` is masked Supervisor text."""
        if reason not in LEFTOVER_REASONS:
            raise ValueError(f"unknown leftover reason: {reason}")
        if not isinstance(store_slug, str) or not _SLUG_RE.fullmatch(store_slug):
            raise ValueError("invalid store slug")
        items = self._doc["leftovers"]
        since = next((o.get("since") for o in items if o.get("store_slug") == store_slug), None)
        item = {
            "repository": repository,
            "store_slug": store_slug,
            "user": user if isinstance(user, str) else None,
            "masked_url": _masked_url(masked_url),
            "since": since if isinstance(since, str) else utc_timestamp(),
            "reason": reason,
            "message": sanitize(message) if isinstance(message, str) else "",
            "revoked": bool(revoked),
        }
        self._doc["leftovers"] = [o for o in items if o.get("store_slug") != store_slug] + [item]
        self._write()

    def drop_leftover(self, store_slug: str) -> bool:
        """Remove the leftover of one store slug; False (no write) when there is none."""
        items = self._doc["leftovers"]
        kept = [o for o in items if o.get("store_slug") != store_slug]
        if len(kept) == len(items):
            return False
        self._doc["leftovers"] = kept
        self._write()
        return True

    def unconfigured_repositories(self) -> list[str]:
        """Repository names of the recorded entries that are no longer configured."""
        return [entry["repository"] for entry in self._entries.values() if not entry["configured"]]

    def drop_repository(self, repository: str) -> bool:
        """Remove an unconfigured entry from the document; a configured repository is never dropped."""
        key = repository.lower()
        entry = self._entries.get(key)
        if entry is None or entry["configured"]:
            return False
        del self._entries[key]
        self._write()
        return True

    def record_request(self, *, id: str, action: str, repository: str, result: str, code: str = "") -> None:
        """Append the result of one operator request; keeps the last MAX_REQUESTS."""
        if result not in REQUEST_RESULTS:
            raise ValueError(f"unknown request result: {result}")
        item = {
            "id": id,
            "action": action,
            "repository": repository,
            "result": result,
            "code": code if isinstance(code, str) else "",
            "finished": utc_timestamp(),
        }
        self._doc["requests"] = (self._doc["requests"] + [item])[-MAX_REQUESTS:]
        self._write()
