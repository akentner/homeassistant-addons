---
phase: 20-litellm-addon
plan: 01
subsystem: infra
tags: [home-assistant, addon, litellm, scaffold, postgres, pgdg]

# Dependency graph
requires:
  - phase: 20-context
    provides: D-01..D-35 design decisions captured in 20-CONTEXT.md
provides:
  - litellm/ 4-file scaffold (config.yaml, build.yaml, Dockerfile, run.sh)
  - litellm/.upstream.yaml (BerriAI/litellm sync tracking)
  - litellm/generate_config.py (HA options.json → LiteLLM YAML envelope)
  - litellm/README.md + .gitignore
  - Root README.md LiteLLM entry
affects: [20-02, 20-03, 20-04]

# Actuals (#2632)
actuals:
  tokens: 2700
  tasks: 2
  commits: 5

# Tech tracking
tech-stack:
  added: [litellm[proxy]==1.40.0, psycopg[binary]==3.2.*, prisma==0.*, postgresql-16 (PGDG), pyyaml]
  patterns: [multi-stage Dockerfile with python:3.13-slim-bookworm builder, bashio with-contenv + set -e, bash-sequential postgres init]

key-files:
  created:
    - litellm/config.yaml
    - litellm/build.yaml
    - litellm/Dockerfile
    - litellm/run.sh
    - litellm/.upstream.yaml
    - litellm/README.md
    - litellm/.gitignore
    - litellm/generate_config.py
  modified:
    - README.md

key-decisions:
  - "PGDG repo + PostgreSQL 16 (not Debian Trixie default 15.x) — PLAN.md Q7 resolution applied to Dockerfile"
  - "Python helper over bash+jq for generate_config.py (D-17) — phone-logger precedent; Python is already in wheelhouse"
  - "Plan 01 ships minimal envelope (model_list + empty general_settings); Plan 02 expands to master/salt env-var references"

patterns-established:
  - "Pattern: HA add-on scaffold = config.yaml + build.yaml + Dockerfile + run.sh + README.md + .upstream.yaml + .gitignore (8 files)"
  - "Pattern: Multi-stage Dockerfile — python:slim builder → ${BUILD_FROM} HA base; ARG BUILD_FROM before first FROM"
  - "Pattern: bash-sequential Postgres lifecycle — version detection → initdb-if-missing → pg_hba entry → pg_ctl start → pg_isready wait → idempotent user/db create"

requirements-completed:
  - LITELLM-01
  - LITELLM-02
  - LITELLM-03
  - LITELLM-08

coverage:
  - id: D1
    description: "litellm/ 4-file HA Supervisor add-on scaffold matching iac-runner/gatus/authentik pattern (config.yaml, build.yaml, Dockerfile, run.sh) + .upstream.yaml + .gitignore + README.md"
    requirement: "LITELLM-01"
    verification:
      - kind: automated
        ref: "python3 internal/validate-addon-config.py litellm"
        status: pass
      - kind: automated
        ref: "yamllint litellm/config.yaml"
        status: pass
    human_judgment: false
  - id: D2
    description: "Multi-stage Dockerfile (python:3.13-slim-bookworm AS litellm-builder → ${BUILD_FROM} ha-debian-trixie) with PGDG postgresql-16 per PLAN.md Q7, full OCI label block, ARG BUILD_FROM before first FROM"
    requirement: "LITELLM-02"
    verification:
      - kind: automated
        ref: "bash internal/validate-dockerfile-args.sh litellm/Dockerfile"
        status: pass
      - kind: automated
        ref: "pre-commit run hadolint --files litellm/Dockerfile"
        status: pass
    human_judgment: false
  - id: D3
    description: "run.sh bash-sequential Postgres lifecycle (initdb-if-missing → pg_hba entry → pg_ctl start → pg_isready wait → idempotent user/db create → generate_config.py → exec litellm) with bashio set -e + signal-trap placeholders"
    requirement: "LITELLM-03"
    verification:
      - kind: automated
        ref: "shellcheck litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D4
    description: "generate_config.py — Python helper transforming HA options.json → LiteLLM YAML envelope (model_list + general_settings); Plan 02 expands to env-var references for secrets"
    requirement: "LITELLM-04"
    verification:
      - kind: automated
        ref: "python3 -c \"import sys; sys.path.insert(0, 'litellm'); from generate_config import transform; print(transform({'models': []}))\""
        status: pass
    human_judgment: false
  - id: D5
    description: "Root README.md LiteLLM entry between iac-runner and gatus"
    requirement: "LITELLM-08"
    verification:
      - kind: automated
        ref: "grep -c '### \\[LiteLLM\\]' README.md"
        status: pass
    human_judgment: false

# Metrics
duration: 35min
completed: 2026-09-19
status: complete
---

# Phase 20 Plan 01: litellm/ HA Supervisor Add-on Scaffold + generate_config.py

**Scaffolded litellm/ HA Supervisor add-on (4-file pattern + .upstream.yaml + .gitignore + README) and generate_config.py Python helper for HA options.json → LiteLLM YAML envelope**

## Performance

