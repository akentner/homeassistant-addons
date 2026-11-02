"""Public routes of the skeleton: exact method+path opt-out of the ingress gate, and everything that must stay closed."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from app.web.skeleton import DEFAULT_CSP, Request, Router, StaticFiles, ingress_user, make_server

from test_skeleton_server import INGRESS, JSON_HEADERS, Client, make_static

FORGED = {
    "X-Ingress-Path": "/api/hassio_ingress/abc",
    "X-Remote-User-Id": "u1",
    "X-Remote-User-Name": "mallory",
    "X-Remote-User-Groups": "system-admin",
}


def build() -> tuple[Router, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []
    router = Router()

    def whoami(req: Request) -> Any:
        seen.append({"user": ingress_user(req.headers), "public": req.public, "id_header": req.headers.get("X-Remote-User-Id")})
        return {"ok": True}

    router.add("GET", "/api/health", whoami, public=True)
    router.add("POST", "/api/ping", lambda req: (201, req.body()), public=True)
    router.add("GET", "/api/status.json", lambda req: {"status": "ok"}, public=True)
    router.add("GET", "/api/private", lambda req: {"secret": 1})
    router.add("POST", "/api/private", lambda req: {"secret": 2})
    router.add("GET", "/api/users/{name}", lambda req: {"name": req.params["name"]})
    return router, seen


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Callable[..., tuple[Client, list[dict[str, Any]]]]]:
    servers: list[Any] = []

    def _start(**kwargs: Any) -> tuple[Client, list[dict[str, Any]]]:
        router, seen = build()
        kwargs.setdefault("csp", DEFAULT_CSP)
        httpd = make_server(router, make_static(tmp_path / "static"), 0, host="127.0.0.1", ingress_remote="127.0.0.1" if kwargs.pop("ingress_peer", False) else "10.9.9.9", **kwargs)
        thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        servers.append((httpd, thread))
        return Client(httpd.server_address[1]), seen

    yield _start
    for httpd, thread in servers:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


# ---- router unit ----


def test_default_is_private_and_public_is_exact() -> None:
    router, _ = build()
    assert router.is_public("GET", "/api/health")
    assert router.is_public("POST", "/api/ping")
    assert not router.is_public("GET", "/api/private")
    assert not router.is_public("POST", "/api/health")
    assert not router.is_public("get", "/api/health")
    assert not router.is_public("HEAD", "/api/health")
    assert not router.is_public("OPTIONS", "/api/health")
    assert not router.is_public("GET", "/api/users/bob")


@pytest.mark.parametrize(
    "pattern",
    [
        "/api/users/{name}", "/", "/icon", "/static", "/static/app.css", "/a/../b", "/a/./b", "/a/", "api/x", "/a b",
        "/a%2e", "/a?b", "/a#b", "//a", "/a//b", "", "/a;b", "/..", "/.hidden/x", "/A/ä",
    ],
)
def test_unsafe_public_patterns_are_rejected(pattern: str) -> None:
    with pytest.raises(ValueError):
        Router().add("GET", pattern, lambda req: None, public=True)


def test_private_registration_is_unchanged() -> None:
    router = Router()
    router.add("GET", "/api/users/{name}", lambda req: None)
    router.add("GET", "/", lambda req: None)
    assert router.routes() == [("GET", "/api/users/{name}"), ("GET", "/")]
    assert not router.is_public("GET", "/")


# ---- over HTTP ----


def test_public_get_works_without_ingress_with_api_headers(served: Callable[..., Any]) -> None:
    cli, _ = served()
    status, resp, data = cli.call("GET", "/api/health")
    assert status == 200 and json.loads(data) == {"ok": True}
    assert resp.getheader("Cache-Control") == "no-store"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    assert resp.getheader("Referrer-Policy") == "same-origin"
    assert resp.getheader("Content-Security-Policy") is None  # api responses never carry it, public or not
    assert cli.json("GET", "/api/status.json") == (200, {"status": "ok"})
    assert cli.json("GET", "/api/health?x=1")[0] == 200  # a query string is not part of the route


def test_public_route_does_not_depend_on_the_csp_setting(served: Callable[..., Any]) -> None:
    cli, _ = served(csp=None)
    assert cli.call("GET", "/api/health")[0] == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def test_other_methods_on_a_public_route_stay_closed(served: Callable[..., Any], method: str) -> None:
    cli, _ = served()
    status, _, data = cli.call(method, "/api/health", {"Content-Type": "application/json"}, b"{}" if method in ("POST", "PUT", "PATCH") else None)
    assert status == 403
    assert data == b"" if method == "HEAD" else json.loads(data) == {"error": "ingress_only"}


def test_a_public_post_route_takes_a_body_without_ingress(served: Callable[..., Any]) -> None:
    cli, _ = served()
    assert cli.json("POST", "/api/ping", {"Content-Type": "application/json"}, b'{"a":1}') == (201, {"a": 1})
    assert cli.json("POST", "/api/ping", {"Content-Type": "text/plain"}, b"x")[0] == 400
    assert cli.call("GET", "/api/ping")[0] == 403


@pytest.mark.parametrize("method", ["GET", "POST", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("path", ["/api/private", "/api/users/bob", "/nope", "/api", "/api/healthz", "/api/health/x"])
def test_private_unknown_and_neighbour_paths_stay_closed(served: Callable[..., Any], method: str, path: str) -> None:
    cli, _ = served()
    assert cli.call(method, path)[0] == 403


@pytest.mark.parametrize("path", ["/", "/icon", "/static/app.mjs", "/static/app.css", "/static/../api/health"])
def test_static_index_and_icon_are_never_public(served: Callable[..., Any], path: str) -> None:
    cli, _ = served()
    status, _, data = cli.call("GET", path)
    assert status == 403 and json.loads(data) == {"error": "ingress_only"}


@pytest.mark.parametrize(
    "target",
    [
        "/api/health/", "//api/health", "/api//health", "/api/./health", "/api/x/../health", "/api/%68ealth", "/api/%2e/health",
        "/%2e/api/health", "/api/health%00", "/api/health%2f", "/api/health;x", "/API/health", "/Api/Health", "/api/health.",
        "//evil.example/api/health", "http://example.invalid/api/health", "/api/health/..", "/api/private?/api/health",
        "/api/private?x=/api/health", "/api/private/../health", "/static/x/../../api/health", "/api/health\\", "/api\\health",
    ],
)
def test_bypass_attempts_are_rejected(served: Callable[..., Any], target: str) -> None:
    cli, seen = served()
    assert cli.call("GET", target)[0] == 403, target
    assert seen == []  # the handler never ran


def test_a_public_handler_sees_no_ingress_identity(served: Callable[..., Any]) -> None:
    cli, seen = served()
    assert cli.call("GET", "/api/health", FORGED)[0] == 200
    assert seen == [{"user": None, "public": True, "id_header": None}]


def test_forged_ingress_headers_from_a_foreign_peer_do_not_open_private_routes(served: Callable[..., Any]) -> None:
    cli, _ = served()
    for path in ("/api/private", "/", "/api/users/bob"):
        assert cli.call("GET", path, FORGED)[0] == 403


def test_ingress_callers_keep_everything_including_identity(served: Callable[..., Any]) -> None:
    cli, seen = served(ingress_peer=True)
    headers = {**INGRESS, "X-Remote-User-Id": "u1", "X-Remote-User-Name": "alice"}
    for path in ("/", "/static/app.mjs", "/api/private", "/api/health", "/api/users/bob"):
        assert cli.call("GET", path, headers)[0] == 200, path
    assert cli.json("POST", "/api/private", JSON_HEADERS, b"{}")[0] == 200
    assert seen[0]["public"] is False and seen[0]["user"]["user_id"] == "u1"
    assert cli.json("POST", "/api/health", JSON_HEADERS, b"{}")[0] == 405  # unchanged: HEAD/POST need their own route


def test_demo_api_registers_no_public_route(tmp_path: Path) -> None:
    from app.web import demo_api

    router = Router()
    demo_api.register(router, version="1", lib_version="1")
    assert not any(router.is_public(m, p) for m, p in router.routes())
