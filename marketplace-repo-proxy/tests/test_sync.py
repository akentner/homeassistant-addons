"""Sync cycle against local file:// and 127.0.0.1 upstream fixtures (never GitHub)."""

from __future__ import annotations

import http.server
import itertools
import logging
import threading
from pathlib import Path

import pytest
from upstream import commit, file_upstream, git, make_upstream

from app import gitops, status, sync
from app.gitops import Upstream
from app.options import Options, RepoSpec
from app.paths import Paths
from app.status import StatusWriter, read_status

GOOD = {"repository.yaml": "name: fixture\n", "demo/config.yaml": "name: demo\n"}


@pytest.fixture(autouse=True)
def _ticking_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Distinct status timestamps, so `last_change` moves are observable within one second."""
    counter = itertools.count()
    monkeypatch.setattr(status, "utc_timestamp", lambda ts=None: f"2026-11-18T11:{next(counter) % 60:02d}:00Z")


def _token() -> str:
    # Built at runtime so no token-shaped literal sits in the repository
    return "sentinel" + "-pat-" + "9876543210"


def _options(*specs: RepoSpec, token: str | None = None) -> Options:
    return Options(github_token=_token() if token is None else token, sync_interval=15, repositories=specs)


def _cycle(tmp_path: Path, options: Options, upstream: Upstream | None = None) -> dict:
    """One cycle with a fresh writer that seeds from the previous status.json, like a service restart would."""
    paths = Paths.under(tmp_path)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    writer = StatusWriter(paths, options.repositories, True, options.sync_interval)
    writer.begin_cycle("startup")
    sync.run_cycle(paths, options, upstream or file_upstream(tmp_path), logging.getLogger("test.sync"), writer)
    writer.end_cycle(0)
    doc = read_status(paths)
    assert doc is not None
    return doc


def _entry(doc: dict, slug: str) -> dict:
    return next(e for e in doc["repositories"] if e["repository"] == slug)


def test_good_repository_is_ok_with_addons(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "good", GOOD)
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "good"))), "o/good")
    assert entry["status"] == "ok"
    assert entry["message"] == ""
    assert entry["addons"] == ["demo"]
    assert entry["branch"] == "main"
    assert entry["branch_source"] == "upstream_default"
    assert entry["head"] is not None and len(entry["head"]) == 12
    assert entry["refs_changed"] is True
    assert entry["last_success"] and entry["last_change"]


def test_repository_without_repository_yaml(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "bare", {"demo/config.yaml": "name: demo\n"})
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "bare"))), "o/bare")
    assert entry["status"] == "no_repository_yaml"
    assert entry["message"] == "repository.yaml missing at the branch root"
    assert Paths.under(tmp_path).repo_dir("o", "bare").is_dir()


def test_missing_upstream_repository_is_not_found(tmp_path: Path) -> None:
    (tmp_path / "upstream").mkdir()
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "missing"))), "o/missing")
    assert entry["status"] == "not_found"
    assert entry["head"] is None


def test_missing_configured_branch_is_not_found(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "good", GOOD)
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "good", "nope"))), "o/good")
    assert entry["status"] == "not_found"
    assert entry["branch_source"] == "configured"


def test_upstream_without_default_branch_is_not_found(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "empty", {})
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "empty"))), "o/empty")
    assert entry["status"] == "not_found"
    assert entry["message"] == "upstream has no default branch"


def test_invalid_branch_name_is_not_found(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "good", GOOD)
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "good", "bad..name"))), "o/good")
    assert entry["status"] == "not_found"
    assert entry["message"] == "invalid branch name"


def test_empty_token_is_auth_failed_without_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_upstream(tmp_path, "o", "good", GOOD)
    paths = Paths.under(tmp_path)
    paths.data_dir.mkdir(parents=True)
    options = _options(RepoSpec("o", "good"), token="")
    writer = StatusWriter(paths, options.repositories, False, 15)
    calls: list[list[str]] = []
    monkeypatch.setattr(gitops, "run_git", lambda args, *a, **k: calls.append(list(args)))
    sync.run_cycle(paths, options, file_upstream(tmp_path), logging.getLogger("test.sync"), writer)
    doc = read_status(paths)
    assert doc is not None
    entry = _entry(doc, "o/good")
    assert entry["status"] == "auth_failed"
    assert entry["message"] == "github_token is empty"
    assert calls == []


def test_upstream_push_is_reported_once(tmp_path: Path) -> None:
    bare = make_upstream(tmp_path, "o", "good", GOOD)
    options = _options(RepoSpec("o", "good"))
    first = _entry(_cycle(tmp_path, options), "o/good")
    commit(bare, {"other/config.json": "{}\n"}, "add other")
    second = _entry(_cycle(tmp_path, options), "o/good")
    third = _entry(_cycle(tmp_path, options), "o/good")
    assert second["refs_changed"] is True
    assert second["head"] != first["head"]
    assert second["last_change"] != first["last_change"]
    assert second["addons"] == ["demo", "other"]
    assert third["refs_changed"] is False
    assert third["head"] == second["head"]
    assert third["last_change"] == second["last_change"]


def test_failed_cycle_keeps_the_served_head(tmp_path: Path) -> None:
    bare = make_upstream(tmp_path, "o", "good", GOOD)
    options = _options(RepoSpec("o", "good"))
    good = _entry(_cycle(tmp_path, options), "o/good")
    git(["--git-dir", str(bare), "symbolic-ref", "HEAD", "refs/heads/gone"])  # upstream loses its default branch
    failed = _entry(_cycle(tmp_path, options), "o/good")
    assert failed["status"] == "not_found"
    assert failed["head"] == good["head"]
    assert failed["addons"] == good["addons"]
    assert failed["last_success"] == good["last_success"]


def test_branch_change_moves_head_and_drops_the_old_ref(tmp_path: Path) -> None:
    bare = make_upstream(tmp_path, "o", "good", GOOD)
    commit(bare, {"dev/config.yaml": "name: dev\n"}, "dev branch", branch="dev")
    _cycle(tmp_path, _options(RepoSpec("o", "good", "main")))
    entry = _entry(_cycle(tmp_path, _options(RepoSpec("o", "good", "dev"))), "o/good")
    repo = Paths.under(tmp_path).repo_dir("o", "good")
    refs = git(["--git-dir", str(repo), "for-each-ref", "--format=%(refname)"]).split()
    assert git(["--git-dir", str(repo), "symbolic-ref", "HEAD"]).strip() == "refs/heads/dev"
    assert refs == ["refs/heads/dev"]
    assert entry["status"] == "ok"
    assert entry["branch"] == "dev"
    assert entry["branch_source"] == "configured"
    assert entry["refs_changed"] is True
    assert entry["addons"] == ["demo", "dev"]


class _Unauthorized(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="fixture"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_: object) -> None:
        return


def test_token_never_reaches_status_or_log(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Unauthorized)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    upstream = Upstream(base=f"http://127.0.0.1:{server.server_address[1]}", allow_protocol="http", overridden=True)
    try:
        with caplog.at_level(logging.DEBUG):
            doc = _cycle(tmp_path, _options(RepoSpec("o", "good"), RepoSpec("o", "pinned", "main")), upstream)
    finally:
        server.shutdown()
        server.server_close()
    text = Paths.under(tmp_path).status_file.read_text()
    assert [e["status"] for e in doc["repositories"]] == ["auth_failed", "auth_failed"]
    assert _token() not in text
    assert _token() not in caplog.text
    assert "uthorization" not in text and "uthorization" not in caplog.text
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("o/good" in w and "expired, revoked or missing access" in w for w in warnings)
