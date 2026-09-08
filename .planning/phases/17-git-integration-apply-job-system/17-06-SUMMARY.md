---
phase: 17-git-integration-apply-job-system
plan: 06
subsystem: api
tags: [go, chi, http-handlers, error-taxonomy, slog, sec-03, opentofu]

requires:
  - phase: 17-git-integration-apply-job-system
    provides:
      "17-02's contract.RunAccepted + the 20 ErrCode* constants, 17-03's git.Manager.Pull + git.Error taxonomy,
      17-04's runs.OutputPage.Redactions, 17-05's jobq.Queue.Submit + ErrCapacityExhausted"
  - phase: 16-iac-runner-foundation
    provides: "internal/httpapi router + handler shape (version.go), auth.RequireBearer, the OBS-01 request logger"
provides:
  - "statusForCode: the single error_code -> HTTP status table for every Phase 17 endpoint"
  - "writeError / writeGitError: the shared contract.ErrorResponse emitters 17-08's read handlers consume"
  - "ReposPull: POST /v1/repos/{name}/pull incl. the D-10/D-12 `ff_only` wire flag (GIT-03)"
  - "Plan + Apply: POST /v1/plan and POST /v1/apply, 202 + Location, 503 + Retry-After on capacity (RUN-02/RUN-03)"
  - "auditRedactions: the SEC-03 `redaction.audit` slog record, with a single-emission call contract for 17-08"
  - "Two handler seams (repoPuller, submitter) that keep the exported signatures concrete for router.go"
affects:
  [
    17-07 startup wiring (constructs *git.Manager and *jobq.Queue for these handlers),
    17-08 read endpoints + router mount (reuses writeError/writeGitError and owes the auditRedactions call),
    19 live verification,
  ]

actuals:
  tokens: 14132
  tasks: 3
  commits: 6
plan_head_before: 0633f25cb969939f9d4f861a450d73554c6c41a3

tech-stack:
  added: []
  patterns:
    - "Exported handler keeps the concrete dependency (*git.Manager / *jobq.Queue) for router.go; an unexported
      handler core takes a minimal method-set interface so every response branch is unit-testable"
    - "One status table (statusForCode) owns error_code -> HTTP status for all five Phase 17 endpoints; handlers
      never pick a status for a typed error themselves"
    - "Compile-time signature locks (var _ func(...) = Fn) in the test files instead of grep-based assertions"
    - "Untyped errors are logged, never serialized: the wire gets a fixed code + fixed message (GIT-04)"

key-files:
  created:
    - iac-runner/internal/httpapi/handlers/write_error.go
    - iac-runner/internal/httpapi/handlers/write_error_test.go
    - iac-runner/internal/httpapi/handlers/repos_pull.go
    - iac-runner/internal/httpapi/handlers/repos_pull_test.go
    - iac-runner/internal/httpapi/handlers/plan.go
    - iac-runner/internal/httpapi/handlers/plan_test.go
    - iac-runner/internal/httpapi/handlers/redaction_audit.go
    - iac-runner/internal/httpapi/handlers/redaction_audit_test.go
  modified: []

key-decisions:
  - "GIT-03/SC-3 statuses win over the plan's sample code: git_ssh_handshake + git_unauthorized are 403 and
    git_non_fast_forward is 409, not the blanket 502 the plan's Task 1 <behavior> block sketched"
  - "The optional `ff_only` request body implements the D-10/D-12 resolution 17-03 shipped: default false, so a
    body-less pull on a pinned repo re-lands on its ref; only an explicit true triggers the 400 refusal"
  - "A malformed request body on all three write endpoints returns run_invalid_dir, the taxonomy's request-shape
    slot — inventing a new code would be a contract change (17-02 owns contract/types.go, D-20 needs a DOCS.md row)"
  - "An unclassified (non-*git.Error) failure is 500 + apply_failed with a fixed message from writeGitError;
    repos_pull keeps its own 502 + git_clone_failed fallback because a pull failure is git-side by construction"
  - "auditRedactions is the single emission point for `redaction.audit` and is silent on a zero-redaction page"
  - "The handler forwards `dir` verbatim to Submit: runs.ValidateDir inside the queue stays the only validator"

patterns-established:
  - "Interface seam per handler, concrete exported signature: reposPullHandler(repoPuller) / submitHandler(submitter,
    kind) are the testable cores behind ReposPull / Plan / Apply"
  - "DisallowUnknownFields on every request body so a typo'd field is a loud 400, never a dropped instruction"
  - "Audit/observability records carry counts and identifiers only, never the content they describe"

requirements-completed: [GIT-03, RUN-02, RUN-03]

