---
phase: 22-cups-paperless-ngx-pdf-document-upload
plan: 02
subsystem: docs
tags: [cups, cups-pdf, paperless-ngx, documentation, home-assistant-addon, versioning]

requires:
  - phase: 22-01
    provides: Disabled-by-default `paperless_upload` cups-pdf queue + background upload worker, shipped config schema/defaults, corrected `PostProcessing` directive name, D-08 UUID-reuse mechanism
provides:
  - Full DOCS.md documentation of the `paperless_upload` feature (options table, outbox lifecycle, known limitations, corrected PostProcessing design notes)
  - README.md Features-list mention of the paperless-ngx upload capability
  - cups add-on version bumped 0.1.0-13 -> 0.1.0-14 via the repo's 3-file sync scheme, with a pushed `cups/v0.1.0-14` tag
affects: []

actuals:
  tokens: 5094
  tasks: 2
  commits: 2
  plan_head_before: cb045a2cd0abed33f150dd1650052bbc97db17a2
  plan_head_after: 690e1df2c5b3b75799b84a1e8f165e0f11664ddd

tech-stack:
  added: []
  patterns:
    - "Documentation-only plans still get a full task-by-task verify/acceptance-criteria/commit loop and a final full regression re-run of the feature's own verify script -- proves docs describe real, unbroken behavior rather than aspirational behavior"

key-files:
  created: []
  modified:
    - cups/DOCS.md
    - cups/README.md
    - cups/config.yaml

key-decisions:
  - "Reused the existing single `[docs]: DOCS.md` reference link for the new README Features bullet rather than adding a second, anchor-specific link -- matches this add-on's own established convention (every other Features bullet links nowhere; only the closing 'See DOCS.md' line carries the reference)."
  - "Design notes correction paragraph consolidates all four required sub-points (fixed outbox path/D-05, corrected PostProcessing argument model, 0o777 outbox rationale, minimal exhausted-retry visibility) into one bolded-lead paragraph, matching this file's established one-entry-per-topic Design notes style rather than splitting into four separate entries."

patterns-established: []

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15]

coverage:
  - id: D1
    description: "cups/DOCS.md documents every paperless_upload option (enabled, queue_name, location, url, token, timeout, retry_count, retry_delay) with its exact shipped default and purpose"
    verification:
      - kind: manual_procedural
        ref: "grep -A20 '## Paperless-ngx PDF Upload' cups/DOCS.md | grep -c 'queue_name|retry_count|retry_delay|timeout' returns 4; manual cross-check against cups/config.yaml's options.paperless_upload block confirmed byte-for-byte match (queue_name=PDF-to-DMS, timeout=30, retry_count=5, retry_delay=60)"
        status: pass
    human_judgment: false
  - id: D2
    description: "DOCS.md's Design notes explicitly record the corrected PostProcessing (not PostProcess) title-derivation mechanism -- three positional args, no title env var, title recovered from the PDF's own filename"
    verification:
      - kind: manual_procedural
        ref: "grep -n 'environment variable' cups/DOCS.md -- both occurrences confirmed to sit inside the single new Design notes correction paragraph, none elsewhere describing the mechanism as an env var"
        status: pass
    human_judgment: false
  - id: D3
    description: "cups/README.md's Features list mentions the paperless-ngx upload capability, consistent with the existing bullet style, reusing the existing [docs] reference link (no duplicate link introduced)"
    verification:
      - kind: manual_procedural
        ref: "grep -c 'paperless-ngx' cups/README.md == 1; grep -c '\\[docs\\]: DOCS.md' cups/README.md == 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "Re-running internal/verify-cups-paperless-upload.sh after documentation changes still passes in full -- happy path, D-07 disabled-by-default regression, D-09/D-15 retry-exhaustion -- proving no drift between docs and shipped behavior"
    verification:
      - kind: integration
        ref: "bash internal/verify-cups-paperless-upload.sh"
        status: pass
    human_judgment: false
  - id: D5
    description: "cups/config.yaml's version is bumped via make update-version (3-file sync scheme) for this functional add-on documentation change, and make validate-versions confirms config.yaml/build.yaml/README.md remain consistent"
    verification:
      - kind: manual_procedural
        ref: "grep -n '^version:' cups/config.yaml shows 0.1.0-14; make validate-versions exits 0 for all add-ons including cups (config.yaml 0.1.0-14 / build.yaml 0.1.0 / README.md 0.1.0, consistent by design since only the subpatch moved); cups/v0.1.0-14 tag created and pushed against the clean post-commit HEAD"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-09-28
