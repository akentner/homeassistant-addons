"""gitops: failure classification, sanitising, HEAD inspection, ref hygiene, environments and upstream resolution."""

from __future__ import annotations

import base64
import http.server
import socket
import subprocess
import threading
from pathlib import Path

import pytest
from upstream import commit, file_upstream, git, git_env, make_upstream

from app import gitops
from app.gitops import (
    GitResult,
    HeadInfo,
    Upstream,
    UpstreamOverrideError,
    auth_env,
    check_branch_name,
    classify,
    cleanup_stale_tmp,
    ensure_and_fetch,
    inspect_head,
    prune_foreign_refs,
    ref_snapshot,
    remote_url,
    resolve_upstream,
    run_maintenance,
    sanitize,
)
from app.options import RepoSpec
from app.paths import Paths

AUTH_MESSAGE = "upstream rejected the credentials (expired, revoked or missing access)"
NOT_FOUND_MESSAGE = "repository or branch not found upstream"


def _token() -> str:
    # Built at runtime so no token-shaped literal sits in the repository
    return "sentinel" + "-pat-" + "0123456789"


# --- classify ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (GitResult(0, "", ""), "ok"),
        (GitResult(128, "", "fatal: could not read Username for 'http://h': terminal prompts disabled\n"), "auth_failed"),
        (
            GitResult(128, "", "fatal: unable to access 'http://h/o/r.git/': The requested URL returned error: 403\n"),
            "auth_failed",
        ),
        (
            GitResult(128, "", "fatal: unable to access 'http://h/o/r.git/': The requested URL returned error: 401\n"),
            "auth_failed",
        ),
        (GitResult(128, "", "fatal: repository 'http://h/o/r.git/' not found\n"), "not_found"),
        (GitResult(128, "", "fatal: couldn't find remote ref refs/heads/x\n"), "not_found"),
        (
            GitResult(128, "", "fatal: unable to access 'http://h/o/r.git/': Could not resolve host: h\n"),
            "fetch_failed",
        ),
        (GitResult(124, "", "timeout"), "fetch_failed"),
    ],
)
def test_classify_maps_git_results_to_status_codes(result: GitResult, status: str) -> None:
    assert classify(result)[0] == status


def test_classify_messages_are_fixed_for_auth_and_not_found() -> None:
    auth = classify(GitResult(128, "", "fatal: could not read Username for 'http://h': terminal prompts disabled"))
    missing = classify(GitResult(128, "", "fatal: repository 'http://h/o/r.git/' not found"))
    timeout = classify(GitResult(124, "", "timeout"))
    assert auth == ("auth_failed", AUTH_MESSAGE)
    assert missing == ("not_found", NOT_FOUND_MESSAGE)
    assert timeout == ("fetch_failed", "timeout")


class _StatusHandler(http.server.BaseHTTPRequestHandler):
    code = 401

    def _answer(self) -> None:
        self.send_response(self.code)
        if self.code == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="fixture"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = _answer
    do_POST = _answer

    def log_message(self, *_: object) -> None:  # keep pytest output quiet
        return


def _serve(code: int) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = type("Handler", (_StatusHandler,), {"code": code})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.mark.parametrize(("code", "status"), [(401, "auth_failed"), (403, "auth_failed"), (404, "not_found")])
def test_real_git_against_http_status_is_classified(code: int, status: str) -> None:
    server, base = _serve(code)
    try:
        upstream = Upstream(base=base, allow_protocol="http", overridden=True)
        url = remote_url(upstream, RepoSpec("o", "r"))
        result = gitops.run_git(["ls-remote", "--symref", url, "HEAD"], auth_env(_token(), "http"), timeout=30)
    finally:
        server.shutdown()
        server.server_close()
    assert result.returncode != 0
    assert classify(result)[0] == status


def test_real_git_against_closed_port_is_fetch_failed() -> None:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    url = f"http://127.0.0.1:{port}/o/r.git"
    result = gitops.run_git(["ls-remote", url, "HEAD"], auth_env(_token(), "http"), timeout=30)
    status, message = classify(result)
    assert status == "fetch_failed"
    assert message and "\n" not in message


# --- sanitize ------------------------------------------------------------------------------------------------------


