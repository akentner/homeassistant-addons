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

| Option                                | Type   | Default    | Description                                                                   |
| ------------------------------------- | ------ | ---------- | ----------------------------------------------------------------------------- |
| `log_level`                           | enum   | `info`     | bashio → LiteLLM log level (`debug`/`info`/`warning`/`error`)                 |
| `master_key`                          | secret | (auto-gen) | Master key — leave blank for auto-gen, or paste a `sk-…` string               |
| `salt_key`                            | secret | (auto-gen) | Salt key — leave blank for auto-gen (no `sk-` prefix)                         |
| `providers.openai_api_key`            | secret | `""`       | OpenAI API key                                                                |
| `providers.anthropic_api_key`         | secret | `""`       | Anthropic API key                                                             |
| `providers.google_api_key`            | secret | `""`       | Google AI Studio API key                                                      |
| `providers.azure_api_key`             | secret | `""`       | Azure OpenAI API key                                                          |
| `providers.minimax_api_key`           | secret | `""`       | MiniMax API key (M3/MiniMax-Text/etc — see "Custom Providers" below)          |
| `models`                              | list   | `[]`       | List of `{name, provider, api_base?, api_key?, model_name?, litellm_params?}` |
| `postgres.shared_buffers`             | string | `64MB`     | Postgres `shared_buffers` setting (SIGHUP-reloadable)                         |
| `postgres.max_connections`            | int    | `20`       | Postgres `max_connections` setting (**restart required**)                     |
| `postgres.log_min_duration_statement` | int    | `1000`     | Query log threshold (ms; SIGHUP-reloadable; `0` = log all)                    |

Model name regex: `^[a-zA-Z0-9._:/+-]{1,256}$` (allows `/` for LiteLLM path syntax like
`bedrock/anthropic.claude-3-5-sonnet`).

## Custom Providers (MiniMax, custom endpoints)

The `providers.<name>_api_key` fields are shortcuts for the built-in litellm provider list. For any other
OpenAI-compatible API (MiniMax, custom proxies, internal gateways, …) add a `models[]` entry with `provider` set to the
matching key:

```yaml
models:
  - name: "minimax-m3"
    provider: "minimax"
    api_base: "https://api.minimax.com/v1"
    model_name: "minimax-M3"
  - name: "internal-llama"
    provider: "custom_openai"
    api_base: "http://192.168.1.50:11434/v1"
    model_name: "llama3.1"
```

`generate_config.py` resolves the per-model `api_key` field by mapping the `provider` value to an env-var name. The
mapping is in `PROVIDER_ENV_VARS` inside `generate_config.py`; `provider="minimax"` → `${MINIMAX_API_KEY}`. Unknown
providers fall back to `${CUSTOM_API_KEY}`. Set the key in the `providers.<name>_api_key` Configuration-tab field; the
runtime export happens in `run.sh` after `generate_config.py` runs.

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
- `/data/litellm_config.yaml` — synthesized LiteLLM config

### Postgres Reset Procedure

If the Postgres cluster becomes corrupted or you want to start fresh:

1. Stop the add-on.
2. Remove the data directory: `docker exec -it <container> rm -rf /data/postgresql` (or via the HA terminal add-on).
3. Start the add-on. `initdb` runs automatically on first start (idempotent — only runs when
   `/data/postgresql/PG_VERSION` is missing).
4. The litellm user and database are recreated automatically.
5. Spend logs and virtual keys are LOST (acceptable; restore from HA backup to recover).

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

### "401 Unauthorized" from a model

The provider key (`openai_api_key`, `anthropic_api_key`, …) is missing. Set it in **Settings → Add-ons → LiteLLM →
Configuration** (under the `providers.*_api_key` field) and restart the add-on.

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
