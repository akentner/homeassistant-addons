---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
verified: 2026-10-03T12:10:00Z
status: gaps_found
score: 12/14 must-haves verified
covered_files:
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-01-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-01-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-02-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-02-SUMMARY.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-03-PLAN.md
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-03-SUMMARY.md
  - README.md
  - cups/DOCS.md
  - cups/Dockerfile
  - cups/README.md
  - cups/build.yaml
  - cups/config.yaml
  - cups/generate_config.py
  - cups/run.sh
  - internal/base-image-config.yaml
  - internal/cups-migration-suggestion.sh
  - internal/verify-cups-scaffold.sh
covered_digest: "v2:sha256:641d866c6a9b2e67260ef1a963e0ea7d0c2c2e0701769a5bb9ae7f94871a9e4a"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "avahi-resolve -a <haos-op3050-1 IP> resolves to the fixed avahi_hostname with no auto-renamed -2 suffix (D-11; 21-03 must_have; the hostname-conflict-rename leg of the phase goal)"
    status: failed
    reason: >-
      Live host observation 2026-10-03: the running avahi-daemon in app_72a005f5_cups is `avahi-daemon: running
      [cups-2.local]` although the generated /etc/avahi/avahi-daemon.conf correctly has host-name=cups.
      `avahi-resolve -a 192.168.178.3` returns `cups-2.local`; `avahi-resolve-host-name cups.local` times out (nobody
      owns it). The add-on lost the hostname probe at startup (container started 2026-09-29T07:25Z) and nothing in
      run.sh/generate_config.py recovers from or prevents the rename. The static fixed host-name= is necessary but
      not sufficient.
    artifacts:
      - path: "cups/run.sh"
        issue: "Starts avahi-daemon then cupsd with no check that avahi actually claimed avahi_hostname; no handling of a post-start rename"
      - path: "cups/generate_config.py"
        issue: "build_avahi_conf() only writes host-name=; no conflict mitigation (e.g. disable cache/proxy interaction, start ordering)"
    missing:
      - "Root-cause why the host-name probe still conflicts on the live host (candidate: stale cached record of the previous container instance answered by a mDNS proxy/repeater during probing; unconfirmed)"
      - "A startup guard in run.sh that waits for avahi to settle and verifies/handles the claimed hostname (e.g. log + restart avahi/cupsd, or fail loudly)"
      - "Live-host verification (not only the docker smoke test) that the hostname survives an add-on restart/update"
  - truth: "AirPrint reliability: the printer's advertised _ipp._tcp/_printer._tcp service is resolvable by clients (the phase goal's browse-vs-resolve split from the original diagnosis must be gone)"
    status: failed
    reason: >-
      From the HA host container AND from an independent LAN client (this workstation, 192.168.178.108),
      `avahi-browse -t -r -p _ipp._tcp` lists `Brother-MFC-7460DN @ cups` but `Failed to resolve service ...: Timeout
      reached`. This is exactly the original symptom (browse works, resolve fails) the phase was created to remove.
      Likely linked to the cups vs cups-2 hostname split (the service's SRV target cannot be resolved while the host
      announces as cups-2.local) -- the mechanism is not confirmed, the observable failure is.
    artifacts:
      - path: "cups/run.sh"
        issue: "cupsd registers its DNS-SD records without any guarantee that Avahi's hostname is settled / matches avahi_hostname"
    missing:
      - "Reproduce and fix so that `avahi-browse -r _ipp._tcp` yields a resolved `=` line from a LAN client"
      - "Add the browse -r resolve check to the live-rollout verification (21-03 only checked avahi-resolve -a and the log grep)"
deferred: []
human_verification: []
---

# Phase 21: cups print server addon airprint mdns fixes -- Verification Report

**Phase Goal:** Fork the third-party `f1c878cb_cups` add-on into a new, own `cups/` add-on (4-file pattern),
permanently fixing the AirPrint/mDNS reliability bug (Avahi legacy-unicast reflector slot exhaustion, Avahi
hostname-conflict rename, IPv6 resolution ambiguity) via HA-configurable options, then roll out on `haos-op3050-1`
replacing `f1c878cb_cups`.
**Verified:** 2026-10-03
**Status:** gaps_found
**Re-verification:** No -- initial verification

Note: the add-on has since been extended by Phase 22 (paperless-ngx upload, cups-pdf, print-history poller). Only
the Phase 21 decisions D-01..D-13 (plus D-14 brlaser driver added mid-rollout) were verified; Phase 22 features are
out of scope here.

