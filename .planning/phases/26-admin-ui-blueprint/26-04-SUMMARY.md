---
phase: 26-admin-ui-blueprint
plan: 04
subsystem: ui
tags: [i18n, intl, hooks, preact, node-test]
requires:
  - phase: 26-01
    provides: lib/api.mjs, vendored Preact, fakedom test double
provides:
  - lib/hooks.mjs (useAsync, usePoll), lib/ingress.mjs (isEmbedded, assertRelative, apiHref, errorKey)
  - lib/format.mjs (Intl formatters for de/en)
  - lib/i18n.mjs with strings.de/en base tables (contract C5)
  - node tests incl. de/en parity and used-key scans over every strings pair under static/
affects: [26-08, 26-10, 26-11]
actuals:
  tasks: 3
  commits: 4
key-files:
  created:
    - admin-ui/app/web/static/lib/hooks.mjs
    - admin-ui/app/web/static/lib/ingress.mjs
    - admin-ui/app/web/static/lib/format.mjs
    - admin-ui/app/web/static/lib/i18n.mjs
    - admin-ui/app/web/static/lib/strings.de.mjs
    - admin-ui/app/web/static/lib/strings.en.mjs
    - admin-ui/tests/js/api.test.mjs
    - admin-ui/tests/js/hooks_ingress.test.mjs
    - admin-ui/tests/js/format.test.mjs
    - admin-ui/tests/js/i18n.test.mjs
status: complete
---

# Phase 26 Plan 04: Hooks, Formatters and i18n Summary

The framework-free core of the browser lib: hooks, ingress helpers, Intl formatting and de/en i18n, with tests that make
a missing translation or a dynamic key a red build.

## Task Commits

1. **Task 1: hooks, ingress helpers, ported API tests** - `91f1f1f`
2. **Task 2: Intl formatters** - `16a9c5b`
3. **Task 3: i18n mechanics, string tables, parity tests** - `3de84d5` (feat)

## Verification Results

- `node --test` over api, hooks_ingress, format, i18n and tracer: 41 pass, 0 fail
- `i18n.test.mjs` also passes with `LANG=de_DE.UTF-8` (16 pass)
- `pytest admin-ui/tests -q`: 86 passed (includes the node suite wrapper)
- `api.test.mjs` is byte-identical to ntfy's (its import path was already correct)

## Deviations from Plan

- `usePoll` skips a tick only when `document.visibilityState === "hidden"` (instead of requiring `"visible"`), so
  environments without the property (fake DOM, old WebViews) still poll.
- `isEmbedded` additionally returns false when `win.parent` is missing, so the fake DOM window counts as top-level.
- The "english fallback when de lacks a key" branch of `t()` has no dedicated test: `registerStrings` forbids one-sided
  keys by design, so no seam exists to create that state. The marker path is tested.
- Format tests assert exact strings after whitespace normalisation; they were green on Node 22.23.

## Open Points

None.
