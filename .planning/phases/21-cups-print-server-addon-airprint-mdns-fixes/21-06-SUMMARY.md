---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 06
subsystem: infra
tags: [cups, lpadmin, registration, migration-helper, uuid-stability, docs, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "21-05 avahi startup guard, hardening verifier, fullmatch validation"
provides:
  - "Failure-tolerant /tmp/register-printers.sh (per-entry warning, aggregated exit status) -- WR-09"
  - "PRINTER_NAME_RE [A-Za-z0-9_-]{1,127} for printers[].name and paperless_upload.queue_name; NAME_RE kept for avahi_hostname -- WR-05"
  - "YAML-safe migration helper with name flagging and socket:// reminder -- IN-06"
  - "UUID-stability scaffold check that recreates the container and compares with uuid5 -- WR-07"
  - "DOCS/README for the guard, IPv6 publishing and corrected rollout verification; cups 0.1.0-16 (untagged)"
affects: [21-07]

plan_head_before: 2d045b6712e3f4d46cb6c0052b1b453c3b73fac9
plan_head_after: 65330b2cd3cadd83509b56a7368c4988a164633f
actuals:
  tokens: 14000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Generated shell script with per-entry if/else and an aggregated exit status instead of set -e"
    - "Capture-then-filter instead of piping a remote command into an early-exiting grep/head under pipefail"
    - "Container recreation (not docker restart) to reproduce Supervisor's fresh-writable-layer behavior"

key-files:
  created: []
  modified:
    - cups/generate_config.py
    - internal/verify-cups-hardening.sh
    - internal/cups-migration-suggestion.sh
    - internal/verify-cups-scaffold.sh
    - cups/DOCS.md
    - cups/README.md
    - cups/config.yaml

key-decisions:
  - "build_printer_registration takes an optional extra_snippets list so the cups-pdf snippet sits before the final exit; main() no longer appends it after the script text"
  - "The first container's UUIDs are asserted too, after waiting for the post-fixup readiness line, so the baseline is not read mid-fixup"

requirements-completed: [D-03, D-04, D-11, D-13]

duration: n/a (single executor session)
completed: 2026-10-03
status: complete
---

# Phase 21 Plan 06: Registration hardening, migration helper safety, non-vacuous UUID test, docs and 0.1.0-16 Summary

One failing `lpadmin` call no longer takes later printers or the cups-pdf queue down, underscore queue names register, the
migration helper emits YAML the add-on accepts, the UUID-stability check now fails when the fixup is removed, and the guard,
IPv6 change and corrected verification are documented with `cups` bumped to 0.1.0-16 (no tag).

## Accomplishments

- **Task 1 (WR-09, WR-05).** The generated script has no `set -e`; each `lpadmin` call (generic, brlaser, cups-pdf) is an
  if/else that prints `registered printer: <name>` or `WARNING: registration of <name> failed` to stderr and sets
  `REGISTER_FAILED`; the script ends with `exit "$REGISTER_FAILED"`, so run.sh's retry loop is unchanged. `PRINTER_NAME_RE`
  (fullmatch) now validates printer and cups-pdf queue names; names still reach lpadmin only via `shlex.quote`.
- **Task 2 (IN-06, WR-05, WR-07).** Migration helper: container list captured first, then `grep -m1 -F` on the variable
  (no pipe, so no SIGPIPE under pipefail); backslash/quote escaping for name and uri; WARNING comment before names outside
  the add-on's charset; driver/driver_model reminder when a `socket://` uri is present; no line over 120 columns.
  `internal/verify-cups-scaffold.sh` honors `CUPS_ADDON_DIR`, stops and recreates the container with identical flags and
  mount, and asserts both pre- and post-recreation UUIDs equal `urn:uuid:` + the host-computed uuid5.
- **Task 3.** DOCS: `avahi_use_ipv6` row (AAAA/ip6.arpa over IPv4), name charset, new `**Avahi startup guard (D-11).**`
  paragraph (log lines, 0/30/90 s schedule, degrade-and-continue, startup-only), Migration step 2 now uses
  `avahi-resolve-host-name -4` and `avahi-browse -t -r _ipp._tcp` from a LAN client and explicitly demotes the reverse lookup;
  README feature bullet; `make update-version ADDON=cups VERSION=0.1.0-16 NO_TAG=yes` (config 0.1.0-16, build.yaml 0.1.0,
  badge v0.1.0, no tag).

## Verification evidence

| Check | Result |
| ----- | ------ |
| `shellcheck -e SC1091 -e SC2034` on hardening, helper, scaffold; `py_compile generate_config.py` | clean |
| `bash internal/verify-cups-hardening.sh` | all PASS (earlier 21-05 tests plus 13 new assertions) |
| `bash internal/verify-cups-paperless-upload.sh` (docker/podman) | ALL CHECKS PASSED |
| `bash internal/verify-cups-scaffold.sh` (docker/podman), recreation + uuid5 | ALL CHECKS PASSED; pre- and post-recreation UUIDs equal the uuid5 values |
| `bash internal/verify-cups-avahi-guard.sh` regression | RESULT: PASS (all assertions) |
| `make validate-versions`, `make validate-addons` | pass |
| `pre-commit run --files cups/DOCS.md cups/README.md cups/config.yaml cups/build.yaml` | pass (prettier reformatted DOCS tables once, re-run clean) |
| Read-only contract grep on the helper (non-comment lines) | 0 hits |

**RED proofs (observed).**

- Task 1: hardening script run with `CUPS_ADDON_DIR` pointing at a copy of `cups/` using the pre-task `generate_config.py`
  (`git show 2d045b6:cups/generate_config.py`) prints 11 FAIL, including the underscore-name test (`Brother_MFC_7460DN` not
  registered), the "set -e" test, "lpadmin still called for the entry AFTER the failing one", the exit-status tests and the
  `PDF_to_DMS` queue tests; RESULT: FAIL.
- WR-07: scaffold run with `CUPS_ADDON_DIR` pointing at a copy whose `build_printer_uuid_fixup_script` returns None at once
  exits 1 with `FAIL: pre-recreation testprinter UUID 'urn:uuid:2e2c5b74-...' != expected 'urn:uuid:dd92b350-...'` (same for
  brlasertest), `FAIL: 'cupsd is ready (post-fixup restart)' did not appear within 40s -- the UUID fixup did not run` and the
  two post-recreation UUID mismatches. Note: with the fixup gone the earlier `docker restart` based check would have kept
  matching before/after (same writable layer), which is why it was vacuous.

## Task Commits

| Task | Commit | Description |
| ---- | ------ | ----------- |
| 1 | e66e7ef | fix: failure-tolerant registration, PRINTER_NAME_RE, hardening Tests 1-4 |
| 2 | 2e92a39 | fix: migration helper safety, recreation-based uuid5 test, hardening helper tests |
| 3 | 65330b2 | docs: guard/IPv6/verification docs, cups 0.1.0-16 (no tag) |

## Deviations from Plan

**1. [Rule 1 - Bug] Existing hardening Test 3 counted `lpadmin ` at line start**
- The 21-05 assertion looked for lines starting with `lpadmin `; the new if/else form starts them with `if lpadmin `.
  Updated the assertion in the same commit (behavior asserted is unchanged: exactly one lpadmin call).

**2. [Rule 3 - Blocking] cups-pdf snippet placement**
- `main()` appended the cups-pdf snippet to the script text after `build_printer_registration` returned; with the new final
  `exit "$REGISTER_FAILED"` line the snippet would have sat after the exit and never run. `build_printer_registration`
  gained an optional `extra_snippets` argument and `main()` passes the snippet through it.

**3. [Rule 1 - Bug] `docker logs | grep -q` under pipefail**
- The new post-fixup wait helper first piped `docker logs` into `grep -q`; that can SIGPIPE docker and report a false miss
  (the same class as IN-06). It captures the logs into a variable first.

**4. Acceptance criterion not literally satisfiable**
- `awk 'length > 120' cups/DOCS.md cups/README.md | wc -l` prints 38, all of them pre-existing Markdown table rows
  (`.markdownlint.json` sets `tables: false`; prettier keeps tables on one line). The two table rows this plan edited stay
  within the existing column widths, and every non-table line (including all new prose) is at most 120 columns
  (`awk 'length > 120 && !/^\|/'` prints 0 for both files).

**5. Task 1 hardening commit contains only Task 1 tests**
- The hardening script was committed in two stages (Task 1 sections, then the helper section with Task 2) so each commit is
  green on its own.

**Total deviations:** 5 (3 auto-fixes, 1 criterion interpretation, 1 process note). No scope change.

## Self-Check: PASSED

- Modified files exist; commits e66e7ef, 2e92a39, 65330b2 exist on this branch.
- `grep '^version: "0.1.0-16"' cups/config.yaml` matches; `git tag --list 'cups/v0.1.0-16'` is empty.
- No modifications to STATE.md / ROADMAP.md.

## Known limitations and follow-ups

- Registration retry: a persistently failing entry now makes run.sh re-run the whole script 5 times (idempotent, a few
  seconds of brlaser PPD lookup per pass) and then log `printer registration failed after retries`; the other entries are
  registered on the first pass.
- Out of scope, unchanged: the `IdleExitTimeout` cupsd.conf warning; Phase 22 findings (CR-01/CR-03/WR-01/02/03/06/08/10,
  IN-01..05, IN-07).
- Live proof (restart survival, LAN resolution), image publication and the tag are plan 21-07; nothing was run against
  haos-op3050-1 and no git tag was created.
- Local docker is podman emulation (pasta networking): the throwaway names `cups-verify` / `cups-guard` were announced on the
  workstation LAN during the scaffold and guard runs.

## Known Stubs

None.

## Threat Flags

None. T-21-15 (widened queue-name charset): fullmatch + `shlex.quote` + validated-only echo, covered by hardening Tests 1 and
4 (space, slash, trailing newline, 127/128 boundary). T-21-16: Test 2 runs the real generated script against a failing stub.
T-21-17: helper Test 1 includes a uri with a double quote and parses the output as YAML.
