---
phase: 24-ntfy-add-on-admin-gui
plan: 02
subsystem: backend
tags: [ntfy, sqlite, subprocess, python-stdlib, testing]
requires: [24-01]
provides:
  - complete NtfyCli (C6) and AuthDb (C5) adapters
  - executable fake ntfy CLI over a real-schema auth.db, plus make_context test helper
affects: [24-03, 24-06, 24-07, 24-08, 24-09]
actuals:
  tasks: 3
  commits: 2
requirements-completed: [D-02, D-05, D-08, D-13]
completed: 2026-11-02
---

# Phase 24 Plan 02: NtfyCli and AuthDb complete, fake ntfy Summary

## Commits

- `b2069a0` feat(ntfy): complete NtfyCli adapter, add fake ntfy CLI and test context helper (Task 1)
- next commit: feat(ntfy): complete read-only AuthDb ... conformance test (Tasks 2 and 3; Task 3 produced no extra code
  change, lint and conformance findings were clean)

## Verification

- `pytest` on test_ntfycli, test_authdb, test_contract, test_render_config, test_server: 58 passed.
- py_compile, import without PyYAML, no `print(`, single `mode=ro` line in authdb.py, no line over 120 chars in the two
  modules (test_render_config.py line 47 from 24-01 is over 120, not touched here).
- Fake log never contains the sample password (asserted); writes are serialized (overlap marker test); 300 reads
  concurrent with 20 CLI writes show no `database is locked`.

## Deviations

1. Invalid input (empty password, name `-x`, bad permission/topic/expires/token) raises `ValueError` before spawning,
   as the plan's behavior list says. The 24-01 tracer raised `NtfyCliError("invalid")` for these; API handlers in
   24-06+ must validate first or map `ValueError` to `bad_request`.
2. `reveal_token(user, token_id_)` keeps the parameter name `token_id_` (frozen interface in the plan) while the
   `AuthReader` Protocol says `token_id`; the conformance test exempts that one name. Call it positionally.
3. `size_bytes()` returns `None` (not 0) for a missing file, per the plan interface; `Health.db.size_bytes` can be null.
4. `NtfyCli.__init__` accepts `Path | str` for the file arguments. Retry sleep is the module function
   `app.ntfycli.sleep` (patch that in tests).
5. Task 1 was committed before `authdb.py` (Task 2), so that single commit alone would fail `test_ntfycli.py` at
   `has_user`; HEAD is consistent.

## Open points

- `bootstrap.ensure_admin` now sees `ValueError` for an invalid `admin_user`; `bootstrap.main` should keep
  catching broad exceptions (never block delivery). Not touched (outside files_modified).
- `check_schema` reports a DB without `schemaVersion` or an unreadable/corrupt file as `db_unsupported`; only a missing
  file is `db_unavailable`.
- The fake `user list` output is simplified (no `server config` suffixes); services use the DB, not CLI listings.
- Fake hooks for later plans: `FAKE_NTFY_LOG`, `FAKE_NTFY_LOCK_ONCE`, `FAKE_NTFY_DELAY`, `FAKE_NTFY_OVERLAP_DIR`.
