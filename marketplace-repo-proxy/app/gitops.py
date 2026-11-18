"""git plumbing for the sync service: upstream resolution, per-call environments, bare repository create/fetch.

The GitHub PAT exists only in the environment dict of one git child process (`GIT_CONFIG_VALUE_0`); it is never put
into argv, a remote URL or a repository config (D-08).
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from app.options import RepoSpec
from app.paths import Paths

UPSTREAM_OVERRIDE_ENV = "MRP_TEST_UPSTREAM_BASE"  # test only: container environment, never options or manifests
DEFAULT_UPSTREAM = "https://github.com"
PUSH_DISABLED_URL = "no-push://disabled"
GIT_TIMEOUT = 600

_BASE_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LC_ALL": "C",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


class UpstreamOverrideError(ValueError):
    """The test upstream override is set but not a plain http(s) base URL."""


@dataclass(frozen=True)
class Upstream:
    base: str
    allow_protocol: str
    overridden: bool


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


def resolve_upstream(environ: Mapping[str, str]) -> Upstream:
    """Upstream base URL: GitHub, or the test override from the given environment mapping."""
    value = environ.get(UPSTREAM_OVERRIDE_ENV, "")
    if not value:
        return Upstream(DEFAULT_UPSTREAM, "https", False)
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError as exc:
        raise UpstreamOverrideError("upstream override is not a valid URL") from exc
    if parts.scheme not in ("http", "https") or not host:
        raise UpstreamOverrideError("upstream override needs an http(s) scheme and a host")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UpstreamOverrideError("upstream override must not carry userinfo")
    if parts.query or parts.fragment or "?" in value or "#" in value:
        raise UpstreamOverrideError("upstream override must not carry a query or fragment")
    return Upstream(value.rstrip("/"), parts.scheme, True)


def remote_url(upstream: Upstream, spec: RepoSpec) -> str:
    return f"{upstream.base}/{spec.owner}/{spec.name}.git"


def auth_env(token: str, allow_protocol: str) -> dict[str, str]:
    """Environment for one authenticated git call, built from scratch (never a copy of the process env)."""
    header = "Authorization: Basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = dict(_BASE_ENV)
    env.update(
        {
            "GIT_ALLOW_PROTOCOL": allow_protocol,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": header,
        }
    )
    return env


def local_env() -> dict[str, str]:
    """Environment for local-only git calls: no credentials, no network protocols."""
    env = dict(_BASE_ENV)
    env["GIT_ALLOW_PROTOCOL"] = "file"
    return env


def run_git(
    args: Sequence[str], env: Mapping[str, str], cwd: Path | None = None, timeout: int = GIT_TIMEOUT
) -> GitResult:
    """Run git; never raises on a non-zero exit. A timeout maps to returncode 124."""
    try:
        proc = subprocess.run(
            ["git", *args],
            env=dict(env),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GitResult(124, "", "timeout")
    return GitResult(proc.returncode, proc.stdout, proc.stderr)


def default_branch(url: str, env: Mapping[str, str]) -> str | None:
    """Upstream default branch from `ls-remote --symref`, None when the upstream has none."""
    result = run_git(["ls-remote", "--symref", url, "HEAD"], env)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            return line[len("ref: refs/heads/") : -len("\tHEAD")] or None
    return None


def configure_repo(repo_dir: Path, url: str, branch: str) -> None:
    """Fetch refspec for one branch, push disabled, smart-HTTP read-only, HEAD on the branch (D-10, D-15)."""
    env = local_env()
    git_dir = ["--git-dir", str(repo_dir)]
    settings = (
        ["config", "remote.origin.url", url],
        ["config", "--replace-all", "remote.origin.fetch", f"+refs/heads/{branch}:refs/heads/{branch}"],
        ["config", "remote.origin.pushurl", PUSH_DISABLED_URL],
        ["config", "http.receivepack", "false"],
        ["config", "http.getanyfile", "false"],
        ["symbolic-ref", "HEAD", f"refs/heads/{branch}"],
    )
    for args in settings:
        result = run_git([*git_dir, *args], env)
        if result.returncode != 0:
            first = (result.stderr.strip().splitlines() or [""])[0]
            raise RuntimeError(f"git {args[0]} failed: {first}")


def fetch(repo_dir: Path, env: Mapping[str, str]) -> GitResult:
    """Full-history fetch of the configured refspec; maintenance stays out of the authenticated call."""
    return run_git(
        [
            "--git-dir",
            str(repo_dir),
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            "-c",
            "http.lowSpeedLimit=1000",
            "-c",
            "http.lowSpeedTime=60",
            "fetch",
            "--prune",
            "--no-tags",
            "origin",
        ],
        env,
    )


def classify(result: GitResult) -> tuple[str, str]:
    """RED stub."""
    return "fetch_failed", ""


def sanitize(text: str, limit: int = 300) -> str:
    """RED stub."""
    return text


def check_branch_name(branch: str) -> bool:
    """RED stub."""
    return True


@dataclass(frozen=True)
class HeadInfo:
    head: str | None
    has_repository_yaml: bool
    addons: tuple[str, ...]


def inspect_head(repo_dir: Path) -> HeadInfo:
    """RED stub."""
    return HeadInfo(None, False, ())


def ref_snapshot(repo_dir: Path) -> dict[str, str]:
    """RED stub."""
    return {}


def prune_foreign_refs(repo_dir: Path, branch: str) -> int:
    """RED stub."""
    return 0


def run_maintenance(repo_dir: Path) -> GitResult:
    """RED stub."""
    return GitResult(0, "", "")


def cleanup_stale_tmp(paths: Paths) -> int:
    """RED stub."""
    return 0


def ensure_and_fetch(paths: Paths, spec: RepoSpec, url: str, branch: str, env: Mapping[str, str]) -> GitResult:
    """Fetch into the bare repository; a new one is built in a temp dir and renamed only after a good fetch."""
    final = paths.repo_dir(spec.owner, spec.name)
    if final.exists():
        configure_repo(final, url, branch)
        return fetch(final, env)
    final.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmp = final.parent / f".{spec.name}.git.tmp"
    if tmp.exists() or tmp.is_symlink():
        shutil.rmtree(tmp, ignore_errors=True)
    created = run_git(["init", "--bare", "-q", str(tmp)], local_env())
    if created.returncode != 0:
        return created
    try:
        configure_repo(tmp, url, branch)
        result = fetch(tmp, env)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return result
    os.rename(tmp, final)
    return result
