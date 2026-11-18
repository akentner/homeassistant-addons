"""s6 longrun `access-watch`: keeps the access symlink tree equal to /data/access.json (D-06).

Run as `python3 -m app.watch`. Polls the file signature (inode, mtime, size) every second and reconciles through
`AccessStore` when it changes, so hand edits and every writer (CLI now, GUI and API later) take effect within about a
second. A deleted file removes every link, a corrupt one is moved aside and also removes every link (fail closed).
It runs as its own service so a long fetch never delays a revocation, and without the container environment: it reads
only the repository list from the options and never uses the upstream credential (D-13).
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from typing import Any, Iterable

from app.access import AccessSchemaError, AccessStore
from app.logsetup import setup_logging
from app.options import OptionsError, RepoSpec, load_options
from app.paths import Paths

LOG = logging.getLogger("mrp.watch")
_UNSEEN = object()  # first poll always reconciles


class AccessWatcher:
    def __init__(self, paths: Paths, specs: Iterable[RepoSpec], log: logging.Logger, interval: float = 1.0) -> None:
        self.paths = paths
        self.specs = tuple(specs)
        self.log = log
        self.interval = interval
        self._seen: Any = _UNSEEN
        self._error_seen: Any = _UNSEEN

    def signature(self) -> tuple[int, int, int] | None:
        """(st_ino, st_mtime_ns, st_size) of access.json, None when it does not exist."""
        try:
            st = os.stat(self.paths.access_file)
        except FileNotFoundError:
            return None
        return (st.st_ino, st.st_mtime_ns, st.st_size)

    def poll_once(self) -> bool:
        """Reconcile when the signature changed since the last poll; True when a reconcile ran."""
        signature = self.signature()
        if signature == self._seen:
            return False
        try:
            AccessStore(self.paths, self.log).reconcile(self.specs)
        except AccessSchemaError:
            if signature != self._error_seen:
                self.log.error("access.json has a newer schema than this add-on version supports; links unchanged")
                self._error_seen = signature
            self._seen = signature  # same content, same answer: wait for the next change
            return False
        except OSError as exc:
            if signature != self._error_seen:
                self.log.error("access reconcile failed (%s); retrying", type(exc).__name__)
                self._error_seen = signature
            return False  # signature not recorded: retry at the next poll
        # the signature from before the reconcile: an edit made during it is picked up at the next poll
        self._seen = signature
        self._error_seen = _UNSEEN
        return True

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set():
            self.poll_once()
            stop.wait(self.interval)


def main(argv: list[str] | None = None, paths: Paths | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.watch",
        description="Keep the access symlink tree equal to /data/access.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
    paths = paths or Paths.default()
    try:
        options = load_options(paths.options_file)
    except OptionsError as exc:
        setup_logging("info")
        LOG.error("%s", exc)
        return 1
    # keep only what this service needs; the credential is not used here
    specs, log_level = options.repositories, options.log_level
    del options
    setup_logging(log_level)

    stop = threading.Event()

    def _stop(*_: Any) -> None:
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _stop)

    LOG.info("access watcher started (%d repositories)", len(specs))
    AccessWatcher(paths, specs, LOG).run_forever(stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
