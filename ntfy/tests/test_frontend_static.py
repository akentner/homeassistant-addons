"""Static guards for the shipped frontend: vendored runtime integrity and ingress/XSS invariants."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"
VENDOR = STATIC / "vendor"
BUNDLE = VENDOR / "preact-htm.mjs"
SHA256 = "72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7"
REQUIRED_EXPORTS = ["html", "render", "useState", "useEffect", "useMemo", "useRef", "useCallback"]

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


def test_vendored_bundle_hash() -> None:
    assert hashlib.sha256(BUNDLE.read_bytes()).hexdigest() == SHA256
    assert SHA256 in (VENDOR / "README.txt").read_text()


def test_licences_present() -> None:
    assert "Apache License" in (VENDOR / "LICENSE-htm.txt").read_text()
    assert "MIT License" in (VENDOR / "LICENSE-preact.txt").read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_bundle_exports() -> None:
    script = (
        f"import({BUNDLE.as_uri()!r}).then(m => console.log(JSON.stringify(Object.keys(m))))"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    for name in REQUIRED_EXPORTS:
        assert f'"{name}"' in proc.stdout


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
