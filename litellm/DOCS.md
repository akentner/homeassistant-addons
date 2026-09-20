# Home Assistant Add-on: LiteLLM

OpenAI-compatible API gateway with bundled PostgreSQL — virtual keys, spend tracking, and model routing for HA
Conversation and homelab apps.

## About

[LiteLLM][litellm] is an OpenAI-compatible API gateway that proxies 100+ LLM providers (OpenAI, Anthropic, Google,
Azure, Ollama, Bedrock, …) behind a single auth surface and persists virtual keys + spend logs + model definitions in
PostgreSQL. This add-on bundles LiteLLM + PostgreSQL in a single HA Supervisor add-on for LAN / Tailscale deployment.

## Install

1. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add
   `https://github.com/akentner/homeassistant-addons`.
2. Search for **LiteLLM** in the Add-on Store, click it, then **Install**.
3. Start the add-on. The first start generates a fresh master key (see First Start below).

## First Start

On the first start, `run.sh` generates a master key and logs it via `bashio::log.notice` (one-time emission). Subsequent
restarts reload the key from `/data/.litellm_master_key` silently.

1. Open the add-on log in the HA UI.
2. Find the line reading `litellm_master_key=sk-…` (64 hex chars after the `sk-` prefix).
3. Go to **Settings → Add-ons → LiteLLM → Configuration** and paste the full string (including `sk-`) into the
   `master_key` field.
4. Restart the add-on. Subsequent restarts will load the key from the Configuration tab; the auto-gen branch in `run.sh`
   is skipped.

Salt key follows the identical pattern (key is in `/data/.litellm_salt_key`; log line is `litellm_salt_key=…` without
`sk-` prefix; enter in the `salt_key` field of the Configuration tab).

## Adding Models

Models are managed **through the litellm UI** (UI → Models → Add Model), not via HA Configuration. The add-on sets
`STORE_MODEL_IN_DB=True` by default — model definitions persist in PostgreSQL and survive restarts. Provider API keys
are also entered in the litellm UI (UI → Models → Add Model → Credentials) and stored in the same DB.

The litellm UI is reachable at:

- **HA Ingress:** HA sidebar → LiteLLM
- **Direct port:** `http://<ha-host>:4000/ui` (Swagger UI is at `http://<ha-host>:4000/`)

Provider-specific notes:

