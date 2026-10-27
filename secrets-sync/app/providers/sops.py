"""SOPS provider: decrypts a SOPS+age encrypted YAML file in memory and flattens it into secrets (see docs/SPEC.md)."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Mapping

import yaml

from .base import Problem, ProviderError, Snapshot

SOPS_TIMEOUT = 30  # seconds
DEFAULT_FILE = "/config/secrets.sops.yaml"
DEFAULT_SEPARATOR = "_"
DEFAULT_AGE_KEY_FILE = "/addon_config/age.key"


class Provider:
    name = "sops"

    def __init__(self, cfg: Mapping[str, Any] | None = None) -> None:
        cfg = cfg or {}
        # Accept both the bare option block and the full options mapping
        block = cfg.get("sops") if isinstance(cfg.get("sops"), Mapping) else cfg
        self._file = str(block.get("file") or DEFAULT_FILE)
        sep = block.get("flatten_separator")
        self._sep = DEFAULT_SEPARATOR if sep is None else str(sep)
        self._key_file = str(block.get("age_key_file") or os.environ.get("SS_AGE_KEY_FILE") or DEFAULT_AGE_KEY_FILE)

    def validate(self, cfg: Mapping[str, Any] | None = None) -> list[Problem]:
        problems: list[Problem] = []
        if not self._file.strip():
            problems.append(Problem("sops_missing_file", "sops.file is not set"))
        if not self._sep:
            problems.append(Problem("sops_empty_separator", "sops.flatten_separator must not be empty"))
        return problems

    def fetch(self) -> Snapshot:
        self._check_key_file()
        path = Path(self._file)
        raw = self._read_encrypted(path)
        meta = self._parse(raw, "sops_not_encrypted", "file is not valid YAML")
        if not isinstance(meta, dict) or not isinstance(meta.get("sops"), dict):
            raise ProviderError("sops_not_encrypted", "file has no top-level sops block")
        data = self._decrypt(path)
        secrets = self._flatten(data)
        try:
            revision = str(int(path.stat().st_mtime))
        except OSError:
            revision = ""
        return Snapshot(secrets=secrets, revision=revision)

    def _check_key_file(self) -> None:
        try:
            st = os.stat(self._key_file)
        except OSError:
            raise ProviderError("sops_key_missing", "age key file not found") from None
        if not stat.S_ISREG(st.st_mode):
            raise ProviderError("sops_key_missing", "age key path is not a regular file")
        if st.st_mode & 0o077:
            raise ProviderError("sops_key_permissions", "age key file must have mode 600 or stricter")

    @staticmethod
    def _read_encrypted(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ProviderError("sops_file_missing", "sops file not found") from None
        except (OSError, UnicodeDecodeError):
            raise ProviderError("sops_file_unreadable", "sops file cannot be read") from None

    @staticmethod
    def _parse(text: str, code: str, message: str) -> Any:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            # Never chain: the YAML error may quote file content
            raise ProviderError(code, message) from None

    def _decrypt(self, path: Path) -> Any:
        # The sops child needs no Bitwarden credentials
        env = {k: v for k, v in os.environ.items() if not k.startswith("BW_")}
        env["SOPS_AGE_KEY_FILE"] = self._key_file
        try:
            proc = subprocess.run(
                ["sops", "-d", "--output-type", "yaml", str(path)],
                capture_output=True,
                env=env,
                timeout=SOPS_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ProviderError("sops_timeout", "sops timed out") from None
        except FileNotFoundError:
            raise ProviderError("sops_binary_missing", "sops binary not found") from None
        except OSError:
            raise ProviderError("sops_exec_failed", "sops could not be executed") from None
        if proc.returncode != 0:
            # stderr is deliberately dropped, it must not reach logs or state
            raise ProviderError("sops_decrypt_failed", f"sops exited with code {proc.returncode}")
        data = self._parse(proc.stdout.decode("utf-8", "replace"), "sops_invalid_yaml", "decrypted data is not YAML")
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ProviderError("sops_invalid_yaml", "decrypted data is not a mapping")
        data.pop("sops", None)
        return data

    def _flatten(self, data: Mapping[str, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        bad: list[str] = []
        collisions: list[str] = []

        def walk(node: Mapping[Any, Any], prefix: str) -> None:
            for key, value in node.items():
                name = f"{prefix}{self._sep}{key}" if prefix else str(key)
                if isinstance(value, Mapping):
                    walk(value, name)
                elif isinstance(value, (list, tuple, set)) or value is None:
                    bad.append(name)
                else:
                    if name in out:
                        collisions.append(name)
                    out[name] = _to_str(value)

        walk(data, "")
        if bad:
            raise ProviderError("sops_unsupported_value", "unsupported value type for keys: " + ", ".join(sorted(bad)))
        if collisions:
            raise ProviderError("key_collision", "flattened key collision: " + ", ".join(sorted(set(collisions))))
        return out


def _to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
