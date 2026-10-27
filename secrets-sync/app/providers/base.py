"""Provider contract shared by the engine and all providers (see docs/SPEC.md).

Providers are pure sources: they fetch and decrypt, they never write to /config and never log values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class Problem:
    """A configuration or runtime problem. Must never contain secret values."""

    code: str  # stable machine code, e.g. "bw_missing_client_id", "sops_not_encrypted"
    message: str  # human readable, English
    severity: str = "error"  # "error" | "warning"


@dataclass
class Snapshot:
    """Result of one successful fetch of one provider."""

    secrets: dict[str, str] = field(default_factory=dict)  # final keys for secrets.yaml
    files: dict[str, bytes] = field(default_factory=dict)  # relative path (below the files dir) -> content
    revision: str = ""  # source version, display only (e.g. bw revisionDate, sops file mtime)


class ProviderError(Exception):
    """Fetch failed. `code` is a stable machine code stored as `error_code` in state.json.

    The message must not contain secret values (no stderr dumps of tools that may echo input).
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class Provider(Protocol):
    name: str  # "bitwarden" | "sops" - also the key in options and in state.json `providers`

    def validate(self, cfg: Mapping[str, Any]) -> list[Problem]:
        """Check the provider's option block for completeness. No network, no subprocess, no file reads of secrets."""
        ...

    def fetch(self) -> Snapshot:
        """Fetch + decrypt. Raise ProviderError on failure. Every external call needs a timeout."""
        ...
