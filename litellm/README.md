# LiteLLM

[![Release][release-shield]][release] ![Project Stage][project-stage-shield]
![Supports amd64 Architecture][amd64-shield]

OpenAI-compatible API gateway with bundled PostgreSQL — virtual keys, spend tracking, and model routing for HA
Conversation and homelab apps.

## About

[LiteLLM][litellm] is an OpenAI-compatible API gateway that proxies 100+ LLM providers (OpenAI, Anthropic, Google,
Azure, Ollama, Bedrock, …) behind a single auth surface and persists virtual keys + spend logs + model definitions in
PostgreSQL. This add-on bundles LiteLLM + PostgreSQL in a single HA Supervisor add-on for LAN / Tailscale deployment,
with HA Ingress for Swagger UI access from the HA UI sidebar.

## Features

- **Bundled PostgreSQL** — no external database add-on needed; LiteLLM's virtual keys + spend logs + model definitions
  persist across restarts
- **100+ LLM providers** — OpenAI, Anthropic, Google, Azure, Ollama, Bedrock, custom OpenAI-compatible endpoints, all
  routable through one `master_key`
- **DB-backed model management** — `STORE_MODEL_IN_DB=True` by default; add and edit models via the litellm UI (HA
  Ingress or direct port), no add-on restart needed
- **Master-key auto-generation** — first-start emits a one-time log line with the plaintext key; operator pastes it into
  the add-on Configuration tab for HA Conversation integration
- **HA Conversation integration** — drop-in `api_base` for the standard `openai_conversation:` integration in HA Core
- **Direct LAN/Tailscale access** — port 4000/tcp on the HA host; HA Ingress for Swagger UI
- **Extra env vars per service** — `env.{litellm,postgres,valkey}` lists let you set arbitrary additional env vars on
  each backing service (litellm proxy vars, libpq defaults, valkey knobs)
- **Postgres tuning** — `shared_buffers` + `log_min_duration_statement` apply via SIGHUP-reload (no restart);
  `max_connections` requires restart (documented)
- **Auto-update** — daily 06:00 UTC bumps the upstream LiteLLM pin via `.upstream.yaml`; manual override via
  `make release ADDON=litellm VERSION=X.Y.Z`
- **HA Backup integration** — `map: backup: rw` includes all runtime state in HA Supervisor-managed backups

## Install

1. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add
   `https://github.com/akentner/homeassistant-addons`.
2. Search for **LiteLLM** in the Add-on Store, click it, then **Install**.
3. Start the add-on. The first start generates a fresh master key (see First Start below).

## First Start

1. Open the add-on log in the HA UI.
2. Find the line reading `litellm_master_key=sk-…` (64 hex chars after the `sk-` prefix).
3. Go to **Settings → Add-ons → LiteLLM → Configuration** and paste the full string (including `sk-`) into the
   `master_key` field.
4. Restart the add-on. Subsequent restarts load the key from the Configuration tab; the auto-gen branch in `run.sh` is
   skipped.

## Configuration

See [DOCS.md][docs] for the full options schema, the HA Conversation integration snippet, the Postgres reset procedure,
and troubleshooting.

[release-shield]: https://img.shields.io/badge/version-v1.102.1-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/litellm/v0.1.0
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[docs]: https://github.com/akentner/homeassistant-addons/blob/main/litellm/DOCS.md
[litellm]: https://github.com/BerriAI/litellm
