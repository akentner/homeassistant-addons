# Phase 21 Review Disposition

Bulk disposition of the 20 findings in 21-REVIEW.md (plan 21-09, Task 3). `closed` rows cite the closing commit,
`deferred` rows carry one line of reason. No per-finding code investigation was done for this ledger.

| ID | Severity | Title | Disposition | Evidence or reason |
|----|----------|-------|-------------|--------------------|
| CR-01 | critical | Print history silently stops recording after a container recreation (job-id counter reset) | deferred | owned by the print-history poller, not by D-01..D-13; no Phase 21 decision depends on it |
| CR-02 | critical | run.sh ignores a failed `generate_config.py`, so "Refusing to start" is not honoured | closed | commit 6d8414a (run.sh refuses to start when generate_config.py fails) |
| CR-03 | critical | Upload worker can upload a truncated PDF (and never the sidecar title) | deferred | owned by the Phase 22 paperless upload feature (upload-worker.py), not by D-01..D-13 |
| WR-01 | warning | Plaintext admin password written to a world-readable script and never removed | deferred | credential-on-disk hardening of the provisioning script; out of scope for this mDNS gap round |
| WR-02 | warning | A redirecting paperless-ngx URL turns a failed upload into a "success" | deferred | owned by the Phase 22 paperless upload feature (redirect handling in the upload worker) |
| WR-03 | warning | Numeric options are unbounded and unvalidated; `url`/`token` are never checked at startup | deferred | owned by the Phase 22 paperless upload options, not by D-01..D-13 |
| WR-04 | warning | `$`-anchored validation regexes accept a trailing newline | closed | commit 6d8414a (fullmatch validation at all call sites) |
| WR-05 | warning | `NAME_RE` is used as the CUPS queue-name charset but rejects underscores (and the migration script feeds it such names) | closed | commit e66e7ef (PRINTER_NAME_RE accepts underscores, NAME_RE kept for host names) |
| WR-06 | warning | Print history misses jobs that complete out of id order (multi-printer setups) | deferred | owned by the print-history poller (20 s Get-Jobs poller), out of scope for this gap round |
| WR-07 | warning | UUID-stability test in verify-cups-scaffold.sh cannot fail | closed | commit 2e92a39 (UUID test recreates the container and compares) |
| WR-08 | warning | paperless verify script's title/sidecar assertions are satisfied by the failure path | deferred | owned by the Phase 22 paperless verifier assertions, not by D-01..D-13 |
| WR-09 | warning | One failing `lpadmin` aborts registration of every later printer and the cups-pdf queue | closed | commit e66e7ef (per-entry failure tolerance, aggregated exit status) |
| WR-10 | warning | Root upload worker follows symlinks inside a world-writable (0777) outbox | deferred | owned by the Phase 22 paperless upload worker (symlink hardening), not by D-01..D-13 |
| IN-01 | info | Docs disagree with code | deferred | docs item for the next cups release; no Phase 21 decision depends on it |
| IN-02 | info | Duplicated registration snippet builders and doubled warnings | deferred | refactor item; no behaviour change required by D-01..D-13 |
| IN-03 | info | `usb://` URIs are accepted/documented but the add-on cannot reach USB devices | deferred | out of scope for this gap round (USB passthrough is a separate add-on capability decision) |
| IN-04 | info | Line-length / lint | deferred | lint item for the next cups release; the repository linters do not gate it here |
| IN-05 | info | Nested option translations may not be applied | deferred | needs a check in the HA add-on UI; out of scope for this gap round |
| IN-06 | info | Migration helper silently downgrades printers and has a pipefail/SIGPIPE edge | closed | commit 2e92a39 (YAML-safe migration helper, grep -m1 -F, driver reminder) |
| IN-07 | info | Operational edge cases in run.sh / cupsd scoping | deferred | operational edge cases (boot-time trap, Listen on DHCP change, admin over HTTP); out of scope here |

## Carry-forward notes

- **D-08 wording over-read.** D-08 forbids a watchdog or log monitor for the slot-exhaustion error only. It does not
  forbid supervising the avahi host name, and D-11 (a fixed host name) requires that the name is KEPT. The comments
  "startup-only, no watchdog -- D-08" in cups/avahi-guard.sh and cups/run.sh and the matching sentence in cups/DOCS.md
  over-read D-08. Correcting them needs a change under cups/ (a rebuild); it is delivered by the optional plans
  21-11/21-12 if they are activated, otherwise by the next cups release.
- **iPhone / Mac print check.** The optional end-to-end check from a real iPhone or Mac (AirPrint discovery and a test
  page) is still outstanding; it is not a Phase 21 must-have and is not covered by the live verifier.
- **Formatting.** `.planning/` is excluded from prettier, so this table needs no column padding.
