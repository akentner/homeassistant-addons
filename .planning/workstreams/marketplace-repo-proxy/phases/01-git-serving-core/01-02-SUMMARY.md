---
phase: 01-git-serving-core
plan: 02
subsystem: infra
tags: [sync, status-json, git, error-classification, trigger-file, python]

requires:
  - "01-01: Paths, Options, jsonio, logsetup, gitops (auth_env, local_env, run_git, ensure_and_fetch), sync --once"
provides:
  - "app/status.py: SCHEMA, STATUS_CODES, REASONS, StatusWriter (begin_cycle, record, end_cycle, snapshot), read_status"
  - "/data/status.json contract (D-14, D-20, D-26) with pending/ok/auth_failed/not_found/no_repository_yaml/fetch_failed"
  - "gitops: classify, sanitize, check_branch_name, HeadInfo, inspect_head, ref_snapshot, prune_foreign_refs, run_maintenance, cleanup_stale_tmp, ls_remote_head"
  - "sync: SyncService (stop, wait_reason, run_cycle_once, run_forever), run_cycle(paths, options, upstream, log, writer, stop=None), run_disabled, main(--once)"
  - "Trigger semantics for /run/marketplace-repo-proxy/sync.request: 1 s poll, unlink before the cycle, coalescing, interval restart"
  - "tests/upstream.py: git_env, git, make_upstream, commit, file_upstream (local bare upstream, no network)"
affects: [01-03, 01-05, 03-gui]

actuals:
  tokens: 17900
  tasks: 3
  commits: 6
plan_head_before: 061f78dd06aba40f9c512818b190748a74586a71
plan_head_after: 481e84722e7e7a351a2cae0a26b0418014f3deee

tech-stack:
  added: []
  patterns:
    - "Status codes from LC_ALL=C git stderr via regex table; fixed messages for auth_failed and not_found"
    - "Single-writer status.json via StatusWriter (atomic replace, 0600), seeded from the previous file"
    - "Injectable clock/sleep/wall in SyncService for deterministic loop tests"
    - "Fail closed on an invalid test upstream override: record fetch_failed, never sync, idle until SIGTERM"

key-files:
  created:
    - marketplace-repo-proxy/app/status.py
    - marketplace-repo-proxy/tests/upstream.py
    - marketplace-repo-proxy/tests/test_gitops.py
    - marketplace-repo-proxy/tests/test_status.py
    - marketplace-repo-proxy/tests/test_sync.py
  modified:
    - marketplace-repo-proxy/app/gitops.py
    - marketplace-repo-proxy/app/sync.py

key-decisions:
  - "The trigger file is unlinked before every cycle (any reason), not only before request cycles: a pending request is satisfied by any full cycle that starts after it"
  - "An invalid test upstream override writes upstream_override: true (the variable is set) and every repository fetch_failed; with --once main returns 1"
  - "StatusWriter.record passes every message through gitops.sanitize and run_cycle also scrubs the PAT, its header and base64 forms from messages before recording or logging"
  - "check_branch_name rejects a leading '-' and '@{' before calling git (git would read '-x' as an option and expand '@{-1}')"

patterns-established:
  - "RED stubs again: each test(01-02) commit adds signature stubs so RED fails on assertions, not on imports"

requirements-completed: [MRP-02, MRP-05]

