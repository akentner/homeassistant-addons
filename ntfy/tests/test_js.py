"""Runs the node --test unit tests of the frontend modules; skipped without node."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path(__file__).resolve().parent / "js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_node_unit_tests() -> None:
    # Pass files explicitly: node 22 does not accept a directory argument.
    files = sorted(str(p) for p in JS_DIR.glob("*.test.mjs"))
    assert files, "no node tests found"
    proc = subprocess.run(["node", "--test", *files], capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
