---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
verified: 2026-10-04T07:20:00Z
status: gaps_found
score: 12/14 must-haves verified
covered_files:
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-01-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-01-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-02-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-02-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-03-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-03-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-04-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-04-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-05-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-05-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-06-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-06-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-07-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-07-SUMMARY.md
  - README.md
  - cups/DOCS.md
  - cups/Dockerfile
  - cups/README.md
  - cups/avahi-guard.sh
  - cups/build.yaml
  - cups/config.yaml
  - cups/generate_config.py
  - cups/run.sh
  - internal/base-image-config.yaml
  - internal/cups-migration-suggestion.sh
  - internal/verify-cups-avahi-guard.sh
  - internal/verify-cups-hardening.sh
  - internal/verify-cups-mdns-live.sh
  - internal/verify-cups-scaffold.sh
covered_digest: "v2:sha256:98143857a2defdb4245dc89c9a93289ff33556b7e1f0082bf3999f5df73a91a0"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 12/14
  gaps_closed: []
  gaps_remaining:
    - "avahi-resolve -a <haos-op3050-1 IP> / daemon FQDN is the fixed avahi_hostname (truth 13)"
    - "_ipp._tcp resolvable from a LAN client (truth 14)"
  regressions: []
gaps:
  - truth: "The fixed avahi_hostname (cups.local) is claimed AND KEPT by the running avahi-daemon on the live host (D-11; 21-VERIFICATION truth 13)"
    status: failed
    reason: >-
      Live read-only observation 2026-10-04 09:17-09:19 CEST on add-on 0.1.0-16 (container started 09:12:17, i.e. the
      "restart 2" boot that 21-07 recorded as RESULT: PASS). The guard reported `hostname claimed: cups.local (attempt
      1/3)` / `RESULT: claimed` at 09:12:23, but at 09:14:57 (2 min 34 s later, long after the guard returned)
      avahi logged `Host name conflict, retrying with cups-2` and `Server startup complete. Host name is cups-2.local`.
      `dbus-send ... GetHostNameFqdn` -> `cups-2.local`; `ps` -> `avahi-daemon: running [cups-2.local]`; the SSH/SFTP
      services are re-announced as `cups-2`. `bash internal/verify-cups-mdns-live.sh --assert --mask` -> RESULT: FAIL (3
      failed): daemon-fqdn, lan-forward-v4, lan-service-resolve. The rename persisted at the re-check 2 minutes later
      (09:19:08). The 21-05 guard is startup-only (hold window = 5 polls) and does not detect or recover from a conflict
      that arrives after it returned; the retry/backoff logic therefore never ran. 21-07's "closed on live host (3
      boots, claimed on attempt 1)" measured the claim at boot, not that it is kept.
    artifacts:
      - path: "cups/avahi-guard.sh"
        issue: "Settle window ends after AVAHI_GUARD_HOLD (5) consecutive polls; a conflict a few minutes later is neither detected nor retried; avahi never returns to the original name by itself"
      - path: "cups/run.sh"
        issue: "avahi_guard_start is the only host-name handling; nothing re-checks GetHostNameFqdn or re-registers cupsd's DNS-SD records after the guard returned"
    missing:
      - "Root cause of the post-claim conflict (who answered/announced cups.local at 09:14:57; confirmed observation: from this LAN client `avahi-resolve-host-name -4 cups.local` now answers 192.168.178.108 = the verifying workstation, which hosts two HA test containers with zeroconf, while the host's own record is cups-2.local; origin of that answer unproven; 21-04's conflict-capture experiment was never run)"
      - "Either keep the claim for a longer observation window / detect a later rename and recover (restart avahi + cupsd registration), or prevent the conflict (probe/announce loop through mdns-repeater with the host's other avahi daemons)"
      - "Live proof that the name is still cups.local after >= 10 minutes and after the next restart, not only at boot"
  - truth: "AirPrint reliability: the printer's advertised _ipp._tcp service is resolvable by LAN clients (browse-vs-resolve split gone; 21-VERIFICATION truth 14)"
    status: failed
    reason: >-
      Same boot, after the post-claim rename: `lan-service-resolve: no resolved _ipp._tcp record for cups.local / host
      IPv4 (1 browse '+' line seen: browse-works/resolve-fails)`. cupsd registered `Brother-MFC-7460DN @ cups` under
      DNSSDHostName cups.local at 09:12:27; once avahi became cups-2.local the SRV target no longer exists (the original
      symptom). It was resolvable only during the 2.5 minutes before the rename.
    artifacts:
      - path: "cups/avahi-guard.sh"
        issue: "see gap 1; the same missing post-claim handling"
    missing:
      - "Same fix as gap 1 plus a live `avahi-browse -t -r _ipp._tcp` resolved `=` line from a LAN client at least 10 min after boot"
