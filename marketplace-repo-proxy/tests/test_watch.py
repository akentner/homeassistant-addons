"""access-watch service (app.watch): hand edits of /data/access.json reach the symlink tree within one poll."""

from __future__ import annotations

import json
import logging
import os
import threading
import time

import pytest

from app import watch
from app.access import AccessStore, new_hash
from app.options import RepoSpec
from app.paths import Paths
from app.watch import AccessWatcher

REPO = "example-org/private-addons"
SPEC = RepoSpec("example-org", "private-addons")
SPECS = (SPEC,)


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    return p


@pytest.fixture
def log(caplog):
    caplog.set_level(logging.DEBUG)
    return logging.getLogger("test.watch")


@pytest.fixture
def users(paths, log):
    store = AccessStore(paths, log)
    return {name: store.add(REPO, name, specs=SPECS)["hash"] for name in ("alice", "bob")}


def link(p: Paths, hash_: str):
    return p.link_path(SPEC.owner, SPEC.name, hash_)


def symlinks(p: Paths) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(p.access_root):
        found += [os.path.join(dirpath, n) for n in dirnames + filenames if os.path.islink(os.path.join(dirpath, n))]
    return found


def rewrite_without(p: Paths, user: str) -> None:
    """A hand edit: plain rewrite of the file, no AccessStore."""
    doc = json.loads(p.access_file.read_text(encoding="utf-8"))
    doc["entries"] = [e for e in doc["entries"] if e["user"] != user]
    p.access_file.write_text(json.dumps(doc, indent=4), encoding="utf-8")


def test_first_poll_reconciles_and_an_unchanged_file_does_not(paths, log, monkeypatch):
    calls = []
    original = AccessStore.reconcile

    def spy(self, specs):
        calls.append(tuple(specs))
        return original(self, specs)

    monkeypatch.setattr(AccessStore, "reconcile", spy)
    watcher = AccessWatcher(paths, SPECS, log)
    assert watcher.poll_once() is True
    assert watcher.poll_once() is False
    assert calls == [SPECS]


def test_signature_is_none_without_file_and_changes_with_content(paths, log, users):
    watcher = AccessWatcher(paths, SPECS, log)
    first = watcher.signature()
    assert first is not None and len(first) == 3
    rewrite_without(paths, "alice")
    assert watcher.signature() != first
    paths.access_file.unlink()
    assert watcher.signature() is None


def test_hand_edit_removing_an_entry_unlinks_it_at_the_next_poll(paths, log, users):
    watcher = AccessWatcher(paths, SPECS, log)
    watcher.poll_once()
    rewrite_without(paths, "alice")
    assert watcher.poll_once() is True
    assert not os.path.lexists(link(paths, users["alice"]))
    assert link(paths, users["bob"]).is_symlink()


def test_deleting_access_json_removes_every_link(paths, log, users):
    watcher = AccessWatcher(paths, SPECS, log)
    watcher.poll_once()
    paths.access_file.unlink()
    assert watcher.poll_once() is True
    assert symlinks(paths) == []


def test_corrupt_access_json_fails_closed(paths, log, users):
    watcher = AccessWatcher(paths, SPECS, log)
    watcher.poll_once()
    paths.access_file.write_text("{broken", encoding="utf-8")
    assert watcher.poll_once() is True
    assert symlinks(paths) == []
    assert paths.access_file.with_name("access.json.corrupt").exists()


def test_newer_schema_logs_once_and_keeps_links(paths, log, users, caplog):
    watcher = AccessWatcher(paths, SPECS, log)
    watcher.poll_once()
    before = sorted(symlinks(paths))
    paths.access_file.write_text(json.dumps({"schema": 2, "entries": []}), encoding="utf-8")
    caplog.clear()
    assert watcher.poll_once() is False
    assert watcher.poll_once() is False
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert sorted(symlinks(paths)) == before


def test_watcher_log_never_contains_a_full_hash(paths, log, users, caplog):
    doc = json.loads(paths.access_file.read_text(encoding="utf-8"))
    bad = new_hash().upper()
    doc["entries"].append({"repository": REPO, "user": "carol", "hash": bad, "source": "gui"})
    paths.access_file.write_text(json.dumps(doc), encoding="utf-8")
    watcher = AccessWatcher(paths, SPECS, log)
    assert watcher.poll_once() is True
    assert "example-org/private-addons/carol" in caplog.text
    for value in (users["alice"], users["bob"], bad, bad.lower()):
        assert value not in caplog.text


def test_run_forever_exits_within_one_interval_after_stop(paths, log):
    watcher = AccessWatcher(paths, SPECS, log, interval=0.2)
    stop = threading.Event()
    thread = threading.Thread(target=watcher.run_forever, args=(stop,))
    thread.start()
    time.sleep(0.3)
    assert thread.is_alive()
    started = time.monotonic()
    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert time.monotonic() - started < 0.4


def test_run_forever_picks_up_a_hand_edit(paths, log, users):
    watcher = AccessWatcher(paths, SPECS, log, interval=0.05)
    stop = threading.Event()
    thread = threading.Thread(target=watcher.run_forever, args=(stop,))
    thread.start()
    try:
        time.sleep(0.15)
        rewrite_without(paths, "alice")
        deadline = time.monotonic() + 2
        while os.path.lexists(link(paths, users["alice"])) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not os.path.lexists(link(paths, users["alice"]))
        assert link(paths, users["bob"]).is_symlink()
    finally:
        stop.set()
        thread.join(timeout=2)


def test_main_with_unreadable_options_returns_1(paths):
    paths.options_file.write_text("{not json", encoding="utf-8")
    assert watch.main([], paths=paths) == 1
