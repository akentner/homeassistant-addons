---
phase: 03-meridian-add-on
plan: "02"
subsystem: infra
tags: [homeassistant, addon, bashio, meridian, claude-max, oauth]

# Dependency graph
requires:
  - phase: 03-01
    provides: meridian Dockerfile and build.yaml establishing the container image
provides:
  - meridian/config.yaml: HA add-on manifest with port 3456 declaration and options schema
  - meridian/run.sh: credential persistence symlink, startup guard, env export, proxy launch
affects:
  - 03-03-readme-docs
  - 03-04-upstream-yaml-and-hook-update

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "bashio config read + export: VAR=$(bashio::config 'key'); export VAR"
    - "Credential guard: check file existence, exit 1 with instructions when absent"
    - "Symlink for persistent OAuth token: ln -sf /data/.claude /root/.claude"
    - "exec handoff to S6: exec node WORKING_DIR/dist/cli.js"

key-files:
  created:
    - meridian/config.yaml
    - meridian/run.sh
  modified: []

key-decisions:
  - "Port 3456/tcp declared in ports section (not host_network) per D-13 / MER-04"
  - "Credential check on /data/.claude/.claude.json — exit 1 immediately, no polling per D-06/D-07"
  - "MERIDIAN_HOST=0.0.0.0 hardcoded (not configurable) — LAN/Tailscale reachability per D-08"
  - "exec node WORKING_DIR/dist/cli.js — S6 handles restart, no upstream supervisor script per D-10/D-11"

patterns-established:
  - "Meridian run.sh pattern: mkdir /data dir, symlink, credential check, bashio config read, export, exec"

requirements-completed:
  - MER-01
  - MER-04
  - MER-05
  - MER-06
  - MER-07

# Metrics
duration: 5min
completed: 2026-04-04
---

# Phase 03 Plan 02: Meridian config.yaml and run.sh Summary

**HA add-on manifest for Meridian with port 3456 and OAuth credential guard startup script using /data/.claude symlink**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-04T09:34:02Z
- **Completed:** 2026-04-04T09:39:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `meridian/config.yaml` with version 1.26.6-0, port 3456/tcp exposure, and two user options (log_level, port)
- Created `meridian/run.sh` with OAuth credential persistence via /data/.claude symlink and actionable error guidance
- run.sh passes shellcheck and is executable; config.yaml passes yamllint

## Task Commits

Each task was committed atomically:

1. **Task 1: Create meridian/config.yaml** - `61c0244` (feat)
2. **Task 2: Create meridian/run.sh** - `27f3aaa` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `meridian/config.yaml` - HA add-on manifest: name, version, slug, port 3456, options/schema, addon_config map
- `meridian/run.sh` - Startup script: symlink /root/.claude to /data/.claude, credential guard, config read, exec node

## Decisions Made

- Followed plan specifications (D-05 through D-14, D-18) exactly
- Used `path: /opt/meridian/data` in map section, matching fritz-callmonitor2mqtt pattern
- MERIDIAN_HOST hardcoded to 0.0.0.0 (not read from config) — consistent with D-08 intent

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- config.yaml and run.sh complete — next plans can create README.md, DOCS.md, .upstream.yaml, and update pre-commit hook
- No blockers

---

_Phase: 03-meridian-add-on_ _Completed: 2026-04-04_
