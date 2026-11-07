#!/usr/bin/env python3
"""Fake ntfy CLI over a real-schema auth.db (messages and exit codes follow spike ntfy-cli, section 3).

Observability: FAKE_NTFY_LOG appends one JSON line per call (argv, env_password boolean, never the value);
FAKE_NTFY_LOCK_ONCE names a file that is removed on first sight and answers `database is locked`.
"""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import string
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contract import cli_topic_to_db, db_topic_to_cli  # noqa: E402
from helpers.ntfy_db import make_auth_db  # noqa: E402

NAME_RE = re.compile(r"^[a-zA-Z0-9_][-_.+@a-zA-Z0-9]{0,63}$")
TOPIC_RE = re.compile(r"^[a-zA-Z0-9_*][-_a-zA-Z0-9*]{0,63}$")
PERMS = {
    "read-write": (1, 1), "rw": (1, 1), "read": (1, 0), "read-only": (1, 0), "ro": (1, 0),
    "write": (0, 1), "write-only": (0, 1), "wo": (0, 1), "deny": (0, 0), "none": (0, 0),
}
PHRASE = {(1, 1): "read-write", (1, 0): "read-only", (0, 1): "write-only", (0, 0): "no"}


class Fail(Exception):
    pass


def out(text: str) -> None:
    print(text, flush=True)


def uname(name: str) -> str:
    return "*" if name in ("everyone", "*") else name


