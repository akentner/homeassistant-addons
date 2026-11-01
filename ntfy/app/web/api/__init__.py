"""API modules: every module not starting with `_` exposes register(router, ctx) and is picked up automatically."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from app.web.server import Router


def register_all(router: Router, ctx: Any) -> None:
    """Import all API modules in sorted order and let each register its routes."""
    names = sorted(name for _, name, _ in pkgutil.iter_modules(__path__) if not name.startswith("_"))
    for name in names:
        module = importlib.import_module(f"{__name__}.{name}")
        register = getattr(module, "register", None)
        if register is None:
            raise RuntimeError(f"API module {name} has no register(router, ctx)")
        register(router, ctx)
