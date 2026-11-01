"""Random topic suggestion (D-17): proposes a topic and the default ACL, writes nothing."""

from __future__ import annotations

import secrets
import string
from typing import Any, Callable

from app.contract import DEFAULT_TOPIC_ACL, TOPIC_RE, ApiError

ALPHABET = string.ascii_letters + string.digits
LENGTH = 16
ATTEMPTS = 20


def suggest(ctx: Any, rng: Callable[[str], str] = secrets.choice) -> dict[str, Any]:
    """A 16-character topic not colliding (case-insensitively) with an existing rule pattern, plus the default ACL."""
    taken = {row["topic"].lower() for row in ctx.db.list_acl()}
    for _ in range(ATTEMPTS):
        topic = "".join(rng(ALPHABET) for _ in range(LENGTH))
        if topic.lower() not in taken and TOPIC_RE.match(topic):
            return {
                "topic": topic,
                "acl": [{"user": user, "permission": permission} for user, permission in DEFAULT_TOPIC_ACL],
            }
    raise ApiError("conflict", "could not generate a unique topic")
