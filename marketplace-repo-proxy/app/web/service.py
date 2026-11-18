"""Service layer of the management page: token-free options, repository overview and build version.

The GUI keeps only non-secret options: `GuiConfig.options` always has `github_token == ""` (D-07). Sync state comes from
`/data/status.json` (single writer `sync`, atomic replace, no lock needed; D-17) and the optional registration state
from the isolated reader in `app.web.registration` (D-19). The add-on version is read once at start from the file the
image build writes (D-30); no Supervisor call and no environment variable are involved.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import socket
import time
from pathlib import Path
from typing import Any, Callable

from app.logsetup import mask_hashes
from app.options import Options, load_options
from app.paths import Paths
from app.status import BRANCH_SOURCES, STATUS_CODES, read_status
from app.web.registration import REGISTRATION_STATES, read_registration

LOG = logging.getLogger("mrp.gui")

VERSION_FILE = Path("/opt/marketplace-repo-proxy/BUILD_VERSION")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-[0-9]+$")
_VERSION_MAX = 32
DETAIL_MAX = 200
_SYNC_TEXT_FIELDS = ("state", "last_started", "last_finished", "next_due", "reason")
_ROW_TEXT_FIELDS = ("last_attempt", "last_success", "last_change", "head")


def read_build_version(path: Path = VERSION_FILE) -> str | None:
    """The full add-on version (`X.Y.Z-N`) written at build time, or None: never a guessed or partial version."""
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if len(text) > _VERSION_MAX or not _VERSION_RE.fullmatch(text):
        return None
    return text


@dataclasses.dataclass(frozen=True)
class GuiConfig:
    options: Options  # github_token is always "" here
    hostname: str
    version: str | None = None


def load_gui_config(paths: Paths, hostname: str | None = None, version_file: Path = VERSION_FILE) -> GuiConfig:
    """Options without the credential (OptionsError propagates), host name and build version, read once at start."""
    options = load_options(paths.options_file)
    safe = dataclasses.replace(options, github_token="")
    del options
    return GuiConfig(safe, hostname or socket.gethostname(), read_build_version(version_file))


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


class GuiService:
    def __init__(
        self,
        paths: Paths,
        config: GuiConfig,
        clock: Callable[[], float] = time.time,
        registration: Callable[[Paths], dict | None] = read_registration,
    ) -> None:
        self.paths = paths
        self.config = config
        self.clock = clock
        self.registration = registration

    def _registrations(self) -> dict | None:
        try:
            result = self.registration(self.paths)
        except Exception as exc:  # noqa: BLE001 - a broken reader means "no data", never a failed overview
            LOG.error("registration reader failed (%s)", type(exc).__name__)
            return None
        return result if isinstance(result, dict) else None

    @staticmethod
    def _registration_value(value: Any) -> dict[str, str] | None:
        if not isinstance(value, dict) or value.get("state") not in REGISTRATION_STATES:
            return None
        result = {"state": value["state"]}
        detail = value.get("detail")
        if isinstance(detail, str):
            result["detail"] = mask_hashes(detail)[:DETAIL_MAX]
        return result

    def _sync(self, doc: dict | None) -> dict[str, Any]:
        raw = doc.get("sync") if doc is not None else None
        raw = raw if isinstance(raw, dict) else {}
        sync: dict[str, Any] = {key: _text(raw.get(key)) for key in _SYNC_TEXT_FIELDS}
        interval = raw.get("interval_minutes")
        valid = isinstance(interval, int) and not isinstance(interval, bool)
        sync["interval_minutes"] = interval if valid else self.config.options.sync_interval
        sync["requested"] = self.paths.trigger_file.exists()
        return sync

    @staticmethod
    def _entries(doc: dict | None) -> list[dict]:
        entries = doc.get("repositories") if doc is not None else None
        return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []

    def overview(self) -> dict[str, Any]:
        doc = read_status(self.paths)
        entries = self._entries(doc)
        registrations = self._registrations()
        rows: list[dict[str, Any]] = []
        for spec in self.config.options.repositories:
            entry = next(
                (e for e in entries if isinstance(e.get("repository"), str) and e["repository"].lower() == spec.key),
                {},
            )
            branch_source = entry.get("branch_source")
            status = entry.get("status")
            addons = entry.get("addons")
            row: dict[str, Any] = {
                "repository": spec.slug,
                "branch": entry["branch"] if isinstance(entry.get("branch"), str) else spec.branch,
                "branch_source": branch_source if branch_source in BRANCH_SOURCES else None,
                "status": status if status in STATUS_CODES else None,
                "message": entry["message"] if isinstance(entry.get("message"), str) else "",
            }
            row.update({key: _text(entry.get(key)) for key in _ROW_TEXT_FIELDS})
            row["addons"] = [a for a in addons if isinstance(a, str)] if isinstance(addons, list) else []
            row["registration"] = self._registration_value(registrations.get(spec.key)) if registrations else None
            rows.append(row)
        return {
            "now_ms": int(self.clock() * 1000),
            "status_available": doc is not None,
            "sync": self._sync(doc),
            "repositories": rows,
        }

    def meta(self) -> dict[str, Any]:
        return {"version": self.config.version}
