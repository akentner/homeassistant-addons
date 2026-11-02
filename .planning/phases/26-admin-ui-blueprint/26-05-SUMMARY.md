---
phase: 26-admin-ui-blueprint
plan: 05
subsystem: ui
tags: [ha-theme-sync, postmessage, wcag, kiosk, node-test]
requires:
  - phase: 26-01
    provides: lib directory, fakedom, node test conventions
provides:
  - color.mjs (parseColor, serializeColor, relativeLuminance, contrastRatio, isDarkColor, pickOnColor)
  - theme-sync.mjs (createThemeSync, THEME_WHITELIST)
  - ha-bridge.mjs (createHaBridge)
affects: [26-08, 26-10, 26-11, 26-13]
actuals:
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "Injectable window and timers, no globals at import time"
    - "Only parsed and re-serialised colours reach setProperty"
key-files:
  created:
    - admin-ui/app/web/static/lib/color.mjs
    - admin-ui/app/web/static/lib/theme-sync.mjs
    - admin-ui/app/web/static/lib/ha-bridge.mjs
    - admin-ui/tests/js/color.test.mjs
    - admin-ui/tests/js/theme_sync.test.mjs
    - admin-ui/tests/js/ha_bridge.test.mjs
  modified: []
key-decisions:
  - "theme-sync removes data-theme only if it set it itself, so an app-set theme is never clobbered"
  - "inbound bridge messages are refused when the page origin is opaque (no safe origin to compare)"
  - "configure() clears the sticky host-bar flag and the freeze guard (explicit user action)"
requirements-completed: [D-11, D-12, D-13, D-14, D-16, PD-08, PD-10, PD-11, PD-12]
status: complete
---

# Phase 26 Plan 05: Colour maths, theme sync and HA bridge Summary

**Three standalone, injectable modules: strict colour parsing/WCAG maths, a guarded `--sync-*` theme sync and the
`home-assistant/*` postMessage bridge with a narrow-driven kiosk policy; all degrade to the own theme / fixed layout.**

## Task Commits

1. **Task 1: color.mjs and theme-sync.mjs** - `e5148c1`
2. **Task 2: ha-bridge.mjs** - `afa3c5c`

## Verification Results

- `node --test color.test.mjs theme_sync.test.mjs ha_bridge.test.mjs`: 49 pass, 0 fail
  (color 8, theme_sync 18, ha_bridge 23)
- Modules have no `console.` calls and no imports besides `./color.mjs` (theme-sync); plain Node import succeeds

## Deviations from Plan

None functional. Additions to the injectable options, all optional: `now` (clock) on both stateful modules. Status
additions as announced in the plan: `kioskFrozen` (bridge state), reason `error` (theme-sync). theme-sync also reports
`disposed` after `dispose()` and counts `refresh`/`event` besides `observer`/`poll`/`apply`.

## Known Stubs

None. Live behaviour (A1-A11) is deliberately left to the spike (plan 26-13).

## Threat Flags

None beyond the plan register (T-26-20..T-26-25 mitigated and covered by tests).

## Self-Check: PASSED

STATE.md, ROADMAP.md and state.json untouched; files limited to `files_modified`.