deferred: []
human_verification: []
---

# Phase 21: cups print server addon airprint mdns fixes -- Verification Report

**Phase Goal:** Fork the third-party `f1c878cb_cups` add-on into a new, own `cups/` add-on (4-file pattern),
permanently fixing the AirPrint/mDNS reliability bug (Avahi legacy-unicast reflector slot exhaustion, Avahi
hostname-conflict rename, IPv6 resolution ambiguity) via HA-configurable options, then roll out on `haos-op3050-1`
replacing `f1c878cb_cups`.
**Verified:** 2026-10-04
**Status:** gaps_found
**Re-verification:** Yes -- after gap-closure plans 21-04..21-07 (previous: gaps_found, 12/14)

Phase 22 features (paperless upload, cups-pdf, print-history poller) are out of scope; only D-01..D-13 (+ D-14 brlaser)
are verified.

## Result in one paragraph

The code-level gap closure is real and verified: the startup guard, CR-02 refuse-to-start, fullmatch validation,
`publish-aaaa-on-ipv4=no`, failure-tolerant registration, YAML-safe migration helper and a non-vacuous UUID test all exist,
are wired and their verifiers pass; the image for 0.1.0-16 is published and running on the host. D-10 (no AAAA) is now
live-green. **But the phase's core outcome -- a hostname that stays `cups.local` and a resolvable AirPrint service -- is
not achieved on the live host today.** On the very boot that 21-07 recorded as PASS, avahi lost the name 2 min 34 s after
the guard reported `claimed`, and the add-on has been `cups-2.local` with an unresolvable `_ipp._tcp` since. The guard only
protects the first seconds of a boot, whereas the loss also occurs later. Truths 13 and 14 therefore remain FAILED.

## Goal Achievement

### Observable Truths

