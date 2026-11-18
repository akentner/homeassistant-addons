"""Golden characterisation of the ingress server: status, ordered headers (without Date and Server) and body bytes.

The expected values were recorded once against the ingress handler before it was refactored onto the shared JSON base
and are kept here as literals; they are never computed from the code under test. Any observable change of the ingress
server (gate, header order, cache policy, CSP, ETag, error bodies) fails this matrix.
"""

from __future__ import annotations

import http.client
import threading
from pathlib import Path
from typing import Iterator

import pytest

from app.web.skeleton import DEFAULT_CSP, ApiError, make_server
from test_skeleton_server import INGRESS, JSON_HEADERS, ForeignError, build_router, make_static

Headers = list[tuple[str, str]]

# Recorded literals shared by many cases.
JSON_CT = ("Content-Type", "application/json; charset=utf-8")
NO_STORE = ("Cache-Control", "no-store")
NO_CACHE = ("Cache-Control", "no-cache")
NOSNIFF = ("X-Content-Type-Options", "nosniff")
REFERRER = ("Referrer-Policy", "same-origin")
CLOSE = ("Connection", "close")
CSP = (
    "Content-Security-Policy",
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'self'",
)
CSS_ETAG = '"7c98040a54165758"'
INDEX_ETAG = '"d3d389ab09df8536"'

GATE_403: Headers = [JSON_CT, ("Content-Length", "25"), NO_STORE, NOSNIFF, REFERRER, CLOSE]
CSS_HEADERS: Headers = [
    ("Content-Type", "text/css; charset=utf-8"), ("Content-Length", "6"), NO_CACHE, NOSNIFF, REFERRER, CSP,
    ("ETag", CSS_ETAG),
]
CSS_304_HEADERS: Headers = [
    ("Content-Type", "text/css; charset=utf-8"), ("Content-Length", "0"), NO_CACHE, NOSNIFF, REFERRER, CSP,
    ("ETag", CSS_ETAG),
]
BIG_BODY = b"{" + b" " * 69998 + b"}"

