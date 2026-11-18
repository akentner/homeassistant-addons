---
phase: 02-supervisor-integration
plan: 03
subsystem: api
tags: [supervisor, store-removal, request-queue, leftovers, reserved-labels, cli]

requires:
  - phase: 02-supervisor-integration
    provides: "02-01: SupervisorClient.remove_repository/CallResult.in_use, Registrar, SupervisorStateWriter (D-28/D-29 rendering), fake Supervisor with in_use; 02-02: Registrar.work_due/run_due and the `supervisor` wake-up of the sync wait loop"
provides:
  - "app.access: is_reserved; AccessStore.revoke(..., system=False) guard; retire_and_replace / undo_retire (one locked write each, field `retired`)"
  - "app.supervisor_state: LEFTOVER_REASONS, REQUEST_RESULTS, MAX_REQUESTS; add_leftover, drop_leftover, leftovers, drop_repository, unconfigured_repositories, record_request; typed carry-over of leftovers[] and requests[]"
  - "app.registration: REQUEST_ACTIONS, REQUEST_NAME_RE, Registrar.pending_requests, Registrar.handle_request; request queue in work_due/run_due; leftover and unconfigured cleanup in register_pass (no DELETE)"
  - "CLI: mrp local status [owner/repo], mrp local remove {owner/repo}, cli.LOCAL_WAIT_SECONDS; error code user_reserved for local / local.* in users add/revoke"
affects: [02-04, 02-05, 02-06, 02-07, phase-3-gui]

actuals:
  tokens: 20978
  tasks: 2
  commits: 4
plan_head_before: fcb1eaabe7f9c7c40489533cbbccef49f5b1c01e
plan_head_after: 25d1acef8050fd59c9982f3acdc970e62ae785a6

tech-stack:
  added: []
  patterns:
    - "Operator request queue: CLI writes {16 hex}.json (0600 in a 0700 dir), the sync wait loop unlinks, validates as untrusted input and executes once, result in supervisor.json requests[]"
    - "DELETE targets come only from slugs recorded in supervisor.json (current registration or leftover), never from the store list"
    - "Gone-from-the-store resolution inside the existing GET of the registration pass instead of a retry loop"

key-files:
  created: []
  modified:
    - marketplace-repo-proxy/app/access.py
    - marketplace-repo-proxy/app/cli.py
    - marketplace-repo-proxy/app/registration.py
    - marketplace-repo-proxy/app/supervisor_state.py
    - marketplace-repo-proxy/tests/test_access.py
    - marketplace-repo-proxy/tests/test_cli.py
    - marketplace-repo-proxy/tests/test_registration.py

key-decisions:
  - "add_leftover masks `message` with app.gitops.sanitize, not mask_text: supervisor_state must not import app.supervisor (Plan 01 import boundary, same as 02-02); the Registrar applies mask_text before the call"
  - "After a successful removal the configured repository keeps its last store_slug and masked_url with in_store false (registration missing), so a repeated mrp local remove right after it answers done without a DELETE; the next pass clears both"
  - "An unconfigured repository whose current store repository was removed but which still has a refused leftover stays in supervisor.json (configured false, registration leftover) until its last leftover is gone"
  - "retire_and_replace/undo_retire accept only reserved labels for both the current and the retired user (invalid_user otherwise), so a retired entry can never be revoked through the CLI"
  - "mrp local status prints tab-separated repository and leftover lines and masks any 32-hex run it finds in the file (defence in depth; the file holds masked values only)"
  - "Request files that cannot be unlinked are remembered in memory and never executed or counted by work_due, so they cannot keep the wait loop busy"

patterns-established:
  - "tests/test_registration.py: _register, _refused, _request, _stub_registered, _deletes, _outcome helpers for request-queue tests (Plan 04 rotation can reuse them); StubClient.remove"
  - "tests/test_cli.py: seed_state / seed_result and the no_wait fixture (LOCAL_WAIT_SECONDS 0, fixed request id)"

requirements-completed: []

