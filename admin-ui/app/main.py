"""Entry point of the admin UI blueprint add-on: `python3 -m app.main`."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.web import demo_api
from app.web.skeleton import DEFAULT_CSP, INGRESS_REMOTE, Router, StaticFiles, make_server, serve

DEFAULT_PORT = 8099
PACKAGE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    port: int
    ingress_remote: str
    version: str
    csp: str | None


def build_config(environ: Mapping[str, str]) -> Config:
    """Read the ADMIN_UI_* environment; ADMIN_UI_CSP is `strict` (default) or `off` (spike escape hatch, PD-07)."""
    mode = environ.get("ADMIN_UI_CSP", "strict")
    if mode == "strict":
        csp: str | None = DEFAULT_CSP
    elif mode == "off":
        csp = None
    else:
        raise ValueError(f"ADMIN_UI_CSP must be 'strict' or 'off', got {mode!r}")
    return Config(
        port=int(environ.get("ADMIN_UI_PORT", str(DEFAULT_PORT))),
        ingress_remote=environ.get("ADMIN_UI_INGRESS_REMOTE", INGRESS_REMOTE),
        version=environ.get("ADMIN_UI_VERSION", "unknown"),
        csp=csp,
    )


def main() -> int:
    cfg = build_config(os.environ)
    static_dir = PACKAGE_DIR / "web" / "static"
    lib_version = (static_dir / "lib" / "VERSION").read_text(encoding="utf-8").strip()
    router = Router()
    demo_api.register(router, version=cfg.version, lib_version=lib_version)
    server = make_server(router, StaticFiles(static_dir), cfg.port, ingress_remote=cfg.ingress_remote, csp=cfg.csp)
    print(f"listening on port {cfg.port}", flush=True)
    serve(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
