"""Entry point of the admin GUI process: `python3 -m app.gui` (restarted by run.sh when it exits)."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping

from app.context import build_context
from app.contract import GUI_PORT, INGRESS_REMOTE
from app.web.admin_ui import DEFAULT_CSP, serve
from app.web.api import register_all
from app.web.server import Router, make_server

LEVELS = {"trace": logging.DEBUG, "debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING,
          "error": logging.ERROR}


def csp_from_env(environ: Mapping[str, str]) -> str | None:
    """NTFY_GUI_CSP: `strict` (default) keeps the skeleton CSP, `off` removes it (diagnostics only), else ValueError."""
    value = environ.get("NTFY_GUI_CSP", "strict")
    if value == "strict":
        return DEFAULT_CSP
    if value == "off":
        return None
    raise ValueError(f"NTFY_GUI_CSP must be 'strict' or 'off', got {value!r}")


def main() -> int:
    ctx = build_context()
    logging.basicConfig(stream=sys.stdout, level=LEVELS.get(ctx.options.log_level, logging.INFO),
                        format="[gui] %(levelname)s %(message)s")
    router = Router()
    register_all(router, ctx)
    port = int(os.environ.get("NTFY_GUI_PORT", str(GUI_PORT)))
    server = make_server(router, port, os.environ.get("NTFY_INGRESS_REMOTE", INGRESS_REMOTE),
                         csp=csp_from_env(os.environ))
    print(f"[gui] listening on port {port}", flush=True)
    serve(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
