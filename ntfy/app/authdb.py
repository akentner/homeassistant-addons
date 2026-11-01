"""Read-only view of ntfy's auth.db (contract C5). Core of plan 24-01; 24-02 completes it.

Every read opens its own short-lived read-only connection and closes it again: ntfy uses a rollback journal, so a held
read transaction would block CLI writes for about 5 seconds. This process never writes to the database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.contract import SUPPORTED_AUTH_SCHEMA, ApiError, db_user_to_api


class AuthDb:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        if not self.path.is_file():
            raise ApiError("db_unavailable", "auth database does not exist yet")
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=2.0)
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

    def check_schema(self) -> dict[str, Any]:
        """SchemaStatus: {version, supported, error}; never raises."""
        try:
            rows = self._query("SELECT version FROM schemaVersion WHERE id = 1")
        except ApiError as exc:
            return {"version": None, "supported": False, "error": exc.code}
        version = int(rows[0]["version"]) if rows else None
        supported = version == SUPPORTED_AUTH_SCHEMA
        return {"version": version, "supported": supported, "error": None if supported else "db_unsupported"}

    def ensure_supported(self) -> None:
        status = self.check_schema()
        if status["error"] == "db_unavailable":
            raise ApiError("db_unavailable", "auth database is not available")
        if not status["supported"]:
            raise ApiError("db_unsupported", f"auth schema version {status['version']} is not supported")

    def list_users(self) -> list[dict[str, Any]]:
        """UserRow list ordered by name; the anonymous user `*` appears as `everyone`."""
        self.ensure_supported()
        rows = self._query(
            "SELECT u.user AS name, u.role AS role, u.provisioned AS provisioned, t.code AS tier "
            "FROM user u LEFT JOIN tier t ON t.id = u.tier_id ORDER BY u.user"
        )
        return [
            {
                "name": db_user_to_api(row["name"]),
                "role": row["role"],
                "tier": row["tier"],
                "provisioned": bool(row["provisioned"]),
            }
            for row in rows
        ]

    def size_bytes(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0