def test_sanitize_drops_authorization_lines() -> None:
    text = "fatal: something broke\nauthorization: Basic abc\nAUTHORIZATION: Bearer x\n"
    out = sanitize(text)
    assert "authorization" not in out.lower()
    assert "Basic abc" not in out
    assert "something broke" in out


def test_sanitize_masks_standalone_32_hex() -> None:
    hash_ = "0123456789abcdef" * 2
    out = sanitize(f"fatal: '/srv/git/access/o/r/{hash_}' missing")
    assert hash_ not in out
    assert "0123…" in out


def test_sanitize_returns_one_bounded_line() -> None:
    out = sanitize("warning: first\n" + "fatal: " + "x" * 1000 + "\nmore\n")
    assert "\n" not in out
    assert 0 < len(out) <= 300


# --- inspect_head --------------------------------------------------------------------------------------------------


def _synced(tmp_path: Path, files: dict[str, str], name: str = "r") -> Path:
    make_upstream(tmp_path, "o", name, files)
    paths = Paths.under(tmp_path)
    spec = RepoSpec("o", name)
    url = remote_url(file_upstream(tmp_path), spec)
    result = ensure_and_fetch(paths, spec, url, "main", auth_env(_token(), "file"))
    assert result.returncode == 0, result.stderr
    return paths.repo_dir("o", name)


def test_inspect_head_reports_repository_yaml_and_addons(tmp_path: Path) -> None:
    repo = _synced(
        tmp_path,
        {
            "repository.yaml": "name: fixture\n",
            "demo/config.yaml": "name: demo\n",
            "other/config.json": "{}\n",
            ".hidden/config.yaml": "name: hidden\n",
            "x/rootfs/config.yaml": "name: rootfs\n",
            "demo/README.md": "demo\n",
        },
    )
    info = inspect_head(repo)
    assert isinstance(info, HeadInfo)
    assert info.addons == ("demo", "other")
    assert info.has_repository_yaml is True
    assert info.head is not None and len(info.head) == 12
    int(info.head, 16)


def test_inspect_head_without_repository_yaml(tmp_path: Path) -> None:
    repo = _synced(tmp_path, {"demo/config.yaml": "name: demo\n"})
    info = inspect_head(repo)
    assert info.has_repository_yaml is False
    assert info.addons == ("demo",)


# --- refs ----------------------------------------------------------------------------------------------------------


def test_prune_foreign_refs_keeps_only_the_branch(tmp_path: Path) -> None:
    repo = _synced(tmp_path, {"repository.yaml": "name: fixture\n"})
    sha = git(["--git-dir", str(repo), "rev-parse", "refs/heads/main"]).strip()
    git(["--git-dir", str(repo), "update-ref", "refs/heads/old", sha])
    git(["--git-dir", str(repo), "update-ref", "refs/pull/1/head", sha])
    removed = prune_foreign_refs(repo, "main")
    refs = git(["--git-dir", str(repo), "for-each-ref", "--format=%(refname)"]).split()
    assert removed == 2
    assert refs == ["refs/heads/main"]


def test_ref_snapshot_lists_refs_and_head(tmp_path: Path) -> None:
    repo = _synced(tmp_path, {"repository.yaml": "name: fixture\n"})
    sha = git(["--git-dir", str(repo), "rev-parse", "refs/heads/main"]).strip()
    assert ref_snapshot(repo) == {"refs/heads/main": sha, "HEAD": "refs/heads/main"}


def test_ref_snapshot_changes_after_upstream_commit(tmp_path: Path) -> None:
    repo = _synced(tmp_path, {"repository.yaml": "name: fixture\n"})
    before = ref_snapshot(repo)
    commit(tmp_path / "upstream" / "o" / "r.git", {"demo/config.yaml": "name: demo\n"}, "add demo")
    spec = RepoSpec("o", "r")
    url = remote_url(file_upstream(tmp_path), spec)
    assert ensure_and_fetch(Paths.under(tmp_path), spec, url, "main", auth_env(_token(), "file")).returncode == 0
    assert ref_snapshot(repo) != before


def test_ref_snapshot_of_missing_repo_is_empty(tmp_path: Path) -> None:
    assert ref_snapshot(tmp_path / "missing.git") == {}


# --- ensure_and_fetch ----------------------------------------------------------------------------------------------


