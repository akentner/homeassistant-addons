"""Bearer token verifiers of the admin-UI skeleton: only SHA-256 digests are kept and compared in constant time; token
values are never logged, printed or put into messages."""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol


class TokenVerifier(Protocol):
    """Anything that can tell whether a presented bearer token is valid."""

    def verify(self, presented: str) -> bool: ...


class OptionToken:
    """Token from an add-on `password` option; only its SHA-256 digest is kept in memory."""

    def __init__(self, value: str | None) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("option token missing: the API stays off")
        try:
            raw = value.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError("option token must be printable ASCII without spaces") from None
        self._digest = hashlib.sha256(raw).digest()

    def verify(self, presented: str) -> bool:
        try:
            candidate = hashlib.sha256(presented.encode("ascii")).digest()
        except (UnicodeEncodeError, AttributeError):
            return False
        # Equal-length digests: no TypeError on non-ASCII input and no length leak
        return hmac.compare_digest(candidate, self._digest)

    def __repr__(self) -> str:
        return "OptionToken(<redacted>)"
