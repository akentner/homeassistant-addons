"""Start-time bootstrap (D-04): create the admin from the options when it is missing. 24-09 extends apply_options."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

from app.context import Context, build_context
from app.contract import ApiError
from app.ntfycli import NtfyCliError


@dataclass
class BootstrapReport:
    admin_created: bool = False
    admin_existed: bool = False
    notes: list[str] = field(default_factory=list)


def wait_for_auth_db(ctx: Context, timeout: float = 60.0, interval: float = 0.5) -> bool:
    """Wait until the running server has created auth.db (the CLI refuses to work before that)."""
    deadline = time.monotonic() + timeout
    while True:
        if ctx.db.check_schema()["supported"]:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def ensure_admin(ctx: Context) -> BootstrapReport:
    """Create admin_user with admin_password unless it exists; an existing user's password is never touched."""
    report = BootstrapReport()
    options = ctx.options
    if not options.admin_password:
        print("[bootstrap] admin_password is empty: admin user not created", flush=True)
        report.notes.append("admin_password empty")
        return report
    try:
        existing = {user["name"] for user in ctx.db.list_users()}
    except ApiError:
        existing = set()  # missing or unreadable auth.db counts as no users
    if options.admin_user in existing:
        report.admin_existed = True
        return report
    try:
        ctx.cli.user_add(options.admin_user, options.admin_password, role="admin")
    except NtfyCliError as exc:
        if exc.code == "exists":
            report.admin_existed = True
            return report
        raise
    report.admin_created = True
    print(f"[bootstrap] admin user {options.admin_user} created", flush=True)
    return report


def apply_options(ctx: Context) -> BootstrapReport:
    """Apply the options baseline; this plan only ensures the admin."""
    return ensure_admin(ctx)


def main() -> int:
    try:
        ctx = build_context()
        if not wait_for_auth_db(ctx):
            print("[bootstrap] auth.db not ready after 60 s, skipping bootstrap", file=sys.stderr, flush=True)
            return 0
        apply_options(ctx)
    except Exception as exc:  # noqa: BLE001 - delivery must not depend on bootstrap; log type and message only
        print(f"[bootstrap] failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
