"""`mrp` CLI: users add and reconcile (app.cli)."""

from __future__ import annotations

import json
import logging
import os
import re

import pytest

from app import cli
from app.access import HASH_RE, new_hash
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
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    assert capsys.readouterr().out.startswith("internal: ")
    assert records == []
