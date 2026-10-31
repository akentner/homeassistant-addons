# Secrets Sync

Syncs secrets from pluggable providers into `/config/secrets.yaml` and optional files below `/config/secrets_files`.

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml`, no
auto-update and ships its code in the add-on directory (the repo-wide "no bundled source" rule does not apply). Its
image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA base image only,
3-file version sync via `make update-version`, and a local `docker build` before every Dockerfile commit. Version bumps
are manual. The Bitwarden CLI version is pinned in `build.yaml` (`BW_CLI_VERSION`).

## Options

| Option                      | Default                     | Description                                                                                  |
| --------------------------- | --------------------------- | -------------------------------------------------------------------------------------------- |
| `providers`                 | `[bitwarden]`               | Enabled providers, order = priority for `collision_policy: priority`                         |
| `interval`                  | `300`                       | Seconds between cycles (60 to 86400); manual sync at most every 10 s                         |
| `check_interval`            | `60`                        | Seconds between cheap change checks of the SOPS git source (0 = off, 1 to 29 become 30)      |
| `collision_policy`          | `error`                     | `error`: nothing is written on a duplicate key; `priority`: earlier wins                     |
| `shrink_guard_percent`      | `30`                        | Refuse to write when items drop by more than this share (1 to 100)                           |
| `log_level`                 | `info`                      | `debug`, `info`, `warning`, `error`; values are never logged                                 |
| `usage_scan`                | `all`                       | `off`, `config` (HA config) or `all` (plus other add-on configs, read-only)                  |
| `synthetic_keys`            | `[]`                        | List of `name` + `template`; keys composed from other keys (see "Synthetic keys")            |
| `bitwarden.server_url`      | `https://bitwarden.com`     | Server URL (also Vaultwarden)                                                                |
| `bitwarden.client_id`       | empty                       | API key `client_id` (`user.xxxx`), passed via env                                            |
| `bitwarden.client_secret`   | empty                       | API key `client_secret`, passed via env                                                      |
| `bitwarden.master_password` | empty                       | Unlocks the vault, passed via env                                                            |
| `bitwarden.organization_id` | empty                       | Optional: only items of this organization (name or UUID)                                     |
| `bitwarden.collection_id`   | empty                       | Optional: only items of this collection (name or UUID)                                       |
| `bitwarden.key_style`       | `legacy`                    | Key naming scheme (only `legacy` so far)                                                     |
| `bitwarden.notes_dir`       | `bitwarden`                 | Directory for secure-note files below `/config/secrets_files`                                |
| `sops.source`               | `file`                      | `file` (local path) or `git` (repository)                                                    |
| `sops.file`                 | `/config/secrets.sops.yaml` | SOPS-encrypted YAML file                                                                     |
| `sops.flatten_separator`    | `_`                         | Joins nested keys                                                                            |
| `sops.git_url`              | empty                       | Repository URL: `git@host:org/repo.git`, `ssh://...` or `https://...`, no credentials inside |
| `sops.git_branch`           | `main`                      | Branch to read                                                                               |
| `sops.git_path`             | `secrets.sops.yaml`         | Path of the encrypted file in the repository                                                 |
| `sops.git_username`         | `x-access-token`            | User name for https token login                                                              |
| `sops.git_token`            | empty                       | https access token, passed via env only                                                      |

Both provider blocks are always present in the options. Missing or empty parts are reported as problems (UI and
`state.json`) and the provider is skipped, the add-on keeps running.

## Paths

| Path                       | Purpose                                                               |
| -------------------------- | --------------------------------------------------------------------- |
| `/config/secrets.yaml`     | Target, sorted keys, header `# managed by Secrets Sync - do not edit` |
| `/config/secrets.yaml.bak` | Previous version                                                      |
| `/config/secrets_files/`   | Files from providers (secure notes), tracked in a manifest            |
| `/addon_config/age.key`    | age private key for the SOPS provider (mode 600 or stricter)          |
| `/data/state.json`         | State contract (no secret values)                                     |

The first successful run **replaces an existing `secrets.yaml`**; the old file is kept as `secrets.yaml.bak` (the backup
is overwritten on every later write, so copy it away if you need the original). Files in the manifest that vanish from
all snapshots are deleted. Files in `secrets_files` that are not in the manifest (unmanaged) are never touched and never
overwritten.

