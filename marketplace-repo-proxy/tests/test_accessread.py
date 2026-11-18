"""Non-destructive locked read of access.json (app.accessread, D-09, D-10, WR-04): never renames, never raises vaguely."""

from __future__ import annotations

import contextlib
import json
import logging
import os

import pytest

from app.access import AccessStore
from app.accessread import AccessUnavailable, file_signature, read_entries_safe
from app.paths import Paths

REPO = "example-org/private-addons"


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    return p


@pytest.fixture
def store(paths, caplog):
    caplog.set_level(logging.DEBUG)
    return AccessStore(paths, logging.getLogger("test.accessread"))


def assert_untouched(paths: Paths, content: str) -> None:
    assert paths.access_file.read_text(encoding="utf-8") == content
    assert not paths.access_file.with_name("access.json.corrupt").exists()
    assert sorted(p.name for p in paths.data_dir.iterdir()) == ["access.json"]


def test_missing_file_gives_empty_list(store):
    assert read_entries_safe(store) == []


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "",
        "[]",
        '"text"',
        '{"entries": []}',
        '{"schema": true, "entries": []}',
        '{"schema": "1", "entries": []}',
        '{"schema": 1, "entries": {}}',
        '{"schema": 1, "entries": ["x"]}',
        '{"schema": 2, "entries": []}',
    ],
    ids=[
        "invalid-json",
        "empty-file",
        "array",
        "string",
        "no-schema",
        "bool-schema",
        "str-schema",
        "entries-object",
        "entry-not-object",
        "newer-schema",
    ],
)
def test_bad_file_raises_and_stays_in_place(paths, store, content):
    paths.access_file.write_text(content, encoding="utf-8")
    with pytest.raises(AccessUnavailable):
        read_entries_safe(store)
    assert_untouched(paths, content)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads files regardless of mode")
def test_unreadable_file_raises_and_stays_in_place(paths, store):
    store.add(REPO, "alice")
    content = paths.access_file.read_text(encoding="utf-8")
    os.chmod(paths.access_file, 0)
    try:
        with pytest.raises(AccessUnavailable):
            read_entries_safe(store)
    finally:
        os.chmod(paths.access_file, 0o600)
    assert_untouched(paths, content)


def test_valid_file_gives_copies(store):
    store.add(REPO, "alice")
    store.add(REPO, "bob")
    entries = read_entries_safe(store)
    assert [e["user"] for e in entries] == ["alice", "bob"]
    entries[0]["user"] = "mallory"
    entries[1]["specs"] = {"nested": True}
    entries.clear()
    assert [e["user"] for e in store.list_entries()] == ["alice", "bob"]
    assert "specs" not in store.list_entries()[1]


def test_unknown_fields_are_kept_in_the_copies(paths, store):
    paths.access_file.write_text(
        json.dumps({"schema": 1, "extra": 1, "entries": [{"repository": REPO, "user": "alice", "note": [1]}]}),
        encoding="utf-8",
    )
    assert read_entries_safe(store) == [{"repository": REPO, "user": "alice", "note": [1]}]


def test_read_holds_the_store_lock(store, monkeypatch):
    held = []
    original = AccessStore.locked

    @contextlib.contextmanager
    def spy(self):
        with original(self):
            held.append(True)
            yield
            held.append(False)

    monkeypatch.setattr(AccessStore, "locked", spy)
    read_entries_safe(store)
    assert held == [True, False]


def test_file_signature(paths, store):
    assert file_signature(paths.access_file) is None
    store.add(REPO, "alice")
    first = file_signature(paths.access_file)
    assert first is not None and len(first) == 3 and all(isinstance(v, int) for v in first)
    assert file_signature(paths.access_file) == first
    store.add(REPO, "bob")
    assert file_signature(paths.access_file) != first
