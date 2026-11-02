"""Ingress-gated HTTP server skeleton for HA add-on admin GUIs (stdlib only, relative imports only)."""

from .errors import ERROR_STATUS, ApiError
from .ingress import INGRESS_REMOTE, is_ingress
from .router import Download, Request, Router
from .server import make_handler, make_server
from .static import StaticFiles

__all__ = [
    "ERROR_STATUS",
    "INGRESS_REMOTE",
    "ApiError",
    "Download",
    "Request",
    "Router",
    "StaticFiles",
    "is_ingress",
    "make_handler",
    "make_server",
]
