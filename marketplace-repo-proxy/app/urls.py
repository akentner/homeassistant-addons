"""Store URL building and hash masking. Full URLs go to the operator's terminal only; logs get masked ones."""

from __future__ import annotations

from app.options import Options
from app.paths import HTTP_PORT


def mask_hash(hash_: str) -> str:
    """First 4 hex chars plus an ellipsis: tells users apart, keeps 112 bits secret."""
    return hash_[:4] + "…"


def internal_base(hostname: str, port: int = HTTP_PORT) -> str:
    return f"http://{hostname}:{port}"


def store_url(base: str, owner: str, name: str, hash_: str) -> str:
    return f"{base.rstrip('/')}/repo/{owner}/{name}/{hash_}"


def masked_store_url(base: str, owner: str, name: str, hash_: str) -> str:
    return store_url(base, owner, name, mask_hash(hash_))


def store_urls(options: Options, hostname: str, owner: str, name: str, hash_: str) -> dict[str, str]:
    """`internal` always; `public` only when `public_url` is configured."""
    urls = {"internal": store_url(internal_base(hostname), owner, name, hash_)}
    if options.public_url:
        urls["public"] = store_url(options.public_url, owner, name, hash_)
    return urls
