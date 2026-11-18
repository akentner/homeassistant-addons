"""`mrp` CLI, run inside the container (`docker exec <container> mrp ...`).

Prints store URLs with print() to stdout only: this module never uses logging, so a full URL (with its access hash)
reaches only the operator's terminal (D-17). Domain errors print `error: <code>` to stderr and exit 1; usage errors
exit 2.
"""

from __future__ import annotations

import argparse
import socket
import sys

from app.access import AccessError, AccessStore
from app.options import OptionsError, load_options
from app.paths import Paths
from app.urls import store_urls

EPILOG = """examples:
  mrp users add example-org/private-addons alice
  mrp reconcile
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mrp",
        description="Manage access to the repositories served by Marketplace Repo Proxy.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    users = commands.add_parser("users", help="manage users")
    users_commands = users.add_subparsers(dest="users_command", required=True)
    add = users_commands.add_parser("add", help="add a user and print the store URL")
    add.add_argument("repository", help="configured repository as owner/repo")
    # nargs="?": a label that starts with "-" must reach validation (invalid_user), not argparse's option parsing
    add.add_argument("user", nargs="?", help="user label")
    add.add_argument("--hash", dest="hash_", default=None, help="use this 32-hex access hash instead of a new one")
    commands.add_parser("reconcile", help="rebuild the access symlink tree from access.json")
    return parser


def _error(code: str) -> int:
    print(f"error: {code}", file=sys.stderr, flush=True)
    return 1


def _users_add(args: argparse.Namespace, paths: Paths, hostname: str) -> int:
    options = load_options(paths.options_file)
    spec = options.find(args.repository)
    if spec is None:
        return _error("repository_unknown")
    store = AccessStore(paths)
    with store.locked():
        entry = store.add(spec.slug, args.user, source="cli", hash_=args.hash_)
        store.reconcile(options.repositories)
    urls = store_urls(options, hostname, spec.owner, spec.name, entry["hash"])
    print(f"internal: {urls['internal']}", flush=True)
    if "public" in urls:
        print(f"public: {urls['public']}", flush=True)
    return 0


def _reconcile(paths: Paths) -> int:
    options = load_options(paths.options_file)
    links = AccessStore(paths).reconcile(options.repositories)
    print(f"{links} access links", flush=True)
    return 0


def main(argv: list[str] | None = None, paths: Paths | None = None, hostname: str | None = None) -> int:
    parser = _parser()
    try:
        args, extra = parser.parse_known_args(argv)
        if args.command == "users" and args.user is None and len(extra) == 1:
            args.user, extra = extra[0], []
        if extra or (args.command == "users" and args.user is None):
            parser.error("unrecognized or missing arguments")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    paths = paths or Paths.default()
    hostname = hostname or socket.gethostname()
    try:
        if args.command == "users":
            return _users_add(args, paths, hostname)
        return _reconcile(paths)
    except AccessError as exc:
        return _error(exc.code)
    except OptionsError:
        return _error("options_invalid")


if __name__ == "__main__":
    sys.exit(main())
