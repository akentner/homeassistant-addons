"""Store URL building and hash masking (RED stub; implemented in the GREEN step)."""

from __future__ import annotations

from app.options import Options
from app.paths import HTTP_PORT


def mask_hash(hash_: str) -> str:
    return ""


def internal_base(hostname: str, port: int = HTTP_PORT) -> str:
    return ""


def store_url(base: str, owner: str, name: str, hash_: str) -> str:
    return ""


def masked_store_url(base: str, owner: str, name: str, hash_: str) -> str:
    return ""


def store_urls(options: Options, hostname: str, owner: str, name: str, hash_: str) -> dict[str, str]:
    return {}
