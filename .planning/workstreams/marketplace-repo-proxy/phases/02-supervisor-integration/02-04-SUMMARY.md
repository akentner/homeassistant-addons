---
phase: 02-supervisor-integration
plan: 04
subsystem: api
tags: [supervisor, rotation, leftovers, request-queue, cli]
status: complete

requires:
  - phase: 02-supervisor-integration
    provides: "02-01: SupervisorClient, Registrar, SupervisorStateWriter (D-28/D-29); 02-02: wait-loop wake-up; 02-03: retire_and_replace/undo_retire, add_leftover(revoked=), request queue, mrp local remove/status"
provides:
  - "app.registration: REQUEST_ACTIONS = (remove, rotate); Registrar._rotate (add first, rollback via undo_retire, revoke of local.{old slug} right after the add, DELETE of the old slug, leftover in_use/error with revoked true)"
  - "app.registration: RETIRED_RE; register_pass revokes retired local.* entries (leftover interrupted while listed) and reports recorded slugs that are no longer current (leftover orphaned); hostname-change warning in Registrar.__init__"
  - "CLI: mrp local rotate {owner/repo} [--yes] with the D-11 warning; error confirmation_required without --yes; outputs rotated/refused/queued/error"
affects: [02-05, 02-06, 02-07, phase-3-gui]

actuals:
  tokens: 10700
  tasks: 2
  commits: 4
plan_head_before: 16f606d0ac4e8b0de913c0f86187521c0486e983
plan_head_after: b802109abf6920171dcc6dc2602b86fd1c0b96f9

tech-stack:
  added: []
  patterns:
    - "Add-first rotation: retire + new entry in one locked write, POST, then revoke, then DELETE; rollback is one locked write"
    - "Report-only leftover detection inside the existing GET of the registration pass (no DELETE, no retry loop)"
    - "Confirmation lives in the CLI only (--yes); the request file carries no confirmation key"

key-files:
  created: []
  modified:
    - marketplace-repo-proxy/app/registration.py
    - marketplace-repo-proxy/app/cli.py
    - marketplace-repo-proxy/tests/test_registration.py
    - marketplace-repo-proxy/tests/test_cli.py

key-decisions:
  - "Rotation old slug = recorded store_slug when valid, else store_slug of the current local URL; retired label local.{old slug}; the masked old URL is computed before the revoke"
  - "Any exception from add_repository (not only a failed CallResult) rolls the rotation back with undo_retire before it propagates; SupervisorRefused counts as a failed add"
  - "The leftover check of a pass (orphaned) runs in its own try block after the registration of the repository, so an internal error in the registration does not lose the recorded slug"
  - "An interrupted remnant's slug is taken from its label (the slug the rotation would DELETE), its masked URL from its hash"
  - "supervisor_state.py needed no change: add_leftover already accepts user=None and the writer already keeps previous_hostname and writes the current hostname"

patterns-established:
  - "tests/test_registration.py: _rotate_setup, CheckingClient (check right before the DELETE), _retired_entries, _link_names, _interrupt_rotation, _hand_drop_local"
  - "tests/test_cli.py: ROTATE_WARNING, seed_rotate_result"

requirements-completed: [MRP-10]

