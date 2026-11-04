"""Runs the node --test tests of the Preact front end (tests/js); skipped without node."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path(__file__).resolve().parent / "js"
FILES = ("model", "i18n", "host_card", "app")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_node_unit_tests() -> None:
    files = [str(JS_DIR / f"{name}.test.mjs") for name in FILES]
    present = sorted(p.name for p in JS_DIR.glob("*.test.mjs"))
    assert present == sorted(f"{name}.test.mjs" for name in FILES), "node test files and the list in test_js.py differ"
    proc = subprocess.run(["node", "--test", *files], capture_output=True, text=True, timeout=180, check=False)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
