"""API error codes of the admin-UI skeleton: a stable machine code, its HTTP status and a human message."""

from __future__ import annotations

import re

ERROR_STATUS: dict[str, int] = {
    "bad_request": 400,
    "confirmation_required": 400,
    "ingress_only": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "protected": 409,
    "payload_too_large": 413,
    "internal_error": 500,
}


class ApiError(Exception):
    """An error with a stable machine code; the server renders it as {"error": code, "message": message}."""

    def __init__(self, code: str, message: str = "", status: int | None = None) -> None:
        if code not in ERROR_STATUS:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.status = status if status is not None else ERROR_STATUS[code]


_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


def register_error_code(code: str, status: int) -> None:
    """Extend the stable error table; re-registering the same pair is a no-op, a different status is an error."""
    if not isinstance(code, str) or not _CODE_RE.match(code):
        raise ValueError(f"malformed error code: {code!r}")
    if isinstance(status, bool) or not isinstance(status, int) or not 400 <= status <= 599:
        raise ValueError(f"invalid status for {code}: {status!r}")
    existing = ERROR_STATUS.get(code)
    if existing is None:
        ERROR_STATUS[code] = status
    elif existing != status:
        raise ValueError(f"error code {code} already registered with status {existing}")