ROADMAP lists no formal Success Criteria; truths are the PLAN `must_haves` of 21-01/02/03 (D-01..D-13) as in the first
verification, re-checked against the code at HEAD and the live host.

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | `cups/` has the 4-file pattern plus generate_config.py (D-01, D-02) | VERIFIED | files present (now also `avahi-guard.sh`, copied by Dockerfile); `make validate-addons`, `make validate-versions` pass; version sync `config.yaml 0.1.0-16` / `build.yaml 0.1.0` / README badge `v0.1.0`; tag `cups/v0.1.0-16` -> a36e6bd, `git diff a36e6bd HEAD -- cups internal` empty (published image == HEAD code) |
| 2  | Generated avahi-daemon.conf: `enable-reflector=no`, fixed `host-name=`, `use-ipv6=no` defaults (D-07, D-09, D-10, D-11) | VERIFIED | `generate_config.py:724-755` renders host-name / use-ipv6 / `publish-aaaa-on-ipv4=no` (when ipv6 off) / enable-reflector; hardening verifier PASS; live conf `enable-reflector=no`, `use-ipv6=no` (assert PASS); live `lan-no-aaaa` PASS (was FAIL on 0.1.0-13); 0 "No slot available" lines |
| 3  | printers list-of-objects registered via lpadmin (D-03, D-04) | VERIFIED | hardening verifier: per-entry failure tolerance, underscore names (`PRINTER_NAME_RE`), disabled skipped, `file://` rejected; live log `registered printer: Brother-MFC-7460DN (brlaser ...)` |
| 4  | config.yaml exposes the D-05 surface | VERIFIED | unchanged since first verification (plus Phase 22 extras); `git diff` of option schema by 21-05 empty |
| 5  | `host_network: true` | VERIFIED | `ha apps info --raw-json`: `host_network: true` |
| 6  | No slot-exhaustion watchdog (D-08) | VERIFIED | no watchdog in run.sh/avahi-guard.sh; guard is explicitly startup-only and documented as such |
| 7  | Base-image tracking, no `.upstream.yaml` (D-06) | VERIFIED | `internal/base-image-config.yaml` cups entry, no `cups/.upstream.yaml` |
| 8  | README/DOCS document D-05 options, reflector rationale (D-07), no-watchdog (D-08) | VERIFIED | plus guard/IPv6/verification text added by 21-06 |
| 9  | Root README lists the cups add-on | VERIFIED | unchanged |
| 10 | Read-only migration-suggestion script (D-13) | VERIFIED | shellcheck clean; hardening verifier helper tests PASS (YAML-safe, name-flagging, socket reminder) |
| 11 | `cups` installed and running on haos-op3050-1 (D-12) | VERIFIED | `ha apps info 72a005f5_cups --raw-json`: `state: started`, `version: 0.1.0-16`, `version_latest: 0.1.0-16`, `update_available: false`, container `app_72a005f5_cups` Up |
| 12 | `f1c878cb_cups` removed (D-12) | VERIFIED | unchanged from first verification (not re-queried; no conflicting evidence) |
| 13 | Daemon claims AND keeps the fixed host name `cups.local`; no `-2` rename (D-11) | FAILED | Live 2026-10-04: guard `claimed` at 09:12:23, then `Host name conflict, retrying with cups-2` at 09:14:57; `GetHostNameFqdn=cups-2.local` at 09:17 and 09:19; `--assert` RESULT: FAIL (daemon-fqdn). See gap 1 |
| 14 | `_ipp._tcp` resolvable by LAN clients (browse-vs-resolve split removed) | FAILED | Live `--assert`: lan-service-resolve FAIL (browse-works/resolve-fails). See gap 2 |

**Score:** 12/14 truths verified (unchanged from the first verification: the same two truths fail, for a different and
later-in-time mechanism).

### Re-verification of the closed claims (21-07 SUMMARY vs. now)

