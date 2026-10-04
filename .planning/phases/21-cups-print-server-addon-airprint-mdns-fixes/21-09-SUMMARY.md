---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 09
subsystem: testing
tags: [cups, avahi, mdns, live-verifier, watch, bash, stub-selftest, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "21-07 live proof that lost the host name; 21-08 isolated local test containers and the quiet-window cause"
provides:
  - "internal/verify-cups-mdns-live.sh --watch: timed, read-only, mechanically classified observation (PASS / FAIL / INVALID / PASS-UNVERIFIED-QUIET)"
  - "internal/verify-cups-watch-selftest.sh: stubbed ssh/avahi/docker proof of the classification and the read-only contract"
  - "21-REVIEW-DISPOSITION.md settled (6 closed with commit evidence, 14 deferred with a reason) and the diagnosis correction on record"
affects: [21-10, phase-21-verification]

tech-stack:
  added: []
  patterns:
    - "Watch result is falsifiable: events history must be verified for a closing PASS, otherwise exit 4"
    - "Stub tools on PATH answering by remote command words, scenario state in files"

key-files:
  created:
    - internal/verify-cups-watch-selftest.sh
  modified:
    - internal/verify-cups-mdns-live.sh
    - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-REVIEW-DISPOSITION.md
    - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-07-SUMMARY.md
    - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-VERIFICATION.md

key-decisions:
  - "continuity and host-name-conflict are watch-only checks (outside run_checks) so `--assert` output stays byte-identical to the pre-change script (proved against a1ace38 in the self-test)"
  - "A round is quiet unless a cups container was running during it or a matching local event happened at or before its end; FAIL needs a failing quiet round, so a failure after a local cups create/start event is INVALID, not FAIL"
  - "Container log is read once per round with `docker logs --since <StartedAt>` and filtered locally; no other new remote command shape"
  - "D-08 over-read in cups/ comments and DOCS is only recorded (ledger carry-forward), cups/ is untouched"

patterns-established:
  - "Do not run podman/docker verifiers on the workstation during a live proof: written into the live verifier header"

requirements-completed: [D-07, D-10, D-11, D-12]

plan_head_before: 7b6d8a31e24b9f848d1fd6ce8d13b426519d196b
plan_head_after: 9f12447b8942c4f77e2f105664ea05317e8f11c8
actuals:
  tokens: 11900
  tasks: 3
  commits: 4

completed: 2026-10-04
status: complete
---

# Phase 21 Plan 09: Live verifier watch mode and ledger cleanup Summary

**`verify-cups-mdns-live.sh --watch` repeats the read-only checks on a fixed cadence and ends with one mechanically
derived result line (PASS / FAIL / INVALID / PASS-UNVERIFIED-QUIET) that cannot be satisfied by a restart, an avahi
host-name conflict, a non-quiet workstation or an unverifiable local-events history; the review ledger and the
diagnosis wording are corrected.**

## Task 1 (tracer): `--watch` end to end against stubs

- The Step 6 checks moved into `run_checks`; `--assert` output is byte-identical to the pre-change script (the
  self-test compares both runs against stubs, baseline `a1ace38`) and prints no `WATCH` lines.
- New options `--watch MINUTES`, `--watch-seconds N`, `--interval S` (default 120, min 1), mutually exclusive with
  `--diagnose`; `--settle-wait` applies once before round 1. Rounds run at `start + n*interval` (no drift).
- The IP masker uses `sed -u -E`, so a masked 30-minute watch streams. The header documents the options, exit codes
  and the quiet-window rule (no podman/docker verifiers on the workstation during a live proof).
- `internal/verify-cups-watch-selftest.sh`: stubs for `ssh`, `avahi-*` and a local `docker`; scenario state in files.
- Commit `66aa4ae`.

## Task 2 (TDD): classification, quiet window, continuity, milestones, conflict, read-only contract

- Per round: `WATCH round=n quiet=yes|NO:<names>|unknown` from the workstation's `docker ps` (name or image contains
  `cups`, case-insensitive), a `continuity` check (StartedAt unchanged, add-on state started), and
  `host-name-conflict` (no `Host name conflict` in `docker logs --since <StartedAt>`).
- After the last round: `WATCH MILESTONES: age+2m=.. age+10m=.. age+30m=..`, `WATCH QUIET-WINDOW: since=..
  container-start=.. covers-container-start=yes|no events=OK|UNVERIFIED|UNAVAILABLE`, `WATCH SUMMARY` (rounds,
  duration, first failure with round/t/age, quiet violations, restarts) and exactly one result line:
  PASS 0, FAIL 1, INVALID 3, PASS-UNVERIFIED-QUIET 4. The first failing round prints a `WATCH CONTEXT` block with up to
  40 matching container-log lines.
- The post-hoc `docker events --since <quiet-window start>` defaults to the add-on container's StartedAt, so a local
  cups container created between the restart and the first round is found (test 3); `--quiet-since` takes
  `container-start`, `watch-start`, an epoch or an ISO time (test 3b). Both the docker and the podman event shapes
  are parsed. `events=OK` needs podman with a persistent event logger or an event within 900 s of the window start.
