"""Tests for app.maintenance: typed confirmation, backups first, cache clearing, reset everything, test publish."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from app import bootstrap, maintenance
from app.contract import ApiError
from helpers import ntfy_db
from helpers.ctx import make_context

TOKEN = "tk_" + "a" * 29
MESSAGES_DDL = (
    "CREATE TABLE messages (id INT PRIMARY KEY, mid TEXT, sequence_id TEXT, time INT, event TEXT, expires INT, "
    "topic TEXT, message TEXT, title TEXT, priority INT, tags TEXT, click TEXT, icon TEXT, actions TEXT, "
    "attachment_name TEXT, attachment_type TEXT, attachment_size INT, attachment_expires INT, attachment_url TEXT, "
    "attachment_deleted INT, sender TEXT, user TEXT, content_type TEXT, encoding TEXT, published INT);"
    "CREATE TABLE schemaVersion (id INT PRIMARY KEY, version INT);"
    "CREATE TABLE stats (key TEXT PRIMARY KEY, value INT);"
)


def seed(ctx: Any) -> None:
    ntfy_db.add_user(ctx.paths.auth_db, "admin", role="admin")
    ntfy_db.add_user(ctx.paths.auth_db, "alice")
    ntfy_db.add_acl(ctx.paths.auth_db, "alice", "alerts", "rw")
    ntfy_db.add_acl(ctx.paths.auth_db, "everyone", "pub", "ro")
    ctx.origins.set_acl("alice", "alerts", "gui")


def make_cache(path: Path, rows: int = 3, with_table: bool = True) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(MESSAGES_DDL if with_table else "CREATE TABLE other (x INT);")
    if with_table:
        for i in range(rows):
            conn.execute("INSERT INTO messages (id, mid, topic, message) VALUES (?, ?, 't', 'm')", (i, f"m{i}"))
    conn.commit()
    conn.close()


def count_rows(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    finally:
        conn.close()


def backup_files(ctx: Any) -> list[Path]:
    return sorted(ctx.paths.backup_dir.glob("auth-*.db")) if ctx.paths.backup_dir.exists() else []


@pytest.fixture()
def ctx(tmp_path: Path) -> Any:
    context = make_context(tmp_path, admin_password="pw")
    seed(context)
    return context


@pytest.mark.parametrize(
    ("func", "bad"),
    [
        (maintenance.reset_acls, ""),
        (maintenance.reset_acls, "clear cache"),
        (maintenance.clear_cache, "Clear cache"),
        (maintenance.reset_everything, "reset acls"),
    ],
)
def test_wrong_confirmation_changes_nothing(ctx: Any, func: Any, bad: str) -> None:
    with pytest.raises(ApiError) as err:
        func(ctx, bad)
    assert err.value.code == "confirmation_required"
    assert backup_files(ctx) == []
    assert ctx.db.counts()["acl_rules"] == 2
    assert ctx.db.counts()["users"] == 2


def test_non_string_confirmation_is_refused(ctx: Any) -> None:
    with pytest.raises(ApiError) as err:
        maintenance.reset_acls(ctx, None)  # type: ignore[arg-type]
    assert err.value.code == "confirmation_required"


def test_reset_acls_removes_rules_keeps_users(ctx: Any) -> None:
    result = maintenance.reset_acls(ctx, "reset acls")
    assert result["done"] is True
    assert result["backup"]["reason"] == "reset-acls"
    assert len(backup_files(ctx)) == 1
    assert ctx.db.counts() == {"users": 2, "acl_rules": 0, "tokens": 0}
    assert ctx.origins.snapshot()["acls"] == {}


def test_reset_acls_backup_contains_old_rules(ctx: Any) -> None:
    result = maintenance.reset_acls(ctx, "reset acls")
    conn = sqlite3.connect(ctx.backups.path_for(result["backup"]["name"]))
    try:
        assert conn.execute("SELECT COUNT(*) FROM user_access").fetchone()[0] == 2
    finally:
        conn.close()


def test_clear_cache_deletes_messages_and_matching_files(ctx: Any) -> None:
    make_cache(ctx.paths.cache_db, rows=4)
    att = ctx.paths.attachment_dir
    att.mkdir()
    (att / "abc123XYZ").write_bytes(b"x")
    (att / "Zz9").write_bytes(b"x")
    (att / ".keep").write_bytes(b"x")
    (att / "name.txt").write_bytes(b"x")
    (att / "subdir").mkdir()
    (att / "subdir" / "inner").write_bytes(b"x")
    result = maintenance.clear_cache(ctx, "clear cache")
    assert result["messages_deleted"] == 4
    assert result["attachments_deleted"] == 2
    assert result["backup"]["reason"] == "clear-cache"
    assert count_rows(ctx.paths.cache_db) == 0
    assert sorted(p.name for p in att.iterdir()) == [".keep", "name.txt", "subdir"]
    assert (att / "subdir" / "inner").exists()


def test_clear_cache_keeps_symlinks(ctx: Any, tmp_path: Path) -> None:
    make_cache(ctx.paths.cache_db, rows=0)
    att = ctx.paths.attachment_dir
    att.mkdir()
    target = tmp_path / "outside"
    target.write_bytes(b"keep")
    (att / "link1").symlink_to(target)
    result = maintenance.clear_cache(ctx, "clear cache")
    assert result["attachments_deleted"] == 0
    assert target.exists()


def test_clear_cache_without_attachment_dir_counts_zero(ctx: Any) -> None:
    make_cache(ctx.paths.cache_db, rows=1)
    result = maintenance.clear_cache(ctx, "clear cache")
    assert result["messages_deleted"] == 1
    assert result["attachments_deleted"] == 0


def test_clear_cache_without_messages_table_fails(ctx: Any) -> None:
    make_cache(ctx.paths.cache_db, with_table=False)
    with pytest.raises(ApiError) as err:
        maintenance.clear_cache(ctx, "clear cache")
    assert err.value.code == "ntfy_error"


def test_clear_cache_without_cache_db_succeeds(ctx: Any) -> None:
    assert not ctx.paths.cache_db.exists()
    result = maintenance.clear_cache(ctx, "clear cache")
    assert result["messages_deleted"] == 0
    assert not ctx.paths.cache_db.exists()


def recreate_admin(ctx: Any) -> Any:
    calls: list[int] = []

    def stub(context: Any) -> None:
        calls.append(1)
        context.cli.user_add(context.options.admin_user, context.options.admin_password, role="admin")

    return stub, calls


def test_reset_everything_requires_admin_password(tmp_path: Path) -> None:
    context = make_context(tmp_path, admin_password="")
    seed(context)
    with pytest.raises(ApiError) as err:
        maintenance.reset_everything(context, "reset everything")
    assert err.value.code == "conflict"
    assert backup_files(context) == []
    assert context.db.counts()["users"] == 2


def test_reset_everything_wipes_and_recreates(ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    stub, calls = recreate_admin(ctx)
    monkeypatch.setattr(bootstrap, "apply_options", stub)
    result = maintenance.reset_everything(ctx, "reset everything")
    assert result["backup"]["reason"] == "reset-everything"
    assert len(backup_files(ctx)) == 1
    assert calls == [1]
    names = {u["name"] for u in ctx.db.list_users()}
    assert "alice" not in names
    assert "admin" in names
    assert ctx.db.counts()["acl_rules"] == 0


def test_reset_everything_fails_when_admin_not_recreated(ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "apply_options", lambda context: None)
    with pytest.raises(ApiError) as err:
        maintenance.reset_everything(ctx, "reset everything")
    assert err.value.code == "ntfy_error"


def test_services_hold_the_context_lock(ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    held: list[bool] = []

    def spy(*_a: Any, **_k: Any) -> None:
        held.append(ctx.lock._is_owned())  # type: ignore[attr-defined]

    monkeypatch.setattr(ctx.cli, "access_reset", spy)
    maintenance.reset_acls(ctx, "reset acls")
    assert held == [True]


class FakeHttp:
    def __init__(self, ctx: Any, status: int = 200, body: bytes = b'{"id": "abc123"}', boom: bool = False) -> None:
        self.ctx, self.status, self.body, self.boom = ctx, status, body, boom
        self.calls: list[tuple[str, dict[str, str], bytes]] = []
        self.tokens_during: int | None = None

    def __call__(self, url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
        self.calls.append((url, headers, body))
        self.tokens_during = self.ctx.db.counts()["tokens"]
        if self.boom:
            raise OSError("down")
        return self.status, self.body


def test_publish_test_ok_and_token_removed(ctx: Any) -> None:
    http = FakeHttp(ctx)
    result = maintenance.publish_test(ctx, "alerts", "hi", http=http)
    assert result == {"ok": True, "status": 200, "id": "abc123"}
    url, headers, body = http.calls[0]
    assert url == "http://127.0.0.1:8000/alerts"
    assert headers["Authorization"].startswith("Bearer tk_")
    assert body == b"hi"
    assert http.tokens_during == 1
    assert ctx.db.counts()["tokens"] == 0


def test_publish_test_default_message_and_truncation(ctx: Any) -> None:
    http = FakeHttp(ctx)
    maintenance.publish_test(ctx, "alerts", http=http)
    assert http.calls[0][2] == b"ntfy admin GUI test"
    maintenance.publish_test(ctx, "alerts", "x" * 900, http=http)
    assert len(http.calls[1][2]) == 512


def test_publish_test_rate_limited(ctx: Any) -> None:
    result = maintenance.publish_test(ctx, "alerts", http=FakeHttp(ctx, status=429, body=b"nope"))
    assert result == {"ok": False, "status": 429, "id": None}
    assert ctx.db.counts()["tokens"] == 0


def test_publish_test_removes_token_when_http_raises(ctx: Any) -> None:
    with pytest.raises(OSError):
        maintenance.publish_test(ctx, "alerts", http=FakeHttp(ctx, boom=True))
    assert ctx.db.counts()["tokens"] == 0


def test_publish_test_missing_admin(tmp_path: Path) -> None:
    context = make_context(tmp_path, admin_password="pw")
    with pytest.raises(ApiError) as err:
        maintenance.publish_test(context, "alerts", http=FakeHttp(context))
    assert err.value.code == "conflict"


@pytest.mark.parametrize("topic", ["", "-x", "a b", "a/b", "x" * 65])
def test_publish_test_invalid_topic(ctx: Any, topic: str) -> None:
    with pytest.raises(ApiError) as err:
        maintenance.publish_test(ctx, topic, http=FakeHttp(ctx))
    assert err.value.code == "bad_request"
