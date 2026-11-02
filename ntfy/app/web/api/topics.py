"""GET /api/topics/suggest: random topic with the default ACL (contract C10)."""

from __future__ import annotations

from typing import Any

from app.topics import suggest
from app.web.server import Request, Router


def register(router: Router, ctx: Any) -> None:
    router.add("GET", "/api/topics/suggest", lambda _req: suggest(ctx))
