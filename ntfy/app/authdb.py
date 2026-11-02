"""Read-only view of ntfy's auth.db (contract C5).

Every read opens its own short-lived read-only connection, fetches all rows and closes it again: ntfy uses a rollback
journal, so a held read transaction would block CLI writes for about 5 seconds. This process never writes.

`last_access` of a token is lazy: ntfy batches the update (tens of seconds late) and a never-used token carries its
creation time, so it must never be presented as a live "last used" value.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.contract import (
    SUPPORTED_AUTH_SCHEMA,
    AclRow,
    ApiError,
    SchemaStatus,
    TokenRow,
    UserRow,
    db_topic_to_cli,
    db_user_to_api,
    perm_from_flags,
    token_id,
    token_prefix,
)


def _db_user(name: str) -> str:
    return "*" if name in ("everyone", "*") else name


class AuthDb:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=5.0)

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        if not self.path.is_file():
            raise ApiError("db_unavailable", "auth database does not exist yet")
        conn: sqlite3.Connection | None = None
        try:
            conn = self._connect()
            conn.row_factory = sqlite3.Row
            return conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            text = str(exc).lower()
            code = "locked" if "locked" in text or "busy" in text else "db_unavailable"
            raise ApiError(code, "auth database cannot be read") from exc
        except sqlite3.Error as exc:
            raise ApiError("db_unavailable", "auth database cannot be read") from exc
        finally:
            if conn is not None:
                conn.close()

    def check_schema(self) -> SchemaStatus:
        """Schema status {version, supported, error}; never raises."""
        if not self.path.is_file():
            return {"version": None, "supported": False, "error": "db_unavailable"}
        try:
            rows = self._query("SELECT version FROM schemaVersion WHERE id = 1")
        except ApiError as exc:
            if exc.code == "db_unavailable":
                # unreadable file or missing schemaVersion table: both mean this is not a supported ntfy DB
                return {"version": None, "supported": False, "error": "db_unsupported"}
            return {"version": None, "supported": False, "error": exc.code}
        version = int(rows[0]["version"]) if rows else None
        supported = version == SUPPORTED_AUTH_SCHEMA
        return {"version": version, "supported": supported, "error": None if supported else "db_unsupported"}

    def ensure_supported(self) -> None:
        status = self.check_schema()
        if status["error"] is None:
            return
        if status["error"] == "db_unavailable":
            raise ApiError("db_unavailable", "auth database is not available")
        if status["error"] == "locked":
            raise ApiError("locked", "auth database is locked")
        raise ApiError("db_unsupported", f"auth schema version {status['version']} is not supported")

    def list_users(self, include_hash: bool = False) -> list[UserRow]:
        """Users ordered by name; the anonymous user `*` appears as `everyone` (role anonymous)."""
        self.ensure_supported()
        rows = self._query(
            "SELECT u.user AS name, u.role AS role, u.provisioned AS provisioned, t.code AS tier, u.pass AS pass "
            "FROM user u LEFT JOIN tier t ON t.id = u.tier_id ORDER BY u.user"
        )
        result: list[UserRow] = []
        for row in rows:
            user: UserRow = {
                "name": db_user_to_api(row["name"]),
                "role": row["role"],
                "tier": row["tier"],
                "provisioned": bool(row["provisioned"]),
            }
            if include_hash:
                user["pass_hash"] = row["pass"]
            result.append(user)
        return result

    def _acl(self, user: str | None) -> list[AclRow]:
        self.ensure_supported()
        sql = (
            "SELECT u.user AS user, a.topic AS topic, a.read AS read, a.write AS write, a.provisioned AS provisioned "
            "FROM user_access a JOIN user u ON u.id = a.user_id"
        )
        params: tuple[Any, ...] = ()
        if user is not None:
            sql += " WHERE u.user = ?"
            params = (_db_user(user),)
        rows = self._query(sql, params)
        result: list[AclRow] = [
            {
                "user": db_user_to_api(row["user"]),
                "topic": db_topic_to_cli(row["topic"]),
                "permission": perm_from_flags(row["read"], row["write"]),
                "read": bool(row["read"]),
                "write": bool(row["write"]),
                "provisioned": bool(row["provisioned"]),
            }
            for row in rows
        ]
        result.sort(key=lambda r: (r["user"], r["topic"]))
        return result

    def list_acl(self) -> list[AclRow]:
        """All ACL rows with topics in CLI form (`%` is `*`, `\\_` is `_`), sorted by (user, topic)."""
        return self._acl(None)

    def snapshot_acl(self, user: str) -> list[AclRow]:
        """ACL rows of one user, used to re-apply rules after a role change (ntfy wipes them on admin)."""
        return self._acl(user)

    def _token_rows(self, user: str | None) -> list[sqlite3.Row]:
        self.ensure_supported()
        sql = (
            "SELECT u.user AS user, k.token AS token, k.label AS label, k.expires AS expires, "
            "k.last_access AS last_access, k.last_origin AS last_origin, k.provisioned AS provisioned "
            "FROM user_token k JOIN user u ON u.id = k.user_id"
        )
        params: tuple[Any, ...] = ()
        if user is not None:
            sql += " WHERE u.user = ?"
            params = (_db_user(user),)
        return self._query(sql + " ORDER BY u.user, k.last_access, k.label", params)

    def list_tokens(self, user: str | None = None) -> list[TokenRow]:
        """Token metadata; the value is read only to derive id and prefix and is never part of a row."""
        return [
            {
                "user": db_user_to_api(row["user"]),
                "token_id": token_id(row["token"]),
                "prefix": token_prefix(row["token"]),
                "label": row["label"],
                "expires": int(row["expires"]),
                "last_access": int(row["last_access"]),
                "last_origin": row["last_origin"],
                "provisioned": bool(row["provisioned"]),
            }
            for row in self._token_rows(user)
        ]

    def reveal_token(self, user: str, token_id_: str) -> str | None:
        """Full token value for a matching (user, id) pair, else None."""
        for row in self._token_rows(user):
            if token_id(row["token"]) == token_id_:
                return str(row["token"])
        return None

    def counts(self) -> dict[str, int]:
        """users (without the anonymous user), acl_rules, tokens."""
        self.ensure_supported()
        users = self._query("SELECT COUNT(*) AS n FROM user WHERE user != '*'")[0]["n"]
        acl = self._query("SELECT COUNT(*) AS n FROM user_access")[0]["n"]
        tokens = self._query("SELECT COUNT(*) AS n FROM user_token")[0]["n"]
        return {"users": int(users), "acl_rules": int(acl), "tokens": int(tokens)}

    def has_user(self, name: str) -> bool:
        self.ensure_supported()
        return bool(self._query("SELECT 1 FROM user WHERE user = ?", (_db_user(name),)))

    def size_bytes(self) -> int | None:
        try:
            return self.path.stat().st_size
        except OSError:
            return None
