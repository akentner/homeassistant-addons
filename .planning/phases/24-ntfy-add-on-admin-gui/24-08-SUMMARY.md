---
phase: 24-ntfy-add-on-admin-gui
plan: 08
subsystem: backend
tags: [ntfy, maintenance, reset, export, backups, health]
requires: ["24-02", "24-03"]
provides:
  - maintenance services (reset_acls, clear_cache, reset_everything, publish_test)
  - routes POST api/reset/{acls,cache,everything}, GET api/export, GET/POST api/backups, GET api/backups/{name}
  - GET api/health with counts and POST api/health/publish
affects: [24-10, 24-11]
actuals:
  tasks: 3
  commits: 3
key-files:
  created:
    - ntfy/app/maintenance.py
    - ntfy/app/web/api/export.py
    - ntfy/app/web/api/backups.py
    - ntfy/app/web/api/reset.py
  modified:
    - ntfy/app/web/api/health.py
requirements-completed: [D-04, D-09, D-11, D-14, D-17, ROADMAP-SC4, ROADMAP-SC6]
completed: 2026-11-02
---

# Phase 24 Plan 08: resets, cache clearing, test publish, export and backups Summary

## Commits

- `5581754` feat(ntfy): add guarded resets, cache clearing and test publish services
- `9d98f9a` feat(ntfy): add export and backup endpoints
- `11730de` feat(ntfy): add guarded reset routes, health counts and test publish route and API tests

## Verification

- `pytest ntfy/tests` (whole directory in this worktree): all green. This plan's modules: test_maintenance 26 passed,
  test_api_maintenance 21 test functions (parametrized to more cases), plus test_contract, test_server, test_exporter,
  test_backups.
- py_compile of all five modules, no line over 120 chars. No Docker used.

## Deviations

1. Tasks 2 and 3 share `test_api_maintenance.py`, which imports `reset`, so the whole test file landed in the Task 3
   commit; the Task 2 commit contains only `export.py` and `backups.py`.
2. `reset_acls` and `clear_cache` return `{"done": True, "backup": ...}` (cache additionally the two counters).
3. `export` and the reset routes reject an empty `format=` / `include_hashes=` value (400) instead of treating it as
   the default.
4. `publish_test` lets an exception raised by the injected/real HTTP call propagate after the token is removed
   (the router then answers 500 or the mapped error); HTTP error statuses (429, 401 ...) are returned as `ok: false`.
5. `GET api/health` also catches `ApiError` from `counts()` and falls back to `counts: null` (never raises).

## Open points for later waves

- `reset_everything` is tested with a stubbed `bootstrap.apply_options`; the real recreation of admin and baseline
  (24-09) must be proven in 24-11.
- `maintenance.publish_test` does not catch `OSError`/`URLError` from the real network call; the GUI shows a generic
  500 then. 24-10 may want `ok:false` handling or 24-11 can decide.
- Reset and cache routes are not called with the real ntfy yet (cache DELETE was verified live during planning only).
- The health `ntfy_health` probe is reused unchanged; tests patch `app.web.api.health.ntfy_health`.