# (id, method, path, request headers, request body, raw putrequest, status, response headers, response body)
CASES = [
    ("gate_get", "GET", "/api/health", {}, None, False, 403, GATE_403, b'{"error": "ingress_only"}'),
    ("gate_head", "HEAD", "/api/health", {}, None, False, 403, GATE_403, b""),
    ("gate_options", "OPTIONS", "/api/health", {}, None, False, 403, GATE_403, b'{"error": "ingress_only"}'),
    ("gate_static", "GET", "/static/app.css", {}, None, False, 403, GATE_403, b'{"error": "ingress_only"}'),
    (
        "json_200", "GET", "/api/health", INGRESS, None, False, 200,
        [JSON_CT, ("Content-Length", "12"), NO_STORE, NOSNIFF, REFERRER],
        b'{"ok": true}',
    ),
    (
        "params", "GET", "/api/users/a%2Bb", INGRESS, None, False, 200,
        [JSON_CT, ("Content-Length", "15"), NO_STORE, NOSNIFF, REFERRER],
        b'{"name": "a+b"}',
    ),
    (
        "no_content", "POST", "/api/nothing", INGRESS, None, False, 204,
        [JSON_CT, ("Content-Length", "0"), NO_STORE, NOSNIFF, REFERRER],
        b"",
    ),
    (
        "download", "GET", "/api/download", INGRESS, None, False, 200,
        [
            ("Content-Type", "text/plain"), ("Content-Length", "4"), NO_STORE, NOSNIFF, REFERRER,
            ("Content-Disposition", 'attachment; filename="a.txt"'),
        ],
        b"data",
    ),
    (
        "created", "POST", "/api/echo", JSON_HEADERS, b'{"k": 1}', False, 201,
        [JSON_CT, ("Content-Length", "8"), NO_STORE, NOSNIFF, REFERRER],
        b'{"k": 1}',
    ),
    (
        "index", "GET", "/", INGRESS, None, False, 200,
        [
            ("Content-Type", "text/html; charset=utf-8"), ("Content-Length", "31"), NO_CACHE, NOSNIFF, REFERRER, CSP,
            ("ETag", INDEX_ETAG),
        ],
        b"<!doctype html><title>t</title>",
    ),
    ("static_200", "GET", "/static/app.css", INGRESS, None, False, 200, CSS_HEADERS, b"body{}"),
    (
        "static_304", "GET", "/static/app.css", {**INGRESS, "If-None-Match": CSS_ETAG}, None, False, 304,
        CSS_304_HEADERS, b"",
    ),
    (
        "not_found", "GET", "/api/missing", INGRESS, None, False, 404,
        [JSON_CT, ("Content-Length", "46"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "not_found", "message": "not found"}',
    ),
    (
        "method_not_allowed", "PUT", "/api/health", INGRESS, None, False, 405,
        [JSON_CT, ("Content-Length", "64"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "method_not_allowed", "message": "method not allowed"}',
    ),
    (
        "too_large", "POST", "/api/echo", JSON_HEADERS, BIG_BODY, False, 413,
        [JSON_CT, ("Content-Length", "67"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "payload_too_large", "message": "request body too large"}',
    ),
    (
        "bad_json", "POST", "/api/echo", JSON_HEADERS, b"{not json", False, 400,
        [JSON_CT, ("Content-Length", "51"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "bad_request", "message": "invalid JSON"}',
    ),
    (
        "chunked", "POST", "/api/echo", {**JSON_HEADERS, "Transfer-Encoding": "chunked"}, None, True, 400,
        [JSON_CT, ("Content-Length", "71"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "bad_request", "message": "chunked bodies are not supported"}',
    ),
    (
        "boom", "GET", "/api/boom", INGRESS, None, False, 500,
        [JSON_CT, ("Content-Length", "56"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "internal_error", "message": "internal error"}',
    ),
    (
        "mapped", "POST", "/api/foreign", JSON_HEADERS, b"{}", False, 409,
        [JSON_CT, ("Content-Length", "42"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "conflict", "message": "exists"}',
    ),
    (
        "protected", "GET", "/api/protected", INGRESS, None, False, 409,
        [JSON_CT, ("Content-Length", "41"), NO_STORE, NOSNIFF, REFERRER, CLOSE],
        b'{"error": "protected", "message": "nope"}',
    ),
    (
        "public", "GET", "/api/public", {}, None, False, 200,
        [JSON_CT, ("Content-Length", "16"), NO_STORE, NOSNIFF, REFERRER],
        b'{"public": true}',
    ),
]


@pytest.fixture(scope="module")
def port(tmp_path_factory: pytest.TempPathFactory) -> Iterator[int]:
    router = build_router()
    router.add("GET", "/api/public", lambda req: {"public": req.public}, public=True)
    static = make_static(Path(tmp_path_factory.mktemp("ingress")) / "static")
    server = make_server(
        router,
        static,
        0,
        ingress_remote="127.0.0.1",
        host="127.0.0.1",
        csp=DEFAULT_CSP,
        error_mappers={ForeignError: lambda exc: ApiError("conflict", "exists")},
    )
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.mark.parametrize(
    ("method", "path", "headers", "body", "raw", "status", "expected_headers", "expected_body"),
    [pytest.param(*case[1:], id=case[0]) for case in CASES],
)
def test_ingress_response_is_unchanged(
    port: int,
    method: str,
    path: str,
    headers: dict[str, str],
    body: bytes | None,
    raw: bool,
    status: int,
    expected_headers: Headers,
    expected_body: bytes,
) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        if raw:
            # Sent header by header, so the request carries Transfer-Encoding without a chunked body
            conn.putrequest(method, path)
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders()
        else:
            conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        received = [(k, v) for k, v in resp.getheaders() if k not in ("Date", "Server")]
        data = resp.read()
    finally:
        conn.close()
    assert resp.status == status
    assert received == expected_headers
    assert data == expected_body


def test_matrix_covers_every_response_kind() -> None:
    assert len(CASES) >= 20
    assert len({case[0] for case in CASES}) == len(CASES)
