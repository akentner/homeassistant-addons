"""Add-on shell tests: manifest, Dockerfile, run.sh, 3-file version sync and the repo config validator."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ADDON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = ADDON_DIR.parent
EXPECTED_VERSION = "0.1.0"


def load_yaml(name: str) -> Any:
    return yaml.safe_load((ADDON_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["config.yaml", "build.yaml", "Dockerfile", "run.sh", ".dockerignore", "README.md",
                                  "CHANGELOG.md"])
def test_required_files_exist(name: str) -> None:
    assert (ADDON_DIR / name).is_file()


def test_manifest_is_ingress_only_and_manual() -> None:
    config = load_yaml("config.yaml")
    assert config["ingress"] is True
    assert config["ingress_port"] == 8099
    assert config["boot"] == "manual"
    assert config["panel_admin"] is False
    assert "ports" not in config
    assert "ports_description" not in config
    assert config["host_network"] is False
    assert config["arch"] == ["amd64"]
    assert config["slug"] == "admin_ui"
    assert config["image"].endswith("{arch}-admin_ui")


def test_no_upstream_file() -> None:
    assert not (ADDON_DIR / ".upstream.yaml").exists()


def test_dockerfile_uses_ha_base_and_downloads_nothing() -> None:
    lines = [ln.strip() for ln in (ADDON_DIR / "Dockerfile").read_text(encoding="utf-8").splitlines()]
    instructions = [ln for ln in lines if ln and not ln.startswith("#")]
    first_from = next(i for i, ln in enumerate(instructions) if ln.startswith("FROM "))
    assert any(ln.startswith("ARG BUILD_FROM") for ln in instructions[:first_from])
    default = next(ln for ln in instructions[:first_from] if ln.startswith("ARG BUILD_FROM"))
    assert "ghcr.io/home-assistant/" in default
    text = "\n".join(instructions)
    assert not re.search(r"\b(curl|wget|git)\b", text)
    assert load_yaml("build.yaml")["build_from"]["amd64"].startswith("ghcr.io/home-assistant/")


def test_run_sh_is_executable_bashio_and_execs_the_app() -> None:
    run_sh = ADDON_DIR / "run.sh"
    assert os.access(run_sh, os.X_OK)
    text = run_sh.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/with-contenv bashio\n")
    assert "exec python3 -m app.main" in text


def test_versions_are_in_sync() -> None:
    config_version = load_yaml("config.yaml")["version"]
    build_version = load_yaml("build.yaml")["args"]["VERSION"]
    readme = (ADDON_DIR / "README.md").read_text(encoding="utf-8")
    badge = re.search(r"version-v(\d+\.\d+\.\d+)-", readme)
    assert badge is not None
    assert config_version.rsplit("-", 1)[0] == build_version == badge.group(1) == EXPECTED_VERSION


def test_dockerignore_excludes_tests() -> None:
    assert "tests/" in (ADDON_DIR / ".dockerignore").read_text(encoding="utf-8").splitlines()


def test_repo_config_validator_accepts_the_manifest() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "internal" / "validate-addon-config.py"), str(ADDON_DIR)],
        capture_output=True, text=True, timeout=60, check=False, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
