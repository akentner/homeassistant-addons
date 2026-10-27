"""Atomic, verified writes for secrets.yaml and provider files (see docs/SPEC.md, security rules 2 and 4)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import yaml

HEADER = "# managed by Secrets Sync - do not edit\n"
# Characters PyYAML treats as line breaks or rejects as non-printable: emit them as \uXXXX escapes
_ESCAPE = re.compile("[\x7f-\x9f  ￾￿]")


class WriteError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UnsafePathError(WriteError):
    def __init__(self, message: str = "unsafe path") -> None:
        super().__init__("unsafe_path", message)


@dataclass
class FilesResult:
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # existing files we do not manage


# ---------------------------------------------------------------- secrets.yaml


def _quote(text: str) -> str:
    return _ESCAPE.sub(lambda m: "\\u%04x" % ord(m.group()), json.dumps(text, ensure_ascii=False))


def render_secrets(secrets: Mapping[str, str]) -> str:
    return HEADER + "".join(f"{_quote(str(k))}: {_quote(str(secrets[k]))}\n" for k in sorted(secrets))


def verify_roundtrip(text: str, secrets: Mapping[str, str]) -> None:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WriteError("yaml_verify_failed", f"rendered YAML does not parse ({type(exc).__name__})") from exc
    if (loaded or {}) != dict(secrets):
        raise WriteError("yaml_verify_failed", "rendered YAML does not round-trip to the input")


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _stage(path: Path, data: bytes) -> Path:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = _stage(path, data)
    try:
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


def _read_existing(path: Path) -> bytes | None:
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(mode):
        raise UnsafePathError("target is not a regular file")
    return path.read_bytes()


def write_secrets(path: Path, secrets: Mapping[str, str]) -> bool:
    """Write `secrets` to `path`. Returns False if the content is already byte-identical."""
    text = render_secrets(secrets)
    verify_roundtrip(text, secrets)
    try:
        data = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WriteError("yaml_verify_failed", "value is not encodable as UTF-8") from exc
    tmp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = _read_existing(path)
        if previous == data:
            os.chmod(path, 0o600)
            return False
        tmp = _stage(path, data)
        verify_roundtrip(tmp.read_text(encoding="utf-8"), secrets)
        if previous is not None:
            _atomic_write(path.with_name(path.name + ".bak"), previous)
        os.replace(tmp, path)
        tmp = None
        _fsync_dir(path.parent)
        os.chmod(path, 0o600)
    except OSError as exc:
        raise WriteError("write_failed", f"cannot write {path.name} ({type(exc).__name__})") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return True


def read_secrets(path: Path) -> dict[str, str] | None:
    """Current secrets.yaml as dict (None if missing or unreadable). Used for key diffs only."""
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return None
    return {str(k): str(v) for k, v in loaded.items()}


# ---------------------------------------------------------------- provider files


def safe_relpath(rel: str) -> tuple[str, ...]:
    """Validate a provider supplied relative path and return its segments."""
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\\" in rel or "\0" in rel:
        raise UnsafePathError()
    parts = tuple(rel.split("/"))
    if any(p in ("", ".", "..") for p in parts):
        raise UnsafePathError()
    return parts


def _target(base: Path, parts: tuple[str, ...], create: bool) -> Path | None:
    """Walk below `base` without following symlinks. None if (not create and) a component is missing."""
    cur = base
    for index, part in enumerate(parts):
        cur = cur / part
        last = index == len(parts) - 1
        try:
            mode = os.lstat(cur).st_mode
        except FileNotFoundError:
            if last:
                return cur
            if not create:
                return None
            os.mkdir(cur, 0o700)
            continue
        if stat.S_ISLNK(mode):
            raise UnsafePathError("symlink in path")
        if last and not stat.S_ISREG(mode):
            raise UnsafePathError("target is not a regular file")
        if not last and not stat.S_ISDIR(mode):
            raise UnsafePathError("path component is not a directory")
    return cur


def load_manifest(path: Path) -> dict[str, str]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        files = loaded["files"]
        return {str(k): str(v) for k, v in files.items()}
    except (OSError, ValueError, KeyError, AttributeError, TypeError):
        return {}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_files(files_dir: Path, manifest_path: Path, files: Mapping[str, bytes]) -> FilesResult:
    result = FilesResult()
    manifest = load_manifest(manifest_path)
    new_manifest: dict[str, str] = {}
    files_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        for rel in sorted(files):
            data = files[rel]
            parts = safe_relpath(rel)
            target = _target(files_dir, parts, create=True)
            assert target is not None
            digest = _sha(data)
            try:
                current = target.read_bytes() if os.path.lexists(target) else None
            except OSError as exc:
                raise WriteError("write_failed", f"cannot read {rel} ({type(exc).__name__})") from exc
            if current is not None and current != data and rel not in manifest:
                result.skipped.append(rel)
                continue
            if current != data:
                _atomic_write(target, data)
                result.written.append(rel)
            else:
                os.chmod(target, 0o600)
            new_manifest[rel] = digest
        for rel in sorted(set(manifest) - set(files)):
            try:
                parts = safe_relpath(rel)
                target = _target(files_dir, parts, create=False)
            except UnsafePathError:
                continue  # tampered manifest entry: forget it, never touch the path
            if target is not None and os.path.lexists(target):
                target.unlink()
                result.removed.append(rel)
                for parent in target.parents:
                    if parent == files_dir:
                        break
                    try:
                        parent.rmdir()
                    except OSError:
                        break
    except OSError as exc:
        raise WriteError("write_failed", f"cannot write provider files ({type(exc).__name__})") from exc
    # Keep entries of skipped (unmanaged) files out of the manifest so they stay untouched
    if new_manifest != manifest:
        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(manifest_path, json.dumps({"version": 1, "files": new_manifest}, indent=2).encode())
        except OSError as exc:
            raise WriteError("write_failed", f"cannot write manifest ({type(exc).__name__})") from exc
    return result
