"""Structure checks for the blueprint documents: rule ids, spike ids, sections, facts and line length."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ADDON = Path(__file__).resolve().parents[1]
DOCS = ADDON / "DOCS.md"

SECTIONS = [
    "Repository exception",
    "Rules",
    "Library reference",
    "Consumer recipe",
    "Distribution",
    "HA integration",
    "Live spike results",
    "Migration paths",
    "Security notes",
    "Follow-up",
]
RULE_STATUS = {"enforced", "review", "unverified"}
SPIKE_STATUS = {"pending", "verified", "failed", "not-applicable"}
FORBIDDEN = [r"eyJ[A-Za-z0-9_-]{10,}", r"ts\.net", r"haos-op3050", r"hassio-n2plus", r"lxc-haos", r"campoint"]


def _text() -> str:
    return DOCS.read_text(encoding="utf-8")


def _rows(prefix_re: str) -> list[list[str]]:
    rows = []
    for line in _text().splitlines():
        if re.match(prefix_re, line):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def test_docs_required_sections_exist() -> None:
    headings = re.findall(r"^## (.+?)\s*$", _text(), flags=re.MULTILINE)
    for name in SECTIONS:
        assert headings.count(name) == 1, f"section {name!r} must appear exactly once"


def test_docs_rules_table_has_every_rule_once() -> None:
    rows = _rows(r"^\| R-\d")
    ids = [r[0] for r in rows]
    assert ids == [f"R-{n:02d}" for n in range(1, 16)]
    for row in rows:
        assert len(row) == 4, row
        assert all(cell for cell in row), f"empty cell in {row[0]}"
        assert row[3] in RULE_STATUS, f"{row[0]}: status {row[3]!r}"


def test_docs_unverified_claims_are_labelled() -> None:
    status = {r[0]: r[3] for r in _rows(r"^\| R-\d")}
    # CSP (PD-07) and the live HA behaviour stay unverified until the spike records results.
    assert status["R-11"] == "unverified"
    assert status["R-13"] == "unverified"


def test_docs_spike_table_has_every_item_once() -> None:
    rows = _rows(r"^\| S\d")
    assert [r[0] for r in rows] == [f"S{n}" for n in range(1, 16)]
    for row in rows:
        assert len(row) == 6, row
        assert all(cell for cell in row), f"empty cell in {row[0]}"
        assert row[5] in SPIKE_STATUS, f"{row[0]}: status {row[5]!r}"
    assert re.search(r"^Verified on: .+", _text(), flags=re.MULTILINE), "missing 'Verified on:' header line"


def test_docs_states_drift_semantics() -> None:
    text = _text().lower()
    for fragment in ["tampered", "same version", "behind", "--strict", "ahead"]:
        assert fragment in text, fragment
    assert "make sync-admin-ui" in text
    assert "make check-admin-ui-sync" in text


def test_docs_states_ha_integration_limits() -> None:
    text = _text()
    assert "20260128.0" in text
    assert "20260729.0" in text
    assert "undocumented" in text
    assert "stability promise" in text
    assert "docked" in text and "kiosk" in text.lower()
    assert "no_answer" in text


def test_docs_prose_lines_fit_120_columns() -> None:
    for number, line in enumerate(_text().splitlines(), start=1):
        if line.startswith("|"):
            continue
        assert len(line) <= 120, f"DOCS.md:{number} has {len(line)} columns"


def test_docs_contains_no_secrets_or_real_hostnames() -> None:
    text = _text()
    for pattern in FORBIDDEN:
        assert not re.search(pattern, text), pattern


def _repo() -> Path:
    return ADDON.parent


def test_docs_root_readme_registers_the_addon() -> None:
    text = (_repo() / "README.md").read_text(encoding="utf-8")
    assert text.count("### [Admin UI Blueprint](./admin-ui)") == 1
    section = text.split("### [Admin UI Blueprint](./admin-ui)", 1)[1].split("\n### ", 1)[0]
    assert "**Features:**" in section
    assert "![Supports amd64 Architecture][amd64-shield]" in section


def test_docs_claude_md_exception_names_admin_ui() -> None:
    text = (_repo() / "CLAUDE.md").read_text(encoding="utf-8")
    section = text.split("## Exception:", 1)[1].split("\n## ", 1)[0].split("<!--", 1)[0]
    assert "haos-monitor" in section and "admin-ui" in section
    assert "make sync-admin-ui" in section


def test_docs_base_image_config_has_admin_ui_entry() -> None:
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((_repo() / "internal" / "base-image-config.yaml").read_text(encoding="utf-8"))
    assert data["addons"]["admin-ui"] == data["addons"]["ntfy"]
    assert "haos-monitor" not in data["addons"]  # PD-09: follow-up only


def test_docs_addon_readme_and_changelog() -> None:
    readme = (ADDON / "README.md").read_text(encoding="utf-8")
    assert all(len(line) <= 120 for line in readme.splitlines())
    assert len(re.findall(r"^\[release-shield\]: .*version-v", readme, flags=re.MULTILINE)) == 1
    assert "DOCS.md" in readme
    changelog = (ADDON / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0-0]" in changelog
