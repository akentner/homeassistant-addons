---
phase: 17-git-integration-apply-job-system
verified: 2026-09-08T18:05:00Z
status: human_needed
score: 23/23 must-haves verified
covered_files:
  - ".planning/REQUIREMENTS.md"
  - ".planning/ROADMAP.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-01-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-01-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-02-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-02-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-03-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-03-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-04-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-04-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-05-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-05-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-06-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-06-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-07-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-07-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-08-PLAN.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-08-SUMMARY.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-CONTEXT.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-DISCUSSION-LOG.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-REVIEW-FIX.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-REVIEW.md"
  - ".planning/phases/17-git-integration-apply-job-system/17-SECURITY.md"
  - ".planning/phases/17-git-integration-apply-job-system/deferred-items.md"
  - "iac-runner/DOCS.md"
  - "iac-runner/Dockerfile"
  - "iac-runner/README.md"
  - "iac-runner/build.yaml"
  - "iac-runner/cmd/runner/main.go"
  - "iac-runner/cmd/runner/signals.go"
  - "iac-runner/config.yaml"
  - "iac-runner/internal/contract/types.go"
  - "iac-runner/internal/git/errors.go"
  - "iac-runner/internal/git/errors_test.go"
  - "iac-runner/internal/git/manager.go"
  - "iac-runner/internal/git/manager_test.go"
  - "iac-runner/internal/git/repo.go"
  - "iac-runner/internal/httpapi/handlers/get_run.go"
  - "iac-runner/internal/httpapi/handlers/get_run_test.go"
  - "iac-runner/internal/httpapi/handlers/list_runs.go"
  - "iac-runner/internal/httpapi/handlers/list_runs_test.go"
  - "iac-runner/internal/httpapi/handlers/plan.go"
  - "iac-runner/internal/httpapi/handlers/plan_test.go"
  - "iac-runner/internal/httpapi/handlers/redaction_audit.go"
  - "iac-runner/internal/httpapi/handlers/redaction_audit_test.go"
  - "iac-runner/internal/httpapi/handlers/repos_pull.go"
  - "iac-runner/internal/httpapi/handlers/repos_pull_test.go"
  - "iac-runner/internal/httpapi/handlers/write_error.go"
  - "iac-runner/internal/httpapi/handlers/write_error_test.go"
  - "iac-runner/internal/httpapi/router.go"
  - "iac-runner/internal/httpapi/router_test.go"
  - "iac-runner/internal/jobq/exec.go"
  - "iac-runner/internal/jobq/exec_test.go"
  - "iac-runner/internal/jobq/queue.go"
  - "iac-runner/internal/jobq/queue_test.go"
  - "iac-runner/internal/jobq/serialization_test.go"
  - "iac-runner/internal/runs/dir.go"
  - "iac-runner/internal/runs/dir_test.go"
  - "iac-runner/internal/runs/ids.go"
  - "iac-runner/internal/runs/ids_test.go"
  - "iac-runner/internal/runs/output.go"
  - "iac-runner/internal/runs/output_test.go"
  - "iac-runner/internal/runs/redact.go"
  - "iac-runner/internal/runs/redact_test.go"
  - "iac-runner/internal/runs/retention.go"
  - "iac-runner/internal/runs/retention_test.go"
  - "iac-runner/internal/runs/store.go"
  - "iac-runner/internal/runs/store_test.go"
covered_digest: "v1:sha256:7bb39e3b0991290be65a94513aebfef032eaecf0448698cbc5f6d5660e7ee143"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth:
      "GIT-03 SSH host-key pinning and deploy-key-only authentication observed against a live remote (security threat
      T-09a residual)"
    addressed_in: "Phase 19"
    evidence:
      "Phase 19 goal: 'Every v1.4 requirement is empirically verified against a live HA host (ha-nextgen or
      haos-op3050-1)'; assignment already recorded in 17-03-SUMMARY.md and 17-SECURITY.md T-09a"
  - truth: "End-to-end tofu plan + apply + drift + idempotency cycle against real infrastructure"
    addressed_in: "Phase 19"
    evidence:
      "Phase 19 SC-2: 'End-to-end plan + apply + drift + idempotency cycle against a local_file-provider fixture: apply
      succeeds, re-apply shows No changes, …'"
  - truth: "State-backend credentials reach the tofu child process so `tofu init` against r2/s3 can authenticate"
    addressed_in: "Phase 19"
    evidence:
      "Phase 19 SC-3: 'State-backend matrix: all three backends (r2, s3, local) verified end-to-end against a real R2
      bucket …'; recorded in deferred-items.md and in internal/jobq/exec.go's tofuEnv() doc comment"
  - truth: "The add-on installs on a real HA host and answers /v1/version 200 + /healthz 200 within 2s"
    addressed_in: "Phase 19"
    evidence:
      "Phase 19 SC-1: 'make install-runner-equivalent (or direct docker run against the built image) installs the add-on
      in a real HA host; /v1/version returns 200; /healthz returns 200 within 2s'"
human_verification:
  - test:
      "Run a real `tofu plan` (or any long-running, chatty command) through POST /v1/plan on the built image and compare
      the tail of `GET /v1/runs/{id}?page=<last>` against `cat /data/runs/{id}/output.log | wc -l`. Then trigger the
      timeout path with `apply_timeout_minutes: 5` against a command that ignores SIGTERM."
    expected:
      "No output lines are lost at the end of the run; the run reaches status `failed` with `error_code: apply_timeout`;
      no `jobq.output_join_timeout` WARN is emitted on the normal path; no orphaned tofu process survives."
    why_human:
      "17-REVIEW-FIX.md WR-01 replaced `cmd.StdoutPipe()` with runner-owned `os.Pipe` files and moved the scanner join
      to AFTER `cmd.Wait()`. `TestDefaultExecCapturesBothStreams` / `TestDefaultExecTimeoutSendsSIGTERMThenSIGKILL` /
      `TestDefaultExecLongCommandJoinsCleanly` exercise this with `sh`, but the executor itself marked the change
      'requires human verification (process/pipe lifecycle change)' — a real tofu with provider subprocesses is the case
      the fix exists for and no test reproduces it."
  - test:
      "On a /data volume that already holds run directories, restart the add-on. Include (a) a run left at status
      `running`, (b) a run left at `queued`, (c) a directory with a valid run-id name but no readable `meta.json` and an
      mtime older than `runs_retention_hours`. Then read the boot log and `GET /v1/runs`."
    expected:
      "(a) and (b) both report status `interrupted` with a `finished_at` and no `error_code`; `runs_swept_interrupted`
      logs count 2; (c) is deleted and logged as `runs.rotated_unparseable`; no run that is genuinely queued/running in
      THIS container is ever deleted."
    why_human:
      "17-REVIEW-FIX.md WR-06 changed a tested boot-sweep contract: `SweepInterrupted` now also sweeps `queued`, and
      `Rotate` ages an unparseable directory by its own mtime. The executor marked it 'requires human verification
      (changes a tested boot-sweep contract)'. `TestSweepInterruptedTransitionsActiveRuns` and
      `TestRotateReclaimsUnparseableRunDirectory` pass, but the destructive branch runs against a real /data on first
      boot after upgrade and a false positive deletes operator run history irreversibly."
  - test:
      "With `max_parallel_jobs: 4`, submit 4 applies against repo A (so three wait on A's mutex) and then one plan
      against repo B. Repeat with all 5 against repo A."
    expected:
      "The repo-B submission returns 202, not 503 `apply_capacity_exhausted`; the 5th repo-A submission returns 503 with
      `Retry-After: 30`; every run eventually reaches a terminal status and no repo stays wedged."
    why_human:
      "17-REVIEW-FIX.md WR-08 reordered the admission gates — `work()` now hands the global slot back BEFORE waiting on
      the repo mutex and takes a fresh one after. The executor marked it 'requires human verification (concurrency
      reordering)'. `TestSameRepoWaiterDoesNotStarveOtherRepos` and the serialization suite prove it under `-race`
      against an injected exec, so this is a confirmation pass against real process timing rather than an open question."
