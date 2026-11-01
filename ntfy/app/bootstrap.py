"""Start-time bootstrap: admin (D-04), options baseline (D-05), daily backup (D-14); never blocks ntfy."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field

from app import baseline
from app.context import Context, build_context
from app.contract import ApiError
from app.ntfycli import NtfyCliError


@dataclass
class BootstrapReport:
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"{len(self.actions)} action(s), {len(self.warnings)} warning(s)"


def wait_for_auth_db(ctx: Context, timeout: float = 60.0, interval: float = 0.5) -> bool:
    """Wait until the running server has created auth.db (the CLI refuses to work before that)."""
    deadline = time.monotonic() + timeout
    while True:
        if ctx.db.check_schema()["supported"]:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def ensure_admin(ctx: Context) -> list[str]:
    """Create admin_user with admin_password unless it exists; an existing user's password is never touched."""
    options = ctx.options
    if not options.admin_password:
        print("[bootstrap] admin_password is empty: admin user not created", flush=True)
        return []
    try:
        existing = {user["name"] for user in ctx.db.list_users()}
    except ApiError:
        existing = set()  # missing or unreadable auth.db counts as no users
    if options.admin_user in existing:
        return []
    try:
        ctx.cli.user_add(options.admin_user, options.admin_password, role="admin")
    except NtfyCliError as exc:
        if exc.code == "exists":
            return []
        raise
    ctx.origins.set_user(options.admin_user, "options")
    print(f"[bootstrap] admin user {options.admin_user} created", flush=True)
    return [f"admin user {options.admin_user} created"]


def _describe(report: baseline.BaselineReport) -> list[str]:
    actions = [f"user {name} created" for name in report.users_created]
    actions += [f"rule {user} {topic} {perm} set" for user, topic, perm in report.rules_set]
    actions += [f"password of {name} reset" for name in report.passwords_reset]
    actions += [f"{item} now owned by gui" for item in report.orphaned]
    return actions


def apply_options(ctx: Context) -> BootstrapReport:
    """Admin first, then the baseline; a failure in one step is a warning and the other still runs."""
    report = BootstrapReport()
    try:
        report.actions += ensure_admin(ctx)
    except Exception as exc:  # noqa: BLE001 - type and message only, never option values
        report.warnings.append(f"admin: {type(exc).__name__}: {exc}")
    try:
        result = baseline.apply_baseline(ctx)
        report.actions += _describe(result)
        report.warnings += result.warnings
    except Exception as exc:  # noqa: BLE001
        report.warnings.append(f"baseline: {type(exc).__name__}: {exc}")
    return report


def main() -> int:
    try:
        ctx = build_context()
    except Exception as exc:  # noqa: BLE001
        print(f"[bootstrap] cannot build context: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    try:
        if not wait_for_auth_db(ctx):
            print("[bootstrap] auth.db not ready after 60 s, skipping bootstrap", file=sys.stderr, flush=True)
            return 0
        try:
            backup = ctx.backups.create_daily()
            if backup:
                print(f"[bootstrap] daily backup {backup['name']} created", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] warning: daily backup failed: {type(exc).__name__}: {exc}", flush=True)
        report = apply_options(ctx)
        print(f"[bootstrap] done: {report.summary()}", flush=True)
        for warning in report.warnings:
            print(f"[bootstrap] warning: {warning}", flush=True)
    except Exception as exc:  # noqa: BLE001 - delivery must not depend on bootstrap; log type and message only
        print(f"[bootstrap] failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
