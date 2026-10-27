"""Supervisor + Bitwarden provider + fake bw: full cycle, secrets never leak into logs/state."""

from __future__ import annotations

import json
import logging
import stat
from pathlib import Path

import yaml

from app.engine import config as config_mod
from app.engine.config import load_config
from app.engine.supervisor import Supervisor
from app.main import main

ITEMS = [
    {"type": 1, "name": "Mqtt: Main", "login": {"username": "u-unique-name", "password": "pw: \"quoted\"\nline2 ü"}},
    {"type": 2, "name": "ssh key", "notes": "PRIVATE-KEY-BODY-unique"},
]
SENSITIVE = ["csecret-value", "master-pw-value", "pw: \"quoted\"", "PRIVATE-KEY-BODY-unique", "u-unique-name"]


def setup(tmp_path, monkeypatch, bw_cfg):
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps({"providers": ["bitwarden"], "interval": 60, "bitwarden": bw_cfg}))
    for name, sub in (("SS_OPTIONS", "options.json"), ("SS_SECRETS_FILE", "cfg/secrets.yaml"),
                      ("SS_FILES_DIR", "cfg/files"), ("SS_STATE_FILE", "data/state.json"), ("SS_DATA_DIR", "data")):
        monkeypatch.setenv(name, str(tmp_path / sub))
    return load_config()


def test_full_cycle_no_leaks(tmp_path, monkeypatch, fake_bw, bw_cfg, caplog):
    caplog.set_level(logging.DEBUG)
    fake_bw.set_items(ITEMS)
    cfg = setup(tmp_path, monkeypatch, bw_cfg)
    sup = Supervisor(cfg)
    assert sup.run_once() == "ok"
    data = yaml.safe_load(cfg.secrets_file.read_text(encoding="utf-8"))
    assert data == {"mqtt_main_username": "u-unique-name", "mqtt_main_password": "pw: \"quoted\"\nline2 ü"}
    assert (cfg.files_dir / "bitwarden" / "ssh_key.txt").read_text() == "PRIVATE-KEY-BODY-unique"
    assert stat.S_IMODE(cfg.secrets_file.stat().st_mode) == 0o600
    state_text = cfg.state_file.read_text()
    state = json.loads(state_text)
    assert state["versions"]["bw"] == "2025.10.0"
    assert state["providers"]["bitwarden"]["revision"] == ""
    # failing run: tool stderr echoes secrets, they must not surface anywhere
    fake_bw.fail("sync", code=1, stderr="leak csecret-value master-pw-value")
    assert sup.run_once() == "degraded"
    fake_bw.clear_fail()
    fake_bw.fail("login", code=1, stderr="leak csecret-value")
    blob = caplog.text + cfg.state_file.read_text() + state_text
    for value in SENSITIVE:
        assert value not in blob
    assert "bw_sync_failed" in blob


def test_main_once_without_web(tmp_path, monkeypatch, fake_bw, bw_cfg):
    fake_bw.set_items(ITEMS)
    cfg = setup(tmp_path, monkeypatch, bw_cfg)
    assert main(["--once"]) == 0
    assert cfg.secrets_file.exists()
    assert json.loads(cfg.state_file.read_text())["status"] == "ok"


def test_registry_has_bitwarden():
    assert "bitwarden" in config_mod.PROVIDER_MODULES
    assert Path(config_mod.__file__).exists()
