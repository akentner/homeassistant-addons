---
phase: 22
review: 22-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: fixed
    title: "HTTP redirects turn the upload into a GET and the worker records it as a success"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Worker can pick up a PDF that cups-pdf is still writing, and can race the title-sidecar hook"
  - id: WR-02
    severity: warning
    disposition: open
    title: "`process_new_document` silently overwrites a same-named document that is still in `processing/`"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Retry-state field types are not validated, one bad file stalls that document forever"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Exhaustion WARNING names the pre-disambiguation filename"
  - id: WR-05
    severity: warning
    disposition: open
    title: "No validation of `url`/`token` when the feature is enabled; every document is dead-lettered silently"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Success path deletes sidecar and retry state before the PDF is moved, so a failure re-uploads the document"
  - id: WR-07
    severity: warning
    disposition: open
    title: "Verifier cannot detect a broken title-recovery mechanism"
  - id: WR-08
    severity: warning
    disposition: open
    title: "`paperless_upload.queue_name` can collide with a `printers[]` name"
  - id: IN-01
    severity: info
    disposition: open
    title: "Internal finding ID \"(WR-05)\" appears in a runtime log line"
  - id: IN-02
    severity: info
    disposition: open
    title: "Shared `collision_tag` only holds when the PDF itself collides"
  - id: IN-03
    severity: info
    disposition: open
    title: "Falsy-zero coercion of numeric options"
  - id: IN-04
    severity: info
    disposition: open
    title: "DOCS.md and the worker docstring disagree about the sidecar on success"
  - id: IN-05
    severity: info
    disposition: open
    title: "Stage directories are all `0o777`, no sticky bit, and `https` verification cannot be configured"
  - id: IN-06
    severity: info
    disposition: open
    title: "`avahi_guard_start` claims it always leaves avahi running"
open: 14
total: 15
recorded: 2026-10-04T17:57:04.211Z
  - id: WR-09
    severity: warning
    disposition: open
    title: "Malformed Location header makes _safe_redirect_target() raise; document is re-POSTed forever"
  - id: IN-07
    severity: info
    disposition: open
    title: "Redirect probe only covers Location /login/; sanitising and cap untested"
  - id: IN-08
    severity: info
    disposition: open
    title: "Only HTTP 200 counts as success; 201/202/204 are dead-lettered"
---

# Phase 22: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | fixed | 22-04 (commits 3ffbf09, 8a98342, 17d3553) |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| WR-07 | warning | open | - |
| WR-08 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| WR-09 | warning | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
