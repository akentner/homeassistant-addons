#!/usr/bin/env python3
"""Sync the admin-UI lib and Python skeleton into add-on consumers and detect drift (D-05, D-06, PD-01, PD-04).

The Docker build context of an add-on is ./<addon>, so the shared code is distributed by copy:

    admin-ui/app/web/static/lib/  ->  <addon>/app/web/static/vendor/admin-ui/   (LIB.stamp)
    admin-ui/app/web/skeleton/    ->  <addon>/app/web/admin_ui/                 (LIB.stamp)

Each copy carries a plain-text LIB.stamp ("version X.Y.Z" / "sha256 <tree hash>") and admin-ui/lib.lock records the
source state. Usage:

    sync-admin-ui.py                  refresh admin-ui/lib.lock only
    sync-admin-ui.py --addon NAME     copy to that consumer (repeatable, creates it), refresh the lock
    sync-admin-ui.py --all            copy to every discovered consumer, refresh the lock
    sync-admin-ui.py --release X.Y.Z  advance the lib version, sync all consumers and strictly check
    sync-admin-ui.py --check [--strict]   verify lock, copies and versions

Exit codes: 0 ok (warnings allowed), 1 drift, 2 usage or IO error. Stdlib only; never touches git or the network.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

SOURCE_ADDON = "admin-ui"
LIB_SRC = Path(SOURCE_ADDON) / "app/web/static/lib"
SKELETON_SRC = Path(SOURCE_ADDON) / "app/web/skeleton"
LOCK = Path(SOURCE_ADDON) / "lib.lock"
LIB_DST = Path("app/web/static/vendor/admin-ui")
SKELETON_DST = Path("app/web/admin_ui")
STAMP_NAME = "LIB.stamp"
VERSION_FILE = "VERSION"

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SKIP_DIRS = {"__pycache__"}


class SyncError(Exception):
    """Unsafe input or IO problem (exit code 2)."""


def _skipped(name: str) -> bool:
    return name == STAMP_NAME or name.endswith(".pyc")


def tree_hash(root: Path) -> str:
    """Deterministic sha256 over relative paths and file contents; refuses symlinks anywhere in the tree."""
    if root.is_symlink():
        raise SyncError(f"symlink not allowed: {root}")
    entries: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        for name in list(dirnames):
            if (base / name).is_symlink():
                raise SyncError(f"symlink not allowed: {base / name}")
            if name in SKIP_DIRS:
                dirnames.remove(name)
        for name in filenames:
            path = base / name
            if path.is_symlink():
                raise SyncError(f"symlink not allowed: {path}")
            if not _skipped(name):
                entries.append((path.relative_to(root).as_posix(), path))
    digest = hashlib.sha256()
    for rel, path in sorted(entries):
        digest.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


def read_version(lib_dir: Path) -> str:
    try:
        version = (lib_dir / VERSION_FILE).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SyncError(f"cannot read {lib_dir / VERSION_FILE}: {exc}") from exc
    if not VERSION_RE.match(version):
        raise SyncError(f"invalid version in {lib_dir / VERSION_FILE}: {version!r}")
    return version


def vkey(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def parse_kv(text: str, keys: tuple[str, ...]) -> dict[str, str] | None:
    """Strict parser: exactly the given keys in order, `key value` per line, valid version and 64-hex values."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) != len(keys):
        return None
    out: dict[str, str] = {}
    for line, key in zip(lines, keys):
        parts = line.split(" ")
        if len(parts) != 2 or parts[0] != key:
            return None
        value = parts[1]
        ok = VERSION_RE.match(value) if key == "version" else HASH_RE.match(value)
        if not ok:
            return None
        out[key] = value
    return out


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def source_state(root: Path) -> tuple[str, str, str]:
    lib, skeleton = root / LIB_SRC, root / SKELETON_SRC
    for path in (lib, skeleton):
        if not path.is_dir():
            raise SyncError(f"source directory missing: {path}")
    return read_version(lib), tree_hash(lib), tree_hash(skeleton)


def lock_text(version: str, lib_hash: str, skeleton_hash: str) -> str:
    return f"version {version}\nlib {lib_hash}\nskeleton {skeleton_hash}\n"


