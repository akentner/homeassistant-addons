---
phase: 27-ntfy-admin-ui-lib-migration
plan: 07
subsystem: ntfy Docker verification and phase exit gate
tags: [docker, verify, e2e, csp, exit-gate]
requires: [27-02, 27-03, 27-04, 27-05, 27-06]
provides:
  - Docker scaffold verify for the lib layout (closure, 404 paths, response headers)
  - E2E gate scenario covering the lib and strings static paths
  - phase exit gate results
affects: [27-VERIFICATION]
key-files:
  modified:
    - internal/verify-ntfy-scaffold.sh
    - internal/verify-ntfy-e2e.py
status: tasks-1-2-complete-task-3-pending
metrics:
  completed: 2026-11-03
actuals:
  tokens: 1500
  tasks: 2
  commits: 2
plan_head_before: f983b36
plan_head_after: 4f9408e
---

# Phase 27 Plan 07: Docker verifies and phase exit gate Summary

The migrated ntfy add-on builds into a real image and passes the Docker scaffold verify (exit 0) and the Docker E2E
(122 checks, 0 failed). The phase exit gate is green. Task 3 (the human UAT in real Home Assistant ingress) is not
part of this run and is pending.

`actuals.tokens` is chars/4 over the changed text (about 40 added lines). `commits: 2` counts the two code commits
(`plan_head_after` is the last of them; the SUMMARY commit follows).

## Tasks

| Task | Name | Commit | Result |
| ---- | ---- | ------ | ------ |
| 1 | Extend the Docker verify scripts for lib layout, closure and headers | b1f50b8 | shellcheck, `bash -n`, `py_compile` clean |
| 1b | Request closure files status-only (binary body warning) | 4f9408e | follow-up fix in the same script |
| 2 | Run the Docker verifies one after the other, then the exit gate | no code change | all green, see below |

### Task 1: verify script changes

- `internal/verify-ntfy-scaffold.sh`: the old `/static/lib/api.mjs` check now reads `/static/vendor/admin-ui/api.mjs`
  (still expects the template string that builds relative `api/` URLs).
- New block "Frontend closure": a host-side `find` over `ntfy/app/web/static` for the served extensions (mjs, js, css,
  png, svg, txt); every file is requested through the container with the ingress header and must answer 200; at least
  30 files are required; `vendor/admin-ui/LIB.stamp`, `/static/vendor/preact-htm.mjs` (old bundle) and
  `/static/lib/ui.mjs` must answer 404.
- New block "Response headers": for `/` and `/static/app.mjs` a CSP containing `script-src 'self'` and
  `frame-ancestors 'self'`, `x-content-type-options: nosniff` and no `x-frame-options`; for `/api/health` no CSP and
  `cache-control: no-store`.
- `internal/verify-ntfy-e2e.py`: `s14_gate` also requests `/static/vendor/admin-ui/ui.mjs` and
  `/static/strings.en.mjs` without the ingress header (expects 403 `ingress_only`). Nothing else changed.

### Task 2: results

Docker was idle before the run (no verify or e2e container, no image build running). The two verifies ran strictly one
after the other and left nothing behind (`docker ps -a` for the `ntfy-verify` and `ntfy-e2e` prefixes lists 0
containers after both runs).

| Check | Result |
| ----- | ------ |
| `bash internal/verify-ntfy-scaffold.sh` | exit 0, "All ntfy scaffold verifications passed."; closure block: 38 files served, 404 for LIB.stamp and old bundle paths; response headers block passed |
| `bash internal/verify-ntfy-e2e.sh` | exit 0, "All ntfy e2e checks passed", 122 checks, 0 failed, 17 scenario headings (1 to 16 plus 12b); baseline 120 checks, +2 from the new gate paths |
| `make check-admin-ui-sync` | OK (lib 0.5.0, ntfy lib and skeleton, secrets-sync lib and skeleton) |
| `STRICT=yes make check-admin-ui-sync` | OK |
| `make check-admin-ui-rules` | OK |
| `make test-ntfy` | Node 127 pass 0 fail; pytest 386 passed |
| `make validate-versions` | passed for all add-ons |
| `make validate-addons` | passed |
| `make validate-dockerfiles` | OK |
| `uv run --with pyyaml python3 internal/validate-addon-config.py` | passed |
| `uv run --with pyyaml bash internal/verify-ntfy-registration.sh` | "All ntfy registration checks passed" |
| `git diff origin/main -- admin-ui ntfy/Dockerfile ntfy/run.sh ntfy/build.yaml` | empty (origin/main fetched, 29e6587) |
| Co-Authored-By in `origin/main..HEAD` | none |

Versions: lib 0.5.0 (`ntfy/app/web/admin_ui/LIB.stamp`), ntfy add-on 2.37.0-2.

Note on the scaffold's "health (schema 10)" echo line: the check itself accepts schema 10 or 11; the label is
unchanged from Phase 24 and only cosmetic.

## Deviations from Plan

**1. [Rule 1 - Bug] Closure loop passed binary `icon.png` through a shell variable**
- **Found during:** Task 2, first scaffold run (the run passed, but printed a NUL-byte warning from the `gui` helper)
- **Issue:** the shared `gui` helper captures the body in a variable; a PNG body triggered a bash warning.
- **Fix:** the closure loop requests each file status-only (`curl -o /dev/null -w '%{http_code}'`).
- **Files modified:** `internal/verify-ntfy-scaffold.sh`
- **Commit:** 4f9408e

Otherwise: plan executed as written. No lib copy was edited, no earlier-plan code needed a fix, no versions changed,
`ntfy/Dockerfile` and `ntfy/run.sh` are untouched.

## Auth gates

None.

## Known Stubs

None.

## Threat Flags

None (verify scripts only; the existing sentinel-password checks for server.yml, logs and PID 1 cmdline ran
unchanged and passed, T-27-21).

## Task 3 UAT: pending

Task 3 (human UAT of the migrated panel in real Home Assistant ingress, per the plan's `how-to-verify`) was not run
by this executor and is handled by the parent session. To be filled with pass or fail per area (look, language, views,
errors, CSP header present and zero violations, HA integration, card), plus HA core version, browser or app and access
path. Record no tokens, host names or user names.

## Self-Check: PASSED

- internal/verify-ntfy-scaffold.sh and internal/verify-ntfy-e2e.py exist and carry the new checks
- commits b1f50b8 and 4f9408e are ancestors of HEAD
