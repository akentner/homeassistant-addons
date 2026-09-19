---
phase: 20-litellm-addon
plan: 02
subsystem: auth
tags: [home-assistant, addon, litellm, master-key, salt-key, signal-trap, secrets]

# Dependency graph
requires:
  - phase: 20-plan-01
    provides: litellm/ scaffold + minimal generate_config.py envelope
provides:
  - Master/Salt-Key lifecycle in run.sh (bashio::config → file fallback → auto-gen with log-once)
  - Signal-trap (_on_term 30s drain + _on_hup log-reopen forward)
  - LITELLM_LOG mapping via ${LOG_LEVEL^^} (D-19)
  - Full generate_config.py transformation with env-var secret references (no plaintext)
  - Provider routing (openai/anthropic/google/azure/ollama/bedrock/custom)
affects: [20-03, 20-04]

# Actuals (#2632)
actuals:
  tokens: 4900
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: [openssl (already in alpine), bashio::log_level supersedes hand-rolled case mapping]
  patterns: [bashio::config → file fallback → auto-gen chain, signal-trap with PID forwarding via background+wait, env-var reference pattern for secrets]

key-files:
  modified:
    - litellm/run.sh
    - litellm/generate_config.py

key-decisions:
  - "Replaced Plan 01's `exec litellm` with `litellm & + LITELLM_PID=$! + wait` so the signal trap can forward SIGTERM/SIGHUP — exec would replace the shell and lose the trap"
  - "Master/Salt-Key auto-gen emits ONE bashio::log.notice line with the plaintext on first start (audit Q9 UX compromise); subsequent restarts reload silently from /data/.litellm_*_key"
  - "All secrets reference env-vars in the generated YAML (${LITELLM_MASTER_KEY}, ${LITELLM_SALT_KEY}, ${OPENAI_API_KEY}, etc.) — never plaintext (D-33 verifier contract)"
  - "Keyless providers (ollama) emit NO api_key field — Plan 02 fixes a Plan-defined sentinel-string defect that would have produced `api_key: os.environ/None` in YAML"

patterns-established:
  - "Pattern: signal-trap-before-init — install traps at the top of run.sh, BEFORE postgres init, so SIGTERM during init still drains cleanly"
  - "Pattern: background + wait daemon supervision — keeps the shell alive as PID1 so traps can forward to ${LITELLM_PID}, replacing s6-overlay"
  - "Pattern: env-var reference for secrets — generated YAML contains only ${VAR} placeholders; bashio + run.sh materialize env-vars from /data files (chmod 600) or !secret resolution"

requirements-completed:
  - LITELLM-04
  - LITELLM-05

coverage:
  - id: D1
    description: "run.sh Master-Key lifecycle: bashio::config 'master_key' → /data/.litellm_master_key → auto-gen with openssl rand -hex 32 + sk- prefix + chmod 600 + export LITELLM_MASTER_KEY"
    requirement: "LITELLM-05"
    verification:
      - kind: automated
        ref: "shellcheck litellm/run.sh"
        status: pass
      - kind: automated
        ref: "bash -n litellm/run.sh"
        status: pass
      - kind: automated
        ref: "grep -cE 'MASTER_KEY_FILE=/data/.litellm_master_key|openssl rand -hex 32|sk-|chmod 600.*MASTER_KEY_FILE|export LITELLM_MASTER_KEY' litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D2
    description: "run.sh Salt-Key lifecycle: identical pattern to master_key, no sk- prefix, /data/.litellm_salt_key + export LITELLM_SALT_KEY"
    requirement: "LITELLM-05"
    verification:
      - kind: automated
        ref: "grep -cE 'SALT_KEY_FILE=/data/.litellm_salt_key|export LITELLM_SALT_KEY' litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D3
    description: "run.sh signal-trap: _on_term forwards SIGTERM to litellm with 30s drain + force-kill fallback; _on_hup forwards SIGHUP for log-reopen; traps installed BEFORE postgres init"
    requirement: "LITELLM-03"
    verification:
      - kind: automated
        ref: "grep -cE 'trap _on_term TERM|trap _on_hup HUP|seq 1 30' litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D4
    description: "generate_config.py emits litellm_settings.master_key referencing ${LITELLM_MASTER_KEY} (env-var, no plaintext); salt_key referencing ${LITELLM_SALT_KEY}"
    requirement: "LITELLM-04"
    verification:
      - kind: automated
        ref: "python3 -c 'from generate_config import transform; ...' with LITELLM_MASTER_KEY env var; assert '${LITELLM_MASTER_KEY}' in output, 'sk-test-...' not in output"
        status: pass
      - kind: automated
        ref: "python3 -m py_compile litellm/generate_config.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "generate_config.py routes provider-specific api_key to env-vars: openai → ${OPENAI_API_KEY}, anthropic → ${ANTHROPIC_API_KEY}, google → ${GOOGLE_API_KEY}, azure → ${AZURE_API_KEY}; ollama (keyless) emits no api_key"
    requirement: "LITELLM-04"
    verification:
      - kind: automated
        ref: "transform() smoke test with full options (gpt-4o openai + claude anthropic + ollama-llama3) asserts each model emits correct env-var reference and ollama omits api_key"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-09-19
