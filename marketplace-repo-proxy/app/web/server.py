"""GUI server of Marketplace Repo Proxy: JSON routes behind the ingress gate, plus the static Preact page.

Built on the admin-ui skeleton (app.web.admin_ui, copied by `make sync-admin-ui`). No route is public (D-03): every
method and path must come from the Supervisor's ingress peer with a non-empty `X-Ingress-Path`. Git traffic never runs
through this server. An OSError is mapped to a plain `internal_error` with only its type name logged, because its text
can carry a path with an access hash and the skeleton would print the traceback otherwise. Access errors map to their
stable codes (D-15); no exception text ever becomes a response message.
"""

from __future__ import annotations

import logging
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.access import AccessError, AccessSchemaError
from app.accessread import AccessUnavailable
from app.web.admin_ui import DEFAULT_CSP, INGRESS_REMOTE, ApiError, Request, Router, StaticFiles, register_error_code
from app.web.admin_ui import make_server as skeleton_make_server
from app.web.service import GuiService

LOG = logging.getLogger("mrp.gui")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Stable access error codes (D-15, Phase 1 codes plus access_unavailable); the lib already has confirmation_required
# (400) and protected (409).
ACCESS_ERRORS = {
    "repository_unknown": 404,
    "user_unknown": 404,
    "user_exists": 409,
    "hash_conflict": 409,
    "invalid_hash": 409,
    "invalid_user": 400,
    "user_reserved": 400,
    "access_unavailable": 503,
}
for _code, _status in ACCESS_ERRORS.items():
    register_error_code(_code, _status)


def _os_error(exc: Exception) -> ApiError:
    LOG.error("request failed (%s)", type(exc).__name__)
    return ApiError("internal_error", "internal error")


def _access_unavailable(_exc: Exception) -> ApiError:
    return ApiError("access_unavailable", "access store unavailable")


def _access_error(exc: Exception) -> ApiError:
    if isinstance(exc, AccessSchemaError):
        return _access_unavailable(exc)
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in ACCESS_ERRORS:
        return ApiError(code, code.replace("_", " "))
    LOG.error("request failed (%s)", type(exc).__name__)
    return ApiError("internal_error", "internal error")


def _strict_body(req: Request, allowed: set[str]) -> dict[str, Any]:
    """The JSON object body ({} when none was sent); a non-object or an unknown field is a bad_request."""
    body = req.body()
    if set(body) - allowed:
        raise ApiError("bad_request", "unknown field")
    return body


def build_router(service: GuiService) -> Router:
    router = Router()

    def api_overview(_req: Request) -> dict[str, Any]:
        return service.overview()

    def api_meta(_req: Request) -> dict[str, Any]:
        return service.meta()

    def api_sync(req: Request) -> tuple[int, dict[str, Any]]:
        # A JSON object body is required: it forces a CORS preflight for cross-origin callers (CSRF hardening)
        if not isinstance(req.json, dict):
            raise ApiError("bad_request", "JSON object body required")
        if req.json:
            raise ApiError("bad_request", "unknown field")
        return 202, service.request_sync()

    def _repository(req: Request) -> str:
        return f"{req.params['owner']}/{req.params['repo']}"

    def api_access(_req: Request) -> dict[str, Any]:
        return service.access_list()

    def api_access_add(req: Request) -> tuple[int, dict[str, Any]]:
        body = _strict_body(req, {"user"})
        return 201, service.add_user(_repository(req), body.get("user"))

    def api_access_urls(req: Request) -> dict[str, Any]:
        return service.user_urls(_repository(req), req.params["user"])

    def api_access_revoke(req: Request) -> None:
        body = _strict_body(req, {"confirm"})
        service.revoke_user(_repository(req), req.params["user"], body.get("confirm"))

    def api_access_rotate(req: Request) -> dict[str, Any]:
        body = _strict_body(req, {"confirm"})
        return service.rotate_user(_repository(req), req.params["user"], body.get("confirm"))

    router.add("GET", "/api/overview", api_overview)
    router.add("GET", "/api/meta", api_meta)
    router.add("POST", "/api/sync", api_sync)
    router.add("GET", "/api/access", api_access)
    router.add("POST", "/api/access/{owner}/{repo}", api_access_add)
    router.add("GET", "/api/access/{owner}/{repo}/{user}/urls", api_access_urls)
    router.add("DELETE", "/api/access/{owner}/{repo}/{user}", api_access_revoke)
    router.add("POST", "/api/access/{owner}/{repo}/{user}/rotate", api_access_rotate)
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
        error_mappers={OSError: _os_error, AccessUnavailable: _access_unavailable, AccessError: _access_error},
    )