## Goal Achievement

### Observable Truths

ROADMAP lists no formal Success Criteria; the truths come from the PLAN `must_haves` of 21-01/02/03 (D-01..D-13).

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | `cups/` has the 4-file pattern plus generate_config.py (D-01, D-02) | VERIFIED | `cups/{config.yaml,build.yaml,Dockerfile,run.sh,README.md,DOCS.md,generate_config.py}` exist; `make validate-addons` and `make validate-versions` pass; slug `cups` |
| 2  | Generated avahi-daemon.conf: `enable-reflector=no` default, fixed `host-name=` from `avahi_hostname`, `use-ipv6=no` default (D-07, D-09, D-10, D-11) | VERIFIED | Ran `build_avahi_conf({})` -> `host-name=cups`, `use-ipv6=no`, `enable-reflector=no`; with options flipped -> `yes`/`x1`/`yes`; invalid hostname (`a\nb`) -> exit 1. Live container's /etc/avahi/avahi-daemon.conf matches. Generation is a real template render, not sed (D-09) |
| 3  | printers list-of-objects registered via lpadmin (D-03, D-04) | VERIFIED | `build_printer_registration()` run with 3 entries: enabled ipp -> `lpadmin -p P1 ...`, `enabled:false` skipped, `file://` rejected by scheme allowlist. Live host `lpstat -v` shows Brother-MFC-7460DN registered |
| 4  | config.yaml exposes the D-05 surface (avahi_reflector, avahi_hostname, avahi_use_ipv6, printers[{name,uri,enabled}], log_level) | VERIFIED | `cups/config.yaml` options/schema contain all five (superset: later added server_aliases, admin_*, location/driver, paperless_upload). `uri` typed `str` per the Task-1 checkpoint decision |
| 5  | `host_network: true` | VERIFIED | `cups/config.yaml` |
| 6  | No slot-exhaustion watchdog (D-08) | VERIFIED | grep of run.sh/generate_config.py: only comments stating the absence; DOCS.md "No slot-exhaustion watchdog (D-08)" |
| 7  | Base-image tracking, no `.upstream.yaml` (D-06) | VERIFIED | `internal/base-image-config.yaml` `cups:` entry matches gatus/meridian pattern; `base-image-update.yml` iterates `cfg.get("addons")` keys; `cups/.upstream.yaml` absent |
| 8  | README/DOCS document every D-05 option and the reflector-default-off rationale (D-07) and no-watchdog (D-08) | VERIFIED | DOCS.md options table lines 10-12, line 249; README.md lines 10-33 |
| 9  | Root README lists the cups add-on | VERIFIED | README.md line 85 "### [CUPS Print Server](./cups)" |
| 10 | Read-only migration-suggestion script (D-13) | VERIFIED | `internal/cups-migration-suggestion.sh` only issues `ha apps info` + `lpstat -v` (no install/uninstall/restart); shellcheck clean; DOCS "Migrating from f1c878cb_cups" filled (placeholder grep = 0) |
| 11 | `cups` installed and running on haos-op3050-1 (D-12) | VERIFIED | Live: `ha apps info 72a005f5_cups` -> `state: started`, version 0.1.0-13; `app_72a005f5_cups` container up since 2026-09-29; printer registered with brlaser PPD |
| 12 | `f1c878cb_cups` removed (D-12) | VERIFIED | Live: `ha apps info f1c878cb_cups` -> `state: unknown`, `version: null` (store listing only) |
| 13 | avahi-resolve of the host IP returns the fixed `avahi_hostname`, no `-2` rename (D-11; 21-03 must_have) | FAILED | Live: `avahi-resolve -a 192.168.178.3` -> `cups-2.local`; `ps` -> `avahi-daemon: running [cups-2.local]`; `avahi-resolve-host-name cups.local` -> timeout; SSH/SFTP services announced as `cups-2` |
| 14 | AirPrint service resolvable by clients (browse-vs-resolve split removed) | FAILED | Live container and independent LAN client: `avahi-browse -t -r -p _ipp._tcp` -> `+ Brother-MFC-7460DN @ cups` then `Failed to resolve service ... Timeout reached` (same for `_printer._tcp`) |

**Score:** 12/14 truths verified

The 21-03 SUMMARY records D2 (mDNS fixes proven on the live host) as `verification: []`, `human_judgment: true`, with
the transcript explicitly "not re-captured". That claim is contradicted by today's live state.

### Deferred Items

