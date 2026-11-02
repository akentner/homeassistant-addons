"""Origin sidecar (contract C4): which source created a user, ACL rule or token (gui | options | iac).

ntfy's auth.db has no such field, so the add-on keeps `<data>/origins.json`. Entries without a record count as `gui`.
A corrupt file never crashes the add-on: it is renamed to `origins.json.corrupt` and the store starts empty.
"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.contract import ORIGINS

LOG = logging.getLogger("ntfy.origins")

SCHEMA = 1
DEFAULT_ORIGIN = "gui"
TOKEN_ID_RE = re.compile(r"^[0-9a-f]{12}$")
_SECTIONS = ("users", "acls", "tokens", "acl_stash")


def _empty() -> dict[str, Any]:
    return {"schema": SCHEMA, "users": {}, "acls": {}, "tokens": {}, "acl_stash": {}}


def _check_origin(origin: str) -> str:
    if origin not in ORIGINS:
        raise ValueError(f"unknown origin: {origin!r}")
    return origin


def _check_token_id(value: str) -> str:
    if not isinstance(value, str) or not TOKEN_ID_RE.match(value):
        raise ValueError("invalid token id")
    return value


def _valid_document(doc: Any) -> bool:
    """Shape check; every stored origin must be a known one."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return False
    for section in _SECTIONS:
        if not isinstance(doc.get(section), dict):
            return False
    if not all(isinstance(k, str) and v in ORIGINS for k, v in doc["users"].items()):
        return False
    for section in ("acls", "tokens"):
        for user, inner in doc[section].items():
            if not isinstance(user, str) or not isinstance(inner, dict):
                return False
            if not all(isinstance(k, str) and v in ORIGINS for k, v in inner.items()):
                return False
    for user, rules in doc["acl_stash"].items():
        if not isinstance(user, str) or not isinstance(rules, list):
            return False
        for rule in rules:
            if not isinstance(rule, dict) or not isinstance(rule.get("topic"), str):
                return False
            if not isinstance(rule.get("permission"), str) or rule.get("origin") not in ORIGINS:
                return False
    return True


class OriginStore:
    """Thread-safe, write-through origin store."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._sig = self._signature()
        self._doc = self._load()

    # The bootstrap process and the GUI process share the sidecar: every access first reloads the file when another
    # process replaced it, and every write runs under an exclusive flock so no process overwrites the other's records.

    def _signature(self) -> tuple[int, int, int] | None:
        try:
            st = self._path.stat()
        except OSError:
            return None
        return (st.st_ino, st.st_mtime_ns, st.st_size)

    def _refresh(self) -> None:
        sig = self._signature()
        if sig != self._sig:
            self._sig = sig
            self._doc = self._load()

    @contextlib.contextmanager
    def _read(self) -> Any:
        with self._lock:
            self._refresh()
            yield

    @contextlib.contextmanager
    def _txn(self) -> Any:
        with self._lock:
            lock_path = self._path.with_name(self._path.name + ".lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with open(lock_path, "a", encoding="utf-8") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                try:
                    self._refresh()
                    yield
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    # --- persistence -----------------------------------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return _empty()
        except OSError:
            LOG.warning("origins file unreadable, starting empty")
            return _empty()
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = None
        if _valid_document(doc):
            return doc
        LOG.warning("origins file is corrupt, moved to %s.corrupt and starting empty", self._path.name)
        try:
            os.replace(self._path, self._path.with_name(self._path.name + ".corrupt"))
        except OSError:
            pass
        return _empty()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".origins-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                os.fchmod(handle.fileno(), 0o600)
                json.dump(self._doc, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
            self._sig = self._signature()
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # --- reads -----------------------------------------------------------------------------------------------------

    def get_user(self, name: str) -> str:
        with self._read():
            return self._doc["users"].get(name, DEFAULT_ORIGIN)

    def get_acl(self, user: str, topic: str) -> str:
        with self._read():
            return self._doc["acls"].get(user, {}).get(topic, DEFAULT_ORIGIN)

    def get_token(self, user: str, token_id_: str) -> str:
        with self._read():
            return self._doc["tokens"].get(user, {}).get(token_id_, DEFAULT_ORIGIN)

    def snapshot(self) -> dict[str, Any]:
        with self._read():
            return copy.deepcopy(self._doc)

    # --- writes ----------------------------------------------------------------------------------------------------

    def set_user(self, name: str, origin: str) -> None:
        _check_origin(origin)
        with self._txn():
            self._doc["users"][name] = origin
            self._save()

    def set_acl(self, user: str, topic: str, origin: str) -> None:
        _check_origin(origin)
        with self._txn():
            self._doc["acls"].setdefault(user, {})[topic] = origin
            self._save()

    def set_token(self, user: str, token_id_: str, origin: str) -> None:
        _check_origin(origin)
        _check_token_id(token_id_)
        with self._txn():
            self._doc["tokens"].setdefault(user, {})[token_id_] = origin
            self._save()

    def drop_user(self, name: str) -> None:
        """Remove the user and cascade to its rules, tokens and stash."""
        with self._txn():
            for section in _SECTIONS:
                self._doc[section].pop(name, None)
            self._save()

    def drop_acl(self, user: str, topic: str) -> None:
        with self._txn():
            rules = self._doc["acls"].get(user)
            if rules is not None:
                rules.pop(topic, None)
                if not rules:
                    del self._doc["acls"][user]
            self._save()

    def drop_token(self, user: str, token_id_: str) -> None:
        with self._txn():
            tokens = self._doc["tokens"].get(user)
            if tokens is not None:
                tokens.pop(token_id_, None)
                if not tokens:
                    del self._doc["tokens"][user]
            self._save()

    def clear_acls(self) -> None:
        with self._txn():
            self._doc["acls"] = {}
            self._save()

    def clear_all(self) -> None:
        with self._txn():
            self._doc = _empty()
            self._save()

    def stash_acl(self, user: str, rules: list[dict]) -> None:
        """Remember a user's rules (topic, permission, origin) so they can be restored later."""
        clean = []
        for rule in rules:
            clean.append(
                {
                    "topic": str(rule["topic"]),
                    "permission": str(rule["permission"]),
                    "origin": _check_origin(rule.get("origin", DEFAULT_ORIGIN)),
                }
            )
        with self._txn():
            self._doc["acl_stash"][user] = clean
            self._save()

    def pop_acl_stash(self, user: str) -> list[dict]:
        with self._txn():
            rules = self._doc["acl_stash"].pop(user, [])
            self._save()
            return rules

    def prune(
        self,
        live_users: set[str],
        live_acls: set[tuple[str, str]],
        live_tokens: set[tuple[str, str]],
    ) -> int:
        """Drop records for users, rules and tokens that no longer exist; returns the number removed."""
        removed = 0
        with self._txn():
            for name in [u for u in self._doc["users"] if u not in live_users]:
                del self._doc["users"][name]
                removed += 1
            for section, live in (("acls", live_acls), ("tokens", live_tokens)):
                for user in list(self._doc[section]):
                    inner = self._doc[section][user]
                    for key in [k for k in inner if (user, k) not in live]:
                        del inner[key]
                        removed += 1
                    if not inner:
                        del self._doc[section][user]
            if removed:
                self._save()
        return removed
