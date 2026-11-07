"""This add-on's own slug and version from the Supervisor (GET http://supervisor/addons/self/info).

`/addons/self/...` needs no `hassio_api`. The token comes from `SUPERVISOR_TOKEN` and is never logged or returned;
any failure yields None, so the GUI hides the info link and the version instead of guessing. Only a complete answer is
cached, failures are retried after a pause.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

SUPERVISOR_URL = "http://supervisor/addons/self/info"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,31}$")
TIMEOUT_S = 2.0
RETRY_AFTER_S = 60.0
MAX_BYTES = 256 * 1024
# The s6 base image keeps container variables out of the environment of plain `#!/bin/sh` processes
TOKEN_FILE = "/run/s6/container_environment/SUPERVISOR_TOKEN"

Opener = Callable[[urllib.request.Request, float], Any]
Info = dict[str, str]


def _open(req: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - fixed http://supervisor URL


def _token(environ: Mapping[str, str], token_file: str = TOKEN_FILE) -> str:
    token = environ.get("SUPERVISOR_TOKEN", "")
    if token:
        return token
    try:
        with open(token_file, encoding="utf-8") as fh:
            return fh.read(512).strip()
    except OSError:
        return ""


def fetch_info(environ: Mapping[str, str], opener: Opener = _open, token_file: str = TOKEN_FILE) -> Info | None:
    """Return {"slug", "version"} (both validated), or None (no token, no answer, unexpected shape)."""
    token = _token(environ, token_file)
    if not token:
        return None
    req = urllib.request.Request(SUPERVISOR_URL, headers={"Authorization": f"Bearer {token}"})
    try:
        with opener(req, TIMEOUT_S) as resp:
            data = json.loads(resp.read(MAX_BYTES))["data"]
        slug, version = data["slug"], data["version"]
    except Exception:  # noqa: BLE001 - every failure means "unknown"; details could contain the token
        return None
    if not (isinstance(slug, str) and SLUG_RE.match(slug) and isinstance(version, str) and VERSION_RE.match(version)):
        return None
    return {"slug": slug, "version": version}


class InfoResolver:
    """Thread-safe lazy lookup: caches a found answer for good and retries a failed one at most once a minute."""

    def __init__(
        self,
        environ: Mapping[str, str],
        fetch: Callable[[Mapping[str, str]], Info | None] = fetch_info,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._environ = environ
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._info: Info | None = None
        self._next_try = 0.0

    def get(self) -> Info | None:
        with self._lock:
            if self._info is None and self._clock() >= self._next_try:
                self._info = self._fetch(self._environ)
                if self._info is None:
                    self._next_try = self._clock() + RETRY_AFTER_S
            return self._info
