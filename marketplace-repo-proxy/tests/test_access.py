"""Access store lifecycle (app.access): add, get, list, revoke, reconcile, concurrency and bad data."""

from __future__ import annotations

import json
import logging
import os
import threading

import pytest

from app.access import (
    HASH_RE,
    RESERVED_USERS,
    AccessError,
    AccessSchemaError,
    AccessStore,
    new_hash,
)
from app.options import RepoSpec
from app.paths import Paths

REPO = "example-org/private-addons"
SPEC = RepoSpec("example-org", "private-addons")
OTHER = RepoSpec("other-org", "tools")
SPECS = (SPEC, OTHER)


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    return p


@pytest.fixture
def log(caplog):
    caplog.set_level(logging.DEBUG)
    return logging.getLogger("test.access")


@pytest.fixture
def store(paths, log):
    return AccessStore(paths, log)


def entry(repository: str, user: str, hash_: str | None = None, **extra) -> dict:
    return {
        "repository": repository,
        "user": user,
        "hash": hash_ or new_hash(),
        "created": "2026-01-01T00:00:00Z",
        "source": "gui",
        **extra,
    }


def write_doc(p: Paths, doc: dict) -> None:
    p.access_file.write_text(json.dumps(doc), encoding="utf-8")


def stored(p: Paths) -> dict:
    return json.loads(p.access_file.read_text(encoding="utf-8"))


def symlinks(p: Paths) -> set:
    found = set()
    for dirpath, dirnames, filenames in os.walk(p.access_root):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                found.add(path)
    return found


def link(p: Paths, spec: RepoSpec, hash_: str):
    return p.link_path(spec.owner, spec.name, hash_)


def test_new_hash_values_are_unique_and_32_hex():
    values = [new_hash() for _ in range(1000)]
    assert len(set(values)) == 1000
    assert all(HASH_RE.match(v) for v in values)


def test_revoke_removes_entry_and_link_while_other_user_keeps_access(store, paths):
    alice = store.add(REPO, "alice", specs=SPECS)
    bob = store.add(REPO, "bob", specs=SPECS)
    assert link(paths, SPEC, alice["hash"]).is_symlink()
    assert store.revoke(REPO, "alice", specs=SPECS) is True
    assert [e["user"] for e in stored(paths)["entries"]] == ["bob"]
    assert not os.path.lexists(link(paths, SPEC, alice["hash"]))
    assert os.readlink(link(paths, SPEC, bob["hash"])) == str(paths.repo_dir(SPEC.owner, SPEC.name))


def test_revoke_of_unknown_user_returns_false_and_writes_nothing(store, paths):
    store.add(REPO, "bob", specs=SPECS)
    before = paths.access_file.read_bytes()
    before_stat = paths.access_file.stat()
    assert store.revoke(REPO, "alice", specs=SPECS) is False
    assert paths.access_file.read_bytes() == before
    after_stat = paths.access_file.stat()
    assert (after_stat.st_ino, after_stat.st_mtime_ns) == (before_stat.st_ino, before_stat.st_mtime_ns)


def test_revoke_without_specs_still_unlinks_the_removed_hash(store, paths):
    alice = store.add(REPO, "alice", specs=SPECS)
    bob = store.add(REPO, "bob", specs=SPECS)
    assert store.revoke(REPO.upper(), "alice") is True
    assert not os.path.lexists(link(paths, SPEC, alice["hash"]))
    assert link(paths, SPEC, bob["hash"]).is_symlink()


def test_revoke_with_specs_reconciles_in_the_same_operation(store, paths):
    store.add(REPO, "alice", specs=SPECS)
    hand_added = entry(OTHER.slug, "carol")
    doc = stored(paths)
    doc["entries"].append(hand_added)
    write_doc(paths, doc)
    assert store.revoke(REPO, "alice", specs=SPECS) is True
    assert link(paths, OTHER, hand_added["hash"]).is_symlink()
    assert symlinks(paths) == {str(link(paths, OTHER, hand_added["hash"]))}


