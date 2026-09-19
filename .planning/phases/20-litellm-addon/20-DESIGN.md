---
phase: 20-litellm-addon
plan: 01
type: design
wave: 0
depends_on: []
files_modified:
  - .planning/phases/20-litellm-addon/PLAN.md
autonomous: false
status: ideation
status_note: |
  Pre-execution design document. Captures conversation decisions from
  2026-09-19 (local LiteLLM evaluation → decision to ship as HA add-on).
  NOT yet ready for /gsd-execute-phase — split into executable plans
  once the open questions are resolved.
requirements:
  - LITELLM-01
  - LITELLM-02
  - LITELLM-03
  - LITELLM-04
  - LITELLM-05
  - LITELLM-06
  - LITELLM-07
  - LITELLM-08
  - LITELLM-09
  - LITELLM-10
must_haves:
  truths:
    - "An add-on directory `litellm/` follows the established 4-file pattern (config.yaml, build.yaml, Dockerfile,
      run.sh) + .upstream.yaml, matching every other shipped add-on in this repo"
    - "The container bundles PostgreSQL + LiteLLM in a single image using HA base images only — no generic
      postgres:16-alpine / python:3.12-slim base — following the authentik precedent for multi-service in one image"
    - "PostgreSQL and LiteLLM are supervised via bash-sequential start in run.sh (postgres → wait → litellm via
      `exec`) — no s6-overlay, matching the authentik precedent"
    - "The HA-UI Options schema exposes models: [] (empty default), per-provider api_key fields with !secret
      support, master_key + salt_key with !secret + auto-gen fallback, and a `postgres` tuning block with small-home
      defaults"
    - "The add-on exposes port 4000 both via HA Ingress (Swagger UI in HA UI) and via direct port mapping (API for
      LAN/Tailscale clients)"
    - "Renovate-equivalent (.upstream.yaml + .github/workflows/auto-update.yml) bumps the LiteLLM pin on each
      upstream release"
  artifacts: []
  key_links: []
---

<objective>
Design a Home Assistant Supervisor add-on (`litellm/`) that bundles LiteLLM (OpenAI-compatible API gateway) and
PostgreSQL (state store for virtual keys, spend logs, model definitions) in a single container, deployed primarily on
the local network (LAN + Tailscale) for Home Assistant Conversation integration and other homelab apps.

Purpose: HA-Conversation + HA-Automation callers need an OpenAI-compatible endpoint that proxies many providers
(OpenAI, Anthropic, Ollama on `pve`, etc.) with one auth surface and persistent state. Bundling PostgreSQL avoids
shipping a sibling `litellm-postgres` add-on, at the cost of the add-on image carrying both runtimes.

Output: this document captures the decisions from a 2026-09-19 design conversation. It is NOT a runnable plan — when
the user wants to ship the add-on, the open questions section splits this into executable plans (one per phase,
following the iac-runner pattern).

Requirements satisfied (when implemented):

- LITELLM-01 — Add-on scaffold (4-file pattern + .upstream.yaml)
- LITELLM-02 — Multi-stage Dockerfile (HA-debian-trixie base + LiteLLM pip-install + postgres apt-install + run.sh)
- LITELLM-03 — run.sh: bash-sequential start (postgres initdb on first run → wait → litellm exec)
- LITELLM-04 — config.yaml: schema with models + provider keys (!secret) + master/salt (!secret + auto-gen) +
  postgres tuning block + ingress + ports 4000/tcp
- LITELLM-05 — Master/salt key lifecycle: !secret default + auto-generated fallback persisted in /data/
- LITELLM-06 — Postgres tuning defaults (shared_buffers=64MB, max_connections=20, log_min_duration_statement=1000) +
  Options override with `pg_reload_conf` for SIGHUP-reloadable settings
- LITELLM-07 — Auto-update via .upstream.yaml tracking LiteLLM releases
- LITELLM-08 — LAN-primary exposure (direct port 4000) + Ingress (Swagger UI in HA UI)
- LITELLM-09 — DOCS.md: operator reference (HA-Conversation config, master-key retrieval, postgres reset, options
  schema, troubleshooting)
- LITELLM-10 — README.md: add-on entry in root repo README + add-on shield badges (3-file versioning aligned)

Out of scope (decided):

