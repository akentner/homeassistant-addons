---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 07
subsystem: infra
tags: [cups, avahi, mdns, airprint, live-verification, haos-op3050-1, gap-closure]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: "21-04 live verifier and RED baseline; 21-05 avahi startup guard and publish-aaaa-on-ipv4=no; 21-06 hardening, docs and the 0.1.0-16 bump"
provides:
  - "Published image amd64-cups:0.1.0-16 (tag cups/v0.1.0-16), anonymously pullable"
  - "Live proof on haos-op3050-1: update plus two plain restarts all end in RESULT: PASS"
  - "Verdict for 21-VERIFICATION truths #13 and #14 and for D-10/D-11 completion"
affects: [phase-21-verification]

plan_head_before: a36e6bdb1e620a2ba4e38b62a02e1574f8a8fd3a
actuals:
  tasks: 3
  commits: 0

key-files:
  created: []
  modified: []

key-decisions:
  - "Publication was done by the orchestrator on explicit user instruction: main merged with origin/main (merge, not rebase, to keep the SHAs cited in .planning stable), pushed, then tag cups/v0.1.0-16 via make update-version"
  - "Live mutations (update, restarts) were run by the user from their own shell because the auto-mode classifier blocks remote shell writes; the orchestrator only ran read-only verification"
  - "The optional iPhone/iPad/Mac print check was not performed and is not claimed"

requirements-completed: [D-11, D-12]

completed: 2026-10-04
status: gaps_found
---

# Phase 21 Plan 07: Live proof on haos-op3050-1 Summary

**The fixed host name `cups.local` is claimed on the first guard attempt after an add-on update and after two plain
restarts, but it was NOT kept on the restart-2 boot: avahi renamed itself to `cups-2` 2 min 34 s after the claim.
Truths #13 and #14 are therefore still open.**

## Task 1: Publication

- `main` was 50 commits ahead of and 5 behind `origin/main` (bot updates for `litellm` and `meridian`, no overlap).
  Merged `origin/main` into `main` (no conflicts), pushed (`f52a1b2..a36e6bd`).
- Tag `cups/v0.1.0-16` created with `make update-version ADDON=cups VERSION=0.1.0-16`; it points at `a36e6bd` (HEAD).
- The push changed only `cups/`, `internal/` and `.planning/`, so `build.yml` built only `cups`. Run `37142688282`:
  success (`cups (amd64) / build`).

## Task 2: Image availability and pre-update baseline

- `./internal/verify-image-availability.sh --addon cups --grace-minutes 0`: `amd64-cups:0.1.0-16` anonymously pullable.
- Baseline on the old live add-on (version `0.1.0-13`, state started), `--assert --mask`:

```text
PASS conf-reflector, PASS conf-ipv6, PASS slot-exhaustion (0 lines)
FAIL daemon-fqdn: GetState=2 GetHostNameFqdn=cups-2.local, expected cups.local
FAIL lan-forward-v4: cups.local resolved to 'nothing' from this LAN client
FAIL lan-no-aaaa: cups-2.local still publishes an AAAA record although avahi_use_ipv6=false
FAIL lan-service-resolve: no resolved _ipp._tcp record (browse-works/resolve-fails)
RESULT: FAIL (4 failed)
```

The host name loss therefore recurred on `0.1.0-13` after the transient recovery seen at 18:00 on 2026-10-03.

## Task 3: Live update and two restarts

Update note: the Supervisor reported `update_available: true`, but the UI button was inactive; the update was started
with `ha apps update 72a005f5_cups` (user, own shell). Cause of the inactive button not established.

All three events were observed from this LAN client. Each boot is identified by a distinct avahi
`Local service cookie`:

| Event | Boot (local time) | Cookie | Guard | `--assert` |
|-------|-------------------|--------|-------|------------|
| Update to 0.1.0-16 (container recreated) | 2026-10-03 23:19 / cupsd 23:22 | 2407587356 | `hostname claimed: cups.local (attempt 1/3)`, `RESULT: claimed` | `RESULT: PASS` (settle-wait 60) |
| Restart 1 | 2026-10-03 23:30:56 | 1196832960 | `hostname claimed: cups.local (attempt 1/3)`, `RESULT: claimed` | `RESULT: PASS` (23:32, settle-wait 60) |
| Restart 2 | 2026-10-04 09:12 | 3354254864 | `hostname claimed: cups.local (attempt 1/3)`, `RESULT: claimed` | `RESULT: PASS` (settle-wait 60) |

