"""Tests for app.tokens and the token routes (D-13: values hidden by default)."""

from __future__ import annotations

import http.client
import json
import logging
import re
import threading
import time
from typing import Any, Iterator

import pytest

from app import tokens
from app.contract import TOKEN_RE, ApiError
from app.web import server as srv
from app.web.api import tokens as tokens_api
from helpers import ntfy_db
from helpers.ctx import make_context

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc", "Content-Type": "application/json"}
TOKEN_ANY = re.compile(r"tk_[a-z0-9]{29}")
OLD = "tk_" + "a" * 29


@pytest.fixture()
def ctx(tmp_path: Any) -> Any:
    context = make_context(tmp_path)
    ntfy_db.add_user(context.paths.auth_db, "alice")
    ntfy_db.add_user(context.paths.auth_db, "bob")
    return context


def test_create_returns_value_and_meta(ctx: Any) -> None:
    result = tokens.create_token(ctx, "alice", "ci", "2d")
    assert TOKEN_RE.match(result["value"])
    assert result["label"] == "ci"
    assert result["origin"] == "gui"
    assert result["user"] == "alice"
    assert abs(result["expires"] - (time.time() + 2 * 86400)) < 120
    assert result["expires_at"].endswith("Z")
    assert ctx.origins.get_token("alice", result["id"]) == "gui"


def test_create_without_label_and_expiry(ctx: Any) -> None:
    result = tokens.create_token(ctx, "alice", None, None)
    assert result["label"] == ""
    assert result["expires"] == 0
    assert result["expires_at"] is None


def test_create_validation(ctx: Any) -> None:
    def code(user: str, label: Any, expires: Any) -> str:
        with pytest.raises(ApiError) as exc:
            tokens.create_token(ctx, user, label, expires)
        return exc.value.code

    assert code("nobody", "x", None) == "not_found"
    assert code("everyone", "x", None) == "bad_request"
    assert code("alice", "a\x01b", None) == "bad_request"
    assert code("alice", "x" * 65, None) == "bad_request"
    assert code("alice", "x", "2w") == "bad_request"


def test_list_has_no_values(ctx: Any) -> None:
    created = tokens.create_token(ctx, "alice", "ci", None)
    tokens.create_token(ctx, "bob", "other", None)
    ntfy_db.add_token(ctx.paths.auth_db, "alice", OLD, label="old")
    rows = tokens.list_tokens(ctx)
    assert len(rows) == 3
    dump = json.dumps(rows)
    assert not TOKEN_ANY.search(dump)
    assert all("value" not in row for row in rows)
    assert created["value"] not in dump


def test_list_filter_and_origin(ctx: Any) -> None:
    tokens.create_token(ctx, "alice", "ci", None)
    tokens.create_token(ctx, "bob", "other", None)
    rows = tokens.list_tokens(ctx, "alice")
    assert [r["user"] for r in rows] == ["alice"]
    assert rows[0]["origin"] == "gui"


def test_reveal(ctx: Any, caplog: pytest.LogCaptureFixture) -> None:
    created = tokens.create_token(ctx, "alice", "ci", None)
    with caplog.at_level(logging.INFO, logger="ntfy.audit"):
        value = tokens.reveal_token(ctx, "alice", created["id"])
    assert value == created["value"]
    assert "token revealed" in caplog.text
    assert "alice" in caplog.text and created["id"] in caplog.text
    assert value not in caplog.text


def test_reveal_wrong_user_or_unknown(ctx: Any) -> None:
    created = tokens.create_token(ctx, "alice", "ci", None)
    for user, tid in (("bob", created["id"]), ("alice", "000000000000")):
        with pytest.raises(ApiError) as exc:
            tokens.reveal_token(ctx, user, tid)
        assert exc.value.code == "not_found"


def test_revoke(ctx: Any, caplog: pytest.LogCaptureFixture) -> None:
    created = tokens.create_token(ctx, "alice", "ci", None)
    with caplog.at_level(logging.INFO, logger="ntfy.audit"):
        tokens.revoke_token(ctx, "alice", created["id"])
    assert tokens.list_tokens(ctx, "alice") == []
    assert ctx.origins.get_token("alice", created["id"]) == "gui"  # back to default, record dropped
    assert ctx.origins.snapshot()["tokens"].get("alice", {}) == {}
    assert created["value"] not in caplog.text


def test_revoke_unknown(ctx: Any) -> None:
    with pytest.raises(ApiError) as exc:
        tokens.revoke_token(ctx, "alice", "000000000000")
    assert exc.value.code == "not_found"


# --- HTTP ---------------------------------------------------------------------------------------------------------


@pytest.fixture()
def port(ctx: Any) -> Iterator[int]:
    router = srv.Router()
    tokens_api.register(router, ctx)
    server = srv.make_server(router, 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def call(port: int, method: str, path: str, body: Any = None) -> tuple[int, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        payload = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=payload, headers=INGRESS)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, (json.loads(data) if data else None)
    finally:
        conn.close()


def test_http_lifecycle(port: int, ctx: Any) -> None:
    status, body = call(port, "POST", "/api/tokens", {"user": "alice", "label": "ci", "expires": "1h"})
    assert status == 201
    token = body["token"]
    assert TOKEN_RE.match(token["value"])

    status, body = call(port, "GET", "/api/tokens?user=alice")
    assert status == 200
    assert not TOKEN_ANY.search(json.dumps(body))
    assert [t["id"] for t in body["tokens"]] == [token["id"]]

    status, body = call(port, "POST", "/api/tokens/reveal", {"user": "alice", "id": token["id"]})
    assert (status, body) == (200, {"value": token["value"]})

    status, _ = call(port, "DELETE", f"/api/tokens?user=alice&id={token['id']}")
    assert status == 204
    assert ctx.db.reveal_token("alice", token["id"]) is None


def test_http_missing_parameters(port: int) -> None:
    assert call(port, "POST", "/api/tokens", {"label": "x"})[0] == 400
    assert call(port, "POST", "/api/tokens/reveal", {"user": "alice"})[0] == 400
    assert call(port, "DELETE", "/api/tokens?user=alice")[0] == 400
    assert call(port, "POST", "/api/tokens", {"user": "alice", "label": 5})[0] == 400


def test_http_errors_map(port: int) -> None:
    assert call(port, "POST", "/api/tokens", {"user": "nobody"})[0] == 404
    assert call(port, "POST", "/api/tokens", {"user": "alice", "expires": "2w"})[0] == 400
    assert call(port, "DELETE", "/api/tokens?user=alice&id=000000000000")[0] == 404
