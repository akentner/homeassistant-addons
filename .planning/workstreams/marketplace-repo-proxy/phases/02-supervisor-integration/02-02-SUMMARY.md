---
phase: 02-supervisor-integration
plan: 02
subsystem: api
tags: [supervisor, store-reload, rate-limit, status-json, sync-loop]

requires:
  - phase: 02-supervisor-integration
    provides: "02-01: SupervisorClient.reload_store, Registrar.after_cycle hook, SupervisorStateWriter with reload defaults, fake Supervisor"
provides:
  - "StatusWriter.head_changes: lower-case keys whose served head moved this cycle, measured against the carried status.json head"
  - "Registrar reload gate: clock/wall keywords, interval_seconds, last_reload_at, reload_pending, window_open, request_reload, _send_reload, work_due, run_due"
  - "after_cycle(status_doc, head_changes): reload only for repositories with in_store true before the pass (D-28)"
  - "SupervisorStateWriter.set_reload / reload_state; typed carry-over of the reload section"
  - "SyncService.wait_reason value `supervisor`; run_forever dispatch to Registrar.run_due without a sync cycle"
affects: [02-03, 02-04, 02-05, 02-06, phase-3-gui]

actuals:
  tokens: 7281
  tasks: 3
  commits: 7
plan_head_before: fe0f2f34346e2743b2c11226db1af05d995cf24b
plan_head_after: c4638eaeaa503575ed5ece2e27e4a49f6ed89eac

tech-stack:
  added: []
  patterns:
    - "Change detection against persisted state (carried head) instead of the per-container bare-repo snapshot"
    - "Rate-limit window closes before the call (last_reload_at set first); pending flag persisted, clock in memory"
    - "Wait-loop wake-up reason for side work that never becomes a sync cycle"

key-files:
  created: []
  modified:
    - marketplace-repo-proxy/app/status.py
    - marketplace-repo-proxy/app/registration.py
    - marketplace-repo-proxy/app/supervisor_state.py
    - marketplace-repo-proxy/app/sync.py
    - marketplace-repo-proxy/tests/test_status.py
    - marketplace-repo-proxy/tests/test_registration.py
    - marketplace-repo-proxy/tests/test_sync.py
    - marketplace-repo-proxy/tests/fake_supervisor.py

key-decisions:
  - "supervisor_state masks the reload message with app.gitops.sanitize instead of importing app.supervisor.mask_text: the Plan 01 import boundary allows only registration and sync to import the client module; the Registrar masks with mask_text before it calls set_reload"
  - "_send_reload catches every exception from the client call and records it as a failed reload (pending stays true, window stays closed), so the deferred reload is never lost and the wait loop cannot spin"
  - "A deferral logs `store reload: deferred until {UTC}` each time a cycle wants a reload inside a closed window (at most once per cycle)"
  - "The carried reload section of supervisor.json is type-checked field by field (wrong types fall back to defaults)"

patterns-established:
  - "tests/test_registration.py: Clock, _gated, _gate_options, _registered_stub, _reload_doc helpers for reload-gate tests (Plans 03-05 can reuse)"
  - "tests/test_sync.py: StubRegistrar and the registrar= keyword of _service for wait-loop tests"

requirements-completed: [MRP-09]

