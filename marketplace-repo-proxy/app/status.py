"""/data/status.json: the sync state contract read by the Phase 3 GUI (D-14, D-20, D-26).

Single writer: the sync service. Every write is an atomic replace with mode 0600, so readers never see a partial file
and need no lock. Field names are a contract: later phases may add fields but must not rename them.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Sequence

from app.gitops import sanitize
from app.jsonio import atomic_write_json, read_json, utc_timestamp
from app.options import RepoSpec
from app.paths import Paths

SCHEMA = 1
STATUS_CODES = ("pending", "ok", "auth_failed", "not_found", "no_repository_yaml", "fetch_failed")
REASONS = ("startup", "interval", "request")
BRANCH_SOURCES = ("configured", "upstream_default")
# A served mirror exists after these: head, add-ons and last_success move forward
SUCCESS_CODES = ("ok", "no_repository_yaml")
CARRIED_FIELDS = ("last_success", "last_change", "head", "addons")


def read_status(paths: Paths) -> dict | None:
    """The current status document, or None when it is missing, unreadable or not a JSON object."""
    try:
        doc = read_json(paths.status_file)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _previous_entries(paths: Paths) -> dict[str, dict]:
    doc = read_status(paths)
    entries = doc.get("repositories") if doc else None
    if not isinstance(entries, list):
        return {}
    previous: dict[str, dict] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("repository"), str):
            previous[entry["repository"].lower()] = entry
    return previous


def _carry(entry: dict, old: dict) -> None:
    """Copy the last good state of a still-configured repository, ignoring values of the wrong type."""
    for key in ("last_success", "last_change", "head"):
        if isinstance(old.get(key), str):
            entry[key] = old[key]
    addons = old.get("addons")
    if isinstance(addons, list) and all(isinstance(a, str) for a in addons):
        entry["addons"] = list(addons)


class StatusWriter:
    """Owns status.json for one sync process; seeded from the previous file at construction."""

    def __init__(
        self, paths: Paths, specs: Iterable[RepoSpec], upstream_overridden: bool, interval_minutes: int
    ) -> None:
        self._paths = paths
        previous = _previous_entries(paths)
        self._entries: dict[str, dict[str, Any]] = {}
        for spec in specs:
            entry: dict[str, Any] = {
                "repository": spec.slug,
                "branch": spec.branch,
                "branch_source": "configured" if spec.branch else "upstream_default",
                "status": "pending",
                "message": "",
                "last_attempt": None,
                "last_success": None,
                "last_change": None,
                "head": None,
                "addons": [],
                "refs_changed": False,
            }
            old = previous.get(spec.key)
            if old is not None:
                _carry(entry, old)
            self._entries[spec.key] = entry
        self._doc: dict[str, Any] = {
            "schema": SCHEMA,
            "updated": None,
            "upstream_override": bool(upstream_overridden),
            "sync": {
                "state": "idle",
                "last_started": None,
                "last_finished": None,
                "next_due": None,
                "interval_minutes": interval_minutes,
                "reason": None,
            },
        }
        self._write()

    def _write(self) -> None:
        self._doc["updated"] = utc_timestamp()
        self._doc["repositories"] = list(self._entries.values())
        self._paths.status_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._paths.status_file, self._doc)

    def snapshot(self) -> dict:
        """Deep copy of the document as last written."""
        return copy.deepcopy(self._doc)

    def begin_cycle(self, reason: str) -> None:
        if reason not in REASONS:
            raise ValueError(f"unknown sync reason: {reason}")
        self._doc["sync"].update({"state": "running", "last_started": utc_timestamp(), "reason": reason})
        self._write()

    def end_cycle(self, next_due_epoch: float | None) -> None:
        due = utc_timestamp(next_due_epoch) if next_due_epoch is not None else None
        self._doc["sync"].update({"state": "idle", "last_finished": utc_timestamp(), "next_due": due})
        self._write()

    def record(
        self,
        slug: str,
        *,
        status: str,
        message: str,
        branch: str | None,
        branch_source: str,
        head: str | None = None,
        addons: Sequence[str] | None = None,
        refs_changed: bool = False,
    ) -> None:
        """Result of one attempt. A failure keeps head, add-ons and last_success: the bare repo still serves them."""
        if status not in STATUS_CODES or status == "pending":
            raise ValueError(f"unknown status code: {status}")
        if branch_source not in BRANCH_SOURCES:
            raise ValueError(f"unknown branch source: {branch_source}")
        entry = self._entries.get(slug.lower())
        if entry is None:
            raise KeyError(f"repository not configured: {slug}")
        now = utc_timestamp()
        entry.update(
            {
                "branch": branch,
                "branch_source": branch_source,
                "status": status,
                "message": sanitize(message),
                "last_attempt": now,
                "refs_changed": bool(refs_changed) and status in SUCCESS_CODES,
            }
        )
        if status in SUCCESS_CODES:
            entry["last_success"] = now
            entry["head"] = head
            entry["addons"] = list(addons or [])
            if refs_changed:
                entry["last_change"] = now
        self._write()
