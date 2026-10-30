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


def test_page_renders_state(srv: Srv) -> None:
    code, body = srv.req("GET", "/", INGRESS)
    assert code == 200
    for needle in ("mqtt_password", "bitwarden", "sops", "sync_ok", "Sync now", "Preview", "0.1.0"):
        assert needle in body
    assert "http://" not in body and "https://" not in body
    assert "fetch(url" in body and "'api/sync'" in body and "'api/preview'" in body


def test_page_requires_ingress(srv: Srv) -> None:
    assert srv.req("GET", "/")[0] == 403


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
        code, body = s.req("GET", "/", INGRESS)
        assert code == 200 and "starting" in body
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


def test_events_and_fields_are_escaped(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    evil = f"<script>alert('{SECRET}')</script>"
    st["events"][0]["message"] = evil
    st["keys"]["names"] = ["<img src=x onerror=1>"]
    st["providers"]["bitwarden"]["problems"] = [{"severity": "error", "code": "<b>", "message": evil}]
    p = tmp_path / "s.json"
    p.write_text(json.dumps(st))
    s = Srv(ctrl, p)
    try:
        _, body = s.req("GET", "/", INGRESS)
        assert "<script>alert(" not in body
        assert "<img src=x" not in body and "<b>" not in body
        assert "&lt;script&gt;alert(&#x27;" in body
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


def test_page_shows_usage_and_escapes(srv: Srv, state_file: Path) -> None:
    data = json.loads(state_file.read_text())
    data["usage"]["missing"]["<script>x</script>"] = {"count": 1, "refs": [{"file": "a<b>.yaml", "line": 3}]}
    state_file.write_text(json.dumps(data))
    status, page = srv.req("GET", "/", INGRESS)
    assert status == 200 and "Secret usage" in page and "mqtt_password" in page and "old_api_key" in page
    assert "<script>x</script>" not in page and "&lt;script&gt;x&lt;/script&gt;" in page


def test_page_without_usage_block_still_renders(srv: Srv, state_file: Path) -> None:
    data = json.loads(state_file.read_text())
    data.pop("usage")
    state_file.write_text(json.dumps(data))
    status, page = srv.req("GET", "/", INGRESS)
    assert status == 200 and "scan is off" in page


def _page(ctrl: FakeController, tmp_path: Path, state: dict[str, Any]) -> str:
    p = tmp_path / "s.json"
    p.write_text(json.dumps(state))
    s = Srv(ctrl, p)
    try:
        code, body = s.req("GET", "/", INGRESS)
        assert code == 200
        return body
    finally:
        s.close()


def test_check_block_rendered_from_example(srv: Srv) -> None:
    _, body = srv.req("GET", "/", INGRESS)
    assert "Change check" in body and "enabled, every 60 s" in body
    assert "unchanged" in body and "Triggered syncs" in body


def test_old_state_without_check_renders_nothing(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st.pop("check")
    body = _page(ctrl, tmp_path, st)
    assert "Change check" not in body and "Triggered syncs" not in body


def test_check_error_and_changed(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["check"].update(result="error", error_code="git_auth_failed", triggered_syncs=3)
    body = _page(ctrl, tmp_path, st)
    assert 'class="badge error">error<' in body and "git_auth_failed" in body
    st["check"].update(result="changed", error_code=None)
    assert 'class="badge changed">changed<' in _page(ctrl, tmp_path, st)


def test_check_disabled(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["check"] = {"enabled": False, "interval": 0, "last_check_at": None, "result": None}
    body = _page(ctrl, tmp_path, st)
    assert "Change check" in body and "disabled" in body and "every" not in body.split("Change check")[1][:200]


def test_check_garbage_and_escaping(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["check"] = {"enabled": True, "interval": "<b>", "last_check_at": "nope", "result": "<i>", "error_code": "<u>"}
    body = _page(ctrl, tmp_path, st)
    assert "<b>" not in body and "<i>" not in body and "<u>" not in body
    assert _page(ctrl, tmp_path, {**EXAMPLE, "check": "x"})  # non-dict tolerated


def test_provider_revision_shown(srv: Srv) -> None:
    _, body = srv.req("GET", "/", INGRESS)
    assert "Revision" in body and "<code>1761560000</code>" in body


def test_ago() -> None:
    from datetime import datetime, timezone

    from app.web.server import _ago

    now = datetime(2026, 10, 27, 16, 1, 30, tzinfo=timezone.utc)
    assert _ago("2026-10-27T16:00:30Z", now) == "1 min ago"
    assert _ago("2026-10-27T16:01:20Z", now) == "10 s ago"
    assert _ago("2026-10-27T19:01:30Z", now) == "just now"
    assert _ago(None, now) == "-" and _ago("junk", now) == "-"


def test_synthetic_keys_badged(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["keys"]["names"] = ["db_dsn", "mqtt_password", "<x>"]
    st["keys"]["added"] = ["db_dsn"]
    st["keys"]["synthetic"] = ["db_dsn", "<x>"]
    body = _page(ctrl, tmp_path, st)
    assert "<code>db_dsn</code> <span" in body and body.count('class="tag">synthetic<') == 3
    assert "<code>mqtt_password</code> <span" not in body
    assert "<x>" not in body and "&lt;x&gt;" in body


def test_old_state_without_synthetic_renders_as_before(srv: Srv) -> None:
    _, body = srv.req("GET", "/", INGRESS)
    assert 'class="tag">synthetic<' not in body and "<code>mqtt_password</code>" in body


def test_synthetic_garbage_tolerated(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["keys"]["synthetic"] = "nope"
    assert _page(ctrl, tmp_path, st)
    st["keys"]["synthetic"] = [None, 3]
    assert _page(ctrl, tmp_path, st)


def test_synthetic_card_shows_config_refs_and_status(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st["synthetic"] = [
        {"name": "db_dsn", "template": "pg://{{ db_user }}@h", "refs": ["db_user"], "status": "ok", "error_code": None},
        {"name": "<bad>", "template": "{{ x ", "refs": [], "status": "error", "error_code": "synthetic_syntax"},
        {"name": "wait", "template": "{{ y }}", "refs": ["y"], "status": "pending", "error_code": None},
    ]
    body = _page(ctrl, tmp_path, st)
    assert "<h2>Synthetic keys</h2>" in body
    assert "pg://{{ db_user }}@h" in body and "<code>db_user</code>" in body
    assert "synthetic_syntax" in body and "parsed (not rendered yet)" in body
    assert "<bad>" not in body and "&lt;bad&gt;" in body


def test_no_synthetic_card_when_absent_or_empty(ctrl: FakeController, tmp_path: Path) -> None:
    st = copy.deepcopy(EXAMPLE)
    st.pop("synthetic", None)
    assert "<h2>Synthetic keys</h2>" not in _page(ctrl, tmp_path, st)
    st["synthetic"] = []
    assert "<h2>Synthetic keys</h2>" not in _page(ctrl, tmp_path, st)
