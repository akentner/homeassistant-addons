---
phase: quick-260927-ntq
plan: 260927-ntq
subsystem: cups-add-on
tags: [cups, airprint, ppd, config-generation, home-assistant-addon]
dependency-graph:
  requires: [21-03]
  provides: [printers[].presets]
  affects: [cups/generate_config.py, cups/config.yaml, internal/verify-cups-scaffold.sh]
tech-stack:
  added: []
  patterns:
    - "Apple *APPrinterPreset PPD extension injection via TEMP-copy + lpadmin -P reload"
    - "Flattened string schema field as fallback for HA add-on options schema's depth-2 nesting cap"
key-files:
  created: []
  modified:
    - cups/generate_config.py
    - cups/config.yaml
    - internal/verify-cups-scaffold.sh
    - cups/DOCS.md
    - cups/README.md
decisions:
  - "Flattened `presets: str?` field (not nested presets[] list-of-objects) -- HA's add-on options schema caps nested list/dict depth at two; printers[] already uses both levels (resolved during planning, not re-litigated during execution)"
  - "Fixed a factually inaccurate DOCS.md cross-reference during T3: the plan's proposed text claimed an existing 'duplex design note' already pointed operators at lpoptions -- no such note exists in DOCS.md, so the parenthetical claim was removed rather than shipped as a broken/misleading link (Rule 1)"
metrics:
  duration: "~15 min"
  completed: 2026-09-27
status: complete
actuals:
  tokens: 7197
  tasks: 3
  commits: 3
  plan_head_before: 6bf21fa
  plan_head_after: 925074f
---

# Quick Task 260927-ntq: Configurable AirPrint Print Presets Summary

Adds `printers[].presets` to the `cups` add-on: operators can declare named AirPrint print presets (e.g. "Duplex
Fein") bundling a printer's own existing PPD option/choice pairs (Duplex + Resolution) into Apple's
`*APPrinterPreset` PPD stanza, so iOS's print sheet shows a preset picker instead of only individual controls
nested under "Optionen".

## What Was Built

- **`cups/generate_config.py`**: `PRESET_NAME_RE` / `PRESET_OPTION_TOKEN_RE` validation regexes,
  `slugify_preset_id()` (de-duplicated PPD keyword derivation), `_parse_presets_field()` (flattened-string parser),
  `build_preset_injection_snippet()` (renders the shell fragment that copies the printer's live PPD to a TEMP file,
  appends validated `*APPrinterPreset` stanzas via a quoted heredoc, and reloads via `lpadmin -P`). Wired into both
  driver branches (`brlaser` and `generic`) of `build_printer_registration()`.
- **`cups/config.yaml`**: `printers[].presets: str?` schema field; version bumped `0.1.0-8` -> `0.1.0-9`.
- **`internal/verify-cups-scaffold.sh`**: fixture `presets` fields on both existing printer entries (one valid +
  one deliberately malformed on `testprinter`; the real Duplex/Resolution combo + a slug-collision pair on
  `brlasertest`) and 9 new assertions covering the positive case, negative/skip case, slug-collision de-dup, and
  live on-disk PPD proof.
- **`cups/DOCS.md`** / **`cups/README.md`**: new `### Printer presets` subsection (worked example, `lpoptions`
  discovery instructions, schema-depth fallback rationale, PPD-extensions-spec attribution), Design notes
  paragraph, Printers table row, README Features bullet.

## Verification

- **T1**: `ast.parse` compiles clean; `config.yaml` schema carries `presets: str?`; `make validate-addons` passes.
  Manual sanity check of `slugify_preset_id` (collision `_2` suffix) and `build_preset_injection_snippet` (valid +
  invalid preset in one call) confirmed expected output before committing.
- **T2**: `bash -n` passes. Full empirical Docker-based run of `internal/verify-cups-scaffold.sh` (real cupsd
  inside a built container, ~1 min) printed `ALL CHECKS PASSED` with all 9 new preset assertions green:
  stanza generated, option lines present, `lpadmin -P` reload call present, slug collision de-duplicated
  (`test_preset` / `test_preset_2`), valid sibling preset unaffected by an invalid one, invalid preset skipped
  from the generated script, WARNING logged, and both `brlasertest.ppd` and `testprinter.ppd` on disk carry the
  injected stanza after the container actually ran.
- **T3**: `grep -c presets` > 0 in both docs files; `config.yaml` reports `0.1.0-9`; `build.yaml` reports `0.1.0`
  (base semver unchanged, subpatch-only bump, correct per the 3-file scheme); `make lint` passes (prettier
  auto-reformatted the two markdown files' line-wrapping on first run per its own `printWidth: 120` config --
  re-ran and confirmed clean); `make validate-addons` passes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed a factually inaccurate DOCS.md cross-reference**
- **Found during:** Task 3
- **Issue:** The plan's proposed "Discovering valid Key/Value pairs" paragraph included the parenthetical "(the
  same command the [duplex design note](#design-notes) already points operators at)" -- but `cups/DOCS.md` does
  not contain any prior mention of `lpoptions` for a duplex option; no such note exists to link to.
- **Fix:** Removed the parenthetical claim rather than ship a misleading/broken cross-reference; the sentence
  reads correctly without it.
- **Files modified:** `cups/DOCS.md`
- **Commit:** 925074f

### Version tag

`make update-version ADDON=cups VERSION=0.1.0-9` created and pushed git tag `cups/v0.1.0-9` to `origin` successfully
(matches this repo's established pattern of tagging the pre-bump HEAD commit, same as `cups/v0.1.0-6`/`v0.1.0-7`
before it) -- not a skipped/failed push as the plan's fallback language anticipated.

## Self-Check

```
FOUND: cups/generate_config.py
FOUND: cups/config.yaml
FOUND: internal/verify-cups-scaffold.sh
FOUND: cups/DOCS.md
FOUND: cups/README.md
FOUND commit 7551b8b
FOUND commit 3caee0a
FOUND commit 925074f
```

## Self-Check: PASSED
