"""Builder for an ntfy auth.db (schema version 10) for tests; DDL trimmed from the ntfy 2.36.0 spike."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.contract import cli_topic_to_db

DDL = """
CREATE TABLE tier (
  id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  messages_limit INT NOT NULL, messages_expiry_duration INT NOT NULL, emails_limit INT NOT NULL,
  calls_limit INT NOT NULL, reservations_limit INT NOT NULL, attachment_file_size_limit INT NOT NULL,
  attachment_total_size_limit INT NOT NULL, attachment_expiry_duration INT NOT NULL,
  attachment_bandwidth_limit INT NOT NULL, stripe_monthly_price_id TEXT, stripe_yearly_price_id TEXT
);
CREATE TABLE user (
  id TEXT PRIMARY KEY,
  tier_id TEXT,
  user TEXT NOT NULL,
  pass TEXT NOT NULL,
  role TEXT CHECK (role IN ('anonymous','admin','user')) NOT NULL,
  prefs JSON NOT NULL DEFAULT '{}',
  sync_topic TEXT NOT NULL,
  provisioned INT NOT NULL,
  stats_messages INT NOT NULL DEFAULT 0, stats_emails INT NOT NULL DEFAULT 0, stats_calls INT NOT NULL DEFAULT 0,
  stripe_customer_id TEXT, stripe_subscription_id TEXT, stripe_subscription_status TEXT,
  stripe_subscription_interval TEXT, stripe_subscription_paid_until INT, stripe_subscription_cancel_at INT,
  created INT NOT NULL,
  deleted INT,
  FOREIGN KEY (tier_id) REFERENCES tier (id)
);
CREATE UNIQUE INDEX idx_user ON user (user);
CREATE TABLE user_access (
  user_id TEXT NOT NULL,
  topic TEXT NOT NULL,
  read INT NOT NULL, write INT NOT NULL,
  owner_user_id INT,
  provisioned INT NOT NULL,
  PRIMARY KEY (user_id, topic)
);
CREATE TABLE user_token (
  user_id TEXT NOT NULL,
  token TEXT NOT NULL,
  label TEXT NOT NULL,
  last_access INT NOT NULL,
  last_origin TEXT NOT NULL,
  expires INT NOT NULL,
  provisioned INT NOT NULL,
  PRIMARY KEY (user_id, token)
);
CREATE UNIQUE INDEX idx_user_token ON user_token (token);
CREATE TABLE schemaVersion (id INT PRIMARY KEY, version INT NOT NULL, min_version INT NOT NULL);
"""

FILLER_HASH = "$2a$10$" + "a" * 53
_FLAGS = {"rw": (1, 1), "ro": (1, 0), "wo": (0, 1), "deny": (0, 0)}


def _connect(path: Path | str) -> sqlite3.Connection:
    return sqlite3.connect(str(path))


def make_auth_db(path: Path | str, version: int = 10) -> Path:
    """Create the schema, the anonymous user and the schemaVersion row (id 1, `version`, min_version 1)."""
    conn = _connect(path)
    try:
        conn.executescript(DDL)
        conn.execute(
            "INSERT INTO user (id, user, pass, role, sync_topic, provisioned, created) "
            "VALUES ('u_everyone', '*', '', 'anonymous', 'st_everyone', 0, 0)"
        )
        conn.execute("INSERT INTO schemaVersion (id, version, min_version) VALUES (1, ?, 1)", (version,))
        conn.commit()
    finally:
        conn.close()
    return Path(path)


def _user_id(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute("SELECT id FROM user WHERE user = ?", ("*" if name == "everyone" else name,)).fetchone()
    if row is None:
        raise KeyError(name)
    return str(row[0])


def add_user(
    path: Path | str, name: str, role: str = "user", tier_code: str | None = None, pass_hash: str = FILLER_HASH,
    provisioned: int = 0,
) -> None:
    conn = _connect(path)
    try:
        tier_id = None
        if tier_code:
            conn.execute(
                "INSERT OR IGNORE INTO tier VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, NULL, NULL)",
                (f"ti_{tier_code}", tier_code, tier_code.title()),
            )
            tier_id = f"ti_{tier_code}"
        conn.execute(
            "INSERT INTO user (id, tier_id, user, pass, role, sync_topic, provisioned, created) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (f"u_{name}", tier_id, name, pass_hash, role, f"st_{name}", provisioned),
        )
        conn.commit()
    finally:
        conn.close()


def add_acl(path: Path | str, user: str, topic_cli: str, permission: str, provisioned: int = 0) -> None:
    read, write = _FLAGS[permission]
    conn = _connect(path)
    try:
        conn.execute(
            "INSERT INTO user_access (user_id, topic, read, write, owner_user_id, provisioned) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (_user_id(conn, user), cli_topic_to_db(topic_cli), read, write, provisioned),
        )
        conn.commit()
    finally:
        conn.close()


def add_token(
    path: Path | str, user: str, token: str, label: str = "", expires: int = 0, last_access: int = 0,
    provisioned: int = 0,
) -> None:
    conn = _connect(path)
    try:
        conn.execute(
            "INSERT INTO user_token (user_id, token, label, last_access, last_origin, expires, provisioned) "
            "VALUES (?, ?, ?, ?, '0.0.0.0', ?, ?)",
            (_user_id(conn, user), token, label, last_access, expires, provisioned),
        )
        conn.commit()
    finally:
        conn.close()
