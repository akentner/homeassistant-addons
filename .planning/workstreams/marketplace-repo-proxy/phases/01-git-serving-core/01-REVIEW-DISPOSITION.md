---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "Branch change rewrites HEAD and refspec before the fetch succeeds, breaking the served mirror"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Protocol v2 serves unadvertised objects by SHA, defeating \"only this one branch is served\""
  - id: WR-02
    severity: warning
    disposition: open
    title: "`^…$` validators accept a trailing newline (user label, hash, owner)"
  - id: WR-03
    severity: warning
    disposition: open
    title: "Credentials in `public_url` are written unmasked to the add-on log"
  - id: WR-04
    severity: warning
    disposition: open
    title: "`access.json` is renamed to `.corrupt` on transient read errors and partial writes; an earlier `.corrupt` is overwritten"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Atomic JSON writes do not fsync the directory, so a revocation can be lost on power failure"
  - id: IN-01
    severity: info
    disposition: open
    title: "Failed upstream-default probes overwrite the known branch with `null` in status.json"
  - id: IN-02
    severity: info
    disposition: open
    title: "`mrp users add` writes the entry, then can die with a traceback before printing the URL"
  - id: IN-03
    severity: info
    disposition: open
    title: "`github_token` is not stripped"
  - id: IN-04
    severity: info
    disposition: open
    title: "`sync_interval` has no upper bound"
  - id: IN-05
    severity: info
    disposition: open
    title: "Dead code: `gitops.default_branch` and `AccessStore.entries`"
  - id: IN-06
    severity: info
    disposition: open
    title: "`init.py` docstring overstates the failure policy"
  - id: IN-07
    severity: info
    disposition: open
    title: "Leftover temp files with hashes and orphaned bare repositories are never cleaned up"
open: 13
total: 13
recorded: 2026-11-18T14:38:13.729Z
---

# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