coverage:
  - id: D1
    description: "Upstream 401/403 -> auth_failed, 404/missing branch/no default branch -> not_found, network/timeout/other -> fetch_failed, with secret-free one-line messages"
    requirement: MRP-02
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gitops.py (classify table, real git against 127.0.0.1 401/403/404 server and a closed port)"
        status: pass
    human_judgment: false
  - id: D2
    description: "status.json contract: pending seed in options order, mode 0600, carry-over of the last good state, drop of removed repositories, cycle state"
    requirement: MRP-02
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_status.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Sync cycle: ok with HEAD and add-ons, no_repository_yaml, refs_changed after an upstream push and false without one, branch change leaves only refs/heads/{branch}"
    requirement: MRP-02
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_sync.py (file:// fixtures)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Trigger file starts a cycle within one poll, bursts coalesce, interval restarts after every cycle, stop within one poll, invalid override fails closed"
    requirement: MRP-02
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_sync.py (fake clock and sleep, main tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Sentinel PAT never in status.json or captured sync log output after a cycle against a local 401 server"
    requirement: MRP-05
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_sync.py::test_token_never_reaches_status_or_log"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-11-18
status: complete
---

# Phase 1 Plan 02: Sync service, status.json and "Sync now" trigger Summary

**Upstream failures map to stable codes (`auth_failed`, `not_found`, `no_repository_yaml`, `fetch_failed`) with
secret-free one-line messages. `/data/status.json` reports per repository the branch, HEAD, add-ons and
`refs_changed` and keeps the last good state when an upstream breaks. A `SyncService` loop runs on the interval and
within one second of `/run/marketplace-repo-proxy/sync.request`, coalescing bursts.**

## Performance

- **Duration:** about 10 min
- **Started:** 2026-11-18T13:38:11Z
- **Completed:** 2026-11-18T13:48Z
- **Tasks:** 3 (all TDD)
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments

- `classify` follows the RESEARCH stderr table under `LC_ALL=C`. Real git against a `127.0.0.1` `ThreadingHTTPServer`
  maps 401 and 403 to `auth_failed` and 404 to `not_found`. A closed port gives `fetch_failed`. A missing `file://`
  repository ("does not appear to be a git repository") is also `not_found`.
- `inspect_head` reads HEAD, the root `repository.yaml|yml|json` and the add-on directories from the bare repository
  without a checkout. It applies the Supervisor rule: `**/config.{yaml,yml,json}`, skipping hidden parts and `rootfs`.
- `run_cycle` re-sets the refspec and HEAD on every cycle, prunes every foreign ref after the fetch and computes
  `refs_changed` from the ref and HEAD snapshots. `git maintenance run --auto` runs with `local_env()` only.
- `StatusWriter` owns status.json. It seeds `pending` entries in options order, carries over `last_success`,
  `last_change`, `head` and `addons` for repositories that are still configured (case-insensitive), and drops removed
  ones.
- `SyncService` provides the 1 s trigger poll, unlink before the cycle, coalescing, interval restart, stale temp
  cleanup at start and a stop check between repositories. `main` installs the SIGTERM and SIGINT handlers and fails
  closed on an invalid override.

## Task Commits

1. **Task 1: classification, sanitising, HEAD inspection, ref hygiene (TDD)**
   - RED `d4f105b` (test), GREEN `b94b4f8` (feat)
2. **Task 2: status.json per repository (TDD)**
   - RED `bcd4bdd` (test), GREEN `83183c3` (feat)
3. **Task 3: "Sync now" trigger file and interval loop (TDD)**
   - RED `2390565` (test), GREEN `481e847` (feat)

REFACTOR: none needed in any task.

## TDD Gate Compliance

Each RED run used `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest <files> -q
--junitxml=<phase dir>/red-01-02-tN.xml`. The record went through `gsd-tools check tdd-red-evidence`. The records were
moved out of the repository afterwards.

| Task | RED result | Target | Verdict | Semantic assessment |
| --- | --- | --- | --- | --- |
| 1 | exit 1, 38 tests, 23 failed, 0 errors | `test_inspect_head_reports_repository_yaml_and_addons` | `RED_EVIDENCE_OK` (`target_test_failed`) | fails on `assert () == ('demo', 'other')`: the stub `inspect_head` returns no add-ons. Every failure is an `AssertionError` against a stub; the 15 passes test Plan 01 code (`auth_env`, `resolve_upstream`, `ensure_and_fetch`) |
| 2 | exit 1, 21 tests, 19 failed | `test_failed_attempt_keeps_the_last_good_state` | `RED_EVIDENCE_OK` (`target_test_failed`) | fails on `status.json missing or unreadable`: the stub writer writes nothing. The only failure without an `AssertionError` is `DID NOT RAISE ValueError` (pytest.raises), also against the stub |
| 3 | exit 1, 21 tests, 7 failed | `test_requests_during_a_cycle_coalesce_into_one` | `RED_EVIDENCE_OK` (`target_test_failed`) | fails on `assert [] == ['startup', 'request']`: the stub `run_forever` runs no cycle. The 14 passes are Task 2 tests plus `--once`, valid-override and stop-between-repositories, which Task 2 code already satisfies |

GREEN: the same commands with all tests passing (38 / 21 / 21).

## Verification Results

| Command | Result |
| --- | --- |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 87 passed |
| same suite with `uv run --offline --python 3.12 ...` (target runtime) | 87 passed |
| `pytest marketplace-repo-proxy/tests/test_gitops.py -q` (Task 1 verify, needs at least 20) | 38 passed |
| `pytest marketplace-repo-proxy/tests/test_status.py marketplace-repo-proxy/tests/test_sync.py -q` (Task 2 verify, at least 12) | 21 + 21 passed |
| `pre-commit run --files` on all 7 plan files (gitleaks, end-of-file, whitespace, version and config validators) | all Passed |

Acceptance greps: in `gitops.py`, `def classify` 1, `def inspect_head` 1 and `"maintenance", "run", "--auto"` 1. In
`status.py`, `"fetch_failed"` 1, `"no_repository_yaml"` 2 and `upstream_override` 1. In `sync.py`,
`class SyncService` 1, `missing_ok=True` 1, `.record(` 2, `trigger_file` 2 and `classify(` 2. `test_sync.py` has 21
`^def test_` (Task 2 plus 10 loop and main tests). No image build, no verify script and no Dockerfile change, as the
plan requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RED commits carry interface stubs**

- **Found during:** Tasks 1-3 (RED)
- **Issue:** the new names did not exist yet, and tests importing them would fail at collection (INVALID_RED).
- **Fix:** each `test(01-02)` commit adds signature stubs to `gitops.py`, `status.py` or `sync.py`, so the targets
  fail on assertions. GREEN replaced every stub. This is the same pattern as Plan 01.
- **Commits:** `d4f105b`, `bcd4bdd`, `2390565`

**2. [Rule 2 - Missing critical] `gitops.ls_remote_head` so a failed default-branch probe can be classified**

- **Found during:** Task 2
- **Issue:** `default_branch` returns only `str | None`, which loses the `GitResult` that `classify` needs. The plan
  requires `classify` on a non-zero ls-remote.
- **Fix:** `ls_remote_head(url, env) -> (GitResult, branch | None)`. `default_branch` delegates to it, and its
  signature is unchanged.
- **Files:** `marketplace-repo-proxy/app/gitops.py`. **Commit:** `83183c3`

**3. [Rule 2 - Missing critical] Defense in depth for messages and per-repository isolation**

- **Found during:** Task 2
- **Fix:** `StatusWriter.record` passes every message through `sanitize` and rejects unknown status codes or branch
  sources. `run_cycle` also scrubs the PAT, the full header and the base64 part from messages. An unexpected
  exception in one repository becomes `fetch_failed` (`internal error: <ExceptionType>`) and does not end the cycle
  for the others.
- **Commit:** `83183c3`

**4. [Rule 1 - Bug] `check_branch_name("-x")` would pass `-x` to git as an option**

- **Found during:** Task 1
- **Fix:** an empty name, a leading `-` or `@{` is rejected before `git check-ref-format --branch` runs.
- **Commit:** `b94b4f8`

**5. [Rule 1 - Bug] Test timestamps had one-second resolution**

- **Found during:** Task 2 GREEN (`test_upstream_push_is_reported_once`)
- **Issue:** `utc_timestamp` has second precision, so `last_change` could not differ between two fast cycles.
- **Fix:** an autouse fixture in `test_status.py` and `test_sync.py` patches `status.utc_timestamp` with a ticking
  clock. Production code is unchanged.
- **Commit:** `83183c3`

### Interpretations within plan scope (not deviations)

- The trigger file is unlinked before every cycle, whatever started it. A request that is pending when a cycle starts
  is served by that cycle. Requests that arrive during the cycle still cause exactly one more cycle.
- `run_cycle` takes an optional `stop` event (added in Task 2, used by Task 3). The plan signature
  `run_cycle(paths, options, upstream, log, writer)` still works.
- An invalid override writes `upstream_override: true`, because the variable is set. With `--once`, `main` records
  `fetch_failed` and returns 1. Without `--once` it idles until SIGTERM and returns 0.
- `sanitize` keeps the first `fatal:`/`error:` line, or the first remaining line, and truncates it to 300 characters
  with a trailing `…`.
- A repository whose configured branch is missing upstream reports `not_found` on fetch. HEAD in the bare repository
  then already points to the new branch. The previous refs stay until a fetch succeeds.

**Total deviations:** 5 auto-fixed (1 blocking, 2 missing critical, 2 bugs). **Impact:** no contract change. All names
in the plan's artifacts list exist with the planned signatures; `ls_remote_head` and `run_disabled` are additions.

## Issues Encountered

- None blocking. A previous executor left `tests/upstream.py` untracked. It was kept unchanged and committed in the
  Task 1 RED commit.

## Known Stubs

None. All RED stubs were replaced in the GREEN commits.

## Threat Flags

None. No new endpoint, auth path or schema at a trust boundary beyond the plan's threat model. T-01-11 to T-01-16 are
mitigated as planned and covered by tests (sanitize, sentinel scan, local-only maintenance, timeout mapping,
`prune_foreign_refs`, fail-closed override, atomic 0600 writes).

## Next Phase Readiness

- 01-03 (`mrp sync`) can create the trigger file. The contract is unchanged: any content, any root process.
- 01-05 (verify script) can check `status.json` codes, `refs_changed` after an upstream push and the override
  WARNING end to end.
- Phase 3 GUI: read `status.json` with `app.status.read_status`. Field names are the contract.
- REQUIREMENTS.md checkboxes for MRP-02 and MRP-05 stay open. `requirements.ready-ids` blocks both because sibling
  plans also declare them (MRP-02: 01-06; MRP-05: 01-03, 01-04, 01-05).

## Self-Check: PASSED

- All 7 key files exist on disk. Commits `d4f105b`, `b94b4f8`, `bcd4bdd`, `83183c3`, `2390565` and `481e847` are
  ancestors of HEAD.
