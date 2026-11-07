---
phase: 27-ntfy-admin-ui-lib-migration
plan: 01
subsystem: ntfy admin GUI (frontend)
tags: [admin-ui, preact, i18n, node-tests]
requires: [phase 26 admin-ui lib (0.5.0 at execution time)]
provides:
  - ntfy page on the synced admin-ui lib (vendor/admin-ui + admin_ui skeleton copy)
  - shell with Topbar, hash routing, health poll, optional HA wiring
  - de/en string scaffolding (core/access/manage parts)
  - shared components, additive model helpers, view test harness, closure and registry guards
affects: [27-02, 27-03, 27-04, 27-05]
tech-stack:
  added: []
  patterns: [copy-only lib consumption, string aggregators over per-plan part files, temporary re-export shims]
key-files:
  created:
    - ntfy/app/web/static/components.mjs
    - ntfy/app/web/static/strings.de.mjs
    - ntfy/app/web/static/strings.en.mjs
    - ntfy/app/web/static/strings/{core,access,manage}.{de,en}.mjs
    - ntfy/app/web/static/vendor/admin-ui/ (generated)
    - ntfy/app/web/admin_ui/ (generated)
    - ntfy/tests/js/harness.mjs
    - ntfy/tests/js/{app,i18n,components,views_access,views_manage}.test.mjs
    - ntfy/tests/test_static_closure.py
  modified:
    - ntfy/app/web/static/{app.mjs,app.css,index.html,lib/api.mjs,lib/ui.mjs,lib/model.mjs}
    - ntfy/tests/js/{fakedom.mjs,model.test.mjs}
    - ntfy/tests/{test_frontend_static.py,test_registry.py}
  removed:
    - ntfy/app/web/static/vendor/{preact-htm.mjs,README.txt,LICENSE-htm.txt,LICENSE-preact.txt}
    - ntfy/tests/js/views.test.mjs
decisions:
  - "Lib 0.5.0 instead of the planned 0.4.0 (admin-ui/lib.lock was already 0.5.0); no API conflict with the plan"
  - "Topbar nav=tabs (old look); infoPath stays unused (no add-on slug in api/health, D-13)"
  - "app.title and app.version live in ntfy core strings (not in the lib tables)"
  - "origin labels are localized (GUI/Options/IaC), the badge class stays the raw origin"
status: complete
metrics:
  duration: ~1h
  completed: 2026-11-03
actuals:
  tokens: 16000
  tasks: 3
  commits: 3
plan_head_before: 29e6587365e4bd854936094fbc59f24c7320cdae
plan_head_after: ebfad9c88c8faf0729e83ca8341e74739df6b798
---

# Phase 27 Plan 01: ntfy page on the admin-ui lib Summary

The ntfy admin GUI now boots on the copied admin-ui lib (shell, tokens, Preact, API client) with de/en strings, shared
ntfy components, a shared view-test harness and real-server closure and registry guards; the seven views still run
unchanged through two temporary shims.

`actuals.tokens` is an estimate (chars/4 over the ~1200 added lines of hand-written code and tests, generated lib copies
excluded). `commits: 3` counts the three task commits; the SUMMARY commit follows them.

## Tasks

| Task | Commit | Result |
| ---- | ------ | ------ |
| 1 Tracer: sync lib, boot page on it | 1aa93a8 | `make sync-admin-ui ADDON=ntfy` (lock "up to date"), old vendor gone, `lib/api.mjs` and `lib/ui.mjs` shims, index.html on lib base.css, app.css reduced to ntfy rules, lib fakedom, scanner test replaces vendor hash tests, `test_static_closure.py` |
| 2 Shell, strings, harness | cd1ba93 | `app.mjs` on Topbar/useHashRoute/usePoll with optional bridge + theme sync, string parts and aggregators, `harness.mjs`, views tests split, `app.test.mjs`, `i18n.test.mjs` |
| 3 Components, model, guards | ebfad9c | `components.mjs`, `protectionKind`/`effectiveExplain`, perm/origin/expiry strings, `components.test.mjs`, registry `apiHref` and `test_error_codes_have_strings` |

