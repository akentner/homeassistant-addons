"""API error codes of the admin-UI skeleton: a stable machine code, its HTTP status and a human message."""

from __future__ import annotations

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
