"""Ask the Home Assistant Supervisor to re-read secrets.yaml.

The Supervisor keeps its own copy of secrets.yaml to resolve `!secret` in add-on options and refuses to save options
that reference a key it does not know yet. `GET /addons/self/options/config` is open to every add-on and reloads that
copy as a side effect (throttled by the Supervisor to once per 60 s). The response holds resolved options, so the body
is never read.
"""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("secrets_sync")

URL = "http://supervisor/addons/self/options/config"
SKIPPED = "skipped"  # not running under a Supervisor (no SUPERVISOR_TOKEN)
RETRY_AFTER = 65  # the Supervisor skips a reload within 60 s of the previous one


def supervisor_reload() -> str | None:
    """Trigger the reload. Returns None on success, SKIPPED without a Supervisor, else an error code."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return SKIPPED
    req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed internal URL
            resp.read(0)
            return None if resp.status == 200 else f"http_{resp.status}"
    except urllib.error.HTTPError as exc:
        return f"http_{exc.code}"
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return type(exc).__name__
