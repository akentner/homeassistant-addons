---
phase: 03-meridian-add-on
plan: "01"
subsystem: infra
tags: [dockerfile, bun, nodejs, meridian, upstream-tracking]

# Dependency graph
requires:
  - phase: 02-auto-update-workflow
    provides: .upstream.yaml auto-update infrastructure and validate-versions hook pattern
provides:
  - meridian/Dockerfile — multi-stage bun build + HA amd64-base runtime
  - meridian/build.yaml — HA add-on build config with VERSION=1.26.6
  - meridian/.upstream.yaml — auto-update config watching rynfar/meridian
affects: [03-02, 03-03, 03-04, 03-05]

# Tech tracking
tech-stack:
  added: [oven/bun:1, @anthropic-ai/claude-code, nodejs, npm]
  patterns: [multi-stage Dockerfile with bun build + HA base runtime, GitHub tarball fetch at build time]

key-files:
  created:
    - meridian/Dockerfile
    - meridian/build.yaml
    - meridian/.upstream.yaml
  modified:
    - .pre-commit-config.yaml

key-decisions:
  - "Multi-stage build: oven/bun:1 compiles TS, HA amd64-base:3.22 is the runtime stage (D-01)"
  - "Source fetched via GitHub archive tarball at build time — consistent with phone-logger pattern (D-02)"
  - "node_modules copied from build stage, not re-installed at runtime (D-04)"
  - "@anthropic-ai/claude-code installed globally via npm to provide the claude CLI binary (D-03)"
  - "validate-versions pre-commit hook extended to include meridian alongside existing add-ons (D-15)"

patterns-established:
  - "Multi-stage Node.js HA add-on: bun build stage + HA base runtime, copy dist + node_modules"
  - "GitHub tarball fetch: curl -fsSL archive/refs/tags/v${VERSION}.tar.gz | tar xz --strip-components=1"

requirements-completed: [MER-02, MER-03, MER-08]

# Metrics
duration: 4min
completed: 2026-04-04
---

# Phase 3 Plan 01: Meridian Build Infrastructure Summary

**Two-stage Dockerfile (oven/bun:1 build + HA amd64-base:3.22 runtime) with GitHub tarball fetch and auto-update wiring
for rynfar/meridian v1.26.6**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-04T09:33:03Z
- **Completed:** 2026-04-04T09:35:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `meridian/build.yaml` with VERSION=1.26.6 and HA amd64-base:3.22 base image
- Created `meridian/.upstream.yaml` watching rynfar/meridian with sync versioning
- Created `meridian/Dockerfile` with two-stage build: bun compiles TS, HA base runs node
- Extended validate-versions pre-commit hook to cover meridian directory (D-15)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create meridian/build.yaml and meridian/.upstream.yaml** - `55d15ca` (feat)
2. **Task 2: Create meridian/Dockerfile (multi-stage bun build + HA runtime)** - `b483f37` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `meridian/build.yaml` — HA add-on build config: VERSION=1.26.6, amd64-base:3.22, WORKING_DIR=/opt/meridian
- `meridian/.upstream.yaml` — auto-update: watches rynfar/meridian, v\* pattern, sync versioning
- `meridian/Dockerfile` — two-stage: bun:1 fetches+builds TS source, HA base runs node with @anthropic-ai/claude-code
- `.pre-commit-config.yaml` — validate-versions files pattern extended to include meridian

## Decisions Made

- Worktree has hadolint commented out in `.pre-commit-config.yaml` (differs from main branch); DL3016 suppression
  handled via inline `# hadolint ignore=DL3016` comment in the Dockerfile
- validate-versions pattern update applied to worktree version (was `^fritz-callmonitor2mqtt/...` only, now includes
  `phone-logger` and `meridian`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Observation] validate-versions pattern in worktree differs from main branch**

- **Found during:** Task 2 (Dockerfile creation, .pre-commit-config.yaml update)
- **Issue:** Worktree `.pre-commit-config.yaml` had pattern `^fritz-callmonitor2mqtt/...` only (main branch had already
  added `phone-logger`). The worktree version was behind on the previous fix too.
- **Fix:** Updated pattern to `^(fritz-callmonitor2mqtt|phone-logger|meridian)/(config\.yaml|build\.yaml|README\.md)$`
  covering all three add-ons
- **Files modified:** `.pre-commit-config.yaml`
- **Committed in:** b483f37 (Task 2 commit)

---

**Total deviations:** 1 auto-adjusted (worktree pre-commit config state) **Impact on plan:** No scope creep — D-15 was
already planned; worktree divergence required covering both the previous pattern and the new meridian addition.

## Issues Encountered

None — plan executed cleanly with one observation about worktree config state.

## User Setup Required

None - no external service configuration required at this stage.

## Next Phase Readiness

- Build infrastructure ready: Dockerfile, build.yaml, .upstream.yaml all in place
- Next plans (03-02 through 03-05) can now create config.yaml, run.sh, README.md, DOCS.md
- The meridian/ directory is registered in auto-update tracking
- No blockers

---

## Self-Check: PASSED

- FOUND: meridian/Dockerfile
- FOUND: meridian/build.yaml
- FOUND: meridian/.upstream.yaml
- FOUND: .planning/phases/03-meridian-add-on/03-01-SUMMARY.md
- FOUND: commit 55d15ca (Task 1)
- FOUND: commit b483f37 (Task 2)

_Phase: 03-meridian-add-on_ _Completed: 2026-04-04_
