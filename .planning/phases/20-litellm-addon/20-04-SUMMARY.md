---
phase: 20-litellm-addon
plan: 04
subsystem: docs
tags: [home-assistant, addon, litellm, docs, verifier, spike]

# Dependency graph
requires:
  - phase: 20-plan-01
    provides: litellm/ scaffold + minimal generate_config.py envelope
  - phase: 20-plan-02
    provides: Master/Salt-Key lifecycle + signal-trap + full generate_config.py transformation
  - phase: 20-plan-03
    provides: Postgres tuning reload + auto-update LITELLM_VERSION sync
provides:
  - litellm/DOCS.md operator reference (11 sections, 120-char line discipline)
  - litellm/README.md polished (About/Features/Install/First Start/Configuration)
  - Root README.md LiteLLM entry polished (iac-runner-style)
  - internal/verify-litellm-scaffold.sh (D-32 — image build + size ≤ 500 MiB + OCI labels)
  - internal/verify-litellm-no-secret-leak.sh (D-33 — master-key plaintext count = 1)
  - internal/verify-litellm-postgres-reset.sh (D-34 — reset procedure end-to-end)
  - internal/spike-litellm-secret-schema.sh (D-35 — password? + !secret empirical validation)
affects: []

# Actuals (#2632)
actuals:
  tokens: 5200
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns: [shell-verifier pattern (bash + set -euo pipefail + clear exit codes), empirical-spike pattern (sandbox add-on in /tmp + validate-addon-config.py + write result to .out)]

key-files:
  created:
    - litellm/DOCS.md
    - internal/verify-litellm-scaffold.sh
    - internal/verify-litellm-no-secret-leak.sh
    - internal/verify-litellm-postgres-reset.sh
    - internal/spike-litellm-secret-schema.sh
  modified:
    - litellm/README.md
    - README.md

key-decisions:
  - "Verifier scripts run as `set -euo pipefail` + clear `✓` / `✗` output — matches the existing repo verifier pattern (verify-bridge-scaffold.sh)"
  - "Spike script creates sandbox in /tmp and runs validate-addon-config.py — Plan 04 ships the script, the operator runs it on their HA-OS instance and updates DOCS.md §Spike Result with the empirical result"
  - "DOCS.md uses `text` fenced code blocks for URL examples (markdownlint MD040 compliance)"

requirements-completed:
  - LITELLM-09
  - LITELLM-10

coverage:
  - id: D1
    description: "litellm/DOCS.md exists with all 11 operator-reference sections (About, Install, First Start, HA Conversation Integration, Direct Port Access, Options, Postgres Tuning, Backup & Restore, Auto-Update, Troubleshooting, Spike Result)"
    requirement: "LITELLM-09"
    verification:
      - kind: automated
        ref: "grep -cE '^## (About|Install|First Start|HA Conversation Integration|Direct Port Access|Options|Postgres Tuning|Backup & Restore|Auto-Update|Troubleshooting|Spike Result)$' litellm/DOCS.md"
        status: pass
      - kind: automated
        ref: "pre-commit run markdownlint-cli2 --files litellm/DOCS.md"
        status: pass
      - kind: automated
        ref: "awk 'length > 120' litellm/DOCS.md"
        status: pass
    human_judgment: false
  - id: D2
    description: "litellm/README.md polished with About/Features/Install/First Start/Configuration sections + v0.1.0 badge + DOCS.md link"
    requirement: "LITELLM-10"
    verification:
      - kind: automated
        ref: "grep -cE '^# LiteLLM|v0\\.1\\.0|^## (About|Features|Install)' litellm/README.md"
        status: pass
      - kind: automated
        ref: "pre-commit run markdownlint-cli2 --files litellm/README.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "internal/verify-litellm-scaffold.sh asserts image builds + size ≤ 500 MiB + OCI labels (D-32)"
    requirement: "LITELLM-09"
    verification:
      - kind: automated
        ref: "shellcheck internal/verify-litellm-scaffold.sh"
        status: pass
      - kind: automated
        ref: "grep -cE 'docker build|500 MiB|io\\.hass\\.name|org\\.opencontainers\\.image\\.version|maintainer' internal/verify-litellm-scaffold.sh"
        status: pass
    human_judgment: false
  - id: D4
    description: "internal/verify-litellm-no-secret-leak.sh asserts master-key plaintext count = 1 + no password=<hex> in logs (D-33)"
    requirement: "LITELLM-09"
    verification:
      - kind: automated
        ref: "shellcheck internal/verify-litellm-no-secret-leak.sh"
        status: pass
    human_judgment: false
  - id: D5
    description: "internal/verify-litellm-postgres-reset.sh validates rm -rf + restart + initdb + PostgreSQL ready cycle (D-34)"
    requirement: "LITELLM-09"
    verification:
      - kind: automated
        ref: "shellcheck internal/verify-litellm-postgres-reset.sh"
        status: pass
    human_judgment: false
  - id: D6
    description: "internal/spike-litellm-secret-schema.sh creates sandbox add-on + runs validate-addon-config.py for password? + !secret (D-35)"
    requirement: "LITELLM-09"
    verification:
      - kind: automated
        ref: "shellcheck internal/spike-litellm-secret-schema.sh"
        status: pass
    human_judgment: false

