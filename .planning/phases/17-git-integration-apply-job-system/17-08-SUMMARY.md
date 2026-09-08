---
phase: 17-git-integration-apply-job-system
plan: 08
subsystem: api
tags: [go, chi, http-handlers, pagination, sec-03, redaction-audit, router, run-history]

requires:
  - phase: 17-git-integration-apply-job-system
    provides:
      "17-02's contract.RunDetail/RunSummary/RunListResponse + the pagination and listing constants, 17-04's runs.Store
      Load/List/ReadOutput + IsValidRunID + ErrRunNotFound, 17-06's writeError/statusForCode and the auditRedactions
      emission point"
  - phase: 16-iac-runner-foundation
    provides:
      "internal/httpapi router + the /v1 auth subrouter, auth.RequireBearer, handlers.Version, the OBS-01 request logger"
provides:
  - "GetRun: GET /v1/runs/{id} -> contract.RunDetail with a paginated, read-time-redacted output page (RUN-04)"
  - "ListRuns: GET /v1/runs -> contract.RunListResponse with ?repo=/?status=/?limit= and the RUN-05 caps"
  - "NewRouter with the Phase 17 signature: all five new endpoints mounted inside the existing /v1 bearer gate"
  - "The production caller of auditRedactions — ROADMAP SC-10 is now observable end-to-end (window 1 closed)"
  - "router_test.go: the first test file over internal/httpapi, proving the Phase 16 surface did not regress"
  - "Two more handler seams (runReader, runLister) plus runDetail/runSummary/formatRunTime projections"
