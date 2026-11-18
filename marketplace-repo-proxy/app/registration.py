"""Self-registration of the proxy's `local` store URLs with the Supervisor (MRP-08, D-05 to D-07, D-28).

One system user `local` (source `system`) per configured repository. After every sync cycle the registration pass
adds the internal store URL `http://{hostname}:8080/repo/{owner}/{repo}/{hash}` of every repository whose last sync is
`ok` when `GET /store/repositories` does not list its store slug. The pass reports facts (`in_store`, `error`) to the
state writer, which derives the registration value and message. A failing Supervisor never ends the pass; the next
cycle starts again with `GET`. The pass never removes a store repository (D-27): it only drops leftovers and
unconfigured repositories whose store slug is no longer listed and revokes their `local` labels.

Store reload (MRP-09, D-08): after the pass, one `POST /store/reload` when the served head of a repository whose
`local` URL was in the store before the pass changed (D-28: `in_store`, whatever the registration value). At most one
reload per sync interval: a change inside a closed window sets `pending`, which `run_due` sends from the sync wait loop
once the window opens. `pending` is persisted in /data/supervisor.json; the window clock is in memory, so the first
window after a restart is open.

Operator requests (MRP-10, D-02, D-03): `mrp` never calls the Supervisor. It writes
`{supervisor_requests_dir}/{16 hex}.json` with exactly `id`, `action`, `repository`, `created`; `run_due` unlinks each
file, validates it as untrusted input and executes it once, recording the result in supervisor.json `requests`.
`remove` sends `DELETE` only for store slugs recorded in supervisor.json from the proxy's own `local` URLs (the current
registration or a leftover), never for a slug taken from the store list. A refusal (`used by installed apps`) becomes
a leftover that is never forced and never retried by the loop (D-09, D-10); only a new request tries again.

`rotate` (D-09, D-11) renames the current `local` entry to `local.{old slug}` and adds a new `local` entry in one locked
write, adds the new URL to the store first and, only after a 200/409, revokes the retired entry at once (the old URL
answers 404 from the next request; nothing skips this step) and then tries to `DELETE` the old slug. A failed add rolls
the rotation back in one locked write. A refusal leaves the old store repository as a leftover (`revoked: true`).

Leftover detection (D-10, D-11, D-28; report only, never a DELETE): a retired `local.{slug}` entry found by a pass is
the remnant of a rotation stopped between the retire write and the revoke; the pass revokes it and, while its slug is
listed, records leftover `interrupted`. A recorded slug that differs from the slug the pass records now and is still
listed (hand edit of access.json, hostname change) becomes leftover `orphaned`. Only `mrp local remove` deletes them.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from app.access import HASH_RE, AccessError, AccessStore, is_reserved
from app.gitops import sanitize
from app.jsonio import utc_timestamp
from app.options import Options, RepoSpec, parse_repository
from app.paths import Paths
from app.supervisor import CallResult, SupervisorClient, SupervisorRefused, mask_text, store_slug
from app.supervisor_state import SupervisorStateWriter
from app.urls import internal_base, masked_store_url, store_url

LOCAL_USER = "local"
LOG = logging.getLogger("mrp.store")
REQUEST_ACTIONS = ("remove", "rotate")
REQUEST_NAME_RE = re.compile(r"[0-9a-f]{16}\.json")
REQUEST_KEYS = frozenset({"id", "action", "repository", "created"})
REQUEST_MAX_BYTES = 4096
_ID_RE = re.compile(r"[0-9a-f]{16}")
_ACTION_RE = re.compile(r"[a-z][a-z_]{0,31}")
_SLUG_RE = re.compile(r"[0-9a-f]{8}")
RETIRED_RE = re.compile(LOCAL_USER + r"\.([0-9a-f]{8})")  # `local.{old store slug}`: only between retire and revoke
INVALID_REQUEST = "ignored an invalid supervisor request file"


def _failure(result: CallResult, http_code: str) -> tuple[str, int | None]:
    """Error code and HTTP status of a failed call (`timeout`/`unreachable` without an HTTP answer)."""
    if result.status == 0:
        return (result.message if result.message in ("timeout", "unreachable") else "unreachable"), None
    return http_code, result.status


def _refused_code(exc: SupervisorRefused) -> str:
    return "token_missing" if exc.code == "token_missing" else "internal_error"


class Registrar:
    """Registration pass of the sync process; the only caller of the Supervisor client."""

    def __init__(
        self,
        paths: Paths,
        options: Options,
        client: SupervisorClient,
        hostname: str,
        log: logging.Logger | None = None,
        *,
        state: SupervisorStateWriter | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
    ) -> None:
        self.paths = paths
        self.options = options
        self.client = client
        self.hostname = hostname
        self.log = log or LOG
        self.base = internal_base(hostname)
        self.access = AccessStore(paths, self.log)
        # Written at construction (D-29): the document exists before the first Supervisor call
        self.state = state or SupervisorStateWriter(
            paths, hostname=hostname, register_local=options.register_local, specs=options.repositories
        )
        self.clock = clock
        self.wall = wall
        self.interval_seconds = options.sync_interval * 60
        self.last_reload_at: float | None = None
        self.reload_pending = self.state.reload_state()["pending"] is True
        self._stuck: set[str] = set()  # request entries that could not be unlinked: never wake the loop for them
        previous = self.state.previous_hostname
        if previous is not None and previous.lower() != hostname.lower():
            self.log.warning("store: hostname changed since the last run; earlier store URLs are reported as leftovers")

    def local_entry(self, spec: RepoSpec) -> dict | None:
        """The repository's `local` access entry, only when its hash is valid."""
        entry = self.access.get(spec.slug, LOCAL_USER)
        if entry is None or not isinstance(entry.get("hash"), str) or not HASH_RE.fullmatch(entry["hash"]):
            return None
        return entry

    def ensure_local(self, spec: RepoSpec) -> dict:
        """The existing `local` entry or a new one; its link exists before the Supervisor clones."""
        entry = self.local_entry(spec)
        if entry is not None:
            return entry
        try:
            self.access.add(spec.slug, LOCAL_USER, source="system", specs=self.options.repositories)
        except AccessError as exc:
            if exc.code != "user_exists":
                raise
        entry = self.local_entry(spec)
        if entry is None:
            raise RuntimeError("local access entry is unusable")
        return entry

    def local_url(self, spec: RepoSpec, hash_: str) -> str:
        return store_url(self.base, spec.owner, spec.name, hash_)

    def _masked(self, spec: RepoSpec, entry: dict | None) -> tuple[str | None, str]:
        if entry is None:
            return None, ""
        return (
            store_slug(self.local_url(spec, entry["hash"])),
            masked_store_url(self.base, spec.owner, spec.name, entry["hash"]),
        )

    def _had_error(self, spec: RepoSpec) -> bool:
        current = self.state.repository(spec.slug)
        return bool(current and current.get("error"))

    def _list_failed(self, wanting: list[RepoSpec], entries: dict[str, dict | None], code: str, status: int | None,
                     label: str) -> None:
        entering = False
        for spec in wanting:
            entering = entering or not self._had_error(spec)
            current = self.state.repository(spec.slug) or {}
            slug, masked = self._masked(spec, entries[spec.key])
            self.state.set_repository(
                spec.slug,
                in_store=bool(current.get("in_store")),
                error=code,
                error_status=status,
                store_slug=slug,
                masked_url=masked,
            )
        if entering:
            self.log.warning("store list unavailable: %s", label)

    def register_pass(self, status_doc: dict) -> None:
        """Check (and add when missing) the `local` URL of every configured repository; one GET per pass."""
        statuses: dict[str, Any] = {}
        items = status_doc.get("repositories") if isinstance(status_doc, dict) else None
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("repository"), str):
                statuses[item["repository"].lower()] = item.get("status")
        specs = self.options.repositories
        entries = {spec.key: self.local_entry(spec) for spec in specs}
        wants = {spec.key: self.options.register_local and statuses.get(spec.key) == "ok" for spec in specs}
        recorded = bool(self.state.leftovers() or self.state.unconfigured_repositories())
        remnants = {spec.key: self._retired_entries(spec) for spec in specs}
        before = {spec.key: self.state.repository(spec.slug) or {} for spec in specs}

        if not any(entries.values()) and not any(wants.values()) and not recorded and not any(remnants.values()):
            for spec in specs:
                self.state.set_repository(spec.slug, in_store=False, error=None)
            return

        wanting = [spec for spec in specs if wants[spec.key]]
        try:
            result = self.client.list_repositories()
        except SupervisorRefused as exc:
            code = _refused_code(exc)
            self._list_failed(wanting, entries, code, None, code)
            return
        if not result.ok or not isinstance(result.data, list):
            self.state.set_contact(result.status, result.message or None)
            if result.status == 0:
                code, status = _failure(result, "store_list_unavailable")
                label = code
            else:
                code, status, label = "store_list_unavailable", result.status, str(result.status)
            self._list_failed(wanting, entries, code, status, label)
            return
        self.state.set_contact(result.status, None)
        present = {
            item["slug"] for item in result.data if isinstance(item, dict) and isinstance(item.get("slug"), str)
        }
        if recorded:
            self._resolve_gone(present)
            entries = {spec.key: self.local_entry(spec) for spec in specs}

        for spec in specs:
            try:
                self._revoke_interrupted(spec, remnants[spec.key], present)
                self._register_one(spec, wants[spec.key], entries[spec.key], present)
            except Exception as exc:  # one repository must not end the pass for the others
                had_error = self._had_error(spec)
                current = self.state.repository(spec.slug) or {}
                slug, masked = self._masked(spec, self.local_entry(spec))
                self.state.set_repository(
                    spec.slug,
                    in_store=bool(current.get("in_store")),
                    error="internal_error",
                    store_slug=slug,
                    masked_url=masked,
                )
                if not had_error:
                    self.log.warning("store: registration of %s failed: internal error (%s)", spec.slug,
                                     type(exc).__name__)
            try:
                self._report_orphaned(spec, before[spec.key], present)
            except Exception as exc:
                self.log.warning("store: leftover check of %s failed: internal error (%s)", spec.slug,
                                 type(exc).__name__)

    def _retired_entries(self, spec: RepoSpec) -> list[dict]:
        """Access entries `local.{slug}` of one repository: remnants of an interrupted rotation (a completed rotation
        never leaves one, D-11)."""
        return [
            entry
            for entry in self.access.list_entries(spec.slug)
            if isinstance(entry.get("user"), str) and RETIRED_RE.fullmatch(entry["user"])
        ]

    def _has_leftover(self, slug: str) -> bool:
        return any(item.get("store_slug") == slug for item in self.state.leftovers())

    def _revoke_interrupted(self, spec: RepoSpec, remnants: list[dict], present: set[str]) -> None:
        """Revoke every retired entry at once (D-11); a listed slug without a leftover becomes `interrupted`."""
        for entry in remnants:
            user = entry["user"]
            slug = RETIRED_RE.fullmatch(user).group(1)  # type: ignore[union-attr]
            hash_ = entry.get("hash")
            masked = (
                masked_store_url(self.base, spec.owner, spec.name, hash_)
                if isinstance(hash_, str) and HASH_RE.fullmatch(hash_)
                else ""
            )
            self.access.revoke(spec.slug, user, specs=self.options.repositories, system=True)
            self.log.info("store: %s retired URL of an interrupted rotation revoked", spec.slug)
            if slug in present and not self._has_leftover(slug):
                self.state.add_leftover(
                    repository=spec.slug, store_slug=slug, user=user, masked_url=masked, reason="interrupted",
                    revoked=True,
                )
                self.log.warning("store: %s leftover %s (%s)", spec.slug, slug, "interrupted")

    def _report_orphaned(self, spec: RepoSpec, before: dict, present: set[str]) -> None:
        """A slug recorded before the pass that is still listed but no longer the current one becomes `orphaned`
        (hand edit of access.json, hostname change); never deleted automatically."""
        recorded = before.get("store_slug")
        if not isinstance(recorded, str) or not _SLUG_RE.fullmatch(recorded) or recorded not in present:
            return
        current = (self.state.repository(spec.slug) or {}).get("store_slug")
        if not isinstance(current, str) or current == recorded or self._has_leftover(recorded):
            return
        if self.access.get(spec.slug, f"{LOCAL_USER}.{recorded}") is not None:
            return  # a retired entry covers it
        masked = before.get("masked_url")
        self.state.add_leftover(
            repository=spec.slug, store_slug=recorded, user=None,
            masked_url=masked if isinstance(masked, str) else "", reason="orphaned",
        )
        self.log.warning("store: %s leftover %s (%s)", spec.slug, recorded, "orphaned")

    def _register_one(self, spec: RepoSpec, wants_add: bool, entry: dict | None, present: set[str]) -> None:
        if not wants_add:
            slug, masked = self._masked(spec, entry)
            self.state.set_repository(
                spec.slug, in_store=slug is not None and slug in present, error=None, store_slug=slug,
                masked_url=masked,
            )
            return
        had_error = self._had_error(spec)
        entry = self.ensure_local(spec)
        url = self.local_url(spec, entry["hash"])
        slug, masked = store_slug(url), masked_store_url(self.base, spec.owner, spec.name, entry["hash"])
        if slug in present:
            self.state.set_repository(spec.slug, in_store=True, error=None, store_slug=slug, masked_url=masked)
            return
        try:
            result = self.client.add_repository(url)
        except SupervisorRefused as exc:
            code = _refused_code(exc)
            self.state.set_repository(spec.slug, in_store=False, error=code, store_slug=slug, masked_url=masked)
            if not had_error:
                self.log.warning("store: registration of %s failed: %s", spec.slug, code)
            return
        if result.ok or result.duplicate:
            self.state.set_repository(spec.slug, in_store=True, error=None, store_slug=slug, masked_url=masked)
            self.log.info("store: %s registered as %s (%s)", spec.slug, slug, masked)
            return
        code, status = _failure(result, "add_rejected")
        self.state.set_repository(
            spec.slug, in_store=False, error=code, error_status=status, store_slug=slug, masked_url=masked
        )
        if not had_error:
            self.log.warning(
                "store: registration of %s failed: %s", spec.slug, mask_text(result.message) or f"http {result.status}"
            )

    def _to_register(self, repository: str) -> bool:
        return self.options.register_local and self.options.find(repository) is not None

    def _revoke_label(self, repository: str, user: Any) -> bool:
        """Revoke a reserved label the proxy owns; anything else (a hand-edited user, None) is left alone."""
        if not isinstance(user, str) or not is_reserved(user):
            return False
        return self.access.revoke(repository, user, specs=self.options.repositories, system=True)

    def _resolve_gone(self, present: set[str]) -> None:
        """Drop leftovers and unconfigured entries whose store slug is no longer listed; never sends DELETE."""
        for item in self.state.leftovers():
            slug, repository, user = item["store_slug"], item["repository"], item.get("user")
            if slug in present:
                continue
            if user != LOCAL_USER or not self._to_register(repository):
                self._revoke_label(repository, user)
            self.state.drop_leftover(slug)
            self.log.info("store: leftover %s of %s is gone; dropped", slug, repository)
        for repository in self.state.unconfigured_repositories():
            current = self.state.repository(repository) or {}
            if current.get("store_slug") in present or self.state.leftovers(repository):
                continue
            self._revoke_label(repository, LOCAL_USER)
            self.state.drop_repository(repository)
            self.log.info(
                "store: %s is no longer configured and its store repository is gone; local entry revoked", repository
            )

    # --- operator requests (MRP-10) ---------------------------------------------------------------------------------

    def _request_files(self) -> tuple[list[Path], list[Path]]:
        """(valid-named request files, other entries to delete); temporary files of a writer and directories are
        skipped, so neither keeps the wait loop busy."""
        directory = self.paths.supervisor_requests_dir
        try:
            names = os.listdir(directory)
        except OSError:
            return [], []
        valid: list[tuple[int, str, Path]] = []
        invalid: list[Path] = []
        for name in names:
            if name.startswith(".") or name in self._stuck:
                continue
            path = directory / name
            try:
                info = path.lstat()
            except OSError:
                continue
            if stat.S_ISDIR(info.st_mode):
                continue
            if REQUEST_NAME_RE.fullmatch(name) and stat.S_ISREG(info.st_mode):
                valid.append((info.st_mtime_ns, name, path))
            else:
                invalid.append(path)
        return [path for _, _, path in sorted(valid)], invalid

    def pending_requests(self) -> list[Path]:
        """Request files with a valid name, oldest first (mtime, then name)."""
        return self._request_files()[0]

    def _unlink(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            self._stuck.add(path.name)

    def _drop_invalid(self, path: Path) -> None:
        self._unlink(path)
        self.log.warning(INVALID_REQUEST)

    def _read_request(self, path: Path) -> dict | None:
        """Read and unlink one request file; the parsed document when it is valid, else None (file already gone)."""
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as handle:
                raw = handle.read(REQUEST_MAX_BYTES + 1)
        except OSError:
            raw = None
        self._unlink(path)
        if path.name in self._stuck:
            return None  # never execute a request whose file stays: it would run again on the next call
        if raw is None or len(raw) > REQUEST_MAX_BYTES:
            return None
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        if not isinstance(doc, dict) or set(doc) != REQUEST_KEYS:
            return None
        if not all(isinstance(doc[key], str) for key in REQUEST_KEYS):
            return None
        if not _ID_RE.fullmatch(doc["id"]) or path.name != f"{doc['id']}.json" or len(doc["repository"]) > 200:
            return None
        return doc

    def _run_request(self, path: Path) -> None:
        doc = self._read_request(path)
        if doc is None:
            self.log.warning(INVALID_REQUEST)
            return
        action = doc["action"] if _ACTION_RE.fullmatch(doc["action"]) else "invalid"
        repository = sanitize(doc["repository"], 200) or "-"
        try:
            result, code = self.handle_request(doc)
        except Exception as exc:  # the request is answered either way; the CLI must not wait in vain
            self.log.warning("store: request %s %s failed: internal error (%s)", action, repository,
                             type(exc).__name__)
            result, code = "failed", "internal_error"
        self.state.record_request(id=doc["id"], action=action, repository=repository, result=result, code=code)
        self.log.info("store: request %s %s: %s", action, repository, result)

    def handle_request(self, doc: dict) -> tuple[str, str]:
        """Execute one validated request; returns (result, code) with result in REQUEST_RESULTS."""
        action = doc.get("action")
        if action not in REQUEST_ACTIONS:
            return "rejected", "invalid_request"
        if action == "rotate":
            return self._rotate(doc["repository"])
        return self._remove(doc["repository"])

    def _rotate(self, argument: str) -> tuple[str, str]:
        """Rotate the `local` URL of one configured repository: add the new URL first, revoke the old one at once,
        then try to remove the old store repository (D-09, D-11); never forced, never retried by the loop."""
        try:
            owner, name = parse_repository(argument)
        except (TypeError, ValueError):
            return "rejected", "repository_unknown"
        spec = self.options.find(f"{owner}/{name}")
        if spec is None:
            return "rejected", "repository_unknown"
        if not self.options.register_local:
            return "rejected", "register_local_disabled"
        entry = self.local_entry(spec)
        if entry is None:
            return "rejected", "not_registered"
        try:
            listing = self.client.list_repositories()
        except SupervisorRefused:
            return "failed", "store_list_unavailable"
        if not listing.ok or not isinstance(listing.data, list):
            return "failed", "store_list_unavailable"

        current = self.state.repository(spec.slug) or {}
        recorded = current.get("store_slug")
        old_slug = recorded if isinstance(recorded, str) and _SLUG_RE.fullmatch(recorded) else store_slug(
            self.local_url(spec, entry["hash"])
        )
        retired = f"{LOCAL_USER}.{old_slug}"
        old_masked = masked_store_url(self.base, spec.owner, spec.name, entry["hash"])  # the hash is gone after revoke

        # One locked write: the new link exists before the Supervisor clones, the old one still serves during the add
        _, new = self.access.retire_and_replace(spec.slug, LOCAL_USER, retired, specs=self.options.repositories)
        new_url = self.local_url(spec, new["hash"])
        new_slug = store_slug(new_url)
        new_masked = masked_store_url(self.base, spec.owner, spec.name, new["hash"])
        try:
            result = self.client.add_repository(new_url)
        except SupervisorRefused as exc:
            result = CallResult(False, 0, message=_refused_code(exc))
        except Exception:
            self.access.undo_retire(spec.slug, LOCAL_USER, retired, specs=self.options.repositories)
            self.log.warning("store: rotation of %s failed; old registration kept", spec.slug)
            raise
        if not (result.ok or result.duplicate):
            self.access.undo_retire(spec.slug, LOCAL_USER, retired, specs=self.options.repositories)
            self.log.warning("store: rotation of %s failed; old registration kept", spec.slug)
            return "failed", "add_failed"

        # D-11: the old URL stops serving right after the add, before the DELETE and whatever its answer is
        self.access.revoke(spec.slug, retired, specs=self.options.repositories, system=True)
        self.state.set_repository(spec.slug, in_store=True, error=None, store_slug=new_slug, masked_url=new_masked)
        self.log.info("store: %s rotated: new %s registered; old URL revoked", spec.slug, new_slug)

        try:
            removal = self.client.remove_repository(old_slug)
        except SupervisorRefused as exc:
            removal = CallResult(False, 0, message=_refused_code(exc))
        if removal.ok or removal.not_found:
            self.state.drop_leftover(old_slug)
            self.log.info("store: %s removed %s", spec.slug, old_slug)
            return "done", ""
        reason = "in_use" if removal.in_use else "error"
        self.state.add_leftover(
            repository=spec.slug,
            store_slug=old_slug,
            user=retired,
            masked_url=old_masked,
            reason=reason,
            message=mask_text(removal.message),
            revoked=True,
        )
        self.log.warning("store: %s leftover %s (%s)", spec.slug, old_slug, reason)
        if removal.in_use:
            return "refused", "in_use"
        return "failed", "remove_failed"

    def _remove(self, argument: str) -> tuple[str, str]:
        try:
            owner, name = parse_repository(argument)
        except (TypeError, ValueError):
            return "rejected", "repository_unknown"
        spec = self.options.find(f"{owner}/{name}")
        current = self.state.repository(f"{owner}/{name}")
        leftovers = self.state.leftovers(f"{owner}/{name}")
        if spec is None and current is None and not leftovers:
            return "rejected", "repository_unknown"
        repository = spec.slug if spec is not None else (current or leftovers[0])["repository"]

        # Targets: slugs recorded from the proxy's own URLs only (never a slug from the store list)
        targets: dict[str, dict[str, Any]] = {}
        for item in leftovers:
            targets[item["store_slug"]] = {
                "user": item.get("user"), "masked_url": item.get("masked_url") or "",
                "revoked": item.get("revoked") is True, "current": False,
            }
        removes_current = spec is None or not self.options.register_local
        slug = current.get("store_slug") if current else None
        if removes_current and isinstance(slug, str) and _SLUG_RE.fullmatch(slug):
            target = targets.setdefault(
                slug, {"user": LOCAL_USER, "masked_url": current.get("masked_url") or "", "revoked": False}
            )
            target["current"] = True
        if not targets:
            if spec is not None and self.options.register_local:
                return "rejected", "register_local_enabled"
            return "rejected", "not_registered"

        try:
            listing = self.client.list_repositories()
        except SupervisorRefused:
            return "failed", "store_list_unavailable"
        if not listing.ok or not isinstance(listing.data, list):
            return "failed", "store_list_unavailable"
        present = {
            item["slug"] for item in listing.data if isinstance(item, dict) and isinstance(item.get("slug"), str)
        }

        refused = failed = False
        for slug, target in targets.items():
            outcome = self._remove_one(repository, spec, slug, target, present)
            refused = refused or outcome == "refused"
            failed = failed or outcome == "failed"
        if failed:
            return "failed", "remove_failed"
        if refused:
            return "refused", "in_use"
        return "done", ""

    def _remove_one(
        self, repository: str, spec: RepoSpec | None, slug: str, target: dict[str, Any], present: set[str]
    ) -> str:
        """DELETE one recorded slug; returns `removed`, `refused` or `failed`."""
        if slug in present:
            try:
                result = self.client.remove_repository(slug)
            except SupervisorRefused:
                return "failed"
            if result.in_use:
                self.state.add_leftover(
                    repository=repository,
                    store_slug=slug,
                    user=target["user"],
                    masked_url=target["masked_url"],
                    reason="in_use",
                    message=mask_text(result.message),
                    revoked=target["revoked"],
                )
                self.log.warning("store: %s leftover %s (%s)", repository, slug, "in_use")
                return "refused"
            if not (result.ok or result.not_found):
                return "failed"
        self._revoke_label(repository, target["user"])
        self.state.drop_leftover(slug)
        if target["current"]:
            if spec is not None:
                self.state.set_repository(
                    spec.slug, in_store=False, error=None, store_slug=slug, masked_url=target["masked_url"]
                )
            elif self.state.leftovers(repository):
                self.state.set_repository(
                    repository, in_store=False, error=None, store_slug=slug, masked_url=target["masked_url"],
                    configured=False,
                )
            else:
                self.state.drop_repository(repository)
        self.log.info("store: %s removed %s", repository, slug)
        return "removed"

    def after_cycle(self, status_doc: dict, head_changes: Iterable[str] = frozenset()) -> None:
        """Hook of the sync loop after every cycle: the registration pass, then at most one store reload.

        Only a head change of a repository whose URL was in the store before the pass counts; one added in this pass
        was cloned at its current head already.
        """
        in_store_before = set()
        for spec in self.options.repositories:
            current = self.state.repository(spec.slug)
            if current is not None and current.get("in_store") is True:
                in_store_before.add(spec.key)
        self.register_pass(status_doc)
        changed = {key.lower() for key in head_changes} & in_store_before
        if changed or (self.reload_pending and self.window_open()):
            self.request_reload()

    def work_due(self) -> bool:
        """True when the sync wait loop should wake for Supervisor work: a request file, or a pending reload whose
        window is open."""
        valid, invalid = self._request_files()
        return bool(valid or invalid) or (self.reload_pending and self.window_open())

    def run_due(self) -> None:
        """Supervisor work of the wait loop; never fetches. Operator requests first (each file once; a file created
        meanwhile waits for the next call), then the pending reload when it is due."""
        valid, invalid = self._request_files()
        for path in invalid:
            self._drop_invalid(path)
        for path in valid:
            self._run_request(path)
        if self.reload_pending and self.window_open():
            self._send_reload()

    def window_open(self) -> bool:
        """True when no reload was attempted yet or a full sync interval has passed since the last attempt."""
        return self.last_reload_at is None or self.clock() - self.last_reload_at >= self.interval_seconds

    def request_reload(self) -> None:
        """Send a reload now when the window is open, else keep it as `pending` for the wait loop."""
        if self.window_open():
            self._send_reload()
            return
        self.reload_pending = True
        self.state.set_reload(pending=True)
        remaining = self.interval_seconds - (self.clock() - (self.last_reload_at or 0.0))
        self.log.info("store reload: deferred until %s", utc_timestamp(self.wall() + remaining))

    def _send_reload(self) -> None:
        # The window closes before the call: an exception or a hung call never opens a reload storm (D-08)
        self.last_reload_at = self.clock()
        self.reload_pending = True
        requested = utc_timestamp(self.wall())
        try:
            result = self.client.reload_store()
        except SupervisorRefused as exc:
            result = CallResult(False, 0, message=_refused_code(exc))
        except Exception as exc:  # the reload stays owed; the next window retries it
            result = CallResult(False, 0, message=f"internal error ({type(exc).__name__})")
        if result.ok:
            self.reload_pending = False
            self.state.set_reload(last_requested=requested, last_result="ok", pending=False, message="")
            self.log.info("store reload: ok")
            return
        message = mask_text(result.message) or f"http {result.status}"
        self.state.set_reload(last_requested=requested, last_result="failed", pending=True, message=message)
        self.log.warning("store reload: failed: %s", message)
