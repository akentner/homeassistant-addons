"""Tests for the bearer token verifiers: option token validation (D-07, D-11), the no-token refusal (D-08) and the
generated token with its 0600 SHA-256 file, once-only plaintext and rotation (D-06).

Every token value is generated at test time; hash files live only under pytest's tmp_path."""

from __future__ import annotations

import hashlib
import http.server
import os
import re
import secrets
import stat
import threading
from pathlib import Path
from typing import Any, Iterator

import pytest

from app.web.skeleton import Router
from app.web.skeleton import tokens as tokens_module
from app.web.skeleton.api import make_api_server
from app.web.skeleton.tokens import OPTION_TOKEN_MIN_LENGTH, GeneratedToken, OptionToken
from test_skeleton_server import Client


def _valid_option_token() -> str:
    return "opt-" + secrets.token_hex(OPTION_TOKEN_MIN_LENGTH)


def _printable(length: int) -> str:
    """A printable ASCII value of exactly `length` characters (URL-safe alphabet, never a space)."""
    return secrets.token_urlsafe(length)[:length]


# --- OptionToken (D-07, D-11) ---


def test_option_token_rejects_missing_values() -> None:
    for value in (None, "", 42):
        with pytest.raises(ValueError):
            OptionToken(value)  # type: ignore[arg-type]


def test_option_token_rejects_non_printable_or_non_ascii() -> None:
    base = _valid_option_token()
    for value in (base + " x", base + "\tx", base + "ä", base + "\nx", " " + base, base + " "):
        with pytest.raises(ValueError):
            OptionToken(value)


def test_option_token_minimum_length_boundary() -> None:
    # D-11: the minimum the user decided on 2026-11-17; also binds ntfy Phase 25
    assert OPTION_TOKEN_MIN_LENGTH == 16
    short = _printable(15)
    assert len(short) == 15
    with pytest.raises(ValueError):
        OptionToken(short)
    exact = _printable(16)
    assert len(exact) == 16
    assert OptionToken(exact).verify(exact) is True


def test_option_token_messages_never_contain_the_value() -> None:
    base = _valid_option_token()
    rejected = [_printable(15), _printable(8), base + " x", base + "\tx", base + "ä", base + "\nx"]
    for value in rejected:
        assert len(value) >= 3
        with pytest.raises(ValueError) as info:
            OptionToken(value)
        message = str(info.value)
        assert value not in message


def test_option_token_verify() -> None:
    value = _valid_option_token()
    token = OptionToken(value)
    assert token.verify(value) is True
    assert token.verify("wrong-" + secrets.token_hex(OPTION_TOKEN_MIN_LENGTH)) is False
    assert token.verify(value[:-1]) is False
    assert token.verify(value + "ä") is False
    assert token.verify(None) is False  # type: ignore[arg-type]
    assert token.verify(value.encode("ascii")) is False  # type: ignore[arg-type]


def test_option_token_repr_and_state_hide_the_value() -> None:
    value = _valid_option_token()
    token = OptionToken(value)
    assert value not in repr(token)
    assert not hasattr(token, "__dict__")
    assert OptionToken.__slots__ == ("_digest",)
    assert isinstance(token._digest, bytes)
    assert len(token._digest) == 32


# --- No token, no API (D-08) ---