Each of the three runs printed:

```text
PASS conf-reflector, PASS conf-ipv6, PASS slot-exhaustion (0 lines)
PASS daemon-fqdn: GetState=2 and GetHostNameFqdn=cups.local
PASS lan-forward-v4: cups.local resolves to the host IPv4 from this LAN client
PASS lan-no-aaaa: cups.local publishes no AAAA record
PASS lan-service-resolve: 1 resolved _ipp._tcp record(s) point at cups.local / host IPv4
RESULT: PASS
```

Additional observations:

- `ha apps info`: version `0.1.0-16`, state `started` after every event.
- avahi's log is now visible in the add-on log (`Server startup complete. Host name is cups.local.`, clean
  `Got SIGTERM` shutdown), which was impossible on 0.1.0-13 (dead `/dev/log`).
- A second assert on 2026-10-04 09:07, about 9.5 h after restart 1, was also `RESULT: PASS`.
- The avahi warning `Detected another IPv4 mDNS stack running on this host` is expected (HAOS host avahi and
  `mdns-repeater`, see 21-04 E2) and not new.

## Verdicts

| Truth | Verdict |
|-------|---------|
| #13 fixed host name claimed AND kept | **Open.** Claimed at boot 3 of 3; kept for 9.5 h on the restart-1 boot but lost on the restart-2 boot (see below) |
| #14 `_ipp._tcp` resolvable from a LAN client | **Open.** `PASS lan-service-resolve` held only while the name was held; fails again after the rename (browse works, resolve fails) |
| D-10 no AAAA over IPv4 | **Closed** (`PASS lan-no-aaaa` in every run, also after the rename) |
| D-11 / D-12 live proof with retained transcript | Transcripts retained; they prove the claim at boot, not that the name is kept |

## Correction after re-verification (2026-10-04)

The first version of this summary reported #13/#14 as closed. That was wrong: every `--assert` PASS above was taken
within about 2 minutes of the boot. The add-on log of the restart-2 boot (container started 09:12:17) shows:

```text
[avahi-guard] INFO: hostname claimed: cups.local (attempt 1/3)      (09:12)
[avahi-guard] RESULT: claimed
Host name conflict, retrying with cups-2                             (09:14:57, same daemon, cookie 3354254864)
Server startup complete. Host name is cups-2.local.
```

Re-run at 09:21: `FAIL daemon-fqdn` (`cups-2.local`), `FAIL lan-forward-v4`, `FAIL lan-service-resolve`,
`RESULT: FAIL (3 failed)`. Cause in our code: `cups/avahi-guard.sh` is startup-only (returns after 5 stable polls), so a
conflict minutes later is neither detected nor retried, and cupsd keeps announcing the service with the stale target.
The conflicting announcer is still unidentified because avahi does not log the conflicting record without `--debug`
and the 21-04 capture experiment was never run.

## Limits of this proof

- Restart 1 and the update were not each followed by the plan's literal `--settle-wait 180`; 60 s was used, and the
  guard claimed on attempt 1 in every boot (worst-case guard duration was therefore not exercised).
- The loss is intermittent and NOT limited to cold start: the restart-1 boot held the name for at least 9.5 h, the
  restart-2 boot lost it after 2.5 min. Three clean claims at boot do not show that the name is kept.
- The conflict-capture experiment of 21-04 was never run, so a persistent foreign claimant of `cups.local` was
  neither proven nor excluded; the guard only makes a loss visible and keeps the published name consistent.
- The optional iPhone/iPad/Mac check (printer selectable and prints) was not performed.

## Out-of-scope observations (candidate follow-ups)

- `cupsd` logs `Unknown directive IdleExitTimeout on line 33 (and 12) of /etc/cups/cupsd.conf` on every start.
- `cups/print-history-poller.py:35` polls `lpstat -W completed -o` every 20 s, which makes cupsd log
  `Limiting Get-Jobs response to 500 jobs.` per poll (`POLL_INTERVAL_SECONDS = 20`).
- `cupsctl: Unable to connect to server: Bad file descriptor` once after a restart; absorbed by the retry in
  `cups/run.sh` (no `failed after retries` line).
- Host-level: `boot_fail` for another add-on and `no_current_backup` reported by the Supervisor.

## Deviations

- Task 1 was executed by the orchestrator on explicit user instruction rather than left to the user.
- Live mutations were executed by the user; no mutating command was run by an agent.
- `--settle-wait 60` instead of 180 (see Limits).
