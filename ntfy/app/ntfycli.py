"""Write adapter around the ntfy CLI (contract C6). Core of plan 24-01; 24-02 adds the remaining methods.

Passwords travel only through the NTFY_PASSWORD environment variable, never through argv. Every call is a list-form
subprocess without a shell, and inputs are validated before spawning (argv-injection guard).
"""

from __future__ import annotations

import os
import subprocess
import threading
import time

from app.contract import USERNAME_RE


class NtfyCliError(Exception):
    """A failed CLI call; code is one of exists, not_found, invalid, provisioned, locked, other."""

    def __init__(self, code: str, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.returncode = returncode


def classify(text: str) -> str:
    """Classify the stdout text of a failed call (exit code is always 1, the reason is only in the text)."""
    low = text.lower()
    if "provisioned" in low:
        return "provisioned"
    if "already exists" in low:
        return "exists"
    if "does not exist" in low or "not found" in low:
        return "not_found"
    if "invalid argument" in low or "must be" in low:
        return "invalid"
    if "database is locked" in low:
        return "locked"
    return "other"


class NtfyCli:
    """Runs `ntfy user|access|token ...` against the live auth database."""

    _write_lock = threading.Lock()
    LOCK_RETRIES = 3
    LOCK_BACKOFF = 1.0

    def __init__(self, binary: str, config_file: str, auth_file: str, timeout: float = 20.0) -> None:
        self.binary = binary
        self.config_file = str(config_file)
        self.auth_file = str(auth_file)
        self.timeout = timeout

    def _run(self, args: list[str], password: str | None = None) -> str:
        env = dict(os.environ)
        env["NTFY_CONFIG_FILE"] = self.config_file
        env["NTFY_AUTH_FILE"] = self.auth_file
        env.pop("NTFY_PASSWORD", None)
        if password is not None:
            env["NTFY_PASSWORD"] = password
        message = ""
        with self._write_lock:
            for attempt in range(self.LOCK_RETRIES + 1):
                try:
                    proc = subprocess.run(  # noqa: S603 - list form, validated inputs, no shell
                        [self.binary, *args],
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                        env=env,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise NtfyCliError("other", "ntfy CLI timed out") from exc
                except OSError as exc:
                    raise NtfyCliError("other", f"cannot run ntfy CLI: {type(exc).__name__}") from exc
                if proc.returncode == 0:
                    return proc.stdout
                message = (proc.stdout or proc.stderr or "").strip()
                code = classify(message)
                if code == "locked" and attempt < self.LOCK_RETRIES:
                    time.sleep(self.LOCK_BACKOFF)
                    continue
                raise NtfyCliError(code, message, proc.returncode)
        raise NtfyCliError("other", message)  # pragma: no cover - loop always returns or raises

    def user_add(self, name: str, password: str, role: str = "user") -> None:
        """Add a user; an existing user raises NtfyCliError(exists) and keeps its password."""
        if not USERNAME_RE.match(name):
            raise NtfyCliError("invalid", "invalid user name")
        if role not in ("user", "admin"):
            raise NtfyCliError("invalid", "role must be user or admin")
        if not password:
            raise NtfyCliError("invalid", "password must not be empty")
        self._run(["user", "add", f"--role={role}", name], password=password)
