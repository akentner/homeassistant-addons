"""Entry point configuration and server construction."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from app.main import DEFAULT_PORT, Config, build_config, build_server
from conftest import INGRESS, REAL_STATUS_SH


def test_defaults() -> None:
    cfg = build_config({})
    assert cfg == Config(
        port=8100,
        ingress_remote="172.30.32.2",
        hosts_file="/etc/haos-monitor.hosts",
        logdir="/share/haos-monitor",
        status_sh="/status.sh",
        env_file="/etc/haos-monitor.env",
    )
    assert DEFAULT_PORT == 8100


def test_overrides_through_the_six_variables() -> None:
    cfg = build_config(
        {
            "HAOS_MONITOR_GUI_PORT": "9000",
            "HAOS_MONITOR_INGRESS_REMOTE": "127.0.0.1",
            "HOSTS_FILE": "/h",
            "LOGDIR": "/l",
            "STATUS_SH": "/s",
            "ENV_FILE": "/e",
        }
    )
    assert cfg == Config(9000, "127.0.0.1", "/h", "/l", "/s", "/e")


@pytest.mark.parametrize("raw", ["0", "65536", "abc", "", "-1", "80.5"])
def test_bad_ports_name_the_variable(raw: str) -> None:
    with pytest.raises(ValueError, match="HAOS_MONITOR_GUI_PORT"):
        build_config({"HAOS_MONITOR_GUI_PORT": raw})


def test_build_server_answers_overview(env: dict[str, Path]) -> None:
    import http.client

    cfg = build_config(
        {
            "HAOS_MONITOR_GUI_PORT": "1",
            "HAOS_MONITOR_INGRESS_REMOTE": "127.0.0.1",
            "HOSTS_FILE": str(env["hosts_file"]),
            "LOGDIR": str(env["logdir"]),
            "STATUS_SH": str(REAL_STATUS_SH),
            "ENV_FILE": str(env["env_file"]),
        }
    )
    cfg = Config(0, cfg.ingress_remote, cfg.hosts_file, cfg.logdir, cfg.status_sh, cfg.env_file)
    server: Any = build_server(cfg, host="127.0.0.1")
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        conn.request("GET", "/api/overview", headers=INGRESS)
        resp = conn.getresponse()
        data = json.loads(resp.read())
        assert resp.status == 200 and data["hosts"][0]["slug"] == "ha_backup"
        conn.request("GET", "/api/overview")
        assert conn.getresponse().status == 403
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