# Metrics
duration: 22min
completed: 2026-09-19
status: complete
---

# Phase 20 Plan 04: Operator Documentation + Verifier Scripts

**Shipped the operator reference (DOCS.md, 11 sections), polished both add-on and root README, and added four verifier/spike scripts (scaffold / no-secret-leak / postgres-reset / secret-schema) — closes the documentation gap from Plans 01-03 and codifies D-32..D-35 contracts into runnable bash**

## Performance

- **Duration:** ~22 min
- **Tasks:** 2 of 2 complete
- **Files created:** 5 (DOCS.md + 4 verifier scripts)
- **Files modified:** 2 (litellm/README.md, root README.md)

## Accomplishments

- DOCS.md (181 lines, 11 sections) covers About / Install / First Start (master-key retrieval) / HA Conversation Integration (openai_conversation snippet with `!secret litellm_api_base` + `!secret litellm_master_key`) / Direct Port Access / Options (every key with type + default + schema validation note) / Postgres Tuning (SIGHUP-reload vs `max_connections` restart caveat) / Backup & Restore (`map: backup: rw` + Postgres reset procedure) / Auto-Update (daily 06:00 UTC + `make release` manual override) / Troubleshooting / Spike Result.
- litellm/README.md polished with About / Features / Install / First Start / Configuration sections; v0.1.0 badge; DOCS.md link.
- Root README.md LiteLLM entry polished to match the iac-runner style: 1-paragraph intro with `[litellm-upstream]` link syntax + 6-bullet feature list.
- 4 verifier/spike scripts under `internal/`:
  - `verify-litellm-scaffold.sh` (D-32): docker build + image size ≤ 500 MiB + OCI labels (io.hass.*, org.opencontainers.image.*, maintainer).
  - `verify-litellm-no-secret-leak.sh` (D-33): master-key plaintext count = exactly 1 + no `password=<hex>` substring in logs. SYNTHETIC_OPTIONS materialized to /tmp before docker run so the `-v` mount resolves to a real file (closes a Plan-script gap).
  - `verify-litellm-postgres-reset.sh` (D-34): initial start → `rm -rf /data/postgresql` → restart → assert `Initializing PostgreSQL` + `PostgreSQL ready.` cycle (DOCS.md §Backup & Restore procedure end-to-end).
  - `spike-litellm-secret-schema.sh` (D-35): empirical spike for `password?` + `!secret` combination. Builds a sandbox add-on in `/tmp/spike-litellm-secret-schema/` and runs `validate-addon-config.py`; writes the result to `/tmp/spike-litellm-secret-schema.out` for operator review.

## Task Commits

1. **Task 1: DOCS.md** — `af74157` (docs)
2. **Task 2: README polish + 4 verifier scripts + root README entry** — `d8f8be1` (feat)

**Plan metadata:**
- `8adf831` (docs: 20-03-SUMMARY.md)
- `bb8178f`, `9be3e11`, plus earlier 20-03/02/01 chain

## Files Created/Modified

