"""Ingress-gated HTTP server of the admin-UI skeleton: gate, router dispatch, static whitelist, JSON helpers.

Every request is gated first (any method, any path): only the Supervisor ingress peer with an X-Ingress-Path header
gets through, all others see 403 ingress_only, so unknown paths leak nothing. The one exception is a route registered
with `Router.add(..., public=True)`: exactly that method and literal path is served without ingress (and without any
ingress identity); static files, the index and the icon are never public.
"""

from __future__ import annotations

import json
import signal
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import FrameType
from typing import Any, Callable

from .errors import ApiError
from .headers import DEFAULT_CSP, security_headers
from .ingress import INGRESS_REMOTE, is_ingress
from .router import Download, Request, Router
from .static import StaticFiles, etag_matches

MAX_BODY = 65536
BODY_METHODS = ("POST", "PUT", "PATCH", "DELETE")


# Headers a caller on the published port could forge to look like an ingress viewer.
_IDENTITY_PREFIXES = ("x-remote-user-", "x-ingress-")


class _PublicHeaders:
    """Read-only header view for requests without ingress: identity and ingress headers are not visible."""

    def __init__(self, headers: Any) -> None:
        self._headers = headers

    def get(self, name: str, default: Any = None) -> Any:
        return default if name.lower().startswith(_IDENTITY_PREFIXES) else self._headers.get(name, default)

    def __getitem__(self, name: str) -> Any:
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.get(name) is not None

    def items(self) -> list[tuple[str, Any]]:
        return [(k, v) for k, v in self._headers.items() if not k.lower().startswith(_IDENTITY_PREFIXES)]


def make_handler(
    router: Router,
    static: StaticFiles,
    *,
    ingress_remote: str = INGRESS_REMOTE,
    server_version: str = "AdminUi",
    csp: str | None = DEFAULT_CSP,
    error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None = None,
) -> type[BaseHTTPRequestHandler]:
    mappers = dict(error_mappers or {})

    class GuiHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - query strings can carry names
            return

        def _send(
            self,
            status: int,
            body: bytes,
            ctype: str,
            cache: str = "no-store",
            extra: dict[str, str] | None = None,
            kind: str = "api",
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            for key, value in security_headers(kind, csp).items():
                self.send_header(key, value)
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload, sort_keys=True).encode(), "application/json; charset=utf-8")

        def _error(self, exc: ApiError) -> None:
            # The request body may be unread: do not reuse the connection
            self.close_connection = True
            self._json(exc.status, {"error": exc.code, "message": exc.message})

        def _read_body(self) -> Any:
            if self.headers.get("Transfer-Encoding"):
                raise ApiError("bad_request", "chunked bodies are not supported")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError as exc:
                raise ApiError("bad_request", "invalid Content-Length") from exc
            if length < 0:
                raise ApiError("bad_request", "invalid Content-Length")
            if length > MAX_BODY:
                raise ApiError("payload_too_large", "request body too large")
            if length == 0:
                return None
            if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
                raise ApiError("bad_request", "content type must be application/json")
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise ApiError("bad_request", "invalid JSON") from exc

        def _dispatch(self) -> None:
            via_ingress = is_ingress(self.client_address[0], self.headers, ingress_remote)
            # The request target exactly as sent, without its query: compared literally, never normalised or decoded.
            # (http.server already collapses leading slashes in self.path, the request line still has them.)
            words = self.requestline.split(" ")
            raw_path = (words[1] if len(words) > 1 else self.path).split("?", 1)[0]
            if not via_ingress and not router.is_public(self.command, raw_path):
                self.close_connection = True
                self._json(403, {"error": "ingress_only"})
                return
            parts = urllib.parse.urlsplit(self.path)
            method = self.command
            try:
                if method == "GET" and via_ingress:
                    asset = static.resolve_asset(parts.path)
                    if asset is not None:
                        kind = "html" if parts.path == "/" else "static"
                        validator = {"ETag": asset.etag}
                        if etag_matches(self.headers.get("If-None-Match"), asset.etag):
                            self._send(304, b"", asset.ctype, cache="no-cache", extra=validator, kind=kind)
                        else:
                            self._send(200, asset.body, asset.ctype, cache="no-cache", extra=validator, kind=kind)
                        return
                handler, params = router.match(method, parts.path)
                body = self._read_body() if method in BODY_METHODS else None
                request = Request(
                    method=method,
                    path=parts.path,
                    params=params,
                    query=urllib.parse.parse_qs(parts.query, keep_blank_values=True),
                    headers=self.headers if via_ingress else _PublicHeaders(self.headers),
                    json=body,
                    public=not via_ingress,
                )
                result = handler(request)
            except ApiError as exc:
                self._error(exc)
                return
            except Exception as exc:  # noqa: BLE001 - never leak exception text; traceback goes to stdout only
                mapped = next((fn(exc) for cls, fn in mappers.items() if isinstance(exc, cls)), None)
                if mapped is not None:
                    self._error(mapped)
                    return
                print(traceback.format_exc(), flush=True)
                self._error(ApiError("internal_error", "internal error"))
                return
            if result is None:
                self._send(204, b"", "application/json; charset=utf-8")
            elif isinstance(result, Download):
                disposition = {"Content-Disposition": f'attachment; filename="{result.filename}"'}
                self._send(200, result.data, result.content_type, extra=disposition)
            elif isinstance(result, tuple):
                self._json(result[0], result[1])
            else:
                self._json(200, result)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _dispatch  # noqa: N815

    GuiHandler.server_version = server_version
    return GuiHandler


def make_server(
    router: Router,
    static: StaticFiles,
    port: int,
    *,
    ingress_remote: str = INGRESS_REMOTE,
    host: str = "0.0.0.0",
    csp: str | None = DEFAULT_CSP,
    error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None = None,
) -> ThreadingHTTPServer:
    handler = make_handler(router, static, ingress_remote=ingress_remote, csp=csp, error_mappers=error_mappers)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve(server: ThreadingHTTPServer) -> None:
    """Run until SIGTERM or SIGINT, then close the socket."""

    def stop(_signum: int, _frame: FrameType | None) -> None:
        # shutdown() blocks until serve_forever returns, so it must not run in the signal handler's thread
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
