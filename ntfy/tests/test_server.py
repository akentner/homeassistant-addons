"""Tests for app.web.server: ingress gate, router, error mapping and the static whitelist (in-process server)."""

from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path
from typing import Any, Iterator

import pytest

from app.contract import ApiError
from app.ntfycli import NtfyCliError
from app.web import server as srv
from app.web.admin_ui import DEFAULT_CSP, StaticFiles
from app.web.server import Download, Request, Router, make_server

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}
JSON_HEADERS = {**INGRESS, "Content-Type": "application/json"}


def build_router() -> Router:
    router = Router()
    router.add("GET", "/api/health", lambda req: {"ok": True})
    router.add("GET", "/api/users/{name}", lambda req: {"name": req.params["name"]})
    router.add("POST", "/api/echo", lambda req: (201, req.body()))
    router.add("DELETE", "/api/echo", lambda req: req.body())
    router.add("POST", "/api/nothing", lambda req: None)
    router.add("GET", "/api/download", lambda req: Download("a.txt", "text/plain", b"data"))

    def boom(req: Request) -> Any:
        raise RuntimeError("secret detail")

    def api_error(req: Request) -> Any:
        raise ApiError("protected", "nope")

    def cli_error(req: Request) -> Any:
        raise NtfyCliError("exists", "user exists")

    router.add("GET", "/api/boom", boom)
    router.add("GET", "/api/protected", api_error)
    router.add("POST", "/api/cli", cli_error)
    return router


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(self, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, resp, data
        finally:
            conn.close()

    def json(self, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None):
        status, resp, data = self.call(method, path, headers, body)
        return status, (json.loads(data) if data else None)


def start(router: Router, remote: str = "127.0.0.1", **kwargs: Any) -> tuple[Any, Client]:
    httpd = make_server(router, 0, ingress_remote=remote, host="127.0.0.1", **kwargs)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, Client(httpd.server_address[1])


@pytest.fixture()
def client() -> Iterator[Client]:
    httpd, cli = start(build_router())
    yield cli
    httpd.shutdown()
    httpd.server_close()


def test_gate_allows_ingress_and_serves_static(client: Client) -> None:
    for path in ("/", "/static/app.mjs", "/static/app.css", "/api/health"):
        status, _, _ = client.call("GET", path, INGRESS)
        assert status == 200, path


def test_gate_blocks_everything_without_header(client: Client) -> None:
    for method, path in (("GET", "/"), ("GET", "/static/app.mjs"), ("GET", "/api/health"), ("GET", "/nope"),
                         ("POST", "/api/echo"), ("DELETE", "/api/echo")):
        status, body = client.json(method, path)
        assert (status, body) == (403, {"error": "ingress_only"}), (method, path)


def test_gate_blocks_foreign_remote() -> None:
    httpd, cli = start(build_router(), remote="10.9.9.9")
    try:
        for path in ("/", "/static/app.mjs", "/api/health", "/nope"):
            assert cli.json("GET", path, INGRESS) == (403, {"error": "ingress_only"})
        assert cli.json("POST", "/api/echo", {**JSON_HEADERS}, b"{}")[0] == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_router_errors_and_params(client: Client) -> None:
    assert client.json("GET", "/api/missing", INGRESS)[0:2] == (404, {"error": "not_found", "message": "not found"})
    status, body = client.json("PUT", "/api/health", INGRESS)
    assert status == 405 and body["error"] == "method_not_allowed"
    assert client.json("GET", "/api/users/a%2Bb", INGRESS) == (200, {"name": "a+b"})
    assert client.json("GET", "/api/users/a+b", INGRESS) == (200, {"name": "a+b"})


def test_body_rules(client: Client) -> None:
    status, body = client.json("POST", "/api/echo", JSON_HEADERS, json.dumps({"k": 1}).encode())
    assert (status, body) == (201, {"k": 1})
    assert client.json("POST", "/api/echo", JSON_HEADERS, b"[1]")[0] == 400
    assert client.json("POST", "/api/echo", JSON_HEADERS, b"{not json")[0] == 400
    status, body = client.json("POST", "/api/echo", JSON_HEADERS, b"{" + b" " * 70000 + b"}")
    assert status == 413 and body["error"] == "payload_too_large"
    assert client.json("POST", "/api/echo", {**INGRESS, "Content-Type": "text/plain"}, b"{}")[0] == 400
    assert client.json("DELETE", "/api/echo", JSON_HEADERS, b'{"confirm": "x"}') == (200, {"confirm": "x"})


def test_response_kinds(client: Client) -> None:
    assert client.call("POST", "/api/nothing", INGRESS)[0] == 204
    status, resp, data = client.call("GET", "/api/download", INGRESS)
    assert status == 200 and data == b"data" and "attachment" in resp.getheader("Content-Disposition")
    _, resp, _ = client.call("GET", "/api/health", INGRESS)
    assert resp.getheader("Cache-Control") == "no-store" and resp.getheader("X-Content-Type-Options") == "nosniff"
    _, resp, _ = client.call("GET", "/static/app.css", INGRESS)
    assert resp.getheader("Cache-Control") == "no-cache" and resp.getheader("X-Frame-Options") is None


def test_exception_mapping(client: Client, capsys: pytest.CaptureFixture[str]) -> None:
    assert client.json("GET", "/api/protected", INGRESS) == (409, {"error": "protected", "message": "nope"})
    status, body = client.json("GET", "/api/boom", INGRESS)
    assert status == 500 and body == {"error": "internal_error", "message": "internal error"}
    assert "secret detail" not in json.dumps(body)
    status, body = client.json("POST", "/api/cli", JSON_HEADERS, b"{}")
    assert status == 409 and body["error"] == "conflict"
    assert "RuntimeError" in capsys.readouterr().out


def stop(httpd: Any) -> None:
    httpd.shutdown()
    httpd.server_close()


def test_static_whitelist(client: Client, tmp_path: Path) -> None:
    for path in ("/static/../app/contract.py", "/static/%2e%2e/x", "/static/..%2fcontract.py", "/static/.hidden.css",
                 "/static/nope.css", "/static/server.py"):
        assert client.call("GET", path, INGRESS)[0] == 404, path
    # a symlink escaping the static root and a .py file below it
    static = tmp_path / "static"
    static.mkdir()
    (tmp_path / "secret.css").write_text("x")
    (static / "link.css").symlink_to(tmp_path / "secret.css")
    (static / "mod.py").write_text("x")
    (static / "ok.css").write_text("ok")
    httpd, custom = start(build_router(), static=StaticFiles(static))
    try:
        assert custom.call("GET", "/static/link.css", INGRESS)[0] == 404
        assert custom.call("GET", "/static/mod.py", INGRESS)[0] == 404
        assert custom.call("GET", "/static/ok.css", INGRESS)[0] == 200
    finally:
        stop(httpd)


def test_default_static_root_follows_the_module_constant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "ok.css").write_text("ok")
    monkeypatch.setattr(srv, "STATIC_DIR", tmp_path)
    httpd, cli = start(build_router())
    try:
        assert cli.call("GET", "/static/ok.css", INGRESS)[0] == 200
        assert cli.call("GET", "/static/app.mjs", INGRESS)[0] == 404
    finally:
        stop(httpd)


