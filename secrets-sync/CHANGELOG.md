# Changelog

All notable changes to the **Secrets Sync** add-on are documented in this file. The add-on is our own code with no
upstream project, so every entry is add-on specific.

## [0.4.4-0] - 2026-10-31

- Feature: when the shrink guard blocks a write, the overview page lists the key names that would be removed, added or
  changed and offers an "Apply anyway" button (forced sync, asks for confirmation). New `guard` block in `state.json`;
  names only, never values.

## [0.4.3-0] - 2026-10-31

- Feature: the overview page has a "Synthetic keys" card with every configured key, its template, the key names it uses
  and its status (`ok`, parsed but not rendered yet, or the error code such as `synthetic_syntax`,
  `synthetic_forbidden`, `synthetic_undefined`). New `synthetic` block in `state.json`.

## [0.4.2-0] - 2026-10-30

- Fix: after a master password change `bw unlock` failed forever with `bw_unlock_failed` because the locally cached key
  no longer matched the new password. The provider now logs in again once and retries the unlock; the error then says to
  check `master_password`.

## [0.4.1-0] - 2026-10-30

- Feature: Bitwarden SSH-key items (type 5) are exported as `<name>_public_key`. The private key (`<name>_private_key`)
  is exported only if the item has a custom field `secrets_sync_export_private_key` with value `true`. The
  `item_skipped` notice now counts only cards and identities.

## [0.4.0-0] - 2026-10-27

- Feature: synthetic keys. New option `synthetic_keys` (list of `name` + `template`) composes keys from other keys with
  a sandboxed Jinja template, e.g. a database URL from user and password (`urlquote`, `substr`, `default`, ...).
  Rendered values are never logged. The image now contains `py3-jinja2`.

## [0.3.1-0] - 2026-10-27

- Fix: archived and trashed Bitwarden items are no longer imported (`archivedDate`/`deletedDate`); only active items
  become secrets. Info event `item_inactive` reports the count.

## [0.3.0-0] - 2026-10-27

- Feature: SOPS git source. New `sops.source: git` with `git_url`, `git_branch`, `git_path`, `git_username`,
  `git_token`; SSH deploy key (`/addon_config/deploy_key`, read-only) or https token, selected by the URL. The image now
  contains `git` and `openssh-client`.
- Feature: change check. New option `check_interval` (default 60 s, 0 = off): a cheap `git ls-remote` starts a sync as
  soon as the repository changed; the regular `interval` stays as fallback. Result shown in the web page and in `check`
  of `state.json`.

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
