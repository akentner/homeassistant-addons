#!/usr/bin/env python3
"""Static blueprint rules for admin-UI front ends (D-15, D-16, PD-02, PD-10, PD-12).

Scans the demo (`admin-ui/app/web/static`, lib in `lib/`) and every consumer found through
`<addon>/app/web/static/vendor/admin-ui/LIB.stamp` for:

    urls          absolute URLs / paths (the front end runs below an unknown ingress prefix)
    markup        raw-markup APIs, eval and string timers (XSS)
    csp           inline <script>, inline on<event> handlers and style attributes in HTML
    vendor        vendored Preact/htm bundle pinned by sha256, README mention, licence files
    selfcontained relative imports in the lib stay inside the lib directory
    publicapi     app code never imports <lib>/vendor directly, only the lib's public modules
    storage       web storage keys are namespaced ("<namespace>:<name>")

This is a regex scanner, not a parser: dynamic constructions need review. `--self-test` seeds one violation per rule
and checks that exactly that rule fires. Exit codes: 0 clean, 1 findings, 2 usage error. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

VENDOR_SHA256 = "72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7"
BUNDLE_NAME = "preact-htm.mjs"
LICENCE_FILES = ("LICENSE-htm.txt", "LICENSE-preact.txt")

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
INLINE_PATTERNS = {
    "inline <script> without src": re.compile(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>", re.I),
    "inline event handler attribute": re.compile(r"<[a-zA-Z][^>]*\son[a-zA-Z]+\s*=", re.S),
    "inline style attribute": re.compile(r"<[a-zA-Z][^>]*\sstyle\s*=", re.S),
}
SPECIFIER = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)["'](\.{1,2}/[^"']*)["']""")
HTML_SRC = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.I)
STORAGE_CALL = re.compile(r"""\b(?:local|session)Storage\s*\.\s*(?:get|set|remove)Item\(\s*([^,)]*)""")
KEY_CONST = re.compile(r"""\bconst\s+(\w*KEY)\s*=\s*(["'`])([^"'`]*)\2""")
NAMESPACED = re.compile(r"^[a-z0-9_-]+:\S+$")
KEY_IDENTIFIER = re.compile(r"^[\w.]*KEY$")


class Finding(NamedTuple):
    path: str
    line: int
    rule: str
    message: str


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _shipped(static_dir: Path) -> list[Path]:
    """mjs/html/css files below static_dir that are not inside a vendor/ directory."""
    out = []
    for dirpath, dirnames, filenames in os.walk(static_dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if d != "vendor" and d != "__pycache__"]
        for name in filenames:
            if name.endswith((".mjs", ".html", ".css")):
                out.append(Path(dirpath) / name)
    return sorted(out)


def _inside(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.normpath(path)).relative_to(Path(os.path.normpath(parent)))
    except ValueError:
        return False
    return True


