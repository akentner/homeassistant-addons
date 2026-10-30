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
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_ITEM_TYPES = {1: "login", 2: "note", 3: "card", 4: "identity"}
_LOCKED_MARKERS = ("vault is locked", "not logged in")
_CRED_ENV = (
    ("client_id", "BW_CLIENTID", "bw_missing_client_id"),
    ("client_secret", "BW_CLIENTSECRET", "bw_missing_client_secret"),
    ("master_password", "BW_PASSWORD", "bw_missing_master_password"),
)


def _export_private(item: dict[str, Any]) -> bool:
    """An SSH-key item exports its private key only with the custom field `secrets_sync_export_private` = true."""
    for fld in item.get("fields") or []:
        if (isinstance(fld, dict) and str(fld.get("name", "")).strip().lower() == "secrets_sync_export_private"
                and str(fld.get("value", "")).strip().lower() == "true"):
            return True
    return False


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
                raise ProviderError("bw_auth_failed", f"bw login failed on server {want}: check server_url, client_id, client_secret")
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
        org_id = self._resolve("organization_id", "organizations", None)
        if org_id:
            args += ["--organizationid", org_id]
        coll_id = self._resolve("collection_id", "collections", org_id)
        if coll_id:
            args += ["--collectionid", coll_id]
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
        filtered = len(args) > 2
        # Only active items: archived and trashed ones must never become secrets
        active = [i for i in items if not (isinstance(i, dict) and (i.get("archivedDate") or i.get("deletedDate")))]
        inactive = len(items) - len(active)
        items = active
        log.info("bitwarden: %d items listed (organization filter %s, collection filter %s)", len(items),
                 "set" if self._cfg.get("organization_id") else "off",
                 "set" if self._cfg.get("collection_id") else "off")
        if inactive:
            log.info("bitwarden: %d archived/trashed items ignored", inactive)
            self.notices.append(("info", "item_inactive", f"{inactive} archived/trashed items ignored"))
        if not items and filtered and not inactive:
            self.notices.append(("warning", "bw_filter_empty", "the organization/collection filter matched no "
                                 "items: check organization_id / collection_id (log_level debug lists what is visible)"))
        if log.isEnabledFor(logging.DEBUG):
            self._debug_overview(items)
        return self._build(items)

    # ------------------------------------------------------------ debug

    def _resolve(self, option: str, what: str, org_id: str | None) -> str | None:
        """Accept a UUID or the display name of an organization/collection and return the UUID."""
        wanted = str(self._cfg.get(option) or "").strip()
        if not wanted or _UUID.match(wanted):
            return wanted or None
        found = self._json_list(["list", what])
        if found is None:
            raise ProviderError("bw_list_failed", f"bw list {what} failed (needed to resolve {option})")
        if org_id:
            found = [f for f in found if f.get("organizationId") == org_id]
        for match in (lambda n: n == wanted, lambda n: n.casefold() == wanted.casefold()):
            hits = [f for f in found if isinstance(f.get("name"), str) and match(f["name"])]
            if len(hits) == 1:
                return str(hits[0].get("id"))
            if len(hits) > 1:
                raise ProviderError(f"bw_{option}_ambiguous", f"{option} '{wanted}' matches {len(hits)} {what}; "
                                    "use the UUID (log_level debug lists the ids)")
        names = ", ".join(repr(f.get("name")) for f in found)
        raise ProviderError(f"bw_{option}_not_found", f"{option} '{wanted}' not found; the service user sees "
                            f"these {what}: {names or 'none'}")

    def _json_list(self, args: list[str]) -> list[dict[str, Any]] | None:
        res = self._run(args)
        if res.rc != 0:
            return None
        try:
            data = json.loads(res.stdout)
        except ValueError:
            return None
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else None

    def _debug_overview(self, selected: list[Any]) -> None:
        """Log organizations, collections and item names with ids. Never values or any other item field."""
        picked = {i.get("id") for i in selected if isinstance(i, dict)}
        orgs = self._json_list(["list", "organizations"])
        log.debug("bitwarden debug: organizations: %s", "unavailable" if orgs is None else len(orgs))
        for org in orgs or []:
            log.debug("bitwarden debug: org id=%s name=%r", org.get("id"), org.get("name"))
        colls = self._json_list(["list", "collections"])
        log.debug("bitwarden debug: collections: %s", "unavailable" if colls is None else len(colls))
        for coll in colls or []:
            log.debug("bitwarden debug: collection id=%s name=%r org=%s", coll.get("id"), coll.get("name"),
                      coll.get("organizationId"))
        everything = self._json_list(["list", "items"])
        log.debug("bitwarden debug: vault items (unfiltered): %s", "unavailable" if everything is None
                  else len(everything))
        for item in everything or []:
            log.debug("bitwarden debug: item %r type=%s org=%s collections=%s selected=%s", item.get("name"),
                      _ITEM_TYPES.get(item.get("type"), item.get("type")), item.get("organizationId") or "-",
                      ",".join(item.get("collectionIds") or []) or "-", item.get("id") in picked)

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
            elif kind == 5:
                ssh = item.get("sshKey") or {}
                put(f"{base}_public_key", ssh.get("publicKey"), item_name)
                if _export_private(item):
                    put(f"{base}_private_key", ssh.get("privateKey"), item_name)
            else:
                skipped += 1
        if skipped:
            self.notices.append(("info", "item_skipped", f"{skipped} card/identity items skipped"))
        snap.revision = max(revisions, default="")
        return snap
