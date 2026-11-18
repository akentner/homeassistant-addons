"""GUI server routes behind the skeleton's ingress gate: overview, meta, Sync now, gate matrix, OSError hygiene."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.paths import Paths
from app.web.admin_ui import INGRESS_REMOTE
from app.web.server import build_router, make_server
from app.web.service import GuiConfig, GuiService, load_gui_config
from guihelpers import INGRESS, serve, write_options  # noqa: F401

REPO = "example-org/private-addons"
LOOPBACK = "127.0.0.1"
HEX32 = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")
JSON = {**INGRESS, "Content-Type": "application/json"}


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    p = Paths.under(tmp_path)
    write_options(p, [{"repository": REPO}])
    return p


def make_service(paths: Paths, version: str | None = None) -> GuiService:
    config = load_gui_config(paths, hostname="h", version_file=paths.data_dir / "none")
    return GuiService(paths, GuiConfig(config.options, config.hostname, version))


def start(serve: Any, svc: GuiService, ingress_remote: str = LOOPBACK) -> Any:
    return serve(make_server(svc, 0, ingress_remote=ingress_remote, host=LOOPBACK))


def test_overview_needs_ingress_header(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths))
    status, _resp, body = client.call("GET", "/api/overview")
    assert status == 403 and json.loads(body)["error"] == "ingress_only"
    status, resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 200
    assert resp.getheader("Cache-Control") == "no-store"
    assert json.loads(body)["repositories"][0]["repository"] == REPO


@pytest.mark.parametrize("version", ["0.1.0-3", None])
def test_meta_route(serve: Any, paths: Paths, version: str | None) -> None:
    client = start(serve, make_service(paths, version))
    status, resp, body = client.call("GET", "/api/meta", INGRESS)
    assert status == 200
    assert resp.getheader("Cache-Control") == "no-store"
    assert json.loads(body) == {"version": version}


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
@pytest.mark.parametrize("path", ["/", "/api/overview", "/api/meta", "/api/sync", "/static/app.mjs"])
def test_gate_matrix_without_header(serve: Any, paths: Paths, method: str, path: str) -> None:
    client = start(serve, make_service(paths))
    status, _resp, body = client.call(method, path)
    assert status == 403
    assert json.loads(body)["error"] == "ingress_only"


def test_real_ingress_remote_refuses_loopback_with_header(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths), ingress_remote=INGRESS_REMOTE)
    for path in ("/", "/api/overview", "/api/meta"):
        status, _resp, _body = client.call("GET", path, INGRESS)
        assert status == 403


def test_no_public_route(paths: Paths) -> None:
    router = build_router(make_service(paths))
    routes = router.routes()
    assert routes
    assert not any(router.is_public(method, pattern) for method, pattern in routes)
    assert {("GET", "/api/overview"), ("GET", "/api/meta"), ("POST", "/api/sync")} <= set(routes)


def test_static_page_served_through_ingress(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths))
    for path in ("/", "/static/app.mjs", "/static/views/repositories.mjs"):
        status, _resp, _body = client.call("GET", path, INGRESS)
        assert status == 200, path


def test_sync_post_with_empty_object(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths))
    status, resp, body = client.call("POST", "/api/sync", JSON, b"{}")
    assert status == 202
    assert json.loads(body) == {"requested": True}
    assert resp.getheader("Cache-Control") == "no-store"
    assert json.loads(paths.trigger_file.read_text(encoding="utf-8")) == {}


@pytest.mark.parametrize(
    "headers,body",
    [
        (INGRESS, None),
        (JSON, b"[]"),
        (JSON, b'{"x": 1}'),
        ({**INGRESS, "Content-Type": "text/plain"}, b"{}"),
    ],
    ids=["no_body", "array", "unknown_field", "text_plain"],
)
def test_sync_post_bad_request(serve: Any, paths: Paths, headers: dict[str, str], body: bytes | None) -> None:
    client = start(serve, make_service(paths))
    status, _resp, raw = client.call("POST", "/api/sync", headers, body)
    assert status == 400
    assert json.loads(raw)["error"] == "bad_request"
    assert not paths.trigger_file.exists()


def test_os_error_is_internal_error_without_hash(
    serve: Any, paths: Paths, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    hash_ = "0123456789abcdef0123456789abcdef"
    svc = make_service(paths)

    def broken() -> dict:
        raise PermissionError(13, "Permission denied", f"/srv/git/access/example-org/private-addons/{hash_}")

    monkeypatch.setattr(svc, "overview", broken)
    client = start(serve, svc)
    status, _resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 500
    assert json.loads(body)["error"] == "internal_error"
    assert not HEX32.search(body.decode("utf-8"))
    captured = capsys.readouterr()
    assert not HEX32.search(captured.out + captured.err)
