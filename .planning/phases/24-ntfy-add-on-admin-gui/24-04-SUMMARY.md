---
phase: 24-ntfy-add-on-admin-gui
plan: 04
subsystem: ui
tags: [preact, htm, vendoring, frontend, node-test]
requires: [24-01]
provides:
  - vendored htm 3.1.1 preact bundle with licences, provenance and hash gate
  - lib/model.mjs, lib/api.mjs, lib/ui.mjs and the full app.css
  - static scan for absolute URLs, raw-HTML APIs and dynamic code evaluation
affects: [24-10, 24-11]
actuals:
  tasks: 3
  commits: 3
requirements-completed: [D-16, D-17, D-12, D-13]
completed: 2026-11-02
---

# Phase 24 Plan 04: vendored htm/Preact, frontend lib, CSS, JS tests Summary

## Commits

- `20c6477` feat(ntfy): vendor htm 3.1.1 preact bundle and add static frontend scan
- `6566d00` feat(ntfy): add pure model helpers and relative-URL API client with node tests
- `37c3466` feat(ntfy): add shared UI components, full stylesheet and node test runner

## Verification

- Bundle sha256 equals the pinned `72284e8e...1fd7`, 13194 bytes; both licence files present.
- `node --test ntfy/tests/js/*.test.mjs`: 14 passed, 0 failed (model, api, ui).
- `pytest ntfy/tests` (whole directory in this worktree): all green; `test_js.py` + `test_frontend_static.py`: 18 passed.
- `node --check lib/ui.mjs` ok; no line over 120 chars in `lib/*.mjs`; `app.css` has dark mode and no `url(`/`@import`.

## Deviations

1. `node --test ntfy/tests/js/` (directory argument, as in the plan's acceptance criteria) fails on Node 22
   (`Cannot find module .../js`). Use `node --test ntfy/tests/js/*.test.mjs`; `test_js.py` passes the files explicitly.
2. `buildUrl` encodes `! ' ( ) *` additionally, because `encodeURIComponent` leaves `*` unescaped but the plan requires
   `topic=x%2A`.
3. The JSON pre-commit hook reformatted `topic_cases.json` (one key per line, keys sorted); content is unchanged.
4. The static scan also covers the 24-01 files (`app.mjs`, `index.html`, `app.css`) and passes on them.
5. Executed inline in the worktree (no gsd-executor). STATE.md, ROADMAP.md, state.json untouched.

## Open points for later waves

- `ui.mjs` is only import/export tested under node (no DOM); component behaviour needs a browser check in 24-10/24-11.
- `matchTopic` parity with Python `topic_match` is covered on one side only: 24-11 must load `topic_cases.json` in pytest.
- `app.mjs` and `index.html` from the tracer are untouched; 24-10 replaces them with the preact views.
- `icon.png` is still missing (see 24-01 open points).
