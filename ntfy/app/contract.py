"""Shared contract of the ntfy add-on (plan 24-01, sections C1-C13).

Single source for paths, options, error codes and mapping helpers. Every other module codes against this file; it
imports nothing from the rest of the app (no ntfycli, no authdb) so that it stays importable everywhere.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- C1 ports, schema ----------------------------------------------------------------------------------------------

NTFY_PORT = 8000
GUI_PORT = 8099
INGRESS_REMOTE = "172.30.32.2"
SUPPORTED_AUTH_SCHEMA = 10

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_][-_.+@a-zA-Z0-9]{0,63}$")


@dataclass(frozen=True)
class Paths:
    """C1: every file the add-on touches, derived from one data directory."""

    data_dir: Path
    options_file: Path
    auth_db: Path
    cache_db: Path
    server_yml: Path
    origins_file: Path
    backup_dir: Path
    attachment_dir: Path

    @classmethod
    def for_dir(cls, data_dir: Path | str, options_file: Path | str | None = None) -> "Paths":
        base = Path(data_dir)
        return cls(
            data_dir=base,
            options_file=Path(options_file) if options_file else base / "options.json",
            auth_db=base / "auth.db",
            cache_db=base / "cache.db",
            server_yml=base / "server.yml",
            origins_file=base / "origins.json",
            backup_dir=base / "backups",
            attachment_dir=base / "attachments",
        )

    @classmethod
    def from_env(cls) -> "Paths":
        return cls.for_dir(os.environ.get("NTFY_DATA_DIR", "/data"), os.environ.get("NTFY_OPTIONS") or None)


# --- C2 options ----------------------------------------------------------------------------------------------------

DEFAULT_OPTIONS: dict[str, Any] = {
    "base_url": "https://ntfy.example.com",
    "enable_web_ui": True,
    "behind_proxy": True,
    "auth_default_access": "deny-all",
    "admin_user": "admin",
    "admin_password": "",
    "baseline_users": [],
    "baseline_overwrite_passwords": False,
    "backup_keep": 10,
    "cache_duration": "12h",
    "attachments_enabled": True,
    "attachment_total_size_limit": "1G",
    "attachment_file_size_limit": "15M",
    "attachment_expiry_duration": "12h",
    "log_level": "info",
}


class OptionsError(ValueError):
    """options.json holds a value of the wrong type."""


@dataclass(frozen=True)
class BaselineUser:
    username: str
    password: str
    topic: str
    write_access: bool


@dataclass(frozen=True)
class Options:
    base_url: str = DEFAULT_OPTIONS["base_url"]
    enable_web_ui: bool = True
    behind_proxy: bool = True
    auth_default_access: str = "deny-all"
    admin_user: str = "admin"
    admin_password: str = field(default="", repr=False)
    baseline_users: tuple[BaselineUser, ...] = ()
    baseline_overwrite_passwords: bool = False
    backup_keep: int = 10
    cache_duration: str = "12h"
    attachments_enabled: bool = True
    attachment_total_size_limit: str = "1G"
    attachment_file_size_limit: str = "15M"
    attachment_expiry_duration: str = "12h"
    log_level: str = "info"


def _get(data: dict[str, Any], key: str, kind: type) -> Any:
    """Return data[key] checked against kind, or the default when the key is absent."""
    if key not in data:
        return DEFAULT_OPTIONS[key]
    value = data[key]
    if kind is int and isinstance(value, bool):
        raise OptionsError(f"option {key} must be int")
    if not isinstance(value, kind):
        raise OptionsError(f"option {key} must be {kind.__name__}")
    return value


def _get_optional_str(data: dict[str, Any], key: str) -> str:
    """Optional string option: absent -> default, null or empty -> '' (setting omitted)."""
    if key not in data:
        return DEFAULT_OPTIONS[key]
    value = data[key]
    if value is None:
        return ""
    if not isinstance(value, str):
        raise OptionsError(f"option {key} must be str")
    return value


def parse_options(data: dict[str, Any]) -> Options:
    """Build Options from a parsed options object; unknown keys are ignored."""
    users: list[BaselineUser] = []
    raw_users = data.get("baseline_users") or []
    if not isinstance(raw_users, list):
        raise OptionsError("option baseline_users must be a list")
    for entry in raw_users:
        if not isinstance(entry, dict):
            raise OptionsError("option baseline_users entries must be objects")
        write = entry.get("write_access", False)
        if not isinstance(write, bool):
            raise OptionsError("baseline_users.write_access must be bool")
        users.append(
            BaselineUser(
                username=str(entry.get("username", "")),
                password=str(entry.get("password", "")),
                topic=str(entry.get("topic", "")),
                write_access=write,
            )
        )
    return Options(
        base_url=_get(data, "base_url", str),
        enable_web_ui=_get(data, "enable_web_ui", bool),
        behind_proxy=_get(data, "behind_proxy", bool),
        auth_default_access=_get(data, "auth_default_access", str),
        admin_user=_get(data, "admin_user", str),
        admin_password=_get(data, "admin_password", str),
        baseline_users=tuple(users),
        baseline_overwrite_passwords=_get(data, "baseline_overwrite_passwords", bool),
        backup_keep=_get(data, "backup_keep", int),
        cache_duration=_get(data, "cache_duration", str),
        attachments_enabled=_get(data, "attachments_enabled", bool),
        attachment_total_size_limit=_get_optional_str(data, "attachment_total_size_limit"),
        attachment_file_size_limit=_get_optional_str(data, "attachment_file_size_limit"),
        attachment_expiry_duration=_get_optional_str(data, "attachment_expiry_duration"),
        log_level=_get(data, "log_level", str),
    )


def load_options(path: Path | str) -> Options:
    """Read options.json (C2). A missing file gives the defaults; a non-object or wrong types raise OptionsError."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except (OSError, ValueError) as exc:
        raise OptionsError(f"cannot read options: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise OptionsError("options must be a JSON object")
    return parse_options(data)


# --- C8 API errors -------------------------------------------------------------------------------------------------

ERROR_STATUS: dict[str, int] = {
    "bad_request": 400,
    "confirmation_required": 400,
    "ingress_only": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "protected": 409,
    "payload_too_large": 413,
    "ntfy_error": 502,
    "db_unavailable": 503,
    "db_unsupported": 503,
    "locked": 503,
    "internal_error": 500,
}


class ApiError(Exception):
    """An error with a stable machine code; the router renders it as {"error": code, "message": message}."""

    def __init__(self, code: str, message: str = "", status: int | None = None) -> None:
        if code not in ERROR_STATUS:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.status = status if status is not None else ERROR_STATUS[code]


# --- C7 CLI error mapping (primitives only: this module must not import ntfycli) -----------------------------------

CLI_ERROR_TO_API: dict[str, str] = {
    "exists": "conflict",
    "not_found": "not_found",
    "invalid": "bad_request",
    "provisioned": "protected",
    "locked": "locked",
    "other": "ntfy_error",
}


def api_error_from_cli(code: str, message: str) -> ApiError:
    """Map a NtfyCliError code to the API error."""
    return ApiError(CLI_ERROR_TO_API.get(code, "ntfy_error"), message)


# --- C5 permission and user mapping --------------------------------------------------------------------------------


def perm_from_flags(read: int | bool, write: int | bool) -> str:
    """(read, write) flags of user_access to rw / ro / wo / deny."""
    return {(1, 1): "rw", (1, 0): "ro", (0, 1): "wo", (0, 0): "deny"}[(1 if read else 0, 1 if write else 0)]


def db_user_to_api(name: str) -> str:
    """The anonymous DB user `*` is `everyone` in the API."""
    return "everyone" if name == "*" else name
