---
phase: 02-supervisor-integration
plan: 05
subsystem: testing
tags: [verify, docker, supervisor, fake-supervisor, rotation, store-reload, secret-hygiene]
status: complete

requires:
  - phase: 02-supervisor-integration
    provides: "02-01: Registrar, SupervisorClient, supervisor.json (D-28/D-29), fake Supervisor container, d29_check; 02-02: store reload with window and persisted pending; 02-03: mrp local remove/status, leftovers, request queue; 02-04: mrp local rotate --yes, D-11 warning, revoked leftovers"
provides:
  - "internal/verify-marketplace-repo-proxy.sh: Docker proof of ROADMAP Phase 2 criteria 1-4 next to Phase 1 criteria 1-5; last line `✓ marketplace-repo-proxy Phase 2 verified (Supervisor integration, criteria 1-4)`"
  - "Helpers start_proxy, recreate_proxy, fake_count, fake_field, wait_fake_field, reload_of, wait_reload, supervisor_gets, wait_gets, local_hashes, write_options; options_json takes an optional register_local argument"
  - "Steps (4c), (9) extended, (9b), (9c), (15), (16), (16b), (17), (18), (19)"
affects: [02-06, 02-07, phase-3-gui]

actuals:
  tokens: 7474
  tasks: 2
  commits: 2
plan_head_before: a433907f3a059b55da70e90eec36ba28dd80a31f
plan_head_after: 621b6c8c3ac16487823fd031613b1121221eb106

tech-stack:
  added: []
  patterns:
    - "Negative checks after a recreate or restart wait for the next pass's store-list line (`supervisor GET /store/repositories: ` count), so a late POST or reload cannot slip past them"
    - "Deferred-reload check waits for `reload.pending` true, which the pass writes when it decides, before it asserts that the reload count did not change"
    - "Supervisor-unreachable stand-in: `docker network disconnect` of the fake, reconnect with `--alias supervisor`; the fake keeps its in-memory store"
    - "Token positive control through a needles file of `NAME=value` lines matched with `grep -xF -f` against /proc/{pid}/environ inside the container"

key-files:
  created: []
  modified:
    - internal/verify-marketplace-repo-proxy.sh

key-decisions:
  - "Step (16b) first restores the valid PAT and restarts: only repositories whose last sync is ok want a registration (D-07) and get `error` when the store list fails; step (12) leaves the wrong PAT in place"
  - "Step (16b) checks the list-failure log line as built and pinned by Plan 01 (`store list unavailable: unreachable`); the plan text named the add-failure line"
  - "Step (13) compares dave's masked startup lines before and after the restart, because step (9c) recreates the container after dave exists"
  - "No product file changed: every Phase 2 container check passed against the code of Plans 01-04"

patterns-established:
  - "recreate_proxy = docker rm -f + start_proxy + wait for a store-list line and both synced repositories ok"
  - "fake_field '<python expression on doc>' [args] reads store.json of the fake (reloads, heads, repositories)"

requirements-completed: [MRP-07, MRP-08, MRP-09, MRP-10]

coverage:
  - id: D1
    description: "Criterion 1 / MRP-08: a container recreate with the same /data and hostname and an unchanged upstream sends no POST /store/repositories and no reload; both local hashes are unchanged; no `store reload:` line"
    requirement: MRP-08
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh, step (4c)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Criterion 2 / MRP-09: one reload after an upstream change that pulls the new SHA through the proxy; a second change inside the window is deferred (pending true, still 1 reload); a recreate sends the pending reload once (2 reloads, second SHA)"
    requirement: MRP-09
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh, steps (9), (9b), (9c)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Criterion 3 / MRP-10: rotate without --yes is refused with the D-11 warning and no Supervisor request; with --yes and the old slug in use: POST before the refused DELETE, revoked in_use leftover, old URL 404 and new URL 200 at once, no full URL anywhere; mrp local remove retries the leftover; register_local false sends no POST and mrp local remove gives missing"
    requirement: MRP-10
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh, steps (15), (16), (17)"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-28/D-29 in a container: missing, registered, leftover and error (Supervisor disconnected: error unreachable, fixed message, in_store kept, serving unaffected); d29_check passes after (4b), (15), (16b), (18)"
    requirement: MRP-07
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh, steps (4b), (15), (16b), (18)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Criterion 4 / MRP-07: every fake request is allow-listed with a valid token, exactly 3 POST repositories, 3 DELETE, 2 reloads; Supervisor sentinel absent from logs and /data state files, present in app.sync's environment under SUPERVISOR_TOKEN and HASSIO_TOKEN, absent from lighttpd and app.watch; no full hash (incl. every local hash) in logs or supervisor.json; supervisor.json mode 600"
    requirement: MRP-07
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh, steps (18), (19)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-11-19
---

# Phase 2 Plan 05: Container proof of the Supervisor integration Summary

