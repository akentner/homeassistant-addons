---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 10
subsystem: testing
tags: [cups, avahi, mdns, live-proof, watch, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "21-08 isolated local test containers; 21-09 --watch mode of the live verifier"
provides:
  - "Three quiet 32-minute live observations of cups 0.1.0-16 on haos-op3050-1, all WATCH RESULT: PASS"
affects: [phase-21-verification]

key-decisions:
  - "Optional negative control (Task 4) skipped: it would deliberately rename the live host and the three PASS observations already carry the verdict"
  - "Restart 1 used the earlier quiet-since T0 (14:08:08Z) instead of a fresh TP, because the promise was continuous since `idle`; this window is a superset of the planned one"

requirements-completed: [D-07, D-10, D-11, D-12]

completed: 2026-10-04
status: complete
---

# Phase 21 Plan 10: Quiet live proof Summary

**The fixed host name `cups.local` was kept on the live add-on (0.1.0-16, unchanged) in three independent 32-minute
observations: the current boot and two plain restarts. Every watch ended `WATCH RESULT: PASS` with `events=OK`, every
round `quiet=yes`, no restart, no `Host name conflict`.**

All three restarts/observations were run by the human (restart) or read-only by the agent. No agent ran a mutating
command. Transcripts below are masked; none contains a dotted-quad IPv4 address.

## Observations

| # | Boot | Container start | Result | Rounds | Quiet |
|---|------|-----------------|--------|--------|-------|
| 1 | current boot | 2026-10-04T07:47:21Z | PASS | 17 / 32:10 | 17 of 17 `quiet=yes` |
| 2 | restart 1 | 2026-10-04T14:42:01Z | PASS | 17 / 32:10 | 17 of 17 `quiet=yes` |
| 3 | restart 2 | 2026-10-04T15:21:27Z | PASS | 17 / 32:11 | 17 of 17 `quiet=yes` |

```
Observation 1
WATCH QUIET-WINDOW: since=2026-10-04T14:08:08Z container-start=2026-10-04T07:47:21Z covers-container-start=no events=OK
WATCH MILESTONES: age+2m=PASS age+10m=PASS age+30m=PASS
WATCH SUMMARY: rounds=17 duration=32:10 first-failure=none quiet-violations=0 restarts=0
WATCH RESULT: PASS

Observation 2 (restart 1)
WATCH QUIET-WINDOW: since=2026-10-04T14:08:08Z container-start=2026-10-04T14:42:01Z covers-container-start=yes events=OK
WATCH MILESTONES: age+2m=PASS age+10m=PASS age+30m=PASS
WATCH SUMMARY: rounds=17 duration=32:10 first-failure=none quiet-violations=0 restarts=0
WATCH RESULT: PASS

Observation 3 (restart 2)
WATCH QUIET-WINDOW: since=2026-10-04T15:15:09Z container-start=2026-10-04T15:21:27Z covers-container-start=yes events=OK
WATCH MILESTONES: age+2m=PASS age+10m=PASS age+30m=PASS
WATCH SUMMARY: rounds=17 duration=32:11 first-failure=none quiet-violations=0 restarts=0
WATCH RESULT: PASS
```

Notes per observation:

- **1 (current boot):** `covers-container-start=no` is expected: the boot is about 6.5 h older than the quiet promise, so
  its earlier part is covered only by the conflict and continuity checks. The restarted boots are the strong evidence.
- **2 and 3:** `covers-container-start=yes`; the events history is queried from before the restart, so a container that
  started and stopped between restart and first round would have been seen.
- **Guard claim line (restart 2, from the container log):** `[avahi-guard] INFO: hostname claimed: cups.local (attempt 1/3)`.
  Restart 1: `hostname claimed: cups.local (attempt 1/3)` and `Server startup complete. Host name is cups.local.`
  No `Host name conflict` line in any boot's log.
- **Workstation:** lap-aleken-tux1 (podman, journald event logger) ran only `mosq`, `ha-a`, `ha-b` during all windows;
  no cups container. The watch only sees this workstation; other LAN devices are outside its evidence.

## Verdict per verification truth

| Truth | Checks | Verdict |
|-------|--------|---------|
| #13 fixed host name kept | `daemon-fqdn`, `lan-forward-v4`, `host-name-conflict`, `continuity` PASS in all 51 rounds of all three boots | closed by live evidence |
| #14 service resolves at the fixed name | `lan-service-resolve` PASS in every round; milestones +2/+10/+30 min PASS on both restarted boots | closed by live evidence |
| D-10 | `lan-no-aaaa` PASS in every round | holds |
| D-07 | `conf-reflector`, `slot-exhaustion` PASS in every round | holds |
| D-11, D-12 | no host-name loss over time, host name not claimed by local test containers | holds in the observed windows |

## Diagnosis status

Confirmed by the quiet observation: with no local cups container on the workstation, the host name stayed `cups.local`
for three boots, including the +30 min point where the 21-07 proof had lost it. Local test containers claiming `cups.local`
(plan 21-08) are the cause; the add-on itself needed no change. Plans 21-11/21-12 (parked as `*-PLAN-OUTLINE.md`) are not
required.

## Deviations from Plan

1. **Task 4 (optional negative control) skipped** at the orchestrator's recommendation; it needs a deliberate rename of the
   live host and the verdict does not depend on it. Not asked of the user as a hard gate; the mechanism remains supported
   by the 21-07 timing evidence and the 21-08 isolation proof.
2. **Restart 1 quiet-since:** `T0` of observation 1 was used instead of a fresh `TP` recorded before the instruction.
   The promise was continuous, and the window is a superset of the planned one.
3. **Log excerpt source:** `ha apps logs` returned only the last 100 lines, so the boot excerpt was read with a read-only
   `docker logs` on the host instead.

## Next

Phase gates (code review, verification), then `/gsd-verify-work 21` to refresh 21-VERIFICATION.md.

## Self-Check: PASSED
