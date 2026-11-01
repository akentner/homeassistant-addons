"""Bootstrap (24-09): admin, baseline wiring, daily backup, failure isolation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app import bootstrap
from app.bootstrap import apply_options, ensure_admin
from app.context import build_context
from helpers.ctx import FAKE_NTFY, make_context, write_options
from helpers.ntfy_db import make_auth_db

ADMIN_PW = "admin-pw-123"
BASE_PW = "base-pw-456"


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_NTFY_LOG", str(path))
    return path


def argvs(path):
    if not path.exists():
        return []
    return [json.loads(line)["argv"] for line in path.read_text().splitlines()]


def test_ensure_admin_creates_with_origin_once(tmp_path, log_path):
    ctx = make_context(tmp_path, admin_user="root", admin_password=ADMIN_PW)
    assert ensure_admin(ctx) == ["admin user root created"]
    assert {u["name"]: u["role"] for u in ctx.db.list_users()}["root"] == "admin"
    assert ctx.origins.get_user("root") == "options"
    count = len(argvs(log_path))
    assert ensure_admin(ctx) == []
    assert len(argvs(log_path)) == count


def test_empty_password_skips_with_log(tmp_path, capsys, log_path):
    ctx = make_context(tmp_path, admin_user="root", admin_password="")
    assert ensure_admin(ctx) == []
    out = capsys.readouterr().out
    assert "admin_password" in out
    assert argvs(log_path) == []


def test_existing_admin_password_not_touched(tmp_path, log_path):
    ctx = make_context(tmp_path, admin_user="root", admin_password=ADMIN_PW)
    ctx.cli.user_add("root", "changed-pw-9", role="admin")
    log_path.unlink(missing_ok=True)
    assert ensure_admin(ctx) == []
    assert not any("change-pass" in a for a in argvs(log_path))


def test_apply_options_runs_both_steps(tmp_path):
    ctx = make_context(
        tmp_path, admin_user="root", admin_password=ADMIN_PW,
        baseline_users=[{"username": "alice", "password": BASE_PW, "topic": "t1", "write_access": True}],
    )
    report = apply_options(ctx)
    assert report.warnings == []
    assert "admin user root created" in report.actions
    assert "user alice created" in report.actions
    assert "rule alice t1 rw set" in report.actions


def test_failing_admin_step_does_not_stop_baseline(tmp_path):
    ctx = make_context(
        tmp_path, admin_user="-bad", admin_password=ADMIN_PW,
        baseline_users=[{"username": "alice", "password": BASE_PW, "topic": "", "write_access": True}],
    )
    report = apply_options(ctx)
    assert len(report.warnings) == 1 and report.warnings[0].startswith("admin:")
    assert "user alice created" in report.actions


def test_failing_baseline_step_is_warning(tmp_path, monkeypatch):
    ctx = make_context(tmp_path, admin_user="root", admin_password=ADMIN_PW)

    def boom(_ctx):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(bootstrap.baseline, "apply_baseline", boom)
    report = apply_options(ctx)
    assert "admin user root created" in report.actions
    assert report.warnings == ["baseline: RuntimeError: kaputt"]


def _env(tmp_path, monkeypatch, **overrides):
    paths = write_options(tmp_path, **overrides)
    monkeypatch.setenv("NTFY_DATA_DIR", str(paths.data_dir))
    monkeypatch.setenv("NTFY_OPTIONS", str(paths.options_file))
    monkeypatch.setenv("NTFY_BIN", str(FAKE_NTFY))
    return paths


def _fixed_clock(monkeypatch, when: datetime):
    real = bootstrap.build_context

    def build(*args, **kwargs):
        ctx = real(*args, **kwargs)
        ctx.backups._clock = lambda: when.timestamp()
        return ctx

    monkeypatch.setattr(bootstrap, "build_context", build)


def test_main_daily_backup_once_per_day(tmp_path, monkeypatch):
    paths = _env(tmp_path, monkeypatch, admin_user="root", admin_password=ADMIN_PW)
    make_auth_db(paths.auth_db)
    _fixed_clock(monkeypatch, datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc))
    assert bootstrap.main() == 0
    first = [b for b in build_context(paths).backups.list()]
    assert [b["reason"] for b in first] == ["daily"]
    # the backup was taken before the admin was created
    import sqlite3
    conn = sqlite3.connect(paths.backup_dir / first[0]["name"])
    assert conn.execute("SELECT COUNT(*) FROM user WHERE user = 'root'").fetchone()[0] == 0
    conn.close()
    assert bootstrap.main() == 0
    assert len(build_context(paths).backups.list()) == 1


def test_main_without_auth_db_makes_no_backup(tmp_path, monkeypatch):
    paths = _env(tmp_path, monkeypatch, admin_user="root", admin_password=ADMIN_PW)
    monkeypatch.setattr(bootstrap, "wait_for_auth_db", lambda ctx, *a, **k: True)
    assert bootstrap.main() == 0
    assert not paths.backup_dir.exists() or list(paths.backup_dir.iterdir()) == []


def test_main_returns_zero_for_missing_cli(tmp_path, monkeypatch, capsys):
    paths = _env(tmp_path, monkeypatch, admin_user="root", admin_password=ADMIN_PW)
    make_auth_db(paths.auth_db)
    monkeypatch.setenv("NTFY_BIN", str(tmp_path / "does-not-exist"))
    assert bootstrap.main() == 0
    assert "warning" in capsys.readouterr().out


def test_main_output_has_no_passwords(tmp_path, monkeypatch, capsys, log_path):
    paths = _env(
        tmp_path, monkeypatch, admin_user="root", admin_password=ADMIN_PW,
        baseline_users=[{"username": "alice", "password": BASE_PW, "topic": "t1", "write_access": True}],
    )
    make_auth_db(paths.auth_db)
    assert bootstrap.main() == 0
    captured = capsys.readouterr()
    for secret in (ADMIN_PW, BASE_PW):
        assert secret not in captured.out + captured.err
        assert secret not in log_path.read_text()


def test_main_invalid_options_returns_one(tmp_path, monkeypatch):
    paths = _env(tmp_path, monkeypatch)
    paths.options_file.write_text("{not json", encoding="utf-8")
    assert bootstrap.main() == 1


def test_reset_everything_reapplies(tmp_path):
    ctx = make_context(
        tmp_path, admin_user="root", admin_password=ADMIN_PW,
        baseline_users=[{"username": "alice", "password": BASE_PW, "topic": "t1", "write_access": True}],
    )
    apply_options(ctx)
    ctx.cli.user_delete("root")
    ctx.cli.user_delete("alice")
    ctx.origins.clear_all()
    report = apply_options(ctx)
    assert "admin user root created" in report.actions
    assert "user alice created" in report.actions
    assert {u["name"] for u in ctx.db.list_users()} >= {"root", "alice"}