On the host, the `/addon_config` folder (age key) is `/addon_configs/<repository-hash>_secrets_sync/` (for example
reachable through the Samba or SSH add-on). `/config` is the normal Home Assistant configuration directory.

## Bitwarden provider

Needs a personal API key (Bitwarden web vault: Account settings, Security, Keys, "View API key") plus the master
password. The vault is read with `bw sync` and `bw list items`, restricted by organization/collection when configured.

### Why the master password is needed

The API key only authenticates against the server; the vault stays locked. Bitwarden encrypts end to end, so the client
derives the decryption key from the master password (`bw unlock`). Without it `bw list items` cannot read names or
values, organization items included. Bitwarden Secrets Manager (`bws`, access tokens) works without a master password,
but it is a different product with a different data model and Vaultwarden does not support it.

### Organization and collection names (debug log)

`organization_id` and `collection_id` accept the display name or the UUID (the web vault does not show the UUID of an
organization). Names are resolved with `bw list organizations` / `bw list collections`; an unknown name reports which
names the service user can see, an ambiguous one asks for the UUID. A filter that matches no items yields zero items and
the shrink guard then refuses to write (event `bw_filter_empty`). Set `log_level` to `debug` and restart the add-on to
list what the service user can see, including the UUIDs:

```text
bitwarden debug: org id=<uuid> name='My Org'
bitwarden debug: collection id=<uuid> name='Secrets' org=<uuid>
bitwarden debug: item 'Router' type=login org=<uuid> collections=<uuid> selected=True
```

Only names, ids, item types and the selection result are logged; no values and no other item fields.

### Recommended: dedicated service user

Do not use your personal account. Create a separate Bitwarden/Vaultwarden user for the add-on:

1. Give it its own master password and API key (a leak then never exposes your personal vault).
2. Share only the collection with the secrets, with read-only access, and set `collection_id` (and `organization_id`) to
   that collection.
3. Set `organization_id` to the organization name or UUID.
4. Rotate API key and master password if they ever appear in a log or an error message. Home Assistant prints the
   options into the error text when saving them fails.

### Legacy key naming

`key_style: legacy` builds the key from the item name (`<name>`):

1. Replace each of `? : & , % @ -` with a space
2. Replace each of `[ ] { } # * ! | >` and spaces with `_`
3. Squeeze repeated `_`, lowercase

| Item type        | Resulting keys                                                                                                                    |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Login            | `<name>_username`, `<name>_password`, `<name>_notes` (only if set)                                                                |
| Login URIs       | `<name>_uri_1`, `<name>_uri_2`, ... (1-based)                                                                                     |
| Custom fields    | `<name>_<sanitised field name>`                                                                                                   |
| Secure note      | File `<notes_dir>/<sanitised name>` (`.txt` appended if no extension), no secret key                                              |
| SSH key (type 5) | Secret `<name>_public_key`; `<name>_private_key` only if the item has the custom field `secrets_sync_export_private_key` = `true` |
| Card, identity   | Ignored (event `item_skipped`, count only)                                                                                        |
| Archived/trashed | Ignored (event `item_inactive`, count only); only active items are imported                                                       |

Example: item `Mosquitto: Broker-1` with user and password becomes `mosquitto_broker_1_username` and
`mosquitto_broker_1_password`.

## Synthetic keys

Synthetic keys are composed from other keys with a small, sandboxed Jinja template, for example a database URL from
separate user and password keys. They are rendered after all providers were merged and before the shrink guard and the
write, so they work with every provider. Result: a normal key in `secrets.yaml`.

```yaml
synthetic_keys:
  - name: db_dsn
    template: "postgresql://{{ db_user | urlquote }}:{{ db_password | urlquote }}@db:5432/ha"
```

- `name` must match `^[A-Za-z_][A-Za-z0-9_]{0,127}$` and be unique among synthetic keys (`synthetic_invalid_name`).
- `template` must not be empty and may have at most 2048 characters (`synthetic_template_too_long`).
- A name that already exists as a real key is an error (`synthetic_collision`); a synthetic key never overrides a real
  one, independent of `collision_policy`.
- **Synthetic keys cannot reference each other.** Every template only sees the real, merged keys, so there is no
  chaining and no ordering problem.