- RED: `bash internal/verify-cups-watch-selftest.sh` against the Task 1 loop failed 44 assertions on the planned
  behavior (target test "summary names round 3, its t and age"); `gsd_run check tdd-red-evidence` returned
  `RED_EVIDENCE_OK` (record built from the self-test's PASS/FAIL lines as TAP, scratch file, not committed).
  Commit `7ee03b6`. The plan's own RED proof against the pre-plan script
  (`LIVE_SCRIPT=<git show a1ace38:internal/verify-cups-mdns-live.sh>`) exits 1 with 59 failing assertions (`--watch`
  is unknown there).
- GREEN: all nine tests (1-9 including 3b) pass, `RESULT: PASS` in about 35 s. Exit codes observed: 0 pass, 1
  first-FAIL, 3 quiet-violation and gap-event scenarios, 4 docker engine with empty history / failing events command /
  no engine. The gap-event scenario's recorded `docker events` arguments show `--since` equal to the container's
  StartedAt epoch. No output line is exactly `WATCH RESULT: PASS` in the unverifiable scenarios. Commit `144a9ad`.
- Read-only contract (test 7): every remote command matches a reader whitelist and no mutating verb. Shapes seen:
  `true`, `ha apps info <slug> --raw-json`, `docker ps`, `docker inspect`, `docker logs`, `docker logs --since`,
  `docker exec <container> cat|dbus-send|timeout`.
- `bash internal/verify-cups-hardening.sh` still prints `RESULT: PASS`; shellcheck (`-e SC1091 -e SC2034`) is clean.

## Task 3: ledger, diagnosis note, carry-forward

- `21-REVIEW-DISPOSITION.md`: columns `Disposition` and `Evidence or reason`. CR-02 and WR-04 closed by `6d8414a`,
  WR-05 and WR-09 by `e66e7ef`, WR-07 and IN-06 by `2e92a39` (each confirmed with `git show --stat`). The other 14 are
  `deferred` with one line of reason; none left `open`. "Carry-forward notes" list the D-08 wording over-read in
  cups/avahi-guard.sh, cups/run.sh and cups/DOCS.md (needs a cups/ change: plans 21-11/21-12 or the next cups
  release), the optional iPhone/Mac check and the prettier exclusion of `.planning/`.
- `21-07-SUMMARY.md` and `21-VERIFICATION.md` got append-only diagnosis paragraphs (9 and 17 added lines, 0 deleted):
  own test container, journal timing, "strongly indicated, confirmed by timing; final confirmation = quiet observation
  in plan 21-10", truths #13/#14 stay open. No literal IP addresses in any added line.
- The plan's Task 3 verify command passes (run from a script file, same commands).
- Commit `9f12447`.

## TDD Gate Compliance

Task 2: RED commit `7ee03b6` (`test(21-09)`) precedes GREEN commit `144a9ad` (`feat(21-09)`); RED evidence recorded
above. No refactor commit.

## Deviations from Plan

### Interpretations

**1. [Clarification] Watch-only extra checks.** `host-name-conflict` is implemented beside `run_checks` rather than
inside it: the plan says `--assert` keeps its exact output, and the byte-for-byte comparison against `a1ace38` only
holds that way.

**2. [Clarification] Precedence with post-hoc events.** The plan orders FAIL before INVALID by "a quiet round failed".
Rounds after a matching local container event are not quiet, so a failure after such an event is INVALID, not FAIL;
events dated after a failing round do not taint it (but still make the overall result INVALID, as the plan states
for an event inside the window). Test 3 covers this.

### Auto-fixed Issues

None beyond fixing stub typos and a mis-wrapped phrase in the appended paragraph during development.

**Total deviations:** 0 auto-fixed, 2 interpretations. No scope change; `git diff --stat -- cups/` is empty.

## Known Stubs

None (the self-test's stubs are test doubles, not product stubs).

## Threat Flags

None. T-21-24 mitigated (reader whitelist test), T-21-25 mitigated (`--mask` unchanged, options object never printed,
no addresses in the appended notes), T-21-26 and T-21-SC accepted as planned.

## Notes for plan 21-10

- Use `--quiet-since <epoch>` for the moment the quiet promise began; the default window starts at the container
  start. Only `WATCH RESULT: PASS` (exit 0) closes truths #13 and #14; exit 4 (`PASS-UNVERIFIED-QUIET`) must be rejected.
- Do not start any podman/docker verifier on the workstation while the watch runs.
- No live host was contacted by this plan.

## Self-Check: PASSED

- internal/verify-cups-watch-selftest.sh, internal/verify-cups-mdns-live.sh and the three `.planning` documents exist.
- Commits 66aa4ae, 7ee03b6, 144a9ad, 9f12447 exist on main.
- Self-test `RESULT: PASS`, hardening verifier `RESULT: PASS`, shellcheck clean, `cups/` unchanged.
