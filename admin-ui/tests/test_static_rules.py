"""Static blueprint rules: the scanner on the real demo tree, seeded violations per rule, vendored bundle integrity."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "admin-ui" / "app" / "web" / "static"
LIB = STATIC / "lib"
VENDOR = LIB / "vendor"
BUNDLE = VENDOR / "preact-htm.mjs"
SCRIPT = REPO / "internal" / "check-admin-ui-rules.py"
REQUIRED_EXPORTS = (
    "Component createContext h html render useCallback useContext useDebugValue useEffect useErrorBoundary "
    "useImperativeHandle useLayoutEffect useMemo useReducer useRef useState"
).split()

spec = importlib.util.spec_from_file_location("check_admin_ui_rules", SCRIPT)
assert spec and spec.loader
rules = importlib.util.module_from_spec(spec)
sys.modules["check_admin_ui_rules"] = rules
spec.loader.exec_module(rules)


def test_scanner_is_clean_on_real_demo_tree() -> None:
    findings = rules.scan_static(STATIC, LIB)
    assert findings == [], "\n".join(f"{f.path}:{f.line} [{f.rule}] {f.message}" for f in findings)


def test_scanner_covers_files() -> None:
    assert rules._shipped(STATIC), "scan covers no files"


def test_script_exits_clean_and_self_test_passes() -> None:
    for args in ([], ["--self-test"]):
        proc = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr


def _tree(root: Path, overrides: dict[str, str | None]) -> Path:
    rules._write_tree(root, overrides)
    return root


def test_clean_seed_tree_has_no_findings(tmp_path: Path) -> None:
    root = _tree(tmp_path, {})
    assert rules.scan_static(root, root / "lib", rules._SELF_SHA) == []


@pytest.mark.parametrize(("name", "overrides", "rule"), rules._SEEDS, ids=[s[0] for s in rules._SEEDS])
def test_each_rule_detects_its_seed(tmp_path: Path, name: str, overrides: dict[str, str | None], rule: str) -> None:
    root = _tree(tmp_path, overrides)
    found = rules.scan_static(root, root / "lib", rules._SELF_SHA)
    assert found and {f.rule for f in found} == {rule}, name


def test_findings_never_contain_file_contents(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"app.mjs": 'const secret = "TOPSECRET"; el.innerHTML = secret;\n'})
    for finding in rules.scan_static(root, root / "lib", rules._SELF_SHA):
        assert "TOPSECRET" not in " ".join(map(str, finding))


def test_consumer_layout_lib_copy_is_checked_for_self_containment(tmp_path: Path) -> None:
    static = tmp_path / "app" / "web" / "static"
    rules._write_tree(static, {})
    shutil.move(static / "lib", static / "vendor" / "admin-ui")
    (static / "app.mjs").write_text('import { html } from "./vendor/admin-ui/ui.mjs";\n')
    lib = static / "vendor" / "admin-ui"
    assert rules.scan_static(static, lib, rules._SELF_SHA) == []
    (lib / "api.mjs").write_text('import "./missing.mjs";\n')
    assert {f.rule for f in rules.scan_static(static, lib, rules._SELF_SHA)} == {"selfcontained"}


def test_patterns_detect() -> None:
    assert rules.URL_PATTERNS["src/href/action attribute"].search('<a href="/x">')
    assert rules.URL_PATTERNS["fetch"].search("fetch('https://x')")
    assert rules.URL_PATTERNS["import from"].search("import {a} from '/vendor/x.mjs'")
    assert not rules.URL_PATTERNS["import from"].search("import {a} from '../vendor/x.mjs'")
    assert not rules.URL_PATTERNS["src/href/action attribute"].search('<a href="static/x">')
    assert rules.DANGEROUS_PATTERNS["innerHTML"].search("el.innerHTML = x")


def test_vendored_bundle_hash_and_readme() -> None:
    assert hashlib.sha256(BUNDLE.read_bytes()).hexdigest() == rules.VENDOR_SHA256
    assert rules.VENDOR_SHA256 in (VENDOR / "README.txt").read_text()


def test_licences_present() -> None:
    assert "Apache License" in (VENDOR / "LICENSE-htm.txt").read_text()
    assert "MIT License" in (VENDOR / "LICENSE-preact.txt").read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_bundle_exports_all_names() -> None:
    script = f"import({BUNDLE.as_uri()!r}).then(m => console.log(JSON.stringify(Object.keys(m))))"
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    for name in REQUIRED_EXPORTS:
        assert f'"{name}"' in proc.stdout, name
