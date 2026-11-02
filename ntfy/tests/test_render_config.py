"""Tests for app.render_config: options to server.yml (contract C3)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

from app.contract import Options, Paths, load_options, parse_options
from app.render_config import main, render_server_yml, write_server_yml


def render(tmp_path: Path, **overrides: object) -> str:
    base = {**{"admin_password": "adminpw", "baseline_overwrite_passwords": True}, **overrides}
    options = parse_options(base)
    return render_server_yml(options, Paths.for_dir(tmp_path))


def test_defaults(tmp_path: Path) -> None:
    text = render(tmp_path)
    assert 'web-root: "/"' in text
    assert 'listen-http: ":8000"' in text
    assert f'auth-file: "{tmp_path}/auth.db"' in text
    assert f'cache-file: "{tmp_path}/cache.db"' in text
    assert "enable-login: true" in text
    assert "enable-signup: false" in text
    assert "attachment-cache-dir" in text


def test_web_ui_disabled(tmp_path: Path) -> None:
    assert 'web-root: "disable"' in render(tmp_path, enable_web_ui=False)


def test_attachments_disabled_omit_every_key(tmp_path: Path) -> None:
    keys = [line.split(":")[0] for line in render(tmp_path, attachments_enabled=False).splitlines()]
    assert not [key for key in keys if key.startswith("attachment")]


def test_empty_optional_limit_is_omitted(tmp_path: Path) -> None:
    text = render(tmp_path, attachment_total_size_limit="", attachment_expiry_duration=None)
    assert "attachment-total-size-limit" not in text
    assert "attachment-expiry-duration" not in text
    assert "attachment-file-size-limit" in text


def test_no_secret_or_option_name_in_output(tmp_path: Path) -> None:
    text = render(tmp_path, baseline_users=[{"username": "u", "password": "basepw", "topic": "t", "write_access": True}])
    for forbidden in ("adminpw", "basepw", "baseline_overwrite_passwords", "password"):
        assert forbidden not in text


def test_file_mode_and_main(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "options.json").write_text(json.dumps({"base_url": "https://n.example.org", "admin_password": "x"}))
    monkeypatch.setenv("NTFY_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("NTFY_OPTIONS", raising=False)
    assert main() == 0
    server_yml = tmp_path / "server.yml"
    assert stat.S_IMODE(server_yml.stat().st_mode) == 0o600
    assert 'base-url: "https://n.example.org"' in server_yml.read_text()
    assert (tmp_path / "attachments").is_dir()


def test_main_fails_on_bad_options(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "options.json").write_text(json.dumps({"enable_web_ui": "yes"}))
    monkeypatch.setenv("NTFY_DATA_DIR", str(tmp_path))
    assert main() == 1


def test_write_server_yml_is_rewritten_each_start(tmp_path: Path) -> None:
    paths = Paths.for_dir(tmp_path)
    write_server_yml(Options(base_url="https://a"), paths)
    write_server_yml(Options(base_url="https://b"), paths)
    assert "https://b" in paths.server_yml.read_text() and "https://a" not in paths.server_yml.read_text()
    assert load_options(tmp_path / "missing.json").base_url == "https://ntfy.example.com"