**One `bash internal/verify-marketplace-repo-proxy.sh` run now proves ROADMAP Phase 2 criteria 1-4 against the built
image and the fake Supervisor container: no re-registration after a recreate, one store reload per interval with a
persisted pending reload, confirmed rotation with an immediate revoke and a refused DELETE, its retry, all four D-28
values (incl. `error` while the Supervisor is unreachable), removal with `register_local: false`, an exact request audit
and token/hash hygiene.**

## Performance

- **Duration:** about 9 min (three serialized verify runs of about 3-4 min each)
- **Started:** 2026-11-18T23:42:14Z
- **Completed:** 2026-11-18T23:51:34Z (UTC)
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- **Step (4c), container recreate:** `recreate_proxy` (`docker rm -f` plus `start_proxy` with the same `/data` and
  hostname and a fresh `/srv/git`). After the next pass's store-list line, the fake still has 2
  `POST /store/repositories` and 0 reloads. Both `local` hashes are unchanged and the log has no `store reload:` line.
- **Step (9), upstream change:** exactly 1 reload. The fake's `heads` value for the private-addons slug is the new full
  SHA, `reload.last_result` is `ok` and `pending` is false. The log has `supervisor POST /store/reload: 200` and
  `store reload: ok`.
- **Step (9b), second change inside the window:** `reload.pending` is true, the count stays at 1 and the log has
  `store reload: deferred until`.
- **Step (9c), recreate:** the pending reload is sent once (2 reloads). It pulls the second SHA and `pending` is false
  afterwards.
- **Step (15), rotation with a refusal:**
    - Without `--yes`: exit 1, the D-11 warning and `error: confirmation_required`. The request log, the slug and the
      old URL (200) are unchanged.
    - With `--yes` and the old slug in the fake's in-use file: `refused: in_use`. The last POST comes before the
      refused DELETE (status 400) of the old slug.
    - `supervisor.json` has one leftover: `in_use`, `local.{old}`, `revoked: true`. The registration is `leftover`,
      `in_store` is true and the new slug is in the fake store.
    - `access.json` has no `local.*` label left. The old URL answers 404 and the new one 200.
    - The log has the `rotated` and `leftover` lines, and `mrp local status` prints a `leftover` line.
    - No full store URL appears in the log, `supervisor.json` or the status output, and `d29 ok`.
- **Step (16), retry:** with the in-use file empty, `mrp local remove` prints `removed:`. The old URL stays 404 and the
  new one 200. No leftover is left, the registration is `registered` and the old slug is gone from the fake store.
- **Step (16b), Supervisor unreachable:**
    - The valid PAT is restored first (see Deviations).
    - Disconnecting the fake gives `error`/`unreachable` with `The Supervisor is unreachable` for both repositories.
      `in_store` stays true.
    - The log has `store list unavailable: unreachable`, the new URL still answers 200 and `d29 ok`.
    - After the reconnect, both are `registered` with `error` null and no new POST.
- **Step (17), `register_local: false`:** after the restart there is no POST and private-addons stays `registered`.
  `mrp local remove example-org/branched` removes its slug, its `local` URL answers 404 and it is `missing` with
  `in_store` false.
- **Step (18), request audit:** every request is allow-listed with `auth: ok`. The counts are exactly 3
  `POST /store/repositories`, 3 `DELETE` and 2 `POST /store/reload`. Every registration value is in the D-28 set and the
  final `d29 ok`.
- **Step (19), secret hygiene:**
    - Needles files hold the sentinel, its two `NAME=value` lines and 8 full hashes, including all three `local`
      hashes.
    - No sentinel in `docker logs`, `status.json`, `supervisor.json` or `access.json`.
    - No hash in `docker logs` or `supervisor.json`, and `supervisor.json` has mode 600.
    - Positive control: `app.sync` has the sentinel under both names.
    - `lighttpd` and `app.watch` have neither name nor the sentinel (PIDs read again after the restarts).

## Verification

| Command | Result |
| ------- | ------ |
| `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh` (baseline, before Task 1) | exit 0, 97 `✓` lines |
| same, after Task 1 | exit 0, 113 `✓`, no `✗`, `==> (4c)`, `==> (9b)`, `==> (9c)` once each |
| same, after Task 2 (committed script) | exit 0, 159 `✓` (+62 over baseline, +46 over Task 1), no `✗`, `==> (16b)` once, last line `✓ marketplace-repo-proxy Phase 2 verified (Supervisor integration, criteria 1-4)` |
| `shellcheck internal/verify-marketplace-repo-proxy.sh` | clean |
| `pre-commit run --files internal/verify-marketplace-repo-proxy.sh` | all hooks Passed or Skipped |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 436 passed (no product file touched) |
| grep counts | `recreate_proxy` 3, `store reload: deferred until` 2, `never run it in two worktrees at the same time` 1, `mrp local rotate` 10, `mrp local remove` 7, `confirmation_required` 2, `network disconnect` 1, `d29_check` 5, `HASSIO_TOKEN=` 2 |

