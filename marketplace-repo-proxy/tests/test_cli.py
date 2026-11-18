"""`mrp` CLI: users list/add/url/revoke, sync and reconcile (app.cli)."""

from __future__ import annotations

import json
import logging
import os
import re

import pytest

from app import cli
from app.access import HASH_RE, AccessStore, new_hash
from app.paths import Paths

REPO = "example-org/private-addons"
HOST = "proxy-test"
URL_RE = re.compile(r"^internal: http://proxy-test:8080/repo/example-org/private-addons/([0-9a-f]{32})$")


@pytest.fixture
def paths(tmp_path):
    p = Paths.under(tmp_path)
    p.data_dir.mkdir(parents=True)
    write_options(p)
    return p


def write_options(p: Paths, **extra) -> None:
    doc = {"github_token": "", "repositories": [{"repository": REPO}], **extra}
    p.options_file.write_text(json.dumps(doc), encoding="utf-8")


def run(p: Paths, *argv: str) -> int:
    return cli.main(list(argv), paths=p, hostname=HOST)


def stored(p: Paths) -> dict:
    return json.loads(p.access_file.read_text(encoding="utf-8"))


def test_new_hash_is_32_hex_and_random():
    first, second = new_hash(), new_hash()
    assert HASH_RE.match(first) and HASH_RE.match(second)
    assert first != second


def test_users_add_prints_internal_url_and_links(paths, capsys):
    assert run(paths, "users", "add", REPO, "alice") == 0
    out = capsys.readouterr().out.splitlines()
    match = URL_RE.match(out[0])
    assert match, out
    hash_ = match.group(1)
    link = paths.link_path("example-org", "private-addons", hash_)
    assert link.is_symlink()
    assert os.readlink(link) == str(paths.repo_dir("example-org", "private-addons"))
    entry = stored(paths)["entries"][0]
    assert entry["repository"] == REPO and entry["user"] == "alice" and entry["hash"] == hash_
    assert entry["source"] == "cli"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", entry["created"])
    assert paths.access_file.stat().st_mode & 0o777 == 0o600


def test_users_add_with_public_url_prints_public_line(paths, capsys):
    write_options(paths, public_url="https://addons.example.com/")
    assert run(paths, "users", "add", REPO, "alice") == 0
    out = capsys.readouterr().out.splitlines()
    hash_ = URL_RE.match(out[0]).group(1)
    assert out[1] == f"public: https://addons.example.com/repo/{REPO}/{hash_}"


def test_unknown_repository_is_refused(paths, capsys):
    assert run(paths, "users", "add", "example-org/other", "alice") == 1
    assert capsys.readouterr().err.strip() == "error: repository_unknown"
    assert not paths.access_file.exists()


def test_second_add_of_same_user_is_refused(paths, capsys):
    assert run(paths, "users", "add", REPO, "alice") == 0
    capsys.readouterr()
    assert run(paths, "users", "add", REPO.upper(), "alice") == 1
    assert capsys.readouterr().err.strip() == "error: user_exists"
    assert len(stored(paths)["entries"]) == 1


def test_invalid_user_label_is_refused(paths, capsys):
    assert run(paths, "users", "add", REPO, "-x") == 1
    assert capsys.readouterr().err.strip() == "error: invalid_user"


def test_malformed_hash_option_is_refused(paths, capsys):
    assert run(paths, "users", "add", REPO, "alice", "--hash", "not-a-hash") == 1
    assert capsys.readouterr().err.strip() == "error: invalid_hash"


def test_explicit_hash_is_stored(paths, capsys):
    hash_ = new_hash()
    assert run(paths, "users", "add", REPO, "alice", "--hash", hash_) == 0
    assert stored(paths)["entries"][0]["hash"] == hash_
    assert capsys.readouterr().out.splitlines()[0].endswith("/" + hash_)


