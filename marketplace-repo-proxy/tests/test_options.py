"""Options contract (app.options, MRP-01, D-12, D-16): values become paths and refspecs, so validation is strict."""

from __future__ import annotations

import json

import pytest

from app.options import (
    DEFAULT_INTERVAL,
    MIN_INTERVAL,
    Options,
    OptionsError,
    RepoSpec,
    _valid_branch,
    load_options,
    parse_options,
    parse_repository,
)

TOKEN = "SENTINEL-" + "PAT-" + "0001"


def repos(*items) -> Options:
    return parse_options({"github_token": TOKEN, "repositories": list(items)})


def test_full_valid_document_parses():
    options = parse_options(
        {
            "github_token": TOKEN,
            "sync_interval": 30,
            "public_url": "https://addons.example.invalid",
            "repositories": [
                {"repository": "example-org/private-addons"},
                {"repository": "example-org/other_addons.v2", "branch": "release/stable"},
            ],
            "register_local": False,
            "api_enabled": True,
            "log_level": "debug",
        }
    )
    assert options == Options(
        github_token=TOKEN,
        sync_interval=30,
        public_url="https://addons.example.invalid",
        repositories=(
            RepoSpec("example-org", "private-addons", None),
            RepoSpec("example-org", "other_addons.v2", "release/stable"),
        ),
        register_local=False,
        api_enabled=True,
        log_level="debug",
        rejected=(),
    )
    assert options.find("Example-Org/Private-Addons") == options.repositories[0]


@pytest.mark.parametrize(
    "value",
    [
        "owner/..",
        "owner/.",
        "own er/x",
        "-owner/x",
        "o" * 40 + "/x",
        "owner/repo.git",
        "owner/Repo.GIT",
        "ownerrepo",
        "owner/x/y",
        "owner/",
        "/x",
        "evil\n/repo",
    ],
)
def test_invalid_repository_is_rejected(value):
    with pytest.raises(ValueError):
        parse_repository(value)
    options = repos({"repository": value}, {"repository": "example-org/kept"})
    assert options.repositories == (RepoSpec("example-org", "kept"),)
    assert len(options.rejected) == 1


def test_longest_valid_owner_is_accepted():
    assert parse_repository("o" * 39 + "/x") == ("o" * 39, "x")


def test_case_insensitive_duplicate_is_rejected():
    options = repos({"repository": "Example-Org/Addons"}, {"repository": "example-org/addons"})
    assert options.repositories == (RepoSpec("Example-Org", "Addons"),)
    assert options.rejected == ("example-org/addons: duplicate repository",)


@pytest.mark.parametrize("branch", ["../x", "-x", "a b", "x.lock", "x/", "/x", "a//b", "a..b"])
def test_unsafe_branch_skips_the_whole_entry(branch):
    options = repos({"repository": "example-org/addons", "branch": branch})
    assert options.repositories == ()
    assert options.rejected == ("example-org/addons: invalid branch",)


def test_validators_reject_a_trailing_newline():
    # `$` also matches before a final newline; every validator must match the whole string
    assert _valid_branch("main") is True
    assert _valid_branch("main\n") is False


@pytest.mark.parametrize("branch", [None, "", "   "])
def test_empty_branch_means_upstream_default(branch):
    options = repos({"repository": "example-org/addons", "branch": branch})
    assert options.repositories == (RepoSpec("example-org", "addons", None),)


def test_non_list_repositories_give_none():
    assert parse_options({"repositories": "example-org/addons"}).repositories == ()


@pytest.mark.parametrize(
    "value, expected",
    [(3, MIN_INTERVAL), (5, 5), (60, 60), ("x", DEFAULT_INTERVAL), (True, DEFAULT_INTERVAL), (None, DEFAULT_INTERVAL)],
)
def test_sync_interval_is_clamped_and_defaulted(value, expected):
    assert parse_options({"sync_interval": value}).sync_interval == expected


def test_sync_interval_defaults_to_15():
    assert DEFAULT_INTERVAL == 15 and MIN_INTERVAL == 5
    assert parse_options({}).sync_interval == 15


@pytest.mark.parametrize(
    "value, expected, rejected",
    [
        (None, "", False),
        ("", "", False),
        ("https://h.example/", "https://h.example", False),
        ("http://h.example:8443/base/", "http://h.example:8443/base", False),
        ("ftp://h.example", "", True),
        ("h.example", "", True),
        ("https://", "", True),
        (42, "", True),
    ],
)
def test_public_url_is_normalised_or_rejected(value, expected, rejected):
    data = {} if value is None else {"public_url": value}
    options = parse_options(data)
    assert options.public_url == expected
    assert options.rejected == (("public_url: must be an http(s) URL with a host",) if rejected else ())


def test_unknown_log_level_falls_back_to_info():
    assert parse_options({"log_level": "trace"}).log_level == "info"
    assert parse_options({}).log_level == "info"


def test_non_bool_flags_keep_defaults():
    options = parse_options({"register_local": "no", "api_enabled": 1})
    assert options.register_local is True and options.api_enabled is False


def test_token_never_in_repr_or_rejected_messages():
    options = parse_options(
        {
            "github_token": TOKEN,
            "public_url": "ftp://h.example",
            "repositories": [
                {"repository": "example-org/.."},
                {"repository": "example-org/addons", "branch": "../x"},
                {"repository": 7},
                "example-org/plain-string",
            ],
        }
    )
    assert options.github_token == TOKEN
    assert TOKEN not in repr(options)
    assert len(options.rejected) == 5
    assert all(TOKEN not in message for message in options.rejected)


def test_non_string_token_becomes_empty():
    assert parse_options({"github_token": 1234}).github_token == ""


def test_load_options_missing_file_gives_defaults(tmp_path):
    assert load_options(tmp_path / "options.json") == Options()


def test_load_options_invalid_json_hides_the_content(tmp_path):
    path = tmp_path / "options.json"
    path.write_text('{"github_token": "' + TOKEN + '", ', encoding="utf-8")
    with pytest.raises(OptionsError) as info:
        load_options(path)
    assert TOKEN not in str(info.value)
    assert "github_token" not in str(info.value)


def test_load_options_json_list_is_refused(tmp_path):
    path = tmp_path / "options.json"
    path.write_text(json.dumps([{"github_token": TOKEN}]), encoding="utf-8")
    with pytest.raises(OptionsError) as info:
        load_options(path)
    assert TOKEN not in str(info.value)


def test_load_options_reads_a_valid_file(tmp_path):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"repositories": [{"repository": "example-org/addons"}]}), encoding="utf-8")
    assert load_options(path).repositories == (RepoSpec("example-org", "addons"),)
