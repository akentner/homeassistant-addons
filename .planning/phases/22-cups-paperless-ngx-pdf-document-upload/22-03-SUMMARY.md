---
phase: 22-cups-paperless-ngx-pdf-document-upload
plan: 03
subsystem: infra
tags: [cups, paperless-ngx, defensive-validation, resilience, ha-addon]

# Dependency graph
requires:
  - phase: 22-01
    provides: cups/upload-worker.py (background outbox worker), internal/verify-cups-paperless-upload.sh (Scenarios 1-3)
  - phase: 22-02
    provides: cups/DOCS.md + README.md documentation, prior version bump to 0.1.0-14
provides:
  - CR-01 closed — a syntactically-valid-but-non-dict .retry.json no longer permanently stalls the processing/ retry queue
  - WR-02 closed — a syntactically-valid-but-non-dict .json title sidecar no longer breaks D-11's never-skipped guarantee
  - WR-05 closed — a sent//failed/ filename collision is disambiguated (timestamp+pid suffix) instead of silently overwriting an already-retained document
  - New Scenario 4 in internal/verify-cups-paperless-upload.sh proving all three fixes end-to-end against a real built image
affects: [cups add-on maintenance, future outbox/worker changes]

# Actuals (#2632)
actuals:
  tokens: 3937
  tasks: 2
  commits: 2
  plan_head_before: 4169f7564792a670be83ad9177a220433dfe3c2c
  plan_head_after: 79423a482c506845b4b71d49bbe7d1328081cc94

tech-stack:
  added: []
  patterns:
    - "Defensive isinstance(dict) validation on every untrusted-state JSON.loads() result before indexing it, degrading into an existing fallback path rather than raising"
    - "unique_destination()/_disambiguation_suffix() helper pair: check-destination-exists before Path.replace(), disambiguate with a UTC-timestamp+pid suffix, log a WARNING, and share one collision_tag across a colliding PDF+sidecar pair"

key-files:
  created: []
  modified:
    - cups/upload-worker.py
    - internal/verify-cups-paperless-upload.sh
    - cups/config.yaml

key-decisions:
  - "is_due() call site moved inside poll_once()'s existing per-document try/except (previously outside it) — closes CR-01 at the control-flow layer; load_retry_state()'s new isinstance(dict) check closes it independently at the data-validation layer (defense in depth)"
  - "attempt_and_route()'s exhausted-retry branch computes ONE shared collision_tag when the PDF's failed/ destination already exists, passing it explicitly to both the PDF's and sidecar's unique_destination() calls, so a colliding pair stays correlated by suffix for a human triaging failed/ later"
  - "Scenario 4 injects fixtures directly into the outbox bind mount (no docker exec, no lp print job) since the goal is proving state-validation resilience, not print-pipeline mechanics already covered by Scenarios 1/3"

requirements-completed: [D-11, D-13, D-15]

coverage:
  - id: D1
    description: "read_title() falls back to the D-11 timestamp title (never raises) for a syntactically-valid-but-non-dict .json sidecar"
    requirement: "D-11"
    verification:
      - kind: unit
        ref: "Task 1's standalone python3 unit check — WR-02 assertion (title.startswith('Scan_'))"
        status: pass
      - kind: e2e
        ref: "internal/verify-cups-paperless-upload.sh Scenario 4 — badtitle-doc.pdf converges to sent/ despite malformed sidecar"
        status: pass
    human_judgment: false
  - id: D2
    description: "A poisoned .retry.json no longer stalls the processing/ retry scan for alphabetically-later documents"
    requirement: "D-13"
    verification:
      - kind: unit
        ref: "Task 1's standalone python3 unit check — CR-01 assertion (is_due() returns True for non-dict retry state)"
        status: pass
      - kind: e2e
        ref: "internal/verify-cups-paperless-upload.sh Scenario 4 — zzz-normal.pdf converges out of processing/ despite poison-aaa.pdf's malformed retry state"
        status: pass
    human_judgment: false
  - id: D3
    description: "A sent//failed/ filename collision is disambiguated with a logged WARNING instead of silently overwriting an already-retained document"
    requirement: "D-15"
    verification:
      - kind: unit
        ref: "Task 1's standalone python3 unit check — WR-05 assertion (unique_destination() disambiguates, pre-existing content untouched)"
        status: pass
      - kind: e2e
        ref: "internal/verify-cups-paperless-upload.sh Scenario 4 — pre-existing sent/collide.pdf byte-identical, new arrival disambiguated to exactly one collide-*.pdf, WARNING logged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Pre-existing Scenarios 1-3 (happy path, D-07 disabled regression, retry/backoff exhaustion) still pass unchanged"
    verification:
      - kind: e2e
        ref: "internal/verify-cups-paperless-upload.sh — full run, all 4 scenarios, exit 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "cups/config.yaml version bumped 0.1.0-14 -> 0.1.0-15 via make update-version; 3-file sync scheme validated"
    verification:
      - kind: other
        ref: "make validate-versions"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-09-29
