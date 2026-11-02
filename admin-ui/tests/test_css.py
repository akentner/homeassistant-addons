"""Tests for lib/base.css: token parity, WCAG contrast, theme-sync hooks and CSS hygiene (stdlib only)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_PATH = Path(__file__).resolve().parent.parent / "app" / "web" / "static" / "lib" / "base.css"

TOKENS = ["bg", "fg", "card", "bd", "mut", "ok", "warn", "err", "acc", "chip", "hover", "shadow", "on-acc", "on-err"]
SYNCED = ["bg", "card", "fg", "bd", "acc", "on-acc"]
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# ---------------------------------------------------------------- parser helpers


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def parse_blocks(text: str, context: str = "") -> list[tuple[str, str, str]]:
    """Return (context, selector, body) for every rule; at-rule bodies are parsed recursively."""
    out: list[tuple[str, str, str]] = []
    i, n = 0, len(text)
    while i < n:
        j = text.find("{", i)
        if j < 0:
            break
        head = text[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        body = text[j + 1 : k - 1]
        if head.startswith("@"):
            out.extend(parse_blocks(body, f"{context}{head}|"))
        else:
            out.append((context, re.sub(r"\s+", " ", head), body))
        i = k
    return out


def parse_decls(body: str) -> dict[str, str]:
    decls: dict[str, str] = {}
    for part in body.split(";"):
        if ":" in part:
            name, value = part.split(":", 1)
            decls[name.strip()] = re.sub(r"\s+", " ", value.strip())
    return decls


@pytest.fixture(scope="module")
def css() -> str:
    return strip_comments(CSS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def blocks(css: str) -> list[tuple[str, str, str]]:
    return parse_blocks(css)


def find_decls(blocks: list[tuple[str, str, str]], selector: str, context_has: str = "") -> dict[str, str]:
    for ctx, sel, body in blocks:
        if sel == selector and context_has in ctx and (context_has or "@media" not in ctx):
            return parse_decls(body)
    raise AssertionError(f"block not found: {selector!r} (context {context_has!r})")


@pytest.fixture(scope="module")
def themes(blocks: list[tuple[str, str, str]]) -> dict[str, dict[str, str]]:
    return {
        "light": find_decls(blocks, ":root"),
        "dark_media": find_decls(blocks, ':root:not([data-theme="light"])', "prefers-color-scheme: dark"),
        "dark": find_decls(blocks, '[data-theme="dark"]'),
        "light_attr": find_decls(blocks, '[data-theme="light"]'),
    }


def token(theme: dict[str, str], name: str) -> str:
    return theme[f"--{name}"]


def fallback(value: str) -> str:
    m = re.fullmatch(r"var\(--sync-[a-z-]+, (#[0-9a-fA-F]{6})\)", value)
    return m.group(1) if m else value


# ---------------------------------------------------------------- WCAG helpers


def luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_helper_self_check() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.02)
    assert contrast("#ffffff", "#777777") == contrast("#777777", "#ffffff")


# ---------------------------------------------------------------- tokens and parity


@pytest.mark.parametrize("theme_name", ["light", "dark_media", "dark", "light_attr"])
def test_token_declared_in_every_theme_block(themes: dict[str, dict[str, str]], theme_name: str) -> None:
    for name in TOKENS:
        assert f"--{name}" in themes[theme_name], f"--{name} missing in {theme_name}"


def test_parity_dark_media_equals_dark_attribute(themes: dict[str, dict[str, str]]) -> None:
    dark_media = {k: v for k, v in themes["dark_media"].items() if k.startswith("--")}
    dark = {k: v for k, v in themes["dark"].items() if k.startswith("--")}
    assert dark_media == dark


def test_parity_light_attribute_equals_default(themes: dict[str, dict[str, str]]) -> None:
    light = {k: v for k, v in themes["light"].items() if k.startswith("--")}
    light_attr = {k: v for k, v in themes["light_attr"].items() if k.startswith("--")}
    assert light == light_attr


def test_scheme_declarations(themes: dict[str, dict[str, str]]) -> None:
    assert themes["light"]["color-scheme"] == "light dark"
    assert themes["dark"]["color-scheme"] == "dark"
    assert themes["dark_media"]["color-scheme"] == "dark"
    assert themes["light_attr"]["color-scheme"] == "light"


@pytest.mark.parametrize("theme_name", ["light", "dark_media", "dark", "light_attr"])
def test_sync_hooks_wrap_hex_fallbacks(themes: dict[str, dict[str, str]], theme_name: str) -> None:
    theme = themes[theme_name]
    for name in SYNCED:
        value = token(theme, name)
        m = re.fullmatch(rf"var\(--sync-{name}, (#[0-9a-fA-F]{{6}})\)", value)
        assert m, f"--{name} in {theme_name} is not a sync hook with hex fallback: {value}"
    for name in set(TOKENS) - set(SYNCED):
        assert "--sync-" not in token(theme, name), f"--{name} must not be syncable"


def test_sync_fallbacks_match_planned_palette(themes: dict[str, dict[str, str]]) -> None:
    light = {n: fallback(token(themes["light"], n)) for n in SYNCED}
    dark = {n: fallback(token(themes["dark"], n)) for n in SYNCED}
    assert light["bg"] == "#f4f5f7" and light["card"] == "#ffffff" and light["on-acc"] == "#ffffff"
    assert dark["bg"] == "#111315" and dark["card"] == "#1b1e21" and dark["on-acc"] == "#0b1220"


# ---------------------------------------------------------------- contrast


@pytest.mark.parametrize("theme_name", ["light", "dark"])
def test_contrast_text_tokens_on_surfaces(themes: dict[str, dict[str, str]], theme_name: str) -> None:
    theme = themes[theme_name]
    for fg in ("fg", "mut", "ok", "warn", "err", "acc"):
        for bg in ("bg", "card", "chip", "hover"):
            ratio = contrast(fallback(token(theme, fg)), fallback(token(theme, bg)))
            assert ratio >= 4.5, f"{theme_name}: --{fg} on --{bg} is {ratio:.2f}"


@pytest.mark.parametrize("theme_name", ["light", "dark"])
def test_contrast_text_on_fill(themes: dict[str, dict[str, str]], theme_name: str) -> None:
    theme = themes[theme_name]
    for on, fill in (("on-acc", "acc"), ("on-err", "err")):
        ratio = contrast(fallback(token(theme, on)), fallback(token(theme, fill)))
        assert ratio >= 4.5, f"{theme_name}: --{on} on --{fill} is {ratio:.2f}"


@pytest.mark.parametrize("theme_name", ["light", "dark"])
def test_contrast_focus_ring(themes: dict[str, dict[str, str]], theme_name: str) -> None:
    theme = themes[theme_name]
    for bg in ("bg", "card"):
        ratio = contrast(fallback(token(theme, "acc")), fallback(token(theme, bg)))
        assert ratio >= 3.0, f"{theme_name}: focus ring on --{bg} is {ratio:.2f}"


# ---------------------------------------------------------------- components and a11y

CONTRACT_SELECTORS = [
    ".topbar", ".brand-icon", ".tabs", ".tab", ".tab.active", ".card", ".grid", ".toolbar", ".spacer", "table.data",
    ".badge", ".badge.ok", ".badge.warn", ".badge.degraded", ".badge.error", ".badge.muted", ".badge.info", ".btn",
    ".btn.secondary", ".btn.danger", ".btn.small", ".form-row", ".actions", ".copy-field", ".notice", ".notice.error",
    ".notice.info", ".modal-backdrop", ".modal", ".modal-head", ".modal-body", ".toast-stack", ".toast",
    ".danger-zone", ".danger-row", ".mono", ".muted", ".loading", ".sr-only", ".menu-btn", ".lang-switch",
    ".theme-isolated", ".tablist", ".tabpanel", ".hint",
]  # fmt: skip

ABSENT_SELECTORS = [".matrix", ".badge.gui", ".badge.options", ".badge.iac", ".toolbar label"]


def all_selectors(blocks: list[tuple[str, str, str]]) -> set[str]:
    found: set[str] = set()
    for _, sel, _ in blocks:
        for part in sel.split(","):
            found.add(re.sub(r"\s+", " ", part.strip()))
    return found


def test_component_contract_classes_present(blocks: list[tuple[str, str, str]]) -> None:
    present = all_selectors(blocks)
    missing = [s for s in CONTRACT_SELECTORS if s not in present]
    assert not missing, f"missing selectors: {missing}"


def test_component_ntfy_only_selectors_absent(blocks: list[tuple[str, str, str]]) -> None:
    present = all_selectors(blocks)
    leaked = [s for s in present if any(s == a or s.startswith(a + " ") or s.startswith(a + ".") for a in ABSENT_SELECTORS)]
    assert not leaked, f"ntfy-only selectors leaked: {leaked}"


def test_component_button_colours_use_tokens(blocks: list[tuple[str, str, str]]) -> None:
    assert find_decls(blocks, ".btn")["color"] == "var(--on-acc)"
    assert find_decls(blocks, ".btn.danger")["color"] == "var(--on-err)"


def test_a11y_focus_visible_rule(blocks: list[tuple[str, str, str]], css: str) -> None:
    rule = next((b for b in blocks if ":focus-visible" in b[1]), None)
    assert rule is not None
    decls = parse_decls(rule[2])
    assert decls["outline"].startswith("2px solid var(--acc)")
    assert "input:focus," not in css


def test_a11y_reduced_motion_and_small_screen(blocks: list[tuple[str, str, str]]) -> None:
    reduced = [b for b in blocks if "prefers-reduced-motion: reduce" in b[0]]
    assert reduced, "reduced-motion block missing"
    joined = " ".join(b[2] for b in reduced)
    assert "animation" in joined and "transition" in joined
    assert any("max-width: 600px" in b[0] for b in blocks)


def test_component_topbar_height_and_selected_tab(blocks: list[tuple[str, str, str]]) -> None:
    assert find_decls(blocks, ".topbar")["height"] == "56px"
    assert '.tab[aria-selected="true"]' in all_selectors(blocks)


def test_component_sr_only_is_visually_hidden(blocks: list[tuple[str, str, str]]) -> None:
    decls = find_decls(blocks, ".sr-only")
    assert decls["position"] == "absolute"
    assert decls["width"] == "1px" and decls["height"] == "1px"
    assert decls["overflow"] == "hidden"


def test_component_menu_button_touch_target(blocks: list[tuple[str, str, str]]) -> None:
    decls = find_decls(blocks, ".menu-btn")
    assert int(decls["min-width"].removesuffix("px")) >= 40
    assert int(decls["min-height"].removesuffix("px")) >= 40


# ---------------------------------------------------------------- hygiene


def test_hygiene_no_import_and_no_absolute_url(css: str) -> None:
    assert "@import" not in css
    for m in re.finditer(r"url\(\s*['\"]?([^)'\"]*)", css):
        target = m.group(1).strip()
        assert not target.startswith("/") and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target), target


def test_hygiene_hex_only_inside_token_blocks(blocks: list[tuple[str, str, str]]) -> None:
    token_selectors = {":root", ':root:not([data-theme="light"])', '[data-theme="dark"]', '[data-theme="light"]'}
    for ctx, sel, body in blocks:
        if sel in token_selectors:
            continue
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body), f"hex colour outside token blocks in {sel!r}"


def test_hygiene_only_declared_tokens_referenced(css: str, themes: dict[str, dict[str, str]]) -> None:
    declared = {k for k in themes["light"] if k.startswith("--")}
    sync = {f"--sync-{n}" for n in SYNCED}
    for m in re.finditer(r"var\((--[a-z-]+)", css):
        name = m.group(1)
        # --safe-* are layout variables set per element from the bridge insets, not theme tokens
        assert name in declared or name in sync or name.startswith("--safe-"), f"undeclared token {name}"


def test_hygiene_file_ends_with_single_newline() -> None:
    raw = CSS_PATH.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