def test_revoke_of_entry_with_glob_hash_unlinks_nothing_else(store, paths):
    bob = store.add(REPO, "bob", specs=SPECS)
    doc = stored(paths)
    doc["entries"].append(entry(REPO, "mallory", "*"))
    write_doc(paths, doc)
    assert store.revoke(REPO, "mallory") is True
    assert link(paths, SPEC, bob["hash"]).is_symlink()


def test_get_matches_repository_case_insensitively_and_user_exactly(store):
    alice = store.add(REPO, "alice")
    found = store.get(REPO.upper(), "alice")
    assert found == alice
    assert store.get(REPO, "Alice") is None
    assert store.get(OTHER.slug, "alice") is None
    found["user"] = "changed"
    assert store.get(REPO, "alice")["user"] == "alice"


def test_list_entries_sorted_filtered_and_copied(store):
    store.add(OTHER.slug, "zed")
    store.add(REPO, "bob")
    store.add("Example-Org/Private-Addons", "alice")
    listed = store.list_entries()
    assert [(e["repository"].lower(), e["user"]) for e in listed] == [
        (REPO, "alice"),
        (REPO, "bob"),
        (OTHER.slug, "zed"),
    ]
    assert [e["user"] for e in store.list_entries(REPO.upper())] == ["alice", "bob"]
    listed[0]["user"] = "changed"
    assert store.list_entries()[0]["user"] == "alice"


@pytest.mark.parametrize("source", ["cli", "gui", "api"])
def test_reserved_label_is_refused_for_non_system_sources(store, paths, source):
    assert "local" in RESERVED_USERS
    with pytest.raises(AccessError) as exc:
        store.add(REPO, "local", source=source)
    assert exc.value.code == "user_reserved"
    assert not paths.access_file.exists()


def test_reserved_label_is_accepted_for_system_source(store):
    created = store.add(REPO, "local", source="system")
    assert created["source"] == "system" and created["user"] == "local"


def test_client_hash_used_by_any_entry_is_a_conflict(store, paths):
    alice = store.add(REPO, "alice")
    with pytest.raises(AccessError) as exc:
        store.add(OTHER.slug, "bob", hash_=alice["hash"])
    assert exc.value.code == "hash_conflict"
    assert len(stored(paths)["entries"]) == 1


def test_malformed_client_hash_is_invalid(store):
    with pytest.raises(AccessError) as exc:
        store.add(REPO, "alice", hash_=new_hash().upper())
    assert exc.value.code == "invalid_hash"


def test_unknown_keys_and_fields_survive_add_and_revoke(store, paths):
    bob = entry(REPO, "bob", note="n")
    write_doc(paths, {"schema": 1, "x_future": 1, "entries": [bob]})
    store.add(REPO, "alice", specs=SPECS)
    assert stored(paths)["x_future"] == 1
    assert store.revoke(REPO, "alice", specs=SPECS) is True
    after = stored(paths)
    assert after["x_future"] == 1
    assert after["entries"] == [bob]


@pytest.mark.parametrize("operation", ["add", "revoke", "reconcile"])
def test_newer_schema_is_refused_without_writing(store, paths, operation):
    write_doc(paths, {"schema": 2, "entries": [entry(REPO, "alice")]})
    before = paths.access_file.read_bytes()
    with pytest.raises(AccessSchemaError):
        if operation == "add":
            store.add(REPO, "bob", specs=SPECS)
        elif operation == "revoke":
            store.revoke(REPO, "alice", specs=SPECS)
        else:
            store.reconcile(SPECS)
    assert paths.access_file.read_bytes() == before


def test_corrupt_file_is_moved_aside_and_its_content_never_logged(store, paths, caplog):
    sentinel = "SENTINEL-CORRUPT-" + new_hash()
    paths.access_file.write_text("{not json " + sentinel, encoding="utf-8")
    assert store.list_entries() == []
    corrupt = paths.access_file.with_name("access.json.corrupt")
    assert sentinel in corrupt.read_text(encoding="utf-8")
    assert not paths.access_file.exists()
    assert "corrupt" in caplog.text
    assert sentinel not in caplog.text


