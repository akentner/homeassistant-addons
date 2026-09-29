---
phase: 22
review: 22-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "D-15 exhaustion log line reports the pre-disambiguation filename on a `failed/` collision"
  - id: WR-02
    severity: warning
    disposition: open
    title: "retry-state hardening validates the JSON is a dict but not its field types"
  - id: IN-01
    severity: info
    disposition: open
    title: "internal finding ID \"(WR-05)\" leaks into a production log line"
  - id: IN-02
    severity: info
    disposition: open
    title: "`collision_tag` sharing between PDF and sidecar is only reliable when the PDF itself collides"
  - id: IN-03
    severity: info
    disposition: open
    title: "pre-existing falsy-zero coercion bug in numeric option parsing (out of this diff's scope)"
  - id: CR-01
    severity: critical
    disposition: open
    title: "`is_due()` runs outside per-document error isolation — one corrupted retry-state file can silently stall the entire upload queue"
  - id: WR-03
    severity: warning
    disposition: open
    title: "No validation that `url`/`token` are set when `paperless_upload.enabled: true`"
  - id: WR-04
    severity: warning
    disposition: open
    title: "No uniqueness check between `paperless_upload.queue_name` and `printers[].name`"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Outbox `sent/`/`failed/` moves silently overwrite same-named files across add-on restarts"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Upload response body is logged verbatim; the \"token never leaks\" verification does not generalize"
open: 10
total: 10
recorded: 2026-09-29T16:42:36.565Z
---

# Phase 22: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| CR-01 | critical | open | - (not in the current review) |
| WR-03 | warning | open | - (not in the current review) |
| WR-04 | warning | open | - (not in the current review) |
| WR-05 | warning | open | - (not in the current review) |
| WR-06 | warning | open | - (not in the current review) |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
