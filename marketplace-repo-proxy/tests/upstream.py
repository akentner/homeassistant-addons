"""Local bare-upstream fixtures for tests: no network, isolated git config, placeholder identity."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from app.gitops import Upstream

_IDENTITY = {
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}


def git_env() -> dict[str, str]:
    """Environment for fixture git calls: no global/system config (signing, hooks), fixed identity."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    env.update(_IDENTITY)
    return env


def git(args: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> str:
    """Run a fixture git command; raises on failure, returns stdout."""
    proc = subprocess.run(
        ["git", *args], env=env or git_env(), cwd=cwd, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def make_upstream(root: Path, owner: str, name: str, files: dict[str, str], branch: str = "main") -> Path:
    """Bare repository under `root/upstream/{owner}/{name}.git`, with one commit when `files` is not empty."""
    bare = Path(root) / "upstream" / owner / f"{name}.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    git(["init", "--bare", "-q", f"--initial-branch={branch}", str(bare)])
    if files:
        commit(bare, files, "initial", branch=branch)
    return bare


def commit(bare: Path, files: dict[str, str], message: str, branch: str | None = None) -> str:
    """Commit `files` on top of `branch` (default: the bare repo's HEAD branch) and return the new full SHA.

    A missing branch starts from the current HEAD commit, so a new branch carries the existing tree.
    """
    gd = ["--git-dir", str(bare)]
    if branch is None:
        branch = git([*gd, "symbolic-ref", "--short", "HEAD"]).strip()
    with tempfile.TemporaryDirectory(prefix="mrp-fixture-") as tmp:
        work = Path(tmp) / "work"
        work.mkdir()
        env = git_env()
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")
        parent = _resolve(bare, f"refs/heads/{branch}") or _resolve(bare, "HEAD")
        wt = [*gd, "--work-tree", str(work)]
        if parent:
            git([*wt, "read-tree", parent], env=env)
        for rel, content in files.items():
            target = work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git([*wt, "add", "--", *files.keys()], env=env, cwd=work)
        tree = git([*gd, "write-tree"], env=env).strip()
        args = [*gd, "commit-tree", tree, "-m", message]
        if parent:
            args += ["-p", parent]
        sha = git(args, env=env).strip()
        git([*gd, "update-ref", f"refs/heads/{branch}", sha])
    return sha


def _resolve(bare: Path, ref: str) -> str | None:
    proc = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        env=git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or None


def file_upstream(root: Path) -> Upstream:
    """Upstream pointing at `root/upstream` over file:// (tests only; the env override accepts http(s) only)."""
    return Upstream(base=f"file://{Path(root)}/upstream", allow_protocol="file", overridden=True)
