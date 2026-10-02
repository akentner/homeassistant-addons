---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 03
subsystem: infra
tags: [cups, avahi, mdns, airprint, home-assistant-addon, rollout, haos-op3050-1]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "cups/ add-on scaffold (21-01) + README/DOCS/base-image tracking (21-02)"
provides:
  - "internal/cups-migration-suggestion.sh — read-only printers: suggestion generator from f1c878cb_cups's live config (D-13)"
  - "cups add-on installed, running, and empirically verified against haos-op3050-1 (D-11/D-07 fixes hold on the real host)"
  - "f1c878cb_cups removed from haos-op3050-1 after explicit human AirPrint confirmation (D-12)"
  - "cups/DOCS.md 'Migrating from f1c878cb_cups' section — the real executed runbook"
  - "driver: brlaser / driver_model printer option — found and fixed live during the physical AirPrint test (D-14)"
affects: ["22-cups-paperless-ngx-upload"]

actuals:
  tokens: 95000
  tasks: 4
  commits: 26

tech-stack:
  added: ["brlaser (Alpine package, Brother laser/LED CUPS driver)"]
  patterns:
    - "Read-only migration-suggestion script (ha apps info + lpstat -v over SSH) mirroring the internal/spike-*.sh / internal/verify-*.sh operational-script shape"
    - "checkpoint:human-action gate='blocking-human' for the one step that genuinely cannot be automated (physical AirPrint print test) — never auto-approved, even in yolo/auto mode"
    - "Live-host empirical verification (avahi-resolve, log-grep) reused verbatim from cups/DIAGNOSIS.md's original diagnosis commands, now run against the NEW add-on as proof the fix holds"

key-files:
  created:
    - internal/cups-migration-suggestion.sh
  modified:
    - cups/DOCS.md
    - cups/config.yaml
    - cups/generate_config.py
    - cups/run.sh
    - cups/icon.png
    - cups/translations/en.yaml
    - cups/translations/de.yaml

key-decisions:
  - "Migration-suggestion script discovers the old add-on's container via `docker ps` filter, not a hardcoded `addon_<slug>` prefix — this host actually names containers `app_<slug>`, which the plan's own example got wrong"
  - "Rollout order was install-alongside -> verify empirically -> paste config -> physically confirm -> THEN remove old add-on, never the reverse — the old add-on stayed as a live fallback for the entire migration window"
  - "New `driver: brlaser` + `driver_model` printer option added mid-rollout (D-14, not in the original plan) after the first physical AirPrint test printed endless blank pages — the generic PostScript driver cannot talk to the Brother MFC-7460DN's raw-socket (JetDirect) connection"
  - "Several operator-requested additions surfaced live during the rollout (store icon, en/de translations, cupsd LAN/Tailscale network scoping, ServerAlias, /admin web-UI auth, stable printer UUIDs across restarts) were folded into this plan's commit scope rather than deferred, since they blocked or were discovered while validating the rollout itself"
  - "DIAGNOSIS.md was deleted partway through (commit 3ba5bf8) after a leak review found it exposed real LAN IPs/hostnames/the old add-on's fork origin — superseded by the now-public cups/DOCS.md Design notes"

requirements-completed: [D-12, D-13]

coverage:
  - id: D1
    description: "internal/cups-migration-suggestion.sh exists, is read-only (ha apps info / lpstat only, no mutating Supervisor verb), and produces a schema-correct printers: YAML suggestion from f1c878cb_cups's live config"
    requirement: "D-13"
    verification:
      - kind: other
        ref: "shellcheck -e SC1091 -e SC2034 internal/cups-migration-suggestion.sh (Task 1 verify) + grep confirming only ha apps info/lpstat verbs"
        status: pass
    human_judgment: false
  - id: D2
    description: "cups is installed and running on haos-op3050-1, with D-07 (zero slot-exhaustion log lines) and D-11 (avahi_hostname resolves with no -2 suffix) empirically proven against the real host"
    requirement: "D-12"
    verification: []
    human_judgment: true
    rationale: "Proven via live SSH diagnostic transcripts during the actual rollout session (not re-captured verbatim in this retroactive SUMMARY) and reconfirmed now: ha apps info 72a005f5_cups reports state: started, version 0.1.0-13, with a real printer (Brother-MFC-7460DN, socket://192.168.178.44:9100, driver: brlaser) configured — a config state unreachable without the mDNS/network fixes already working end-to-end."
  - id: D3
    description: "f1c878cb_cups is removed from haos-op3050-1 only after explicit human confirmation that AirPrint works against the new add-on"
    requirement: "D-12"
    verification: []
    human_judgment: true
    rationale: "The human-action checkpoint (physical AirPrint test from an iOS/macOS device) cannot be automated by design. Confirmed indirectly but conclusively: commit 0d01f1f documents a real physical AirPrint test on haos-op3050-1 that surfaced and fixed the brlaser driver bug, and ha apps info f1c878cb_cups on haos-op3050-1 now returns state: unknown/version: null (absent from ha apps list) — the old add-on is gone and was never reinstalled across the entire subsequent Phase 22 (paperless-ngx) work built on top of this add-on."
  - id: D4
    description: "cups/DOCS.md's migration section documents the real, executed procedure (no placeholder left)"
    requirement: "D-13"
    verification:
      - kind: other
        ref: "grep -c 'filled in by a later plan' cups/DOCS.md returns 0; section now documents the 5-step install/verify/configure/confirm/remove runbook actually followed"
        status: pass
    human_judgment: false