def stamp_text(version: str, digest: str) -> str:
    return f"version {version}\nsha256 {digest}\n"


def validate_name(root: Path, name: str) -> Path:
    if not NAME_RE.match(name) or name == SOURCE_ADDON:
        raise SyncError(f"invalid add-on name: {name!r}")
    addon = root / name
    if addon.is_symlink() or not addon.is_dir() or not (addon / "config.yaml").is_file():
        raise SyncError(f"not an add-on directory with config.yaml: {name}")
    resolved_root = root.resolve()
    for dst in (LIB_DST, SKELETON_DST):
        try:
            (addon / dst).resolve().relative_to(resolved_root)
        except ValueError as exc:
            raise SyncError(f"destination escapes the repository root: {name}") from exc
    return addon


def discover_consumers(root: Path) -> list[str]:
    names = []
    for entry in sorted(root.iterdir()):
        if entry.name == SOURCE_ADDON or entry.name.startswith(".") or not entry.is_dir() or entry.is_symlink():
            continue
        if (entry / LIB_DST / STAMP_NAME).exists() or (entry / SKELETON_DST / STAMP_NAME).exists():
            names.append(entry.name)
    return names


def copy_part(src: Path, dst: Path, version: str, digest: str) -> bool:
    """Replace dst with a copy of src plus stamp; returns False when it was already up to date."""
    stamp = stamp_text(version, digest)
    stamp_path = dst / STAMP_NAME
    if dst.is_dir() and not dst.is_symlink():
        if tree_hash(dst) == digest and stamp_path.is_file() and stamp_path.read_text(encoding="utf-8") == stamp:
            return False
    elif dst.is_symlink():
        raise SyncError(f"symlink not allowed: {dst}")
    tmp = dst.with_name(dst.name + ".sync-tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", STAMP_NAME), symlinks=False)
    if tree_hash(tmp) != digest:
        shutil.rmtree(tmp)
        raise SyncError(f"copy of {src} does not match its source hash")
    write_text(tmp / STAMP_NAME, stamp)
    if dst.exists():
        shutil.rmtree(dst)
    tmp.rename(dst)
    return True


def do_sync(root: Path, addons: list[str], all_consumers: bool) -> int:
    targets = [validate_name(root, name) for name in addons]
    if all_consumers:
        targets += [validate_name(root, name) for name in discover_consumers(root) if name not in addons]
    version, lib_hash, skeleton_hash = source_state(root)
    for addon in targets:
        for src, dst_rel, digest in ((LIB_SRC, LIB_DST, lib_hash), (SKELETON_SRC, SKELETON_DST, skeleton_hash)):
            changed = copy_part(root / src, addon / dst_rel, version, digest)
            print(f"{'UPDATED' if changed else 'up to date'} {addon.name} {dst_rel}", flush=True)
    new_lock = lock_text(version, lib_hash, skeleton_hash)
    lock_path = root / LOCK
    if lock_path.is_file() and lock_path.read_text(encoding="utf-8") == new_lock:
        print(f"up to date {LOCK}", flush=True)
    else:
        write_text(lock_path, new_lock)
        print(f"UPDATED {LOCK} (version {version})", flush=True)
    return 0


def check_part(
    consumer: str, label: str, dst: Path, version: str, digest: str, strict: bool, is_lib: bool
) -> tuple[int, list[str]]:
    """Returns (fail count, report lines) for one copy."""
    where = f"{consumer} {label}"
    stamp_path = dst / STAMP_NAME
    if not stamp_path.is_file():
        return 1, [f"FAIL {where}: missing copy or stamp (run make sync-admin-ui)"]
    try:
        stamp = parse_kv(stamp_path.read_text(encoding="utf-8"), ("version", "sha256"))
    except (OSError, UnicodeDecodeError):
        stamp = None
    if stamp is None:
        return 1, [f"FAIL {where}: tampered (stamp malformed)"]
    if tree_hash(dst) != stamp["sha256"]:
        return 1, [f"FAIL {where}: tampered (content differs from its stamp)"]
    if is_lib and read_version(dst) != stamp["version"]:
        return 1, [f"FAIL {where}: tampered (VERSION differs from its stamp)"]
    have, want = vkey(stamp["version"]), vkey(version)
    if have == want:
        if stamp["sha256"] != digest:
            return 1, [f"FAIL {where}: same version {version}, different hash (bump lib/VERSION and sync)"]
        return 0, [f"OK {where}: {version}"]
    if have < want:
        line = f"{where}: behind (copy {stamp['version']}, source {version})"
        return (1, [f"FAIL {line}"]) if strict else (0, [f"WARN {line}"])
    return 1, [f"FAIL {where}: ahead (copy {stamp['version']}, source {version})"]


