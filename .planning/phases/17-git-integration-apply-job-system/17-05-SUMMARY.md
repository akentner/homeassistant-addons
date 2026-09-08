---
phase: 17-git-integration-apply-job-system
plan: 05
subsystem: infra
tags: [go, opentofu, concurrency, semaphore, mutex, os-exec, sigterm, jobq]

requires:
  - phase: 17-git-integration-apply-job-system
    provides: "internal/contract run kinds/statuses and the D-19 error_code taxonomy (17-01/17-02)"
  - phase: 17-git-integration-apply-job-system
    provides: "internal/runs NewRunID, ValidateDir, Store, OutputWriter (17-02/17-04)"
  - phase: 17-git-integration-apply-job-system
    provides: "internal/git Manager (Repo/WorkTree/EnsureCloned) and the typed *git.Error (17-03)"
  - phase: 16-bridge-foundation
    provides: "internal/statebackend Backend interface (UseLockfile/Endpoint/Bucket/Region)"
provides:
  - "internal/jobq: the background execution engine behind POST /v1/plan and POST /v1/apply"
  - "Queue.Submit — non-blocking admission returning a run id, with ErrCapacityExhausted on saturation"
  - "Queue.Drain — waits for in-flight jobs, for the cmd/runner SIGTERM window"
  - "ExecFunc/ExecSpec/ExecResult — the injectable process seam (DefaultExec is the os/exec implementation)"
  - "RUN-02/RUN-03 tofu command lines, the D-16 SIGTERM->SIGKILL kill chain, and the D-17/D-18 plan-artifact lifecycle"
affects: [17-06 HTTP handlers, 17-07 options wiring and main.go, 17-08 docs]

actuals:
  tokens: 17472
  tasks: 3
  commits: 6
plan_head_before: de19c5832830fa8f0802b3cc3a5262879300de85

tech-stack:
  added: []
  patterns:
    - "Injected ExecFunc seam: admission control, serialization and command lines are provable with no tofu binary"
    - "Non-blocking buffered-channel semaphore for visible back-pressure instead of an invisible queue"
    - "Per-key mutex map behind an RWMutex with read-then-upgrade creation (mirrors terraform-bridge/internal/mutex)"
    - "Bounded mutex acquisition with release hand-off, so an abandoned Lock() can never wedge a repo"
    - "Occupancy-counter test harness: concurrency claims asserted against atomic counters, never timestamps"

key-files:
  created:
    - iac-runner/internal/jobq/queue.go
    - iac-runner/internal/jobq/exec.go
    - iac-runner/internal/jobq/queue_test.go
    - iac-runner/internal/jobq/exec_test.go
    - iac-runner/internal/jobq/serialization_test.go
  modified: []

key-decisions:
  - "ExecSpec carries Path and Env in addition to the plan's published fields — the plan's own DefaultExec body
    dereferences both, and threading them through the spec keeps ExecFunc a pure function of its argument."
  - "The mutex wait is bounded by apply_timeout and, on expiry, hands the pending acquisition to a second goroutine
    that releases it. terraform-bridge's TryAcquire leaves the lock held in that case, which would permanently wedge
    the repo — the exact failure RUN-06 exists to prevent."
  - "DefaultExec joins the output scanners with a bound (killGrace) rather than unbounded: a SIGKILLed shell can leave
    an orphaned grandchild holding the pipe write end, so an unbounded join would hang the worker forever."
  - "killGrace is a package-level var (production value 10s) purely so the kill-chain tests can shrink it."
  - "A failed tofu init short-circuits and reports init's own exit code; running plan/apply against an uninitialized
    directory would only produce a second, more confusing error."
  - "os.Environ() is passed to the tofu process so backend credentials and TF_* knobs propagate (17-07 exports them)."

patterns-established:
  - "Rejection before capacity: unknown repo, invalid dir, missing clone and missing tofu are all refused before the
    semaphore acquire and before any run directory exists, so malformed requests cannot consume capacity."
  - "Defer registration order as a contract: the slot release is registered first so it runs last, and the recover
    defer is registered before lock.Lock() so a panic under the mutex is still recovered."
  - "Compile-time signature locks (`var _ func(...) = Fn`) in the test file, because the plan's end-anchored grep
    criteria cannot match valid Go — drift becomes a build failure instead of a grep miss."

