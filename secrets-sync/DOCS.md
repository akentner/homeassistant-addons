# Secrets Sync

Syncs secrets from pluggable providers into `/config/secrets.yaml` and optional files below `/config/secrets_files`.

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml`, no
auto-update and ships its code in the add-on directory (the repo-wide "no bundled source" rule does not apply). Its
image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA base image only,
3-file version sync via `make update-version`, and a local `docker build` before every Dockerfile commit. Version bumps
are manual. The Bitwarden CLI version is pinned in `build.yaml` (`BW_CLI_VERSION`).

## Options

| Option                      | Default                     | Description                                                              |
| --------------------------- | --------------------------- | ------------------------------------------------------------------------ |
| `providers`                 | `[bitwarden]`               | Enabled providers, order = priority for `collision_policy: priority`     |
| `interval`                  | `300`                       | Seconds between cycles (60 to 86400); manual sync at most every 10 s     |
| `collision_policy`          | `error`                     | `error`: nothing is written on a duplicate key; `priority`: earlier wins |
| `shrink_guard_percent`      | `30`                        | Refuse to write when items drop by more than this share (1 to 100)       |
| `log_level`                 | `info`                      | `debug`, `info`, `warning`, `error`; values are never logged             |
| `bitwarden.server_url`      | `https://bitwarden.com`     | Server URL (also Vaultwarden)                                            |
| `bitwarden.client_id`       | empty                       | API key `client_id` (`user.xxxx`), passed via env                        |
| `bitwarden.client_secret`   | empty                       | API key `client_secret`, passed via env                                  |
| `bitwarden.master_password` | empty                       | Unlocks the vault, passed via env                                        |
| `bitwarden.organization_id` | empty                       | Optional: only items of this organization                                |
| `bitwarden.collection_id`   | empty                       | Optional: only items of this collection                                  |
| `bitwarden.key_style`       | `legacy`                    | Key naming scheme (only `legacy` so far)                                 |
| `bitwarden.notes_dir`       | `bitwarden`                 | Directory for secure-note files below `/config/secrets_files`            |
| `sops.file`                 | `/config/secrets.sops.yaml` | SOPS-encrypted YAML file                                                 |
| `sops.flatten_separator`    | `_`                         | Joins nested keys                                                        |

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

### Recommended: dedicated service user

Do not use your personal account. Create a separate Bitwarden/Vaultwarden user for the add-on:

1. Give it its own master password and API key (a leak then never exposes your personal vault).
2. Share only the collection with the secrets, with read-only access, and set `collection_id` (and `organization_id`) to
   that collection.
3. Use the organization UUID for `organization_id` (not the display name).
4. Rotate API key and master password if they ever appear in a log or an error message. Home Assistant prints the
   options into the error text when saving them fails.

### Legacy key naming

`key_style: legacy` builds the key from the item name (`<name>`):

1. Replace each of `? : & , % @ -` with a space
2. Replace each of `[ ] { } # * ! | >` and spaces with `_`
3. Squeeze repeated `_`, lowercase

| Item type      | Resulting keys                                                                       |
| -------------- | ------------------------------------------------------------------------------------ |
| Login          | `<name>_username`, `<name>_password`, `<name>_notes` (only if set)                   |
| Login URIs     | `<name>_uri_1`, `<name>_uri_2`, ... (1-based)                                        |
| Custom fields  | `<name>_<sanitised field name>`                                                      |
| Secure note    | File `<notes_dir>/<sanitised name>` (`.txt` appended if no extension), no secret key |
| Card, identity | Ignored (event `item_skipped`, count only)                                           |

Example: item `Mosquitto: Broker-1` with user and password becomes `mosquitto_broker_1_username` and
`mosquitto_broker_1_password`.

## SOPS provider

Decrypts `sops.file` with `sops -d` (output only in memory, no temp file). The age key must exist at
`/addon_config/age.key` as a regular file with mode `0600` or stricter. The file must contain a top-level `sops`
mapping, otherwise it is treated as not encrypted and rejected. Top-level scalars map 1:1, nested mappings are flattened
with `flatten_separator`. Lists and other non-scalars are reported as problems (key name only).

## Collisions and guards

- A key present twice (across providers or within one snapshot) is `key_collision` with `collision_policy: error`:
  nothing is written for that cycle. With `priority` the provider listed first in `providers` wins.
- If a provider fails after a restart, the cycle is `degraded` and nothing is written, so a partial merge never drops
  keys.
- The shrink guard (`shrink_guard_percent`) blocks writes with zero items or a sharp drop. It clears itself when a later
  cycle passes. A deliberate large removal needs one forced sync from the UI (`POST /api/sync?force=1`, Ingress only).

## Web UI and API

Ingress sidebar entry "Secrets Sync". Optional port `8099/tcp` serves only `GET /api/health` and `GET /api/status.json`;
the status page (`GET /`) and all POST routes work through Ingress only. A manual sync is possible when the last attempt
is at least 10 s old (the interval itself is at least 60 s).

| Route              | Method | Result                                                                                     |
| ------------------ | ------ | ------------------------------------------------------------------------------------------ |
| `/`                | GET    | Status page (Ingress only)                                                                 |
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
