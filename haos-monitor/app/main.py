"""Entry point of the HAOS Monitor GUI: `python3 -m app.main` (started and supervised by run.sh)."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from http.server import ThreadingHTTPServer

from app.web.admin_ui import INGRESS_REMOTE, serve
from app.web.server import Sources, make_server

# Equals ingress_port in config.yaml (a test pins both); never listed under `ports`
DEFAULT_PORT = 8100


@dataclass(frozen=True)
class Config:
    port: int
    ingress_remote: str
    hosts_file: str
    logdir: str
    status_sh: str
    env_file: str


def _port(raw: str) -> int:
    name = "HAOS_MONITOR_GUI_PORT"
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer in 1..65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be an integer in 1..65535")
    return port


def build_config(environ: Mapping[str, str]) -> Config:
    return Config(
        port=_port(environ.get("HAOS_MONITOR_GUI_PORT", str(DEFAULT_PORT))),
        ingress_remote=environ.get("HAOS_MONITOR_INGRESS_REMOTE", INGRESS_REMOTE),
        hosts_file=environ.get("HOSTS_FILE", "/etc/haos-monitor.hosts"),
        logdir=environ.get("LOGDIR", "/share/haos-monitor"),
        status_sh=environ.get("STATUS_SH", "/status.sh"),
        env_file=environ.get("ENV_FILE", "/etc/haos-monitor.env"),
    )


def build_server(cfg: Config, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    sources = Sources(cfg.hosts_file, cfg.logdir, cfg.status_sh, cfg.env_file)
    return make_server(sources, cfg.port, host=host, ingress_remote=cfg.ingress_remote)


def main() -> int:
    cfg = build_config(os.environ)
    server = build_server(cfg)
    print(f"listening on port {cfg.port}", flush=True)
    serve(server)  # main thread: it installs the SIGTERM/SIGINT handlers
    return 0


if __name__ == "__main__":
    sys.exit(main())
