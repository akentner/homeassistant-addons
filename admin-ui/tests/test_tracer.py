"""Tracer tests: ingress gate matrix, health and static serving, vendored runtime pin, skeleton import hygiene."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest

from app.web import demo_api
from app.web.skeleton import ApiError, Router, StaticFiles

from conftest import ADMIN_UI_DIR, INGRESS

STATIC_DIR = ADMIN_UI_DIR / "app" / "web" / "static"
SKELETON_DIR = ADMIN_UI_DIR / "app" / "web" / "skeleton"
VENDOR_DIR = STATIC_DIR / "lib" / "vendor"
PREACT_SHA256 = "72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7"
LIB_VERSION = (STATIC_DIR / "lib" / "VERSION").read_text(encoding="utf-8").strip()


def build_client(serve, remote: str = "127.0.0.1"):
    router = Router()
    demo_api.register(router, version="9.9.9", lib_version=LIB_VERSION)
    return serve(router, StaticFiles(STATIC_DIR), ingress_remote=remote)


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("path", ["/", "/static/app.mjs", "/api/health", "/nope"])
def test_gate_blocks_without_header(serve, method: str, path: str) -> None:
    client = build_client(serve)
    status, _, data = client.call(method, path)
    assert status == 403
    if method != "HEAD":
        assert json.loads(data) == {"error": "ingress_only"}


def test_gate_blocks_empty_header(serve) -> None:
    status, _, data = build_client(serve).call("GET", "/api/health", {"X-Ingress-Path": ""})
    assert status == 403
    assert json.loads(data) == {"error": "ingress_only"}


@pytest.mark.parametrize("method", ["GET", "POST", "HEAD", "OPTIONS"])
def test_foreign_peer_is_blocked_even_with_header(serve, method: str) -> None:
    client = build_client(serve, remote="10.9.9.9")
    for path in ("/", "/api/health", "/static/app.mjs"):
        status, _, _ = client.call(method, path, INGRESS)
        assert status == 403


def test_index_and_health_are_served_through_the_gate(serve) -> None:
    client = build_client(serve)
    status, resp, data = client.call("GET", "/", INGRESS)
    assert status == 200
    assert resp.getheader("Content-Type") == "text/html; charset=utf-8"
    assert b'id="app"' in data
    status, resp, data = client.call("GET", "/api/health", INGRESS)
    assert status == 200
    assert json.loads(data) == {"status": "ok", "addon_version": "9.9.9", "lib_version": LIB_VERSION}
    assert resp.getheader("Cache-Control") == "no-store"


def test_lib_client_is_served_as_javascript(serve) -> None:
    status, resp, data = build_client(serve).call("GET", "/static/lib/api.mjs", INGRESS)
    assert status == 200
    assert resp.getheader("Content-Type") == "text/javascript; charset=utf-8"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    assert b"buildUrl" in data


def test_vendored_bundle_is_pinned() -> None:
    bundle = VENDOR_DIR / "preact-htm.mjs"
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == PREACT_SHA256
    assert PREACT_SHA256 in (VENDOR_DIR / "README.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["/static/lib/VERSION", "/static/../app/main.py", "/static/.hidden.css", "/static/lib/nope.mjs"])
def test_static_whitelist_hides_everything_else(serve, path: str) -> None:
    status, _, data = build_client(serve).call("GET", path, INGRESS)
    assert status == 404
    assert json.loads(data)["error"] == "not_found"


def test_static_has_no_frame_options(serve) -> None:
    client = build_client(serve)
    for path in ("/", "/static/app.mjs", "/static/app.css"):
        status, resp, _ = client.call("GET", path, INGRESS)
        assert status == 200
        assert resp.getheader("X-Frame-Options") is None
        assert resp.getheader("Cache-Control") == "no-cache"


def test_unexpected_exception_is_a_generic_500(serve, capsys) -> None:
    router = Router()

    def boom(_req):
        raise RuntimeError("secret detail")

    router.add("GET", "/api/boom", boom)
    client = serve(router, StaticFiles(STATIC_DIR))
    status, _, data = client.call("GET", "/api/boom", INGRESS)
    assert status == 500
    assert json.loads(data) == {"error": "internal_error", "message": "internal error"}
    assert b"secret" not in data


def test_api_error_defaults_and_unknown_code() -> None:
    err = ApiError("protected")
    assert (err.status, err.message) == (409, "protected")
    with pytest.raises(ValueError):
        ApiError("nope")


def test_skeleton_imports_only_stdlib_or_relative() -> None:
    stdlib = sys.stdlib_module_names
    sources = sorted(SKELETON_DIR.glob("*.py"))
    assert {p.name for p in sources} >= {"__init__.py", "errors.py", "ingress.py", "router.py", "server.py", "static.py"}
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in stdlib, f"{source.name}: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert (node.module or "").split(".")[0] in stdlib, f"{source.name}: {node.module}"
                else:
                    assert node.level == 1, f"{source.name}: deep relative import"