affects:
  [
    17-07 startup wiring (must replace main.go's three nil arguments with real deps),
    19 live verification (the read endpoints are the observation surface for every other Phase 17 truth),
  ]

actuals:
  tokens: 13209
  tasks: 3
  commits: 5
plan_head_before: dc1ec8e275443b98a98859205121cb6526d8de32

tech-stack:
  added: []
  patterns:
    - "Exported handler keeps the concrete *runs.Store for router.go; an unexported core takes a one/two-method
      interface (runReader, runLister) so every response branch is unit-testable with no run directory on disk"
    - "Compile-time signature locks (var _ func(...) = Fn) in the test files instead of anchored greps — a Go signature
      cannot be matched by a ^...$ regex because the opening brace shares the line"
    - "Wire projections are field-by-field functions (runDetail, runSummary), never a shared struct or an alias, so a
      future runs.Meta field cannot leak into the API by accident"
    - "Query-parameter caps are applied in the handler before the store is asked, even though the store clamps too: only
      the handler can report the applied value back to the client"

key-files:
  created:
    - iac-runner/internal/httpapi/handlers/get_run.go
    - iac-runner/internal/httpapi/handlers/get_run_test.go
    - iac-runner/internal/httpapi/handlers/list_runs.go
    - iac-runner/internal/httpapi/handlers/list_runs_test.go
    - iac-runner/internal/httpapi/router_test.go
  modified:
    - iac-runner/internal/httpapi/router.go
    - iac-runner/cmd/runner/main.go

key-decisions:
  - "auditRedactions (17-06's helper) is called from GetRun rather than the plan's inline slog.Info sketch — the plan
    would have created a SECOND emission point with a different record name (iac_runner.redaction.audit vs
    redaction.audit), breaking the exactly-once contract 17-06 wrote and leaving SC-10 unmet"
  - 'The off-taxonomy error_code "internal" the plan''s sample code used is replaced by contract.ErrCodeApplyFailed
    (500) and contract.ErrCodeRunInvalidDir (400) — every 4xx/5xx body carries a real ErrCode* value per D-19/D-20, and
    run_invalid_dir is the request-shape slot 17-06 already established'
  - "NewRouter APPENDS the three Phase 17 dependencies after the Phase 16 arguments rather than reordering, so the
    RUN-01 /v1/version mount and the auth gate are provably untouched"
  - "main.go passes nil for gitMgr/runStore/q with a TODO(17-07): the router mount (this plan) and the startup wiring
    (17-07) are separate plans, and a compiling build is a hard acceptance criterion of this one"
  - "A bad ?page=/?page_size=/?limit= value falls back to the default instead of 400ing — these are navigation hints,
    and a typo in a hand-typed curl should show page 1, not an error the operator has to decode"
  - 'An empty listing is 200 + {"runs":[],"count":0,...}, never 404: a repo with zero runs and an unconfigured repo are
    both ''nothing to show'', and only the Options list distinguishes them'

patterns-established:
  - "router_test.go asserts reachability AND which side of the auth gate a route is on — the two things a router change
    can break that no handler test can see"
  - "A 401 (not a 404) on an anonymous request is the positive proof that a route is mounted INSIDE the gate; a 404
    would mean it was never mounted, a 2xx that it was mounted outside"

requirements-completed: [RUN-01, RUN-04, RUN-05]

coverage:
  - id: D1
    description:
      "GET /v1/runs/{id} returns the full RUN-04 body — status, exit_code, started_at, finished_at, paginated
      output_lines, page, page_size, total_lines — projected from runs.Meta plus one ReadOutput page"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunSuccess"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunQueuedRunHasEmptyOutput"
        status: pass
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterGetRunServesAStoredRun"
        status: pass
    human_judgment: false
  - id: D2
    description:
      "The served output page is redacted at read time and its redaction count reaches the operator's log as exactly one
      `redaction.audit` record per response, carrying identifiers and counts but never the lines"
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunWithRedactionsEmitsAudit"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunNoRedactionsNoAudit"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunAuditEmittedOncePerRequest"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsEmitsNoAuditRecord"
        status: pass
    human_judgment: false
  - id: D3
    description:
      "?page= and ?page_size= are honoured verbatim and clamped to the OBS-03 caps before the store is asked, so an
      oversized request cannot make the runner read an unbounded window"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunPagination"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunPageSizeClamped"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunBadPaginationFallsBack"
        status: pass
    human_judgment: false
  - id: D4
    description:
      "An unknown or malformed run id is a typed 404 (run_not_found / run_unknown_id), never a filesystem error or a
      panic, and a malformed id never reaches the store at all"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunMalformedIDIsRunUnknownID"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunNotFound"
        status: pass
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterReadEndpointsReachable"
        status: pass
    human_judgment: false
  - id: D5
    description:
      "GET /v1/runs returns the most recent runs with default limit 20 and cap 100, filtered by ?repo= and ?status=,
      with ?status=interrupted a first-class value (D-02)"
    requirement: RUN-05
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsDefaultLimit"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsLimitClamped"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsRepoFilter"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsStatusFilterInterrupted"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsStatusFilterEveryEnumValue"
        status: pass
    human_judgment: false
  - id: D6
    description:
      "Newest-first ordering of the listing (RUN-05's ordering half) is the store's sort, exercised through the handler
      only as pass-through"
    requirement: RUN-05
    verification:
      - kind: unit
        ref: "internal/runs/store_test.go#TestStoreListOrdersByStartedAtDesc"
        status: pass
    human_judgment: true
    rationale:
      "The handler forwards the store's slice untouched, so ordering is proven at the store boundary (17-04), not here.
      Observing it through the HTTP surface with several real runs is Phase 19's job."
  - id: D7
    description:
      "Every 4xx/5xx body from both read handlers carries a contract.ErrCode* value plus a human-readable message; raw
      error strings, errnos and filesystem paths never cross the API boundary"
    verification:
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunLoadFailureDoesNotLeak"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/get_run_test.go#TestGetRunReadOutputFailureDoesNotLeak"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsStoreFailureDoesNotLeak"
        status: pass
      - kind: unit
        ref: "internal/httpapi/handlers/list_runs_test.go#TestListRunsUnknownStatus"
        status: pass
    human_judgment: false
  - id: D8
    description:
      "All five Phase 17 endpoints are reachable behind the existing bearer gate, and the Phase 16 surface (/v1/version,
      /v1/auth/rotate, /healthz, /) behaves exactly as before"
    requirement: RUN-01
    verification:
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterPhase17EndpointsRequireBearer"
        status: pass
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterVersionStillMounted"
        status: pass
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterAuthRotateStillMounted"
        status: pass
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterPhase16SurfaceUnauthenticated"
        status: pass
      - kind: integration
        ref: "internal/httpapi/router_test.go#TestRouterReadEndpointsReachable"
        status: pass
    human_judgment: false
  - id: D9
    description: "The three write endpoints answer real work through the router (a pull, a queued plan, a queued apply)"
    verification: []
    human_judgment: true
    rationale:
      "This plan proves they are mounted and gated; making them DO anything needs main.go to construct a *git.Manager
      and a *jobq.Queue, which is 17-07's task. Phase 19 observes the live behavior."

