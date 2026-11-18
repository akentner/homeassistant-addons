"""Tests for the bearer-gated API listener: option token, gate, shared JSON base, router dispatch over a real socket."""

from __future__ import annotations

import inspect
import json
import secrets
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from app.web.skeleton import ERROR_STATUS, Request, Router, make_server, serve
from app.web.skeleton.api import make_api_server
from app.web.skeleton.tokens import OptionToken
from test_skeleton_server import Client, build_router, make_static

# Generated per test run: obviously fake, never a real credential.
TOKEN = "test-token-" + secrets.token_hex(16)
UNAUTHORIZED = {"error": "unauthorized", "message": "unauthorized"}


def build_api_router() -> Router:
    router = Router()
    router.add("GET", "/api/ping", lambda req: {"ok": True})

    def headers(req: Request) -> Any:
        return {"authorization": req.headers.get("Authorization"), "public": req.public}

    router.add("GET", "/api/headers", headers)
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
