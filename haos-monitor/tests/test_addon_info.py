"""Slug and version lookup against the Supervisor (fake opener, no network)."""

from __future__ import annotations

import io
import json
import urllib.request
from typing import Any

import pytest

from app.addon_info import RETRY_AFTER_S, SUPERVISOR_URL, InfoResolver, fetch_info


class Reply(io.BytesIO):
    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def opener_returning(payload: Any) -> Any:
    seen: list[urllib.request.Request] = []

    def opener(req: urllib.request.Request, timeout: float) -> Reply:
        seen.append(req)
        return Reply(json.dumps(payload).encode())

    opener.seen = seen  # type: ignore[attr-defined]
    return opener


def test_fetch_info_returns_slug_and_version_with_the_bearer_token() -> None:
    opener = opener_returning({"result": "ok", "data": {"slug": "a1b2c3d4_haos_monitor", "version": "0.7.3-0"}})
    assert fetch_info({"SUPERVISOR_TOKEN": "secret"}, opener) == {"slug": "a1b2c3d4_haos_monitor", "version": "0.7.3-0"}
    (req,) = opener.seen
    assert req.full_url == SUPERVISOR_URL
    assert req.get_header("Authorization") == "Bearer secret"


def test_no_token_means_unknown_without_a_request(tmp_path: Any) -> None:
    opener = opener_returning({})
    assert fetch_info({}, opener, str(tmp_path / "missing")) is None
    assert opener.seen == []


@pytest.mark.parametrize(
    "data",
    [
        {"slug": "x", "version": "<b>1</b>"},
        {"slug": "../x", "version": "1.0.0"},
        {"slug": "x"},
        {"version": "1.0.0"},
        {"slug": 1, "version": "1.0.0"},
        {"slug": "x", "version": "v" * 40},
    ],
)
def test_unexpected_shapes_are_unknown(data: dict[str, Any]) -> None:
    assert fetch_info({"SUPERVISOR_TOKEN": "t"}, opener_returning({"data": data})) is None


def test_a_failing_supervisor_is_unknown_and_does_not_leak_the_token() -> None:
    def boom(req: urllib.request.Request, timeout: float) -> Reply:
        raise OSError("down: Bearer secret")

    assert fetch_info({"SUPERVISOR_TOKEN": "secret"}, boom) is None


def test_resolver_caches_success_and_retries_failure_after_a_pause() -> None:
    now = [0.0]
    answers: list[Any] = [None, {"slug": "s", "version": "1.0.0"}]
    calls: list[int] = []

    def fetch(_env: Any) -> Any:
        calls.append(1)
        return answers.pop(0)

    resolver = InfoResolver({}, fetch, lambda: now[0])
    assert resolver.get() is None
    assert resolver.get() is None and len(calls) == 1  # inside the pause
    now[0] += RETRY_AFTER_S
    assert resolver.get() == {"slug": "s", "version": "1.0.0"}
    assert resolver.get() == {"slug": "s", "version": "1.0.0"} and len(calls) == 2  # cached for good


def test_token_falls_back_to_the_s6_container_environment_file(tmp_path: Any) -> None:
    token_file = tmp_path / "SUPERVISOR_TOKEN"
    token_file.write_text("from-file\n")
    opener = opener_returning({"data": {"slug": "s", "version": "1.0.0"}})
    assert fetch_info({}, opener, str(token_file)) == {"slug": "s", "version": "1.0.0"}
    (req,) = opener.seen
    assert req.get_header("Authorization") == "Bearer from-file"
