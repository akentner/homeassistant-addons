---
phase: 26-admin-ui-blueprint
plan: 13
subsystem: infra
tags: [spike, ha-iframe, theme, csp, docs]
requires:
  - phase: 26-12
    provides: final tree, lock, smoke script
provides:
  - dated spike log with run A (redacted)
  - DOCS.md spike table with a status for every S item and the Verified on header
  - follow-up list (live spike gaps, bd null, CSP header check, R-07 items)
affects: []
requirements-completed: [D-14]
status: complete-with-gaps
---

# Phase 26 Plan 13: Live spike Summary

**Only run A (desktop panel, HA default dark theme) was done. Evidence-free items are `not-applicable` with follow-ups;
no code or default changed.**

## Result

- Verified (limited): S1, S2, S4, S5, S6, S9 (reservation: CSP header presence unconfirmed), S11 (admin only), S15
  (frontend version missing).
- Not-applicable (not run): S3, S7, S8, S10, S12, S13, S14.
- R-11 and R-13 stay `unverified`; R-07 stays `review` (user decision). Rule statuses in `DOCS.md` and `views/rules.mjs`
  are unchanged and agree.
- No change to the kiosk default, the CSP constant or the origin check: the data does not contradict the design.

## Deviations

- `admin-ui/tests/test_docs.py` is not in `files_modified`: its test that forced every spike row to stay `pending` was
  replaced by one that requires every row to be recorded and the `Verified on: HA core` header. This was required by
  the plan's own acceptance criteria.
- The CHANGELOG bullet went under `[0.1.0-2]` (current version) instead of `[0.1.0-0]`.
- Run B to H were not done and H is optional. The `ha.frontend` field of the result block held the add-on version; it was
  not used as frontend version.

## Verification

- `node --test admin-ui/tests/js/*.test.mjs`: 255 pass, 0 fail
- `pytest admin-ui/tests`: 252 passed
- `make check-admin-ui-sync check-admin-ui-rules`: OK (lock 0.2.1, unchanged)
- `bash internal/verify-admin-ui-scaffold.sh`: all passed (image rebuilt; CSP header present in the image, which is not a
  live HA observation)

## Open points

See the Follow-up section of `admin-ui/DOCS.md`: rerun of the missing spike items, `bd` null, CSP header check in the
network tab, R-07 number formatting and scanner rule.