coverage:
  - id: D1
    description: "status.json head_changes: a real upstream change is told apart from a first-ever sync, a restart or a recreated container"
    requirement: MRP-09
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_status.py -k head_change (4 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Reload gate: one POST /store/reload per interval for a head change of a repository in the store before the pass; pending on a closed window; failed reload keeps pending; masked message in supervisor.json"
    requirement: MRP-09
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_registration.py -k reload (12 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Wait-loop supervisor wake-up: a deferred reload is sent when its window opens without a sync cycle, also after a restart"
    requirement: MRP-09
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_sync.py -k supervisor (3 tests); test_registration.py test_work_due_follows_pending_and_the_window, test_restart_*"
        status: pass
    human_judgment: false
  - id: D4
    description: "No reload storm on container start: the verify container (first-ever sync) sends no POST /store/reload"
    requirement: MRP-09
    verification:
      - kind: e2e
        ref: "flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh (step 4b: exactly 2 POST requests)"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-11-18
status: complete
---

# Phase 2 Plan 02: Store reload gate Summary

**Upstream changes of a registered repository now trigger one `POST /store/reload` per sync interval at most, measured against the head carried in `/data/status.json`, with a persisted `pending` flag that the sync wait loop sends as soon as the window opens.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-11-18T21:42:17Z
- **Completed:** 2026-11-18T21:55:43Z
- **Tasks:** 3
- **Files modified:** 8 (0 created, 8 modified)

## Accomplishments

- `StatusWriter.head_changes` holds the lower-case keys of repositories whose served head moved in the current cycle. It compares against the head carried from the previous `status.json`, so a first-ever sync, a `docker restart` and a recreated container with an unchanged upstream report nothing. `begin_cycle` clears the set. `refs_changed`, `REASONS` and every contract field are unchanged.
- `Registrar.after_cycle(status_doc, head_changes)` notes which repositories had `in_store` true before the pass (D-28: the registration value is not compared, so `leftover` counts), runs the registration pass, then calls `request_reload()` once when a changed repository was in the store, or when a pending reload's window is open. A repository added in the same pass does not trigger a reload.
- The window is open when `last_reload_at is None` or `clock() - last_reload_at >= interval_seconds`. `_send_reload` sets `last_reload_at` before the call. An `ok` result clears `pending` and logs `store reload: ok`. A failure, refusal or exception keeps `pending`, records `last_result: failed` with a masked message and logs `store reload: failed: {message}` at warning. A closed window sets and persists `pending` and logs `store reload: deferred until {UTC}`.
- `/data/supervisor.json` `reload` is filled through `set_reload` (`last_result` must be None, `ok` or `failed`) and read through `reload_state()`, which returns a copy. A carried section is type-checked field by field.
- `SyncService.wait_reason` returns `supervisor` after the stop and trigger checks when `registrar.work_due()` is true. `run_forever` then calls `run_supervisor_work()` → `Registrar.run_due()` without `run_cycle_once`, so `sync.reason` never becomes `supervisor`. A failure logs `store work failed: {Type}` and the loop goes on.
- A `reload.pending` persisted by a previous process is sent after the first cycle of the new process, because the in-memory window starts open.

## Task Commits

1. **Task 1: head_changes against the carried head**: `63d7ff9` (test, RED: 4 failed), `a8b97fd` (feat, GREEN)
2. **Task 2: reload gate once per interval**: `dc3a668` (test, RED: 10 failed), `a2170a9` (fix: fake request-log race, see Deviations), `2b3ed9d` (feat, GREEN)
3. **Task 3: deferred reload from the wait loop**: `7210623` (test, RED: 5 failed), `c4638ea` (feat, GREEN)

**Plan metadata:** see the docs commit that adds this SUMMARY.

## Verification (commands and results)

| Command | Result |
|---------|--------|
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests/test_status.py -q` | 16 passed |
| same, `-k head_change` | 4 passed (required at least 4) |
| `grep -c head_changes marketplace-repo-proxy/app/status.py` | 5 (required at least 3) |
| removed-contract-line guard over `git diff` of `app/status.py` (`REASONS\|STATUS_CODES\|refs_changed`) | 0 |
| `... pytest marketplace-repo-proxy/tests/test_registration.py -q` | 58 passed |
| same, `-k reload` | 12 passed (required at least 7) |
| `grep -c 'reload_store(' app/registration.py` / `grep -c head_changes app/sync.py` | 1 / 1 |
| `... pytest marketplace-repo-proxy/tests -q` (full suite) | 322 passed (repeated runs green) |
| `... pytest marketplace-repo-proxy/tests/test_sync.py -q -k supervisor` | 3 passed (required at least 3) |
| `grep -c '"supervisor"' app/status.py` / `grep -c 'work_due()' app/sync.py` | 0 / 1 |
| `pre-commit run --files` over the 7 plan files | exit 0, all hooks passed |
| `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh` | exit 0, 97 `✓`, 0 `✗`; step 4b still sees exactly 2 `POST` (no reload on a first-ever sync) |
| `git diff --quiet` over Dockerfile, rootfs, config.yaml, build.yaml, README.md | unchanged (no version or Dockerfile change) |
| privacy grep (IPs, e-mails) over every staged diff | nothing found |

## Files Created/Modified

- `marketplace-repo-proxy/app/status.py`: `head_changes` set, filled in `record`, cleared in `begin_cycle`
- `marketplace-repo-proxy/app/registration.py`: reload gate (`after_cycle`, `window_open`, `request_reload`, `_send_reload`, `work_due`, `run_due`), module docstring
- `marketplace-repo-proxy/app/supervisor_state.py`: `_reload_section`, `set_reload`, `reload_state`, `RELOAD_RESULTS`
- `marketplace-repo-proxy/app/sync.py`: passes `head_changes` to `after_cycle`, `supervisor` wake-up reason, `run_supervisor_work`
- `marketplace-repo-proxy/tests/test_status.py`: 4 head-change tests
- `marketplace-repo-proxy/tests/test_registration.py`: 13 reload-gate, wait-loop and restart tests; `StubClient.reload_store`
- `marketplace-repo-proxy/tests/test_sync.py`: 3 wake-up tests, `StubRegistrar`, `registrar=` keyword of `_service`
- `marketplace-repo-proxy/tests/fake_supervisor.py`: request log and `store.json` written before the answer

## Decisions Made

- The reload message is masked twice. The Registrar applies `mask_text`, and `set_reload` applies `app.gitops.sanitize` again. `supervisor_state` does not import the client module (see Deviation 2).
- `_send_reload` treats every exception from the client call as a failed reload. `pending` stays set and the window stays closed, so the reload is retried in the next window and the loop cannot spin.
- A deferral is logged each time a cycle wants a reload while the window is closed, which is at most once per cycle.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The fake Supervisor logged a request only after it had answered**
- **Found during:** Task 2 (full-suite run)
- **Issue:** `_handle` sent the response and only then called `state.record`/`state.save`. A client could return and read the request log before its request was in it. Plan 01's `test_supervisor.py::test_one_log_line_per_sent_request` and `test_store_calls_against_the_fake` failed in about 1 of 8 runs. The new fake-based reload test reads the same log.
- **Fix:** `_send` now records the entry and saves `store.json` before the answer is written. An add after a client timeout is still recorded, which keeps the Plan 01 `asyncio.shield` fidelity.
- **Files modified:** `marketplace-repo-proxy/tests/fake_supervisor.py` (outside the plan's file list; a test harness only)
- **Verification:** 25 consecutive runs of `test_supervisor.py` + `test_registration.py` passed, and the verify script stayed green (the container runs the same fake).
- **Committed in:** `a2170a9`

**2. [Rule 3 - Blocking] `set_reload` cannot import `mask_text` without breaking the Plan 01 import boundary**
- **Found during:** Task 2
- **Issue:** The plan says the message goes "through `mask_text`" in `supervisor_state.py`. Importing `app.supervisor` there fails `test_supervisor.py::test_static_import_boundaries`, which allows only `registration` and `sync` to import the client module. That boundary keeps the CLI and other readers of `supervisor_state` from loading the client.
- **Fix:** The Registrar masks the Supervisor text with `mask_text`. `set_reload` and the carried section mask again with `app.gitops.sanitize`, the 32-hex masker that `mask_text` builds on. T-02-13 still holds: tests check that the full hash appears neither in the state file nor in the log.
- **Files modified:** `marketplace-repo-proxy/app/supervisor_state.py`
- **Committed in:** `2b3ed9d`

**3. [Rule 1 - Bug] Wrong expectation in a Task 3 RED test**
- **Found during:** Task 3 GREEN
- **Issue:** `test_supervisor_work_runs_from_the_wait_loop_without_a_sync_cycle` expected two `after_cycle` calls. The last fake cycle sets `stop`, and Plan 01's guard skips the store pass while the service is stopping.
- **Fix:** The test now expects one `after_cycle` call, with a comment explaining why.
- **Committed in:** `c4638ea`

**4. [Rule 2 - Robustness] Typed carry-over of the `reload` section**
- **Found during:** Task 2
- **Issue:** Plan 01 carried the previous `reload` dict verbatim, so a foreign file could seed a non-bool `pending` or an unmasked message.
- **Fix:** `_reload_section` keeps only correctly typed fields, masks the message and otherwise falls back to the defaults. The Registrar also seeds `reload_pending` only from `pending is True`.
- **Committed in:** `2b3ed9d`

---

**Total deviations:** 4 auto-fixed (2 Rule 1, 1 Rule 2, 1 Rule 3).
**Impact on plan:** correctness and test reliability only. There was no scope creep and no Dockerfile, rootfs, version or docs change.

## TDD Gate Compliance

Each task has a RED commit before its GREEN commit: Task 1 `63d7ff9` (4 failed) → `a8b97fd`; Task 2 `dc3a668` (10 failed) → `2b3ed9d`; Task 3 `7210623` (5 failed) → `c4638ea`. No refactor commits were needed. The `fix` commit `a2170a9` repairs the test harness and sits between Task 2's RED and GREEN commits.

## Known Stubs

- `supervisor.json` `leftovers[]` and `requests[]` still hold empty defaults. Plans 03-04 fill them. `run_due`/`work_due` cover only the pending reload; Plan 03 extends them with the request queue, as the plan intends.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 03 can extend `Registrar.work_due`/`run_due` with the request queue. The `supervisor` wake-up reason and `run_supervisor_work` already dispatch to them.
- Plan 05 (container proof) can drive a head change against the fake Supervisor. The fake now logs `POST /store/reload` before it answers and counts it in `store.json` `reloads`.

## Self-Check: PASSED

- All 8 modified files exist on disk.
- Commits `63d7ff9`, `a8b97fd`, `dc3a668`, `a2170a9`, `2b3ed9d`, `7210623` and `c4638ea` are ancestors of HEAD.
- The measured commit count from the ledger is 7.
