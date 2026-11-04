"""End-to-end closure check: the real server serves everything the page imports, and nothing it should hide.

Only the HTTP surface is used (make_server signature, ingress header), so the test survives the server rewrite.
"""

from __future__ import annotations

import http.client
import re
import threading
import urllib.parse
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.web.server import Router, make_server

STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"
INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/token"}
WHITELIST_EXT = {"mjs", "js", "css", "png", "svg", "txt"}

LINK_RE = re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.I)
SCRIPT_RE = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.I)
IMPORT_FROM_RE = re.compile(r"""\bfrom\s*["'](\.{1,2}/[^"']+)["']""")
IMPORT_BARE_RE = re.compile(r"""\bimport\s*["'](\.{1,2}/[^"']+)["']""")
DYN_LITERAL_RE = re.compile(r"""\bimport\(\s*["'](\.{1,2}/[^"']+)["']\s*\)""")
DYN_TEMPLATE_RE = re.compile(r"""\bimport\(\s*`(\.{1,2}/[^`$]*)\$\{[^}]*\}([^`]*)`\s*\)""")
CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')\s]+)["']?\s*\)""", re.I)
CSS_IMPORT_RE = re.compile(r"""@import\s+(?:url\(\s*)?["']([^"']+)["']""", re.I)


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def get(self, path: str, headers: dict[str, str] | None = INGRESS) -> tuple[int, str, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", path, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.getheader("Content-Type") or "", resp.read()
        finally:
            conn.close()


@pytest.fixture(scope="module")
def client() -> Iterator[Client]:
    httpd = make_server(Router(), 0, ingress_remote="127.0.0.1", host="127.0.0.1")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield Client(httpd.server_address[1])
    httpd.shutdown()
    httpd.server_close()


def _is_local(ref: str) -> bool:
    return not ref.startswith(("data:", "#")) and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", ref) and not ref.startswith("//")


def _expand_template(base_url: str, prefix: str, suffix: str) -> list[str]:
    """A literal-prefixed dynamic import stands for every file of that directory with the given suffix."""
    directory = urllib.parse.urlsplit(urllib.parse.urljoin(base_url, prefix)).path
    rel = directory.removeprefix("/static/")
    found = sorted(p.name for p in (STATIC / rel).iterdir() if p.is_file() and p.name.endswith(suffix))
    assert found, f"dynamic import {prefix}*{suffix} matches no file"
    return [urllib.parse.urljoin(base_url, prefix + name) for name in found]


def _references(url: str, text: str, ctype: str) -> list[str]:
    path = urllib.parse.urlsplit(url).path
    refs: list[str] = []
    if path == "/":
        refs += LINK_RE.findall(text) + SCRIPT_RE.findall(text)
    elif path.endswith((".mjs", ".js")):
        for rx in (IMPORT_FROM_RE, IMPORT_BARE_RE, DYN_LITERAL_RE):
            refs += rx.findall(text)
        expanded = [u for prefix, suffix in DYN_TEMPLATE_RE.findall(text) for u in _expand_template(url, prefix, suffix)]
        return [urllib.parse.urljoin(url, r) for r in refs if _is_local(r)] + expanded
    elif path.endswith(".css"):
        refs += [r for r in CSS_URL_RE.findall(text) + CSS_IMPORT_RE.findall(text)]
    return [urllib.parse.urljoin(url, r) for r in refs if _is_local(r) or r.startswith("/static/")]


def _crawl(client: Client) -> dict[str, tuple[int, str]]:
    seen: dict[str, tuple[int, str]] = {}
    queue = ["/"]
    while queue:
        url = queue.pop()
        key = urllib.parse.urlsplit(url).path
        if key in seen:
            continue
        status, ctype, body = client.get(key)
        seen[key] = (status, ctype)
        if status != 200:
            continue
        queue += _references(key, body.decode("utf-8", "replace"), ctype)
    return seen


def test_page_import_closure_is_served(client: Client) -> None:
    seen = _crawl(client)
    assert "/" in seen and "/static/app.mjs" in seen and "/static/vendor/admin-ui/base.css" in seen
    assert len(seen) >= 15, sorted(seen)
    for path, (status, ctype) in seen.items():
        assert status == 200, f"{path} answered {status}"
        ext = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
        if path == "/":
            assert ctype.startswith("text/html"), path
        elif ext in ("mjs", "js"):
            assert ctype.startswith("text/javascript"), f"{path}: {ctype}"
        elif ext == "css":
            assert ctype.startswith("text/css"), f"{path}: {ctype}"


def test_page_links_are_relative_and_below_the_ingress_path(client: Client) -> None:
    _, _, body = client.get("/")
    text = body.decode()
    for ref in LINK_RE.findall(text) + SCRIPT_RE.findall(text):
        assert not ref.startswith("/") and "://" not in ref, ref
    assert text.index("vendor/admin-ui/base.css") < text.index("static/app.css")
    assert not re.search(r"\son[a-z]+\s*=|\sstyle\s*=|<style\b", text, re.I), "inline handler or style in index.html"
    assert not re.search(r"<script\b(?![^>]*\bsrc=)", text, re.I), "inline script in index.html"


def test_every_whitelisted_static_file_is_served(client: Client) -> None:
    files = [p for p in STATIC.rglob("*") if p.is_file() and p.suffix.lstrip(".") in WHITELIST_EXT]
    assert len(files) >= 25
    for path in files:
        url = "/static/" + path.relative_to(STATIC).as_posix()
        status, _, body = client.get(url)
        assert status == 200, url
        assert body == path.read_bytes(), url


def test_lib_stamp_and_unlisted_files_are_not_served(client: Client) -> None:
    assert client.get("/static/vendor/admin-ui/LIB.stamp")[0] == 404
    assert client.get("/static/vendor/admin-ui/VERSION")[0] == 404
    assert client.get("/static/vendor/admin-ui/LIB.stamp", headers={})[0] == 403