status: complete
---

# Phase 22 Plan 02: cups-pdf Paperless-ngx Documentation + Version Sync Summary

**DOCS.md/README.md coverage for the `paperless_upload` feature (options table, outbox lifecycle, corrected PostProcessing design notes) plus a 3-file version sync to `0.1.0-14`, both cross-checked against a full re-run of the feature's own verify script.**

## Performance
- **Duration:** 5 min
- **Started:** 2026-09-28T20:06:24Z
- **Completed:** 2026-09-28T20:11:27Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments
- `cups/DOCS.md` gained a `paperless_upload` row in the top-level Add-on Options table, a full "Paperless-ngx PDF Upload" subsection (field table with exact shipped defaults, outbox lifecycle `incoming/` -> `processing/` -> `sent/`/`failed/`, and a "Known limitations" subsection), and a Design notes paragraph documenting the corrected `PostProcessing` (not `PostProcess`) title-derivation mechanism, the fixed shared-outbox rationale (D-05), the world-writable `0o777` outbox trade-off, and the deliberately minimal exhausted-retry log visibility
- `cups/README.md`'s Features list now mentions the paperless-ngx upload capability, reusing the existing `[docs]: DOCS.md` reference link (no duplicate link added)
- `cups/config.yaml`'s version bumped `0.1.0-13` -> `0.1.0-14` via `make update-version ADDON=cups VERSION=0.1.0-14` (the repo's mandatory 3-file sync scheme); `build.yaml`/README badge correctly reported "no changes needed" since only the subpatch moved
- `cups/v0.1.0-14` tag created and pushed against the clean post-commit HEAD via a second, best-effort `make update-version` invocation (the first invocation correctly deferred tagging while the tree was still dirty, per `update-version.py`'s own safety check)
- Full regression: `internal/verify-cups-paperless-upload.sh` re-run end-to-end after all documentation and version changes, all 3 scenarios (happy path, D-07 disabled-by-default, D-09/D-15 retry exhaustion) pass unchanged

## Task Commits
1. **Task 1: cups/DOCS.md — paperless_upload options table + Design notes** - `0c985d8` (docs)
2. **Task 2: cups/README.md feature bullet + version bump + final regression** - `690e1df` (feat)

## Files Created/Modified
- `cups/DOCS.md` - new `paperless_upload` options-table row, "Paperless-ngx PDF Upload" subsection (fields, outbox lifecycle, known limitations), Design notes correction paragraph
- `cups/README.md` - new Features bullet for the paperless-ngx upload capability
- `cups/config.yaml` - `version` bumped `0.1.0-13` -> `0.1.0-14`

## Decisions Made
- Reused the single existing `[docs]: DOCS.md` reference link for the new README bullet rather than adding a second, anchor-specific link — matches this add-on's own convention where only the closing "See DOCS.md" line carries a reference-style link.
- Consolidated all four required Design-notes sub-points (fixed outbox path, corrected PostProcessing argument model, `0o777` outbox rationale, minimal exhausted-retry visibility) into one bolded-lead paragraph rather than four separate entries, matching this file's established one-entry-per-topic style.

## Deviations from Plan

None - plan executed exactly as written. `prettier` (a pre-commit hook) reformatted `cups/DOCS.md`'s table whitespace on the first commit attempt; the commit was re-staged and re-run with the reformatted content, which is expected pre-commit-hook behavior in this repo, not a deviation from the plan's intent.

**Total deviations:** 0. **Impact:** None — the plan's `must_haves` are satisfied exactly as specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Phase 22 complete — the `paperless_upload` feature (cups-pdf queue, PostProcessing hook, upload worker with retry/backoff, full documentation, version bump) is fully built, documented, and verified. Ready for `/gsd-verify-work`.

## Self-Check: PASSED

- FOUND: cups/DOCS.md
- FOUND: cups/README.md
- FOUND: cups/config.yaml
- FOUND: .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-SUMMARY.md
- FOUND commit: 0c985d8 (Task 1)
- FOUND commit: 690e1df (Task 2)

---
*Phase: 22-cups-paperless-ngx-pdf-document-upload*
*Completed: 2026-09-28*