def find_user(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM user WHERE user = ?", (uname(name),)).fetchone()
    if row is None:
        raise Fail(f"user {name} does not exist")
    return row


def need_password() -> str:
    pw = os.environ.get("NTFY_PASSWORD", "")
    if not pw:
        raise Fail("password: inappropriate ioctl for device")
    return pw


def listing(conn: sqlite3.Connection, only: str | None = None) -> None:
    for u in conn.execute("SELECT * FROM user ORDER BY user"):
        if only is not None and u["user"] != uname(only):
            continue
        out(f"user {u['user']} (role: {u['role']}, tier: none)")
        if u["role"] == "admin":
            out("- read-write access to all topics (admin role)")
            continue
        rows = conn.execute("SELECT * FROM user_access WHERE user_id = ? ORDER BY topic", (u["id"],)).fetchall()
        for a in rows:
            phrase = PHRASE[(a["read"], a["write"])]
            sep = "access to" if phrase != "no" else "access to"
            out(f"- {phrase} {sep} topic {db_topic_to_cli(a['topic'])}")
        if not rows:
            out("- no topic-specific permissions")


def run(conn: sqlite3.Connection, argv: list[str]) -> None:
    if not argv or argv[0] in ("access",) and len(argv) == 1:
        listing(conn)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "user":
        return user_cmd(conn, rest)
    if cmd == "access":
        return access_cmd(conn, rest)
    if cmd == "token":
        return token_cmd(conn, rest)
    raise Fail(f"unknown command {cmd}")


def positional(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def user_cmd(conn: sqlite3.Connection, args: list[str]) -> None:
    sub, rest = (args[0], args[1:]) if args else ("list", [])
    if sub == "list":
        return listing(conn)
    if sub == "add":
        role = "user"
        for a in rest:
            if a.startswith("--role="):
                role = a.split("=", 1)[1]
        pos = positional(rest)
        if len(pos) != 1:
            raise Fail("invalid argument")
        name = pos[0]
        if role not in ("user", "admin"):
            raise Fail("role must be either 'user' or 'admin'")
        pw = need_password()
        if not NAME_RE.match(name):
            raise Fail("invalid argument")
        if conn.execute("SELECT 1 FROM user WHERE user = ?", (name,)).fetchone():
            raise Fail(f"user {name} already exists")
        conn.execute(
            "INSERT INTO user (id, user, pass, role, sync_topic, provisioned, created) VALUES (?,?,?,?,?,0,?)",
            (f"u_{name}", name, "$2a$10$" + "a" * 53, role, f"st_{name}", int(time.time())),
        )
        del pw
        return out(f"user {name} added with role {role}")
    pos = positional(rest)
    if sub in ("del", "remove", "rm"):
        user = find_user(conn, pos[0])
        if user["provisioned"]:
            raise Fail("cannot change or delete provisioned user")
        conn.execute("DELETE FROM user_access WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM user_token WHERE user_id = ?", (user["id"],))
        conn.execute("DELETE FROM user WHERE id = ?", (user["id"],))
        return out(f"user {pos[0]} removed")
    if sub == "change-pass":
        user = find_user(conn, pos[0])
        need_password()
        if user["provisioned"]:
            raise Fail("cannot change or delete provisioned user")
        return out(f"changed password for user {pos[0]}")
    if sub == "change-role":
        if len(pos) != 2 or pos[1] not in ("user", "admin"):
            raise Fail("usage: ntfy user change-role USERNAME ROLE")
        user = find_user(conn, pos[0])
        if user["provisioned"]:
            raise Fail("cannot change or delete provisioned user")
        conn.execute("UPDATE user SET role = ? WHERE id = ?", (pos[1], user["id"]))
        if pos[1] == "admin":
            conn.execute("DELETE FROM user_access WHERE user_id = ?", (user["id"],))
        return out(f"changed role for user {pos[0]} to {pos[1]}")
    raise Fail(f"unknown user command {sub}")


def access_cmd(conn: sqlite3.Connection, args: list[str]) -> None:
    pos = positional(args)
    if "--reset" in args:
        if not pos:
            conn.execute("DELETE FROM user_access")
            return out("reset access for all users")
        user = find_user(conn, pos[0])
        if len(pos) == 1:
            conn.execute("DELETE FROM user_access WHERE user_id = ?", (user["id"],))
            return out(f"reset access for user {pos[0]}")
        if not TOPIC_RE.match(pos[1]):
            raise Fail("invalid argument")
        conn.execute(
            "DELETE FROM user_access WHERE user_id = ? AND topic = ?", (user["id"], cli_topic_to_db(pos[1]))
        )
        return out(f"reset access for user {pos[0]} and topic {pos[1]}")
    if len(pos) == 1:
        find_user(conn, pos[0])
        return listing(conn, pos[0])
    if len(pos) != 3:
        raise Fail("invalid argument")
    user_name, topic, perm = pos
    user = find_user(conn, user_name)
    if perm not in PERMS:
        raise Fail("permission must be one of: read-write, read-only, write-only, or deny "
                   "(or the aliases: read, ro, write, wo, none)")
    if not TOPIC_RE.match(topic):
        raise Fail("invalid argument")
    read, write = PERMS[perm]
    conn.execute(
        "INSERT OR REPLACE INTO user_access (user_id, topic, read, write, owner_user_id, provisioned) "
        "VALUES (?,?,?,?,NULL,0)",
        (user["id"], cli_topic_to_db(topic), read, write),
    )
    if (read, write) == (0, 0):
        return out(f"revoked all access to topic {topic}")
    return out(f"granted {PHRASE[(read, write)]} access to topic {topic}")


def token_cmd(conn: sqlite3.Connection, args: list[str]) -> None:
    sub, rest = (args[0], args[1:]) if args else ("list", [])
    pos = positional(rest)
    if sub == "add":
        label, expires = "", 0
        for a in rest:
            if a.startswith("--label="):
                label = a.split("=", 1)[1]
            elif a.startswith("--expires="):
                value = a.split("=", 1)[1]
                if not re.fullmatch(r"[0-9]+[smhd]", value):
                    raise Fail("invalid argument")
                expires = int(time.time()) + int(value[:-1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[value[-1]]
        user = find_user(conn, pos[0])
        token = "tk_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=29))
        now = int(time.time())
        conn.execute(
            "INSERT INTO user_token (user_id, token, label, last_access, last_origin, expires, provisioned) "
            "VALUES (?,?,?,?,'0.0.0.0',?,0)",
            (user["id"], token, label, now, expires),
        )
        tail = "never expires" if not expires else f"expires {time.ctime(expires)}"
        return out(f"token {token} created for user {pos[0]}, {tail}")
    if sub in ("remove", "del", "rm"):
        user = find_user(conn, pos[0])
        row = conn.execute(
            "SELECT * FROM user_token WHERE user_id = ? AND token = ?", (user["id"], pos[1] if len(pos) > 1 else "")
        ).fetchone()
        if row is None:
            raise Fail("token not found")
        if row["provisioned"]:
            raise Fail("cannot change or delete provisioned token")
        conn.execute("DELETE FROM user_token WHERE user_id = ? AND token = ?", (user["id"], row["token"]))
        return out(f"token {row['token']} for user {pos[0]} removed")
    if sub == "list":
        if pos:
            find_user(conn, pos[0])
        rows = conn.execute(
            "SELECT u.user, k.* FROM user_token k JOIN user u ON u.id = k.user_id ORDER BY u.user"
        ).fetchall()
        rows = [r for r in rows if not pos or r["user"] == uname(pos[0])]
        if not rows:
            return out("no users with tokens")
        for r in rows:
            out(f"user {r['user']}")
            out(f"- {r['token']}, accessed from {r['last_origin']}")
        return None
    raise Fail(f"unknown token command {sub}")


def main() -> int:
    argv = sys.argv[1:]
    log = os.environ.get("FAKE_NTFY_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"argv": argv, "env_password": bool(os.environ.get("NTFY_PASSWORD"))}) + "\n")
    lock_file = os.environ.get("FAKE_NTFY_LOCK_ONCE")
    if lock_file and os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except FileNotFoundError:
            pass
        else:
            out("database is locked")
            return 1
    delay = float(os.environ.get("FAKE_NTFY_DELAY", "0") or 0)
    overlap = os.environ.get("FAKE_NTFY_OVERLAP_DIR")
    marker = None
    if overlap:
        marker = Path(overlap) / f"run-{os.getpid()}"
        if any(Path(overlap).glob("run-*")):
            (Path(overlap) / "OVERLAP").touch()
        marker.touch()
    try:
        path = os.environ.get("NTFY_AUTH_FILE")
        if not path:
            out("option database-url or auth-file not set; auth is unconfigured for this server")
            return 1
        if not Path(path).exists():
            make_auth_db(path)
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            run(conn, argv)
            conn.commit()
            if delay:
                time.sleep(delay)
        finally:
            conn.close()
        return 0
    except Fail as exc:
        out(str(exc))
        return 1
    finally:
        if marker is not None:
            marker.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
