"""Sync cycle against local file:// and 127.0.0.1 upstream fixtures (never GitHub)."""

from __future__ import annotations

import http.server
import itertools
import json
import logging
import os
import signal
import socket
import threading
import time
from pathlib import Path

import pytest
from upstream import commit, file_upstream, git, make_upstream

from app import gitops, status, sync
from app.gitops import Upstream
from app.logsetup import Redactor
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


def test_failed_branch_change_keeps_serving_the_old_branch(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "good", GOOD)
    good = _entry(_cycle(tmp_path, _options(RepoSpec("o", "good", "main"))), "o/good")
    repo = Paths.under(tmp_path).repo_dir("o", "good")
    before = git(["--git-dir", str(repo), "rev-parse", "HEAD"]).strip()
    failed = _entry(_cycle(tmp_path, _options(RepoSpec("o", "good", "stabel"))), "o/good")  # typo: no such branch
    assert failed["status"] == "not_found"
    assert failed["branch"] == "stabel"
    assert failed["head"] == good["head"]
    assert failed["addons"] == good["addons"]
    assert failed["last_success"] == good["last_success"]
    gd = ["--git-dir", str(repo)]
    assert git([*gd, "symbolic-ref", "HEAD"]).strip() == "refs/heads/main"
    assert git([*gd, "rev-parse", "--verify", "HEAD"]).strip() == before
    assert git([*gd, "for-each-ref", "--format=%(refname)"]).split() == ["refs/heads/main"]
    assert git([*gd, "config", "--get-all", "remote.origin.fetch"]).split() == ["+refs/heads/main:refs/heads/main"]
    clone = tmp_path / "clone"
    git(["clone", "-q", str(repo), str(clone)])
    assert (clone / "repository.yaml").read_text() == GOOD["repository.yaml"]
    assert (clone / "demo" / "config.yaml").is_file()


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


# --- SyncService loop: fake clock and sleep, no real waiting -------------------------------------------------------

INTERVAL_S = 5 * 60
CYCLE_S = 10.0


