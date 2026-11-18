"""Tests for the bearer-gated API listener: option token, gate, shared JSON base, router dispatch over a real socket."""

from __future__ import annotations

import hashlib
import http.client
import http.server
import inspect
import json
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from app.web.skeleton import (
    ERROR_STATUS,
    ApiError,
    Download,
    Request,
    Router,
    ingress_user,
    make_server,
    serve,
)
from app.web.skeleton import api as api_module
from app.web.skeleton.server import MAX_BODY
from app.web.skeleton.api import _UNAUTHORIZED_BODY, make_api_server
from app.web.skeleton.tokens import GeneratedToken, OptionToken
from test_skeleton_server import Client, ForeignError, build_router, make_static

# Generated per test run: obviously fake, never a real credential.
TOKEN = "test-token-" + secrets.token_hex(16)
UNAUTHORIZED = {"error": "unauthorized", "message": "unauthorized"}
AUTH = {"Authorization": f"Bearer {TOKEN}"}
JSON_AUTH = {**AUTH, "Content-Type": "application/json"}


def build_api_router(echo_calls: list[Any] | None = None) -> Router:
    """Test router; every call of POST /api/echo is appended to `echo_calls` (proves "handler not called")."""
    router = Router()
    router.add("GET", "/api/ping", lambda req: {"ok": True})

    def headers(req: Request) -> Any:
        return {"authorization": req.headers.get("Authorization"), "public": req.public}

    def echo(req: Request) -> Any:
        if echo_calls is not None:
            echo_calls.append(req.path)
        return 201, req.body()

    def boom(req: Request) -> Any:
        raise RuntimeError("secret detail")

    def api_error(req: Request) -> Any:
        raise ApiError("protected", "nope")

    def foreign(req: Request) -> Any:
        raise ForeignError("exists")

    def whoami(req: Request) -> Any:
        return {"user": ingress_user(req.headers), "public": req.public, "id": req.headers.get("X-Remote-User-Id")}

    router.add("GET", "/api/headers", headers)
    router.add("POST", "/api/echo", echo)
    router.add("POST", "/api/nothing", lambda req: None)
    router.add("GET", "/api/download", lambda req: Download("a.txt", "text/plain", b"data"))
    router.add("GET", "/api/boom", boom)
    router.add("GET", "/api/protected", api_error)
    router.add("POST", "/api/foreign", foreign)
    router.add("GET", "/api/whoami", whoami)
    return router


@pytest.fixture
def api() -> Iterator[Callable[..., Client]]:
    """Factory api(router=None, verifier=None, **kwargs) -> Client; servers are closed on teardown."""
    servers: list[Any] = []

    def _start(router: Router | None = None, verifier: Any = None, **kwargs: Any) -> Client:
        httpd = make_api_server(
            router or build_api_router(), 0, verifier or OptionToken(TOKEN), bind="127.0.0.1", **kwargs
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


def test_valid_token_reaches_the_route(api: Callable[..., Client]) -> None:
    client = api()
    status, resp, data = client.call("GET", "/api/ping", {"Authorization": f"Bearer {TOKEN}"})
    assert status == 200
    assert json.loads(data) == {"ok": True}
    assert resp.getheader("Cache-Control") == "no-store"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    assert resp.getheader("Referrer-Policy") == "same-origin"
    assert resp.getheader("Content-Security-Policy") is None


def test_missing_wrong_or_basic_credentials_get_the_identical_401(api: Callable[..., Client]) -> None:
    client = api()
    bodies = []
    for headers in (
        {},
        {"Authorization": "Bearer wrong-" + secrets.token_hex(8)},
        {"Authorization": "Basic dGVzdDp0ZXN0"},
    ):
        status, resp, data = client.call("GET", "/api/ping", headers)
        assert status == 401, headers
        assert json.loads(data) == UNAUTHORIZED
        assert resp.getheader("WWW-Authenticate") == "Bearer"
        assert resp.getheader("Connection") == "close"
        bodies.append(data)
    assert bodies[0] == bodies[1] == bodies[2]


def test_handler_never_sees_the_authorization_header(api: Callable[..., Client]) -> None:
    client = api()
    status, _, data = client.call("GET", "/api/headers", {"Authorization": f"Bearer {TOKEN}"})
    assert status == 200
    assert json.loads(data) == {"authorization": None, "public": True}


def test_no_verifier_refuses_before_binding() -> None:
    with pytest.raises(ValueError):
        make_api_server(build_api_router(), 0, None, bind="127.0.0.1")


def test_bind_has_no_default() -> None:
    with pytest.raises(TypeError):
        make_api_server(build_api_router(), 0, OptionToken(TOKEN))  # type: ignore[call-arg]
    param = inspect.signature(make_api_server).parameters["bind"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is inspect.Parameter.empty


def test_unauthorized_is_not_in_the_import_time_error_table() -> None:
    admin_ui = Path(__file__).resolve().parents[1]
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(admin_ui)!r})\n"
        "import app.web.skeleton.api\n"
        "from app.web.skeleton.errors import ERROR_STATUS\n"
        "assert 'unauthorized' not in ERROR_STATUS, ERROR_STATUS\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    server = make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind="127.0.0.1")
    try:
        assert ERROR_STATUS["unauthorized"] == 401
    finally:
        server.server_close()


