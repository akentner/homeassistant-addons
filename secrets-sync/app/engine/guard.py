"""Shrink guard: refuse to overwrite secrets.yaml with a suspiciously smaller set (see docs/SPEC.md)."""

from __future__ import annotations


def check_shrink(items: int, last_items: int | None, percent: int, force: bool = False) -> str | None:
    """Return an error code if the write must be refused, else None.

    Zero items is always refused; `force` only lifts the percentage check.
    """
    if items <= 0:
        return "shrink_guard"
    if force or last_items is None or last_items <= 0:
        return None
    if items < last_items * (1 - percent / 100):
        return "shrink_guard"
    return None
