"""The shipped static tree: blueprint scanner clean, token-only CSS, strict page shell, relative imports, no stray files."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADDON = REPO / "haos-monitor"
STATIC = ADDON / "app" / "web" / "static"
LIB = STATIC / "vendor" / "admin-ui"
SCRIPT = REPO / "internal" / "check-admin-ui-rules.py"

spec = importlib.util.spec_from_file_location("check_admin_ui_rules", SCRIPT)
assert spec and spec.loader
rules = importlib.util.module_from_spec(spec)
sys.modules["check_admin_ui_rules"] = rules
spec.loader.exec_module(rules)


def shipped(suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        p for p in STATIC.rglob("*") if p.is_file() and "vendor" not in p.relative_to(STATIC).parts and p.suffix in suffixes
    )


def test_scanner_is_clean_and_haos_monitor_is_a_discovered_target() -> None:
    findings = rules.scan_static(STATIC, LIB)
    assert findings == [], "\n".join(f"{f.path}:{f.line} [{f.rule}] {f.message}" for f in findings)
    assert (STATIC, LIB) in rules.discover_targets(REPO)
    assert rules._shipped(STATIC), "the scanner covers no files"


def test_app_css_uses_tokens_only() -> None:
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "hex colour literal"
    assert not re.search(r"\b(?:rgb|rgba|hsl|hsla|color-mix|oklch|lab)\(", css), "colour function"
    assert "!important" not in css
    assert "@import" not in css
    assert "url(" not in css
    assert css.endswith("\n") and not css.endswith("\n\n")
    declared = set(re.findall(r"(--[a-z0-9-]+)\s*:", (LIB / "base.css").read_text(encoding="utf-8")))
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    assert used, "app.css uses no tokens at all"
    assert used <= declared, f"unknown tokens: {sorted(used - declared)}"


def test_index_html_is_a_strict_shell() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert re.findall(r'<link rel="stylesheet" href="([^"]+)"', page) == [
        "static/vendor/admin-ui/base.css",
        "static/app.css",
    ]
    assert page.count('<div id="app"></div>') == 1
    assert re.findall(r"<script\b[^>]*>", page) == ['<script type="module" src="static/app.mjs">']
    assert not re.search(r"<script\b(?![^>]*\bsrc=)", page)
    assert not re.search(r"<[a-zA-Z][^>]*\s(?:on[a-z]+|style)\s*=", page)
    for ref in re.findall(r'(?:src|href)="([^"]+)"', page):
        assert not ref.startswith(("/", "http:", "https:", "//")), ref


def test_every_shipped_file_is_servable() -> None:
    from app.web.admin_ui.static import CONTENT_TYPES

    for path in STATIC.rglob("*"):
        rel = path.relative_to(STATIC)
        if not path.is_file() or rel.parts[0] == "vendor" or rel.as_posix() == "index.html":
            continue
        assert path.suffix.lstrip(".") in CONTENT_TYPES, f"{rel} would be unreachable (404)"


def test_modules_import_relative_and_reach_the_lib_through_public_modules() -> None:
    files = shipped((".mjs",))
    assert {p.name for p in files} >= {"app.mjs", "model.mjs", "host-card.mjs", "overview.mjs"}
    for path in files:
        text = path.read_text(encoding="utf-8")
        for spec_ in re.findall(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)["']([^"']+)["']""", text):
            assert spec_.startswith(("./", "../")), f"{path.name}: non-relative import {spec_}"
            target = (path.parent / spec_).resolve()
            assert target.is_file(), f"{path.name}: missing import {spec_}"
            if LIB in target.parents:
                assert target.parent == LIB and target.suffix == ".mjs", f"{path.name}: lib internals {spec_}"


def test_web_storage_is_not_used_or_namespaced() -> None:
    for path in shipped((".mjs",)):
        text = path.read_text(encoding="utf-8")
        for key in re.findall(r"""(?:local|session)Storage\s*\.\s*\w+Item\(\s*["']([^"']+)["']""", text):
            assert key.startswith("haos-monitor:"), f"{path.name}: {key}"
        assert not re.search(r"\b(?:local|session)Storage\b", text), f"{path.name} uses web storage"


def test_no_raw_markup_apis_and_no_absolute_fetch() -> None:
    for path in shipped((".mjs", ".html")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|dangerouslySetInnerHTML|document\.write", text), path.name
        assert not re.search(r"""fetch\(\s*["'`]/""", text), path.name
