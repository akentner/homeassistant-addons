"""GET /api/users, minimal tracer version (24-06 replaces it with the full user API)."""

from __future__ import annotations

from typing import Any

from app.web.server import Request, Router


def register(router: Router, ctx: Any) -> None:
    def list_users(_req: Request) -> dict[str, Any]:
        users = [
            {
                "name": row["name"],
                "role": row["role"],
                "tier": row["tier"],
                "origin": "gui",
                "provisioned": row["provisioned"],
                "protected": False,
                "protected_reason": None,
                "acl_count": 0,
                "token_count": 0,
            }
            for row in ctx.db.list_users()
        ]
        return {"users": users}

    router.add("GET", "/api/users", list_users)
