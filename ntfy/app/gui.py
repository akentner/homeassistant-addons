"""Entry point of the admin GUI process: `python3 -m app.gui` (restarted by run.sh when it exits)."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from types import FrameType

from app.context import build_context
from app.contract import GUI_PORT, INGRESS_REMOTE
from app.web.api import register_all
from app.web.server import Router, make_server

LEVELS = {"trace": logging.DEBUG, "debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING,
          "error": logging.ERROR}


def main() -> int:
    ctx = build_context()
    logging.basicConfig(stream=sys.stdout, level=LEVELS.get(ctx.options.log_level, logging.INFO),
                        format="[gui] %(levelname)s %(message)s")
    router = Router()
    register_all(router, ctx)
    port = int(os.environ.get("NTFY_GUI_PORT", str(GUI_PORT)))
    server = make_server(router, port, os.environ.get("NTFY_INGRESS_REMOTE", INGRESS_REMOTE))

    def stop(_signum: int, _frame: FrameType | None) -> None:
        # shutdown() blocks until serve_forever returns, so it must not run in the signal handler's thread
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"[gui] listening on port {port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
