"""NtfyCli against the fake ntfy binary."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest
from app import ntfycli
from app.contract import TOKEN_RE
from app.ntfycli import NtfyCli, NtfyCliError
from helpers.ctx import FAKE_NTFY, make_context

PASSWORD = "S3cret-pw!xyz"


@pytest.fixture
def env(tmp_path, monkeypatch):
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_NTFY_LOG", str(log))
    monkeypatch.setattr(ntfycli, "sleep", lambda _s: None)
    ctx = make_context(tmp_path)
    return ctx, log


def calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def rows(ctx, sql: str) -> list[tuple]:
    conn = sqlite3.connect(ctx.paths.auth_db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_user_add_env_password_and_exists(env):
    ctx, log = env
    ctx.cli.user_add("alice", PASSWORD)
    last = calls(log)[-1]
    assert PASSWORD not in json.dumps(last)
    assert last["env_password"] is True
    assert PASSWORD not in log.read_text()
    with pytest.raises(NtfyCliError) as exc:
        ctx.cli.user_add("alice", PASSWORD)
    assert exc.value.code == "exists"


def test_context_cli_and_db_see_same_user(env):
    ctx, _ = env
    ctx.cli.user_add("u", "p")
    assert "u" in [u["name"] for u in ctx.db.list_users()]


@pytest.mark.parametrize("name,pw", [("alice", ""), ("-x", "pw")])
def test_invalid_user_add_rejected_before_spawn(env, name, pw):
    ctx, log = env
    with pytest.raises(ValueError):
        ctx.cli.user_add(name, pw)
    assert calls(log) == []


def test_access_set_wildcards_and_everyone(env):
    ctx, _ = env
    ctx.cli.user_add("alice", "pw")
    ctx.cli.access_set("alice", "a_b*", "rw")
    ctx.cli.access_set("everyone", "up*", "wo")
    stored = rows(ctx, "SELECT u.user, a.topic, a.read, a.write FROM user_access a JOIN user u ON u.id=a.user_id")
    assert ("alice", "a\\_b%", 1, 1) in stored
    assert ("*", "up%", 0, 1) in stored


def test_access_set_errors(env):
    ctx, log = env
    with pytest.raises(NtfyCliError) as exc:
        ctx.cli.access_set("ghost", "t", "rw")
    assert exc.value.code == "not_found"
    ctx.cli.user_add("alice", "pw")
    n = len(calls(log))
    with pytest.raises(ValueError):
        ctx.cli.access_set("alice", "t", "bogus")
    assert len(calls(log)) == n


def test_access_deny_stores_zero_row(env):
    ctx, _ = env
    ctx.cli.user_add("alice", "pw")
    ctx.cli.access_set("alice", "t", "deny")
    assert rows(ctx, "SELECT read, write FROM user_access") == [(0, 0)]


def test_access_reset_variants(env):
    ctx, log = env
    for u in ("alice", "bob"):
        ctx.cli.user_add(u, "pw")
        ctx.cli.access_set(u, "x", "ro")
        ctx.cli.access_set(u, "y", "ro")
    ctx.cli.access_reset("alice", "x")
    assert len(rows(ctx, "SELECT 1 FROM user_access")) == 3
    ctx.cli.access_reset("alice")
    assert len(rows(ctx, "SELECT 1 FROM user_access")) == 2
    ctx.cli.access_reset()
    assert rows(ctx, "SELECT 1 FROM user_access") == []
    n = len(calls(log))
    with pytest.raises(ValueError):
        ctx.cli.access_reset("alice", "a%b%")
    assert len(calls(log)) == n


def test_change_role_to_admin_wipes_acl(env):
    ctx, _ = env
    ctx.cli.user_add("bob", "pw")
    ctx.cli.access_set("bob", "t*", "ro")
    ctx.cli.user_change_role("bob", "admin")
    assert rows(ctx, "SELECT 1 FROM user_access") == []


def test_token_add_and_remove(env):
    ctx, log = env
    ctx.cli.user_add("alice", "pw")
    token = ctx.cli.token_add("alice", label="ci", expires="2d")
    assert TOKEN_RE.match(token)
    argv = calls(log)[-1]["argv"]
    assert "--label=ci" in argv and "--expires=2d" in argv
    with pytest.raises(ValueError):
        ctx.cli.token_add("alice", expires="tomorrow")
    ctx.cli.token_remove("alice", token)
    with pytest.raises(NtfyCliError) as exc:
        ctx.cli.token_remove("alice", token)
    assert exc.value.code == "not_found"


def test_lock_once_is_retried(env, tmp_path, monkeypatch):
    ctx, log = env
    sleeps: list[float] = []
    monkeypatch.setattr(ntfycli, "sleep", sleeps.append)
    lock = tmp_path / "lock-once"
    lock.write_text("x")
    monkeypatch.setenv("FAKE_NTFY_LOCK_ONCE", str(lock))
    ctx.cli.user_add("alice", "pw")
    assert sleeps == [1.0]
    assert ctx.db.has_user("alice")


def test_three_consecutive_locks_give_locked(env, monkeypatch):
    ctx, _ = env
    monkeypatch.setattr(ntfycli, "classify", lambda _t: "locked")
    # a failing call (unknown user) reported as locked every time exhausts the retries
    sleeps: list[float] = []
    monkeypatch.setattr(ntfycli, "sleep", sleeps.append)
    with pytest.raises(NtfyCliError) as exc:
        ctx.cli.user_delete("ghost")
    assert exc.value.code == "locked"
    assert len(sleeps) == 3


def test_writes_are_serialized_across_threads(env, tmp_path, monkeypatch):
    ctx, _ = env
    overlap = tmp_path / "overlap"
    overlap.mkdir()
    monkeypatch.setenv("FAKE_NTFY_OVERLAP_DIR", str(overlap))
    monkeypatch.setenv("FAKE_NTFY_DELAY", "0.01")
    errors: list[Exception] = []

    def work(i: int) -> None:
        try:
            for j in range(5):
                ctx.cli.user_add(f"u{i}x{j}", "pw")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert not (overlap / "OVERLAP").exists()
    assert len(rows(ctx, "SELECT 1 FROM user WHERE user != '*'")) == 40


def test_provisioned_users_are_protected(env):
    ctx, _ = env
    conn = sqlite3.connect(ctx.paths.auth_db)
    conn.execute(
        "INSERT INTO user (id, user, pass, role, sync_topic, provisioned, created) "
        "VALUES ('u_p', 'prov', 'x', 'user', 'st_p', 1, 0)"
    )
    conn.commit()
    conn.close()
    for call in (
        lambda: ctx.cli.user_delete("prov"),
        lambda: ctx.cli.user_change_pass("prov", "pw"),
        lambda: ctx.cli.user_change_role("prov", "admin"),
    ):
        with pytest.raises(NtfyCliError) as exc:
            call()
        assert exc.value.code == "provisioned"


def test_missing_binary_and_timeout_map_to_other(tmp_path):
    cli = NtfyCli(binary=str(tmp_path / "nope"), config_file=tmp_path / "s.yml", auth_file=tmp_path / "a.db")
    with pytest.raises(NtfyCliError) as exc:
        cli.user_delete("x")
    assert exc.value.code == "other"
    slow = NtfyCli(binary=str(FAKE_NTFY), config_file=tmp_path / "s.yml", auth_file=tmp_path / "a.db", timeout=0.0001)
    with pytest.raises(NtfyCliError) as exc:
        slow.user_delete("x")
    assert exc.value.code == "other"


def test_user_delete_and_change_pass(env):
    ctx, _ = env
    ctx.cli.user_add("alice", "pw")
    ctx.cli.user_change_pass("alice", "new")
    ctx.cli.user_delete("alice")
    assert not ctx.db.has_user("alice")
    with pytest.raises(NtfyCliError) as exc:
        ctx.cli.user_delete("alice")
    assert exc.value.code == "not_found"
