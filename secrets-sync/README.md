# Home Assistant Add-on: Secrets Sync

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Keeps `/config/secrets.yaml` in sync with Bitwarden and/or a SOPS-encrypted file.

## About

Home Assistant reads credentials from `secrets.yaml`. This add-on pulls them from a central source and writes the file
for you, so the vault stays the single source of truth. Providers are pluggable: `bitwarden` (Bitwarden or Vaultwarden
via the `bw` CLI) and `sops` (age-encrypted YAML). It is our own code, not an upstream wrapper (see [DOCS.md][docs]).

## Features

- Bitwarden items become keys in the legacy naming scheme (`<name>_username`, `<name>_password`, ...), secure notes
  become files
- SOPS YAML files are decrypted in memory and flattened into keys
- Several providers at once, with a collision policy (`error` or `priority`)
- Ingress status page: provider status, key names with added/removed/changed, events, "Sync now", "Preview"
- `/api/health` and `/api/status.json` for Gatus and other monitors (also on the optional port 8099/tcp)
- Never exits on errors: backoff and retry, the last good `secrets.yaml` stays in place

## Security notes

- Credentials are handed to `bw` via environment variables only, never as command line arguments. The SOPS age key is a
  file (`/addon_config/age.key`, mode 600), not an option.
- Secret values are never logged, at any log level, and never appear in `state.json`, API responses or the web page.
  Only key names are shown.
- All YAML values are written as double-quoted scalars and every write is verified by a parse round trip before the
  atomic rename. The previous file is kept as `secrets.yaml.bak`.
- File paths from providers (secure notes) are confined to `/config/secrets_files`: absolute paths, `..`, backslashes
  and symlink escapes are rejected, files get mode 600.
- A shrink guard refuses a write when the item count drops sharply (default: more than 30 %), a key that exists in two
  sources is an error and nothing is written for that cycle.
- Triggering sync from the UI (POST) is only possible through Ingress.
- The add-on holds your vault master password. Restrict access to the add-on configuration and its backups accordingly,
  and prefer a dedicated Bitwarden account or collection with read-only access.

## Configuration

Enable a provider in `providers` and fill its block (`bitwarden` or `sops`). A missing or incomplete block is shown as a
problem in the UI and in `state.json`; the add-on keeps running.

See [DOCS.md][docs] for all options, the key naming scheme and the Gatus conditions.

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
