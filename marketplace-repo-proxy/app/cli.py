"""`mrp` CLI (RED stub; implemented in the GREEN step)."""

from __future__ import annotations

import sys

from app.paths import Paths


def main(argv: list[str] | None = None, paths: Paths | None = None, hostname: str | None = None) -> int:
    return 1


if __name__ == "__main__":
    sys.exit(main())