def test_unknown_keys_and_fields_survive_add(paths):
    doc = {
        "schema": 1,
        "future_key": {"keep": True},
        "entries": [
            {
                "repository": REPO,
                "user": "bob",
                "hash": new_hash(),
                "created": "2026-01-01T00:00:00Z",
                "source": "gui",
                "note": "kept",
            }
        ],
    }
    paths.access_file.write_text(json.dumps(doc), encoding="utf-8")
    assert run(paths, "users", "add", REPO, "alice") == 0
    after = stored(paths)
    assert after["future_key"] == {"keep": True}
    assert after["entries"][0] == doc["entries"][0]
    assert [e["user"] for e in after["entries"]] == ["bob", "alice"]


def test_newer_schema_is_refused_without_write(paths, capsys):
    doc = {"schema": 2, "entries": []}
    paths.access_file.write_text(json.dumps(doc), encoding="utf-8")
    assert run(paths, "users", "add", REPO, "alice") == 1
    assert capsys.readouterr().err.strip() == "error: schema_unsupported"
    assert stored(paths) == doc


def test_reconcile_prints_link_count(paths, capsys):
    assert run(paths, "users", "add", REPO, "alice") == 0
    assert run(paths, "users", "add", REPO, "bob") == 0
    capsys.readouterr()
    assert run(paths, "reconcile") == 0
    assert capsys.readouterr().out.strip() == "2 access links"


def test_unknown_subcommand_exits_2(paths, capsys):
    assert run(paths, "bogus") == 2
    capsys.readouterr()


def test_cli_output_never_reaches_logging(paths, capsys):
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    root = logging.getLogger()
    handler = Capture(level=logging.DEBUG)
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        assert run(paths, "users", "add", REPO, "alice") == 0
        assert run(paths, "reconcile") == 0
        assert run(paths, "users", "list") == 0
        assert run(paths, "users", "url", REPO, "alice") == 0
        assert run(paths, "users", "revoke", REPO, "alice") == 0
        assert run(paths, "sync") == 0
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    assert capsys.readouterr().out.startswith("internal: ")
    assert records == []


def add_user(p: Paths, user: str, capsys) -> str:
    assert run(p, "users", "add", REPO, user) == 0
    return URL_RE.match(capsys.readouterr().out.splitlines()[0]).group(1)


def test_add_with_hash_already_in_use_is_a_conflict(paths, capsys):
    hash_ = add_user(paths, "alice", capsys)
    assert run(paths, "users", "add", REPO, "bob", "--hash", hash_) == 1
    assert capsys.readouterr().err.strip() == "error: hash_conflict"


def test_add_of_reserved_label_is_refused(paths, capsys):
    assert run(paths, "users", "add", REPO, "local") == 1
    assert capsys.readouterr().err.strip() == "error: user_reserved"


def test_users_list_shows_masked_hashes_only(paths, capsys):
    alice = add_user(paths, "alice", capsys)
    bob = add_user(paths, "bob", capsys)
    assert run(paths, "users", "list") == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) == 2
    for line, user, hash_ in zip(lines, ("alice", "bob"), (alice, bob)):
        assert REPO in line and user in line and "cli" in line
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", line)
        assert hash_[:4] + "…" in line
    assert alice not in out and bob not in out
    assert "(inactive)" not in out


def test_users_list_marks_unconfigured_repositories_inactive_and_filters(paths, capsys):
    add_user(paths, "alice", capsys)
    AccessStore(paths).add("example-org/retired", "carol")
    assert run(paths, "users", "list") == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    retired = [line for line in lines if "carol" in line]
    assert retired and retired[0].endswith("(inactive)")
    assert run(paths, "users", "list", REPO.upper()) == 0
    filtered = capsys.readouterr().out.splitlines()
    assert len(filtered) == 1 and "alice" in filtered[0]


def test_users_url_prints_the_same_urls_as_add(paths, capsys):
    write_options(paths, public_url="https://addons.example.com")
    assert run(paths, "users", "add", REPO, "alice") == 0
    added = capsys.readouterr().out
    assert run(paths, "users", "url", REPO, "alice") == 0
    assert capsys.readouterr().out == added


def test_users_url_of_unknown_user_fails(paths, capsys):
    assert run(paths, "users", "url", REPO, "alice") == 1
    assert capsys.readouterr().err.strip() == "error: user_unknown"