duration: 10 min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 08: Read-side HTTP surface + router mount Summary

**`GET /v1/runs/{id}` and `GET /v1/runs` now project the on-disk run tree onto the wire — a paginated, read-time
redacted output page and a filtered newest-first listing — and all five Phase 17 endpoints are mounted inside the
existing `/v1` bearer gate, with the Phase 16 surface proven unchanged by the first test file this repository has ever
had over `internal/httpapi`.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-08T11:58Z
- **Completed:** 2026-09-08T12:08Z
- **Tasks:** 3 of 3 (plus one inherited obligation, discharged)
- **Files:** 5 created, 2 modified

## Accomplishments

- `GetRun` — `GET /v1/runs/{id}`: the `runs.IsValidRunID` guard before any I/O, a typed 404 for both the malformed and
  the absent id, `?page=` / `?page_size=` clamped to the OBS-03 caps, and a field-by-field `Meta` + `OutputPage` →
  `contract.RunDetail` projection where `nil` output marshals as `[]` and an unfinished run reports no `finished_at`.
- `ListRuns` — `GET /v1/runs`: `?status=` validated against the five `RunStatus` values at the HTTP boundary (D-02's
  `interrupted` included), `?limit=` clamped to 100 **and echoed** so a truncated page is visible, `?repo=` forwarded
  verbatim, and an empty result served as a 200 with an empty array.
- `NewRouter` with the Phase 17 signature — the three new dependencies appended after the Phase 16 arguments, all five
  new mounts inside the same `r.Route("/v1", …)` block behind `auth.RequireBearer`.
- `router_test.go` — 6 top-level tests (10 including sub-tests) over the _mounted_ router: the Phase 16 non-regression,
  the five-endpoint 401 sweep, and one end-to-end `GET /v1/runs/{id}` over a real `runs.Store`.
- 67 top-level tests in `internal/httpapi/handlers` (up from 44), all against interface seams — no run directory, no
  `tofu`, no network.

## The inherited obligation, discharged: ROADMAP SC-10

17-06 shipped `auditRedactions(ctx, runID, runs.OutputPage)` as the single SEC-03 emission point and recorded in
`.planning/WINDOWS.md` (entry 1, `unmet-truth`) that it had **no production caller** — SC-10 was not observable
end-to-end. It now has exactly one:

```go
outputPage, err := rd.ReadOutput(id, page, pageSize)
// … error handling …
auditRedactions(r.Context(), id, outputPage)   // once, before the body
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusOK)
_ = json.NewEncoder(w).Encode(runDetail(meta, outputPage))
```

The call sits **after `ReadOutput` and before the response body**, and is passed the same `OutputPage` that is about to
be served, exactly as 17-06's call contract specified — so the audited numbers are by construction the numbers the
client received. `GET /v1/runs` does **not** call it (`TestListRunsEmitsNoAuditRecord` asserts that), and neither do the
three write endpoints. `TestGetRunAuditEmittedOncePerRequest` issues two requests and asserts exactly two records, which
is what makes "exactly once" a checked property rather than a claim.

**Window 1 is now `fixed`** (`gsd-tools windows fixed 1`; `open_count: 0`). 17-06's coverage entry D7 was
`human_judgment: true` for precisely this reason; the equivalent entry here (D2) is `human_judgment: false` with four
passing verifications.

## Phase 16 non-regression: proven, not assumed

`internal/httpapi` had no test file before this plan. Since `router.go` is the one edit that can break the whole Phase
16 surface, the claim is now a test:

| Route                  | Assertion                                                                  | Test                                      |
| ---------------------- | -------------------------------------------------------------------------- | ----------------------------------------- |
| `GET /`                | 200 + `contract.RootResponse` carrying the runner version, no token needed | `TestRouterPhase16SurfaceUnauthenticated` |
| `GET /healthz`         | never 401 — an external monitor must probe liveness without a token        | `TestRouterPhase16SurfaceUnauthenticated` |
| `GET /v1/version`      | 200 + `VersionHandshake` with all four fields populated (RUN-01)           | `TestRouterVersionStillMounted`           |
| `POST /v1/auth/rotate` | 200 + `RotateResponse` with a _fresh_ token and a grace window             | `TestRouterAuthRotateStillMounted`        |
| the five Phase 17 URLs | 401 + `{"error_code":"unauthorized"}` when anonymous                       | `TestRouterPhase17EndpointsRequireBearer` |

`/healthz` is asserted as **"not 401"** rather than "200": its body depends on a `tofu` binary being on `PATH`, which is
a property of the host, not of the router. Asserting 200 would make the router test fail for an environment reason (the
same artifact `deferred-items.md` already records for `TestHealthzBothPass`).

The 401 sweep is the load-bearing one. A **404** there would mean the route was never mounted; a **2xx** would mean it
was mounted _outside_ the auth gate. Only a 401 proves both "reachable" and "authenticated" at once — which is the
entire reason all five mounts live inside the single `r.Route("/v1", …)` block.

## The `NewRouter` argument order, as implemented (for 17-07)

```go
func NewRouter(
    runnerVersion string,
    store *auth.TokenStore,
    validator *keys.Validator,
    gitMgr *git.Manager,
    runStore *runs.Store,
    q *jobq.Queue,
) http.Handler
```

Appended, never reordered — the three Phase 16 arguments keep their positions. The order is locked at compile time in
`router_test.go`:

```go
var _ func(string, *auth.TokenStore, *keys.Validator, *git.Manager, *runs.Store, *jobq.Queue) http.Handler = NewRouter
```

**17-07's one required edit** is in `cmd/runner/main.go`, which this plan left as a deliberate seam:

```go
router := httpapi.NewRouter(runnerVersion, store, keysValidator, nil, nil, nil)
```

with a `TODO(17-07)` above it. Until those nils become real dependencies: `/`, `/healthz`, `/v1/version` and
`/v1/auth/rotate` are fully functional, and the five Phase 17 endpoints answer 500 via chi's `Recoverer` (which sits
above every handler in the middleware chain, so a nil-dependency panic is a 500 and not a dead listener). Passing nils
rather than half-wiring the deps here keeps the plan boundary clean; passing nothing was not an option, because
`go build ./...` exiting 0 is a hard acceptance criterion of Task 3.

## The test seams (for 17-07 and Phase 19)

Same shape 17-06 established — **exported constructor keeps the concrete dependency, unexported core takes a minimal
method-set interface**:

```go
type runReader interface {                     // get_run.go
    Load(runID string) (runs.Meta, error)
    ReadOutput(runID string, page, pageSize int) (runs.OutputPage, error)
}
func getRunHandler(rd runReader) http.HandlerFunc

type runLister interface {                     // list_runs.go
    List(f runs.ListFilter) ([]runs.Meta, error)
}
func listRunsHandler(l runLister) http.HandlerFunc
```

The fake-store strategy the tests adopted, explicitly, so later plans can copy it:

- **`fakeRunReader`** (`get_run_test.go`) holds a `runs.Meta` + `loadErr`, a `runs.OutputPage` + `readErr`, and records
  every call: `loads []string` and `reads []readOutputCall{id, page, pageSize}`. Recording the calls is what makes the
  two most important assertions possible at all — "`Load` was never reached for a malformed id" and "`pageSize` was
  clamped to 1000 **before** the store was asked", neither of which is visible in the response body. Its `ReadOutput`
  back-fills a zero `Page`/`PageSize` from the requested values, so a test that only cares about `Lines` does not have
  to restate the pagination.