coverage:
  - id: D1
    description: "Reserved labels: users add/revoke refuse local and local.*; only system revoke passes; retire/undo primitives for the rotation"
    requirement: MRP-10
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_access.py + test_cli.py -k 'reserved or retire or local_status' (43 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "mrp local remove through the sync process: DELETE of the recorded slug only; refusal becomes an in_use leftover, never forced or retried by the loop; register_local_enabled; unconfigured removal; cleanup of gone leftovers and unconfigured repositories without DELETE"
    requirement: MRP-10
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_registration.py + test_cli.py -k 'remove or leftover or request' (56 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "CLI never reaches the Supervisor: no import of app.supervisor or app.registration in cli.py"
    requirement: MRP-10
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_supervisor.py::test_static_import_boundaries"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-11-18
status: complete
---

# Phase 2 Plan 03: Local store repository removal Summary

**`mrp local remove` queues a request file that the sync process executes once. The process sends `DELETE` only for store slugs it recorded from its own `local` URLs. A Supervisor refusal becomes an `in_use` leftover in `/data/supervisor.json`, which the loop never forces and never retries. The `local` and `local.*` labels are now reserved for the add-on itself.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-11-18T23:19:12Z
- **Completed:** 2026-11-18T23:29:54Z
- **Tasks:** 2
- **Files modified:** 7 (0 created, 7 modified)

## Accomplishments

- `is_reserved` matches `local` and `local.*` in any case. `add` refuses these labels for every source except `system`. `revoke` refuses them unless the caller passes `system=True`, and it checks this before it takes the lock or writes anything. As a result, `mrp users revoke {repo} local` answers `error: user_reserved` and can no longer orphan a registered store repository (RESEARCH Pitfall 6).
- `retire_and_replace` and `undo_retire` each do one locked read-modify-write. The first renames the system entry `local` to `local.{x}` (the hash stays, the `retired` field is set) and adds a new `local` entry with a unique hash. The second reverses that and unlinks the new hash. Unknown keys and fields stay as they are. Plan 04 builds the rotation on these two primitives.
- `mrp local status [owner/repo]` reads `/data/supervisor.json` only. For each repository it prints a tab-separated line with the registration, store slug and masked URL, plus `(unconfigured)` where it applies. It then prints a `reload:` line and one `leftover` line per leftover. It never prints a full hash and never logs.
- `mrp local remove {owner/repo}` validates the argument and writes `{16 hex}.json` with exactly the keys `id`, `action`, `repository` and `created` (file 0600, directory 0700). It then waits up to `LOCAL_WAIT_SECONDS` (30) for its id in `requests[]` and prints `removed: ...` (exit 0), `refused: in_use ...` (exit 1), `error: {code}` (exit 1) or `queued: {id}` (exit 0). The command accepts no further flag; `--revoke-old` is an argparse error (D-11).
- `Registrar.work_due` is now also true while a request file exists. `run_due` first deletes invalid entries with the warning `ignored an invalid supervisor request file`. It then runs every pending request once, oldest first by `(mtime, name)`: the file is unlinked before it is read, the content is validated (exact keys, all values strings, id equal to the file name, size limit, no symlink), `handle_request` runs, and the result is recorded. A due reload follows after that. A file created during `run_due` waits for the next call. Dotfiles (temporary files of the atomic writer) and directories are ignored.
- How `remove` works:
    - **Targets:** the targets are every leftover of the repository, plus the recorded current slug (user `local`) when `register_local` is false or the repository is unconfigured. Without any target the request is rejected with `register_local_enabled` or `not_registered`.
    - **Store list:** one `GET` follows. If it fails, the result is `failed`/`store_list_unavailable` and nothing changes.
    - **Slug gone, 200 or 404:** the label is revoked with `system=True`, the leftover is dropped, and the repository becomes `missing` (configured) or leaves the file (unconfigured).
    - **`in_use`:** a leftover `{reason: in_use, revoked: <kept>}` is recorded with a masked message, and a warning `store: {repo} leftover {slug} (in_use)` is logged. No access entry changes.
    - **Any other answer:** the state stays unchanged and the code is `remove_failed`.
- `register_pass` now also sends its `GET` when leftovers or unconfigured recorded repositories exist. A leftover whose slug the store no longer lists is dropped and its label revoked: always for `local.*`, and for `local` only when the repository is not to be registered. This logs `store: leftover {slug} of {repo} is gone; dropped`. An unconfigured repository whose slug is gone and that has no leftovers left loses its `local` entry and leaves the state, which logs `store: {repo} is no longer configured and its store repository is gone; local entry revoked`. The pass never sends `DELETE`.
- `supervisor.json`: carried `leftovers[]` are type-checked field by field. Items without a valid 8-hex slug are dropped, an unknown reason becomes `error`, and a URL or user that contains a 32-hex run is cleared. `requests[]` keeps the last 20 entries.

## Task Commits

1. **Task 1: reserved labels, system revoke, retire primitives, `mrp local status`**: `b65c278` (test, RED: import error in test_access, 11 CLI failures), `08ce7c4` (feat, GREEN)
2. **Task 2: `mrp local remove` through the sync process, leftovers, request queue**: `7d515a9` (test, RED: 30 registration failures, 14 CLI failures/errors), `25d1ace` (feat, GREEN)

**Plan metadata:** see the docs commit that adds this SUMMARY.

## Verification (commands and results)

| Command | Result |
|---------|--------|
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests/test_access.py marketplace-repo-proxy/tests/test_cli.py -q` | green (Task 1 gate) |
| same, `-k "reserved or retire or local_status"` | 43 passed (required at least 15; baseline 5) |
| `grep -c 'def is_reserved\|def retire_and_replace\|def undo_retire'` (each, `app/access.py`) | 1 / 1 / 1 |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` (full suite) | 408 passed |
| `... pytest marketplace-repo-proxy/tests/test_registration.py marketplace-repo-proxy/tests/test_cli.py -q -k "remove or leftover or request"` | 56 passed (required at least 14) |
| `grep -c 'remove_repository(' app/registration.py` / `app/cli.py` | 1 / 0 |
| `... pytest marketplace-repo-proxy/tests/test_supervisor.py -q -k "import or ast"` | 1 passed (`test_static_import_boundaries`) |
| `pre-commit run --files` over the 7 plan files | exit 0, all hooks passed |
| `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh` | exit 0, 97 `✓`, 0 `✗` (Phase 1 and Phase 2 waves 1-2 checks unchanged; no Docker change in this plan) |
| privacy grep (IPs other than loopback/0.0.0.0, e-mails, token shapes) over every staged diff | nothing found |
| `git diff --quiet` over Dockerfile, rootfs, config.yaml, build.yaml, README.md | unchanged (no version or Dockerfile change, D-21) |

## Files Created/Modified

- `marketplace-repo-proxy/app/access.py`: `is_reserved`, `_unique_hash`, reserved guard in `add`/`revoke(system=)`, `retire_and_replace`, `undo_retire`, `_check_retire_labels`
- `marketplace-repo-proxy/app/cli.py`: `local status`, `local remove`, `LOCAL_WAIT_SECONDS`, `_request_id`, EPILOG (reserved labels, `mrp local`)
- `marketplace-repo-proxy/app/registration.py`: request queue (`_request_files`, `pending_requests`, `_read_request`, `_run_request`, `handle_request`, `_remove`, `_remove_one`), `_resolve_gone` in `register_pass`, `work_due`/`run_due` extended
- `marketplace-repo-proxy/app/supervisor_state.py`: `LEFTOVER_REASONS`, `REQUEST_RESULTS`, `MAX_REQUESTS`, `_leftover` carry-over, `leftovers`, `add_leftover`, `drop_leftover`, `unconfigured_repositories`, `drop_repository`, `record_request`
- `marketplace-repo-proxy/tests/test_access.py`: 26 tests (reserved labels, system revoke, retire/undo)
- `marketplace-repo-proxy/tests/test_cli.py`: 26 tests (`user_reserved`, help text, `local status`, `local remove`)
- `marketplace-repo-proxy/tests/test_registration.py`: 34 tests (removal, refusal, leftovers, request files, state writer); `StubClient.remove`

## Decisions Made

- The leftover message is masked twice. The Registrar applies `mask_text`, and `add_leftover` applies `app.gitops.sanitize` again, following the 02-02 precedent. The tests check that neither the state file nor the log contains a 32-hex run after a refusal whose text carries the full URL.
- A removal keeps the last `store_slug`/`masked_url` with `in_store: false`. A repeat right after it answers `done` without a `DELETE`. After a pass, a repeat answers `rejected`/`not_registered`.
- Leftover targets keep their `revoked` value on a new refusal, so a rotation leftover (Plan 04, `revoked: true`) is never marked as served again.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `add_leftover` cannot call `mask_text`**
- **Found during:** Task 2
- **Issue:** The plan says `add_leftover` "runs `message` through `mask_text`". `app/supervisor_state.py` must not import `app.supervisor`, because `test_static_import_boundaries` allows only `registration` and `sync` to import it.
- **Fix:** The Registrar masks with `mask_text` before it calls `add_leftover`, and the writer masks again with `app.gitops.sanitize`. This is the same solution as 02-02 Deviation 2.
- **Files modified:** `marketplace-repo-proxy/app/supervisor_state.py`, `marketplace-repo-proxy/app/registration.py`
- **Committed in:** `25d1ace`

**2. [Rule 2 - Robustness] Typed carry-over of `leftovers[]`**
- **Found during:** Task 2
- **Issue:** Plan 01 carried the previous `leftovers` list verbatim. A leftover is now a `DELETE` target, so an untyped item could lead to a call with a bad slug, and a foreign file could seed an unmasked URL.
- **Fix:** `_leftover` keeps only typed fields and requires an 8-hex slug. It maps an unknown reason to `error` and clears values that contain a 32-hex run. `requests[]` is cut to the last 20 on load.
- **Committed in:** `25d1ace`

**3. [Rule 2 - Robustness] A request file that cannot be unlinked must not spin the wait loop or run twice**
- **Found during:** Task 2
- **Issue:** `work_due` would stay true for a file that `run_due` cannot delete. `wait_reason` would then return `supervisor` on every pass without sleeping, and the request would run again each time.
- **Fix:** Such names are kept in an in-memory set. They are never executed and never counted by `work_due`.
- **Verification:** `test_request_file_that_cannot_be_unlinked_never_runs_or_keeps_the_loop_busy`
- **Committed in:** `25d1ace`

**4. [Rule 2 - Hardening] Retire primitives accept reserved labels only**
- **Found during:** Task 1
- **Issue:** The plan validates the retired label only against `USER_RE`. A non-reserved retired label (for example `alice`) could later be revoked through the CLI.
- **Fix:** Both labels must pass `is_reserved` and differ from each other; otherwise the code is `invalid_user`.
- **Committed in:** `08ce7c4`

**5. [Rule 2 - Test coverage] Three edge tests added after GREEN**
- The plan names `remove_failed` (another DELETE error) and `not_registered`, but the RED set did not pin them. The tests `test_remove_request_with_another_delete_error_fails_and_changes_nothing` and `test_remove_request_without_a_recorded_registration_is_not_registered`, plus the unlink test from deviation 3, were added in `25d1ace`. They passed on their first run against the GREEN code.

---

**Total deviations:** 5 auto-fixed (1 Rule 3, 4 Rule 2).
**Impact on plan:** correctness and robustness only. There was no scope creep and no Dockerfile, rootfs, version or docs change.

## TDD Gate Compliance

Each task has a RED commit before its GREEN commit: Task 1 `b65c278` (collection error from the missing `is_reserved`, 11 CLI failures) → `08ce7c4`; Task 2 `7d515a9` (30 registration failures, 1 CLI failure and 13 errors from the missing `LOCAL_WAIT_SECONDS`) → `25d1ace`. No refactor commits were needed. One D-27 test (`test_unconfigured_repository_is_never_removed_by_a_pass_and_shows_leftover`) already passed at RED: it pins behaviour from Plan 01 (no removal by a pass) that this plan must keep.

## Known Stubs

None. `REQUEST_ACTIONS` holds only `remove`, as the plan intends; Plan 04 adds `rotate`.

## Threat Flags

None beyond the plan's threat model (T-02-14 to T-02-19 are all mitigated and tested). The request directory is the new trust boundary the plan names.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Plan 04 (rotation) can use `retire_and_replace`/`undo_retire`, `add_leftover(..., revoked=True)`, `REQUEST_ACTIONS` and `handle_request`. The removal path already keeps `revoked` and retries rotation leftovers through `mrp local remove`.
- Plan 05 (container proof) can drive `mrp local remove` against the fake Supervisor's `in-use` file. The log lines and the `refused: in_use` / `removed:` output prefixes are fixed.
- Plan 06 (DOCS) should document `leftovers[]`, `requests[]`, `mrp local status|remove` and the reserved labels.

## Self-Check: PASSED

- All 7 modified files exist on disk.
- Commits `b65c278`, `08ce7c4`, `7d515a9` and `25d1ace` are ancestors of HEAD.
- The measured commit count from the ledger is 4 (`plan_head_before` fcb1eaa, `plan_head_after` 25d1ace).
- MRP-10 is not marked complete: this plan delivers the removal half; Plan 04 delivers the rotation half.
