---
phase: 27-ntfy-admin-ui-lib-migration
plan: 03
subsystem: ntfy admin GUI (access views)
tags: [admin-ui, preact, i18n, a11y, node-tests]
requires: [27-01]
provides:
  - users, ACL and matrix views on the admin-ui lib (lib components, lib API client, de/en strings)
  - keyboard-operable matrix cells, labelled forms, sr-only captions, th scopes
  - 26 view tests (users 11, acl 8, matrix 8 incl. a11y audit, hostile text, error mapping, de/en)
affects: [27-05]
tech-stack:
  added: []
  patterns: [literal key tables (ROLE_KEYS, PROTECT_KEYS), tp plural pairs, ConfirmDialog rethrow for in-dialog errors]
key-files:
  modified:
    - ntfy/app/web/static/views/users.mjs
    - ntfy/app/web/static/views/acl.mjs
    - ntfy/app/web/static/views/matrix.mjs
    - ntfy/app/web/static/strings/access.en.mjs
    - ntfy/app/web/static/strings/access.de.mjs
    - ntfy/tests/js/views_access.test.mjs
decisions:
  - "Lib 0.5.0 instead of the planned 0.4.0; no API conflict"
  - "Rule delete keeps a plain danger confirmation (D-13); user delete keeps type-to-confirm with the confirm field"
  - "Per-row action buttons carry parameterised aria-labels naming the user (visible text unchanged)"
status: complete
metrics:
  completed: 2026-11-03
actuals:
  tokens: 21000
  tasks: 3
  commits: 3
plan_head_before: 2d83232bb53cce67395d3a45e402c089a7a3e27f
plan_head_after: c2935b6966dd472a847170c211d87629fdd06ae8
---

# Phase 27 Plan 03: users, ACL and matrix on the admin-ui lib Summary

The three access views now import only the vendored lib public modules, `components.mjs` and `lib/model.mjs`; every
text and aria label goes through `tt`/`tp` with identical de/en keys; API errors show as the lib's `errors.<code>` text.

`actuals.tokens` is an estimate (chars/4 over the hand-written views, strings and tests). `commits: 3` counts the three
task commits; the SUMMARY commit follows them.

## Tasks

| Task | Commit | Result |
| ---- | ------ | ------ |
| 1 users view | bc576dd | list/add/password/role/delete/detail on lib; `dropped_rules` read as integer (toast via `tp`); delete needs the typed name and sends `{confirm}`; promote with rules asks first |
| 2 ACL view | ce58e77 | labelled add form with local validation, filter field, uniquely named per-row PermSelect, plain danger delete confirmation with errors in the dialog |
| 3 matrix view | c2935b6 | `button.cell-btn` cells with aria-label, editor Modal with named PermSelect, tools link only for concrete topics, caption and scopes |

## Verification

- `node --test ntfy/tests/js/*.test.mjs`: 76 passed, 0 failed. `views_access.test.mjs` has 27 tests (users 11, acl 8,
  matrix 8); with `i18n.test.mjs` (7) the own files give 34 passing.
- `uv run --with pytest --with pyyaml python3 -m pytest ntfy/tests -q`: 350 passed (registry test included).
- `make check-admin-ui-rules` and `make check-admin-ui-sync` OK. `titleKey` of the three views is `view.users`,
  `view.acl`, `view.matrix`. No import of `lib/ui.mjs` or `lib/api.mjs` left in the three views.
- No file outside the six owned ones changed; nothing under `vendor/`, `admin_ui/`, `admin-ui/`.

## Deviations from Plan

1. **[Setup] Worktree base.** The worktree was created at 29e6587 (an ancestor of the intended base); fast-forwarded to
   2d83232 (`git merge --ff-only`) before any work.
2. **[Lib version] 0.5.0 instead of 0.4.0** (as noted in 27-01).
3. **Tests import the lib audit helper** from `admin-ui/tests/js/a11y_audit.mjs` (relative path, read only). Plan 27-05
   should keep that import path valid in the CI job (the ntfy frontend job must check out `admin-ui/tests`).
4. **Test order:** the users tests were written first and run, but the acl and matrix tests were written together with the
   views in one step per task (red state not separately captured); every listed behavior has an assertion.
5. **A session crash (disk full) interrupted the run** after the users strings and tests were written but before any
   commit; the partial work was sound and kept.

## Open needs (no blocking lib need, D-03 not triggered)

- `PermSelect` (plan 27-01 file) has no `id` passthrough, so the permission control in the ACL add form and the matrix
  editor is named through `aria-label` next to a visible `<label>` without `for`. Works for assistive tech; an `id`
  prop would allow a proper `Field` association. Not changed here (file owned by 27-01).
- Lib `Field` hint and `ConfirmDialog` need nothing further.

## Known Stubs

None.

## Threat Flags

None. No new endpoints or trust-boundary surface; all backend values are text nodes, mitigations T-27-09/10/11 are
covered by tests (hostile names, typed-name delete with `confirm` body, dropped-rules count in the toast).

## Self-Check: PASSED

- Files found: users.mjs, acl.mjs, matrix.mjs, access.{de,en}.mjs, views_access.test.mjs.
- Commits found: bc576dd, ce58e77, c2935b6 (ancestors of HEAD).
