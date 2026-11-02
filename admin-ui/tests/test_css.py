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
