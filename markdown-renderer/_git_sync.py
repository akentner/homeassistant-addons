#!/usr/bin/env python3
"""Synchronize configured Markdown namespaces with their git remotes.

Reads ``/data/options.json`` (same source as ``generate_nginx.py``) and walks
the ``directories[]`` list. For each entry whose ``git_pull`` or
``git_pull_interval`` is set, probes the path with ``git rev-parse``; if it is
already a git repo, runs ``git pull --ff-only``; if not, and ``git_url`` is
configured, runs ``git clone``. All git failures are logged as ``WARNING:``
lines but never raise — the contract is that nginx must always be allowed
to start (GIT-05).

Invocation:

    python3 /app/_git_sync.py              # one-shot startup pull
    python3 /app/_git_sync.py --periodic   # one iteration of the periodic loop

The outer ``while true`` periodic loop lives in ``run.sh`` so signal handling
and PID management stay in the shell. The ``--periodic`` flag tells this
script to skip any namespace whose own ``git_pull_interval`` has not yet
elapsed since its last pull (tracked in-memory only, D-09).

Per-namespace interval state is in-memory (a module-level ``last_pull`` dict)
and resets on every add-on restart — the first periodic iteration pulls every
namespace whose ``git_pull_interval > 0`` once. This matches the v1.1
philosophy of keeping state out of ``/data``.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure HOME is set before any git invocation. Some HA Supervisor container
# environments do not export HOME by default; `git config --global` and other
# git operations abort with `fatal: $HOME not set` if HOME is unset. Mirrors
# run.sh:9 but defends against environments where run.sh's export is not
# inherited (e.g. when this script is invoked from a context that clears env).
os.environ.setdefault("HOME", "/root")

# Path to the canonical HA options source. Mirrors generate_nginx.py so the
# two scripts agree on input shape (D-04: each script reads options.json
# independently to keep concerns separated).
OPTIONS_PATH = Path("/data/options.json")

# Tag printed in front of every non-fatal warning so HA Supervisor log
# filtering can pick them up easily.
WARNING_PREFIX = "WARNING:"

# In-memory interval state. Keyed by namespace name, value is
# ``time.monotonic()`` timestamp of the last successful pull. Resets on
# process restart — first ``--periodic`` iteration will pull every namespace
# whose interval is configured (D-09).
last_pull: dict[str, float] = {}


def _is_git_repo(path: Path) -> bool:
    """Return True if ``path`` is inside a working git repository.

    Runs ``git -C <path> rev-parse --git-dir`` and treats a zero exit code
    as proof of repo membership (D-06). Non-zero exit means the path is not
    inside a repo and ``_git_sync`` should fall back to ``git_url`` cloning
    or skip with a warning.
    """
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--git-dir"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _git_pull(path: Path) -> bool:
    """Run ``git pull --ff-only`` against ``path``. Return True on success.

    Uses ``--ff-only`` so a non-fast-forward local state (e.g. a manual edit
    the user made on the host) never gets silently overwritten. Failures
    emit a ``WARNING:`` log line with the captured stderr but never raise
    (D-07, GIT-05). Success emits an ``INFO:`` line so the periodic loop's
    pull invocations are visible in HA Supervisor logs.
    """
    result = subprocess.run(
        ["git", "-C", str(path), "pull", "--ff-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"{WARNING_PREFIX} git pull failed for {path}: "
            f"{(result.stderr or '').strip()}",
            flush=True,
        )
        return False
    # Surface git's own output so the operator can see whether the pull
    # was a no-op ("Already up to date.") or fetched new commits
    # ("Fast-forward", "Updating <sha>..<sha>"). This is the same text
    # the user would see if they ran `git pull` manually.
    git_stdout = (result.stdout or "").strip()
    if git_stdout:
        print(f"INFO: git pull for {path}: {git_stdout}", flush=True)
    return True


def _git_clone(git_url: str, path: Path) -> bool:
    """Run ``git clone <git_url> <path>`` once. Return True on success.

    Single attempt only — no retry. A clone that fails (auth, network,
    typo in URL) should be obvious to the user via the warning line; a
    silent retry would only delay the failure and could spam logs on every
    periodic tick. This matches GIT-05's "non-blocking" contract: log and
    move on, do not crash the add-on.
    """
    result = subprocess.run(
        ["git", "clone", git_url, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"{WARNING_PREFIX} git clone failed for {git_url} -> {path}: "
            f"{(result.stderr or '').strip()}",
            flush=True,
        )
        return False
    # Surface git's clone progress (e.g. "Cloning into '<path>'...")
    # so the operator can see the clone actually happened.
    git_stdout = (result.stdout or "").strip()
    if git_stdout:
        print(f"INFO: git clone {git_url} -> {path}: {git_stdout}", flush=True)
    return True


def sync_namespace(
    name: str,
    path: Path,
    git_pull: bool,
    git_pull_interval: int,
    git_url: str,
    periodic: bool,
) -> None:
    """Sync a single namespace according to its git configuration.

    Behavior matrix (D-02, D-06, D-07):

    - Periodic mode and the namespace's own ``git_pull_interval`` has not
      yet elapsed since its last successful pull: skip silently.
    - Path is not a git repo and ``git_url`` is set: clone it.
    - Path is not a git repo and ``git_url`` is empty: log a warning and
      serve whatever local content exists (or an empty Docsify SPA).
    - Path is a git repo: pull with ``--ff-only``; update ``last_pull``
      on success.

    This function never raises; all failure paths are converted to warning
    log lines so the add-on startup chain in ``run.sh`` cannot be blocked
    by a flaky git remote.
    """
    # Periodic-mode gate: skip namespaces whose own interval has not elapsed.
    # ``periodic=False`` (startup pull) always proceeds regardless of
    # ``git_pull_interval`` because the whole point of the startup pull is
    # to refresh state once before nginx serves traffic.
    if periodic and git_pull_interval > 0:
        elapsed = time.monotonic() - last_pull.get(name, 0.0)
        if elapsed < git_pull_interval:
            return

    # Cloning only happens when the path is not yet a repo. This covers the
    # first-time setup case (D-02): user pre-creates an empty directory
    # under /share, points git_url at the upstream repo, and the add-on
    # clones on first run.
    if not _is_git_repo(path):
        if git_url:
            if _git_clone(git_url, path):
                last_pull[name] = time.monotonic()
        else:
            print(
                f"{WARNING_PREFIX} {name}: path is not a git repo and no "
                f"git_url set, serving local content at {path}",
                flush=True,
            )
        return

    # Repo already exists — pull. ``git_pull`` flag (startup-only) and
    # ``git_pull_interval`` (periodic) are both honored here. We always
    # pull when reached: the caller (sync_all_namespaces) has already
    # filtered by interval in periodic mode.
    if _git_pull(path):
        last_pull[name] = time.monotonic()


def sync_all_namespaces(periodic: bool = False) -> int:
    """Walk the configured directories and sync each one. Always returns 0.

    Always returns 0 (never raises) so ``run.sh`` can ``exec nginx`` even
    when every single namespace has an unreachable git remote — GIT-05
    contract. The intent of the periodic loop is best-effort currency, not
    a hard guarantee that pulls succeed.

    Namespaces without ``git_pull`` and without a positive
    ``git_pull_interval`` are skipped without invoking the git binary at
    all (GIT-03).
    """
    if not OPTIONS_PATH.exists():
        print(
            f"{WARNING_PREFIX} {OPTIONS_PATH} not found, skipping git sync",
            flush=True,
        )
        return 0

    try:
        with OPTIONS_PATH.open() as f:
            options = json.load(f)
    except (OSError, json.JSONDecodeError) as err:
        print(
            f"{WARNING_PREFIX} could not read {OPTIONS_PATH}: {err}, "
            f"skipping git sync",
            flush=True,
        )
        return 0

    directories = options.get("directories", [])
    if not isinstance(directories, list):
        print(
            f"{WARNING_PREFIX} 'directories' is not a list, skipping git "
            f"sync",
            flush=True,
        )
        return 0

    for entry in directories:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        path_str = entry.get("path", "")
        if not isinstance(name, str) or not isinstance(path_str, str):
            continue
        if not name or not path_str:
            continue

        # Per-namespace git config. All three fields are optional; defaults
        # match the HA schema defaults documented in 06-CONTEXT.md D-01/D-02.
        git_pull_flag = bool(entry.get("git_pull", False))
        git_pull_interval = int(entry.get("git_pull_interval", 0) or 0)
        git_url = entry.get("git_url", "") or ""

        # GIT-03: no git binary invocation when neither flag is set. We
        # only enter this branch when the user has actually opted in.
        if not git_pull_flag and git_pull_interval <= 0:
            continue

        path = Path(path_str)
        sync_namespace(
            name=name,
            path=path,
            git_pull=git_pull_flag,
            git_pull_interval=git_pull_interval,
            git_url=git_url,
            periodic=periodic,
        )

    return 0


def main() -> int:
    """Parse args and run one startup or periodic sync pass. Always returns 0."""
    parser = argparse.ArgumentParser(
        description=(
            "Sync Markdown namespace directories with their git remotes. "
            "Reads /data/options.json. Never blocks startup on git errors."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--periodic",
        action="store_true",
        help=(
            "Run one iteration of the periodic loop: respect each namespace's "
            "git_pull_interval before pulling. Without this flag the script "
            "treats the invocation as the startup pull and pulls every "
            "namespace that has git_pull=true."
        ),
    )
    args = parser.parse_args()
    return sync_all_namespaces(periodic=args.periodic)


if __name__ == "__main__":
    sys.exit(main())
