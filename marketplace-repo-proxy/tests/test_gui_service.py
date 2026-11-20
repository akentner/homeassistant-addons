"""GUI service layer: token-free options, overview from status.json, registration reader, build version, Sync now,
the access actions (list, add, URLs, revoke, rotate) on AccessStore and the last fetch per user (read-only).

Registration fixtures document the interface Phase 2 has to meet (D-19): /data/supervisor.json is a JSON object whose
`repositories` list holds one object per repository with `repository` (`owner/repo`, matched case-insensitively),
`registration` (one of `registered`, `missing`, `leftover`, `error`) and an optional `message`; every other key is
ignored, and a missing or unreadable file, a repository without an entry or any other state mean "no data".
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

import app.access
from app.access import AccessError, AccessStore
from app.accessread import AccessUnavailable
from app.paths import Paths
from app.web.admin_ui import ApiError
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


# --- access (MRP-14) ----------------------------------------------------------------------------------------------

ADDON_DIR = Path(__file__).resolve().parent.parent
UNCONFIGURED = "example-org/gone"
PUBLIC = "https://addons.example.invalid"


def access_doc(paths: Paths) -> dict:
    return json.loads(paths.access_file.read_text(encoding="utf-8"))


def entry_of(paths: Paths, repository: str, user: str) -> dict | None:
    return next(
        (
            e
            for e in access_doc(paths)["entries"]
            if e["repository"].lower() == repository.lower() and e["user"] == user
        ),
        None,
    )


def links(paths: Paths) -> set[str]:
    root = paths.access_root
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_symlink()} if root.is_dir() else set()


def write_access(paths: Paths, entries: list[dict]) -> None:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.access_file.write_text(json.dumps({"schema": 1, "entries": entries}), encoding="utf-8")


def seed(paths: Paths, repository: str, user: str, source: str = "cli") -> dict:
    """An entry written through the real store, with its link (configured repositories only)."""
    config = load_gui_config(paths, hostname="proxy-host", version_file=paths.data_dir / "nope")
    return AccessStore(paths).add(repository, user, source=source, specs=config.options.repositories)


def test_access_list_without_file_lists_configured_repositories(paths: Paths) -> None:
    data = service(paths).access_list()
    assert data["repositories"] == [
        {"repository": REPO, "active": True, "users": []},
        {"repository": OTHER, "active": True, "users": []},
    ]
    assert isinstance(data["now_ms"], int)
    assert not paths.access_file.exists()


def test_access_list_groups_sorts_flags_and_never_carries_hash_or_url(paths: Paths) -> None:
    seed(paths, REPO, "dave", "cli")
    seed(paths, REPO, "alice", "gui")
    seed(paths, REPO, "local", "system")
    seed(paths, OTHER, "carol", "api")
    seed(paths, UNCONFIGURED, "bob")
    seed(paths, "Example-Org/Gone", "erin")
    data = service(paths).access_list()
    rows = data["repositories"]
    assert [(r["repository"], r["active"]) for r in rows] == [(REPO, True), (OTHER, True), (UNCONFIGURED, False)]
    assert rows[0]["users"] == [
        {"user": "alice", "source": "gui", "created": rows[0]["users"][0]["created"], "protected": False,
         "last_fetch": None},
        {"user": "dave", "source": "cli", "created": rows[0]["users"][1]["created"], "protected": False,
         "last_fetch": None},
        {"user": "local", "source": "system", "created": rows[0]["users"][2]["created"], "protected": True,
         "last_fetch": None},
    ]
    assert all(isinstance(u["created"], str) for u in rows[0]["users"])
    assert [u["user"] for u in rows[2]["users"]] == ["bob", "erin"]
    text = json.dumps(data)
    assert not HEX32.search(text)
    assert "http" not in text


def test_access_list_reserved_label_is_protected_and_unknown_source_is_none(paths: Paths) -> None:
    write_access(
        paths,
        [
            {"repository": REPO, "user": "LOCAL", "hash": HASH, "created": 5, "source": "cli"},
            {"repository": REPO, "user": "x", "hash": "1" * 32, "source": "other"},
            {"repository": REPO, "user": 5, "hash": "2" * 32},
            {"repository": "not a repo", "user": "y", "hash": "3" * 32},
        ],
    )
    users = service(paths).access_list()["repositories"][0]["users"]
    assert users == [
        {"user": "LOCAL", "source": "cli", "created": None, "protected": True, "last_fetch": None},
        {"user": "x", "source": None, "created": None, "protected": False, "last_fetch": None},
    ]


@pytest.mark.parametrize("user", [None, "", 5, "a b", "-x", "ä", "x" * 65])
def test_add_user_rejects_invalid_label(paths: Paths, user: object) -> None:
    with pytest.raises(AccessError) as info:
        service(paths).add_user(REPO, user)
    assert info.value.code == "invalid_user"
    assert not paths.access_file.exists()


def test_add_user_reserved_label(paths: Paths) -> None:
    with pytest.raises(AccessError) as info:
        service(paths).add_user(REPO, "local")
    assert info.value.code == "user_reserved"


def test_add_user_twice_is_user_exists(paths: Paths) -> None:
    svc = service(paths)
    svc.add_user(REPO, "carol")
    with pytest.raises(AccessError) as info:
        svc.add_user(REPO, "carol")
    assert info.value.code == "user_exists"


def test_add_user_unknown_repository(paths: Paths) -> None:
    with pytest.raises(AccessError) as info:
        service(paths).add_user("example-org/unknown", "carol")
    assert info.value.code == "repository_unknown"


def test_add_user_matches_repository_case_insensitively_and_stores_configured_case(paths: Paths) -> None:
    result = service(paths).add_user("Example-Org/Private-Addons", "carol")
    assert result["repository"] == REPO and result["user"] == "carol" and result["source"] == "gui"
    entry = entry_of(paths, REPO, "carol")
    assert entry is not None and entry["repository"] == REPO and entry["source"] == "gui"
    assert links(paths) == {f"{REPO}/{entry['hash']}"}
    assert result["urls"] == {"internal": f"http://proxy-host:8080/repo/{REPO}/{entry['hash']}"}


def test_add_user_with_public_url(paths: Paths) -> None:
    write_options(paths, [{"repository": REPO}], public_url=PUBLIC)
    result = service(paths).add_user(REPO, "carol")
    hash_ = entry_of(paths, REPO, "carol")["hash"]
    assert result["urls"] == {
        "internal": f"http://proxy-host:8080/repo/{REPO}/{hash_}",
        "public": f"{PUBLIC}/repo/{REPO}/{hash_}",
    }


def test_user_urls(paths: Paths) -> None:
    svc = service(paths)
    added = svc.add_user(REPO, "carol")
    assert svc.user_urls("EXAMPLE-ORG/private-addons", "carol") == added["urls"]
    for user in ("Carol", "nobody"):
        with pytest.raises(AccessError) as info:
            svc.user_urls(REPO, user)
        assert info.value.code == "user_unknown"
    with pytest.raises(AccessError) as info:
        svc.user_urls(UNCONFIGURED, "carol")
    assert info.value.code == "repository_unknown"


def test_user_urls_invalid_stored_hash(paths: Paths) -> None:
    write_access(paths, [{"repository": REPO, "user": "carol", "hash": "nope", "source": "cli"}])
    with pytest.raises(AccessError) as info:
        service(paths).user_urls(REPO, "carol")
    assert info.value.code == "invalid_hash"


# revoke


@pytest.mark.parametrize("confirm", [None, "", "Carol", " carol", "carol ", "CAROL", 1, ["carol"]])
def test_revoke_needs_exact_confirm(paths: Paths, confirm: object) -> None:
    seed(paths, REPO, "carol")
    before = paths.access_file.read_bytes()
    with pytest.raises(ApiError) as info:
        service(paths).revoke_user(REPO, "carol", confirm)
    assert info.value.code == "confirmation_required"
    assert paths.access_file.read_bytes() == before


def test_revoke_removes_entry_and_link_then_user_unknown(paths: Paths) -> None:
    seed(paths, REPO, "carol")
    alice = seed(paths, REPO, "alice")
    svc = service(paths)
    assert svc.revoke_user("Example-Org/Private-Addons", "carol", "carol") is None
    assert entry_of(paths, REPO, "carol") is None
    assert links(paths) == {f"{REPO}/{alice['hash']}"}
    with pytest.raises(AccessError) as info:
        svc.revoke_user(REPO, "carol", "carol")
    assert info.value.code == "user_unknown"


def test_revoke_label_is_case_sensitive(paths: Paths) -> None:
    seed(paths, REPO, "carol")
    with pytest.raises(AccessError) as info:
        service(paths).revoke_user(REPO, "Carol", "Carol")
    assert info.value.code == "user_unknown"
    assert entry_of(paths, REPO, "carol") is not None


def test_revoke_works_for_unconfigured_repository(paths: Paths) -> None:
    seed(paths, UNCONFIGURED, "bob")
    service(paths).revoke_user("Example-Org/Gone", "bob", "bob")
    assert access_doc(paths)["entries"] == []


@pytest.mark.parametrize("user,source", [("local", "system"), ("helper", "system")])
def test_revoke_of_system_user_is_protected(paths: Paths, user: str, source: str) -> None:
    seed(paths, REPO, user, source)
    before = paths.access_file.read_bytes()
    with pytest.raises(ApiError) as info:
        service(paths).revoke_user(REPO, user, user)
    assert info.value.code == "protected"
    assert paths.access_file.read_bytes() == before


def test_revoke_of_reserved_label_with_other_source_is_protected(paths: Paths) -> None:
    write_access(paths, [{"repository": REPO, "user": "Local", "hash": HASH, "source": "cli"}])
    with pytest.raises(ApiError) as info:
        service(paths).revoke_user(REPO, "Local", "Local")
    assert info.value.code == "protected"


# rotate


def test_rotate_replaces_hash_keeps_source_and_resets_created(paths: Paths) -> None:
    old = seed(paths, REPO, "carol", "cli")
    doc = access_doc(paths)
    doc["entries"][0]["created"] = "2020-01-01T00:00:00Z"
    paths.access_file.write_text(json.dumps(doc), encoding="utf-8")
    result = service(paths).rotate_user("Example-Org/Private-Addons", "carol", "carol")
    entry = entry_of(paths, REPO, "carol")
    assert entry["hash"] != old["hash"]
    assert entry["source"] == "cli"
    assert entry["created"] != "2020-01-01T00:00:00Z"
    assert links(paths) == {f"{REPO}/{entry['hash']}"}
    assert result == {
        "repository": REPO,
        "user": "carol",
        "source": "cli",
        "created": entry["created"],
        "urls": {"internal": f"http://proxy-host:8080/repo/{REPO}/{entry['hash']}"},
    }
    assert len(access_doc(paths)["entries"]) == 1


def test_second_rotate_gives_a_third_hash(paths: Paths) -> None:
    first = seed(paths, REPO, "carol")["hash"]
    svc = service(paths)
    svc.rotate_user(REPO, "carol", "carol")
    second = entry_of(paths, REPO, "carol")["hash"]
    svc.rotate_user(REPO, "carol", "carol")
    third = entry_of(paths, REPO, "carol")["hash"]
    assert len({first, second, third}) == 3
    assert links(paths) == {f"{REPO}/{third}"}


@pytest.mark.parametrize("confirm", [None, "Carol", " carol", 1])
def test_rotate_needs_exact_confirm(paths: Paths, confirm: object) -> None:
    seed(paths, REPO, "carol")
    before = paths.access_file.read_bytes()
    with pytest.raises(ApiError) as info:
        service(paths).rotate_user(REPO, "carol", confirm)
    assert info.value.code == "confirmation_required"
    assert paths.access_file.read_bytes() == before


def test_rotate_of_unconfigured_repository_is_repository_unknown(paths: Paths) -> None:
    seed(paths, UNCONFIGURED, "bob")
    with pytest.raises(AccessError) as info:
        service(paths).rotate_user(UNCONFIGURED, "bob", "bob")
    assert info.value.code == "repository_unknown"


def test_rotate_of_unknown_user(paths: Paths) -> None:
    with pytest.raises(AccessError) as info:
        service(paths).rotate_user(REPO, "nobody", "nobody")
    assert info.value.code == "user_unknown"


def test_rotate_of_system_user_is_protected(paths: Paths) -> None:
    seed(paths, REPO, "local", "system")
    before = paths.access_file.read_bytes()
    with pytest.raises(ApiError) as info:
        service(paths).rotate_user(REPO, "local", "local")
    assert info.value.code == "protected"
    assert paths.access_file.read_bytes() == before


@pytest.mark.parametrize("source", ["other", None])
def test_rotate_refuses_invalid_stored_source_before_any_write(paths: Paths, source: object) -> None:
    write_access(paths, [{"repository": REPO, "user": "carol", "hash": HASH, "source": source}])
    before = paths.access_file.read_bytes()
    with pytest.raises(AccessError) as info:
        service(paths).rotate_user(REPO, "carol", "carol")
    assert info.value.code == "invalid_user"
    assert paths.access_file.read_bytes() == before


def test_rotate_restores_the_old_hash_when_add_fails(paths: Paths, monkeypatch: pytest.MonkeyPatch) -> None:
    old = seed(paths, REPO, "carol", "gui")
    real_add = AccessStore.add
    calls = {"n": 0}

    def flaky_add(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(28, "No space left on device")
        return real_add(self, *args, **kwargs)

    monkeypatch.setattr(AccessStore, "add", flaky_add)
    with pytest.raises(OSError):
        service(paths).rotate_user(REPO, "carol", "carol")
    entry = entry_of(paths, REPO, "carol")
    assert entry is not None and entry["hash"] == old["hash"] and entry["source"] == "gui"
    assert links(paths) == {f"{REPO}/{old['hash']}"}


def test_rotate_keeps_the_add_error_when_add_fails_after_its_write(
    paths: Paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-01: reconcile_tree fails after add() replaced access.json; no rollback, the OSError surfaces unchanged."""
    old = seed(paths, REPO, "carol", "gui")
    real_reconcile = app.access.reconcile_tree
    calls = {"n": 0}

    def flaky_reconcile(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # 1 = revoke, 2 = add (after its atomic write)
            raise OSError(28, "No space left on device")
        return real_reconcile(*args, **kwargs)

    monkeypatch.setattr(app.access, "reconcile_tree", flaky_reconcile)
    with pytest.raises(OSError) as info:
        service(paths).rotate_user(REPO, "carol", "carol")
    assert not isinstance(info.value, AccessError)
    assert info.value.errno == 28
    entries = [e for e in access_doc(paths)["entries"] if e["user"] == "carol"]
    assert len(entries) == 1
    assert entries[0]["hash"] != old["hash"] and entries[0]["source"] == "gui"
    assert calls["n"] == 2  # no rollback add (it would reconcile a third time)


def test_rotate_keeps_the_add_error_when_the_rollback_fails(paths: Paths, monkeypatch: pytest.MonkeyPatch) -> None:
    seed(paths, REPO, "carol", "gui")

    def failing_add(self, *args, **kwargs):
        raise OSError(28, "No space left on device") if "hash_" not in kwargs else OSError(5, "I/O error")

    monkeypatch.setattr(AccessStore, "add", failing_add)
    with pytest.raises(OSError) as info:
        service(paths).rotate_user(REPO, "carol", "carol")
    assert info.value.errno == 28
    assert entry_of(paths, REPO, "carol") is None  # fail closed: revoked, rollback failed


_READER = r"""
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from app.access import AccessStore
from app.accessread import read_entries_safe
from app.paths import Paths
store = AccessStore(Paths.under(sys.argv[2]))
ready, stop = pathlib.Path(sys.argv[3]), pathlib.Path(sys.argv[4])
reads = missing = double = 0
while True:
    done = stop.exists()
    count = sum(1 for e in read_entries_safe(store) if e.get("user") == "carol")
    reads += 1
    missing += count == 0
    double += count > 1
    ready.touch()
    if done:
        break
print(json.dumps({"reads": reads, "missing": missing, "double": double}))
"""


def test_rotate_is_atomic_for_a_locked_reader_in_another_process(paths: Paths, tmp_path: Path) -> None:
    seed(paths, REPO, "carol")
    ready, stop = tmp_path / "ready", tmp_path / "stop"
    proc = subprocess.Popen(
        [sys.executable, "-c", _READER, str(ADDON_DIR), str(tmp_path), str(ready), str(stop)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "reader did not start"
        svc = service(paths)
        hashes = set()
        for _ in range(50):
            svc.rotate_user(REPO, "carol", "carol")
            hashes.add(entry_of(paths, REPO, "carol")["hash"])
        stop.touch()
        out, _err = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    result = json.loads(out)
    assert result["reads"] > 1
    assert result["missing"] == 0 and result["double"] == 0
    assert len(hashes) == 50


# unreadable access.json: refused everywhere, file untouched, never renamed

UNREADABLE = ["{not json", '{"schema": 2, "entries": []}', '{"schema": 1, "entries": {}}']


@pytest.mark.parametrize("content", UNREADABLE)
@pytest.mark.parametrize("action", ["list", "add", "urls", "revoke", "rotate"])
def test_unreadable_access_file_is_refused_and_left_alone(paths: Paths, content: str, action: str) -> None:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.access_file.write_text(content, encoding="utf-8")
    svc = service(paths)
    calls = {
        "list": lambda: svc.access_list(),
        "add": lambda: svc.add_user(REPO, "carol"),
        "urls": lambda: svc.user_urls(REPO, "carol"),
        "revoke": lambda: svc.revoke_user(REPO, "carol", "carol"),
        "rotate": lambda: svc.rotate_user(REPO, "carol", "carol"),
    }
    with pytest.raises(AccessUnavailable):
        calls[action]()
    assert paths.access_file.read_text(encoding="utf-8") == content
    assert not paths.access_file.with_name("access.json.corrupt").exists()


def test_access_log_lines_name_labels_only(paths: Paths, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    svc = service(paths)
    svc.add_user(REPO, "carol")
    svc.add_user(REPO, "dave")
    svc.rotate_user(REPO, "carol", "carol")
    svc.revoke_user(REPO, "dave", "dave")
    text = caplog.text
    assert "gui: added user carol to example-org/private-addons" in text
    assert "gui: rotated user carol of example-org/private-addons" in text
    assert "gui: revoked user dave from example-org/private-addons" in text
    assert not HEX32.search(text)
    assert "http" not in text


# last fetch per user (MRP-15, D-21): /data/last-fetch.json is read once per list, never written or renamed by the GUI

LAST_FETCH = "2026-11-18T12:00:05Z"


def last_fetch_file(paths: Paths) -> Path:
    return paths.data_dir / "last-fetch.json"


def write_last_fetch_doc(paths: Paths, entries: list[dict], schema: int = 1) -> None:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    doc = {"schema": schema, "updated": LAST_FETCH, "entries": entries}
    last_fetch_file(paths).write_text(json.dumps(doc), encoding="utf-8")


def fetched(user: str, repository: str = REPO, when: str = LAST_FETCH) -> dict:
    return {"repository": repository, "user": user, "last_fetch": when}


def access_entry(user: str, created: object, repository: str = REPO, hash_: str = HASH) -> dict:
    entry = {"repository": repository, "user": user, "hash": hash_, "source": "gui"}
    if created is not _MISSING:
        entry["created"] = created
    return entry


_MISSING = object()


def last_fetch_by_user(data: dict, repository: str = REPO) -> dict[str, object]:
    row = rows_by_repo(data)[repository]
    return {u["user"]: u["last_fetch"] for u in row["users"]}


def test_last_fetch_is_none_without_last_fetch_file(paths: Paths) -> None:
    seed(paths, REPO, "alice")
    seed(paths, OTHER, "bob")
    data = service(paths).access_list()
    assert last_fetch_by_user(data) == {"alice": None}
    assert last_fetch_by_user(data, OTHER) == {"bob": None}
    assert not last_fetch_file(paths).exists()


@pytest.mark.parametrize(
    "created,expected",
    [
        ("2026-11-18T12:00:00Z", LAST_FETCH),  # fetched after creation
        (LAST_FETCH, None),  # same second: not strictly newer
        ("2026-11-18T12:00:06Z", None),  # created (or rotated) after the record
        (_MISSING, LAST_FETCH),  # no created: the record is shown
        (None, LAST_FETCH),
        (5, LAST_FETCH),
        ("yesterday", LAST_FETCH),
        ("2026-11-18 12:00:00", LAST_FETCH),
    ],
)
def test_last_fetch_display_rule(paths: Paths, created: object, expected: str | None) -> None:
    write_access(paths, [access_entry("alice", created)])
    write_last_fetch_doc(paths, [fetched("alice")])
    assert last_fetch_by_user(service(paths).access_list()) == {"alice": expected}


def test_last_fetch_matches_repository_case_insensitively_and_user_exactly(paths: Paths) -> None:
    write_access(
        paths,
        [
            access_entry("alice", "2026-11-18T12:00:00Z"),
            access_entry("Alice", "2026-11-18T12:00:00Z", hash_="1" * 32),
            access_entry("bob", "2026-11-18T12:00:00Z", hash_="2" * 32),
        ],
    )
    write_last_fetch_doc(paths, [fetched("alice", "Example-Org/Private-Addons"), fetched("Bob")])
    assert last_fetch_by_user(service(paths).access_list()) == {"Alice": None, "alice": LAST_FETCH, "bob": None}


@pytest.mark.parametrize(
    "content",
    ["{not json", json.dumps({"schema": 2, "updated": LAST_FETCH, "entries": [fetched("alice")]}), "[]"],
)
def test_invalid_last_fetch_file_means_never_for_everyone_and_stays_untouched(paths: Paths, content: str) -> None:
    write_access(paths, [access_entry("alice", "2026-11-18T12:00:00Z")])
    last_fetch_file(paths).write_text(content, encoding="utf-8")
    before = sorted(p.name for p in paths.data_dir.iterdir())
    assert last_fetch_by_user(service(paths).access_list()) == {"alice": None}
    assert last_fetch_file(paths).read_text(encoding="utf-8") == content
    assert sorted(p.name for p in paths.data_dir.iterdir()) == before


def test_last_fetch_for_inactive_repositories_follows_the_same_rule(paths: Paths) -> None:
    write_access(
        paths,
        [
            access_entry("erin", "2026-11-18T12:00:00Z", UNCONFIGURED),
            access_entry("frank", "2026-11-18T12:00:09Z", UNCONFIGURED, "1" * 32),
        ],
    )
    write_last_fetch_doc(paths, [fetched("erin", UNCONFIGURED), fetched("frank", UNCONFIGURED)])
    data = service(paths).access_list()
    assert rows_by_repo(data)[UNCONFIGURED]["active"] is False
    assert last_fetch_by_user(data, UNCONFIGURED) == {"erin": LAST_FETCH, "frank": None}


def test_rotation_shows_never_until_the_new_url_is_used(paths: Paths) -> None:
    svc = service(paths)
    svc.add_user(REPO, "carol")
    write_last_fetch_doc(paths, [fetched("carol", when="2099-01-01T00:00:00Z")])
    assert last_fetch_by_user(svc.access_list()) == {"carol": "2099-01-01T00:00:00Z"}
    svc.rotate_user(REPO, "carol", "carol")
    write_last_fetch_doc(paths, [fetched("carol", when="2000-01-01T00:00:00Z")])
    assert last_fetch_by_user(svc.access_list()) == {"carol": None}


def test_access_list_never_writes_the_last_fetch_file(paths: Paths) -> None:
    write_access(paths, [access_entry("alice", "2026-11-18T12:00:00Z")])
    write_last_fetch_doc(paths, [fetched("alice")])
    before = last_fetch_file(paths).stat()
    service(paths).access_list()
    after = last_fetch_file(paths).stat()
    assert (before.st_ino, before.st_mtime_ns, before.st_size) == (after.st_ino, after.st_mtime_ns, after.st_size)
    assert not HEX32.search(json.dumps(service(paths).access_list()))
