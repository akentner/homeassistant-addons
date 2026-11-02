"""HTTP tests for the users and ACL endpoints (in-process server, fake ntfy CLI)."""

from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path
from typing import Any, Iterator

import pytest

from app.contract import ROUTES
from app.web.api import acl, users
from app.web.server import Router, make_server
from helpers.ctx import make_context
from helpers.ntfy_db import add_acl, add_token, add_user

HEADERS = {"X-Ingress-Path": "/api/hassio_ingress/abc", "Content-Type": "application/json"}
TOKEN = "tk_" + "b" * 29
USER_KEYS = {
    "name", "role", "tier", "origin", "provisioned", "protected", "protected_reason", "acl_count", "token_count",
}


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
            conn.request(method, path, body=data, headers=HEADERS)
            resp = conn.getresponse()
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
        finally:
            conn.close()


@pytest.fixture()
def env(tmp_path: Path) -> Iterator[tuple[Client, Any, Router]]:
    ctx = make_context(tmp_path, admin_user="root")
    add_user(ctx.paths.auth_db, "root", role="admin")
    add_user(ctx.paths.auth_db, "alice")
    add_acl(ctx.paths.auth_db, "alice", "a_b*", "rw")
    add_token(ctx.paths.auth_db, "alice", TOKEN, label="ci")
    router = Router()
    users.register(router, ctx)
    acl.register(router, ctx)
    httpd = make_server(router, 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield Client(httpd.server_address[1]), ctx, router
    httpd.shutdown()
    httpd.server_close()


def test_route_set_matches_contract(env) -> None:
    _, _, router = env
    expected = sorted((r.method, r.pattern) for r in ROUTES if r.pattern.startswith(("/api/users", "/api/acl")))
    assert sorted(router.routes()) == expected


def test_list_users_shape(env) -> None:
    client, _, _ = env
    status, data = client.call("GET", "/api/users")
    assert status == 200
    assert all(set(u) == USER_KEYS for u in data["users"])
    assert data["users"][-1]["name"] == "everyone"


def test_create_user(env) -> None:
    client, ctx, _ = env
    status, data = client.call("POST", "/api/users", {"name": "bob", "password": "pw"})
    assert status == 201 and data["user"]["name"] == "bob"
    assert ctx.db.has_user("bob")


@pytest.mark.parametrize(
    "body", [b"not json", b"[1]", {"password": "x"}, {"name": "bob"}, {"name": "bob", "password": "x", "z": 1}]
)
def test_create_user_bad_bodies(env, body: Any) -> None:
    client, _, _ = env
    status, data = client.call("POST", "/api/users", body)
    assert status == 400 and data["error"] == "bad_request"


def test_create_existing_user_conflicts(env) -> None:
    client, _, _ = env
    status, data = client.call("POST", "/api/users", {"name": "alice", "password": "pw"})
    assert status == 409 and data["error"] == "conflict"


def test_user_detail_has_no_token_value(env) -> None:
    client, _, _ = env
    status, data = client.call("GET", "/api/users/alice")
    assert status == 200
    assert data["user"]["name"] == "alice"
    assert [r["topic"] for r in data["acl"]] == ["a_b*"]
    assert len(data["tokens"]) == 1
    assert "value" not in data["tokens"][0]
    assert "tk_" not in json.dumps(data["tokens"]).replace(data["tokens"][0]["prefix"], "")
    assert TOKEN not in json.dumps(data)


def test_unknown_user_is_404(env) -> None:
    client, _, _ = env
    assert client.call("GET", "/api/users/nobody")[0] == 404


def test_patch_role_returns_dropped_rules(env) -> None:
    client, _, _ = env
    status, data = client.call("PATCH", "/api/users/alice", {"role": "admin"})
    assert status == 200
    assert data["user"]["role"] == "admin" and data["dropped_rules"] == 1


def test_patch_password_and_validation(env) -> None:
    client, _, _ = env
    status, data = client.call("PATCH", "/api/users/alice", {"password": "new"})
    assert status == 200 and data["dropped_rules"] == 0
    assert client.call("PATCH", "/api/users/alice", {"foo": 1})[0] == 400
    assert client.call("PATCH", "/api/users/alice", {})[0] == 400


def test_delete_user_confirmation(env) -> None:
    client, ctx, _ = env
    status, data = client.call("DELETE", "/api/users/alice", {"confirm": "nope"})
    assert status == 400 and data["error"] == "confirmation_required"
    assert client.call("DELETE", "/api/users/alice", {"confirm": "alice"})[0] == 204
    assert not ctx.db.has_user("alice")


def test_delete_options_admin_is_protected(env) -> None:
    client, _, _ = env
    status, data = client.call("DELETE", "/api/users/root", {"confirm": "root"})
    assert status == 409 and data["error"] == "protected"


def test_acl_put_get_delete(env) -> None:
    client, _, _ = env
    status, data = client.call("PUT", "/api/acl", {"user": "alice", "topic": "a_c*", "permission": "ro"})
    assert status == 200 and data["rule"]["origin"] == "gui"
    status, data = client.call("GET", "/api/acl?user=alice")
    assert [r["topic"] for r in data["rules"]] == ["a_b*", "a_c*"]
    assert client.call("DELETE", "/api/acl?user=alice&topic=a_c%2A")[0] == 204
    status, data = client.call("GET", "/api/acl?user=alice")
    assert [r["topic"] for r in data["rules"]] == ["a_b*"]


def test_acl_validation(env) -> None:
    client, _, _ = env
    assert client.call("PUT", "/api/acl", {"user": "alice", "topic": "x"})[0] == 400
    assert client.call("PUT", "/api/acl", {"user": "alice", "topic": "x", "permission": "rw", "z": 1})[0] == 400
    assert client.call("DELETE", "/api/acl?user=alice")[0] == 400
    assert client.call("DELETE", "/api/acl?topic=x")[0] == 400
    assert client.call("DELETE", "/api/acl?user=alice&topic=missing")[0] == 404


def test_plus_in_user_name_is_decoded(env) -> None:
    client, ctx, _ = env
    add_user(ctx.paths.auth_db, "a+b")
    status, data = client.call("GET", "/api/users/a%2Bb")
    assert status == 200 and data["user"]["name"] == "a+b"
