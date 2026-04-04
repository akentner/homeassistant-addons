---
id: 260404-o5b
type: quick
phase: quick
plan: 260404-o5b
subsystem: meridian
tags: [dockerfile, npm, oauth, run.sh, config.yaml]
dependency_graph:
  requires: []
  provides: [meridian-single-stage-build, meridian-oauth-polling]
  affects: [meridian/Dockerfile, meridian/run.sh, meridian/config.yaml]
tech_stack:
  added: []
  patterns: [npm-global-install, oauth-background-polling]
key_files:
  created: []
  modified:
    - meridian/Dockerfile
    - meridian/run.sh
    - meridian/config.yaml
decisions:
  - Replace multi-stage bun build with single-stage npm install of @rynfar/meridian
  - Poll for oauth credentials instead of hard-exiting on missing credentials
  - Remove addon_config map since /data is implicit persistent volume
metrics:
  duration: "~2 minutes"
  completed: "2026-04-04"
  tasks_completed: 3
  files_modified: 3
---

# Quick Task 260404-o5b: Meridian Dockerfile Simplify + OAuth Polling Summary

**One-liner:** Replaced fragile bun multi-stage build with single-stage npm install of @rynfar/meridian and added
background oauth polling in run.sh instead of hard-exit on missing credentials.

## Tasks Completed

| Task | Name                                                       | Commit  | Files                |
| ---- | ---------------------------------------------------------- | ------- | -------------------- |
| 1    | Simplify Dockerfile to single-stage npm install            | c7429d1 | meridian/Dockerfile  |
| 2    | Update run.sh — oauth polling flow and meridian invocation | 99eebe7 | meridian/run.sh      |
| 3    | Fix config.yaml map — use data type for /data access       | 19af0b3 | meridian/config.yaml |

## Changes Made

### Task 1: Dockerfile

Removed the two-stage build (Stage 1: `oven/bun`, Stage 2: HA base). Replaced with a single-stage Dockerfile that:

- Uses `ghcr.io/home-assistant/amd64-base:3.23` directly
- Installs Node.js and npm via apk
- Installs `@rynfar/meridian@${VERSION}` globally via npm
- Installs `@anthropic-ai/claude-code` globally via npm
- Copies `run.sh` to `/run.sh` and sets CMD to run it
- Drops `ENV WORKING_DIR` (no longer needed — global binaries on PATH)

### Task 2: run.sh

Replaced hard-exit on missing credentials with a background oauth polling flow:

- Starts `claude login &` in background (prints OAuth URL to HA logs)
- Polls every 5 seconds up to 600 seconds for `/data/.claude/.claude.json` to appear
- Kills background login process after credentials are found
- Changed final exec from `exec node "${WORKING_DIR}/dist/cli.js"` to `exec meridian`

### Task 3: config.yaml

Removed the `addon_config` map entry (was mounting to `/opt/meridian/data`, now unused). The implicit `/data` volume
provides OAuth credential persistence without an explicit mount entry. Set `map: []`.

## Verification

All checks passed:

- `make lint` — all pre-commit hooks passed
- `make validate-addons` — all three add-ons validated
- `shellcheck -e SC1091 -e SC2034 meridian/run.sh` — no warnings
- `grep -c "FROM oven/bun" meridian/Dockerfile` — outputs 0 (no bun stage)
- `grep "exec meridian" meridian/run.sh` — matches
- `grep "npm install -g @rynfar/meridian" meridian/Dockerfile` — matches

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files exist:

- meridian/Dockerfile: present and contains single FROM line
- meridian/run.sh: present and contains `exec meridian`
- meridian/config.yaml: present with `map: []`

Commits exist:

- c7429d1: feat(260404-o5b): replace multi-stage bun build with single-stage npm install
- 99eebe7: feat(260404-o5b): rewrite run.sh with oauth polling flow and exec meridian
- 19af0b3: fix(260404-o5b): remove addon_config map from meridian config.yaml