def test_no_token_never_binds(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never_bind(self: http.server.HTTPServer) -> None:
        pytest.fail("a socket was bound without a usable token")

    # Every server class of the skeleton inherits HTTPServer.server_bind, so this covers any subclass
    monkeypatch.setattr(http.server.HTTPServer, "server_bind", _never_bind)
    router = Router()
    router.add("GET", "/api/ping", lambda req: {"ok": True})
    for verifier in (None, object()):
        with pytest.raises(ValueError):
            make_api_server(router, 0, verifier, bind="127.0.0.1")  # type: ignore[arg-type]


# --- GeneratedToken (D-06) ---

HASH_LINE = re.compile(r"sha256 [0-9a-f]{64}\n")
URLSAFE_43 = re.compile(r"[A-Za-z0-9_-]{43}")


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _hash_line(plaintext: str) -> str:
    return f"sha256 {hashlib.sha256(plaintext.encode('ascii')).hexdigest()}\n"


@pytest.fixture
def no_umask() -> Iterator[None]:
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


def test_first_load_creates_a_0600_hash_file(tmp_path: Path, no_umask: None) -> None:
    path = tmp_path / "api-token"
    token = GeneratedToken.load_or_create(path)
    plaintext = token.take_plaintext()
    assert plaintext is not None
    assert _mode(path) == 0o600
    content = path.read_text(encoding="ascii")
    assert HASH_LINE.fullmatch(content)
    assert content == _hash_line(plaintext)
    assert token.path == path


def test_plaintext_is_offered_exactly_once(tmp_path: Path) -> None:
    token = GeneratedToken.load_or_create(tmp_path / "api-token")
    plaintext = token.take_plaintext()
    assert plaintext is not None
    assert URLSAFE_43.fullmatch(plaintext)
    assert token.take_plaintext() is None
    assert token.verify(plaintext) is True


def test_reload_offers_no_plaintext_and_verifies(tmp_path: Path) -> None:
    path = tmp_path / "api-token"
    original = GeneratedToken.load_or_create(path).take_plaintext()
    assert original is not None
    reloaded = GeneratedToken.load_or_create(path)
    assert reloaded.take_plaintext() is None
    assert reloaded.verify(original) is True
    assert reloaded.verify("wrong") is False
    assert reloaded.verify(original + "ä") is False
    assert reloaded.verify(None) is False  # type: ignore[arg-type]


def test_loose_permissions_are_tightened(tmp_path: Path) -> None:
    path = tmp_path / "api-token"
    original = GeneratedToken.load_or_create(path).take_plaintext()
    os.chmod(path, 0o644)
    reloaded = GeneratedToken.load_or_create(path)
    assert _mode(path) == 0o600
    assert reloaded.verify(original) is True  # type: ignore[arg-type]


def test_rotate_replaces_the_token(tmp_path: Path, no_umask: None) -> None:
    path = tmp_path / "api-token"
    token = GeneratedToken.load_or_create(path)
    first = token.take_plaintext()
    assert first is not None
    # A pending first-start plaintext is cleared by a rotation
    pending = GeneratedToken.load_or_create(tmp_path / "pending-token")
    new_pending = pending.rotate()
    assert pending.take_plaintext() is None
    assert pending.verify(new_pending) is True

    new = token.rotate()
    assert URLSAFE_43.fullmatch(new)
    assert new != first
    assert token.verify(first) is False
    assert token.verify(new) is True
    assert path.read_text(encoding="ascii") == _hash_line(new)
    assert _mode(path) == 0o600
    assert token.take_plaintext() is None
    assert sorted(p.name for p in tmp_path.iterdir()) == ["api-token", "pending-token"]


def _malformed_contents() -> list[bytes]:
    return [
        b"",
        b"sha256 xyz\n",
        b"sha256 " + b"a" * 63 + b"\n",
        b"sha256 " + b"A" * 64 + b"\n",
        b"sha256 " + b"a" * 64 + b"\nsha256 " + b"b" * 64 + b"\n",
        b"md5 " + b"a" * 64 + b"\n",
        secrets.token_urlsafe(32).encode("ascii") + b"\n",  # looks like a stored plaintext token (43 characters)
        "sha256 ä\n".encode("utf-8"),
    ]


def test_malformed_files_raise_and_stay_untouched(tmp_path: Path) -> None:
    path = tmp_path / "api-token"
    for content in _malformed_contents():
        path.write_bytes(content)
        os.chmod(path, 0o600)
        with pytest.raises(ValueError) as info:
            GeneratedToken.load_or_create(path)
        message = str(info.value)
        for piece in content.decode("utf-8").split():
            assert piece not in message, content
        # Untouched and not regenerated: same bytes, no new token file, no temporary file
        assert path.read_bytes() == content
        assert [p.name for p in tmp_path.iterdir()] == ["api-token"]


def test_failed_replace_keeps_the_old_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "api-token"
    token = GeneratedToken.load_or_create(path)
    old = token.take_plaintext()
    before = path.read_bytes()

    def _fail(src: Any, dst: Any) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(tokens_module.os, "replace", _fail)
    with pytest.raises(OSError):
        token.rotate()
    assert token.verify(old) is True  # type: ignore[arg-type]
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["api-token"]


def _fail_directory_sync(monkeypatch: pytest.MonkeyPatch, where: str) -> None:
    """Make the directory fsync after os.replace fail, either at os.open of the directory or at os.fsync."""
    real_open, real_fsync = os.open, os.fsync

    def _open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if where == "open" and os.path.isdir(path):
            raise OSError("directory open failed")
        return real_open(path, flags, *args, **kwargs)

    def _fsync(fd: int) -> None:
        if where == "fsync" and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("directory fsync failed")
        real_fsync(fd)

    monkeypatch.setattr(tokens_module.os, "open", _open)
    monkeypatch.setattr(tokens_module.os, "fsync", _fsync)


@pytest.mark.parametrize("where", ["open", "fsync"])
def test_failed_directory_sync_never_locks_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str) -> None:
    # WR-01: once os.replace has put a hash on disk, its plaintext must reach the caller and memory must match the disk
    path = tmp_path / "api-token"
    _fail_directory_sync(monkeypatch, where)
    token = GeneratedToken.load_or_create(path)
    first = token.take_plaintext()
    assert first is not None
    assert GeneratedToken.load_or_create(path).verify(first) is True

    new = token.rotate()
    assert token.verify(new) is True
    assert token.verify(first) is False
    reloaded = GeneratedToken.load_or_create(path)
    assert reloaded.verify(new) is True
    assert reloaded.verify(first) is False
    assert [p.name for p in tmp_path.iterdir()] == ["api-token"]