def test_users_revoke_removes_entry_and_link(paths, capsys):
    alice = add_user(paths, "alice", capsys)
    bob = add_user(paths, "bob", capsys)
    assert run(paths, "users", "revoke", REPO, "alice") == 0
    assert capsys.readouterr().out.strip() == f"revoked alice from {REPO}"
    assert not os.path.lexists(paths.link_path("example-org", "private-addons", alice))
    assert paths.link_path("example-org", "private-addons", bob).is_symlink()
    assert [e["user"] for e in stored(paths)["entries"]] == ["bob"]
    assert run(paths, "users", "revoke", REPO, "alice") == 1
    assert capsys.readouterr().err.strip() == "error: user_unknown"


def test_users_revoke_works_for_unconfigured_repository(paths, capsys):
    AccessStore(paths).add("example-org/retired", "carol")
    assert run(paths, "users", "revoke", "example-org/retired", "carol") == 0
    assert capsys.readouterr().out.strip() == "revoked carol from example-org/retired"
    assert stored(paths)["entries"] == []


def test_revoke_label_starting_with_dash_is_unknown_not_usage(paths, capsys):
    assert run(paths, "users", "revoke", REPO, "-x") == 1
    assert capsys.readouterr().err.strip() == "error: user_unknown"


def test_sync_writes_the_trigger_file(paths, capsys):
    assert run(paths, "sync") == 0
    assert capsys.readouterr().out.strip() == "sync requested"
    assert paths.trigger_file.exists()
    assert paths.trigger_file.stat().st_mode & 0o777 == 0o600
    assert paths.run_dir.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "argv",
    [
        ("users", "list"),
        ("users", "add", REPO, "bob"),
        ("users", "url", REPO, "alice"),
        ("users", "revoke", REPO, "alice"),
    ],
)
def test_newer_schema_is_refused_by_every_users_command(paths, capsys, argv):
    doc = {"schema": 2, "entries": [{"repository": REPO, "user": "alice", "hash": new_hash()}]}
    paths.access_file.write_text(json.dumps(doc), encoding="utf-8")
    before = paths.access_file.read_bytes()
    assert run(paths, *argv) == 1
    assert capsys.readouterr().err.strip() == "error: schema_unsupported"
    assert paths.access_file.read_bytes() == before


def test_help_explains_secret_urls_and_rotation(paths, capsys):
    assert run(paths, "--help") == 0
    out = capsys.readouterr().out
    assert "secret" in out and "revoke" in out and "rotat" in out


# --- reserved labels and `mrp local status` (Phase 2) --------------------------------------------------------------

HEX32_RE = re.compile(r"[0-9a-fA-F]{32}")


@pytest.mark.parametrize("user", ["local", "local.0a1b2c3d", "LOCAL"])
def test_users_revoke_of_reserved_label_is_refused(paths, capsys, user):
    created = AccessStore(paths).add(REPO, user, source="system")
    before = paths.access_file.read_bytes()
    assert run(paths, "users", "revoke", REPO, user) == 1
    assert capsys.readouterr().err.strip() == "error: user_reserved"
    assert paths.access_file.read_bytes() == before
    assert AccessStore(paths).get(REPO, user)["hash"] == created["hash"]


def test_users_add_of_reserved_dot_label_is_refused(paths, capsys):
    assert run(paths, "users", "add", REPO, "local.x") == 1
    assert capsys.readouterr().err.strip() == "error: user_reserved"
    assert not paths.access_file.exists()


def test_help_names_the_reserved_labels(paths, capsys):
    assert run(paths, "--help") == 0
    out = capsys.readouterr().out
    assert "local.*" in out and "mrp local status" in out and "mrp local remove" in out


