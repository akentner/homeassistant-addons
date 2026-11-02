from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.backups import BackupStore
from app.context import Context, build_context
from app.contract import ApiError, Paths
from app.origins import OriginStore
from helpers.ntfy_db import add_user, make_auth_db


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start.timestamp()

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock(datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc))


@pytest.fixture
def db(tmp_path):
    path = make_auth_db(tmp_path / "auth.db")
    add_user(path, "alice")
    return path


def make_store(tmp_path, db, clock, keep=3):
    return BackupStore(tmp_path / "backups", db, keep, clock)


def test_create_is_valid_copy_with_modes(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock)
    backup = store.create("manual")
    assert backup["name"] == "auth-20261102T100000Z-manual.db"
    assert backup["reason"] == "manual" and backup["created"] == "2026-11-02T10:00:00Z"
    path = tmp_path / "backups" / backup["name"]
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "backups").stat().st_mode & 0o777 == 0o700
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert {r[0] for r in conn.execute("SELECT user FROM user")} == {"*", "alice"}
    finally:
        conn.close()


def test_existing_dir_mode_is_fixed(tmp_path, db, clock):
    (tmp_path / "backups").mkdir(mode=0o755)
    make_store(tmp_path, db, clock).create()
    assert (tmp_path / "backups").stat().st_mode & 0o777 == 0o700


def test_same_second_gives_distinct_files(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock, keep=5)
    first, second = store.create("x"), store.create("x")
    assert first["name"] != second["name"]
    assert len(store.list()) == 2


def test_reason_is_sanitised(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock)
    assert store.create("../Evil Reason!")["reason"] == "evil-reason"
    assert store.create("***")["reason"] == "manual"
    assert len(store.create("a" * 100)["reason"]) <= 40


def test_rotation_keeps_newest(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock, keep=3)
    names = []
    for _ in range(5):
        names.append(store.create("manual")["name"])
        clock.now += 60
    assert [b["name"] for b in store.list()] == names[:1:-1]
    assert store.rotate() == 0


def test_rotate_removes_surplus_when_keep_shrinks(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock, keep=5)
    for _ in range(4):
        store.create()
        clock.now += 60
    store.keep = 2
    assert store.rotate() == 2
    assert len(store.list()) == 2


def test_create_daily_once_per_utc_day(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock, keep=10)
    first = store.create_daily()
    assert first is not None and first["reason"] == "daily"
    clock.now += 3600
    assert store.create_daily() is None
    clock.now += 86400
    assert store.create_daily() is not None


def test_create_daily_without_db_is_none(tmp_path, clock):
    assert make_store(tmp_path, tmp_path / "auth.db", clock).create_daily() is None


def test_manual_backup_does_not_count_as_daily(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock)
    store.create("manual")
    assert store.create_daily() is not None


def test_list_newest_first_ignores_strays(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock, keep=5)
    store.create("a")
    clock.now += 60
    store.create("b")
    (tmp_path / "backups" / "x.db").write_text("x")
    (tmp_path / "backups" / ".backup-1.tmp").write_text("x")
    listing = store.list()
    assert [b["reason"] for b in listing] == ["b", "a"]
    assert all(b["size_bytes"] > 0 for b in listing)


def test_path_for_validation(tmp_path, db, clock):
    store = make_store(tmp_path, db, clock)
    name = store.create()["name"]
    assert store.path_for(name) == tmp_path / "backups" / name
    for bad in ("../etc/passwd", "auth-..db", "x.db", ""):
        with pytest.raises(ApiError) as err:
            store.path_for(bad)
        assert err.value.code == "bad_request"
    with pytest.raises(ApiError) as err:
        store.path_for("auth-20200101T000000Z-manual.db")
    assert err.value.code == "not_found"


def test_create_without_auth_db(tmp_path, clock):
    with pytest.raises(ApiError) as err:
        make_store(tmp_path, tmp_path / "auth.db", clock).create()
    assert err.value.code == "db_unavailable"


def test_create_on_garbage_db_is_db_unavailable(tmp_path, clock):
    bad = tmp_path / "auth.db"
    bad.write_text("not a database")
    with pytest.raises(ApiError) as err:
        make_store(tmp_path, bad, clock).create()
    assert err.value.code == "db_unavailable"
    assert list((tmp_path / "backups").iterdir()) == []


def test_build_context_wires_stores(tmp_path):
    (tmp_path / "options.json").write_text('{"backup_keep": 4}')
    ctx = build_context(Paths.for_dir(tmp_path))
    assert isinstance(ctx, Context)
    assert isinstance(ctx.origins, OriginStore)
    assert isinstance(ctx.backups, BackupStore)
    assert ctx.backups.keep == 4