def test_two_stores_writing_concurrently_lose_no_entry(paths, log):
    stores = (AccessStore(paths, log), AccessStore(paths, log))
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            for n in range(25):
                stores[index].add(REPO, f"t{index}-{n}")
        except BaseException as exc:  # pragma: no cover - surfaced by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    entries = stored(paths)["entries"]
    assert len(entries) == 50
    assert len({e["hash"] for e in entries}) == 50


def test_file_modes_are_0600_after_every_write(store, paths):
    store.add(REPO, "alice", specs=SPECS)
    assert paths.access_file.stat().st_mode & 0o777 == 0o600
    store.add(REPO, "bob", specs=SPECS)
    assert paths.access_file.stat().st_mode & 0o777 == 0o600
    store.revoke(REPO, "alice", specs=SPECS)
    assert paths.access_file.stat().st_mode & 0o777 == 0o600
    assert paths.lock_file.stat().st_mode & 0o777 == 0o600


def test_valid_hash_has_no_link_under_another_repository(store, paths):
    alice = store.add(REPO, "alice", specs=SPECS)
    assert not os.path.lexists(link(paths, OTHER, alice["hash"]))
    assert store.revoke(REPO, "alice", specs=SPECS)
    assert symlinks(paths) == set()


def test_symlinked_directory_level_is_replaced_by_a_real_directory(store, paths, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    paths.access_root.mkdir(parents=True)
    os.symlink(elsewhere, paths.access_root / SPEC.owner)
    alice = store.add(REPO, "alice", specs=SPECS)
    owner_dir = paths.access_root / SPEC.owner
    assert not owner_dir.is_symlink() and owner_dir.is_dir()
    assert link(paths, SPEC, alice["hash"]).is_symlink()
    assert list(elsewhere.iterdir()) == []


def test_reconcile_invariant_one_link_per_valid_configured_entry(store, paths, caplog):
    alice = entry(REPO, "alice")
    bob = entry("Example-Org/Private-Addons", "bob")
    carol = entry(OTHER.slug, "carol")
    bad_hash = new_hash().upper()
    dave = entry(OTHER.slug, "dave", bad_hash)
    erin = entry("example-org/unconfigured", "erin")
    write_doc(paths, {"schema": 1, "entries": [alice, bob, carol, dave, erin]})

    stray_dir = paths.access_root / SPEC.owner / SPEC.name
    stray_dir.mkdir(parents=True)
    (stray_dir / "stray.txt").write_text("x", encoding="utf-8")
    os.symlink(paths.repo_dir(SPEC.owner, SPEC.name), stray_dir / new_hash())
    unconfigured_dir = paths.access_root / "example-org" / "unconfigured"
    unconfigured_dir.mkdir(parents=True)
    os.symlink(paths.repo_dir("example-org", "unconfigured"), unconfigured_dir / erin["hash"])

    assert store.reconcile(SPECS) == 3
    expected = {
        str(link(paths, SPEC, alice["hash"])): paths.repo_dir(SPEC.owner, SPEC.name),
        str(link(paths, SPEC, bob["hash"])): paths.repo_dir(SPEC.owner, SPEC.name),
        str(link(paths, OTHER, carol["hash"])): paths.repo_dir(OTHER.owner, OTHER.name),
    }
    assert symlinks(paths) == set(expected)
    for path, target in expected.items():
        assert os.readlink(path) == str(target)
    assert not (stray_dir / "stray.txt").exists()

    inodes = {path: os.lstat(path).st_ino for path in expected}
    assert store.reconcile(SPECS) == 3
    assert {path: os.lstat(path).st_ino for path in expected} == inodes

    for directory in (
        paths.access_root,
        paths.access_root / SPEC.owner,
        paths.access_root / SPEC.owner / SPEC.name,
        paths.access_root / OTHER.owner,
        paths.access_root / OTHER.owner / OTHER.name,
    ):
        assert directory.stat().st_mode & 0o777 == 0o711

    assert "other-org/tools/dave" in caplog.text
    for value in (alice["hash"], bob["hash"], carol["hash"], erin["hash"], bad_hash, bad_hash.lower()):
        assert value not in caplog.text
