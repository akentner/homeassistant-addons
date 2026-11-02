"""Shared runtime context (contract C9): options, paths, CLI writer and DB reader in one object."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.authdb import AuthDb
from app.backups import BackupStore
from app.contract import Options, Paths, load_options
from app.ntfycli import NtfyCli
from app.origins import OriginStore


@dataclass
class Context:
    options: Options
    paths: Paths
    cli: NtfyCli
    db: AuthDb
    origins: Any = None  # OriginStore
    backups: Any = None  # BackupStore
    clock: Callable[[], float] = time.time
    lock: threading.RLock = field(default_factory=threading.RLock)


def build_context(paths: Paths | None = None) -> Context:
    paths = paths or Paths.from_env()
    options = load_options(paths.options_file)
    cli = NtfyCli(os.environ.get("NTFY_BIN", "ntfy"), str(paths.server_yml), str(paths.auth_db))
    return Context(
        options=options,
        paths=paths,
        cli=cli,
        db=AuthDb(paths.auth_db),
        origins=OriginStore(paths.origins_file),
        backups=BackupStore(paths.backup_dir, paths.auth_db, options.backup_keep),
    )