def seed_state(p: Paths, **overrides) -> dict:
    doc = {
        "schema": 1,
        "updated": "2026-11-18T12:00:00Z",
        "register_local": True,
        "hostname": HOST,
        "supervisor": {"last_contact": None, "last_status": None, "last_error": None},
        "reload": {"last_requested": "2026-11-18T11:00:00Z", "last_result": "ok", "pending": False, "message": ""},
        "repositories": [
            {
                "repository": REPO,
                "registration": "leftover",
                "message": "1 old store repository left (in_use); see mrp local status",
                "configured": True,
                "in_store": True,
                "store_slug": "0a1b2c3d",
                "masked_url": f"http://{HOST}:8080/repo/{REPO}/3f9c…",
            },
            {
                "repository": "example-org/retired",
                "registration": "leftover",
                "configured": False,
                "in_store": True,
                "store_slug": "4e5f6a7b",
                "masked_url": f"http://{HOST}:8080/repo/example-org/retired/9a8b…",
            },
            {
                "repository": "example-org/fresh",
                "registration": "missing",
                "configured": True,
                "in_store": False,
                "store_slug": None,
                "masked_url": "",
            },
        ],
        "leftovers": [
            {
                "repository": REPO,
                "store_slug": "11223344",
                "user": "local",
                "masked_url": f"http://{HOST}:8080/repo/{REPO}/aa11…",
                "since": "2026-11-18T10:00:00Z",
                "reason": "in_use",
                "message": "masked",
                "revoked": False,
            },
            {
                "repository": "example-org/retired",
                "store_slug": "55667788",
                "user": None,
                "masked_url": "",
                "since": "2026-11-18T09:00:00Z",
                "reason": "orphaned",
                "message": "",
                "revoked": False,
            },
        ],
        "requests": [],
    }
    doc.update(overrides)
    p.supervisor_state_file.write_text(json.dumps(doc), encoding="utf-8")
    return doc


def test_local_status_without_state_file(paths, capsys):
    assert run(paths, "local", "status") == 0
    assert capsys.readouterr().out.strip() == "no registration state yet"


def test_local_status_prints_registration_reload_and_leftovers(paths, capsys):
    seed_state(paths)
    assert run(paths, "local", "status") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"{REPO}\tleftover\t0a1b2c3d\thttp://{HOST}:8080/repo/{REPO}/3f9c…"
    assert lines[1] == (
        f"example-org/retired\tleftover\t4e5f6a7b\thttp://{HOST}:8080/repo/example-org/retired/9a8b…\t(unconfigured)"
    )
    assert lines[2] == "example-org/fresh\tmissing\t-\t-"
    assert lines[3] == "reload: last 2026-11-18T11:00:00Z ok, pending no"
    assert lines[4] == f"leftover\t{REPO}\t11223344\tin_use\tlocal\t2026-11-18T10:00:00Z"
    assert lines[5] == "leftover\texample-org/retired\t55667788\torphaned\t-\t2026-11-18T09:00:00Z"
    assert len(lines) == 6


def test_local_status_filters_by_repository(paths, capsys):
    seed_state(paths, reload={"last_requested": None, "last_result": None, "pending": True, "message": ""})
    assert run(paths, "local", "status", REPO.upper()) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(f"{REPO}\tleftover\t")
    assert lines[1] == "reload: last never -, pending yes"
    assert lines[2].startswith(f"leftover\t{REPO}\t")
    assert len(lines) == 3


def test_local_status_rejects_a_malformed_repository(paths, capsys):
    seed_state(paths)
    assert run(paths, "local", "status", "not-a-repository") == 1
    assert capsys.readouterr().err.strip() == "error: repository_unknown"


def test_local_status_never_prints_a_hash_and_never_logs(paths, capsys):
    seed_state(paths)
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    root = logging.getLogger()
    handler = Capture(level=logging.DEBUG)
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        assert run(paths, "local", "status") == 0
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    out = capsys.readouterr().out
    assert out and not HEX32_RE.search(out)
    assert records == []


def test_local_status_masks_a_hash_planted_in_the_state_file(paths, capsys):
    planted = new_hash()
    doc = seed_state(paths)
    doc["repositories"][0]["masked_url"] = f"http://{HOST}:8080/repo/{REPO}/{planted}"
    doc["leftovers"][0]["user"] = planted
    paths.supervisor_state_file.write_text(json.dumps(doc), encoding="utf-8")
    assert run(paths, "local", "status") == 0
    out = capsys.readouterr().out
    assert planted not in out and not HEX32_RE.search(out)
