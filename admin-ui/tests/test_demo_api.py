"""Tests for the demo API (in-process server behind the ingress gate) and the env parsing of app.main."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from app.main import build_config
from app.web import demo_api
from app.web.skeleton import DEFAULT_CSP, ERROR_STATUS, Router, StaticFiles

from conftest import INGRESS, Client

JSON = {**INGRESS, "Content-Type": "application/json"}


@pytest.fixture
def api(serve: Callable[..., Client], tmp_path: Path) -> Client:
    router = Router()
    demo_api.register(router, version="9.9.9", lib_version="0.1.0", clock=lambda: 1234)
    return serve(router, StaticFiles(tmp_path))


def jcall(api: Client, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    raw = None if body is None else json.dumps(body).encode()
    status, _, data = api.call(method, path, headers or JSON, raw)
    return status, (json.loads(data) if data else None)


def test_health(api: Client) -> None:
    assert jcall(api, "GET", "/api/health", headers=INGRESS) == (
        200,
        {"status": "ok", "addon_version": "9.9.9", "lib_version": "0.1.0"},
    )


def test_seeds(api: Client) -> None:
    status, body = jcall(api, "GET", "/api/items", headers=INGRESS)
    assert status == 200
    items = body["items"]
    assert [i["name"] for i in items] == ["alpha", "beta", "locked"]
    assert [i["locked"] for i in items] == [False, False, True]
    assert all(set(i) == {"id", "name", "note", "locked", "created"} and i["created"] == 1234 for i in items)


def test_create_validation_and_conflict(api: Client) -> None:
    status, item = jcall(api, "POST", "/api/items", {"name": "  gamma ", "note": "n"})
    assert status == 201 and item["name"] == "gamma" and item["locked"] is False
    for bad in ({}, {"name": "  "}, {"name": "x" * 41}, {"name": 5}, {"name": "ok", "note": "n" * 201}):
        assert jcall(api, "POST", "/api/items", bad)[0] == 400, bad
    status, body = jcall(api, "POST", "/api/items", {"name": "ALPHA"})
    assert (status, body["error"]) == (409, "conflict")
    assert jcall(api, "POST", "/api/items", {"name": "x" * 40})[0] == 201


def test_update(api: Client) -> None:
    assert jcall(api, "PUT", "/api/items/1", {"note": "changed"})[1]["note"] == "changed"
    status, body = jcall(api, "PUT", "/api/items/1", {"name": "renamed"})
    assert status == 200 and body["name"] == "renamed" and body["note"] == "changed"
    assert jcall(api, "PUT", "/api/items/99", {"note": "x"})[1]["error"] == "not_found"
    assert jcall(api, "PUT", "/api/items/3", {"note": "x"})[1]["error"] == "protected"
    assert jcall(api, "PUT", "/api/items/1", {"name": "beta"})[1]["error"] == "conflict"
    assert jcall(api, "PUT", "/api/items/1", {"name": "Renamed"})[0] == 200  # own name is no conflict
    assert jcall(api, "PUT", "/api/items/1", {"name": ""})[0] == 400


def test_delete_order_and_type_to_confirm(api: Client) -> None:
    assert jcall(api, "DELETE", "/api/items/99", {"confirm": "x"})[1]["error"] == "not_found"
    assert jcall(api, "DELETE", "/api/items/3", {"confirm": "locked"})[1]["error"] == "protected"
    assert jcall(api, "DELETE", "/api/items/3")[1]["error"] == "protected"
    status, body = jcall(api, "DELETE", "/api/items/1")
    assert (status, body["error"]) == (400, "confirmation_required")
    assert jcall(api, "DELETE", "/api/items/1", {"confirm": "Alpha"})[0] == 400
    assert jcall(api, "DELETE", "/api/items/1", {"confirm": "alpha"}) == (204, None)
    names = [i["name"] for i in jcall(api, "GET", "/api/items", headers=INGRESS)[1]["items"]]
    assert names == ["beta", "locked"]


@pytest.mark.parametrize("code", sorted(ERROR_STATUS))
def test_fail_endpoint_every_code(api: Client, code: str) -> None:
    status, body = jcall(api, "GET", f"/api/fail/{code}", headers=INGRESS)
    assert status == ERROR_STATUS[code] and body["error"] == code


def test_fail_teapot_boom_and_unknown(api: Client, capsys: pytest.CaptureFixture[str]) -> None:
    assert ERROR_STATUS["teapot"] == 418
    assert jcall(api, "GET", "/api/fail/teapot", headers=INGRESS)[0] == 418
    status, body = jcall(api, "GET", "/api/fail/boom", headers=INGRESS)
    assert status == 500 and body["error"] == "internal_error" and "secret" not in json.dumps(body)
    assert "secret detail" in capsys.readouterr().out
    assert jcall(api, "GET", "/api/fail/nonsense", headers=INGRESS)[0] == 404


def test_slow_clamps_and_validates(api: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    waited: list[float] = []
    monkeypatch.setattr(demo_api, "_sleep", waited.append)
    assert jcall(api, "GET", "/api/slow", headers=INGRESS) == (200, {"ok": True, "waited_ms": 800})
    assert jcall(api, "GET", "/api/slow?ms=50", headers=INGRESS)[1]["waited_ms"] == 50
    assert jcall(api, "GET", "/api/slow?ms=999999", headers=INGRESS)[1]["waited_ms"] == 2000
    assert jcall(api, "GET", "/api/slow?ms=-5", headers=INGRESS)[1]["waited_ms"] == 0
    assert jcall(api, "GET", "/api/slow?ms=abc", headers=INGRESS)[0] == 400
    assert waited == [0.8, 0.05, 2.0, 0.0]


def test_whoami(api: Client) -> None:
    assert jcall(api, "GET", "/api/whoami", headers=INGRESS) == (200, {"user": None})
    status, body = jcall(
        api, "GET", "/api/whoami", headers={**INGRESS, "X-Remote-User-Name": "alex", "X-Remote-User-Groups": "a, b"}
    )
    assert status == 200 and body["user"]["name"] == "alex" and body["user"]["groups"] == ["a", "b"]
    assert set(body) == {"user"}  # no wholesale header dump


def test_echo_and_body_limit(api: Client) -> None:
    assert jcall(api, "POST", "/api/echo", {"a": [1, 2]}) == (200, {"echo": {"a": [1, 2]}})
    status, _, _ = api.call("POST", "/api/echo", JSON, b'{"x":"' + b"a" * 70000 + b'"}')
    assert status == 413


def test_state_is_per_register_call(serve: Callable[..., Client], tmp_path: Path) -> None:
    clients = []
    for _ in range(2):
        router = Router()
        demo_api.register(router, version="1", lib_version="1")
        clients.append(serve(router, StaticFiles(tmp_path)))
    jcall(clients[0], "POST", "/api/items", {"name": "only-first"})
    assert len(jcall(clients[1], "GET", "/api/items", headers=INGRESS)[1]["items"]) == 3


def test_build_config_defaults_and_overrides() -> None:
    cfg = build_config({})
    assert (cfg.port, cfg.ingress_remote, cfg.version, cfg.csp) == (8099, "172.30.32.2", "unknown", DEFAULT_CSP)
    cfg = build_config(
        {"ADMIN_UI_PORT": "9000", "ADMIN_UI_INGRESS_REMOTE": "1.2.3.4", "ADMIN_UI_VERSION": "2.0", "ADMIN_UI_CSP": "off"}
    )
    assert (cfg.port, cfg.ingress_remote, cfg.version, cfg.csp) == (9000, "1.2.3.4", "2.0", None)


def test_build_config_rejects_unknown_csp_mode() -> None:
    with pytest.raises(ValueError):
        build_config({"ADMIN_UI_CSP": "lax"})
