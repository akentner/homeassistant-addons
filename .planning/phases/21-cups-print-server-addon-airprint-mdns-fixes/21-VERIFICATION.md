---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
verified: 2026-10-04T17:55:00Z
status: passed
score: 14/14 must-haves verified
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
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-08-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-08-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-09-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-09-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-10-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-10-SUMMARY.md
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
  - internal/cups-test-isolation.sh
  - internal/verify-cups-avahi-guard.sh
  - internal/verify-cups-hardening.sh
  - internal/verify-cups-mdns-live.sh
  - internal/verify-cups-scaffold.sh
  - internal/verify-cups-watch-selftest.sh
covered_digest: "v2:sha256:65369eafe81907b920648257c7e8b765cc1845c873192dadf44060e77ced06f9"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 12/14
  gaps_closed:
    - "The fixed avahi_hostname (cups.local) is claimed AND KEPT by the running avahi-daemon on the live host (truth 13)"
    - "_ipp._tcp resolvable from a LAN client at the fixed name (truth 14)"
  gaps_remaining: []
  regressions: []
gaps: []
deferred: []
advisory:
  - finding: "Comments in cups/run.sh, cups/avahi-guard.sh and cups/DOCS.md read D-08 as 'no host-name supervision' (startup-only, no watchdog); D-08 only forbids a slot-exhaustion watchdog"
    category: other
    reason: "Wording only; the add-on behaviour matches the shipped decision. Needs a cups/ change (rebuild), so it is carried forward in 21-REVIEW-DISPOSITION.md for the next cups release"
    evidence_status: "recorded in ledger carry-forward notes"
  - finding: "Add-on has no runtime recovery if a foreign LAN device ever announces cups.local (guard is startup-only; optional plans 21-11/21-12 parked)"
    category: other
    reason: "The only observed cause (own test container) is removed and isolation is test-enforced; three quiet observations plus a fresh 2h24m-old boot hold. Residual risk from a genuinely foreign announcer is not covered and not demonstrated"
    evidence_status: "no occurrence observed"
human_verification: []
---

# Phase 21: cups print server addon airprint mdns fixes -- Verification Report

**Phase Goal:** Fork the third-party `f1c878cb_cups` add-on into a new, own `cups/` add-on (4-file pattern),
permanently fixing the AirPrint/mDNS reliability bug (Avahi legacy-unicast reflector slot exhaustion, Avahi
hostname-conflict rename, IPv6 resolution ambiguity) via HA-configurable options, then roll out on `haos-op3050-1`
replacing `f1c878cb_cups`.
**Verified:** 2026-10-04T17:55:00Z
**Status:** passed
**Re-verification:** Yes -- after gap-closure round 2 (plans 21-08, 21-09, 21-10); previous: gaps_found, 12/14

Phase 22 features (paperless upload, cups-pdf, print-history poller) are out of scope; only D-01..D-13 (+ D-14 brlaser)
are verified.

## Re-verification result (2026-10-04, after 21-08..21-10)

Truths 13 and 14, the only two that failed, are now VERIFIED, on evidence the verifier re-measured itself rather than
taken from 21-10-SUMMARY.md:

1. **Live, fresh, read-only (17:45Z):** `ha apps info 72a005f5_cups --raw-json` -> `state: started`, `version:
   0.1.0-16 == version_latest`, `host_network: true`. `docker inspect` on the host: StartedAt `2026-10-04T15:21:27Z`
   (exactly the "restart 2" boot of 21-10), RestartCount 0, i.e. the container is 2 h 24 min old and has not restarted
   since. `docker logs`: 0 `Host name conflict` lines; `Server startup complete. Host name is cups.local.`;
   `[avahi-guard] INFO: hostname claimed: cups.local (attempt 1/3)`.
   `bash internal/verify-cups-mdns-live.sh --assert --mask` -> every check PASS (conf-reflector, conf-ipv6,
   slot-exhaustion, daemon-fqdn `cups.local`, lan-forward-v4, lan-no-aaaa, lan-service-resolve: 1 resolved `_ipp._tcp`
   record), `RESULT: PASS`. The same checks failed at +2.5 min on the 0.1.0-16 boot of the previous verification; this
   boot is more than 55 times past that point and still `cups.local`.