def scan_static(static_dir: Path, lib_dir: Path | None = None, vendor_sha: str = VENDOR_SHA256) -> list[Finding]:
    """Scan one static tree; `lib_dir` is the lib directory (default `<static_dir>/lib`)."""
    static_dir = Path(static_dir)
    lib_dir = Path(lib_dir) if lib_dir is not None else static_dir / "lib"
    if not lib_dir.is_absolute():
        lib_dir = static_dir / lib_dir
    findings: list[Finding] = []

    def add(path: Path, line: int, rule: str, message: str) -> None:
        findings.append(Finding(str(path), line, rule, message))

    shipped = _shipped(static_dir)
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        for label, pattern in URL_PATTERNS.items():
            for m in pattern.finditer(text):
                add(path, _line(text, m.start()), "urls", f"absolute reference ({label})")
        for label, pattern in DANGEROUS_PATTERNS.items():
            for m in pattern.finditer(text):
                add(path, _line(text, m.start()), "markup", f"dangerous construct ({label})")
        if path.suffix == ".html":
            for label, pattern in INLINE_PATTERNS.items():
                for m in pattern.finditer(text):
                    add(path, _line(text, m.start()), "csp", label)
        in_lib = _inside(path, lib_dir)
        if path.suffix == ".mjs":
            for m in SPECIFIER.finditer(text):
                target = path.parent / m.group(1)
                if in_lib and (not _inside(target, lib_dir) or not target.is_file()):
                    add(path, _line(text, m.start()), "selfcontained", f"import leaves the lib or is missing: {m.group(1)}")
                if not in_lib and _inside(target, lib_dir / "vendor"):
                    add(path, _line(text, m.start()), "publicapi", f"imports lib vendor directly: {m.group(1)}")
            for m in STORAGE_CALL.finditer(text):
                arg = m.group(1).strip()
                literal = re.fullmatch(r"""(["'`])(.*)\1?""", arg)
                if literal:
                    ok = bool(NAMESPACED.match(literal.group(2)))
                else:
                    ok = bool(KEY_IDENTIFIER.match(arg))
                if not ok:
                    add(path, _line(text, m.start()), "storage", "storage key must be '<namespace>:<name>' or a *KEY constant")
            for m in KEY_CONST.finditer(text):
                if not NAMESPACED.match(m.group(3)):
                    add(path, _line(text, m.start()), "storage", f"{m.group(1)} must be namespaced '<namespace>:<name>'")
        elif path.suffix == ".html":
            for m in HTML_SRC.finditer(text):
                if _inside(path.parent / m.group(1), lib_dir / "vendor") and not in_lib:
                    add(path, _line(text, m.start()), "publicapi", f"imports lib vendor directly: {m.group(1)}")

    vendor = lib_dir / "vendor"
    bundle = vendor / BUNDLE_NAME
    if not bundle.is_file():
        add(bundle, 0, "vendor", "vendored bundle missing")
    elif hashlib.sha256(bundle.read_bytes()).hexdigest() != vendor_sha:
        add(bundle, 0, "vendor", "bundle sha256 differs from the pinned value")
    readme = vendor / "README.txt"
    if not readme.is_file() or vendor_sha not in readme.read_text(encoding="utf-8"):
        add(readme, 0, "vendor", "vendor README missing or does not mention the pinned sha256")
    for licence in LICENCE_FILES:
        if not (vendor / licence).is_file():
            add(vendor / licence, 0, "vendor", "licence file missing")
    # A consumer's lib copy lives below vendor/ and is not scanned above: still check that it is self-contained
    for path in sorted(lib_dir.rglob("*.mjs")) if lib_dir.is_dir() else []:
        if path in shipped or "vendor" in path.relative_to(lib_dir).parts:
            continue
        text = path.read_text(encoding="utf-8")
        for m in SPECIFIER.finditer(text):
            target = path.parent / m.group(1)
            if not _inside(target, lib_dir) or not target.is_file():
                add(path, _line(text, m.start()), "selfcontained", f"import leaves the lib or is missing: {m.group(1)}")
    return sorted(set(findings), key=lambda f: (f.path, f.line, f.rule, f.message))


def discover_targets(root: Path) -> list[tuple[Path, Path]]:
    targets: list[tuple[Path, Path]] = []
    demo = root / "admin-ui" / "app" / "web" / "static"
    if demo.is_dir():
        targets.append((demo, demo / "lib"))
    for entry in sorted(root.iterdir()):
        if entry.name == "admin-ui" or not entry.is_dir() or entry.is_symlink():
            continue
        static = entry / "app" / "web" / "static"
        if (static / "vendor" / "admin-ui" / "LIB.stamp").is_file():
            targets.append((static, static / "vendor" / "admin-ui"))
    return targets


# --- self-test ----------------------------------------------------------------------------------------------------

