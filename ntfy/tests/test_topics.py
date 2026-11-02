"""Tests for app.topics and GET /api/topics/suggest."""

from __future__ import annotations

import http.client
import itertools
import json
import re
import threading
from typing import Any, Iterator

import pytest

from app.contract import DEFAULT_TOPIC_ACL, TOPIC_RE, ApiError
from app.topics import suggest
from app.web import server as srv
from app.web.api import topics as topics_api
from helpers import ntfy_db
from helpers.ctx import make_context

PATTERN = re.compile(r"^[A-Za-z0-9]{16}$")


@pytest.fixture()
def ctx(tmp_path: Any) -> Any:
    return make_context(tmp_path)


def test_topic_shape(ctx: Any) -> None:
    topic = suggest(ctx)["topic"]
    assert PATTERN.match(topic)
    assert TOPIC_RE.match(topic)


def test_suggestions_unique(ctx: Any) -> None:
    topics = [suggest(ctx)["topic"] for _ in range(200)]
    assert len(set(topics)) == 200


def test_default_acl(ctx: Any) -> None:
    assert suggest(ctx)["acl"] == [
        {"user": "homeassistant", "permission": "rw"},
        {"user": "akentner", "permission": "ro"},
    ]
    assert [(e["user"], e["permission"]) for e in suggest(ctx)["acl"]] == list(DEFAULT_TOPIC_ACL)


def test_collision_retries(ctx: Any) -> None:
    ntfy_db.add_acl(ctx.paths.auth_db, "everyone", "AAAAAAAAAAAAAAAA", "ro")
    # first 16 draws build the colliding topic (compared case-insensitively), the rest build a different one
    chars = itertools.chain("a" * 16, "b" * 16)
    result = suggest(ctx, rng=lambda _alphabet: next(chars))
    assert result["topic"] == "b" * 16


def test_gives_up_after_20_attempts(ctx: Any) -> None:
    ntfy_db.add_acl(ctx.paths.auth_db, "everyone", "a" * 16, "ro")
    with pytest.raises(ApiError) as exc:
        suggest(ctx, rng=lambda _alphabet: "a")
    assert exc.value.code == "conflict"


@pytest.fixture()
def port(ctx: Any) -> Iterator[int]:
    router = srv.Router()
    topics_api.register(router, ctx)
    server = srv.make_server(router, 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def test_http_suggest(port: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/api/topics/suggest", headers={"X-Ingress-Path": "/x"})
        resp = conn.getresponse()
        body = json.loads(resp.read())
    finally:
        conn.close()
    assert resp.status == 200
    assert PATTERN.match(body["topic"])
    assert body["acl"][0] == {"user": "homeassistant", "permission": "rw"}
