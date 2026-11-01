"""Guarded reset routes (contract C10, D-11): ACLs, message cache and everything, each with a typed phrase."""

from __future__ import annotations

from typing import Any, Callable

from app import maintenance
from app.contract import ApiError
from app.web.server import Request, Router


def _handler(ctx: Any, name: str) -> Callable[[Request], dict[str, Any]]:
    def handle(req: Request) -> dict[str, Any]:
        confirm = req.body().get("confirm")
        if not isinstance(confirm, str):
            raise ApiError("bad_request", "confirm must be a string")
        return getattr(maintenance, name)(ctx, confirm)

    return handle


def register(router: Router, ctx: Any) -> None:
    router.add("POST", "/api/reset/acls", _handler(ctx, "reset_acls"))
    router.add("POST", "/api/reset/cache", _handler(ctx, "clear_cache"))
    router.add("POST", "/api/reset/everything", _handler(ctx, "reset_everything"))
