"""GUI server of HAOS Monitor: one aggregate JSON endpoint behind the ingress gate, plus the static Preact page.

Built on the admin-ui skeleton (app.web.admin_ui, copied by `make sync-admin-ui`). No route is public: the machine
endpoints (status, metrics, hosts, incidents) stay on the busybox httpd on 8099, so every request here must come
through ingress. The endpoint takes no request parameter; every slug comes from the hosts file and is validated
before it reaches an argv or a log path. The private key and the options file are never opened: the key fingerprint
and type arrive through status.sh.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from app.hosts import HostsUnavailable, load_hosts
from app.incidents import last_incidents
from app.status import StatusError, read_status
from app.web.admin_ui import INGRESS_REMOTE, ApiError, Request, Router, StaticFiles, register_error_code
from app.web.admin_ui import make_server as _make_server

STATIC_DIR = Path(__file__).resolve().parent / "static"

register_error_code("hosts_unavailable", 503)


@dataclass(frozen=True)
class Sources:
    hosts_file: Path | str
    logdir: Path | str
    status_sh: Path | str
    env_file: Path | str


def status_env(sources: Sources) -> dict[str, str]:
    """The only environment status.sh gets: nothing of the GUI process (tokens included) leaks into it."""
    return {
        "PATH": os.environ.get("PATH") or "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LOGDIR": str(sources.logdir),
        "HOSTS_FILE": str(sources.hosts_file),
        "ENV_FILE": str(sources.env_file),
    }


def build_router(
    sources: Sources,
    clock: Callable[[], float] = time.time,
    addon_info: Callable[[], dict[str, str] | None] = lambda: None,
) -> Router:
    router = Router()
    logdir = Path(sources.logdir)

    def api_overview(_req: Request) -> dict[str, Any]:
        try:
            hosts = load_hosts(sources.hosts_file)
        except HostsUnavailable as exc:
            raise ApiError("hosts_unavailable", "hosts unavailable") from exc
        env = status_env(sources)
        entries: list[dict[str, Any]] = []
        for host in hosts:
            try:
                status: dict[str, Any] | None = read_status(host.slug, status_sh=sources.status_sh, env=env)
                error: str | None = None
            except StatusError:
                status, error = None, "status_failed"
            log = logdir / f"{host.slug}.log"
            if log.parent != logdir:  # the slug passed fullmatch, so this cannot happen; keep the path inside LOGDIR
                raise ApiError("internal_error", "internal error")
            entries.append(
                {
                    "slug": host.slug,
                    "name": host.name,
                    "host": host.host,
                    "status": status,
                    "error": error,
                    "incidents": last_incidents(log),
                }
            )
        body: dict[str, Any] = {"now_ms": int(clock() * 1000), "hosts": entries}
        info = addon_info()
        if info:  # unknown (no token, direct run): the keys stay out and the GUI hides the info link and the version
            body["addon_slug"] = info["slug"]
            body["addon_version"] = info["version"]
        return body

    # Not public: the machine endpoints stay on the busybox httpd (8099), this server only answers ingress.
    router.add("GET", "/api/overview", api_overview)
    return router


def make_server(
    sources: Sources,
    port: int,
    host: str = "0.0.0.0",
    ingress_remote: str = INGRESS_REMOTE,
    addon_info: Callable[[], dict[str, str] | None] = lambda: None,
) -> ThreadingHTTPServer:
    router = build_router(sources, addon_info=addon_info)
    return _make_server(router, StaticFiles(STATIC_DIR), port, ingress_remote=ingress_remote, host=host)
