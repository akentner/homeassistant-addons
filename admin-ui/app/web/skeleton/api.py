"""Bearer-gated JSON API listener of the admin-UI skeleton.

Contract: a separate server on its own port next to the ingress server, never a second gate inside it. The bearer check
runs first, for every method and every path (unknown ones included), before routing or reading a body; every failure
gets one identical 401 with `WWW-Authenticate: Bearer`. The listener answers JSON only: no static files, no index, no
icon and no CORS. It is never routed through ingress or a public reverse proxy (R-16); the consumer always states the
bind address explicitly, there is no default exposure.
"""

from __future__ import annotations

import ipaddress
import json
import urllib.parse
from http.server import ThreadingHTTPServer
from typing import Any, Callable

from .errors import ApiError, register_error_code
from .router import Request, Router
from .server import BODY_METHODS, _JsonHandler, _PublicHeaders
from .tokens import TokenVerifier

# One fixed body for every authentication failure, so all failures are byte-identical.
_UNAUTHORIZED_BODY: bytes = json.dumps({"error": "unauthorized", "message": "unauthorized"}, sort_keys=True).encode()

# Credentials headers that consumer handlers on the API port never see.
_HIDDEN = ("authorization", "proxy-authorization")


class _ApiHeaders:
    """Read-only header view for the API port: credentials, identity and ingress headers are not visible."""

    def __init__(self, headers: Any) -> None:
        self._headers = _PublicHeaders(headers)

    def get(self, name: str, default: Any = None) -> Any:
        return default if name.lower().startswith(_HIDDEN) else self._headers.get(name, default)

    def __getitem__(self, name: str) -> Any:
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.get(name) is not None

    def items(self) -> list[tuple[str, Any]]:
        return [(k, v) for k, v in self._headers.items() if not k.lower().startswith(_HIDDEN)]


def _bearer_token(headers: Any) -> str | None:
    """The credential of an `Authorization: Bearer <token>` header, or None; never raises."""
    try:
        value = headers.get("Authorization")
        if not isinstance(value, str):
            return None
        scheme, _, rest = value.strip(" \t").partition(" ")
        if scheme.lower() != "bearer":
            return None
        token = rest.lstrip(" ")
        return token or None
    except Exception:  # noqa: BLE001 - any parsing problem is an authentication failure
        return None


def _make_api_handler(
    router: Router,
    verifier: TokenVerifier,
    *,
    server_version: str,
    error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None,
) -> type[_JsonHandler]:
    class ApiHandler(_JsonHandler):
        # Seconds; StreamRequestHandler applies it to the socket, so idle or slow clients are dropped (the largest body
        # is 64 KiB). The ingress handler keeps no timeout.
        timeout = 30

        def _unauthorized(self) -> None:
            self.close_connection = True
            self._send(
                401, _UNAUTHORIZED_BODY, "application/json; charset=utf-8", extra={"WWW-Authenticate": "Bearer"}
            )

        def _dispatch(self) -> None:
            # Gate first, for every method and path: nothing is routed or read before the token is valid
            token = _bearer_token(self.headers)
            if token is None or verifier.verify(token) is not True:
                self._unauthorized()
                return
            parts = urllib.parse.urlsplit(self.path)
            try:
                handler, params = router.match(self.command, parts.path)
                body = self._read_body() if self.command in BODY_METHODS else None
                request = Request(
                    method=self.command,
                    path=parts.path,
                    params=params,
                    query=urllib.parse.parse_qs(parts.query, keep_blank_values=True),
                    headers=_ApiHeaders(self.headers),
                    json=body,
                    public=True,
                )
                result = handler(request)
            except Exception as exc:  # noqa: BLE001 - mapped to a stable error code, never leaked
                self._fail(exc)
                return
            self._respond(result)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _dispatch  # noqa: N815

    # Assigned after the class statement: a class body does not see the enclosing function's variables
    ApiHandler.server_version = server_version
    ApiHandler.mappers = dict(error_mappers or {})
    return ApiHandler


def make_api_server(
    router: Router,
    port: int,
    verifier: TokenVerifier,
    *,
    bind: str,
    server_version: str = "AdminUiApi",
    error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None = None,
) -> ThreadingHTTPServer:
    """Build the bearer-gated API server; `bind` has no default, the consumer states its exposure explicitly.

    Raises ValueError before any socket exists: without a usable verifier (no token: the API stays off), when `bind`
    is not an IPv4 literal (ThreadingHTTPServer is AF_INET) and when the router has a public route."""
    if verifier is None or not callable(getattr(verifier, "verify", None)):
        raise ValueError("no API token: the API stays off")
    try:
        address = ipaddress.ip_address(bind)
    except (TypeError, ValueError):
        address = None
    if not isinstance(address, ipaddress.IPv4Address):
        # The message names no value
        raise ValueError("bind must be an IPv4 address")
    if any(router.is_public(method, pattern) for method, pattern in router.routes()):
        raise ValueError("public routes are not allowed on the API router")
    # Lazy and idempotent: the import-time error table stays unchanged for consumers that pin it
    register_error_code("unauthorized", 401)
    handler = _make_api_handler(router, verifier, server_version=server_version, error_mappers=error_mappers)
    server = ThreadingHTTPServer((bind, port), handler)
    server.daemon_threads = True
    return server
