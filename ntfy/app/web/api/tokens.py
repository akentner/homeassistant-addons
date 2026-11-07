"""Token routes (contract C10): list, create, reveal on demand, revoke."""

from __future__ import annotations

from typing import Any

from app import tokens
from app.contract import ApiError
from app.web.server import Request, Router


def _text(value: Any, name: str, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise ApiError("bad_request", f"{name} is required")
        return None
    if not isinstance(value, str) or (required and not value):
        raise ApiError("bad_request", f"{name} must be a non-empty string" if required else f"{name} must be a string")
    return value


def register(router: Router, ctx: Any) -> None:
    def list_all(req: Request) -> Any:
        return {"tokens": tokens.list_tokens(ctx, req.arg("user") or None)}

    def create(req: Request) -> Any:
        body = req.body()
        user = _text(body.get("user"), "user")
        label = _text(body.get("label"), "label", required=False)
        expires = _text(body.get("expires"), "expires", required=False)
        return 201, {"token": tokens.create_token(ctx, user or "", label, expires)}

    def reveal(req: Request) -> Any:
        body = req.body()
        user = _text(body.get("user"), "user")
        tid = _text(body.get("id"), "id")
        return {"value": tokens.reveal_token(ctx, user or "", tid or "")}

    def revoke(req: Request) -> Any:
        user, tid = req.arg("user"), req.arg("id")
        if not user or not tid:
            raise ApiError("bad_request", "user and id are required")
        tokens.revoke_token(ctx, user, tid)
        return None

    router.add("GET", "/api/tokens", list_all)
    router.add("POST", "/api/tokens", create)
    router.add("POST", "/api/tokens/reveal", reveal)
    router.add("DELETE", "/api/tokens", revoke)