coverage:
  - id: D1
    description:
      "POST /v1/repos/{name}/pull calls git.Manager.Pull with the request's ff_only flag and returns 200
      {name,mode,head}; both pull modes (ff-only, ref) are reported as the manager resolved them"
    requirement: GIT-03
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullSuccess"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullRefModeIsPassedThrough"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullFFOnlyFlagReachesPull"
        status: pass
    human_judgment: false
  - id: D2
    description:
      "Every git_* failure surfaces as its typed error_code with the GIT-03/SC-3 status: 403 auth, 409
      non-fast-forward, 404 clone-missing/ref-not-found, 400 ref+ff_only conflict, 502 DNS/opaque"
    requirement: GIT-03
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/write_error_test.go#TestStatusForCodeTable"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullSSHHandshakeIs403"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullNonFastForwardIs409"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullRefPullIncompatibleIs400"
        status: pass
    human_judgment: false
  - id: D3
    description:
      "No 4xx/5xx body carries raw stderr, a stack trace or a filesystem path — an unclassified error yields a
      fixed code plus a fixed message and the detail stays in the add-on log"
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullOpaqueErrorDoesNotLeak"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/write_error_test.go#TestWriteGitErrorOpaqueFallback"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestSubmitOpaqueErrorDoesNotLeak"
        status: pass
    human_judgment: false
  - id: D4
    description:
      "POST /v1/plan and POST /v1/apply return 202 + Location: /v1/runs/{id} + RunAccepted{queued} and submit the
      correct RunKind, without doing the tofu work inline"
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestPlanQueuesRunKindPlan"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestApplyQueuesRunKindApply"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestPlanMissingDirIsLegal"
        status: pass
    human_judgment: false
  - id: D5
    description:
      "A saturated runner refuses both submit endpoints identically: 503 + Retry-After: 30 +
      apply_capacity_exhausted, with no Location header and no run created (D-06)"
    requirement: RUN-03
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestPlanCapacityExhausted"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestApplyCapacityExhausted"
        status: pass
      - kind: unit
        ref: "internal/jobq/queue_test.go#TestSubmitCapacityExhausted"
        status: pass
    human_judgment: false
  - id: D6
    description:
      "A malformed or unknown-field body is rejected with 400 + run_invalid_dir before jobq.Submit is called at
      all, so a stream of bad requests can neither consume a slot nor create a run directory"
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestPlanMalformedBody"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/plan_test.go#TestPlanUnknownField"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/repos_pull_test.go#TestReposPullUnknownBodyField"
        status: pass
    human_judgment: false
  - id: D7
    description:
      "The SEC-03 `redaction.audit` slog record carries the served page's redaction count, run id and request id,
      and never the page content"
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/redaction_audit_test.go#TestAuditRedactionsEmitsRecord"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/redaction_audit_test.go#TestAuditRedactionsNeverLogsContent"
        status: pass
    human_judgment: true
    rationale:
      "The helper is proven, but it has no production caller until 17-08 mounts GET /v1/runs/{id}. ROADMAP SC-10 is
      only observable end-to-end once that call exists — recorded as an open window."
  - id: D8
    description:
      "Two concurrent applies on one repo both get 202 while the second waits, and cross-repo applies run in
      parallel (RUN-06 through the HTTP surface)"
    requirement: RUN-03
    verification: []
    human_judgment: true
    rationale:
      "The serialization itself is 17-05's, unit-proven at the queue boundary. Observing it THROUGH the HTTP
      endpoints needs a mounted router (17-08), a wired queue (17-07) and a real tofu — Phase 19's job."

duration: 19 min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 06: Write-side HTTP surface (pull, plan, apply) Summary

**The three Phase 17 write endpoints now exist as handlers over the git manager and the job queue, with one shared
`error_code` → HTTP status table that turns every typed failure from `internal/git` and `internal/jobq` into a
contract-shaped response and lets nothing else — no stderr, no path, no stack trace — cross the API boundary.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-09-08T11:31Z
- **Completed:** 2026-09-08T11:50Z
- **Tasks:** 3 of 3 (plus one inherited obligation)
- **Files:** 8 created, 0 modified

## Accomplishments

- `statusForCode` — the single mapping from all 20 `contract.ErrCode*` values to an HTTP status, with the
  GIT-03/SC-3-mandated 403 / 409 rows and a fail-safe 502 default for the additive codes D-20 promises will appear.
- `writeError` / `writeGitError` — the shared `contract.ErrorResponse` emitters. `writeGitError` uses `errors.As`, so
  a `%w`-wrapped `*git.Error` from `jobq.Submit` still lands on its own status.
- `ReposPull` — `POST /v1/repos/{name}/pull` with the optional `{"ff_only":<bool>}` body that implements the
  D-10/D-12 resolution, an unknown-repo 404 before any git command runs, and an opaque-error path that logs the
  detail and serves a fixed message.
