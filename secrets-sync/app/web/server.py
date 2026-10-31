"""Web UI and JSON API of Secrets Sync (see docs/SPEC.md, "Web <-> engine").

Serves a static HTML shell plus JS/CSS (ingress only) and the JSON API. The page renders itself from
api/status.json in the browser; the server never interpolates state into HTML. Reads the state file on every
request and talks to the supervisor only through the Controller protocol.
"""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.controller import Controller

INGRESS_REMOTE = "172.30.32.2"
STATIC_DIR = Path(__file__).resolve().parent / "static"
# Whitelist of served files: URL path -> (file below STATIC_DIR, content type)
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/icon": ("icon.png", "image/png"),
}


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


def make_handler(
    controller: Controller, state_path: Path, ingress_only: bool = True, ingress_remote: str = INGRESS_REMOTE
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SecretsSync"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - quiet, no query strings logged
            return

        def _send(self, code: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Any) -> None:
            self._send(code, json.dumps(payload, sort_keys=True).encode(), "application/json; charset=utf-8")

        def _is_ingress(self) -> bool:
            if not ingress_only:
                return True
            return self.client_address[0] == ingress_remote and bool(self.headers.get("X-Ingress-Path"))

        def do_GET(self) -> None:  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                code, body = health(read_state(state_path))
                self._json(code, body)
            elif path == "/api/status.json":
                self._json(200, read_state(state_path))
            elif path in ASSETS:
                if ingress_only and not self._is_ingress():
                    # Page and assets are meant for ingress; the optional TCP port exposes only the JSON endpoints.
                    self._json(403, {"error": "ingress_only"})
                    return
                name, ctype = ASSETS[path]
                try:
                    body = (STATIC_DIR / name).read_bytes()
                except OSError:
                    self._json(404, {"error": "not_found"})
                    return
                self._send(200, body, ctype, cache="no-cache")
            else:
                self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            parts = urllib.parse.urlsplit(self.path)
            if parts.path not in ("/api/sync", "/api/preview"):
                self._json(404, {"error": "not_found"})
                return
            if not self._is_ingress():
                self._json(403, {"error": "ingress_only"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(min(length, 65536))
            try:
                if parts.path == "/api/preview":
                    self._json(200, controller.preview())
                    return
                force = urllib.parse.parse_qs(parts.query).get("force") == ["1"]
                started = bool(controller.trigger_sync(force=force))
            except Exception:  # noqa: BLE001 - never leak exception text, it may carry provider output
                self._json(500, {"error": "internal_error"})
                return
            if started:
                self._json(202, {"started": True})
            else:
                self._json(429, {"started": False, "error": "rate_limited"})

    return Handler


def make_server(
    controller: Controller,
    state_path: Path | str,
    port: int,
    ingress_only: bool = True,
    host: str = "0.0.0.0",
    ingress_remote: str = INGRESS_REMOTE,
) -> ThreadingHTTPServer:
    handler = make_handler(controller, Path(state_path), ingress_only, ingress_remote)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve(controller: Controller, state_path: Path | str, port: int, ingress_only: bool = True) -> None:
    """Blocking; run in a thread by app/main.py."""
    make_server(controller, state_path, port, ingress_only).serve_forever()
