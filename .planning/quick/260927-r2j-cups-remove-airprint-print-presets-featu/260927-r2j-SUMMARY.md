---
quick_id: "260927-r2j"
subsystem: infra
tags: [cups, home-assistant-addon, airprint, ppd, config-generation]

# Actuals (#2632) / commit ledger (#3968)
actuals:
  tokens: 6800
  tasks: 3
  commits: 3
plan_head_before: 7a54a5b62115a6d95533dc8c704ab750640d60de
plan_head_after: 065caa2febd61682ba9872f538d28d44c20fe81b

key-files:
  modified:
    - cups/generate_config.py
    - cups/config.yaml
    - internal/verify-cups-scaffold.sh
    - cups/DOCS.md
    - cups/README.md
    - cups/build.yaml

duration: ~20min
completed: 2026-09-27
status: complete
---

# Quick Task 260927-r2j: Remove AirPrint Print-Presets Feature Summary

**Fully removed the `printer_presets` config option, its `*APPrinterPreset` PPD-injection machinery, and every supporting fixture/assertion/doc reference — the feature was confirmed empirically to be inert for iOS/AirPrint (a PPD-only mechanism iOS never reads).**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3/3 completed
- **Files modified:** 5 (generate_config.py, config.yaml, verify-cups-scaffold.sh, DOCS.md, README.md); build.yaml touched by `make update-version` but its `VERSION` value (0.1.0) was already correct (base version unchanged, subpatch-only bump)

## Accomplishments

- `cups/generate_config.py`: deleted the module-docstring paragraph, three regex constants (`PRESET_NAME_RE`, `PRESET_OPTION_TOKEN_RE`, `_PRESET_SLUG_SANITIZE_RE`), and three functions (`slugify_preset_id`, `build_preset_injection_snippet`, `group_presets_by_printer`) — 258 lines removed. `build_printer_registration()` and `main()` no longer reference presets at all. The unrelated stable-printer-UUID feature (`import uuid`, `PRINTER_UUID_NAMESPACE`, `compute_stable_printer_uuid`, `build_printer_uuid_fixup_script`) verified fully intact.
- `cups/config.yaml`: removed the `printer_presets: []` option default and its `schema:` block.
- `internal/verify-cups-scaffold.sh`: removed the `printer_presets` fixture array and the entire "Checking AirPrint preset injection" assertion block (positive, slug-collision, negative, unmatched-FK, and live-on-disk-PPD checks — 121 lines). The restart-survival section's UUID-stability and registration-survival checks were left fully intact; only the two preset-survival sub-checks were removed and the banner text updated.
- `cups/DOCS.md`: removed the `## Printer Presets` section, its `## Add-on Options` table row, and the Design-notes AirPrint-preset paragraph; fixed the stable-UUID design note's prose to no longer mention preset injection.
- `cups/README.md`: removed the `printer_presets` Features bullet.
- Version bumped `0.1.0-11` → `0.1.0-12` via `make update-version ADDON=cups VERSION=0.1.0-12`.
- Full Docker-based `internal/verify-cups-scaffold.sh` run: `ALL CHECKS PASSED`, including printer-UUID-stability-across-restart and registration-survival checks.

## Task Commits

Each task was committed atomically:

1. **T1: Core removal — generate_config.py + config.yaml** - `efbae5d` (feat)
2. **T2: Reshape internal/verify-cups-scaffold.sh** - `da362d0` (test)
3. **T3: Docs, README, and version bump** - `065caa2` (docs)

_Prettier's pre-commit hook reformatted `cups/DOCS.md`'s prose-wrap during T3's commit attempt; the commit was re-run after the auto-fix and passed clean._

## Files Created/Modified

- `cups/generate_config.py` - preset constants/functions/call-sites deleted (258 lines removed); stable-UUID feature untouched
- `cups/config.yaml` - `printer_presets` option + schema removed; version → `0.1.0-12`
- `cups/build.yaml` - touched by `make update-version` (VERSION arg unchanged at `0.1.0`, base version didn't change)
- `internal/verify-cups-scaffold.sh` - fixture + assertion block removed (121 lines); restart-survival section's non-preset checks preserved
- `cups/DOCS.md` - Printer Presets section/table-row/design-note removed; stable-UUID note's prose fixed
- `cups/README.md` - Features bullet removed

## Decisions Made

- None beyond the plan's own scope — pure removal, no replacement mechanism, no migration shim (matches the plan's explicit Out-of-Scope declaration).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Deleted a stray git tag pointing at the wrong commit**
- **Found during:** Task 3 (version bump)
- **Issue:** `make update-version ADDON=cups VERSION=0.1.0-12` created and pushed an annotated tag `cups/v0.1.0-12` to origin *before* the version-bump files were committed — the tag pointed at T2's commit (`da362d0`), whose `cups/config.yaml` still read `version: "0.1.0-11"`. This is the same "tagging the pre-bump commit" class of bug STATE.md records was previously fixed for the automated bump workflows (`quick-260909-rll`), but the plain `make update-version` target (without `NO_TAG=yes`) still exhibits it. Confirmed via `internal/update-version.py`'s own docstring that pushing this tag triggers no build workflow (tags are not a `build.yml` trigger), so no bad image was built — but the tag itself was a real, pushed inconsistency (release marker pointing at the wrong version).
- **Fix:** Deleted the tag locally (`git tag -d`) and from origin (`git push origin :refs/tags/cups/v0.1.0-12`) immediately after discovering the mismatch. After committing T3 (`065caa2`, which contains the actual `0.1.0-12` config.yaml), re-created the annotated tag on the correct commit and pushed it again.
- **Files modified:** none (git ref only)
- **Verification:** `git rev-parse cups/v0.1.0-12^{commit}` now resolves to `065caa2`, whose `cups/config.yaml` reads `version: "0.1.0-12"`.
- **Committed in:** n/a (tag operation, not a file commit) — performed between the T2 and T3 file commits

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** No scope creep — this was a tooling side-effect discovered while following the plan's own explicit version-bump instruction. Left uncorrected it would have published an incorrect release marker on GitHub.

## Issues Encountered

None beyond the tag mismatch documented above.

## Next Phase Readiness

- `cups` add-on is on `0.1.0-12` with `printer_presets` fully removed; three-file version sync intact (`make validate-versions` passes as part of every commit's pre-commit hook).
- Deploying/restarting this add-on on `haos-op3050-1` is explicitly out of scope for this task (per plan) and remains for a later, separate step.
- `cups/run.sh`'s boot-phase comment still mentions "preset injection" in prose only (no code/identifiers) — flagged in the plan's Out-of-Scope section as a follow-up candidate, not addressed here.

---

*Quick task: 260927-r2j*
*Completed: 2026-09-27*

## Self-Check: PASSED