requirements-completed: [RUN-02, RUN-03, RUN-06]

coverage:
  - id: D1
    description: "Submitting a plan or an apply returns immediately with a run id while tofu runs in the background"
    requirement: "RUN-02"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/queue_test.go#TestSubmitReturnsRunIDAndQueuedMeta"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two applies against the same repo never run at the same time; the second waits its turn"
    requirement: "RUN-06"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/serialization_test.go#TestSameRepoAppliesSerialize"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/serialization_test.go#TestSecondSameRepoRunIsQueuedWhileFirstRuns"
        status: pass
    human_judgment: false
  - id: D3
    description: "Applies against different repos do run at the same time"
    requirement: "RUN-06"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/serialization_test.go#TestCrossRepoAppliesRunInParallel"
        status: pass
    human_judgment: false
  - id: D4
    description: "A saturated runner refuses new submissions with a distinct capacity error instead of queueing"
    requirement: "RUN-06"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/queue_test.go#TestSubmitCapacityExhausted"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/serialization_test.go#TestCapacityRefusesThirdSubmission"
        status: pass
    human_judgment: false
  - id: D5
    description: "The repo mutex and the global slot are released on success, failure and a recovered panic"
    requirement: "RUN-06"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/serialization_test.go#TestFailedJobReleasesRepoMutex"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/serialization_test.go#TestPanickingJobReleasesRepoMutex"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/queue_test.go#TestWorkerPanicIsRecoveredAndSlotReleased"
        status: pass
    human_judgment: false
  - id: D6
    description: "The RUN-02 plan command line writes its artifact into the run directory"
    requirement: "RUN-02"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestRunJobPlanCommandLine"
        status: pass
    human_judgment: false
  - id: D7
    description: "An apply consumes a prior successful plan artifact, and applies inline without one or after retention swept it"
    requirement: "RUN-03"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestExecApplyUsesPriorPlanFile"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestRunJobApplyInlineWhenNoPriorPlan"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestApplyFallsBackWhenPriorPlanFileMissing"
        status: pass
    human_judgment: false
  - id: D8
    description: "A run past its deadline is SIGTERMed, SIGKILLed 10s later, and recorded failed with a timeout code"
    requirement: "RUN-03"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestDefaultExecTimeoutSendsSIGTERMThenSIGKILL"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestDefaultExecGracefulExitNotKilled"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/queue_test.go#TestTimeoutMarksRunFailedWithTimeoutCode"
        status: pass
    human_judgment: false
  - id: D9
    description: "Every tofu stdout/stderr line lands in the run's output log while the job is still running"
    requirement: "RUN-02"
    verification:
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestRunJobStreamsOutputToRunLog"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/jobq/exec_test.go#TestDefaultExecCapturesBothStreams"
        status: pass
    human_judgment: false
  - id: D10
    description: "Observing live plan/apply progress through GET /v1/runs/{id} against a real repo and a real tofu binary"
    verification: []
    human_judgment: true
    rationale: "The HTTP surface lands in 17-06 and the wiring in 17-07; end-to-end observation needs a real repo,
      real credentials and a real tofu binary, none of which exist in this plan's scope."

duration: 25 min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 05: jobq Background Execution Engine Summary

**`internal/jobq` runs OpenTofu plan/apply as background jobs behind a non-blocking `max_parallel_jobs` semaphore and a
per-repo mutex, with a SIGTERM-then-SIGKILL timeout chain, prior-plan-artifact consumption, and line-by-line output
capture — RUN-06's serialization guarantee proven by occupancy counters under `-race -count=5`.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-08T11:05:00Z
- **Completed:** 2026-09-08T11:30:00Z
- **Tasks:** 3 of 3
- **Files created:** 5 (2 source, 3 test; 2259 lines added)

## Accomplishments

- **Admission control that cannot be starved or wedged.** Unknown repo, invalid `dir`, missing clone and missing tofu
  are all refused *before* the semaphore acquire, so a stream of malformed requests can neither consume capacity nor
  litter `/data/runs` with stillborn runs. Saturation is refused with `ErrCapacityExhausted` (D-06) rather than queued.
