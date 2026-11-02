"""AuthDb read model, schema pinning and contract conformance of both adapters."""

from __future__ import annotations

import inspect
import json
import re
import sqlite3
import threading

import pytest
from app import ntfycli
from app.authdb import AuthDb
from app.contract import AuthReader, ApiError, CliWriter, token_id
from app.ntfycli import NtfyCli
from helpers import ntfy_db
from helpers.ctx import make_context

TOKEN_A = "tk_" + "a" * 29
TOKEN_B = "tk_" + "b" * 29


@pytest.fixture
def db(tmp_path) -> AuthDb:
    path = ntfy_db.make_auth_db(tmp_path / "auth.db")
    ntfy_db.add_user(path, "alice", tier_code="pro")
    ntfy_db.add_user(path, "bob", role="admin", provisioned=1)
    ntfy_db.add_acl(path, "alice", "up*", "wo")
    ntfy_db.add_acl(path, "alice", "a_b*", "rw")
    ntfy_db.add_acl(path, "everyone", "*", "ro")
    ntfy_db.add_acl(path, "bob", "pub", "deny", provisioned=1)
    ntfy_db.add_token(path, "alice", TOKEN_A, label="ci", expires=1900000000, last_access=5)
    ntfy_db.add_token(path, "bob", TOKEN_B)
    return AuthDb(path)


def test_list_users_anonymous_tier_and_hash(db):
    users = {u["name"]: u for u in db.list_users()}
    assert users["everyone"]["role"] == "anonymous"
    assert users["alice"]["tier"] == "pro"
    assert users["bob"]["tier"] is None and users["bob"]["provisioned"] is True
    assert all("pass_hash" not in u for u in users.values())
    hashed = {u["name"]: u for u in db.list_users(include_hash=True)}
    assert hashed["alice"]["pass_hash"].startswith("$2a$")


def test_list_acl_cli_form_sorted(db):
    acl = db.list_acl()
    got = [(r["user"], r["topic"], r["permission"]) for r in acl]
    assert got == sorted(got, key=lambda t: (t[0], t[1]))
    assert ("alice", "up*", "wo") in got
    assert ("alice", "a_b*", "rw") in got
    assert ("everyone", "*", "ro") in got
    assert ("bob", "pub", "deny") in got
    row = next(r for r in acl if r["topic"] == "up*")
    assert (row["read"], row["write"], row["provisioned"]) == (False, True, False)


def test_list_tokens_never_contains_value(db):
    tokens = db.list_tokens()
    assert not re.search(r"tk_[a-z0-9]{29}", json.dumps(tokens))
    row = next(t for t in tokens if t["user"] == "alice")
    assert row["prefix"] == TOKEN_A[:7]
    assert row["token_id"] == token_id(TOKEN_A)
    assert row["expires"] == 1900000000
    assert next(t for t in tokens if t["user"] == "bob")["expires"] == 0
    assert [t["user"] for t in db.list_tokens("alice")] == ["alice"]


def test_reveal_token(db):
    assert db.reveal_token("alice", token_id(TOKEN_A)) == TOKEN_A
    assert db.reveal_token("alice", "nonexistent0") is None
    assert db.reveal_token("alice", token_id(TOKEN_B)) is None


def test_counts_has_user_snapshot(db):
    assert db.counts() == {"users": 2, "acl_rules": 4, "tokens": 2}
    assert db.has_user("alice") and db.has_user("everyone") and not db.has_user("ghost")
    assert {r["topic"] for r in db.snapshot_acl("alice")} == {"up*", "a_b*"}
    assert db.snapshot_acl("everyone")[0]["topic"] == "*"
    assert db.size_bytes() > 0


def test_unsupported_version(tmp_path):
    path = ntfy_db.make_auth_db(tmp_path / "auth.db", version=9)
    db = AuthDb(path)
    status = db.check_schema()
    assert status["supported"] is False and status["version"] == 9
    with pytest.raises(ApiError) as exc:
        db.ensure_supported()
    assert exc.value.code == "db_unsupported"
    with pytest.raises(ApiError):
        db.list_users()


def test_missing_file(tmp_path):
    db = AuthDb(tmp_path / "none.db")
    assert db.check_schema()["error"] == "db_unavailable"
    with pytest.raises(ApiError) as exc:
        db.list_acl()
    assert exc.value.code == "db_unavailable"
    assert db.size_bytes() is None


def test_missing_schema_table_is_unsupported(tmp_path):
    path = tmp_path / "other.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE x (a INT)")
    conn.commit()
    conn.close()
    db = AuthDb(path)
    status = db.check_schema()
    assert status["supported"] is False and status["error"] == "db_unsupported"
    with pytest.raises(ApiError) as exc:
        db.counts()
    assert exc.value.code == "db_unsupported"


def test_connection_is_read_only(db):
    conn = db._connect()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM user_access")
    finally:
        conn.close()


def test_every_read_checks_schema(tmp_path):
    db = AuthDb(ntfy_db.make_auth_db(tmp_path / "auth.db", version=11))
    for call in (db.list_users, db.list_acl, db.list_tokens, db.counts, lambda: db.has_user("a"),
                 lambda: db.snapshot_acl("a"), lambda: db.reveal_token("a", "x")):
        with pytest.raises(ApiError):
            call()


def test_reads_do_not_block_cli_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(ntfycli, "sleep", lambda _s: None)
    ctx = make_context(tmp_path)
    ctx.cli.user_add("seed", "pw")
    stop = threading.Event()
    failures: list[Exception] = []
    reads = 0

    def reader() -> None:
        nonlocal reads
        try:
            while reads < 300 and not stop.is_set():
                ctx.db.list_users()
                ctx.db.list_acl()
                reads += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(exc)

    thread = threading.Thread(target=reader)
    thread.start()
    for i in range(20):
        ctx.cli.user_add(f"w{i}", "pw")
    stop.set()
    thread.join()
    assert failures == []
    assert ctx.db.counts()["users"] == 21


def _params(fn) -> list[str]:
    return list(inspect.signature(fn).parameters)


@pytest.mark.parametrize("impl,proto", [(AuthDb, AuthReader), (NtfyCli, CliWriter)])
def test_conforms_to_contract_protocol(impl, proto):
    for name, member in inspect.getmembers(proto, inspect.isfunction):
        if name.startswith("_"):
            continue
        assert hasattr(impl, name), f"{impl.__name__}.{name} missing"
        got = [p for p in _params(getattr(impl, name))]
        want = [p for p in _params(member)]
        # the reveal_token protocol names the second parameter `token_id`, shadowed in the module by the helper
        if name == "reveal_token":
            assert got[:2] == want[:2] or got == ["self", "user", "token_id_"]
        else:
            assert got == want, f"{impl.__name__}.{name}: {got} != {want}"
