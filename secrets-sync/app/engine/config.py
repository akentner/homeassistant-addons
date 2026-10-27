"""Add-on configuration: environment paths + options.json (see docs/SPEC.md, "Runtime paths")."""

from __future__ import annotations

import importlib
import json
import os
import re
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
USAGE_SCOPES = ("off", "config", "all")
MIN_INTERVAL = 60
MIN_CHECK_INTERVAL = 30  # 1..29 are raised to this
SYNTHETIC_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
SYNTHETIC_MAX_TEMPLATE = 2048


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
    usage_scan: str = "off"  # off | config | all (load_config defaults to all)
    addon_configs_dir: Path = Path("/addon_configs")
    check_interval: int = 0  # seconds between change checks, 0 = off (load_config defaults to 60)
    synthetic_keys: tuple[tuple[str, str], ...] = ()  # (name, template), order as configured


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


def _check_interval(raw: Any, problems: list[Problem]) -> int:
    value = _int(raw, 60, 0, 3600, "check_interval", problems)
    return MIN_CHECK_INTERVAL if 0 < value < MIN_CHECK_INTERVAL else value


def _synthetic_keys(raw: Any, problems: list[Problem]) -> tuple[tuple[str, str], ...]:
    """Parse `synthetic_keys`; invalid entries are reported (by index, never by template text) and dropped."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        problems.append(Problem("config_invalid", "option 'synthetic_keys' must be a list"))
        return ()
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        where = f"synthetic_keys[{index}]"
        name, template = (item.get("name"), item.get("template")) if isinstance(item, dict) else (None, None)
        if not isinstance(name, str) or not SYNTHETIC_NAME.match(name):
            problems.append(Problem("synthetic_invalid_name", f"{where}: name must match {SYNTHETIC_NAME.pattern}"))
        elif name in seen:
            problems.append(Problem("synthetic_invalid_name", f"{where}: duplicate name '{name}'"))
        elif not isinstance(template, str) or not template.strip():
            problems.append(Problem("config_invalid", f"{where}: template must be a non-empty string"))
        elif len(template) > SYNTHETIC_MAX_TEMPLATE:
            problems.append(Problem("synthetic_template_too_long",
                                    f"{where}: template exceeds {SYNTHETIC_MAX_TEMPLATE} characters"))
        else:
            seen.add(name)
            out.append((name, template))
    return tuple(out)


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

    usage_scan = _choice(options.get("usage_scan"), "all", USAGE_SCOPES, "usage_scan", problems)
    check_interval = _check_interval(options.get("check_interval"), problems)
    synthetic_keys = _synthetic_keys(options.get("synthetic_keys"), problems)
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
        usage_scan=usage_scan,
        addon_configs_dir=Path(env.get("SS_ADDON_CONFIGS_DIR", "/addon_configs")),
        check_interval=check_interval,
        synthetic_keys=synthetic_keys,
        problems=tuple(problems),  # keep last: it must be evaluated after every validation above
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
