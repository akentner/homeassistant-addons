"""RED stub: access.json change watcher (replaced in the GREEN commit)."""

from __future__ import annotations

import logging
import threading
from typing import Iterable

from app.options import RepoSpec
from app.paths import Paths


class AccessWatcher:
    def __init__(self, paths: Paths, specs: Iterable[RepoSpec], log: logging.Logger, interval: float = 1.0) -> None:
        self.paths = paths
        self.specs = tuple(specs)
        self.log = log
        self.interval = interval

    def signature(self) -> tuple[int, int, int] | None:
        return None

    def poll_once(self) -> bool:
        return False

    def run_forever(self, stop: threading.Event) -> None:
        return None


def main(argv: list[str] | None = None, paths: Paths | None = None) -> int:
    return 0
