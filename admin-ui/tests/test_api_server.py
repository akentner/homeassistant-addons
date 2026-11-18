"""Tests for the bearer-gated API listener: option token, gate, shared JSON base, router dispatch over a real socket."""

from __future__ import annotations

import inspect
import json
import secrets
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from app.web.skeleton import ERROR_STATUS, Request, Router
from app.web.skeleton.api import make_api_server
from app.web.skeleton.tokens import OptionToken
from test_skeleton_server import Client

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
