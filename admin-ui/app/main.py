"""Entry point of the admin UI blueprint add-on: `python3 -m app.main`."""

from __future__ import annotations

import os
import signal
import sys
import threading
from pathlib import Path
from types import FrameType

from app.web import demo_api
from app.web.skeleton import INGRESS_REMOTE, Router, StaticFiles, make_server

DEFAULT_PORT = 8099
PACKAGE_DIR = Path(__file__).resolve().parent


def main() -> int:
    static_dir = PACKAGE_DIR / "web" / "static"
    lib_version = (static_dir / "lib" / "VERSION").read_text(encoding="utf-8").strip()
    router = Router()
    demo_api.register(router, version=os.environ.get("ADMIN_UI_VERSION", "unknown"), lib_version=lib_version)
    port = int(os.environ.get("ADMIN_UI_PORT", str(DEFAULT_PORT)))
    server = make_server(
        router,
        StaticFiles(static_dir),
        port,
        ingress_remote=os.environ.get("ADMIN_UI_INGRESS_REMOTE", INGRESS_REMOTE),
    )

    def stop(_signum: int, _frame: FrameType | None) -> None:
        # shutdown() blocks until serve_forever returns, so it must not run in the signal handler's thread
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"listening on port {port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
