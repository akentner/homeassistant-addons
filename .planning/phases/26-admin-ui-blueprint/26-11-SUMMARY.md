---
phase: 26-admin-ui-blueprint
plan: 11
subsystem: demo-gui
tags: [admin-ui, demo, rules, spike, redaction]
requires:
  - phase: 26-07
    provides: DOCS.md rules table (R-01..R-15) and spike table (S1..S15)
  - phase: 26-10
    provides: demo shell, VIEWS, view pattern
provides:
  - rules checklist view (RULES, RULES_STORAGE_KEY) with pytest cross-check against DOCS.md and the repository
  - spike view (CHECKS, buildResult, redact) probing S1..S15 with a redacted copy-as-JSON result block
  - strings demo.nav.rules/spike, demo.rules.*, demo.spike.* in de and en
affects: [26-12, 26-13]
actuals:
  tasks: 2
  commits: 2
key-files:
  created:
    - admin-ui/app/web/static/views/rules.mjs
    - admin-ui/app/web/static/views/spike.mjs
    - admin-ui/tests/js/rules_view.test.mjs
    - admin-ui/tests/js/spike_view.test.mjs
    - admin-ui/tests/test_rules_view.py
  modified:
    - admin-ui/app/web/static/app.mjs
    - admin-ui/app/web/static/app.css
    - admin-ui/app/web/static/strings.de.mjs
    - admin-ui/app/web/static/strings.en.mjs
    - admin-ui/tests/js/views.test.mjs
requirements-completed: [D-02, D-11, D-12, D-13, D-14, D-15, D-16, PD-07, PD-08, PD-11, PD-12]
status: complete
---

# Phase 26 Plan 11: Rules checklist and spike view Summary

**The demo now has a rules checklist that cannot drift from DOCS.md and a spike page that probes S1..S15 and emits a
uniform, redacted JSON result for the live run of 26-13.**

## Task Commits

1. **Task 1: rules checklist view and DOCS cross-check** - `df8df37`
2. **Task 2: spike view, probes S1..S15, redacted result block** - `39f5773`

## Verification

- `node --test admin-ui/tests/js/*.test.mjs`: 224 pass, 0 fail (`rules_view` 6, `spike_view` 22).
- `pytest admin-ui/tests`: 240 passed (`test_rules_view.py`: 4).
- `python3 internal/check-admin-ui-rules.py`: exit 0.
- Acceptance greps: R-ids 31 (>=15), storage key 1, spike S-ids 46, `buildResult` 2, `navigate("/config")` 1.

## Deviations / open points

- **Literal i18n keys per rule/policy/path.** R-06 forbids dynamically built keys, so `rules.mjs` and `spike.mjs` use
  literal key maps (`TEXT`, `POLICY_KEYS`, ...) instead of template-string keys.
- **`CHECKS` carries `hintKey` besides `titleKey`** (one instruction text per S-id).
- **S8** has a select (copied / fallback / failed) feeding the result, plus a note field that is deliberately NOT part
  of the result (free text could leak). S7/S8/S10/S11 report `ok: null` / `not_run` until the tester runs them.
- **Redaction is conservative.** `redact` drops any string containing `://`, `Bearer`, a private/Tailscale IPv4, a
  common-TLD hostname or 20+ token characters in a row. Probe details therefore use space-separated short tokens
  (a first version with underscore-joined details was dropped by the redactor; caught by the snapshot test). A custom
  HA group id of 20+ characters would be dropped from `whoami.groups`.
- `generated_at` is date-only so the copy value stays stable between renders.
- S1 reads only `parent.document.documentElement` reachability (as specified), never its content.
- **Not verified:** real browser rendering and the probes against a real HA (fake-DOM tests only); that is 26-12/26-13.
- DOCS.md untouched (rule statuses unchanged); STATE.md, ROADMAP.md, state.json untouched; no push, merge, PR, tag;
  Docker verify script not run.