# --- serve(server, *more): several servers in one process ---


class _FakeServer:
    """Stand-in for ThreadingHTTPServer: serve_forever blocks until shutdown, unless `main` triggers the stop."""

    def __init__(self, installed: dict[int, Callable[..., None]] | None = None, fail: bool = False) -> None:
        self.installed = installed
        self.fail = fail
        self.stopped = threading.Event()
        self.started = threading.Event()
        self.returned = threading.Event()
        self.shutdowns = 0
        self.closed = False

    def serve_forever(self) -> None:
        self.started.set()
        if self.fail:
            raise RuntimeError("x")
        if self.installed is not None:
            self.installed[signal.SIGTERM](signal.SIGTERM, None)
        assert self.stopped.wait(5)
        self.returned.set()

    def shutdown(self) -> None:
        self.shutdowns += 1
        self.stopped.set()

    def server_close(self) -> None:
        self.closed = True


def _record_signals(monkeypatch: pytest.MonkeyPatch) -> dict[int, Callable[..., None]]:
    from app.web.skeleton import server as srv

    installed: dict[int, Callable[..., None]] = {}
    monkeypatch.setattr(srv.signal, "signal", lambda signum, handler: installed.__setitem__(signum, handler))
    return installed


def test_serve_runs_and_stops_every_server(monkeypatch: pytest.MonkeyPatch) -> None:
    installed = _record_signals(monkeypatch)
    main = _FakeServer(installed)
    extra = _FakeServer()
    serve(main, extra)  # type: ignore[arg-type]
    assert signal.SIGTERM in installed and signal.SIGINT in installed
    assert extra.started.is_set() and extra.returned.wait(5)
    assert extra.shutdowns >= 1 and main.shutdowns >= 1
    assert main.closed and extra.closed


def test_serve_closes_every_server_when_the_first_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _record_signals(monkeypatch)
    main = _FakeServer(fail=True)
    extra = _FakeServer()
    with pytest.raises(RuntimeError):
        serve(main, extra)  # type: ignore[arg-type]
    assert extra.shutdowns >= 1 and extra.returned.wait(5)
    assert main.closed and extra.closed