None. Phase 22 is a paperless-ngx feature phase and does not cover mDNS hostname stability.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `cups/config.yaml` | Manifest + D-05 options | VERIFIED | host_network true, options/schema complete |
| `cups/build.yaml` | base image + VERSION | VERIFIED | amd64-base:3.24, VERSION 0.1.0 (matches 0.1.0-15 / README) |
| `cups/Dockerfile` | apk cups/avahi/dbus/python3 | VERIFIED | HA base image only |
| `cups/run.sh` | generate -> dbus -> avahi -> cupsd -> register | VERIFIED (with CR-02 caveat) | order correct; exit status of generate_config.py unchecked |
| `cups/generate_config.py` | avahi conf + registration | VERIFIED | executed; output correct |
| `internal/verify-cups-scaffold.sh` | docker smoke test | VERIFIED (exists, shellcheck clean) | asserts host-name/use-ipv6/enable-reflector strings; cannot reproduce a LAN hostname conflict (no other mDNS host) |
| `internal/cups-migration-suggestion.sh` | D-13 | VERIFIED | read-only |
| `internal/base-image-config.yaml` | cups entry | VERIFIED | |
| `cups/README.md`, `cups/DOCS.md`, root `README.md` | docs | VERIFIED | |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| run.sh | generate_config.py -> avahi-daemon.conf -> avahi-daemon | step 1 before step 4 | WIRED | live conf file present with expected values |
| generate_config.py printers handler | /tmp/register-printers.sh -> lpadmin | run.sh step 7 | WIRED | live printer registered |
| config.yaml options | /data/options.json -> generate_config.py | `load_options()` | WIRED | |
| avahi_hostname -> actual announced hostname | avahi-daemon runtime state | host-name= | NOT_WIRED in practice | conf says `cups`, daemon runs as `cups-2` |
| base-image-config.yaml cups: | base-image-update.yml | key iteration | WIRED | |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| avahi-daemon.conf | host-name / reflector / ipv6 | `/data/options.json` via bashio-provisioned options | Yes (live file matches options) | FLOWING |
| register-printers.sh | printers[] | options.json | Yes (live lpstat) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| avahi conf defaults | `build_avahi_conf({})` (interface stubbed) | reflector no / ipv6 no / host-name=cups | PASS |
| invalid hostname refused | `build_avahi_conf({"avahi_hostname":"a\nb"})` | exit 1 | PASS |
| printer registration builder | `build_printer_registration(...)` | P1 registered, P2 skipped, P3 rejected | PASS |
| add-on validators | `make validate-addons`, `make validate-versions` | pass | PASS |
| shellcheck | run.sh + 2 internal scripts | clean | PASS |
| Live: no slot exhaustion | `docker logs | grep -c "No slot available"` | 0 | PASS |
| Live: hostname stable | `avahi-resolve -a 192.168.178.3` | `cups-2.local` | FAIL |
| Live: service resolvable | `avahi-browse -t -r -p _ipp._tcp` (container and LAN client) | resolve timeout | FAIL |

All live checks were read-only (no restart or config change was performed).

### Probe Execution

SKIPPED -- no probes declared by the phase (`scripts/*/tests/probe-*.sh` absent; verification is by
`internal/verify-cups-scaffold.sh`, a docker build+run script not run here to avoid a heavy build; see Behavioral
Spot-Checks for the direct checks performed).

### Requirements Coverage