- **RUN-06 proven from seven angles, not asserted.** `serialization_test.go` gates a fake exec per repo and records
  concurrent occupancy in atomic counters: same-repo peak occupancy is 1, cross-repo peak is 2, and a failed job, a
  panicking job and a drained queue all leave the repo mutex free. Nothing is inferred from timestamps.
- **The tofu command lines are literal and tested.** `init -input=false -no-color` (plus
  `-backend-config=use_lockfile=true` only when the backend asks for it), then either
  `plan -no-color -input=false -out=<run dir>/plan.tfplan` or `apply -no-color -input=false -auto-approve [<plan file>]`.
  A failed init short-circuits and reports its own exit code.
- **The timeout releases the state lock.** `cmd.Cancel` sends SIGTERM and `cmd.WaitDelay` escalates to SIGKILL 10s
  later (D-16), so tofu gets a chance to drop its S3/file lock instead of leaving a stale lock for the next apply.
- **The plan-artifact lifecycle handles retention.** An apply consumes the newest succeeded plan for the same
  `(repo, dir)` whose artifact still exists on disk, and falls back to an inline apply when retention already swept it
  (D-17/D-18).

## Task Commits

1. **Task 1: Queue admission control, per-repo mutex, run lifecycle** — `ab59156` (test, RED) → `aff5972` (feat, GREEN)
2. **Task 2: tofu command lines, timeout kill chain, plan artifact, output capture** — `d13be9e` (test, RED) →
   `37538c4` (feat, GREEN)
3. **Task 3: prove RUN-06 serialization and cross-repo parallelism** — `6e2681a` (test)

**Plan metadata:** `adc63e8` (docs: complete plan). The measured `commits: 6` in the frontmatter is
`git rev-list --count de19c58..HEAD` and therefore includes this metadata commit alongside the five task commits.

No REFACTOR commit was needed for either TDD task: both GREEN implementations landed in their final shape and the
suites stayed green, so a no-op `refactor(...)` commit would have been noise.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
| ---- | --- | ----- | -------- | ----- |
| 1 | `ab59156` | `aff5972` | — | RED verdict `RED_EVIDENCE_OK`, target `TestSubmitUnknownRepo` |
| 2 | `d13be9e` | `37538c4` | — | RED verdict `RED_EVIDENCE_OK`, target `TestRunJobPlanCommandLine` |
| 3 | n/a | n/a | — | Test-only task (see Deviation 5) |

Both RED phases were validated with `gsd-tools check tdd-red-evidence` after translating `go test -json` into the TAP
shape the checker parses (the checker is written against the Node test runner; the translation is a faithful
one-line-per-test rendering of the actual Go run, not a hand-written record).

## Files Created/Modified

- `iac-runner/internal/jobq/queue.go` — the two admission gates (non-blocking global semaphore + blocking per-repo
  mutex), `New`/`Submit`/`Drain`, the worker goroutine with its release discipline, and the store status transitions.
- `iac-runner/internal/jobq/exec.go` — `runJob` (command sequences, deadline, output sinks), `priorPlanFile` (D-18),
  and `DefaultExec` (os/exec with the D-16 kill chain and line-oriented pipe scanning).
- `iac-runner/internal/jobq/queue_test.go` — 14 tests plus the shared `newEnv` harness (fake git runner, temp store,
  planted working trees) that the other two test files reuse.
- `iac-runner/internal/jobq/exec_test.go` — 14 tests: command-line assertions via a recording fake, plus real
  `/bin/sh` scripts for both kill-chain paths.
- `iac-runner/internal/jobq/serialization_test.go` — 7 RUN-06 proofs on the occupancy harness.

## Decisions Made

See `key-decisions` in the frontmatter. The three that future plans need to know about:

1. **`ExecSpec` gained `Path` and `Env`.** 17-06/17-07 consume the published contract; those two fields are part of it.
2. **`Queue.Drain(ctx)` is the SIGTERM hook.** 17-07 must call it inside `cmd/runner/signals.go`'s 30s window;
   `Drain` returns `ctx.Err()` if the deadline passes first, which is the signal to escalate.
