"""pytest path setup: `import app...` resolves to marketplace-repo-proxy/app."""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ADDON_DIR = TESTS_DIR.parent

for entry in (str(ADDON_DIR), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
