---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 01
subsystem: infra
tags: [cups, avahi, mdns, airprint, home-assistant-addon, docker, dbus]

requires: []
provides:
  - "cups/ add-on scaffold (config.yaml, build.yaml, Dockerfile, run.sh, generate_config.py) forking f1c878cb_cups"
  - "generated avahi-daemon.conf with enable-reflector=no, fixed host-name=, use-ipv6=no (the permanent AirPrint/mDNS fix)"
  - "printers[] list-of-objects HA options schema ({name, uri, enabled}) with uri typed str + runtime scheme-allowlist validation"
  - "internal/verify-cups-scaffold.sh — real docker build+run smoke test proving the tracer end-to-end"
affects: [21-02-docs-and-rollout-tracking, 21-03-rollout]

actuals:
  tokens: 3925
  tasks: 3
  commits: 1

tech-stack:
  added: [cups, cups-filters, avahi, avahi-tools, dbus (apk packages, no new language/framework)]
  patterns:
    - "Generated config file at startup (D-09), never sed-patched — mirrors gatus/generate_config.py"
    - "argv-array + shlex.quote() for all subprocess construction that embeds user-supplied values (T-21-01)"
    - "list-of-objects HA options schema for printers (mirrors phone-logger's adapter-list pattern)"

key-files:
  created:
    - cups/config.yaml
    - cups/build.yaml
    - cups/Dockerfile
    - cups/run.sh
    - cups/generate_config.py
    - internal/verify-cups-scaffold.sh
  modified: []

key-decisions:
  - "printers[].uri HA options-schema type: str (permissive), NOT url — Task 1 checkpoint decision, pre-recorded by the user before this run started. Runtime scheme-allowlist validation (ipp/ipps/socket/usb/dnssd/lpd/http) lives in generate_config.py instead, so it never re-triggers the D-03 migration cost if a new CUPS URI scheme needs support later."
  - "lpadmin printer registration uses -m drv:///sample.drv/generic.ppd (static generic driver), not -m everywhere (CUPS driverless IPP-Everywhere) — everywhere performs a live IPP capability query against the device AT REGISTRATION TIME, so a printer that is powered off when the add-on (re)starts would fail to register at all. Discovered empirically during the Task 2 smoke test with an intentionally-unreachable fixture URI (192.0.2.10, TEST-NET-1) — exactly the contingency the plan's action text anticipated and pre-authorized a fallback for."
  - "Dockerfile runs `addgroup root lpadmin` — CUPS restricts admin operations (lpadmin) to members of the `lpadmin` SystemGroup; root is not a member of that group by default even when the whole container runs as root."

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-07, D-08, D-09, D-10, D-11]

coverage:
  - id: D1
    description: "cups/ add-on scaffold with full 4-file pattern + generate_config.py, matching every other add-on's structure"
    requirement: "D-01, D-02"
    verification:
      - kind: other
        ref: "python3 internal/validate-addon-config.py cups"
        status: pass
    human_judgment: false
  - id: D2
    description: "Generated /etc/avahi/avahi-daemon.conf carries enable-reflector=no, host-name=<avahi_hostname>, use-ipv6=no by default"
    requirement: "D-07, D-09, D-10, D-11"
    verification:
      - kind: e2e
        ref: "internal/verify-cups-scaffold.sh (docker build+run, docker exec cat /etc/avahi/avahi-daemon.conf assertions)"
        status: pass
    human_judgment: false
  - id: D3
    description: "One fixture printer registers via lpadmin against a live cupsd, proving the printers[] tracer path end-to-end"
    requirement: "D-03, D-04"
    verification:
      - kind: e2e
        ref: "internal/verify-cups-scaffold.sh (docker exec lpstat -p testprinter)"
        status: pass
    human_judgment: false
  - id: D4
    description: "cups/config.yaml exposes exactly the D-05 option surface (avahi_reflector, avahi_hostname, avahi_use_ipv6, printers, log_level) with host_network: true"
    requirement: "D-05"
    verification:
      - kind: other
        ref: "cups/config.yaml (manual read: schema block + host_network: true)"
        status: pass
    human_judgment: false
  - id: D5
    description: "No slot-exhaustion watchdog anywhere in the add-on (D-08) — structurally impossible with enable-reflector=no"
    verification:
      - kind: e2e
        ref: "internal/verify-cups-scaffold.sh (docker logs grep 'No slot available for legacy unicast reflection' — must be absent)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Every repo-wide static gate (config schema, yamllint, Dockerfile ARG scope, hadolint, shellcheck, py_compile) passes on the new cups/ files with zero workflow/pre-commit edits"
    verification:
      - kind: other
        ref: "python3 internal/validate-addon-config.py cups && yamllint cups/config.yaml cups/build.yaml && ./internal/validate-dockerfile-args.sh && hadolint --ignore DL3008 --ignore DL3018 --ignore DL3059 --ignore DL4006 --ignore DL3016 cups/Dockerfile && shellcheck -e SC1091 -e SC2034 cups/run.sh && bash -n cups/run.sh && python3 -m py_compile cups/generate_config.py"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-09-26
