"""Bearer token verifiers of the admin-UI skeleton: only SHA-256 digests are kept and compared in constant time; token
values are never logged, printed or put into messages."""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol

# Floor for operator-chosen option tokens, decided by the user (D-11); also binding for ntfy Phase 25
OPTION_TOKEN_MIN_LENGTH = 16


class TokenVerifier(Protocol):
    """Anything that can tell whether a presented bearer token is valid."""

    def verify(self, presented: str) -> bool: ...


class OptionToken:
    """Token from an add-on `password` option; only its SHA-256 digest is kept in memory.

    The value must be printable ASCII without spaces (0x21..0x7E) and at least OPTION_TOKEN_MIN_LENGTH characters long;
    it is never stripped or normalised, and no error message contains it."""

    __slots__ = ("_digest",)

    def __init__(self, value: str | None) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("option token missing: the API stays off")
        if not all("\x21" <= char <= "\x7e" for char in value):
            raise ValueError("option token must be printable ASCII without spaces")
        if len(value) < OPTION_TOKEN_MIN_LENGTH:
            raise ValueError(f"option token shorter than {OPTION_TOKEN_MIN_LENGTH} characters")
        self._digest = hashlib.sha256(value.encode("ascii")).digest()

    def verify(self, presented: str) -> bool:
        try:
            candidate = hashlib.sha256(presented.encode("ascii")).digest()
        except (UnicodeEncodeError, AttributeError):
            return False
        # Equal-length digests: no TypeError on non-ASCII input and no length leak
        return hmac.compare_digest(candidate, self._digest)

    def __repr__(self) -> str:
        return "OptionToken(<redacted>)"
