"""Git access for the SOPS provider: validation, cache sync and the cheap ls-remote probe (see docs/SPEC.md).

All git calls use argv lists and timeouts. stderr is only inspected to pick an error code and is never forwarded.
Tokens travel only via the environment (GIT_ASKPASS), never via argv or the URL.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .base import ProviderError

GIT_TIMEOUT = 60
LS_REMOTE_TIMEOUT = 20
ASKPASS = Path(__file__).resolve().parent.parent / "bin" / "git-askpass"
ADDON_KNOWN_HOSTS = Path("/addon_config/known_hosts")
DEFAULT_DEPLOY_KEY = "/addon_config/deploy_key"
DEFAULT_DATA_DIR = "/data"

_SCP_RE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[^\s]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _allowed_protocols() -> str:
    return os.environ.get("SS_GIT_ALLOW_PROTOCOL") or "ssh:https"


def _file_allowed() -> bool:
    return "file" in _allowed_protocols().split(":")


def url_kind(url: str) -> str | None:
    """Return "ssh", "https" or "file" (tests only) for an acceptable URL, else None."""
    if not url or url.startswith("-") or any(c.isspace() or ord(c) < 32 for c in url):
        return None
    if _SCP_RE.match(url):
        return "ssh"
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme == "https" and parts.hostname:
        return "https"
    if parts.scheme == "ssh" and parts.hostname:
        return "ssh"
    if _file_allowed() and (parts.scheme == "file" or url.startswith("/")):
        return "file"
    return None


def url_has_credentials(url: str) -> bool:
    """https with any userinfo, or ssh with a password part, is rejected (ssh://git@host is fine)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme == "https":
        return "@" in parts.netloc
    if parts.scheme == "ssh":
        userinfo = parts.netloc.rpartition("@")[0]
        return ":" in userinfo
    return False


def path_valid(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path or "\0" in path:
        return False
    return ".." not in path.split("/")


def branch_valid(branch: str) -> bool:
    return bool(branch) and not branch.startswith("-") and not any(c.isspace() or ord(c) < 32 for c in branch)


def _classify(stderr: str, default: str) -> str:
    low = stderr.lower()
    if "remote branch" in low and "not found" in low or "couldn't find remote ref" in low:
        return "git_ref_not_found"
    if any(
        p in low
        for p in ("permission denied", "authentication failed", "could not read username", "host key verification")
    ) or any(p in low for p in ("401", "403")):
        return "git_auth_failed"
    return default


class GitSource:
    def __init__(self, url: str, branch: str, path: str, username: str = "") -> None:
        self.url = url
        self.branch = branch
        self.path = path
        self.username = username
        self.data_dir = Path(os.environ.get("SS_DATA_DIR") or DEFAULT_DATA_DIR)
        self.kind = url_kind(url)
        digest = hashlib.sha1((url + "\0" + branch).encode(), usedforsecurity=False).hexdigest()[:12]
        self.cache = self.data_dir / "git" / digest

    # -- environment -------------------------------------------------------------------------------------------

    def _env(self) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.data_dir),
            "LC_ALL": "C",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ALLOW_PROTOCOL": _allowed_protocols(),
        }
        if self.kind == "ssh":
            env["GIT_SSH_COMMAND"] = self._ssh_command()
        elif self.kind == "https":
            token = os.environ.get("SS_GIT_TOKEN")
            if token:
                env["GIT_ASKPASS"] = str(ASKPASS)
                env["SS_GIT_TOKEN"] = token
                env["SS_GIT_USERNAME"] = self.username or "x-access-token"
        return env

    def _ssh_command(self) -> str:
        key = Path(os.environ.get("SS_GIT_DEPLOY_KEY") or DEFAULT_DEPLOY_KEY)
        try:
            st = os.stat(key)
        except OSError:
            raise ProviderError("git_key_missing", "deploy key not found") from None
        if not stat.S_ISREG(st.st_mode):
            raise ProviderError("git_key_missing", "deploy key is not a regular file")
        if st.st_mode & 0o077:
            raise ProviderError("git_key_permissions", "deploy key must have mode 600 or stricter")
        if shutil.which("ssh") is None:
            raise ProviderError("git_binary_missing", "ssh binary not found")
        if ADDON_KNOWN_HOSTS.is_file():
            hosts, mode = ADDON_KNOWN_HOSTS, "yes"
        else:
            hosts, mode = self.data_dir / "known_hosts", "accept-new"
        return (
            f"ssh -i {_quote(str(key))} -o IdentitiesOnly=yes -o BatchMode=yes "
            f"-o UserKnownHostsFile={_quote(str(hosts))} -o StrictHostKeyChecking={mode}"
        )

    # -- git calls ---------------------------------------------------------------------------------------------

    def _git(self, args: list[str], timeout: int, default_code: str, cwd: Path | None = None) -> str:
        argv = ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.ext.allow=never", *args]
        env = self._env()
        try:
            proc = subprocess.run(
                argv, capture_output=True, env=env, timeout=timeout, check=False, cwd=str(cwd) if cwd else None
            )
        except subprocess.TimeoutExpired:
            raise ProviderError("git_timeout", "git timed out") from None
        except FileNotFoundError:
            raise ProviderError("git_binary_missing", "git binary not found") from None
        except OSError:
            raise ProviderError("git_exec_failed", "git could not be executed") from None
        if proc.returncode != 0:
            code = _classify(proc.stderr.decode("utf-8", "replace"), default_code)
            raise ProviderError(code, f"git failed ({code})")
        return proc.stdout.decode("utf-8", "replace")

    def probe(self) -> str:
        """`git ls-remote` for the branch head; returns the full commit SHA."""
        ref = f"refs/heads/{self.branch}"
        out = self._git(["ls-remote", "--", self.url, ref], LS_REMOTE_TIMEOUT, "git_fetch_failed")
        for line in out.splitlines():
            sha, _, name = line.partition("\t")
            if name.strip() == ref and _SHA_RE.match(sha):
                return sha
        raise ProviderError("git_ref_not_found", "branch not found")

    def sync(self) -> tuple[Path, str]:
        """Bring the cache to the branch head. Returns (resolved file path, full commit SHA)."""
        self._update_cache()
        sha = self._git(["rev-parse", "HEAD"], GIT_TIMEOUT, "git_exec_failed", cwd=self.cache).strip()
        if not _SHA_RE.match(sha):
            raise ProviderError("git_exec_failed", "unexpected git output")
        return self._resolve(), sha

    def _update_cache(self) -> None:
        if (self.cache / ".git").is_dir():
            try:
                ref = f"refs/heads/{self.branch}"
                self._git(["fetch", "--depth", "1", "origin", ref], GIT_TIMEOUT, "git_fetch_failed", cwd=self.cache)
                self._git(["reset", "--hard", "FETCH_HEAD"], GIT_TIMEOUT, "git_fetch_failed", cwd=self.cache)
                self._git(["clean", "-fdx"], GIT_TIMEOUT, "git_fetch_failed", cwd=self.cache)
                return
            except ProviderError as exc:
                if exc.code in ("git_timeout", "git_binary_missing", "git_key_missing", "git_key_permissions"):
                    raise
            # Broken cache: drop it and clone once
            shutil.rmtree(self.cache, ignore_errors=True)
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.cache, ignore_errors=True)
        try:
            self._git(
                ["clone", "--depth", "1", "--single-branch", "--branch", self.branch, "--", self.url, str(self.cache)],
                GIT_TIMEOUT,
                "git_clone_failed",
            )
        except ProviderError:
            shutil.rmtree(self.cache, ignore_errors=True)
            raise

    def _resolve(self) -> Path:
        if not path_valid(self.path):
            raise ProviderError("git_path_invalid", "git_path is invalid")
        root = self.cache.resolve()
        cur = root
        for part in self.path.split("/"):
            if part in ("", "."):
                continue
            cur = cur / part
            if cur.is_symlink():
                raise ProviderError("git_path_invalid", "git_path must not contain symlinks")
        try:
            resolved = cur.resolve(strict=True)
        except (FileNotFoundError, NotADirectoryError):
            raise ProviderError("git_file_missing", "file not found in repository") from None
        except OSError:
            raise ProviderError("git_path_invalid", "git_path cannot be resolved") from None
        if root != resolved and root not in resolved.parents:
            raise ProviderError("git_path_invalid", "git_path escapes the repository")
        if not resolved.is_file():
            raise ProviderError("git_file_missing", "git_path is not a regular file")
        return resolved


def _quote(value: str) -> str:
    """Quote for GIT_SSH_COMMAND, which git runs through a shell."""
    return "'" + value.replace("'", "'\\''") + "'"
