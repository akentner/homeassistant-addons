"""auth.db backups (contract C12, D-14): created from a short read-only connection, rotated, one daily per UTC day."""

from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app.contract import BACKUP_NAME_RE, ApiError, Backup, iso_utc

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
_NAME_PARTS_RE = re.compile(r"^auth-([0-9]{8}T[0-9]{6}Z)(?:-([a-z0-9-]{1,40}))?\.db$")
_REASON_CLEAN_RE = re.compile(r"[^a-z0-9-]+")


def _clean_reason(reason: str) -> str:
    cleaned = _REASON_CLEAN_RE.sub("-", str(reason).lower()).strip("-")[:40].strip("-")
    return cleaned or "manual"


def _parse_stamp(stamp: str) -> datetime:
    return datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc)


class BackupStore:
    def __init__(
        self, backup_dir: Path, auth_db: Path, keep: int, clock: Callable[[], float] = time.time
    ) -> None:
        self._dir = Path(backup_dir)
        self._auth_db = Path(auth_db)
        self.keep = max(1, int(keep))
        self._clock = clock
        self._lock = threading.RLock()

    # --- helpers ---------------------------------------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self._dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._dir, 0o700)

    def _files(self) -> list[tuple[str, Path, re.Match[str]]]:
        """Valid backup files, oldest first (stamp, then name)."""
        if not self._dir.is_dir():
            return []
        found = []
        for entry in self._dir.iterdir():
            match = _NAME_PARTS_RE.match(entry.name)
            if match and BACKUP_NAME_RE.match(entry.name) and entry.is_file():
                found.append((match.group(1), entry, match))
        found.sort(key=lambda item: (item[0], item[1].name))
        return found

    @staticmethod
    def _describe(path: Path, match: re.Match[str]) -> Backup:
        return {
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "created": iso_utc(_parse_stamp(match.group(1)).timestamp()),
            "reason": match.group(2) or "unknown",
        }

    # --- API -------------------------------------------------------------------------------------------------------

    def create(self, reason: str = "manual") -> Backup:
        if not self._auth_db.is_file():
            raise ApiError("db_unavailable", "auth.db does not exist yet")
        suffix = _clean_reason(reason)
        with self._lock:
            self._ensure_dir()
            moment = datetime.fromtimestamp(int(self._clock()), tz=timezone.utc)
            while True:
                name = f"auth-{moment.strftime(STAMP_FORMAT)}-{suffix}.db"
                if not (self._dir / name).exists():
                    break
                moment += timedelta(seconds=1)
            fd, tmp = tempfile.mkstemp(dir=self._dir, prefix=".backup-", suffix=".tmp")
            os.close(fd)
            try:
                source = sqlite3.connect(f"file:{self._auth_db}?mode=ro", uri=True, timeout=5)
                try:
                    target = sqlite3.connect(tmp)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                finally:
                    source.close()
                os.chmod(tmp, 0o600)
                os.replace(tmp, self._dir / name)
            except sqlite3.Error as exc:
                raise ApiError("db_unavailable", f"backup failed: {type(exc).__name__}") from exc
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
            self.rotate()
            match = _NAME_PARTS_RE.match(name)
            assert match is not None
            return self._describe(self._dir / name, match)

    def list(self) -> list[Backup]:
        with self._lock:
            return [self._describe(path, match) for _, path, match in reversed(self._files())]

    def path_for(self, name: str) -> Path:
        if not isinstance(name, str) or not BACKUP_NAME_RE.match(name):
            raise ApiError("bad_request", "invalid backup name")
        path = self._dir / name
        if not path.is_file():
            raise ApiError("not_found", "backup not found")
        if path.resolve().parent != self._dir.resolve():
            raise ApiError("bad_request", "invalid backup name")
        return path

    def rotate(self) -> int:
        """Delete everything but the newest `keep` backups; returns the number removed."""
        with self._lock:
            files = self._files()
            removed = 0
            for _, path, _ in files[: max(0, len(files) - self.keep)]:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
            return removed

    def create_daily(self) -> Backup | None:
        """One backup per UTC day (reason `daily`); None when one exists or auth.db is missing."""
        if not self._auth_db.is_file():
            return None
        with self._lock:
            today = datetime.fromtimestamp(int(self._clock()), tz=timezone.utc).strftime("%Y%m%d")
            for stamp, _, match in self._files():
                if match.group(2) == "daily" and stamp.startswith(today):
                    return None
            return self.create("daily")
