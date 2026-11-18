"""Logging with defense in depth: known secret values and 32-hex access hashes never reach the add-on log."""

from __future__ import annotations

import logging
import re
import sys
import threading
from typing import Iterable

MIN_LEN = 4  # shorter values would mangle ordinary log text
# Standalone 32-hex runs only, so 40-hex commit SHAs stay intact
HASH_TOKEN_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")


class Redactor(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self._values: list[str] = []
        self._lock = threading.Lock()

    def register(self, values: Iterable[str]) -> None:
        with self._lock:
            known = set(self._values)
            known.update(v for v in values if isinstance(v, str) and len(v) >= MIN_LEN)
            self._values = sorted(known, key=len, reverse=True)

    def scrub(self, text: str) -> str:
        with self._lock:
            values = list(self._values)
        for value in values:
            if value in text:
                text = text.replace(value, "***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        scrubbed = self.scrub(message)
        if scrubbed != message:
            record.msg, record.args = scrubbed, ()
        return True


def mask_hashes(text: str) -> str:
    """Replace every standalone 32-hex run with its first 4 chars plus an ellipsis."""
    return HASH_TOKEN_RE.sub(lambda m: m.group(0)[:4] + "…", text)


class SafeFormatter(logging.Formatter):
    """Masks hashes and scrubs registered secrets in the final line, tracebacks included."""

    def __init__(self, fmt: str, redactor: Redactor) -> None:
        super().__init__(fmt)
        self._redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        return mask_hashes(self._redactor.scrub(super().format(record)))


def setup_logging(level: str, redactor: Redactor | None = None) -> Redactor:
    redactor = redactor or Redactor()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SafeFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s", redactor))
    handler.addFilter(redactor)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    return redactor