status: complete
---

# Phase 21 Plan 01: cups/ Add-on Scaffold Summary

**cups/ add-on forked from f1c878cb_cups with a generated avahi-daemon.conf (reflector off, fixed hostname, IPv6 off) and a list-of-objects printers schema, proven end-to-end by a real docker build+run smoke test registering one fixture printer.**

## Performance

- **Duration:** 35 min
- **Tasks:** 3 (1 checkpoint:decision — pre-resolved before this run, 1 tracer, 1 auto)
- **Files modified:** 6 (all new)

## Task 1: Decision (printers[].uri schema type)

This checkpoint was already resolved before this execution run started — the user selected `str` (permissive) with
runtime scheme-allowlist validation over HA's built-in `url` schema type, because `vol.Url`'s acceptance of non-http
CUPS URI schemes (`ipp://`, `socket://`, `usb://`, `dnssd://`, `lpd://`) was unverified and a wrong choice here is a
costly (D-03) schema migration for every installed user. No code was written for this task; it only gates Task 2's
schema shape, which is implemented per the recorded decision.

## Accomplishments

- Forked the third-party `f1c878cb_cups` add-on into a new, own `cups/` add-on (D-01, D-02) with the full 4-file
  pattern + `generate_config.py` config-bridge script
- `generate_config.py` renders `/etc/avahi/avahi-daemon.conf` carrying all three permanent AirPrint/mDNS fixes:
  `enable-reflector=no` (D-07), a fixed `host-name=` from `avahi_hostname` (D-11), `use-ipv6=no` (D-10)
- `printers` is a list-of-objects HA options schema (`{name, uri, enabled}`, D-03/D-04) from the start; each valid
  entry is registered via `lpadmin` at container startup, built from a `shlex.quote()`-escaped argv list
- `internal/verify-cups-scaffold.sh` proves the tracer end-to-end via a real `docker build` + `docker run`: the
  generated avahi-daemon.conf carries the fixture's values, one fixture printer registers and is visible via
  `lpstat -p`, and zero occurrences of the reflector slot-exhaustion log message appear
- Every repo-wide static gate (`validate-addon-config.py`, `yamllint`, `validate-dockerfile-args.sh`,
  `hadolint`, `shellcheck`, `bash -n`, `py_compile`) passes on the new files with zero fixes needed and zero
  workflow/pre-commit config edits

## Task Commits

1. **Task 2: Scaffold cups/ add-on: Avahi fix + one printer end-to-end** - `d96286c` (feat)
2. **Task 3: Pass every repo-wide static gate on the new cups/ files** - no additional commit; every gate passed
   cleanly against Task 2's committed files, so there was nothing to fix or re-commit

**Plan metadata:** (this commit, `docs(21-01): complete cups/ scaffold plan`)

## Files Created/Modified

- `cups/config.yaml` - HA manifest + full D-05 options/schema (`avahi_reflector`, `avahi_hostname`,
  `avahi_use_ipv6`, `printers` list-of-objects, `log_level`), `host_network: true`, ports 631/tcp+udp
- `cups/build.yaml` - `build_from: amd64-base:3.24` + `args.VERSION: "0.1.0"` (apk-only, no upstream binary version
  to pin, mirrors `network-tools/build.yaml`)
- `cups/Dockerfile` - single-stage HA base + `apk add cups cups-filters avahi avahi-tools dbus python3` +
  `addgroup root lpadmin` (Rule 1 fix, see Deviations) + standard LABELS boilerplate
- `cups/run.sh` - bashio config reads, `generate_config.py` invocation, dbus/avahi/cupsd startup sequence
  (mirrors network-tools' incantation), bounded readiness wait, retrying printer registration, `cupsctl LogLevel`
  mapping, SIGTERM/SIGINT forwarding to `cupsd`
- `cups/generate_config.py` - renders `/etc/avahi/avahi-daemon.conf` + `/tmp/register-printers.sh` from
  `/data/options.json`, with `NAME_RE` validation on `avahi_hostname`/`printers[].name` and a URI-scheme allowlist
  on `printers[].uri` (T-21-01 mitigation — argv-array + `shlex.quote()`, never an interpolated shell string)
- `internal/verify-cups-scaffold.sh` - docker build+run smoke test: fixture `options.json`, four assertions
  (host-name, use-ipv6, enable-reflector, printer registration), zero-tolerance grep for the slot-exhaustion message

## Decisions Made

- **printers[].uri type: `str`** (Task 1, pre-recorded) — permissive, with runtime scheme-allowlist validation in
  `generate_config.py` rather than HA's `url` type, whose acceptance of `ipp://`/`socket://`/`usb://`/`dnssd://`/
  `lpd://` schemes was unverified and would have been a costly (D-03) lock-out risk if wrong.
- **`-m drv:///sample.drv/generic.ppd` instead of `-m everywhere`** for `lpadmin` printer registration — see
  Deviations below; this was empirically forced by the smoke test, not a plan-time choice.
- **`addgroup root lpadmin` in the Dockerfile** — see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] lpadmin admin operations require `lpadmin` SystemGroup membership**
- **Found during:** Task 2 (initial `internal/verify-cups-scaffold.sh` run)
- **Issue:** `lpadmin -p testprinter -v ... -E -m everywhere` failed with `lpadmin: Forbidden`. Alpine's cups
  package ships `SystemGroup lpadmin` in `/etc/cups/cups-files.conf`; CUPS checks group membership (not UID) for
  admin operations (`CUPS-Add-Modify-Printer` etc.), and root's default group list does not include `lpadmin` even
  when the whole container runs as root.
