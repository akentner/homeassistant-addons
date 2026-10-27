"""Merge provider snapshots into one secret set (see docs/SPEC.md, "Engine semantics")."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.engine.writer import UnsafePathError, safe_relpath
from app.providers.base import Snapshot


class MergeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Merged:
    secrets: dict[str, str] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)
    shadowed: list[tuple[str, str, str]] = field(default_factory=list)  # (name, winner, loser)


def merge(contributions: Sequence[tuple[str, Snapshot]], policy: str) -> Merged:
    """Union of all snapshots, in priority order. Collisions fail (policy `error`) or the earlier provider wins."""
    out = Merged()
    secret_src: dict[str, str] = {}
    file_src: dict[str, str] = {}
    for provider, snap in contributions:
        for path in snap.files:
            try:
                safe_relpath(path)
            except UnsafePathError as exc:
                raise MergeError("unsafe_path", f"provider {provider} returned an unsafe file path") from exc
        for key, value in snap.secrets.items():
            if key in secret_src:
                if policy == "priority":
                    out.shadowed.append((key, secret_src[key], provider))
                    continue
                raise MergeError("key_collision", f"key '{key}' provided by {secret_src[key]} and {provider}")
            secret_src[key] = provider
            out.secrets[key] = value
        for path, content in snap.files.items():
            if path in file_src:
                if policy == "priority":
                    out.shadowed.append((path, file_src[path], provider))
                    continue
                raise MergeError("key_collision", f"file '{path}' provided by {file_src[path]} and {provider}")
            file_src[path] = provider
            out.files[path] = content
    return out
