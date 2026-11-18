"""git plumbing for the sync service: upstream resolution, per-call environments, bare repository create/fetch.

The GitHub PAT exists only in the environment dict of one git child process (`GIT_CONFIG_VALUE_0`); it is never put
into argv, a remote URL or a repository config (D-08).
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from app.logsetup import mask_hashes
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


def ls_remote_head(url: str, env: Mapping[str, str]) -> tuple[GitResult, str | None]:
    """`ls-remote --symref <url> HEAD` result plus the default branch it names (None when there is none)."""
    result = run_git(["ls-remote", "--symref", url, "HEAD"], env)
    if result.returncode != 0:
        return result, None
    for line in result.stdout.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            return result, line[len("ref: refs/heads/") : -len("\tHEAD")] or None
    return result, None


def default_branch(url: str, env: Mapping[str, str]) -> str | None:
    """Upstream default branch from `ls-remote --symref`, None when the upstream has none."""
    return ls_remote_head(url, env)[1]


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


def fetch(repo_dir: Path, url: str, branch: str, env: Mapping[str, str]) -> GitResult:
    """Full-history fetch of one branch with an explicit refspec; maintenance stays out of the authenticated call.

    The refspec is passed on the command line instead of read from the repository config, so a fetch of a new branch
    never depends on (or changes) the served `HEAD`; `--prune` only acts inside this one refspec.
    """
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
            url,
            f"+refs/heads/{branch}:refs/heads/{branch}",
        ],
        env,
    )


AUTH_FAILED_MESSAGE = "upstream rejected the credentials (expired, revoked or missing access)"
NOT_FOUND_MESSAGE = "repository or branch not found upstream"
REPOSITORY_FILES = ("repository.yaml", "repository.yml", "repository.json")
CONFIG_SUFFIXES = (".yaml", ".yml", ".json")

# stderr is produced under LC_ALL=C; git never prints "401" for a prompt-less 401, it asks for a username instead
_AUTH_RE = re.compile(
    r"could not read (username|password)|terminal prompts disabled|returned error: 40[13]\b|authentication failed",
    re.IGNORECASE,
)
_NOT_FOUND_RE = re.compile(
    r"repository '[^']*' not found|couldn't find remote ref|returned error: 404\b"
    r"|does not appear to be a git repository",
    re.IGNORECASE,
)


def sanitize(text: str, limit: int = 300) -> str:
    """One human-readable line from git output: no `Authorization` line, 32-hex runs masked, at most `limit` chars."""
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and "authorization" not in line.lower()
    ]
    if not lines:
        return ""
    chosen = next((line for line in lines if line.lower().startswith(("fatal:", "error:"))), lines[0])
    chosen = mask_hashes(chosen)
    if len(chosen) > limit:
        chosen = chosen[: limit - 1] + "…"
    return chosen


def classify(result: GitResult) -> tuple[str, str]:
    """Map a git result to a stable status code (D-14, D-26) and a secret-free one-line message."""
    if result.returncode == 0:
        return "ok", ""
    if result.returncode == 124 and result.stderr.strip() == "timeout":
        return "fetch_failed", "timeout"
    if _AUTH_RE.search(result.stderr):
        return "auth_failed", AUTH_FAILED_MESSAGE
    if _NOT_FOUND_RE.search(result.stderr):
        return "not_found", NOT_FOUND_MESSAGE
    return "fetch_failed", sanitize(result.stderr) or f"git exited with status {result.returncode}"


def check_branch_name(branch: str) -> bool:
    """True when git accepts `branch` as a branch name (`git check-ref-format --branch`)."""
    if not branch or branch.startswith("-") or "@{" in branch:
        return False
    return run_git(["check-ref-format", "--branch", branch], local_env()).returncode == 0


@dataclass(frozen=True)
class HeadInfo:
    head: str | None
    has_repository_yaml: bool
    addons: tuple[str, ...]


def _is_addon_config(path: PurePosixPath) -> bool:
    """Supervisor discovery rule: `**/config.*` with a yaml|yml|json suffix, no part hidden or named `rootfs`."""
    if path.stem != "config" or path.suffix not in CONFIG_SUFFIXES:
        return False
    return not any(part.startswith(".") or part == "rootfs" for part in path.parts)


def inspect_head(repo_dir: Path) -> HeadInfo:
    """HEAD commit, repository.yaml presence and add-on directories, read from the bare repository (no checkout)."""
    env = local_env()
    git_dir = ["--git-dir", str(repo_dir)]
    rev = run_git([*git_dir, "rev-parse", "--verify", "--quiet", "--short=12", "HEAD"], env)
    if rev.returncode != 0 or not rev.stdout.strip():
        return HeadInfo(None, False, ())
    head = rev.stdout.strip()
    top = run_git([*git_dir, "ls-tree", "-z", "--name-only", "HEAD"], env)
    names = set(top.stdout.split("\0")) if top.returncode == 0 else set()
    tree = run_git([*git_dir, "ls-tree", "-r", "-z", "--name-only", "HEAD"], env)
    addons: set[str] = set()
    if tree.returncode == 0:
        for name in tree.stdout.split("\0"):
            if not name:
                continue
            path = PurePosixPath(name)
            if _is_addon_config(path):
                addons.add(str(path.parent))
    return HeadInfo(head, any(name in names for name in REPOSITORY_FILES), tuple(sorted(addons)))


def ref_snapshot(repo_dir: Path) -> dict[str, str]:
    """Every ref with its object id plus the `HEAD` symbolic target; empty for a missing repository."""
    if not Path(repo_dir).is_dir():
        return {}
    env = local_env()
    git_dir = ["--git-dir", str(repo_dir)]
    snapshot: dict[str, str] = {}
    refs = run_git([*git_dir, "for-each-ref", "--format=%(refname) %(objectname)"], env)
    if refs.returncode == 0:
        for line in refs.stdout.splitlines():
            name, _, oid = line.partition(" ")
            if name:
                snapshot[name] = oid
    head = run_git([*git_dir, "symbolic-ref", "-q", "HEAD"], env)
    if head.returncode == 0 and head.stdout.strip():
        snapshot["HEAD"] = head.stdout.strip()
    return snapshot


def prune_foreign_refs(repo_dir: Path, branch: str) -> int:
    """Delete every ref other than `refs/heads/{branch}` (`fetch --prune` only prunes inside the refspec, D-10)."""
    env = local_env()
    git_dir = ["--git-dir", str(repo_dir)]
    keep = f"refs/heads/{branch}"
    refs = run_git([*git_dir, "for-each-ref", "--format=%(refname)"], env)
    if refs.returncode != 0:
        return 0
    removed = 0
    for name in refs.stdout.split():
        if name != keep and run_git([*git_dir, "update-ref", "-d", name], env).returncode == 0:
            removed += 1
    return removed


def run_maintenance(repo_dir: Path) -> GitResult:
    """`git maintenance run --auto` with the credential-free environment only (D-08)."""
    return run_git(["--git-dir", str(repo_dir), "maintenance", "run", "--auto"], local_env())


def cleanup_stale_tmp(paths: Paths) -> int:
    """Remove `{repos_root}/*/.*.git.tmp` left behind by a crash during a first fetch."""
    if not paths.repos_root.is_dir():
        return 0
    removed = 0
    for tmp in paths.repos_root.glob("*/.*.git.tmp"):
        if tmp.is_symlink() or not tmp.is_dir():
            tmp.unlink(missing_ok=True)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
        removed += 1
    return removed


def ensure_and_fetch(paths: Paths, spec: RepoSpec, url: str, branch: str, env: Mapping[str, str]) -> GitResult:
    """Fetch into the bare repository; a new one is built in a temp dir and renamed only after a good fetch.

    For an existing repository, `HEAD` and the stored refspec move to `branch` only after its fetch succeeded: a failed
    fetch after a branch change (typo, branch not pushed yet, expired token) leaves the previous branch served.
    """
    final = paths.repo_dir(spec.owner, spec.name)
    if final.exists():
        result = fetch(final, url, branch, env)
        if result.returncode == 0:
            configure_repo(final, url, branch)
        return result
    final.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmp = final.parent / f".{spec.name}.git.tmp"
    if tmp.exists() or tmp.is_symlink():
        shutil.rmtree(tmp, ignore_errors=True)
    created = run_git(["init", "--bare", "-q", str(tmp)], local_env())
    if created.returncode != 0:
        return created
    try:
        configure_repo(tmp, url, branch)
        result = fetch(tmp, url, branch, env)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return result
    os.rename(tmp, final)
    return result
