---
phase: 01-git-serving-core
plan: 04
subsystem: infra
tags: [startup-log, masking, failure-policy, options, logging, ci, pytest]

requires:
  - phase: 01-git-serving-core
    provides: "Plan 01 modules app/init.py, app/urls.py, app/access.py, app/options.py, app/logsetup.py"
provides:
  - "app/init.py startup log: summary line, per-repository branch and user count, per-user label with masked internal and public store URLs"
  - "D-28 failure policy in init: exit 1 only for OptionsError and AccessSchemaError"
  - "Regression tests tests/test_init.py, tests/test_options.py, tests/test_logsetup.py"
  - "CI job marketplace-repo-proxy at the end of .github/workflows/lint.yml (python -m pytest marketplace-repo-proxy/tests -q)"
affects: [01-05, 01-06]

actuals:
  tokens: 6500
  tasks: 2
  commits: 3
plan_head_before: 550c4c98a2c3811d63dc35ac556648a043c518aa
plan_head_after: 9e8f05990be056fa604451937481a78f876d2dba

tech-stack:
  added: []
  patterns:
    - "Startup log lines built only from labels and urls.masked_store_url values (no full hash, no PAT)"
    - "init loads access.json and reconciles under one store lock, then logs from the same entries"
    - "Log scrubbing tests attach a StreamHandler(io.StringIO()) with SafeFormatter plus redactor, caplog-independent"

key-files:
  created:
    - marketplace-repo-proxy/tests/test_init.py
    - marketplace-repo-proxy/tests/test_options.py
    - marketplace-repo-proxy/tests/test_logsetup.py
  modified:
    - marketplace-repo-proxy/app/init.py
    - .github/workflows/lint.yml

key-decisions:
  - "01-04: a failed safe.directory write and an OSError while rebuilding the symlink tree are logged and survived (D-28); only OptionsError and AccessSchemaError return 1"
  - "01-04: the per-repository user count and user lines list only entries reconcile links (valid label and 32-hex hash)"

patterns-established:
  - "Masked URLs built as masked_store_url(internal_base(hostname) or public_url, owner, name, hash)"

requirements-completed: [MRP-01, MRP-05]

