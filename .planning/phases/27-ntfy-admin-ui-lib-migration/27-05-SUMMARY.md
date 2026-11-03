---
phase: 27-ntfy-admin-ui-lib-migration
plan: 05
subsystem: ntfy admin GUI (cleanup, guards, CI)
tags: [admin-ui, node-tests, pytest, ci, zizmor]
requires: [27-02, 27-03, 27-04]
provides:
  - ntfy without any duplicate of the lib (static/lib holds only model.mjs)
  - cross-cutting guards: view sweep (en/de), orphan-key scan, css token, contrast and inline-style rules
  - CI job ntfy in lint.yml (gated by lint-results) and make test-ntfy
affects: [27-07]
tech-stack:
  added: []
  patterns: [verbatim copy of the lib test helper (a11y_audit.mjs), appended CI job with line-anchored zizmor deferrals untouched]
key-files:
  created:
    - ntfy/tests/js/a11y_audit.mjs
    - ntfy/tests/js/sweep.test.mjs
    - ntfy/tests/js/i18n_coverage.test.mjs
    - ntfy/tests/test_frontend_rules.py
  modified:
    - ntfy/app/web/static/lib/model.mjs
    - ntfy/app/web/static/components.mjs
    - ntfy/tests/js/{model,api,components,harness,views_access,views_manage}.test.mjs
    - .github/workflows/lint.yml
    - Makefile
  removed:
    - ntfy/app/web/static/lib/ui.mjs
    - ntfy/app/web/static/lib/api.mjs
    - ntfy/tests/js/ui.test.mjs
decisions:
  - "model.mjs export list is pinned by a node test (15 names); PERMISSION_LABELS and confirmMatches went with the old API"
  - "contrast pairs are read from app.css rules (not hard-coded colours), so a later colour change is tested"
  - "no pair needed a css change: every ntfy-only text pair is at least 4.5:1 in light, dark and the dark media block"
status: complete
metrics:
  duration: ~1h
  completed: 2026-11-03
actuals:
  tokens: 9000
  tasks: 3
  commits: 4
plan_head_before: e074f84647bd2cf143294ca1383f9ea3019c1757
plan_head_after: a8623bd0936359c5aa62f6bb2a914efe3d5282a1
---

# Phase 27 Plan 05: shims removed, guards and CI for ntfy Summary

ntfy no longer carries a copy of the lib (only `lib/model.mjs` remains, with a pinned export list), a sweep over all
seven views in en and de plus orphan-key, contrast and inline-style guards enforce the blueprint rules, and a new CI job
`ntfy` plus `make test-ntfy` run the ntfy suites.

`actuals.tokens` is an estimate (chars/4 over the added test code and edits). `commits: 4` is measured with
`git rev-list --count e074f84..HEAD` before this SUMMARY commit.

## Tasks

| Task | Commit | Result |
| ---- | ------ | ------ |
| 1 shims and old model API | 9045f3e | `lib/ui.mjs`, `lib/api.mjs`, `ui.test.mjs` deleted; model keeps 15 exports (list test); `api.test.mjs` and `harness.mjs` import the vendored lib |
| PermSelect id (follow-up) | 3afe10c | optional `id` prop on the select, two assertions (set and absent) |
| 2 guards | 9eb91a3 | local `a11y_audit.mjs` (cmp identical to admin-ui), `sweep.test.mjs` (25 tests), `i18n_coverage.test.mjs`, `test_frontend_rules.py` (23 tests); view tests repointed to the local helper |
| 3 CI and Makefile | a8623bd | job `ntfy` appended, `lint-results` needs `[lint, admin-ui, ntfy]` with a third verdict clause, `make test-ntfy` |

## Verification

- `node --test ntfy/tests/js/*.test.mjs`: 127 tests, 127 pass, 0 fail (baseline at the start of this plan 100, after
  removing the old formatter, confirm and describer tests and ui.test.mjs).
- `uv run --with pytest --with pyyaml python3 -m pytest ntfy/tests -q`: 386 passed (363 before task 2; +23 rules tests).
- `make check-admin-ui-sync`, `make check-admin-ui-rules` OK; `pre-commit run check-admin-ui-sync` and
  `check-admin-ui-rules --all-files` Passed (existing hook regexes cover ntfy, `.pre-commit-config.yaml` unchanged).
- `uvx zizmor@1.30.1 --offline --config zizmor.yml .github/workflows/lint.yml`: "No findings to report" (5 ignored,
  8 suppressed). YAML assertion: `jobs.ntfy.permissions == {contents: read}`, `lint-results.needs == [lint, admin-ui, ntfy]`.
- `git diff --numstat` on lint.yml before commit: 39 added, 2 deleted (only the `needs:` line and the verdict line).
- `make -n test-ntfy` and `make help | grep -c test-ntfy` print the target (1); `make test-ntfy` green.
- Acceptance: `ls ntfy/app/web/static/lib` prints `model.mjs`; model export list prints the 15 expected names;
  `grep -c vendor/admin-ui/api.mjs ntfy/tests/js/api.test.mjs` is 1; `git status` clean for `admin-ui`,
  `ntfy/app/web/static/vendor`, `ntfy/app/web/admin_ui`.
- Guard sanity: an injected orphan key makes the orphan test fail (checked once, then reverted).

## Deviations from Plan

1. **[Rule 3] Worktree base.** The worktree started at 29e6587 and was fast-forwarded to e074f84 (merge of plan 27-04) as
   instructed.
2. **[Rule 3] Files outside `files_modified`.** `ntfy/tests/js/harness.mjs` imported `lib/ui.mjs` (the shim), so it now
   imports `vendor/admin-ui/ui.mjs` (one line). `views_access.test.mjs` and `views_manage.test.mjs` were repointed from
   `admin-ui/tests/js/a11y_audit.mjs` to the local copy, as requested by the orchestrator. `components.mjs` and
   `components.test.mjs` got the optional `PermSelect` id (follow-up item).
3. **[Plan drift] lint.yml has a third job.** `secrets-sync` (appended by another plan) sits after `admin-ui`. The `ntfy`
   job is appended after it (end of file, as the zizmor line anchors require). Consequence: `pytest==9.1.1` occurs 3
   times (plan expected 2) and `persist-credentials: false` 3 times. `secrets-sync` is not added to `lint-results`
   (outside this plan).
4. **[Plan wording] Dead-helper list.** Besides the listed formatters, `PERMISSION_LABELS` and `confirmMatches` were
   removed too (no importer left; the plan's export list excludes them).
5. **[Env] actionlint is not installed locally**; the repo's pre-commit hook `Lint GitHub Actions workflow files` and the
   zizmor hook ran on the commit and passed.
6. Guards were written test-only as the plan prescribes; the guards passed on first run against the migrated code (no
   css pair needed a change).

## Friction / notes for the admin-ui manager (not requested)

- `a11y_audit.mjs` is now copied verbatim by ntfy; a lib-shipped test-support module would remove the copy.

## Known Stubs

None.

## Threat Flags

None. The only new surface is the CI job (T-27-16): `contents: read`, `persist-credentials: false`, no secrets, no
caches, pinned test tools identical to the admin-ui job, zizmor clean.

## Self-Check: PASSED

- Files found: `ntfy/tests/js/{a11y_audit,sweep.test,i18n_coverage.test}.mjs`, `ntfy/tests/test_frontend_rules.py`;
  `lib/ui.mjs`, `lib/api.mjs`, `tests/js/ui.test.mjs` are gone.
- Commits found: 9045f3e, 3afe10c, 9eb91a3, a8623bd (ancestors of HEAD).
