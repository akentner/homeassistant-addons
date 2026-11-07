"""Static guards for the shipped frontend: ingress/XSS invariants and the admin-ui blueprint scanner.

The vendored runtime (bundle hash, licences) belongs to the synced lib copy; the scanner rule `vendor` checks it.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "ntfy" / "app" / "web" / "static"
VENDOR = STATIC / "vendor"
LIB = VENDOR / "admin-ui"
SCRIPT = REPO / "internal" / "check-admin-ui-rules.py"

spec = importlib.util.spec_from_file_location("check_admin_ui_rules", SCRIPT)
assert spec and spec.loader
rules = importlib.util.module_from_spec(spec)
sys.modules["check_admin_ui_rules"] = rules
spec.loader.exec_module(rules)

# An absolute reference: leading slash (also protocol-relative) or a URL scheme.
ABS = r"""\s*(?:/|[a-zA-Z][a-zA-Z0-9+.-]*:)"""
URL_PATTERNS = {
    "src/href/action attribute": re.compile(r"""\b(?:src|href|action)\s*=\s*["']""" + ABS, re.I),
    "css url()": re.compile(r"""url\(\s*["']?""" + ABS.strip(), re.I),
    "css @import": re.compile(r"@import\b", re.I),
    "import from": re.compile(r"""\bfrom\s*["']""" + ABS),
    "bare import": re.compile(r"""\bimport\s*["']""" + ABS),
    "dynamic import": re.compile(r"""\bimport\(\s*["'`]""" + ABS),
    "fetch": re.compile(r"""\bfetch\(\s*["'`]""" + ABS),
}
DANGEROUS_PATTERNS = {
    "innerHTML": re.compile(r"\binnerHTML\b"),
    "outerHTML": re.compile(r"\bouterHTML\b"),
    "insertAdjacentHTML": re.compile(r"insertAdjacentHTML"),
    "dangerouslySetInnerHTML": re.compile(r"dangerouslySetInnerHTML"),
    "document.write": re.compile(r"document\.write"),
    "eval": re.compile(r"\beval\s*\("),
    "new Function": re.compile(r"\bnew\s+Function\b"),
    "string timer": re.compile(r"""\bset(?:Timeout|Interval)\(\s*["'`]"""),
}


def shipped_files() -> list[Path]:
    files = [p for ext in ("mjs", "html", "css") for p in STATIC.rglob(f"*.{ext}")]
    return sorted(p for p in files if VENDOR not in p.parents)


def test_blueprint_scanner_is_clean() -> None:
    findings = rules.scan_static(STATIC, LIB)
    assert findings == [], "\n".join(f"{f.path}:{f.line} [{f.rule}] {f.message}" for f in findings)


def test_scan_finds_files() -> None:
    assert shipped_files(), "scan covers no files"


@pytest.mark.parametrize("path", shipped_files(), ids=lambda p: str(p.relative_to(STATIC)))
def test_no_absolute_urls(path: Path) -> None:
    text = path.read_text()
    hits = [name for name, rx in URL_PATTERNS.items() if rx.search(text)]
    assert not hits, f"{path.name}: absolute URL via {hits}"


@pytest.mark.parametrize("path", shipped_files(), ids=lambda p: str(p.relative_to(STATIC)))
def test_no_raw_html_or_eval(path: Path) -> None:
    text = path.read_text()
    hits = [name for name, rx in DANGEROUS_PATTERNS.items() if rx.search(text)]
    assert not hits, f"{path.name}: forbidden API {hits}"


def test_scan_patterns_detect() -> None:
    assert URL_PATTERNS["src/href/action attribute"].search('<a href="/x">')
    assert URL_PATTERNS["fetch"].search("fetch('https://x')")
    assert URL_PATTERNS["import from"].search("import {a} from '/vendor/x.mjs'")
    assert not URL_PATTERNS["import from"].search("import {a} from '../vendor/x.mjs'")
    assert not URL_PATTERNS["src/href/action attribute"].search('<a href="static/x">')
    assert DANGEROUS_PATTERNS["innerHTML"].search("el.innerHTML = x")
