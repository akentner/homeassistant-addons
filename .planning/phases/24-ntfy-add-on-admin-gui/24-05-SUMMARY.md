---
phase: 24-ntfy-add-on-admin-gui
plan: 05
subsystem: docs
tags: [ntfy, registration, translations, docs, migration]
requires: [24-01]
provides:
  - root README entry and base-image tracking block for ntfy
  - icon.png, logo.png and the GUI icon copy
  - en/de translations for every option, README, CHANGELOG, DOCS.md with migration guide
  - internal/verify-ntfy-registration.sh (offline completeness gate)
affects: [24-10, 24-11]
actuals:
  tasks: 3
  commits: 3
requirements-completed: [ROADMAP-SC1, D-05, D-06, D-07, D-10, D-11, D-12, D-13, D-14, D-15, D-18]
completed: 2026-11-02
---

# Phase 24 Plan 05: registration, icons, translations, docs Summary

## Commits

- `e041218` feat(ntfy): register add-on in README and base-image tracking, add icon and logo
- `797cc80` docs(ntfy): add translations, README and changelog
- next: docs(ntfy): add DOCS with migration guide and offline registration gate (see `git log`)

## Verification

- `bash internal/verify-ntfy-registration.sh` passes; shellcheck clean.
- `pre-commit run --files` on all touched markdown, yaml and the script: green (hadolint skipped, no Dockerfile).
- `make validate-versions` passes; `pytest ntfy/tests`: 117 passed.
- Icon 128x128 (upstream `ntfy.png`, unchanged), logo 250x100 RGBA (192px PWA icon scaled to 100px, centred), GUI copy
  byte-identical. No line over 120 chars in DOCS.md.

## Deviations

1. Prettier rewraps prose and pads tables; the DOCS option table cells were shortened so rows stay at 120 columns.
2. The verify script reads `host_network` via the yget helper and compares with the string `False` (PyYAML output).
3. The README `[release*]` link lines are unchanged (checked in the diff).
4. DOCS.md links `docs/EXPORT_SCHEMA.md` relative to the add-on directory (file exists from 24-03).

## Open points for later waves

- DOCS.md states the behaviour from the plan's facts list; 24-11 must reconcile it with the running add-on, in
  particular: degraded mode is described as read-only GUI, the bootstrap runs a moment after ntfy start, the `iac`
  origin is only mentioned as "later", token reveal is described as POST.
- CHANGELOG compare links assume the tag format `ntfy/vX.Y.Z-N` (as gatus); no such tag exists yet.
- The GUI header (24-10) can use `./icon`; `static/icon.png` now exists.
