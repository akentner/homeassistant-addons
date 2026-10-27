"""SOPS provider: decrypts a SOPS+age encrypted YAML file in memory and flattens it into secrets (see docs/SPEC.md)."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Mapping

import yaml

from . import gitsource
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
        self._source = str(block.get("source") or "file")
        self._file = str(block.get("file") or DEFAULT_FILE)
        self._git_url = str(block.get("git_url") or "").strip()
        self._git_branch = str(block.get("git_branch") or "main")
        self._git_path = str(block.get("git_path") or "secrets.sops.yaml")
        self._git_username = str(block.get("git_username") or "")
        sep = block.get("flatten_separator")
        self._sep = DEFAULT_SEPARATOR if sep is None else str(sep)
        self._key_file = str(block.get("age_key_file") or os.environ.get("SS_AGE_KEY_FILE") or DEFAULT_AGE_KEY_FILE)

    def validate(self, cfg: Mapping[str, Any] | None = None) -> list[Problem]:
        problems: list[Problem] = []
        if self._source not in ("file", "git"):
            problems.append(Problem("sops_invalid_source", "sops.source must be file or git"))
        if not self._sep:
            problems.append(Problem("sops_empty_separator", "sops.flatten_separator must not be empty"))
        if self._source == "git":
            problems.extend(self._validate_git())
        elif not self._file.strip():
            problems.append(Problem("sops_missing_file", "sops.file is not set"))
        return problems

    def _validate_git(self) -> list[Problem]:
        url = self._git_url
        if not url:
            return [Problem("sops_git_missing_url", "sops.git_url is not set")]
        problems: list[Problem] = []
        if gitsource.url_has_credentials(url):
            problems.append(Problem("sops_git_url_credentials", "sops.git_url must not contain credentials"))
        elif gitsource.url_kind(url) is None:
            problems.append(Problem("sops_git_url_scheme", "sops.git_url must be ssh or https"))
        if not gitsource.branch_valid(self._git_branch):
            problems.append(Problem("sops_git_branch_invalid", "sops.git_branch is invalid"))
        if not gitsource.path_valid(self._git_path):
            problems.append(Problem("sops_git_path_invalid", "sops.git_path must be a relative path inside the repo"))
        return problems

    def _git(self) -> gitsource.GitSource:
        return gitsource.GitSource(self._git_url, self._git_branch, self._git_path, self._git_username)

    def check(self) -> str | None:
        if self._source != "git":
            return None
        if any(p.severity == "error" for p in self._validate_git()):
            raise ProviderError("sops_invalid_config", "git source is not configured correctly")
        return self._git().probe()

    def fetch(self) -> Snapshot:
        self._check_key_file()
        sha = ""
        if self._source == "git":
            if any(p.severity == "error" for p in self._validate_git()):
                raise ProviderError("sops_invalid_config", "git source is not configured correctly")
            path, sha = self._git().sync()
        else:
            path = Path(self._file)
        raw = self._read_encrypted(path)
        meta = self._parse(raw, "sops_not_encrypted", "file is not valid YAML")
        if not isinstance(meta, dict) or not isinstance(meta.get("sops"), dict):
            raise ProviderError("sops_not_encrypted", "file has no top-level sops block")
        data = self._decrypt(path)
        secrets = self._flatten(data)
        if sha:
            return Snapshot(secrets=secrets, revision=sha[:12], check_token=sha)
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
        # The sops child needs no Bitwarden or git credentials
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BW_", "SS_GIT_"))}
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
