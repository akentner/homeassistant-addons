from __future__ import annotations

import json

import pytest

from app.engine.config import load_config, load_provider, ProviderLoadError
from app.engine.guard import check_shrink
from app.engine.merge import MergeError, merge
from app.providers.base import Snapshot


def snap(**secrets):
    return Snapshot(secrets=dict(secrets))


def test_union():
    out = merge([("bitwarden", snap(a="1")), ("sops", snap(b="2"))], "error")
    assert out.secrets == {"a": "1", "b": "2"}


def test_collision_error_names_both_sources_not_values():
    with pytest.raises(MergeError) as exc:
        merge([("bitwarden", snap(a="value-1")), ("sops", snap(a="value-2"))], "error")
    assert exc.value.code == "key_collision"
    assert "bitwarden" in str(exc.value) and "sops" in str(exc.value) and "value" not in str(exc.value)


def test_collision_priority_first_wins():
    out = merge([("bitwarden", snap(a="1")), ("sops", snap(a="2"))], "priority")
    assert out.secrets == {"a": "1"}
    assert out.shadowed == [("a", "bitwarden", "sops")]


def test_file_collision_and_unsafe_path():
    a = Snapshot(files={"x.txt": b"1"})
    b = Snapshot(files={"x.txt": b"2"})
    with pytest.raises(MergeError) as exc:
        merge([("p1", a), ("p2", b)], "error")
    assert exc.value.code == "key_collision"
    with pytest.raises(MergeError) as exc:
        merge([("p1", Snapshot(files={"../x": b"1"}))], "error")
    assert exc.value.code == "unsafe_path"


def test_guard():
    assert check_shrink(0, 10, 50) == "shrink_guard"
    assert check_shrink(0, None, 50) == "shrink_guard"
    assert check_shrink(5, 10, 50) is None
    assert check_shrink(4, 10, 50) == "shrink_guard"
    assert check_shrink(4, 10, 50, force=True) is None
    assert check_shrink(0, 10, 50, force=True) == "shrink_guard"
    assert check_shrink(1, None, 50) is None


def _env(tmp_path, options):
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps(options))
    return {"SS_OPTIONS": str(opts), "SS_STATE_FILE": str(tmp_path / "state.json")}


def test_config_defaults_and_paths(tmp_path):
    cfg = load_config(_env(tmp_path, {"providers": ["bitwarden", "sops", "bitwarden"], "interval": 120,
                                      "bitwarden": {"server_url": "https://x"}}))
    assert cfg.providers == ("bitwarden", "sops")
    assert cfg.interval == 120 and cfg.collision_policy == "error" and cfg.shrink_guard_percent == 30
    assert cfg.provider_cfg["bitwarden"]["server_url"] == "https://x"
    assert cfg.provider_cfg["sops"] == {}
    assert cfg.problems == ()
    assert str(cfg.secrets_file) == "/config/secrets.yaml" and cfg.port == 8099


def test_config_problems(tmp_path):
    cfg = load_config(_env(tmp_path, {"providers": ["nope"], "interval": 5, "collision_policy": "x"}))
    codes = [p.code for p in cfg.problems]
    assert codes.count("config_invalid") == 3 and "no_providers" in codes
    assert cfg.interval == 300


def test_config_missing_options(tmp_path):
    cfg = load_config({"SS_OPTIONS": str(tmp_path / "missing.json")})
    assert any(p.code == "config_invalid" for p in cfg.problems)


def test_load_provider_unknown():
    with pytest.raises(ProviderLoadError):
        load_provider("nope", {})