- `Plan` + `Apply` — one `submitHandler` parameterized by `contract.RunKind`, answering 202 + `Location` +
  `RunAccepted` immediately, and 503 + `Retry-After: 30` + `apply_capacity_exhausted` on saturation.
- `auditRedactions` — the SEC-03 `redaction.audit` record, with a written single-emission call contract so 17-08
  cannot double-log it.
- 44 top-level tests in `internal/httpapi/handlers` (112 including sub-tests), all against interface seams: no
  network, no repository, no `tofu`, no run directory.

## The three inherited obligations, discharged

### 1. SEC-03 `redaction.audit` (from 17-04)

`auditRedactions(ctx, runID, runs.OutputPage)` in `redaction_audit.go` is the emission point. It logs
`redaction.audit` at INFO with `request_id`, `run_id`, `redactions`, `page`, `page_size`, `total_lines` — counts and
identifiers only, never `page.Lines`. A logged secret is a leaked secret even when the response was clean, so
`TestAuditRedactionsNeverLogsContent` asserts the content is absent from the record.

**Contract for 17-08 — emitted exactly once per response, and this is how that is guaranteed structurally:**

| Endpoint                    | Calls `auditRedactions`?          | Why                                                   |
| --------------------------- | --------------------------------- | ----------------------------------------------------- |
| `GET /v1/runs/{id}`         | **Yes, exactly once**             | The only endpoint that serves output lines            |
| `GET /v1/runs`              | No                                | A listing carries no output — nothing was redacted    |
| `POST /v1/repos/{n}/pull`   | No                                | Serves no run output                                  |
| `POST /v1/plan`, `/v1/apply`| No                                | Serve no run output                                   |

17-08's `GetRun` must call it **once, after `runs.Store.ReadOutput` returns and before writing the response body**,
passing the same `OutputPage` it is about to serve — so the audited numbers are by construction the numbers the
client received. It must NOT call `runs.Redact` itself (`ReadOutput` already redacted) and must NOT emit its own
`redaction.audit` record.

A page with `Redactions == 0` emits nothing. A running apply is polled repeatedly; a zero record per poll would bury
the records that matter. The counted event is "redaction happened", not "output was read" — the latter is already the
middleware's `http.request` record.

**Open window:** the helper has no production caller until 17-08 lands, so ROADMAP SC-10 is not yet observable
end-to-end. Recorded in `.planning/WINDOWS.md` as an `unmet-truth`, and as coverage entry D7 with
`human_judgment: true`.

### 2. Capacity mapping (from 17-05)

`errors.Is(err, jobq.ErrCapacityExhausted)` → `Retry-After: 30` set **before** `WriteHeader`, then 503 +
`apply_capacity_exhausted`. No `Location` header is written on the refusal (asserted). No run directory is created
because `Submit`'s semaphore acquire is step 5 — after the four validation rejections and before
`runs.NewRunID`/`store.Create` — which 17-05 proved at the queue boundary
(`internal/jobq/queue_test.go#TestSubmitCapacityExhausted`). Every other `Submit` error goes through
`writeGitError`, so its `Code` is already the wire value and the handler picks no status of its own.

### 3. The D-10/D-12 `ff_only` wire flag (from 17-03)

`reposPullRequest{FFOnly bool `json:"ff_only"`}` is optional; three body shapes all mean the same thing — no body,
an empty body, `{}` — because the documented usage is a bare POST. The zero value is load-bearing:

| Request                                       | Repo state       | Result                                     |
| --------------------------------------------- | ---------------- | ------------------------------------------ |
| no body / `{}` / `{"ff_only":false}`          | unpinned         | `git pull --ff-only`, 200 `mode: "ff-only"` |
| no body / `{}` / `{"ff_only":false}`          | pinned via `ref` | fetch + checkout, 200 `mode: "ref"` (D-10)  |
| `{"ff_only":true}`                            | unpinned         | identical to above — the request agrees     |
| `{"ff_only":true}`                            | pinned via `ref` | 400 `git_ref_pull_incompatible` (D-12)      |
| `{"ffonly":true}` / any unknown field         | any              | 400 — `DisallowUnknownFields`               |