coverage:
  - id: D1
    description: "mrp local rotate --yes: POST new URL before DELETE old slug; old link gone before the DELETE; refusal -> revoked in_use leftover, registration leftover, never retried; failed add rolls back; another DELETE error -> error leftover; rejections without Supervisor writes"
    requirement: MRP-10
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_registration.py + test_cli.py -k rotat (23 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-11 warning on every mrp local rotate; without --yes error confirmation_required, exit 1, no request file; --revoke-old is a usage error"
    requirement: MRP-10
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_cli.py -k local_rotate"
        status: pass
    human_judgment: false
  - id: D3
    description: "Leftovers after a crash (interrupted, revoked by the pass), a hand edit or a hostname change (orphaned); one warning each; no DELETE; mrp local remove retries an orphaned leftover"
    requirement: MRP-10
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_registration.py -k 'interrupted or orphaned or hostname' (6 tests)"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-11-19
---

# Phase 2 Plan 04: Rotation of the `local` user and the leftover lifecycle Summary

**`mrp local rotate --yes` registers the new `local` URL first, revokes the old URL right after the add and then tries
to remove the old store repository; refusals, crashes, hand edits and hostname changes all end up as reported leftovers
that only an explicit `mrp local remove` ever deletes.**

## Performance

- **Duration:** about 5 min
- **Started:** 2026-11-18T23:34:55Z
- **Completed:** 2026-11-18T23:39:33Z (UTC)
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `rotate` request in the sync process. `retire_and_replace` runs as one locked write, then `POST` adds the new URL.
  Only after a 200 or 409 does the process revoke `local.{old slug}` (`system=True`), record the new slug as
  `registered` and log `store: {repo} rotated: new {slug} registered; old URL revoked`. Then it sends `DELETE` for the
  old slug:
    - 200 or 404 → `done`
    - `in_use` → leftover `in_use` with `revoked: true`, registration `leftover`, result `refused`
    - any other answer → leftover `error` with `revoked: true`, result `failed`/`remove_failed`
- Rollback: if the add fails, `undo_retire` restores the old hash under `local` in one locked write and logs
  `store: rotation of {repo} failed; old registration kept`. The result is `failed`/`add_failed` and the registration
  facts are not touched.
- `mrp local rotate {owner/repo} [--yes]`:
    - Always prints the D-11 warning on stderr first.
    - Without `--yes`: `error: confirmation_required` plus `rerun with --yes to rotate`, exit 1, no request file.
    - With `--yes`: queues the request through the shared `_queue_request` helper, which `mrp local remove` now also
      uses.
    - Prints `rotated: …` (exit 0), `refused: in_use …` naming both slugs (exit 1), `queued: {id}` (exit 0) or
      `error: {code}`.
    - The EPILOG documents in-place `local` rotation.
- Registration pass:
    - Revokes every retired `local.{slug}` entry at once and records leftover `interrupted` (`revoked: true`) when the
      slug is still listed.
    - Records a slug as leftover `orphaned` (`user: null`) when it was recorded before the pass, is still listed, is no
      longer current and no leftover or retired entry covers it.
    - Logs each leftover once at warning level and never sends `DELETE` for them.
- `Registrar.__init__` logs `store: hostname changed since the last run; earlier store URLs are reported as leftovers`
  once when the hostname recorded in supervisor.json differs from the current one.

## Task Commits

1. **Task 1: rotation add-first, revoke, remove** — RED `e2d2c82` (test), GREEN `8e8fd18` (feat)
2. **Task 2: interrupted/orphaned/hostname leftovers** — RED `8e7f15a` (test), GREEN `b802109` (feat)

## Files Created/Modified

- `marketplace-repo-proxy/app/registration.py`: rotate branch, `RETIRED_RE`, `_retired_entries`, `_revoke_interrupted`,
  `_report_orphaned`, hostname warning
- `marketplace-repo-proxy/app/cli.py`: `local rotate` subcommand with `--yes`, `_queue_request`/`_print_queued`/
  `_result_error` shared with `local remove`, `_rotation_slugs`, EPILOG
- `marketplace-repo-proxy/tests/test_registration.py`: 9 rotation tests and 6 leftover-detection tests
- `marketplace-repo-proxy/tests/test_cli.py`: 13 `local rotate` and help tests

## Verification

- `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests/test_registration.py marketplace-repo-proxy/tests/test_cli.py -q`
  → 173 passed. `-k rotat` selects 23 tests and all pass (the acceptance criterion needs at least 11).
- `... -m pytest marketplace-repo-proxy/tests/test_registration.py -q -k "interrupted or orphaned or hostname"` → 6
  passed (needs at least 5).
- Full suite `... -m pytest marketplace-repo-proxy/tests -q` → 436 passed.
- `pre-commit run --files` on the five plan files → all hooks pass or skip.
- Acceptance greps:
    - `"rotate"` in registration.py: 2
    - `retire_and_replace(` in registration.py: 1
    - `confirmation_required` in cli.py: 1
    - `"interrupted"` in registration.py: 2
    - `"orphaned"` in registration.py: 2
- `app/cli.py` still imports neither `app.supervisor` nor `app.registration` (`test_static_import_boundaries` passes).
- Not required by the plan, but the manager asked for it:
  `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy.sh` exited 0 (97 checks, none failed).
  The script currently covers the Phase 1 criteria; Plan 05 adds the rotation container proof.

## Decisions Made

The `key-decisions` list in the frontmatter has the full set. The most important ones:

- The rotation takes the old slug from the recorded `store_slug` when it is valid, as the plan says.
- Any exception from the add rolls the rotation back before it propagates, so the old URL keeps serving.
- The orphaned check runs separately from the per-repository registration error handler.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Robustness] Rollback also on an exception from `add_repository`**
- **Found during:** Task 1
- **Issue:** The plan rolls back when the add result is neither `ok` nor `duplicate`. An unexpected exception (not
  `SupervisorRefused`) would leave the new `local` entry and the retired entry in place until the next pass.
