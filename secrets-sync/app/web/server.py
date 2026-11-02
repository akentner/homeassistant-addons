"""Web UI and JSON API of Secrets Sync (see docs/SPEC.md, "Web <-> engine").

Built on the admin-ui skeleton (app.web.admin_ui, copied by `make sync-admin-ui`): every request passes the ingress
gate, except GET api/health and GET api/status.json, which are public routes for the optional TCP port. The page
renders itself from api/status.json in the browser; the server never interpolates state into HTML. Reads the state
file on every request and talks to the supervisor only through the Controller protocol.
"""

from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.controller import Controller
from app.web.admin_ui import INGRESS_REMOTE, Request, Router, StaticFiles
from app.web.admin_ui import make_server as _make_server

STATIC_DIR = Path(__file__).resolve().parent / "static"


def read_state(path: Path) -> dict[str, Any]:
    """Return the parsed state, or {} when missing, partial or not a JSON object."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_stale(state: dict[str, Any]) -> bool:
    if state.get("stale") is True:
        return True
    age, interval = state.get("age_seconds"), state.get("interval")
    if isinstance(age, int) and isinstance(interval, int) and not isinstance(age, bool):
        return age > 2 * interval
    return False


def health(state: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status = state.get("status") if isinstance(state.get("status"), str) else "starting"
    stale = _is_stale(state)
    body = {
        "status": status,
        "age_seconds": state.get("age_seconds"),
        "stale": stale,
        "items": state.get("items"),
        "error_code": state.get("error_code"),
    }
    return (200 if status == "ok" and not stale else 503), body


def build_router(controller: Controller, state_path: Path) -> Router:
    router = Router()

    def api_health(_req: Request) -> tuple[int, dict[str, Any]]:
        return health(read_state(state_path))

    def api_status(_req: Request) -> dict[str, Any]:
        return read_state(state_path)

    def api_preview(_req: Request) -> tuple[int, dict[str, Any]]:
        try:
            return 200, controller.preview()
        except Exception:  # noqa: BLE001 - never leak exception text, it may carry provider output
            return 500, {"error": "internal_error"}

    def api_sync(req: Request) -> tuple[int, dict[str, Any]]:
        try:
            started = bool(controller.trigger_sync(force=req.arg("force") == "1"))
        except Exception:  # noqa: BLE001 - same as above
            return 500, {"error": "internal_error"}
        if started:
            return 202, {"started": True}
        return 429, {"started": False, "error": "rate_limited"}

    # Only these two are reachable without ingress (the optional published port); everything else is gated.
    router.add("GET", "/api/health", api_health, public=True)
    router.add("GET", "/api/status.json", api_status, public=True)
    router.add("POST", "/api/sync", api_sync)
    router.add("POST", "/api/preview", api_preview)
    return router


def make_server(
    controller: Controller,
    state_path: Path | str,
    port: int,
    host: str = "0.0.0.0",
    ingress_remote: str = INGRESS_REMOTE,
) -> ThreadingHTTPServer:
    router = build_router(controller, Path(state_path))
    return _make_server(router, StaticFiles(STATIC_DIR), port, ingress_remote=ingress_remote, host=host)


def serve(controller: Controller, state_path: Path | str, port: int) -> None:
    """Blocking; run in a thread by app/main.py (the skeleton's serve() installs signal handlers: main thread only)."""
    make_server(controller, state_path, port).serve_forever()
