"""Request, Download and Router of the admin-UI skeleton: `{param}` path segments, 404/405 as ApiError."""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import ApiError


@dataclass
class Download:
    """Handler result that is sent as an attachment."""

    filename: str
    content_type: str
    data: bytes


@dataclass
class Request:
    method: str
    path: str
    params: dict[str, str] = field(default_factory=dict)
    query: dict[str, list[str]] = field(default_factory=dict)
    headers: Any = field(default_factory=dict)
    json: Any = None
    # True for a request that did not come through ingress (only possible on routes registered with public=True).
    # Such a request carries no ingress identity: never trust identity headers there.
    public: bool = False

    def arg(self, name: str) -> str | None:
        """First query value or None."""
        values = self.query.get(name)
        return values[0] if values else None

    def body(self) -> dict[str, Any]:
        """The JSON object body ({} when none was sent); anything else is a bad_request."""
        if self.json is None:
            return {}
        if not isinstance(self.json, dict):
            raise ApiError("bad_request", "JSON object expected")
        return self.json


Handler = Callable[[Request], Any]


# A public route is a literal path: segments of plain characters only, no `{param}`, no dot segments, no trailing slash.
PUBLIC_PATH_RE = re.compile(r"^(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)+$")
# Served by the static handler or reserved for it: never public.
NEVER_PUBLIC = ("/icon", "/static")


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, str, list[str], Handler]] = []
        self._public: set[tuple[str, str]] = set()

    def add(self, method: str, pattern: str, handler: Handler, public: bool = False) -> None:
        """Register a route. `public=True` lets exactly this method and literal path through without ingress (for
        example a health check on an optionally published port); everything else stays ingress-only."""
        method = method.upper()
        if public:
            segments = pattern.split("/")
            if (
                not PUBLIC_PATH_RE.match(pattern)
                or ".." in segments
                or "." in segments
                or pattern == NEVER_PUBLIC[0]
                or pattern == NEVER_PUBLIC[1]
                or pattern.startswith(NEVER_PUBLIC[1] + "/")
            ):
                raise ValueError(f"public route needs a literal path outside /, /icon and /static: {pattern!r}")
            self._public.add((method, pattern))
        self._routes.append((method, pattern, pattern.strip("/").split("/"), handler))

    def is_public(self, method: str, path: str) -> bool:
        """True only when this exact method AND this exact raw path were registered with public=True.

        No normalisation, no prefix match, no case folding: `/api/health/`, `//api/health`, `/api/./health`,
        `/api/%68ealth` and `/API/health` are all not public. HEAD and OPTIONS are public only when registered."""
        return (method, path) in self._public

    def routes(self) -> list[tuple[str, str]]:
        return [(method, pattern) for method, pattern, _, _ in self._routes]

    def match(self, method: str, path: str) -> tuple[Handler, dict[str, str]]:
        """Return (handler, params); raise ApiError not_found (404) or method_not_allowed (405)."""
        segments = path.strip("/").split("/")
        path_matched = False
        for route_method, _, parts, handler in self._routes:
            if len(parts) != len(segments):
                continue
            params: dict[str, str] = {}
            for part, segment in zip(parts, segments):
                if part.startswith("{") and part.endswith("}"):
                    if not segment:
                        break
                    params[part[1:-1]] = urllib.parse.unquote(segment)
                elif part != segment:
                    break
            else:
                path_matched = True
                if route_method == method:
                    return handler, params
        if path_matched:
            raise ApiError("method_not_allowed", "method not allowed")
        raise ApiError("not_found", "not found")
