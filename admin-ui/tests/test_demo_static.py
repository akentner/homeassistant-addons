"""Served-files test: every file the demo page references is served through the ingress gate with the right type."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.web import demo_api
from app.web.skeleton import Router, StaticFiles
from app.web.skeleton.static import CONTENT_TYPES

from conftest import ADMIN_UI_DIR, INGRESS

STATIC_DIR = ADMIN_UI_DIR / "app" / "web" / "static"
LIB_DIR = STATIC_DIR / "lib"
LIB_VERSION = (LIB_DIR / "VERSION").read_text(encoding="utf-8").strip()
IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)["'](\.{1,2}/[^"'`$]+)["']""")
HTML_REF_RE = re.compile(r"""\b(?:src|href)\s*=\s*["'](static/[^"']+)["']""")


def _client(serve):
    router = Router()
    demo_api.register(router, version="9.9.9", lib_version=LIB_VERSION)
    return serve(router, StaticFiles(STATIC_DIR))


def _content_type(path: Path) -> str:
    return CONTENT_TYPES[path.suffix.lstrip(".")]


def _referenced() -> set[str]:
    """URL paths (below /static/) referenced by index.html and by relative imports of app and view modules."""
    found: set[str] = set()
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for ref in HTML_REF_RE.findall(index):
        found.add(ref[len("static/"):])
    sources = [STATIC_DIR / "app.mjs", *sorted((STATIC_DIR / "views").glob("*.mjs"))]
    for source in sources:
        for ref in IMPORT_RE.findall(source.read_text(encoding="utf-8")):
            target = (source.parent / ref).resolve()
            found.add(target.relative_to(STATIC_DIR.resolve()).as_posix())
    return found


def test_index_references_exist_and_are_relative() -> None:
    index = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    refs = HTML_REF_RE.findall(index)
    assert "static/lib/base.css" in refs and "static/app.css" in refs and "static/app.mjs" in refs
    for ref in refs:
        assert (STATIC_DIR / ref[len("static/"):]).is_file(), ref
    assert not re.search(r"""\b(?:src|href)\s*=\s*["'](?:/|[a-z][a-z0-9+.-]*:)""", index, re.I)


def test_every_referenced_file_is_served(serve) -> None:
    client = _client(serve)
    referenced = _referenced()
    assert {"lib/ui.mjs", "lib/base.css", "app.css", "strings.de.mjs", "strings.en.mjs"} <= referenced
    for rel in sorted(referenced):
        path = STATIC_DIR / rel
        status, resp, data = client.call("GET", f"/static/{rel}", INGRESS)
        assert status == 200, rel
        assert resp.getheader("Content-Type") == _content_type(path), rel
        assert data == path.read_bytes(), rel


def test_every_servable_lib_file_is_served(serve) -> None:
    client = _client(serve)
    files = [p for p in sorted(LIB_DIR.rglob("*")) if p.is_file() and p.suffix.lstrip(".") in CONTENT_TYPES]
    assert files
    for path in files:
        rel = path.relative_to(STATIC_DIR).as_posix()
        status, resp, _ = client.call("GET", f"/static/{rel}", INGRESS)
        assert status == 200, rel
        assert resp.getheader("Content-Type") == _content_type(path), rel


def test_vendored_runtime_is_served_and_version_stamp_is_hidden(serve) -> None:
    client = _client(serve)
    status, resp, _ = client.call("GET", "/static/lib/vendor/preact-htm.mjs", INGRESS)
    assert status == 200
    assert resp.getheader("Content-Type") == "text/javascript; charset=utf-8"
    status, _, _ = client.call("GET", "/static/lib/VERSION", INGRESS)
    assert status == 404


@pytest.mark.parametrize("view", ["gallery", "tokens", "language", "crud"])
def test_view_modules_exist_once_written(view: str) -> None:
    path = STATIC_DIR / "views" / f"{view}.mjs"
    if path.exists():
        assert path.stat().st_size > 0