| 21-07 claim | Verdict |
| ----------- | ------- |
| 3 boots with distinct cookies, each claimed on attempt 1, `--assert` PASS | Accepted as correct for the instant they were taken (log of the current boot shows the same `claimed` lines, cookie 3354254864) |
| "#13 closed on live host", "#14 closed on live host" | **Not upheld**: same boot lost the name 2.5 min after the claim and is renamed at verification time. The 9.5 h stability after restart 1 is real but shows the loss is intermittent, not fixed |
| "guard only makes a loss visible" (Limits section) | Confirmed correct, and it did make the loss visible (`Host name conflict` is now in `ha apps logs`) -- but the guard cannot see this loss, because it occurred after the guard returned |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| run.sh | generate_config.py (refuse on failure) | `if ! python3 /generate_config.py; ... exit 1` (CR-02) | WIRED | hardening/guard verifiers exercise the refuse scenario |
| run.sh step 4 | avahi-guard.sh `avahi_guard_start` | `. /avahi-guard.sh` | WIRED | live log shows `[avahi-guard] INFO/RESULT` lines |
| generate_config.py | /tmp/avahi-guard.env | `resolve_avahi_hostname` shared with conf | WIRED | live log `Config written to /tmp/avahi-guard.env` |
| avahi guard -> cupsd start ordering | cupsd starts after settled claim | run.sh step 4 before step 6 | WIRED | live ordering: claimed 07:12:23Z -> cupsd |
| avahi_hostname -> hostname held by running daemon | avahi runtime state | `host-name=` + guard | NOT_WIRED over time | name held for 2.5 min, then lost, no recovery path |
| cupsd DNS-SD records -> avahi hostname | SRV target | cupsd `DNSSDHostName` taken once at start | NOT_WIRED after rename | cupsd keeps announcing `cups.local` targets after avahi abandoned it |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| avahi-daemon.conf | host-name / ipv6 / reflector | `/data/options.json` | Yes (live conf matches options) | FLOWING |
| /tmp/avahi-guard.env | expected FQDN | same validation helper | Yes | FLOWING |
| register-printers.sh | printers[] | options.json | Yes (live printer registered) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Hardening (fullmatch, CR-02, WR-04/05/09, IN-06, avahi conf) | `bash internal/verify-cups-hardening.sh` | RESULT: PASS | PASS |
| Trailing-newline hostname rejected | `NAME_RE.fullmatch("cups\n")` | False (`"cups"` True) | PASS |
| Shell/Python lint | `shellcheck -e SC1091 -e SC2034 cups/run.sh cups/avahi-guard.sh internal/*.sh`; `py_compile` | clean | PASS |
| Add-on structure and version sync | `make validate-addons`, `make validate-versions` | pass | PASS |
| Live: reflector/ipv6 conf, 0 slot lines | `internal/verify-cups-mdns-live.sh --assert --mask` (run once, read-only) | PASS x3 | PASS |
| Live: daemon FQDN is `cups.local` | same (D-Bus GetHostNameFqdn) | `cups-2.local` | FAIL |
| Live: `cups.local` forward from LAN client | same | resolves to 192.168.178.108 (the verifying workstation), not the host | FAIL |
| Live: no AAAA published | same | PASS | PASS |
| Live: `_ipp._tcp` resolves | same | browse-works/resolve-fails | FAIL |
| Live: persistence of rename | read-only D-Bus + `ps` re-check 2 min later | still `cups-2.local` | confirmed |

Not re-run (cost, no new evidence expected): `internal/verify-cups-avahi-guard.sh` and `internal/verify-cups-scaffold.sh`
(docker/podman builds). Their PASS results are recorded in 21-05/21-06 SUMMARY; they cannot reproduce a LAN-side conflict
by construction, so they could not change this verdict. `verify-cups-paperless-upload.sh` is Phase 22 (run by the
orchestrator).

All live commands were read-only (`ha apps info`, `docker logs`, `docker exec ... dbus-send/ps`, the read-only verifier).

### Probe Execution

SKIPPED -- no `scripts/*/tests/probe-*.sh` declared; phase verification is by the `internal/verify-cups-*.sh` scripts above.

### Requirements Coverage

No REQUIREMENTS.md IDs map to this phase; D-01..D-13 are claimed by plans 21-01..21-07 (21-04..21-07: D-05, D-07..D-13).

| Requirement | Status | Evidence |
| ----------- | ------ | -------- |
| D-01..D-06, D-08, D-09 | SATISFIED | truths 1-8 |
| D-07 (reflector off) | SATISFIED | conf + 0 slot messages live |
| D-10 (IPv6 ambiguity) | SATISFIED | `use-ipv6=no` + `publish-aaaa-on-ipv4=no`; live `lan-no-aaaa` PASS |
| D-11 (fixed host name stops the conflict rename) | BLOCKED (outcome) | directive and boot-time guard correct, but the name is lost again at runtime on the live host (truths 13, 14) |
| D-12 (rollout, replace old add-on) | SATISFIED | truths 11, 12 |
| D-13 (migration suggestion) | SATISFIED | truth 10 |

### Code Review Cross-Reference (21-REVIEW.md)

Closed in code and verified by `verify-cups-hardening.sh` (RED proofs recorded in 21-05/06 SUMMARY): CR-02
(`run.sh` refuses to start), WR-04 (`fullmatch` at all call sites in `generate_config.py`), WR-05 (`PRINTER_NAME_RE`
with underscores, `NAME_RE` kept for hostnames), WR-09 (no `set -e`, per-entry failure, aggregated exit), IN-06
(migration helper), WR-07 (UUID test via container recreation). Remaining `$`-anchored patterns are only used with
`fullmatch` (checked: no `.match(` on them).