class FakeTime:
    """Monotonic clock plus a sleep that only advances it; `on_sleep` hooks run after every poll."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps = 0
        self.on_sleep: list = []

    def clock(self) -> float:
        return self.now

    def wall(self) -> float:
        return 1_800_000_000.0 + self.now

    def sleep(self, seconds: float) -> None:
        assert seconds == 1.0
        self.now += seconds
        self.sleeps += 1
        for hook in list(self.on_sleep):
            hook()


def _service(
    tmp_path: Path, fake: FakeTime, monkeypatch: pytest.MonkeyPatch, *, during=None, max_cycles: int = 3, registrar=None
):
    """SyncService with a fake run_cycle that records (start, reason, trigger present) and lasts CYCLE_S."""
    paths = Paths.under(tmp_path)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    options = Options(github_token=_token(), sync_interval=5, repositories=(RepoSpec("o", "good"),))
    cycles: list[dict] = []
    holder: dict = {}

    def fake_run_cycle(paths_, options_, upstream_, log_, writer, stop=None):  # type: ignore[no-untyped-def]
        cycles.append(
            {
                "start": fake.now,
                "reason": writer.snapshot()["sync"]["reason"],
                "trigger": paths.trigger_file.exists(),
            }
        )
        if during is not None:
            during(len(cycles))
        fake.now += CYCLE_S
        cycles[-1]["end"] = fake.now
        if len(cycles) >= max_cycles:
            holder["service"].stop.set()

    monkeypatch.setattr(sync, "run_cycle", fake_run_cycle)
    service = sync.SyncService(
        paths,
        options,
        file_upstream(tmp_path),
        logging.getLogger("test.sync"),
        clock=fake.clock,
        sleep=fake.sleep,
        wall=fake.wall,
        registrar=registrar,
    )
    holder["service"] = service
    return service, paths, cycles


def _stop_after(fake: FakeTime, service, seconds: float) -> None:  # type: ignore[no-untyped-def]
    limit = fake.now + seconds
    fake.on_sleep.append(lambda: service.stop.set() if fake.now >= limit else None)


def test_interval_cycle_starts_after_the_interval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    service, _, cycles = _service(tmp_path, fake, monkeypatch, max_cycles=2)
    _stop_after(fake, service, 2 * INTERVAL_S)
    service.run_forever()
    assert [c["reason"] for c in cycles] == ["startup", "interval"]
    gap = cycles[1]["start"] - cycles[0]["end"]
    assert INTERVAL_S <= gap < INTERVAL_S + 1.0


def test_trigger_file_starts_a_request_cycle_within_a_second(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    service, paths, cycles = _service(tmp_path, fake, monkeypatch, max_cycles=2)
    created: dict = {}

    def touch() -> None:
        if fake.sleeps == 30 and not created:
            paths.trigger_file.write_text("{}", encoding="utf-8")
            created["at"] = fake.now

    fake.on_sleep.append(touch)
    _stop_after(fake, service, INTERVAL_S - 60)
    service.run_forever()
    assert [c["reason"] for c in cycles] == ["startup", "request"]
    assert cycles[1]["trigger"] is False
    assert 0 <= cycles[1]["start"] - created["at"] <= 1.0
    assert not paths.trigger_file.exists()


def test_requests_during_a_cycle_coalesce_into_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    paths = Paths.under(tmp_path)

    def burst(n: int) -> None:
        if n == 1:
            for _ in range(3):
                paths.trigger_file.write_text("{}", encoding="utf-8")

    service, _, cycles = _service(tmp_path, fake, monkeypatch, during=burst, max_cycles=5)
    _stop_after(fake, service, INTERVAL_S - 60)
    service.run_forever()
    assert [c["reason"] for c in cycles] == ["startup", "request"]


def test_interval_restarts_after_a_request_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    service, paths, cycles = _service(tmp_path, fake, monkeypatch, max_cycles=3)
    fake.on_sleep.append(
        lambda: paths.trigger_file.write_text("{}", encoding="utf-8") if fake.sleeps == 100 else None
    )
    _stop_after(fake, service, 3 * INTERVAL_S)
    service.run_forever()
    assert [c["reason"] for c in cycles] == ["startup", "request", "interval"]
    gap = cycles[2]["start"] - cycles[1]["end"]
    assert INTERVAL_S <= gap < INTERVAL_S + 1.0


def test_stop_event_ends_run_forever_within_one_poll(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    service, _, cycles = _service(tmp_path, fake, monkeypatch)
    stopped: dict = {}

    def stop_once() -> None:
        if fake.sleeps == 5:
            service.stop.set()
            stopped["sleeps"] = fake.sleeps

    fake.on_sleep.append(stop_once)
    service.run_forever()
    assert len(cycles) == 1
    assert fake.sleeps == stopped["sleeps"]
    assert service.wait_reason() is None


class StubRegistrar:
    """Supervisor work due from `due_at` (fake clock) until `run_due` ran once; records every hook call."""

    def __init__(self, fake: FakeTime, due_at: float | None = None, error: Exception | None = None) -> None:
        self.fake = fake
        self.due_at = due_at
        self.error = error
        self.runs: list[float] = []
        self.cycles: list[frozenset] = []

    def work_due(self) -> bool:
        return self.due_at is not None and self.fake.now >= self.due_at

    def run_due(self) -> None:
        self.runs.append(self.fake.now)
        self.due_at = None
        if self.error is not None:
            raise self.error

    def after_cycle(self, status_doc: dict, head_changes: frozenset = frozenset()) -> None:
        self.cycles.append(head_changes)


def test_supervisor_work_runs_from_the_wait_loop_without_a_sync_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeTime()
    registrar = StubRegistrar(fake)
    service, paths, cycles = _service(tmp_path, fake, monkeypatch, max_cycles=2, registrar=registrar)
    reasons: list[str | None] = []
    fake.on_sleep.append(lambda: reasons.append((read_status(paths) or {}).get("sync", {}).get("reason")))
    registrar.due_at = fake.now + CYCLE_S + 30
    _stop_after(fake, service, 2 * INTERVAL_S)
    service.run_forever()
    assert len(registrar.runs) == 1
    assert [c["reason"] for c in cycles] == ["startup", "interval"]
    assert CYCLE_S + 30 <= registrar.runs[0] - cycles[0]["start"] <= CYCLE_S + 31
    gap = cycles[1]["start"] - cycles[0]["end"]
    assert INTERVAL_S <= gap < INTERVAL_S + 1.0
    assert "supervisor" not in reasons
    assert registrar.cycles == [frozenset()]  # the last fake cycle sets stop, which skips the store pass
    doc = read_status(paths)
    assert doc is not None and doc["sync"]["reason"] == "interval"


def test_stop_ends_run_forever_within_one_poll_with_supervisor_work_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeTime()
    registrar = StubRegistrar(fake)
    service, _, cycles = _service(tmp_path, fake, monkeypatch, registrar=registrar)

    def stop_and_owe() -> None:
        if fake.sleeps == 5:
            service.stop.set()
            registrar.due_at = fake.now  # due at the same poll: stop wins

    fake.on_sleep.append(stop_and_owe)
    service.run_forever()
    assert fake.sleeps == 5
    assert registrar.runs == []
    assert len(cycles) == 1


def test_supervisor_work_failure_is_logged_and_the_loop_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeTime()
    registrar = StubRegistrar(fake, due_at=fake.now + CYCLE_S + 5, error=RuntimeError("boom"))
    service, _, cycles = _service(tmp_path, fake, monkeypatch, max_cycles=2, registrar=registrar)
    _stop_after(fake, service, 2 * INTERVAL_S)
    with caplog.at_level(logging.WARNING, logger="test.sync"):
        service.run_forever()
    assert len(registrar.runs) == 1
    assert [c["reason"] for c in cycles] == ["startup", "interval"]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["store work failed: RuntimeError"]
    assert "boom" not in caplog.text


def test_stale_temp_dirs_are_removed_at_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeTime()
    service, paths, cycles = _service(tmp_path, fake, monkeypatch, max_cycles=1)
    stale = paths.repos_root / "o" / ".good.git.tmp"
    (stale / "objects").mkdir(parents=True)
    service.run_forever()
    assert not stale.exists()
    assert [c["reason"] for c in cycles] == ["startup"]


def test_stop_is_checked_between_repositories(tmp_path: Path) -> None:
    make_upstream(tmp_path, "o", "a", GOOD)
    make_upstream(tmp_path, "o", "b", GOOD)
    paths = Paths.under(tmp_path)
    paths.data_dir.mkdir(parents=True)
    options = _options(RepoSpec("o", "a"), RepoSpec("o", "b"))
    writer = StatusWriter(paths, options.repositories, True, 15)
    stop = threading.Event()

    class StopAfterFirst(logging.Logger):
        def info(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def,override]
            stop.set()

    sync.run_cycle(paths, options, file_upstream(tmp_path), StopAfterFirst("t"), writer, stop)
    doc = read_status(paths)
    assert doc is not None
    assert [e["status"] for e in doc["repositories"]] == ["ok", "pending"]


# --- main ----------------------------------------------------------------------------------------------------------


@pytest.fixture
def main_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """main() against Paths.under(tmp_path); logging setup and signal handlers are captured, umask restored."""
    paths = Paths.under(tmp_path)
    paths.data_dir.mkdir(parents=True)
    paths.run_dir.mkdir(parents=True)
    paths.options_file.write_text(
        json.dumps({"github_token": _token(), "sync_interval": 5, "repositories": [{"repository": "o/good"}]}),
        encoding="utf-8",
    )
    handlers: dict = {}
    monkeypatch.setattr(sync.Paths, "default", classmethod(lambda cls: paths))
    monkeypatch.setattr(sync, "setup_logging", lambda level, redactor=None: redactor or Redactor())
    monkeypatch.setattr(sync.signal, "signal", lambda sig, handler: handlers.__setitem__(sig, handler))
    monkeypatch.delenv(gitops.UPSTREAM_OVERRIDE_ENV, raising=False)
    old_umask = os.umask(0o022)
    yield paths, handlers
    os.umask(old_umask)


def test_main_once_runs_exactly_one_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, main_env) -> None:
    paths, _ = main_env
    make_upstream(tmp_path, "o", "good", GOOD)
    monkeypatch.setattr(sync, "resolve_upstream", lambda environ: file_upstream(tmp_path))
    real = sync.run_cycle
    calls: list[int] = []

    def counting(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(sync, "run_cycle", counting)
    assert sync.main(["--once"]) == 0
    assert len(calls) == 1
    doc = read_status(paths)
    assert doc is not None
    assert doc["sync"]["state"] == "idle"
    assert doc["sync"]["reason"] == "startup"
    assert doc["repositories"][0]["status"] == "ok"


def test_invalid_override_disables_syncing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, main_env
) -> None:
    paths, handlers = main_env
    monkeypatch.setenv(gitops.UPSTREAM_OVERRIDE_ENV, "ftp://upstream.invalid/")
    calls: list[list[str]] = []
    monkeypatch.setattr(gitops, "run_git", lambda args, *a, **k: calls.append(list(args)))
    result: dict = {}
    with caplog.at_level(logging.INFO, logger="mrp.sync"):
        worker = threading.Thread(target=lambda: result.setdefault("rc", sync.main([])), daemon=True)
        worker.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            doc = read_status(paths)
            if doc and doc["repositories"][0]["status"] == "fetch_failed" and signal.SIGTERM in handlers:
                break
            time.sleep(0.02)
        time.sleep(0.2)
        assert worker.is_alive(), "service must idle until stopped"
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        worker.join(5)
    assert not worker.is_alive()
    assert result["rc"] == 0
    doc = read_status(paths)
    assert doc is not None
    assert [e["status"] for e in doc["repositories"]] == ["fetch_failed"]
    assert doc["repositories"][0]["message"] == "invalid test upstream override"
    assert calls == []
    assert "invalid test upstream override; syncing disabled" in caplog.text


def test_valid_override_is_announced_and_reported(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, main_env
) -> None:
    paths, _ = main_env
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    sock.close()
    monkeypatch.setenv(gitops.UPSTREAM_OVERRIDE_ENV, base)
    with caplog.at_level(logging.INFO, logger="mrp.sync"):
        assert sync.main(["--once"]) == 0
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings.count(f"test upstream override active: {base}") == 1
    doc = read_status(paths)
    assert doc is not None
    assert doc["upstream_override"] is True
    assert doc["repositories"][0]["status"] == "fetch_failed"
