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


# ---- API / docs drift (plan 26-12): the documented API equals the real one ----

BROWSER_EXPORTS = {
    "api.mjs": "ApiClientError buildUrl request get post put patch del",
    "ingress.mjs": "isEmbedded assertRelative apiHref errorKey",
    "hooks.mjs": "useAsync usePoll",
    "format.mjs": "formatDateTime formatRelative formatBytes formatNumber",
    "i18n.mjs": "LANGS LANG_STORAGE_KEY detectLang getLang setLang useLang useT t tp tError registerStrings",
    "color.mjs": "parseColor serializeColor relativeLuminance contrastRatio isDarkColor pickOnColor",
    "theme-sync.mjs": "createThemeSync THEME_WHITELIST",
    "ha-bridge.mjs": "createHaBridge",
    "a11y.mjs": "tabbables nextTabTarget useUid",
    "shell.mjs": "Topbar LangSwitch TabNav ErrorBoundary parseHash useHashRoute",
    "ui.mjs": "toast Toasts Modal ConfirmDialog confirmMatches Badge ErrorNote Loading CopyField Tabs DataTable Field",
}
SKELETON_EXPORTS = (
    "ApiError ERROR_STATUS register_error_code Request Router Download StaticFiles INGRESS_REMOTE is_ingress "
    "ingress_user DEFAULT_CSP security_headers MAX_BODY make_handler make_server serve"
).split()


def _library_reference() -> str:
    return _text().split("\n## Library reference", 1)[1].split("\n## ", 1)[0]


def _mentions(section: str, name: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", section) is not None


def test_docs_library_reference_documents_every_export() -> None:
    section = _library_reference()
    missing = [
        f"{module}:{name}"
        for module, names in BROWSER_EXPORTS.items()
        for name in names.split()
        if not _mentions(section, name)
    ]
    missing += [f"skeleton:{name}" for name in SKELETON_EXPORTS if not _mentions(section, name)]
    assert not missing, f"undocumented exports: {missing}"
    for name in ("Component", "createContext", "html", "render", "useState", "useEffect"):
        assert name in section or "Preact exports" in section


def test_docs_library_reference_lists_every_lib_file() -> None:
    section = _library_reference()
    lib = ADDON / "app" / "web" / "static" / "lib"
    names = sorted(p.name for p in lib.glob("*.mjs")) + ["base.css", "preact-htm.mjs"]
    missing = [n for n in names if n not in section and not (n.startswith("strings.") and "strings.de.mjs" in section)]
    assert not missing, f"lib files missing from the library reference: {missing}"


def test_docs_skeleton_public_names_match_the_package() -> None:
    import ast

    tree = ast.parse((ADDON / "app" / "web" / "skeleton" / "__init__.py").read_text(encoding="utf-8"))
    declared = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in node.targets)
    )
    # MAX_BODY lives in server.py and is documented there; the package re-exports the rest.
    assert set(declared) == set(SKELETON_EXPORTS) - {"MAX_BODY"}


def test_docs_mentions_make_targets_and_changelog_topics() -> None:
    text = _text()
    for target in ("sync-admin-ui", "check-admin-ui-sync", "check-admin-ui-rules", "test-admin-ui"):
        assert f"make {target}" in text, target
    changelog = (ADDON / "CHANGELOG.md").read_text(encoding="utf-8").lower()
    for fragment in ("sync tooling", "rules scanner", "ci job", "export contract", "lib.lock"):
        assert fragment in changelog, fragment


def test_docs_spike_items_stay_pending_until_recorded() -> None:
    rows = _rows(r"^\| S\d")
    pending = [r[0] for r in rows if r[5] == "pending"]
    assert pending == [r[0] for r in rows], "spike results are recorded only by plan 26-13"
    assert "not yet run" in _text()
