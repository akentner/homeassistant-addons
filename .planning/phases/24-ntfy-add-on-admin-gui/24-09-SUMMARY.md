---
phase: 24-ntfy-add-on-admin-gui
plan: 09
subsystem: backend
tags: [ntfy, bootstrap, baseline, origins, backups]
requires: [24-02, 24-03]
provides:
  - apply_baseline (additive, origin-aware, D-18 password overwrite) and BaselineReport
  - bootstrap with ensure_admin (origin options), apply_options (actions/warnings) and daily backup in main
affects: [24-08, 24-11]
actuals:
  tasks: 2
  commits: 2
requirements-completed: [D-04, D-05, D-06, D-08, D-14, D-18]
completed: 2026-11-02
---

# Phase 24 Plan 09: baseline, admin bootstrap, daily backup Summary

## Commits

- `9a2335e` feat(ntfy): add additive options baseline with origin ownership
- `8fea65e` feat(ntfy): wire baseline, admin origin and daily backup into bootstrap

## Verification

- `pytest test_bootstrap test_baseline test_contract`: 45 passed (baseline 20, bootstrap 12); `pytest ntfy/tests`: 149 passed.
- py_compile ok, no line over 120 chars, no `user_delete`/`access_reset` in baseline.py, `create_daily` called in `main`.
- No Docker used.

## Deviations

1. `BootstrapReport` changed shape (`actions`, `warnings`, `summary()`) as the plan specifies; the tracer fields
   (`admin_created`, `admin_existed`, `notes`) are gone and `ensure_admin` now returns `list[str]`.
2. `main()` takes the daily backup after `wait_for_auth_db` (auth.db only exists once the server runs, see 24-01
   deviation 1), still before any change. On a first start without auth.db nothing is backed up.
3. Orphan handling never flips `admin_user` (its `options` origin is owned by `ensure_admin`, not the baseline).
4. The fake CLI stores a constant filler hash, so tests assert `change-pass` calls (argv, `env_password`), not hash changes.
5. Executed inline, STATE/ROADMAP/state.json untouched.

## Open points for later waves

- A baseline user that already exists keeps its origin (usually `gui`); only users the baseline creates become `options`.
- `main()` returns 1 only when the context cannot be built (invalid options.json); run.sh must tolerate that (background job).
- 24-08 "reset everything" should call `apply_options(ctx)` after `origins.clear_all()`; verified by a test.
- Orphaned `options` records of users/rules deleted elsewhere are only pruned by `origins.prune`, which nothing calls at start.
