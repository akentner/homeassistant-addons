---
phase: 27-ntfy-admin-ui-lib-migration
plan: 02
subsystem: ntfy admin GUI (backend server)
tags: [admin-ui, skeleton, csp, error-contract]
requires: [27-01 (vendored skeleton ntfy/app/web/admin_ui, lib 0.5.0)]
provides:
  - app.contract.ApiError / ERROR_STATUS / INGRESS_REMOTE are the skeleton objects plus 4 registered ntfy codes
  - app.web.server is a 44-line adapter over the skeleton (was 244 lines)
  - app.gui.csp_from_env and the NTFY_GUI_CSP=strict|off escape hatch
affects: [27-07]
key-files:
  modified:
    - ntfy/app/contract.py
    - ntfy/app/web/server.py
    - ntfy/app/gui.py
    - ntfy/tests/test_contract.py
    - ntfy/tests/test_server.py
  created:
    - ntfy/tests/test_gui.py
decisions:
  - "Lib 0.5.0 instead of the planned 0.4.0 (as in 27-01); 0.5.0 adds public routes, which ntfy does not use, so the gate behaves as before"
  - "make_server(static=...) takes a StaticFiles; the default is resolved at call time so a patched STATIC_DIR still works"
  - "Server header is now AdminUi (skeleton make_server has no server_version argument); not asserted in tests"
status: complete
metrics:
  completed: 2026-11-03
actuals:
  tokens: 14000
  tasks: 2
  commits: 2
plan_head_before: 2d83232
plan_head_after: b00d2d1
---

# Phase 27 Plan 02: ntfy server on the admin-ui skeleton Summary

The ntfy GUI server now runs on the vendored skeleton; gate, router, static whitelist, body rules, security headers and
shutdown come from `app.web.admin_ui`, with unchanged API error codes, routes and response shapes.
(`commits`/`plan_head_after` count the two code commits; the SUMMARY commit follows them.)

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | C8 error contract on the skeleton ApiError, 4 ntfy codes registered | 3776c03 |
| 2 | Thin server adapter, entry point on skeleton `serve`, `NTFY_GUI_CSP` switch | b00d2d1 |

## What changed

- `contract.py`: ApiError, ERROR_STATUS (register_error_code for ntfy_error 502, db_unavailable 503, db_unsupported 503,
  locked 503) and INGRESS_REMOTE are imported from the skeleton and re-exported by name; CLI mapping and ROUTES untouched.
  A literal 13-code mapping test pins the contract.
- `server.py`: re-exports Request, Router, Download, STATIC_DIR; `make_server(router, port, ingress_remote, host, static,
  csp)` delegates to the skeleton with a `NtfyCliError` mapper (NtfyCliError -> api_error_from_cli).
- `gui.py`: `csp_from_env` (unset or `strict` -> DEFAULT_CSP, `off` -> None, else ValueError); signal handling replaced by
  the skeleton `serve`. The `[gui] listening` line and NTFY_GUI_PORT / NTFY_INGRESS_REMOTE stay.
- Tests: test_contract (identity, literal mapping, idempotent registration, ingress constant), test_server (CSP on page and
  static only, headers on every response, csp=None, static root injection, STATIC_DIR default), new test_gui.

## Verification

- `pytest ntfy/tests -q`: 367 passed (includes node view tests via test_js.py and test_registry, test_static_closure).
- `make check-admin-ui-sync`: OK (ntfy lib/skeleton 0.5.0); `make check-admin-ui-rules`: no findings.
- No diff in `ntfy/app/web/api`, `ntfy/app/web/admin_ui`, `admin-ui` against the base.
- `server.py` 44 lines (< 60); `gui.py` contains no `signal`.

## Deviations from Plan

- Lib is 0.5.0, not 0.4.0 (see decisions). No effect on this plan.
- Acceptance check `git diff origin/main -- ...` was run against the base commit 2d83232 instead, because plan 27-01 lives on
  the feature branch and not on origin/main.
- Worktree started on main (29e6587); fast-forwarded to 2d83232 (the stated base) before any work.
- Plan commit ledger (protocol 0c) was not recorded for the first commit; the base 2d83232 was taken from the git history.
- A disk-full crash interrupted the first session after commit 3776c03; the working tree edits survived and were verified
  and committed as b00d2d1. No rework needed.

## Lib friction (for the admin-ui manager, nothing blocking)

- Skeleton `make_server` has no `server_version` argument, so the Server header says `AdminUi` for ntfy (cosmetic).

## Known Stubs

None.

## Threat Flags

None. T-27-05..07 are covered by the existing gate, error-body and whitelist tests running against the skeleton; T-27-08 by
the CSP tests and the `NTFY_GUI_CSP=off` switch (live check stays with plan 27-07).

## Self-Check: PASSED

- 3776c03 and b00d2d1 exist in the branch history; files listed above exist.
