---
phase: 27-ntfy-admin-ui-lib-migration
plan: 04
subsystem: ntfy admin GUI (management views)
tags: [admin-ui, preact, i18n, node-tests, secrets-handling]
requires: [27-01]
provides:
  - health, tools, tokens and data views on the vendored admin-ui lib (0.5.0)
  - de/en strings under health., tools., tokens., data. (strings/manage.{de,en}.mjs)
  - 32 view tests in views_manage.test.mjs (health 7, tools 6, tokens 9, data 8 plus German and audit checks)
affects: [27-05]
tech-stack:
  added: []
  patterns: [literal UPPER_CASE key tables for the i18n scanner, throw-from-onConfirm to keep a dialog open with the localized error]
key-files:
  modified:
    - ntfy/app/web/static/views/health.mjs
    - ntfy/app/web/static/views/tools.mjs
    - ntfy/app/web/static/views/tokens.mjs
    - ntfy/app/web/static/views/data.mjs
    - ntfy/app/web/static/strings/manage.de.mjs
    - ntfy/app/web/static/strings/manage.en.mjs
    - ntfy/tests/js/views_manage.test.mjs
decisions:
  - "Test publish: success only when the response has ok true; ok false (429, 0, other) toasts a localized failure and shows the status"
  - "Dialog actions (revoke, resets, publish) throw from onConfirm so the lib ConfirmDialog stays open and shows the localized code"
  - "Reset titles and texts are three literal tables (RESET_TITLES, RESET_TEXTS) instead of a list with titleKey fields, because tt(item.titleKey) is a dynamic key for the i18n scanner"
status: complete
metrics:
  duration: ~2h incl. one crash/resume (disk full)
  completed: 2026-11-03
actuals:
  tokens: 22000
  tasks: 3
  commits: 3
plan_head_before: 2d83232bb53cce67395d3a45e402c089a7a3e27f
plan_head_after: 8c07d3c87b24d146b56fe0a5ab6a471e05cd0b09
---

# Phase 27 Plan 04: health, tools, tokens and data on the admin-ui lib Summary

The four management views now import only the vendored lib modules, `components.mjs` and `lib/model.mjs`, render every
text through `tt`/`tp` with de/en keys, build download links with `apiHref`, and keep the Phase 24 guards (hidden token
values, typed reset phrases, confirmed test publish). The test publish now reports `ok:false` as a failure.

`actuals.tokens` is chars/4 over the diff of the seven files (about 89 KB of diff text); `commits: 3` is measured with
`git rev-list --count 2d83232..HEAD` before this SUMMARY commit.

## Tasks

| Task | Commit | Result |
| ---- | ------ | ------ |
| 1 health and tools | 711c258 | status card with formatBytes/plural counts, guarded publish with the real outcome, effective-rights lookup via `effectiveExplain` + literal table, generator with structured per-user result lines |
| 2 tokens | 7d405a5 | Row-local reveal state, labelled CopyField, create dialog with presets and validation, danger revoke, ExpiryText/TimeStamp/OriginBadge |
| 3 data | 8c07d3c | export and backup links via `apiHref`, Intl dates and sizes, reason table, three typed-phrase resets with plural-aware toast counts |

## Verification

- `node --test ntfy/tests/js/*.test.mjs`: 80 tests, 80 pass, 0 fail (includes plan 27-03 files as of this base).
  `views_manage.test.mjs` plus `i18n.test.mjs`: 39 pass.
- `make check-admin-ui-rules` OK, `make check-admin-ui-sync` OK (lib 0.5.0, skeleton 0.5.0).
- `pytest ntfy/tests/test_registry.py`: 9 passed; whole `ntfy/tests`: 350 passed.
- Acceptance: meta titleKeys print `view.health`, `view.tools`, `view.tokens`, `view.data`; `effectiveExplain` used in
  tools.mjs; `apiHref` used in data.mjs (4 occurrences); a test asserts no `tk_` + 29 characters in text or input values
  before Reveal and after Hide; the exact-phrase test checks wrong, differently-cased and exact phrases and the posted
  `{confirm}` body.
- `git status` clean outside the seven owned files; nothing under `vendor/`, `admin_ui/`, `admin-ui/`, no STATE.md,
  ROADMAP.md or state.json edits.

## Deviations from Plan

1. **[Environment] Worktree base.** The isolation worktree started at 29e6587 (before plan 27-01). Fast-forwarded
   (`--ff-only`) to 2d83232 as instructed, then worked from there. A disk-full crash interrupted the first session after
   the strings, health and tools files were written but before any commit; the files were intact and kept.
2. **[Lib version] 0.5.0 instead of 0.4.0** (as in 27-01). No API difference affected these views.
3. **[Rule 3] a11y helper import.** `auditNames`/`auditTables` are imported from `admin-ui/tests/js/a11y_audit.mjs`
   because `ntfy/tests/js/a11y_audit.mjs` belongs to plan 27-05 (not in this plan's files). 27-05 can repoint the import
   to its local copy.
4. **[Plan wording] Reset list.** `RESETS` as a list of `{kind, titleKey, textKey}` would need `tt(item.titleKey)`, a
   dynamic key rejected by `i18n.test.mjs`; three literal tables are used instead.
5. **[Bug fix by design] Test publish** now reports failure for `ok:false` (429 rate limit, 0 unreachable, other status);
   the old view always toasted success. No API shape change.
6. **Size text** is now lib output (`2 KiB`, `1 MiB`), as the plan prescribed; old assertions ported.
7. Tests were written together with the views in one pass rather than strictly red first (the old tests were the
   baseline); each behavior in the plan has an assertion.
8. `download=""` instead of a bare `download` attribute on the export and backup links, so the browser does not receive
   the string `true` as a suggested file name via the DOM property.

## Notes for later plans

- Dialog errors inside `ConfirmDialog` use the lib `ErrorNote`, so the ntfy extra hint line (`ERROR_HINTS`) is not shown
  inside dialogs; the code text itself is localized.
- `lib/model.mjs` still exports `fmtBytes`, `fmtUnix`, `fmtExpiry`, `relTime`, `describeEffective`, `protectionLabel`;
  none of my views use them any more (27-05 can drop them together with `lib/ui.mjs` and `lib/api.mjs`).
- Token values: kept only in `Row` state and in the creation dialog; toasts and errors never contain a value
  (tested).

## Known Stubs

None.

## Threat Flags

None. No new endpoints or trust boundaries; all URLs are relative, all values are text nodes.

## Self-Check: PASSED

- Files found: views health/tools/tokens/data, strings manage.{de,en}.mjs, views_manage.test.mjs.
- Commits found: 711c258, 7d405a5, 8c07d3c (ancestors of HEAD).