Had `ff_only` defaulted to `true` (as the plan's Task 1 sample code did), a pinned repo could never be refreshed at
all: every bare POST would hit D-12's refusal. That is exactly the outcome 17-03 resolved against.

## The error_code → HTTP status table as implemented

`statusForCode` in `write_error.go` is the single source. **17-08 must not contradict it — call `writeError` /
`writeGitError` rather than choosing a status.**

| error_code                  | Status | Why                                                             |
| --------------------------- | ------ | --------------------------------------------------------------- |
| `git_ssh_handshake`         | 403    | GIT-03/SC-3 verbatim: an auth failure is the operator's to fix   |
| `git_unauthorized`          | 403    | GIT-03/SC-3 verbatim                                            |
| `git_non_fast_forward`      | 409    | GIT-03/SC-3 verbatim: a diverged branch is a state conflict      |
| `git_ref_not_found`         | 404    | The named `ref`/`branch` does not exist on the remote            |
| `git_clone_missing`         | 404    | D-14: the precondition is absent                                 |
| `git_ref_pull_incompatible` | 400    | D-12: a request-shape contradiction, not an infra failure        |
| `git_dns_failure`           | 502    | Upstream unreachable                                             |
| `git_clone_failed`          | 502    | Generic git-side failure, incl. the opaque-error fallback        |
| `run_unknown_repo`          | 404    | Not in the `repos` Options list                                  |
| `run_unknown_id`            | 404    | Reserved for 17-08's `GET /v1/runs/{id}`                         |
| `run_not_found`             | 404    | Reserved for 17-08                                               |
| `run_invalid_dir`           | 400    | D-21/D-22, and the malformed-body slot on all three write paths  |
| `run_tofu_not_found`        | 503    | Well-formed request, runner temporarily unable to serve it       |
| `run_capacity_exhausted`    | 503    | Reserved taxonomy slot (D-19); handlers emit the apply_* spelling |
| `apply_capacity_exhausted`  | 503    | D-06, the value actually emitted, paired with `Retry-After: 30`   |
| `apply_already_running`      | 409    | State conflict                                                   |
| `apply_timeout`             | 504    | D-15/D-16: the process was killed at the deadline                |
| `plan_timeout`              | 504    | Plan-side counterpart                                            |
| `apply_failed`              | 500    | Also the fallback for an unclassified error                      |
| `unauthorized`              | 401    | Pre-existing AUTHR-02 value (the middleware writes it itself)     |
| _anything else_             | 502    | D-20 makes codes additive; the default must never be a 2xx        |

`writeError` appends the D-19 hint to `message` as ` — <hint>`, because `contract.ErrorResponse` carries only
`error_code` / `message` / `request_id` and adding a field there is 17-02's call, not a handler's.

## Exported handler signatures (for 17-08's router mount)

```go
func ReposPull(gitMgr *git.Manager) http.HandlerFunc   // POST /v1/repos/{name}/pull
func Plan(q *jobq.Queue) http.HandlerFunc              // POST /v1/plan
func Apply(q *jobq.Queue) http.HandlerFunc             // POST /v1/apply
```

Mount inside the existing `r.Route("/v1", …)` block, behind `auth.RequireBearer` — every handler in this plan assumes
a missing or wrong token never reaches it. All three are `http.HandlerFunc`, so `r.Post(...)` takes them directly.
Package-shared helpers available to 17-08 (same `handlers` package, unexported):

```go
func writeError(w http.ResponseWriter, status int, code, message, hint string)
func writeGitError(w http.ResponseWriter, err error)      // *git.Error -> statusForCode; else 500 + apply_failed
func statusForCode(code string) int
func auditRedactions(ctx context.Context, runID string, page runs.OutputPage)
```

## The test seams 17-07 and 17-08 should reuse

Both handlers follow the same shape: **the exported constructor keeps the concrete dependency** (so `router.go` passes
`*git.Manager` / `*jobq.Queue` with no adapter), while **an unexported core takes a minimal method-set interface**:

```go
type repoPuller interface {                    // repos_pull.go
    Repo(name string) (git.RepoConfig, bool)
    Pull(ctx context.Context, name string, ffOnly bool) (git.PullOutcome, error)
}
func reposPullHandler(p repoPuller) http.HandlerFunc

type submitter interface {                     // plan.go
    Submit(req jobq.Request) (string, error)
}
func submitHandler(q submitter, kind contract.RunKind) http.HandlerFunc
```

The `fakeQueue` strategy the tests adopted, explicitly, so 17-08 can copy it:

- `fakeQueue` holds `fn func(jobq.Request) (string, error)` plus a mutex-guarded `submits []jobq.Request`. A test sets
  `fn` to drive a branch and reads `recorded()` to assert what the handler actually asked for — that is how
  `Kind: plan` vs `Kind: apply` and "dir forwarded verbatim" are proven rather than assumed.
- `stubPuller` records `(name, ffOnly)` per call, which is what makes the `ff_only` wire contract testable.
- **No mock library, no generated doubles, no `*jobq.Queue` construction in a handler test.** A real queue would need
  a store, a git manager and a tofu path, and would re-test 17-05.
- Signature drift is caught by compile-time locks (`var _ func(*jobq.Queue) http.HandlerFunc = Plan`) in the test
  files, not by grep — a Go signature cannot be matched by an anchored regex because the opening brace shares the line.

## Task Commits

1. **Task 1: POST /v1/repos/{name}/pull + the shared error map** (TDD)
   - RED `10901c3` — `test(17-06)`: 19 tests + skeletons; verdict `RED_EVIDENCE_OK`, target `TestReposPullSuccess`
   - GREEN `d181b9d` — `feat(17-06)`: `statusForCode`, `writeError`, `writeGitError`, `ReposPull`
2. **Tasks 3 + 2: POST /v1/plan + POST /v1/apply** (TDD, executed test-first — see Deviation 4)
   - RED `0067c0d` — `test(17-06)`: 15 tests + skeleton; verdict `RED_EVIDENCE_OK`, target
     `TestPlanQueuesRunKindPlan`
   - GREEN `dc30431` — `feat(17-06)`: `Plan`, `Apply`, `submitHandler`
3. **Inherited obligation: the SEC-03 `redaction.audit` record** (TDD)
   - RED `66a2eb9` — `test(17-06)`: 4 tests + skeleton; verdict `RED_EVIDENCE_OK`, target
     `TestAuditRedactionsEmitsRecord`
   - GREEN `dad051b` — `feat(17-06)`: `auditRedactions`

No REFACTOR commit was needed: each GREEN landed in its final shape and the suite stayed green, so a no-op
`refactor(...)` commit would have been noise.

## TDD Gate Compliance

| Cycle                        | RED       | GREEN     | REFACTOR | Notes                                                          |
| ---------------------------- | --------- | --------- | -------- | -------------------------------------------------------------- |
| Task 1 (pull + error map)    | `10901c3` | `d181b9d` | —        | `RED_EVIDENCE_OK`, target `TestReposPullSuccess`               |
| Tasks 3+2 (plan + apply)     | `0067c0d` | `dc30431` | —        | `RED_EVIDENCE_OK`, target `TestPlanQueuesRunKindPlan`          |
| Obligation (redaction.audit) | `66a2eb9` | `dad051b` | —        | `RED_EVIDENCE_OK`, target `TestAuditRedactionsEmitsRecord`     |

All three RED phases were validated with `gsd-tools check tdd-red-evidence` after translating `go test -json` into
the TAP shape the checker parses (it is written against the Node test runner; the translation is a faithful
one-line-per-top-level-test rendering of the actual Go run, not a hand-written record). Each RED failed on an
assertion for the planned behavior — the skeletons published the contracts so the suites compiled, which is what
keeps a Go RED out of the `fixture_or_load_failure` verdict.

## Files Created/Modified

- `iac-runner/internal/httpapi/handlers/write_error.go` (137 lines) — `statusForCode` (the full taxonomy table),
  `writeError` (hint concatenation), `writeGitError` (`errors.As` + the 500 fallback).
- `iac-runner/internal/httpapi/handlers/write_error_test.go` (205) — 7 tests: the whole status table, the
  never-succeeds invariant, the body shape, the hint, the wrapped-error unwrap, the opaque fallback.
- `iac-runner/internal/httpapi/handlers/repos_pull.go` (165) — `ReposPull`, `reposPullHandler`, `repoPuller`,
  `reposPullRequest`/`reposPullResponse`, `decodeReposPullBody`.
- `iac-runner/internal/httpapi/handlers/repos_pull_test.go` (338) — 12 tests + the `stubPuller` seam.
- `iac-runner/internal/httpapi/handlers/plan.go` (134) — `Plan`, `Apply`, `submitHandler`, `submitter`,
  `planApplyRequest`, `retryAfterCapacitySeconds`.
- `iac-runner/internal/httpapi/handlers/plan_test.go` (368) — 15 tests + the `fakeQueue` seam.
- `iac-runner/internal/httpapi/handlers/redaction_audit.go` (60) — `auditRedactions` + the single-emission call
  contract in the file doc.
- `iac-runner/internal/httpapi/handlers/redaction_audit_test.go` (135) — 4 tests incl. the slog capture helper.

`internal/httpapi/router.go` was deliberately NOT touched — 17-08 owns the mount (plan verification step 7, verified).

## Decisions Made

1. **403 / 409 over 502 for git auth and non-fast-forward.** The plan's Task 1 `<behavior>` block said 502 for
   `git_ssh_handshake`; GIT-03, ROADMAP SC-3, the plan's own `<success_criteria>` and 17-03's handoff all say 403 for
   auth failures and 409 for non-fast-forward. Three sources against one sample snippet — and the semantics agree
   with them: an operator has to fix a deploy key or a diverged branch, whereas a 5xx reads as "the runner is broken,
   retry later". Implemented per the requirement (Deviation 1).
2. **`run_invalid_dir` is the malformed-body code on all three write endpoints.** The D-19 taxonomy has no generic
   bad-request slot, and adding one would be a contract change owned by 17-02 plus a DOCS.md row (D-20).
   `run_invalid_dir` is the taxonomy's request-shape entry and the plan already prescribed it for `/v1/plan`; using
   it on `/pull` too keeps a client's error handling uniform across the write surface.
3. **The unclassified-error fallback differs by endpoint, on purpose.** `writeGitError` answers 500 +
   `apply_failed` (its callers include `Submit`, whose untyped failures are store/run-id problems — genuinely
   internal). `repos_pull` intercepts the non-`*git.Error` case first and answers 502 + `git_clone_failed`, because
   any failure of `Pull` is git-side by construction, and `git_clone_failed` is the taxonomy's generic git bucket.
4. **`Retry-After` is a constant, not a function of queue depth.** There is no queue — a saturated runner refuses
   (D-06) — so the only honest answer is "try again in a bit", and a stable 30 is a number an operator's retry loop
   can be written against.
5. **`Location` is a path, not an absolute URL.** The add-on is reached through the HA ingress proxy as often as
   directly; baking in a scheme and host would produce a `Location` the client cannot follow. Every HTTP client
   resolves a relative `Location` against the request URL (RFC 7231 §7.1.2).
6. **`dir` is forwarded verbatim.** A handler that pre-cleaned it could smuggle a path past `runs.ValidateDir`, which
   D-21 makes the single validator. `TestSubmitForwardsDirVerbatim` locks this.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] The plan's sample status mapping contradicted GIT-03/SC-3**

