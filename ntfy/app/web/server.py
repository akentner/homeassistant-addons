"""Ingress-gated HTTP server of the ntfy admin GUI (contract C8): a thin adapter over the vendored skeleton.

Gate, router, static whitelist, JSON helpers, security headers and shutdown live in app.web.admin_ui; this module keeps
the names the api modules import (Request, Router, Download, make_server) and adds the ntfy specifics: the static root
and the NtfyCliError to API error mapping.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

from app.contract import INGRESS_REMOTE, ApiError, api_error_from_cli
from app.ntfycli import NtfyCliError
from app.web.admin_ui import DEFAULT_CSP, Download, Request, Router, StaticFiles
from app.web.admin_ui import make_server as skeleton_make_server

__all__ = ["STATIC_DIR", "Download", "Request", "Router", "make_server"]

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _cli_error(exc: Exception) -> ApiError:
    assert isinstance(exc, NtfyCliError)
    return api_error_from_cli(exc.code, exc.message)


def make_server(
    router: Router,
    port: int,
    ingress_remote: str = INGRESS_REMOTE,
    host: str = "0.0.0.0",
    static: StaticFiles | None = None,
    csp: str | None = DEFAULT_CSP,
) -> ThreadingHTTPServer:
    return skeleton_make_server(
        router,
        StaticFiles(STATIC_DIR) if static is None else static,
        port,
        ingress_remote=ingress_remote,
        host=host,
        csp=csp,
        error_mappers={NtfyCliError: _cli_error},
    )