def _config(repo: Path, key: str) -> str | None:
    proc = subprocess.run(
        ["git", "--git-dir", str(repo), "config", "--get", key],
        env=git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def test_ensure_and_fetch_builds_a_read_only_bare_repo(tmp_path: Path) -> None:
    repo = _synced(tmp_path, {"repository.yaml": "name: fixture\n"})
    assert _config(repo, "remote.origin.pushurl") == "no-push://disabled"
    assert _config(repo, "http.receivepack") == "false"
    assert _config(repo, "http.getanyfile") == "false"
    assert _config(repo, "remote.origin.mirror") is None
    assert git(["--git-dir", str(repo), "symbolic-ref", "HEAD"]).strip() == "refs/heads/main"
    assert not (repo / "shallow").exists()
    assert not (repo.parent / ".r.git.tmp").exists()


def test_failed_first_fetch_leaves_no_directories(tmp_path: Path) -> None:
    paths = Paths.under(tmp_path)
    spec = RepoSpec("o", "missing")
    url = remote_url(file_upstream(tmp_path), spec)
    result = ensure_and_fetch(paths, spec, url, "main", auth_env(_token(), "file"))
    assert result.returncode != 0
    assert not paths.repo_dir("o", "missing").exists()
    assert not (paths.repos_root / "o" / ".missing.git.tmp").exists()


def test_run_maintenance_uses_the_local_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _synced(tmp_path, {"repository.yaml": "name: fixture\n"})
    seen: list[tuple[list[str], dict[str, str]]] = []
    real = gitops.run_git

    def spy(args, env, cwd=None, timeout=gitops.GIT_TIMEOUT):  # type: ignore[no-untyped-def]
        seen.append((list(args), dict(env)))
        return real(args, env, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(gitops, "run_git", spy)
    run_maintenance(repo)
    assert seen, "run_maintenance started no git process"
    args, env = seen[-1]
    assert args[-3:] == ["maintenance", "run", "--auto"]
    assert env == gitops.local_env()


def test_cleanup_stale_tmp_removes_leftover_temp_dirs(tmp_path: Path) -> None:
    paths = Paths.under(tmp_path)
    stale = paths.repos_root / "o" / ".r.git.tmp"
    (stale / "objects").mkdir(parents=True)
    keep = paths.repos_root / "o" / "r.git"
    keep.mkdir(parents=True)
    assert cleanup_stale_tmp(paths) == 1
    assert not stale.exists()
    assert keep.exists()


# --- auth_env ------------------------------------------------------------------------------------------------------


def test_auth_env_has_exactly_the_documented_keys() -> None:
    env = auth_env(_token(), "https")
    assert set(env) == {
        "PATH",
        "HOME",
        "LC_ALL",
        "GIT_TERMINAL_PROMPT",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_GLOBAL",
        "GIT_ALLOW_PROTOCOL",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_KEY_0",
        "GIT_CONFIG_VALUE_0",
    }
    encoded = base64.b64encode(f"x-access-token:{_token()}".encode()).decode()
    assert env["GIT_CONFIG_VALUE_0"] == f"Authorization: Basic {encoded}"
    assert all(_token() not in value for value in env.values())


def test_auth_env_ignores_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_TRACE", "1")
    monkeypatch.setenv("GIT_CURL_VERBOSE", "1")
    env = auth_env(_token(), "https")
    assert "GIT_TRACE" not in env
    assert "GIT_CURL_VERBOSE" not in env


# --- resolve_upstream ----------------------------------------------------------------------------------------------


def test_resolve_upstream_defaults_to_github() -> None:
    assert resolve_upstream({}) == Upstream("https://github.com", "https", False)


def test_resolve_upstream_accepts_plain_http_override() -> None:
    assert resolve_upstream({gitops.UPSTREAM_OVERRIDE_ENV: "http://h:8080/"}) == Upstream("http://h:8080", "http", True)


@pytest.mark.parametrize(
    "value",
    ["http://user:pw@h:8080", "ftp://h/", "http://h/?x=1", "http://h/#frag"],
)
def test_resolve_upstream_rejects_unsafe_overrides(value: str) -> None:
    with pytest.raises(UpstreamOverrideError):
        resolve_upstream({gitops.UPSTREAM_OVERRIDE_ENV: value})


# --- check_branch_name ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("branch", "valid"), [("main", True), ("release/1.x", True), ("a..b", False), ("-x", False)])
def test_check_branch_name(branch: str, valid: bool) -> None:
    assert check_branch_name(branch) is valid
