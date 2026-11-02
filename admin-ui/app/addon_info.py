"""Resolves this add-on's own slug from the Supervisor (GET http://supervisor/addons/self/info).

`/addons/self/...` needs no `hassio_api` (see the Home Assistant app security guide). The token comes from the
`SUPERVISOR_TOKEN` environment variable and is never logged or returned; any failure yields None, so the GUI hides
the info link instead of guessing a slug. Only successes are cached, failures are retried after a pause.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

SUPERVISOR_URL = "http://supervisor/addons/self/info"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
TIMEOUT_S = 2.0
RETRY_AFTER_S = 60.0
MAX_BYTES = 256 * 1024

Opener = Callable[[urllib.request.Request, float], Any]


def _open(req: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - fixed http://supervisor URL


def fetch_slug(environ: Mapping[str, str], opener: Opener = _open) -> str | None:
    """Return the validated slug of this add-on, or None (no token, no answer, unexpected shape)."""
    token = environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        return None
    req = urllib.request.Request(SUPERVISOR_URL, headers={"Authorization": f"Bearer {token}"})
    try:
        with opener(req, TIMEOUT_S) as resp:
            payload = json.loads(resp.read(MAX_BYTES))
        slug = payload["data"]["slug"]
    except Exception:  # noqa: BLE001 - every failure means "unknown"; details could contain the token
        return None
    return slug if isinstance(slug, str) and SLUG_RE.match(slug) else None


class SlugResolver:
    """Thread-safe lazy lookup: caches a found slug for good and retries a failed one at most once a minute."""

    def __init__(
        self,
        environ: Mapping[str, str],
        fetch: Callable[[Mapping[str, str]], str | None] = fetch_slug,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._environ = environ
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._slug: str | None = None
        self._next_try = 0.0

    def get(self) -> str | None:
        with self._lock:
            if self._slug is None and self._clock() >= self._next_try:
                self._slug = self._fetch(self._environ)
                if self._slug is None:
                    self._next_try = self._clock() + RETRY_AFTER_S
            return self._slug