- Multi-arch builds (aarch64, armv7) — matches repo-wide convention; both current hosts are x86_64
- Cloudflare-fronted exposure (`litellm.akentner.de` + CF Tunnel + CF Access) — LAN-primary, no public surface needed
- Splitting into `litellm` + `litellm-postgres` sibling add-ons — single image is the explicit user decision
- HA Ingress WebSocket streaming — direct port handles streaming; Ingress only for Swagger UI HTML
- HA-WebSocket-based custom integration — MQTT Discovery is the existing add-on pattern (see iac-runner Phase 18)
- SQLite fallback — PostgreSQL is mandatory; SQLite not worth the dual-code-path
- OAuth/PKCE flow for HA-Auth — Master-key bearer is sufficient for LAN
- Web-based admin UI — LiteLLM's Swagger UI is sufficient; no custom panel
</objective>

<execution_context>
This document is NOT an executable plan. It is a design doc that captures the decisions needed before splitting into
GSD executable plans. When ready to ship, the user runs `/gsd-plan-phase 20` (or the GSD equivalent) and the GSD
planner breaks this into N execution plans following the iac-runner pattern (4 plans for v1.4 iac-runner, 7 plans
for v1.3 opentofu-bridge — both visible under `.planning/phases/16-...` and `.planning/phases/09-...`).

No code is to be authored from this document directly. Use it as the input to the GSD plan-phase workflow.
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/codebase/CONVENTIONS.md (when present)

# Pattern sources — read these BEFORE implementing:

@authentik/run.sh (lines 1-119) — the proven multi-service-in-one-container pattern in this repo. Specifically:
- PostgreSQL start via `su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl ... start"`
- Wait-for-ready via `until pg_isready -h 127.0.0.1; do sleep 1; done`
- Optional service (Valkey) daemonized via `--daemonize yes` + same wait-for-ready pattern
- Final service via `exec runuser -u <user> -- <binary>` (PID1, foreground)
- Persistent secrets in `/data/.<keyfile>` with `openssl`/`tr -dc` generation, idempotent first-start logic

@authentik/Dockerfile (lines 1-77) — the proven multi-stage HA-debian build:
- `ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie` declared BEFORE first FROM
- Stage 1 pulls upstream binary (here: LiteLLM via pip wheelhouse)
- Stage 2 starts from `${BUILD_FROM}`, `apt-get install postgresql ...` adds the runtime DB
- COPY --from=stage-1 brings the binary in
- COPY run.sh + chmod +x + CMD ["/run.sh"]

@authentik/config.yaml — the proven multi-service add-on manifest shape:
- `init: false` (we want our own startup ordering, not supervisor-managed init)
- `host_network: false` (postgresql on 127.0.0.1, liteLLM also on 127.0.0.1)
- `arch: [amd64]` (single-arch like iac-runner, terraform-bridge, gatus, network-tools, phone-logger)
- `ports: { 9000/tcp: 9000 }` + `ports_description` — direct port access for LAN clients
- No `ingress: true` (authentik chose direct-port-only because OAuth callback URLs need stable external addresses;
  LiteLLM uses Ingress because Swagger UI in HA UI is a nice-to-have, with direct port for the API)

