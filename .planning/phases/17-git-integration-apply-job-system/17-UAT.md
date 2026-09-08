---
status: testing
phase: 17-git-integration-apply-job-system
source: [17-VERIFICATION.md]
started: 2026-09-08T17:30:00Z
updated: 2026-09-08T17:30:00Z
---

## Current Test

number: 1
name: Output-Pipe-Lifecycle und Timeout-Pfad gegen ein echtes tofu (WR-01)
expected: |
  No output lines are lost at the end of the run; the run reaches status `failed` with `error_code: apply_timeout`; no
  `jobq.output_join_timeout` WARN is emitted on the normal path; no orphaned tofu process survives.
awaiting: user response

## Tests

### 1. Output-Pipe-Lifecycle und Timeout-Pfad gegen ein echtes tofu (WR-01)

Run a real `tofu plan` (or any long-running, chatty command) through `POST /v1/plan` on the built image and compare the
tail of `GET /v1/runs/{id}?page=<last>` against `cat /data/runs/{id}/output.log | wc -l`. Then trigger the timeout path
with `apply_timeout_minutes: 5` against a command that ignores SIGTERM.

expected: No output lines are lost at the end of the run; the run reaches status `failed` with
`error_code: apply_timeout`; no `jobq.output_join_timeout` WARN is emitted on the normal path; no orphaned tofu process
survives.

why_human: `17-REVIEW-FIX.md` WR-01 replaced `cmd.StdoutPipe()` with runner-owned `os.Pipe` files and moved the scanner
join to AFTER `cmd.Wait()`. The `sh`-based tests pass under `-race`, but a real tofu with provider subprocesses is the
case the fix exists for and no test reproduces it.

result: [pending]

### 2. Boot-Sweep gegen ein echtes /data mit Alt-Runs (WR-06)

On a `/data` volume that already holds run directories, restart the add-on. Include (a) a run left at status `running`,
(b) a run left at `queued`, (c) a directory with a valid run-id name but no readable `meta.json` and an mtime older than
`runs_retention_hours`. Then read the boot log and `GET /v1/runs`.

expected: (a) and (b) both report status `interrupted` with a `finished_at` and no `error_code`;
`runs_swept_interrupted` logs count 2; (c) is deleted and logged as `runs.rotated_unparseable`; no run that is genuinely
queued/running in THIS container is ever deleted.

why_human: `17-REVIEW-FIX.md` WR-06 changed a tested boot-sweep contract — `SweepInterrupted` now also sweeps `queued`,
and `Rotate` ages an unparseable directory by its own mtime. The destructive branch runs against a real `/data` on first
boot after upgrade, and a false positive deletes operator run history irreversibly.

result: [pending]

### 3. Admission-Reordering unter echtem Prozess-Timing (WR-08)

With `max_parallel_jobs: 4`, submit 4 applies against repo A (so three wait on A's mutex) and then one plan against repo
B. Repeat with all 5 against repo A.

expected: The repo-B submission returns 202, not 503 `apply_capacity_exhausted`; the 5th repo-A submission returns 503
with `Retry-After: 30`; every run eventually reaches a terminal status and no repo stays wedged.

why_human: `17-REVIEW-FIX.md` WR-08 reordered the admission gates — `work()` now hands the global slot back BEFORE
waiting on the repo mutex and takes a fresh one after. Proven under `-race` against an injected exec, so this is a
confirmation pass against real process timing rather than an open question.

result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
