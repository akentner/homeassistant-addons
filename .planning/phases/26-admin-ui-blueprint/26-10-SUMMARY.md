---
phase: 26-admin-ui-blueprint
plan: 10
subsystem: demo-gui
tags: [admin-ui, demo, preact, i18n, a11y]
requires:
  - phase: 26-02
    provides: demo API (items, fail, slow)
  - phase: 26-08
    provides: lib components and shell
provides:
  - demo shell (VIEWS, App, loadView, ThemeChip) and four views (gallery, tokens, language, crud)
  - demo strings de/en (app.*, demo.nav.*, demo.health.*, demo.theme.*, demo.gallery.*, demo.tokens.*,
    demo.language.*, demo.crud.*)
  - view tests, whole-demo sweeps and served-files test
affects: [26-11, 26-12]
actuals:
  tasks: 3
  commits: 3
key-files:
  created:
    - admin-ui/app/web/static/views/gallery.mjs
    - admin-ui/app/web/static/views/tokens.mjs
    - admin-ui/app/web/static/views/language.mjs
    - admin-ui/app/web/static/views/crud.mjs
    - admin-ui/tests/js/views.test.mjs
    - admin-ui/tests/test_demo_static.py
  modified:
    - admin-ui/app/web/static/index.html
    - admin-ui/app/web/static/app.mjs
    - admin-ui/app/web/static/app.css
    - admin-ui/app/web/static/strings.de.mjs
    - admin-ui/app/web/static/strings.en.mjs
  deleted:
    - admin-ui/tests/js/tracer.test.mjs
requirements-completed: [D-01, D-02, D-04, D-08, D-09, D-10, D-11, D-13, D-15, D-16, PD-02, PD-05]
status: complete
---

# Phase 26 Plan 10: Demo shell and gallery Summary

**The tracer page is replaced by the real demo: shell with topbar, health badge, theme chip, hash navigation and optional
HA wiring, plus the gallery, token, language and CRUD views, all built from public lib exports only.**

## Task Commits

1. **Task 1: shell, index page, strings scaffold, served-files test** - `d7cebb9`
2. **Task 2: gallery and token views** - `8068db8`
3. **Task 3: language and CRUD views, whole-demo sweeps** - `82f7036`

## Verification

- `node --test admin-ui/tests/js/*.test.mjs`: 196 pass, 0 fail (`views.test.mjs`: 33 tests).
- `pytest admin-ui/tests`: 236 passed (incl. `test_demo_static.py`, `test_tracer.py`, `test_static_rules.py`).
- `python3 internal/check-admin-ui-rules.py`: exit 0 (demo is a clean consumer, no vendor imports).
- Sweeps: every view in `en` and `de` has no unlabeled control, no `th` without scope, no `[key]` marker and only
  relative request URLs; open dialogs (gallery modal/confirm, CRUD edit) keep accessible names.
- Hostile strings (`<b>alice</b>`) stay text in list, edit modal title, confirm message, gallery table and health badge;
  hostile hash `#/../../x` falls back to the gallery.

## Deviations / open points

- **Health badge text is now localized** (`state.ok` -> "OK" instead of the raw status `ok` of the tracer); unknown
  statuses (hostile test) are still shown verbatim as text. The tracer assertions were moved into `views.test.mjs`
  accordingly.
- **`createHaBridge`/`createThemeSync` need an explicit `win`** (the lib does not default it; without it `start()`
  throws). `app.mjs` passes `globalThis.window` lazily in `defaultHa()`. Not a lib change; worth a doc line in 26-12/DOCS.
- **No real-browser check yet.** All view tests run on the fake DOM. Not verified: the CSS-only token swatches, the
  `theme-isolated` panels with live `getComputedStyle` values (tests stub it), layout and focus behaviour. Belongs to the
  Docker verify in 26-12.
- `test_demo_static.py::test_view_modules_exist_once_written` is a weak placeholder check; the real coverage is the
  referenced-files and lib-files tests.
- Not touched: STATE.md, ROADMAP.md, state.json; no push, no merge, Docker verify script not run. Rules and spike views
  are left to plan 26-11.