@iac-runner/config.yaml (lines 1-47) — the proven list-of-dict Options pattern + schema validation:
- `repos: [{name, url, branch?, ref?}]` is the only proven list-of-dict in this repo
- Schema uses HA Supervisor's match() / list() / int(1,N) / bool? / str? vocabulary
- `services: ["mqtt:need"]` + `homeassistant_api: true` is the proven HA-MQTT-Discovery wiring (liteLLM does NOT
  need this — it's a passive API server, not an entity publisher)

@iac-runner/build.yaml (lines 1-6) — the proven minimal HA-base build.yaml:
- `build_from: { amd64: "ghcr.io/home-assistant/amd64-base:3.24" }`
- `args: { VERSION: "X.Y.Z", RUNNER_VERSION: "X.Y.Z" }` — VERSION is the add-on's published version; the second
  arg is the upstream binary version

@gatus/Dockerfile (lines 1-30) — the proven upstream-binary-download pattern:
- Stage 1 downloads upstream release artifact
- Stage 2 starts from HA base, COPY --from=stage-1 brings the binary
- We mirror this for LiteLLM: stage 1 = `pip wheel` produces a tarball, stage 2 = HA-debian + postgres + COPY

@network-tools/Dockerfile (lines 1-30) — the proven `apk add --no-cache` runtime pattern (we use `apt-get install`
on debian instead, matching authentik)

# Conversation context (2026-09-19):

User evaluated LiteLLM locally via `podman-compose` against `https://docs.litellm.ai/docker-compose.yml` — ran
into three layered problems (rootless podman bridge netlink failure, legacy docker-compose v1 fallback in podman,
`network_mode: host` requirement to talk to LAN-side postgres). After working through those, the user pivoted to
"should this become an HA add-on?". Local eval confirmed LiteLLM itself works (Swagger UI at /, /health/readiness
returns `{"status":"healthy","db":"connected"}`); add-on is the natural next step.

Decisions made during the conversation (all in this document, not yet in CONVENTIONS.md or PROJECT.md).

# Out of Scope clarification (cross-reference):

PROJECT.md "Out of Scope" lists `Multi-arch builds (arm64, armv7)` and other items. LiteLLM inherits the
multi-arch exclusion.
</context>

<design>

## 1. Identity and Add-on Structure

- Add-on name: `LiteLLM` (display name)
- Add-on slug: `litellm` (HA Supervisor internal identifier, used as DNS name for HA-Core → add-on calls)
- Add-on description: `OpenAI-compatible API gateway with bundled PostgreSQL — virtual keys, spend tracking,
  model routing for HA Conversation and homelab apps`
- Lives at: `litellm/{config.yaml, build.yaml, Dockerfile, run.sh, README.md, DOCS.md, .upstream.yaml}`
- 4-file pattern matching every other shipped add-on in the repo (no new directories under `litellm/`)
- 3-file versioning enforced: `config.yaml` (`X.Y.Z-N`), `build.yaml` (`X.Y.Z`), `README.md` shields (`vX.Y.Z`)
- Architecture: `amd64` only (matches iac-runner, terraform-bridge, gatus, network-tools, phone-logger; multi-arch
  explicitly out-of-scope per PROJECT.md)

## 2. Image Build (Multi-Stage Dockerfile)

Stage 1 — pip-install LiteLLM into a wheelhouse:

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.13-debian-trixie
ARG VERSION

FROM python:3.13-slim-bookworm AS litellm-builder

ARG LITELLM_VERSION
RUN pip wheel --wheel-dir=/wheels \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
        "prisma==0.*"
```

Stage 2 — HA-debian base + postgres + LiteLLM (mirrors `authentik/Dockerfile`):

```dockerfile
FROM ${BUILD_FROM}
ARG VERSION
ARG LITELLM_VERSION

# apt-get pattern from authentik (lines 15-25)
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql \
        postgresql-client \
        curl \
        jq \
        bash \
        libssl3 \
        libffi8 \
    && rm -rf /var/lib/apt/lists/*

# LiteLLM runtime
COPY --from=litellm-builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels \
        "litellm[proxy]==${LITELLM_VERSION}" \
        "psycopg[binary]==3.2.*" \
    && rm -rf /wheels

# Add-on startup
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 4000
CMD ["/run.sh"]
```

**Build args** in `build.yaml`:

```yaml
build_from:
  amd64: "ghcr.io/home-assistant/amd64-base-debian:trixie"
args:
  VERSION: "0.1.0"
  LITELLM_VERSION: "1.40.0"
```

**Why two versions:**
- `VERSION` is the add-on's published version (3-file versioning scheme)
- `LITELLM_VERSION` is the upstream LiteLLM version the image is built against
- Subpatch `-N` in `config.yaml` covers add-on-only changes (Dockerfile, run.sh, schema); SemVer `X.Y.Z` change
  aligns with `LITELLM_VERSION` bump via `.upstream.yaml`

## 3. config.yaml Manifest (Schema)

```yaml
name: "LiteLLM"
description: "OpenAI-compatible API gateway with bundled PostgreSQL for HA Conversation and homelab apps."
version: "0.1.0-0"
slug: "litellm"
init: false
arch:
  - amd64
url: "https://github.com/akentner/homeassistant-addons"
startup: "application"
boot: "manual"
host_network: false
ingress: true
ingress_port: 4000
ports:
  4000/tcp: 4000
ports_description:
  4000/tcp: "OpenAI-compatible API (HTTP) — direct port for LAN/Tailscale clients"
map:
  - type: addon_config
    read_only: false
    path: /addon_config

options:
  log_level: "info"
  master_key: !secret litellm_master_key
  salt_key: !secret litellm_salt_key
  providers:
    openai_api_key: !secret openai_api_key
    anthropic_api_key: !secret anthropic_api_key
    google_api_key: !secret google_api_key
    azure_api_key: !secret azure_api_key
  models: []
  postgres:
    shared_buffers: "64MB"
    max_connections: 20
    log_min_duration_statement: 1000

schema:
  log_level: "list(debug|info|warning|error)?"
  master_key: "password?"
  salt_key: "password?"
  providers:
    openai_api_key: "password?"
    anthropic_api_key: "password?"
    google_api_key: "password?"
    azure_api_key: "password?"
  models:
    - name: "match(^[a-zA-Z0-9._:-]{1,128}$)"
      provider: "list(openai|anthropic|google|azure|ollama|bedrock)"
      api_base: "url?"
  postgres:
    shared_buffers: "str?"
    max_connections: "int(5,200)?"
    log_min_duration_statement: "int(0,60000)?"
```

**Key design choices:**

- `init: false` — we control startup ordering in run.sh, not Supervisor init system (matches authentik precedent)
- `host_network: false` — both postgres and litellm bind to 127.0.0.1 inside the container; only port 4000 is
  exposed to the host network
- `ingress: true` + `ingress_port: 4000` — Swagger UI accessible via `https://<ha-host>/api/hassio_ingress/<slug>/`
  for browser access from HA UI; streaming/long-poll API clients use direct port 4000 instead
- `ports: { 4000/tcp: 4000 }` — direct LAN/Tailscale access for HA Conversation, custom apps, and `curl` testing
- `master_key: !secret litellm_master_key` + `salt_key: !secret litellm_salt_key` — HA Supervisor resolves
  `!secret` against HA Core's `secrets.yaml` before the add-on starts; if unresolved (empty), run.sh auto-generates
- `providers: { ...: !secret ... }` — operator puts keys in `secrets.yaml`, never in HA UI
- `models: []` — empty default; operator configures models via HA UI (per add-on use case)
- `postgres: { ... }` — Options schema for tuning overrides; small-home defaults baked in

## 4. run.sh (Bash Sequential Start)

Mirrors `authentik/run.sh` lines 1-119. Sequential pattern: postgres → wait → liteLLM `exec`. No s6-overlay.

```bash
#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# ── Options ──────────────────────────────────────────────────────────────────
LOG_LEVEL=$(bashio::config 'log_level' 'info')

# ── Master/Salt key: !secret → /data/ → auto-gen ──────────────────────────────
MASTER_KEY_FILE=/data/.litellm_master_key
SALT_KEY_FILE=/data/.litellm_salt_key

MASTER_KEY=$(bashio::config 'master_key' '')
if [ -z "${MASTER_KEY}" ] && [ -f "${MASTER_KEY_FILE}" ]; then
    MASTER_KEY=$(cat "${MASTER_KEY_FILE}")
fi
if [ -z "${MASTER_KEY}" ]; then
    bashio::log.warning "master_key not in secrets.yaml and not in /data — auto-generating"
    MASTER_KEY="sk-$(openssl rand -hex 32)"
    echo "${MASTER_KEY}" > "${MASTER_KEY_FILE}"
    chmod 600 "${MASTER_KEY_FILE}"
fi
export LITELLM_MASTER_KEY="${MASTER_KEY}"

# (analogous for salt_key)

# ── PostgreSQL setup ─────────────────────────────────────────────────────────
PG_VERSION=$(find /usr/lib/postgresql/ -maxdepth 1 -mindepth 1 -type d | sort -V | tail -1 | xargs basename)
PG_BIN="/usr/lib/postgresql/${PG_VERSION}/bin"
PG_DATA=/data/postgresql
PG_PASS_FILE=/data/.pg_password

if [ ! -f "${PG_PASS_FILE}" ]; then
    bashio::log.info "Generating PostgreSQL password..."
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40 > "${PG_PASS_FILE}"
    chmod 600 "${PG_PASS_FILE}"
fi
PG_PASS=$(cat "${PG_PASS_FILE}")

mkdir -p "${PG_DATA}"
chown postgres:postgres "${PG_DATA}"

if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    bashio::log.info "Initializing PostgreSQL ${PG_VERSION} database..."
    su -s /bin/bash postgres -c "${PG_BIN}/initdb -D ${PG_DATA} --encoding=UTF8 --locale=C"
    echo "host litellm litellm 127.0.0.1/32 md5" >> "${PG_DATA}/pg_hba.conf"
fi

# ── Apply user-supplied postgres tuning (pg_reload_conf-friendly) ───────────
SHARED_BUFFERS=$(bashio::config 'postgres.shared_buffers' '64MB')
MAX_CONNECTIONS=$(bashio::config 'postgres.max_connections' '20')
LOG_MIN_DURATION=$(bashio::config 'postgres.log_min_duration_statement' '1000')
cat > "${PG_DATA}/litellm-tuning.conf" <<EOF
shared_buffers = ${SHARED_BUFFERS}
log_min_duration_statement = ${LOG_MIN_DURATION}
EOF
# max_connections needs restart; apply via postgresql.conf.append if differs from default
chown postgres:postgres "${PG_DATA}/litellm-tuning.conf"

bashio::log.info "Starting PostgreSQL..."
su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl -D ${PG_DATA} -o '-h 127.0.0.1' -l /data/postgresql.log start"

until su -s /bin/bash postgres -c "${PG_BIN}/pg_isready -h 127.0.0.1" 2>/dev/null; do
    sleep 1
done

# Create database/user on first start
su -s /bin/bash postgres -c "psql -h 127.0.0.1 -tAc \"SELECT 1 FROM pg_roles WHERE rolname='litellm'\"" 2>/dev/null \
    | grep -q 1 || {
    bashio::log.info "Creating litellm PostgreSQL user and database..."
    su -s /bin/bash postgres -c "psql -h 127.0.0.1 -c \"CREATE USER litellm WITH PASSWORD '${PG_PASS}';\""
    su -s /bin/bash postgres -c "psql -h 127.0.0.1 -c \"CREATE DATABASE litellm OWNER litellm;\""
}

# Reload tuning.conf (SIGHUP to postgres picks up shared_buffers/log_min_duration)
su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl -D ${PG_DATA} reload"

# ── Build LiteLLM config.yaml from Options ───────────────────────────────────
LITELLM_CONFIG=/data/litellm_config.yaml
bashio::var.json \
    log_level "$(bashio::config 'log_level' 'info')" \
    | jq -r '... (transform options + models list into LiteLLM YAML)' > "${LITELLM_CONFIG}"

# ── Start LiteLLM (PID1, foreground) ─────────────────────────────────────────
export DATABASE_URL="postgresql://litellm:${PG_PASS}@127.0.0.1:5432/litellm"
exec litellm --config "${LITELLM_CONFIG}"
```

**Why bash-sequential, not s6-overlay:** the authentik add-on already runs PostgreSQL + Valkey + Authentik in one
container via this exact pattern. Proving s6-overlay is unnecessary in this repo. Trade-off: postgres crash
triggers container restart, which HA Supervisor handles via `restart: always` (proven across all add-ons).

## 5. Master/Salt Key Lifecycle (Hybrid)

- **Default in schema:** `!secret litellm_master_key` — operator puts the key in HA Core `secrets.yaml`
- **Fallback 1:** persisted in `/data/.litellm_master_key` (chmod 600) — survives container restart
- **Fallback 2:** auto-generated via `openssl rand -hex 32` on first start; one-time `bashio::log.warning` printed
  with the generated key for operator to capture
- **Operator workflow:** on first install, copy the auto-generated key from add-on log → paste into
  `~/.homeassistant/secrets.yaml` as `litellm_master_key: sk-...`; restart add-on to pick up the
  `!secret`-resolved value going forward
- **HA Conversation integration** in HA Core `configuration.yaml`:
  ```yaml
  openai_conversation:
    api_base: !secret litellm_api_base        # http://litellm:4000/v1
    api_key: !secret litellm_master_key
  ```
- **Salt key** follows the identical pattern
- **Provider keys (OpenAI, Anthropic, etc.):** `!secret` only — never auto-generated (operator MUST supply)

## 6. Postgres Tuning (Small-Home Defaults)

| Setting                         | Default  | Options override | Reload semantics     |
| ------------------------------- | -------- | ---------------- | -------------------- |
| `shared_buffers`                | `64MB`   | yes              | `pg_reload_conf`     |
| `max_connections`               | `20`     | yes              | **requires restart** |
| `log_min_duration_statement` (ms)| `1000`   | yes              | `pg_reload_conf`     |
| `effective_cache_size`          | `256MB`  | no (fixed)       | `pg_reload_conf`     |
| `work_mem`                      | `4MB`    | no (fixed)       | `pg_reload_conf`     |

**Implementation:** `/data/postgresql/litellm-tuning.conf` with the three operator-tunable settings; rest are
hardcoded in `postgresql.conf` via `include_if_exists` directive. On options change via HA UI, run.sh rewrites
`tuning.conf` and triggers `pg_ctl reload`. `max_connections` changes are documented as "restart required" in
DOCS.md.

## 7. Auto-Update via .upstream.yaml

```yaml
upstream:
  repository: "BerriAI/litellm"
  version_pattern: "v*"
  version_strip: "^v"

addon:
  version_pattern: "sync"  # add-on version tracks upstream exactly
```

Mirrors the proven `gatus/.upstream.yaml` pattern. Triggers daily workflow (06:00 UTC) via
`.github/workflows/auto-update.yml` → commits 3-file version update + CHANGELOG.md entry → automated multi-arch
build via `.github/workflows/build.yml` → image at `ghcr.io/akentner/homeassistant-addons/litellm`.

**No auto-merge** — same rationale as `gatus`: LiteLLM upstream sometimes breaks small API fields; manual review
keeps regressions out of the auto-pipeline.

## 8. Network Exposure (LAN-Primary)

- **Direct port 4000** — primary API access path for HA Conversation + LAN/Tailscale clients
  - From HA Core: `http://litellm:4000/v1` (Supervisor-managed DNS)
  - From LAN: `http://<ha-host>:4000/v1` (HA host LAN IP, e.g. 192.168.x.x)
  - From Tailscale: `http://<ha-host>.<tailnet>.ts.net:4000/v1` (HA host on tailnet, if Tailscale runs on HA-OS)
- **Ingress port 4000** — Swagger UI in HA UI (read-only docs, no streaming)
- **Auth** — `LITELLM_MASTER_KEY` enforced on every `/v1/*` request; LAN-side trust is the network layer
- **NOT exposed:** Cloudflare-fronted `litellm.akentner.de` — explicitly out of scope per user decision 2026-09-19
- **No `host_network: true`** — postgres stays on 127.0.0.1 inside the container; only port 4000 reaches host net

## 9. Verification Strategy (Post-Implementation)

When split into GSD executable plans, the verification surface will mirror iac-runner Phase 19:

1. Install add-on on live `haos-op3050-1`; `/health/liveliness` returns 200
2. End-to-end `/v1/chat/completions` call with a real model (OpenAI or local Ollama on `pve` via Tailscale)
3. HA Conversation integration in `configuration.yaml` → speak to HA → LiteLLM routes to model → response
4. Spend tracking persists across restart: insert key, run test call, `SELECT spend FROM litellm.spend_logs`
5. Master-key auto-gen → operator copies → restart → still works (rotation-less)
6. Provider-key `!secret` resolution: omit `openai_api_key` from `secrets.yaml` → add-on starts with empty key →
   requests to OpenAI models return 401 with clear error
7. Postgres tuning reload: change `log_min_duration_statement` via HA UI → next slow query logs with new threshold
8. `make update-version ADDON=litellm VERSION=0.2.0` succeeds; pre-commit `validate-versions.sh` passes
9. Auto-update workflow bumps to upstream release; CI builds multi-arch image; image appears at ghcr.io

</design>

<open_questions>

These questions block splitting into GSD executable plans. Resolve before invoking `/gsd-plan-phase 20`.

1. **CI workflow** — does this add-on need its own `.github/workflows/build-iac-runner.yml`-equivalent, or does the
   unified `.github/workflows/build.yml` (added in iac-runner quick 260909-rln) cover it? Lean toward unified (it
   already auto-discovers add-ons with `config.yaml`+`build.yaml`).

2. **HA Conversation URL discovery** — does HA Supervisor resolve `litellm:4000` for HA-Core → add-on calls on this
   HA-OS version (2026.x), or do we need a different hostname pattern? Check via
   `kubectl exec`/`ha addons info litellm` after first install. (The internal-DNS hostname is HA-version-specific.)

3. **Tailscale reachability from HA-OS add-on** — if user wants LiteLLM to call Ollama on `pve` via Tailscale IP,
   is the Tailscale add-on installed on `haos-op3050-1`? If not, the `ollama` model provider in Options can't
   actually route. Decide: document as prerequisite, or stub out the network reachability test.

4. **TLS termination** — direct port 4000 is plain HTTP. For Tailscale-only LAN use that's fine (Tailscale
   encrypts). For any direct LAN exposure (no Tailscale), the operator must put a reverse proxy in front. Document
   in DOCS.md, or add Caddy/Traefik via separate add-on?

5. **Prisma migrations on LiteLLM upgrade** — does upgrading `LITELLM_VERSION` (via Renovate bump) require manual
   `prisma migrate deploy` step, or does the LiteLLM entrypoint handle this automatically? Empirical check needed
   before Phase 19 E2E.

6. **`prometheus_multiproc_dir`** — authentik sets this to a writable tmp dir (line 84-86 of authentik/run.sh).
   Does LiteLLM have an equivalent multiprocess metric requirement when run via uvicorn --workers? Decide based on
   whether we run uvicorn with `--workers > 1` (we probably don't — single-worker keeps the schema simple).

7. **Postgres version drift** — Debian Trixie's `postgresql` package is 15.x; LiteLLM upstream expects 16+
   (LiteLLM 1.40+ prisma schema may require 16). Verify Debian Trixie ships PG 16 by 2026-09; if not, fall back to
   PGDG apt repo (`apt.postgresql.org`) for PG 16.

8. **`password?` schema with `!secret`** — does HA Supervisor's schema parser actually accept `!secret` references
   in `options:` defaults combined with `password?` in `schema:`? Empirical test on a test add-on before
   LITELLM-04 plan execution.

9. **Master-key surface discipline** — when auto-generated, the master-key plaintext is logged via `bashio::log`.
   Is that acceptable for the v1.5 release, or do we want a `/data/.litellm_master_key`-only approach with the
   operator reading the file via HA terminal add-on? The log line is easier UX; the file-only approach is more
   defensible. Lean toward log-once (matches authentik precedent for `.pg_password`).

10. **3-file versioning for a non-upstream add-on** — iac-runner, terraform-bridge don't have `.upstream.yaml`
    (they don't track an external project). With `.upstream.yaml`, do we still need 3-file versioning? Yes (matches
    gatus precedent: `gatus/` has both `.upstream.yaml` AND 3-file versioning enforced). Document the
    interaction: Renovate bumps `LITELLM_VERSION` in `build.yaml`, then `make update-version` syncs
    `config.yaml`/`README.md` to match.

</open_questions>

<references>

- `authentik/run.sh` lines 1-119 — multi-service-in-one-container via bash sequential start
- `authentik/Dockerfile` lines 1-77 — multi-stage HA-debian build with upstream-binary stage
- `authentik/config.yaml` lines 1-42 — multi-service add-on manifest shape (init: false, ports, map)
- `iac-runner/config.yaml` lines 1-47 — list-of-dict Options + schema vocabulary
- `iac-runner/build.yaml` lines 1-6 — minimal HA-base build.yaml with VERSION + binary-version args
- `gatus/.upstream.yaml` (referenced, not quoted here) — auto-update tracking pattern
- `network-tools/Dockerfile` — runtime-package-install pattern (we use apt instead of apk)
- `internal/validate-addon-config.py` lines 9-22 — REQUIRED_FIELDS / VALID_ARCH / VALID_STARTUP / VALID_BOOT for
  config.yaml validation
- Home Assistant Add-on Schema reference — https://developers.home-assistant.io/docs/add-ons/configuration
- LiteLLM configuration reference — https://docs.litellm.ai/docs/proxy/configs

</references>

<!--
This document is intentionally NOT executable. To convert to GSD executable plans:

1. Resolve all open questions (above) via conversation or empirical spike
2. Run `/gsd-plan-phase 20` (or equivalent) to split into N execution plans
3. Each plan gets `NN-PLAN.md` format with `<objective>`, `<tasks>`, `<verification>` sections
4. Likely split (mirroring v1.4 iac-runner's 4-phase structure):
   - 20-01: Scaffold (4-file pattern + multi-stage Dockerfile + bash-sequential run.sh skeleton)
   - 20-02: Master/salt lifecycle + Postgres setup + tuning.conf (LITELLM-05, LITELLM-06)
   - 20-03: Options schema + !secret wiring + LiteLLM config synthesis from bashio::config (LITELLM-04)
   - 20-04: Live-HA E2E + DOCS + operator runbook (LITELLM-09)
   - 20-05: Auto-update via .upstream.yaml (LITELLM-07)

The exact plan count is TBD — depends on what the user wants as separate verification gates.
-->
