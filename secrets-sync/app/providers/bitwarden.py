"""Bitwarden provider: pulls vault items through the `bw` CLI (see docs/SPEC.md, "Bitwarden provider").

Secrets reach `bw` only via environment variables, never argv. Tool stderr is never forwarded; failures are
mapped to stable error codes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Mapping

from app.providers.base import Problem, ProviderError, Snapshot

log = logging.getLogger("secrets_sync")

DEFAULT_SERVER = "https://bitwarden.com"
_TR_SPACE = str.maketrans({c: " " for c in "?:&,%@-"})
_TR_UNDERSCORE = str.maketrans({c: "_" for c in "[]{}#*!|> "})
_LOCKED_MARKERS = ("vault is locked", "not logged in")
_CRED_ENV = (
    ("client_id", "BW_CLIENTID", "bw_missing_client_id"),
    ("client_secret", "BW_CLIENTSECRET", "bw_missing_client_secret"),
    ("master_password", "BW_PASSWORD", "bw_missing_master_password"),
)


def sanitise(name: str) -> str:
    """Legacy key naming: tr '?:&,%@-' ' ' | tr '[]{}#*!|> ' '_' | tr -s '_' | lowercase."""
    return re.sub(r"_+", "_", name.translate(_TR_SPACE).translate(_TR_UNDERSCORE)).lower()


@dataclass
class _Result:
    rc: int
    stdout: str
    locked: bool  # stderr indicated an expired / locked session (stderr itself is discarded)


class _Expired(Exception):
    pass


class Provider:
    name = "bitwarden"

    def __init__(self, cfg: Mapping[str, Any], *, env: Mapping[str, str] | None = None, bw: str = "bw",
                 timeout: int = 60) -> None:
        self._cfg = dict(cfg)
        self._env = env
        self._bw = bw
        self._timeout = timeout
        self._session: str | None = None
        self.notices: list[tuple[str, str, str]] = []

    # ------------------------------------------------------------ contract

    def validate(self, cfg: Mapping[str, Any]) -> list[Problem]:
        problems: list[Problem] = []
        if not str(cfg.get("server_url") or "").startswith(("https://", "http://")):
            problems.append(Problem("bw_invalid_server_url", "bitwarden.server_url must be an http(s) URL"))
        for option, env_name, code in _CRED_ENV:
            if not (cfg.get(option) or self._environ().get(env_name)):
                problems.append(Problem(code, f"bitwarden.{option} is not set"))
        if cfg.get("key_style", "legacy") != "legacy":
            problems.append(Problem("bw_unsupported_key_style", "bitwarden.key_style must be 'legacy'"))
        notes_dir = str(cfg.get("notes_dir", "bitwarden"))
        if notes_dir.startswith("/") or "\\" in notes_dir or ".." in notes_dir.split("/"):
            problems.append(Problem("bw_invalid_notes_dir", "bitwarden.notes_dir must be a relative path"))
        return problems

    def fetch(self) -> Snapshot:
        self.notices = []
        for attempt in (1, 2):
            try:
                return self._fetch_once()
            except _Expired:
                self._session = None
                if attempt == 2:
                    raise ProviderError("bw_auth_failed", "bitwarden session expired twice") from None
        raise AssertionError("unreachable")

    # ------------------------------------------------------------ bw plumbing

    def _environ(self) -> Mapping[str, str]:
        return os.environ if self._env is None else self._env

    def _child_env(self) -> dict[str, str]:
        env = dict(self._environ())
        for option, env_name, _ in _CRED_ENV:
            if not env.get(env_name) and self._cfg.get(option):
                env[env_name] = str(self._cfg[option])
        env.setdefault("BITWARDENCLI_APPDATA_DIR", "/data/bw")
        env["BW_NOINTERACTION"] = "true"
        env["NODE_NO_WARNINGS"] = "1"
        env.pop("BW_SESSION", None)
        if self._session:
            env["BW_SESSION"] = self._session
        return env

    def _run(self, args: list[str]) -> _Result:
        try:
            cp = subprocess.run([self._bw, *args], env=self._child_env(), capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=self._timeout, check=False)
        except subprocess.TimeoutExpired:
            raise ProviderError("bw_timeout", f"bw {args[0]} timed out") from None
        except OSError:
            raise ProviderError("bw_not_found", "bw executable cannot be started") from None
        stderr = cp.stderr.decode("utf-8", "replace").lower()
        return _Result(cp.returncode, cp.stdout.decode("utf-8", "replace"),
                       cp.returncode != 0 and any(m in stderr for m in _LOCKED_MARKERS))

    @staticmethod
    def _norm_url(url: Any) -> str:
        return (str(url) if url else DEFAULT_SERVER).rstrip("/")

    def _status(self) -> dict[str, Any]:
        res = self._run(["status"])
        if res.rc != 0:
            raise ProviderError("bw_auth_failed", "bw status failed")
        try:
            data = json.loads(res.stdout)
        except ValueError:
            raise ProviderError("bw_invalid_json", "bw status returned invalid JSON") from None
        if not isinstance(data, dict):
            raise ProviderError("bw_invalid_json", "bw status returned unexpected JSON")
        return data

    def _ensure_session(self) -> None:
        status = self._status()
        state = status.get("status")
        want = self._norm_url(self._cfg.get("server_url"))
        if self._norm_url(status.get("serverUrl")) != want:
            if state != "unauthenticated":
                if self._run(["logout"]).rc != 0:
                    raise ProviderError("bw_auth_failed", "bw logout failed")
                self._session = None
            if self._run(["config", "server", want]).rc != 0:
                raise ProviderError("bw_auth_failed", "bw config server failed")
            state = "unauthenticated"
        if state == "unauthenticated":
            if self._run(["login", "--apikey"]).rc != 0:
                raise ProviderError("bw_auth_failed", "bw login failed")
            self._session = None
            state = "locked"
        if self._session is None or state != "unlocked":
            self._session = None
            res = self._run(["unlock", "--passwordenv", "BW_PASSWORD", "--raw"])
            token = res.stdout.strip()
            if res.rc != 0 or not token:
                raise ProviderError("bw_unlock_failed", "bw unlock failed")
            self._session = token

    def _fetch_once(self) -> Snapshot:
        self._ensure_session()
        sync = self._run(["sync"])
        if sync.locked:
            raise _Expired
        if sync.rc != 0:
            raise ProviderError("bw_sync_failed", "bw sync failed")
        args = ["list", "items"]
        if self._cfg.get("organization_id"):
            args += ["--organizationid", str(self._cfg["organization_id"])]
        if self._cfg.get("collection_id"):
            args += ["--collectionid", str(self._cfg["collection_id"])]
        listed = self._run(args)
        if listed.locked:
            raise _Expired
        if listed.rc != 0:
            raise ProviderError("bw_list_failed", "bw list items failed")
        try:
            items = json.loads(listed.stdout)
        except ValueError:
            raise ProviderError("bw_invalid_json", "bw list returned invalid JSON") from None
        if not isinstance(items, list):
            raise ProviderError("bw_invalid_json", "bw list returned unexpected JSON")
        return self._build(items)

    # ------------------------------------------------------------ mapping

    def _build(self, items: list[Any]) -> Snapshot:
        snap = Snapshot()
        owners: dict[str, str] = {}
        file_owners: dict[str, str] = {}
        skipped = 0
        revisions: list[str] = []
        notes_dir = str(self._cfg.get("notes_dir", "bitwarden")).strip("/")

        def put(key: str, value: Any, item_name: str) -> None:
            if value is None or value == "":
                return
            if key in owners:
                raise ProviderError("key_collision", f"key '{key}' produced by items '{owners[key]}' and "
                                                     f"'{item_name}'")
            owners[key] = item_name
            snap.secrets[key] = str(value)

        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            if isinstance(item.get("revisionDate"), str):
                revisions.append(item["revisionDate"])
            item_name = item["name"]
            base = sanitise(item_name)
            kind = item.get("type")
            if kind == 1:
                login = item.get("login") or {}
                put(f"{base}_username", login.get("username"), item_name)
                put(f"{base}_password", login.get("password"), item_name)
                put(f"{base}_notes", item.get("notes"), item_name)
                uris = [u.get("uri") for u in login.get("uris") or [] if isinstance(u, dict)]
                for number, uri in enumerate(uris, start=1):
                    put(f"{base}_uri_{number}", uri, item_name)
                for fld in item.get("fields") or []:
                    if isinstance(fld, dict) and isinstance(fld.get("name"), str):
                        put(f"{base}_{sanitise(fld['name'])}", fld.get("value"), item_name)
            elif kind == 2:
                note = item.get("notes")
                if note:
                    fname = base.replace("/", "_").replace("\\", "_")
                    if not os.path.splitext(fname)[1]:
                        fname += ".txt"
                    path = f"{notes_dir}/{fname}" if notes_dir else fname
                    if path in file_owners:
                        raise ProviderError("key_collision", f"file '{path}' produced by notes '"
                                                             f"{file_owners[path]}' and '{item_name}'")
                    file_owners[path] = item_name
                    snap.files[path] = str(note).encode("utf-8")
            else:
                skipped += 1
        if skipped:
            self.notices.append(("info", "item_skipped", f"{skipped} card/identity items skipped"))
        snap.revision = max(revisions, default="")
        return snap
