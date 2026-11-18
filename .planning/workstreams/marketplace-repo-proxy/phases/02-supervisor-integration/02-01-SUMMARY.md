---
phase: 02-supervisor-integration
plan: 01
subsystem: api
tags: [supervisor, store-registration, urllib, fake-supervisor, docker-verify]

requires:
  - phase: 01-git-serving-core
    provides: "AccessStore (reserved `local` label, source `system`), Paths, status.json writer, urls/masking, jsonio, logsetup redactor, verify script"
provides:
  - "app/supervisor.py: the only Supervisor client (allow-list of four calls, hardened stdlib transport, masking)"
  - "app/supervisor_state.py: /data/supervisor.json single writer (D-28 registration value, D-29 Phase 3 interface)"
  - "app/registration.py: Registrar (`local` system user, GET then POST after an ok sync)"
  - "SyncService(registrar=...) hook after every cycle; token read only in app.sync"
  - "tests/fake_supervisor.py: stdlib fake Supervisor for pytest and the verify container"
  - "verify step (4b) with a fake Supervisor container (alias `supervisor`) and helper d29_check"
affects: [02-02, 02-03, 02-04, 02-05, 02-06, 02-07, phase-3-gui]

actuals:
  tokens: 24128
  tasks: 2
  commits: 3
plan_head_before: 13d12a7ec17f22523654a12912316ce1d2a8a5f2
plan_head_after: 47a90f75cb81483f2d0f8ca5daf61683e9f502b7

tech-stack:
  added: []
  patterns:
    - "Allow-list checked before any I/O; transport in one private method (`SupervisorClient._send`)"
    - "Callers report facts (`in_store`, `error`); the writer derives `registration` and `message` on every write"
    - "Fake Supervisor shared by pytest (in-process) and the verify script (container with network alias)"

key-files:
  created:
    - marketplace-repo-proxy/app/supervisor.py
    - marketplace-repo-proxy/app/supervisor_state.py
    - marketplace-repo-proxy/app/registration.py
    - marketplace-repo-proxy/tests/fake_supervisor.py
    - marketplace-repo-proxy/tests/test_supervisor.py
    - marketplace-repo-proxy/tests/test_registration.py
    - marketplace-repo-proxy/tests/test_manifest.py
  modified:
    - marketplace-repo-proxy/config.yaml
    - marketplace-repo-proxy/app/paths.py
    - marketplace-repo-proxy/app/sync.py
    - internal/verify-marketplace-repo-proxy.sh

key-decisions:
  - "Registration pass is skipped when the sync service is stopping, and a failing Registrar construction disables registration with one error line instead of ending the sync process"
  - "Registrations log and state keep the masked URL only; supervisor.last_error holds masked Supervisor text, repositories[].message only fixed templates"
  - "The fake Supervisor keeps an add when the client times out (asyncio.shield fidelity), so the next pass finds it with GET"

patterns-established:
  - "assert_d29_shape(doc, options) in tests/test_registration.py: reusable D-28/D-29 shape check for Plans 03-04"
  - "Verify helpers reg_of, wait_reg, fake_requests, d29_check over /data/supervisor.json and the fake's request log"

requirements-completed: [MRP-07, MRP-08]

coverage:
  - id: D1
    description: "Manifest gets hassio_api: true and hassio_role: manager and no other permission key"
    requirement: MRP-07
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_manifest.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Allow-listed Supervisor client: refusals before I/O, token only as unredirected bearer header, no proxy, no redirect, masked messages, one log line per call"
    requirement: MRP-07
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_supervisor.py"
        status: pass
      - kind: e2e
        ref: "flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh (step 4b request log, step 14 environ scans)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Self-registration: local system user per ok repository, internal store URL added when missing, fake Supervisor clones it through lighttpd"
    requirement: MRP-08
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_registration.py"
        status: pass
      - kind: e2e
        ref: "flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh (step 4b tracer line)"
        status: pass
    human_judgment: false
  - id: D4
    description: "/data/supervisor.json contract: D-28 value set via registration_value, D-29 Phase 3 interface, no full hash/URL/token"
    requirement: MRP-08
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_registration.py#test_registration_value_precedence, assert_d29_shape"
        status: pass
      - kind: e2e
        ref: "verify step 4b d29_check prints d29 ok"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-11-18
status: complete
---

# Phase 2 Plan 01: Supervisor registration tracer Summary

