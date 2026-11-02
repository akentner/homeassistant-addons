---
phase: 24-ntfy-add-on-admin-gui
plan: 11
subsystem: verification
tags: [ntfy, e2e, docker, registry-tests, docs]
requires: [24-02, 24-03, 24-04, 24-05, 24-06, 24-07, 24-08, 24-09, 24-10]
provides:
  - route registry, parity and frontend-API drift tests
  - Docker E2E (17 scenarios, 120 checks) against real ntfy 2.36.0
  - DOCS.md and CHANGELOG.md reconciled with the observed behaviour
actuals:
  tasks: 3
  commits: 6
requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16, D-17, D-18, ROADMAP-SC1, ROADMAP-SC2, ROADMAP-SC3, ROADMAP-SC4, ROADMAP-SC5, ROADMAP-SC6]
completed: 2026-11-02
---

# Phase 24 Plan 11: registry tests, Docker E2E, docs reconciliation Summary

## Commits

- `41da84b` test(ntfy): add route registry, parity and frontend-API drift tests
- `2958f12` fix(ntfy): answer ok:false instead of 500 when the test publish cannot reach ntfy
- `32841f7` fix(ntfy): share origins.json between bootstrap and GUI processes without stale reads or lost writes
- `abf3a65` fix(ntfy): let the scaffold verify check the relative API client instead of the replaced tracer app.mjs
- `ca58789` test(ntfy): add Docker E2E harness against real ntfy
- `a8f5603` docs(ntfy): reconcile DOCS and CHANGELOG with the verified behaviour

## Verification (all green, final state)

- `pytest ntfy/tests`: 327 passed. `node --test ntfy/tests/js/*.test.mjs`: 25 passed, 0 failed.
- `bash internal/verify-ntfy-e2e.sh`: 17 scenario headings, 120 checks, 0 failed, `All ntfy e2e checks passed`.
  48 user/topic pairs (6 principals x 8 topics) agree with real ntfy publish/subscribe status codes, plus 4 equal-length
  tie-break pairs (write-capable first). Containers `ntfy-w4-*`, scratch `/tmp/akentner/ntfy-w4/`; none left over.
- `bash internal/verify-ntfy-scaffold.sh`, `bash internal/verify-ntfy-registration.sh`: pass.
- `make validate-versions`, `make validate-addons`, `validate-addon-config.py ntfy`, `validate-dockerfile-args.sh`,
  shellcheck on run.sh and the three verify scripts, hadolint via docker (repo ignore set), pre-commit (all ntfy files,
  gitleaks and the local hadolint hook skipped): green. No bytecode caches tracked.

## Known items settled

- (a) `publish_test` OSError: fixed (see Deviations), `ok:false, status:0`.
- (b) `reset_everything` against real ntfy: carol gone, admin and baseline back with origin options, passwords from the
  options, two baseline rules back. Works through `apply_options`.
- (c) DOCS.md: bootstrap runs after ntfy start, degraded mode (health page plus `db_unsupported` 503, not "read-only"),
  `iac` reserved and never written, token reveal is POST, backup reasons and rotation across all reasons, reset effects,
  test publish statuses, `baseline_overwrite_passwords` (verified, origin and rule untouched, GUI user untouched).
- (d) Evaluator matches ntfy incl. write DESC tie-break, case-sensitivity, `_` literal, everyone and default access.
- (e) Static `header.topbar` in `index.html` left in place: `app.mjs` removes it at mount, it only shows without
  JavaScript. `/icon` serves a PNG (E2E check).
- (f) CHANGELOG compare/tag links removed; a note says links follow the first tag.
- (g) `topic_cases.json` plus a 99-pair cross product are checked against Python `topic_match` (pytest, via node).

## Deviations

1. **Fix in 24-08 files** (`app/maintenance.py`, `tests/test_maintenance.py`): `publish_test` let `OSError`/`URLError`
   from the real network call become a 500. Now caught: `{"ok": false, "status": 0, "id": null}`, token still removed.
   The old test expecting the raised error became the regression test.
2. **Fix in 24-03 files** (`app/origins.py`, `tests/test_origins.py`), found by E2E scenario 1 (origins of the baseline
   showed `gui` after the first start): bootstrap and the GUI are two processes, the GUI's `OriginStore` loaded
   `origins.json` once and stayed stale, and its next write-through would also have erased the options origins the
   bootstrap had written. The store now reloads when the file changed (inode, mtime, size) and writes under an
   exclusive `flock` on `origins.json.lock`. `test_file_mode_0600` expects that lock file; new two-store regression test.
3. **Fix in a 24-01 file** (`internal/verify-ntfy-scaffold.sh`): it asserted the tracer `app.mjs` contains `api/health`;
   24-10 replaced that file. It now checks that `lib/api.mjs` builds relative `api/` URLs.
4. The E2E script reads `NTFY_E2E_PREFIX` (default `ntfy-e2e`) and `NTFY_E2E_WORK`. The `test_registry` call-site scan
   also treats `buildUrl(...)` links (export, backup download) as GET calls and `reset/${kind}` by its literal prefix.
5. Executed inline. STATE.md, ROADMAP.md and state.json untouched. Nothing pushed or merged.

## Open points

- No browser was available: nothing was rendered. Layout, dialogs, clipboard and `download` anchors inside the ingress
  iframe, and the static `index.html` header flash, are unchecked. Needs a manual pass in the HA sidebar.
- The real HA Supervisor ingress (peer `172.30.32.2`) was not exercised; the E2E simulates it with
  `NTFY_INGRESS_REMOTE=127.0.0.1`.
- `bashio::app.version` still logs two harmless ERROR lines per start outside the Supervisor.
- `origins.json.lock` is a new file in `/data`; HA backups include it (empty, harmless).
- Nothing auto-prunes `origins.json`; orphaned records stay until `origins.prune` is called by someone.
- Release links in CHANGELOG are to be added with the first `ntfy/vX.Y.Z-N` tag.
