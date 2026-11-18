"""s6 oneshot `init`: directories and modes, /etc/gitconfig safe.directory, access symlink tree rebuild (D-06, D-15).

Run as `python3 -m app.init`. Offline and fast: it never contacts the upstream or the Supervisor. The startup log
names user labels and masked store URLs only (D-17, D-27). Failure policy (D-28): a non-zero exit halts the container
(S6_BEHAVIOUR_IF_STAGE2_FAILS=2), so only invalid options and an unknown access.json schema are fatal; every other
problem is logged and survived.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
from typing import Any

from app.access import HASH_RE, USER_RE, AccessSchemaError, AccessStore, reconcile_tree
from app.gitops import local_env, run_git
from app.logsetup import setup_logging
from app.options import Options, OptionsError, RepoSpec, load_options, parse_repository
from app.paths import Paths
from app.urls import internal_base, masked_store_url

LOG = logging.getLogger("mrp.init")


def _active_users(entries: list[dict[str, Any]], spec: RepoSpec) -> list[tuple[str, str]]:
    """(label, hash) of the entries that reconcile links for `spec`, sorted by label."""
    users = []
    for entry in entries:
        repository, user, hash_ = entry.get("repository"), entry.get("user"), entry.get("hash")
        if (
            isinstance(repository, str)
            and repository.lower() == spec.key
            and isinstance(user, str)
            and USER_RE.fullmatch(user)
            and isinstance(hash_, str)
            and HASH_RE.fullmatch(hash_)
        ):
            users.append((user, hash_))
    return sorted(users)


def _unconfigured_count(entries: list[dict[str, Any]], options: Options) -> int:
    """Entries with a valid repository that is not configured (reconcile skips them; they stay in the file)."""
    configured = {spec.key for spec in options.repositories}
    count = 0
    for entry in entries:
        repository = entry.get("repository")
        try:
            parse_repository(repository)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if repository.lower() not in configured:
            count += 1
    return count


def log_startup(options: Options, entries: list[dict[str, Any]], hostname: str) -> None:
    """Per repository its branch and user count, per user the label and masked URLs; never a full hash or the PAT."""
    LOG.info(
        "marketplace-repo-proxy: %d repositories configured, %d access entries", len(options.repositories), len(entries)
    )
    base = internal_base(hostname)
    for spec in options.repositories:
        users = _active_users(entries, spec)
        LOG.info("repository %s (branch: %s): %d user(s)", spec.slug, spec.branch or "upstream default", len(users))
        for label, hash_ in users:
            line = f"  user {label} -> {masked_store_url(base, spec.owner, spec.name, hash_)}"
            if options.public_url:
                line += f" | public {masked_store_url(options.public_url, spec.owner, spec.name, hash_)}"
            LOG.info("%s", line)
    unconfigured = _unconfigured_count(entries, options)
    if unconfigured:
        LOG.info("%d access entries belong to repositories that are not configured; they stay inactive", unconfigured)


def run_init(paths: Paths, hostname: str | None = None) -> int:
    """Prepare the container; returns the process exit code (non-zero stops the container)."""
    hostname = hostname or socket.gethostname()
    os.umask(0o077)
    try:
        options = load_options(paths.options_file)
    except OptionsError as exc:
        LOG.error("%s", exc)
        return 1
    for message in options.rejected:
        LOG.warning("ignoring option entry: %s", message)
    if options.repositories and not options.github_token:
        LOG.warning("github_token is empty; sync will report auth_failed")

    if paths.data_dir.exists():
        os.chmod(paths.data_dir, 0o700)
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.run_dir, 0o700)
    # makedirs is umask-bound (077 here): set the traversable modes explicitly
    paths.repos_root.mkdir(parents=True, exist_ok=True)
    for directory in (paths.repos_root.parent, paths.repos_root):
        os.chmod(directory, 0o755)
    paths.access_root.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.access_root, 0o711)

    paths.gitconfig_file.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(
        ["config", "--file", str(paths.gitconfig_file), "--replace-all", "safe.directory", f"{paths.repos_root}/*"],
        local_env(),
    )
    if result.returncode == 0:
        os.chmod(paths.gitconfig_file, 0o644)
    else:
        # D-28: not fatal; clones fail until the next start, sync and the log stay available
        LOG.error("cannot write safe.directory to %s", paths.gitconfig_file)

    store = AccessStore(paths, LOG)
    entries: list[dict[str, Any]] = []
    try:
        with store.locked():
            entries = list(store.load()["entries"])
            links = reconcile_tree(entries, options.repositories, paths, LOG)
    except AccessSchemaError:
        LOG.error("access.json has a newer schema than this add-on version supports; refusing to start")
        return 1
    except OSError as exc:
        # D-28: survive; the watcher reconciles again on the next access.json change
        LOG.error("access symlink tree not rebuilt: %s", type(exc).__name__)
        links = 0
    LOG.debug("access links: %d", links)
    log_startup(options, entries, hostname)
    return 0


def main() -> int:
    setup_logging("info")
    return run_init(Paths.default())


if __name__ == "__main__":
    sys.exit(main())
