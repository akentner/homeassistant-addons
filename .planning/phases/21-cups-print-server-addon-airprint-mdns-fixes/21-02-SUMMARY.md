---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 02
subsystem: infra
tags: [cups, avahi, mdns, airprint, home-assistant-addon, docs, base-image-tracking]

requires:
  - "cups/ add-on scaffold (config.yaml, build.yaml, Dockerfile, run.sh, generate_config.py) from Plan 21-01"
provides:
  - "internal/base-image-config.yaml cups: entry — daily base-image-update.yml tracking (D-06)"
  - "cups/README.md + cups/DOCS.md — full D-05 options documentation + D-07/D-08 design rationale"
  - "Root README.md cups entry in the repo's Add-ons list"
affects: [21-03-rollout]

actuals:
  tokens: 2400
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "internal/base-image-config.yaml entry, not .upstream.yaml, for add-ons with no external upstream project (apk-only base-image tracking)"
    - "cups/README.md + cups/DOCS.md mirror gatus/README.md + gatus/DOCS.md's section shapes (badges/About/Features/Configuration, options table)"

key-files:
  created:
    - cups/README.md
    - cups/DOCS.md
  modified:
    - internal/base-image-config.yaml
    - README.md

key-decisions:
  - "cups: entry in internal/base-image-config.yaml is byte-identical to gatus/meridian/network-tools (amd64-base + home-assistant/docker-base + alpine/Dockerfile + ALPINE_VERSION pattern) — no cups/.upstream.yaml exists anywhere in the tree (D-06)"
  - "cups/README.md and cups/DOCS.md stay English (matching gatus/meridian), not German (network-tools' precedent) — DIAGNOSIS.md and 21-CONTEXT.md are both English"
  - "cups/DOCS.md's 'Migrating from f1c878cb_cups' section is a placeholder heading only — Plan 21-03 owns the real migration procedure"

requirements-completed: [D-06, D-08]

coverage:
  - id: D1
    description: "internal/base-image-config.yaml tracks cups via the same amd64-base + home-assistant/docker-base pattern as gatus/meridian/network-tools, with no cups/.upstream.yaml and no workflow file edits"
    requirement: "D-06"
    verification:
      - kind: other
        ref: "python3 -c \"import yaml; ...\" assertion (Task 1 verify) + test ! -f cups/.upstream.yaml"
        status: pass
    human_judgment: false
  - id: D2
    description: "cups/README.md and cups/DOCS.md document every D-05 option with default + purpose, including the D-07 avahi_reflector rationale and the D-08 no-watchdog design note"
    requirement: "D-05, D-07, D-08, D-10, D-11"
    verification:
      - kind: other
        ref: "grep -c assertions for avahi_reflector/avahi_hostname/avahi_use_ipv6/printers/log_level + grep -ci for the D-08 rationale sentence + grep -c for the Migrating placeholder heading (Task 2 verify)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Root README.md lists the cups add-on in the repository's Add-ons section alongside every other add-on"
    verification:
      - kind: other
        ref: "grep -c 'CUPS Print Server' README.md (Task 3 verify) + git diff --stat confirming a scoped insertion only"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-09-26
status: complete
---

# Phase 21 Plan 02: Docs + Base-Image Tracking Summary

**cups add-on is now tracked by the daily base-image-update.yml workflow via internal/base-image-config.yaml (no .upstream.yaml), fully documented in cups/README.md + cups/DOCS.md across the entire D-05 options surface with the D-07/D-08 design rationale spelled out, and listed in the root README.md's Add-ons section.**

## Performance

- **Duration:** 15 min
- **Tasks:** 3 (all `type="auto"`, no checkpoints)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Added a `cups:` entry to `internal/base-image-config.yaml`'s `addons:` map, byte-identical (apart from the map key)
  to the existing `gatus:`/`meridian:`/`network-tools:` entries — same `amd64-base` image family, same
  `home-assistant/docker-base` source repo/file, same `ALPINE_VERSION` regex. Confirmed no `cups/.upstream.yaml`
  exists (D-06: CUPS/Avahi ship as apk packages baked into the base image, not a downloadable upstream release
  tarball). No edits to `.github/workflows/base-image-update.yml` were needed — its addon loop already derives its
  list from this YAML map's keys.
