"""Strict reader of the hosts file written by run.sh (/etc/haos-monitor.hosts).

Columns: slug, name, host, port, key fingerprint, key type, tab separated. Only the first three are read here; the
fingerprint reaches the GUI through status.sh (which validates it), never from this file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

# fullmatch, never match/$: both tolerate a trailing newline
SLUG_RE = re.compile(r"[a-z0-9_]+")
MAX_SLUG = 128
MAX_NAME = 200
MAX_HOST = 255
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class Host(NamedTuple):
    slug: str
    name: str
    host: str


class HostsUnavailable(Exception):
    """The hosts file cannot be read. The message never carries a path."""


def valid_slug(slug: object) -> bool:
    return isinstance(slug, str) and 0 < len(slug) <= MAX_SLUG and SLUG_RE.fullmatch(slug) is not None


def clean_text(value: str, limit: int) -> str:
    return _CONTROL_RE.sub("", value)[:limit]


def load_hosts(path: Path | str) -> list[Host]:
    """Return the configured hosts in file order; invalid or duplicate slugs and short lines are skipped."""
    try:
        text = Path(path).read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise HostsUnavailable("hosts file unavailable") from exc
    hosts: list[Host] = []
    seen: set[str] = set()
    # split on "\n" only (str.splitlines would also split on form feed and unicode separators)
    for raw in text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        columns = line.split("\t")
        if len(columns) < 3:
            continue
        slug = columns[0]
        if not valid_slug(slug) or slug in seen:
            continue
        seen.add(slug)
        name = clean_text(columns[1], MAX_NAME) or slug
        hosts.append(Host(slug, name, clean_text(columns[2], MAX_HOST)))
    return hosts