- **Fix:** The code calls `undo_retire`, logs the warning and then re-raises. `_run_request` records the result as
  `failed`/`internal_error`. `SupervisorRefused` is mapped to a failed `CallResult`, so it takes the normal
  `add_failed` path.
- **Commit:** `8e8fd18`

**2. [Rule 2 - Robustness] The orphaned check has its own error guard**
- **Found during:** Task 2
- **Issue:** If the orphaned check ran inside the per-repository `try`, an internal error in `_register_one` would skip
  it. That handler still writes the new slug, so the recorded old slug would be lost for every later pass.
- **Fix:** `_report_orphaned` runs after the registration `try`/`except` in a separate guard that only logs.
- **Commit:** `b802109`

**3. [Rule 2 - Minor] Smaller additions inside the plan's scope**
- A successful `DELETE` in a rotation also calls `drop_leftover(old slug)`. It writes nothing when there is no leftover.
- An info line `store: {repo} retired URL of an interrupted rotation revoked` is logged when a pass revokes a remnant.
  It contains no hash.
- The CLI warning names the normalized `owner/repo` when the argument parses. Otherwise it uses the sanitized argument.
- A result code that does not match the format falls back to `error: rotate_failed`.
- **Commits:** `8e8fd18`, `b802109`

**4. [Plan note] `app/supervisor_state.py` is unchanged**
- The plan lists it under Task 2 (allow `user=None`, keep `previous_hostname`). Both already worked after Plan 03, so
  nothing needed to change.

---

**Total deviations:** 3 auto-fixed (Rule 2) and 1 plan note.
**Impact on plan:** robustness only. There was no scope creep and no Dockerfile, rootfs, version or docs change.

## TDD Gate Compliance

Each task has a RED commit before its GREEN commit:

- Task 1: `e2d2c82` → `8e8fd18`. At RED, 21 rotation tests failed. Two passed:
    - `--revoke-old` exited 2 already, because argparse rejected the unknown `rotate` subcommand.
    - The `example-org/unknown` rejection pins the existing behaviour.
- Task 2: `8e7f15a` → `b802109`. At RED, 5 of the 6 tests failed. The one that passed is
  `test_same_hostname_logs_no_hostname_warning`, which is a negative control.

No refactor commits were needed.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-02-20 to T-02-23 and T-02-45 are mitigated and tested. T-02-46 is accepted as
planned.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 05 (container proof):
    - Can run `mrp local rotate … --yes` against the fake Supervisor's in-use file.
    - Output prefixes: `rotated: new store repository`, `refused: in_use old store repository`.
    - Log lines are fixed: `store: {repo} rotated: …`, `store: {repo} leftover {slug} ({reason})`,
      `store: hostname changed since the last run; …`.
- Plan 06 (DOCS) should document:
    - `mrp local rotate --yes` and the D-11 warning with the reinstall procedure
    - leftover reasons `interrupted` and `orphaned` (`user` may be null)
    - that rotation leftovers are always `revoked: true`

## Self-Check: PASSED

- All 4 modified files exist on disk.
- Commits `e2d2c82`, `8e8fd18`, `8e7f15a` and `b802109` are ancestors of HEAD.
- The commit count measured from the ledger is 4 (`plan_head_before` 16f606d, `plan_head_after` b802109).
