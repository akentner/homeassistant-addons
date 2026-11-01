"""GET /api/health (contract C10 Health): ntfy liveness plus database status. Always HTTP 200."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from app.contract import NTFY_PORT
from app.web.server import Request, Router


def ntfy_health(timeout: float = 2.0) -> dict[str, Any]:
    """Ask the local ntfy server; never raises."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{NTFY_PORT}/v1/health", timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return {"healthy": bool(data.get("healthy")), "role": data.get("role")}
    except Exception:  # noqa: BLE001 - any failure means unhealthy
        return {"healthy": False, "role": None}


def register(router: Router, ctx: Any) -> None:
    def health(_req: Request) -> dict[str, Any]:
        ntfy = ntfy_health()
        schema = ctx.db.check_schema()
        try:
            cache_size = ctx.paths.cache_db.stat().st_size
        except OSError:
            cache_size = 0
        if not ntfy["healthy"]:
            status = "error"
        elif not schema["supported"]:
            status = "degraded"
        else:
            status = "ok"
        return {
            "status": status,
            "addon_version": os.environ.get("NTFY_ADDON_VERSION", "unknown"),
            "ntfy": ntfy,
            "db": {
                "schema_version": schema["version"],
                "supported": schema["supported"],
                "size_bytes": ctx.db.size_bytes(),
                "cache_size_bytes": cache_size,
                "error": schema["error"],
            },
            "counts": None,
        }

    router.add("GET", "/api/health", health)