- **Found during:** Task 1
- **Issue:** Task 1's `<behavior>` block and its `writeGitError` sample mapped every `*git.Error` except
  `git_ref_pull_incompatible` to 502. GIT-03 and ROADMAP SC-3 both require "non-fast-forward pulls and auth failures
  surface as typed HTTP 409 / 403 errors", 17-03's handoff spells out the same four rows, and the plan's own
  `<success_criteria>` says "403 auth, 404 missing ref / missing clone, 409 non-fast-forward, 400 ref/ff-only
  conflict". A blanket 502 would have shipped an endpoint that reports operator misconfiguration as a runner fault.
- **Fix:** Implemented the full requirement-level table in `statusForCode` (see the table above), covering all 20
  `contract.ErrCode*` values plus a 502 default for D-20's future additive codes.
- **Files modified:** `write_error.go`, `write_error_test.go`, `repos_pull_test.go`
- **Verification:** `TestStatusForCodeTable` (21 sub-cases), `TestStatusForCodeNeverSucceeds`,
  `TestReposPullSSHHandshakeIs403`, `TestReposPullNonFastForwardIs409`, `TestReposPullCloneMissingIs404`
- **Committed in:** `10901c3` (RED) / `d181b9d` (GREEN)

**2. [Rule 1 - Bug] The plan hardcoded `ffOnly := true`, which would have made pinned repos unrefreshable**

