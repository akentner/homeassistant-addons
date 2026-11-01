from __future__ import annotations

import json
import logging
import threading

import pytest

from app.origins import OriginStore

TID = "0123456789ab"
TID2 = "ba9876543210"


def test_unknown_is_gui_and_persists(tmp_path):
    path = tmp_path / "origins.json"
    store = OriginStore(path)
    assert store.get_user("a") == "gui"
    assert store.get_acl("a", "t") == "gui"
    assert store.get_token("a", TID) == "gui"
    store.set_user("a", "options")
    assert OriginStore(path).get_user("a") == "options"


def test_invalid_origin_and_token_id_rejected(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    with pytest.raises(ValueError):
        store.set_user("a", "evil")
    with pytest.raises(ValueError):
        store.set_acl("a", "t", "")
    with pytest.raises(ValueError):
        store.set_token("a", "nothex", "gui")
    with pytest.raises(ValueError):
        store.stash_acl("a", [{"topic": "t", "permission": "rw", "origin": "bad"}])


def test_document_layout(tmp_path):
    path = tmp_path / "o.json"
    store = OriginStore(path)
    store.set_user("a", "iac")
    doc = json.loads(path.read_text())
    assert doc["schema"] == 1
    assert set(doc) == {"schema", "users", "acls", "tokens", "acl_stash"}


def test_file_mode_0600(tmp_path):
    path = tmp_path / "o.json"
    OriginStore(path).set_user("a", "gui")
    assert path.stat().st_mode & 0o777 == 0o600
    assert [p.name for p in tmp_path.iterdir()] == ["o.json"]


def test_drop_user_cascades(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    store.set_user("a", "options")
    store.set_acl("a", "t", "options")
    store.set_token("a", TID, "gui")
    store.stash_acl("a", [{"topic": "t", "permission": "rw", "origin": "gui"}])
    store.set_user("b", "gui")
    store.drop_user("a")
    snap = store.snapshot()
    assert "a" not in snap["users"] and "a" not in snap["acls"]
    assert "a" not in snap["tokens"] and "a" not in snap["acl_stash"]
    assert snap["users"]["b"] == "gui"


def test_clear_acls_only_rules(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    store.set_user("a", "options")
    store.set_acl("a", "t", "options")
    store.clear_acls()
    assert store.get_acl("a", "t") == "gui"
    assert store.get_user("a") == "options"
    store.clear_all()
    assert store.get_user("a") == "gui"


def test_drop_acl_and_token(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    store.set_acl("a", "t", "iac")
    store.set_token("a", TID, "iac")
    store.drop_acl("a", "t")
    store.drop_token("a", TID)
    snap = store.snapshot()
    assert snap["acls"] == {} and snap["tokens"] == {}


def test_stash_pops_once(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    rules = [{"topic": "t", "permission": "ro", "origin": "options"}]
    store.stash_acl("a", rules)
    assert store.pop_acl_stash("a") == rules
    assert store.pop_acl_stash("a") == []


def test_prune_counts_removed(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    store.set_user("a", "gui")
    store.set_user("gone", "gui")
    store.set_acl("a", "t1", "gui")
    store.set_acl("a", "t2", "gui")
    store.set_token("a", TID, "gui")
    store.set_token("a", TID2, "gui")
    removed = store.prune({"a"}, {("a", "t1")}, {("a", TID)})
    assert removed == 3
    snap = store.snapshot()
    assert snap["users"] == {"a": "gui"}
    assert snap["acls"] == {"a": {"t1": "gui"}}
    assert snap["tokens"] == {"a": {TID: "gui"}}


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"schema": 1, "users": []}', '{"schema": 2}'])
def test_corrupt_file_renamed_and_empty(tmp_path, caplog, content):
    path = tmp_path / "origins.json"
    path.write_text(content)
    path.with_name("origins.json.corrupt").write_text("old")
    with caplog.at_level(logging.WARNING):
        store = OriginStore(path)
    assert store.get_user("a") == "gui"
    assert (tmp_path / "origins.json.corrupt").read_text() == content
    assert not path.exists()
    assert content not in caplog.text
    store.set_user("a", "iac")
    assert OriginStore(path).get_user("a") == "iac"


def test_unknown_origin_in_file_is_corrupt(tmp_path):
    path = tmp_path / "origins.json"
    path.write_text(json.dumps({"schema": 1, "users": {"a": "root"}, "acls": {}, "tokens": {}, "acl_stash": {}}))
    assert OriginStore(path).get_user("a") == "gui"
    assert (tmp_path / "origins.json.corrupt").exists()


def test_snapshot_is_deep_copy(tmp_path):
    store = OriginStore(tmp_path / "o.json")
    store.set_acl("a", "t", "gui")
    snap = store.snapshot()
    snap["acls"]["a"]["t"] = "iac"
    assert store.get_acl("a", "t") == "gui"


def test_threads_lose_no_update(tmp_path):
    path = tmp_path / "o.json"
    store = OriginStore(path)
    threads = [
        threading.Thread(target=lambda i=i: [store.set_user(f"u{i}-{n}", "options") for n in range(10)])
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(OriginStore(path).snapshot()["users"]) == 80