_BUNDLE = "export const html = 1;\n"
_SELF_SHA = hashlib.sha256(_BUNDLE.encode()).hexdigest()
_CLEAN = {
    "index.html": '<!doctype html><html><head><link rel="stylesheet" href="static/app.css"></head>'
    '<body><div id="app"></div><script type="module" src="static/app.mjs"></script></body></html>\n',
    "app.css": "body { margin: 0; }\n",
    "app.mjs": 'import { html } from "./lib/ui.mjs";\nconst THEME_KEY = "adminui:theme";\n'
    "localStorage.getItem(THEME_KEY);\nlocalStorage.setItem(\"adminui:seen\", \"1\");\nexport { html };\n",
    "lib/ui.mjs": 'import { html } from "./vendor/preact-htm.mjs";\nexport { html };\n',
    "lib/api.mjs": 'import "./ui.mjs";\nexport const get = (p) => fetch(p);\n',
    "lib/vendor/preact-htm.mjs": _BUNDLE,
    "lib/vendor/README.txt": f"sha256: {_SELF_SHA}\n",
    "lib/vendor/LICENSE-htm.txt": "Apache License\n",
    "lib/vendor/LICENSE-preact.txt": "MIT License\n",
}
# (name, {file: content or None to delete}, expected rule)
_SEEDS: list[tuple[str, dict[str, str | None], str]] = [
    ("urls: absolute import", {"app.mjs": 'import x from "/abs.mjs";\n'}, "urls"),
    ("urls: absolute fetch", {"app.mjs": 'fetch("/api/x");\n'}, "urls"),
    ("urls: absolute href", {"index.html": _CLEAN["index.html"].replace('href="static', 'href="/static')}, "urls"),
    ("markup: innerHTML", {"app.mjs": "el.innerHTML = x;\n"}, "markup"),
    ("markup: eval", {"app.mjs": "eval(code);\n"}, "markup"),
    ("csp: inline script", {"index.html": _CLEAN["index.html"].replace("</body>", "<script>1</script></body>")}, "csp"),
    ("csp: inline handler", {"index.html": _CLEAN["index.html"].replace('<div id', '<div onclick="x()" id')}, "csp"),
    ("csp: style attribute", {"index.html": _CLEAN["index.html"].replace('<div id', '<div style="a:b" id')}, "csp"),
    ("vendor: tampered bundle", {"lib/vendor/preact-htm.mjs": _BUNDLE + "//x\n"}, "vendor"),
    ("vendor: README without hash", {"lib/vendor/README.txt": "nothing\n"}, "vendor"),
    ("vendor: licence missing", {"lib/vendor/LICENSE-htm.txt": None}, "vendor"),
    ("selfcontained: missing target", {"lib/api.mjs": 'import "./missing.mjs";\n'}, "selfcontained"),
    ("selfcontained: leaves lib", {"lib/api.mjs": 'import "../app.mjs";\n'}, "selfcontained"),
    ("publicapi: vendor import", {"app.mjs": 'import { html } from "./lib/vendor/preact-htm.mjs";\n'}, "publicapi"),
    ("storage: plain literal key", {"app.mjs": 'localStorage.setItem("plain", v);\n'}, "storage"),
    ("storage: plain KEY constant", {"app.mjs": 'const THEME_KEY = "plain";\n'}, "storage"),
]


def _write_tree(root: Path, overrides: dict[str, str | None]) -> None:
    files = {**_CLEAN, **overrides}
    for rel, content in files.items():
        if content is None:
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def self_test() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean"
        _write_tree(clean, {})
        found = scan_static(clean, clean / "lib", _SELF_SHA)
        if found:
            failures += 1
            print(f"FAIL clean tree has findings: {[tuple(f) for f in found]}")
        for index, (name, overrides, rule) in enumerate(_SEEDS):
            root = Path(tmp) / f"seed{index}"
            _write_tree(root, overrides)
            rules = {f.rule for f in scan_static(root, root / "lib", _SELF_SHA)}
            if rules != {rule}:
                failures += 1
                print(f"FAIL {name}: expected only {rule!r}, got {sorted(rules)}")
    print("self-test: " + ("FAILED" if failures else f"ok ({len(_SEEDS)} seeded violations)"))
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="repository root")
    parser.add_argument("--self-test", action="store_true", help="prove the detection with seeded violations")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.root.is_dir():
        print(f"error: root is not a directory: {args.root}", file=sys.stderr)
        return 2
    findings: list[Finding] = []
    for static, lib in discover_targets(args.root):
        findings.extend(scan_static(static, lib))
    for finding in sorted(findings):
        try:
            shown = Path(finding.path).relative_to(args.root)
        except ValueError:
            shown = Path(finding.path)
        print(f"{shown}:{finding.line}: [{finding.rule}] {finding.message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