- **`fakeRunLister`** (`list_runs_test.go`) holds `metas` + `err` and records `calls []runs.ListFilter`. Every filter
  assertion is on the recorded `ListFilter`, not on the returned rows — the handler's job is to build the right filter;
  matching rows is 17-04's job and is already tested there.
- **Two distinct fake types, not one shared `fakeStore`.** They live in the same Go package, so a single type would have
  forced unused fields into both test files and coupled two independent RED cycles.
- **No `*runs.Store` is constructed in a handler test.** A real store would need a temp directory, a `meta.json` and an
  `output.log`, and would re-test 17-04. `router_test.go` is the one place that _does_ use a real store — on purpose,
  because its subject is the integration, not the branches.

## The slog capture pattern (reproducible `redaction.audit` assertions)

17-06's `redaction_audit_test.go` already provides two package-level helpers, and this plan reuses them rather than
re-rolling a capture:

```go
buf := captureSlog(t)      // swaps slog.Default() for a JSON handler over a buffer; t.Cleanup restores it
recs := records(t, buf)    // decodes every JSON log line into []map[string]any
```

Added here, in `get_run_test.go`:

```go
func auditRecords(t *testing.T, buf *bytes.Buffer) []map[string]any   // filters records() to msg == "redaction.audit"
```

The filter is what makes `len(audits) == 1` a valid assertion: `GetRun` also emits `iac_runner.run.load_failed` /
`iac_runner.run.read_output_failed` on its error paths, and under the router the OBS-01 middleware adds an
`http.request` record per call. Counting _all_ records would make the "exactly once" test brittle for reasons that have
nothing to do with redaction. Numeric fields decode as `float64` through `map[string]any`, so assertions compare against
`float64(3)`, not `3`.

## Observed `/data/runs/` permissions under the handler flow

`TestRouterGetRunServesAStoredRun` creates a run through `runs.Store.Create`, writes a line through
`OpenOutput`/`WriteLine`, serves it through the mounted `GET /v1/runs/{id}`, and then stats the tree. 17-04's chmod
enforcement held:

| Path                            | Mode observed | Expected (D-01) |
| ------------------------------- | ------------- | --------------- |
| `<runs-dir>/`                   | `0700`        | `0700`          |
| `<runs-dir>/{run_id}/`          | `0700`        | `0700`          |
| `<runs-dir>/{run_id}/meta.json` | `0600`        | `0600`          |

Asserted, not eyeballed — the modes are checked in the test, so a future change that loosens them fails the suite.

## Deviations from Plan

### 1. [Rule 2 — Missing critical] `auditRedactions` replaces the plan's inline `slog.Info`

- **Found during:** Task 1
- **Issue:** the plan's Task 1 sample code emitted its own record:
  `slog.Info("iac_runner.redaction.audit", …, "repo", meta.Repo, …)`. 17-06 had already shipped `auditRedactions` in
  `redaction_audit.go` as **the single emission point**, under the record name `redaction.audit`, with a written call
  contract naming `GetRun` as its one caller. Following the plan literally would have produced a second emission point
  with a _different_ record name — breaking the exactly-once contract, leaving `auditRedactions` still callerless, and
  leaving ROADMAP SC-10 unmet while looking superficially satisfied.
- **Fix:** `getRunHandler` calls `auditRedactions(r.Context(), id, outputPage)` once, after `ReadOutput` and before the
  response body. No inline record. `TestGetRunAuditEmittedOncePerRequest` and `TestListRunsEmitsNoAuditRecord` fence the
  contract from both sides.
- **Files modified:** `iac-runner/internal/httpapi/handlers/get_run.go`
- **Verification:** `go test ./internal/httpapi/handlers/... -run GetRun` (12/12), window 1 marked `fixed`
- **Commit:** `c5804ad`

### 2. [Rule 2 — Missing critical] The off-taxonomy `"internal"` error_code is replaced by real `ErrCode*` values

