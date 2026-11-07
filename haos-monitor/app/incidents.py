"""Bounded backward scan for the last INCIDENT lines of a host log (same semantics as incidents.cgi).

Only the current log counts (not the rotated `.log.1`), a line counts when it contains ` INCIDENT ` (leading space
included, as in the old grep). The scan reads blocks from the end and stops after `limit` hits, so a healthy host
costs almost nothing; `max_scan` caps the bytes read (log rotation happens at 20 MiB).
"""

from __future__ import annotations

import re
from pathlib import Path

MARKER = b" INCIDENT "
LIMIT = 10
MAX_LINE = 400
BLOCK = 65536
MAX_SCAN = 24 * 1024 * 1024
# control characters other than tab
_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")


def _clean(raw: bytes, max_line: int) -> str:
    text = raw.decode("utf-8", errors="replace")
    if text.endswith("\r"):
        text = text[:-1]
    return _CONTROL_RE.sub("", text)[:max_line]


def last_incidents(
    path: Path | str,
    limit: int = LIMIT,
    max_line: int = MAX_LINE,
    block: int = BLOCK,
    max_scan: int = MAX_SCAN,
) -> list[str]:
    """The newest `limit` INCIDENT lines, oldest first; [] when the file is missing or unreadable."""
    found: list[str] = []
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            pos = fh.tell()
            floor = max(0, pos - max_scan)
            tail = b""  # the partial line at the start of the data read so far
            while pos > floor and len(found) < limit:
                size = min(block, pos - floor)
                pos -= size
                fh.seek(pos)
                data = fh.read(size) + tail
                lines = data.split(b"\n")
                tail = lines[0]
                for line in reversed(lines[1:]):
                    if MARKER in line:
                        found.append(_clean(line, max_line))
                        if len(found) >= limit:
                            break
            else:
                # reached the start of the file (not the scan cap): the remaining tail is a whole line
                if pos == 0 and len(found) < limit and MARKER in tail:
                    found.append(_clean(tail, max_line))
    except OSError:
        return []
    found.reverse()
    return found
