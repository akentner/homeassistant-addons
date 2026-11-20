---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Rotate rollback hides a post-write failure and returns 409 user_exists for a rotation that was persisted"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "The pre-read guard does not prevent `AccessStore.load()` from moving `access.json` aside and writing a one-user file"
  - id: IN-01
    severity: info
    disposition: open
    title: "fetchlog stops recording fetches after one transient access.json read failure until the file changes"
  - id: IN-02
    severity: info
    disposition: open
    title: "Fresh URLs of a user stay on screen after that user is revoked"
  - id: IN-03
    severity: info
    disposition: open
    title: "Rotate is offered for entries with a missing or unknown `source` but always fails with a misleading error"
  - id: IN-04
    severity: info
    disposition: open
    title: "Add-form input ids can collide between repositories"
  - id: IN-05
    severity: info
    disposition: open
    title: "The forwarder silences only Python-level streams, not file descriptors 1 and 2"
  - id: IN-06
    severity: info
    disposition: open
    title: "Node tests run twice in CI"
  - id: IN-07
    severity: info
    disposition: open
    title: "Forced `process.exit` in `test.after` hides leaked timers or handles"
  - id: IN-08
    severity: info
    disposition: open
    title: "Impossible-state guard: `request_sync` creates the run directory that `init` already guarantees"
open: 8
total: 10
recorded: 2026-11-20T20:57:01.563Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | 03-REVIEW-FIX.md |
| WR-02 | warning | fixed | 03-REVIEW-FIX.md |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