- **Found during:** Tasks 1 and 2
- **Issue:** the plan's sample code passed the literal `"internal"` as the `error_code` for three responses (the two
  `GetRun` 5xx paths and the `ListRuns` unknown-`?status=` 400). `"internal"` is not in `contract`'s D-19 taxonomy,
  which the plan's own success criteria require (`Every 4xx/5xx body carries the matching contract.ErrCode* value`);
  worse, `statusForCode("internal")` falls through to the 502 default, so the code and the status would disagree.
- **Fix:** the 5xx paths use `contract.ErrCodeApplyFailed` (500) — the same fallback `writeGitError` already uses for an
  unclassified error — and the unknown-`?status=` 400 uses `contract.ErrCodeRunInvalidDir`, the taxonomy's request-shape
  slot that 17-06 established for malformed bodies on all three write endpoints. No new constant was added: D-20 makes
  codes additive, but `contract/types.go` is 17-02's file and a new code needs a DOCS.md row.
- **Files modified:** `get_run.go`, `list_runs.go`
- **Verification:** the three no-leak tests plus `TestListRunsUnknownStatus` assert a non-empty typed code
- **Commits:** `c5804ad`, `1e98828`

### 3. [Rule 3 — Blocker] `cmd/runner/main.go` updated to the new `NewRouter` signature

- **Found during:** Task 3
- **Issue:** `main.go` called `NewRouter(runnerVersion, store, keysValidator)`. Extending the signature broke
  `go build ./...`, which is Task 3's acceptance criterion and plan verification step 1. `main.go` is not in this plan's
  `files_modified` (17-07 owns the startup wiring).
- **Fix:** the call site now passes `nil, nil, nil` for the three new dependencies, with a `TODO(17-07)` comment
  spelling out exactly which arguments 17-07 must replace and what the interim behavior is. This is the minimum edit
  that restores the build without doing 17-07's work.
- **Files modified:** `iac-runner/cmd/runner/main.go`
- **Verification:** `go build ./...` exits 0
- **Commit:** `14b51ac`

### 4. [Rule 2 — Missing critical] `internal/httpapi/router_test.go` added (not in `files_modified`)

- **Found during:** Task 3
- **Issue:** Task 3's `<behavior>` block lists eight observable route/auth behaviors, but its only acceptance criteria
  are greps over `router.go` plus `go build`. A grep cannot tell a mounted route from a commented one, and
  `internal/httpapi` had **no test file at all** — so the plan's own truth "the Phase 16 surface still behaves exactly
  as before" would have shipped as an assumption.
- **Fix:** added `router_test.go` with 6 top-level tests covering all eight behaviors plus one end-to-end
  `GET /v1/runs/{id}` over a real `runs.Store`.
- **Files created:** `iac-runner/internal/httpapi/router_test.go`
- **Verification:** `go test ./internal/httpapi/ -count=1` — 6/6 pass (10 with sub-tests)
- **Commit:** `14b51ac`

### 5. [Rule 1 — Bug in the plan's verification, not the code] Five grep-shaped acceptance criteria are unsatisfiable

The known phase-wide defect (hit in 17-04, 17-05, 17-06) recurred. In every case the **code is correct and
byte-identical to the plan's `<interfaces>` block**; the regex cannot match. Verified with corrected patterns and, where
a signature is involved, with a compile-time lock — which is strictly stronger than a grep, since it fails the build
rather than a check.

