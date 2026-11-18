"""Last-fetch contract: /data/last-fetch.json (MRP-15, user decision D-21, option-a).

Document: {"schema": 1, "updated": <ts>, "entries": [{"repository": "owner/repo", "user": "<label>",
"last_fetch": <ts>}]}, no other key. Timestamps are ISO 8601 UTC with `Z`. Entries are keyed by (repository, user)
as stored in access.json and sorted by repository (case-insensitive) and user; the file never holds an access hash.

Single writer: the `fetchlog` service, through `atomic_write_json` (mode 0600, fsync, rename, directory fsync), so
readers need no lock. A reader treats a missing, unreadable, invalid or newer-schema file as "no records" and never
renames it. When to show a value (only after the entry's `created`) is the GUI's display rule, not part of this file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, NamedTuple

from app.access import USER_RE
from app.jsonio import atomic_write_json, read_json, utc_timestamp
from app.options import parse_repository
from app.paths import Paths

SCHEMA = 1
FILE_NAME = "last-fetch.json"
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class LastFetchRecord(NamedTuple):
    repository: str
    user: str
    last_fetch: str


def last_fetch_path(paths: Paths) -> Path:
    """`data_dir / FILE_NAME`; the frozen `Paths` dataclass is deliberately not extended (D-24)."""
    return paths.data_dir / FILE_NAME


def _valid_repository(value: Any) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    try:
        parse_repository(value)
    except (TypeError, ValueError):
        return False
    return True


def read_last_fetch(paths: Paths) -> dict[tuple[str, str], LastFetchRecord]:
    """Records keyed by (repository.lower(), user); `{}` for a missing or bad file. Never raises."""
    try:
        doc = read_json(last_fetch_path(paths))
    except Exception:  # unreadable, invalid JSON, too deeply nested: start without records, keep the file
        return {}
    if not isinstance(doc, dict):
        return {}
    schema, entries = doc.get("schema"), doc.get("entries")
    if not isinstance(schema, int) or isinstance(schema, bool) or schema > SCHEMA:
        return {}
    if not isinstance(entries, list):
        return {}
    records: dict[tuple[str, str], LastFetchRecord] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        repository, user, last_fetch = entry.get("repository"), entry.get("user"), entry.get("last_fetch")
        if not _valid_repository(repository):
            continue
        if not isinstance(user, str) or not USER_RE.fullmatch(user):
            continue
        if not isinstance(last_fetch, str) or not TIMESTAMP_RE.fullmatch(last_fetch):
            continue
        key = (repository.lower(), user)
        known = records.get(key)
        if known is None or last_fetch > known.last_fetch:
            records[key] = LastFetchRecord(repository, user, last_fetch)
    return records


def write_last_fetch(paths: Paths, records: Iterable[LastFetchRecord]) -> None:
    """Replace the file atomically with `records` (mode 0600); `data_dir` is created when missing."""
    path = last_fetch_path(paths)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    entries = [
        {"repository": r.repository, "user": r.user, "last_fetch": r.last_fetch}
        for r in sorted(records, key=lambda r: (r.repository.lower(), r.user))
    ]
    atomic_write_json(path, {"schema": SCHEMA, "updated": utc_timestamp(), "entries": entries})
