"""User endpoints (contract C10): list, create, detail, change password/role, delete."""

from __future__ import annotations

from typing import Any

from app import accounts
from app.contract import ApiError, token_meta_from_row
from app.web.server import Request, Router


def _strict_body(req: Request, allowed: set[str]) -> dict[str, Any]:
    body = req.body()
    unknown = set(body) - allowed
    if unknown:
        raise ApiError("bad_request", f"unknown field: {sorted(unknown)[0]}")
    return body


def _string(body: dict[str, Any], key: str, required: bool = True) -> str | None:
    if key not in body:
        if required:
            raise ApiError("bad_request", f"{key} is required")
        return None
    value = body[key]
    if not isinstance(value, str):
        raise ApiError("bad_request", f"{key} must be a string")
    return value


def register(router: Router, ctx: Any) -> None:
    def list_users(_req: Request) -> dict[str, Any]:
        return {"users": accounts.list_users(ctx)}

    def create_user(req: Request) -> tuple[int, dict[str, Any]]:
        body = _strict_body(req, {"name", "password", "role"})
        name = _string(body, "name")
        password = _string(body, "password")
        role = _string(body, "role", required=False) or "user"
        assert name is not None and password is not None
        return 201, {"user": accounts.create_user(ctx, name, password, role)}

    def user_detail(req: Request) -> dict[str, Any]:
        name = req.params["name"]
        user = next((u for u in accounts.list_users(ctx) if u["name"] == name), None)
        if user is None:
            raise ApiError("not_found", "user not found")
        tokens = [
            token_meta_from_row(row, ctx.origins.get_token(name, row["token_id"]))
            for row in ctx.db.list_tokens(name)
        ]
        return {"user": user, "acl": accounts.list_rules(ctx, user=name), "tokens": tokens}

    def patch_user(req: Request) -> dict[str, Any]:
        name = req.params["name"]
        body = _strict_body(req, {"password", "role"})
        if not body:
            raise ApiError("bad_request", "password or role is required")
        password = _string(body, "password", required=False)
        role = _string(body, "role", required=False)
        if password is not None:
            accounts.change_password(ctx, name, password)
        dropped = 0
        if role is not None:
            user, dropped = accounts.change_role(ctx, name, role)
        else:
            user = next(u for u in accounts.list_users(ctx) if u["name"] == name)
        return {"user": user, "dropped_rules": dropped}

    def delete_user(req: Request) -> None:
        body = _strict_body(req, {"confirm"})
        confirm = _string(body, "confirm", required=False)
        accounts.delete_user(ctx, req.params["name"], confirm or "")

    router.add("GET", "/api/users", list_users)
    router.add("POST", "/api/users", create_user)
    router.add("GET", "/api/users/{name}", user_detail)
    router.add("PATCH", "/api/users/{name}", patch_user)
    router.add("DELETE", "/api/users/{name}", delete_user)
