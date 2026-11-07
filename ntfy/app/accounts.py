"""User and ACL services with guardrails (D-12), origin ownership (D-05, D-08) and the role-change rule stash.

Every mutation holds `ctx.lock`, checks the schema first and validates input itself (ApiError, never ValueError).
The ntfy CLI reports success for several no-ops, so existence is pre-checked through the read-only DB.
Promoting a user to admin makes ntfy wipe the explicit rules of that user (spike ntfy-cli gotcha 1): they are stashed
in the origin sidecar (after a backup) and restored on demotion.
"""

from __future__ import annotations

from typing import Any

from app.contract import (
    PERMISSIONS,
    RESERVED_USERNAMES,
    TOPIC_PATTERN_RE,
    USERNAME_RE,
    AclRule,
    ApiError,
    User,
)

MAX_PASSWORD_BYTES = 72  # bcrypt input limit
ROLES = ("user", "admin")


# --- helpers -------------------------------------------------------------------------------------------------------


def _check_password(password: Any) -> None:
    if not isinstance(password, str) or not password:
        raise ApiError("bad_request", "password must not be empty")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ApiError("bad_request", f"password must be at most {MAX_PASSWORD_BYTES} bytes")


def _check_role(role: Any) -> None:
    if role not in ROLES:
        raise ApiError("bad_request", "role must be user or admin")


def _check_new_name(name: Any) -> None:
    if not isinstance(name, str) or name in RESERVED_USERNAMES or not USERNAME_RE.match(name):
        raise ApiError("bad_request", "invalid user name")


def _check_topic(topic: Any) -> None:
    if not isinstance(topic, str) or "%" in topic or not TOPIC_PATTERN_RE.match(topic):
        raise ApiError("bad_request", "invalid topic pattern")


def _protection(ctx: Any, rows: list[dict]) -> dict[str, str]:
    """name -> protected_reason for every protected user."""
    admins = [row["name"] for row in rows if row["role"] == "admin"]
    result: dict[str, str] = {}
    for row in rows:
        name = row["name"]
        if name == "everyone":
            result[name] = "anonymous"
        elif name == ctx.options.admin_user:
            result[name] = "options_admin"
        elif row["role"] == "admin" and admins == [name]:
            result[name] = "last_admin"
    return result


def _build_users(ctx: Any) -> list[User]:
    rows = ctx.db.list_users()
    protection = _protection(ctx, rows)
    acl_counts: dict[str, int] = {}
    for rule in ctx.db.list_acl():
        acl_counts[rule["user"]] = acl_counts.get(rule["user"], 0) + 1
    token_counts: dict[str, int] = {}
    for token in ctx.db.list_tokens():
        token_counts[token["user"]] = token_counts.get(token["user"], 0) + 1
    users: list[User] = []
    for row in rows:
        name = row["name"]
        reason = protection.get(name)
        users.append(
            {
                "name": name,
                "role": row["role"],
                "tier": row["tier"],
                "origin": ctx.origins.get_user(name),
                "provisioned": row["provisioned"],
                "protected": reason is not None,
                "protected_reason": reason,
                "acl_count": acl_counts.get(name, 0),
                "token_count": token_counts.get(name, 0),
            }
        )
    users.sort(key=lambda u: (u["name"] == "everyone", u["name"]))
    return users


def _get_user(ctx: Any, name: str) -> User:
    for user in _build_users(ctx):
        if user["name"] == name:
            return user
    raise ApiError("not_found", "user not found")


def _require_real_user(ctx: Any, name: Any) -> None:
    """The user must exist and must not be the anonymous user."""
    if not isinstance(name, str):
        raise ApiError("bad_request", "invalid user name")
    if name == "everyone":
        raise ApiError("bad_request", "not allowed for the anonymous user everyone")
    if not ctx.db.has_user(name):
        raise ApiError("not_found", "user not found")


def _rule(ctx: Any, row: dict) -> AclRule:
    return {
        "user": row["user"],
        "topic": row["topic"],
        "permission": row["permission"],
        "origin": ctx.origins.get_acl(row["user"], row["topic"]),
    }


# --- users ---------------------------------------------------------------------------------------------------------


def list_users(ctx: Any) -> list[User]:
    ctx.db.ensure_supported()
    return _build_users(ctx)


def create_user(ctx: Any, name: str, password: str, role: str = "user") -> User:
    with ctx.lock:
        ctx.db.ensure_supported()
        _check_new_name(name)
        _check_role(role)
        _check_password(password)
        if ctx.db.has_user(name):
            raise ApiError("conflict", "user already exists")
        ctx.cli.user_add(name, password, role)
        ctx.origins.set_user(name, "gui")
        return _get_user(ctx, name)