- **Found during:** Task 1
- **Issue:** Task 1's sample code sets `ffOnly := true` with the comment "ffOnly is the spec-default". 17-03 shipped
  the opposite contract — "`ffOnly` carries the optional `ff_only` boolean of the request body (17-06 owns the wire,
  default `false`)" — and with `true` hardcoded, **every** bare `POST /v1/repos/{name}/pull` against a `ref`-pinned
  repo would hit D-12's 400 refusal, leaving such a repo with no way to update at all. That is precisely the outcome
  17-03's D-10/D-12 reconciliation rejected.
- **Fix:** Added the optional `{"ff_only":<bool>}` request body (default `false`) and forwarded it to `Pull`, plus the
  three legal no-body shapes and `DisallowUnknownFields` so a typo cannot silently change git semantics.
- **Files modified:** `repos_pull.go`, `repos_pull_test.go`
- **Verification:** `TestReposPullSuccess` (asserts `ffOnly == false` on a body-less POST),
  `TestReposPullFFOnlyFlagReachesPull`, `TestReposPullRefPullIncompatibleIs400`,
  `TestReposPullEmptyJSONBodyIsLegal`, `TestReposPullUnknownBodyField`
- **Committed in:** `10901c3` (RED) / `d181b9d` (GREEN)

**3. [Rule 2 - Missing critical] Three files beyond `files_modified`, all required by obligations the plan carried**

- **Found during:** Tasks 1-3
- **Issue:** The plan lists 5 files, which cannot hold the work it assigns: (a) the shared status table is the
  cross-cutting wire contract for five endpoints and had no test file; (b) the SEC-03 `redaction.audit` obligation
  inherited from 17-04 has no file allocated anywhere in the plan.
