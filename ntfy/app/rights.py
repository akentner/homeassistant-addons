"""Effective-rights evaluator reproducing ntfy's authorization (verified against ntfy 2.36.0)."""

from __future__ import annotations

from typing import Any

from app.contract import (
    TOPIC_RE,
    ApiError,
    Effective,
    cli_topic_to_db,
    topic_match,
)

# auth_default_access -> (read, write) when no rule matches
DEFAULT_ACCESS = {
    "deny-all": (False, False),
    "read-only": (True, False),
    "write-only": (False, True),
    "read-write": (True, True),
}


def _rule(row: dict[str, Any], ctx: Any) -> dict[str, Any]:
    return {
        "user": row["user"],
        "topic": row["topic"],
        "permission": row["permission"],
        "origin": ctx.origins.get_acl(row["user"], row["topic"]),
    }


def effective(ctx: Any, user: str, topic: str) -> Effective:
    """Read/write rights of `user` (or `everyone`) on a concrete topic, with the deciding rule and all candidates."""
    ctx.db.ensure_supported()
    if not TOPIC_RE.match(topic):
        raise ApiError("bad_request", "topic must be a concrete topic name without wildcards")
    users = {row["name"]: row for row in ctx.db.list_users()}
    if user != "everyone" and user not in users:
        raise ApiError("not_found", f"user {user} does not exist")
    if user != "everyone" and users[user]["role"] == "admin":
        return {
            "user": user,
            "topic": topic,
            "read": True,
            "write": True,
            "source": {"kind": "admin", "rule": None},
            "candidates": [],
        }
    matching = [
        row
        for row in ctx.db.list_acl()
        if row["user"] in (user, "everyone") and topic_match(row["topic"], topic)
    ]
    # ntfy: own rules before everyone rules, longer stored pattern first, write-capable first
    matching.sort(
        key=lambda r: (
            1 if (r["user"] == "everyone" and user != "everyone") else 0,
            -len(cli_topic_to_db(r["topic"])),
            0 if r["write"] else 1,
        )
    )
    candidates = [_rule(row, ctx) for row in matching]
    if matching:
        first = matching[0]
        kind = "everyone-rule" if first["user"] == "everyone" else "user-rule"
        return {
            "user": user,
            "topic": topic,
            "read": bool(first["read"]),
            "write": bool(first["write"]),
            "source": {"kind": kind, "rule": candidates[0]},
            "candidates": candidates,
        }
    read, write = DEFAULT_ACCESS.get(ctx.options.auth_default_access, (False, False))
    return {
        "user": user,
        "topic": topic,
        "read": read,
        "write": write,
        "source": {"kind": "default", "rule": None},
        "candidates": [],
    }