coverage:
  - id: D1
    description: "Startup log lists repositories (branch or upstream default, user count) and users with masked internal/public URLs; no full hash or token"
    requirement: "MRP-05"
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_init.py#test_startup_log_lists_users_with_masked_internal_urls"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_init.py#test_startup_log_adds_masked_public_url"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_init.py#test_startup_log_never_contains_the_token"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-28 failure policy: invalid options JSON and access.json schema 2 return 1 (file byte-identical); corrupt access.json, rejected entries, unconfigured entries, empty token are logged and survived"
    requirement: "MRP-05"
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_init.py (13 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Options contract regression tests (names, .git suffix, ./.., duplicates, branches, interval, public_url, token never leaked, load_options errors)"
    requirement: "MRP-01"
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_options.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Log scrubbing regression tests (token and base64 header scrubbed, 32-hex masked, 40-hex SHA intact, traceback scrubbed)"
    requirement: "MRP-05"
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_logsetup.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "CI job marketplace-repo-proxy appended to lint.yml"
    requirement: "MRP-01"
    verification:
      - kind: other
        ref: "pre-commit run --files .github/workflows/lint.yml (actionlint, zizmor, yamllint, gitleaks); git diff --numstat = 23 0"
        status: pass
    human_judgment: true
    rationale: "The job's first run on GitHub Actions happens after push; not observable locally"

duration: 4min
completed: 2026-11-18
status: complete
---

# Phase 01 Plan 04: Startup Log and Regression Tests Summary

**init logs every configured repository and user with masked store URLs (4 hex chars plus `…`), stops the container
only for invalid options or an unknown access.json schema, and CI now runs the add-on's 207 tests on every push.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-11-18T14:02:59Z
- **Completed:** 2026-11-18T14:06:18Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `run_init` logs `marketplace-repo-proxy: {n} repositories configured, {m} access entries`, per repository
  `repository {slug} (branch: {branch|upstream default}): {k} user(s)`, per user
  `  user {label} -> {masked internal URL}[ | public {masked public URL}]`, and one line for entries of unconfigured
  repositories (`... they stay inactive`).
- Empty `github_token` with repositories configured logs `github_token is empty; sync will report auth_failed`.
- D-28: a failed `safe.directory` write and an `OSError` while rebuilding the symlink tree are now logged and survived;
  only `OptionsError` and `AccessSchemaError` return 1.
- Options contract and secret-safe logging are locked by 58 regression tests; CI job `marketplace-repo-proxy` appended
  at the end of `.github/workflows/lint.yml` (23 added lines, 0 deleted).

## Task Commits

1. **Task 1 RED: failing tests for startup log and failure policy** - `b9be872` (test)
2. **Task 1 GREEN: startup log with masked URLs and D-28 policy** - `ebd0370` (feat)
3. **Task 2: options/logsetup regression tests and CI job** - `9e8f059` (test)

## TDD Gate Compliance

- **Task 1 RED:** `pytest marketplace-repo-proxy/tests/test_init.py -q --junitxml` exited 1 with 6 failed, 7 passed.
  Classifier `gsd-tools check tdd-red-evidence` (JUnit format) returned `RED_EVIDENCE_OK`, target
  `test_startup_log_lists_users_with_masked_internal_urls`. Semantic assessment: all six failures are
  `AssertionError`s on missing log lines (summary, per-user, unconfigured, token warning); no import, collection or
  fixture fault. The seven passing tests cover behaviour Plan 01 already shipped (dirs and modes, safe.directory,
  linking, stray symlink, both fatal cases).
- **Task 1 GREEN:** 13/13 pass after the `init.py` change.
- **Task 1 REFACTOR:** none needed.
- **Task 2:** the tests characterise existing Plan 01 modules; per the plan, `app/options.py` and `app/logsetup.py`
  change only when a test exposes a defect. All 58 passed on first run, so there is no RED commit and no fix (the
  plan anticipates this outcome).

## Files Created/Modified

- `marketplace-repo-proxy/app/init.py` - startup log (`log_startup`, `_active_users`, `_unconfigured_count`), token
  warning, D-28 handling; load and reconcile under one store lock
- `marketplace-repo-proxy/tests/test_init.py` - 13 init tests (isolated git env, umask restored)
- `marketplace-repo-proxy/tests/test_options.py` - options contract tests
- `marketplace-repo-proxy/tests/test_logsetup.py` - redactor, hash masking and traceback scrubbing tests
- `.github/workflows/lint.yml` - job `marketplace-repo-proxy` appended at the end

## Decisions Made

- The user count and user lines list only entries that reconcile actually links (valid label, 32-hex hash); invalid
  entries are already warned about by `reconcile_tree`.
- Masked URLs are built with `masked_store_url(internal_base(hostname), ...)` and `masked_store_url(public_url, ...)`,
  matching the keys of `urls.store_urls`. The full URL is never assembled in init.
- The old `access links: N (hostname H)` info line is now a debug line `access links: N`.

## Deviations from Plan

None - plan executed exactly as written. Making the `safe.directory` write failure non-fatal follows the plan's action
("the only non-zero returns stay OptionsError and AccessSchemaError"); it changes Plan 01 behaviour, which returned 1.

## Issues Encountered

None.

## Verification

- `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q`:
  207 passed (136 before this plan).
- `pre-commit run --files` on all five changed files: all hooks passed (actionlint, zizmor, yamllint, gitleaks).
- Acceptance greps: `masked_store_url` 3, `upstream default` 1, `they stay inactive` 1 in `app/init.py`;
  `^  marketplace-repo-proxy:$` 1 in lint.yml; pytest line in the last 30 lines 1; `git diff --numstat` 23 added,
  0 deleted.
- No Docker build, no container, no verify script (per plan; Plan 05 checks the startup log in the built image).

## Next Phase Readiness

- Plan 05 can check the startup log lines listed above in the built container.

## Self-Check: PASSED
