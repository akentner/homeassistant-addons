"""Supervisor client (app.supervisor): allow-list, token handling, transport hardening, envelope parsing, masking.

Every test runs against the in-process fake Supervisor or tiny local servers on 127.0.0.1; never a real Supervisor.
"""

from __future__ import annotations

import ast
import hashlib
import http.server
import logging
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Iterator

import fake_supervisor
import pytest

from app import supervisor
from app.access import new_hash
from app.supervisor import (
    ALLOWED,
    DUPLICATE_ERROR_KEY,
    TOKEN_ENVS,
    CallResult,
    SupervisorClient,
    SupervisorRefused,
    mask_text,
    read_token,
    store_slug,
)

APP_DIR = Path(__file__).resolve().parent.parent / "app"
HEX32_RE = re.compile(r"[0-9a-f]{32}")


def _token() -> str:
    # Built at runtime so no token-shaped literal sits in the repository
    return "sentinel" + "-supervisor-" + secrets.token_hex(4)


def _store_url(hash_: str | None = None) -> str:
    return f"http://addon-host:8080/repo/example-org/private-addons/{hash_ or new_hash()}"


@pytest.fixture
def fake() -> Iterator[tuple[fake_supervisor.FakeState, str]]:
    state = fake_supervisor.FakeState(_token(), clone=lambda url: "Fixture")
    server = fake_supervisor.serve(state)
    try:
        yield state, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _client(state: fake_supervisor.FakeState, base: str, token: str | None = None) -> SupervisorClient:
    return SupervisorClient(state.token if token is None else token, base=base, log=logging.getLogger("mrp.supervisor"))


def _closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _Server:
    """A tiny local HTTP server with a custom handler, shut down by the context manager."""

    def __init__(self, handler: type[http.server.BaseHTTPRequestHandler]) -> None:
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.server.hits = []  # type: ignore[attr-defined]
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self) -> "_Server":
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        return self

    def __exit__(self, *_: object) -> None:
        self.server.shutdown()
        self.server.server_close()


