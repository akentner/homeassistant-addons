"""config.yaml sops options: schema, defaults and the code that reads them must not drift apart."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from app.providers import gitsource
from app.providers.sops import Provider

ADDON = Path(__file__).resolve().parents[2]
CONFIG = yaml.safe_load((ADDON / "config.yaml").read_text())
SOPS_OPTIONS = CONFIG["options"]["sops"]
SOPS_SCHEMA = CONFIG["schema"]["sops"]


def test_unset_git_options_are_absent_from_defaults():
    # The Supervisor validates "str?" options only when present; "" would be written into options.json
    assert set(SOPS_OPTIONS) == {"source", "file", "flatten_separator"}


def test_every_default_has_a_schema_entry_and_every_extra_is_optional():
    assert set(SOPS_OPTIONS) <= set(SOPS_SCHEMA)
    for key in set(SOPS_SCHEMA) - set(SOPS_OPTIONS):
        assert SOPS_SCHEMA[key].endswith("?"), f"{key} is not a default, so its schema must be optional"


def test_schema_declares_source_as_file_or_git():
    assert SOPS_SCHEMA["source"] == "list(file|git)?"


def _keys_read_by_code() -> set[str]:
    sops_py = (ADDON / "app" / "providers" / "sops.py").read_text()
    run_sh = (ADDON / "run.sh").read_text()
    from_provider = set(re.findall(r'block\.get\("(\w+)"\)', sops_py))
    from_run_sh = set(re.findall(r'\(\s*"[A-Z_]+",\s*sops,\s*"(\w+)"\s*\)', run_sh))
    return from_provider | from_run_sh


def test_schema_keys_match_keys_read_by_provider_and_run_sh():
    read = _keys_read_by_code()
    assert read, "key extraction found nothing; the regexes need updating"
    assert set(SOPS_SCHEMA) == read


def test_defaults_without_git_options_validate_for_file_source():
    assert Provider({"sops": dict(SOPS_OPTIONS)}).validate() == []


def test_defaults_without_git_options_report_missing_url_for_git_source():
    block = dict(SOPS_OPTIONS, source="git")
    assert [p.code for p in Provider({"sops": block}).validate()] == ["sops_git_missing_url"]


def test_git_source_applies_branch_and_path_defaults_when_unset():
    block = dict(SOPS_OPTIONS, source="git", git_url="https://example.com/org/repo.git")
    prov = Provider({"sops": block})
    assert prov.validate() == []
    git = prov._git()
    assert (git.branch, git.path, git.username) == ("main", "secrets.sops.yaml", "")


def test_git_username_falls_back_to_x_access_token(monkeypatch):
    monkeypatch.setenv("SS_GIT_TOKEN", "tok")
    git = gitsource.GitSource("https://example.com/org/repo.git", "main", "secrets.sops.yaml", "")
    assert git._env()["SS_GIT_USERNAME"] == "x-access-token"
    named = gitsource.GitSource("https://example.com/org/repo.git", "main", "secrets.sops.yaml", "bot")
    assert named._env()["SS_GIT_USERNAME"] == "bot"


def test_askpass_defaults_username_when_env_has_none():
    askpass = Path(gitsource.ASKPASS)
    env = {"PATH": os.environ["PATH"], "SS_GIT_TOKEN": "tok"}

    def ask(prompt: str) -> str:
        res = subprocess.run([str(askpass), prompt], env=env, capture_output=True, text=True, check=True)
        return res.stdout.strip()

    assert ask("Username for 'https://x': ") == "x-access-token"
    assert ask("Password for 'https://x': ") == "tok"


@pytest.mark.parametrize("key", ["git_username", "git_token"])
def test_run_sh_exports_only_set_values(key):
    # run.sh only exports truthy values, so unset options never produce empty SS_GIT_* variables
    assert f'"{key}"' in (ADDON / "run.sh").read_text()
    assert "if src.get(key):" in (ADDON / "run.sh").read_text()