No REQUIREMENTS.md IDs are mapped to this phase (ROADMAP: "D-01..D-13 CONTEXT.md decisions"). PLAN frontmatter IDs:
21-01 [D-01,D-02,D-03,D-04,D-05,D-07,D-08,D-09,D-10,D-11]; 21-02 [D-06,D-08]; 21-03 [D-12,D-13]. D-01..D-13 are all
claimed by at least one plan; no orphans.

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| D-01 | 21-01 | standalone add-on, real options schema | SATISFIED | truth 1, 4 |
| D-02 | 21-01 | slug/folder `cups` | SATISFIED | truth 1 |
| D-03 | 21-01 | multiple printers from start | SATISFIED | truth 3 |
| D-04 | 21-01 | printers list of {name,uri,enabled}, lpadmin | SATISFIED | truth 3 |
| D-05 | 21-01 | minimum option surface | SATISFIED | truth 4 |
| D-06 | 21-02 | base-image tracking, no .upstream.yaml | SATISFIED | truth 7 |
| D-07 | 21-01 | reflector default no, exposed as option | SATISFIED | truth 2; live conf `enable-reflector=no`; 0 slot messages |
| D-08 | 21-01/02 | no watchdog | SATISFIED | truth 6 |
| D-09 | 21-01 | avahi conf generated from template | SATISFIED | truth 2 |
| D-10 | 21-01 | avahi_use_ipv6 default no | SATISFIED | truth 2; live conf `use-ipv6=no` |
| D-11 | 21-01/03 | fixed host-name to stop conflict-rename | BLOCKED (outcome) | conf directive present, but live daemon is `cups-2.local` and the service is unresolvable (truths 13, 14) |
| D-12 | 21-03 | install on haos-op3050-1, replace old | SATISFIED | truths 11, 12 |
| D-13 | 21-03 | migration suggestion output | SATISFIED | truth 10 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| cups/run.sh | 12 | unchecked `python3 /generate_config.py` (review CR-02) | Warning | the "Refusing to start" contract for an invalid `avahi_hostname` is not honoured; add-on starts with stock avahi config (the original bug) |
| cups/generate_config.py | 1016 | `set -e` in register-printers.sh (review WR-09) | Warning | one bad printer aborts registration of later printers (D-03 multi-printer) |
| cups/generate_config.py | 105-109 | NAME_RE rejects underscores for queue names (WR-05) | Warning | D-13 migration output can contain names the add-on drops |
| internal/cups-migration-suggestion.sh | 74-83 | drops `location`/`driver` (IN-06) | Info | migrating a socket printer reintroduces the blank-pages issue unless docs are read |
| internal/verify-cups-scaffold.sh | 447 | `docker restart` UUID test cannot fail (WR-07) | Warning | false confidence in the UUID-stability test (post-D-13 addition) |

No unreferenced TBD/FIXME/XXX markers in files changed by the phase.

### Code Review Cross-Reference (21-REVIEW.md, all 20 findings "open")

- Touch Phase 21 must-haves: CR-02 (D-11 refuse-to-start / startup guard; reinforces gap 13), WR-09 and WR-05 (D-03/D-04/D-13
  edge cases), WR-04 (trailing-newline defeats the T-21-01 validation claim on `avahi_hostname`: `fullmatch` needed),
  IN-06, WR-07.
- Out of Phase 21 must-have scope (Phase 22 / extras): CR-01 (print-history poller), CR-03, WR-01 (admin password
  script), WR-02, WR-03, WR-06, WR-08, WR-10, IN-01..IN-05, IN-07. Not counted as failures here.
- None of the review findings explain the live `cups-2` rename; that gap is an independent observation.

### Human Verification Required

None added: the failure is directly observable and reproduced from two vantage points. A human decision is needed only
on whether to restart the live add-on to test if the rename recurs on every start (this verification did not mutate
the host).

### Gaps Summary

Everything that is a repo artifact or a static decision (D-01..D-10, D-12, D-13) checks out: the generated Avahi config
is correct, the option schema/registration works, docs/tracking exist, the new add-on runs on haos-op3050-1 and the old
one is gone. The slot-exhaustion leg is fixed (reflector off, zero slot messages in the live log).

The phase goal's second leg -- the hostname-conflict rename -- is not achieved in the live system today. The generated
`host-name=cups` is respected as a request, but avahi-daemon lost the probe at its last start and runs as `cups-2.local`
indefinitely, and the CUPS-advertised printer service cannot be resolved by any client (same browse-OK/resolve-fail
signature as the original DIAGNOSIS). The 21-03 SUMMARY's claim that D-11 was empirically proven on the host is not
backed by retained evidence (`verification: []`) and does not hold now. The add-on has no recovery or guard for a lost
hostname probe, and the docker smoke test cannot reproduce a LAN-side conflict.

Informational: the live host runs 0.1.0-13 and the store reports `version_latest` 0.1.0-13, whereas the repo is at
0.1.0-15 (Phase 22 changes not yet deployed). A redeploy/restart would also be the natural moment to retest the rename.

Suggested next step: `/gsd-plan-phase 21 --gaps` -- diagnose why the probe conflicts on this host (stale cache from
the previous instance vs. a mDNS proxy/repeater), add a startup guard in `run.sh` that confirms Avahi claimed
`avahi_hostname` before cupsd publishes (and handles/logs a lost claim), fix CR-02 together with it, and extend the
rollout verification to include `avahi-browse -r _ipp._tcp` from a LAN client.

---

_Verified: 2026-10-03_
_Verifier: Claude (gsd-verifier)_
