"""Entry point: load config, start the web layer in a thread and run the sync supervisor."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time

from app.engine.config import Config, load_config
from app.engine.redact import Redactor
from app.engine.supervisor import Supervisor

log = logging.getLogger("secrets_sync")


def setup_logging(level: str, redactor: Redactor) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler.addFilter(redactor)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def _start_web(supervisor: Supervisor, cfg: Config) -> threading.Thread | None:
    try:
        from app.web.server import serve
    except ImportError:
        if os.environ.get("SS_ALLOW_NO_WEB") == "1":  # tests only
            log.warning("web layer not available")
            return None
        raise

    def run() -> None:
        while True:
            try:
                serve(supervisor, str(cfg.state_file), cfg.port, ingress_only=True)
            except Exception as exc:  # keep syncing even if the UI dies
                log.error("web server stopped (%s)", type(exc).__name__)
            time.sleep(5)

    thread = threading.Thread(target=run, name="web", daemon=True)
    thread.start()
    return thread


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Secrets Sync")
    parser.add_argument("--once", action="store_true", help="run a single sync cycle and exit")
    args = parser.parse_args(argv)

    cfg = load_config()
    redactor = Redactor()
    setup_logging(cfg.log_level, redactor)
    supervisor = Supervisor(cfg, redactor=redactor)
    log.info("Secrets Sync %s starting (providers: %s)", cfg.version, ", ".join(cfg.providers) or "none")

    if args.once:
        supervisor.state.save()
        supervisor.run_once()
        return 0

    _start_web(supervisor, cfg)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: supervisor.stop())
    supervisor.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
