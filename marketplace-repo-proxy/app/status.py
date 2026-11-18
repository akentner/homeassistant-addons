"""RED stub: status.json contract writer and reader."""

from __future__ import annotations

from typing import Iterable

from app.jsonio import utc_timestamp  # noqa: F401
from app.options import RepoSpec
from app.paths import Paths

SCHEMA = 1
STATUS_CODES = ("pending", "ok", "auth_failed", "not_found", "no_repository_yaml", "fetch_failed")
REASONS = ("startup", "interval", "request")


class StatusWriter:
    def __init__(
        self, paths: Paths, specs: Iterable[RepoSpec], upstream_overridden: bool, interval_minutes: int
    ) -> None:
        self._paths = paths

    def begin_cycle(self, reason: str) -> None:
        return None

    def record(self, slug: str, **_: object) -> None:
        return None

    def end_cycle(self, next_due_epoch: float | None) -> None:
        return None

    def snapshot(self) -> dict:
        return {}


def read_status(paths: Paths) -> dict | None:
    return None
