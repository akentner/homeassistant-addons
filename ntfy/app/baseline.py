"""Options baseline (D-05, D-06, D-08, D-18): additive users and rules from `baseline_users`, never a delete.

Passwords reach the CLI only through its environment; log lines and warnings never contain them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.context import Context
from app.contract import ApiError
from app.ntfycli import NtfyCliError


@dataclass
class BaselineReport:
    users_created: list[str] = field(default_factory=list)
    rules_set: list[tuple[str, str, str]] = field(default_factory=list)
    rules_kept: list[tuple[str, str]] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passwords_reset: list[str] = field(default_factory=list)


def _log(message: str) -> None:
    print(f"[baseline] {message}", flush=True)


def _warn(report: BaselineReport, message: str) -> None:
    report.warnings.append(message)
    print(f"[baseline] warning: {message}", flush=True)


def apply_baseline(ctx: Context) -> BaselineReport:
    report = BaselineReport()
    options = ctx.options
    with ctx.lock:
        try:
            roles = {user["name"]: user["role"] for user in ctx.db.list_users()}
            rules = {(row["user"], row["topic"]): row["permission"] for row in ctx.db.list_acl()}
        except ApiError as exc:
            if exc.code != "db_unavailable":
                raise
            roles, rules = {}, {}

        named_users: set[str] = set()
        named_rules: set[tuple[str, str]] = set()

        for entry in options.baseline_users:
            name = entry.username
            if name == options.admin_user:
                _warn(report, f"entry {name} names the admin user and is ignored")
                continue
            named_users.add(name)
            try:
                _apply_entry(ctx, report, entry, roles, rules, named_rules)
            except (NtfyCliError, ValueError) as exc:
                _warn(report, f"entry {name} failed: {exc}")

        _orphan(ctx, report, named_users, named_rules)
    return report


def _apply_entry(ctx, report, entry, roles, rules, named_rules) -> None:
    name = entry.username
    existed = name in roles
    if not existed:
        try:
            ctx.cli.user_add(name, entry.password, role="user")
        except NtfyCliError as exc:
            if exc.code != "exists":
                raise
            existed = True  # created concurrently: treat like an existing user
            roles[name] = "user"
        else:
            roles[name] = "user"
            ctx.origins.set_user(name, "options")
            report.users_created.append(name)
            _log(f"user {name} created")
    if roles[name] == "admin":
        _warn(report, f"user {name} has the admin role: baseline gets no rules and no password reset")
        return
    if existed and options_overwrite(ctx):
        ctx.cli.user_change_pass(name, entry.password)
        report.passwords_reset.append(name)
        _log(f"password of user {name} set again (baseline_overwrite_passwords)")
    if not entry.topic:
        return
    permission = "rw" if entry.write_access else "ro"
    key = (name, entry.topic)
    named_rules.add(key)
    current = rules.get(key)
    if current is None:
        ctx.cli.access_set(name, entry.topic, permission)
        rules[key] = permission
        ctx.origins.set_acl(name, entry.topic, "options")
        report.rules_set.append((name, entry.topic, permission))
        _log(f"rule {name} {entry.topic} {permission} set")
    elif ctx.origins.get_acl(name, entry.topic) == "options":
        if current != permission:
            ctx.cli.access_set(name, entry.topic, permission)
            rules[key] = permission
            report.rules_set.append((name, entry.topic, permission))
            _log(f"rule {name} {entry.topic} {permission} re-synced")
    else:
        report.rules_kept.append(key)
        _log(f"rule {name} {entry.topic} kept (owned by {ctx.origins.get_acl(name, entry.topic)})")


def options_overwrite(ctx: Context) -> bool:
    return bool(ctx.options.baseline_overwrite_passwords)


def _orphan(ctx, report, named_users, named_rules) -> None:
    """Records still owned by `options` that the current baseline no longer names become `gui`."""
    admin = ctx.options.admin_user
    snap = ctx.origins.snapshot()
    for user, origin in snap["users"].items():
        if origin == "options" and user != admin and user not in named_users:
            ctx.origins.set_user(user, "gui")
            report.orphaned.append(user)
    for user, topics in snap["acls"].items():
        for topic, origin in topics.items():
            if origin == "options" and (user, topic) not in named_rules:
                ctx.origins.set_acl(user, topic, "gui")
                report.orphaned.append(f"{user}:{topic}")
    for item in report.orphaned:
        _log(f"{item} left the options and is now owned by gui")
