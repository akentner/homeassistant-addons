from __future__ import annotations

import os
from pathlib import Path

from app.engine import usage


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_finds_refs_with_file_and_line_and_ignores_comments(tmp_path):
    write(tmp_path / "secrets.yaml", "a: x\n")
    write(tmp_path / "packages" / "m.yaml", "pw: !secret a\n# !secret nope\nu: !secret b  # !secret c\n")
    res = usage.scan([("config", tmp_path)])
    assert res.refs == {"a": [("packages/m.yaml", 1)], "b": [("packages/m.yaml", 3)]}
    assert res.counts == {"a": 1, "b": 1} and res.files_scanned == 1


def test_references_to_a_nested_secrets_file_do_not_count(tmp_path):
    write(tmp_path / "secrets.yaml", "a: x\n")
    write(tmp_path / "esphome" / "secrets.yaml", "wifi: y\n")
    write(tmp_path / "esphome" / "node.yaml", "ssid: !secret wifi\n")
    write(tmp_path / "configuration.yaml", "pw: !secret a\n")
    assert set(usage.scan([("config", tmp_path)]).refs) == {"a"}


def test_works_without_own_secrets_file(tmp_path):
    write(tmp_path / "configuration.yaml", "pw: !secret a\n")
    assert set(usage.scan([("config", tmp_path)]).refs) == {"a"}


def test_skips_hidden_dirs_symlinks_and_oversized_files(tmp_path):
    write(tmp_path / ".storage" / "x.yaml", "k: !secret hidden\n")
    write(tmp_path / "custom_components" / "c.yaml", "k: !secret cc\n")
    write(tmp_path / "big.yaml", "k: !secret big\n" + "#" * (usage.MAX_FILE_BYTES + 1))
    write(tmp_path / "real.yaml", "k: !secret real\n")
    os.symlink(tmp_path / "real.yaml", tmp_path / "link.yaml")
    assert set(usage.scan([("config", tmp_path)]).refs) == {"real"}


def test_addon_configs_root_counts_only_without_own_secrets(tmp_path):
    cfg, addons = tmp_path / "config", tmp_path / "addon_configs"
    write(cfg / "configuration.yaml", "k: !secret a\n")
    write(addons / "slug1" / "app.yaml", "k: !secret b\n")
    write(addons / "slug2" / "secrets.yaml", "own: 1\n")
    write(addons / "slug2" / "app.yaml", "k: !secret own\n")
    res = usage.scan([("config", cfg), ("addon_configs", addons)])
    assert res.refs == {"a": [("configuration.yaml", 1)], "b": [("addon_configs/slug1/app.yaml", 1)]}
    assert res.roots == ["config", "addon_configs"]


def test_missing_root_is_skipped(tmp_path):
    write(tmp_path / "c.yaml", "k: !secret a\n")
    res = usage.scan([("config", tmp_path), ("addon_configs", tmp_path / "nope")])
    assert res.roots == ["config"]


def test_limits_mark_scan_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "MAX_FILES", 2)
    for n in range(5):
        write(tmp_path / f"f{n}.yaml", "k: !secret a\n")
    res = usage.scan([("config", tmp_path)])
    assert res.truncated and res.files_scanned == 2


def test_ref_list_is_capped_but_count_is_exact(tmp_path):
    write(tmp_path / "a.yaml", "".join("k: !secret a\n" for _ in range(30)))
    res = usage.scan([("config", tmp_path)])
    block = usage.summarize(res, {"a", "z"})
    assert block["used"]["a"]["count"] == 30 and len(block["used"]["a"]["refs"]) == usage.MAX_REFS_PER_KEY
    assert block["unused"] == ["z"] and block["missing"] == {}


def test_keys_with_special_characters_and_quotes_and_flow_syntax(tmp_path):
    write(tmp_path / "a.yaml", "a: !secret google_oidc_(proj_x)_client_id\n"
                               "b: !secret \"quoted_key\"\n"
                               "c: [!secret one, !secret two]\n"
                               "d: {k: !secret three}\n")
    assert set(usage.scan([("config", tmp_path)]).refs) == {
        "google_oidc_(proj_x)_client_id", "quoted_key", "one", "two", "three"}
