"""status.sh runner: whitelist, coercions, failure modes, spawn safety, minimal environment and the real-script contract."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from app.status import NUMBER_FIELDS, TEXT_FIELDS, StatusError, read_status
from conftest import FIXTURE_FP, FIXTURE_TYPE, REAL_STATUS_SH, write_log

ENV = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LOGDIR": "/nonexistent", "HOSTS_FILE": "/x", "ENV_FILE": "/y"}

FULL: dict[str, Any] = {name: 1 for name in NUMBER_FIELDS} | {
    "reasons": "stale,kmsg",
    "dstate_tasks": "12 jbd2:wait",
    "kmsg_last": "EXT4-fs error",
    "key_fp": FIXTURE_FP,
    "key_type": FIXTURE_TYPE,
}


def stub(tmp_path: Path, body: str, name: str = "stub.sh") -> Path:
    path = tmp_path / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def printing(tmp_path: Path, payload: Any) -> Path:
    data = tmp_path / "out.json"
    data.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return stub(tmp_path, f"cat '{data}'")


def test_whitelist_sizes() -> None:
    assert len(NUMBER_FIELDS) == 22 and len(TEXT_FIELDS) == 5
    assert len(set(NUMBER_FIELDS) | set(TEXT_FIELDS)) == 27


def test_full_object_yields_exactly_the_whitelist(tmp_path: Path) -> None:
    out = read_status("a", status_sh=printing(tmp_path, FULL | {"extra": 1, "ssh_private_key": "x"}), env=ENV)
    assert set(out) == set(NUMBER_FIELDS) | set(TEXT_FIELDS)
    assert out["reasons"] == "stale,kmsg" and out["key_fp"] == FIXTURE_FP


def test_missing_fields_get_defaults(tmp_path: Path) -> None:
    out = read_status("a", status_sh=printing(tmp_path, {}), env=ENV)
    assert all(out[name] == -1 for name in NUMBER_FIELDS)
    assert all(out[name] == "" for name in TEXT_FIELDS)


@pytest.mark.parametrize("bad", [True, False, "5", None, [1], {"a": 1}, "NaN"])
def test_non_numbers_become_minus_one(tmp_path: Path, bad: Any) -> None:
    out = read_status("a", status_sh=printing(tmp_path, FULL | {"age": bad, "load1": bad}), env=ENV)
    assert out["age"] == -1 and out["load1"] == -1


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_constants_are_rejected_outright(tmp_path: Path, raw: str) -> None:
    with pytest.raises(StatusError):
        read_status("a", status_sh=printing(tmp_path, '{"age": ' + raw + "}"), env=ENV)


def test_huge_float_becomes_minus_one(tmp_path: Path) -> None:
    out = read_status("a", status_sh=printing(tmp_path, '{"age": 1e999, "load1": 0.5}'), env=ENV)
    assert out["age"] == -1 and out["load1"] == 0.5


def test_text_is_sanitised_and_capped(tmp_path: Path) -> None:
    payload = FULL | {
        "reasons": "a\x00b\x1bc" + "r" * 300,
        "dstate_tasks": "t" * 5000,
        "kmsg_last": "k" * 500,
        "key_type": 5,
    }
    out = read_status("a", status_sh=printing(tmp_path, payload), env=ENV)
    assert out["reasons"].startswith("abc") and len(out["reasons"]) == 128
    assert len(out["dstate_tasks"]) == 4000 and len(out["kmsg_last"]) == 200
    assert out["key_type"] == ""


@pytest.mark.parametrize("fp", ["SHA256:ab cd", "SHA256:<b>", "x" * 129, "SHA256:ä", "a\nb"])
def test_bad_fingerprint_is_dropped(tmp_path: Path, fp: str) -> None:
    out = read_status("a", status_sh=printing(tmp_path, FULL | {"key_fp": fp}), env=ENV)
    assert out["key_fp"] == ""


@pytest.mark.parametrize("kind", ["ED 25519", "a" * 33, "<i>", "x\n"])
def test_bad_key_type_is_dropped(tmp_path: Path, kind: str) -> None:
    out = read_status("a", status_sh=printing(tmp_path, FULL | {"key_type": kind}), env=ENV)
    assert out["key_type"] == ""


def test_invalid_marker_and_boundary_lengths_pass(tmp_path: Path) -> None:
    out = read_status("a", status_sh=printing(tmp_path, FULL | {"key_fp": "invalid", "key_type": "t" * 32}), env=ENV)
    assert out["key_fp"] == "invalid" and out["key_type"] == "t" * 32


def test_nonzero_exit_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(StatusError):
        read_status("a", status_sh=stub(tmp_path, "echo '{}'; exit 3"), env=ENV)


@pytest.mark.parametrize("payload", ["", "   \n", "not json", "[1, 2]", "42", '"s"', "null", '{"a":'])
def test_unusable_output_is_an_error(tmp_path: Path, payload: str) -> None:
    with pytest.raises(StatusError):
        read_status("a", status_sh=printing(tmp_path, payload), env=ENV)


def test_oversized_output_is_an_error(tmp_path: Path) -> None:
    big = '{"reasons": "' + "x" * 70000 + '"}'
    with pytest.raises(StatusError):
        read_status("a", status_sh=printing(tmp_path, big), env=ENV)


def test_endless_output_is_cut_off_early(tmp_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(StatusError):
        read_status("a", status_sh=stub(tmp_path, "yes"), env=ENV, timeout=5)
    assert time.monotonic() - started < 4


def test_non_utf8_output_is_an_error(tmp_path: Path) -> None:
    data = tmp_path / "raw"
    data.write_bytes(b'{"reasons": "\xff\xfe"}')
    with pytest.raises(StatusError):
        read_status("a", status_sh=stub(tmp_path, f"cat '{data}'"), env=ENV)


def test_timeout_kills_the_script_promptly(tmp_path: Path) -> None:
    marker = tmp_path / "survived"
    script = stub(tmp_path, f"sleep 5; touch '{marker}'; echo '{{}}'")
    started = time.monotonic()
    with pytest.raises(StatusError):
        read_status("a", status_sh=script, env=ENV, timeout=0.3)
    assert time.monotonic() - started < 3
    time.sleep(0.2)
    assert not marker.exists()


def test_missing_script_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(StatusError):
        read_status("a", status_sh=tmp_path / "nope.sh", env=ENV)


@pytest.mark.parametrize("slug", ["A", "a b", "a;id", "../x", "", "a\n", "a" * 129, "a$(id)"])
def test_invalid_slug_never_spawns(tmp_path: Path, slug: str) -> None:
    marker = tmp_path / "spawned"
    script = stub(tmp_path, f"touch '{marker}'; echo '{{}}'")
    with pytest.raises(ValueError):
        read_status(slug, status_sh=script, env=ENV)
    assert not marker.exists()


def test_slug_is_exactly_one_argv_entry(tmp_path: Path) -> None:
    argv = tmp_path / "argv"
    script = stub(tmp_path, f'printf "%s|" "$#" "$1" > \'{argv}\'; echo \'{{}}\'')
    read_status("ha_backup", status_sh=script, env=ENV)
    assert argv.read_text() == "1|ha_backup|"


def test_environment_is_minimal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "sentinel-token-value")
    dump = tmp_path / "env.json"
    script = tmp_path / "dump.py"
    script.write_text(
        f"#!{sys.executable}\nimport json, os\nopen({str(dump)!r}, 'w').write(json.dumps(dict(os.environ)))\nprint('{{}}')\n"
    )
    script.chmod(0o755)
    read_status("a", status_sh=script, env=ENV)
    seen = json.loads(dump.read_text())
    assert "SUPERVISOR_TOKEN" not in seen and "sentinel-token-value" not in json.dumps(seen)
    assert {"PATH", "LOGDIR", "HOSTS_FILE", "ENV_FILE"} <= set(seen)
    # only what the interpreter itself adds (locale coercion) may appear besides the four names
    assert set(seen) - set(ENV) <= {"LC_CTYPE", "LANG"}


needs_tools = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("sh", "awk", "date")), reason="sh, awk and date are required"
)


def real_env(env: dict[str, Path]) -> dict[str, str]:
    return {
        "PATH": os.environ["PATH"],
        "LOGDIR": str(env["logdir"]),
        "HOSTS_FILE": str(env["hosts_file"]),
        "ENV_FILE": str(env["env_file"]),
    }


@needs_tools
def test_contract_with_the_real_status_sh(env: dict[str, Path]) -> None:
    import subprocess

    raw = subprocess.run(
        [str(REAL_STATUS_SH), "ha_backup"], env=real_env(env), capture_output=True, check=True, text=True
    ).stdout
    assert set(json.loads(raw)) == set(NUMBER_FIELDS) | set(TEXT_FIELDS)
    out = read_status("ha_backup", status_sh=REAL_STATUS_SH, env=real_env(env))
    assert out["key_fp"] == FIXTURE_FP and out["key_type"] == FIXTURE_TYPE
    assert out["problem"] == 0 and 0 <= out["age"] < 60
    assert out["ping"] == 1 and out["p22222"] == 1 and out["p4357"] == 1
    assert out["load1"] == 0.5 and out["io_some10"] == 1.5 and out["up"] == 5000.5


@needs_tools
def test_contract_stale_log_flags_a_problem(env: dict[str, Path]) -> None:
    write_log(env["logdir"], "ha_backup", age=600)
    out = read_status("ha_backup", status_sh=REAL_STATUS_SH, env=real_env(env))
    assert out["r_age"] == 1 and out["problem"] == 1
    assert "stale" in out["reasons"]
