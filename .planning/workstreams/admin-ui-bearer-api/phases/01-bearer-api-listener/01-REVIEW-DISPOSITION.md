---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "Directory fsync failure after `os.replace` leaves a hash nobody has a token for (lockout)"
  - id: WR-02
    severity: warning
    disposition: fixed
    title: "`load_or_create` does not raise `ValueError` for unreadable paths and chmods whatever `path` points at"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "Unauthenticated slow-drip clients hold handler threads indefinitely; the \"slow clients are dropped\" claim is false"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "Bodies on non-body methods are never read, and the connection stays alive (request desync)"
  - id: IN-01
    severity: info
    disposition: deferred
    title: "`Expect: 100-continue` is answered before the bearer check"
  - id: IN-02
    severity: info
    disposition: deferred
    title: "Unauthenticated responses disclose the Python version in `Server`"
  - id: IN-03
    severity: info
    disposition: deferred
    title: "`GeneratedToken` keeps the pending plaintext in an instance `__dict__`"
  - id: IN-04
    severity: info
    disposition: deferred
    title: "`Request.public=True` on the API port contradicts the documented meaning of `public`"
  - id: IN-05
    severity: info
    disposition: deferred
    title: "Full tracebacks from handlers on the API port go to stdout, while `handle_error` prints only the class"
  - id: IN-06
    severity: info
    disposition: deferred
    title: "Necessity (impossible-state guard): `hasattr(headers, \"get_all\")` / `isinstance(values[0], str)` in `_bearer_token`"
  - id: IN-07
    severity: info
    disposition: deferred
    title: "The API listener can die silently while the GUI keeps running"
  - id: IN-08
    severity: info
    disposition: deferred
    title: "Style nits in changed lines"
open: 0
total: 12
recorded: 2026-11-18T15:10:22.539Z
---

# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | 01-REVIEW-FIX.md |
| WR-02 | warning | fixed | 01-REVIEW-FIX.md |
| WR-03 | warning | fixed | 01-REVIEW-FIX.md (fixed; timing and concurrency logic flagged for human verification) |
| WR-04 | warning | fixed | 01-REVIEW-FIX.md |
| IN-01 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-02 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-03 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-04 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-05 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-06 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-07 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |
| IN-08 | info | deferred | deferred by user decision 2026-11-18: phase 1 fixes warnings only; info findings go to consumer adoption work |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved. A `|` in the reason is kept as prose and escaped on the next run.
Re-running the gate keeps every row it can. A row the current review no longer reports is kept and its Source cell flagged, so a finding does not leave this record silently. ONE exception: when a finding id is REUSED by a different finding, the earlier decision cannot keep a row — the id is taken — and it is dropped. A RECORDED decision (anything but `open`) is named on the console when that happens; a row still at `open` is replaced silently, because `open` records no decision to lose.
