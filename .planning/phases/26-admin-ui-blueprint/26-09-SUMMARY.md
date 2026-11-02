---
phase: 26-admin-ui-blueprint
plan: 09
subsystem: ci
tags: [ci, github-actions, supply-chain]
requires:
  - phase: 26-06
    provides: Makefile target check-admin-ui-sync
provides:
  - lint.yml job admin-ui (node --test, pytest, sync check) and lint-results gating on it
affects: [26-12]
actuals:
  tasks: 2
  commits: 1
key-files:
  modified:
    - .github/workflows/lint.yml
key-decisions:
  - "Pins verified by the human via the manager: pytest==9.1.1 (2026-06-19), pyyaml==6.0.3 (2025-09-25)"
requirements-completed: [D-17, PD-13]
status: complete
---

# Phase 26 Plan 09: admin-ui CI job Summary

**lint.yml gains an `admin-ui` job (appended after `lint-results`) running the node lib tests, the pytest suite and
`make check-admin-ui-sync`; `lint-results` now needs both jobs.**

## Task Commits

1. **Task 1: pin checkpoint** - no commit (human-verify, resolved)
2. **Task 2: admin-ui CI job** - see `git log` (`ci(admin-ui): add admin-ui test job ...`)

## Checkpoint resolution

- Human approved `pytest==9.1.1 pyyaml==6.0.3` (via the manager, explicit in chat). 9.1.1 was chosen over the
  audit-flagged 9.2.0 (released 2026-10-27) for recency margin; neither is yanked, source repo pytest-dev/pytest.
- PyPI metadata (release dates, yanked state, source URL) was checked by the worker via the PyPI JSON API.
- **Not verified:** maintainer history / ownership changes and sha256 comparison on PyPI were not checked separately by
  the user.

## Verification

- `git diff --numstat`: 37 additions, 2 deletions (only `needs:` and the verdict `if` line changed).
- zizmor 1.30.1 (`--offline --config zizmor.yml`): no findings (5 ignored, 5 suppressed); deferral lines unmoved.
- YAML assertion (job exists, `needs == [lint, admin-ui]`): ok. `actionlint` not installed locally; CI covers it.
- Local run of the job commands: node 90/90 pass, pytest 228 passed.

## Deviations / open points

- `make check-admin-ui-sync` fails locally with "admin-ui/lib.lock missing". Expected: `lib.lock` is created by plan
  26-12 (see 26-06-SUMMARY). The new CI job will therefore be red on this branch until 26-12 lands; merge 26-09 only
  together with or after 26-12, or accept a red `admin-ui` check in between.
- Task 2 precondition satisfied; no other files touched (STATE.md, ROADMAP.md, state.json untouched).