- **Duration:** ~35 min (planning + scaffold + PGDG fixup + generate_config.py)
- **Started:** 2026-09-19T16:47:00Z (state.stopped_at)
- **Completed:** 2026-09-19T20:11:00Z
- **Tasks:** 2 of 2 complete
- **Files modified:** 9 (8 litellm/ + root README.md)

## Accomplishments

- Scaffolded litellm/ HA Supervisor add-on matching the established 4-file pattern (config.yaml, build.yaml, Dockerfile, run.sh) + .upstream.yaml + .gitignore + README.md
- Multi-stage Dockerfile: python:3.13-slim-bookworm AS litellm-builder (pip wheel litellm + psycopg + prisma) → ${BUILD_FROM} ha-debian-trixie runtime; PGDG repo + postgresql-16 per PLAN.md Q7 (not Debian default 15.x)
- run.sh bashio wrapper with set -e + signal-trap placeholders + bash-sequential Postgres lifecycle (initdb-if-missing, pg_hba.conf entry, pg_ctl start, pg_isready wait, idempotent user/db create) + generate_config.py invocation + exec litellm
- generate_config.py transforms HA options.json (nested-dict schema) → LiteLLM proxy config.yaml (model_list envelope); Plan 02 will expand to env-var references for master_key/salt_key so secrets stay out of /data/litellm_config.yaml
- Root README.md updated with LiteLLM entry between iac-runner and gatus (shield, description, 5-bullet feature list)
- .upstream.yaml mirrors gatus shape: upstream.repository=BerriAI/litellm, version_pattern=v*, version_strip=^v, addon.version_pattern=sync

## Task Commits

Each task was committed atomically:

1. **Task 1a: 4-file scaffold + .upstream.yaml + .gitignore + root README entry** — `493eb71` (feat)
2. **Task 1b: PGDG alignment fixup** — `f490894` (fix)
3. **Task 2: generate_config.py Python helper** — `cebe063` (feat)

**Plan metadata:**
- `e0df1a1` (docs: commit phase 20 plan files + pre-exec design snapshot)
- `fcb14cd` (docs: resolve 4 open questions, update PLAN.md)
- `958ef21` (docs: phase 20 plans written, current_phase 17→20)

## Files Created/Modified

- `litellm/config.yaml` — HA Supervisor manifest: slug=litellm, version=0.1.0-0, arch=[amd64], startup=application, boot=manual, ingress=true (port 4000), ports=4000/tcp:4000, health_check=/health/liveliness, image=ghcr.io/akentner/homeassistant-addons/{arch}-litellm, map=[addon_config, backup:rw]. Options block: log_level, master_key/salt_key !secret defaults, four provider keys (openai/anthropic/google/azure), empty models: [], postgres tuning block (shared_buffers=64MB, max_connections=20, log_min_duration_statement=1000). Schema mirrors options with `password?` for secrets, regex match for model names.
- `litellm/build.yaml` — build_from=ghcr.io/home-assistant/amd64-base-debian:trixie, args.VERSION=0.1.0, args.LITELLM_VERSION=1.40.0 (synced at scaffold time; Plan 03 wires LITELLM_VERSION post-processing into auto-update.yml).
- `litellm/Dockerfile` — Multi-stage: builder (python:3.13-slim-bookworm, pip wheel litellm + psycopg + prisma) → runtime (${BUILD_FROM} ha-debian-trixie, PGDG postgresql-16 install, LiteLLM wheelhouse install from /wheels, generate_config.py + run.sh COPY). Full OCI label block (io.hass.* + org.opencontainers.image.*).
- `litellm/run.sh` — bashio with-contenv bashio + set -e; signal traps (TERM/HUP) with placeholder bodies Plan 02 expands; bashio::config log_level + LITELLM_LOG export; /data/.pg_password (chmod 600) persistent; PG version detection → initdb-if-missing (PG_VERSION file) → pg_hba.conf md5 entry → pg_ctl start → pg_isready loop → idempotent role/db create; DATABASE_URL export; python3 /app/generate_config.py; exec litellm --config /data/litellm_config.yaml.
- `litellm/.upstream.yaml` — upstream.repository=BerriAI/litellm, version_pattern=v*, version_strip=^v, addon.version_pattern=sync.
- `litellm/README.md` — heading + v0.1.0 release badge + amd64 shield; references DOCS.md (written in Plan 04).
- `litellm/.gitignore` — /data exclusion (HA Supervisor bind-mount; prevents accidental commits of runtime state).
- `litellm/generate_config.py` — Python 3 helper. Reads /data/options.json, writes /data/litellm_config.yaml. transform(options) returns {model_list, general_settings} envelope. Plan 01 ships minimal pass-through; Plan 02 expands to env-var references for master_key (LITELLM_MASTER_KEY) and salt_key (LITELLM_SALT_KEY) so secrets stay in /data as plain files (chmod 600) and never land in the YAML.
- `README.md` — Root repo entry: heading `### [LiteLLM]`, amd64 shield, OpenAI-compatible-API-gateway description, 5-bullet feature list (port 4000 LAN/Tailscale, master/salt-key auto-gen, !secret provider keys, bundled postgres, backup:rw, .upstream.yaml sync tracking).

