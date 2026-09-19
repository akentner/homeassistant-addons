---
phase: 20-litellm-addon
plan: 03
subsystem: infra
tags: [home-assistant, addon, litellm, postgres-tuning, auto-update, sighup-reload]

# Dependency graph
requires:
  - phase: 20-plan-01
    provides: litellm/ scaffold + Postgres init lifecycle in run.sh
  - phase: 20-plan-02
    provides: Master/Salt-Key lifecycle + signal-trap in run.sh
provides:
  - Postgres tuning reload (SIGHUP-reloadable settings + restart-required warning)
  - Auto-update workflow LITELLM_VERSION post-processing (Audit B2 fix)
affects: [20-04]

# Actuals (#2632)
actuals:
  tokens: 2100
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: [include_if_exists (PostgreSQL 14+), pg_ctl reload (SIGHUP)]
  patterns: [idempotent include_if_exists directive via grep -q guard, SIGHUP-reload vs restart-required separation, sed-based post-processing guarded by grep]

key-files:
  modified:
    - litellm/run.sh
    - .github/workflows/auto-update.yml

key-decisions:
  - "effective_cache_size=256MB and work_mem=4MB are hardcoded (per D-15 small-home defaults) — not operator-tunable"
  - "max_connections is in tuning.conf for documentation but emits a `requires restart` warning when the operator changes it (D-16 contract)"
  - "Auto-update sed uses explicit string-replacement (not yq) to keep the change small + match existing sed patterns in the workflow"
  - "Sed step is guarded by `if grep -q '^  LITELLM_VERSION:'` for backward compatibility with add-ons that don't declare LITELLM_VERSION"

patterns-established:
  - "Pattern: tuning reload via pg_ctl reload — SIGHUP-reloadable settings apply immediately; restart-required settings get a warning, not a silent failure"
  - "Pattern: idempotent include_if_exists guard — `if ! grep -q` prevents duplicate appends on upgrade-path restores"
  - "Pattern: post-processing sed guarded by grep — adds new auto-update behavior without touching update-version.py (single-purpose Python)"

requirements-completed:
  - LITELLM-06
  - LITELLM-07

coverage:
  - id: D1
    description: "run.sh writes /data/postgresql/litellm-tuning.conf with operator-tunable shared_buffers + log_min_duration_statement + hardcoded effective_cache_size=256MB + work_mem=4MB + max_connections"
    requirement: "LITELLM-06"
    verification:
      - kind: automated
        ref: "grep -cE 'PG_TUNING_CONF=/data/postgresql/litellm-tuning\\.conf|shared_buffers = \\$\\{SHARED_BUFFERS\\}|effective_cache_size = 256MB|work_mem = 4MB' litellm/run.sh"
        status: pass
      - kind: automated
        ref: "shellcheck litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D2
    description: "run.sh appends `include_if_exists = 'litellm-tuning.conf'` to postgresql.conf idempotently (grep -q guard)"
    requirement: "LITELLM-06"
    verification:
      - kind: automated
        ref: "grep -cE \"include_if_exists = 'litellm-tuning\\.conf'\" litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D3
    description: "run.sh triggers pg_ctl reload after writing tuning.conf (D-15: SIGHUP-reloadable settings apply immediately; max_connections requires restart per D-16)"
    requirement: "LITELLM-06"
    verification:
      - kind: automated
        ref: "grep -cE 'pg_ctl -D \\$\\{PG_DATA\\} reload|postgres\\.tuning\\.applied' litellm/run.sh"
        status: pass
    human_judgment: false
  - id: D4
    description: "auto-update.yml has guarded sed post-processing that syncs args.LITELLM_VERSION to new VERSION (D-30 fix)"
    requirement: "LITELLM-07"
    verification:
      - kind: automated
        ref: "yamllint .github/workflows/auto-update.yml"
        status: pass
      - kind: automated
        ref: "pre-commit run 'Lint GitHub Actions workflow files'"
        status: pass
      - kind: automated
        ref: "python3 ordering check: update@122 < sed@134 < commit@164"
        status: pass
    human_judgment: false

# Metrics
duration: 18min
completed: 2026-09-19
status: complete
---

# Phase 20 Plan 03: Postgres Tuning Reload + Auto-Update LITELLM_VERSION Sync

**Wired Postgres tuning reload via SIGHUP into run.sh (D-15, D-16) and added the guarded sed step to auto-update.yml that keeps args.LITELLM_VERSION in lockstep with VERSION on every upstream bump (D-30, Audit B2 fix)**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2 of 2 complete
- **Files modified:** 2 (litellm/run.sh, .github/workflows/auto-update.yml)

## Accomplishments

- Postgres tuning reload: `run.sh` reads operator-supplied `postgres.shared_buffers` + `postgres.log_min_duration_statement` + `postgres.max_connections` from HA Options (with defaults 64MB / 1000 / 20) and writes `/data/postgresql/litellm-tuning.conf` with the operator values + hardcoded `effective_cache_size=256MB` + `work_mem=4MB` (per D-15 small-home defaults).
- `include_if_exists = 'litellm-tuning.conf'` directive appended to postgresql.conf idempotently (`grep -q` guard prevents duplicate appends on upgrade-path restores).
- `pg_ctl reload` after writing — SIGHUP-reloadable settings (`shared_buffers`, `log_min_duration_statement`) apply immediately.
- `bashio::log.info "postgres.tuning.applied shared_buffers=... log_min_duration_statement=..."` audit-friendly log line per D-15.
- `bashio::log.warning "postgres.tuning.max_connections=... requires restart"` emitted only when the operator changed `max_connections` (D-16 restart-required caveat; DOCS.md will document this in Plan 04).
- Auto-update workflow (D-30 / Audit B2 fix): after `update-version.py` runs, a guarded sed step (`if grep -q '^  LITELLM_VERSION:'`) syncs `args.LITELLM_VERSION` to the new `VERSION` for add-ons that declare it (currently only `litellm`). Backward-compatible: add-ons without LITELLM_VERSION (gatus, meridian, iac-runner, network-tools, phone-logger, coding-assistants, authentik) skip the step entirely.
- Sed runs BEFORE `git commit` (line 134) so the commit includes the updated LITELLM_VERSION (line 164).

