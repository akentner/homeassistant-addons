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
import time
from dataclasses import dataclass
from typing import Any

from app.gitops import (
    Upstream,
    UpstreamOverrideError,
    auth_env,
    check_branch_name,
    classify,
    ensure_and_fetch,
    inspect_head,
    ls_remote_head,
    prune_foreign_refs,
    ref_snapshot,
    remote_url,
    resolve_upstream,
    run_maintenance,
    sanitize,
)
from app.logsetup import setup_logging
from app.options import Options, OptionsError, RepoSpec, load_options
from app.paths import Paths
from app.status import StatusWriter

LOG = logging.getLogger("mrp.sync")

EMPTY_TOKEN_MESSAGE = "github_token is empty"
INVALID_BRANCH_MESSAGE = "invalid branch name"
NO_DEFAULT_BRANCH_MESSAGE = "upstream has no default branch"
NO_REPOSITORY_YAML_MESSAGE = "repository.yaml missing at the branch root"


def secret_forms(token: str) -> list[str]:
    """The PAT plus its header and base64 forms: values that must never reach a log line or status.json."""
    if not token:
        return []
    header = auth_env(token, "https")["GIT_CONFIG_VALUE_0"]
    return [token, header, header.split(" ")[-1]]


@dataclass
class Outcome:
    status: str
    message: str = ""
    branch: str | None = None
    head: str | None = None
    addons: tuple[str, ...] = ()
    refs_changed: bool = False


def _sync_one(paths: Paths, options: Options, upstream: Upstream, spec: RepoSpec) -> Outcome:
    """Steps 1-6 of the sync cycle for one repository (RESEARCH Pattern 5); never raises for git failures."""
    if not options.github_token:
        return Outcome("auth_failed", EMPTY_TOKEN_MESSAGE, spec.branch)
    env = auth_env(options.github_token, upstream.allow_protocol)
    url = remote_url(upstream, spec)
    if spec.branch:
        if not check_branch_name(spec.branch):
            return Outcome("not_found", INVALID_BRANCH_MESSAGE, spec.branch)
        branch = spec.branch
    else:
        probe, found = ls_remote_head(url, env)
        if probe.returncode != 0:
            return Outcome(*classify(probe))
        if not found:
            return Outcome("not_found", NO_DEFAULT_BRANCH_MESSAGE)
        branch = found
    repo_dir = paths.repo_dir(spec.owner, spec.name)
    before = ref_snapshot(repo_dir)
    try:
        result = ensure_and_fetch(paths, spec, url, branch, env)
    except (OSError, RuntimeError) as exc:
        return Outcome("fetch_failed", sanitize(str(exc)) or type(exc).__name__, branch)
    if result.returncode != 0:
        return Outcome(*classify(result), branch=branch)
    prune_foreign_refs(repo_dir, branch)
    changed = ref_snapshot(repo_dir) != before
    info = inspect_head(repo_dir)
    run_maintenance(repo_dir)
    if not info.has_repository_yaml:
        return Outcome("no_repository_yaml", NO_REPOSITORY_YAML_MESSAGE, branch, info.head, info.addons, changed)
    return Outcome("ok", "", branch, info.head, info.addons, changed)


def _scrub(text: str, secrets: list[str]) -> str:
    for value in secrets:
        if value and value in text:
            text = text.replace(value, "***")
    return text


def run_cycle(
    paths: Paths,
    options: Options,
    upstream: Upstream,
    log: logging.Logger,
    writer: StatusWriter,
    stop: threading.Event | None = None,
) -> None:
    """One pass over the configured repositories in options order; records every result in status.json."""
    secrets = secret_forms(options.github_token)
    for spec in options.repositories:
        if stop is not None and stop.is_set():
            break
        try:
            outcome = _sync_one(paths, options, upstream, spec)
        except Exception as exc:  # one broken repository must not end the cycle for the others
            outcome = Outcome("fetch_failed", f"internal error: {type(exc).__name__}", spec.branch)
        message = _scrub(outcome.message, secrets)
        writer.record(
            spec.slug,
            status=outcome.status,
            message=message,
            branch=outcome.branch,
            branch_source="configured" if spec.branch else "upstream_default",
            head=outcome.head,
            addons=list(outcome.addons),
            refs_changed=outcome.refs_changed,
        )
        if outcome.status == "ok":
            changed = ", changed" if outcome.refs_changed else ""
            log.info("sync %s: ok (%s @ %s%s)", spec.slug, outcome.branch, outcome.head, changed)
        elif outcome.status == "auth_failed":
            log.warning(
                "sync %s: auth_failed: %s; check github_token (the token itself is not shown)",
                spec.slug,
                sanitize(message),
            )
        else:
            log.warning("sync %s: %s: %s", spec.slug, outcome.status, sanitize(message))


class SyncService:
    """RED stub."""

    def __init__(self, paths: Paths, options: Options, upstream: Upstream, log: logging.Logger, **_: Any) -> None:
        self.stop = threading.Event()

    def wait_reason(self) -> str | None:
        return None

    def run_cycle_once(self, reason: str) -> None:
        return None

    def run_forever(self) -> None:
        return None


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
    redactor.register(secret_forms(options.github_token))
    try:
        upstream = resolve_upstream(os.environ)
    except UpstreamOverrideError as exc:
        LOG.error("%s", exc)
        return 1
    if upstream.overridden:
        LOG.warning("test upstream override active: %s", upstream.base)
    writer = StatusWriter(paths, options.repositories, upstream.overridden, options.sync_interval)

    stop = threading.Event()

    def _stop(*_: Any) -> None:
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _stop)

    reason = "startup"
    while not stop.is_set():
        writer.begin_cycle(reason)
        run_cycle(paths, options, upstream, LOG, writer, stop)
        writer.end_cycle(time.time() + options.sync_interval * 60)
        if args.once:
            break
        for _ in range(options.sync_interval * 60):
            if stop.wait(1):
                break
        reason = "interval"
    return 0


if __name__ == "__main__":
    sys.exit(main())
