"""Self-registration of the proxy's `local` store URLs with the Supervisor (MRP-08, D-05 to D-07, D-28).

One system user `local` (source `system`) per configured repository. After every sync cycle the registration pass
adds the internal store URL `http://{hostname}:8080/repo/{owner}/{repo}/{hash}` of every repository whose last sync is
`ok` when `GET /store/repositories` does not list its store slug. The pass reports facts (`in_store`, `error`) to the
state writer, which derives the registration value and message. A failing Supervisor never ends the pass; the next
cycle starts again with `GET`. No store reload and no removal here.
"""

from __future__ import annotations

import logging
from typing import Any

from app.access import HASH_RE, AccessError, AccessStore
from app.options import Options, RepoSpec
from app.paths import Paths
from app.supervisor import CallResult, SupervisorClient, SupervisorRefused, mask_text, store_slug
from app.supervisor_state import SupervisorStateWriter
from app.urls import internal_base, masked_store_url, store_url

LOCAL_USER = "local"
LOG = logging.getLogger("mrp.store")


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

        if not any(entries.values()) and not any(wants.values()):
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

        for spec in specs:
            try:
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

    def after_cycle(self, status_doc: dict) -> None:
        """Hook of the sync loop: runs after every cycle."""
        self.register_pass(status_doc)
