"""state.json store, exactly per docs/state.schema.json (names only, never values)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("secrets_sync")

MAX_EVENTS = 50
_FMT = "%Y-%m-%dT%H:%M:%SZ"


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(_FMT)


def parse_iso(text: Any) -> float | None:
    try:
        return datetime.strptime(text, _FMT).replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


class StateStore:
    def __init__(self, path: Path, interval: int, versions: dict[str, str],
                 clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.interval = interval
        self.versions = versions
        self._clock = clock
        self.started_at = clock()
        self.status = "starting"
        self.error_code: str | None = None
        self.last_attempt_at: float | None = None
        self.last_success_at: float | None = None
        self.next_sync_at: float | None = None
        self.items = 0
        self.keys: dict[str, list[str]] = {"names": [], "added": [], "removed": [], "changed": []}
        self.providers: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, str]] = []
        self.usage: dict[str, Any] = {"enabled": False}
        self.synthetic: list[dict[str, Any]] = []
        self.check: dict[str, Any] = {"enabled": False, "interval": 0, "last_check_at": None, "result": None}

    def load_previous(self) -> None:
        """Pick up history from a previous run (events, last success, key names)."""
        try:
            prev = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(prev, dict) or prev.get("schema_version") != 1:
            return
        self.last_success_at = parse_iso(prev.get("last_success_at"))
        if isinstance(prev.get("items"), int):
            self.items = prev["items"]
        keys = prev.get("keys")
        if isinstance(keys, dict) and all(isinstance(keys.get(k), list) for k in self.keys):
            self.keys = {k: [str(n) for n in keys[k]] for k in self.keys}
        for event in prev.get("events") or []:
            required = ("at", "level", "code", "message")
            if isinstance(event, dict) and all(isinstance(event.get(k), str) for k in required):
                self.events.append({k: v for k, v in event.items() if isinstance(v, str)})
        del self.events[MAX_EVENTS:]

    def add_event(self, level: str, code: str, message: str, provider: str | None = None) -> None:
        event = {"at": iso(self._clock()) or "", "level": level, "code": code, "message": message}
        if provider:
            event["provider"] = provider
        self.events.insert(0, event)
        del self.events[MAX_EVENTS:]

    def render(self) -> dict[str, Any]:
        now = self._clock()
        age = int(now - self.last_success_at) if self.last_success_at is not None else None
        reference = age if age is not None else now - self.started_at
        return {
            "schema_version": 1,
            "status": self.status,
            "generated_at": iso(now),
            "interval": self.interval,
            "last_attempt_at": iso(self.last_attempt_at),
            "last_success_at": iso(self.last_success_at),
            "age_seconds": age,
            "stale": reference > 2 * self.interval,
            "items": self.items,
            "error_code": self.error_code,
            "next_sync_at": iso(self.next_sync_at),
            "versions": dict(self.versions),
            "providers": self.providers,
            "keys": self.keys,
            "events": self.events,
            "usage": self.usage,
            "synthetic": self.synthetic,
            "check": self.check,
        }

    def save(self) -> None:
        """Atomic write; a failure is logged (code only) and never raised."""
        tmp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state.", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.render(), handle, indent=2, sort_keys=True)
            os.chmod(tmp, 0o644)
            os.replace(tmp, self.path)
            tmp = None
        except OSError as exc:
            log.warning("cannot write state file (%s)", type(exc).__name__)
        finally:
            if tmp:
                Path(tmp).unlink(missing_ok=True)
