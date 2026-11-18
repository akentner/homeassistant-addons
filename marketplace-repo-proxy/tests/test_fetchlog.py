"""Access-log sink receiver (app.fetchlog, D-20 to D-22): datagram -> hash map -> last-fetch file and log line."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from app import fetchlog, lastfetch
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


# --- shared helpers for the behaviour tests ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_hash_in_log(caplog):
    """No log record of any test in this file may contain a 32-hex run (T-03-09)."""
    yield
    assert not HASH_RUN.search(caplog.text)


class Clock:
    def __init__(self, now: float = 1_800_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def writes(monkeypatch):
    """Count last-fetch writes (the real write still happens)."""
    calls = []
    original = fetchlog.write_last_fetch

    def spy(p, records):
        records = list(records)
        calls.append(records)
        return original(p, records)

    monkeypatch.setattr(fetchlog, "write_last_fetch", spy)
    return calls


def fetch_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("fetch:")]


def write_doc(p: Paths, doc) -> str:
    text = doc if isinstance(doc, str) else json.dumps(doc)
    last_fetch_path(p).write_text(text, encoding="utf-8")
    return text


# --- parse_datagram ---------------------------------------------------------------------------------------------


def test_parse_datagram_accepts_the_strict_format():
    hash_ = secrets.token_hex(16)
    assert fetchlog.parse_datagram(f"example-org private-addons {hash_}".encode()) == (
        "example-org",
        "private-addons",
        hash_,
    )


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"a" * 257,
        "exämple private-addons {h}".encode("utf-8"),
        b"example-org  private-addons {h}",
        b"example-org {h}",
        b"example-org private-addons {H}",
        b"example-org private-addons {h}\n",
        b"example-org private-addons {h31}",
        b"example-org/private-addons {h}",
        b"example-org private-addons {h} extra",
    ],
    ids=["empty", "too-long", "non-ascii", "two-spaces", "missing-field", "upper-hash", "newline", "short-hash",
         "slash", "extra-field"],
)
def test_parse_datagram_rejects_everything_else(data):
    hash_ = secrets.token_hex(16)
    data = data.replace(b"{h31}", hash_[:31].encode()).replace(b"{h}", hash_.encode())
    data = data.replace(b"{H}", hash_.upper().encode()).replace("{h}".encode("utf-8"), hash_.encode())
    assert fetchlog.parse_datagram(data) is None


def test_parse_datagram_limit_is_256_bytes():
    hash_ = secrets.token_hex(16)
    owner = "o" * (256 - len(" r ") - 32)
    assert fetchlog.parse_datagram(f"{owner} r {hash_}".encode()) is not None
    assert fetchlog.parse_datagram(f"{owner}o r {hash_}".encode()) is None


# --- AccessMap --------------------------------------------------------------------------------------------------


def test_access_map_lookup_rules(paths, log):
    store = AccessStore(paths, log)
    alice = store.add(REPO, "alice")["hash"]
    other = store.add("example-org/other-addons", "bob")["hash"]
    access_map = AccessMap(paths, log)
    assert access_map.lookup("example-org", "private-addons", alice) == (REPO, "alice")
    assert access_map.lookup("Example-Org", "PRIVATE-addons", alice) == (REPO, "alice")
    assert access_map.lookup("example-org", "private-addons", other) is None  # hash of another repository
    assert access_map.lookup("example-org", "private-addons", secrets.token_hex(16)) is None
    assert access_map.pairs() == {(REPO, "alice"), ("example-org/other-addons", "bob")}


def test_access_map_rebuilds_only_on_signature_change(paths, log, monkeypatch):
    store = AccessStore(paths, log)
    alice = store.add(REPO, "alice")["hash"]
    reads = []
    original = fetchlog.read_entries_safe

    def spy(s):
        reads.append(1)
        return original(s)

    monkeypatch.setattr(fetchlog, "read_entries_safe", spy)
    access_map = AccessMap(paths, log)
    for _ in range(3):
        assert access_map.lookup("example-org", "private-addons", alice) == (REPO, "alice")
    access_map.pairs()
    assert len(reads) == 1
    bob = store.add(REPO, "bob")["hash"]
    assert access_map.lookup("example-org", "private-addons", bob) == (REPO, "bob")
    assert access_map.lookup("example-org", "private-addons", alice) == (REPO, "alice")
    assert len(reads) == 2


def test_access_map_missing_or_empty_file(paths, log):
    access_map = AccessMap(paths, log)
    assert access_map.lookup("example-org", "private-addons", secrets.token_hex(16)) is None
    assert access_map.pairs() == set()
    paths.access_file.write_text('{"schema": 1, "entries": []}', encoding="utf-8")
    assert access_map.pairs() == set()


def test_access_map_invalid_file_is_unavailable_and_not_renamed(paths, log, caplog):
    store = AccessStore(paths, log)
    alice = store.add(REPO, "alice")["hash"]
    access_map = AccessMap(paths, log)
    assert access_map.lookup("example-org", "private-addons", alice) is not None
    paths.access_file.write_text("{broken", encoding="utf-8")
    for _ in range(3):
        assert access_map.lookup("example-org", "private-addons", alice) is None
        assert access_map.pairs() is None
    assert paths.access_file.read_text(encoding="utf-8") == "{broken"
    assert not list(paths.data_dir.glob("*.corrupt"))
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1 and "unavailable" in errors[0].getMessage()


def test_access_map_skips_invalid_entries(paths, log):
    good = secrets.token_hex(16)
    doc = {
        "schema": 1,
        "entries": [
            {"repository": REPO, "user": "alice", "hash": good},
            {"repository": REPO, "user": "bad user", "hash": secrets.token_hex(16)},
            {"repository": "not-a-repo", "user": "bob", "hash": secrets.token_hex(16)},
            {"repository": REPO, "user": "carol", "hash": "short"},
            {"repository": 5, "user": "dave", "hash": secrets.token_hex(16)},
        ],
    }
    paths.access_file.write_text(json.dumps(doc), encoding="utf-8")
    access_map = AccessMap(paths, log)
    assert access_map.lookup("example-org", "private-addons", good) == (REPO, "alice")
    assert access_map.pairs() == {(REPO, "alice"), (REPO, "carol")}


# --- FetchRecorder ----------------------------------------------------------------------------------------------


def test_recorder_throttles_per_hash(paths, log, caplog, writes):
    clock = Clock()
    recorder = FetchRecorder(paths, log, clock=clock)
    hash_ = secrets.token_hex(16)
    pairs = {(REPO, "alice")}
    assert recorder.record(REPO, "alice", hash_, pairs=pairs) is True
    clock.now += 30
    assert recorder.record(REPO, "alice", hash_, pairs=pairs) is False
    assert fetch_lines(caplog) == [f"fetch: alice → {REPO}"]
    assert len(writes) == 1
    clock.now += 31
    assert recorder.record(REPO, "alice", hash_, pairs=pairs) is True
    assert fetch_lines(caplog) == [f"fetch: alice → {REPO}"] * 2
    assert len(writes) == 2


def test_recorder_new_hash_logs_at_once(paths, log, caplog, writes):
    clock = Clock()
    recorder = FetchRecorder(paths, log, clock=clock)
    assert recorder.record(REPO, "alice", secrets.token_hex(16)) is True
    clock.now += 5
    assert recorder.record(REPO, "alice", secrets.token_hex(16)) is True  # rotated: new hash, same label
    assert len(fetch_lines(caplog)) == 2 and len(writes) == 2


def test_recorder_tick_writes_dirty_records_after_the_interval(paths, log, writes):
    clock = Clock()
    recorder = FetchRecorder(paths, log, clock=clock)
    hash_ = secrets.token_hex(16)
    recorder.record(REPO, "alice", hash_)
    first = json.loads(last_fetch_path(paths).read_text(encoding="utf-8"))["entries"][0]["last_fetch"]
    clock.now += 10
    recorder.record(REPO, "alice", hash_)
    recorder.tick(None)
    assert len(writes) == 1
    clock.now += 50
    recorder.tick(None)
    assert len(writes) == 2
    second = json.loads(last_fetch_path(paths).read_text(encoding="utf-8"))["entries"][0]["last_fetch"]
    assert second > first
    clock.now += 120
    recorder.tick(None)  # nothing dirty: no write
    assert len(writes) == 2


def test_recorder_flush_writes_only_dirty_records(paths, log, writes):
    clock = Clock()
    recorder = FetchRecorder(paths, log, clock=clock)
    recorder.flush(None)
    assert writes == [] and not last_fetch_path(paths).exists()
    hash_ = secrets.token_hex(16)
    recorder.record(REPO, "alice", hash_)
    clock.now += 1
    recorder.record(REPO, "alice", hash_)
    recorder.flush(None)
    assert len(writes) == 2
    recorder.flush(None)
    assert len(writes) == 2


def test_recorder_prunes_removed_pairs_unless_unavailable(paths, log):
    clock = Clock()
    recorder = FetchRecorder(paths, log, clock=clock)
    recorder.record(REPO, "alice", secrets.token_hex(16))
    recorder.record(REPO, "bob", secrets.token_hex(16))
    clock.now += 1
    recorder.record(REPO, "carol", secrets.token_hex(16), pairs=None)
    users = [e["user"] for e in json.loads(last_fetch_path(paths).read_text(encoding="utf-8"))["entries"]]
    assert users == ["alice", "bob", "carol"]
    recorder.record(REPO, "carol", secrets.token_hex(16), pairs={(REPO, "carol"), (REPO, "alice")})
    users = [e["user"] for e in json.loads(last_fetch_path(paths).read_text(encoding="utf-8"))["entries"]]
    assert users == ["alice", "carol"]


def test_recorder_write_failure_is_logged_without_content(paths, log, caplog, monkeypatch):
    def boom(p, records):
        raise PermissionError(13, "denied")

    monkeypatch.setattr(fetchlog, "write_last_fetch", boom)
    recorder = FetchRecorder(paths, log, clock=Clock())
    assert recorder.record(REPO, "alice", secrets.token_hex(16)) is True
    assert "last-fetch write failed (PermissionError)" in caplog.text


# --- last-fetch file (D-21) -------------------------------------------------------------------------------------


def test_last_fetch_file_layout_is_fixed_and_sorted(paths, log):
    clock = Clock()
    recorder = FetchRecorder(paths, log, clock=clock)
    for repository, user in [("example-org/zeta", "bob"), (REPO, "carol"), ("Example-Org/Alpha", "zed"), (REPO, "al")]:
        recorder.record(repository, user, secrets.token_hex(16))
    target = last_fetch_path(paths)
    assert target == paths.data_dir / "last-fetch.json" and lastfetch.FILE_NAME == "last-fetch.json"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    raw = target.read_text(encoding="utf-8")
    assert not HASH_RUN.search(raw)
    doc = json.loads(raw)
    assert set(doc) == {"schema", "updated", "entries"} and doc["schema"] == lastfetch.SCHEMA == 1
    assert all(set(e) == {"repository", "user", "last_fetch"} for e in doc["entries"])
    assert [(e["repository"], e["user"]) for e in doc["entries"]] == [
        ("Example-Org/Alpha", "zed"),
        (REPO, "al"),
        (REPO, "carol"),
        ("example-org/zeta", "bob"),
    ]
    assert all(e["last_fetch"] == "2027-01-15T08:00:00Z" for e in doc["entries"])


def test_recorder_resumes_from_a_valid_file(paths, log):
    write_doc(
        paths,
        {"schema": 1, "updated": "2026-01-01T00:00:00Z",
         "entries": [{"repository": REPO, "user": "alice", "last_fetch": "2026-01-01T00:00:00Z"}]},
    )
    recorder = FetchRecorder(paths, log, clock=Clock())
    assert recorder.records == {
        (REPO, "alice"): lastfetch.LastFetchRecord(REPO, "alice", "2026-01-01T00:00:00Z")
    }


@pytest.mark.parametrize(
    "doc",
    ["{broken", '{"schema": 2, "updated": "x", "entries": []}', "[]"],
    ids=["invalid-json", "newer-schema", "array"],
)
def test_bad_file_at_start_is_kept_then_replaced(paths, log, doc):
    text = write_doc(paths, doc)
    recorder = FetchRecorder(paths, log, clock=Clock())
    assert recorder.records == {}
    assert last_fetch_path(paths).read_text(encoding="utf-8") == text
    assert sorted(p.name for p in paths.data_dir.iterdir()) == ["last-fetch.json", "options.json"]
    recorder.record(REPO, "alice", secrets.token_hex(16))
    assert json.loads(last_fetch_path(paths).read_text(encoding="utf-8"))["schema"] == 1


@pytest.mark.parametrize(
    "doc",
    [
        "{broken",
        "null",
        "[]",
        {"entries": []},
        {"schema": True, "entries": []},
        {"schema": 2, "entries": [{"repository": REPO, "user": "alice", "last_fetch": "2026-01-01T00:00:00Z"}]},
        {"schema": 1, "entries": {}},
        {"schema": 1, "entries": ["x", {"repository": "bad", "user": "alice", "last_fetch": "2026-01-01T00:00:00Z"}]},
        {"schema": 1, "entries": [{"repository": REPO, "user": "bad user", "last_fetch": "2026-01-01T00:00:00Z"}]},
        {"schema": 1, "entries": [{"repository": REPO, "user": "alice", "last_fetch": "2026-01-01 00:00:00"}]},
        {"schema": 1, "entries": [{"repository": REPO, "user": "alice", "last_fetch": 5}]},
    ],
    ids=["invalid-json", "null", "array", "no-schema", "bool-schema", "newer-schema", "entries-object",
         "bad-repository", "bad-user", "bad-timestamp", "numeric-timestamp"],
)
def test_read_last_fetch_returns_empty_for_invalid_shapes(paths, doc):
    write_doc(paths, doc)
    assert lastfetch.read_last_fetch(paths) == {}


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads files regardless of mode")
def test_read_last_fetch_unreadable_file(paths):
    write_doc(paths, {"schema": 1, "entries": []})
    os.chmod(last_fetch_path(paths), 0)
    try:
        assert lastfetch.read_last_fetch(paths) == {}
    finally:
        os.chmod(last_fetch_path(paths), 0o600)


def test_write_last_fetch_creates_the_data_dir(tmp_path):
    p = Paths.under(tmp_path / "fresh")
    lastfetch.write_last_fetch(p, [lastfetch.LastFetchRecord(REPO, "alice", "2026-01-01T00:00:00Z")])
    assert json.loads(last_fetch_path(p).read_text(encoding="utf-8"))["entries"] == [
        {"repository": REPO, "user": "alice", "last_fetch": "2026-01-01T00:00:00Z"}
    ]


# --- handler: untrusted datagrams -------------------------------------------------------------------------------


def test_handler_drops_malformed_unknown_and_foreign_datagrams(paths, log, caplog, writes):
    store = AccessStore(paths, log)
    alice = store.add(REPO, "alice")["hash"]
    bob = store.add("example-org/other-addons", "bob")["hash"]
    handle = make_handler(AccessMap(paths, log), FetchRecorder(paths, log, clock=Clock()))
    for data in [
        b"",
        f"example-org private-addons {secrets.token_hex(16)}".encode(),
        f"example-org private-addons {bob}".encode(),
        f"example-org private-addons {alice.upper()}".encode(),
        f"example-org private-addons {alice} ".encode(),
    ]:
        handle(data)
    assert writes == [] and fetch_lines(caplog) == [] and not last_fetch_path(paths).exists()
    handle(f"EXAMPLE-ORG Private-Addons {alice}".encode())
    assert fetch_lines(caplog) == [f"fetch: alice → {REPO}"]  # stored repository, not the datagram's case


def test_handler_with_missing_access_file_writes_nothing(paths, log, caplog, writes):
    handle = make_handler(AccessMap(paths, log), FetchRecorder(paths, log, clock=Clock()))
    handle(f"example-org private-addons {secrets.token_hex(16)}".encode())
    assert writes == [] and fetch_lines(caplog) == []


def test_serve_forever_survives_handler_errors(log, caplog, sock_dir):
    sock = bind_socket(sock_dir / "s" / "fetch.sock", change_owner=False)
    stop = threading.Event()
    seen, ticks = [], []

    def handle(data):
        seen.append(data)
        raise RuntimeError(data.decode())

    thread = threading.Thread(target=serve_forever, args=(sock, stop, handle, lambda: ticks.append(1)), daemon=True)
    thread.start()
    try:
        sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        for _ in range(2):
            sender.sendto(b"x" * 300, str(sock_dir / "s" / "fetch.sock"))
        sender.close()
        assert wait_for(lambda: len(seen) == 2)
    finally:
        stop.set()
        thread.join(timeout=5)
        sock.close()
    assert all(len(d) == fetchlog.MAX_DATAGRAM + 1 for d in seen)  # truncated, then rejected by parse_datagram
    assert len(ticks) >= 2
    assert "fetch record failed (RuntimeError)" in caplog.text
    assert "xxxx" not in caplog.text


# --- bind_socket ------------------------------------------------------------------------------------------------


def test_bind_socket_modes_and_stale_socket(sock_dir):
    path = sock_dir / "s" / "fetch.sock"
    first = bind_socket(path, change_owner=False)
    first.close()
    assert path.exists()  # stale socket left behind
    sock = bind_socket(path, change_owner=False)
    try:
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o710
        assert stat.S_ISSOCK(path.stat().st_mode) and stat.S_IMODE(path.stat().st_mode) == 0o620
        assert sock.gettimeout() == 1.0
        sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sender.sendto(b"ping", str(path))
        sender.close()
        assert sock.recv(64) == b"ping"
    finally:
        sock.close()


def test_bind_socket_changes_owner_to_root_and_the_group(sock_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(fetchlog.os, "chown", lambda p, uid, gid: calls.append((Path(p), uid, gid)))
    looked_up = []

    def gid_lookup(group):
        looked_up.append(group)
        return 4242

    path = sock_dir / "s" / "fetch.sock"
    sock = bind_socket(path, gid_lookup=gid_lookup, change_owner=True)
    sock.close()
    assert looked_up == ["lighttpd"]
    assert calls == [(path.parent, 0, 4242), (path, 0, 4242)]
    assert fetchlog.SOCKET_DIR == Path("/run/mrp-fetch") and fetchlog.SOCKET_GROUP == "lighttpd"


# --- main -------------------------------------------------------------------------------------------------------


@pytest.fixture
def quiet_setup(monkeypatch):
    """main() would replace the root handlers (and with them caplog's); keep the test's logging intact."""
    monkeypatch.setattr(fetchlog, "setup_logging", lambda level: None)
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


def test_main_stops_on_sigterm_and_removes_the_socket(paths, caplog, sock_dir, quiet_setup):
    caplog.set_level(logging.INFO)
    sock_path = sock_dir / "s" / "fetch.sock"
    timer = threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        assert fetchlog.main([], paths=paths, socket_path=sock_path) == 0
    finally:
        timer.cancel()
    assert not sock_path.exists()
    assert "fetch log listening" in caplog.text


def test_main_with_unreadable_options_returns_1(paths, sock_dir, quiet_setup):
    paths.options_file.write_text("{not json", encoding="utf-8")
    assert fetchlog.main([], paths=paths, socket_path=sock_dir / "s" / "fetch.sock") == 1
    assert not (sock_dir / "s").exists()