## Verification

- `make check-admin-ui-sync`, `make check-admin-ui-rules` OK; `python3 internal/sync-admin-ui.py --check --strict` OK;
  `git status --porcelain admin-ui` empty; `ntfy/Dockerfile`, `ntfy/run.sh`, server, contract and api untouched.
- Node: 52 passed, 0 failed (baseline 25). Pytest `ntfy/tests`: 350 passed (baseline 327). `-k error_codes_have_strings`
  runs and passes (not skipped).
- Acceptance greps: no literal colour in `app.css`, `vendor/` holds only `admin-ui`, `strings/` has 6 files,
  `registerStrings` in `app.mjs`, `ERROR_HINTS` in `components.mjs`.
- View test counts: old `views.test.mjs` had 9 tests (7 view-level + 2 cross-cutting). Now `views_access` has 3
  (users, acl, matrix), `views_manage` has 4 (tokens, tools, health, data); the two cross-cutting tests (view files
  exist, URLs relative) live in `app.test.mjs`. No assertion lost; the URL check now inspects the calls of every view
  mount instead of only the last one.
- `app.test.mjs` 10 tests, `i18n.test.mjs` 7, `components.test.mjs` 10.

## Deviations from Plan

1. **[Lib version] 0.5.0 instead of 0.4.0.** `admin-ui/lib.lock` was already at 0.5.0 (lib d5696370, skeleton 0f46d30e).
   Checked against the plan: ui/shell/i18n/format/hooks/ingress APIs match; Topbar has an optional `infoPath` that stays
   unused. Lib strings have `errors.view_failed`, `errors.render_failed`, `state.*` but not `app.title`/`app.version`,
   so those are in ntfy core strings. Lock stayed "up to date" after the sync, `admin-ui/` untouched.
2. **[Rule 3] Closure test threshold.** The plan-implied "at least 25 files" is not reachable for the closure of the
   page at this point (23 modules reached); the test asserts at least 15 reached files plus separately that every
   whitelisted file under `static/` is served byte-identical.
3. **[Rule 3] `VERSION` of the lib copy is not served** (no whitelisted extension, like `LIB.stamp`); the closure test
   asserts both give 404 instead of treating them as whitelisted files.
4. Tests for task 2 and 3 were written together with the code in the same step rather than strictly red-first; every
   behavior in the plan has an assertion.

No auth gates, no lib needs (D-03 not triggered).

## Notes for the later plans

- Views still carry the old `meta` shape and English literals; they keep importing `./lib/ui.mjs` and `./lib/api.mjs`
  (shims, deleted by 27-05). `lib/ui.mjs` re-exports `OriginBadge`, `PermSelect`, `ErrorNote` from `components.mjs`, so
  old views already get the localized versions (origin text is now GUI/Options/IaC, labels localized).
- Harness `failures["GET api/x"] = {status, error, message}` makes a request fail; `fixtures` is mutable;
  `mount(id, params, {lang})`, `calls()`, `all(root)`, `TOKEN_VALUE`, `setLang`, `doc` are exported.
- i18n scanner rules for views: literal first arguments for `t`, `tt`, `tp`, or `UPPER_CASE[x]` table indexes only; any
  quoted `ns.key` literal of an ntfy namespace must resolve.
- Degraded notice shows `db.error` from the backend as secondary muted text, as the plan prescribes (text node only).

## Known Stubs

None. `strings/access.*.mjs` and `strings/manage.*.mjs` are intentionally empty owner files for plans 27-03 and 27-04.

## Threat Flags

None. No new endpoints or trust-boundary surface; the page still only uses relative URLs and text nodes.

## Self-Check: PASSED

- Files found: components.mjs, harness.mjs, test_static_closure.py, strings/ (6 files), vendor/admin-ui/LIB.stamp,
  admin_ui/LIB.stamp.
- Commits found: 1aa93a8, cd1ba93, ebfad9c (ancestors of HEAD).