| Criterion (as written)                                                    | Why it can never match                                                                                        | How it was actually verified                                                                                             |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `^func GetRun\(store \*runs\.Store\) http\.HandlerFunc$`                  | Go puts `{` on the signature line, so `$` cannot follow `Func`                                                | `…HandlerFunc \{$` → 1 hit + `var _ func(*runs.Store) http.HandlerFunc = GetRun`                                         |
| `^func ListRuns\(store \*runs\.Store\) http\.HandlerFunc$`                | same                                                                                                          | `…HandlerFunc \{$` → 1 hit + `var _ func(*runs.Store) http.HandlerFunc = ListRuns`                                       |
| `^func NewRouter\(.*gitMgr.*runStore.*q \*jobq\.Queue.*\) http\.Handler$` | The signature is six lines (a single line would be ~160 chars, over the repo's 120-char convention)           | `var _ func(string, *auth.TokenStore, *keys.Validator, *git.Manager, *runs.Store, *jobq.Queue) http.Handler = NewRouter` |
| `…\|r\.Get\("/runs"\)` must make the mount count 5                        | The real call is `r.Get("/runs", handlers.ListRuns(runStore))` — `"` is followed by `,`, not `)`. Count is 4. | `r\.Get\("/runs",` → the corrected 5-way alternation returns **5**                                                       |
| `r\.Get\("/version"\|r\.Post\("/auth/rotate"\)` must return 2             | Same `,`-vs-`)` defect on the rotate arm. Count is 1.                                                         | `r\.Get\("/version",\|r\.Post\("/auth/rotate",` returns **2**                                                            |

Plan verification step 9 (`grep -c 'func writeError' …/*.go \| grep -c ':1'`) is also mis-shaped — `grep -c` over a glob
prints a `path:count` line for _every_ file including the zeros, so the outer count is meaningless. Verified directly
instead: `grep -c 'func writeError' internal/httpapi/handlers/*.go | grep -v ':0'` returns exactly
`internal/httpapi/handlers/write_error.go:1` — one definition, in 17-06's file. This plan added no second mapping.

**Total deviations:** 4 auto-fixed (2 × Rule 2 correctness, 1 × Rule 3 blocker, 1 × Rule 2 missing verification) plus 1
documented plan-verification defect. **Impact:** all four fixes strengthen the delivered contract — the SC-10 obligation
is discharged rather than superficially satisfied, every error body carries a real taxonomy code, the build compiles,
and the Phase 16 non-regression is a test rather than a claim. No behavior the plan asked for was dropped.

### Plan file-count note

`files_modified` lists 5 files; 7 changed (`+ router_test.go`, `+ cmd/runner/main.go`), per deviations 3 and 4.

## Verification Results

Run in `golang:1.25-alpine` with the host module cache mounted and a `tofu` stub on `PATH` (no Go toolchain on this host
— see `deferred-items.md`).

| Check                                                | Result                                           |
| ---------------------------------------------------- | ------------------------------------------------ |
| `go build ./...`                                     | exit 0                                           |
| `go vet ./...`                                       | exit 0                                           |
| `go test ./internal/httpapi/... -count=1`            | ok — `httpapi` 0.046s, `handlers` 0.024s         |
| `go test ./... -count=1`                             | exit 0, every package ok                         |
| Handler top-level tests (plan wanted ≥ 28)           | **67** (`--- PASS` count, `-v`)                  |
| `internal/httpapi` top-level tests                   | **6** (10 with sub-tests) — new package coverage |
| One `writeError` definition in the package           | `write_error.go:1`, nothing else                 |
| `gofmt -l` on the six files this plan wrote/modified | clean                                            |

Side effect worth recording: `router.go` was on `deferred-items.md`'s pre-existing `gofmt` drift list. It is formatted
now, so that list is down to five files (`cmd/runner/version.go`, `internal/auth/token.go`,
`internal/httpapi/handlers/healthz_test.go`, `internal/keys/validator_test.go`,
`internal/logging/scrubbing_handler_test.go`). The `hadolint` DL3003 finding on `iac-runner/Dockerfile:40` remains
17-07's, untouched.

## Task Commits

1. **Task 1: `GET /v1/runs/{id}`** (TDD)
   - RED `f52b456` — `test(17-08)`: 12 tests + skeleton; verdict `RED_EVIDENCE_OK`, target `TestGetRunSuccess`
   - GREEN `c5804ad` — `feat(17-08)`: `GetRun`, `getRunHandler`, `runDetail`, `formatRunTime`, `parsePositiveInt`, and
     the `auditRedactions` call
2. **Task 2: `GET /v1/runs`** (TDD)
   - RED `dcf6b36` — `test(17-08)`: 11 tests + skeleton; verdict `RED_EVIDENCE_OK`, target `TestListRunsDefaultLimit`
   - GREEN `1e98828` — `feat(17-08)`: `ListRuns`, `listRunsHandler`, `runSummary`, `isKnownRunStatus`, `positiveInt`
3. **Task 3: router mount** (non-TDD)
   - `14b51ac` — `feat(17-08)`: the six-argument `NewRouter`, the five mounts, `router_test.go`, and the `main.go`
     signature bridge

No REFACTOR commit: each GREEN landed in its final shape with the suite green, so a no-op `refactor(...)` would have
been noise.

## TDD Gate Compliance

| Cycle                        | RED       | GREEN     | REFACTOR | Notes                                                              |
| ---------------------------- | --------- | --------- | -------- | ------------------------------------------------------------------ |
| Task 1 (`GET /v1/runs/{id}`) | `f52b456` | `c5804ad` | —        | `RED_EVIDENCE_OK`, target `TestGetRunSuccess` (12/12 failed)       |
| Task 2 (`GET /v1/runs`)      | `dcf6b36` | `1e98828` | —        | `RED_EVIDENCE_OK`, target `TestListRunsDefaultLimit` (9/11 failed) |
| Task 3 (router mount)        | n/a       | `14b51ac` | —        | `type="auto"`, not `tdd="true"` — no RED gate required             |

Both RED phases were validated with `gsd-tools check tdd-red-evidence` after translating `go test -json` into the TAP
shape the checker parses (it is written against the Node test runner; the translation is one line per top-level Go test,
in run order, rendered from the actual run — not hand-written). Each RED failed on an assertion for the planned
behavior; the skeletons published `GetRun`/`getRunHandler`/`runReader` and `ListRuns`/`listRunsHandler`/`runLister` so
the suites compiled, which is what keeps a Go RED out of the `fixture_or_load_failure` verdict.

Task 2's RED shows 9 of 11 failing rather than 11: `TestListRunsCarriesNoOutputLines` and
`TestListRunsEmitsNoAuditRecord` are absence assertions, and the 501 skeleton emitted neither a body nor a record, so
they passed vacuously. Both are meaningful against the real handler in GREEN, and the target test failed as required —
`RED_EVIDENCE_OK` is on the target, not on the whole suite.

## Broken Windows

**Closed:** window 1 (`unmet-truth`, `redaction_audit.go:51`) → `fixed`. `auditRedactions` has a production caller and
ROADMAP SC-10 is observable end-to-end. `open_count: 0`.

**Opened:** none. No stubs, no skipped tests, no unrun `<verify>` blocks in this plan.

## Known Stubs

None. `cmd/runner/main.go`'s three `nil` arguments are not a stub in this plan's deliverable — they are the documented
plan boundary with 17-07, which lists `main.go` in its own `files_modified` and owns the construction of those
dependencies. The `TODO(17-07)` comment names the exact edit.

## Next Phase Readiness

`17-07` is the last plan of the phase. It must:

1. Replace `httpapi.NewRouter(runnerVersion, store, keysValidator, nil, nil, nil)` in `cmd/runner/main.go` with the real
   `*git.Manager`, `*runs.Store` and `*jobq.Queue` — the argument order is compile-locked in `router_test.go`.
2. Fix the `hadolint` DL3003 finding on `iac-runner/Dockerfile:40` (assigned to it in `deferred-items.md`).

After that, every ROADMAP success criterion of Phase 17 is reachable over HTTP and Phase 19 can verify live.

## Self-Check: PASSED

- `iac-runner/internal/httpapi/handlers/get_run.go` — FOUND
- `iac-runner/internal/httpapi/handlers/get_run_test.go` — FOUND
- `iac-runner/internal/httpapi/handlers/list_runs.go` — FOUND
- `iac-runner/internal/httpapi/handlers/list_runs_test.go` — FOUND
- `iac-runner/internal/httpapi/router_test.go` — FOUND
- `iac-runner/internal/httpapi/router.go` — FOUND (modified)
- `iac-runner/cmd/runner/main.go` — FOUND (modified)
- Commits `f52b456`, `c5804ad`, `dcf6b36`, `1e98828`, `14b51ac` — all FOUND in `git log`
- All task `<acceptance_criteria>` re-run and passing (5 verified with corrected patterns, see Deviation 5)
- Plan-level `<verification>` steps 1–5 and 7–9 re-run and passing; step 6 documented as a deviation