def do_check(root: Path, strict: bool) -> int:
    version, lib_hash, skeleton_hash = source_state(root)
    fails = 0
    lock_path = root / LOCK
    lock = None
    if lock_path.is_file():
        lock = parse_kv(lock_path.read_text(encoding="utf-8"), ("version", "lib", "skeleton"))
    if lock is None:
        print(f"FAIL {SOURCE_ADDON} lock: {LOCK} missing or malformed (run make sync-admin-ui)")
        fails += 1
    elif (lock["version"], lock["lib"], lock["skeleton"]) != (version, lib_hash, skeleton_hash):
        print(f"FAIL {SOURCE_ADDON} lock: stale (source changed without refreshing {LOCK})")
        fails += 1
    else:
        print(f"OK {SOURCE_ADDON} lock: {version}")
    for name in discover_consumers(root):
        addon = validate_name(root, name)
        for label, dst_rel, digest, is_lib in (
            ("lib", LIB_DST, lib_hash, True),
            ("skeleton", SKELETON_DST, skeleton_hash, False),
        ):
            count, lines = check_part(name, label, addon / dst_rel, version, digest, strict, is_lib)
            fails += count
            for line in lines:
                print(line)
    return 1 if fails else 0


def release(root: Path, version: str) -> int:
    """Prepare a monorepo library release; no tags, commits, manifest bumps or network access."""
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise SyncError(f"invalid release version: {version!r}")
    current, lib_hash, skeleton_hash = source_state(root)
    if vkey(version) < vkey(current):
        raise SyncError(f"release {version} is older than current lib {current}")
    if version == current:
        lock = root / LOCK
        if not lock.is_file() or lock.read_text(encoding="utf-8") != lock_text(current, lib_hash, skeleton_hash):
            raise SyncError("source changed: release a newer lib version instead of reusing this version")
    # Validate every target before changing VERSION and never downgrade a consumer.
    for name in discover_consumers(root):
        addon = validate_name(root, name)
        for rel in (LIB_DST, SKELETON_DST):
            if (addon / rel).is_symlink():
                raise SyncError(f"symlink not allowed: {addon / rel}")
        dst = addon / LIB_DST
        if dst.exists() and vkey(read_version(dst)) > vkey(version):
            raise SyncError(f"consumer {name} is newer than release {version}")
    if version != current:
        write_text(root / LIB_SRC / VERSION_FILE, version + "\n")
    do_sync(root, [], True)
    return do_check(root, True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="repository root")
    parser.add_argument("--check", action="store_true", help="verify lock, copies and versions")
    parser.add_argument("--strict", action="store_true", help="with --check: a consumer behind the source fails")
    parser.add_argument("--release", metavar="X.Y.Z", help="prepare a lib release and sync all consumers")
    parser.add_argument("--all", action="store_true", help="copy to every discovered consumer")
    parser.add_argument("--addon", action="append", default=[], metavar="NAME", help="copy to this consumer")
    args = parser.parse_args(argv)
    root: Path = args.root
    try:
        if args.release is not None and (args.check or args.strict or args.addon or args.all):
            raise SyncError("--release cannot be combined with sync/check options")
        if args.check and (args.addon or args.all):
            raise SyncError("--check cannot be combined with --addon or --all")
        if args.strict and not args.check:
            raise SyncError("--strict requires --check")
        if not root.is_dir():
            raise SyncError(f"root is not a directory: {root}")
        if args.release is not None:
            return release(root, args.release)
        if args.check:
            return do_check(root, args.strict)
        return do_sync(root, args.addon, args.all)
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