def test_concurrent_verify_during_rotate(tmp_path: Path) -> None:
    token = GeneratedToken.load_or_create(tmp_path / "api-token")
    first = token.take_plaintext()
    stop = threading.Event()
    errors: list[BaseException] = []
    results: list[Any] = []
    candidates = [first, "wrong-" + secrets.token_hex(8), "ä"]

    def _verify_loop() -> None:
        try:
            while not stop.is_set():
                for candidate in candidates:
                    results.append(token.verify(candidate))  # type: ignore[arg-type]
        except BaseException as exc:  # noqa: BLE001 - collected and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=_verify_loop) for _ in range(8)]
    for thread in threads:
        thread.start()
    rotated = []
    try:
        for _ in range(20):
            rotated.append(token.rotate())
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=10)
    assert errors == []
    assert results
    assert all(type(result) is bool for result in results)
    assert token.verify(rotated[-1]) is True
    for earlier in [first, *rotated[:-1]]:
        assert token.verify(earlier) is False  # type: ignore[arg-type]


def test_take_plaintext_from_many_threads(tmp_path: Path) -> None:
    token = GeneratedToken.load_or_create(tmp_path / "api-token")
    barrier = threading.Barrier(8)
    results: list[str | None] = []
    lock = threading.Lock()

    def _take() -> None:
        barrier.wait()
        value = token.take_plaintext()
        with lock:
            results.append(value)

    threads = [threading.Thread(target=_take) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(results) == 8
    assert len([value for value in results if value is not None]) == 1


def test_repr_hides_secrets(tmp_path: Path) -> None:
    path = tmp_path / "api-token"
    token = GeneratedToken.load_or_create(path)
    plaintext = token.take_plaintext()
    digest = hashlib.sha256(plaintext.encode("ascii")).hexdigest()  # type: ignore[union-attr]
    text = repr(token)
    assert str(path) in text
    assert plaintext not in text  # type: ignore[operator]
    assert digest not in text


def test_generated_token_on_a_running_server(tmp_path: Path) -> None:
    token = GeneratedToken.load_or_create(tmp_path / "api-token")
    first = token.take_plaintext()
    router = Router()
    router.add("GET", "/api/ping", lambda req: {"ok": True})
    httpd = make_api_server(router, 0, token, bind="127.0.0.1")
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        client = Client(httpd.server_address[1])
        assert client.call("GET", "/api/ping", {"Authorization": f"Bearer {first}"})[0] == 200
        new = token.rotate()
        assert client.call("GET", "/api/ping", {"Authorization": f"Bearer {first}"})[0] == 401
        assert client.call("GET", "/api/ping", {"Authorization": f"Bearer {new}"})[0] == 200
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