### Context

- `secrets`: read-only mapping of all real keys, e.g. `{{ secrets['db-password'] }}`. Use it for key names that are not
  valid identifiers.
- Every real key whose name is a valid identifier is also a direct variable: `{{ db_user }}`.
- A reference to a key that does not exist is an error (`synthetic_undefined`), not an empty string. Use `default` to
  allow a fallback.

### Filters

Only these filters are available; any other filter is rejected with `synthetic_forbidden`.

| Filter                       | Result                                                                           |
| ---------------------------- | -------------------------------------------------------------------------------- |
| `lower`, `upper`, `trim`     | case conversion, strip whitespace                                                |
| `capitalize`, `title`        | capitalisation                                                                   |
| `replace(old, new)`          | replace text                                                                     |
| `default(value)`             | fallback for an undefined or empty value                                         |
| `length`                     | number of characters                                                             |
| `join(sep)`                  | join a list                                                                      |
| `b64encode`, `b64decode`     | Base64                                                                           |
| `substr(start, length=None)` | Python slice semantics, negative start allowed, never fails when out of range    |
| `urlquote`                   | percent-encodes everything including `/` and `@` (`urllib.parse.quote(safe="")`) |

Jinja's own `urlencode` is deliberately not offered because it keeps `/`.

### Allowed and forbidden constructs

Allowed: `{{ ... }}` output, plain text, `{% if %}` / `{% elif %}` / `{% else %}`, names, constants, `secrets[...]`,
filters from the table, comparisons, `and` / `or` / `not`, `+` and `~` (concatenation), conditional expressions
(`a if x else b`) and list/tuple literals.

Forbidden (error `synthetic_forbidden`): `for`, `set`, macros, `call`, filter blocks, `import`, `include`, `extends`,
`block`, attribute access, calls other than filters (no `range`, `dict`, `lipsum`, ...) and the operators `*`, `**`,
`%`, `//`. The templates run in Jinja's immutable sandbox without loader, extensions or globals.

### Examples

```yaml
synthetic_keys:
  # PostgreSQL DSN: special characters in the password must be percent-encoded
  - name: db_dsn
    template: "postgresql://{{ db_user | urlquote }}:{{ db_password | urlquote }}@db:5432/ha"
  # MQTT URL with a key whose name is not an identifier
  - name: mqtt_url
    template: "mqtt://{{ secrets['mqtt-user'] }}:{{ secrets['mqtt-password'] | urlquote }}@broker:1883"
  # First 8 characters, for example a short token identifier
  - name: api_token_short
    template: "{{ api_token | substr(0, 8) }}"
  # Optional part with a fallback
  - name: db_host_port
    template: "{{ db_host }}:{{ db_port | default('5432') }}"
```

### Errors

A synthetic error is a cycle error like a key collision: nothing is written, the last good `secrets.yaml` stays and the
status becomes `degraded` (or `error` if nothing was ever written). The event names the code and the synthetic key.

| Code                          | Meaning                                                                    |
| ----------------------------- | -------------------------------------------------------------------------- |
| `synthetic_invalid_name`      | name does not match the pattern, or is used twice (config problem)         |
| `synthetic_template_too_long` | template longer than 2048 characters                                       |
| `synthetic_collision`         | name already exists as a real key                                          |
| `synthetic_syntax`            | template has a syntax error                                                |
| `synthetic_forbidden`         | forbidden construct or filter                                              |
| `synthetic_undefined`         | referenced key does not exist (message: synthetic name and referenced key) |
| `synthetic_too_large`         | rendered value longer than 65536 characters                                |
| `synthetic_error`             | any other error while rendering                                            |

**Rendered values are secrets** (a DSN contains the password). They are never logged and never appear in `state.json`,
events, error messages, the web page or the preview. Messages are built from the error class and key names only, never
from Jinja's own message text. `keys.synthetic` in `state.json` lists the names of synthetic keys in the written set;
they count in `items` and in the shrink guard like real keys.

### Overview page

The overview page has a "Synthetic keys" card: key name, the configured template, the key names it uses and the status
(`ok`, parsed but not rendered yet when the cycle ended earlier, or the error code). Syntax errors and forbidden
constructs show up immediately, even while a provider is failing. Templates are configuration, not values, and are part
of `/api/status.json`: never write a literal secret into a template, always reference keys.