- **Fix:** Added `write_error_test.go` (the status table is the single mapping point — an untested table is a wire
  contract nobody checks), plus `redaction_audit.go` + `redaction_audit_test.go` (the obligation, kept in its own
  file so its call contract is discoverable where 17-08 will look for it, rather than buried in an error-helper).
- **Files modified:** the three new files; no existing file's scope changed
- **Verification:** `go build ./...`, `go vet ./...`, `go test ./... -count=1` all exit 0; plan verification step 6's
  file list is 8 rather than 5, step 7 (`router.go` untouched) still holds
- **Committed in:** `10901c3`, `66a2eb9`, `dad051b`

**4. [Rule 3 - Blocking] Tasks 2 and 3 were inverted so the TDD cycle could run**

- **Found during:** Task 2
- **Issue:** Both tasks carry `tdd="true"`, but Task 2 is the `plan.go` implementation and Task 3 is `plan_test.go` —
  in that order the implementation would land before its first test, which is not RED→GREEN and would have produced
  an `unexpected_green` RED verdict for Task 3.
- **Fix:** Executed them as one cycle in TDD order: Task 3's test file plus a contract-only skeleton as the RED
  commit (`0067c0d`), Task 2's implementation as the GREEN commit (`dc30431`). Both tasks keep their own commit and
  their own deliverable; only the order changed.
- **Files modified:** `plan.go`, `plan_test.go`
- **Verification:** `gsd-tools check tdd-red-evidence` → `RED_EVIDENCE_OK` for the RED commit; both tasks'
  acceptance criteria re-run and passing
- **Committed in:** `0067c0d`, `dc30431`

**5. [Rule 1 - Bug] Four acceptance criteria are unsatisfiable as written (the known phase-wide grep defect)**

- **Found during:** Tasks 1-3
- **Issue:** Four criteria cannot pass against valid Go, matching the defect already hit in 17-04 and 17-05:
  - Task 1 #1 `grep -E '^func ReposPull\(gitMgr \*git\.Manager\) http\.HandlerFunc$'` and Task 2 #1's Plan/Apply
    equivalent — a Go function's opening brace shares the signature line, so `$` can never match.
  - Task 1 #5 `grep -E 'errors\.As\(.*\*git\.Error\)'` — `errors.As` takes a **pointer to** the target
    (`var ge *git.Error; errors.As(err, &ge)`); the inline-type form the regex expects is not compilable Go.
  - Task 1 #4 demands the count be exactly `2`; the file has 3 matching lines (the `writeError` call, the status
    contract in the file doc, and the fallback's own comment).
- **Fix:** Verified the underlying truths with corrected checks instead of reshaping the code:
  `grep -cE '^func (Plan|Apply)\(q \*jobq\.Queue\) http\.HandlerFunc \{$'` → 2,
  `grep -E '^func ReposPull\(gitMgr \*git\.Manager\) http\.HandlerFunc \{$'` → line 78,
  `grep -nB1 'errors\.As(err, &ge)'` → present in both `repos_pull.go:112` and `write_error.go:131`,
  and the unknown-repo/`git_clone_failed` criterion at 3 ≥ 2. Every signature is byte-identical to the plan's
  `<interfaces>` block, additionally locked at compile time by
  `var _ func(*git.Manager) http.HandlerFunc = ReposPull` and the `Plan`/`Apply` pair.
- **Files modified:** none (verification method only)
- **Verification:** the corrected greps above, plus the compile-time locks (the package would not build on drift)
- **Committed in:** n/a — no code change

---

**Total deviations:** 5 auto-fixed (2 × Rule 1 bug, 2 × Rule 2 missing-critical, 1 × Rule 3 blocking).
**Impact on plan:** No scope creep. Two deviations correct the plan against its own requirements and against 17-03's
shipped contract; one adds the file the inherited SEC-03 obligation needed; one reorders two tasks so TDD is possible;
one is a verification-method correction with no code impact. The plan's objective — the write-side HTTP surface with a
single error-mapping point — is delivered as specified.

## Issues Encountered

None blocking.

- The plan's `submitJSON` test helper sketch was not usable as written (it derives the URL from the HTTP method and
  builds a `chi.RouteContext` it never attaches). Replaced with `serveSubmit`, which picks the path from the
  `contract.RunKind` and needs no route context, since `/v1/plan` and `/v1/apply` have no URL parameters.
- Environment: no `go` on the host, so every toolchain command ran in `golang:1.25-alpine` with the host module and
  build caches mounted and a `tofu` stub on `PATH` (for the pre-existing `TestHealthzBothPass` probe), per the
  phase's established procedure. `-race` additionally needs `gcc musl-dev` in the throwaway container.