def test_csp_on_page_and_static_but_not_on_api(client: Client) -> None:
    for path in ("/", "/static/app.mjs", "/static/app.css"):
        _, resp, _ = client.call("GET", path, INGRESS)
        assert resp.getheader("Content-Security-Policy") == DEFAULT_CSP, path
    for path in ("/api/health", "/api/missing"):
        _, resp, _ = client.call("GET", path, INGRESS)
        assert resp.getheader("Content-Security-Policy") is None, path


def test_security_headers_on_every_response(client: Client) -> None:
    for path, headers in (("/", INGRESS), ("/static/app.mjs", INGRESS), ("/api/health", INGRESS),
                          ("/api/missing", INGRESS), ("/api/health", None)):
        _, resp, _ = client.call("GET", path, headers)
        assert resp.getheader("X-Content-Type-Options") == "nosniff", path
        assert resp.getheader("Referrer-Policy"), path
        assert resp.getheader("X-Frame-Options") is None, path
    assert client.call("GET", "/", INGRESS)[1].getheader("Cache-Control") == "no-cache"
    assert client.call("GET", "/api/health", INGRESS)[1].getheader("Cache-Control") == "no-store"


def test_csp_can_be_switched_off() -> None:
    httpd, cli = start(build_router(), csp=None)
    try:
        for path in ("/", "/static/app.mjs"):
            _, resp, _ = cli.call("GET", path, INGRESS)
            assert resp.getheader("Content-Security-Policy") is None, path
            assert resp.getheader("X-Content-Type-Options") == "nosniff"
    finally:
        stop(httpd)


def test_adapter_keeps_the_public_names() -> None:
    assert srv.STATIC_DIR.is_dir() and (srv.STATIC_DIR / "index.html").is_file()
    assert (srv.Request, srv.Router, srv.Download) == (Request, Router, Download)