## Secret usage

The add-on scans YAML files for `!secret <key>` and compares the result with the keys in `secrets.yaml`. The web page
shows three lists; nothing is ever deleted automatically.

- **Referenced but missing**: a file references a key that is not in `secrets.yaml` (Home Assistant would fail to load
  it). Also reported as warning event `secret_missing`.
- **Unused**: keys in `secrets.yaml` that no scanned file references.
- **Used**: keys with their use count and the first locations (`file:line`).

Rules: only `.yaml`/`.yml` files are read, hidden folders (`.storage`, `.git`, ...), `custom_components`, `deps`,
`backups` and `secrets_files` are skipped, symlinks and files above 1 MiB are ignored, commented lines are ignored.
`!secret` is resolved like Home Assistant does it: against the nearest `secrets.yaml` in the file's folder or a parent
folder, so ESPHome files next to their own `secrets.yaml` do not count for ours. With `usage_scan: all`, the add-on also
reads `/addon_configs` (mapped read-only via `all_addon_configs`); files there count only when no `secrets.yaml` of
their own is found. Limits: 20000 files and 20 s per scan; the scan runs after every cycle, at most once a minute. The
state (`state.json`, key `usage`) contains key names and file/line positions only, never values.

UI-managed configuration (dashboards, integrations, `.storage`) cannot reference `!secret` and is not covered.

## SOPS provider

Decrypts `sops.file` with `sops -d` (output only in memory, no temp file). The age key must exist at
`/addon_config/age.key` as a regular file with mode `0600` or stricter. The file must contain a top-level `sops`
mapping, otherwise it is treated as not encrypted and rejected. Top-level scalars map 1:1, nested mappings are flattened
with `flatten_separator`. Lists and other non-scalars are reported as problems (key name only).

### Git source

With `sops.source: git` the encrypted file is read from a git repository instead of `sops.file`. The repository holds
the same SOPS-encrypted YAML file as before (any path, set `git_path`); it must contain the top-level `sops` mapping.
The **age key is still required** at `/addon_config/age.key` (mode 600): git only transports the encrypted file, it is
decrypted in memory as before. The add-on keeps a shallow clone (`--depth 1`, single branch) in `/data/git`.

The URL decides the authentication:

| URL                                  | Authentication                                          |
| ------------------------------------ | ------------------------------------------------------- |
| `git@host:org/repo.git`, `ssh://...` | SSH deploy key `/addon_config/deploy_key`               |
| `https://...`                        | token (`git_username` + `git_token`), or none if public |

#### SSH deploy key (read-only)

