# Changelog

All notable changes to the **Secrets Sync** add-on are documented in this file. The add-on is our own code with no
upstream project, so every entry is add-on specific.

## [0.1.0-1] - 2026-10-27

- Fix: options could not be saved ("Missing option 'bitwarden?'"). The `bitwarden` and `sops` blocks are now always
  present with defaults; HA does not support optional dict keys.

## [0.1.0-0] - 2026-10-27

- Initial release: sync secrets from Bitwarden (`bw` CLI, API key login) and SOPS (age) into `/config/secrets.yaml` and
  optional files below `/config/secrets_files`.
- Ingress status page with per-provider status, key names (added/removed/changed), events, "Sync now" and "Preview".
- `/api/health` and `/api/status.json` for Gatus, optional on port 8099/tcp.
- Safety nets: atomic verified writes, shrink guard, collision detection, last good file is kept on any error.