status: complete
---

# Phase 20 Plan 02: Master/Salt-Key Lifecycle + generate_config.py Expansion

**Wired Master/Salt-Key lifecycle into run.sh (D-11, D-12) and expanded generate_config.py to translate the full HA options.json schema into a LiteLLM-compatible YAML with env-var secret references (D-17, D-25, D-26)**

## Performance

- **Duration:** ~25 min (Plan 02 + Plan-deviation fixup)
- **Tasks:** 2 of 2 complete
- **Files modified:** 2 (litellm/run.sh, litellm/generate_config.py)

## Accomplishments

- Master-Key lifecycle: bashio::config 'master_key' → /data/.litellm_master_key file fallback → auto-gen branch with `bashio::log.notice` one-time plaintext emission + `openssl rand -hex 32` + `sk-` prefix + chmod 600 + `export LITELLM_MASTER_KEY`. Log-once UX: subsequent restarts reload silently from the persistent file.
- Salt-Key lifecycle: identical pattern, no `sk-` prefix (LiteLLM salt_key is raw 64-hex-char). `/data/.litellm_salt_key` + `export LITELLM_SALT_KEY`.
- Signal-trap (D-10): `_on_term` forwards SIGTERM to `${LITELLM_PID}` with 30s drain + force-kill fallback; `_on_hup` forwards SIGHUP for log-reopen (LiteLLM 1.39+ behavior). Traps installed BEFORE postgres init so SIGTERM during init still drains cleanly.
- LITELLM_LOG mapping via `${LOG_LEVEL^^}` (D-19): bash uppercase-conversion of bashio log_level; picks up future bashio log levels automatically.
- Background + wait daemon supervision: replaced `exec litellm` with `litellm & + LITELLM_PID=$! + wait` so the signal trap can forward SIGTERM/SIGHUP. Standard bash idiom for signal-trapped daemon supervision without s6-overlay.
- generate_config.py: full HA options.json → LiteLLM YAML transformation with `litellm_settings.master_key: ${LITELLM_MASTER_KEY}` + `salt_key: ${LITELLM_SALT_KEY}` (no plaintext), `model_list[].litellm_params.api_key` routed to provider env-vars (openai → ${OPENAI_API_KEY}, anthropic → ${ANTHROPIC_API_KEY}, etc.), `general_settings.telemetry: false`, and provider fallback for unknown providers (`CUSTOM_API_KEY` env-var placeholder).
- Provider routing: openai/anthropic/google/azure → respective env-vars; ollama → keyless (no api_key emitted); bedrock → AWS_ACCESS_KEY_ID chain; unknown → CUSTOM_API_KEY fallback (documented in DOCS.md Plan 04).

## Task Commits

1. **Task 1: run.sh Master/Salt-Key lifecycle + signal-trap** — `465838b` (feat)
2. **Task 2: generate_config.py expansion** — `2eadbdb` (feat)

**Plan metadata:**
- `b6e6534` (docs: 20-01-SUMMARY.md)
- `cebe063`, `f490894`, `493eb71`, `958ef21`, `fcb14cd`, `e0df1a1` (Plan 01 chain)

## Files Created/Modified

- `litellm/run.sh` — Replaced Plan 01 placeholder signal-trap with full `_on_term` (30s drain + force-kill) + `_on_hup` (SIGHUP forward) handlers; added Master/Salt-Key auto-gen branches (D-11, D-12) with bashio::config → file → log-once fallback chain; replaced `exec litellm` with background+wait pattern (lines 56, 70, 114, 115: env-var exports precede the `python3 /app/generate_config.py` invocation at line 118); preserved Postgres init lifecycle from Plan 01 (PG_VERSION detection, initdb-if-missing, pg_hba entry, pg_ctl start, pg_isready wait, idempotent user/db create, DATABASE_URL export).
- `litellm/generate_config.py` — Added `os` + yaml imports; defined `PROVIDER_ENV_VARS` map (openai/anthropic/google/azure/ollama/bedrock); added `_provider_env_var()` lookup helper; added `_build_model_entry()` for per-model translation (model + api_key + api_base + litellm_params passthrough); expanded `transform()` to emit `litellm_settings.master_key: ${LITELLM_MASTER_KEY}` + `salt_key: ${LITELLM_SALT_KEY}` (env-var references, never plaintext); expanded `main()` to always honor runtime env-vars over any inline plaintext (security invariant).

## Decisions Made