- `litellm/DOCS.md` — 181 lines, 11 sections. Plan-deviation fixups: markdown table column padding removed (column alignment put 7 lines over 120 chars); fenced code blocks at lines 63/69 tagged `text` for MD040 compliance.
- `litellm/README.md` — Replaced Plan 01 placeholder with full About/Features/Install/First Start/Configuration structure + v0.1.0 badge + DOCS.md link.
- `README.md` — LiteLLM entry polished to match iac-runner style. Plan-deviation fixup: re-added `[litellm-upstream]` link syntax (the polished entry uses the existing `litellm-upstream` reference at line 253 — without the link syntax, markdownlint MD053 would fail).
- `internal/verify-litellm-scaffold.sh` — Bash + set -euo pipefail + yq-free build.yaml parsing. Builds `litellm-verify:local` and asserts size + OCI labels.
- `internal/verify-litellm-no-secret-leak.sh` — Bash + set -euo pipefail. Runs container with synthetic options.json (no real secrets), captures logs, asserts master-key plaintext count = 1.
- `internal/verify-litellm-postgres-reset.sh` — Bash + set -euo pipefail. Walks the DOCS.md reset procedure end-to-end. Plan-deviation fixup: writes SYNTHETIC_OPTIONS to /tmp/litellm-verify-options.json before docker run (closes a Plan-script gap where the mount would dangle).
- `internal/spike-litellm-secret-schema.sh` — Bash + set -euo pipefail. Creates sandbox add-on in /tmp/spike-litellm-secret-schema/ with config.yaml using `password?` schema + `!secret` default, runs validate-addon-config.py, writes result to .out file. Plan-deviation fixup: added `# shellcheck disable=SC2012` for the deliberate `ls -la` use (pre-commit shellcheck hook treats info-level as error; the directive is the cleaner fix than replacing with `find` which would lose human-readable output).

## Decisions Made

- **Verifier scripts are manual-invocation only** — Plan 04 explicitly defers CI integration. The scripts are callable now but not wired into GitHub Actions. An operator runs `bash internal/verify-litellm-{scaffold,no-secret-leak,postgres-reset}.sh` during development; CI integration is a follow-up phase.
- **Spike script doesn't auto-clean the sandbox** — Plan 04 explicitly defers auto-cleanup. The spike creates `/tmp/spike-litellm-secret-schema/` with the sandbox add-on; the operator reviews the result in `/tmp/spike-litellm-secret-schema.out` and removes the sandbox manually. This is intentional: the spike output is the artifact the operator wants to read.
- **DOCS.md §Spike Result is a placeholder** — The spike has been written but not yet run on a live HA-OS instance. The DOCS.md section reads "Pending — see `internal/spike-litellm-secret-schema.sh`. Run the spike once on the operator's HA-OS instance and document the result here." This matches Plan 04's explicit out-of-scope confirmation: the spike is shipped as code; the result-documenting is operator work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 - Correctness] verify-litellm-no-secret-leak.sh had a dangling /tmp mount reference**
- **Found during:** shellcheck run (SC2034 unused variable warning)
- **Issue:** Plan's script declared SYNTHETIC_OPTIONS but never wrote it to /tmp/litellm-verify-options.json, while the docker run line referenced `-v /tmp/litellm-verify-options.json:/data/options.json:ro`. Without the write, the mount would dangle on first invocation and the container would see an empty options.json (which would still work, but the verifier wouldn't be testing the intended SYNTHETIC_OPTIONS contract).
- **Fix:** Added `echo "${SYNTHETIC_OPTIONS}" > /tmp/litellm-verify-options.json` before the docker run.
- **Files modified:** internal/verify-litellm-no-secret-leak.sh
- **Verification:** shellcheck exits 0 (no SC2034); the SYNTHETIC_OPTIONS variable is now used.
- **Committed in:** d8f8be1 (Task 2 commit)

**2. [Rule 4 - Correctness] verify-litellm-postgres-reset.sh had the same dangling mount**
- **Found during:** shellcheck run (SC2034 unused variable warning)
- **Issue:** Same pattern as verifier 1.
- **Fix:** Same fix — added `echo "${SYNTHETIC_OPTIONS}" > /tmp/litellm-verify-options.json` before the docker run.
- **Files modified:** internal/verify-litellm-postgres-reset.sh
- **Verification:** shellcheck exits 0.
- **Committed in:** d8f8be1 (Task 2 commit)

