"""Tests for app.contract: mapping helpers, validators, options, route table and the DB fixture builder."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
import yaml

from app import contract as c
from helpers.ntfy_db import make_auth_db

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_topic_mapping_round_trip() -> None:
    assert c.cli_topic_to_db("a_b*") == "a\\_b%"
    assert c.db_topic_to_cli("a\\_b%") == "a_b*"
    assert c.cli_topic_to_db("up*") == "up%"
    for topic in ("up*", "*", "a_b*", "plain", "x_y_z"):
        assert c.db_topic_to_cli(c.cli_topic_to_db(topic)) == topic
    assert c.db_topic_to_cli("%") == "*"


def test_perm_flags_are_inverse() -> None:
    for perm in c.PERMISSIONS:
        assert c.perm_from_flags(*c.flags_from_perm(perm)) == perm
    assert c.perm_from_flags(1, 0) == "ro"


def test_topic_match_semantics() -> None:
    assert c.topic_match("pub*", "pub1")
    assert not c.topic_match("pub*", "PUB1")
    assert not c.topic_match("a_b*", "aXbz")
    assert c.topic_match("a_b*", "a_bz")
    assert c.topic_match("*", "anything")
    assert not c.topic_match("x", "xy")
    assert c.topic_match("x", "x")


def test_token_helpers() -> None:
    first, second = c.token_id("tk_" + "a" * 29), c.token_id("tk_" + "b" * 29)
    assert len(first) == 12 and int(first, 16) >= 0
    assert first == c.token_id("tk_" + "a" * 29)
    assert first != second
    assert c.token_prefix("tk_abcdefghij") == "tk_abcd"


def test_validators() -> None:
    for good in ("alice", "a.b@c", "_x", "a" * 64):
        assert c.USERNAME_RE.match(good)
    for bad in ("-x", "bad name", "a/b", "a" * 65, "%", ""):
        assert not c.USERNAME_RE.match(bad)
    assert c.TOPIC_PATTERN_RE.match("pre*") and not c.TOPIC_RE.match("pre*")
    assert c.TOPIC_RE.match("homeassistant")
    assert not c.TOPIC_PATTERN_RE.match("%")
    assert c.TOKEN_RE.match("tk_" + "a" * 29) and not c.TOKEN_RE.match("tk_short")
    assert c.DURATION_RE.match("12h") and not c.DURATION_RE.match("1w")
    assert c.BACKUP_NAME_RE.match("auth-20261101T120000Z.db")
    assert c.BACKUP_NAME_RE.match("auth-20261101T120000Z-daily.db")
    assert not c.BACKUP_NAME_RE.match("../auth-20261101T120000Z.db")


def test_options_baseline_overwrite_passwords() -> None:
    assert c.parse_options({}).baseline_overwrite_passwords is False
    assert c.parse_options({"baseline_overwrite_passwords": True}).baseline_overwrite_passwords is True
    with pytest.raises(c.OptionsError):
        c.parse_options({"baseline_overwrite_passwords": "true"})


def test_load_options_ignores_unknown_and_missing(tmp_path: Path) -> None:
    path = tmp_path / "options.json"
    assert c.load_options(path).admin_user == "admin"
    path.write_text(json.dumps({"admin_user": "root", "listen_port": 9, "baseline_users": [
        {"username": "u", "password": "p", "topic": "t", "write_access": True}]}))
    options = c.load_options(path)
    assert options.admin_user == "root"
    assert options.baseline_users[0].write_access is True
    path.write_text("[]")
    with pytest.raises(c.OptionsError):
        c.load_options(path)


def test_option_keys_and_defaults_match_config_yaml() -> None:
    config = yaml.safe_load(CONFIG.read_text())
    assert set(config["options"]) == set(c.OPTION_KEYS)
    assert set(config["schema"]) == set(c.OPTION_KEYS)
    parsed = c.parse_options({})
    for key, value in config["options"].items():
        actual = getattr(parsed, key)
        assert (list(actual) if isinstance(actual, tuple) else actual) == value, key


def test_routes_table() -> None:
    keys = [(r.method, r.pattern) for r in c.ROUTES]
    assert len(keys) == len(set(keys)) == 23
    assert {r.owner for r in c.ROUTES} <= {"24-01", "24-06", "24-07", "24-08"}


def test_api_error_status_and_unknown_code() -> None:
    assert c.ApiError("protected", "x").status == 409
    with pytest.raises(ValueError):
        c.ApiError("nope")


def test_api_error_from_cli_covers_all_codes() -> None:
    expected = {"exists": "conflict", "not_found": "not_found", "invalid": "bad_request", "provisioned": "protected",
                "locked": "locked", "other": "ntfy_error"}
    for code, api_code in expected.items():
        error = c.api_error_from_cli(code, "m")
        assert error.code == api_code and error.message == "m"


def test_token_meta_from_row() -> None:
    row: c.TokenRow = {"user": "u", "token_id": "abc", "prefix": "tk_abcd", "label": "l", "expires": 0,
                       "last_access": 5, "last_origin": "1.2.3.4", "provisioned": False}
    meta = c.token_meta_from_row(row, "gui")
    assert meta["expires_at"] is None and "value" not in meta
    assert set(meta) == {"id", "user", "prefix", "label", "expires", "expires_at", "last_access", "last_origin",
                         "origin"}
    future = int(time.time()) + 3600
    row["expires"] = future
    assert c.token_meta_from_row(row, "gui")["expires_at"].endswith("Z")


def test_ntfy_db_fixture_schema_version(tmp_path: Path) -> None:
    path = make_auth_db(tmp_path / "auth.db")
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT id, version, min_version FROM schemaVersion").fetchone()
        anon = conn.execute("SELECT id, user, role, provisioned FROM user").fetchone()
    finally:
        conn.close()
    assert "|".join(map(str, row)) == "1|10|1"
    assert anon == ("u_everyone", "*", "anonymous", 0)
