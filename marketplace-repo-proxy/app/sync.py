"""Sync service (s6 longrun, D-13): the only process that ever builds the authenticated git environment.

Run as `python3 -m app.sync` (`--once` for a single cycle).
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from typing import Any

from app.gitops import (
    Upstream,
    UpstreamOverrideError,
    auth_env,
    default_branch,
    ensure_and_fetch,
    remote_url,
    resolve_upstream,
)
from app.logsetup import setup_logging
from app.options import Options, OptionsError, load_options
from app.paths import Paths

LOG = logging.getLogger("mrp.sync")


def _first_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0] if lines else "no output"


def run_cycle(paths: Paths, options: Options, upstream: Upstream, log: logging.Logger, writer: Any = None) -> None:
    """One pass over the configured repositories, in options order."""
    for spec in options.repositories:
        if not options.github_token:
            log.warning("skipping %s: github_token is empty", spec.slug)
            continue
        env = auth_env(options.github_token, upstream.allow_protocol)
        url = remote_url(upstream, spec)
        branch = spec.branch or default_branch(url, env)
        if not branch:
            log.warning("skipping %s: no branch configured and no upstream default branch found", spec.slug)
            continue
        try:
            result = ensure_and_fetch(paths, spec, url, branch, env)
        except (OSError, RuntimeError) as exc:
            log.warning("sync of %s failed: %s", spec.slug, exc)
            continue
        if result.returncode == 0:
            log.info("synced %s (%s)", spec.slug, branch)
        else:
            log.warning("sync of %s failed: %s", spec.slug, _first_line(result.stderr))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.sync",
        description="Sync the configured repositories into bare repositories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--once", action="store_true", help="run a single sync cycle and exit")
    args = parser.parse_args(argv)

    os.umask(0o022)  # bare repositories must stay readable for the lighttpd user
    paths = Paths.default()
    try:
        options = load_options(paths.options_file)
    except OptionsError as exc:
        setup_logging("info")
        LOG.error("%s", exc)
        return 1
    redactor = setup_logging(options.log_level)
    if options.github_token:
        header = auth_env(options.github_token, "https")["GIT_CONFIG_VALUE_0"]
        redactor.register([options.github_token, header, header.split(" ")[-1]])
    try:
        upstream = resolve_upstream(os.environ)
    except UpstreamOverrideError as exc:
        LOG.error("%s", exc)
        return 1
    if upstream.overridden:
        LOG.warning("test upstream override active: %s", upstream.base)

    stop = threading.Event()

    def _stop(*_: Any) -> None:
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _stop)

    while not stop.is_set():
        run_cycle(paths, options, upstream, LOG)
        if args.once:
            break
        for _ in range(options.sync_interval * 60):
            if stop.wait(1):
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