**3. [Rule 1 - Style/Format] README.md polished entry would have triggered MD053 (unused link reference)**
- **Found during:** markdownlint-cli2 pre-commit run
- **Issue:** Polished entry didn't use the `[litellm-upstream]` link syntax that exists in the README's reference definitions at line 253.
- **Fix:** Added `[LiteLLM][litellm-upstream]` syntax in the entry's first paragraph.
- **Files modified:** README.md
- **Verification:** pre-commit markdownlint-cli2 passes.
- **Committed in:** d8f8be1 (Task 2 commit)

**4. [Rule 1 - Style/Format] spike script's `ls -la` triggered SC2012 (info-level)**
- **Found during:** pre-commit shellcheck run
- **Issue:** pre-commit shellcheck treats info-level SC2012 as a failure (repo policy). Replacing with `find ... -ls` would lose human-readable output.
- **Fix:** Added `# shellcheck disable=SC2012` directive on the line above the `ls -la` invocation.
- **Files modified:** internal/spike-litellm-secret-schema.sh
- **Verification:** shellcheck exits 0.
- **Committed in:** d8f8be1 (Task 2 commit)

**5. [Rule 1 - Style/Format] DOCS.md markdown table column padding put 7 lines over 120 chars**
- **Found during:** markdownlint-cli2 / awk line-length check
- **Issue:** Plan-preserved table had alignment whitespace that pushed 7 rows past the 120-char markdownlint limit.
- **Fix:** Removed column-alignment whitespace; tables render identically without it.
- **Files modified:** litellm/DOCS.md
- **Verification:** awk 'length > 120' returns no output; markdownlint-cli2 passes.
- **Committed in:** af74157 (Task 1 commit)

---

**Total deviations:** 5 auto-fixed (2 correctness, 3 style/format)
**Impact on plan:** All auto-fixes essential for shellcheck + markdownlint compliance + script correctness (no dangling mounts). No scope creep.

## Issues Encountered

None.

## User Setup Required

DOCS.md §Spike Result is a placeholder. Operator should:

1. Copy the spike sandbox (`/tmp/spike-litellm-secret-schema/` — created by `bash internal/spike-litellm-secret-schema.sh`) to a real HA-OS instance.
2. Add the local repo URL to HA Settings → Add-ons → Add-on Store.
3. Install the "Spike Add-on (litellm-secret-schema)" add-on.
4. Verify HA Supervisor accepts the options without rejecting the `!secret` default.
5. Update `litellm/DOCS.md` §Spike Result with the empirical install result.

Beyond the spike, the verifier scripts require a Docker host to invoke; the E2E flow on a real HA instance is deferred to operator-runtime testing (not in scope for Plan 04).

## Next Phase Readiness

- Phase 20 complete. All 4 plans landed. The litellm/ add-on is ready for first install on a live HA instance.
- Verifier scripts are callable from any Docker host for pre-deploy validation.
- Auto-update workflow keeps VERSION + LITELLM_VERSION in lockstep on every upstream release.
- HA-Backup integration (`map: backup: rw`) is in place from Plan 01's config.yaml; backup/restore works without further configuration.

No blockers. All success_criteria pass:

- litellm/DOCS.md exists with all 11 sections + `!secret` integration snippet + reset procedure + `max_connections` caveat + `make release` reference + auto-update mention
- litellm/README.md is polished with About + Features + Install + First Start + Configuration sections
- Root README.md has a polished LiteLLM entry between iac-runner and gatus
- internal/verify-litellm-scaffold.sh exists + executable + passes shellcheck + asserts build/size/labels
- internal/verify-litellm-no-secret-leak.sh exists + executable + passes shellcheck + asserts no-secret-leak
- internal/verify-litellm-postgres-reset.sh exists + executable + passes shellcheck + asserts reset
- internal/spike-litellm-secret-schema.sh exists + executable + passes shellcheck + tests password?+!secret
- DOCS.md §Spike Result is documented (placeholder, operator fills in)
- All Markdown files respect the 120-char line limit per .markdownlint.json
- No code implements deferred ideas (CI integration of verifiers, architecture deep-dive in DOCS.md)

---
*Phase: 20-litellm-addon*
*Completed: 2026-09-19*
