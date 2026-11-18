"""`mrp` CLI, run inside the container (`docker exec <container> mrp ...`).

Prints store URLs with print() to stdout only: this module never uses logging, so a full URL (with its access hash)
reaches only the operator's terminal (D-17). `users list` shows masked hashes only. Domain errors print
`error: <code>` to stderr and exit 1; usage errors exit 2.
"""

from __future__ import annotations

import argparse
import socket
import sys
from typing import Any

from app.access import HASH_RE, AccessError, AccessStore
from app.jsonio import atomic_write_json
from app.options import Options, OptionsError, load_options
from app.paths import Paths
from app.urls import mask_hash, store_urls

USER_COMMANDS = ("add", "url", "revoke")  # take <owner/repo> <user>

EPILOG = """A store URL contains the user's access hash: treat the full URL as a secret. Only `users add` and
`users url` print it, to this terminal; `users list` shows masked hashes.

Rotation: there is no in-place rotation. `users revoke` and then `users add` the same user; the new URL has a new
hash, so the consumer must re-add the repository in the add-on store and reinstall its add-ons.

examples:
  mrp users list [example-org/private-addons]
  mrp users add example-org/private-addons alice
  mrp users url example-org/private-addons alice
  mrp users revoke example-org/private-addons alice
  mrp sync
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

    listing = users_commands.add_parser("list", help="list users with masked hashes")
    listing.add_argument("repository", nargs="?", default=None, help="only this repository (owner/repo)")

    helps = {
        "add": "add a user and print the store URL (secret)",
        "url": "print a user's store URL (secret)",
        "revoke": "remove a user; the URL stops working at the next request",
    }
    for name in USER_COMMANDS:
        sub = users_commands.add_parser(name, help=helps[name])
        sub.add_argument("repository", help="repository as owner/repo")
        # nargs="?": a label that starts with "-" must reach validation, not argparse's option parsing
        sub.add_argument("user", nargs="?", help="user label")
        if name == "add":
            sub.add_argument("--hash", dest="hash_", default=None, help="use this 32-hex access hash")

    commands.add_parser("sync", help="request a sync of all repositories now")
    commands.add_parser("reconcile", help="rebuild the access symlink tree from access.json")
    return parser


def _error(code: str) -> int:
    print(f"error: {code}", file=sys.stderr, flush=True)
    return 1


def _print_urls(options: Options, hostname: str, owner: str, name: str, hash_: str) -> None:
    urls = store_urls(options, hostname, owner, name, hash_)
    print(f"internal: {urls['internal']}", flush=True)
    if "public" in urls:
        print(f"public: {urls['public']}", flush=True)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else "?"


def _users_list(args: argparse.Namespace, paths: Paths) -> int:
    options = load_options(paths.options_file)
    entries = AccessStore(paths).list_entries(args.repository)
    if not entries:
        print("no users", flush=True)
        return 0
    for entry in entries:
        repository, hash_ = entry.get("repository"), entry.get("hash")
        masked = mask_hash(hash_) if isinstance(hash_, str) and HASH_RE.fullmatch(hash_) else "<invalid>"
        active = isinstance(repository, str) and options.find(repository) is not None
        fields = [_text(repository), _text(entry.get("user")), _text(entry.get("source")), _text(entry.get("created"))]
        line = "\t".join(fields + [masked])
        print(line if active else f"{line}\t(inactive)", flush=True)
    return 0


def _users_add(args: argparse.Namespace, paths: Paths, hostname: str) -> int:
    options = load_options(paths.options_file)
    spec = options.find(args.repository)
    if spec is None:
        return _error("repository_unknown")
    entry = AccessStore(paths).add(spec.slug, args.user, source="cli", hash_=args.hash_, specs=options.repositories)
    _print_urls(options, hostname, spec.owner, spec.name, entry["hash"])
    return 0


def _users_url(args: argparse.Namespace, paths: Paths, hostname: str) -> int:
    options = load_options(paths.options_file)
    spec = options.find(args.repository)
    if spec is None:
        return _error("repository_unknown")
    entry = AccessStore(paths).get(spec.slug, args.user)
    if entry is None:
        return _error("user_unknown")
    hash_ = entry.get("hash")
    if not isinstance(hash_, str) or not HASH_RE.fullmatch(hash_):
        return _error("invalid_hash")
    _print_urls(options, hostname, spec.owner, spec.name, hash_)
    return 0


def _users_revoke(args: argparse.Namespace, paths: Paths) -> int:
    options = load_options(paths.options_file)
    spec = options.find(args.repository)
    repository = spec.slug if spec is not None else args.repository  # unconfigured repositories can be revoked too
    if not AccessStore(paths).revoke(repository, args.user, specs=options.repositories):
        return _error("user_unknown")
    print(f"revoked {args.user} from {repository}", flush=True)
    return 0


def _sync(paths: Paths) -> int:
    """Create the D-12 trigger file; the sync service starts a full cycle within about a second."""
    if not paths.run_dir.is_dir():
        paths.run_dir.mkdir(parents=True, exist_ok=True)
        paths.run_dir.chmod(0o700)
    atomic_write_json(paths.trigger_file, {})
    print("sync requested", flush=True)
    return 0


def _reconcile(paths: Paths) -> int:
    options = load_options(paths.options_file)
    links = AccessStore(paths).reconcile(options.repositories)
    print(f"{links} access links", flush=True)
    return 0


def _dispatch(args: argparse.Namespace, paths: Paths, hostname: str) -> int:
    if args.command == "sync":
        return _sync(paths)
    if args.command == "reconcile":
        return _reconcile(paths)
    if args.users_command == "list":
        return _users_list(args, paths)
    if args.users_command == "add":
        return _users_add(args, paths, hostname)
    if args.users_command == "url":
        return _users_url(args, paths, hostname)
    return _users_revoke(args, paths)


def main(argv: list[str] | None = None, paths: Paths | None = None, hostname: str | None = None) -> int:
    parser = _parser()
    try:
        args, extra = parser.parse_known_args(argv)
        needs_user = args.command == "users" and args.users_command in USER_COMMANDS
        if needs_user and args.user is None and len(extra) == 1:
            args.user, extra = extra[0], []
        if extra or (needs_user and args.user is None):
            parser.error("unrecognized or missing arguments")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    paths = paths or Paths.default()
    hostname = hostname or socket.gethostname()
    try:
        return _dispatch(args, paths, hostname)
    except AccessError as exc:
        return _error(exc.code)
    except OptionsError:
        return _error("options_invalid")


if __name__ == "__main__":
    sys.exit(main())
