"""Test context helper: options.json, fresh schema-10 auth.db and a Context whose CLI is the fake ntfy binary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.context import Context, build_context
from app.contract import DEFAULT_OPTIONS, Paths
from app.ntfycli import NtfyCli
from helpers.ntfy_db import make_auth_db

FAKE_NTFY = Path(__file__).resolve().parent / "fake_ntfy.py"


def write_options(tmp_path: Path, **overrides: Any) -> Paths:
    """Create <tmp>/data with options.json (C2 defaults plus overrides) and return its Paths."""
    data = Path(tmp_path) / "data"
    data.mkdir(parents=True, exist_ok=True)
    options = {**DEFAULT_OPTIONS, **overrides}
    (data / "options.json").write_text(json.dumps(options), encoding="utf-8")
    return Paths.for_dir(data)


def make_context(tmp_path: Path, **overrides: Any) -> Context:
    """Context over a fresh auth.db whose `cli` runs the fake binary against the same database."""
    paths = write_options(tmp_path, **overrides)
    make_auth_db(paths.auth_db)
    ctx = build_context(paths)
    ctx.cli = NtfyCli(binary=str(FAKE_NTFY), config_file=paths.server_yml, auth_file=paths.auth_db)
    return ctx
