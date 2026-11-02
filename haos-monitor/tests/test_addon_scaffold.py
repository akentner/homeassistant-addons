"""Add-on shell: manifest (two ports), Dockerfile, run.sh, legacy endpoint files, version sync, secrets hygiene."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.main import DEFAULT_PORT

ADDON_DIR = Path(__file__).resolve().parent.parent
LEGACY_EXECUTABLE = ("run.sh", "monitor.sh", "status.sh", "mqtt.sh", "status.cgi", "metrics.cgi", "hosts.cgi", "incidents.cgi")


def load_yaml(name: str) -> Any:
    return yaml.safe_load((ADDON_DIR / name).read_text(encoding="utf-8"))


def dockerfile_instructions() -> list[str]:
    lines = [ln.strip() for ln in (ADDON_DIR / "Dockerfile").read_text(encoding="utf-8").splitlines()]
    joined: list[str] = []
    for ln in lines:
        if not ln or ln.startswith("#"):
            continue
        if joined and joined[-1].endswith("\\"):
            joined[-1] = joined[-1][:-1].rstrip() + " " + ln
        else:
            joined.append(ln)
    return joined


def test_manifest_ingress_on_the_gui_port_and_only_the_machine_port_published() -> None:
    config = load_yaml("config.yaml")
    assert config["ingress"] is True
    assert config["ingress_port"] == 8100 == DEFAULT_PORT
    assert config["ports"] == {"8099/tcp": None}
    assert list(config["ports_description"]) == ["8099/tcp"]
    assert config["panel_admin"] is True
    assert config.get("host_network", False) is False
    assert config["arch"] == ["amd64"]
    assert config["slug"] == "haos_monitor"


def test_the_gui_port_is_never_published() -> None:
    config = load_yaml("config.yaml")
    assert not any(str(key).startswith(str(DEFAULT_PORT)) for key in config["ports"])
    assert not any(str(key).startswith(str(DEFAULT_PORT)) for key in config.get("ports_description", {}))


def test_no_upstream_file() -> None:
    assert not (ADDON_DIR / ".upstream.yaml").exists()


def test_dockerfile_base_python_and_copies() -> None:
    instructions = dockerfile_instructions()
    first_from = next(i for i, ln in enumerate(instructions) if ln.startswith("FROM "))
    arg = next(ln for ln in instructions[:first_from] if ln.startswith("ARG BUILD_FROM"))
    assert "ghcr.io/home-assistant/" in arg
    assert load_yaml("build.yaml")["build_from"]["amd64"].startswith("ghcr.io/home-assistant/")
    text = "\n".join(instructions)
    apk = next(ln for ln in instructions if "apk add" in ln)
    assert re.search(r"\bpython3\b", apk)
    assert "COPY app/ /opt/haos-monitor-gui/app/" in text
    assert "COPY icon.png /opt/haos-monitor-gui/app/web/static/icon.png" in text
    assert "COPY run.sh monitor.sh status.sh mqtt.sh /" in text
    assert "COPY httpd.conf /etc/httpd.conf" in text
    for src, dst in (
        ("status.cgi", "/www/cgi-bin/status"),
        ("metrics.cgi", "/www/cgi-bin/metrics"),
        ("hosts.cgi", "/www/api/hosts.json"),
        ("incidents.cgi", "/www/api/incidents.json"),
    ):
        assert f"COPY {src} {dst}" in text
    assert "ln -s ../cgi-bin/status /www/api/status.json" in text
    assert "ln -s ../cgi-bin/metrics /www/api/metrics.txt" in text
    assert "index.html" not in text, "the page is no longer copied into busybox httpd"
    assert not re.search(r"\b(curl|wget|git|npm|pip)\b", text), "nothing is downloaded at build time"
    assert not any(ln.startswith("WORKDIR") for ln in instructions), "legacy scripts keep their working directory"
    assert instructions[-1] == 'CMD ["/run.sh"]'


def test_dockerignore_keeps_tests_and_caches_out_of_the_context() -> None:
    lines = (ADDON_DIR / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for entry in ("tests/", ".pytest_cache/", "**/__pycache__/"):
        assert entry in lines


def test_run_sh_starts_the_gui_after_the_hosts_check_and_httpd_on_8099() -> None:
    run_sh = ADDON_DIR / "run.sh"
    text = run_sh.read_text(encoding="utf-8")
    assert os.access(run_sh, os.X_OK)
    assert text.startswith("#!/bin/sh\n")
    assert "set -u" not in text
    assert "httpd -p 8099 -h /www -c /etc/httpd.conf" in text
    assert "python3 -m app.main" in text
    assert "cd /opt/haos-monitor-gui" in text
    check = text.index('[ -s "$HOSTS" ]')
    assert check < text.index("python3 -m app.main") < text.index("httpd -p 8099")


def test_legacy_endpoint_files_exist_and_keep_their_mode_and_the_page_is_gone() -> None:
    for name in LEGACY_EXECUTABLE:
        path = ADDON_DIR / name
        assert path.is_file(), name
        assert os.access(path, os.X_OK), name
    assert (ADDON_DIR / "httpd.conf").is_file()
    assert not (ADDON_DIR / "index.html").exists()


def test_versions_are_in_sync() -> None:
    config_version = load_yaml("config.yaml")["version"]
    build_version = load_yaml("build.yaml")["args"]["VERSION"]
    readme = (ADDON_DIR / "README.md").read_text(encoding="utf-8")
    badge = re.search(r"version-v(\d+\.\d+\.\d+)-", readme)
    assert badge is not None
    assert config_version.rsplit("-", 1)[0] == build_version == badge.group(1)


def test_no_private_key_marker_in_any_file_of_the_add_on() -> None:
    # assembled from fragments, so this file never contains the marker itself
    marker = re.compile(re.escape("-----BEGIN ") + r"[A-Z ]*" + re.escape("PRIVATE KEY-----"))
    checked = 0
    for path in ADDON_DIR.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".png", ".pyc"):
            continue
        checked += 1
        assert not marker.search(path.read_text(encoding="utf-8", errors="replace")), path.relative_to(ADDON_DIR)
    assert checked > 20


@pytest.mark.parametrize("name", ["config.yaml", "build.yaml", "Dockerfile", "run.sh", ".dockerignore", "README.md", "CHANGELOG.md", "DOCS.md"])
def test_required_files_exist(name: str) -> None:
    assert (ADDON_DIR / name).is_file()
