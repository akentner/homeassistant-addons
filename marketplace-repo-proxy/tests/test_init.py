"""s6 oneshot `init` (app.init): dirs and modes, safe.directory, reconcile, startup log, D-28 failure policy."""

from __future__ import annotations

import json
import logging
import os
import subprocess

import pytest

from app.access import new_hash
from app.init import run_init
from app.paths import Paths

HOST = "proxy-test"
REPO = "example-org/private-addons"
OTHER = "example-org/other-addons"
UNLISTED = "example-org/unlisted-addons"
INTERNAL = f"http://{HOST}:8080/repo/{REPO}/"
PUBLIC = f"https://addons.example.invalid/repo/{REPO}/"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """run_init sets umask 077 for the process: restore it; keep a developer's git config out of the test."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    previous = os.umask(0o022)
    os.umask(previous)
    yield
    os.umask(previous)


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    write_options(p)
    return p


def write_options(p: Paths, **extra) -> None:
    doc = {
        "github_token": "SENTINEL-" + "PAT-" + "0001",
        "repositories": [{"repository": REPO}, {"repository": OTHER, "branch": "stable"}],
        **extra,
    }
    p.options_file.write_text(json.dumps(doc), encoding="utf-8")


def entry(repository: str, user: str, hash_: str) -> dict:
    return {"repository": repository, "user": user, "hash": hash_, "created": "2026-01-01T00:00:00Z", "source": "cli"}


def write_access(p: Paths, entries: list[dict]) -> None:
    p.access_file.write_text(json.dumps({"schema": 1, "entries": entries}), encoding="utf-8")


@pytest.fixture
def users(paths):
    """alice and bob for REPO, carol for a repository that is not configured."""
    hashes = {"alice": new_hash(), "bob": new_hash(), "carol": new_hash()}
    write_access(
        paths,
        [
            entry(REPO, "alice", hashes["alice"]),
            entry(REPO, "bob", hashes["bob"]),
            entry(UNLISTED, "carol", hashes["carol"]),
        ],
    )
    return hashes


def init(p: Paths, caplog) -> int:
    caplog.set_level(logging.DEBUG)
    return run_init(p, hostname=HOST)


def links(p: Paths) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(p.access_root):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                found.append(os.path.relpath(path, p.access_root))
    return sorted(found)


def lines(caplog, level: int = logging.INFO) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def test_init_creates_dirs_with_modes_and_safe_directory(paths, caplog):
    assert init(paths, caplog) == 0
    assert paths.data_dir.stat().st_mode & 0o777 == 0o700
    assert paths.run_dir.stat().st_mode & 0o777 == 0o700
    assert paths.access_root.stat().st_mode & 0o777 == 0o711
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(
        ["git", "config", "--file", str(paths.gitconfig_file), "--get-all", "safe.directory"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [f"{paths.repos_root}/*"]


def test_init_links_configured_entries_only(paths, users, caplog):
    assert init(paths, caplog) == 0
    assert links(paths) == sorted(
        [f"example-org/private-addons/{users['alice']}", f"example-org/private-addons/{users['bob']}"]
    )


def test_startup_log_lists_users_with_masked_internal_urls(paths, users, caplog):
    assert init(paths, caplog) == 0
    info = lines(caplog)
    assert "marketplace-repo-proxy: 2 repositories configured, 3 access entries" in info
    assert f"repository {REPO} (branch: upstream default): 2 user(s)" in info
    assert f"repository {OTHER} (branch: stable): 0 user(s)" in info
    assert f"  user alice -> {INTERNAL}{users['alice'][:4]}…" in info
    assert f"  user bob -> {INTERNAL}{users['bob'][:4]}…" in info
    for hash_ in users.values():
        assert hash_ not in caplog.text


def test_startup_log_adds_masked_public_url(paths, users, caplog):
    write_options(paths, public_url="https://addons.example.invalid/")
    assert init(paths, caplog) == 0
    info = lines(caplog)
    assert f"  user alice -> {INTERNAL}{users['alice'][:4]}… | public {PUBLIC}{users['alice'][:4]}…" in info
    for hash_ in users.values():
        assert hash_ not in caplog.text


def test_unconfigured_entries_are_summarised_and_stay_inactive(paths, users, caplog):
    assert init(paths, caplog) == 0
    info = lines(caplog)
    assert "1 access entries belong to repositories that are not configured; they stay inactive" in info
    assert not any("carol" in line for line in info)
    assert not any(users["carol"] in link for link in links(paths))


def test_startup_log_never_contains_the_token(paths, users, caplog):
    assert init(paths, caplog) == 0
    assert "SENTINEL-" + "PAT-" + "0001" not in caplog.text


def test_stray_symlink_is_removed(paths, users, tmp_path, caplog):
    stray = paths.link_path("example-org", "private-addons", new_hash())
    stray.parent.mkdir(parents=True)
    stray.symlink_to(tmp_path)
    assert init(paths, caplog) == 0
    assert not stray.is_symlink()
    assert len(links(paths)) == 2


def test_invalid_options_json_is_fatal(paths, caplog):
    paths.options_file.write_text('{"github_token": ', encoding="utf-8")
    assert init(paths, caplog) == 1
    assert len(lines(caplog, logging.ERROR)) == 1


def test_newer_access_schema_is_fatal_and_file_untouched(paths, caplog):
    raw = json.dumps({"schema": 2, "entries": [entry(REPO, "alice", new_hash())]}).encode()
    paths.access_file.write_bytes(raw)
    assert init(paths, caplog) == 1
    assert paths.access_file.read_bytes() == raw
    assert len(lines(caplog, logging.ERROR)) == 1


def test_corrupt_access_json_is_survived(paths, caplog):
    paths.access_file.write_text("{not json", encoding="utf-8")
    assert init(paths, caplog) == 0
    assert paths.access_file.with_name("access.json.corrupt").exists()
    assert links(paths) == []
    assert "marketplace-repo-proxy: 2 repositories configured, 0 access entries" in lines(caplog)


def test_rejected_repository_entry_is_warned_and_survived(paths, caplog):
    write_options(paths, repositories=[{"repository": REPO}, {"repository": "example-org/.."}])
    assert init(paths, caplog) == 0
    warnings = lines(caplog, logging.WARNING)
    assert any("example-org/.." in line for line in warnings)
    assert "marketplace-repo-proxy: 1 repositories configured, 0 access entries" in lines(caplog)


def test_empty_token_with_repositories_warns(paths, caplog):
    write_options(paths, github_token="")
    assert init(paths, caplog) == 0
    assert "github_token is empty; sync will report auth_failed" in lines(caplog, logging.WARNING)


def test_empty_token_without_repositories_does_not_warn(paths, caplog):
    write_options(paths, github_token="", repositories=[])
    assert init(paths, caplog) == 0
    assert "github_token is empty; sync will report auth_failed" not in lines(caplog, logging.WARNING)
