---
phase: 26-admin-ui-blueprint
plan: 12
subsystem: infra
tags: [lock, pre-commit, check-all, contract-test, docs, docker-smoke]
requires:
  - phase: 26-06
    provides: sync script, rules scanner, make targets
  - phase: 26-07
    provides: DOCS.md, test_docs.py
  - phase: 26-09
    provides: CI job admin-ui
provides:
  - admin-ui/lib.lock (version 0.1.0, lib and skeleton hashes)
  - pre-commit hooks check-admin-ui-sync and check-admin-ui-rules; admin-ui in the Dockerfile ARG hook
  - check-all prerequisites check-admin-ui-sync and check-admin-ui-rules
  - lib_contract.test.mjs (exact export sets of all lib modules) and docs drift tests
  - extended Docker smoke script (whole demo)
affects: [26-13]
requirements-completed: [D-01, D-03, D-04, D-05, D-06, D-15, D-16, D-17, PD-01, PD-02, PD-09, PD-13]
status: complete
---

# Phase 26 Plan 12: Lock, hooks, contract test, docs and final smoke Summary

**The lock makes the drift check non-vacuous, hooks and `check-all` run it with the rules scanner, the public API is
pinned by a test and DOCS.md, and the final image passes an end-to-end smoke.**

## Task Commits

1. **Task 1: lock, hooks, check-all** - `cab3aa3`
2. **Task 2: export contract test and DOCS reconciliation** - `c3ac73e`
3. **Task 3: extended Docker smoke script** - `54577e4`

## Accomplishments

- `lib.lock` created after the lib and skeleton trees passed the whitespace, EOF and line-ending hooks unchanged.
- Hooks are path-scoped (`pass_filenames: false`) with the same argument as the opencode gate hook.
- `lib_contract.test.mjs`: 14 tests, one per module, strings default-only, coverage of new files, plain-Node import
  safety. The real exports matched the expected lists exactly; no helper had to be un-exported.
- `test_docs.py`: five new tests (exports documented, lib files listed, skeleton `__all__` equals the documented names,
  make targets and changelog topics, spike items still pending).
- DOCS.md: reconciled intro, `check-admin-ui-rules` / `test-admin-ui` described, formatter options, bridge status values
  and theme-sync reasons; CHANGELOG `[0.1.0-0]` extended.
- Smoke script: every demo view file and `base.css` with type, seeded list, create 201, duplicate 409, delete 400 then
  204, 418 `teapot`, 500 without exception text, whoami echo and null, CSP with `script-src 'self'`, no
  `X-Frame-Options`, plus the earlier gate, hash and SIGTERM steps.

## Verification

- `node --test admin-ui/tests/js/*.test.mjs`: 238 pass, 0 fail
- `pytest admin-ui/tests -q`: 245 passed
- `make check-admin-ui-sync check-admin-ui-rules validate-versions validate-dockerfiles validate-addons
  verify-update-version-tag-timing`: green; `validate-addon-config.py` green; hadolint on `admin-ui/Dockerfile` green
- `bash internal/verify-admin-ui-scaffold.sh`: all steps passed; no container or `admin-ui-verify` image left over
- `pre-commit run --files <all phase files>`: all hooks passed (including the two new ones)
- No version string edited in this plan.

## Deviations

- The unused `--build-arg VERSION` was dropped from the smoke script (Dockerfile does not declare it; plan-checker
  finding).
- `admin-ui/README.md` already links DOCS.md (asserted by `test_docs_addon_readme_and_changelog`); no change needed.

## Open points

- `make check-all` fails in the `lint` member `verify-bridge-scaffold` (terraform-bridge image 84.9 MB over the 60 MiB
  cap). Not caused by this branch: it touches nothing under `terraform-bridge/`. All other members, including the two
  new ones, pass. To be handled separately on `main`.
- The CI job from 26-09 is green on this branch now that the lock exists.
- Live HA spike (S1..S15) stays `pending` for plan 26-13.