- **Background + wait instead of `exec litellm`** — `exec` replaces the shell, losing the signal trap. The standard bash idiom (background + wait + capture `$!` as `${LITELLM_PID}`) keeps the shell alive as PID1 so traps can deliver signals to the captured child PID. This is the bash-equivalent of s6-overlay's process supervision without adding a runtime dependency.
- **Master/Salt-Key auto-gen emits plaintext on first start** — Audit Q9 UX compromise: the operator needs to copy the auto-generated key into `secrets.yaml` for persistence across re-installs. The bashio::log.notice line is the only plaintext emission in the lifecycle; subsequent restarts reload silently from `/data/.litellm_*_key`.
- **Env-var references in YAML, never plaintext** — D-33 verifier contract. Generated YAML contains `${VAR}` placeholders for all secrets. Bashio + run.sh materialize the env-vars from `/data/.litellm_*_key` files (chmod 600) or `!secret` resolution. Plaintext never lands in `/data/litellm_config.yaml`.
- **Ollama provider emits no api_key field** — Plan 02 fixes a Plan-defined sentinel-string defect that would have produced `api_key: os.environ/None` (literal string) in YAML for keyless providers. Replaced with Python `None` so the `if api_key_ref:` check correctly omits the field; ollama's YAML entry has `model + api_base` only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 - Correctness] generate_config.py ollama provider would have emitted broken api_key field**
- **Found during:** Task 2 smoke test (output inspection)
- **Issue:** Plan 02 action block specified `api_key_ref = f"${{{env_var}}}" if env_var else "os.environ/None"`. For ollama (env_var is None), this emitted the literal string `"os.environ/None"` into the YAML's `api_key` field. LiteLLM would not understand `api_key: os.environ/None` and would reject the config.
- **Fix:** Replaced the sentinel string with Python `None`: `if env_var is None: api_key_ref = None else api_key_ref = f"${{{env_var}}}"`. The `if api_key_ref:` check on line 63 (next line) correctly omits the field for None.
- **Files modified:** litellm/generate_config.py
- **Verification:** Smoke test now asserts `'api_key' not in ollama_entry['litellm_params']` and passes. YAML output for ollama: `model + api_base` only, no api_key field.
- **Committed in:** 2eadbdb (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (correctness defect in plan-defined sentinel)
**Impact on plan:** Auto-fix essential for YAML correctness. No scope creep; net code is shorter (one less special-case branch).

## Issues Encountered

None.

## User Setup Required

None for Plan 02 itself. Plan 04 ships DOCS.md which will document the operator-facing parts:
- Master-key retrieval (read `/data/.litellm_master_key` or copy from first-start bashio::log.notice line)
- Provider-key routing (set `providers.*_api_key` in HA secrets.yaml — referenced via env-vars in the generated YAML)
- Unknown-provider fallback (`CUSTOM_API_KEY` env-var export for non-listed providers)

## Next Phase Readiness

- Plan 03 (postgres tuning reload + LITELLM_VERSION post-processing) can build on:
  - The Master/Salt-Key lifecycle already in run.sh (Plan 03 adds the postgres tuning reload on top of the existing PG init)
  - The `generate_config.py` reading `/data/options.json` (Plan 03 may add postgres tuning propagation to a `litellm-tuning.conf` that's pg_reload_conf'd)
  - The `build.yaml` `args.LITELLM_VERSION=1.40.0` (Plan 03 wires the auto-update.yml post-processing)
- Plan 04 (DOCS.md + verifier scripts + README polish) can build on the entire authentication + config-synthesis primitive — D-33 verifier (no plaintext secrets in `/data/litellm_config.yaml`) is now testable against the Plan 02 output

No blockers. All success_criteria pass:

- run.sh has the complete Master/Salt-Key lifecycle (D-11/D-12) with bashio::config → file → auto-gen chain
- run.sh has the signal-trap (D-10) with _on_term (30s drain) + _on_hup (log-reopen forward to litellm)
- run.sh has LITELLM_LOG mapping via `${LOG_LEVEL^^}` (D-19)
- All env-var exports (LITELLM_MASTER_KEY, LITELLM_SALT_KEY, DATABASE_URL) appear BEFORE the generate_config.py invocation in file order (verified by Python ordering check)
- shellcheck + bash -n both pass on run.sh
- generate_config.py emits litellm_settings.master_key + salt_key referencing env-vars (no plaintext)
- generate_config.py routes provider-specific api_key to the right env-var (openai → ${OPENAI_API_KEY}, etc.)
- generate_config.py emits general_settings.telemetry: false
- python3 -m py_compile + transform() smoke test both pass (including the ollama-keyless assertion)
- No code implements deferred ideas (master-key rotation endpoint, Cloudflare-fronted surface, multi-arch, OAuth/PKCE, web admin UI)
- The auto-gen log-once behavior is preserved: only fires when both bashio::config and /data/.litellm_*_key return empty

---
*Phase: 20-litellm-addon*
*Completed: 2026-09-19*
