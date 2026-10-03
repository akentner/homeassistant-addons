---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 04
subsystem: infra
tags: [cups, avahi, mdns, airprint, verification, haos-op3050-1, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "cups add-on live on haos-op3050-1 (21-03); failed truths #13/#14 from 21-VERIFICATION.md"
provides:
  - "internal/verify-cups-mdns-live.sh: read-only live verifier (--assert / --diagnose) for the mDNS host-name claim and _ipp._tcp resolvability"
  - "RED baseline (4 FAIL) and a masked E1..E9 evidence record for the lost host-name claim"
  - "Diagnosis classification (inconclusive) and the go/no-go decision for the guard plan 21-05..21-07"
affects: [21-05, 21-06, 21-07]

plan_head_before: f63e517a3c77352552d398a8a3de60e1186c50ce
plan_head_after: 94dc3aab349e18dc40b123573efb4877f20d17a3
actuals:
  tokens: 4506
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Three-vantage-point mDNS verification: in-container D-Bus vs in-container files vs LAN-client avahi tools"
    - "Read-only live-host script with whitelisted jq extraction (credential-bearing options object never printed) and an IP masker"

key-files:
  created:
    - internal/verify-cups-mdns-live.sh
  modified: []

key-decisions:
  - "Classification inconclusive: the conflict-capture experiment was not run; the loss was restart/timing specific"
  - "decision: proceed (the user's decision) - continue with the startup-guard plans 21-05..21-07 as designed"
  - "avahi-browse is called with -k so the raw _ipp._tcp type appears in field 5 (without -k avahi prints the friendly name)"

requirements-completed: [D-07, D-10, D-11]

duration: n/a (interactive, spanned a human approval gate)
completed: 2026-10-03
status: complete
---

# Phase 21 Plan 04: Live mDNS verifier and root-cause diagnosis Summary

A read-only live verifier (`internal/verify-cups-mdns-live.sh`) now measures the two failed 21-VERIFICATION truths (#13 fixed
host name, #14 `_ipp._tcp` resolvable) from three vantage points. It reproduced the failure (4 FAIL), collected nine evidence
sections, and a post-restart run shows both truths cleared without any code fix, which makes the loss restart/timing specific.

## Accomplishments

- **Verifier (`--assert`, Task 1).** Read-only checks `conf-reflector`, `conf-ipv6`, `slot-exhaustion` (D-07/D-10),
  `daemon-fqdn`, `lan-forward-v4`, `lan-service-resolve` (D-11), `lan-no-aaaa` (D-10) and INFO-only reverse lookups.
  Exit 0/1/2 contract, `--mask`, `--settle-wait`. Shellcheck-clean, no mutating verbs.
- **Evidence collector (`--diagnose`, Task 2).** Sections E1..E9 with IP-masked stdout and a raw log outside the repo.
- **Diagnosis and decision (Task 3).** Experiment skipped; classification `inconclusive`; decision `proceed`.

## Task 1 baseline (RED, `--assert --mask`, before any change, 2026-10-03)

```
PASS conf-reflector, PASS conf-ipv6, PASS slot-exhaustion (0 lines)
FAIL daemon-fqdn: GetState=2 GetHostNameFqdn=cups-2.local, expected cups.local
FAIL lan-forward-v4: cups.local resolved to nothing from this LAN client
FAIL lan-no-aaaa: cups-2.local still publishes an AAAA record (<IPv6>) although avahi_use_ipv6=false
FAIL lan-service-resolve: no resolved _ipp._tcp record for cups.local (1 browse '+' line: browse-works/resolve-fails)
INFO reverse-container / reverse-lan: cups-2.local (shared-IP reverse lookup, not asserted)
RESULT: FAIL (4 failed)
```

## Diagnosis evidence (E1..E9, masked)

| Section | Evidence |
| ------- | -------- |
| E1 addon-state | version 0.1.0-13 (latest 0.1.0-13), started, watchdog true, boot auto; avahi_hostname=cups, avahi_use_ipv6=false, avahi_reflector=false |
| E2 avahi-processes | cups container `avahi-daemon: running [cups-2.local]`; network-tools container `avahi-daemon: running [72a005f5-network-tools.local]`; `hassio_multicast: mdns-repeater -f hassio` |
| E3 live-avahi-conf | host-name=cups, use-ipv6=no, allow-interfaces=enp2s0, enable-reflector=no |
| E4 syslog-sink | `/dev/log -> /run/systemd/journal/dev-log`, not a live socket. HINT: avahi conflict/rename logs are discarded |
| E5 daemon-dbus | GetState=2, GetHostName=cups-2, GetHostNameFqdn=cups-2.local. HINT: host-name claim lost |
| E6 service-instance-suffix | instance "Brother-MFC-7460DN @ cups" vs daemon host name cups-2. HINT: service registered under a stale host name |
| E7 start-times | host boot 2026-09-29T07:19:35Z; network-tools started 07:25:23Z; cups 07:25:42Z. HINT: 19 s apart, cold-start race plausible |
| E8 lan-names | `cups.local` no answer (-4/-6); `cups-2.local` and the HA host name resolve on -4 and -6; reverse of host IP: cups-2.local |
| E9 sibling-publish-config | network-tools sets publish-addresses=no (no HINT) |

Planning-time hypotheses: (1) dead log sink confirmed (E4); (2) stale service-instance suffix confirmed (E6); (3) shared-IP
reverse lookup not assertable (kept INFO-only); (4) D-10 shortfall confirmed (`lan-no-aaaa`, E8); (5) cold-start race
plausible but unproven (E7).

## Diagnosis

**Experiment status:** the human-gated conflict-capture experiment (three 25 s foreground `avahi-daemon --debug` trials)
was NOT run. The user approved it, but the Claude Code auto-mode classifier blocked the mutating remote commands. Only the
first step of trial 1 ran (`avahi-daemon --kill` inside the add-on container), which left the add-on without mDNS. The user
then restarted the add-on manually (`ha apps restart 72a005f5_cups`), which restored it. cupsd logged
`Defaulting to "DNSSDHostName cups.local"` at 18:00:37 on 0.1.0-13. No trial transcripts exist (0 of 3 trials captured).

**Post-restart `--assert --settle-wait 60 --mask` (as reported to the executor by the coordinator, from the user's run):**

```
PASS conf-reflector
PASS conf-ipv6
PASS slot-exhaustion (0 lines)
PASS daemon-fqdn (GetState=2, GetHostNameFqdn=cups.local)
PASS lan-forward-v4
FAIL lan-no-aaaa: cups.local still publishes an AAAA record although avahi_use_ipv6=false
PASS lan-service-resolve (1 resolved _ipp._tcp record)
INFO reverse-container / reverse-lan: cups.local (not asserted)
RESULT: FAIL (1 failed)
```

Baseline 4 FAIL -> post-restart 1 FAIL. The single remaining FAIL is `lan-no-aaaa`.

**classification:** inconclusive. Experiment not run (3 debug trials skipped). Post-restart `--assert` shows PASS for
`daemon-fqdn`, so no persistent claimant was observed on this restart.

**Interpretation.**
- Truths #13 (fixed host name) and #14 (`_ipp._tcp` resolvable) cleared after a plain restart with no code change. The loss
  is therefore timing/restart-specific, not a proven persistent claimant, and it may recur on the next boot or update
  (the original loss coincided with a cold start 19 s after a sibling avahi daemon, E7).
- Avahi's own conflict logs have been unobservable since go-live (E4), so the cause of the original loss cannot be named
  from existing evidence. The guard plan makes the next occurrence observable.
- `lan-no-aaaa` is a real, reproducible gap: `use-ipv6=no` only disables IPv6 sockets; `publish-aaaa-on-ipv4` defaults to
  yes. It is addressed by 21-05/21-07.

recommended: proceed
decision: proceed

(`decision: proceed` is the user's decision, "proceed, inconclusive passt so". The guard plans 21-05..21-07 may start.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] avahi-browse printed the friendly service type, breaking the field-5 match**
- **Found during:** Task 2
- **Issue:** `avahi-browse -t -r -p _ipp._tcp` prints "Internet Printer" in field 5, so `lan-service-resolve` could never PASS.
- **Fix:** Added `-k` (no-db-lookup) to both avahi-browse calls; unescape `\032` and `\064` when extracting instance names.
- **Files modified:** internal/verify-cups-mdns-live.sh
- **Commit:** 94dc3aa

### Plan-level deviation

**2. Task 3 experiment not executed.** The classifier denied the mutating remote commands after the first `avahi-daemon
--kill`. The user restarted the add-on manually and chose to proceed with classification `inconclusive`. The only host
mutation made by this plan was that one `--kill` (followed by the user's manual restart). No further mutating command was
run on haos-op3050-1.

**Total deviations:** 1 auto-fixed (1 bug), 1 plan-level (Task 3 skipped by user decision). **Impact:** diagnosis is
weaker than planned (no avahi conflict log captured) but the verifier gives an objective red/green signal for 21-05..21-07.

## Out-of-scope observations (not fixed)

- cupsd logs `Unknown directive IdleExitTimeout on line 33 (and 12) of /etc/cups/cupsd.conf` on every start. It is not
  found in `cups/` or `internal/`, so it probably comes from the upstream default conf in the base image. Candidate for a
  separate follow-up.

## Known Stubs

None.

## Threat Flags

None. The script only reads; the options object is never printed (whitelisted jq fields); stdout is IP-masked.

## Issues Encountered

- `gsd_run` was not on PATH in the executor shell; state close-out used `node /home/akentner/.claude/gsd-core/bin/gsd-tools.cjs`.

## Next Phase Readiness

Ready for 21-05 (startup guard). It should log avahi conflicts to a reachable sink (E4), re-register or fail loudly when the
claimed host name differs from `avahi_hostname`, and set `publish-aaaa-on-ipv4=no` when `avahi_use_ipv6` is false.
21-07 re-runs `internal/verify-cups-mdns-live.sh --assert` against the live host as the green signal.

## Self-Check: PASSED

- internal/verify-cups-mdns-live.sh exists and is executable.
- Commits 31dedc4 and 94dc3aa exist on main.
