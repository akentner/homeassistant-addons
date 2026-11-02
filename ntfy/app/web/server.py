"""Ingress-gated HTTP server of the ntfy admin GUI (contract C8): gate, router, static whitelist, JSON helpers.

Every request is gated first (any method, any path): only the Supervisor ingress peer with an X-Ingress-Path header
gets through, all others see 403 ingress_only, so unknown paths leak nothing.
"""

from __future__ import annotations

import json
import re
import traceback
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from app.contract import INGRESS_REMOTE, ApiError, api_error_from_cli
from app.ntfycli import NtfyCliError

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY = 65536
BODY_METHODS = ("POST", "PUT", "PATCH", "DELETE")
SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
CONTENT_TYPES = {
    "mjs": "text/javascript; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "png": "image/png",
    "svg": "image/svg+xml",
    "txt": "text/plain; charset=utf-8",
}


@dataclass
class Download:
    """Handler result that is sent as an attachment."""

    filename: str
    content_type: str
    data: bytes


@dataclass
class Request:
    method: str
    path: str
    params: dict[str, str] = field(default_factory=dict)
    query: dict[str, list[str]] = field(default_factory=dict)
    headers: Any = field(default_factory=dict)
    json: Any = None

    def arg(self, name: str) -> str | None:
        """First query value or None."""
        values = self.query.get(name)
        return values[0] if values else None

    def body(self) -> dict[str, Any]:
        """The JSON object body ({} when none was sent); anything else is a bad_request."""
        if self.json is None:
            return {}
        if not isinstance(self.json, dict):
            raise ApiError("bad_request", "JSON object expected")
        return self.json


Handler = Callable[[Request], Any]


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, str, list[str], Handler]] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        self._routes.append((method.upper(), pattern, pattern.strip("/").split("/"), handler))

    def routes(self) -> list[tuple[str, str]]:
        return [(method, pattern) for method, pattern, _, _ in self._routes]

    def match(self, method: str, path: str) -> tuple[Handler, dict[str, str]]:
        """Return (handler, params); raise ApiError not_found (404) or method_not_allowed (405)."""
        segments = path.strip("/").split("/")
        path_matched = False
        for route_method, _, parts, handler in self._routes:
            if len(parts) != len(segments):
                continue
            params: dict[str, str] = {}
            for part, segment in zip(parts, segments):
                if part.startswith("{") and part.endswith("}"):
                    if not segment:
                        break
                    params[part[1:-1]] = urllib.parse.unquote(segment)
                elif part != segment:
                    break
            else:
                path_matched = True
                if route_method == method:
                    return handler, params
        if path_matched:
            raise ApiError("method_not_allowed", "method not allowed")
        raise ApiError("not_found", "not found")


def resolve_static(path: str) -> tuple[bytes, str] | None:
    """Return (content, content type) for a whitelisted static path, else None (-> 404)."""
    if path == "/":
        rel = "index.html"
        ctype_override: str | None = "text/html; charset=utf-8"
    elif path == "/icon":
        rel = "icon.png"
        ctype_override = None
    elif path.startswith("/static/"):
        rel = path[len("/static/"):]
        ctype_override = None
    else:
        return None
    segments = rel.split("/")
    if not all(SEGMENT_RE.match(segment) for segment in segments):
        return None
    ext = segments[-1].rsplit(".", 1)[-1] if "." in segments[-1] else ""
    if ext not in CONTENT_TYPES and ctype_override is None:
        return None
    root = STATIC_DIR.resolve()
    try:
        target = (root / rel).resolve()
        target.relative_to(root)
        if not target.is_file():
            return None
        return target.read_bytes(), ctype_override or CONTENT_TYPES[ext]
    except (OSError, ValueError):
        return None


def make_handler(router: Router, ingress_remote: str = INGRESS_REMOTE) -> type[BaseHTTPRequestHandler]:
    class GuiHandler(BaseHTTPRequestHandler):
        server_version = "NtfyGui"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - query strings can carry names/topics
            return

        def _send(
            self, status: int, body: bytes, ctype: str, cache: str = "no-store", extra: dict[str, str] | None = None
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
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

        def _is_ingress(self) -> bool:
            return self.client_address[0] == ingress_remote and bool(self.headers.get("X-Ingress-Path"))

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
            if not self._is_ingress():
                self.close_connection = True
                self._json(403, {"error": "ingress_only"})
                return
            parts = urllib.parse.urlsplit(self.path)
            method = self.command
            try:
                if method == "GET":
                    asset = resolve_static(parts.path)
                    if asset is not None:
                        self._send(200, asset[0], asset[1], cache="no-cache")
                        return
                handler, params = router.match(method, parts.path)
                body = self._read_body() if method in BODY_METHODS else None
                request = Request(
                    method=method,
                    path=parts.path,
                    params=params,
                    query=urllib.parse.parse_qs(parts.query, keep_blank_values=True),
                    headers=self.headers,
                    json=body,
                )
                result = handler(request)
            except ApiError as exc:
                self._error(exc)
                return
            except NtfyCliError as exc:
                self._error(api_error_from_cli(exc.code, exc.message))
                return
            except Exception:  # noqa: BLE001 - never leak exception text; traceback goes to stdout only
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

    return GuiHandler


def make_server(
    router: Router, port: int, ingress_remote: str = INGRESS_REMOTE, host: str = "0.0.0.0"
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(router, ingress_remote))
    server.daemon_threads = True
    return server