def change_password(ctx: Any, name: str, password: str) -> None:
    with ctx.lock:
        ctx.db.ensure_supported()
        _require_real_user(ctx, name)
        _check_password(password)
        ctx.cli.user_change_pass(name, password)


def delete_user(ctx: Any, name: str, confirm: str) -> None:
    with ctx.lock:
        ctx.db.ensure_supported()
        _require_real_user(ctx, name)
        user = _get_user(ctx, name)
        if user["protected"]:
            raise ApiError("protected", f"user is protected ({user['protected_reason']})")
        if confirm != name:
            raise ApiError("confirmation_required", "type the user name to confirm the deletion")
        ctx.backups.create("user-delete")
        ctx.cli.user_delete(name)
        ctx.origins.drop_user(name)


def change_role(ctx: Any, name: str, role: str) -> tuple[User, int]:
    """Returns (user, dropped_rules); dropped_rules is the number of rules stashed by a promotion."""
    with ctx.lock:
        ctx.db.ensure_supported()
        _check_role(role)
        _require_real_user(ctx, name)
        user = _get_user(ctx, name)
        if user["role"] == role:
            return user, 0
        if role == "user" and user["protected"]:
            raise ApiError("protected", f"user is protected ({user['protected_reason']})")
        if role == "admin":
            return _promote(ctx, name)
        return _demote(ctx, name)


def _promote(ctx: Any, name: str) -> tuple[User, int]:
    snapshot = ctx.db.snapshot_acl(name)
    if snapshot:
        ctx.backups.create("role-change")
    ctx.cli.user_change_role(name, "admin")
    if snapshot:
        ctx.origins.stash_acl(
            name,
            [
                {
                    "topic": row["topic"],
                    "permission": row["permission"],
                    "origin": ctx.origins.get_acl(name, row["topic"]),
                }
                for row in snapshot
            ],
        )
        for row in snapshot:
            ctx.origins.drop_acl(name, row["topic"])
    return _get_user(ctx, name), len(snapshot)


def _demote(ctx: Any, name: str) -> tuple[User, int]:
    ctx.cli.user_change_role(name, "user")
    pending = ctx.origins.pop_acl_stash(name)
    for index, rule in enumerate(pending):
        try:
            ctx.cli.access_set(name, rule["topic"], rule["permission"])
        except Exception:
            ctx.origins.stash_acl(name, pending[index:])  # keep what is not restored yet
            raise
        ctx.origins.set_acl(name, rule["topic"], rule["origin"])
    return _get_user(ctx, name), 0


# --- ACL rules -----------------------------------------------------------------------------------------------------


def list_rules(ctx: Any, user: str | None = None, topic: str | None = None) -> list[AclRule]:
    ctx.db.ensure_supported()
    rows = ctx.db.list_acl()
    if user is not None:
        rows = [row for row in rows if row["user"] == user]
    if topic is not None:
        rows = [row for row in rows if row["topic"] == topic]
    return [_rule(ctx, row) for row in rows]


def _find_rule(ctx: Any, user: str, topic: str) -> dict | None:
    for row in ctx.db.list_acl():
        if row["user"] == user and row["topic"] == topic:
            return row
    return None


def set_rule(ctx: Any, user: str, topic: str, permission: str) -> AclRule:
    with ctx.lock:
        ctx.db.ensure_supported()
        if permission not in PERMISSIONS:
            raise ApiError("bad_request", "permission must be one of rw, ro, wo, deny")
        _check_topic(topic)
        if not isinstance(user, str):
            raise ApiError("bad_request", "invalid user name")
        if user != "everyone":
            if not ctx.db.has_user(user):
                raise ApiError("not_found", "user not found")
            role = next((row["role"] for row in ctx.db.list_users() if row["name"] == user), "user")
            if role == "admin":
                raise ApiError("bad_request", "admin users have access to all topics; rules are not allowed")
        existing = _find_rule(ctx, user, topic)
        origin = "iac" if existing is not None and ctx.origins.get_acl(user, topic) == "iac" else "gui"
        ctx.cli.access_set(user, topic, permission)
        stored = _find_rule(ctx, user, topic)
        if stored is None:
            raise ApiError("ntfy_error", "rule was not stored")
        ctx.origins.set_acl(user, topic, origin)
        return _rule(ctx, stored)


def remove_rule(ctx: Any, user: str, topic: str) -> None:
    with ctx.lock:
        ctx.db.ensure_supported()
        if not isinstance(user, str) or not isinstance(topic, str):
            raise ApiError("bad_request", "user and topic are required")
        _check_topic(topic)
        if _find_rule(ctx, user, topic) is None:
            raise ApiError("not_found", "rule not found")
        ctx.cli.access_reset(user, topic)
        ctx.origins.drop_acl(user, topic)