## Task Commits

1. **Task 1: run.sh Postgres tuning reload** — `9be3e11` (feat)
2. **Task 2: auto-update.yml LITELLM_VERSION sync** — `bb8178f` (feat)

**Plan metadata:**
- `9f3efbc` (docs: 20-02-SUMMARY.md)
- `2eadbdb`, `465838b`, `b6e6534` (Plan 02 chain)

## Files Created/Modified

- `litellm/run.sh` — Inserted Postgres tuning block between `bashio::log.info "PostgreSQL ready."` (line 101) and `python3 /app/generate_config.py` (line 159). The block reads three bashio::config values (shared_buffers, log_min_duration_statement, max_connections), writes `/data/postgresql/litellm-tuning.conf` via heredoc, sets `chown postgres:postgres`, ensures the `include_if_exists` directive is present in postgresql.conf (idempotent `grep -q` guard), triggers `pg_ctl reload`, emits the tuning-applied log line, then queries the running max_connections value and emits the restart-required warning only if it differs from the new value. Plan 02 Master/Salt-Key lifecycle + signal-trap (12 grep matches) fully preserved.
- `.github/workflows/auto-update.yml` — Inserted LITELLM_VERSION sync step between `python3 internal/update-version.py ... --no-tag || { ... continue }` (line 122-127) and `if git diff --quiet; then` (line 141). The sed expression uses explicit string-replacement with `|` delimiter to avoid sed-regex conflicts with the `"` characters in the YAML value.

## Decisions Made

- **Hardcoded effective_cache_size + work_mem** — per D-15 small-home defaults; not operator-tunable. Operator control is limited to the three SIGHUP-reloadable settings (shared_buffers, log_min_duration_statement) + max_connections (with restart-required caveat).
- **Explicit sed string-replacement (not yq)** — keeps the workflow change small (one line) and matches the existing sed pattern in the workflow. yq would add a round-trip dependency; sed is sufficient for the explicit string-replace case.
- **Backwards-compatible grep guard** — `if grep -q '^  LITELLM_VERSION:'` makes the sed step a no-op for add-ons that don't declare LITELLM_VERSION. Verified by inspection: only `litellm/build.yaml` matches the guard.
- **Restart-required warning (not silent failure)** — when max_connections differs from the running value, run.sh emits `bashio::log.warning "requires restart — current value remains ..."`. The warning makes the operator aware of the post-restart requirement without aborting startup; the new value is written to tuning.conf for the next restart.

## Deviations from Plan

None - plan executed as written. The plan's action block had 4-space indentation in the markdown that I removed during paste (shellcheck and bash don't care about indentation, but the file style is column-0 for shell commands).

## Issues Encountered

- **actionlint not on PATH** — pre-commit's "Lint GitHub Actions workflow files" hook covers the same lint surface (it's the actionlint GitHub Action wrapper), so the verification still ran via `pre-commit run --files .github/workflows/auto-update.yml` and passed. Direct `actionlint` binary is not in this dev host's PATH.

## User Setup Required

None for Plan 03 itself. Plan 04 ships DOCS.md which will document:
- Operator-facing tuning knobs (postgres.shared_buffers, postgres.log_min_duration_statement, postgres.max_connections)
- max_connections restart-required caveat
- Auto-update behavior for litellm (LITELLM_VERSION stays in lockstep with VERSION on every daily bump)

## Next Phase Readiness

- Plan 04 (DOCS.md + verifier scripts + README polish) can build on:
  - The tuning.conf reload runtime behavior (DOCS.md documents the operator knobs + restart caveat)
  - The auto-update LITELLM_VERSION sync (DOCS.md documents that the auto-update bumps both versions in lockstep)
  - The Plan 02 Master/Salt-Key log-once behavior (DOCS.md documents operator retrieval of auto-generated keys)

No blockers. All success_criteria pass:

- run.sh has the postgres tuning reload block between `PostgreSQL ready.` (line 101) and `python3 /app/generate_config.py` (line 159) in file order
- The tuning block writes /data/postgresql/litellm-tuning.conf with operator-supplied shared_buffers + log_min_duration_statement + hardcoded effective_cache_size=256MB + work_mem=4MB (5 grep matches)
- The tuning block appends `include_if_exists = 'litellm-tuning.conf'` to postgresql.conf idempotently (2 grep matches)
- The tuning block triggers `pg_ctl reload` to apply SIGHUP-reloadable settings (3 grep matches for reload)
- The tuning block emits `postgres.tuning.applied` log line (1 match)
- The tuning block emits a warning when max_connections differs from current value (restart-required caveat)
- shellcheck + bash -n both pass on run.sh
- auto-update.yml has the guarded sed step that syncs args.LITELLM_VERSION to the new VERSION (1 match for the sed line)
- The sed step runs AFTER update-version.py (line 122) and BEFORE git commit (line 164)
- The sed step is guarded by `if grep -q '^  LITELLM_VERSION:'` (backward-compatible with other add-ons)
- yamllint + pre-commit actionlint both pass on auto-update.yml
- The Plan 01 + Plan 02 changes are preserved (no regression)
- No code implements deferred ideas (pg_dump integration, custom secrets: mount, OAuth/PKCE)

---
*Phase: 20-litellm-addon*
*Completed: 2026-09-19*
