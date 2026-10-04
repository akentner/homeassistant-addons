---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 08
subsystem: testing
tags: [cups, avahi, mdns, test-isolation, podman, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "21-05 avahi startup guard and guard verifier; 21-07 live proof that lost the host name"
provides:
  - "internal/cups-test-isolation.sh: single choke point for every local cups container start (refusal + LAN-mDNS isolation)"
  - "Guard verifier `isolation` scenario with a non-isolated negative control"
  - "Host-side hardening check that fails a verifier bypassing the helper (RED-proven)"
affects: [21-09, 21-10, phase-21-verification]

tech-stack:
  added: []
  patterns:
    - "Sourced test library wraps every `docker run` of the add-on image; `ip link set <if> multicast off` under the image's own /init entrypoint"

key-files:
  created:
    - internal/cups-test-isolation.sh
  modified:
    - internal/verify-cups-avahi-guard.sh
    - internal/verify-cups-scaffold.sh
    - internal/verify-cups-paperless-upload.sh
    - internal/verify-cups-hardening.sh

key-decisions:
  - "Isolation by `multicast off` on non-lo interfaces (NET_ADMIN), not `--network none`: avahi still claims its name and reaches running, cupsd Listen and host.docker.internal stub servers keep working"
  - "Refusal layer validates the mounted options.json before docker is called; a syntactically invalid hostname is allowed through so the `refuse` scenario still tests run.sh's own rejection"
  - "cups_lan_run exists as the only non-isolated entry point, still bound to the unique-name rule"

patterns-established:
  - "Never start a cups container without internal/cups-test-isolation.sh; enforced by the static scan in internal/verify-cups-hardening.sh"

requirements-completed: [D-11, D-12]

plan_head_before: 04a4f6accd48f7b33938685393847fb762b907a1
plan_head_after: 7db64ee7b5e3dcb14b5ee8cdeceeed235887954d
actuals:
  tokens: 8400
  tasks: 3
  commits: 3

completed: 2026-10-04
status: complete
---

# Phase 21 Plan 08: Local test container isolation Summary

**Every local cups verifier now starts its containers through one helper that refuses the default host name `cups`
and switches multicast off on the container's real interfaces, so a test container can no longer announce a name on
the LAN; a host-side check, RED-proven against the pre-change paperless verifier, keeps it that way.**

## Task 1 (tracer): helper and guard verifier

- `internal/cups-test-isolation.sh` provides `cups_test_hostname`, `cups_isolated_run`, `cups_isolated_bash` and
  `cups_lan_run`, all through one internal docker wrapper that honours `CUPS_TEST_TIMEOUT`. The mute snippet is
  overridable with `CUPS_TEST_MUTE_SNIPPET` (test-only knob).
- `internal/verify-cups-avahi-guard.sh`: claim, refuse and the harness go through the helper; the IPv6 log check moved
  out of `claim` into the new `isolation` scenario's control container. New scenario `isolation`: the isolated container
  claims on the guard's first attempt, D-Bus reports its name, and its log has no "Joining mDNS multicast group" for
  any interface except `lo`; the non-isolated control joins on `wlan0` (PASS), so the assertion is capable of failing.
- Full run: `RESULT: PASS` for claim, lost, unsettled, refuse and isolation (59 s).
- RED proof: `CUPS_TEST_MUTE_SNIPPET=: bash internal/verify-cups-avahi-guard.sh --scenario isolation` exits 1 with
  `FAIL: isolated container: avahi joined mDNS on a real interface: Joining mDNS multicast group on interface
  wlan0.IPv4 with address 192.168.178.108.` The unmodified run exits 0.
- The `refuse` scenario still reports a non-zero container exit, `generate_config.py failed` and no `[avahi-guard]`
  line: the helper lets the invalid-name fixture through to the add-on's own refusal.
- Commit `6007542`.

## Task 2: scaffold and paperless verifiers

- Paperless: all four fixtures carry `avahi_hostname` from `cups_test_hostname` (`pl-happy`, `pl-disabled`, `pl-retry`,
  `pl-resil`; the disabled fixture's heredoc is now unquoted) and all four containers start via `cups_isolated_run`.
  Stub servers stay reachable through `host.docker.internal`. ALL CHECKS PASSED.
- Scaffold: `start_container` and the debug-tier container use `cups_isolated_run`; new assertion "no mDNS multicast
  group joined on any interface except lo" (log captured into a variable first). `cupsd Listen bound to a detected
  interface IP`, the UUID-recreation checks and all others unchanged and green. ALL CHECKS PASSED.
- `git diff --stat -- cups/` is empty: no add-on change, no version bump, no rebuild.
- Commit `0881923`.

## Task 3: hardening check (TDD)

- New section "local test containers cannot claim the live host name (isolation, Plan 21-08)": helper refusals
  (no options.json, no `avahi_hostname`, `"cups"`, empty, no mount, also for `cups_isolated_bash` and `cups_lan_run`)
  exit 2 with an empty docker log; acceptance logs `--cap-add NET_ADMIN`, the image and `multicast off` for the
  isolated entry points and none for `cups_lan_run`; `cups_test_hostname` format/length/tag rules; static scan of every
  `internal/verify-cups-*.sh` with a `docker build` line for raw `docker|podman run|create` and a missing helper source.
  `CUPS_VERIFIER_DIR` selects the scanned directory. Stub docker only, 0.4 s runtime.
- RED proof: a scratch copy of `internal/` with `git show a1ace38:internal/verify-cups-paperless-upload.sh` run via
  `CUPS_VERIFIER_DIR=<copy>` exits 1 with `FAIL: internal/verify-cups-paperless-upload.sh contains no raw docker run /
  docker create / podman run (found: docker run --rm -d --name "${HAPPY_CONTAINER}" \)` and `FAIL: ...sources
  cups-test-isolation.sh`. The normal run prints `RESULT: PASS` (exit 0).
- Commit `7db64ee`.

## TDD Gate Compliance

Task 3 is `tdd="true"` but its subject (the helper) was built in Task 1 and the converted verifiers in Task 2, as the
plan orders it. The RED state is therefore demonstrated against the pre-change paperless verifier copy rather than by a
separate failing-test commit; there is no standalone `test(...)` commit preceding a `feat(...)` commit for the check
itself. RED evidence and GREEN run are recorded above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Flaky device-uri check in the paperless verifier**
- **Found during:** Task 2 (first full run)
- **Issue:** `lpstat -v verify-pdf-queue` right after `wait_for_queue` printed nothing once in four runs (FAIL "device
  uri unexpected: "), because run.sh's UUID-fixup restarts cupsd shortly after first readiness. Later runs passed, so
  it is a timing race in the existing check, not an effect of the isolation.
- **Fix:** the check now polls up to 15 s for a non-empty answer.
- **Files modified:** internal/verify-cups-paperless-upload.sh
- **Commit:** 0881923

**Total deviations:** 1 auto-fixed. No scope change.

## Notes

- The diagnosis (own paperless test containers announcing `cups.local` through podman's pasta networking, journal
  timing 09:14:55 vs 09:14:57) is taken from the plan; this plan removes the cause, final confirmation is the quiet
  observation in plan 21-10. Not independently re-confirmed here.
- The negative control container announces a unique throwaway name (`cups-vf-ctl-<stamp>`) on the real LAN for about
  a minute per guard-verifier run; do not run the guard verifier during a live proof.
- Local docker is podman emulation; the verifier runs here used the real image built from `cups/` at HEAD.

## Known Stubs

None.

## Threat Flags

None. T-21-21 and T-21-23 mitigated as planned (helper refusal and isolation; RED-proven static scan); T-21-22
(`--cap-add NET_ADMIN` on throwaway containers) accepted as planned.

## Self-Check: PASSED

- internal/cups-test-isolation.sh, the four modified verifiers and this file exist.
- Commits 6007542, 0881923, 7db64ee exist on main.
- shellcheck (`-e SC1091 -e SC2034`) clean on all five scripts; hardening, guard, scaffold and paperless verifiers all
  green.
