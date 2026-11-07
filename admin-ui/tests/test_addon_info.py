"""Slug lookup against the Supervisor (fake opener, no network) and its use in api/health."""

from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path
from typing import Any, Callable

import pytest

from app.addon_info import RETRY_AFTER_S, SUPERVISOR_URL, SlugResolver, fetch_slug
from app.web import demo_api
from app.web.skeleton import Router, StaticFiles

from conftest import INGRESS, Client


class Reply(io.BytesIO):
    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def opener_returning(payload: Any) -> Callable[..., Reply]:
    seen: list[urllib.request.Request] = []

    def opener(req: urllib.request.Request, timeout: float) -> Reply:
        seen.append(req)
        return Reply(payload if isinstance(payload, bytes) else json.dumps(payload).encode())

    opener.seen = seen  # type: ignore[attr-defined]
    return opener


def test_fetch_slug_calls_the_supervisor_with_the_bearer_token() -> None:
    opener = opener_returning({"result": "ok", "data": {"slug": "local_admin_ui"}})
    assert fetch_slug({"SUPERVISOR_TOKEN": "secret-token"}, opener) == "local_admin_ui"
    (req,) = opener.seen  # type: ignore[attr-defined]
    assert req.full_url == SUPERVISOR_URL
    assert req.get_header("Authorization") == "Bearer secret-token"


@pytest.mark.parametrize("slug", ["a1b2c3d4_admin_ui", "local_admin_ui"])
def test_fetch_slug_accepts_repo_and_local_slugs(slug: str) -> None:
    assert fetch_slug({"SUPERVISOR_TOKEN": "t"}, opener_returning({"data": {"slug": slug}})) == slug


@pytest.mark.parametrize(
    "payload",
    [b"not json", {"data": {}}, {"data": {"slug": 5}}, {"data": {"slug": "../x"}}, {"data": {"slug": "A b"}}, {"result": "error"}],
)
def test_fetch_slug_rejects_bad_answers(payload: Any) -> None:
    assert fetch_slug({"SUPERVISOR_TOKEN": "t"}, opener_returning(payload)) is None


def test_fetch_slug_without_token_never_calls_out() -> None:
    def boom(*_a: Any) -> None:
        raise AssertionError("must not be called")

    assert fetch_slug({}, boom) is None  # type: ignore[arg-type]
    assert fetch_slug({"SUPERVISOR_TOKEN": ""}, boom) is None  # type: ignore[arg-type]


def test_fetch_slug_swallows_errors_and_never_leaks_the_token(capsys: pytest.CaptureFixture[str]) -> None:
    def failing(*_a: Any) -> None:
        raise OSError("connection refused for Bearer secret-token")

    assert fetch_slug({"SUPERVISOR_TOKEN": "secret-token"}, failing) is None  # type: ignore[arg-type]
    out = capsys.readouterr()
    assert "secret-token" not in out.out + out.err


def test_resolver_caches_success_and_throttles_failures() -> None:
    now = [0.0]
    calls: list[int] = []
    answers = [None, "local_admin_ui"]

    def fetch(_env: Any) -> str | None:
        calls.append(1)
        return answers.pop(0)

    resolver = SlugResolver({}, fetch, lambda: now[0])
    assert resolver.get() is None
    assert resolver.get() is None  # throttled: no second call inside the pause
    assert len(calls) == 1
    now[0] = RETRY_AFTER_S + 1
    assert resolver.get() == "local_admin_ui"
    assert resolver.get() == "local_admin_ui"
    assert len(calls) == 2


def make_api(serve: Callable[..., Client], tmp_path: Path, slug: Callable[[], str | None]) -> Client:
    router = Router()
    demo_api.register(router, version="9.9.9", lib_version="0.1.0", slug=slug)
    return serve(router, StaticFiles(tmp_path))


def test_health_adds_addon_slug_when_known(serve: Callable[..., Client], tmp_path: Path) -> None:
    status, _, data = make_api(serve, tmp_path, lambda: "local_admin_ui").call("GET", "/api/health", INGRESS)
    assert status == 200
    assert json.loads(data) == {"status": "ok", "addon_version": "9.9.9", "lib_version": "0.1.0", "addon_slug": "local_admin_ui"}


def test_health_omits_addon_slug_when_unknown(serve: Callable[..., Client], tmp_path: Path) -> None:
    _, _, data = make_api(serve, tmp_path, lambda: None).call("GET", "/api/health", INGRESS)
    assert "addon_slug" not in json.loads(data)
