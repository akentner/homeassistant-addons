"""Baseline (24-09): additive, idempotent, origin-aware, never deletes."""

from __future__ import annotations

import json

import pytest

from app.baseline import apply_baseline
from app.contract import ApiError
from helpers.ctx import make_context

PW = "s3cret-pw-1"


def entry(username="alice", password=PW, topic="t1", write_access=True):
    return {"username": username, "password": password, "topic": topic, "write_access": write_access}


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_NTFY_LOG", str(path))
    return path


def calls(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]



def perm(ctx, user, topic):
    return {(r["user"], r["topic"]): r["permission"] for r in ctx.db.list_acl()}.get((user, topic))


def test_empty_baseline_changes_nothing(tmp_path, log_path):
    ctx = make_context(tmp_path)
    report = apply_baseline(ctx)
    assert report == type(report)()
    assert calls(log_path) == []


def test_new_entry_creates_user_and_rule(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    report = apply_baseline(ctx)
    assert report.users_created == ["alice"]
    assert report.rules_set == [("alice", "t1", "rw")]
    assert perm(ctx, "alice", "t1") == "rw"
    assert ctx.origins.get_user("alice") == "options"
    assert ctx.origins.get_acl("alice", "t1") == "options"
    roles = {u["name"]: u["role"] for u in ctx.db.list_users()}
    assert roles["alice"] == "user"


def test_read_only_entry(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry(write_access=False)])
    apply_baseline(ctx)
    assert perm(ctx, "alice", "t1") == "ro"


