"""API tests for the maintenance slice (export, backups, resets, health) over an in-process server."""

from __future__ import annotations

import http.client
import json
import logging
import threading
from pathlib import Path
from typing import Any, Iterator

import pytest

from app import bootstrap
from app.web.api import backups as backups_api
from app.web.api import export as export_api
from app.web.api import health as health_api
from app.web.api import reset as reset_api
from app.web.server import Router, make_server
from helpers import ntfy_db
from helpers.ctx import make_context

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc", "Content-Type": "application/json"}
TOKEN = "tk_" + "b" * 29
HASH = "$2a$10$" + "z" * 53


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            data = None if body is None else json.dumps(body).encode()
            conn.request(method, path, body=data, headers=INGRESS)
            resp = conn.getresponse()
            return resp.status, resp, resp.read()
        finally:
            conn.close()

    def json(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        status, _resp, raw = self.call(method, path, body)
        return status, (json.loads(raw) if raw else None)


def serve(ctx: Any, *modules: Any) -> tuple[Any, Client, Router]:
    router = Router()
    for module in modules:
        module.register(router, ctx)
    httpd = make_server(router, 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, Client(httpd.server_address[1]), router


def seeded(tmp_path: Path, **opts: Any) -> Any:
    ctx = make_context(tmp_path, **opts)
    ntfy_db.add_user(ctx.paths.auth_db, "admin", role="admin", pass_hash=HASH)
    ntfy_db.add_user(ctx.paths.auth_db, "alice", pass_hash=HASH)
    ntfy_db.add_acl(ctx.paths.auth_db, "alice", "alerts", "rw")
    ntfy_db.add_token(ctx.paths.auth_db, "alice", TOKEN, label="phone")
    return ctx


@pytest.fixture()
def ctx(tmp_path: Path) -> Any:
    return seeded(tmp_path, admin_password="pw")


@pytest.fixture()
def data_client(ctx: Any) -> Iterator[Client]:
    httpd, client, _ = serve(ctx, export_api, backups_api)
    yield client
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture()
def reset_client(ctx: Any) -> Iterator[Client]:
    httpd, client, _ = serve(ctx, reset_api, health_api)
    yield client
    httpd.shutdown()
    httpd.server_close()


# --- export -------------------------------------------------------------------------------------------------------


def test_export_json_default(data_client: Client) -> None:
    status, resp, raw = data_client.call("GET", "/api/export")
    assert status == 200
    assert resp.getheader("Content-Disposition") == 'attachment; filename="ntfy-state.json"'
    doc = json.loads(raw)
    assert doc["schema"] == 1
    assert {u["name"] for u in doc["users"]} == {"admin", "alice"}
    assert doc["acl"][0]["topic"] == "alerts"
    assert doc["tokens"][0]["label"] == "phone"
    assert b"$2" not in raw
    assert b"tk_" not in raw
    assert all("password_hash" not in u for u in doc["users"])


def test_export_yaml_matches_json(data_client: Client) -> None:
    yaml = pytest.importorskip("yaml")
    _, resp, raw_json = data_client.call("GET", "/api/export")
    status, yresp, raw_yaml = data_client.call("GET", "/api/export?format=yaml")
    assert status == 200
    assert yresp.getheader("Content-Disposition") == 'attachment; filename="ntfy-state.yaml"'
    assert yresp.getheader("Content-Type").startswith("application/yaml")
    a, b = json.loads(raw_json), yaml.safe_load(raw_yaml)
    a.pop("generated_at")
    b.pop("generated_at")
    assert a == b


def test_export_with_hashes_is_audited(data_client: Client, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="ntfy.audit"):
        status, _resp, raw = data_client.call("GET", "/api/export?include_hashes=1")
    assert status == 200
    users = json.loads(raw)["users"]
    assert all(u["password_hash"] == HASH for u in users)
    assert [r.getMessage() for r in caplog.records if r.name == "ntfy.audit"] == ["export with password hashes"]
    assert b"tk_" not in raw


@pytest.mark.parametrize("query", ["format=xml", "include_hashes=2", "include_hashes=true", "format="])
def test_export_rejects_bad_parameters(data_client: Client, query: str) -> None:
    status, body = data_client.json("GET", f"/api/export?{query}")
    assert status == 400
    assert body["error"] == "bad_request"


# --- backups ------------------------------------------------------------------------------------------------------


def test_backup_create_list_download(data_client: Client) -> None:
    status, body = data_client.json("POST", "/api/backups", {})
    assert status == 201
    name = body["backup"]["name"]
    assert body["backup"]["reason"] == "manual"
    status, listing = data_client.json("GET", "/api/backups")
    assert status == 200
    assert [b["name"] for b in listing["backups"]] == [name]
    status, resp, raw = data_client.call("GET", f"/api/backups/{name}")
    assert status == 200
    assert raw.startswith(b"SQLite format 3")
    assert resp.getheader("Content-Disposition") == f'attachment; filename="{name}"'


def test_backup_list_is_newest_first(data_client: Client, ctx: Any) -> None:
    ctx.backups.create("old")
    data_client.json("POST", "/api/backups", {})
    names = [b["name"] for b in data_client.json("GET", "/api/backups")[1]["backups"]]
    assert len(names) == 2
    assert names == sorted(names, reverse=True) or names[0].endswith("manual.db")


def test_backup_create_rejects_non_object(data_client: Client) -> None:
    status, body = data_client.json("POST", "/api/backups", [1])
    assert status == 400
    assert body["error"] == "bad_request"


@pytest.mark.parametrize("name", ["..%2F..%2Fetc%2Fpasswd", "auth-..db", "x.db", "%2e%2e"])
def test_backup_download_rejects_bad_names(data_client: Client, name: str) -> None:
    status, _resp, raw = data_client.call("GET", f"/api/backups/{name}")
    assert status in (400, 404)
    assert b"root:" not in raw
    assert not raw.startswith(b"SQLite")


def test_backup_download_unknown_valid_name(data_client: Client) -> None:
    status, body = data_client.json("GET", "/api/backups/auth-20200101T000000Z-manual.db")
    assert status == 404
    assert body["error"] == "not_found"


def test_data_routes_are_the_owned_c10_rows(ctx: Any) -> None:
    router = Router()
    export_api.register(router, ctx)
    backups_api.register(router, ctx)
    assert sorted(router.routes()) == sorted(
        [
            ("GET", "/api/export"),
            ("GET", "/api/backups"),
            ("POST", "/api/backups"),
            ("GET", "/api/backups/{name}"),
        ]
    )


# --- resets -------------------------------------------------------------------------------------------------------

PHRASES = {"acls": "reset acls", "cache": "clear cache", "everything": "reset everything"}


@pytest.mark.parametrize("kind", ["acls", "cache", "everything"])
def test_reset_wrong_confirmation(reset_client: Client, ctx: Any, kind: str) -> None:
    status, body = reset_client.json("POST", f"/api/reset/{kind}", {"confirm": "yes"})
    assert status == 400
    assert body["error"] == "confirmation_required"
    assert ctx.db.counts() == {"users": 2, "acl_rules": 1, "tokens": 1}
    assert not ctx.paths.backup_dir.exists() or not list(ctx.paths.backup_dir.glob("auth-*.db"))


@pytest.mark.parametrize("body", [[1], {}, {"confirm": 5}, {"confirm": None}])
@pytest.mark.parametrize("kind", ["acls", "cache", "everything"])
def test_reset_bad_body(reset_client: Client, kind: str, body: Any) -> None:
    status, resp = reset_client.json("POST", f"/api/reset/{kind}", body)
    assert status == 400
    assert resp["error"] == "bad_request"


def test_reset_acls_route(reset_client: Client, ctx: Any) -> None:
    status, body = reset_client.json("POST", "/api/reset/acls", {"confirm": PHRASES["acls"]})
    assert status == 200
    assert body["done"] is True
    assert body["backup"]["reason"] == "reset-acls"
    assert ctx.db.counts()["acl_rules"] == 0
    assert ctx.db.counts()["users"] == 2


def test_reset_cache_route(reset_client: Client, ctx: Any) -> None:
    import sqlite3

    conn = sqlite3.connect(ctx.paths.cache_db)
    conn.execute("CREATE TABLE messages (id INT, topic TEXT)")
    conn.executemany("INSERT INTO messages VALUES (?, 't')", [(1,), (2,)])
    conn.commit()
    conn.close()
    status, body = reset_client.json("POST", "/api/reset/cache", {"confirm": PHRASES["cache"]})
    assert status == 200
    assert body["messages_deleted"] == 2
    assert body["attachments_deleted"] == 0


def test_reset_everything_route(reset_client: Client, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bootstrap,
        "apply_options",
        lambda c: c.cli.user_add(c.options.admin_user, c.options.admin_password, role="admin"),
    )
    status, body = reset_client.json("POST", "/api/reset/everything", {"confirm": PHRASES["everything"]})
    assert status == 200
    assert body["backup"]["reason"] == "reset-everything"
    assert [u["name"] for u in ctx.db.list_users() if u["name"] != "everyone"] == ["admin"]


def test_reset_everything_without_admin_password(tmp_path: Path) -> None:
    ctx = seeded(tmp_path, admin_password="")
    httpd, client, _ = serve(ctx, reset_api)
    try:
        status, body = client.json("POST", "/api/reset/everything", {"confirm": PHRASES["everything"]})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 409
    assert body["error"] == "conflict"
    assert ctx.db.counts()["users"] == 2


# --- health -------------------------------------------------------------------------------------------------------


def test_health_fills_counts(reset_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_api, "ntfy_health", lambda: {"healthy": True, "role": "server"})
    status, body = reset_client.json("GET", "/api/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["counts"] == {"users": 2, "acl_rules": 1, "tokens": 1}
    assert body["db"]["schema_version"] == 10


def test_health_degraded_on_unsupported_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from helpers.ntfy_db import make_auth_db

    ctx = make_context(tmp_path)
    ctx.paths.auth_db.unlink()
    make_auth_db(ctx.paths.auth_db, version=9)
    monkeypatch.setattr(health_api, "ntfy_health", lambda: {"healthy": True, "role": "server"})
    httpd, client, _ = serve(ctx, health_api)
    try:
        status, body = client.json("GET", "/api/health")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200
    assert body["status"] == "degraded"
    assert body["counts"] is None
    assert body["db"]["supported"] is False


def test_health_publish_route(reset_client: Client, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[Any, ...]] = []

    def fake(context: Any, topic: str, message: str | None = None) -> dict[str, Any]:
        seen.append((context is ctx, topic, message))
        return {"ok": True, "status": 200, "id": "m1"}

    monkeypatch.setattr(health_api, "_publish", fake)
    status, body = reset_client.json("POST", "/api/health/publish", {"topic": "abc", "message": "hi"})
    assert status == 200
    assert body == {"ok": True, "status": 200, "id": "m1"}
    assert seen == [(True, "abc", "hi")]


@pytest.mark.parametrize("body", [{"topic": "-bad"}, {"topic": "a b"}, {}, {"topic": 3}, {"topic": "ok", "message": 1}])
def test_health_publish_invalid_input(reset_client: Client, body: dict[str, Any]) -> None:
    status, resp = reset_client.json("POST", "/api/health/publish", body)
    assert status == 400
    assert resp["error"] == "bad_request"


def test_reset_and_health_routes_are_the_owned_c10_rows(ctx: Any) -> None:
    router = Router()
    reset_api.register(router, ctx)
    health_api.register(router, ctx)
    assert sorted(router.routes()) == sorted(
        [
            ("POST", "/api/reset/acls"),
            ("POST", "/api/reset/cache"),
            ("POST", "/api/reset/everything"),
            ("GET", "/api/health"),
            ("POST", "/api/health/publish"),
        ]
    )
