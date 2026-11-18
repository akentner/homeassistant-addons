"""s6 oneshot `init`: directories and modes, /etc/gitconfig safe.directory, access symlink tree rebuild (D-06, D-15).

Run as `python3 -m app.init`. Offline and fast: it never contacts the upstream or the Supervisor.
"""

from __future__ import annotations

import logging
import os
import socket
import sys

from app.access import AccessSchemaError, AccessStore
from app.gitops import local_env, run_git
from app.logsetup import setup_logging
from app.options import OptionsError, load_options
from app.paths import Paths

LOG = logging.getLogger("mrp.init")


def run_init(paths: Paths, hostname: str | None = None) -> int:
    """Prepare the container; returns the process exit code (non-zero stops the container)."""
    hostname = hostname or socket.gethostname()  # used by the startup log (Plan 04)
    os.umask(0o077)
    try:
        options = load_options(paths.options_file)
    except OptionsError as exc:
        LOG.error("%s", exc)
        return 1
    for message in options.rejected:
        LOG.warning("ignoring option entry: %s", message)

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
    if result.returncode != 0:
        LOG.error("cannot write safe.directory to %s", paths.gitconfig_file)
        return 1
    os.chmod(paths.gitconfig_file, 0o644)

    try:
        links = AccessStore(paths, LOG).reconcile(options.repositories)
    except AccessSchemaError:
        LOG.error("access.json has a newer schema than this add-on version supports; refusing to start")
        return 1
    LOG.info("access links: %d (hostname %s)", links, hostname)
    return 0


def main() -> int:
    setup_logging("info")
    return run_init(Paths.default())


if __name__ == "__main__":
    sys.exit(main())