status: complete
---

# Phase 22 Plan 03: Close CR-01/WR-02/WR-05 outbox-state defensive validation Summary

**Three defensive-validation gaps in `cups/upload-worker.py` (poisoned `.retry.json` stalling the retry queue, a malformed `.json` title sidecar breaking the timestamp-fallback guarantee, and an unguarded `Path.replace()` collision in `sent/`/`failed/`) are closed with `isinstance(dict)` validation and a new `unique_destination()` helper, proven end-to-end against a real built image via a new Scenario 4.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-09-29T16:14:00Z (approx.)
- **Completed:** 2026-09-29T16:29:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `read_title()` now validates `isinstance(parsed, dict)` before calling `.get("title")`, degrading a syntactically-valid-but-non-dict `.json` sidecar into the existing D-11 timestamp-fallback path instead of raising `AttributeError` (closes WR-02)
- `load_retry_state()` now rejects non-dict parsed JSON (returns `None`, treated as "no prior attempts"), and `is_due()`'s call site moved inside `poll_once()`'s existing per-document `try/except` — closing CR-01 at both the data-validation layer and the control-flow layer (defense in depth)
- New `_disambiguation_suffix()`/`unique_destination()` helpers disambiguate a same-named `sent/`/`failed/` collision (e.g. after cupsd's job-ID counter resets across a container restart) with a timestamp+pid suffix and a logged WARNING, instead of silently overwriting an already-retained document via `Path.replace()`'s rename-clobber semantics (closes WR-05)
- New "Scenario 4" in `internal/verify-cups-paperless-upload.sh` injects real malformed-state fixtures (poisoned `.retry.json`, malformed `.json` sidecar, a `sent/collide.pdf` filename collision) directly into a real built image's outbox bind mount and proves all three fixes end-to-end, alongside the pre-existing 3 scenarios still passing unchanged
- `cups/config.yaml` version bumped `0.1.0-14` → `0.1.0-15` via `make update-version` (3-file sync scheme); `cups/v0.1.0-15` git tag created and pushed

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix CR-01, WR-02, WR-05 in cups/upload-worker.py** - `82a93a5` (fix)
2. **Task 2: Extend the verify script with Scenario 4, bump the add-on version, run the full regression** - `79423a4` (test)

_No separate plan-metadata commit was made for this run — sequential/sole-executor mode; STATE.md/ROADMAP.md updates land in the next commit alongside this SUMMARY._

## Files Created/Modified
- `cups/upload-worker.py` - `isinstance(dict)` validation in `read_title()`/`load_retry_state()`, `is_due()` moved inside `poll_once()`'s per-document try/except, new `unique_destination()`/`_disambiguation_suffix()` helpers wired into `attempt_and_route()`'s `sent/`/`failed/` moves, docstring updated
- `internal/verify-cups-paperless-upload.sh` - new "Scenario 4" section (malformed-state + collision resilience), header comment bullet added
- `cups/config.yaml` - version `0.1.0-14` → `0.1.0-15`

## Decisions Made
- CR-01 fixed at both layers (data-validation in `load_retry_state()` AND control-flow in `poll_once()`) per the review's own combined recommendation, so a future regression in either alone cannot resurrect the poison-pill stall
- WR-05's exhausted-retry branch computes one shared `collision_tag` up front (only when the PDF's `failed/` destination already exists) and passes it explicitly to both the PDF's and sidecar's `unique_destination()` calls, keeping a colliding pair correlated by an identical suffix for later human triage
- Scenario 4 writes fixtures directly into the outbox bind mount rather than driving them through `lp`/cups-pdf, since the goal is proving worker-side state-validation resilience (already covered end-to-end by print-pipeline mechanics in Scenarios 1 and 3), not re-testing the print pipeline itself

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Docker in this environment runs via a podman emulation shim (`Emulate Docker CLI using podman`) — pre-existing environment characteristic, not related to this plan's changes; all 4 scenarios passed under it exactly as Scenarios 1-3 did before this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 5 must-haves from this plan's frontmatter are verified true (see `coverage` block above)
- 22-VERIFICATION.md's `gaps_found` status (10/12 truths, CR-01/WR-02/WR-05 open) should now score 12/12 on re-verification
- No blockers for Phase 22 closure

## Self-Check: PASSED

- `cups/upload-worker.py` exists on disk
- `internal/verify-cups-paperless-upload.sh` exists on disk
- `22-03-SUMMARY.md` exists on disk
- Commits `82a93a5`, `79423a4`, `aa1d527` all found in `git log --oneline --all`
- All acceptance criteria from Task 1 and Task 2 re-verified passing
- Full `bash internal/verify-cups-paperless-upload.sh` re-run: exit 0, 4 scenarios, all PASS

---
*Phase: 22-cups-paperless-ngx-pdf-document-upload*
*Completed: 2026-09-29*