**The sync process now registers each `ok` repository's `local` store URL with the Supervisor through a four-call allow-listed stdlib client; a fake Supervisor container clones both URLs through lighttpd in the verify script.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-11-18T21:25:49Z
- **Completed:** 2026-11-18T21:39:14Z
- **Tasks:** 2
- **Files modified:** 11 (7 created, 4 modified)

## Accomplishments

- `config.yaml` has `hassio_api: true` and `hassio_role: manager`. No other permission key was added.
- `app/supervisor.py` refuses every call outside `GET`/`POST /store/repositories`, `DELETE /store/repositories/{8 hex}` and `POST /store/reload` before any network I/O. It ignores proxy environment variables, never follows a redirect and sends the token as an unredirected bearer header. Each sent request gets exactly one log line `supervisor {METHOD} {template}: {status}`.
- `app/registration.py` creates one `local` access entry (source `system`) for each repository whose last sync is `ok`. When `GET` does not list `sha1(url.lower())[:8]`, it adds the internal URL `http://{hostname}:8080/repo/{owner}/{repo}/{hash}` with `POST`. Supervisor failures become error codes and never end the pass or the sync loop.
- `app/supervisor_state.py` writes `/data/supervisor.json` at every sync start, before any Supervisor call. `registration` is always one of `registered|missing|leftover|error`, recomputed on every write. `message` comes only from fixed templates.
- Verify step (4b) proves registration end to end: both `ok` repositories are `registered`, and the fake store lists them as `Verify fixture` and `Verify fixture branched stable`. The fake saw only authenticated `GET` and exactly 2 `POST` requests, and `d29 ok` was printed. The step (14) needles now hold 7 hashes, including both `local` hashes.

## Task Commits

1. **Task 1: tracer, register local store URLs end to end** - `23b1343` (feat)
2. **Task 2: client and registration unit tests** - `b0e9cef` (test, RED: 1 of 80 failed), `47a90f7` (fix, GREEN: fake keeps an add after a client timeout)

**Plan metadata:** see the docs commit that adds this SUMMARY.

## Verification (commands and results)

| Command | Result |
|---------|--------|
| `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh` (4 runs; final run after the last commit) | exit 0, 97 `✓`, 0 `✗`; prints `✓ tracer: the fake Supervisor cloned both registered local store URLs`, `✓ supervisor.json Phase 3 interface (D-29): d29 ok` and the final `✓ marketplace-repo-proxy Phase 1 verified (criteria 1-5)` |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 302 passed |
| same, only `test_supervisor.py test_registration.py test_manifest.py` | 80 passed (at least 30 required) |
| same, `test_supervisor.py -k "import or ast"` | 1 passed |
| `make validate-addons validate-versions && python3 internal/validate-addon-config.py` | exit 0, no `ERROR` |
| `shellcheck internal/verify-marketplace-repo-proxy.sh` (also `-S info`) | clean |
| `pre-commit run --files` over the Task 2 files | all hooks passed (gitleaks included) |
| manifest check (`hassio_api`, `hassio_role`, forbidden keys) | exit 0 |
| `grep -l SUPERVISOR_TOKEN marketplace-repo-proxy/app/*.py` | only `app/supervisor.py` |
| `git diff --quiet HEAD -- Dockerfile rootfs build.yaml README.md`, `version: "0.1.0-1"` | unchanged, count 1 |
| privacy grep over every staged diff | only `127.0.0.1` / `0.0.0.0` |

## Files Created/Modified

- `marketplace-repo-proxy/app/supervisor.py` - the allow-listed Supervisor client, `read_token`, `store_slug`, `mask_text`
- `marketplace-repo-proxy/app/supervisor_state.py` - `/data/supervisor.json` writer, `registration_value`, `registration_message`, `safe_message`
- `marketplace-repo-proxy/app/registration.py` - `Registrar` (`local` user, registration pass)
- `marketplace-repo-proxy/app/sync.py` - `registrar=` keyword, guarded `after_cycle` hook, token and client wiring in `main`
- `marketplace-repo-proxy/app/paths.py` - `supervisor_state_file`, `supervisor_requests_dir`
- `marketplace-repo-proxy/config.yaml` - `hassio_api`, `hassio_role`
- `marketplace-repo-proxy/tests/fake_supervisor.py` - stdlib fake Supervisor (in-process and container)
- `marketplace-repo-proxy/tests/test_supervisor.py`, `test_registration.py`, `test_manifest.py` - 80 tests
- `internal/verify-marketplace-repo-proxy.sh` - fake Supervisor container, `HASSIO_TOKEN` sentinel, step (4b), 7 hash needles

