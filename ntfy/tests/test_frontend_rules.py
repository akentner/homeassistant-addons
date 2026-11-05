"""Blueprint rules for ntfy's own front-end files: css token hygiene (R-08), text contrast in both themes (R-08)
and no inline styles or scripts in templates (R-11). Stdlib only; the contrast helper follows admin-ui/tests/test_css.py."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"
APP_CSS = STATIC / "app.css"
BASE_CSS = STATIC / "vendor" / "admin-ui" / "base.css"
INDEX_HTML = STATIC / "index.html"
OWN_MODULES = [STATIC / "app.mjs", STATIC / "components.mjs", STATIC / "lib" / "model.mjs", *sorted((STATIC / "views").glob("*.mjs"))]

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FN_COLOUR_RE = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)


# ---------------------------------------------------------------- css parsing


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
def own_css() -> str:
    return strip_comments(APP_CSS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def own_blocks(own_css: str) -> list[tuple[str, str, str]]:
    return parse_blocks(own_css)


@pytest.fixture(scope="module")
def themes() -> dict[str, dict[str, str]]:
    blocks = parse_blocks(strip_comments(BASE_CSS.read_text(encoding="utf-8")))

    def decls(selector: str, context_has: str = "") -> dict[str, str]:
        for ctx, sel, body in blocks:
            if sel == selector and context_has in ctx and (context_has or "@media" not in ctx):
                return parse_decls(body)
        raise AssertionError(f"block not found in base.css: {selector!r}")

    return {
        "light": decls(":root"),
        "dark": decls('[data-theme="dark"]'),
        "dark_media": decls(':root:not([data-theme="light"])', "prefers-color-scheme: dark"),
    }


def fallback(value: str) -> str:
    """Resolve a synced token such as var(--sync-acc, #0969da) to its default hex."""
    m = re.fullmatch(r"var\(--sync-[a-z-]+, (#[0-9a-fA-F]{6})\)", value)
    return m.group(1) if m else value


def theme_hex(theme: dict[str, str], name: str) -> str:
    value = fallback(theme[f"--{name}"])
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), f"--{name} is not a plain hex colour: {value}"
    return value


def rule_colour(blocks: list[tuple[str, str, str]], selector: str) -> str:
    """The token named by `color: var(--x)` of the rule that declares exactly this selector (comma lists split)."""
    for ctx, sel, body in blocks:
        if "@media" in ctx:
            continue
        if selector in [s.strip() for s in sel.split(",")]:
            colour = parse_decls(body).get("color", "")
            m = re.fullmatch(r"var\(--([a-z-]+)\)", colour)
            if m:
                return m.group(1)
    raise AssertionError(f"no 'color: var(--token)' rule for {selector!r} in app.css")


# ---------------------------------------------------------------- WCAG helpers


def luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_contrast_helper_self_check() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.02)
    assert contrast("#ffffff", "#777777") == contrast("#777777", "#ffffff")


# ---------------------------------------------------------------- tokens only


def test_app_css_has_no_literal_colour(own_css: str) -> None:
    assert not HEX_RE.search(own_css), f"hex colour in app.css: {HEX_RE.search(own_css).group(0)}"
    assert not FN_COLOUR_RE.search(own_css), f"colour function in app.css: {FN_COLOUR_RE.search(own_css).group(0)}"


def test_app_css_references_only_lib_tokens(own_css: str, themes: dict[str, dict[str, str]]) -> None:
    declared = {k for k in themes["light"] if k.startswith("--")}
    used = set(re.findall(r"var\((--[a-z-]+)", own_css))
    assert used, "app.css uses no tokens at all"
    unknown = sorted(used - declared)
    assert not unknown, f"tokens not defined by the lib base.css: {unknown}"


def test_app_css_defines_no_token_of_its_own(own_blocks: list[tuple[str, str, str]]) -> None:
    for _, sel, body in own_blocks:
        assert not [k for k in parse_decls(body) if k.startswith("--")], f"custom property declared in {sel!r}"


def test_app_css_has_no_import_and_no_absolute_url(own_css: str) -> None:
    assert "@import" not in own_css
    for m in re.finditer(r"url\(\s*['\"]?([^)'\"]*)", own_css):
        target = m.group(1).strip()
        assert not target.startswith("/") and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target), target


# ---------------------------------------------------------------- contrast of ntfy-only text pairs

CHIP_BADGES = [".badge.gui", ".badge.options", ".badge.iac"]
MATRIX_TEXT = [".matrix td.rw", ".matrix td.ro", ".matrix td.wo", ".matrix td.deny"]


@pytest.mark.parametrize("theme_name", ["light", "dark", "dark_media"])
def test_origin_badges_reach_4_5_on_the_chip(
    own_blocks: list[tuple[str, str, str]], themes: dict[str, dict[str, str]], theme_name: str
) -> None:
    theme = themes[theme_name]
    for selector in CHIP_BADGES:
        fg = rule_colour(own_blocks, selector)
        ratio = contrast(theme_hex(theme, fg), theme_hex(theme, "chip"))
        assert ratio >= 4.5, f"{theme_name}: {selector} (--{fg}) on --chip is {ratio:.2f}"


@pytest.mark.parametrize("theme_name", ["light", "dark", "dark_media"])
def test_matrix_and_link_text_reach_4_5_on_the_surfaces(
    own_blocks: list[tuple[str, str, str]], themes: dict[str, dict[str, str]], theme_name: str
) -> None:
    theme = themes[theme_name]
    for selector in [*MATRIX_TEXT, ".link-btn"]:
        fg = rule_colour(own_blocks, selector)
        # the matrix sits on --card, links sit on --card or the page --bg; a hovered matrix cell uses --hover
        for bg in ("card", "bg", "hover"):
            ratio = contrast(theme_hex(theme, fg), theme_hex(theme, bg))
            assert ratio >= 4.5, f"{theme_name}: {selector} (--{fg}) on --{bg} is {ratio:.2f}"


# ---------------------------------------------------------------- templates (R-11)


@pytest.mark.parametrize("path", OWN_MODULES, ids=lambda p: p.relative_to(STATIC).as_posix())
def test_no_inline_style_in_templates(path: Path) -> None:
    code = re.sub(r"(^|[^:])//.*$", r"\1", path.read_text(encoding="utf-8"), flags=re.M)
    assert not re.search(r"\bstyle\s*=", code), f"inline style attribute in {path.name}"
    assert not re.search(r"\.style\b|setAttribute\(\s*[\"']style", code), f"style assignment in {path.name}"
    assert not re.search(r"\bstyle\s*:\s*[\"'`]", code), f"string style prop in {path.name}"


def test_index_html_has_no_inline_script_handler_or_style() -> None:
    page = INDEX_HTML.read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", page, re.I), "inline script"
    assert not re.search(r"\son[a-z]+\s*=", page, re.I), "inline event handler"
    assert not re.search(r"\sstyle\s*=", page, re.I), "inline style attribute"
    assert not re.search(r"<style\b", page, re.I), "inline style element"
    assert not re.search(r"javascript:", page, re.I)


def test_own_module_list_is_complete() -> None:
    names = {p.name for p in OWN_MODULES}
    assert {"app.mjs", "components.mjs", "model.mjs"} <= names
    assert len([p for p in OWN_MODULES if p.parent.name == "views"]) == 5
