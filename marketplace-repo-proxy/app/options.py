"""Load and re-validate /data/options.json (MRP-01). Values become paths and refspecs, so validate strictly."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MIN_INTERVAL = 5
DEFAULT_INTERVAL = 15
LOG_LEVELS = ("debug", "info", "warning", "error")
OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


class OptionsError(Exception):
    """options.json is unreadable, not JSON or not an object."""


@dataclass(frozen=True)
class RepoSpec:
    owner: str
    name: str
    branch: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def key(self) -> str:
        return self.slug.lower()


@dataclass(frozen=True)
class Options:
    github_token: str = field(default="", repr=False)
    sync_interval: int = DEFAULT_INTERVAL
    public_url: str = ""
    repositories: tuple[RepoSpec, ...] = ()
    register_local: bool = True
    api_enabled: bool = False
    log_level: str = "info"
    rejected: tuple[str, ...] = ()

    def find(self, repository: str) -> RepoSpec | None:
        """Configured spec for `owner/repo`, case-insensitive."""
        wanted = repository.strip().lower()
        for spec in self.repositories:
            if spec.key == wanted:
                return spec
        return None


def parse_repository(value: str) -> tuple[str, str]:
    """Split and validate `owner/repo`; raises ValueError."""
    if not isinstance(value, str) or value.count("/") != 1:
        raise ValueError("repository must be owner/repo")
    owner, name = value.strip().split("/")
    if not OWNER_RE.match(owner):
        raise ValueError("invalid owner")
    if not REPO_RE.match(name) or name in (".", "..") or name.lower().endswith(".git"):
        raise ValueError("invalid repository name")
    return owner, name


def _valid_branch(branch: str) -> bool:
    return bool(
        BRANCH_RE.match(branch)
        and not branch.startswith(("-", "/"))
        and not branch.endswith(("/", ".lock"))
        and ".." not in branch
        and "//" not in branch
    )


def _bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    return value if isinstance(value, bool) else default


def _public_url(value: Any, rejected: list[str]) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        url = value.strip().rstrip("/")
        parts = urlsplit(url)
        if parts.scheme in ("http", "https") and parts.hostname:
            return url
    rejected.append("public_url: must be an http(s) URL with a host")
    return ""


def _repositories(value: Any, rejected: list[str]) -> tuple[RepoSpec, ...]:
    specs: list[RepoSpec] = []
    seen: set[str] = set()
    if not isinstance(value, list):
        return ()
    for item in value:
        raw = item.get("repository") if isinstance(item, dict) else None
        label = raw if isinstance(raw, str) else "?"
        try:
            owner, name = parse_repository(raw)  # type: ignore[arg-type]
        except ValueError as exc:
            rejected.append(f"{label}: {exc}")
            continue
        branch = item.get("branch")
        if branch is None or (isinstance(branch, str) and branch.strip() == ""):
            branch = None
        elif not isinstance(branch, str) or not _valid_branch(branch.strip()):
            rejected.append(f"{label}: invalid branch")
            continue
        else:
            branch = branch.strip()
        spec = RepoSpec(owner, name, branch)
        if spec.key in seen:
            rejected.append(f"{label}: duplicate repository")
            continue
        seen.add(spec.key)
        specs.append(spec)
    return tuple(specs)


def parse_options(data: dict) -> Options:
    rejected: list[str] = []
    token = data.get("github_token", "")
    interval = data.get("sync_interval", DEFAULT_INTERVAL)
    if isinstance(interval, bool) or not isinstance(interval, int):
        interval = DEFAULT_INTERVAL
    log_level = data.get("log_level", "info")
    return Options(
        github_token=token if isinstance(token, str) else "",
        sync_interval=max(MIN_INTERVAL, interval),
        public_url=_public_url(data.get("public_url"), rejected),
        repositories=_repositories(data.get("repositories", []), rejected),
        register_local=_bool(data, "register_local", True),
        api_enabled=_bool(data, "api_enabled", False),
        log_level=log_level if log_level in LOG_LEVELS else "info",
        rejected=tuple(rejected),
    )


def load_options(path: Path) -> Options:
    """A missing file gives the defaults; unreadable, invalid or non-object content raises OptionsError."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Options()
    except (OSError, ValueError) as exc:
        raise OptionsError(f"cannot read options: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise OptionsError("cannot read options: not a JSON object")
    return parse_options(data)