## Decisions Made

- `SyncService` skips the registration pass while it is stopping, so a 180 s `POST` timeout cannot delay a shutdown.
- `sync.main` wraps the client and `Registrar` construction. On a failure it logs `store registration disabled: {type}` and keeps syncing and serving.
- `registration_message` pluralizes the leftover text: `1 old store repository left (...)` and `{n} old store repositories left (...)`. The plan wrote the template as `repository(ies)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The fake Supervisor dropped an add when the client timed out**
- **Found during:** Task 2 (RED run)
- **Issue:** After the client timed out, the fake's reply raised `BrokenPipeError`. The request was never recorded, which does not match the Supervisor's `asyncio.shield` behaviour.
- **Fix:** `_send` now catches `BrokenPipeError`/`ConnectionResetError`, so the add stays done and is recorded. In-process servers also poll every 50 ms, which cuts test teardown from 0.5 s.
- **Files modified:** `marketplace-repo-proxy/tests/fake_supervisor.py`
- **Verification:** `test_post_timeout_is_an_error_and_the_next_pass_starts_with_get` passes; the verify script is green after the change.
- **Committed in:** `47a90f7`

**2. [Rule 2 - Missing critical] Shutdown and construction guards in the sync loop**
- **Found during:** Task 1
- **Issue:** A registration pass after a stop request could block shutdown for up to 180 s. An exception while constructing the `Registrar` would end the sync process.
- **Fix:** the pass now requires `not self.stop.is_set()`, and construction is guarded with one error line.
- **Files modified:** `marketplace-repo-proxy/app/sync.py`
- **Committed in:** `23b1343`

**3. [Rule 2 - Security] Seeded `masked_url` with a 32-hex run is dropped**
- **Found during:** Task 1
- **Issue:** The writer carried `masked_url` from the previous file with a type check only, so a foreign file could carry a full hash forward.
- **Fix:** `_carry` drops a `masked_url` that contains a 32-hex run.
- **Files modified:** `marketplace-repo-proxy/app/supervisor_state.py`
- **Committed in:** `23b1343`

**4. [Note - contract detail] On-disk key order**
- `app/jsonio.atomic_write_json` writes with `sort_keys=True`, so the keys of each `repositories[]` object are alphabetical in the file. The in-memory and `snapshot()` order is `repository`, `registration`, `message`, then the additions. `jsonio.py` is outside this plan's file list and JSON key order has no meaning, so it was left unchanged. Plan 06 docs should not promise a key order in the file.

**5. [Rule 3 - Blocking] Pre-commit shellcheck rejected SC2015 (info level)**
- The verify script's `A && B || fail` became an explicit `if`, and the verify script was re-run green before the commit. The step (4b) `local` entry check also asserts `source: system` (one entry per repository), which its `✓` line already claimed. A `wait_reg` helper was added next to `reg_of`.

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 2), 1 Rule 3 lint fix, 1 contract note.
**Impact on plan:** correctness and robustness only. No scope creep: no Dockerfile, rootfs, version or docs change.

## TDD Gate Compliance

Task 2 is `tdd="true"`, but the tracer (Task 1) had already implemented the client and the registrar the tests cover. The RED commit `b0e9cef` therefore failed on only 1 of 80 tests, the POST-timeout case, which exposed the fake's `BrokenPipe` bug. The GREEN commit `47a90f7` fixed it. No refactor commit was needed.

## Known Stubs

- `supervisor.json` `reload`, `leftovers[]` and `requests[]` exist with empty defaults. This is intentional: Plan 02 fills `reload`, Plans 03-04 fill `leftovers`/`requests`. They do not block this plan's goal.
- `Paths.supervisor_requests_dir` is defined but not yet used (first used by Plan 03).

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 02 (store reload) can add to `SupervisorClient.reload_store`, the `reload` section and `Registrar.after_cycle`.
- Plans 03-04 extend `SupervisorStateWriter` through `_write` and reuse `assert_d29_shape`.
- The verify script runs the fake Supervisor with `--in-use-file /tmp/fake/in-use` for the refusal checks in later plans.

## Self-Check: PASSED

- All 7 created files exist on disk.
- Commits `23b1343`, `b0e9cef` and `47a90f7` are ancestors of HEAD.
- The measured commit count from the ledger is 3.
