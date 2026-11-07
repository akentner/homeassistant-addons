"""Token lifecycle services (D-13): values stay hidden except in the create response and on explicit reveal."""

from __future__ import annotations

import logging
from typing import Any

from app.contract import (
    DURATION_RE,
    LABEL_RE,
    ApiError,
    TokenMeta,
    token_id,
    token_meta_from_row,
)

audit = logging.getLogger("ntfy.audit")


def _require_user(ctx: Any, user: str) -> None:
    if user == "everyone":
        raise ApiError("bad_request", "tokens cannot belong to everyone")
    if not user or not ctx.db.has_user(user):
        raise ApiError("not_found", f"user {user} does not exist")


def _meta(ctx: Any, row: Any) -> TokenMeta:
    return token_meta_from_row(row, ctx.origins.get_token(row["user"], row["token_id"]))


def list_tokens(ctx: Any, user: str | None = None) -> list[TokenMeta]:
    """Token metadata, never values; optionally filtered by user."""
    ctx.db.ensure_supported()
    return [_meta(ctx, row) for row in ctx.db.list_tokens(user)]


def create_token(ctx: Any, user: str, label: str | None, expires: str | None) -> dict[str, Any]:
    """Create a token; the returned dict is a TokenMeta plus `value` (the only time it is returned on create)."""
    with ctx.lock:
        ctx.db.ensure_supported()
        _require_user(ctx, user)
        if label is not None and not LABEL_RE.match(label):
            raise ApiError("bad_request", "invalid label")
        if expires is not None and not DURATION_RE.match(expires):
            raise ApiError("bad_request", "invalid expiry duration, use e.g. 30m, 12h or 7d")
        try:
            value = ctx.cli.token_add(user, label or None, expires or None)
        except ValueError as exc:
            raise ApiError("bad_request", str(exc)) from exc
        tid = token_id(value)
        ctx.origins.set_token(user, tid, "gui")
        row = next((r for r in ctx.db.list_tokens(user) if r["token_id"] == tid), None)
        if row is None:
            raise ApiError("ntfy_error", "created token not found in the database")
        result: dict[str, Any] = dict(_meta(ctx, row))
        result["value"] = value
        return result


def reveal_token(ctx: Any, user: str, token_id_: str) -> str:
    """Full token value on demand; audit-logged without the value."""
    ctx.db.ensure_supported()
    value = ctx.db.reveal_token(user, token_id_)
    if value is None:
        raise ApiError("not_found", "token not found")
    audit.info("token revealed user=%s id=%s", user, token_id_)
    return str(value)


def revoke_token(ctx: Any, user: str, token_id_: str) -> None:
    """Resolve the id to the value server-side, remove through the CLI and drop the origin record."""
    with ctx.lock:
        ctx.db.ensure_supported()
        value = ctx.db.reveal_token(user, token_id_)
        if value is None:
            raise ApiError("not_found", "token not found")
        try:
            ctx.cli.token_remove(user, value)
        except ValueError as exc:
            raise ApiError("bad_request", str(exc)) from exc
        ctx.origins.drop_token(user, token_id_)
        audit.info("token revoked user=%s id=%s", user, token_id_)
