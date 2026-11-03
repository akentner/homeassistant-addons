"""Tracer: one path end to end - synced skeleton (app.web.admin_ui) -> gate -> router -> hosts file -> real status.sh."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import FIXTURE_FP, FIXTURE_TYPE, INGRESS

METHODS = ("GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS")
PATHS = ("/", "/api/overview", "/static/vendor/admin-ui/base.css", "/nope")
RAW_VARIANTS = ("//api/overview", "/api/overview/", "/api/%6Fverview", "/API/overview")


def make(env: dict[str, Path], remote: str = "127.0.0.1") -> Any:
    from app.web.server import Sources, make_server

    sources = Sources(env["hosts_file"], env["logdir"], env["status_sh"], env["env_file"])
    return make_server(sources, 0, host="127.0.0.1", ingress_remote=remote)


def test_skeleton_imports_as_package() -> None:
    import app.web.admin_ui as skeleton

    assert skeleton.INGRESS_REMOTE == "172.30.32.2"


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", PATHS + RAW_VARIANTS)
def test_gate_closes_everything_without_ingress(serve: Any, env: dict[str, Path], method: str, path: str) -> None:
    client = serve(make(env))
    status, _resp, body = client.call(method, path)
    assert status == 403
    if method != "HEAD":
        assert json.loads(body) == {"error": "ingress_only"}


@pytest.mark.parametrize("path", ("/", "/api/overview", "//api/overview"))
def test_gate_rejects_foreign_peer(serve: Any, env: dict[str, Path], path: str) -> None:
    client = serve(make(env, remote="10.255.255.1"))
    status, _resp, body = client.call("GET", path, INGRESS)
    assert status == 403
    assert json.loads(body) == {"error": "ingress_only"}


def test_no_public_routes(env: dict[str, Path]) -> None:
    from app.web.server import Sources, build_router

    router = build_router(Sources(env["hosts_file"], env["logdir"], env["status_sh"], env["env_file"]))
    routes = router.routes()
    assert routes == [("GET", "/api/overview")]
    for method, path in routes:
        assert router.is_public(method, path) is False


def test_overview_runs_the_real_status_sh(serve: Any, env: dict[str, Path]) -> None:
    client = serve(make(env))
    status, resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 200
    assert resp.getheader("Content-Type", "").startswith("application/json")
    data = json.loads(body)
    assert isinstance(data["now_ms"], int)
    assert len(data["hosts"]) == 1
    host = data["hosts"][0]
    assert (host["slug"], host["name"], host["host"]) == ("ha_backup", "ha-backup", "192.0.2.9")
    assert host["error"] is None
    assert host["status"]["key_fp"] == FIXTURE_FP
    assert host["status"]["key_type"] == FIXTURE_TYPE
    assert isinstance(host["status"]["age"], int) and host["status"]["age"] < 60
    assert host["status"]["problem"] in (0, 1)


def test_static_lib_copy_is_served(serve: Any, env: dict[str, Path]) -> None:
    client = serve(make(env))
    status, resp, _body = client.call("GET", "/static/vendor/admin-ui/base.css", INGRESS)
    assert status == 200
    assert resp.getheader("Content-Type", "").startswith("text/css")
    for hidden in ("LIB.stamp", "VERSION"):
        status, _resp, _body = client.call("GET", f"/static/vendor/admin-ui/{hidden}", INGRESS)
        assert status == 404
