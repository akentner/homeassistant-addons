---
quick_id: "260927-p3c"
subsystem: infra
tags: [cups, airprint, uuid, avahi, bash, python]

provides:
  - "compute_stable_printer_uuid() + PRINTER_UUID_NAMESPACE in cups/generate_config.py: deterministic uuid5 per printer name"
  - "build_printer_uuid_fixup_script(): renders /tmp/fixup-printer-uuids.sh, patches only the target printer's own UUID line"
  - "cups/run.sh new boot phase (step 8): stop cupsd, run fixup, restart cupsd, re-poll readiness"
  - "internal/verify-cups-scaffold.sh: empirical proof of UUID stability across a real docker restart, hardened against a pre-fixup-read race"
affects: [cups add-on]

actuals:
  tokens: 6886
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "printers.conf patched only while cupsd is fully stopped (never live-edit + SIGHUP)"
    - "deterministic uuid5(namespace, name) for stable external identity across a non-persisted filesystem"
    - "verifier polls container logs for a literal run.sh readiness line rather than trusting printer-registration settling as proof of an internal sub-phase's completion"

key-files:
  created: []
  modified:
    - cups/generate_config.py
    - cups/run.sh
    - internal/verify-cups-scaffold.sh
    - cups/DOCS.md
    - cups/config.yaml

key-decisions:
  - "UUID fixup patches printers.conf only while cupsd is fully stopped (kill -TERM/wait, patch, restart, re-poll) -- a live edit + SIGHUP reload was rejected per the file's own header warning and apple/cups#2590"
  - "build_printer_registration() now returns (script, registered_names) so the exact validated printer-name list flows into UUID fixup with zero drift"
  - "verify-cups-scaffold.sh's post-restart UUID read is gated on run.sh's own 'cupsd is ready (post-fixup restart)' log line (scoped to lines written after this boot's docker restart), not on lpstat -v/-r settling, which only proves the FIRST pre-fixup cupsd instance is up"

requirements-completed: []

duration: "~35 min"
completed: 2026-09-27
status: complete
---

# Quick Task 260927-p3c: Stable Printer UUID Across Restarts Summary

**Deterministic `uuid.uuid5()`-derived printer UUIDs patched into `printers.conf` via a new stop/patch/restart boot phase, fixing iOS/AirPrint ghost-duplicate printer entries caused by CUPS re-randomizing every printer's UUID on every add-on restart.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-09-27
- **Tasks:** 3/3
- **Files modified:** 5 (cups/generate_config.py, cups/run.sh, internal/verify-cups-scaffold.sh, cups/DOCS.md, cups/config.yaml)

## Accomplishments

- `compute_stable_printer_uuid(name)` derives a deterministic `uuid.uuid5()` value from a fixed, hardcoded namespace UUID + the printer's own `name` — same name always yields the same UUID, on every host, forever.
- `build_printer_registration()` now returns `(script_text, registered_names)`, so `build_printer_uuid_fixup_script()` consumes the exact validated name list with provably zero drift from what actually got registered.
- `build_printer_uuid_fixup_script()` renders `/tmp/fixup-printer-uuids.sh`: an embedded Python program that isolates each `<Printer NAME>...</Printer>` stanza via a non-greedy DOTALL regex and patches only that stanza's own `UUID urn:uuid:...` line — never touching a sibling printer's UUID or any other directive.
- `cups/run.sh` gains a new boot phase (step 8, between printer registration and the log-level step): gracefully stops the already-running `cupsd`, runs the fixup script, starts a fresh `cupsd`, and re-runs the same readiness-polling wait used on first boot. Registration/preset injection are deliberately NOT re-run.
- `internal/verify-cups-scaffold.sh` empirically proves UUID stability across a **real** `docker restart` (not just re-running a script) for both fixture printers, plus no-regression checks that registration and PPD presets survive the restart.
- **Orchestrator-mandated hardening applied to T2 before dispatch:** the plan's original settle check (`lpstat -v testprinter && lpstat -v brlasertest`) only proves the *first* (pre-fixup) `cupsd` instance is up — printer registration happens entirely before the new UUID-fixup phase begins, so that check could read a stale, still-pre-fixup UUID. Replaced/supplemented with a poll for run.sh's own literal `cupsd is ready (post-fixup restart)` log line, scoped to log lines written strictly after this boot's `docker restart` (via a pre-restart log-line-count baseline), so a stale prior-boot occurrence of the same string can never be mistaken for fresh evidence. Only reads/compares UUIDs once that line is observed; times out with a clear failure message otherwise.
- Full empirical Docker run of `internal/verify-cups-scaffold.sh` executed for real (not `bash -n` only): **`ALL CHECKS PASSED`**, including both new UUID-stability assertions (`testprinter` and `brlasertest` UUIDs byte-identical before/after `docker restart`) and the hardened post-fixup-restart log-line gate.
- `cups/DOCS.md`'s Design notes documents the root cause, both rejected approaches (`lpadmin -o printer-uuid=`, live-edit+SIGHUP), and the two-phase-boot mechanism with its accepted boot-time cost.
- `cups` version bumped one subpatch: `0.1.0-9` → `0.1.0-10` via `make update-version ADDON=cups VERSION=0.1.0-10` (explicit full `X.Y.Z-N` string, per repo hard rule).

## Task Commits

Each task was committed atomically:

1. **T1: Core mechanism in `cups/generate_config.py` + `cups/run.sh`** — `349cb15` (feat)
2. **T2: Empirical proof in `internal/verify-cups-scaffold.sh`** — `c206265` (test)
3. **T3: Docs + version bump** — `5aef4da` (docs)

_No TDD tasks in this plan — one commit per task._

