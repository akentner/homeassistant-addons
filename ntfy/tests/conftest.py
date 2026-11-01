"""pytest path setup: `import app...` resolves to ntfy/app, `import helpers...` to ntfy/tests/helpers."""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
NTFY_DIR = TESTS_DIR.parent

for entry in (str(NTFY_DIR), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
