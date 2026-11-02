---
phase: 24-ntfy-add-on-admin-gui
plan: 10
subsystem: ui
tags: [preact, htm, frontend, node-test, fake-dom]
requires: [24-04]
provides:
  - GUI shell (hash router, tabs, lazy view loader, health poll) and seven views
  - expiryState and describeEffective helpers in lib/model.mjs
  - fake DOM and mount tests for every view
affects: [24-11]
actuals:
  tasks: 3
  commits: 3
requirements-completed: [D-09, D-11, D-12, D-13, D-14, D-16, D-17]
completed: 2026-11-02
---

# Phase 24 Plan 10: GUI shell and seven views Summary

## Commits

- `f5f0b8b` feat(ntfy): add GUI shell, model helpers, users and ACL views
- `ea08d55` feat(ntfy): add matrix, tokens and tools views
- next: feat(ntfy): add health and data views with fake-DOM mount tests

## Verification

- `node --test ntfy/tests/js/*.test.mjs`: 25 passed (9 mount tests in views.test.mjs).
- `pytest ntfy/tests`: 131 passed (static scan covers all new files).
- `node --check` on app.mjs and all views, prettier 3.1.0 check, no line over 120 chars.
- No browser available: nothing was rendered in a real browser.

## Deviations

1. `index.html` is not in files_modified. The shell renders its own header (icon, badge, add-on version) and removes the
   static `header.topbar` of index.html at mount; `#badge` there is unused now. 24-11 or a later plan may clean it up.
2. Prettier (default embedded-language formatting) reformatted the htm templates; mount tests pass afterwards.
3. `views.test.mjs` ends the worker with `process.exit` 300 ms after the last test: Preact/toast timers otherwise keep
   node alive indefinitely.
4. The per-user token list in the Users detail row shows `expires_at` converted to Unix seconds.

## Open points

- Real-browser check of layout, dialogs, clipboard in the ingress iframe and `download` anchors is still outstanding
  (24-11 / manual).
- `icon.png` is still missing (header hides the image on error).
- Reveal/export/backup links rely on the C10 routes of 24-07/08; only stubbed responses were tested.
- Export download uses a plain anchor with a relative href; the ingress header must be present for it (iframe context).