- **Fix:** Added `RUN addgroup root lpadmin` to `cups/Dockerfile` (verified with a debug build: `getent group
  lpadmin` shows `lpadmin:x:102:root` afterward).
- **Files modified:** `cups/Dockerfile`
- **Verification:** `internal/verify-cups-scaffold.sh` printer-registration assertion passes.
- **Committed in:** `d96286c` (Task 2 commit)

**2. [Rule 1 - Bug] `-m everywhere` requires the printer to be live-reachable at registration time**
- **Found during:** Task 2 (same smoke-test run, after fix #1)
- **Issue:** `lpadmin ... -m everywhere` (CUPS driverless IPP-Everywhere model) performs a live IPP capability
  query against the device URI when the queue is created. The plan's own fixture intentionally used an
  unreachable TEST-NET-1 address (`192.0.2.10`) and failed with `Unable to connect to 192.0.2.10:631: Host is
  down`. In production this means any printer that is powered off or unreachable at add-on (re)start would fail
  to register at all — defeating the purpose of a persistent print queue for a home printer that isn't always on.
  The plan's action text explicitly pre-authorized this exact fallback ("fall back to `-m drv:///sample.drv/
  generic.ppd` ... if `-m everywhere` proves unavailable during the Task 2 smoke test").
- **Fix:** Switched `generate_config.py`'s `lpadmin` argv to `-m drv:///sample.drv/generic.ppd` — a static generic
  PostScript driver that registers the queue unconditionally; CUPS only contacts the device when a job is
  actually printed. (`lpadmin` emits a non-fatal "Printer drivers are deprecated" notice, which does not affect
  registration.)
- **Files modified:** `cups/generate_config.py`
- **Verification:** `internal/verify-cups-scaffold.sh` printer-registration assertion passes (`lpstat -p
  testprinter` reports the printer registered even though its URI is unreachable).
- **Committed in:** `d96286c` (Task 2 commit)

**3. [Rule 1 - Bug] Transient race between `lpstat -r` readiness and lpadmin's admin interface**
- **Found during:** Task 2 (same smoke-test run, after fix #2)
- **Issue:** Even after fix #1, the very first `lpadmin` call issued by `run.sh` immediately upon `lpstat -r`
  first reporting the scheduler up intermittently failed with `Unable to connect to server: Bad file descriptor`
  or `Unauthorized`, while a manual retry a few seconds later (or in a fresh debug session) succeeded every time.
  `lpstat -r`'s "scheduler is running" check does not guarantee cupsd's admin/IPP interface has finished its own
  internal setup.
- **Fix:** `run.sh` now retries `sh /tmp/register-printers.sh` up to 5 times with a 1s pause between attempts.
  `lpadmin` is idempotent, so retrying after a transient failure is safe.
- **Files modified:** `cups/run.sh`
- **Verification:** `internal/verify-cups-scaffold.sh` passed reliably after this fix (verified via repeated runs).
- **Committed in:** `d96286c` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs discovered by actually running the tracer against a real
container, not architectural changes). All three were necessary for the tracer's stated goal ("one printer
registered and reachable... proven by a real docker build+run smoke test") to be genuinely true rather than
apparently true. No scope creep — no new files, no schema changes beyond what the plan already specified.
**Impact on plan:** Task 3's static gates (`validate-addon-config.py`, `yamllint`, `validate-dockerfile-args.sh`,
`hadolint`, `shellcheck`, `py_compile`) all passed cleanly against the Task 2 files as committed — no further
fixes were needed, so Task 3 produced no additional commit.

## Issues Encountered

None beyond the three deviations documented above, all resolved during Task 2's own verify loop before that
task's commit was made.

## User Setup Required

None — no external service configuration required. (Rollout to `haos-op3050-1` replacing `f1c878cb_cups` is
Plan 21-03's scope, not this plan's.)

## Next Phase Readiness

- The tracer's full happy path (scaffold -> avahi-daemon.conf with all three fixes -> one printer registered) is
  proven end-to-end and committed — Plan 21-02 (docs + `internal/base-image-config.yaml` tracking) and Plan 21-03
  (rollout to `haos-op3050-1`) can build on this without re-verifying the core mechanism.
- No blockers. The `-m drv:///sample.drv/generic.ppd` driver choice (Deviation #2) should be mentioned in Plan
  21-02's `cups/DOCS.md` so operators understand why driverless auto-detection isn't used.

---
*Phase: 21-cups-print-server-addon-airprint-mdns-fixes*
*Completed: 2026-09-26*

## Self-Check: PASSED

All 6 created files found on disk; commit `d96286c` found in git history.