2. **Independent quiet-window check (workstation, `podman events`, read-only):** the only cups containers created or
   started on the verifying workstation on 2026-10-04 are (a) 07:14:55Z, the paperless verifier containers carrying the
   default host name `cups` -- two seconds before the live avahi logged `Host name conflict, retrying with cups-2` at
   07:14:57Z (09:14:57 CEST), which reproduces the diagnosis timing from the podman event history; (b) planning spikes
   07:52-08:06Z; (c) the isolated guard/scaffold/paperless verifier runs 09:53-10:06Z, produced by the 21-08 helper. There
   is **no cups container event after 10:06:16Z**, which covers all three watch windows (quiet-since 14:08:08Z, 14:08:08Z
   and 15:15:09Z; the last window ended around 16:00Z). The watch's own claim "workstation quiet in every round" is
   therefore true by an independent source.
3. **Natural negative/positive control inside the evidence:** the isolated verifier runs at 09:53-10:06Z happened while
   the 07:47Z boot of the live add-on was running; 21-10 observation 1 (conflict check over the whole boot since
   container start, `events=OK`) records no conflict. The one non-isolated run at 07:14:55Z renamed the live host two
   seconds later. Together with 21-08's RED/GREEN isolation tests this supports "test containers were the cause" without
   needing the skipped negative control.
4. **The instrument is sound (re-read, not trusted):** `internal/verify-cups-mdns-live.sh` `watch_loop` (lines 568-721):
   `FAIL` if any quiet round failed; `INVALID` if any non-quiet round or any matching local create/start event;
   `PASS-UNVERIFIED-QUIET` unless events history is verified; `PASS` only otherwise. Continuity (StartedAt unchanged) and
   `host-name-conflict` are per-round checks. `bash internal/verify-cups-watch-selftest.sh` (stubbed ssh/avahi/docker)
   -> `RESULT: PASS` (all nine scenarios, 34 s).
5. **The published add-on is the code in the repository:** `git diff a36e6bd HEAD -- cups internal/base-image-config.yaml`
   is empty (tag `cups/v0.1.0-16` == HEAD content), so the live image carries no un-reviewed change; plans 21-08..21-10
   changed only `internal/` and `.planning/`.

Caveats (kept visible, none blocks): observation 1 only covers the quiet window from 14:08:08Z of a 07:47Z boot
(`covers-container-start=no`); the strong evidence is restarts 1 and 2 (`covers-container-start=yes`, milestones +2/+10/+30
PASS) plus the fresh 2 h 24 min boot above. The optional negative control (deliberate rename of the live host) was
skipped. Only this one workstation is watched; other LAN devices announcing `cups.local` are outside the evidence.

## Goal Achievement

### Observable Truths

ROADMAP lists no formal Success Criteria; truths are the PLAN `must_haves` of 21-01/02/03 (D-01..D-13) as in the earlier
verifications, plus the must_haves of 21-08/09/10, re-checked at HEAD and on the live host.

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | `cups/` has the 4-file pattern plus generate_config.py (D-01, D-02) | VERIFIED | files present incl. `avahi-guard.sh`; `make validate-addons` and `make validate-versions` pass (re-run); `cups/` unchanged vs published tag |
| 2  | Generated avahi-daemon.conf: `enable-reflector=no`, fixed `host-name=`, `use-ipv6=no` defaults (D-07, D-09, D-10, D-11) | VERIFIED | `bash internal/verify-cups-hardening.sh` -> RESULT: PASS (re-run); live `conf-reflector`, `conf-ipv6`, `slot-exhaustion`, `lan-no-aaaa` PASS |
| 3  | printers list-of-objects registered via lpadmin (D-03, D-04) | VERIFIED | unchanged since earlier verification; hardening verifier PASS |
| 4  | config.yaml exposes the D-05 surface | VERIFIED | unchanged (`git diff a36e6bd HEAD -- cups` empty) |
| 5  | `host_network: true` | VERIFIED | live `ha apps info --raw-json` -> `host_network: true` |
| 6  | No slot-exhaustion watchdog (D-08) | VERIFIED | no watchdog in run.sh/avahi-guard.sh; see advisory 1 on over-wide comment wording |
| 7  | Base-image tracking, no `.upstream.yaml` (D-06) | VERIFIED | unchanged |
| 8  | README/DOCS document D-05 options, reflector rationale, no-watchdog | VERIFIED | unchanged |
| 9  | Root README lists the cups add-on | VERIFIED | unchanged |
| 10 | Read-only migration-suggestion script (D-13) | VERIFIED | hardening verifier helper tests PASS (re-run) |
| 11 | `cups` installed and running on haos-op3050-1 (D-12) | VERIFIED | live: `state: started`, `0.1.0-16`, `update_available: false`; container started 15:21:27Z, RestartCount 0 |
| 12 | `f1c878cb_cups` removed (D-12) | VERIFIED | re-queried read-only: `ha apps info f1c878cb_cups` -> `installed: false` (repository entry only) |
| 13 | Daemon claims AND keeps the fixed host name `cups.local`; no `-2` rename (D-11) | VERIFIED | see "Re-verification result" 1-3: three 32-min `WATCH RESULT: PASS` (21-10), milestones +2/+10/+30 PASS on both restarts, plus fresh live `--assert` PASS on a 2 h 24 min old boot with 0 conflict lines |
| 14 | `_ipp._tcp` resolvable by LAN clients at the fixed name (browse-vs-resolve split gone) | VERIFIED | live `lan-service-resolve` PASS (1 resolved record -> `cups.local` / host IPv4) now and in every watch round |
| 15 | (21-08) No local verifier can announce the live name; test containers LAN-isolated | VERIFIED | `internal/cups-test-isolation.sh` present; `verify-cups-hardening.sh` section "isolation" PASS incl. static scan of 3 verifiers (re-run, RED proof recorded in 21-08); podman history shows isolated runs 09:53-10:06Z without a live rename |
| 16 | (21-09) `--watch` instrument is read-only, mechanical and falsifiable | VERIFIED | code re-read (above); self-test `RESULT: PASS`; shellcheck clean on all phase files (only an unrelated SC2329 info in `verify-update-version-tag-timing.sh`) |
| 17 | (21-09) Review ledger settled, diagnosis correction recorded append-only | VERIFIED | `21-REVIEW-DISPOSITION.md`: 6 closed with commit hashes (6d8414a, e66e7ef, 2e92a39), 14 deferred each with a reason, 0 open |
| 18 | (21-10) Three quiet watches PASS, human-run restarts, agent read-only | VERIFIED | transcripts consistent with live container StartedAt and independent podman event history; no mutating command found |

