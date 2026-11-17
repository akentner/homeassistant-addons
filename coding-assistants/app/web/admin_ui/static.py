"""Whitelisted static file serving of the admin-UI skeleton: per-segment regex, extension whitelist, containment.

Every asset gets a strong ETag (hash of the served bytes). `/` (index.html) is served with its `static/...` asset URLs
rewritten to `static/...?v=<hash of that asset>`, so a changed asset changes the index and its ETag.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
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
# Only attribute values that point below static/ are versioned; anything else is left as it is.
ASSET_ATTR_RE = re.compile(r'(\b(?:src|href)=")(static/[^"?#]+)(")')


@dataclass(frozen=True)
class Asset:
    body: bytes
    ctype: str
    etag: str


def etag_matches(header: str | None, etag: str) -> bool:
    """True when an If-None-Match header value matches `etag` (list, weak prefix and `*` are accepted)."""
    if not header:
        return False
    for candidate in header.split(","):
        candidate = candidate.strip()
        if candidate == "*" or candidate.removeprefix("W/") == etag:
            return True
    return False


class StaticFiles:
    """Serves `/` (index.html), `/icon` (icon.png) and `/static/<rel>` below one root directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        # path -> ((mtime_ns, size), sha256 hex); avoids rehashing unchanged files
        self._hashes: dict[Path, tuple[tuple[int, int], str]] = {}

    def _locate(self, rel: str, allow_html: bool = False) -> tuple[Path, str] | None:
        segments = rel.split("/")
        if not all(SEGMENT_RE.match(segment) for segment in segments):
            return None
        ext = segments[-1].rsplit(".", 1)[-1] if "." in segments[-1] else ""
        if ext not in CONTENT_TYPES and not allow_html:
            return None
        try:
            root = self.root.resolve()
            target = (root / rel).resolve()
            target.relative_to(root)
            if not target.is_file():
                return None
        except (OSError, ValueError):
            return None
        return target, CONTENT_TYPES.get(ext, "")

    def _digest(self, target: Path) -> str:
        stat = target.stat()
        key = (stat.st_mtime_ns, stat.st_size)
        cached = self._hashes.get(target)
        if cached is not None and cached[0] == key:
            return cached[1]
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        self._hashes[target] = (key, digest)
        return digest

    def _asset_version(self, rel: str) -> str | None:
        found = self._locate(rel[len("static/"):])
        if found is None:
            return None
        try:
            return self._digest(found[0])[:12]
        except OSError:
            return None

    def resolve_asset(self, path: str) -> Asset | None:
        """Return the asset (content, content type, strong ETag) for a whitelisted static path, else None (-> 404)."""
        if path == "/":
            rel, html = "index.html", True
        elif path == "/icon":
            rel, html = "icon.png", False
        elif path.startswith("/static/"):
            rel, html = path[len("/static/"):], False
        else:
            return None
        found = self._locate(rel, allow_html=html)
        if found is None:
            return None
        target, ctype = found
        try:
            if html:
                text = target.read_text(encoding="utf-8")

                def version(match: re.Match[str]) -> str:
                    v = self._asset_version(match.group(2))
                    return match.group(0) if v is None else f"{match.group(1)}{match.group(2)}?v={v}{match.group(3)}"

                body = ASSET_ATTR_RE.sub(version, text).encode("utf-8")
                return Asset(body, "text/html; charset=utf-8", f'"{hashlib.sha256(body).hexdigest()[:16]}"')
            data = target.read_bytes()
            return Asset(data, ctype, f'"{hashlib.sha256(data).hexdigest()[:16]}"')
        except (OSError, UnicodeDecodeError):
            return None

    def resolve(self, path: str) -> tuple[bytes, str] | None:
        """Return (content, content type) for a whitelisted static path, else None (-> 404)."""
        asset = self.resolve_asset(path)
        return None if asset is None else (asset.body, asset.ctype)
