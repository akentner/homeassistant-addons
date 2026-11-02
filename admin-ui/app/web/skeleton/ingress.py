"""Ingress gate predicate: only the Supervisor ingress peer carrying X-Ingress-Path may reach the server."""

from __future__ import annotations

from typing import Any

INGRESS_REMOTE = "172.30.32.2"


def is_ingress(peer: str, headers: Any, remote: str = INGRESS_REMOTE) -> bool:
    """True when the TCP peer equals the Supervisor address AND a non-empty X-Ingress-Path header is present."""
    return peer == remote and bool(headers.get("X-Ingress-Path"))
