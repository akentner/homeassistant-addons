"""status.json contract (D-14, D-20, D-26): seeding, carry-over, per-repository records and cycle state."""

from __future__ import annotations

import itertools
import json
import stat
from pathlib import Path

import pytest

from app import status
from app.jsonio import atomic_write_json
from app.options import RepoSpec
from app.paths import Paths
from app.status import REASONS, SCHEMA, STATUS_CODES, StatusWriter, read_status

SPECS = (RepoSpec("Org", "one"), RepoSpec("org", "two", "dev"), RepoSpec("other", "three"))


@pytest.fixture(autouse=True)
def _ticking_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every timestamp is distinct, so `updated` and `last_attempt` changes are observable."""
    counter = itertools.count()
    monkeypatch.setattr(status, "utc_timestamp", lambda ts=None: f"2026-11-18T10:{next(counter) % 60:02d}:00Z")


def _paths(tmp_path: Path) -> Paths:
    paths = Paths.under(tmp_path)
    paths.data_dir.mkdir(parents=True)
    return paths


def _doc(paths: Paths) -> dict:
    doc = read_status(paths)
    assert doc is not None, "status.json missing or unreadable"
    return doc


def _entry(doc: dict, slug: str) -> dict:
    return next(e for e in doc["repositories"] if e["repository"] == slug)


def test_contract_constants() -> None:
    assert SCHEMA == 1
    assert STATUS_CODES == ("pending", "ok", "auth_failed", "not_found", "no_repository_yaml", "fetch_failed")
    assert REASONS == ("startup", "interval", "request")


def test_initial_file_lists_every_repository_as_pending(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    StatusWriter(paths, SPECS, True, 15)
    assert paths.status_file.exists()
    assert stat.S_IMODE(paths.status_file.stat().st_mode) == 0o600
    doc = read_status(paths)
    assert doc is not None
    assert doc["schema"] == 1
    assert doc["upstream_override"] is True
    assert doc["sync"]["interval_minutes"] == 15
    assert doc["sync"]["state"] == "idle"
    assert [e["repository"] for e in doc["repositories"]] == ["Org/one", "org/two", "other/three"]
    for entry in doc["repositories"]:
        assert entry["status"] == "pending"
        assert entry["head"] is None
        assert entry["addons"] == []
        assert entry["refs_changed"] is False
    assert _entry(doc, "org/two")["branch_source"] == "configured"
    assert _entry(doc, "Org/one")["branch_source"] == "upstream_default"


def test_repository_entry_has_the_contract_fields(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    StatusWriter(paths, SPECS, False, 15)
    doc = read_status(paths)
    assert doc is not None
    assert set(doc) >= {"schema", "updated", "upstream_override", "sync", "repositories"}
    assert set(doc["sync"]) == {"state", "last_started", "last_finished", "next_due", "interval_minutes", "reason"}
    assert set(doc["repositories"][0]) == {
        "repository",
        "branch",
        "branch_source",
        "status",
        "message",
        "last_attempt",
        "last_success",
        "last_change",
        "head",
        "addons",
        "refs_changed",
    }


def test_failed_attempt_keeps_the_last_good_state(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    writer = StatusWriter(paths, SPECS, False, 15)
    writer.record(
        "Org/one",
        status="ok",
        message="",
        branch="main",
        branch_source="upstream_default",
        head="0123456789ab",
        addons=["demo"],
        refs_changed=True,
    )
    good = _entry(_doc(paths), "Org/one")
    token = "sentinel" + "-pat-" + "42"
    writer.record(
        "org/ONE",
        status="auth_failed",
        message=f"Authorization: Basic {token}\nupstream rejected the credentials",
        branch="main",
        branch_source="upstream_default",
    )
    entry = _entry(_doc(paths), "Org/one")
    assert entry["status"] == "auth_failed"
    assert entry["head"] == "0123456789ab"
    assert entry["addons"] == ["demo"]
    assert entry["last_success"] == good["last_success"]
    assert entry["last_change"] == good["last_change"]
    assert entry["last_attempt"] != good["last_attempt"]
    assert entry["refs_changed"] is False
    assert token not in paths.status_file.read_text()
    assert "uthorization" not in paths.status_file.read_text()


def test_no_repository_yaml_counts_as_a_success_without_change(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    writer = StatusWriter(paths, SPECS, False, 15)
    writer.record(
        "other/three",
        status="no_repository_yaml",
        message="repository.yaml missing at the branch root",
        branch="main",
        branch_source="upstream_default",
        head="ba9876543210",
        addons=[],
        refs_changed=False,
    )
    entry = _entry(_doc(paths), "other/three")
    assert entry["status"] == "no_repository_yaml"
    assert entry["head"] == "ba9876543210"
    assert entry["last_success"] is not None
    assert entry["last_change"] is None


def test_previous_file_carries_over_configured_and_drops_removed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    atomic_write_json(
        paths.status_file,
        {
            "schema": 1,
            "repositories": [
                {
                    "repository": "org/one",
                    "status": "ok",
                    "last_success": "2026-11-01T00:00:00Z",
                    "last_change": "2026-10-01T00:00:00Z",
                    "head": "aaaaaaaaaaaa",
                    "addons": ["demo"],
                },
                {"repository": "gone/repo", "status": "ok", "head": "bbbbbbbbbbbb"},
            ],
        },
    )
    StatusWriter(paths, SPECS, False, 15)
    doc = read_status(paths)
    assert doc is not None
    assert [e["repository"] for e in doc["repositories"]] == ["Org/one", "org/two", "other/three"]
    entry = _entry(doc, "Org/one")
    assert entry["status"] == "pending"
    assert entry["last_success"] == "2026-11-01T00:00:00Z"
    assert entry["last_change"] == "2026-10-01T00:00:00Z"
    assert entry["head"] == "aaaaaaaaaaaa"
    assert entry["addons"] == ["demo"]


def test_unreadable_previous_file_is_ignored(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.status_file.write_text("{not json", encoding="utf-8")
    StatusWriter(paths, SPECS, False, 15)
    doc = read_status(paths)
    assert doc is not None
    assert all(e["status"] == "pending" for e in doc["repositories"])


def test_cycle_state_and_updated_change_on_every_write(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    writer = StatusWriter(paths, SPECS, False, 15)
    first = _doc(paths)
    writer.begin_cycle("request")
    running = _doc(paths)
    assert running["sync"]["state"] == "running"
    assert running["sync"]["reason"] == "request"
    assert running["sync"]["last_started"]
    assert running["updated"] != first.get("updated")
    writer.end_cycle(1_800_000_000)
    idle = _doc(paths)
    assert idle["sync"]["state"] == "idle"
    assert idle["sync"]["last_finished"]
    assert idle["sync"]["next_due"]
    assert idle["updated"] != running["updated"]


def test_record_rejects_unknown_status_codes(tmp_path: Path) -> None:
    writer = StatusWriter(_paths(tmp_path), SPECS, False, 15)
    with pytest.raises(ValueError):
        writer.record("Org/one", status="broken", message="", branch=None, branch_source="upstream_default")


def test_read_status_without_file_is_none(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    assert read_status(paths) is None
    paths.status_file.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert read_status(paths) is None