1. Create a dedicated key without passphrase: `ssh-keygen -t ed25519 -N "" -C secrets-sync -f deploy_key`
2. Add `deploy_key.pub` to the repository as a **read-only** deploy key (GitHub: Settings, Deploy keys, leave "Allow
   write access" off; GitLab: Settings, Repository, Deploy keys).
3. Copy the private key `deploy_key` to `/addon_config/deploy_key` (host:
   `/addon_configs/<repository-hash>_secrets_sync/`) and set mode 600. Any other mode is rejected with
   `git_key_permissions`.
4. Optional: put your `known_hosts` lines at `/addon_config/known_hosts`. Then the host key is verified strictly.
   Without that file the first seen host key is trusted and persisted in `/data/known_hosts` (trust on first use).

#### https token

Create a fine-grained personal access token with read-only access to that one repository (GitHub: repository permission
Contents = Read-only). Set `git_url` to the `https://` URL (without credentials) and `git_token`. `git_username` is
`x-access-token` for GitHub and `oauth2` for GitLab. The token is handed to git through an askpass helper from the
environment; it is never part of the URL, argv, logs or `state.json`. Public repositories need no token.

#### Change check

Every `check_interval` seconds (default 60) the add-on runs a cheap `git ls-remote` for the branch. When the commit
changed since the last successful sync, a full sync starts right away (event `source_changed`). The regular `interval`
stays as a fallback and always fetches. `check_interval: 0` turns the check off; values 1 to 29 are raised to 30. A
failing check never changes the status and never triggers a backoff; it is shown in the status page and in `check` of
`state.json` (`result`: `unchanged`, `changed`, `error`, `unsupported`) and raises the event `check_failed` once per
distinct code. The file source and Bitwarden are not probed.

#### Git error codes

| Code                  | Meaning                                                                     |
| --------------------- | --------------------------------------------------------------------------- |
| `git_binary_missing`  | `git` or `ssh` not found in the image                                       |
| `git_timeout`         | a git call ran into its timeout (60 s, `ls-remote` 20 s)                    |
| `git_auth_failed`     | permission denied / 401 / 403: wrong key, deploy key not added, bad token   |
| `git_clone_failed`    | clone failed (URL, network)                                                 |
| `git_fetch_failed`    | fetch failed; the cache is re-cloned once per cycle                         |
| `git_ref_not_found`   | branch does not exist                                                       |
| `git_exec_failed`     | git could not be started                                                    |
| `git_key_missing`     | ssh URL but no `/addon_config/deploy_key`                                   |
| `git_key_permissions` | deploy key is not a regular file with mode 600 or stricter                  |
| `git_path_invalid`    | `git_path` empty, absolute, contains `..`, a backslash, or leaves the clone |
| `git_file_missing`    | `git_path` is not a regular file in the checked-out branch                  |

Configuration problems reported by validation: `sops_git_missing_url`, `sops_git_url_credentials` (credentials inside
the URL), `sops_git_url_scheme` (only ssh and https), `sops_git_path_invalid`, `sops_git_branch_invalid`.

## Collisions and guards

- A key present twice (across providers or within one snapshot) is `key_collision` with `collision_policy: error`:
  nothing is written for that cycle. With `priority` the provider listed first in `providers` wins.
- If a provider fails after a restart, the cycle is `degraded` and nothing is written, so a partial merge never drops
  keys.
- The shrink guard (`shrink_guard_percent`) blocks writes with zero items or a sharp drop. It clears itself when a later
  cycle passes. When it blocks a write, the overview page lists the key names that would be removed, added or changed
  and offers an "Apply anyway" button (forced sync after a confirmation; `POST /api/sync?force=1`, Ingress only). Zero
  items are never forced.

## Web UI and API

Ingress sidebar entry "Secrets Sync". Optional port `8099/tcp` serves only `GET /api/health` and `GET /api/status.json`;
the status page (`GET /`) and all POST routes work through Ingress only. A manual sync is possible when the last attempt
is at least 10 s old (the interval itself is at least 60 s).

The page has a fixed top bar (status, items, last sync, version, buttons) and tabs for keys, synthetic keys, key usage
and events. It loads `api/status.json` and refreshes every 15 s, or when you press Refresh. The tab selection is kept
(URL hash `#keys`, `#synthetic`, `#usage`, `#events`). When the shrink guard blocks a write, a card under the top bar
lists the key names that would be removed, added or changed and offers "Apply anyway". A double-click on any key name
copies it to the clipboard.

| Route              | Method | Result                                                                                     |
| ------------------ | ------ | ------------------------------------------------------------------------------------------ |
| `/`                | GET    | Status page shell and `static/app.js`, `static/app.css` (Ingress only)                     |
| `/api/status.json` | GET    | Full state (key names only)                                                                |
| `/api/health`      | GET    | `{"status","age_seconds","stale","items","error_code"}`; 200 if ok and not stale, else 503 |
| `/api/sync`        | POST   | 202 started, 429 rate limited, `?force=1` lifts the shrink guard once (Ingress only)       |
| `/api/preview`     | POST   | Key names that would be written (Ingress only)                                             |

`status` is one of `starting`, `ok`, `degraded` (guard, collision, partial or provider error with a valid last file) or
`error` (nothing ever written or unusable config). `stale` means the last success is older than twice the interval.

### Gatus

Enable port 8099/tcp (or use the internal hostname) and add:

```yaml
endpoints:
  - name: Secrets Sync
    url: "http://72a005f5-secrets-sync:8099/api/health"
    interval: 5m
    conditions:
      - "[STATUS] == 200"
      - "[BODY].age_seconds < 900"
```

`[STATUS] == 200` already covers `status == ok` and not stale (503 otherwise). `age_seconds < 900` additionally alerts
when syncing stalls for three default intervals. Add `[BODY].items > 0` to alert on an empty vault.
