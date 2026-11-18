"""Registration status of each repository in the local add-on store, read from Phase 2's /data/supervisor.json (D-19).

This module is the single place that reads `/data/supervisor.json` and maps it into
`{repository.lower(): {"state": ..., "detail": ...}}`. It imports no Phase 2 module: when Phase 2 writes another
layout, only this reader and its fixture tests change.

Interface Phase 2 has to meet (assumed layout):

- A JSON object, written by Phase 2's single writer with atomic replace. This reader takes no lock and never writes,
  renames or deletes the file.
- `repositories`: a list with one object per repository holding `repository` (`owner/repo`, matched
  case-insensitively), `registration` (one of `registered`, `missing`, `leftover`, `error`) and an optional `message`.
- Every other top-level key and every other entry key is ignored. A missing or unreadable file, a repository without an
  entry and any other state value mean "no data" for that repository.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.paths import Paths

FILE_NAME = "supervisor.json"
REGISTRATION_STATES = ("registered", "missing", "leftover", "error")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def read_registration(paths: Paths) -> dict[str, dict[str, str]] | None:
    """Map of repository.lower() -> {"state": ..., "detail"?: ...}, or None when the file is missing or malformed."""
    path: Path = paths.data_dir / FILE_NAME
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # missing, unreadable, invalid JSON or invalid UTF-8
        return None
    if not isinstance(doc, dict):
        return None
    entries = doc.get("repositories")
    if not isinstance(entries, list):
        return None
    result: dict[str, dict[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        repository = entry.get("repository")
        state = entry.get("registration")
        if not isinstance(repository, str) or not _REPOSITORY_RE.fullmatch(repository):
            continue
        if not isinstance(state, str) or state not in REGISTRATION_STATES:
            continue
        key = repository.lower()
        if key in result:  # the first entry per repository wins
            continue
        value = {"state": state}
        message = entry.get("message")
        if isinstance(message, str):
            value["detail"] = message
        result[key] = value
    return result