**Score:** 14/14 core truths (1-14) verified; the supplementary 21-08..21-10 truths (15-18) are also verified.
`behavior_unverified: 0` -- the time-dependent invariant in truth 13 has behavioural evidence (live watches over time),
not just presence.

### Re-verification of the closed claims (21-10 SUMMARY vs. now)

| 21-10 claim | Verdict |
| ----------- | ------- |
| Obs 1 current boot (07:47:21Z), 17/17 rounds quiet, PASS | Accepted; weaker for the pre-14:08Z part (conflict + continuity checks only), disclosed by the transcript itself |
| Obs 2 restart 1 (14:42:01Z) PASS, covers-container-start=yes | Accepted; no cups container event after 10:06Z on the workstation |
| Obs 3 restart 2 (15:21:27Z) PASS, claim attempt 1 | Accepted; live container StartedAt equals this value and RestartCount is 0 |
| "Diagnosis confirmed: local test containers were the cause" | Accepted as strongly supported (timing 07:14:55Z vs 07:14:57Z reproduced from podman events; 3 quiet boots; isolated runs did not rename), not as proven by intervention (negative control skipped) |
| "Plans 21-11/21-12 not required" | Accepted for the phase goal; see advisory 2 for the residual foreign-announcer risk |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| run.sh | generate_config.py (refuse on failure) | `if ! python3 /generate_config.py; ... exit 1` (CR-02) | WIRED | hardening verifier PASS |
| run.sh step 4 | avahi-guard.sh `avahi_guard_start` | `. /avahi-guard.sh` | WIRED | live log shows `[avahi-guard] INFO` claim line |
| avahi_hostname -> hostname held by running daemon | avahi runtime state | `host-name=` + guard | WIRED (observed over time) | held for 2 h 24 min on the current boot, 3 x 32 min watches |
| cupsd DNS-SD records -> avahi hostname | SRV target | cupsd `DNSSDHostName` | WIRED while the name holds | resolved `_ipp._tcp` record points at `cups.local` |
| every local cups verifier -> internal/cups-test-isolation.sh | docker run choke point | helper + static scan | WIRED | hardening verifier static scan PASS (3 verifiers) |
| verify-cups-mdns-live.sh --watch -> 21-10 transcripts | live proof | same run_checks as --assert | WIRED | live `--assert` re-run PASS |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| avahi-daemon.conf | host-name / ipv6 / reflector | `/data/options.json` | Yes (live conf matches options) | FLOWING |
| register-printers.sh | printers[] | options.json | Yes (live printer registered) | FLOWING |
| watch verdict | rounds / quiet / events | live ssh + avahi + local engine events | Yes (re-measured live) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Live checks incl. fixed name and service resolve | `bash internal/verify-cups-mdns-live.sh --assert --mask` (read-only) | RESULT: PASS, 7 checks PASS | PASS |
| Live container age / restarts / conflicts | read-only `docker inspect`, `docker logs \| grep -c` via ssh | StartedAt 15:21:27Z, RestartCount 0, 0 conflicts | PASS |
| Hardening verifier (incl. isolation section) | `bash internal/verify-cups-hardening.sh` | RESULT: PASS (0.4 s, stub docker) | PASS |
| Watch classification and read-only contract | `bash internal/verify-cups-watch-selftest.sh` | RESULT: PASS (34 s, stubs only) | PASS |
| Shell lint | `shellcheck -e SC1091 -e SC2034 cups/run.sh cups/avahi-guard.sh internal/*.sh` | clean for all phase files | PASS |
| Add-on structure / version sync | `make validate-addons`, `make validate-versions` | pass | PASS |
| Workstation quiet during watch windows | `podman events --since 07:00Z` filtered to create/start | no cups container after 10:06:16Z | PASS |

