---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 05
subsystem: infra
tags: [cups, avahi, mdns, airprint, dbus, startup-guard, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "21-04 diagnosis: avahi log went to a dead syslog sink (E4), service registered under a stale host name (E6), AAAA still published (lan-no-aaaa)"
provides:
  - "cups/avahi-guard.sh: sourced startup guard (avahi undaemonized, D-Bus claim check, bounded retry, degrade-and-continue)"
  - "run.sh refuses to start when generate_config.py fails (CR-02) and clears stale pid files"
  - "generate_config.py: shared hostname validation, /tmp/avahi-guard.env, fullmatch validation everywhere (WR-04), publish-aaaa-on-ipv4=no when avahi_use_ipv6 is false (D-10)"
  - "internal/verify-cups-avahi-guard.sh (docker: claim, lost, unsettled, refuse) and internal/verify-cups-hardening.sh (fast, docker-free)"
affects: [21-06, 21-07]

plan_head_before: 4a51dcad4954acca2226c1494874e4f4f834905f
plan_head_after: 9411a962426158c8abc0c83fcb7abaef5b4e5044
actuals:
  tokens: 8000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Sourced bash library with env-var tunables for tests and errexit-safe control flow (bashio may run with set -e)"
    - "Startup-only ordering guard: wait for D-Bus-reported settled state before starting the dependent daemon"
    - "Host-side module-import verifier with CUPS_ADDON_DIR override to prove tests can fail (RED proof)"

key-files:
  created:
    - cups/avahi-guard.sh
    - internal/verify-cups-avahi-guard.sh
    - internal/verify-cups-hardening.sh
  modified:
    - cups/run.sh
    - cups/generate_config.py
    - cups/Dockerfile

key-decisions:
  - "avahi runs in the foreground of a background job so its own log reaches the add-on log"
  - "Readiness comes from the D-Bus API (GetState/GetHostNameFqdn), not from process titles"
  - "Retry schedule 30 s then 90 s (3 attempts); after the last attempt continue under the actual name with an ERROR rather than exit"
  - "No new add-on option or schema field (D-05) and no watchdog (D-08); AVAHI_GUARD_* env vars are test tunables only"

requirements-completed: [D-05, D-08, D-09, D-10, D-11]

duration: n/a (single interactive executor session)
completed: 2026-10-03
status: complete
---

# Phase 21 Plan 05: Avahi startup guard, config refusal and IPv6 publish fix Summary

cupsd now starts only after avahi has reported a settled host name over D-Bus, avahi's own log lines reach `ha apps logs`,
a lost claim is retried with bounded backoff and then degraded loudly (never blocking), a failed or unsafe
`generate_config.py` stops the add-on before any daemon starts, and `avahi_use_ipv6: false` really removes the AAAA records.

## Accomplishments

- **Task 1 (tracer): startup guard.** `cups/avahi-guard.sh` (`avahi_guard_start` and helpers) is sourced by `run.sh` step 4. It
  launches `avahi-daemon` undaemonized (stderr becomes the add-on log), polls `GetState`/`GetHostNameFqdn`, requires state 2
  with an unchanged FQDN for 5 polls, logs `[avahi-guard] INFO: hostname claimed: <fqdn>` before `run.sh` waits for cupsd, and
  on a lost claim stops/restarts avahi (backoff 30 s, 90 s). After the last attempt it logs one ERROR and continues
  (`RESULT: degraded` or `unsettled`), leaving avahi running. `generate_config.py` writes the validated expectation to
  `/tmp/avahi-guard.env` through the same helper (`resolve_avahi_hostname`) as the conf `host-name=` line. The shutdown trap
  is now a `cleanup` function that also stops avahi so goodbye packets go out.
- **Task 2: CR-02 / WR-04.** `run.sh` exits 1 with `generate_config.py failed -- refusing to start` before anything starts.
  All 11 validation call sites use `fullmatch`, so a trailing newline is rejected. Proven RED/GREEN host-side and by the docker
  `refuse` scenario.
- **Task 3: D-10 completion.** `build_avahi_conf` emits `[publish]` / `publish-aaaa-on-ipv4=no` between `[server]` and
  `[reflector]` when `avahi_use_ipv6` is false and no `[publish]` section when true. In the claim scenario the container had a
  routable IPv6 address and avahi registered no IPv6 address record.

## Verification evidence

| Check | Result |
| ----- | ------ |
| `shellcheck -e SC1091 -e SC2034 cups/run.sh cups/avahi-guard.sh internal/verify-cups-*.sh`, `py_compile`, `hadolint` (plan ignore list) | clean |
| Local `docker build` of `cups/` (podman-emulated docker) before the Dockerfile commit | built OK |
| `bash internal/verify-cups-avahi-guard.sh` (claim, lost, unsettled, refuse) | all 18 assertions PASS |
| `bash internal/verify-cups-hardening.sh` | all PASS, 0.07 s |
| RED proof: `CUPS_ADDON_DIR=<copy with fullmatch -> match> bash internal/verify-cups-hardening.sh` | exit 1; FAIL for trailing-newline hostname (Test 1, guard env) and printer-name (Test 3) |
| TDD RED before the fix, run on the unmodified code: hardening Task 2 | 4 FAIL, Task 3 default-conf check FAIL |
| `bash internal/verify-cups-scaffold.sh` regression (incl. real `docker restart`) | ALL CHECKS PASSED (38 PASS) |
| `git diff 4a51dca HEAD -- cups/config.yaml` | empty (no option/schema change) |

## Task Commits

| Task | Commit | Description |
| ---- | ------ | ----------- |
| 1 | ab996cc | feat: avahi startup guard (library, run.sh wiring, env file, Dockerfile COPY, docker verifier) |
| 2 | 6d8414a | fix: refuse to start on failed config generation, fullmatch validation, hardening verifier, `refuse` scenario |
| deviation | e919f13 | fix: errexit-safe guard, clear stale pid files on restart |
| 3 | 9411a96 | fix: `publish-aaaa-on-ipv4=no`, hardening Tests, claim scenario extension |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Guard was not safe under bashio's errexit**
- **Found during:** final scaffold regression after Task 3
- **Issue:** `actual=$(avahi_guard_wait_settled)` returns non-zero for "timed out / avahi exited". run.sh runs under
  `with-contenv bashio`, where a bare failing assignment terminates the script silently, so the container exited
  instead of continuing. My `bash -c` harness had no errexit, so the first docker run of the scenarios did not catch it.
- **Fix:** `if actual=$(...); then rc=0; else rc=$?; fi`; `|| true` on `kill`/`wait` in `avahi_guard_stop`; `if` instead of
  `[ ] && cmd` in the guard and the `cleanup` trap function; the docker harness now runs under `set -e`. An extra ad-hoc run
  with a failing `avahi-daemon` confirmed 3 attempts, `RESULT: unsettled`, `EXIT=0` under errexit.
- **Files modified:** cups/avahi-guard.sh, cups/run.sh, internal/verify-cups-avahi-guard.sh
- **Commit:** e919f13 (guard/run.sh) and 9411a96 (harness `set -e`)

**2. [Rule 3 - Blocking] Stale pid files after a container restart**
- **Found during:** the same scaffold run (the `docker restart` UUID-stability check regressed)
- **Issue:** a container restart reuses the filesystem; `/run/dbus/dbus.pid` made dbus-daemon refuse to start and
  `/run/avahi-daemon/pid` made avahi report `Daemon already running on PID 85`. The old daemonized start only logged a
  non-fatal failure; the guard would have retried against a dead avahi for minutes.
- **Fix:** `run.sh` step 2 removes `/var/run/dbus/pid`, `/var/run/dbus/dbus.pid`, `/var/run/avahi-daemon/pid` (nothing runs yet
  at that point).
- **Commit:** e919f13

**3. [Rule 3 - Blocking] shellcheck version difference**
- shellcheck 0.11 reports SC2329 and the pre-commit pin 0.10.0.1 reports SC2317 for the EXIT-trap `cleanup` function in the
  new verifier, and SC2016 for the single-quoted harness script. Added targeted `# shellcheck disable=` directives; the first
  commit attempt was rejected by the hook and redone (single commit ab996cc, hooks on).

**Total deviations:** 3 (1 bug, 2 blocking). Impact: none on scope; commit 3 shipped slightly earlier than Task 3 content
because the fixes touched Task 1 files.

## Known limitations and follow-ups

- `cups/avahi-guard.sh` log text refers to "DOCS.md, Avahi startup guard"; that section does not exist yet and is the
  responsibility of plan 21-06 (docs, version bump).
- `cups/config.yaml` version is untouched (`0.1.0-15`); the version bump belongs to 21-06.
- The live proof (hostname survives restart, `_ipp._tcp` resolvable from the LAN, no AAAA) is plan 21-07; no command was run
  against haos-op3050-1 in this plan.
- Out of scope, unchanged: the `IdleExitTimeout` cupsd.conf warning (visible in every container log).
- The guard can only mask, not cure, a persistent foreign claimant of `cups.local`: after 3 attempts it publishes under the
  renamed host and logs an ERROR.
- Local verification ran on podman (docker CLI emulation, pasta networking: the container shares the workstation LAN, so avahi
  announced the throwaway names `cups-guard` / `cups-verify` there; none of the live names was used).

## Known Stubs

None.

## Threat Flags

None. The only new trust-boundary surface is `/tmp/avahi-guard.env`, written from the already-validated hostname
(alphanumerics and hyphens, T-21-11) and sourced by `run.sh`.

## Self-Check: PASSED

- Created files exist: cups/avahi-guard.sh, internal/verify-cups-avahi-guard.sh, internal/verify-cups-hardening.sh.
- Commits ab996cc, 6d8414a, e919f13, 9411a96 exist on this branch.
- No modifications to STATE.md / ROADMAP.md.
