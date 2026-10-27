# Changelog

All notable changes to the **Secrets Sync** add-on are documented in this file. The add-on is our own code with no
upstream project, so every entry is add-on specific.

## [0.2.0-0] - 2026-10-27

- Feature: secret usage. The add-on scans YAML files for `!secret <key>` and shows keys that are referenced but missing,
  unused keys and the use count with `file:line` locations in the web page (`usage` in `state.json`). New option
  `usage_scan` (`off`, `config`, `all`, default `all`); `all` maps the configs of other add-ons read-only
  (`all_addon_configs:ro`). Event `secret_missing` for referenced keys that are not in `secrets.yaml`.

## [0.1.2-0] - 2026-10-27

- Debug: with `log_level: debug` the Bitwarden provider logs organizations (id, name), collections (id, name,
  organization) and every vault item (name, type, organization, collection ids, whether it was selected). No values and
  no other item fields are logged.
- Info log per sync: number of items listed and whether the organization/collection filter is set.
- `organization_id` / `collection_id` accept the display name or the UUID (names are resolved through `bw list`).
  Unknown or ambiguous names fail with a clear error.
- Warning `bw_filter_empty` when a filter matches no items. Provider notices are now also reported when the cycle fails
  (for example by the shrink guard).

## [0.1.1-0] - 2026-10-27

- Diagnostics: a failed provider now reports its reason in the events (for a rejected Bitwarden login: which server was
  used and which options to check). No secret values are included.

## [0.1.0-1] - 2026-10-27

- Fix: options could not be saved ("Missing option 'bitwarden?'"). The `bitwarden` and `sops` blocks are now always
  present with defaults; HA does not support optional dict keys.

## [0.1.0-0] - 2026-10-27

- Initial release: sync secrets from Bitwarden (`bw` CLI, API key login) and SOPS (age) into `/config/secrets.yaml` and
  optional files below `/config/secrets_files`.
- Ingress status page with per-provider status, key names (added/removed/changed), events, "Sync now" and "Preview".
- `/api/health` and `/api/status.json` for Gatus, optional on port 8099/tcp.
- Safety nets: atomic verified writes, shrink guard, collision detection, last good file is kept on any error.
