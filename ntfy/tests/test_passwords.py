"""Placeholder password guard: weak option values never become accounts (2026-11-03 incident)."""

from __future__ import annotations

import pytest

from app.baseline import apply_baseline
from app.bootstrap import apply_options, ensure_admin
from app.passwords import MIN_LENGTH, password_problem
from helpers.ctx import make_context

GOOD = "a-real-secret-123"


@pytest.mark.parametrize(
    "username, password, fragment",
    [
        ("alice", "", "empty"),
        ("alice", "!secret ntfy_user_alice_password", "!secret"),
        ("alice", "  !secret x", "!secret"),
        ("alice", "alice", "username"),
        ("Alice", "aLiCe", "username"),
        ("homeassistant", "homeassistant", "username"),
        ("alice", "short7!", "shorter"),
    ],
)
def test_rejected_values(username, password, fragment):
    problem = password_problem(username, password)
    assert problem is not None and fragment in problem
    assert password not in problem or password == ""


def test_accepts_a_real_password():
    assert password_problem("alice", GOOD) is None
    assert password_problem("alice", "x" * MIN_LENGTH) is None


def test_baseline_does_not_create_placeholder_accounts(tmp_path, capsys):
    ctx = make_context(
        tmp_path,
        baseline_users=[
            {"username": "alice", "password": "alice", "topic": "t1", "write_access": True},
            {"username": "bob", "password": "!secret ntfy_user_bob_password", "topic": "t2", "write_access": True},
            {"username": "carol", "password": GOOD, "topic": "t3", "write_access": False},
        ],
    )
    report = apply_baseline(ctx)
    users = {u["name"] for u in ctx.db.list_users()} - {"everyone"}
    assert users == {"carol"}
    assert report.users_created == ["carol"]
    assert [rule[0] for rule in report.rules_set] == ["carol"]
    assert len(report.warnings) == 2
    assert all("user not created" in w for w in report.warnings)
    out = capsys.readouterr().out
    assert "!secret ntfy_user_bob_password" not in out
    assert "alice" in out and "equals the username" in out


def test_fresh_db_sets_baseline_password_regardless_of_overwrite_flag(tmp_path, monkeypatch):
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_NTFY_LOG", str(log))
    ctx = make_context(
        tmp_path,
        baseline_overwrite_passwords=False,
        baseline_users=[{"username": "alice", "password": GOOD, "topic": "t1", "write_access": True}],
    )
    report = apply_baseline(ctx)
    assert report.users_created == ["alice"]
    text = log.read_text()
    assert '"user"' in text and '"add"' in text
    assert GOOD not in text


def test_overwrite_never_sets_a_placeholder_on_existing_user(tmp_path, monkeypatch):
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_NTFY_LOG", str(log))
    ctx = make_context(
        tmp_path,
        baseline_overwrite_passwords=True,
        baseline_users=[{"username": "alice", "password": "alice", "topic": "t1", "write_access": True}],
    )
    ctx.cli.user_add("alice", GOOD, role="user")
    log.unlink(missing_ok=True)
    report = apply_baseline(ctx)
    assert report.passwords_reset == []
    assert any("not reset" in w for w in report.warnings)
    assert not log.exists() or "change-pass" not in log.read_text()


def test_overwrite_resets_a_valid_password(tmp_path):
    ctx = make_context(
        tmp_path,
        baseline_overwrite_passwords=True,
        baseline_users=[{"username": "alice", "password": GOOD, "topic": "t1", "write_access": True}],
    )
    ctx.cli.user_add("alice", "another-old-pw-9", role="user")
    report = apply_baseline(ctx)
    assert report.passwords_reset == ["alice"]


@pytest.mark.parametrize("bad", ["root", "!secret ntfy_admin_password", "short"])
def test_admin_is_not_created_with_a_placeholder(tmp_path, bad):
    ctx = make_context(tmp_path, admin_user="root", admin_password=bad)
    with pytest.raises(ValueError, match="not created"):
        ensure_admin(ctx)
    assert "root" not in {u["name"] for u in ctx.db.list_users()}


def test_apply_options_reports_the_admin_refusal_as_warning(tmp_path):
    ctx = make_context(
        tmp_path,
        admin_user="root",
        admin_password="root",
        baseline_users=[{"username": "alice", "password": GOOD, "topic": "t1", "write_access": True}],
    )
    report = apply_options(ctx)
    assert any(w.startswith("admin: ValueError") and "equals the username" in w for w in report.warnings)
    assert "alice" in {u["name"] for u in ctx.db.list_users()}
