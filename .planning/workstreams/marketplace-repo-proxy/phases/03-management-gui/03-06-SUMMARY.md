---
phase: 03-management-gui
plan: 06
subsystem: ui
tags: [admin-ui, preact, node-test, i18n, a11y, ci]

requires:
  - phase: 03-management-gui
    provides: "03-01 GUI server, api/overview, POST api/sync, api/meta, tracer Repositories view, model.mjs"
provides:
  - "views/repositories.mjs: global Sync now button, pollMs cadence (2 s while requested/running, 15 s idle), sync line, registration column only when data exists, branch-source hint, add-on names as text"
  - "model.mjs: pollMs, REGISTRATION_KEYS, BRANCH_KEYS, hasRegistration"
  - "strings mrp.sync.*, mrp.reg.*, mrp.repo.branch.* (de/en)"
  - "tests/js/{fakedom,a11y_audit}.mjs, tests/js/{i18n,model,repositories}.test.mjs, tests/test_js.py (FILES = i18n, model, repositories)"
  - "Makefile test-admin-ui-consumers line and CI steps (node tests, lib sync, blueprint rules) in job marketplace-repo-proxy"
affects: [03-03, 03-04, 03-05]

actuals:
  tasks: 3
  commits: 4
plan_head_before: ba8153d
plan_head_after: 5b4b8ea

tech-stack:
  added: []
  patterns:
    - "i18n key-existence scan globs views/*.mjs, so the Access and Info views of 03-03/03-05 are covered without a test change"
    - "Dynamic i18n keys are rejected; only literal keys, *_KEYS table lookups, x.labelKey/x.titleKey and statusKey(...) are sanctioned"

key-files:
  created:
    - marketplace-repo-proxy/tests/js/fakedom.mjs
    - marketplace-repo-proxy/tests/js/a11y_audit.mjs
    - marketplace-repo-proxy/tests/js/i18n.test.mjs
    - marketplace-repo-proxy/tests/js/model.test.mjs
    - marketplace-repo-proxy/tests/js/repositories.test.mjs
    - marketplace-repo-proxy/tests/test_js.py
  modified:
    - marketplace-repo-proxy/app/web/static/views/repositories.mjs
    - marketplace-repo-proxy/app/web/static/model.mjs
    - marketplace-repo-proxy/app/web/static/strings.de.mjs
    - marketplace-repo-proxy/app/web/static/strings.en.mjs
    - Makefile
    - .github/workflows/lint.yml

key-decisions:
  - "03-06: the i18n scanner sanctions BRANCH_KEYS lookups in addition to STATUS_KEYS/REGISTRATION_KEYS; every value of those tables is checked against both string tables"
  - "03-06: no string-table fix was needed in Task 3; all i18n and a11y checks passed on the tables from Task 2"

requirements-completed: []

duration: interrupted run (executor session ended during Task 3; orchestrator finished Task 3 and the SUMMARY)
completed: 2026-11-19
status: complete
---

# Phase 3 Plan 06: Repositories View and Tested admin-ui Consumer Summary

**Repositories view with one global Sync now button, 2 s/15 s poll cadence, registration column only when data
exists and the top-bar version, plus node tests (fakedom, i18n parity and key scan, a11y audits) run from pytest, the
consumer runner and CI**

## Accomplishments

- Sync now in the Repositories view posts `{}` to the relative `api/sync`, shows a toast, disables itself while a
  cycle is requested or running; failures show the localised error text, never the server message.
- The view polls every 2 s while the sync is `requested` or `running` and every 15 s when idle; the sync line shows
  the state and the next due time.
- Registration column appears only when at least one repository has registration data (D-19), each of the four
  states has its own text; hostile `message`, `detail` and add-on names render as text only.
- Top bar shows the version from `api/meta` (D-30); null or failed `api/meta` renders no version element.
- `tests/test_js.py` runs the node suite (`i18n`, `model`, `repositories`) from pytest; `make
  test-admin-ui-consumers` and CI job `marketplace-repo-proxy` run it too, plus lib-sync and blueprint-rules checks.

## Task Commits

1. **Task 1: tracer (Sync now → node test → pytest wrapper → consumer runner → CI)** - `eacdbbf` (feat)
2. **Task 2 RED: sync state, poll cadence, registration column, branch source** - `3f57874` (test)
3. **Task 2 GREEN** - `e7bc9b3` (feat)
4. **Task 3: i18n parity, key-existence scan and a11y audits** - `5b4b8ea` (test)

## Verification

- `node --test marketplace-repo-proxy/tests/js/*.test.mjs`: 35 tests, 35 pass, 0 fail.
- `make check-admin-ui-sync check-admin-ui-rules`: green, no finding for marketplace-repo-proxy.
- `pytest marketplace-repo-proxy/tests/test_js.py`: 1 passed.
- Full add-on suite `pytest marketplace-repo-proxy/tests`: 391 passed.
- `make test-admin-ui-consumers`: all consumers green (marketplace-repo-proxy 391 passed).
- `a11y_audit.mjs` is a byte copy of `haos-monitor/tests/js/a11y_audit.mjs` (sha256 identical).
- `grep -c '"i18n", "model", "repositories"' tests/test_js.py` = 1.
- `lint.yml` diff hunks start at lines 313, 321, 326 (none above line 297); Makefile consumer line present.
- `pre-commit run --files` on the Task 3 files: all hooks passed.

## TDD Gate Compliance

- Task 2: RED `3f57874` before GREEN `e7bc9b3`.
- Task 3: the new tests passed on first run against the Task 2 string tables, so no GREEN fix commit followed (the
  plan only fixes string tables when a finding appears).

## Deviations from Plan

- **Interrupted executor (process).** The executor session ended during Task 3. The orchestrator found the Task 3
  test files uncommitted plus one stray edit to `views/repositories.mjs` that removed the Sync now button label (a
  negative-control probe of the a11y audit left in place). That edit was discarded with `git restore` on the single
  path; the remaining Task 3 files matched the plan and were committed after all Task 3 checks passed.
- A negative control (button without label) could not be confirmed in isolation: with the label removed, the earlier
  Sync now tests fail and the file runs into poll timeouts before the a11y tests report. The audit logic itself flags
  a button without text (`nameOf` falls back to `textContent`).
- `app/web/static/app.mjs` is listed in `files_modified` but needed no change; the top-bar version from 03-01 already
  matched the tests.

## Issues Encountered

None beyond the interruption above.

## Self-Check: PASSED

- Created files exist on disk; commits `eacdbbf`, `3f57874`, `e7bc9b3`, `5b4b8ea` are on branch
  `feat/marketplace-repo-proxy-p3`.