| Provider  | `api_base` (if custom)                 | `api_key` source                                                  |
| --------- | -------------------------------------- | ----------------------------------------------------------------- |
| OpenAI    | (default)                              | [platform.openai.com](https://platform.openai.com)                |
| Anthropic | (default)                              | [console.anthropic.com](https://console.anthropic.com)            |
| Google    | (default)                              | [aistudio.google.com](https://aistudio.google.com)                |
| Azure     | `https://<resource>.openai.azure.com/` | Azure portal                                                      |
| MiniMax   | `https://api.minimax.com/v1`           | MiniMax dashboard                                                 |
| Ollama    | `http://<ollama-host>:11434/v1`        | (none — LAN-only)                                                 |
| Bedrock   | (default)                              | AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (set via `env.litellm`) |
| Custom    | `https://<your-endpoint>/v1`           | Custom                                                            |

For providers not listed in litellm's native provider list (MiniMax, custom OpenAI-compatible endpoints, internal
gateways), select **OpenAI-compatible** in the UI and set `api_base` to the endpoint root. litellm uses the OpenAI
client class internally with the custom base.

## HA Conversation Integration

After the master key is set in the add-on's Configuration tab, add this to your HA Core `configuration.yaml`:

```yaml
openai_conversation:
  api_base: http://litellm:4000/v1
  api_key: sk-...
```

Where `sk-...` is the master key you pasted into the Configuration tab (or read directly from
`/data/.litellm_master_key` if you set up HA secrets externally).

The `litellm:4000` hostname is HA Supervisor's DNS for the add-on (HA-OS-version-specific; works on 2026.x and later).
Alternative: use the direct LAN/Tailscale URL (see below).

## Direct Port Access

From HA Core (via HA Supervisor DNS):

```text
http://litellm:4000/v1
```

From LAN / Tailscale clients:

```text
http://<ha-host>:4000/v1
```

The Swagger UI is also accessible via Ingress at `https://<ha-host>/api/hassio_ingress/litellm/`.

## Options

Secrets are configured via the HA Add-on Configuration tab (not `secrets.yaml`). The empty-string defaults trigger the
`run.sh` auto-gen branch for `master_key` and `salt_key`; provider keys without a value cause LiteLLM to log a clear
"missing API key" error for the affected model.

| Option                                | Type   | Default    | Description                                                             |
| ------------------------------------- | ------ | ---------- | ----------------------------------------------------------------------- |
| `log_level`                           | enum   | `info`     | bashio → LiteLLM log level (`debug`/`info`/`warning`/`error`)           |
| `master_key`                          | secret | (auto-gen) | Master key — leave blank for auto-gen, or paste a `sk-…` string         |
| `salt_key`                            | secret | (auto-gen) | Salt key — leave blank for auto-gen (no `sk-` prefix)                   |
| `ingress_origin`                      | string | `""`       | HA origin for ingress framing (see "HA Ingress" below)                  |
| `env.litellm[]`                       | list   | `[]`       | Extra env vars exported into the litellm process (see "Extra Env Vars") |
| `env.postgres[]`                      | list   | `[]`       | Extra env vars inlined into every postgres invocation                   |
| `env.valkey[]`                        | list   | `[]`       | Extra env vars exported into the valkey-server process                  |
| `postgres.shared_buffers`             | string | `64MB`     | Postgres `shared_buffers` setting (SIGHUP-reloadable)                   |
| `postgres.max_connections`            | int    | `20`       | Postgres `max_connections` setting (**restart required**)               |
| `postgres.log_min_duration_statement` | int    | `1000`     | Query log threshold (ms; SIGHUP-reloadable; `0` = log all)              |

Each `env.*` list entry has two fields: `name` (UPPER_SNAKE_CASE POSIX env-var name) and `value` (string).

## Extra Env Vars

Use the `env.{litellm,postgres,valkey}` lists to set additional environment variables on each service. Each entry is a
`{name, value}` pair. Example:

```yaml
env:
  litellm:
    - name: "LITELLM_LOG"
      value: "DEBUG"
    - name: "AWS_ACCESS_KEY_ID"
      value: "AKIA..."
    - name: "AWS_SECRET_ACCESS_KEY"
      value: "..."
  postgres:
    - name: "POSTGRES_INITDB_ARGS"
      value: "--encoding=UTF8 --locale=C"
  valkey:
    - name: "VALKEY_PASSWORD"
      value: "..."
```

### `env.litellm`

Exported into the litellm process environment **before** the wrapper starts. Useful for any litellm env var not exposed
as an add-on option (UI login, telemetry, cache TTLs, AWS creds for Bedrock, etc.). Reference: the [litellm proxy
docs][litellm-env] list every supported variable.

`STORE_MODEL_IN_DB=True` is **always** exported by default — overriding it via `env.litellm` is supported but disables
DB-backed model management (the UI will reject `/model/new` with an error if you set it to `False`).

### `env.postgres`

Inlined as `KEY=VALUE` prefixes into every `su -s /bin/bash postgres -c "..."` invocation (initdb, pg_ctl, psql). The
postgres server itself reads very few env vars at runtime — most useful entries are **libpq defaults** for the psql
client (PGUSER, PGHOST, PGDATABASE, PGPORT, PGOPTIONS, PGSSLMODE, …) and `POSTGRES_INITDB_ARGS` for first-start init.

Note: `PGUSER`/`PGHOST`/etc. only affect psql commands inside this container (DB/user creation, `SHOW max_connections`).
They do **not** propagate to litellm, which connects via the explicit
`DATABASE_URL=postgresql://litellm:…@127.0.0.1:5432/litellm`.

### `env.valkey`

Exported into the run.sh shell so `valkey-server` inherits them. valkey-server honors very few env-driven knobs natively
— `VALKEY_PASSWORD` is the most useful, though the add-on does not currently translate it into `--requirepass` (the
server is bound to `127.0.0.1` only, so auth is optional). The list exists for future expansion and operator
experimentation.

## HA Ingress

The litellm UI uses `Content-Security-Policy: frame-ancestors 'none'` (hardcoded in litellm 1.101.0's
`ProxyServer.setup_csp_headers` — no upstream config knob). That blocks HA Supervisor's ingress iframe embedding with:

> Refused to display '<https://ha-nextgen.akentner.de/>' in a frame because an ancestor violates the following Content
> Security Policy directive: "frame-ancestors 'none'".

Set `ingress_origin` to your **bare** HA origin (no trailing slash, no path) to allow the ingress iframe:

| Value                            | Effect                                                                                                          |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `""` (empty / unset)             | CSP stays `frame-ancestors 'none'` — ingress blocked. Direct port (`:4000`) and HA Conversation API still work. |
| `https://ha-nextgen.akentner.de` | CSP becomes `frame-ancestors 'self' https://ha-nextgen.akentner.de` — HA sidebar iframe loads.                  |
| Any other origin                 | Same as above with that origin trusted.                                                                         |

The wrapper at `/app/run_litellm.py` subclasses `litellm.proxy.proxy_server.ProxyServer` and overrides
`setup_csp_headers()` with an HTTP middleware that rewrites the `frame-ancestors` directive when `INGRESS_ORIGIN` is
set. `run.sh` reads `ingress_origin` via `bashio::config` and exports it as `INGRESS_ORIGIN` before launching the
wrapper. Restart the add-on after changing this field (the middleware is registered once at proxy startup).

## Postgres Tuning

`shared_buffers` and `log_min_duration_statement` are SIGHUP-reloadable: changes take effect on the next add-on restart
without a separate Postgres restart.

`max_connections` requires a **full Postgres restart** to take effect. After changing it, stop the add-on, then start it
again. The log line `postgres.tuning.max_connections=N requires restart — current value remains M` confirms the change
is queued for the next restart.

Hardcoded (non-tunable): `effective_cache_size = 256MB`, `work_mem = 4MB`.

## Backup & Restore

This add-on uses `map: backup: rw` to include all `/data` contents in HA Supervisor-managed backups:

- `/data/postgresql` — Postgres data directory (file-level backup; may be inconsistent on restore)
- `/data/.litellm_master_key` — persisted master key (chmod 600)
- `/data/.litellm_salt_key` — persisted salt key (chmod 600)
- `/data/.pg_password` — persisted Postgres password (chmod 600)
- `/data/litellm_config.yaml` — minimal litellm config (DB-stored models survive via the Postgres backup above)

### Postgres Reset Procedure

If the Postgres cluster becomes corrupted or you want to start fresh:

1. Stop the add-on.
2. Remove the data directory: `docker exec -it <container> rm -rf /data/postgresql` (or via the HA terminal add-on).
3. Start the add-on. `initdb` runs automatically on first start (idempotent — only runs when
   `/data/postgresql/PG_VERSION` is missing).
4. The litellm user and database are recreated automatically.
5. Spend logs and virtual keys are LOST (acceptable; restore from HA backup to recover). Model definitions are also lost
   — re-add them via the litellm UI.

The master key, salt key, and Postgres password persist across the reset (separate files, not affected by
`rm -rf /data/postgresql`).

## Auto-Update

This add-on tracks upstream LiteLLM releases via `.upstream.yaml`. The daily 06:00 UTC GitHub Actions workflow
auto-bumps `VERSION` + `args.LITELLM_VERSION` (synced via a guarded sed step in `.github/workflows/auto-update.yml`) +
`README.md` badge + CHANGELOG.md.

### Manual Override

For emergency bumps or rollbacks:

```bash
make release ADDON=litellm VERSION=X.Y.Z
```

This runs `internal/update-version.py` which updates all three version files + creates and pushes the `litellm/vX.Y.Z`
git tag.

## Troubleshooting

### "Failed to add model: ApiError: Set 'STORE_MODEL_IN_DB=True' in your env…"

This add-on sets `STORE_MODEL_IN_DB=True` by default, so this error means the running container predates the fix (or you
explicitly set `STORE_MODEL_IN_DB=False` in `env.litellm`). Update the add-on, remove the override, and restart.

### "401 Unauthorized" from a model

The provider key is missing in the litellm UI (UI → Models → your model → Credentials). Open the model entry, paste the
key, save. Restart is **not** required — litellm reloads model credentials live.

### Postgres won't start

Check `/data/postgresql.log` (in the add-on log viewer or via the HA terminal add-on). Common causes:

- `data directory has wrong ownership` — verify `/data/postgresql` is owned by `postgres:postgres`
- `lock file "postmaster.pid" already exists` — stale lock from a crashed Postgres; remove it via
  `docker exec -it <container> rm /data/postgresql/postmaster.pid` then restart

### Master-key reset

Delete `/data/.litellm_master_key` and restart the add-on. A new master key is auto-generated and logged via
`bashio::log.notice`. **Warning:** this invalidates all existing client sessions; update the `master_key` field in the
add-on Configuration tab and restart any clients using the old key.

### HA-Supervisor-DNS hostname check

The `litellm:4000` hostname (used in `openai_conversation.api_base`) is HA-OS-version-specific. Verify it resolves from
HA Core:

```bash
ha core dns resolve litellm
```

If the hostname doesn't resolve, use the LAN/Tailscale URL (`http://<ha-host>:4000/v1`) instead.

## Spike Result

Pending — see `internal/spike-litellm-secret-schema.sh`. Run the spike once on the operator's HA-OS instance and
document the result here.

[litellm]: https://github.com/BerriAI/litellm
[litellm-env]: https://docs.litellm.ai/docs/proxy/env_vars