def test_second_run_performs_no_writes(tmp_path, log_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    apply_baseline(ctx)
    before = len(calls(log_path))
    report = apply_baseline(ctx)
    assert len(calls(log_path)) == before
    assert report.users_created == [] and report.rules_set == []


def test_existing_user_untouched_when_flag_false(tmp_path, log_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    ctx.cli.user_add("alice", "other-pw-9", role="user")
    log_path.unlink(missing_ok=True)
    report = apply_baseline(ctx)
    argvs = [c["argv"] for c in calls(log_path)]
    assert not any("change-pass" in a or "add" in a[:2] for a in argvs)
    assert ctx.origins.get_user("alice") == "gui"
    assert report.passwords_reset == []
    assert perm(ctx, "alice", "t1") == "rw"  # rule still applied


def test_flag_true_resets_password_each_run(tmp_path, log_path):
    ctx = make_context(tmp_path, baseline_users=[entry(), entry("bob", topic="")],
                       baseline_overwrite_passwords=True)
    ctx.cli.user_add("alice", "other-pw-9", role="user")
    ctx.cli.user_add("carol", "carol-pw-9", role="user")  # GUI-created, not in baseline
    log_path.unlink(missing_ok=True)
    report = apply_baseline(ctx)
    argvs = [c for c in calls(log_path) if "change-pass" in c["argv"]]
    assert [c["argv"][-1] for c in argvs] == ["alice"]
    assert all(c["env_password"] is True for c in argvs)
    assert report.passwords_reset == ["alice"]
    assert ctx.origins.get_user("alice") == "gui"
    assert report.users_created == ["bob"]  # fresh user: add only, no change-pass
    log_path.unlink()
    assert apply_baseline(ctx).passwords_reset == ["alice", "bob"]
    assert len([c for c in calls(log_path) if "change-pass" in c["argv"]]) == 2
    assert PW not in log_path.read_text()


def test_flag_true_skips_admin_and_admin_user(tmp_path, log_path, capsys):
    ctx = make_context(tmp_path, admin_user="root", baseline_overwrite_passwords=True,
                       baseline_users=[entry("boss"), entry("root")])
    ctx.cli.user_add("boss", "boss-pw-9", role="admin")
    ctx.cli.user_add("root", "root-pw-9", role="admin")
    log_path.unlink(missing_ok=True)
    report = apply_baseline(ctx)
    assert not any("change-pass" in c["argv"] for c in calls(log_path))
    assert report.passwords_reset == []
    assert len(report.warnings) == 2
    assert perm(ctx, "boss", "t1") is None
    assert PW not in capsys.readouterr().out


def test_options_rule_is_resynced(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    apply_baseline(ctx)
    ctx.cli.access_set("alice", "t1", "ro")  # edited out-of-band
    report = apply_baseline(ctx)
    assert report.rules_set == [("alice", "t1", "rw")]
    assert perm(ctx, "alice", "t1") == "rw"


def test_gui_rule_is_kept(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    apply_baseline(ctx)
    ctx.origins.set_acl("alice", "t1", "gui")
    ctx.cli.access_set("alice", "t1", "ro")
    report = apply_baseline(ctx)
    assert report.rules_kept == [("alice", "t1")]
    assert report.rules_set == []
    assert perm(ctx, "alice", "t1") == "ro"


def test_iac_rule_is_kept(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    ctx.cli.user_add("alice", "x-pw-123", role="user")
    ctx.cli.access_set("alice", "t1", "ro")
    ctx.origins.set_acl("alice", "t1", "iac")
    report = apply_baseline(ctx)
    assert report.rules_kept == [("alice", "t1")]
    assert perm(ctx, "alice", "t1") == "ro"


def test_empty_topic_creates_only_user(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry(topic="")])
    report = apply_baseline(ctx)
    assert report.users_created == ["alice"]
    assert ctx.db.list_acl() == []


def test_admin_role_user_gets_warning_and_no_rule(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry("boss")])
    ctx.cli.user_add("boss", "boss-pw-9", role="admin")
    report = apply_baseline(ctx)
    assert len(report.warnings) == 1
    assert ctx.db.list_acl() == []


def test_admin_user_entry_ignored(tmp_path, log_path):
    ctx = make_context(tmp_path, admin_user="root", baseline_users=[entry("root")])
    report = apply_baseline(ctx)
    assert len(report.warnings) == 1
    assert calls(log_path) == []


def test_removed_entry_becomes_gui_and_nothing_is_deleted(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    apply_baseline(ctx)
    ctx.options = type(ctx.options)(**{**ctx.options.__dict__, "baseline_users": ()})
    report = apply_baseline(ctx)
    assert sorted(report.orphaned) == ["alice", "alice:t1"]
    assert ctx.origins.get_user("alice") == "gui"
    assert ctx.origins.get_acl("alice", "t1") == "gui"
    assert perm(ctx, "alice", "t1") == "rw"
    assert any(u["name"] == "alice" for u in ctx.db.list_users())


def test_admin_origin_is_not_orphaned(tmp_path):
    ctx = make_context(tmp_path, admin_user="root")
    ctx.origins.set_user("root", "options")
    assert apply_baseline(ctx).orphaned == []
    assert ctx.origins.get_user("root") == "options"


def test_duplicate_entries_are_idempotent(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry(), entry(write_access=False)])
    report = apply_baseline(ctx)
    assert report.users_created == ["alice"]
    assert perm(ctx, "alice", "t1") == "ro"  # processed in order, the later entry wins (options-owned)


def test_password_never_in_argv_or_output(tmp_path, log_path, capsys):
    ctx = make_context(tmp_path, baseline_users=[entry()])
    apply_baseline(ctx)
    add = [c for c in calls(log_path) if c["argv"][:2] == ["user", "add"]]
    assert add and add[0]["env_password"] is True
    assert PW not in log_path.read_text()
    assert PW not in capsys.readouterr().out


def test_db_unavailable_counts_as_empty(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry()])

    def boom(*a, **k):
        raise ApiError("db_unavailable")

    ctx.db.list_users = boom
    ctx.db.list_acl = boom
    report = apply_baseline(ctx)
    assert report.users_created == ["alice"]


def test_exists_tolerated_and_other_errors_become_warnings(tmp_path, monkeypatch):
    from app.ntfycli import NtfyCliError

    ctx = make_context(tmp_path, baseline_users=[entry("a1"), entry("b1")])
    real = ctx.cli.user_add

    def flaky(name, password, role="user"):
        if name == "a1":
            real(name, password, role)
            raise NtfyCliError("exists", "already exists")
        raise NtfyCliError("other", "boom")

    ctx.cli.user_add = flaky
    report = apply_baseline(ctx)
    assert perm(ctx, "a1", "t1") == "rw"
    assert len(report.warnings) == 1 and "b1" in report.warnings[0]
    assert PW not in report.warnings[0]


def test_invalid_entry_is_warning_and_run_continues(tmp_path):
    ctx = make_context(tmp_path, baseline_users=[entry("-bad"), entry("ok1")])
    report = apply_baseline(ctx)
    assert len(report.warnings) == 1
    assert report.users_created == ["ok1"]
