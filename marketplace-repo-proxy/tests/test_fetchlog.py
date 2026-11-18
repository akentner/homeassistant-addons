"""Access-log sink receiver (app.fetchlog, D-20 to D-22): datagram -> hash map -> last-fetch file and log line."""

from __future__ import annotations

import json
import logging
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from app import fetchlog
from app.access import AccessStore
from app.fetchlog import AccessMap, FetchRecorder, bind_socket, make_handler, serve_forever
from app.lastfetch import last_fetch_path
from app.paths import Paths

REPO = "example-org/private-addons"
ADDON_DIR = Path(__file__).resolve().parent.parent
FETCHSINK = ADDON_DIR / "app" / "fetchsink.py"
HASH_RUN = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    p.options_file.write_text(json.dumps({"repositories": [{"repository": REPO}]}), encoding="utf-8")
    return p


@pytest.fixture
def log(caplog):
    caplog.set_level(logging.DEBUG)
    return logging.getLogger("test.fetchlog")


@pytest.fixture
def sock_dir():
    """Short directory for AF_UNIX paths (107-byte limit), never below tmp_path."""
    directory = Path(tempfile.mkdtemp(prefix="mrpf"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_tracer_upload_pack_line_becomes_one_record_and_one_log_line(paths, log, caplog, sock_dir):
    hash_ = AccessStore(paths, log).add(REPO, "alice", source="cli")["hash"]
    sock_path = sock_dir / "s" / "fetch.sock"
    sock = bind_socket(sock_path, change_owner=False)
    access_map = AccessMap(paths, log)
    recorder = FetchRecorder(paths, log)
    stop = threading.Event()
    thread = threading.Thread(
        target=serve_forever,
        args=(sock, stop, make_handler(access_map, recorder), lambda: recorder.tick(access_map.pairs())),
        daemon=True,
    )
    thread.start()
    try:
        line = f"POST /repo/{REPO}/{hash_}/git-upload-pack 200\n".encode("ascii")
        result = subprocess.run(
            [sys.executable, "-I", str(FETCHSINK), str(sock_path)], input=line, capture_output=True, timeout=30
        )
        assert result.returncode == 0
        assert result.stdout == b"" and result.stderr == b""
        target = last_fetch_path(paths)
        assert wait_for(target.exists)
    finally:
        stop.set()
        thread.join(timeout=5)
        sock.close()

    assert target.name == "last-fetch.json" and target.parent == paths.data_dir
    raw = target.read_text(encoding="utf-8")
    assert not HASH_RUN.search(raw)
    doc = json.loads(raw)
    assert set(doc) == {"schema", "updated", "entries"}
    assert doc["schema"] == 1 and doc["updated"].endswith("Z")
    assert len(doc["entries"]) == 1
    entry = doc["entries"][0]
    assert set(entry) == {"repository", "user", "last_fetch"}
    assert entry["repository"] == REPO and entry["user"] == "alice"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["last_fetch"])
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert f"fetch: alice → {REPO}" in caplog.text
    assert not HASH_RUN.search(caplog.text)
    assert fetchlog.SOCKET_PATH == Path("/run/mrp-fetch/fetch.sock")
