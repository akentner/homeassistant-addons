"""Atomic JSON files (temp file in the same directory, fsync, rename, directory fsync) and UTC timestamps."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


def atomic_write_json(path: Path, doc: object) -> None:
    """Write `doc` to `path` with mode 0600; readers never see a half-written file."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(doc, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    """Make the rename durable (a revocation must survive a power loss); best effort where a platform refuses it.

    The new file is already in place, so a failure here must not report the write as failed.
    """
    try:
        fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def read_json(path: Path) -> object | None:
    """Parsed JSON, or None when the file does not exist. Invalid JSON raises ValueError."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return json.loads(raw)


def utc_timestamp(ts: float | None = None) -> str:
    """ISO 8601 UTC with `Z`, second precision."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if ts is None else ts))
