"""Bearer-gated JSON API listener of the admin-UI skeleton.

Contract: a separate server on its own port next to the ingress server, never a second gate inside it. The bearer check
runs first, for every method and every path (unknown ones included), before routing or reading a body; every failure
gets one identical 401 with `WWW-Authenticate: Bearer`. The listener answers JSON only: no static files, no index, no
icon and no CORS. It is never routed through ingress or a public reverse proxy (R-16); the consumer always states the
bind address explicitly, there is no default exposure.
"""

from __future__ import annotations

import io
import ipaddress
import json
import socket
import sys
import threading
import time
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

# Read limits of the API port (the ingress handler keeps none). Seconds one read may wait for the next byte, an idle
# keep-alive connection included; seconds from the first byte of a request until its line, headers and body are read
# completely; connections open at once (one thread each), a further one is closed before anything is read.
READ_TIMEOUT = 30
REQUEST_DEADLINE = 30
MAX_CONNECTIONS = 32


class _DeadlineReader(io.RawIOBase):
    """Socket reader with the per-read timeout plus a deadline per request, so a client that sends one byte just
    before every per-read timeout is still dropped. A missed timeout or deadline raises TimeoutError."""

    def __init__(self, sock: socket.socket, timeout: float, deadline: float) -> None:
        self._sock = sock
        self._timeout = timeout
        self._seconds = deadline
        self._deadline: float | None = None

    def readable(self) -> bool:
        return True

    def start_request(self) -> None:
        """Called before each request: its clock starts with the next byte received."""
        self._deadline = None

    def readinto(self, buffer: Any) -> int:
        timeout = self._timeout
        if self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("request deadline exceeded")
            timeout = min(timeout, remaining)
        self._sock.settimeout(timeout)
        try:
            count = self._sock.recv_into(buffer)
        finally:
            # Writes keep the plain per-read timeout
            self._sock.settimeout(self._timeout)
        if count and self._deadline is None:
            self._deadline = time.monotonic() + self._seconds
        return count


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
    """The credential of exactly one `Authorization: Bearer <token>` header, or None; never raises.

    Only the Authorization header counts (never the query string, the body, a cookie or another header). The scheme is
    case-insensitive and followed by 1*SP (RFC 6750); the token is non-empty printable ASCII (0x21..0x7E), which rejects
    inner spaces, obs-fold remnants and non-ASCII bytes. Two Authorization headers fail whichever one is valid."""
    try:
        if not hasattr(headers, "get_all"):
            return None
        values = headers.get_all("Authorization") or []
        if len(values) != 1 or not isinstance(values[0], str):
            return None
        scheme, sep, rest = values[0].strip(" \t").partition(" ")
        if not sep or scheme.lower() != "bearer":
            return None
        token = rest.lstrip(" ")
        if not token or not all("\x21" <= char <= "\x7e" for char in token):
            return None
        return token
    except Exception:  # noqa: BLE001 - any parsing problem is an authentication failure
        return None


def _verified(verifier: TokenVerifier, token: str) -> bool:
    """True only when the verifier says exactly True; an exception is a failed check, never a crash or a traceback."""
    try:
        return verifier.verify(token) is True
    except Exception:  # noqa: BLE001 - a broken verifier fails closed
        return False


def _make_api_handler(
    router: Router,
    verifier: TokenVerifier,
    *,
    server_version: str,
    error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None,
) -> type[_JsonHandler]:
    class ApiHandler(_JsonHandler):
        # Per-read timeout (StreamRequestHandler applies it to the socket) and the per-request deadline of
        # _DeadlineReader: a connection that sends nothing, or a request that trickles in, is dropped without a
        # response. The ingress handler keeps neither.
        timeout = READ_TIMEOUT
        request_deadline = REQUEST_DEADLINE

        def setup(self) -> None:
            super().setup()
            self.rfile.close()
            self._reader = _DeadlineReader(self.connection, self.timeout, self.request_deadline)
            self.rfile = io.BufferedReader(self._reader)

        def handle_one_request(self) -> None:
            self._reader.start_request()
            super().handle_one_request()

        def __getattr__(self, name: str) -> Any:
            # Any method token (TRACE, CONNECT, PROPFIND, FOO, lowercase get) reaches the gate instead of the stdlib
            # HTML 501; every other missing attribute (for example _headers_buffer) stays an AttributeError
            if name.startswith("do_"):
                return self._dispatch
            raise AttributeError(name)

        def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
            # Parser errors (400, 414, 431, 505) never reach a method: answer them with the identical 401, so no
            # request text is reflected and nothing bypasses the gate
            self._unauthorized()

        def _carries_body(self) -> bool:
            """True when the request announces body bytes (any Transfer-Encoding or a Content-Length other than 0)."""
            if self.headers.get("Transfer-Encoding") is not None:
                return True
            return any(value.strip(" \t") != "0" for value in self.headers.get_all("Content-Length") or [])

        def _read_body(self) -> Any:
            # Stricter than the ingress handler, which stays unchanged: exactly one Content-Length of plain ASCII
            # digits (no sign, no underscore, no second header that a proxy in front might read instead)
            values = [value.strip(" \t") for value in self.headers.get_all("Content-Length") or []]
            if len(values) > 1 or any(not (value.isascii() and value.isdigit()) for value in values):
                raise ApiError("bad_request", "invalid Content-Length")
            return super()._read_body()

        def _unauthorized(self) -> None:
            self.close_connection = True
            self._send(
                401, _UNAUTHORIZED_BODY, "application/json; charset=utf-8", extra={"WWW-Authenticate": "Bearer"}
            )

        def _dispatch(self) -> None:
            if self.request_version == "HTTP/0.9":
                # No headers on 3.14, parsed headers on 3.12: always the 401 (body only, 0.9 has no status line)
                self._unauthorized()
                return
            # Gate first, for every method and path: nothing is routed or read before the token is valid
            token = _bearer_token(self.headers)
            if token is None or not _verified(verifier, token):
                self._unauthorized()
                return
            if self.command not in BODY_METHODS and self._carries_body():
                # The body is never read: close, so its bytes are never parsed as the next request on this connection
                self.close_connection = True
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
            except TimeoutError:
                # The body missed the read timeout or the deadline: drop the slow client like a slow request head
                self.close_connection = True
                return
            except Exception as exc:  # noqa: BLE001 - mapped to a stable error code, never leaked
                self._fail(exc)
                return
            try:
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


class _ApiServer(ThreadingHTTPServer):
    """The API server; an exception escaping a request prints only its class name (no message, no traceback).

    At most `max_connections` connections are served at once; a further one is closed at once, before a thread starts
    or anything is read, so unauthenticated clients cannot exhaust threads and memory."""

    daemon_threads = True
    max_connections = MAX_CONNECTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._slots = threading.BoundedSemaphore(self.max_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            # No thread started, so nobody else gives the slot back
            self._slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request: Any, client_address: Any) -> None:
        # The stdlib default prints a full traceback to stderr, whose exception message could carry request data
        exc = sys.exc_info()[1]
        print(f"api request failed: {type(exc).__name__}", flush=True)


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
    return _ApiServer((bind, port), handler)
