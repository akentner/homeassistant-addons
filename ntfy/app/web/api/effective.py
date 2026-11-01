"""GET /api/effective?user=&topic= (contract C10 Effective)."""

from __future__ import annotations

from typing import Any

from app.contract import ApiError
from app.rights import effective
from app.web.server import Request, Router


def register(router: Router, ctx: Any) -> None:
    def get_effective(req: Request) -> Any:
        user, topic = req.arg("user"), req.arg("topic")
        if not user or not topic:
            raise ApiError("bad_request", "user and topic are required")
        return effective(ctx, user, topic)

    router.add("GET", "/api/effective", get_effective)
