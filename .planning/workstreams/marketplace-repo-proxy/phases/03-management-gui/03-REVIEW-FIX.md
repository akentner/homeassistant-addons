---
phase: 03-management-gui
fixed_at: 2026-11-20T00:00:00Z
review_path: .planning/workstreams/marketplace-repo-proxy/phases/03-management-gui/03-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-11-20T00:00:00Z
**Source review:** .planning/workstreams/marketplace-repo-proxy/phases/03-management-gui/03-REVIEW.md
**Iteration:** 1

**Summary:**

- Findings in scope: 2 (WR-01, WR-02; scope `critical_warning`, no criticals)
- Fixed: 2
- Skipped: 0
- Out of scope: IN-01 to IN-08 (Info, IN-08 is a necessity finding); they remain open in REVIEW.md

`marketplace-repo-proxy/app/access.py` is unchanged (D-10). Both fixes are in `app/web/service.py` and its tests.

## Fixed Issues

### WR-01: Rotate rollback hides a post-write failure and returns 409 user_exists for a rotation that was persisted

**Files modified:** `marketplace-repo-proxy/app/web/service.py`, `marketplace-repo-proxy/tests/test_gui_service.py`
**Commit:** d1722d3
**Status:** fixed: requires human verification (logic change in the rollback path)
**Applied fix:**

- New `GuiService._restore_after_failed_add()`, called from the `except` branch of `rotate_user` under the store lock.
  It re-reads with `read_entries_safe` and re-adds the old hash only when the new entry is absent (the failed `add`
  wrote nothing). It never raises: a rollback error is logged by type name only, and the bare `raise` in
  `rotate_user` always re-raises the original `add` error.
- When `add` failed after its atomic write (for example in `reconcile_tree`), the new hash stays and the original
  `OSError` surfaces (mapped to 500 `internal_error`, not 409 `user_exists`). `access-watch` reconciles the tree on the
  changed file signature. The `rotate_user` docstring now says this.
- Tests: `test_rotate_keeps_the_add_error_when_add_fails_after_its_write` (patches `app.access.reconcile_tree` to fail
  on its second call, the one after `add`'s write; asserts the `OSError` with errno 28, one entry with a new hash and
  no rollback add) and `test_rotate_keeps_the_add_error_when_the_rollback_fails` (rollback `add` also fails; the
  original errno 28 still surfaces and the user stays revoked, fail closed).

### WR-02: The pre-read guard does not prevent `AccessStore.load()` from moving `access.json` aside and writing a one-user file

**Files modified:** `marketplace-repo-proxy/app/web/service.py`, `marketplace-repo-proxy/tests/test_gui_service.py`,
`marketplace-repo-proxy/DOCS.md`
**Commit:** 6e9be4b
**Status:** fixed: requires human verification (changes the store used for every GUI write)
**Applied fix:**

- New `_GuiStore(AccessStore)` in `service.py`. Its `load()` raises `AccessUnavailable` (503 `access_unavailable`) on
  any read error, invalid shape or newer schema, never renames and returns an empty document only when the file is
  missing. `GuiService._store()` returns it, so `add`, `revoke` and both steps of `rotate` re-read through it. It reuses
  `SCHEMA` and `_valid_shape` from `app.access` (import only, no change to that module).
- `rotate_user` now checks the return value of `store.revoke()` and raises `user_unknown` on `False` instead of going
  on to `add`.
- The module docstring now describes the second safeguard.
- DOCS.md:141 overstated the guarantee ("nothing is changed"): a rotation whose `add` read fails after the revoke
  restores the old hash with a new `created`. The sentence now reads: every action is refused with an error, the page
  never moves the file aside and never drops other users, and a rotation that fails after the revoke puts the old URL
  back when it can.
- Tests: `test_read_failure_after_the_guard_keeps_every_user` (three users; one injected `OSError` on the 2nd read of
  `access.json` for add, revoke and rotate, and on the 3rd read for rotate, the read of `add` after the revoke). It
  asserts `AccessUnavailable`, all users with unchanged hashes, unchanged links and no `access.json.corrupt`.
  `test_rotate_stops_when_revoke_finds_no_entry` asserts `user_unknown` and that `add` is never called. Before the
  fix, all five cases failed against the old `service.py` (checked by swapping in the old file temporarily); after it,
  all pass.

## Verification

Gates ran in the feature worktree itself (branch `feat/marketplace-repo-proxy-p3`, the checkout the orchestrator
assigned). No extra `.claude/worktrees/` worktree was created: the caller said to work in this checkout, and the
generic cleanup tail would have fast-forwarded the main repo's `main` instead of this branch. The numbers are
reproducible from this checkout.

- `python -m pytest tests -q` in `marketplace-repo-proxy/` (pytest 9.1.1 through `uv run --no-project --with ...`,
  same pins as CI): **520 passed** (513 before + 7 new).
- `node --test marketplace-repo-proxy/tests/js/*.test.mjs` from the repo root: **58 passed, 0 failed**.
- Pre-commit hooks passed on both commits without rewriting files.
- No docker build or run, no `internal/verify-*.sh`, no version bump, no network.

---

_Fixed: 2026-11-20T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
