"""Render /data/server.yml from the add-on options (contract C3). Secrets never reach the file."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.contract import NTFY_PORT, OptionsError, Options, Paths, load_options


def _q(value: str) -> str:
    """A JSON string is a valid YAML double-quoted scalar."""
    return json.dumps(value)


def render_server_yml(options: Options, paths: Paths) -> str:
    """Return the server.yml text for the options; no password of any kind is rendered."""
    lines = [
        f"base-url: {_q(options.base_url)}",
        f"listen-http: {_q(f':{NTFY_PORT}')}",
        f"cache-file: {_q(str(paths.cache_db))}",
        f"cache-duration: {_q(options.cache_duration)}",
        f"auth-file: {_q(str(paths.auth_db))}",
        f"auth-default-access: {_q(options.auth_default_access)}",
        "enable-login: true",
        "enable-signup: false",
        f"behind-proxy: {'true' if options.behind_proxy else 'false'}",
        f"web-root: {_q('/' if options.enable_web_ui else 'disable')}",
        f"log-level: {_q(options.log_level)}",
    ]
    if options.attachments_enabled:
        lines.append(f"attachment-cache-dir: {_q(str(paths.attachment_dir))}")
        for key, value in (
            ("attachment-total-size-limit", options.attachment_total_size_limit),
            ("attachment-file-size-limit", options.attachment_file_size_limit),
            ("attachment-expiry-duration", options.attachment_expiry_duration),
        ):
            if value:
                lines.append(f"{key}: {_q(value)}")
    return "\n".join(lines) + "\n"


def write_server_yml(options: Options, paths: Paths) -> Path:
    """Write server.yml atomically with mode 0600 and create the attachment directory when enabled."""
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    if options.attachments_enabled:
        paths.attachment_dir.mkdir(parents=True, exist_ok=True)
    tmp = paths.server_yml.with_name(paths.server_yml.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(render_server_yml(options, paths))
    os.chmod(tmp, 0o600)
    os.replace(tmp, paths.server_yml)
    return paths.server_yml


def main() -> int:
    paths = Paths.from_env()
    try:
        options = load_options(paths.options_file)
    except OptionsError as exc:
        print(f"[render_config] invalid options: {exc}", file=sys.stderr, flush=True)
        return 1
    target = write_server_yml(options, paths)
    print(f"[render_config] wrote {target}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
