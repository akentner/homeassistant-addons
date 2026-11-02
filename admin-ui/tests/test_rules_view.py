"""Cross-check of the demo rules view data against DOCS.md, the repository and the string tables."""

from __future__ import annotations

import re
from pathlib import Path

ADDON = Path(__file__).resolve().parents[1]
REPO = ADDON.parent
DOCS = ADDON / "DOCS.md"
STATIC = ADDON / "app" / "web" / "static"
VIEW = STATIC / "views" / "rules.mjs"


def _docs_rows() -> dict[str, list[str]]:
    rows = {}
    for line in DOCS.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| R-\d", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows[cells[0]] = cells
    return rows


def _view_rules() -> list[dict[str, object]]:
    text = VIEW.read_text(encoding="utf-8")
    block = re.search(r"export const RULES = \[(.*?)\n\];", text, flags=re.S)
    assert block, "RULES array literal not found"
    rules = []
    for entry in re.finditer(r"\{\s*id:\s*\"(R-\d+)\",\s*status:\s*\"(\w+)\",\s*enforcedBy:\s*\[(.*?)\]\s*,?\s*\}", block.group(1), flags=re.S):
        paths = re.findall(r"\"([^\"]+)\"", entry.group(3))
        rules.append({"id": entry.group(1), "status": entry.group(2), "enforcedBy": paths})
    return rules


def test_view_rule_ids_equal_docs_ids() -> None:
    assert [r["id"] for r in _view_rules()] == list(_docs_rows()) == [f"R-{n:02d}" for n in range(1, 16)]


def test_view_statuses_equal_docs_statuses() -> None:
    docs = _docs_rows()
    for rule in _view_rules():
        assert rule["status"] == docs[str(rule["id"])][3], rule["id"]


def test_enforcing_paths_exist_in_the_repository() -> None:
    for rule in _view_rules():
        assert rule["enforcedBy"], f"{rule['id']}: no enforcing path"
        for path in rule["enforcedBy"]:  # type: ignore[attr-defined]
            assert (REPO / str(path)).exists(), f"{rule['id']}: {path} does not exist"


def test_every_rule_has_title_and_how_strings_in_both_languages() -> None:
    for lang in ("de", "en"):
        text = (STATIC / f"strings.{lang}.mjs").read_text(encoding="utf-8")
        for rule in _view_rules():
            nn = str(rule["id"]).split("-")[1]
            for suffix in ("title", "how"):
                key = f"demo.rules.r{nn}.{suffix}"
                assert f'"{key}"' in text, f"{lang}: missing {key}"
