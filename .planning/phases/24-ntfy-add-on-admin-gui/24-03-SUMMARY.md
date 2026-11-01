---
phase: 24-ntfy-add-on-admin-gui
plan: 03
subsystem: backend
tags: [ntfy, origins, backups, export, python-stdlib]
requires: ["24-01"]
provides:
  - OriginStore sidecar (C4), BackupStore (C12), schema-1 exporter (C11), ctx.origins and ctx.backups
affects: [24-06, 24-07, 24-08, 24-09]
actuals:
  tasks: 3
  commits: 3
key-files:
  created:
    - ntfy/app/origins.py
    - ntfy/app/backups.py
    - ntfy/app/exporter.py
    - ntfy/docs/EXPORT_SCHEMA.md
  modified:
    - ntfy/app/context.py
requirements-completed: [D-08, D-09, D-14, ROADMAP-SC6]
completed: 2026-11-02
---

# Phase 24 Plan 03: origin sidecar, backups, export schema 1 Summary

## Commits

- `3af0b4c` feat(ntfy): add origin sidecar store with corruption tolerance
- `2a7ac49` feat(ntfy): add auth.db backup store and wire origins and backups into context
- `7d70a08` feat(ntfy): add schema-1 exporter and export format document

## Verification

- `pytest test_origins test_backups test_exporter test_contract test_server`: 62 passed (origins 16, backups 15,
  exporter 11).
- `pre-commit run --files ntfy/docs/EXPORT_SCHEMA.md` green; `awk 'length > 120'` prints nothing.
- No Docker used.

## Deviations

1. `create()` maps `sqlite3.Error` (for example a garbage auth.db) to `ApiError db_unavailable` and leaves no temp file.
2. A sidecar whose shape is valid but contains an unknown origin value counts as corrupt (renamed, store empty).
3. `BackupStore.keep` is a public attribute (clamped to at least 1) so tests and later plans can read it.
4. The exporter treats rows with role `anonymous` or name `*`/`everyone` as anonymous and runs ACL users through
   `db_user_to_api`, so it works with a reader that returns either form.
5. Executed inline in the worktree (no gsd-executor subagent), STATE/ROADMAP/state.json untouched. The commit hashes in
   24-01-SUMMARY.md differ from `git log` of this branch; not relevant here.

## Open points for later waves

- `AuthDb.list_users(include_hash=...)` is still 24-02's job; the exporter relies on the reader returning `pass_hash`
  when asked and ignores it otherwise.
- Exports of the real `AuthDb` should be cross-checked against C5 row shapes once 24-02 lands (token rows need
  `token_id`, ACL rows `user` in API or DB form).
- 24-06/07/09 must call `origins.prune(...)` themselves; nothing prunes automatically. `create_daily()` is not yet
  called at start (24-09/24-11).
- The origin sidecar does not know about provisioned rows; `options` origins are written by 24-09.