## Files Created/Modified

- `cups/generate_config.py` — `import uuid`; `PRINTERS_CONF_PATH`, `PRINTER_UUID_FIXUP_SCRIPT_PATH`, `PRINTER_UUID_NAMESPACE` constants; `compute_stable_printer_uuid()`; `_PRINTER_UUID_FIXUP_PYTHON_TEMPLATE` + `build_printer_uuid_fixup_script()`; `build_printer_registration()` signature change (`-> tuple[str, list[str]]`) + 2 call-site edits (brlaser + generic branches) to track `registered_names`; `main()` wiring to write the fixup script when non-empty; module docstring bullet
- `cups/run.sh` — new boot phase (step 8: stop cupsd, run fixup, restart cupsd, re-poll readiness); steps 8/9 renumbered to 9/10
- `internal/verify-cups-scaffold.sh` — new "printer UUID stability across a real container restart" section: pre-restart UUID capture, real `docker restart`, hardened post-fixup-restart log-line poll (gated on lines written after this boot's restart, not stale prior occurrences), post-fixup UUID comparison, and no-regression checks (registration + presets survive)
- `cups/DOCS.md` — new Design notes paragraph on the two-phase-boot UUID-stability mechanism
- `cups/config.yaml` — version `0.1.0-9` → `0.1.0-10` (via `make update-version`)

## Decisions Made

- **UUID fixup happens only while `cupsd` is fully stopped** — `printers.conf`'s own generated header says verbatim "DO NOT EDIT THIS FILE WHEN CUPSD IS RUNNING", and `apple/cups#2590` documents the corruption/crash risk of a live edit + SIGHUP reload. The stop/patch/restart cycle costs one extra `cupsd` start/stop/readiness-wait per boot — an accepted, documented trade-off.
- **`registered_names` flows from `build_printer_registration()` directly into `build_printer_uuid_fixup_script()`** rather than re-validating `printers[]` independently, guaranteeing no drift between what gets registered and what gets UUID-fixed-up.
- **T2's verification hardened before trusting it** (per explicit orchestrator instruction reviewed before dispatch): the plan's original registration-settle poll is not proof the internal UUID-fixup restart cycle completed, since printer registration happens entirely in the first (pre-fixup) `cupsd` instance's lifetime. Fixed by polling for run.sh's own post-fixup readiness log line instead, scoped to only lines written after this boot's `docker restart`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `make lint`'s prettier hook reformatted `cups/DOCS.md`**
- **Found during:** Task 3 (Docs + version bump verification)
- **Issue:** `make lint` failed on first run because the prettier pre-commit hook auto-modified `cups/DOCS.md` (its own hook contract: exit 1 the first time it reformats a file)
- **Fix:** Re-staged the prettier-modified `cups/DOCS.md` and re-ran `make lint`, which then passed cleanly
- **Files modified:** `cups/DOCS.md` (whitespace/wrapping only, no content change)
- **Verification:** Second `make lint` run: all hooks passed
- **Committed in:** `5aef4da` (Task 3 commit, prettier's reformatting is part of the same commit)

**2. [Orchestrator-mandated, not a self-discovered deviation] T2's UUID-settle check hardened before dispatch**
- **Found during:** Task 2 (empirical verification)
- **Issue:** The PLAN.md's original `REG_SETTLED_AFTER_RESTART` check (`lpstat -v testprinter && lpstat -v brlasertest`) proves printer *registration* succeeded, not that the internal UUID-fixup stop/patch/restart cycle (run.sh step 8) has completed — registration happens entirely before that phase begins, so the check could read a stale, still-pre-fixup UUID and produce a flaky or falsely-failing result for the exact assertion T2 exists to prove
- **Fix:** Replaced the settle check with a poll of container logs for run.sh's own literal `cupsd is ready (post-fixup restart)` line, restricted to lines written after this boot's `docker restart` (via a pre-restart log-line-count baseline) — UUIDs are only read once that line is observed, or the check fails clearly on timeout
- **Files modified:** `internal/verify-cups-scaffold.sh`
- **Verification:** Full Docker run confirmed the hardened gate fires correctly and is not flaky — `ALL CHECKS PASSED` on the only run performed
- **Committed in:** `c206265` (Task 2 commit)

---

**Total deviations:** 2 (1 auto-fixed lint reformat, 1 orchestrator-mandated hardening applied as instructed)
**Impact on plan:** Both were necessary for correctness (hardening) or clean lint state; no scope creep beyond what the dispatch prompt explicitly required.

## Issues Encountered

None beyond the two items above. The full empirical Docker verification run (image build + container start + real `docker restart` + hardened post-fixup log-line poll) completed successfully on the first attempt.

## Version / Tag Note

`make update-version ADDON=cups VERSION=0.1.0-10` also created and pushed a git tag `cups/v0.1.0-10` to `origin` as part of its normal (non-`--no-tag`) behavior — this succeeded in this environment (unlike the "may fail, non-fatal" caveat noted in the plan for environments without remote credentials). The tag is a release marker only; it does not trigger an image build (per this repo's `.github/RELEASE.md` convention — builds come from `build.yml`, `internal/dispatch-builds.sh`, or an explicit `workflow_dispatch`).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The `cups` add-on's printer UUIDs are now stable across restarts; this is a self-contained, verified fix requiring no follow-on plan.
- Real-host verification (deploying this build to `haos-op3050-1` and confirming the "ghost duplicate printer" symptom no longer recurs across a real HA Supervisor restart) is out of scope for this quick task per its own "Out of Scope" section — deployment happens separately, later.

---

_Quick task: 260927-p3c-cups-stable-printer-uuid-across-restarts_
_Completed: 2026-09-27_