The run output has no 32-hex value. No `mrp-verify*` container or network is left after the runs. All runs were
serialized with `flock ~/.cache/mrp/verify.lock`.

## Task Commits

1. **Task 1: recreate idempotency and once-per-interval store reload** - `92893ba` (test)
2. **Task 2: rotation, retry, D-28 values, request audit and token hygiene** - `621b6c8` (test)

## Files Created/Modified

- `internal/verify-marketplace-repo-proxy.sh`: new helpers, steps (4c), (9b), (9c) and (15) to (19), step (9) extended,
  the step (12) options rewrite moved into `write_options`, step (13) made count-based, and the header updated for
  Phase 2. The header still says the script must never run in two worktrees at the same time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Step (16b) restores the valid PAT before it disconnects the Supervisor**
- **Found during:** Task 2 (while writing the step, before the first run)
- **Issue:** Step (12) restarts the proxy with a wrong PAT, so every repository is `auth_failed` from then on. Per D-07
  and the Plan 01 contract (`register_pass`), only repositories whose last sync is `ok` want a registration, and only
  those get `error` when the store list fails. Without a fix, the plan's expected `error` could never appear. The
  product works as specified.
- **Fix:** Step (16b) first writes `options_json "${PAT}"` (valid PAT) through stdin and restarts the proxy. It waits
  until both repositories are `ok` and a new store-list line appears, then disconnects the fake. Step (17) also uses the
  valid PAT; only `register_local` changes. `options_json` gained an optional `register_local` argument, and the
  options rewrite became the `write_options` helper.
- **Impact:** one extra restart. The restart caused no request beyond GETs, and the exact counts of step (18) hold.
- **Commit:** `621b6c8`

**2. [Plan text mismatch] Log line checked in step (16b)**
- **Issue:** The plan expects `store: registration of example-org/private-addons failed: store list unavailable`. That
  text belongs to the add-failure path. Plan 01 specified and built the store-list failure warning as
  `store list unavailable: {status|timeout|unreachable}` (`app/registration.py:167`), logged once per pass.
- **Fix:** The step checks for the exact line `store list unavailable: unreachable`. The check is just as strict (an
  exact string that also names the cause). No product change was made.
- **Commit:** `621b6c8`

**3. [Rule 1 - Bug in the check] Step (13) would have passed trivially after the recreate**
- **Found during:** Task 1
- **Issue:** Step (13) relied on dave not existing before the restart. Step (9c) recreates the container after dave
  exists, so the init of the recreated container already logs dave's line.
- **Fix:** Step (12) counts dave's masked startup lines before the restart. Step (13) requires more lines after the
  restart.
- **Commit:** `92893ba`

**4. [Rule 2 - False-green guards] Small additions inside the plan's scope**
- Step (4c) runs one more `mrp sync` and waits for the second store-list line. Only then does it check "still 2 POST,
  0 reloads", so a late POST or reload from the first pass cannot slip past.
- Step (9b) waits for `reload.pending` true, which the pass writes when it decides, before it checks that the count is
  still 1.
- Step (15) also checks that the refused DELETE got status 400.
- Step (17) also checks that private-addons stays `registered` with `register_local: false` while its URL is listed
  (D-28 mapping).
- **Commits:** `92893ba`, `621b6c8`

---

**Total deviations:** 1 Rule 3, 1 plan-text mismatch, 1 Rule 1 and 1 Rule 2 group. No expected status, count or HTTP
code was relaxed and no check was dropped.
**Impact on plan:** test script only. No product, Dockerfile, rootfs, version or docs change.

## Known Stubs

None.

## Threat Flags

None. The script adds no new surface. It uses `docker exec --privileged` only for `/proc` reads, as in Phase 1.
T-02-24 to T-02-27 are mitigated as planned:

- exact counts and positive controls
- sentinels and needles files only
- runs serialized under flock
- the `cleanup` trap

## Issues Encountered

None. Every Phase 2 container check passed on the first run against the code of Plans 01-04.

## User Setup Required

None.

## Next Phase Readiness

- Plan 06 (DOCS) can name the verify script as the Phase 2 proof. It should describe the `store list unavailable:`
  warning as built, not as `registration of ... failed`.
- Plan 07 (live E2E) checks on the real host what the fake stands in for: clone on add, refusal text, reload pull and
  the recreate on an add-on update.

## Self-Check: PASSED

- `internal/verify-marketplace-repo-proxy.sh` exists (1174 lines, at least 750 required) and contains `Phase 2 verified`
  and `requests.jsonl`.
- Commits `92893ba` and `621b6c8` are ancestors of HEAD.
