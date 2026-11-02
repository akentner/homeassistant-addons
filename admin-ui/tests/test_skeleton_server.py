"""Tests for the skeleton server: gate, router, body rules, headers, error registry/mappers, static whitelist."""

from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from app.web.skeleton import (
    DEFAULT_CSP,
    ERROR_STATUS,
    ApiError,
    Download,
    Request,
    Router,
    StaticFiles,
    ingress_user,
    make_server,
    register_error_code,
    security_headers,
    serve,
)

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}
JSON_HEADERS = {**INGRESS, "Content-Type": "application/json"}


class ForeignError(Exception):
    pass


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

    def foreign(req: Request) -> Any:
        raise ForeignError("exists")

    router.add("GET", "/api/boom", boom)
    router.add("GET", "/api/protected", api_error)
    router.add("POST", "/api/foreign", foreign)
    return router


def make_static(root: Path) -> StaticFiles:
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text("<!doctype html><title>t</title>")
    (root / "app.mjs").write_text("export {};")
    (root / "app.css").write_text("body{}")
    return StaticFiles(root)


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(self, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> Any:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp, resp.read()
        finally:
            conn.close()

    def json(self, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None) -> Any:
        status, _, data = self.call(method, path, headers, body)
        return status, (json.loads(data) if data else None)


@pytest.fixture
def start(tmp_path: Path) -> Iterator[Callable[..., Client]]:
    """Factory start(remote=..., csp=..., mappers=..., static=...) -> Client; servers are closed on teardown."""
    servers: list[Any] = []

    def _start(remote: str = "127.0.0.1", static: StaticFiles | None = None, **kwargs: Any) -> Client:
        kwargs.setdefault("csp", DEFAULT_CSP)
        httpd = make_server(
            build_router(), static or make_static(tmp_path / "static"), 0, ingress_remote=remote, host="127.0.0.1",
            **kwargs,
        )
        thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        servers.append((httpd, thread))
        return Client(httpd.server_address[1])

    yield _start
    for httpd, thread in servers:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture
def client(start: Callable[..., Client]) -> Client:
    return start(error_mappers={ForeignError: lambda exc: ApiError("conflict", "exists")})


def test_gate_allows_ingress_and_serves_static(client: Client) -> None:
    for path in ("/", "/static/app.mjs", "/static/app.css", "/api/health"):
        assert client.call("GET", path, INGRESS)[0] == 200, path


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("path", ["/", "/static/app.mjs", "/api/health", "/nope", "/static/../etc/passwd"])
def test_gate_blocks_every_method_and_path_without_header(client: Client, method: str, path: str) -> None:
    status, _, data = client.call(method, path)
    assert status == 403
    if method != "HEAD":
        assert json.loads(data) == {"error": "ingress_only"}
    else:
        assert data == b""


def test_gate_blocks_foreign_remote(start: Callable[..., Client]) -> None:
    cli = start(remote="10.9.9.9")
    for path in ("/", "/static/app.mjs", "/api/health", "/nope"):
        assert cli.json("GET", path, INGRESS) == (403, {"error": "ingress_only"})
    assert cli.json("POST", "/api/echo", JSON_HEADERS, b"{}")[0] == 403


def test_router_errors_and_params(client: Client) -> None:
    assert client.json("GET", "/api/missing", INGRESS) == (404, {"error": "not_found", "message": "not found"})
    status, body = client.json("PUT", "/api/health", INGRESS)
    assert status == 405 and body["error"] == "method_not_allowed"
    assert client.json("GET", "/api/users/a%2Bb", INGRESS) == (200, {"name": "a+b"})
    assert client.json("GET", "/api/users/a+b", INGRESS) == (200, {"name": "a+b"})


def test_body_rules(client: Client) -> None:
    assert client.json("POST", "/api/echo", JSON_HEADERS, json.dumps({"k": 1}).encode()) == (201, {"k": 1})
    assert client.json("POST", "/api/echo", JSON_HEADERS, b"[1]")[0] == 400
    assert client.json("POST", "/api/echo", JSON_HEADERS, b"{not json")[0] == 400
    status, body = client.json("POST", "/api/echo", JSON_HEADERS, b"{" + b" " * 70000 + b"}")
    assert status == 413 and body["error"] == "payload_too_large"
    assert client.json("POST", "/api/echo", {**INGRESS, "Content-Type": "text/plain"}, b"{}")[0] == 400
    assert client.json("DELETE", "/api/echo", JSON_HEADERS, b'{"confirm": "x"}') == (200, {"confirm": "x"})


def test_body_rejects_chunked_and_bad_content_length(client: Client) -> None:
    for extra in ({"Transfer-Encoding": "chunked"}, {"Content-Length": "-5"}, {"Content-Length": "abc"}):
        sock = http.client.HTTPConnection("127.0.0.1", client.port, timeout=5)
        try:
            sock.putrequest("POST", "/api/echo")
            for key, value in {**JSON_HEADERS, **extra}.items():
                sock.putheader(key, value)
            sock.endheaders()
            resp = sock.getresponse()
            assert resp.status == 400, extra
            resp.read()
        finally:
            sock.close()


def test_response_kinds_and_cache(client: Client) -> None:
    assert client.call("POST", "/api/nothing", INGRESS)[0] == 204
    status, resp, data = client.call("GET", "/api/download", INGRESS)
    assert status == 200 and data == b"data" and "attachment" in resp.getheader("Content-Disposition")
    assert client.call("GET", "/api/health", INGRESS)[1].getheader("Cache-Control") == "no-store"
    assert client.call("GET", "/static/app.css", INGRESS)[1].getheader("Cache-Control") == "no-cache"


def test_security_headers_everywhere(client: Client) -> None:
    for method, path, headers in (
        ("GET", "/", INGRESS),
        ("GET", "/static/app.mjs", INGRESS),
        ("GET", "/api/health", INGRESS),
        ("GET", "/api/missing", INGRESS),
        ("GET", "/api/health", None),  # gate response
    ):
        _, resp, _ = client.call(method, path, headers)
        assert resp.getheader("X-Content-Type-Options") == "nosniff", path
        assert resp.getheader("Referrer-Policy") == "same-origin", path
        assert resp.getheader("X-Frame-Options") is None, path


def test_csp_on_html_and_static_only(client: Client) -> None:
    for path in ("/", "/static/app.mjs", "/static/app.css"):
        csp = client.call("GET", path, INGRESS)[1].getheader("Content-Security-Policy")
        assert csp == DEFAULT_CSP, path
    assert "script-src 'self'" in DEFAULT_CSP and "frame-ancestors 'self'" in DEFAULT_CSP
    assert client.call("GET", "/api/health", INGRESS)[1].getheader("Content-Security-Policy") is None


def test_csp_can_be_switched_off(start: Callable[..., Client]) -> None:
    cli = start(csp=None)
    for path in ("/", "/static/app.mjs", "/api/health"):
        resp = cli.call("GET", path, INGRESS)[1]
        assert resp.getheader("Content-Security-Policy") is None
        assert resp.getheader("X-Content-Type-Options") == "nosniff"


def test_security_headers_function() -> None:
    assert "Content-Security-Policy" not in security_headers("api", DEFAULT_CSP)
    assert security_headers("html", "x")["Content-Security-Policy"] == "x"
    assert "Content-Security-Policy" not in security_headers("static", None)
    assert not any(k.lower() == "x-frame-options" for k in security_headers("html", DEFAULT_CSP))


def test_exception_mapping(client: Client, capsys: pytest.CaptureFixture[str]) -> None:
    assert client.json("GET", "/api/protected", INGRESS) == (409, {"error": "protected", "message": "nope"})
    status, body = client.json("GET", "/api/boom", INGRESS)
    assert status == 500 and body == {"error": "internal_error", "message": "internal error"}
    assert "secret detail" not in json.dumps(body)
    status, body = client.json("POST", "/api/foreign", JSON_HEADERS, b"{}")
    assert status == 409 and body["error"] == "conflict"
    assert "RuntimeError" in capsys.readouterr().out


def test_unmapped_foreign_exception_is_internal_error(start: Callable[..., Client]) -> None:
    cli = start()
    status, body = cli.json("POST", "/api/foreign", JSON_HEADERS, b"{}")
    assert status == 500 and body["error"] == "internal_error" and "exists" not in json.dumps(body)


def test_register_error_code() -> None:
    register_error_code("teapot_test", 418)
    assert ApiError("teapot_test").status == 418
    register_error_code("teapot_test", 418)  # no-op
    with pytest.raises(ValueError):
        register_error_code("teapot_test", 419)
    for bad_code in ("Bad", "x", "1abc", "a-b", ""):
        with pytest.raises(ValueError):
            register_error_code(bad_code, 400)
    for bad_status in (200, 399, 600, "400"):
        with pytest.raises(ValueError):
            register_error_code("other_code", bad_status)  # type: ignore[arg-type]
    assert "other_code" not in ERROR_STATUS
    ERROR_STATUS.pop("teapot_test")


def test_ingress_user() -> None:
    assert ingress_user({}) is None
    user = ingress_user({
        "X-Remote-User-Id": "abc",
        "X-Remote-User-Name": "alex",
        "X-Remote-User-Display-Name": "Alex " + "x" * 200,
        "X-Remote-User-Groups": " system-admin , ,users,",
    })
    assert user is not None
    assert user["user_id"] == "abc" and user["name"] == "alex"
    assert len(user["display_name"]) == 128
    assert user["groups"] == ["system-admin", "users"]
    only_groups = ingress_user({"X-Remote-User-Groups": "a"})
    assert only_groups is not None and only_groups["groups"] == ["a"] and only_groups["name"] == ""


def test_static_whitelist(start: Callable[..., Client], tmp_path: Path) -> None:
    root = tmp_path / "root"
    static = make_static(root)
    (tmp_path / "secret.css").write_text("x")
    (root / "link.css").symlink_to(tmp_path / "secret.css")
    (root / "mod.py").write_text("x")
    (root / "noext").write_text("x")
    (root / ".hidden.css").write_text("x")
    cli = start(static=static)
    for path in (
        "/static/../app/contract.py",
        "/static/%2e%2e/x",
        "/static/..%2fcontract.py",
        "/static/.hidden.css",
        "/static/nope.css",
        "/static/mod.py",
        "/static/noext",
        "/static/link.css",
    ):
        assert cli.call("GET", path, INGRESS)[0] == 404, path
    assert cli.call("GET", "/static/app.css", INGRESS)[0] == 200


def test_icon_route(start: Callable[..., Client], tmp_path: Path) -> None:
    root = tmp_path / "icon-root"
    static = make_static(root)
    cli = start(static=static)
    assert cli.call("GET", "/icon", INGRESS)[0] == 404
    (root / "icon.png").write_bytes(b"\x89PNG")
    assert cli.call("GET", "/icon", INGRESS)[0] == 200


def test_serve_installs_handlers_and_always_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    import signal
    import time

    from app.web.skeleton import server as srv

    installed: dict[int, Callable[..., None]] = {}
    monkeypatch.setattr(srv.signal, "signal", lambda signum, handler: installed.setdefault(signum, handler))

    class Fake:
        closed = False
        stopped = threading.Event()

        def serve_forever(self) -> None:
            installed[signal.SIGTERM](signal.SIGTERM, None)
            assert self.stopped.wait(2)

        def shutdown(self) -> None:
            self.stopped.set()

        def server_close(self) -> None:
            self.closed = True

    fake = Fake()
    serve(fake)  # type: ignore[arg-type]
    assert fake.closed and signal.SIGTERM in installed and signal.SIGINT in installed
    time.sleep(0)

    class Failing(Fake):
        def serve_forever(self) -> None:
            raise RuntimeError("x")

    failing = Failing()
    with pytest.raises(RuntimeError):
        serve(failing)  # type: ignore[arg-type]
    assert failing.closed