- The pre-existing `hadolint` DL3003 finding on `iac-runner/Dockerfile:40` is untouched and still deferred to 17-07.
  `iac-runner/internal/httpapi/handlers/healthz_test.go` is still not gofmt-clean (pre-existing, in
  `deferred-items.md`); all eight files this plan created are gofmt-clean.

## Known Stubs

None. Every function shipped is fully implemented and unit-tested.

One **unwired** (not stubbed) helper: `auditRedactions` has no production caller until 17-08 mounts
`GET /v1/runs/{id}`. It is complete and tested; what is missing is the consumer, which the plan boundary places in
17-08. Recorded in `.planning/WINDOWS.md` as an `unmet-truth` for ROADMAP SC-10, and as coverage entry D7 with
`human_judgment: true`.

## Threat Flags

| Flag                     | File                                                | Description                                                                                                                                                                                                                                                       |
| ------------------------ | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| threat_flag: network_api | `iac-runner/internal/httpapi/handlers/plan.go`      | First authenticated HTTP path that can start a process. Mitigated by construction: the handler forwards only `repo` and `dir` and builds no command line; `jobq.Submit` validates both before anything is spawned. Auth is inherited from the `/v1` subrouter.       |
| threat_flag: network_api | `iac-runner/internal/httpapi/handlers/repos_pull.go`| First authenticated HTTP path that can reach the network with a deploy key. The only user input is the `{name}` route parameter, matched against the configured repo map (404 on miss), and the boolean `ff_only`. No user string reaches a git argument.             |
| threat_flag: auth_path   | `iac-runner/internal/httpapi/handlers/write_error.go`| `statusForCode` is now the single decision point for what a client learns about a failure. A wrong row could over-disclose (e.g. distinguishing "repo missing" from "key wrong" where that is a signal); the current rows disclose only what GIT-04 mandates.       |

## User Setup Required

None — these handlers are not mounted yet (17-08) and need no external service, credential or environment variable of
their own.

## Next Phase Readiness

**Ready for 17-07 (startup wiring) and 17-08 (read endpoints + router mount).** Neither needs to touch this package's
internals.

- **17-07** constructs the dependencies these handlers take: `git.NewManager(...)` → `*git.Manager` for `ReposPull`,
  and `jobq.New(jobq.Deps{...})` → `*jobq.Queue` for `Plan`/`Apply`. It should also document all 20 `error_code`
  values and their HTTP statuses in `DOCS.md` per D-20 — the table above is copy-ready — and note the optional
  `ff_only` body field on `/v1/repos/{name}/pull`.
- **17-08** mounts all three handlers inside the existing `r.Route("/v1", …)` block behind `RequireBearer`, reuses
  `writeError` / `writeGitError` / `statusForCode` rather than deriving statuses, and **calls `auditRedactions`
  exactly once in `GetRun`** per the contract above. The `run_unknown_id` / `run_not_found` rows are already in the
  table waiting for it.
- **Phase 19** owns the two coverage entries automation cannot close: the `redaction.audit` record appearing in a
  live add-on's log (D7) and RUN-06 serialization observed through the HTTP endpoints against a real `tofu` (D8).

No blockers.

## Self-Check: PASSED

- All 8 `key-files.created` entries verified present on disk with `[ -f ]`.
- All 6 commits verified present in `git log`: `10901c3`, `d181b9d`, `0067c0d`, `dc30431`, `66a2eb9`, `dad051b`.
- `git rev-list --count 0633f25..HEAD` = 6 at SUMMARY-write time, matching the measured `commits: 6` frontmatter
  (`plan_head_before: 0633f25c…`). The SUMMARY's own commit and the STATE/ROADMAP metadata commit follow this
  measurement.
- Plan `<verification>` steps 1-7 all re-run in the container and passing: `go build ./...` exit 0,
  `go vet ./...` exit 0, `go test ./internal/httpapi/...` exit 0, `go test ./...` exit 0 (all 8 packages with tests
  green, no Phase 16 / 17-01..05 regression), `go test ./internal/httpapi/handlers/... -count=1` reports 44
  top-level tests (plan asks for ≥ 14), `git diff --name-only` lists the 8 files (5 planned + 3 per Deviation 3),
  and `router.go` is untouched.
- `go test ./internal/httpapi/... -race -count=1` exit 0 (extra check; the `fakeQueue` is mutex-guarded).
- All acceptance criteria for all three tasks re-run and passing, except the four unsatisfiable regexes replaced with
  corrected checks and compile-time signature locks (Deviation 5).

---

_Phase: 17-git-integration-apply-job-system_ _Completed: 2026-09-08_