- Wrote `cups/README.md` mirroring `gatus/README.md`'s section order (badges, About, Features, Configuration with a
  minimal example, DOCS.md link, shield-link reference block) and `cups/DOCS.md` mirroring `gatus/DOCS.md`'s
  `| Option | Default | Description |` table shape. Every D-05 option (`avahi_reflector`, `avahi_hostname`,
  `avahi_use_ipv6`, `printers`, `log_level`) is documented with its default and purpose. The `printers` sub-table
  documents the `{name, uri, enabled}` schema and the `str` + runtime scheme-allowlist decision from 21-01 (with
  example URIs across `ipp://`, `socket://`, `usb://`). A `## Design notes` section spells out D-08 (no
  slot-exhaustion watchdog, by design, since `avahi_reflector: false` makes the failure class structurally
  impossible) and carries forward 21-01's Deviation #2 rationale (generic driver vs. driverless IPP-Everywhere,
  so an offline printer still registers). The `## Migrating from f1c878cb_cups` section is left as the placeholder
  heading Plan 21-03 will fill in.
- Inserted a `### [CUPS Print Server](./cups)` entry into the root `README.md`'s `## Add-ons` section, between
  Network Tools and IaC Runner, matching the structure (amd64 shield, italicized tagline, short description,
  `**Features:**` bullet list) of every other add-on entry. `git diff --stat` confirms only this section was
  touched — no other content in `README.md` was altered.

## Task Commits

1. **Task 1: Track cups' base image via internal/base-image-config.yaml (D-06)** - `9e006c2` (feat)
2. **Task 2: Write cups/README.md and cups/DOCS.md (D-05, D-07, D-08, D-10, D-11)** - `cefccb7` (docs)
3. **Task 3: Add cups entry to root README.md's Add-ons list** - `96dfdd1` (docs)

## Files Created/Modified

- `internal/base-image-config.yaml` - added `cups:` entry to the `addons:` map (6 lines)
- `cups/README.md` - new: badges, About, Features, Configuration example, DOCS.md link
- `cups/DOCS.md` - new: full options table, printers sub-table + supported URI schemes, Design notes (D-08 +
  generic-driver rationale), Migrating-from-f1c878cb_cups placeholder
- `README.md` - added a `### [CUPS Print Server](./cups)` entry to the `## Add-ons` section

## Decisions Made

- **`cups:` entry byte-identical to gatus/meridian/network-tools** (Task 1) — no new tracking pattern invented;
  reuses the existing amd64-base Alpine-version-regex mechanism exactly.
- **English, not German, for cups/README.md and cups/DOCS.md** (Task 2) — matches `gatus`/`meridian`'s language
  choice rather than `network-tools`' German precedent, since the source documents this plan drew from
  (`DIAGNOSIS.md`, `21-CONTEXT.md`) are both English.
- **Migrating-from-f1c878cb_cups section left as a placeholder** (Task 2) — explicitly scoped to Plan 21-03 per
  this plan's `<action>` instructions; writing real migration steps here would duplicate/preempt that plan's work.

## Deviations from Plan

### Auto-fixed Issues

None beyond formatting. Both `prettier` pre-commit hook runs (on `cups/README.md`+`cups/DOCS.md`, and again on
`README.md`) reformatted line-wrapping on first commit attempt for each file; the hook's own auto-fix was
re-staged and the commit re-run with no content change (verified via `grep`/`git diff --stat` before and after).
This is standard pre-commit hook behavior, not a plan deviation — no Rule 1-4 applied.

**Total deviations:** 0 (excluding routine prettier reformatting, which changed only whitespace/line-wrap, never
content).

## Issues Encountered

None. All three tasks' automated verify commands passed on the first content attempt (prettier's whitespace-only
reformatting required a second commit attempt per file, which is routine pre-commit hook operation, not an issue).

## User Setup Required

None — this plan produced documentation and a config-tracking entry only, no runtime/functional surface to set up.

## Next Phase Readiness

- Plan 21-03 (rollout to `haos-op3050-1`, replacing `f1c878cb_cups`) can proceed: the add-on is now fully
  documented for an operator, and `internal/cups-migration-suggestion.sh` (Plan 21-03's own artifact) will append
  the real migration procedure to `cups/DOCS.md`'s placeholder section created here.
- No blockers.

---

*Phase: 21-cups-print-server-addon-airprint-mdns-fixes*
*Completed: 2026-09-26*

## Self-Check: PASSED

All files verified present on disk (`cups/README.md`, `cups/DOCS.md`, modified `internal/base-image-config.yaml`,
modified `README.md`); commits `9e006c2`, `cefccb7`, `96dfdd1` found in git history via `git log --oneline`.
