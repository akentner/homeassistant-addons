"""Add-on manifest permissions (D-01): manager role for the Supervisor store API and nothing more."""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
FORBIDDEN = ("homeassistant_api", "auth_api", "docker_api", "host_network", "host_pid", "full_access", "privileged")


def _config() -> dict:
    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)  # HA tags such as !secret
    return yaml.load(CONFIG.read_text(encoding="utf-8"), Loader=Loader)


def test_supervisor_api_with_manager_role() -> None:
    config = _config()
    assert config["hassio_api"] is True
    assert config["hassio_role"] == "manager"


def test_no_other_permission_keys() -> None:
    config = _config()
    assert [key for key in FORBIDDEN if key in config] == []


def test_port_stays_unpublished() -> None:
    assert _config()["ports"]["8080/tcp"] is None
