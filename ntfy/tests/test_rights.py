"""Tests for app.rights and GET /api/effective: ntfy precedence verified against ntfy 2.36.0."""

from __future__ import annotations

import http.client
import json
import threading
from typing import Any, Iterator

import pytest

from app.contract import ApiError
from app.rights import effective
from app.web import server as srv
from app.web.api import effective as effective_api
from helpers import ntfy_db
from helpers.ctx import make_context

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}


def seed(ctx: Any) -> None:
    db = ctx.paths.auth_db
    ntfy_db.add_user(db, "alice")
    ntfy_db.add_user(db, "boss", role="admin")
    ntfy_db.add_acl(db, "alice", "*", "ro")
    ntfy_db.add_acl(db, "alice", "a_b*", "rw")
    ntfy_db.add_acl(db, "alice", "pub1", "deny")
    ntfy_db.add_acl(db, "everyone", "x", "rw")
    ntfy_db.add_acl(db, "everyone", "pub*", "ro")


@pytest.fixture()
def ctx(tmp_path: Any) -> Any:
    context = make_context(tmp_path)
    seed(context)
    return context


def rw(result: dict[str, Any]) -> tuple[bool, bool]:
    return result["read"], result["write"]


def test_admin_everything(ctx: Any) -> None:
    result = effective(ctx, "boss", "anything")
    assert rw(result) == (True, True)
    assert result["source"] == {"kind": "admin", "rule": None}
    assert result["candidates"] == []


def test_user_rule_beats_everyone_rule(ctx: Any) -> None:
    result = effective(ctx, "alice", "x")
    assert rw(result) == (True, False)
    assert result["source"]["kind"] == "user-rule"
    assert result["source"]["rule"]["topic"] == "*"


def test_longest_pattern_wins(ctx: Any) -> None:
    result = effective(ctx, "alice", "a_bz")
    assert rw(result) == (True, True)
    assert result["source"]["rule"]["topic"] == "a_b*"


def test_underscore_is_literal(ctx: Any) -> None:
    result = effective(ctx, "alice", "aXbz")
    assert rw(result) == (True, False)
    assert result["source"]["rule"]["topic"] == "*"


def test_exact_deny(ctx: Any) -> None:
    result = effective(ctx, "alice", "pub1")
    assert rw(result) == (False, False)
    assert result["source"]["rule"]["permission"] == "deny"


def test_everyone_rules(ctx: Any) -> None:
    result = effective(ctx, "everyone", "x")
    assert rw(result) == (True, True)
    assert result["source"]["kind"] == "everyone-rule"
    assert rw(effective(ctx, "everyone", "pub9")) == (True, False)


def test_everyone_rule_applies_to_user_without_own_rule(tmp_path: Any) -> None:
    context = make_context(tmp_path)
    ntfy_db.add_user(context.paths.auth_db, "bob")
    ntfy_db.add_acl(context.paths.auth_db, "everyone", "pub*", "ro")
    result = effective(context, "bob", "pub1")
    assert rw(result) == (True, False)
    assert result["source"]["kind"] == "everyone-rule"


def test_length_counts_db_form(tmp_path: Any) -> None:
    # `a_b*` is 5 chars in DB form (a\_b%), equal to `aXbc*`; `a*` is shorter
    context = make_context(tmp_path)
    db = context.paths.auth_db
    ntfy_db.add_user(db, "carl")
    ntfy_db.add_acl(db, "carl", "a_b*", "ro")  # stored a\_b% = 5 chars
    ntfy_db.add_acl(db, "carl", "aXbc*", "rw")  # stored aXbc% = 5 chars, equal length -> write first
    ntfy_db.add_acl(db, "carl", "a*", "deny")
    assert effective(context, "carl", "a_bc")["source"]["rule"]["topic"] == "a_b*"
    result = effective(context, "carl", "aXbcd")
    assert result["source"]["rule"]["topic"] == "aXbc*"


def test_equal_length_write_capable_wins(tmp_path: Any) -> None:
    context = make_context(tmp_path)
    db = context.paths.auth_db
    ntfy_db.add_user(db, "dan")
    ntfy_db.add_acl(db, "dan", "ab*", "ro")
    ntfy_db.add_acl(db, "dan", "*bc", "wo")
    result = effective(context, "dan", "abc")
    assert result["source"]["rule"]["topic"] == "*bc"
    assert rw(result) == (False, True)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("deny-all", (False, False)),
        ("read-only", (True, False)),
        ("write-only", (False, True)),
        ("read-write", (True, True)),
    ],
)
def test_default_access(tmp_path: Any, mode: str, expected: tuple[bool, bool]) -> None:
    context = make_context(tmp_path, auth_default_access=mode)
    ntfy_db.add_user(context.paths.auth_db, "eve")
    result = effective(context, "eve", "nothing")
    assert rw(result) == expected
    assert result["source"] == {"kind": "default", "rule": None}


def test_case_sensitive(tmp_path: Any) -> None:
    context = make_context(tmp_path)
    ntfy_db.add_acl(context.paths.auth_db, "everyone", "pub*", "ro")
    assert effective(context, "everyone", "pub1")["source"]["kind"] == "everyone-rule"
    upper = effective(context, "everyone", "PUB1")
    assert upper["source"]["kind"] == "default"
    assert rw(upper) == (False, False)


def test_candidates_in_precedence_order(ctx: Any) -> None:
    result = effective(ctx, "alice", "a_bz")
    topics = [c["topic"] for c in result["candidates"]]
    assert topics == ["a_b*", "*"]
    assert result["candidates"][0] == result["source"]["rule"]
    assert result["candidates"][0]["origin"] == "gui"


def test_validation(ctx: Any) -> None:
    with pytest.raises(ApiError) as exc:
        effective(ctx, "alice", "a*")
    assert exc.value.code == "bad_request"
    with pytest.raises(ApiError) as exc:
        effective(ctx, "nobody", "x")
    assert exc.value.code == "not_found"


# --- HTTP ---------------------------------------------------------------------------------------------------------


@pytest.fixture()
def port(ctx: Any) -> Iterator[int]:
    router = srv.Router()
    effective_api.register(router, ctx)
    server = srv.make_server(router, 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def get(port: int, path: str) -> tuple[int, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers=INGRESS)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, (json.loads(data) if data else None)
    finally:
        conn.close()


def test_http_effective(port: int) -> None:
    status, body = get(port, "/api/effective?user=alice&topic=x")
    assert status == 200
    assert (body["read"], body["write"]) == (True, False)
    assert body["source"]["kind"] == "user-rule"


def test_http_everyone_accepted(port: int) -> None:
    status, body = get(port, "/api/effective?user=everyone&topic=pub9")
    assert status == 200
    assert body["read"] is True


def test_http_errors(port: int) -> None:
    assert get(port, "/api/effective?user=alice")[0] == 400
    assert get(port, "/api/effective?topic=x")[0] == 400
    assert get(port, "/api/effective?user=alice&topic=x%2A")[0] == 400
    assert get(port, "/api/effective?user=nobody&topic=x")[0] == 404
