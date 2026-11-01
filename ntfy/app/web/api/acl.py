"""ACL endpoints (contract C10): list, set and remove rules."""

from __future__ import annotations

from typing import Any

from app import accounts
from app.contract import ApiError
from app.web.server import Request, Router


def _required(req: Request, name: str) -> str:
    value = req.arg(name)
    if not value:
        raise ApiError("bad_request", f"query parameter {name} is required")
    return value


def register(router: Router, ctx: Any) -> None:
    def list_acl(req: Request) -> dict[str, Any]:
        return {"rules": accounts.list_rules(ctx, user=req.arg("user") or None, topic=req.arg("topic") or None)}

    def put_acl(req: Request) -> dict[str, Any]:
        body = req.body()
        unknown = set(body) - {"user", "topic", "permission"}
        if unknown:
            raise ApiError("bad_request", f"unknown field: {sorted(unknown)[0]}")
        values = []
        for key in ("user", "topic", "permission"):
            if not isinstance(body.get(key), str) or not body[key]:
                raise ApiError("bad_request", f"{key} is required")
            values.append(body[key])
        return {"rule": accounts.set_rule(ctx, *values)}

    def delete_acl(req: Request) -> None:
        accounts.remove_rule(ctx, _required(req, "user"), _required(req, "topic"))

    router.add("GET", "/api/acl", list_acl)
    router.add("PUT", "/api/acl", put_acl)
    router.add("DELETE", "/api/acl", delete_acl)
