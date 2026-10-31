"""Tests for app.web.server against a fake Controller and state files (no secrets involved)."""

from __future__ import annotations

import copy
import http.client
import json
import threading
from pathlib import Path
from typing import Any, Iterator

import pytest

from app.web.server import make_server

DOCS = Path(__file__).resolve().parents[2] / "docs"
EXAMPLE = json.loads((DOCS / "state.example.json").read_text())
SECRET = "S3cr3t-VALUE-do-not-leak"
INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}


class FakeController:
    def __init__(self) -> None:
        self.allow = True
        self.calls: list[str] = []

    def trigger_sync(self, force: bool = False) -> bool:
        self.calls.append("force" if force else "sync")
        return self.allow

    def preview(self) -> dict[str, Any]:
        self.calls.append("preview")
        return {"added": ["a"], "removed": [], "changed": ["b"], "errors": []}


class Srv:
    def __init__(self, ctrl: Any, state: Path, ingress_only: bool = True) -> None:
        # Remote is 127.0.0.1 in tests, so it plays the role of the Supervisor proxy.
        self.httpd = make_server(ctrl, state, 0, ingress_only, host="127.0.0.1", ingress_remote="127.0.0.1")
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def req(self, method: str, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp.status, body

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    p = tmp_path / "state.json"
    p.write_text(json.dumps(EXAMPLE))
    return p


@pytest.fixture
def ctrl() -> FakeController:
    return FakeController()


@pytest.fixture
def srv(ctrl: FakeController, state_file: Path) -> Iterator[Srv]:
    s = Srv(ctrl, state_file)
    yield s
    s.close()


def test_status_json_is_state(srv: Srv) -> None:
    code, body = srv.req("GET", "/api/status.json")
    assert code == 200 and json.loads(body) == EXAMPLE


def test_health_ok(srv: Srv) -> None:
    code, body = srv.req("GET", "/api/health")
    data = json.loads(body)
    assert code == 200
    assert data == {"status": "ok", "age_seconds": 2, "stale": False, "items": 42, "error_code": None}


@pytest.mark.parametrize("status", ["degraded", "error", "starting"])
def test_health_503_for_bad_status(ctrl: FakeController, tmp_path: Path, status: str) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["status"] = status
    p = tmp_path / "s.json"
    p.write_text(json.dumps(st))
    s = Srv(ctrl, p)
    try:
        code, body = s.req("GET", "/api/health")
        assert code == 503 and json.loads(body)["status"] == status
    finally:
        s.close()


def test_health_503_when_stale(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["age_seconds"] = 601  # > 2 * interval (300), flag not set
    p = tmp_path / "s.json"
    p.write_text(json.dumps(st))
    s = Srv(ctrl, p)
    try:
        code, body = s.req("GET", "/api/health")
        assert code == 503 and json.loads(body)["stale"] is True
    finally:
        s.close()


@pytest.mark.parametrize("content", [None, "", "{not json", "[]", '{"status": "ok"', '{"events": "x", "keys": 3}'])
def test_missing_or_partial_state_tolerated(ctrl: FakeController, tmp_path: Path, content: str | None) -> None:
    p = tmp_path / "s.json"
    if content is not None:
        p.write_text(content)
    s = Srv(ctrl, p)
    try:
        assert s.req("GET", "/", INGRESS)[0] == 200
        assert s.req("GET", "/api/status.json")[0] == 200
        assert s.req("GET", "/api/health")[0] == 503
    finally:
        s.close()


def test_schema_invalid_state_does_not_crash(ctrl: FakeController, tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({
        "status": 5, "providers": {"x": "bad", "y": {"problems": "no"}}, "events": [1, None, {"level": 3}],
        "keys": {"names": "abc", "added": None}, "versions": [], "items": "many", "age_seconds": "x",
    }))
    s = Srv(ctrl, p)
    try:
        assert s.req("GET", "/", INGRESS)[0] == 200
        assert s.req("GET", "/api/health")[0] == 503
    finally:
        s.close()


def test_no_response_contains_secret_values(ctrl: FakeController, state_file: Path, tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.yaml"
    secrets.write_text(f'mqtt_password: "{SECRET}"\nmqtt_username: "user-{SECRET}"\n')
    s = Srv(ctrl, state_file)
    try:
        for method, path, hdr in [
            ("GET", "/", INGRESS),
            ("GET", "/api/status.json", None),
            ("GET", "/api/health", None),
            ("POST", "/api/sync", INGRESS),
            ("POST", "/api/preview", INGRESS),
            ("GET", "/nope", None),
        ]:
            _, body = s.req(method, path, hdr)
            assert SECRET not in body
    finally:
        s.close()


def test_post_requires_ingress(srv: Srv, ctrl: FakeController) -> None:
    assert srv.req("POST", "/api/sync")[0] == 403
    assert srv.req("POST", "/api/preview")[0] == 403
    assert ctrl.calls == []


def test_post_requires_ingress_remote(ctrl: FakeController, state_file: Path) -> None:
    s = Srv(ctrl, state_file)
    s.httpd.shutdown()
    s.httpd.server_close()
    other = make_server(ctrl, state_file, 0, True, host="127.0.0.1")  # default remote 172.30.32.2
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", other.server_address[1], timeout=5)
        conn.request("POST", "/api/sync", headers=INGRESS)
        assert conn.getresponse().status == 403
    finally:
        other.shutdown()
        other.server_close()
    assert ctrl.calls == []


def test_sync_202_and_429(srv: Srv, ctrl: FakeController) -> None:
    code, body = srv.req("POST", "/api/sync", INGRESS)
    assert code == 202 and json.loads(body) == {"started": True}
    ctrl.allow = False
    assert srv.req("POST", "/api/sync", INGRESS)[0] == 429


def test_sync_force_passed(state_file: Path) -> None:
    c = FakeController()
    s = Srv(c, state_file)
    try:
        assert s.req("POST", "/api/sync?force=1", INGRESS)[0] == 202
        assert s.req("POST", "/api/sync", INGRESS)[0] == 202
    finally:
        s.close()
    assert c.calls == ["force", "sync"]


def test_preview(srv: Srv) -> None:
    code, body = srv.req("POST", "/api/preview", INGRESS)
    assert code == 200 and json.loads(body)["added"] == ["a"]


def test_controller_exception_is_not_leaked(state_file: Path) -> None:
    class Boom(FakeController):
        def preview(self) -> dict[str, Any]:
            raise RuntimeError(f"bw said {SECRET}")

    s = Srv(Boom(), state_file)
    try:
        code, body = s.req("POST", "/api/preview", INGRESS)
        assert code == 500 and SECRET not in body
    finally:
        s.close()


def test_unknown_routes_and_methods(srv: Srv) -> None:
    assert srv.req("GET", "/api/nope")[0] == 404
    assert srv.req("POST", "/api/health", INGRESS)[0] == 404


def test_shell_is_static_and_relative(srv: Srv, state_file: Path) -> None:
    code, body = srv.req("GET", "/", INGRESS)
    assert code == 200
    assert 'href="static/app.css"' in body and 'src="static/app.js"' in body
    for needle in ("mqtt_password", "bitwarden", "sync_ok"):
        assert needle not in body  # no state data in the shell
    assert "http://" not in body.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in body
    assert 'src="./icon"' in body
    assert 'href="/' not in body and 'src="/' not in body and "innerHTML" not in body


def test_shell_identical_for_any_state(ctrl: FakeController, tmp_path: Path) -> None:
    bodies = []
    for content in ("{}", json.dumps(EXAMPLE), "garbage"):
        p = tmp_path / "s.json"
        p.write_text(content)
        s = Srv(ctrl, p)
        try:
            bodies.append(s.req("GET", "/", INGRESS)[1])
        finally:
            s.close()
    assert len(set(bodies)) == 1


@pytest.mark.parametrize(
    ("path", "ctype"),
    [("/static/app.css", "text/css"), ("/static/app.js", "text/javascript"), ("/", "text/html")],
)
def test_assets_served_with_headers(srv: Srv, path: str, ctype: str) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
    conn.request("GET", path, headers=INGRESS)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    assert resp.status == 200 and body
    assert resp.getheader("Content-Type", "").startswith(ctype)
    assert resp.getheader("Cache-Control") == "no-cache"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"


@pytest.mark.parametrize("path", ["/static/app.css", "/static/app.js", "/"])
def test_assets_ingress_only(srv: Srv, path: str) -> None:
    assert srv.req("GET", path)[0] == 403


@pytest.mark.parametrize(
    "path",
    [
        "/static/", "/static", "/static/index.html", "/static/../app/web/server.py", "/static/%2e%2e/server.py",
        "/static/..%2fserver.py", "/static/app.js/", "/static/app.js/../server.py", "/index.html", "/app.js",
        "//etc/passwd", "/static/nope.js", "/%2e%2e/%2e%2e/etc/passwd",
    ],
)
def test_asset_whitelist_and_traversal(srv: Srv, path: str) -> None:
    code, body = srv.req("GET", path, INGRESS)
    assert code == 404
    assert "def " not in body and "root:" not in body


def test_asset_query_string_ignored(srv: Srv) -> None:
    assert srv.req("GET", "/static/app.js?v=1", INGRESS)[0] == 200


def test_assets_use_no_inner_html_or_external_urls() -> None:
    static = Path(__file__).resolve().parents[2] / "app" / "web" / "static"
    js = (static / "app.js").read_text()
    assert "innerHTML" not in js and "outerHTML" not in js and "insertAdjacentHTML" not in js
    assert "document.write" not in js and "eval(" not in js
    for f in static.iterdir():
        if f.suffix == ".png":
            continue
        text = f.read_text()
        assert "http://" not in text.replace("http://www.w3.org/2000/svg", "") and "https://" not in text
        assert "@import" not in text and "url(" not in text


def test_obsolete_server_side_rendering_removed() -> None:
    import app.web.server as server

    assert not hasattr(server, "render_page")
    assert not [n for n in dir(server) if n.startswith("_render")]


def test_status_json_with_guard_variant(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["error_code"] = "shrink_guard"
    st["guard"] = {"new_items": 1, "last_items": 9, "removed": ["a"], "added": [], "changed": []}
    p = tmp_path / "s.json"
    p.write_text(json.dumps(st))
    s = Srv(ctrl, p)
    try:
        assert json.loads(s.req("GET", "/api/status.json")[1]) == st
    finally:
        s.close()


def test_icon_asset_is_served_and_matches_the_store_icon(srv: Srv) -> None:
    import http.client

    def raw(headers: dict[str, str]) -> tuple[int, str, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
        conn.request("GET", "/icon", headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, resp.getheader("Content-Type") or "", data

    code, ctype, data = raw(INGRESS)
    assert code == 200 and ctype == "image/png" and data.startswith(b"\x89PNG")
    assert raw({})[0] == 403  # ingress only like the other assets
    store = Path(__file__).resolve().parents[2] / "icon.png"
    assert data == store.read_bytes()  # the copy must stay in sync with the add-on store icon
