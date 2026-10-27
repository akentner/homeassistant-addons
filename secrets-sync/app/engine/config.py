"""Add-on configuration: environment paths + options.json (see docs/SPEC.md, "Runtime paths")."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.providers.base import Problem, Provider

PROVIDER_MODULES = {
    "bitwarden": "app.providers.bitwarden",
    "sops": "app.providers.sops",
}
COLLISION_POLICIES = ("error", "priority")
LOG_LEVELS = ("debug", "info", "warning", "error")
MIN_INTERVAL = 60


@dataclass(frozen=True)
class Config:
    providers: tuple[str, ...]
    interval: int
    collision_policy: str
    shrink_guard_percent: int
    log_level: str
    provider_cfg: Mapping[str, Mapping[str, Any]]
    secrets_file: Path
    files_dir: Path
    state_file: Path
    data_dir: Path
    port: int
    version: str
    problems: tuple[Problem, ...] = field(default_factory=tuple)


class ProviderLoadError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _int(raw: Any, default: int, lo: int, hi: int, name: str, problems: list[Problem]) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int) or not lo <= raw <= hi:
        problems.append(Problem("config_invalid", f"option '{name}' must be an integer in {lo}..{hi}"))
        return default
    return raw


def _choice(raw: Any, default: str, choices: tuple[str, ...], name: str, problems: list[Problem]) -> str:
    if raw is None:
        return default
    if raw not in choices:
        problems.append(Problem("config_invalid", f"option '{name}' must be one of {', '.join(choices)}"))
        return default
    return raw


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    problems: list[Problem] = []
    options: dict[str, Any] = {}
    options_path = Path(env.get("SS_OPTIONS", "/data/options.json"))
    try:
        loaded = json.loads(options_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            options = loaded
        else:
            problems.append(Problem("config_invalid", "options file must contain a JSON object"))
    except (OSError, ValueError):
        problems.append(Problem("config_invalid", "options file is missing or not valid JSON"))

    raw_providers = options.get("providers", ["bitwarden"])
    providers: list[str] = []
    if isinstance(raw_providers, list):
        for name in raw_providers:
            if name not in PROVIDER_MODULES:
                problems.append(Problem("config_invalid", f"unknown provider '{name}'"))
            elif name not in providers:
                providers.append(name)
    else:
        problems.append(Problem("config_invalid", "option 'providers' must be a list"))
    if not providers:
        problems.append(Problem("no_providers", "no provider is enabled"))

    provider_cfg: dict[str, Mapping[str, Any]] = {}
    for name in PROVIDER_MODULES:
        block = options.get(name)
        provider_cfg[name] = block if isinstance(block, dict) else {}

    port_raw = env.get("SS_PORT", "8099")
    port = int(port_raw) if port_raw.isdigit() else 8099

    return Config(
        providers=tuple(providers),
        interval=_int(options.get("interval"), 300, MIN_INTERVAL, 86400, "interval", problems),
        collision_policy=_choice(options.get("collision_policy"), "error", COLLISION_POLICIES,
                                 "collision_policy", problems),
        shrink_guard_percent=_int(options.get("shrink_guard_percent"), 30, 1, 100, "shrink_guard_percent", problems),
        log_level=_choice(options.get("log_level"), "info", LOG_LEVELS, "log_level", problems),
        provider_cfg=provider_cfg,
        secrets_file=Path(env.get("SS_SECRETS_FILE", "/config/secrets.yaml")),
        files_dir=Path(env.get("SS_FILES_DIR", "/config/secrets_files")),
        state_file=Path(env.get("SS_STATE_FILE", "/data/state.json")),
        data_dir=Path(env.get("SS_DATA_DIR", "/data")),
        port=port,
        version=env.get("SS_ADDON_VERSION", "unknown"),
        problems=tuple(problems),
    )


def load_provider(name: str, cfg: Mapping[str, Any]) -> Provider:
    module_name = PROVIDER_MODULES.get(name)
    if module_name is None:
        raise ProviderLoadError("unknown_provider", f"unknown provider '{name}'")
    try:
        module = importlib.import_module(module_name)
        return module.Provider(cfg)  # type: ignore[no-any-return]
    except ImportError as exc:
        raise ProviderLoadError("provider_unavailable", f"provider '{name}' cannot be loaded") from exc
