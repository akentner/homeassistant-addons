"""Non-destructive locked read of /data/access.json for frequent readers (GUI, fetchlog; D-09, D-10, WR-04).

`AccessStore.load()` treats any read error as corruption and renames the file to access.json.corrupt (fail closed,
Phase 1). That is right for the single reconciling service, but a reader that runs often (every GUI request, every
mapped fetch) would multiply the chance that a transient OSError or a hand edit caught mid-write wipes every user.
`read_entries_safe` holds the same store lock, never renames anything and raises `AccessUnavailable` instead;
`access-watch` keeps doing the fail-closed handling.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from app.access import SCHEMA, AccessStore
from app.jsonio import read_json


class AccessUnavailable(Exception):
    """access.json is unreadable, invalid or has a newer schema; never renamed from a read path."""


def read_entries_safe(store: AccessStore) -> list[dict[str, Any]]:
    """Deep copies of the stored entries, `[]` when the file is missing; raises `AccessUnavailable` otherwise."""
    with store.locked():
        try:
            doc = read_json(store.paths.access_file)
        except (OSError, ValueError):
            raise AccessUnavailable() from None
    if doc is None:
        return []
    if not isinstance(doc, dict):
        raise AccessUnavailable()
    schema, entries = doc.get("schema"), doc.get("entries")
    if not isinstance(schema, int) or isinstance(schema, bool):
        raise AccessUnavailable()
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise AccessUnavailable()
    if schema > SCHEMA:
        raise AccessUnavailable()
    return copy.deepcopy(entries)


def file_signature(path: Path) -> tuple[int, int, int] | None:
    """(st_ino, st_mtime_ns, st_size), None when the file does not exist."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)
