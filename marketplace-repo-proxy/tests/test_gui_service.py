"""GUI service layer: token-free options, overview from status.json, registration reader, build version, Sync now.

Registration fixtures document the interface Phase 2 has to meet (D-19): /data/supervisor.json is a JSON object whose
`repositories` list holds one object per repository with `repository` (`owner/repo`, matched case-insensitively),
`registration` (one of `registered`, `missing`, `leftover`, `error`) and an optional `message`; every other key is
ignored, and a missing or unreadable file, a repository without an entry or any other state mean "no data".
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

import pytest

from app.paths import Paths
from app.web.registration import FILE_NAME, REGISTRATION_STATES, read_registration
from app.web.service import GuiConfig, GuiService, load_gui_config, read_build_version
from guihelpers import write_options, write_status, write_supervisor

REPO = "example-org/private-addons"
OTHER = "example-org/other"
HASH = "0123456789abcdef0123456789abcdef"
HEX32 = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")
TOKEN = "SENTINEL-TOKEN-0123"


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    p = Paths.under(tmp_path)
    write_options(p, [{"repository": REPO}, {"repository": OTHER, "branch": "stable"}], github_token=TOKEN)
    return p


def service(paths: Paths, **kwargs) -> GuiService:
    config = load_gui_config(paths, hostname="proxy-host", version_file=paths.data_dir / "nope")
    return GuiService(paths, config, **kwargs)


def status_doc(*entries: dict) -> dict:
    return {
        "schema": 1,
        "sync": {
            "state": "idle",
            "last_started": "2026-11-18T10:00:00Z",
            "last_finished": "2026-11-18T10:00:05Z",
            "next_due": "2026-11-18T10:05:05Z",
            "interval_minutes": 5,
            "reason": "startup",
        },
        "repositories": list(entries),
    }


def rows_by_repo(data: dict) -> dict[str, dict]:
    return {row["repository"]: row for row in data["repositories"]}


# --- overview -----------------------------------------------------------------------------------------------------


def test_overview_without_status_file(paths: Paths) -> None:
    data = service(paths).overview()
    assert data["status_available"] is False
    assert [row["repository"] for row in data["repositories"]] == [REPO, OTHER]
    for row in data["repositories"]:
        assert row["status"] is None and row["registration"] is None
        assert row["addons"] == [] and row["message"] == "" and row["head"] is None
    assert data["sync"]["interval_minutes"] == 15
    assert data["sync"]["requested"] is False
    assert data["sync"]["state"] is None


def test_overview_follows_options_order_and_case(paths: Paths) -> None:
    write_status(
        paths,
        status_doc(
            {"repository": "EXAMPLE-ORG/OTHER", "status": "bogus", "addons": "demo", "branch": "stable",
             "branch_source": "configured"},
            {"repository": "Example-Org/Private-Addons", "status": "ok", "message": "fine", "head": "0123456789ab",
             "addons": ["demo", 7], "branch": "main", "branch_source": "upstream_default",
             "last_success": "2026-11-18T10:00:04Z"},
        ),
    )
    config = load_gui_config(paths, hostname="h", version_file=paths.data_dir / "x")
    data = GuiService(paths, config, clock=lambda: 1234.5).overview()
    assert data["now_ms"] == 1234500
    assert data["status_available"] is True
    first, second = data["repositories"]
    assert first["repository"] == REPO and second["repository"] == OTHER
    assert first["status"] == "ok" and first["head"] == "0123456789ab" and first["addons"] == ["demo"]
    assert first["branch"] == "main" and first["branch_source"] == "upstream_default"
    assert first["last_success"] == "2026-11-18T10:00:04Z" and first["message"] == "fine"
    assert second["status"] is None and second["addons"] == []
    assert data["sync"]["interval_minutes"] == 5 and data["sync"]["reason"] == "startup"


def test_overview_repository_configured_after_last_sync(paths: Paths) -> None:
    write_status(paths, status_doc({"repository": REPO, "status": "ok"}))
    rows = rows_by_repo(service(paths).overview())
    assert rows[REPO]["status"] == "ok"
    assert rows[OTHER]["status"] is None and rows[OTHER]["branch"] == "stable"


def test_overview_invalid_status_json_leaves_file_alone(paths: Paths) -> None:
    write_status(paths, "{not json")
    before = paths.status_file.read_bytes()
    data = service(paths).overview()
    assert data["status_available"] is False
    assert paths.status_file.read_bytes() == before


def test_overview_row_keys(paths: Paths) -> None:
    row = service(paths).overview()["repositories"][0]
    assert set(row) == {
        "repository", "branch", "branch_source", "status", "message", "last_attempt", "last_success",
        "last_change", "head", "addons", "registration",
    }


# --- registration slot (D-19) ---------------------------------------------------------------------------------------


def test_registration_patched_reader_value(paths: Paths) -> None:
    svc = service(paths, registration=lambda _p: {REPO: {"state": "leftover", "detail": "x"}})
    assert rows_by_repo(svc.overview())[REPO]["registration"] == {"state": "leftover", "detail": "x"}


def test_registration_patched_reader_unknown_state(paths: Paths) -> None:
    svc = service(paths, registration=lambda _p: {REPO: {"state": "bogus"}})
    assert rows_by_repo(svc.overview())[REPO]["registration"] is None


def test_registration_reader_that_raises_means_no_data(paths: Paths) -> None:
    def broken(_p: Paths) -> dict:
        raise RuntimeError(HASH)

    data = service(paths, registration=broken).overview()
    assert all(row["registration"] is None for row in data["repositories"])


def test_registration_present_file(paths: Paths) -> None:
    write_supervisor(
        paths,
        {
            "schema": 1,
            "repositories": [
                {"repository": "Example-Org/Private-Addons", "registration": "registered", "message": "ok"},
                {"repository": OTHER, "registration": "leftover"},
            ],
            "leftovers": [],
        },
    )
    result = read_registration(paths)
    assert result == {REPO: {"state": "registered", "detail": "ok"}, OTHER: {"state": "leftover"}}
    rows = rows_by_repo(service(paths).overview())
    assert rows[REPO]["registration"] == {"state": "registered", "detail": "ok"}
    assert rows[OTHER]["registration"] == {"state": "leftover"}


@pytest.mark.parametrize("state", REGISTRATION_STATES)
def test_registration_states_map_one_to_one(paths: Paths, state: str) -> None:
    write_supervisor(paths, {"repositories": [{"repository": REPO, "registration": state}]})
    assert read_registration(paths) == {REPO: {"state": state}}
    assert rows_by_repo(service(paths).overview())[REPO]["registration"] == {"state": state}


def test_registration_absent_file(paths: Paths) -> None:
    assert read_registration(paths) is None
    assert all(row["registration"] is None for row in service(paths).overview()["repositories"])


@pytest.mark.parametrize("state", ["pending", "bogus"])
def test_registration_unknown_state_skips_only_that_repository(paths: Paths, state: str) -> None:
    write_supervisor(
        paths,
        {"repositories": [{"repository": REPO, "registration": state}, {"repository": OTHER, "registration": "error"}]},
    )
    assert read_registration(paths) == {OTHER: {"state": "error"}}
    rows = rows_by_repo(service(paths).overview())
    assert rows[REPO]["registration"] is None
    assert rows[OTHER]["registration"] == {"state": "error"}


def _snapshot(paths: Paths) -> tuple[bytes, int, list[str]]:
    path = paths.data_dir / FILE_NAME
    return path.read_bytes(), path.stat().st_mtime_ns, sorted(os.listdir(paths.data_dir))


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        b"\xff\xfe{}",
        json.dumps([{"repository": REPO, "registration": "registered"}]),
        json.dumps({"repositories": {"repository": REPO, "registration": "registered"}}),
    ],
    ids=["invalid_json", "invalid_utf8", "json_array", "repositories_not_list"],
)
def test_registration_corrupt_file_is_none_and_untouched(paths: Paths, content: str | bytes) -> None:
    write_supervisor(paths, content)
    before = _snapshot(paths)
    assert read_registration(paths) is None
    assert all(row["registration"] is None for row in service(paths).overview()["repositories"])
    assert _snapshot(paths) == before


def test_registration_corrupt_entries_are_skipped(paths: Paths) -> None:
    write_supervisor(
        paths,
        {
            "repositories": [
                "not an object",
                {"repository": 7, "registration": "registered"},
                {"repository": "no-slash", "registration": "registered"},
                {"repository": REPO},
                {"repository": OTHER, "registration": "missing", "message": 5},
            ]
        },
    )
    before = _snapshot(paths)
    assert read_registration(paths) == {OTHER: {"state": "missing"}}
    assert _snapshot(paths) == before


def test_registration_missing_entry_and_duplicate_first_wins(paths: Paths) -> None:
    write_supervisor(
        paths,
        {
            "repositories": [
                {"repository": "EXAMPLE-ORG/OTHER", "registration": "missing", "message": "first"},
                {"repository": OTHER, "registration": "registered", "message": "second"},
            ]
        },
    )
    rows = rows_by_repo(service(paths).overview())
    assert rows[OTHER]["registration"] == {"state": "missing", "detail": "first"}
    assert rows[REPO]["registration"] is None


def test_registration_detail_masks_hash_and_is_cut(paths: Paths) -> None:
    message = f"link {HASH} " + "x" * 300
    write_supervisor(paths, {"repositories": [{"repository": REPO, "registration": "error", "message": message}]})
    detail = rows_by_repo(service(paths).overview())[REPO]["registration"]["detail"]
    assert not HEX32.search(detail)
    assert len(detail) == 200


# --- build version (D-30) -------------------------------------------------------------------------------------------


def test_build_version_valid(tmp_path: Path) -> None:
    path = tmp_path / "BUILD_VERSION"
    path.write_text("0.1.0-3\n", encoding="utf-8")
    assert read_build_version(path) == "0.1.0-3"


@pytest.mark.parametrize(
    "content",
    ["", "   \n", "0.1.0", "latest", "v0.1.0-3", "1" * 20 + ".0.0-1" + "1" * 20, b"\xff\xfe0.1.0-3"],
    ids=["empty", "whitespace", "no_subpatch", "latest", "v_prefix", "too_long", "invalid_utf8"],
)
def test_build_version_rejected(tmp_path: Path, content: str | bytes) -> None:
    path = tmp_path / "BUILD_VERSION"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    assert read_build_version(path) is None


def test_build_version_missing_file(tmp_path: Path) -> None:
    assert read_build_version(tmp_path / "missing") is None


def test_build_version_in_config_and_meta(paths: Paths) -> None:
    version_file = paths.data_dir / "BUILD_VERSION"
    version_file.write_text("0.1.0-3\n", encoding="utf-8")
    config = load_gui_config(paths, hostname="h", version_file=version_file)
    assert config.version == "0.1.0-3"
    assert GuiService(paths, config).meta() == {"version": "0.1.0-3"}


def test_meta_without_version(paths: Paths) -> None:
    config = GuiConfig(load_gui_config(paths, hostname="h", version_file=paths.data_dir / "x").options, "h")
    assert config.version is None
    assert GuiService(paths, config).meta() == {"version": None}


# --- token-free options (D-07) ------------------------------------------------------------------------------------


def test_load_gui_config_drops_token(paths: Paths) -> None:
    config = load_gui_config(paths, hostname="h", version_file=paths.data_dir / "x")
    assert config.options.github_token == ""
    assert TOKEN not in repr(config)
    assert all(TOKEN not in str(value) for value in vars(config.options).values())
    assert config.hostname == "h"


def test_load_gui_config_default_hostname(paths: Paths) -> None:
    import socket

    assert load_gui_config(paths, version_file=paths.data_dir / "x").hostname == socket.gethostname()


# --- Sync now (D-18) ----------------------------------------------------------------------------------------------


def test_request_sync_writes_trigger(paths: Paths) -> None:
    svc = service(paths)
    assert not paths.run_dir.exists()
    assert svc.request_sync() == {"requested": True}
    assert json.loads(paths.trigger_file.read_text(encoding="utf-8")) == {}
    assert stat.S_IMODE(paths.trigger_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(paths.run_dir.stat().st_mode) == 0o700
    assert svc.overview()["sync"]["requested"] is True


def test_request_sync_keeps_existing_run_dir_mode(paths: Paths) -> None:
    paths.run_dir.mkdir(parents=True)
    paths.run_dir.chmod(0o755)
    service(paths).request_sync()
    assert stat.S_IMODE(paths.run_dir.stat().st_mode) == 0o755
    assert paths.trigger_file.exists()
