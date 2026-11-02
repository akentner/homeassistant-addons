---
phase: 26-admin-ui-blueprint
plan: 06
subsystem: infra
tags: [ha-addon, sync, drift-check, static-analysis, make]
requires:
  - phase: 26-01
    provides: lib and skeleton trees (C1), vendored bundle pinned by sha256
provides:
  - internal/sync-admin-ui.py (tree hash, LIB.stamp, lib.lock, PD-01 drift semantics)
  - internal/check-admin-ui-rules.py (rules scanner with --self-test, VENDOR_SHA256)
  - Makefile targets sync-admin-ui, check-admin-ui-sync, check-admin-ui-rules, test-admin-ui
  - docs/DEVELOPMENT.md section "Admin UI blueprint and lib sync"
affects: [26-09, 26-12]
requirements-completed: [D-05, D-06, D-15, D-16, PD-01, PD-02, PD-04, PD-10, PD-12]
key-files:
  created:
    - internal/sync-admin-ui.py
    - internal/check-admin-ui-rules.py
    - admin-ui/tests/test_sync.py
    - admin-ui/tests/test_static_rules.py
  modified:
    - Makefile
    - docs/DEVELOPMENT.md
status: complete
---

# Phase 26 Plan 06: Sync tooling and rules scanner Summary

**The lib and skeleton can be copied to consumers with deterministic hashes and stamps, every kind of drift turns red
with the PD-01 semantics, and the static blueprint rules are executable against the demo and any consumer.**

## Accomplishments

- `sync-admin-ui.py`: deterministic tree hash (order independent, skips `LIB.stamp`, `__pycache__`, `*.pyc`, refuses
  symlinks), strict stamp and lock parsers, atomic copy via temp dir and rename, idempotent re-sync, name validation
  before any write. `--check` fails on a stale or missing lock, tampered copies, same version with different hash and
  a consumer ahead; behind warns (fails with `--strict`).
- Fake-consumer proof (PD-02, PD-10): relative imports of the copied lib stay inside the copy, copied `api.mjs` and
  `vendor/preact-htm.mjs` import under Node, copied skeleton imports as `app.web.admin_ui` and answers the gate.
- `check-admin-ui-rules.py`: rules urls, markup, csp, vendor, selfcontained, publicapi, storage; ntfy's regex tables
  ported unchanged; `--self-test` seeds 16 violations and asserts each fires exactly its own rule.
- Makefile targets and the DEVELOPMENT.md section; `check-all` untouched.

## Verification

- `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q`: 185 passed (all admin-ui tests).
- `test_sync.py` 20 test functions (30 cases), `test_static_rules.py` 11 functions (26 cases).
- `python3 internal/check-admin-ui-rules.py --self-test` and the scan of the real demo tree exit 0.
- `make -n` for the four targets, `ADDON=` and `STRICT=yes` change the command line; prettier and markdownlint pass.

## Deviations

- A consumer whose lib or skeleton copy is missing while the other stamp exists is a FAIL ("missing copy or stamp"); the
  plan did not specify this case.
- `check_part` for the skeleton uses the lib `VERSION` as its stamp version (the skeleton has no VERSION file of its
  own); the lock records one `version` for both.
- The scanner also checks self-containment of a consumer's lib copy (below `vendor/`, otherwise skipped by the scan).
- `admin-ui/lib.lock`, the pre-commit hook and the `check-all` membership are deliberately absent (plan 26-12), so
  `make check-admin-ui-sync` reports "lock missing" until then.

## Commits

- 1feab59 feat(admin-ui): add lib sync script with tree hash, stamps, lock and drift check
- 5d2c066 feat(admin-ui): add static blueprint rules scanner with self-test
- 8481898 feat(admin-ui): add sync and check make targets and development docs
