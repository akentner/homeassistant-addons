"""Whitelisted static file serving of the admin-UI skeleton: per-segment regex, extension whitelist, containment."""

from __future__ import annotations

import re
from pathlib import Path

SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
CONTENT_TYPES = {
    "mjs": "text/javascript; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "png": "image/png",
    "svg": "image/svg+xml",
    "txt": "text/plain; charset=utf-8",
}


class StaticFiles:
    """Serves `/` (index.html), `/icon` (icon.png) and `/static/<rel>` below one root directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def resolve(self, path: str) -> tuple[bytes, str] | None:
        """Return (content, content type) for a whitelisted static path, else None (-> 404)."""
        if path == "/":
            rel = "index.html"
            ctype_override: str | None = "text/html; charset=utf-8"
        elif path == "/icon":
            rel = "icon.png"
            ctype_override = None
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
            ctype_override = None
        else:
            return None
        segments = rel.split("/")
        if not all(SEGMENT_RE.match(segment) for segment in segments):
            return None
        ext = segments[-1].rsplit(".", 1)[-1] if "." in segments[-1] else ""
        if ext not in CONTENT_TYPES and ctype_override is None:
            return None
        try:
            root = self.root.resolve()
            target = (root / rel).resolve()
            target.relative_to(root)
            if not target.is_file():
                return None
            return target.read_bytes(), ctype_override or CONTENT_TYPES[ext]
        except (OSError, ValueError):
            return None