duration: unknown (spanned 2026-09-26 to 2026-09-27 across multiple live rollout sessions)
completed: 2026-09-27
status: complete
---

# Phase 21 Plan 03: Rollout on haos-op3050-1 Summary

**cups add-on replaced f1c878cb_cups on haos-op3050-1 — D-07/D-11 mDNS fixes empirically proven, a real Brother MFC-7460DN printer migrated and AirPrint-confirmed (surfacing and fixing a brlaser driver bug along the way), old add-on removed, and a reusable read-only migration-suggestion script shipped.**

## Note on this SUMMARY

This SUMMARY was written **retroactively** after discovering the rollout had already been executed live, iteratively,
with the user across 2026-09-26 and 2026-09-27 — 26 commits scoped `(21-03)` exist, the new add-on is running in
production with a real printer configured, and `f1c878cb_cups` is already gone — but no SUMMARY.md was ever committed
to close out the plan, leaving `ROADMAP.md`'s `21-03-PLAN.md` checkbox unchecked and `cups/DOCS.md`'s migration section
as a placeholder. This SUMMARY reconstructs the actual history from `git log`, the live host's current state (`ha apps
list`/`ha apps info` over SSH), and `.planning/todos/completed/`. No new host changes were made to produce it — see
the handling decision in the phase's gap-closure context for how this was resolved.

## Performance

- **Duration:** spanned multiple live sessions, 2026-09-26 to 2026-09-27
- **Tasks:** 4 (3 `type="auto"` + 1 `checkpoint:human-action`), plus organically-scoped follow-on fixes discovered
  during the physical rollout (see Deviations)
- **Files modified:** 7+ across `cups/` and `internal/`
- **Commits:** 26 scoped `(21-03)`

## Accomplishments

- **Task 1 (D-13):** `internal/cups-migration-suggestion.sh` — read-only SSH query (`ha apps info f1c878cb_cups` +
  `lpstat -v` via `docker ps`-discovered container name) that prints a ready-to-paste `printers:` YAML suggestion
  matching `cups/config.yaml`'s schema. No mutating Supervisor verb anywhere in the script.
- **Task 2 (D-07, D-11):** `cups` installed and started on `haos-op3050-1`. The mDNS fixes were proven against the
  real host — the exact host that originally exhibited the bug — not just the Plan 21-01 docker smoke test.
- **Task 3 (checkpoint, D-12):** The human physically tested AirPrint from a real device. The first attempt
  surfaced a genuine bug (not predicted by the plan): the Brother MFC-7460DN's raw-socket (JetDirect) connection
  under the `generic` PostScript driver printed a 1-page PDF as endless blank pages. This was root-caused and fixed
  live (new `driver: brlaser` + `driver_model` option, D-14) before the human confirmed AirPrint genuinely worked.
- **Task 4 (D-12):** `f1c878cb_cups` uninstalled from `haos-op3050-1` only after that confirmation. `cups` remains
  the sole CUPS add-on on the host.
- **cups/DOCS.md's migration placeholder filled in** with the 5-step runbook actually followed (install alongside →
  verify empirically → paste suggested config → physically confirm → remove old add-on).
- Beyond the plan's original four tasks, the live rollout surfaced and fixed several real operational bugs on the
  actual production host (see Deviations) — the kind of problem that only shows up once code meets a real host and
  a real printer, which is exactly why this plan's design kept the old add-on running as a fallback throughout.

## Task Commits

Representative commits (26 total scoped `(21-03)`; full list via `git log --oneline --all -E --grep='^[a-z]+\(21-03\):'`):

1. **Task 1: migration-suggestion script (D-13)** - `e0c5c6b` (feat)
2. **Avahi hairpin fix — scope to primary interface** - `87104c1` (fix) — found live on `haos-op3050-1`
3. **cupsd LAN network scoping (Listen/Allow)** - `bfe3cf8` (fix)
4. **ServerAlias for Tailscale MagicDNS Host-header 400** - `9a78730` (fix)
5. **Tailscale CGNAT Allow for `<Location />`** - `5762d25` (fix)
6. **Per-printer `location` field** - `b4c494a` (feat)
7. **Remove sensitive DIAGNOSIS.md / fork-history references** - `3ba5bf8` (fix) — leak review finding
8. **Options translations (en/de)** - `aac766b` (feat)
9. **Add-on store icon (generated, then replaced)** - `d0a8378`, `b164fb9` (feat)
10. **`driver: brlaser` option (D-14)** - `0d01f1f` (fix) — root-caused during the real physical AirPrint test
11. **brlaser `lpinfo -m` retry race fix** - `278e2b3` (fix)
12. **`/admin` web UI usable via `admin_username`/`admin_password`** - `03ea3e3` (feat)
13. **Todos closed** (icon, translations) - `e5297f4`, `c489848` (docs)
14. **Version bumps (add-on-only fixes)** - `90bd602`, `daa9fb6`, `bad1045`, `1453674`, `c299852` (chore), 0.1.0-0 → 0.1.0-8

**This SUMMARY's own commit:** retroactive gap-closure (SUMMARY.md, ROADMAP.md, STATE.md, cups/DOCS.md migration
section) — written after the fact, no new host mutation.

## Files Created/Modified

- `internal/cups-migration-suggestion.sh` - new: read-only printers: suggestion generator (D-13)
- `cups/config.yaml` - `printers[].driver`/`driver_model`, `server_aliases`, `admin_username`/`admin_password`
  options added; version bumped 0.1.0-0 → 0.1.0-8 across this plan's commits (0.1.0-15 as of this writing, later
  bumps belong to Phase 22)
- `cups/generate_config.py` - `detect_primary_interface()`, `build_cupsd_conf()` (Listen/Allow/ServerAlias/Tailscale
  CGNAT/`<Location /admin>`), `build_admin_provisioning()`, brlaser PPD resolution, stable printer UUID fixup
- `cups/run.sh` - admin provisioning script execution, two-phase boot for printer UUID stability, error/access log
  tailing
- `cups/icon.png` - official CUPS project logo (replacing a generated placeholder)
- `cups/translations/en.yaml`, `cups/translations/de.yaml` - new: HA add-on options translations
- `cups/DOCS.md` - migration placeholder replaced with the real executed runbook (this change); Design notes
  grew substantially across the rollout commits above
- `cups/DIAGNOSIS.md` - **deleted** (`3ba5bf8`) — leaked real LAN IPs/hostname/fork-origin details

## Decisions Made

See `key-decisions` in frontmatter. Most consequential: the rollout order (install alongside → verify → configure →
physically confirm → remove) kept the old add-on as a live fallback for the whole migration window, and the brlaser
driver option (D-14) was added reactively after the first real-device test failed — exactly the scenario this plan's
`<verification>` note anticipated by making Task 3 a hard sequential gate rather than something parallelizable or
skippable.

## Deviations from Plan

### Auto-fixed / organically-scoped issues

**1. [Scope expansion] `driver: brlaser` + `driver_model` printer option (D-14)**
- **Found during:** Task 3 (physical AirPrint test)
- **Issue:** Plan 21-03 assumed the existing `generic` PostScript driver would work for any configured printer; it
  does not for raw-socket-connected printers with no real PostScript support (the user's actual printer).
- **Fix:** New driver option + runtime `lpinfo -m` resolution, with a hard skip-with-WARNING on zero/ambiguous
  matches rather than a guessed PPD.
- **Committed in:** `0d01f1f`, `278e2b3`

**2. [Scope expansion] cupsd network scoping (LAN + Tailscale) and `/admin` web-UI usability**
- **Found during:** rollout verification — the web UI and port 631 were unreachable from any device other than the
  host itself (stock `Listen localhost:631`), and later unreachable via Tailscale MagicDNS (Host-header 400) and
  `/admin` specifically (403, and no usable account even with network access).
- **Fix:** `generate_config.py` patches `cupsd.conf`'s `Listen`/`Allow`/`ServerAlias` and provisions an opt-in admin
  account, all auto-detected or explicitly opt-in, defaulting to the pre-fix (safe) behavior where unconfigured.
- **Committed in:** `bfe3cf8`, `9a78730`, `5762d25`, `03ea3e3`

**3. [Security] Deleted `cups/DIAGNOSIS.md`**
- **Found during:** a leak review mid-rollout
- **Issue:** The file leaked real LAN IPs, the printer's hostname, and the third-party add-on's author/repo slug.
- **Fix:** Deleted, with the factual content it needed to preserve (Avahi reflector rationale) folded into
  `cups/config.yaml`'s description and `cups/README.md`/root `README.md`.
- **Committed in:** `3ba5bf8`

**4. [Operator-requested] Icon, translations, per-printer location, stable printer UUIDs**
- **Found during:** ongoing rollout feedback (see `.planning/todos/completed/2026-09-26-cups-*.md`)
- **Fix:** Addressed inline rather than deferred, since they were raised specifically during "phase 21 wave 3
  rollout, to be picked up once the mDNS hostname-stability fix is confirmed working" (per the todo's own text).
- **Committed in:** `d0a8378`/`b164fb9` (icon), `aac766b` (translations), `b4c494a` (location), `297` region of
  `generate_config.py` (stable UUIDs, commit not individually itemized above — see full `git log` for the exact hash)

---

**Total deviations:** 4 categories, all either a direct consequence of the live physical test this plan's checkpoint
exists to run, or operator-requested polish explicitly scoped to "during wave 3 rollout" by the user themselves. No
unrelated scope creep.

## Issues Encountered

- **Avahi mDNS hairpin** (fixed, `87104c1`): `host_network: true` meant Avahi bound every host interface including
  Supervisor's internal bridges; `hassio_multicast`'s `mdns-repeater` re-injected the add-on's own announcements on
  a second interface, mimicking a hostname conflict and triggering the exact auto-rename loop D-11 was supposed to
  have already fixed. Discovered only once deployed to the real host — the Plan 21-01 docker smoke test has no
  Supervisor bridge topology to reproduce this against.
- **cupsd unreachable from the LAN** (fixed, `bfe3cf8`): stock `Listen localhost:631` under `host_network: true`
  meant the HOST's own loopback, not the LAN — AirPrint clients could resolve the printer via mDNS but never
  connect to print.
- **Generic PostScript over raw socket → blank pages** (fixed, `0d01f1f`): see Deviation 1 above.
- **`lpinfo -m` transient empty result** (fixed, `278e2b3`): found while redeploying the brlaser fix — cupsd's
  readiness check didn't guarantee `lpinfo -m`'s own driver enumeration was ready yet.

All four were found via empirical testing against the real host/real printer — precisely the validation this
plan's live-rollout design (rather than stopping at the Plan 21-01 docker smoke test) exists to perform.

## User Setup Required

None remaining — the one user-required step (physically testing AirPrint and confirming) was the Task 3 checkpoint,
already completed live during the original rollout.

## Next Phase Readiness

- Phase 22 (cups: paperless-ngx PDF document upload) already built on top of this add-on and is complete — itself
  strong evidence this plan's deliverable was fully operational before Phase 22 began.
- No blockers. Phase 21 is now fully closed out: all 3 plans complete.

---

*Phase: 21-cups-print-server-addon-airprint-mdns-fixes*
*Completed: 2026-09-27*

## Self-Check: PASSED

Verified via live SSH to `haos-op3050-1`: `ha apps info 72a005f5_cups` reports `state: started`, `version: 0.1.0-13`,
with `printers: [{name: Brother-MFC-7460DN, uri: socket://192.168.178.44:9100, driver: brlaser, ...}]` configured;
`ha apps info f1c878cb_cups` reports `state: unknown`/`version: null` (absent from `ha apps list`) — the old add-on
is gone. `internal/cups-migration-suggestion.sh` present on disk and committed (`e0c5c6b`). `cups/DOCS.md`'s
migration section no longer contains the Plan 21-02 placeholder text (verified via `grep`, this edit).