## Decisions Made

- **PGDG + postgresql-16 (not Debian default 15.x)** — PLAN.md Q7 resolution: LiteLLM upstream expects PG 16+ for current Prisma schema. Stage 2 apt-get now installs PGDG-signed repo + postgresql-16 instead of generic postgresql. ~50KB image growth, defensible against upstream drift.
- **Python over bash+jq for generate_config.py (D-17)** — phone-logger precedent; Python is already in the LiteLLM wheelhouse (no extra apt dep); jq transformation of nested-dict → model_list would be fragile.
- **Plan 01 ships minimal envelope (model_list + empty general_settings)** — Plan 02 expands transform() to handle master_key/salt_key env-var references and per-model litellm_params routing. Keeping the scope tight means Plan 01's smoke test is trivially assertable (transform({'models': []}) returns empty envelopes).
- **run.sh signal-trap bodies are placeholders** — TERM handler logs + sleep 1 (Plan 02 wires litellm PID forwarding + drain); HUP handler logs (Plan 02 wires log-reopen). Plan 02 owns the production semantics; Plan 01 establishes the trap wiring shape so the second-task work doesn't touch signal-handling scaffolding.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Implementation drift] Dockerfile Stage 2 apt-get install used Debian default postgresql instead of PGDG postgresql-16**
- **Found during:** Task 1 verification (acceptance_criteria + PLAN.md Q7 cross-check)
- **Issue:** Initial scaffold commit `493eb71` installed `postgresql` + `postgresql-client` (Debian Trixie default = 15.x), but PLAN.md Q7 was resolved on 2026-09-19 to use PGDG repo + postgresql-16 (LiteLLM upstream expects PG 16+ for current Prisma schema).
- **Fix:** Replaced Stage 2 apt-get install with PGDG pattern: install curl + ca-certificates + gnupg, add apt.postgresql.org signed repo to sources.list.d, then apt-get install postgresql-16 + postgresql-client-16.
- **Files modified:** litellm/Dockerfile
- **Verification:** bash internal/validate-dockerfile-args.sh exits 0; hadolint (with DL3008/4006 ignored per repo convention) exits 0; design-decision audit trail preserved via comment "see PLAN.md Q7" so a future maintainer cannot silently revert.
- **Committed in:** f490894 (fix)

---

**Total deviations:** 1 auto-fixed (implementation drift caught by PLAN.md cross-check)
**Impact on plan:** All auto-fixes essential for correctness (avoids silent future Prisma-schema drift). No scope creep.

## Issues Encountered

- **Pre-commit `end-of-file-fixer` hook needed trailing newlines on staged litellm/ files** — the initial commit attempt had `litellm/.upstream.yaml` and `litellm/build.yaml` without final newlines, which `yamllint` flagged. Resolved by re-staging after the hook auto-applied the fix. Single-pass retry; no operator impact.

## User Setup Required

None - no external service configuration required for this plan. The user-facing configuration happens in Plan 02 (master/salt-key lifecycle) and Plan 04 (DOCS.md + verifier scripts). The litellm/ scaffold installs via the standard HA add-on store workflow once the image is published to ghcr.io.

## Next Phase Readiness

- Plan 02 (Master/Salt-Key lifecycle + generate_config.py expansion) can build on:
  - The scaffolded run.sh signal-trap placeholders (TERM/HUP handler bodies will be wired here)
  - The `python3 /app/generate_config.py` invocation already in run.sh (transform() will be expanded for master/salt env-var references)
  - The PostgreSQL ready state (Plan 02 will surface master_key/salt_key rotation via env vars consumed by LiteLLM)
- Plan 03 (postgres tuning reload + LITELLM_VERSION post-processing) can build on:
  - The build.yaml `args.LITELLM_VERSION` field (Plan 03 wires auto-update.yml to post-process)
  - The PGDG-installed postgresql-16 (Plan 03 will wire `pg_reload_conf` for SIGHUP-reloadable settings from options)
- Plan 04 (DOCS.md + verifier scripts + README polish) can build on the entire scaffold

No blockers. All success_criteria pass:

- 8 litellm/ files present (config.yaml, build.yaml, Dockerfile, run.sh, .upstream.yaml, .gitignore, README.md, generate_config.py)
- All four validators exit 0 (validate-addon-config.py, yamllint, validate-dockerfile-args.sh, hadolint with ignored rules)
- generate_config.py smoke test passes (transform({'models': []}) returns empty envelopes)
- Root README.md has the LiteLLM entry
- Dockerfile uses ARG BUILD_FROM with matching default to build.yaml
- Dockerfile has the full OCI label block (16 labels)
- run.sh uses bash-sequential + signal-trap placeholders
- .upstream.yaml mirrors gatus shape with BerriAI/litellm + sync pattern
- No code implements deferred ideas (master-key rotation, Cloudflare surface, multi-arch, OAuth/PKCE, web admin UI)
- pre-commit run on litellm/ files exits 0

---
*Phase: 20-litellm-addon*
*Completed: 2026-09-19*
