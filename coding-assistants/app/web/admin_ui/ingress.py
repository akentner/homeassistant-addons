"""Ingress gate predicate: only the Supervisor ingress peer carrying X-Ingress-Path may reach the server."""

from __future__ import annotations

from typing import Any

INGRESS_REMOTE = "172.30.32.2"


def is_ingress(peer: str, headers: Any, remote: str = INGRESS_REMOTE) -> bool:
    """True when the TCP peer equals the Supervisor address AND a non-empty X-Ingress-Path header is present."""
    return peer == remote and bool(headers.get("X-Ingress-Path"))


_USER_HEADERS = {
    "user_id": "X-Remote-User-Id",
    "name": "X-Remote-User-Name",
    "display_name": "X-Remote-User-Display-Name",
}
_MAX_VALUE = 128


def ingress_user(headers: Any) -> dict[str, Any] | None:
    """The viewer's identity from the X-Remote-User-* headers, or None when none is present. Never log the values."""
    found = False
    user: dict[str, Any] = {}
    for key, header in _USER_HEADERS.items():
        value = (headers.get(header) or "")[:_MAX_VALUE]
        found = found or bool(value)
        user[key] = value
    raw_groups = headers.get("X-Remote-User-Groups") or ""
    groups = [g[:_MAX_VALUE] for g in (part.strip() for part in raw_groups.split(",")) if g]
    user["groups"] = groups
    return user if found or groups else None