def test_serve_real_gui_and_api_servers_stop_together(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    installed = _record_signals(monkeypatch)
    gui = make_server(build_router(), make_static(tmp_path / "static"), 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    api_server = make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind="127.0.0.1")
    gui_port, api_port = gui.server_address[1], api_server.server_address[1]
    errors: list[BaseException] = []

    def run() -> None:
        try:
            serve(gui, api_server)
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert Client(gui_port).json("GET", "/api/health", {"X-Ingress-Path": "/x"}) == (200, {"ok": True})
        assert Client(api_port).json("GET", "/api/ping", {"Authorization": f"Bearer {TOKEN}"}) == (200, {"ok": True})
        assert signal.SIGTERM in installed
        installed[signal.SIGTERM](signal.SIGTERM, None)
        thread.join(timeout=5)
        assert not thread.is_alive() and not errors
        for port in (gui_port, api_port):
            with pytest.raises(ConnectionRefusedError):
                socket.create_connection(("127.0.0.1", port), timeout=2).close()
    finally:
        if thread.is_alive():
            gui.shutdown()
            api_server.shutdown()
        gui.server_close()
        api_server.server_close()


# --- request handling on the API port (D-02, D-03, D-04) ---


def _raw_post(port: int, headers: dict[str, str], path: str = "/api/echo") -> tuple[int, Any]:
    """POST with headers exactly as given and no body (for Content-Length and Transfer-Encoding edge cases)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest("POST", path)
        for key, value in headers.items():
            conn.putheader(key, value)
        conn.endheaders()
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, (json.loads(data) if data else None)
    finally:
        conn.close()


def test_errors_are_json_with_the_token(api: Callable[..., Client]) -> None:
    client = api()
    assert client.json("GET", "/nope", AUTH) == (404, {"error": "not_found", "message": "not found"})
    status, body = client.json("PUT", "/api/ping", AUTH)
    assert status == 405 and body["error"] == "method_not_allowed"
    status, body = client.json("OPTIONS", "/api/ping", AUTH)
    assert status == 405 and body["error"] == "method_not_allowed"


def test_static_index_and_icon_paths_are_not_served(api: Callable[..., Client]) -> None:
    client = api()
    for path in ("/", "/icon", "/index.html", "/static/app.css"):
        assert client.json("GET", path, AUTH) == (404, {"error": "not_found", "message": "not found"}), path


def test_body_rules_with_the_token(api: Callable[..., Client]) -> None:
    client = api()
    assert client.json("POST", "/api/echo", JSON_AUTH, json.dumps({"k": 1}).encode()) == (201, {"k": 1})
    assert client.json("POST", "/api/echo", JSON_AUTH, b"[1]")[0] == 400
    assert client.json("POST", "/api/echo", JSON_AUTH, b"{not json")[0] == 400
    assert client.json("POST", "/api/echo", {**AUTH, "Content-Type": "text/plain"}, b"{}")[0] == 400
    status, body = _raw_post(client.port, {**JSON_AUTH, "Transfer-Encoding": "chunked"})
    assert status == 400 and body["error"] == "bad_request"


def test_max_body_boundary(api: Callable[..., Client]) -> None:
    calls: list[Any] = []
    client = api(build_api_router(calls))
    prefix, suffix = b'{"k": "', b'"}'
    exact = prefix + b"x" * (MAX_BODY - len(prefix) - len(suffix)) + suffix
    assert len(exact) == MAX_BODY == 65536
    status, body = client.json("POST", "/api/echo", JSON_AUTH, exact)
    assert status == 201 and len(body["k"]) == MAX_BODY - len(prefix) - len(suffix)
    assert len(calls) == 1
    status, body = client.json("POST", "/api/echo", JSON_AUTH, exact[:-1] + b' }')
    assert status == 413 and body["error"] == "payload_too_large"
    assert len(calls) == 1


def test_content_length_parsing(api: Callable[..., Client]) -> None:
    calls: list[Any] = []
    client = api(build_api_router(calls))
    for length, expected in (("-1", 400), ("abc", 400), ("99999999999999999999", 413)):
        status, body = _raw_post(client.port, {**JSON_AUTH, "Content-Length": length})
        assert status == expected, length
        assert body["error"] == ("payload_too_large" if expected == 413 else "bad_request"), length
    assert calls == []


def test_response_kinds(api: Callable[..., Client]) -> None:
    client = api()
    status, _, data = client.call("POST", "/api/nothing", AUTH)
    assert status == 204 and data == b""
    status, resp, data = client.call("GET", "/api/download", AUTH)
    assert status == 200 and data == b"data" and "attachment" in resp.getheader("Content-Disposition")
    assert client.json("POST", "/api/echo", JSON_AUTH, b'{"a": 1}') == (201, {"a": 1})


def test_exception_mapping_on_the_api(api: Callable[..., Client], capsys: pytest.CaptureFixture[str]) -> None:
    client = api(error_mappers={ForeignError: lambda exc: ApiError("conflict", "exists")})
    assert client.json("GET", "/api/protected", AUTH) == (409, {"error": "protected", "message": "nope"})
    assert client.json("POST", "/api/foreign", JSON_AUTH, b"{}") == (409, {"error": "conflict", "message": "exists"})
    status, body = client.json("GET", "/api/boom", AUTH)
    assert status == 500 and body == {"error": "internal_error", "message": "internal error"}
    assert "secret detail" not in json.dumps(body)
    out = capsys.readouterr().out
    assert "RuntimeError" in out and "secret detail" in out


def test_headers_on_every_api_response(api: Callable[..., Client]) -> None:
    client = api()
    origin = {"Origin": "https://example.invalid"}
    for method, path, headers, body in (
        ("GET", "/api/ping", AUTH, None),
        ("GET", "/nope", AUTH, None),
        ("PUT", "/api/ping", AUTH, None),
        ("POST", "/api/nothing", AUTH, None),
        ("GET", "/api/download", AUTH, None),
        ("POST", "/api/echo", JSON_AUTH, b"{nope"),
        ("GET", "/api/ping", {}, None),
        ("OPTIONS", "/api/ping", {**AUTH, **origin, "Access-Control-Request-Method": "POST"}, None),
        ("OPTIONS", "/api/ping", origin, None),
        ("GET", "/api/ping", {**AUTH, **origin}, None),
    ):
        _, resp, _ = client.call(method, path, headers, body)
        label = f"{method} {path} {sorted(headers)}"
        assert resp.getheader("Cache-Control") == "no-store", label
        assert resp.getheader("X-Content-Type-Options") == "nosniff", label
        assert resp.getheader("Referrer-Policy") == "same-origin", label
        assert resp.getheader("Content-Security-Policy") is None, label
        assert resp.getheader("X-Frame-Options") is None, label
        assert not [k for k, _ in resp.getheaders() if k.lower().startswith("access-control-")], label


def test_router_with_a_public_route_is_rejected() -> None:
    router = build_api_router()
    router.add("GET", "/api/health", lambda req: {"ok": True}, public=True)
    with pytest.raises(ValueError, match="public routes"):
        make_api_server(router, 0, OptionToken(TOKEN), bind="127.0.0.1")


def test_bind_must_be_an_ipv4_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    for bind in ("127.0.0.1", "0.0.0.0"):
        server = make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind=bind)
        try:
            assert server.server_address[0] == bind
        finally:
            server.server_close()

    def no_bind(self: Any) -> None:
        pytest.fail("a socket was bound for a rejected bind value")

    monkeypatch.setattr(http.server.HTTPServer, "server_bind", no_bind)
    for bind in ("::1", "localhost", ""):
        with pytest.raises(ValueError, match="IPv4"):
            make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind=bind)


def test_two_listeners_in_one_process(api: Callable[..., Client]) -> None:
    first, second = api(), api()
    assert first.port != second.port
    for client in (first, second):
        assert client.json("GET", "/api/ping", AUTH) == (200, {"ok": True})
    assert ERROR_STATUS["unauthorized"] == 401


def test_concurrent_requests_get_their_own_status(api: Callable[..., Client]) -> None:
    client = api()
    count = 20
    barrier = threading.Barrier(count)
    results: dict[int, int] = {}
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        token = TOKEN if index % 2 == 0 else "wrong-" + secrets.token_hex(8)
        try:
            barrier.wait(timeout=5)
            results[index] = client.call("GET", "/api/ping", {"Authorization": f"Bearer {token}"})[0]
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors
    assert results == {i: (200 if i % 2 == 0 else 401) for i in range(count)}


def test_identity_headers_are_hidden(api: Callable[..., Client]) -> None:
    client = api()
    forged = {
        **AUTH,
        "X-Remote-User-Id": "forged-id",
        "X-Remote-User-Name": "forged",
        "X-Remote-User-Groups": "system-admin",
        "X-Ingress-Path": "/api/hassio_ingress/forged",
    }
    assert client.json("GET", "/api/whoami", forged) == (200, {"id": None, "public": True, "user": None})


def test_api_handler_timeout(tmp_path: Path) -> None:
    api_server = make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind="127.0.0.1")
    gui = make_server(build_router(), make_static(tmp_path / "static"), 0, host="127.0.0.1")
    try:
        assert api_server.RequestHandlerClass.timeout == 30
        assert gui.RequestHandlerClass.timeout is None
    finally:
        api_server.server_close()
        gui.server_close()


# --- slow and excess clients are dropped (WR-03) ---


@pytest.fixture
def fast_api(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., tuple[Any, list[Any]]]]:
    """Factory fast_api(max_connections=32) -> (server, echo calls) with a 2 s per-read timeout and a 1 s deadline."""
    servers: list[Any] = []

    def _start(max_connections: int = 32) -> tuple[Any, list[Any]]:
        monkeypatch.setattr(api_module._ApiServer, "max_connections", max_connections)
        calls: list[Any] = []
        httpd = make_api_server(build_api_router(calls), 0, OptionToken(TOKEN), bind="127.0.0.1")
        httpd.RequestHandlerClass.timeout = 2
        httpd.RequestHandlerClass.request_deadline = 1.0
        thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        servers.append((httpd, thread))
        return httpd, calls

    yield _start
    for httpd, thread in servers:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _closed_after(sock: socket.socket, limit: float, drip: bytes = b"") -> float | None:
    """Send `drip` every 0.2 s until the server closes; the seconds until then, or None if it was still open at `limit`.

    Every gap stays far below the 2 s per-read timeout, so only a request deadline can end a dripping connection."""
    start = time.monotonic()
    sock.settimeout(0.2)
    while time.monotonic() - start < limit:
        try:
            if drip:
                sock.sendall(drip)
            if sock.recv(65536) == b"":
                return time.monotonic() - start
        except (ConnectionResetError, BrokenPipeError):
            return time.monotonic() - start
        except TimeoutError:
            continue
    return None


def test_api_read_limits() -> None:
    server = make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind="127.0.0.1")
    try:
        assert server.RequestHandlerClass.timeout == 30
        assert server.RequestHandlerClass.request_deadline == 30
        assert server.max_connections == 32
    finally:
        server.server_close()


def test_slow_drip_request_head_is_dropped_at_the_deadline(fast_api: Callable[..., Any]) -> None:
    httpd, calls = fast_api()
    with socket.create_connection(("127.0.0.1", httpd.server_address[1]), timeout=5) as sock:
        sock.sendall(b"GET /api/ping HTTP/1.1\r\nHost: test\r\nX-Slow: ")
        elapsed = _closed_after(sock, 6, drip=b"a")
    assert elapsed is not None, "a dripping client kept the connection past the deadline"
    assert 0.5 <= elapsed < 4
    assert calls == []


def test_slow_drip_body_is_dropped_without_a_traceback(
    fast_api: Callable[..., Any], capfd: pytest.CaptureFixture[str]
) -> None:
    httpd, calls = fast_api()
    head = (
        "POST /api/echo HTTP/1.1\r\nHost: test\r\nContent-Type: application/json\r\nContent-Length: 64\r\n"
        f"Authorization: Bearer {TOKEN}\r\n\r\n"
    ).encode()
    with socket.create_connection(("127.0.0.1", httpd.server_address[1]), timeout=5) as sock:
        sock.sendall(head)
        elapsed = _closed_after(sock, 6, drip=b" ")
    assert elapsed is not None
    assert elapsed < 4
    assert calls == []
    out, err = capfd.readouterr()
    assert "Traceback" not in out + err
    assert TOKEN not in out + err


def test_idle_connection_closes_after_the_read_timeout(fast_api: Callable[..., Any]) -> None:
    httpd, _ = fast_api()
    with socket.create_connection(("127.0.0.1", httpd.server_address[1]), timeout=5) as sock:
        elapsed = _closed_after(sock, 6)
    assert elapsed is not None
    assert 1.5 <= elapsed < 4


def test_deadline_starts_at_the_first_byte_of_each_request(fast_api: Callable[..., Any]) -> None:
    # Keep-alive idle time between requests counts against the per-read timeout only, never against the deadline
    httpd, _ = fast_api()
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
    try:
        for _ in range(2):
            conn.request("GET", "/api/ping", headers=AUTH)
            resp = conn.getresponse()
            assert resp.status == 200
            assert resp.getheader("Connection") is None
            resp.read()
            time.sleep(1.4)
    finally:
        conn.close()


def test_connections_beyond_the_cap_are_closed_at_once(fast_api: Callable[..., Any]) -> None:
    httpd, _ = fast_api(max_connections=2)
    port = httpd.server_address[1]
    held = [socket.create_connection(("127.0.0.1", port), timeout=5) for _ in range(2)]
    try:
        for sock in held:
            sock.sendall(b"G")
        time.sleep(0.3)
        with socket.create_connection(("127.0.0.1", port), timeout=5) as extra:
            elapsed = _closed_after(extra, 1.5)
        assert elapsed is not None, "a connection beyond the cap was kept open"
    finally:
        for sock in held:
            sock.close()
    # Closed connections give their slots back
    deadline = time.monotonic() + 3
    while True:
        try:
            if Client(port).call("GET", "/api/ping", AUTH)[0] == 200:
                break
        except (ConnectionError, http.client.HTTPException):
            pass
        assert time.monotonic() < deadline, "slots were not released"
        time.sleep(0.1)


# --- every method token, parser error and HTTP/0.9 request reaches the gate (D-05, AUB-02) ---


def raw(port: int, data: bytes) -> bytes:
    """Send raw bytes and read until the server closes (5 s timeout).

    A reset after the response (the server closed with unread request bytes) ends the read like a close does."""
    chunks: list[bytes] = []
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        try:
            sock.sendall(data)
            while chunk := sock.recv(65536):
                chunks.append(chunk)
        except ConnectionResetError:
            pass
    return b"".join(chunks)


def normalised(resp: bytes) -> bytes:
    """The raw response without its Date and Server header lines (they vary by time and build), body kept."""
    head, _, body = resp.partition(b"\r\n\r\n")
    lines = [line for line in head.split(b"\r\n") if not line.lower().startswith((b"date:", b"server:"))]
    return b"\r\n".join(lines) + b"\r\n\r\n" + body


def _request(method: str, path: str, *lines: str) -> bytes:
    """A raw HTTP/1.1 request that closes after the response; `lines` are extra header lines."""
    head = [f"{method} {path} HTTP/1.1", "Host: test", *lines, "Content-Length: 0", "Connection: close"]
    return ("\r\n".join(head) + "\r\n\r\n").encode("latin-1")


def _reference_401(port: int) -> bytes:
    """The normalised 401 of a GET without Authorization: every failure must equal it."""
    ref = normalised(raw(port, _request("GET", "/api/ping")))
    assert ref.startswith(b"HTTP/1.1 401 ")
    assert ref.endswith(_UNAUTHORIZED_BODY)
    return ref


def test_unknown_methods_reach_the_gate(api: Callable[..., Client]) -> None:
    port = api().port
    ref = _reference_401(port)
    for method in ("TRACE", "CONNECT", "PROPFIND", "FOO", "get"):
        assert normalised(raw(port, _request(method, "/api/ping"))) == ref, method


def test_unknown_method_with_the_token_is_405_json(api: Callable[..., Client]) -> None:
    port = api().port
    resp = raw(port, _request("FOO", "/api/ping", f"Authorization: Bearer {TOKEN}"))
    head, _, body = resp.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 405 ")
    assert b"text/html" not in resp
    assert json.loads(body) == {"error": "method_not_allowed", "message": "method not allowed"}


def test_parser_errors_answer_401(api: Callable[..., Client]) -> None:
    port = api().port
    long_target = b"/" + b"a" * 70000
    many = b"".join(b"X-H%d: v\r\n" % n for n in range(101))
    for data in (
        b"GET\r\n\r\n",
        b"GET / FOO/1.1\r\n\r\n",
        b"GET / HTTP/9.9\r\n\r\n",
        b"GET " + long_target + b" HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n",
        b"GET /api/ping HTTP/1.1\r\nHost: test\r\nX-Long: " + b"a" * 70000 + b"\r\nConnection: close\r\n\r\n",
        b"GET /api/ping HTTP/1.1\r\nHost: test\r\n" + many + b"Connection: close\r\n\r\n",
    ):
        resp = raw(port, data)
        label = data[:40]
        assert resp.endswith(_UNAUTHORIZED_BODY), label
        assert b"text/html" not in resp, label
        for reflected in (b"FOO/1.1", b"9.9", b"aaaaaaaaaa"):
            assert reflected not in resp, label
        if resp.startswith(b"HTTP/"):
            assert resp.split(b" ", 2)[1] == b"401", label


def test_http09_gets_only_the_401_body(api: Callable[..., Client]) -> None:
    port = api().port
    assert raw(port, b"GET /api/ping\r\n\r\n") == _UNAUTHORIZED_BODY
    assert raw(port, f"GET /api/ping\r\nAuthorization: Bearer {TOKEN}\r\n\r\n".encode()) == _UNAUTHORIZED_BODY


class _RaisingVerifier:
    def verify(self, presented: str) -> bool:
        raise RuntimeError("verifier broke")


def test_raising_verifier_is_a_failed_check(api: Callable[..., Client], capfd: pytest.CaptureFixture[str]) -> None:
    client = api(verifier=_RaisingVerifier())
    status, resp, data = client.call("GET", "/api/ping", AUTH)
    assert status == 401
    assert data == _UNAUTHORIZED_BODY
    assert resp.getheader("WWW-Authenticate") == "Bearer"
    out, err = capfd.readouterr()
    assert out == "" and err == ""


# --- strict Authorization parsing and one byte-identical 401 for every failed credential (D-05, AUB-02) ---

FAIL_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "FOO")
FAIL_PATHS = ("/api/ping", "/nope", "/", "/icon", "/static/app.css", f"/api/ping?access_token={TOKEN}")


def _failure_variants() -> dict[str, tuple[str, ...]]:
    """Every credential that must fail, as raw header lines (latin-1 strings carrying the exact bytes to send)."""
    wrong = "wrong-" + secrets.token_hex(16)
    return {
        "missing": (),
        "empty": ("Authorization:",),
        "scheme only": ("Authorization: Bearer",),
        "scheme and spaces": ("Authorization: Bearer    ",),
        "wrong": (f"Authorization: Bearer {wrong}",),
        "minus last char": (f"Authorization: Bearer {TOKEN[:-1]}",),
        "plus one char": (f"Authorization: Bearer {TOKEN}x",),
        "last char changed": (f"Authorization: Bearer {TOKEN[:-1]}{'0' if TOKEN[-1] != '0' else '1'}",),
        "no separator": (f"Authorization: Bearer{TOKEN}",),
        "basic": ("Authorization: Basic dGVzdDp0ZXN0",),
        "other scheme": (f"Authorization: Token {TOKEN}",),
        "inner space": (f"Authorization: Bearer {TOKEN} extra",),
        "tab separator": (f"Authorization: Bearer\t{TOKEN}",),
        "duplicate valid+wrong": (f"Authorization: Bearer {TOKEN}", f"Authorization: Bearer {wrong}"),
        "duplicate wrong+valid": (f"Authorization: Bearer {wrong}", f"Authorization: Bearer {TOKEN}"),
        "duplicate valid+valid": (f"Authorization: Bearer {TOKEN}", f"Authorization: Bearer {TOKEN}"),
        "obs-fold": (f"Authorization: Bearer\r\n {TOKEN}",),
        "non-ascii": ("Authorization: Bearer " + "ä".encode().decode("latin-1") + TOKEN,),
        "cookie": (f"Cookie: access_token={TOKEN}",),
        "other header": (f"X-Api-Token: {TOKEN}",),
        "proxy-authorization": (f"Proxy-Authorization: Bearer {TOKEN}",),
    }


def test_every_failure_gets_the_identical_401(api: Callable[..., Client]) -> None:
    port = api().port
    ref = _reference_401(port)
    seen: dict[bytes, str] = {}
    for method in FAIL_METHODS:
        for path in FAIL_PATHS:
            for name, lines in _failure_variants().items():
                seen.setdefault(normalised(raw(port, _request(method, path, *lines))), f"{method} {path} {name}")
    assert list(seen) == [ref], sorted(seen.values())


def test_head_failures_have_the_same_headers_and_no_body(api: Callable[..., Client]) -> None:
    port = api().port
    ref_head = _reference_401(port)[: -len(_UNAUTHORIZED_BODY)]
    seen: dict[bytes, str] = {}
    for path in FAIL_PATHS:
        for name, lines in _failure_variants().items():
            seen.setdefault(normalised(raw(port, _request("HEAD", path, *lines))), f"HEAD {path} {name}")
    assert list(seen) == [ref_head], sorted(seen.values())


def test_accepted_spellings(api: Callable[..., Client]) -> None:
    port = api().port
    for value in (f"bearer {TOKEN}", f"BEARER {TOKEN}", f"Bearer  {TOKEN}", f"Bearer {TOKEN}   "):
        resp = raw(port, _request("GET", "/api/ping", f"Authorization: {value}"))
        head, _, body = resp.partition(b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.1 200 "), value.replace(TOKEN, "TOKEN")
        assert json.loads(body) == {"ok": True}


def test_401_header_order_is_fixed(api: Callable[..., Client]) -> None:
    port = api().port
    expected = [
        b"content-type",
        b"content-length",
        b"cache-control",
        b"x-content-type-options",
        b"referrer-policy",
        b"www-authenticate",
        b"connection",
    ]
    for name, lines in _failure_variants().items():
        head = normalised(raw(port, _request("GET", "/api/ping", *lines))).partition(b"\r\n\r\n")[0]
        names = [line.split(b":", 1)[0].lower() for line in head.split(b"\r\n")[1:]]
        assert names == expected, name


def test_token_only_from_the_authorization_header(api: Callable[..., Client]) -> None:
    port = api().port
    ref = _reference_401(port)
    for data in (
        _request("GET", f"/api/ping?access_token={TOKEN}"),
        _request("GET", "/api/ping", f"Cookie: access_token={TOKEN}"),
        _request("GET", "/api/ping", f"X-Api-Token: {TOKEN}"),
        _request("GET", "/api/ping", f"Proxy-Authorization: Bearer {TOKEN}"),
    ):
        assert normalised(raw(port, data)) == ref
    form = f"access_token={TOKEN}".encode()
    post = (
        "POST /api/echo HTTP/1.1\r\nHost: test\r\nContent-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(form)}\r\nConnection: close\r\n\r\n"
    ).encode() + form
    assert normalised(raw(port, post)) == ref


def test_unread_body_closes_the_connection(api: Callable[..., Client]) -> None:
    calls: list[Any] = []
    port = api(build_api_router(calls)).port
    wrong = "wrong-" + secrets.token_hex(8)
    data = (
        "POST /api/echo HTTP/1.1\r\nHost: test\r\nContent-Type: application/json\r\nContent-Length: 5\r\n"
        f"Authorization: Bearer {wrong}\r\n\r\nhello"
        f"GET /api/ping HTTP/1.1\r\nHost: test\r\nAuthorization: Bearer {TOKEN}\r\n\r\n"
    ).encode()
    resp = raw(port, data)
    assert resp.count(b"HTTP/1.") == 1, resp
    head, _, body = resp.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.1 401 ")
    assert b"\r\nConnection: close" in head
    assert body == _UNAUTHORIZED_BODY
    assert calls == []


# --- no token, bearer value or stored digest ever reaches stdout or stderr (D-09, AUB-04) ---


def test_handle_error_prints_only_the_exception_class(capfd: pytest.CaptureFixture[str]) -> None:
    server = make_api_server(build_api_router(), 0, OptionToken(TOKEN), bind="127.0.0.1")
    try:
        try:
            raise RuntimeError(f"Bearer {TOKEN}")
        except RuntimeError:
            server.handle_error(None, ("127.0.0.1", 0))
    finally:
        server.server_close()
    out, err = capfd.readouterr()
    assert out == "api request failed: RuntimeError\n"
    assert err == ""
    assert TOKEN not in out + err


def test_no_secret_reaches_stdout_or_stderr(
    api: Callable[..., Client], tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    generated = GeneratedToken.load_or_create(tmp_path / "api-token")
    option_client = api()
    generated_client = api(verifier=generated)
    first = generated.take_plaintext()
    assert first is not None
    wrong = "wrong-" + secrets.token_hex(16)
    rotated: list[str] = []

    def _calls(client: Client, token: str) -> list[Callable[[], Any]]:
        auth = {"Authorization": f"Bearer {token}"}
        return [
            lambda: client.call("GET", "/api/ping", auth),
            lambda: client.call("GET", "/api/ping", {"Authorization": f"Bearer {wrong}"}),
            lambda: client.call("GET", f"/api/ping?access_token={token}"),
            lambda: raw(
                client.port,
                _request("GET", "/api/ping", f"Authorization: Bearer {token}", f"Authorization: Bearer {wrong}"),
            ),
            lambda: client.call("GET", "/api/boom", auth),
        ]

    calls = _calls(option_client, TOKEN) + _calls(generated_client, first)
    jobs: list[Callable[[], Any]] = [calls[i % len(calls)] for i in range(48)]
    # Token lifecycle events run in the same pool as the requests
    jobs.insert(10, generated.take_plaintext)
    jobs.insert(25, lambda: rotated.append(generated.rotate()))
    assert len(jobs) == 50
    with ThreadPoolExecutor(8) as pool:
        for future in [pool.submit(job) for job in jobs]:
            future.result()
    assert len(rotated) == 1
    new = rotated[0]
    # The rotated token works on the live server; the old one is gone
    assert generated_client.call("GET", "/api/ping", {"Authorization": f"Bearer {new}"})[0] == 200
    assert generated_client.call("GET", "/api/boom", {"Authorization": f"Bearer {new}"})[0] == 500
    assert generated_client.call("GET", "/api/ping", {"Authorization": f"Bearer {first}"})[0] == 401

    out, err = capfd.readouterr()
    secrets_to_hide = [TOKEN, f"Bearer {TOKEN}", first, f"Bearer {first}", new, f"Bearer {new}"]
    secrets_to_hide += [hashlib.sha256(value.encode("ascii")).hexdigest() for value in (TOKEN, first, new)]
    for secret in secrets_to_hide:
        assert secret not in out
        assert secret not in err
    # The capture is not vacuous: the handler traceback of /api/boom reached it
    assert "Traceback" in out
