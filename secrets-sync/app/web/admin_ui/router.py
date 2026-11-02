"""Request, Download and Router of the admin-UI skeleton: `{param}` path segments, 404/405 as ApiError."""

from __future__ import annotations

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


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, str, list[str], Handler]] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        self._routes.append((method.upper(), pattern, pattern.strip("/").split("/"), handler))

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
