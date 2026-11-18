"""Piped access logger (app/fetchsink.py, D-20): the real file under `python3 -I` forwards, drops and never prints."""

from __future__ import annotations

import ast
import io
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ADDON_DIR = Path(__file__).resolve().parent.parent
FETCHSINK = ADDON_DIR / "app" / "fetchsink.py"
OWNER, NAME = "example-org", "private-addons"


def valid_line(hash_: str, owner: str = OWNER, name: str = NAME) -> bytes:
    return f"POST /repo/{owner}/{name}/{hash_}/git-upload-pack 200\n".encode("ascii")


@pytest.fixture
def sock_dir():
    """Short directory for AF_UNIX paths (107-byte limit), never below tmp_path."""
    directory = Path(tempfile.mkdtemp(prefix="mrpf"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def receiver(sock_dir):
    path = sock_dir / "fetch.sock"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(str(path))
    sock.settimeout(0.3)
    yield path, sock
    sock.close()


def run_sink(data: bytes, sock_path: Path | str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", str(FETCHSINK), str(sock_path)], input=data, capture_output=True, timeout=timeout
    )


def drain(sock: socket.socket) -> list[bytes]:
    received = []
    while True:
        try:
            received.append(sock.recv(4096))
        except TimeoutError:
            return received


def assert_silent(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_forwards_successful_upload_pack_post(receiver):
    path, sock = receiver
    hash_ = secrets.token_hex(16)
    result = run_sink(valid_line(hash_), path)
    assert_silent(result)
    assert drain(sock) == [f"{OWNER} {NAME} {hash_}".encode("ascii")]


def test_crlf_line_is_forwarded(receiver):
    path, sock = receiver
    hash_ = secrets.token_hex(16)
    assert_silent(run_sink(valid_line(hash_).replace(b"\n", b"\r\n"), path))
    assert drain(sock) == [f"{OWNER} {NAME} {hash_}".encode("ascii")]


H = secrets.token_hex(16)  # generated at import time, never a fixed value in the repository
DROPPED = {
    "info-refs-get": f"GET /repo/{OWNER}/{NAME}/{H}/info/refs 200".encode(),
    "post-404": f"POST /repo/{OWNER}/{NAME}/{H}/git-upload-pack 404".encode(),
    "post-403": f"POST /repo/{OWNER}/{NAME}/{H}/git-upload-pack 403".encode(),
    "not-found": b"GET /__not_found 404",
    "hash-31": f"POST /repo/{OWNER}/{NAME}/{H[:31]}/git-upload-pack 200".encode(),
    "hash-33": f"POST /repo/{OWNER}/{NAME}/{H}a/git-upload-pack 200".encode(),
    "hash-upper": f"POST /repo/{OWNER}/{NAME}/{H.upper()}/git-upload-pack 200".encode(),
    "escaped-newline": f"POST /repo/{OWNER}/{NAME}/{H}%0A/git-upload-pack 200".encode(),
    "trailing-field": f"POST /repo/{OWNER}/{NAME}/{H}/git-upload-pack 200 extra".encode(),
    "receive-pack": f"POST /repo/{OWNER}/{NAME}/{H}/git-receive-pack 200".encode(),
    "invalid-utf8": f"POST /repo/{OWNER}/{NAME}/".encode() + b"\xff\xfe" + f"/{H}/git-upload-pack 200".encode(),
    "empty": b"",
    "huge": b"POST /repo/" + b"a" * 100_000 + f"/{NAME}/{H}/git-upload-pack 200".encode(),
}


@pytest.mark.parametrize("line", list(DROPPED.values()), ids=list(DROPPED))
def test_drops_everything_else_silently(receiver, line):
    path, sock = receiver
    assert_silent(run_sink(line + b"\n", path))
    assert drain(sock) == []


def test_keeps_reading_after_bad_lines(receiver):
    path, sock = receiver
    hashes = [secrets.token_hex(16) for _ in range(3)]
    data = b"".join([b"\xff\x00garbage\n", valid_line(hashes[0]), b"GET /__not_found 404\n"])
    data += b"".join(valid_line(h) for h in hashes[1:]) + b"no newline at end"
    assert_silent(run_sink(data, path))
    assert drain(sock) == [f"{OWNER} {NAME} {h}".encode("ascii") for h in hashes]


def test_no_socket_exits_cleanly(sock_dir):
    assert_silent(run_sink(valid_line(secrets.token_hex(16)), sock_dir / "missing.sock"))


def test_no_socket_with_2000_lines_stays_fast(sock_dir):
    data = valid_line(secrets.token_hex(16)) * 2000
    start = time.monotonic()
    assert_silent(run_sink(data, sock_dir / "missing.sock", timeout=10))
    assert time.monotonic() - start < 10


def test_full_receiver_never_blocks(receiver):
    path, sock = receiver  # never read while the forwarder runs: the buffer fills up
    data = valid_line(secrets.token_hex(16)) * 2000
    start = time.monotonic()
    assert_silent(run_sink(data, path, timeout=10))
    assert time.monotonic() - start < 10


def test_refusing_path_exits_cleanly(sock_dir):
    path = sock_dir / "not-a-socket"
    path.write_text("x", encoding="ascii")
    assert_silent(run_sink(valid_line(secrets.token_hex(16)) * 10, path))


def test_no_argument_uses_default_path():
    result = subprocess.run(
        [sys.executable, "-I", str(FETCHSINK)], input=valid_line(secrets.token_hex(16)), capture_output=True, timeout=30
    )
    assert_silent(result)


def test_in_process_main_returns_zero_and_writes_nothing(receiver, monkeypatch, capsys):
    path, sock = receiver
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    sys.path.insert(0, str(FETCHSINK.parent))
    try:
        import fetchsink  # the standalone file, as lighttpd runs it
    finally:
        sys.path.remove(str(FETCHSINK.parent))
    hash_ = secrets.token_hex(16)
    assert fetchsink.main([str(path)], io.BytesIO(valid_line(hash_) + b"\xff\n")) == 0
    assert fetchsink.SOCKET_PATH == "/run/mrp-fetch/fetch.sock"
    assert drain(sock) == [f"{OWNER} {NAME} {hash_}".encode("ascii")]
    monkeypatch.undo()
    assert capsys.readouterr() == ("", "")


def test_imports_only_standard_modules_and_never_prints():
    tree = ast.parse(FETCHSINK.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported == {"__future__", "os", "re", "socket", "sys"}
    calls = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "print" not in calls
