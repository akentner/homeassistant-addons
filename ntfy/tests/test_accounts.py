"""Tests for app.accounts: guardrails, origins, backups and the role-change stash (fake ntfy CLI)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from app import accounts
from app.contract import ApiError
from helpers.ctx import make_context
from helpers.ntfy_db import add_acl, add_token, add_user


@pytest.fixture()
def ctx(tmp_path: Path):
    context = make_context(tmp_path, admin_user="root")
    add_user(context.paths.auth_db, "root", role="admin")
    add_user(context.paths.auth_db, "alice")
    add_acl(context.paths.auth_db, "alice", "a_b*", "rw")
    add_acl(context.paths.auth_db, "alice", "news", "ro")
    add_token(context.paths.auth_db, "alice", "tk_" + "a" * 29)
    return context


def code_of(excinfo: pytest.ExceptionInfo) -> str:
    return excinfo.value.code


def by_name(users: list[dict], name: str) -> dict:
    return next(u for u in users if u["name"] == name)


def test_list_users_everyone_last_and_protection(ctx) -> None:
    users = accounts.list_users(ctx)
    assert users[-1]["name"] == "everyone"
    assert users[-1]["protected_reason"] == "anonymous"
    assert by_name(users, "root")["protected_reason"] == "options_admin"
    assert by_name(users, "alice")["protected"] is False


def test_last_admin_protection_when_options_admin_absent(tmp_path: Path) -> None:
    context = make_context(tmp_path, admin_user="ghost")
    add_user(context.paths.auth_db, "boss", role="admin")
    users = accounts.list_users(context)
    assert by_name(users, "boss")["protected_reason"] == "last_admin"
    add_user(context.paths.auth_db, "boss2", role="admin")
    assert by_name(accounts.list_users(context), "boss")["protected"] is False


def test_list_users_counts_and_origin(ctx) -> None:
    ctx.origins.set_user("alice", "options")
    alice = by_name(accounts.list_users(ctx), "alice")
    assert alice["acl_count"] == 2
    assert alice["token_count"] == 1
    assert alice["origin"] == "options"
    assert set(alice) == {
        "name", "role", "tier", "origin", "provisioned", "protected", "protected_reason", "acl_count", "token_count",
    }


def test_create_user_records_gui_origin(ctx) -> None:
    user = accounts.create_user(ctx, "bob", "pw")
    assert user["name"] == "bob" and user["role"] == "user" and user["origin"] == "gui"
    assert ctx.db.has_user("bob")


def test_create_user_conflict(ctx) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.create_user(ctx, "alice", "pw")
    assert code_of(exc) == "conflict"


@pytest.mark.parametrize("name", ["everyone", "*", "-x", "a" * 65, "", "a b"])
def test_create_user_bad_names(ctx, name: str) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.create_user(ctx, name, "pw")
    assert code_of(exc) == "bad_request"


@pytest.mark.parametrize("password", ["", "x" * 73, "ä" * 37])
def test_create_user_bad_password(ctx, password: str) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.create_user(ctx, "bob", password)
    assert code_of(exc) == "bad_request"


def test_create_user_bad_role(ctx) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.create_user(ctx, "bob", "pw", role="root")
    assert code_of(exc) == "bad_request"


def test_change_password_allowed_for_protected_not_for_everyone(ctx) -> None:
    accounts.change_password(ctx, "root", "newpw")
    with pytest.raises(ApiError) as exc:
        accounts.change_password(ctx, "everyone", "newpw")
    assert code_of(exc) == "bad_request"
    with pytest.raises(ApiError) as exc:
        accounts.change_password(ctx, "nobody", "newpw")
    assert code_of(exc) == "not_found"


def test_delete_requires_confirmation(ctx) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.delete_user(ctx, "alice", "wrong")
    assert code_of(exc) == "confirmation_required"
    assert ctx.db.has_user("alice")


def test_delete_protected_users_refused(ctx) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.delete_user(ctx, "root", "root")
    assert code_of(exc) == "protected"
    with pytest.raises(ApiError) as exc:
        accounts.delete_user(ctx, "everyone", "everyone")
    assert code_of(exc) == "bad_request"


def test_delete_backs_up_and_drops_origins(ctx) -> None:
    ctx.origins.set_user("alice", "gui")
    ctx.origins.set_acl("alice", "news", "gui")
    accounts.delete_user(ctx, "alice", "alice")
    assert not ctx.db.has_user("alice")
    assert any(b["reason"] == "user-delete" for b in ctx.backups.list())
    snap = ctx.origins.snapshot()
    assert "alice" not in snap["users"] and "alice" not in snap["acls"]


def test_change_role_same_role_is_noop(ctx) -> None:
    user, dropped = accounts.change_role(ctx, "alice", "user")
    assert user["role"] == "user" and dropped == 0
    assert ctx.backups.list() == []


def test_demote_protected_refused(ctx) -> None:
    with pytest.raises(ApiError) as exc:
        accounts.change_role(ctx, "root", "user")
    assert code_of(exc) == "protected"


def test_promote_stashes_rules_and_demote_restores_with_origins(ctx) -> None:
    ctx.origins.set_acl("alice", "a_b*", "options")
    ctx.origins.set_acl("alice", "news", "iac")
    user, dropped = accounts.change_role(ctx, "alice", "admin")
    assert user["role"] == "admin" and dropped == 2
    assert any(b["reason"] == "role-change" for b in ctx.backups.list())
    assert ctx.db.snapshot_acl("alice") == []
    stash = ctx.origins.snapshot()["acl_stash"]["alice"]
    assert {(r["topic"], r["permission"], r["origin"]) for r in stash} == {
        ("a_b*", "rw", "options"),
        ("news", "ro", "iac"),
    }
    user, dropped = accounts.change_role(ctx, "alice", "user")
    assert user["role"] == "user" and dropped == 0
    rules = {(r["topic"], r["permission"], r["origin"]) for r in accounts.list_rules(ctx, user="alice")}
    assert rules == {("a_b*", "rw", "options"), ("news", "ro", "iac")}
    assert "alice" not in ctx.origins.snapshot()["acl_stash"]


def test_promote_without_rules_creates_no_backup(ctx) -> None:
    accounts.create_user(ctx, "bob", "pw")
    _, dropped = accounts.change_role(ctx, "bob", "admin")
    assert dropped == 0
    assert ctx.backups.list() == []


def test_set_rule_stores_with_gui_origin(ctx) -> None:
    rule = accounts.set_rule(ctx, "alice", "x_y*", "rw")
    assert rule == {"user": "alice", "topic": "x_y*", "permission": "rw", "origin": "gui"}


def test_set_rule_takes_over_options_rule_but_keeps_iac(ctx) -> None:
    ctx.origins.set_acl("alice", "news", "options")
    assert accounts.set_rule(ctx, "alice", "news", "rw")["origin"] == "gui"
    ctx.origins.set_acl("alice", "news", "iac")
    assert accounts.set_rule(ctx, "alice", "news", "wo")["origin"] == "iac"


def test_set_rule_errors(ctx) -> None:
    cases = [
        (("nobody", "t", "rw"), "not_found"),
        (("root", "t", "rw"), "bad_request"),
        (("alice", "t", "xx"), "bad_request"),
        (("alice", "bad topic", "rw"), "bad_request"),
    ]
    for args, expected in cases:
        with pytest.raises(ApiError) as exc:
            accounts.set_rule(ctx, *args)
        assert code_of(exc) == expected


def test_set_rule_for_everyone_allowed(ctx) -> None:
    rule = accounts.set_rule(ctx, "everyone", "pub", "ro")
    assert rule["user"] == "everyone" and rule["permission"] == "ro"


def test_remove_rule(ctx) -> None:
    ctx.origins.set_acl("alice", "news", "gui")
    accounts.remove_rule(ctx, "alice", "news")
    assert all(r["topic"] != "news" for r in accounts.list_rules(ctx, user="alice"))
    assert "alice" not in ctx.origins.snapshot()["acls"] or "news" not in ctx.origins.snapshot()["acls"]["alice"]
    with pytest.raises(ApiError) as exc:
        accounts.remove_rule(ctx, "alice", "news")
    assert code_of(exc) == "not_found"


def test_list_rules_filter_and_sorting(ctx) -> None:
    accounts.set_rule(ctx, "everyone", "pub", "ro")
    assert [r["topic"] for r in accounts.list_rules(ctx, user="alice")] == ["a_b*", "news"]
    assert [r["user"] for r in accounts.list_rules(ctx)] == ["alice", "alice", "everyone"]
    assert [r["user"] for r in accounts.list_rules(ctx, topic="pub")] == ["everyone"]


def test_two_admins_cannot_both_be_demoted_concurrently(tmp_path: Path) -> None:
    context = make_context(tmp_path, admin_user="ghost")
    add_user(context.paths.auth_db, "a1", role="admin")
    add_user(context.paths.auth_db, "a2", role="admin")
    results: list[str] = []

    def demote(name: str) -> None:
        try:
            accounts.change_role(context, name, "user")
            results.append("ok")
        except ApiError as exc:
            results.append(exc.code)

    threads = [threading.Thread(target=demote, args=(n,)) for n in ("a1", "a2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "protected"]
    assert sum(1 for u in accounts.list_users(context) if u["role"] == "admin") == 1
