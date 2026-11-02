"""Ingress-gated HTTP server skeleton for HA add-on admin GUIs (stdlib only, relative imports only)."""

from .errors import ERROR_STATUS, ApiError, register_error_code
from .headers import DEFAULT_CSP, security_headers
from .ingress import INGRESS_REMOTE, ingress_user, is_ingress
from .router import Download, Request, Router
from .server import make_handler, make_server, serve
from .static import StaticFiles

__all__ = [
    "DEFAULT_CSP",
    "ERROR_STATUS",
    "INGRESS_REMOTE",
    "ApiError",
    "Download",
    "Request",
    "Router",
    "StaticFiles",
    "ingress_user",
    "is_ingress",
    "make_handler",
    "make_server",
    "register_error_code",
    "security_headers",
    "serve",
]
