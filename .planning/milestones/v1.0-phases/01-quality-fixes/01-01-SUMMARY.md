---
phase: 01-quality-fixes
plan: 01
subsystem: ci-hooks, documentation
tags: [pre-commit, validate-versions, docs, phone-logger]
dependency_graph:
  requires: []
  provides: [validate-versions-phone-logger, correct-adapter-type-docs]
  affects: [.pre-commit-config.yaml, phone-logger/DOCS.md]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - .pre-commit-config.yaml
    - phone-logger/DOCS.md
decisions:
  - "Extended files pattern in validate-versions hook to cover both add-ons with single regex alternation"
metrics:
  duration: "<1 minute"
  completed: "2026-04-03T22:14:23Z"
  tasks: 2
  files_modified: 2
---

# Phase 01 Plan 01: Fix validate-versions hook scope and DOCS.md adapter type Summary

Extend validate-versions pre-commit hook to trigger on phone-logger version files, and correct the wrong adapter type
name `fritz` to `fritz_callmonitor` in the example config block of phone-logger/DOCS.md.

## Tasks Completed

| Task | Name                                                | Commit  | Files                   |
| ---- | --------------------------------------------------- | ------- | ----------------------- |
| 1    | Extend validate-versions hook to cover phone-logger | 415eec4 | .pre-commit-config.yaml |
| 2    | Correct adapter type in phone-logger/DOCS.md        | 683e84a | phone-logger/DOCS.md    |

## Decisions Made

- Extended the `files:` pattern in the `validate-versions` hook entry from
  `^fritz-callmonitor2mqtt/(config\.yaml|build\.yaml|README\.md)$` to
  `^(fritz-callmonitor2mqtt|phone-logger)/(config\.yaml|build\.yaml|README\.md)$` using regex alternation. The
  `validate-versions.sh` script already auto-discovers all add-ons — only the trigger pattern needed updating.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- .pre-commit-config.yaml: modified with phone-logger in files pattern — FOUND
- phone-logger/DOCS.md: updated with `fritz_callmonitor` type — FOUND
- Commit 415eec4: FOUND
- Commit 683e84a: FOUND
- `make validate-versions` exits 0 — PASSED