class _Quiet(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _reply(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Recorder(_Quiet):
    def do_GET(self) -> None:
        self.server.hits.append((self.path, self.headers.get("Authorization")))  # type: ignore[attr-defined]
        self._reply(200, b'{"result": "ok", "data": []}')


class _PlainText(_Quiet):
    def do_GET(self) -> None:
        self._reply(200, b"not the envelope")


class _Empty(_Quiet):
    def do_GET(self) -> None:
        self._reply(200, b"")


class _Slow(_Quiet):
    def do_GET(self) -> None:
        time.sleep(0.5)
        try:
            self._reply(200, b'{"result": "ok", "data": []}')
        except OSError:
            pass


# --- allow-list ----------------------------------------------------------------------------------------------------

REFUSED = [
    ("GET", "/store", None, "not_allowed"),
    ("POST", "/addons/x/uninstall", None, "not_allowed"),
    ("get", "/store/repositories", None, "not_allowed"),
    ("GET", "/store/repositories/", None, "not_allowed"),
    ("POST", "/v2/store/reload", None, "not_allowed"),
    ("DELETE", "/store/repositories/{slug}", None, "invalid_slug"),
    ("DELETE", "/store/repositories/{slug}", "", "invalid_slug"),
    ("DELETE", "/store/repositories/{slug}", "abcdef1", "invalid_slug"),
    ("DELETE", "/store/repositories/{slug}", "abcdef123", "invalid_slug"),
    ("DELETE", "/store/repositories/{slug}", "ABCDEF12", "invalid_slug"),
    ("DELETE", "/store/repositories/{slug}", "abcdef12\n", "invalid_slug"),
    ("DELETE", "/store/repositories/{slug}", "../reload", "invalid_slug"),
]


@pytest.mark.parametrize(("method", "template", "slug", "code"), REFUSED)
def test_refused_calls_send_nothing(fake, method: str, template: str, slug: str | None, code: str) -> None:
    state, base = fake
    with pytest.raises(SupervisorRefused) as info:
        _client(state, base).call(method, template, slug=slug)
    assert info.value.code == code
    assert state.requests == []


def test_allow_list_is_exactly_the_four_store_calls() -> None:
    assert ALLOWED == {
        ("GET", "/store/repositories"),
        ("POST", "/store/repositories"),
        ("DELETE", "/store/repositories/{slug}"),
        ("POST", "/store/reload"),
    }
    assert set(supervisor.TIMEOUTS) == set(ALLOWED)


def test_body_only_on_add(fake) -> None:
    state, base = fake
    client = _client(state, base)
    with pytest.raises(SupervisorRefused) as info:
        client.call("POST", "/store/repositories")
    assert info.value.code == "invalid_body"
    with pytest.raises(SupervisorRefused) as info:
        client.call("GET", "/store/repositories", body={"repository": "x"})
    assert info.value.code == "invalid_body"
    with pytest.raises(SupervisorRefused) as info:
        client.call("POST", "/store/repositories", body=["not", "a", "dict"])  # type: ignore[arg-type]
    assert info.value.code == "invalid_body"
    assert state.requests == []


def test_empty_token_is_refused_before_io(fake) -> None:
    state, base = fake
    with pytest.raises(SupervisorRefused) as info:
        _client(state, base, token="").list_repositories()
    assert info.value.code == "token_missing"
    assert state.requests == []


def test_wrong_token_gives_403_without_message(fake) -> None:
    state, base = fake
    result = _client(state, base, token=_token()).list_repositories()
    assert (result.ok, result.status, result.message) == (False, 403, "")
    assert [r["auth"] for r in state.requests] == ["wrong"]


# --- store calls against the fake ----------------------------------------------------------------------------------


def test_store_calls_against_the_fake(fake, monkeypatch: pytest.MonkeyPatch) -> None:
    state, base = fake
    client = _client(state, base)
    listed = client.list_repositories()
    assert listed.ok and listed.status == 200
    assert {item["slug"] for item in listed.data} == {"core", "local"}
    assert state.requests[-1]["auth"] == "ok"

    hash_ = new_hash()
    url = _store_url(hash_)
    added = client.add_repository(url)
    assert added.ok and added.status == 200
    again = client.add_repository(url)
    assert again.duplicate and again.status == 409 and not again.ok
    assert again.error_key == DUPLICATE_ERROR_KEY
    assert hash_ not in again.message

    slug = store_slug(url)
    state.in_use.add(slug)
    refused = client.remove_repository(slug)
    assert refused.in_use and refused.status == 400 and refused.error_key is None
    assert not HEX32_RE.search(refused.message)
    assert "…" in refused.message and hash_[:4] + "…" in refused.message

    missing = client.remove_repository("0123abcd")
    assert missing.not_found and not missing.ok

    state.in_use.clear()
    assert client.remove_repository(slug).ok

    monkeypatch.setattr(fake_supervisor, "_ls_remote_head", lambda source: None)
    reloaded = client.reload_store()
    assert reloaded.ok and state.reloads == 1
    assert all(r["auth"] == "ok" for r in state.requests)


# --- transport hardening -------------------------------------------------------------------------------------------


def test_proxy_environment_is_ignored(fake, monkeypatch: pytest.MonkeyPatch) -> None:
    state, base = fake
    proxy = f"http://127.0.0.1:{_closed_port()}"
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, proxy)
    for name in ("no_proxy", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
    result = _client(state, base).list_repositories()
    assert result.ok
    assert len(state.requests) == 1


def test_redirect_is_never_followed() -> None:
    with _Server(_Recorder) as target:

        class _Redirect(_Quiet):
            def do_GET(self) -> None:
                self._reply(307, b"", {"Location": target.base + "/store/repositories"})

        with _Server(_Redirect) as redirector:
            result = SupervisorClient(_token(), base=redirector.base).list_repositories()
        assert (result.ok, result.status) == (False, 307)
        assert target.server.hits == []  # type: ignore[attr-defined]


def test_timeout_gives_status_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(supervisor.TIMEOUTS, ("GET", "/store/repositories"), 0.2)
    with _Server(_Slow) as slow:
        result = SupervisorClient(_token(), base=slow.base).list_repositories()
    assert (result.ok, result.status, result.message) == (False, 0, "timeout")


def test_closed_port_is_unreachable() -> None:
    result = SupervisorClient(_token(), base=f"http://127.0.0.1:{_closed_port()}").list_repositories()
    assert (result.ok, result.status, result.message) == (False, 0, "unreachable")


@pytest.mark.parametrize("handler", [_PlainText, _Empty])
def test_200_without_envelope_is_a_failure(handler: type[http.server.BaseHTTPRequestHandler]) -> None:
    with _Server(handler) as server:
        result = SupervisorClient(_token(), base=server.base).list_repositories()
    assert (result.ok, result.status, result.data) == (False, 200, None)


# --- token hygiene and logging -------------------------------------------------------------------------------------


def test_token_never_leaves_the_header(fake, caplog: pytest.LogCaptureFixture) -> None:
    state, base = fake
    client = _client(state, base)
    url = _store_url()
    with caplog.at_level(logging.DEBUG):
        results = [client.list_repositories(), client.add_repository(url), client.add_repository(url)]
        results.append(client.remove_repository(store_slug(url)))
        with pytest.raises(SupervisorRefused) as info:
            client.remove_repository("nope")
    texts = [repr(client), str(info.value), repr(info.value), caplog.text]
    for result in results:
        texts += [repr(result), str(result.data), result.message, str(result.error_key)]
    assert all(state.token not in text for text in texts)
    assert "Bearer" not in caplog.text


def test_one_log_line_per_sent_request(fake, caplog: pytest.LogCaptureFixture) -> None:
    state, base = fake
    client = _client(state, base)
    url = _store_url()
    slug = store_slug(url)
    with caplog.at_level(logging.DEBUG, logger="mrp.supervisor"):
        client.list_repositories()
        client.add_repository(url)
        client.add_repository(url)
        client.remove_repository(slug)
        with pytest.raises(SupervisorRefused):
            client.call("GET", "/store")
    lines = [r.getMessage() for r in caplog.records if r.name == "mrp.supervisor"]
    sent = [line for line in lines if line.startswith("supervisor ") and not line.startswith("supervisor call")]
    assert sent == [
        "supervisor GET /store/repositories: 200",
        "supervisor POST /store/repositories: 200",
        "supervisor POST /store/repositories: 409",
        "supervisor DELETE /store/repositories/{slug}: 200",
    ]
    assert len(sent) == len(state.requests)
    assert "supervisor call refused: not_allowed" in lines
    assert not any(slug in line for line in lines)
    assert not any(url in line for line in lines)


def test_read_token_prefers_supervisor_token() -> None:
    first, second = _token(), _token()
    assert TOKEN_ENVS == ("SUPERVISOR_TOKEN", "HASSIO_TOKEN")
    assert read_token({TOKEN_ENVS[0]: f" {first}\n", TOKEN_ENVS[1]: second}) == first
    assert read_token({TOKEN_ENVS[0]: "  ", TOKEN_ENVS[1]: second}) == second
    assert read_token({}) == ""


# --- slug and masking ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["http://addon-host:8080/repo/Example-Org/Private-Addons/", "HTTP://X/Y"])
def test_store_slug_matches_the_fake_and_the_supervisor(url: str) -> None:
    url = url + new_hash()
    expected = hashlib.sha1(url.lower().encode("utf-8")).hexdigest()[:8]
    assert store_slug(url) == fake_supervisor.store_slug(url) == expected
    assert store_slug(url) == store_slug(url.upper())


def test_mask_text_masks_store_paths() -> None:
    hash_ = new_hash()
    text = f"Can't remove 'http://h:8080/repo/o/r/{hash_}'. It's used by installed apps"
    masked = mask_text(text)
    assert f"/repo/o/r/{hash_[:4]}…" in masked
    assert not HEX32_RE.search(masked)
    assert supervisor.REFUSAL_MARKER in masked
    assert mask_text(f"two\nlines {hash_}") == "two"
    assert not HEX32_RE.search(mask_text(f"bare {hash_} run"))


def test_call_result_properties() -> None:
    assert CallResult(False, 409, error_key=DUPLICATE_ERROR_KEY).duplicate
    assert not CallResult(False, 409, error_key="other").duplicate
    assert CallResult(False, 400, message="x used by installed apps").in_use
    assert not CallResult(False, 500, message="x used by installed apps").in_use
    assert CallResult(False, 404).not_found


# --- static boundaries (ast, no import side effects) ---------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_static_import_boundaries() -> None:
    modules = {path.stem: _imports(path) for path in APP_DIR.glob("*.py")}
    importers = {name for name, imports in modules.items() if "app.supervisor" in imports}
    assert importers <= {"registration", "sync"}
    assert "registration" in importers and "sync" in importers
    assert "app.supervisor" not in modules["cli"]
    assert "app.registration" not in modules["cli"]


def test_token_names_only_in_the_client() -> None:
    owners = set()
    for path in APP_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "SUPERVISOR_TOKEN" in node.value or "HASSIO_TOKEN" in node.value:
                    owners.add(path.name)
    assert owners == {"supervisor.py"}