Not closed but not Phase 21 must-haves (Phase 22 / extras, no Phase 21 decision requires them): CR-01, CR-03, WR-01,
WR-02, WR-03, WR-06, WR-08, WR-10, IN-01..IN-05, IN-07 -- Phase 22's own SUMMARYs address part of them.

**WARNING (bookkeeping):** `21-REVIEW-DISPOSITION.md` still lists all 20 findings as `open`, including the six that
21-05/21-06 closed (CR-02, WR-04, WR-05, WR-07, WR-09, IN-06) and none of the remaining ones is marked deferred with a
reason. The code is closed; the ledger is stale and must be updated.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| cups/avahi-guard.sh | `avahi_guard_wait_settled` / `avahi_guard_start` | Startup-only settle check (hold 5 polls) | Blocker (for truths 13/14) | a conflict after the hold window leaves the add-on silently under `cups-2.local` with a stale cupsd SRV target |
| .planning/.../21-REVIEW-DISPOSITION.md | all rows | stale `open` | Warning | closed findings not recorded |

No unreferenced TBD/FIXME/XXX markers introduced.

### Observations (out of scope per instruction, not gaps)

- `IdleExitTimeout` unknown-directive error in cupsd.conf on every start (seen again in this boot's log).
- 20 s Get-Jobs poller causing `Limiting Get-Jobs response to 500 jobs.` per poll (seen in the log).
- `cupsctl` race absorbed by the retry; host-level `boot_fail` / `no_current_backup`.
- Optional iPhone/iPad/Mac print check not performed; 21-04 conflict-capture experiment not run, so the conflict's origin
  is still unknown. Unexplained but relevant for the follow-up: the verifying workstation currently answers
  `cups.local` -> 192.168.178.108 on mDNS (its avahi is itself in `registering`/renamed state, and it runs two HA test
  containers on the host network). Whether this answer caused or merely follows the 09:14:57 conflict is not proven; the
  verifier's own queries are read-only and cannot register names.

**Diagnosis update (2026-10-04, plan 21-09).** The 09:14:57 rename is attributed to our own local test container, not to
an unknown foreign announcer (that wording is superseded): podman created and started the Phase 22 verifier image at
09:14:55 (`journalctl --user`, corroborated by podman's own event history, which lists the container-create event of the
verifier's happy-path container at that second), and its fixtures carried no `avahi_hostname`, so the default `cups` was
announced through pasta networking onto the real LAN two seconds before the live avahi renamed itself.
Label: strongly indicated, confirmed by timing; final confirmation = quiet observation in plan 21-10. Truths #13 and
#14 remain open until then. Plan 21-08 removed the cause (isolated local test containers), plan 21-09 added `--watch`
to measure it.

### Human Verification Required

None. The failure is directly observed and persists. The next step needs a mutating decision (investigate/capture the
conflicting announcer on the LAN, then change the guard), not a manual check.

### Gaps Summary

Everything that is repo-static or boot-time now checks out, and the two previously absent mechanisms (visible avahi logs,
settled-claim ordering) work as designed. The remaining defect is that D-11's real requirement -- the name *stays*
`cups.local` -- is only protected for the first seconds of a boot. On the live host the claim was lost 2.5 minutes after
the guard reported success, which also breaks AirPrint resolution again. 21-07 declared both truths closed on the basis
of boot-time observations; they are not closed.

Suggested next step: `/gsd-plan-phase 21 --gaps`:
1. Identify the post-claim conflicting announcer (run the 21-04 capture experiment, or tcpdump of UDP 5353 for `cups.local`
   on the LAN and on the host's mdns-repeater interface; check the workstation's `cups.local` answer first).
2. Extend the guard: either supervise `GetHostNameFqdn` for a longer window (with bounded recovery that restarts avahi and
   cupsd registration), or remove the cause of the conflict.
3. Re-prove live with a >= 10-minute observation after boot and after a restart; update `21-REVIEW-DISPOSITION.md`.

---

_Verified: 2026-10-04_
_Verifier: Claude (gsd-verifier)_
