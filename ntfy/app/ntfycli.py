"""Write adapter around the ntfy CLI (contract C6). Core of plan 24-01; 24-02 adds the remaining methods.

Passwords travel only through the NTFY_PASSWORD environment variable, never through argv. Every call is a list-form
subprocess without a shell, and inputs are validated before spawning (argv-injection guard).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from app.contract import (
    DURATION_RE,
    LABEL_RE,
    PERMISSIONS,
    TOKEN_RE,
    TOPIC_PATTERN_RE,
    USERNAME_RE,
)

log = logging.getLogger(__name__)
TOKEN_OUT_RE = re.compile(r"token (tk_[a-z0-9]{29}) created for user")


def sleep(seconds: float) -> None:
    """Module-level so tests can patch the retry backoff."""
    time.sleep(seconds)


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

    def __init__(self, binary: str, config_file: Path | str, auth_file: Path | str, timeout: float = 20.0) -> None:
        self.binary = binary
        self.config_file = str(config_file)
        self.auth_file = str(auth_file)
        self.timeout = timeout

    def _run(self, args: list[str], password: str | None = None) -> str:
        log.debug("ntfy %s", " ".join(args[:2]))
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
                    sleep(self.LOCK_BACKOFF)
                    continue
                raise NtfyCliError(code, message, proc.returncode)
        raise NtfyCliError("other", message)  # pragma: no cover - loop always returns or raises

    # --- validation (ValueError before any spawn) ---

    @staticmethod
    def _user(name: str, allow_everyone: bool = False) -> None:
        if allow_everyone and name == "everyone":
            return
        if not isinstance(name, str) or not USERNAME_RE.match(name):
            raise ValueError("invalid user name")

    @staticmethod
    def _password(password: str) -> None:
        if not password:
            raise ValueError("password must not be empty")

    @staticmethod
    def _role(role: str) -> None:
        if role not in ("user", "admin"):
            raise ValueError("role must be user or admin")

    @staticmethod
    def _topic(topic: str) -> None:
        if "%" in topic or not TOPIC_PATTERN_RE.match(topic):
            raise ValueError("invalid topic pattern")

    # --- users ---

    def user_add(self, name: str, password: str, role: str = "user") -> None:
        """Add a user; an existing user raises NtfyCliError(exists) and keeps its password."""
        self._user(name)
        self._role(role)
        self._password(password)
        self._run(["user", "add", f"--role={role}", name], password=password)

    def user_change_pass(self, name: str, password: str) -> None:
        self._user(name)
        self._password(password)
        self._run(["user", "change-pass", name], password=password)

    def user_delete(self, name: str) -> None:
        self._user(name)
        self._run(["user", "del", name])

    def user_change_role(self, name: str, role: str) -> None:
        """Note: ntfy deletes the ACL rows of a user promoted to admin; callers snapshot and re-apply."""
        self._user(name)
        self._role(role)
        self._run(["user", "change-role", name, role])

    # --- access ---

    def access_set(self, user: str, topic: str, permission: str) -> None:
        """Topic in CLI form (`*` wildcard); `everyone` addresses the anonymous user."""
        self._user(user, allow_everyone=True)
        self._topic(topic)
        if permission not in PERMISSIONS:
            raise ValueError("invalid permission")
        self._run(["access", user, topic, permission])

    def access_reset(self, user: str | None = None, topic: str | None = None) -> None:
        """Remove all rules, one user's rules or one rule. A reset of a missing rule still succeeds."""
        if user is None and topic is not None:
            raise ValueError("topic requires a user")
        args = ["access", "--reset"]
        if user is not None:
            self._user(user, allow_everyone=True)
            args.append(user)
            if topic is not None:
                self._topic(topic)
                args.append(topic)
        self._run(args)

    # --- tokens ---

    def token_add(self, user: str, label: str | None = None, expires: str | None = None) -> str:
        """Create a token and return its value (only place it is exposed besides AuthDb.reveal_token)."""
        self._user(user)
        args = ["token", "add"]
        if label:
            if not LABEL_RE.match(label):
                raise ValueError("invalid label")
            args.append(f"--label={label}")
        if expires:
            if not DURATION_RE.match(expires):
                raise ValueError("invalid expiry duration")
            args.append(f"--expires={expires}")
        out = self._run([*args, user])
        match = TOKEN_OUT_RE.search(out)
        if match is None:
            raise NtfyCliError("other", "unexpected token add output")
        return match.group(1)

    def token_remove(self, user: str, token: str) -> None:
        self._user(user)
        if not TOKEN_RE.match(token):
            raise ValueError("invalid token")
        self._run(["token", "remove", user, token])
