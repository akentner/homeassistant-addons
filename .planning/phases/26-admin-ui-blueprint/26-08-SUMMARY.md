---
phase: 26-admin-ui-blueprint
plan: 08
subsystem: ui
tags: [preact, a11y, i18n, focus-management, node-test]
requires:
  - phase: 26-01
    provides: vendored Preact, fakedom, frozen shared contract
  - phase: 26-04
    provides: i18n, hooks, string tables
  - phase: 26-05
    provides: bridge store shape (consumed as a prop)
provides:
  - lib/a11y.mjs (tabbables, nextTabTarget, useUid)
  - lib/ui.mjs complete component set (Toast, Modal, ConfirmDialog, Badge, ErrorNote, Loading, CopyField, Tabs, DataTable, Field)
  - lib/shell.mjs (Topbar, LangSwitch, TabNav, ErrorBoundary, parseHash, useHashRoute)
  - fakedom focus support and tests/js/a11y_audit.mjs (auditNames, auditTables)
affects: [26-10, 26-11]
actuals:
  tasks: 3
  commits: 3
key-files:
  created:
    - admin-ui/app/web/static/lib/a11y.mjs
    - admin-ui/app/web/static/lib/shell.mjs
    - admin-ui/tests/js/a11y_audit.mjs
    - admin-ui/tests/js/a11y.test.mjs
    - admin-ui/tests/js/ui.test.mjs
    - admin-ui/tests/js/shell.test.mjs
  modified:
    - admin-ui/app/web/static/lib/ui.mjs
    - admin-ui/tests/js/fakedom.mjs
status: complete
---

# Phase 26 Plan 08: Components, shell and a11y tests Summary

**The lib now ships the full i18n-aware component and shell layer; dialogs trap and restore focus, every control has an
accessible name, and the audit helper proves it over rendered trees.**

## Task Commits

1. **Task 1: fake-DOM focus support, a11y helpers, audit helper** - `7244bd3`
2. **Task 2: ui.mjs components** - `f476fca`
3. **Task 3: shell.mjs** - `59f3407`

## Verification Results

- `node --test admin-ui/tests/js/*.test.mjs`: 166 pass, 0 fail (a11y 18, ui 39, shell 19 tests)
- `pytest admin-ui/tests -q`: 228 passed
- `python3 internal/check-admin-ui-rules.py`: exit 0

## Deviations from Plan

- fakedom `dispatch` records `defaultPrevented` and bubbles only on request (`{bubbles: true}`); default behaviour is
  unchanged. Removing the focused node resets `document.activeElement`, and `focus()`/`blur()` fire focus/blur events.
- `auditNames` additionally accepts a wrapping `<label>` and the `value` of button-type inputs as names.
- `ErrorBoundary` passes `reset` as `onRetry`, so the note offers a retry button (not required by the plan).
- CopyField fallback: `copy.selected` (kind ok when `execCommand` copied, else info), `copy.manual` when select throws.
- i18n used-key scan only inspects `t(`/`tp(`; components use `useT()` as `tt(...)`, so their keys are covered by the
  render tests (no `[key]` markers in de/en) rather than by the scan.

## Open Points

- `base.css` has no styling for `.tab` buttons inside `Tabs` beyond the shared `.tab`/`.tablist` rules (not in this
  plan's files); check visually in the demo (plan 26-10).