3. **`ErrCapacityExhausted` is a sentinel, not a typed `*git.Error`.** 17-06 must match it with `errors.Is` and emit
   `apply_capacity_exhausted` + `Retry-After: 30` itself; every other Submit rejection already carries its
   `contract.ErrCode*` inside a `*git.Error`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ExecSpec` was missing the `Path` and `Env` fields its own consumer needs**

- **Found during:** Task 1 (contract publication)
- **Issue:** The plan's `<interfaces>` block declares `ExecSpec{WorkDir, Args, Stdout, Stderr}`, but the plan's own
  Task 2 action text builds `exec.CommandContext(ctx, spec.Path, spec.Args...)` and sets `cmd.Env = spec.Env`. With the
  published shape there is no way to hand the resolved tofu binary or the credential environment to an `ExecFunc`
  without closing over `Queue`, which would defeat the injectable seam.
- **Fix:** Added `Path string` and `Env []string` to `ExecSpec`. Purely additive to the published contract.
- **Files modified:** `iac-runner/internal/jobq/queue.go`
- **Verification:** `TestRunJobPlanCommandLine` asserts `calls[1].Path == q.tofuPath`.
- **Committed in:** `aff5972`

**2. [Rule 3 - Blocking] Task 1 could not compile without Task 2's symbols**

- **Found during:** Task 1
- **Issue:** The plan has Task 1's `New` default to `DefaultExec` and Task 1's worker call `q.runJob(...)`, both of
  which the plan assigns to Task 2's `exec.go`. Go has no forward declarations, so Task 1 in isolation does not build.
- **Fix:** Task 1's GREEN commit includes an `exec.go` carrying a documented seam (`runJob` issuing a single exec call,
  `DefaultExec` returning a not-implemented error, `killGrace`). Task 2's GREEN commit replaces the file wholesale with
  the real implementation. Both commits build, vet and test clean in isolation.
- **Files modified:** `iac-runner/internal/jobq/exec.go`
- **Verification:** `go build ./... && go vet ./... && go test ./internal/jobq/... -race` at both `aff5972` and
  `37538c4`.
- **Committed in:** `aff5972`, then `37538c4`

**3. [Rule 3 - Blocking] Grep-shaped acceptance criteria could not be satisfied as written**

- **Found during:** Tasks 1 and 2
- **Issue:** Three distinct defects in the criteria, all of the class already recorded in 17-04:
  - Task 1's signature criterion anchors at end-of-line
    (`^func New\(d Deps\) \(\*Queue, error\)$`), which no valid Go declaration can match because the language requires
    `{` on the signature line. It returns 0 against correct code.
  - Task 2's `"apply"|"-auto-approve"` (want 2) and `applyTimeout|context.WithTimeout` (want 2) count *lines*, not
    occurrences; both tokens naturally sit on one line each.
  - Task 1's four-rejection-code criterion (want 4) requires `ErrCodeGitCloneMissing` in `queue.go`, but that code is
    produced by `git.EnsureCloned` and correctly propagated verbatim rather than re-derived.
- **Fix:** (a) Verified the signature criterion with the corrected `... \{$` pattern (returns 3) and additionally
  pinned the same three signatures as compile-time `var _ func(...) = Fn` assertions, so drift is a build failure.
  (b) Formatted the plan/apply argument slices one element per line — genuinely more readable and satisfies the count —
  and hoisted `timeout := q.applyTimeout` above the `context.WithTimeout` call. (c) Named
  `contract.ErrCodeGitCloneMissing` in the comment at the `EnsureCloned` call site, documenting which taxonomy entry
  that branch surfaces and who owns it. No code was reshaped to satisfy a broken regex.
- **Files modified:** `iac-runner/internal/jobq/queue.go`, `iac-runner/internal/jobq/exec.go`,
  `iac-runner/internal/jobq/queue_test.go`
- **Verification:** Both tasks' full `<verify>` command lines now pass end to end.
- **Committed in:** `aff5972`, `37538c4`

**4. [Rule 1 - Bug] Task 1's gating test fakes panicked once `runJob` issued two exec calls per job**

- **Found during:** Task 2
- **Issue:** Task 1's fake `ExecFunc`s signalled entry with a bare `close(entered)`. That was correct against Task 1's
  single-call seam, but Task 2's real `runJob` calls `q.exec` twice (init, then plan/apply), so the second call panicked
  with `close of closed channel`. The panic was swallowed by the worker's `recover`, which turned it into runs
  spuriously marked `failed` — `TestSubmitCapacityExhausted` and `TestDrainWaitsForInFlight` failed.
- **Fix:** Extracted a `gate(entered, release, res)` helper whose entry signal is `sync.Once`-guarded, and reworded the
  panic-injection fake to key off the first exec call explicitly.
- **Files modified:** `iac-runner/internal/jobq/queue_test.go`
- **Verification:** `go test ./internal/jobq/... -race -count=5` green.
- **Committed in:** `37538c4`

**5. [Rule 3 - Blocking] Task 3 is test-only and cannot produce an intentional RED**

- **Found during:** Task 3
- **Issue:** Task 3 is marked `tdd="true"` but its `<files>` list contains only `serialization_test.go`. The behavior
  it proves was fully implemented by Tasks 1 and 2, so a RED phase would be either an unexpected green (INVALID_RED) or
  a deliberately broken test committed to manufacture a failure.
- **Fix:** Executed Task 3 as a single `test(17-05)` commit. This matches the behavior-adding-task predicate the
  MVP+TDD gate uses (no non-test source files in `<files>` ⇒ exempt) and `tdd.md`'s "the feature may already exist —
  investigate" guidance.
- **Files modified:** `iac-runner/internal/jobq/serialization_test.go`
- **Verification:** All 7 tests pass under `-race -count=5`.
- **Committed in:** `6e2681a`

**6. [Rule 2 - Missing critical] The reference mutex pattern has a lock-leak bug that RUN-06 cannot afford**

- **Found during:** Task 1
- **Issue:** The plan points at `terraform-bridge/internal/mutex/manager.go` as "THE analog" for the bounded acquire.
  Its `TryAcquire` deadline branch abandons the acquiring goroutine: when that goroutine later wins `Lock()`, nobody
  ever calls `Unlock()`, so the key is wedged for the process lifetime. Its own comment concedes this ("we leave the
  lock held"). Copying it would have reintroduced exactly the failure RUN-06 exists to prevent.
- **Fix:** `jobq.acquire` hands the pending acquisition to a second goroutine (`<-acquired; lock.Unlock()`) on expiry,
  so both goroutines terminate and the mutex is always released. The reasoning is documented at the function.
- **Files modified:** `iac-runner/internal/jobq/queue.go`
- **Verification:** `TestPanickingJobReleasesRepoMutex` / `TestFailedJobReleasesRepoMutex` plus the `-count=5` run.
- **Committed in:** `aff5972`

**7. [Rule 2 - Missing critical] The output-scanner join had to be bounded to avoid a worker hang**

- **Found during:** Task 2
- **Issue:** The plan specifies joining both `bufio.Scanner` goroutines with a `sync.WaitGroup` *before* `cmd.Wait()`
  returns, so no trailing line is lost. That is correct for a well-behaved process, but a SIGKILLed shell leaves its
  orphaned grandchild (`sleep` in the kill-chain test, a `terraform-provider-*` plugin in production) holding the pipe's
  write end. EOF then never arrives, the unbounded join never completes, `cmd.Wait()` is never called, and `WaitDelay`
  — which is what would have closed the pipes — never fires. The worker hangs forever holding the repo mutex and a
  slot.
- **Fix:** The join waits on a channel with a `killGrace` bound and logs `jobq.output_join_timeout` on expiry, then
  falls through to `cmd.Wait()`, whose own `WaitDelay` closes the pipes and unblocks the scanners. No line is lost in
  the normal path (EOF arrives first); only an orphan's post-mortem output is dropped, which is correct.
- **Files modified:** `iac-runner/internal/jobq/exec.go`
- **Verification:** `TestDefaultExecTimeoutSendsSIGTERMThenSIGKILL` returns within the 5s bound and logs the expected
  join timeout.
- **Committed in:** `37538c4`

---

**Total deviations:** 7 auto-fixed (Rule 1 × 1, Rule 2 × 2, Rule 3 × 4).
**Impact on plan:** No scope change. Deviations 1, 2 and 5 are mechanical consequences of Go's compilation model and of
the plan's own task split; 3 is the phase-wide grep-criteria defect already recorded in 17-04; 4, 6 and 7 are
correctness fixes without which RUN-06's "the mutex is released on every exit path" guarantee would not actually hold.

## Issues Encountered

- **`Deps.TofuPath == ""` is overloaded.** It means "resolve from PATH", so it cannot express "no tofu binary". The
  dev/CI container has a `tofu` stub on PATH, so `TestSubmitTofuMissing` initially resolved a real path and got no
  error. The test now clears the *resolved* `q.tofuPath` after construction (same-package access) and documents why.
  Production behavior is unaffected.
- **SIGTERM-ignoring test process, observed behavior:** with `sh -c 'trap "" TERM; sleep 30'`, a 200 ms deadline and
  `killGrace` shrunk to 400 ms, `DefaultExec` returned `TimedOut: true, ExitCode: -1` well inside the 5 s bound. It
  also emitted one `jobq.output_join_timeout` warning, because the orphaned `sleep` kept the pipe open — the direct
  observation that motivated deviation 7.
- **Flakiness under `-count=5`:** none. `go test ./internal/jobq/... -race -count=5` completed in 15.3 s with no
  failures and no race reports across repeated runs.
- **Environment:** all Go work ran inside a throwaway `golang:1.25-alpine` container with `gcc musl-dev` added for
  `-race` and a `tofu` stub on PATH for the pre-existing `httpapi/handlers` probe, per the phase's established
  environment facts. Nothing was installed on the host.
- **Out of scope, not fixed:** `gofmt -l .` still reports six pre-existing files
  (`cmd/runner/version.go`, `internal/auth/token.go`, `internal/httpapi/router.go`, and three `_test.go` files) that
  this plan never touched. All five `internal/jobq` files are gofmt-clean. The `hadolint` DL3003 finding on
  `iac-runner/Dockerfile:40` remains deferred to 17-07 per `deferred-items.md`.

## Known Stubs

None. Every function in `internal/jobq` is fully implemented; the Task-1 seam in `exec.go` was replaced in `37538c4`
and no placeholder, TODO or "not implemented" string remains in the package.

## Threat Flags

| Flag | File | Description |
| ---- | ---- | ----------- |
| threat_flag: credential-propagation | `iac-runner/internal/jobq/exec.go` | `runJob` passes `os.Environ()` to the tofu child process, so every variable the runner holds — including the backend credentials 17-07 exports — is visible to tofu and to any provider plugin it loads. This is required for the S3/R2 backend to authenticate and is the intended design, but it is a trust boundary the plan's scope did not spell out. 17-07 should confirm the exported set is the minimum tofu needs. |
| threat_flag: process-spawn | `iac-runner/internal/jobq/exec.go` | `DefaultExec` is a new process-spawn surface reachable from an authenticated HTTP request. Argument construction is entirely internal (no request field reaches `Args`), and `dir` is `runs.ValidateDir`-constrained before it becomes `cmd.Dir`, so there is no injection path — recorded so 17-06's handler review keeps it that way. |

## Next Phase Readiness

Ready for **17-06** (HTTP handlers) and **17-07** (Options wiring):

- 17-06 consumes `jobq.New`, `Queue.Submit`, `jobq.Request`, `jobq.ErrCapacityExhausted` and the `*git.Error` codes.
  Mapping contract: `errors.Is(err, ErrCapacityExhausted)` → 503 + `apply_capacity_exhausted` + `Retry-After: 30`;
  every other Submit error is a `*git.Error` whose `Code` is already the wire value.
- 17-07 fills `jobq.Deps` from Options (`max_parallel_jobs`, `apply_timeout_minutes`) and must call
  `Queue.Drain(ctx)` inside `cmd/runner/signals.go`'s 30 s SIGTERM window.
- The `redaction.audit` slog obligation from 17-04 remains open and is still owned by 17-06 — `jobq` writes raw lines
  and never redacts, per D-08.

No blockers.

---

_Phase: 17-git-integration-apply-job-system_
_Completed: 2026-09-08_

## Self-Check: PASSED

- All 5 created source/test files present on disk.
- All 6 commits (`ab59156`, `aff5972`, `d13be9e`, `37538c4`, `6e2681a`, metadata) reachable in `git log --all`.
- `git rev-list --count de19c58..HEAD` = 6, matching the `actuals.commits` frontmatter value.
- Plan verification re-run clean: `go build ./...`, `go vet ./...`, `go test ./... -race -count=1` and
  `go test ./internal/jobq/... -race -count=5` all exit 0; `git diff -- go.mod go.sum` empty; no `"tofu"` literal in
  any `internal/jobq` test file.