Not re-run (would start local cups containers, forbidden here and by the quiet-window rule): `internal/verify-cups-avahi-guard.sh`,
`internal/verify-cups-scaffold.sh`, `internal/verify-cups-paperless-upload.sh`; their PASS results are in the 21-05/06/08
SUMMARYs. No mutating command was run against the live host and no container was started.

### Probe Execution

SKIPPED -- no `scripts/*/tests/probe-*.sh` declared; verification is by the `internal/verify-cups-*.sh` scripts above.

### Requirements Coverage

No REQUIREMENTS.md IDs map to this phase (`grep -i cups|Phase 21` finds none; ROADMAP: "D-01..D-13, no REQUIREMENTS.md IDs
mapped to this ad-hoc phase"). The IDs in the PLAN frontmatter (D-01..D-13) are CONTEXT.md decisions and are accounted
for there. Plans 21-08/09/10 claim D-07, D-10, D-11, D-12 (21-08: D-11, D-12).

| Decision | Status | Evidence |
| -------- | ------ | -------- |
| D-01..D-06, D-08, D-09 | SATISFIED | truths 1-8 |
| D-07 (reflector off) | SATISFIED | conf + 0 slot messages, PASS in every watch round |
| D-10 (IPv6 ambiguity) | SATISFIED | `use-ipv6=no`, `lan-no-aaaa` PASS in every watch round |
| D-11 (fixed host name stops the conflict rename) | SATISFIED | truth 13, over time (previously BLOCKED) |
| D-12 (rollout, replace old add-on) | SATISFIED | truths 11, 12 |
| D-13 (migration suggestion) | SATISFIED | truth 10 |

No ORPHANED requirements.

### Code Review Cross-Reference (21-REVIEW.md)

The earlier WARNING (stale ledger) is resolved: `21-REVIEW-DISPOSITION.md` records CR-02, WR-04 (6d8414a), WR-05, WR-09
(e66e7ef), WR-07, IN-06 (2e92a39) as closed and the other 14 findings as deferred, each with a reason; none is open. The
three cited commits exist on main. Deferred items (CR-01, CR-03, WR-01..03, 06, 08, 10, IN-01..05, 07) belong to Phase
22 / next cups release and no Phase 21 decision depends on them.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| cups/run.sh, cups/avahi-guard.sh, cups/DOCS.md | 37 / 36 / 249, 357 | "startup-only, no watchdog -- D-08" comments over-read D-08 | Info | wording only; ledger carry-forward; next cups release |
| (phase files) | -- | TBD/FIXME/XXX | none | the only grep hit is `tailXXXX.ts.net` in a hostname comment in `generate_config.py:148`, a placeholder, not a debt marker |

The earlier Blocker (startup-only settle check producing truths 13/14 failure) is downgraded: its observed trigger was
our own test container, which is removed (21-08); no occurrence since in 3 quiet boots.

### Human Verification Required

None required for the status. Informational and optional (already in the ledger's carry-forward notes, not a Phase 21
must-have): a real iPhone/iPad/Mac AirPrint discovery plus test page. The measured proxy (LAN-client `avahi-browse -r`
resolving `_ipp._tcp` to `cups.local` / host IPv4) is what the diagnosis identified as the failing symptom.

### Gaps Summary

No gaps. The only failing truths (13, 14) closed by live, time-extended and independently re-checked evidence; the
instrument that produced it is mechanical and self-tested; the cause (own test container, 21-08) is removed structurally
and enforced host-side. Residual risk and wording items are advisory.

---

_Verified: 2026-10-04T17:55:00Z_
_Verifier: Claude (gsd-verifier)_

---

# Previous verification report (2026-10-04T07:20Z, gaps_found 12/14) -- retained unchanged below

The text below is the prior diagnosis, kept append-only. Its status, score, truth rows 13/14 and gaps are superseded by
the section above.

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