---

# Phase 17: Git Integration + Apply Job System — Verification Report

**Phase Goal:** The add-on clones configured Git repos at startup, exposes `POST /v1/repos/{name}/pull` for SSH-keyed
git-pull, and provides `POST /v1/plan`, `POST /v1/apply`, `GET /v1/runs/{id}`, `GET /v1/runs` for OpenTofu job
lifecycle. Concurrent applies on the same repo are serialized; cross-repo applies run in parallel. `tofu` stdout/stderr
is captured and secret-redacted.

**Verified:** 2026-09-08T18:05:00Z at HEAD `0e60300` **Status:** human_needed **Re-verification:** No — initial
verification

## Goal Achievement

### Observable Truths — ROADMAP Success Criteria (SC-1..SC-11)

| #     | Truth                                                                                                                                                       | Status                                          | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC-1  | `repos` list-of-dict schema with name/url/branch/ref; malformed entries rejected                                                                            | ✓ VERIFIED                                      | `iac-runner/config.yaml:39-44` — `name: match(^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$)`, `url: match(^(git@\|ssh://).+$)`, `branch/ref: str?`. Re-validated in Go at `internal/git/repo.go:26-44,79-106` (name/url/ref regexes, `--`-injection classes rejected). Tests: `TestRepoConfigValidateAccepts/Rejects`, `TestNewManagerRejectsInvalidAndDuplicateRepos`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| SC-2  | Startup clone into `/data/repos/<name>/` if absent; existing untouched; failures non-fatal                                                                  | ✓ VERIFIED                                      | `internal/git/manager.go:cloneOutcome` → `IsCloned` skip (Skipped=true), 3 attempts with 1s/5s backoff, `CloneAll` never returns an error. `cmd/runner/main.go:261-279` logs `git_clone_failed`/`git_clone_skipped`/`git_clone_succeeded` and continues, bounded by `startupCloneTimeout` 5m. Tests PASS: `TestManagerCloneSkipsExistingWorkTree`, `TestManagerCloneRetriesThreeTimesWithBackoff`, `TestManagerCloneAllReportsPerRepoOutcomes`, `TestNewManagerSafeDirectoryFailureIsNotFatal`                                                                                                                                                                                                                                                                                                                                                                                                 |
| SC-3  | `POST /v1/repos/{name}/pull` runs `git pull --ff-only` (or the configured ref) with the deploy key; 409/403 typed                                           | ✓ VERIFIED (documented deviation)               | Unpinned: `manager.go:Pull` → `git pull --ff-only origin -- <branch>`. Pinned: `landOnRef` → `fetch origin -- <ref>` + `checkout --detach FETCH_HEAD`. Credentials: `sshEnv` builds `GIT_SSH_COMMAND=ssh -i <keysDir>/<name>.key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<keysDir>/known_hosts -o BatchMode=yes -o ConnectTimeout=10` + `GIT_TERMINAL_PROMPT=0`. Statuses: `write_error.go:statusForCode` → 403 for `git_ssh_handshake`/`git_unauthorized`, 409 for `git_non_fast_forward`. Tests PASS: `TestManagerPullUnpinnedRunsFastForward`, `TestManagerPullPinnedFetchesAndChecksOut`, `TestManagerPullCarriesSSHCredentials`, `TestReposPullSSHHandshakeIs403`, `TestReposPullNonFastForwardIs409`. **Deviation:** D-12's blanket refusal was narrowed to `ff_only: true` only — see "Deviation analysis" below                                       |
| SC-4  | Git errors surface as typed `error_code: "git_*"` + Options hint; no stack traces                                                                           | ✓ VERIFIED                                      | `internal/git/errors.go` — `git.Error{Code,Message,Hint}` deliberately stores NO stderr (type comment L18-25); `Classify` maps 6 stderr families first-match-wins with a documented fallback. All 8 `git_*` codes in `contract/types.go:170-177`. `repos_pull.go:158-176` logs the unclassified error and serves a fixed 502 body. Tests PASS: `TestClassify` (all families + unknown), `TestErrorMessageCarriesCodeAndHintButNotStderr`, `TestManagerPullErrorBodyHasNoStderrDump`, `TestReposPullOpaqueErrorDoesNotLeak`                                                                                                                                                                                                                                                                                                                                                                     |
| SC-5  | `POST /v1/plan` runs `tofu init -input=false` then `tofu plan -no-color -out=/data/runs/{id}/plan.tfplan`; 202 + `{run_id,status:"queued"}` + `Location`    | ✓ VERIFIED                                      | `jobq/exec.go:runJob` — `init -input=false -no-color` (+ `-backend-config=use_lockfile=true` when the backend requires it), short-circuits on non-zero init; then `plan -no-color -input=false -out=<store.Dir(runID)>/plan.tfplan`. `handlers/plan.go:submitHandler` writes `Location: /v1/runs/<id>` + 202 + `contract.RunAccepted{RunID, RunStatusQueued}`. Tests PASS: `TestRunJobPlanCommandLine`, `TestPlanQueuesRunKindPlan` (asserts `Location == /v1/runs/RID123`), `TestInitFailureShortCircuits`, `TestUseLockfileFlagFollowsBackend`                                                                                                                                                                                                                                                                                                                                               |
| SC-6  | `POST /v1/apply` runs `tofu apply -no-color -auto-approve` (with or without prior plan); 202 + `{run_id,status:"queued"}`                                   | ✓ VERIFIED                                      | `exec.go:runJob` RunKindApply → `apply -no-color -input=false -auto-approve`, with `prior` appended when a fresh artifact exists. `handlers.Apply` shares `submitHandler`. Tests PASS: `TestRunJobApplyInlineWhenNoPriorPlan`, `TestExecApplyUsesPriorPlanFile`, `TestApplyQueuesRunKindApply` (202 + Location), `TestApplyFallsBackWhenPriorPlanFileMissing`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| SC-7  | `GET /v1/runs/{id}` returns status/exit_code/started_at/finished_at + paginated `output_lines` (default 100, max 1000), secret-redacted                     | ✓ VERIFIED                                      | `contract.RunDetail` carries all fields; `ExitCode *int` so a queued run marshals `null`. Caps: `contract.DefaultOutputPageSize = 100`, `MaxOutputPageSize = 1000`, clamped in `get_run.go:106-113` AND again in `runs/output.go:ReadOutput`. Redaction is applied at read time inside `ReadOutput` (`windowCollector.add` → `redactor.line`), so the handler cannot serve unredacted lines. Tests PASS: `TestGetRunSuccess`, `TestGetRunPagination`, `TestGetRunPageSizeClamped`, `TestReadOutputPagination`, `TestReadOutputRedactsAndCounts`, `TestGetRunQueuedRunHasEmptyOutput`                                                                                                                                                                                                                                                                                                           |
| SC-8  | `GET /v1/runs` returns last N (default 20, max 100) ordered `started_at desc`, `?repo=` / `?status=` filters                                                | ✓ VERIFIED                                      | `runs/store.go:List` — `sort.SliceStable` on `StartedAt.After`, filters Repo/Status/Kind/Dir, clamps to `DefaultRunListLimit 20` / `MaxRunListLimit 100`. `list_runs.go` validates `?status=` against the five enum values (400 otherwise) and clamps `?limit=` so the reported `limit` is the applied one. Tests PASS: `TestStoreListOrdersByStartedAtDesc`, `TestStoreListFiltersAndCaps`, `TestListRunsDefaultLimit`, `TestListRunsRepoFilter`, `TestListRunsStatusFilterEveryEnumValue`, `TestListRunsLimitClamped`, `TestListRunsUnknownStatus`                                                                                                                                                                                                                                                                                                                                           |
| SC-9  | Same-repo applies serialized by an in-process per-repo mutex (2nd gets 202 + `queued`, waits); cross-repo parallel; mutex released on success/failure/crash | ✓ VERIFIED (behavioral)                         | `jobq/queue.go` — non-blocking global semaphore (D-06) + blocking per-repo `sync.Mutex` acquired INSIDE `work()`, so the 202 is answered before the wait. Release discipline: `defer q.wg.Done()`, `defer q.releasePending`, `defer recover()` registered before `lock.Lock()`, `defer lock.Unlock()`, `defer func(){ <-q.sem }()`. **Named tests re-run under `-race` for this report:** `TestSameRepoAppliesSerialize` PASS (asserts same-repo peak occupancy == 1 AND that run 2 is observably `queued` while run 1 executes), `TestCrossRepoAppliesRunInParallel` PASS (global peak occupancy == 2), `TestPanickingJobReleasesRepoMutex` PASS, `TestSameRepoWaiterDoesNotStarveOtherRepos` PASS. Also `TestFailedJobReleasesRepoMutex`, `TestSecondSameRepoRunIsQueuedWhileFirstRuns`. Crash recovery = in-process mutex dies with the process (D-05) + boot sweep to `interrupted` (D-02) |
| SC-10 | Redaction covers `^[A-Z0-9]{20}$`, `^[A-Za-z0-9/+=]{40}$`, `-----BEGIN`; a `redaction.audit` record counts redactions                                       | ✓ VERIFIED (broader than spec; one tracked gap) | `runs/redact.go:31,33` are the two literal spec patterns verbatim; `pemHeaderPrefix = "-----BEGIN"` triggers whole-line masking AND a stateful latch that masks the entire PEM body to `-----END` (CR-01). Superset added: `r2HexKeyRe` (32/64 lowercase-hex — Cloudflare R2's real shapes) and `urlUserinfoRe` (`scheme://user:pass@`, WR-02). Audit: `handlers/redaction_audit.go:auditRedactions` is the single emission point, called once per `GET /v1/runs/{id}` from `get_run.go:130`. **Named tests re-run under `-race`:** `TestReadOutputRedactsMultiLinePEM` PASS, `TestReadOutputRedactsPEMBodyOnALaterPage` PASS. Also `TestRedact`, `TestRedactR2AndURLCredentials`, `TestRedactIsLosslessForSecretFreeLines`, `TestGetRunWithRedactionsEmitsAudit`, `TestAuditRedactionsNeverLogsContent`. See "Deviation analysis" for the T-14 gap and the per-page audit semantics           |
| SC-11 | `runs_retention_hours` (default 24) controls rotation; background ticker every retention/4 (default 6h)                                                     | ✓ VERIFIED (behavioral)                         | `config.yaml:46` `runs_retention_hours: "int(1,720)"`, default 24. `runs/retention.go:tickInterval` returns `retention/4` floored at `minTickInterval = 1m`; `StartRetentionTicker` runs `Rotate(retention)` on that cadence; `Rotate` skips `queued`/`running` unconditionally and ages by `FinishedAt ?? StartedAt`. `main.go:308-337` clamps a hand-edited `0` back to 24h (`runs_retention_invalid`), runs one explicit boot `Rotate`, then starts the ticker; `signals.go` stops it inside the SIGTERM drain. **Named tests re-run under `-race`:** `TestTickIntervalCadenceAndFloor` PASS, `TestSweepInterruptedTransitionsActiveRuns` PASS. Also `TestRotateDeletesOldFinishedRuns`, `TestRotateSkipsActiveRuns`, `TestRotateUsesStartedAtWhenFinishedAtNil`, `TestStartRetentionTickerStops(OnContextCancel)`                                                                          |

### Observable Truths — plan `must_haves` not restating an SC

| #   | Truth (source plan)                                                                                                   | Status                  | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| P1  | `max_parallel_jobs` (default 4, 1..32) and `apply_timeout_minutes` (default 60, 5..1440) are operator knobs (17-01)   | ✓ VERIFIED              | `config.yaml:45-46` — `int(1,32)` / `int(5,1440)`; defaults at `config.yaml:27-28` and mirrored in `main.go:113-115` and `jobq/queue.go:41-45`. `TestNewDefaultsAndValidation` clamps out-of-range values                                                                                                                                                                                                                                                                                        |
| P2  | `tofu`, `git`, `ssh` are on PATH in the runtime image; `tofu` is a pinned, checksum-verified release (17-01)          | ✓ VERIFIED              | `Dockerfile:20,58-64` — `ARG TOFU_VERSION=1.10.6`, `grep " tofu_${TOFU_VERSION}_linux_amd64.zip$" SHA256SUMS \| sha256sum -c -`, then `COPY --from=tofu /usr/local/bin/tofu /usr/bin/tofu`; `RUN apk add --no-cache git openssh-client`. 17-07 ran the mandated local `docker build` (checksum verified in-stage, image served `/v1/version`); no later commit touched the Dockerfile                                                                                                            |
| P3  | Every Phase 17 failure carries a stable `error_code` from one documented taxonomy (17-02)                             | ✓ VERIFIED              | `contract/types.go:168-215` — 8 `git_*`, 6 `run_*`, 4 `apply_*`/`plan_*`, plus the preserved `unauthorized`. Every code has a `statusForCode` row (`TestStatusForCodeTable`, `TestStatusForCodeNeverSucceeds`) and a DOCS.md row (`DOCS.md:435-455`)                                                                                                                                                                                                                                             |
| P4  | A run orphaned by a restart is representable as `interrupted`, distinct from a tofu failure (17-02/17-04)             | ✓ VERIFIED              | `contract.RunStatusInterrupted`; `SweepInterrupted` sets it with a `finished_at` and deliberately leaves `error_code` empty; `?status=interrupted` is a first-class filter (`TestListRunsStatusFilterInterrupted`)                                                                                                                                                                                                                                                                               |
| P5  | Run ids never collide and are safe as both a directory name and a URL path segment (17-02)                            | ✓ VERIFIED              | `runs/ids.go` — 10 bytes `crypto/rand` → base32 no-padding, alphabet `[A-Z2-7]` only, so `..`/`/`/`+`/`=` are inexpressible. `TestNewRunIDLengthAndCharset`, `TestNewRunIDUniqueness`, `TestIsValidRunIDRejectsMalformed`                                                                                                                                                                                                                                                                        |
| P6  | A caller cannot escape the repo working tree via `dir` (17-02)                                                        | ✓ VERIFIED              | `runs/dir.go:ValidateDir` rejects NUL, leading `/`, any `..` segment before AND after `filepath.Clean`, and absolute results; `""`/`"."` legally mean the repo root (D-23). Enforced at the single entry point `queue.go:244`. `TestValidateDirAccepts/Rejects`, `TestSubmitInvalidDir`, `TestPlanInvalidDir`                                                                                                                                                                                    |
| P7  | A repo whose clone never succeeded reports `git_clone_missing`, not an obscure tofu error (17-03)                     | ✓ VERIFIED              | `manager.go:EnsureCloned` returns the typed error with a hint naming the pull endpoint; gated in `Submit` step 3 and in `Pull` before any git command. `TestManagerEnsureClonedReportsCloneMissing`, `TestSubmitCloneMissing`, `TestReposPullCloneMissingIs404`                                                                                                                                                                                                                                  |
| P8  | Git authenticates only with the repo's own deploy key and verifies the host; never an agent key or a prompt (17-03)   | ✓ VERIFIED (code level) | `sshEnv` sets `IdentitiesOnly=yes` + `StrictHostKeyChecking=yes` + `BatchMode=yes`; `baseEnv` is an allowlist (`PATH HOME TMPDIR LANG LC_ALL TZ`) so `SSH_AUTH_SOCK` and `SUPERVISOR_TOKEN` never reach the child. `TestManagerSSHEnvCarriesKeyAndKnownHosts`, `TestGitChildEnvironmentIsAllowlisted`. Live-remote proof deferred to Phase 19 (T-09a)                                                                                                                                            |
| P9  | Every run leaves a durable record that survives a restart, with no torn `meta.json` (17-04)                           | ✓ VERIFIED              | `runs/store.go` — `writeMeta` = tempfile in the same dir + `Sync` + `Chmod 0600` + atomic `Rename`; `Update` serializes the read-modify-write under `syscall.Flock(LOCK_EX)` on a DEDICATED `.meta.lock` (so the rename cannot orphan the lock). `TestStoreUpdateConcurrent`, `TestStoreUpdateNoTornReadUnderConcurrentLoad`, `TestStoreCreateSetsModes` — all green under `-race`                                                                                                               |
| P10 | Raw tofu output is preserved verbatim on disk while the API returns only a bounded page (17-04)                       | ✓ VERIFIED              | `output.go:WriteLine` has no length bound anywhere; `ReadOutput` falls back from `bufio.Scanner` to `bufio.Reader.ReadString` on `ErrTooLong` so nothing is lost to the reader's own ceiling either. `TestWriteLineNoTruncation`, `TestReadOutputHandlesLineBeyondScannerCeiling`, `TestWriteLineConcurrentStreams`                                                                                                                                                                              |
| P11 | Capacity saturation is refused with a distinct error, never queued unboundedly (17-05/17-06)                          | ✓ VERIFIED              | `jobq.ErrCapacityExhausted` from the non-blocking `select` on `q.sem` plus the per-repo `reservePending` bound; `plan.go:129-137` maps it to 503 + `Retry-After: 30` + `apply_capacity_exhausted`, and no run directory is created (rejections precede `store.Create`). `TestSubmitCapacityExhausted`, `TestCapacityRefusesThirdSubmission`, `TestPlanCapacityExhausted`, `TestApplyCapacityExhausted` (asserts empty `Location`), `TestSubmitLeavesNoStateWhenCreateFails`                      |
| P12 | A timed-out run is SIGTERMed then SIGKILLed and recorded `failed` with a timeout code — never stuck `running` (17-05) | ✓ VERIFIED (behavioral) | `exec.go:DefaultExec` sets `cmd.Cancel = SIGTERM` and `cmd.WaitDelay = killGrace (10s)`; `queue.go:finish` maps `TimedOut` to `RunStatusFailed` + `apply_timeout` (or `plan_timeout` for a plan). `TestDefaultExecTimeoutSendsSIGTERMThenSIGKILL`, `TestDefaultExecGracefulExitNotKilled`, `TestTimeoutMarksRunFailedWithTimeoutCode`                                                                                                                                                            |
| P13 | An apply after a successful plan for the same (repo, dir) applies that artifact; otherwise inline (17-05)             | ✓ VERIFIED              | `priorPlanFile` filters on repo+status+kind+dir BEFORE the limit and gates on `Meta.HeadSHA == git.Head()`; a stale or unknown head degrades to an inline apply, and a consumed artifact is deleted and cleared from the plan run's meta. `TestExecApplyUsesPriorPlanFile`, `TestApplyIgnoresPlanBuiltAgainstAnotherCommit`, `TestApplyIgnoresPlanWithNoRecordedHead`, `TestApplyConsumesPlanArtifact`, `TestPriorPlanIgnoresOtherDirsAndKinds`, `TestListFilterKindAndDirApplyBeforeTheLimit`   |
| P14 | Output lands in the run log while the job is still running, so progress is pollable (17-05)                           | ✓ VERIFIED              | `runJob` passes per-line `Stdout`/`Stderr` callbacks into `ExecSpec` that call `OutputWriter.WriteLine` during execution; a write failure is logged once and never aborts the apply. `TestRunJobStreamsOutputToRunLog`, `TestDefaultExecCapturesBothStreams`                                                                                                                                                                                                                                     |
| P15 | No raw stderr, stack trace, or filesystem path reaches a 4xx/5xx body (17-06/17-08)                                   | ✓ VERIFIED              | Single choke point `write_error.go:writeError/writeGitError`; unclassified errors get a fixed 500 body and the detail goes to the log. `TestWriteGitErrorOpaqueFallback`, `TestGetRunLoadFailureDoesNotLeak`, `TestGetRunReadOutputFailureDoesNotLeak`, `TestListRunsStoreFailureDoesNotLeak`, `TestSubmitOpaqueErrorDoesNotLeak`                                                                                                                                                                |
| P16 | Startup wires all four Options, logs `repos_loaded`, clones, sweeps, starts retention, and drains on SIGTERM (17-07)  | ✓ VERIFIED              | `main.go` — options parse is FATAL on malformed JSON (WR-07), `repos_loaded` carries count + names + `key_issues` + the three ints, then `CloneAll` → `SweepInterrupted` → boot `Rotate` → `StartRetentionTicker` → `jobq.New` → `NewRouter(...)`, all before `ListenAndServe`. `signals.go` splits the 30s deadline into `httpDrainBudget 25s` + `queueDrainBudget 5s` and calls `queue.Drain`. `TestDrainWaitsForInFlight`, `TestDrainRespectsContextDeadline`, `TestDrainLeavesNoRunningRuns` |
| P17 | An unknown or malformed run id returns a typed 404, never a filesystem error or panic (17-08)                         | ✓ VERIFIED              | `get_run.go:71` calls `runs.IsValidRunID` BEFORE any filesystem access (`run_unknown_id`); `store.Dir` re-guards as a second layer; `Load` collapses missing/invalid/corrupt into `ErrRunNotFound` → `run_not_found`. `TestGetRunMalformedIDIsRunUnknownID`, `TestGetRunNotFound`, `TestStoreLoadUnknownIDReturnsErrRunNotFound`                                                                                                                                                                 |
| P18 | All five endpoints sit behind the bearer gate and the Phase 16 surface is unchanged (17-08)                           | ✓ VERIFIED              | `router.go:78-88` — all five mounts are inside `r.Route("/v1", …)` with `r.Use(auth.RequireBearer(store))`; `/` and `/healthz` stay public by design. `TestRouterPhase17EndpointsRequireBearer`, `TestRouterPhase16SurfaceUnauthenticated`, `TestRouterVersionStillMounted`, `TestRouterAuthRotateStillMounted`, `TestRouterReadEndpointsReachable`, `TestRouterGetRunServesAStoredRun`                                                                                                          |
| P19 | The three version files plus `RUNNER_VERSION` are in sync (17-07)                                                     | ✓ VERIFIED              | `config.yaml: 0.2.1-0` / `build.yaml: VERSION 0.2.1` + `RUNNER_VERSION 0.2.1` / `README.md: version-v0.2.1`. `make validate-versions` PASSES. The 17-07 plan's literal `contains: version-v0\.2\.0` is superseded by the deliberate review-fix bump to 0.2.1 (`455920f`)                                                                                                                                                                                                                         |
| P20 | DOCS.md documents every endpoint, Option, and error_code; README reflects Phase 17 (17-07)                            | ✓ VERIFIED              | `DOCS.md` — endpoint table (L200-214) + per-endpoint sections with curl examples (L275-421) + a 19-row `error_code` table (L435-455) + the four Options with default/range/semantics (L92-168) + an output-redaction section that documents the PEM latch, the hex superset, and the non-zero-only audit record (L462-487) + a startup/shutdown record table (L489-514)                                                                                                                          |

**Score:** 23/23 truths verified (0 present, behavior-unverified)

### Deviation analysis (the two SCs the phase deliberately did not implement literally)

**SC-3 / D-10 vs D-12.** The two locked decisions contradict each other: D-10 says a `ref`-pinned repo re-lands on its
ref for both the startup clone AND `POST /v1/repos/{name}/pull`; D-12 says a pull against a non-empty `ref` is refused
outright with `git_ref_pull_incompatible`. Both cannot hold for the same request. The implementation (`manager.go:Pull`,
reconciliation note in the doc comment) resolves in favor of D-10 and keeps D-12 as an explicit-conflict guard: the
refusal fires only when a caller passes `ff_only: true` against a pinned repo.

I judge this **conforming, not a deviation from the contract**, on three grounds:

1. SC-3 and GIT-03 are worded identically — "runs `git pull --ff-only` **(or the configured ref)**". A pinned repo
   landing on its ref is the second half of that sentence. A blanket D-12 refusal would make the parenthetical
   unreachable.
2. Under a blanket refusal a pinned repo could never be refreshed at all, which contradicts GIT-02's division of labor
   ("existing directories are left untouched — the caller triggers `POST /v1/repos/{name}/pull` to refresh").
3. The reasoning is recorded where a maintainer will find it: the `Pull` doc comment names both decisions, states which
   won, and gives the one-line change to invert it; `reposPullRequest.FFOnly`'s comment explains why the zero value is
   load-bearing; `DOCS.md:284` documents the observable behavior. `TestManagerPullFFOnlyOnPinnedRepoIsRefused` and
   `TestReposPullRefPullIncompatibleIs400` pin the surviving guard.

**SC-10 redaction set.** All three specified patterns are present verbatim and behaviorally proven. Two changes go
beyond the wording, both in the safe direction and both documented in code and DOCS.md: the `-----BEGIN` rule is now a
stateful cross-line latch (CR-01 — a stateless per-line redactor masked the header and served the whole base64 key body,
so the spec's rule did not previously mean what it said), and the pattern set gained Cloudflare R2's real 32/64-char hex
shapes plus URL userinfo (WR-02 — the DEFAULT state backend's own credentials matched neither AWS pattern). Accepted
cost, stated in `redact.go:41-48`: a bare 32/40/64-char hex string in tofu output (a checksum, a git SHA) is masked too;
the raw bytes remain under `/data`.

Two nuances worth an operator's attention, both already documented rather than hidden:

- **Tracked gap (T-14, non-blocking).** The set still has no rule for a 43-character `base64url` token — the runner's
  OWN bearer-token shape — or for dot-separated JWTs, which is what an HA long-lived access token is. Confirmed by
  inspection: `awsSecretKeyRe` is `^[A-Za-z0-9/+=]{40}$`, so neither the length (43) nor the `-`/`_` base64url alphabet
  matches. `17-SECURITY.md` records this as probe-verified-unredacted, medium severity, open below the blocking
  threshold. It is outside SC-10's stated guarantee, so it is not scored as a gap here — but it is the single most
  valuable follow-up in the redaction area.
- **Audit granularity.** SC-10 says the record "counts redactions per-run"; the implementation counts them per served
  page of `GET /v1/runs/{id}` and emits nothing on a zero-redaction page. Given D-08 (redaction happens at READ time,
  the disk log stays raw) there is no single per-run moment at which a total could be computed, so per-page is the only
  coherent form — and `redaction_audit.go`'s call contract plus `DOCS.md:482-487` state the semantics explicitly,
  including that "no record means nothing was withheld from that page".

### Deferred Items

Items not yet met in this phase but explicitly addressed by a later milestone phase — not actionable gaps.

| #   | Item                                                                             | Addressed In | Evidence                                                                                                                                           |
| --- | -------------------------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | GIT-03 SSH pinning / deploy-key-only auth observed against a live remote (T-09a) | Phase 19     | Phase 19 goal: "Every v1.4 requirement is empirically verified against a live HA host"; assignment recorded in 17-03-SUMMARY.md and 17-SECURITY.md |
| 2   | End-to-end tofu plan + apply + drift + idempotency cycle                         | Phase 19     | Phase 19 SC-2 (verbatim: apply succeeds, re-apply shows "No changes", in-place modification triggers a diff, …)                                    |
| 3   | State-backend credentials reaching the tofu child (`tofu init` against r2/s3)    | Phase 19     | Phase 19 SC-3 (three-backend matrix against a real R2 bucket); recorded in deferred-items.md and in `exec.go:tofuEnv()`                            |
| 4   | Add-on installs on a real HA host; `/v1/version` 200, `/healthz` 200 in 2s       | Phase 19     | Phase 19 SC-1 (verbatim)                                                                                                                           |
| 5   | Privilege boundary for the tofu child (accepted risk R-01)                       | own plan     | 17-SECURITY.md R-01, accepted by akentner 2026-09-08: "Mitigating properly requires a privilege boundary … belongs in its own plan"                |

### Required Artifacts

| Artifact                                              | Expected                                       | Status     | Details                                                                                     |
| ----------------------------------------------------- | ---------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------- |
| `iac-runner/config.yaml`                              | `repos` + 3 int options with HA schema entries | ✓ VERIFIED | contains `repos:`, `int(1,32)`, `int(5,1440)`, `int(1,720)`                                 |
| `iac-runner/Dockerfile`                               | Pinned checksum-verified tofu + git/ssh        | ✓ VERIFIED | contains `TOFU_VERSION`, `sha256sum -c -`, `apk add … git openssh-client`                   |
| `iac-runner/internal/contract/types.go`               | Run enums/bodies + full error_code set         | ✓ VERIFIED | contains `ErrCodeGitCloneMissing`; 19 codes, all with a status row                          |
| `iac-runner/internal/runs/ids.go`                     | base32 crypto/rand id + guard                  | ✓ VERIFIED | contains `base32`, `IsValidRunID`                                                           |
| `iac-runner/internal/runs/dir.go`                     | `ValidateDir` per D-21/D-22/D-23               | ✓ VERIFIED | contains `ErrInvalidDir`, `InvalidDirMessage`                                               |
| `iac-runner/internal/git/repo.go`                     | `RepoConfig` + `EffectiveBranch` + `Validate`  | ✓ VERIFIED | contains `EffectiveBranch`; three hardening regexes                                         |
| `iac-runner/internal/git/errors.go`                   | `git.Error` + `Classify`                       | ✓ VERIFIED | contains `Classify`; 7 ordered rules, stderr never stored                                   |
| `iac-runner/internal/git/manager.go`                  | Clone/CloneAll/Pull + GIT_SSH_COMMAND          | ✓ VERIFIED | contains `GIT_SSH_COMMAND`, `UserKnownHostsFile`, `WorkTree`                                |
| `iac-runner/internal/runs/store.go`                   | Create/Load/Update(flock+atomic)/List/Dir      | ✓ VERIFIED | contains `Flock`; dedicated `.meta.lock`                                                    |
| `iac-runner/internal/runs/output.go`                  | JSONL writer + paginated redacted read         | ✓ VERIFIED | contains `OutputLine`, `contract.DefaultOutputPageSize`, `Redact` via `redactor`            |
| `iac-runner/internal/runs/redact.go`                  | SEC-03 patterns + per-call count               | ✓ VERIFIED | contains `-----BEGIN`; stateful latch + 4 pattern families                                  |
| `iac-runner/internal/runs/retention.go`               | SweepInterrupted + Rotate + ticker             | ✓ VERIFIED | contains `SweepInterrupted`, `RunStatusInterrupted`, `tickInterval`                         |
| `iac-runner/internal/jobq/queue.go`                   | Submit + semaphore + per-repo mutex + Drain    | ✓ VERIFIED | contains `ErrCapacityExhausted`, `RunStatusRunning`, `EnsureCloned`                         |
| `iac-runner/internal/jobq/exec.go`                    | tofu command lines + kill-chain + capture      | ✓ VERIFIED | contains `WaitDelay`, `WriteLine`, `UseLockfile`                                            |
| `iac-runner/internal/httpapi/handlers/write_error.go` | `writeError` + `writeGitError`                 | ✓ VERIFIED | contains `writeGitError`; complete `statusForCode` table                                    |
| `iac-runner/internal/httpapi/handlers/repos_pull.go`  | ReposPull handler                              | ✓ VERIFIED | contains `ReposPull`, `git.Error` mapping                                                   |
| `iac-runner/internal/httpapi/handlers/plan.go`        | Plan + Apply, 202 + Location, 503 capacity     | ✓ VERIFIED | contains `func Apply`, `jobq.ErrCapacityExhausted`                                          |
| `iac-runner/internal/httpapi/handlers/get_run.go`     | GetRun + redaction.audit                       | ✓ VERIFIED | contains `GetRun`, `store.ReadOutput`, `Redactions`, `writeError`                           |
| `iac-runner/internal/httpapi/handlers/list_runs.go`   | ListRuns with RUN-05 caps/filters              | ✓ VERIFIED | contains `ListRuns`                                                                         |
| `iac-runner/internal/httpapi/router.go`               | All five mounts behind RequireBearer           | ✓ VERIFIED | contains `r.Post("/repos/{name}/pull"`, `NewRouter`                                         |
| `iac-runner/cmd/runner/main.go`                       | Full Phase 17 startup wiring                   | ✓ VERIFIED | contains `repos_loaded`, `git.NewManager`, `runs.NewStore`, `jobq.New`, `httpapi.NewRouter` |
| `iac-runner/cmd/runner/signals.go`                    | SIGTERM drain extended with `queue.Drain`      | ✓ VERIFIED | contains `queue.Drain`; 25s/5s budget split                                                 |
| `iac-runner/DOCS.md`                                  | Phase 17 operator reference                    | ✓ VERIFIED | contains the redaction section, endpoint table, 19-row error table                          |
| `iac-runner/README.md`                                | Feature list + bumped badge                    | ✓ VERIFIED | `version-v0.2.1` (supersedes the plan's literal `v0.2.0`)                                   |
| _13 `*_test.go` files_                                | Per-plan test artifacts                        | ✓ VERIFIED | All present; every named test pattern from the plans exists and passes                      |

No artifact is a stub, orphan, or hollow: every one of the 23 non-test implementation files is imported and exercised by
at least one other package or by `main.go`, and the compile-time link is proven by `go build ./...` + `go vet ./...`
exiting 0.

### Key Link Verification

| From                                   | To                                         | Via                                                                                                             | Status  |
| -------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | ------- |
| `config.yaml`                          | `cmd/runner/main.go`                       | `options.Repos []git.RepoConfig` + 3 ints unmarshalled from `/data/options.json`                                | ✓ WIRED |
| `Dockerfile`                           | `handlers/healthz.go`                      | `COPY --from=tofu … /usr/bin/tofu` satisfies `exec.LookPath("tofu")`                                            | ✓ WIRED |
| `runs/dir.go`                          | `contract/types.go`                        | `ValidateDir` failure → `ErrCodeRunInvalidDir` (400) at `queue.go:246`                                          | ✓ WIRED |
| `runs/ids.go`                          | `/data/runs/{run_id}`                      | `NewRunID()` output used verbatim as the directory name via `store.Dir`                                         | ✓ WIRED |
| `git/manager.go`                       | `/data/keys/<name>.key` + `known_hosts`    | `GIT_SSH_COMMAND=ssh -i … -o UserKnownHostsFile=… -o BatchMode=yes`                                             | ✓ WIRED |
| `git/errors.go`                        | `contract/types.go`                        | every `classifyRule.code` is a `contract.ErrCodeGit*` constant                                                  | ✓ WIRED |
| `git/manager.go`                       | `/data/repos/<name>`                       | `WorkTree()` joins `reposDir` with the schema-validated name; `IsCloned` probes it                              | ✓ WIRED |
| `runs/output.go`                       | `runs/redact.go`                           | `windowCollector.add` → `redactor.line` on every in-window line; `observe` keeps the latch across skipped lines | ✓ WIRED |
| `runs/output.go`                       | `contract/types.go`                        | `contract.DefaultOutputPageSize` / `MaxOutputPageSize` clamps                                                   | ✓ WIRED |
| `runs/retention.go`                    | `runs/store.go`                            | `SweepInterrupted` → `Update` → `RunStatusInterrupted`                                                          | ✓ WIRED |
| `jobq/queue.go`                        | `runs/store.go`                            | `Create(queued)` → `Update(running)` → `finish(succeeded\|failed)` with ExitCode + FinishedAt                   | ✓ WIRED |
| `jobq/exec.go`                         | `runs/output.go`                           | per-line `Stdout`/`Stderr` callbacks → `OutputWriter.WriteLine` during execution                                | ✓ WIRED |
| `jobq/queue.go`                        | `git/manager.go`                           | `EnsureCloned` gate + `WorkTree` joined with the validated `dir`                                                | ✓ WIRED |
| `jobq/exec.go`                         | `statebackend/backend.go`                  | `backend.UseLockfile()` gates `-backend-config=use_lockfile=true`                                               | ✓ WIRED |
| `handlers/repos_pull.go`               | `git/manager.go`                           | `p.Pull(ctx, name, body.FFOnly)`; `errors.As(&git.Error)` → `writeGitError`                                     | ✓ WIRED |
| `handlers/plan.go`                     | `jobq/queue.go`                            | `q.Submit(jobq.Request{…})`; `errors.Is(jobq.ErrCapacityExhausted)` → 503 + Retry-After                         | ✓ WIRED |
| `handlers/get_run.go`                  | `runs/store.go`                            | `rd.Load(id)` + `rd.ReadOutput(id, page, pageSize)`                                                             | ✓ WIRED |
| `handlers/get_run.go`                  | `handlers/redaction_audit.go`              | one `auditRedactions(ctx, id, outputPage)` call, after read, before body                                        | ✓ WIRED |
| `handlers/get_run.go` / `list_runs.go` | `handlers/write_error.go`                  | both reuse `writeError` / `statusForCode` — one definition per package                                          | ✓ WIRED |
| `httpapi/router.go`                    | `cmd/runner/main.go`                       | `httpapi.NewRouter(runnerVersion, store, keysValidator, gitMgr, runStore, q)`                                   | ✓ WIRED |
| `cmd/runner/signals.go`                | `jobq/queue.go`                            | `queue.Drain(queueCtx)` inside the SIGTERM window, 5s budget                                                    | ✓ WIRED |
| `make update-version`                  | `config.yaml` / `build.yaml` / `README.md` | `0.2.1-0` / `0.2.1` / `v0.2.1`; `make validate-versions` passes                                                 | ✓ WIRED |

### Data-Flow Trace (Level 4)

| Artifact                 | Data Variable               | Source                                                                             | Produces Real Data | Status    |
| ------------------------ | --------------------------- | ---------------------------------------------------------------------------------- | ------------------ | --------- |
| `handlers/get_run.go`    | `RunDetail.OutputLines`     | `store.ReadOutput` → `os.Open(/data/runs/{id}/output.log)` → JSONL decode → redact | Yes                | ✓ FLOWING |
| `handlers/get_run.go`    | `RunDetail.Status/ExitCode` | `store.Load` → `os.ReadFile(meta.json)` written by `jobq.finish`                   | Yes                | ✓ FLOWING |
| `handlers/list_runs.go`  | `RunListResponse.Runs`      | `store.List` → `os.ReadDir(/data/runs)` + per-dir `Load`                           | Yes                | ✓ FLOWING |
| `handlers/plan.go`       | `RunAccepted.RunID`         | `q.Submit` → `runs.NewRunID()` (crypto/rand) + `store.Create`                      | Yes                | ✓ FLOWING |
| `handlers/repos_pull.go` | `reposPullResponse.Head`    | `Pull` → `resolveHead` → real `git rev-parse HEAD` in the working tree             | Yes                | ✓ FLOWING |
| `jobq/exec.go`           | `ExecResult.ExitCode`       | `cmd.ProcessState.ExitCode()` of the real tofu process                             | Yes                | ✓ FLOWING |
| `runs/store.go`          | `Meta.HeadSHA`              | `recordPlanHead` → `git.Head()` → real `git rev-parse`                             | Yes                | ✓ FLOWING |

No hardcoded literal, static return, or in-memory mock terminates any of these chains. `RunAccepted.Status` is the one
constant in a response body (`RunStatusQueued`) and that is correct by contract: SC-9 requires the 202 to say `queued`
regardless of what happens next, and the real status is immediately readable from `meta.json`.

### Behavioral Spot-Checks

| Behavior                                                    | Command                                                                         | Result                                                                          | Status                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------- |
| The whole module compiles and passes vet                    | `go build ./... && go vet ./...` (golang:1.25-alpine, host mod cache)           | exit 0 both                                                                     | ✓ PASS                                 |
| Full suite is green under the race detector                 | `go test -race -count=1 ./...` (one full run, `gcc musl-dev` + `tofu` stub)     | `ok` for all 11 packages with test files, 0 FAIL                                | ✓ PASS                                 |
| SC-9 same-repo serialization is real, not just present      | `go test -race -run TestSameRepoAppliesSerialize ./internal/jobq/`              | PASS — same-repo peak occupancy 1; run 2 observed `queued` while run 1 executes | ✓ PASS                                 |
| SC-9 cross-repo parallelism is real                         | `go test -race -run TestCrossRepoAppliesRunInParallel ./internal/jobq/`         | PASS — global peak occupancy 2                                                  | ✓ PASS                                 |
| SC-9 slot/mutex release survives a panic                    | `go test -race -run TestPanickingJobReleasesRepoMutex ./internal/jobq/`         | PASS                                                                            | ✓ PASS                                 |
| WR-08 fix: a same-repo waiter no longer starves other repos | `go test -race -run TestSameRepoWaiterDoesNotStarveOtherRepos ./internal/jobq/` | PASS                                                                            | ✓ PASS                                 |
| SC-10 PEM latch masks the key BODY, not just the header     | `go test -race -run TestReadOutputRedactsMultiLinePEM ./internal/runs/`         | PASS                                                                            | ✓ PASS                                 |
| SC-10 latch survives pagination starting mid-key            | `go test -race -run TestReadOutputRedactsPEMBodyOnALaterPage ./internal/runs/`  | PASS                                                                            | ✓ PASS                                 |
| SC-11 ticker cadence is retention/4 with a floor            | `go test -race -run TestTickIntervalCadenceAndFloor ./internal/runs/`           | PASS                                                                            | ✓ PASS                                 |
| D-02 boot sweep transitions running/queued → interrupted    | `go test -race -run TestSweepInterruptedTransitionsActiveRuns ./internal/runs/` | PASS                                                                            | ✓ PASS                                 |
| 3-file version sync                                         | `make validate-versions`                                                        | "Version validation passed for all add-ons!"                                    | ✓ PASS                                 |
| Add-on structure                                            | `make validate-addons`                                                          | `iac-runner/ validation passed` (all 6 add-ons)                                 | ✓ PASS                                 |
| Full lint gate                                              | `make lint` (`pre-commit run --all-files`)                                      | All 21 hooks Passed — incl. hadolint, markdownlint, prettier                    | ✓ PASS                                 |
| Live plan/apply against a real tofu + real remote           | —                                                                               | Not runnable without an HA host and an SSH remote                               | ? SKIP → Phase 19 (deferred items 1-4) |

### Probe Execution

| Probe | Command | Result | Status                                                                                                                                                                                                               |
| ----- | ------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| —     | —       | —      | N/A — no `scripts/*/tests/probe-*.sh` exists in this repository, and no Phase 17 plan or success criterion declares a probe. The Go test suite is this phase's runnable verification surface and was executed above. |

### Requirements Coverage

All 13 declared IDs are accounted for. Every ID is also `[x]`-marked in `.planning/REQUIREMENTS.md` (lines 285-360) —
the shared-ID gate that the prompt flagged has since resolved now that all 8 plans carry summaries.

| Requirement | Source Plans               | Description                                          | Status      | Evidence                                                                                                                                                   |
| ----------- | -------------------------- | ---------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GIT-01      | 17-01, 17-07               | `repos` options schema: name/url/branch/ref          | ✓ SATISFIED | SC-1 + P1. `config.yaml:39-44` schema; `git/repo.go` Go re-validation; `main.go` unmarshal + `repos_loaded`                                                |
| GIT-02      | 17-03, 17-07               | Startup clone if absent; existing untouched          | ✓ SATISFIED | SC-2. `cloneOutcome` skip-when-`IsCloned`; `CloneAll` in `main.go:261-279`, non-fatal                                                                      |
| GIT-03      | 17-03, 17-06, 17-07        | SSH-keyed `pull --ff-only` (or ref); 409/403 typed   | ✓ SATISFIED | SC-3 + P8. `Pull` + `sshEnv` + `statusForCode`. **Note:** D-12 narrowed to the `ff_only` conflict — reasoned above. Live-remote proof deferred to Phase 19 |
| GIT-04      | 17-02, 17-03, 17-07        | Typed `git_*` responses with a hint, no stack traces | ✓ SATISFIED | SC-4 + P3. 8 `git_*` codes; `git.Error` stores no stderr; `TestManagerPullErrorBodyHasNoStderrDump`                                                        |
| RUN-01      | 17-07, 17-08               | `GET /v1/version` returns JSON                       | ✓ SATISFIED | Delivered in Phase 16 and PRESERVED here: `router.go:81` mount inside the bearer gate; `TestRouterVersionStillMounted`, `TestVersionAllFieldsPresent`      |
| RUN-02      | 17-05, 17-06, 17-07        | `POST /v1/plan` → background job, 202 + Location     | ✓ SATISFIED | SC-5. `submitHandler` + `runJob` plan branch; `TestPlanQueuesRunKindPlan` asserts the Location header                                                      |
| RUN-03      | 17-05, 17-06, 17-07        | `POST /v1/apply` → background job, 202               | ✓ SATISFIED | SC-6 + P13. `runJob` apply branch with the D-17/D-18 artifact lifecycle                                                                                    |
| RUN-04      | 17-02, 17-04, 17-07, 17-08 | `GET /v1/runs/{id}` full body, paginated + redacted  | ✓ SATISFIED | SC-7 + P17. `contract.RunDetail`; read-time redaction inside `ReadOutput`                                                                                  |
| RUN-05      | 17-07, 17-08               | `GET /v1/runs` last N, ordered desc, filters         | ✓ SATISFIED | SC-8. `store.List` sort + filters + caps; `list_runs.go` enum validation                                                                                   |
| RUN-06      | 17-05, 17-07               | Same-repo applies serialized by a per-repo mutex     | ✓ SATISFIED | SC-9. Behaviorally proven under `-race` by four named tests re-run for this report                                                                         |
| SEC-03      | 17-04, 17-07               | Output redaction + `redaction.audit` count           | ✓ SATISFIED | SC-10. Three specified patterns present + PEM latch + hex/URL superset; single audit emission point. T-14 gap tracked, non-blocking                        |
| OBS-02      | 17-04, 17-07               | Line-by-line capture to `output.log` (JSONL)         | ✓ SATISFIED | P10 + P14. `OutputWriter.WriteLine` JSONL `{ts,stream,line}`, mutex-serialized across both streams; no truncation                                          |
| OBS-03      | 17-04, 17-07               | `page` / `page_size` pagination on run output        | ✓ SATISFIED | SC-7. `parsePositiveInt` + double clamping + overflow guards in both handler and store                                                                     |

**Orphaned requirements:** none. `REQUIREMENTS.md:368` maps exactly these 13 IDs to Phase 17, and every one appears in
at least one plan's `requirements` field.

**Documentation nit (not a gap):** the v1.4 per-requirement traceability table (`REQUIREMENTS.md:372-408`) carries only
`ID → Phase` and no evidence column, unlike the v1.3 table at line 569+ which cites plan + verification method per ID.
Filling it for the v1.4 IDs would make this phase's evidence discoverable from the requirements document.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| —    | —    | —       | —        | Clean  |

- **Debt-marker gate: PASS.** `grep -rnE 'TBD\|FIXME\|XXX' iac-runner/` returns zero hits. No unreferenced debt marker
  exists anywhere in the add-on.
- **`TODO` / `HACK`: zero hits** in code.
- **`placeholder` hits are all benign:** `internal/git/errors.go`'s `namePlaceholder` is a legitimate identifier for the
  hint-template substitution, and the remaining five are Phase 16 comments about the `GET /` root handler — pre-existing
  and out of this phase's scope.
- **Empty-implementation patterns:** the `return null` / `= []` / `=> {}` scans surface only justified cases —
  `runDetail` substitutes `[]string{}` for a nil slice so a queued run marshals `output_lines: []` not `null`;
  `repoKeyIssues` returns `[]string{}` for zero repos; `resolveHead` returns `""` as a documented actionable value
  ("freshness unknown" gets the same safe treatment as "stale"). None flows to a rendered value as fake data.

### Human Verification Required

Three items, all originating from `17-REVIEW-FIX.md` where the executor itself marked the fix
`requires human verification`. Each already has passing automated coverage under `-race`; what is missing is
confirmation against real process timing and a real `/data` volume. **None of them is an unresolved question about
whether the code is correct — they are confirmation passes on changes whose blast radius is larger than their test
harness.**

#### 1. Output capture and the timeout kill-chain against a real tofu

**Test:** Run a real `tofu plan` (or any long-running, chatty command) through `POST /v1/plan` on the built image and
compare the tail of `GET /v1/runs/{id}?page=<last>` against `cat /data/runs/{id}/output.log | wc -l`. Then trigger the
timeout path with `apply_timeout_minutes: 5` against a command that ignores SIGTERM. **Expected:** No output lines are
lost at the end of the run; the run reaches `failed` with `error_code: apply_timeout`; no `jobq.output_join_timeout`
WARN on the normal path; no orphaned tofu process survives. **Why human:** WR-01 replaced `cmd.StdoutPipe()` with
runner-owned `os.Pipe` files and moved the scanner join to AFTER `cmd.Wait()`. Four `DefaultExec` tests exercise this
with `sh`, but a real tofu with provider subprocesses that can inherit the write end is precisely the case the fix
exists for, and no test reproduces it.

#### 2. Boot sweep and unparseable-directory rotation on a real `/data`

**Test:** On a `/data` volume that already holds run directories, restart the add-on with (a) a run left at `running`,
(b) a run left at `queued`, (c) a directory with a valid run-id name, no readable `meta.json`, and an mtime older than
`runs_retention_hours`. Then read the boot log and `GET /v1/runs`. **Expected:** (a) and (b) both report `interrupted`
with a `finished_at` and no `error_code`; `runs_swept_interrupted` logs count 2; (c) is deleted and logged as
`runs.rotated_unparseable`; no run genuinely queued/running in THIS container is ever deleted. **Why human:** WR-06
changed a tested boot-sweep contract — `SweepInterrupted` now also sweeps `queued`, and `Rotate` ages an unparseable
directory by its own mtime. The branch is destructive and runs on first boot after upgrade; a false positive deletes
operator run history irreversibly.

#### 3. Admission-gate reordering under real timing

**Test:** With `max_parallel_jobs: 4`, submit 4 applies against repo A (three wait on A's mutex) and then one plan
against repo B. Repeat with all 5 against repo A. **Expected:** the repo-B submission returns 202, not 503; the 5th
repo-A submission returns 503 with `Retry-After: 30`; every run reaches a terminal status and no repo stays wedged.
**Why human:** WR-08 reordered the gates so `work()` hands the global slot back BEFORE waiting on the repo mutex.
`TestSameRepoWaiterDoesNotStarveOtherRepos` plus the serialization suite prove it under `-race` against an injected
exec, so this is the lowest-risk of the three.

### Gaps Summary

**No gaps.** All 11 ROADMAP Success Criteria and all 12 additional plan `must_haves` are verified against the codebase,
and all 13 requirement IDs are genuinely satisfied by shipped code — not by a stub, not by a SUMMARY claim.

I went looking specifically for the failure modes that survive a high task-completion rate, and did not find them:

- **No stubs.** Every artifact is substantive, imported, used, and its rendered values trace back to a real filesystem
  read or a real process outcome (Level 4 table above). The one constant in a response body is correct by contract.
- **No unwired pieces.** All 22 declared key links resolve, including the three that were the phase's real integration
  risk: `router.go` ← `main.go` (the extended `NewRouter` signature), `signals.go` → `queue.Drain`, and `output.go` →
  `redact.go` (the stateful latch, which is the link a per-line redactor would have silently broken).
- **No presence-only pass on a behavior-dependent truth.** SC-9, SC-11, P9, P12 and the D-02 sweep all assert state
  transitions or cancellation/cleanup invariants that grep cannot see. Each is backed by a named test that I re-ran
  under `-race` for this report, and the SC-9 tests assert peak occupancy and an observed intermediate `queued` status
  rather than merely that a mutex exists. That is why `behavior_unverified` is 0 rather than 5.
- **No debt markers.** Zero `TBD`/`FIXME`/`XXX` in the add-on.

Two SCs were implemented non-literally, and in both cases I judge the implementation to serve the criterion's stated
guarantee better than its literal wording would have (SC-3's D-10/D-12 reconciliation; SC-10's PEM latch and pattern
superset). Both are documented in code, in DOCS.md, and in the phase artifacts, with the inversion path spelled out —
which is what makes them defensible engineering decisions rather than silent scope reduction. No override is required.

The status is `human_needed` rather than `passed` solely because the human-verification section is non-empty: three
review-fix changes were explicitly flagged by the executor as needing a real-environment confirmation pass. Everything
automatable is green — `go build`, `go vet`, `go test -race` across 11 packages, `make lint` (21 hooks), plus
`validate-versions` and `validate-addons`. Nothing blocks Phase 18, which consumes the job-status surface this phase
publishes; the four deferred items are all owned by Phase 19's end-to-end mandate, and R-01 is an accepted risk with a
named owner and date.

---

_Verified: 2026-09-08T18:05:00Z_ _Verifier: Claude (gsd-verifier)_
