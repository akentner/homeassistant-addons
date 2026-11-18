"""GUI server routes behind the skeleton's ingress gate: overview, meta, Sync now, access, gate matrix, error hygiene."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.access import AccessError, AccessSchemaError, AccessStore
from app.paths import Paths
from app.web.admin_ui import INGRESS_REMOTE
from app.web.server import build_router, make_server
from app.web.service import GuiConfig, GuiService, load_gui_config
from guihelpers import INGRESS, serve, write_options  # noqa: F401

REPO = "example-org/private-addons"
LOOPBACK = "127.0.0.1"
HEX32 = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")
JSON = {**INGRESS, "Content-Type": "application/json"}


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    p = Paths.under(tmp_path)
    write_options(p, [{"repository": REPO}])
    return p


def make_service(paths: Paths, version: str | None = None) -> GuiService:
    config = load_gui_config(paths, hostname="h", version_file=paths.data_dir / "none")
    return GuiService(paths, GuiConfig(config.options, config.hostname, version))


def start(serve: Any, svc: GuiService, ingress_remote: str = LOOPBACK) -> Any:
    return serve(make_server(svc, 0, ingress_remote=ingress_remote, host=LOOPBACK))


def test_overview_needs_ingress_header(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths))
    status, _resp, body = client.call("GET", "/api/overview")
    assert status == 403 and json.loads(body)["error"] == "ingress_only"
    status, resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 200
    assert resp.getheader("Cache-Control") == "no-store"
    assert json.loads(body)["repositories"][0]["repository"] == REPO


@pytest.mark.parametrize("version", ["0.1.0-3", None])
def test_meta_route(serve: Any, paths: Paths, version: str | None) -> None:
    client = start(serve, make_service(paths, version))
    status, resp, body = client.call("GET", "/api/meta", INGRESS)
    assert status == 200
    assert resp.getheader("Cache-Control") == "no-store"
    assert json.loads(body) == {"version": version}


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
@pytest.mark.parametrize("path", ["/", "/api/overview", "/api/meta", "/api/sync", "/static/app.mjs"])
def test_gate_matrix_without_header(serve: Any, paths: Paths, method: str, path: str) -> None:
    client = start(serve, make_service(paths))
    status, _resp, body = client.call(method, path)
    assert status == 403
    assert json.loads(body)["error"] == "ingress_only"


def test_real_ingress_remote_refuses_loopback_with_header(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths), ingress_remote=INGRESS_REMOTE)
    for path in ("/", "/api/overview", "/api/meta"):
        status, _resp, _body = client.call("GET", path, INGRESS)
        assert status == 403


def test_no_public_route(paths: Paths) -> None:
    router = build_router(make_service(paths))
    routes = router.routes()
    assert routes
    assert not any(router.is_public(method, pattern) for method, pattern in routes)
    assert {("GET", "/api/overview"), ("GET", "/api/meta"), ("POST", "/api/sync")} <= set(routes)


def test_static_page_served_through_ingress(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths))
    for path in ("/", "/static/app.mjs", "/static/views/repositories.mjs"):
        status, _resp, _body = client.call("GET", path, INGRESS)
        assert status == 200, path


def test_sync_post_with_empty_object(serve: Any, paths: Paths) -> None:
    client = start(serve, make_service(paths))
    status, resp, body = client.call("POST", "/api/sync", JSON, b"{}")
    assert status == 202
    assert json.loads(body) == {"requested": True}
    assert resp.getheader("Cache-Control") == "no-store"
    assert json.loads(paths.trigger_file.read_text(encoding="utf-8")) == {}


@pytest.mark.parametrize(
    "headers,body",
    [
        (INGRESS, None),
        (JSON, b"[]"),
        (JSON, b'{"x": 1}'),
        ({**INGRESS, "Content-Type": "text/plain"}, b"{}"),
    ],
    ids=["no_body", "array", "unknown_field", "text_plain"],
)
def test_sync_post_bad_request(serve: Any, paths: Paths, headers: dict[str, str], body: bytes | None) -> None:
    client = start(serve, make_service(paths))
    status, _resp, raw = client.call("POST", "/api/sync", headers, body)
    assert status == 400
    assert json.loads(raw)["error"] == "bad_request"
    assert not paths.trigger_file.exists()


def test_os_error_is_internal_error_without_hash(
    serve: Any, paths: Paths, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    hash_ = "0123456789abcdef0123456789abcdef"
    svc = make_service(paths)

    def broken() -> dict:
        raise PermissionError(13, "Permission denied", f"/srv/git/access/example-org/private-addons/{hash_}")

    monkeypatch.setattr(svc, "overview", broken)
    client = start(serve, svc)
    status, _resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 500
    assert json.loads(body)["error"] == "internal_error"
    assert not HEX32.search(body.decode("utf-8"))
    captured = capsys.readouterr()
    assert not HEX32.search(captured.out + captured.err)


# --- access routes (MRP-14) ---------------------------------------------------------------------------------------

ACCESS = f"/api/access/{REPO}"


def body_of(raw: bytes) -> dict:
    return json.loads(raw) if raw else {}


def send(client: Any, method: str, path: str, doc: Any = None) -> tuple[int, Any, dict]:
    raw = None if doc is None else json.dumps(doc).encode()
    headers = JSON if raw is not None else INGRESS
    status, resp, data = client.call(method, path, headers, raw)
    return status, resp, body_of(data)


def stored(paths: Paths) -> list[dict]:
    return json.loads(paths.access_file.read_text(encoding="utf-8"))["entries"]


def seed(paths: Paths, user: str, source: str = "cli", repository: str = REPO) -> dict:
    return AccessStore(paths).add(repository, user, source=source)


@pytest.fixture
def client(serve: Any, paths: Paths) -> Any:
    return start(serve, make_service(paths))


def test_access_routes_are_registered_and_none_is_public(paths: Paths) -> None:
    router = build_router(make_service(paths))
    routes = set(router.routes())
    assert {
        ("GET", "/api/access"),
        ("POST", "/api/access/{owner}/{repo}"),
        ("GET", "/api/access/{owner}/{repo}/{user}/urls"),
        ("DELETE", "/api/access/{owner}/{repo}/{user}"),
        ("POST", "/api/access/{owner}/{repo}/{user}/rotate"),
    } <= routes
    assert not any(router.is_public(method, pattern) for method, pattern in routes)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/access"),
        ("POST", ACCESS),
        ("GET", f"{ACCESS}/carol/urls"),
        ("DELETE", f"{ACCESS}/carol"),
        ("POST", f"{ACCESS}/carol/rotate"),
    ],
)
def test_access_routes_need_ingress(client: Any, method: str, path: str) -> None:
    status, _resp, data = client.call(method, path)
    assert status == 403 and json.loads(data)["error"] == "ingress_only"


def test_access_list_route(client: Any, paths: Paths) -> None:
    status, resp, data = send(client, "GET", "/api/access")
    assert status == 200 and resp.getheader("Cache-Control") == "no-store"
    assert data["repositories"] == [{"repository": REPO, "active": True, "users": []}]


@pytest.mark.parametrize("doc", [None, {}, {"user": ""}, {"user": 5}, {"user": None}, {"user": "a b"}])
def test_add_invalid_user(client: Any, paths: Paths, doc: Any) -> None:
    status, _resp, data = send(client, "POST", ACCESS, doc)
    assert status == 400 and data["error"] == "invalid_user"
    assert not paths.access_file.exists()


@pytest.mark.parametrize("doc", [{"user": "carol", "hash": "0" * 32}, {"name": "carol"}, ["carol"]])
def test_add_strict_body(client: Any, paths: Paths, doc: Any) -> None:
    status, _resp, data = send(client, "POST", ACCESS, doc)
    assert status == 400 and data["error"] == "bad_request"
    assert not paths.access_file.exists()


def test_add_reserved_existing_and_unknown_repository(client: Any) -> None:
    assert send(client, "POST", ACCESS, {"user": "local"})[2]["error"] == "user_reserved"
    assert send(client, "POST", ACCESS, {"user": "carol"})[0] == 201
    status, _resp, data = send(client, "POST", ACCESS, {"user": "carol"})
    assert status == 409 and data["error"] == "user_exists"
    status, _resp, data = send(client, "POST", "/api/access/example-org/unknown", {"user": "carol"})
    assert status == 404 and data["error"] == "repository_unknown"


def test_add_with_mixed_case_path(client: Any, paths: Paths) -> None:
    status, resp, data = send(client, "POST", "/api/access/Example-Org/Private-Addons", {"user": "carol"})
    assert status == 201 and resp.getheader("Cache-Control") == "no-store"
    assert data["repository"] == REPO and data["user"] == "carol" and data["source"] == "gui"
    hash_ = stored(paths)[0]["hash"]
    assert data["urls"] == {"internal": f"http://h:8080/repo/{REPO}/{hash_}"}
    assert paths.link_path("example-org", "private-addons", hash_).is_symlink()


def test_urls_route(client: Any, paths: Paths) -> None:
    send(client, "POST", ACCESS, {"user": "carol"})
    hash_ = stored(paths)[0]["hash"]
    status, resp, data = send(client, "GET", f"{ACCESS}/carol/urls")
    assert status == 200 and resp.getheader("Cache-Control") == "no-store"
    assert data == {"internal": f"http://h:8080/repo/{REPO}/{hash_}"}
    for user in ("Carol", "nobody"):
        status, _resp, data = send(client, "GET", f"{ACCESS}/{user}/urls")
        assert status == 404 and data["error"] == "user_unknown"


@pytest.mark.parametrize("doc", [None, {}, {"confirm": "Carol"}, {"confirm": " carol"}, {"confirm": 1}])
def test_revoke_needs_exact_confirm(client: Any, paths: Paths, doc: Any) -> None:
    seed(paths, "carol")
    before = paths.access_file.read_bytes()
    status, _resp, data = send(client, "DELETE", f"{ACCESS}/carol", doc)
    assert status == 400 and data["error"] == "confirmation_required"
    assert paths.access_file.read_bytes() == before


def test_revoke_strict_body(client: Any, paths: Paths) -> None:
    seed(paths, "carol")
    status, _resp, data = send(client, "DELETE", f"{ACCESS}/carol", {"confirm": "carol", "force": True})
    assert status == 400 and data["error"] == "bad_request"
    assert len(stored(paths)) == 1


def test_revoke_with_exact_confirm_removes_entry_and_link(client: Any, paths: Paths) -> None:
    carol = seed(paths, "carol")
    AccessStore(paths).reconcile(make_service(paths).config.options.repositories)
    link = paths.link_path("example-org", "private-addons", carol["hash"])
    assert link.is_symlink()
    status, _resp, data = send(client, "DELETE", f"{ACCESS}/carol", {"confirm": "carol"})
    assert status == 204 and data == {}
    assert stored(paths) == [] and not link.is_symlink()
    status, _resp, data = send(client, "DELETE", f"{ACCESS}/carol", {"confirm": "carol"})
    assert status == 404 and data["error"] == "user_unknown"


def test_revoke_unconfigured_repository(client: Any, paths: Paths) -> None:
    seed(paths, "bob", repository="example-org/gone")
    status, _resp, _data = send(client, "DELETE", "/api/access/example-org/gone/bob", {"confirm": "bob"})
    assert status == 204 and stored(paths) == []


def test_revoke_and_rotate_of_system_user_are_protected(client: Any, paths: Paths) -> None:
    seed(paths, "local", "system")
    before = paths.access_file.read_bytes()
    for method, path in (("DELETE", f"{ACCESS}/local"), ("POST", f"{ACCESS}/local/rotate")):
        status, _resp, data = send(client, method, path, {"confirm": "local"})
        assert status == 409 and data["error"] == "protected", path
    assert paths.access_file.read_bytes() == before


def test_rotate_route(client: Any, paths: Paths) -> None:
    old = seed(paths, "carol", "cli")["hash"]
    status, resp, data = send(client, "POST", f"{ACCESS}/carol/rotate", {"confirm": "carol"})
    assert status == 200 and resp.getheader("Cache-Control") == "no-store"
    new = stored(paths)[0]["hash"]
    assert new != old
    assert data["source"] == "cli" and data["user"] == "carol" and data["repository"] == REPO
    assert data["urls"] == {"internal": f"http://h:8080/repo/{REPO}/{new}"}
    assert not paths.link_path("example-org", "private-addons", old).is_symlink()
    assert paths.link_path("example-org", "private-addons", new).is_symlink()


@pytest.mark.parametrize("doc", [None, {"confirm": "Carol"}, {"confirm": False}])
def test_rotate_needs_exact_confirm(client: Any, paths: Paths, doc: Any) -> None:
    seed(paths, "carol")
    before = paths.access_file.read_bytes()
    status, _resp, data = send(client, "POST", f"{ACCESS}/carol/rotate", doc)
    assert status == 400 and data["error"] == "confirmation_required"
    assert paths.access_file.read_bytes() == before


def test_rotate_unconfigured_repository(client: Any, paths: Paths) -> None:
    seed(paths, "bob", repository="example-org/gone")
    status, _resp, data = send(client, "POST", "/api/access/example-org/gone/bob/rotate", {"confirm": "bob"})
    assert status == 404 and data["error"] == "repository_unknown"


@pytest.mark.parametrize(
    "method,path,doc",
    [
        ("GET", "/api/access", None),
        ("POST", ACCESS, {"user": "carol"}),
        ("GET", f"{ACCESS}/carol/urls", None),
        ("DELETE", f"{ACCESS}/carol", {"confirm": "carol"}),
        ("POST", f"{ACCESS}/carol/rotate", {"confirm": "carol"}),
    ],
)
def test_unreadable_access_file_is_503_and_untouched(
    client: Any, paths: Paths, method: str, path: str, doc: Any
) -> None:
    paths.access_file.write_text("{not json", encoding="utf-8")
    status, _resp, data = send(client, method, path, doc)
    assert status == 503 and data["error"] == "access_unavailable"
    assert paths.access_file.read_text(encoding="utf-8") == "{not json"
    assert not paths.access_file.with_name("access.json.corrupt").exists()


def test_access_os_error_is_internal_error_without_hash(
    serve: Any, paths: Paths, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    hash_ = "0123456789abcdef0123456789abcdef"
    svc = make_service(paths)

    def broken(*_args: Any) -> dict:
        raise PermissionError(13, "Permission denied", f"/srv/git/access/example-org/private-addons/{hash_}")

    monkeypatch.setattr(svc, "rotate_user", broken)
    client = start(serve, svc)
    status, _resp, raw = client.call("POST", f"{ACCESS}/carol/rotate", JSON, b'{"confirm": "carol"}')
    assert status == 500 and json.loads(raw)["error"] == "internal_error"
    assert not HEX32.search(raw.decode("utf-8"))
    captured = capsys.readouterr()
    assert not HEX32.search(captured.out + captured.err)


@pytest.mark.parametrize(
    "exc,code,status",
    [
        (AccessError("invalid_source"), "internal_error", 500),
        (AccessError("hash_conflict"), "hash_conflict", 409),
        (AccessError("invalid_hash"), "invalid_hash", 409),
        (AccessSchemaError("schema_unsupported"), "access_unavailable", 503),
    ],
)
def test_access_error_mapping(
    serve: Any,
    paths: Paths,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exc: Exception,
    code: str,
    status: int,
) -> None:
    svc = make_service(paths)

    def broken(*_args: Any) -> dict:
        raise exc

    monkeypatch.setattr(svc, "access_list", broken)
    client = start(serve, svc)
    got, _resp, raw = client.call("GET", "/api/access", INGRESS)
    data = json.loads(raw)
    assert got == status and data["error"] == code
    assert data["message"] != str(exc) or code == data["message"].replace(" ", "_")
    assert "Traceback" not in capsys.readouterr().out
