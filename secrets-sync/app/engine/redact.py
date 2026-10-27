"""Defense in depth: scrub known secret values from log lines and event messages."""

from __future__ import annotations

import logging
import threading
from typing import Iterable

MIN_LEN = 4  # shorter values would mangle ordinary log text


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
