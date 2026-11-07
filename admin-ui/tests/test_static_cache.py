"""ETag/304 revalidation and versioned asset URLs of the skeleton's static serving."""

from __future__ import annotations

import http.client
import re
import threading
from pathlib import Path
from typing import Iterator

import pytest

from app.web.skeleton import DEFAULT_CSP, Router, StaticFiles, make_server
from app.web.skeleton.static import etag_matches

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}
INDEX = (
    '<link rel="stylesheet" href="static/app.css"><script type="module" src="static/app.mjs"></script>'
    '<a href="other/page">x</a><img src="static/missing.png">'
)


class Env:
    def __init__(self, root: Path, port: int) -> None:
        self.root, self.port = root, port

    def call(self, method: str, path: str, headers: dict[str, str] | None = INGRESS):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp, resp.read()
        finally:
            conn.close()


@pytest.fixture
def env(tmp_path: Path) -> Iterator[Env]:
    root = tmp_path / "static"
    root.mkdir()
    (root / "index.html").write_text(INDEX)
    (root / "app.mjs").write_text("export {};")
    (root / "app.css").write_text("body{}")
    httpd = make_server(
        Router(), StaticFiles(root), 0, ingress_remote="127.0.0.1", host="127.0.0.1", csp=DEFAULT_CSP
    )
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    yield Env(root, httpd.server_address[1])
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def test_etag_values() -> None:
    assert etag_matches('"a"', '"a"')
    assert etag_matches('"b", "a"', '"a"')
    assert etag_matches('W/"a"', '"a"')
    assert etag_matches("*", '"a"')
    assert not etag_matches('"b"', '"a"')
    assert not etag_matches(None, '"a"')


@pytest.mark.parametrize("path", ["/", "/static/app.mjs", "/static/app.css"])
def test_200_has_strong_etag_and_no_last_modified(env: Env, path: str) -> None:
    status, resp, _ = env.call("GET", path)
    assert status == 200
    assert re.fullmatch(r'"[0-9a-f]{16}"', resp.getheader("ETag"))
    assert resp.getheader("Last-Modified") is None
    assert resp.getheader("Cache-Control") == "no-cache"
    assert env.call("GET", path)[1].getheader("ETag") == resp.getheader("ETag")


@pytest.mark.parametrize("path", ["/", "/static/app.mjs"])
def test_matching_etag_gives_304_without_body(env: Env, path: str) -> None:
    etag = env.call("GET", path)[1].getheader("ETag")
    for value in (etag, f"W/{etag}", f'"x", {etag}', "*"):
        status, resp, data = env.call("GET", path, {**INGRESS, "If-None-Match": value})
        assert status == 304 and data == b""
        assert resp.getheader("ETag") == etag
        assert resp.getheader("Cache-Control") == "no-cache"
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
        assert "default-src" in resp.getheader("Content-Security-Policy")


def test_non_matching_etag_gives_200(env: Env) -> None:
    status, _, data = env.call("GET", "/static/app.mjs", {**INGRESS, "If-None-Match": '"nope"'})
    assert status == 200 and data == b"export {};"


def test_304_keeps_the_connection_usable(env: Env) -> None:
    etag = env.call("GET", "/static/app.css")[1].getheader("ETag")
    conn = http.client.HTTPConnection("127.0.0.1", env.port, timeout=5)
    try:
        conn.request("GET", "/static/app.css", headers={**INGRESS, "If-None-Match": etag})
        first = conn.getresponse()
        assert first.status == 304 and first.read() == b""
        conn.request("GET", "/static/app.css", headers=INGRESS)
        second = conn.getresponse()
        assert second.status == 200 and second.read() == b"body{}"
    finally:
        conn.close()


def test_changed_file_changes_etag(env: Env) -> None:
    old = env.call("GET", "/static/app.mjs")[1].getheader("ETag")
    (env.root / "app.mjs").write_text("export const x = 1;")
    assert env.call("GET", "/static/app.mjs")[1].getheader("ETag") != old


def test_index_assets_are_versioned_and_follow_changes(env: Env) -> None:
    _, resp, data = env.call("GET", "/")
    html = data.decode()
    assert re.search(r'href="static/app\.css\?v=[0-9a-f]{12}"', html)
    assert re.search(r'src="static/app\.mjs\?v=[0-9a-f]{12}"', html)
    assert 'href="other/page"' in html and 'src="static/missing.png"' in html
    etag = resp.getheader("ETag")
    version = re.search(r"app\.css\?v=([0-9a-f]{12})", html).group(1)
    (env.root / "app.css").write_text("body{color:red}")
    _, resp2, data2 = env.call("GET", "/")
    assert resp2.getheader("ETag") != etag
    assert re.search(r"app\.css\?v=([0-9a-f]{12})", data2.decode()).group(1) != version


def test_versioned_url_resolves_and_gate_still_holds(env: Env) -> None:
    status, _, data = env.call("GET", "/static/app.mjs?v=abc123")
    assert status == 200 and data == b"export {};"
    etag = env.call("GET", "/static/app.mjs")[1].getheader("ETag")
    status, _, data = env.call("GET", "/static/app.mjs", {"If-None-Match": etag})
    assert status == 403 and b"ingress_only" in data


def test_resolve_keeps_tuple_contract(tmp_path: Path) -> None:
    (tmp_path / "icon.png").write_bytes(b"png")
    assert StaticFiles(tmp_path).resolve("/icon") == (b"png", "image/png")
    assert StaticFiles(tmp_path).resolve("/static/../x") is None
