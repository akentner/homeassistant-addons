"""GUI server of Marketplace Repo Proxy: JSON routes behind the ingress gate, plus the static Preact page.

Built on the admin-ui skeleton (app.web.admin_ui, copied by `make sync-admin-ui`). No route is public (D-03): every
method and path must come from the Supervisor's ingress peer with a non-empty `X-Ingress-Path`. Git traffic never runs
through this server. An OSError is mapped to a plain `internal_error` with only its type name logged, because its text
can carry a path with an access hash and the skeleton would print the traceback otherwise.
"""

from __future__ import annotations

import logging
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.web.admin_ui import DEFAULT_CSP, INGRESS_REMOTE, ApiError, Request, Router, StaticFiles
from app.web.admin_ui import make_server as skeleton_make_server
from app.web.service import GuiService

LOG = logging.getLogger("mrp.gui")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _os_error(exc: Exception) -> ApiError:
    LOG.error("request failed (%s)", type(exc).__name__)
    return ApiError("internal_error", "internal error")


def build_router(service: GuiService) -> Router:
    router = Router()

    def api_overview(_req: Request) -> dict[str, Any]:
        return service.overview()

    def api_meta(_req: Request) -> dict[str, Any]:
        return service.meta()

    router.add("GET", "/api/overview", api_overview)
    router.add("GET", "/api/meta", api_meta)
    return router


def make_server(
    service: GuiService,
    port: int,
    ingress_remote: str = INGRESS_REMOTE,
    host: str = "0.0.0.0",
    static: StaticFiles | None = None,
) -> ThreadingHTTPServer:
    return skeleton_make_server(
        build_router(service),
        StaticFiles(STATIC_DIR) if static is None else static,
        port,
        ingress_remote=ingress_remote,
        host=host,
        csp=DEFAULT_CSP,
        error_mappers={OSError: _os_error},
    )
