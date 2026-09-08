---
phase: 17-git-integration-apply-job-system
plan: 04
subsystem: infra
tags: [go, filesystem, flock, jsonl, redaction, retention, slog, tdd]

# Dependency graph
requires:
  - phase: 17-git-integration-apply-job-system (plan 02)
    provides:
      contract.RunKind / RunStatus / pagination + list-limit constants, runs.NewRunID, runs.IsValidRunID,
      runs.ValidateDir
  - phase: 16-scaffold-auth-state-backends-healthcheck
    provides:
      internal/auth's CreateTemp -> Sync -> Chmod -> Rename atomic-write pattern, internal/logging's SEC-02 `<redacted>`
      marker, slog.SetDefault wiring in cmd/runner/main.go
provides:
  - runs.Store — Create/Load/Update/List/Dir over /data/runs/{run_id}/meta.json, flock-serialized and atomically written
  - runs.Meta — the persisted RUN-04 field set, json tags aligned with contract.RunDetail / RunSummary
  - runs.OutputWriter + Store.OpenOutput/WriteLine/Close — verbatim JSONL {ts,stream,line} capture to output.log
  - runs.Store.ReadOutput + runs.OutputPage — bounded, read-time-redacted page with an exact TotalLines and a Redactions
    count
  - runs.Redact — SEC-03 per-token pattern redaction with a replacement count
  - runs.Store.SweepInterrupted / Rotate / StartRetentionTicker — boot sweep (D-02) and disk bound (D-25, SC-11)
affects: [17-05 tofu job execution, 17-06 HTTP run handlers, 17-07 startup wiring + DOCS]

# Actuals (#2632) — plan carried no `estimate` block; recorded for calibration anyway.
actuals:
  tokens: 15182
  tasks: 3
  commits: 6
plan_head_before: 88ea34829e3043444ac7b7104d0fafde946079a5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "flock on a dedicated .meta.lock sibling file, never on the atomically-renamed target"
    - "windowCollector: count every line, unmarshal + redact only the requested page"
    - "Scanner-with-enlarged-buffer primary read path, bufio.Reader.ReadString fallback on bufio.ErrTooLong"
    - "errors.Join over a directory walk so one corrupt run cannot abort a maintenance pass"
    - "Go TDD RED via API-shaped stubs returning a not-implemented sentinel, so the package compiles and tests fail on
      assertions"

key-files:
  created:
    - iac-runner/internal/runs/store.go
    - iac-runner/internal/runs/store_test.go
    - iac-runner/internal/runs/output.go
    - iac-runner/internal/runs/output_test.go
    - iac-runner/internal/runs/redact.go
    - iac-runner/internal/runs/redact_test.go
    - iac-runner/internal/runs/retention.go
    - iac-runner/internal/runs/retention_test.go
  modified: []

key-decisions:
  - "flock lives on a dedicated .meta.lock file: writeMeta's atomic rename replaces meta.json's inode, so a lock held on
    the old fd would protect nothing"
  - "Load collapses missing id, invalid id and corrupt meta.json into one ErrRunNotFound — a corrupt run is
    operationally identical to a missing one at the API boundary"
  - "Redact tokenizes on the tofu/shell punctuation set (space, tab, quotes, =, comma, parens, brackets, braces, colon,
    semicolon) and re-tests a token together with its trailing '=' run so a base64-padded AWS key is still caught"
  - "ReadOutput surfaces an unparseable record as its raw text (redacted) rather than dropping it — the last line of a
    running job is routinely half-flushed"
  - "SweepInterrupted and Rotate walk os.ReadDir directly instead of List, because List applies the RUN-05 response caps
    which would silently leave older runs stale/undeleted"
  - "SweepInterrupted leaves ErrorCode empty: an interrupted run did not fail, so there is no tofu error to attribute"
  - "Store gained two additive read-only accessors (RunsDir, Now) for the cross-package consumers in 17-05/17-06/17-07"

patterns-established:
  - "Lock-then-read: Update acquires LOCK_EX before Load so the read-modify-write has no lost-update window"
  - "Read-time-only redaction: nothing in the write path calls Redact, asserted by a test that greps the on-disk bytes
    for the raw secret"
  - "Injected clock (now func() time.Time, nil => time.Now) so every filesystem test is deterministic and sleep-free"

requirements-completed: [SEC-03, OBS-02, OBS-03, RUN-04]

coverage:
  - id: D1
    description:
      "Every run leaves a durable record: /data/runs/{run_id}/meta.json (dir 0700, file 0600) round-trips the full
      RUN-04 field set and survives a restart because the file, not memory, is the source of truth"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreCreateLoadRoundTrip"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreCreateLoadRoundTripKeepsExitCodeZero"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreCreateSetsModes"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreLoadUnknownIDReturnsErrRunNotFound"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two goroutines updating the same run's metadata never lose a write and never expose a torn meta.json"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreUpdateConcurrent (50 goroutines, -race)"
        status: pass
      - kind: unit
        ref:
          "iac-runner/internal/runs/store_test.go#TestStoreUpdateNoTornReadUnderConcurrentLoad (200 write/read
          iterations, -race)"
        status: pass
    human_judgment: false
  - id: D3
    description:
      "GET /v1/runs listing semantics: newest-first ordering, repo and status filters, default 20 / max 100 caps, and
      non-run or corrupt directories skipped instead of failing the listing"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreListOrdersByStartedAtDesc"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/store_test.go#TestStoreListFiltersAndCaps"
        status: pass
    human_judgment: false
  - id: D4
    description:
      "The complete raw tofu output is preserved verbatim as JSONL {ts,stream,line} on disk — no line truncated,
      quotes/newlines/10 KB and 8 MiB+ lines all round-trip — while stdout and stderr writers never interleave
      mid-object"
    requirement: OBS-02
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestWriteLineProducesJSONL"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestWriteLineNoTruncation"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestReadOutputHandlesLineBeyondScannerCeiling"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestWriteLineConcurrentStreams (-race)"
        status: pass
    human_judgment: false
  - id: D5
    description:
      "The API never returns more than a bounded page of output: pages are clamped to contract.DefaultOutputPageSize /
      MaxOutputPageSize, TotalLines counts the whole file, a past-the-end page is empty rather than an error, and a run
      with no output yet is an empty page"
    requirement: OBS-03
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestReadOutputPagination"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestReadOutputClampsPageSize"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/output_test.go#TestReadOutputMissingFileIsEmptyPage"
        status: pass
    human_judgment: false
  - id: D6
    description:
      "Credential-shaped strings (R2 access keys, AWS secret keys, PEM private-key blocks) are replaced with <redacted>
      before they leave the process, the count is reported for the redaction.audit record, and the raw bytes stay on
      disk (D-08 read-time-only)"
    requirement: SEC-03
    verification:
      - kind: unit
        ref:
          "iac-runner/internal/runs/redact_test.go#TestRedact (10 cases incl. 19/41-char boundaries and a two-secret
          line)"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/redact_test.go#TestRedactIsLosslessForSecretFreeLines"
        status: pass
      - kind: unit
        ref:
          "iac-runner/internal/runs/output_test.go#TestReadOutputRedactsAndCounts (asserts the on-disk file still holds
          the raw secrets)"
        status: pass
    human_judgment: false
  - id: D7
    description:
      "A run still marked running when the container died is reported as interrupted — not failed, not perpetually
      running — and a corrupt sibling run cannot block the sweep"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/retention_test.go#TestSweepInterruptedTransitionsRunningOnly"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/retention_test.go#TestSweepInterruptedSurvivesCorruptRun"
        status: pass
    human_judgment: false
  - id: D8
    description:
      "Run directories older than the retention window are deleted automatically on a retention/4 cadence (1-minute
      floor), and a queued or running run is never deleted regardless of age"
    requirement: OBS-02
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs/retention_test.go#TestRotateDeletesOldFinishedRuns"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/retention_test.go#TestRotateSkipsActiveRuns"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/retention_test.go#TestRotateUsesStartedAtWhenFinishedAtNil"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/runs/retention_test.go#TestTickIntervalCadenceAndFloor"
        status: pass
      - kind: unit
        ref:
          "iac-runner/internal/runs/retention_test.go#TestStartRetentionTickerStops +
          TestStartRetentionTickerStopsOnContextCancel (-race)"
        status: pass
    human_judgment: false
  - id: D9
    description:
      "The ticker actually reclaims disk on a real 6-hour cadence in a long-lived add-on container, and the
      redaction.audit slog record reaches the operator's log"
    verification: []
    human_judgment: true
    rationale:
      "The retention/4 cadence is unit-tested only at the tickInterval level — observing a real 6h tick and the emitted
      runs.rotated / redaction.audit records requires a live add-on running longer than a test can wait. The audit
      record itself is emitted by 17-06's handler, which does not exist yet."

# Metrics
duration: 12min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 04: Durable Run Store, JSONL Output Capture, SEC-03 Redaction and Retention Summary

**File-backed run history under `/data/runs/{run_id}/`: flock-serialized atomic `meta.json` writes, verbatim JSONL
output capture with read-time credential redaction and bounded pagination, a boot-time `running` → `interrupted` sweep,
and a retention/4 rotation ticker — 25 tests, all green under `-race`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-08T10:50:27Z
- **Completed:** 2026-09-08T11:02:27Z
- **Tasks:** 3 (all `tdd="true"`)
- **Files created:** 8 (4 source, 4 test)

## Accomplishments

- **`runs.Store`** persists the full RUN-04 metadata set to `/data/runs/{run_id}/meta.json` (dir `0700`, file `0600`),
  serializes every read-modify-write through an exclusive `flock`, and writes atomically via
  `CreateTemp → Sync → Chmod → Rename`. 50 concurrent `Update` calls all land; a reader looping `Load` against a looping
  writer never observes a parse error.
- **`runs.List`** answers the RUN-05 shape (newest-first, `repo`/`status` filters, default 20 / max 100 from the shared
  contract constants) and skips non-run directories and corrupt runs rather than blanking the operator's history.
- **JSONL output capture** writes `{"ts","stream","line"}` per captured line, append-only, mutex-guarded so tofu's two
  capture goroutines cannot interleave mid-object. No truncation anywhere: a 10 KB line, a line with embedded quotes and
  newlines, and a line larger than the 8 MiB scanner ceiling all round-trip byte-exact.
- **`ReadOutput`** returns a clamped page with an exact whole-file `TotalLines` and a per-page `Redactions` count,
  applying SEC-03 redaction at read time only — a test greps the on-disk `output.log` and asserts the raw secrets are
  still there (the D-08 invariant).
- **`SweepInterrupted`** turns every stale `running` run into `interrupted` with a `FinishedAt` stamp, and **`Rotate` /
  `StartRetentionTicker`** bound disk usage on the ROADMAP SC-11 cadence without ever deleting a live run.

## Task Commits

Each task ran the full RED → GREEN cycle; every RED phase was validated with `gsd-tools check tdd-red-evidence` and
returned `RED_EVIDENCE_OK` before any implementation was written.

1. **Task 1: Store — meta.json with flock-protected atomic updates, plus List**
   - `fbc462d` (test) — 8 tests + API-shaped stubs. RED: `TestStoreCreateLoadRoundTrip` failed on its own assertion (14
     discovered, 8 failed).
   - `433fe79` (feat) — implementation. GREEN: all pass under `-race`.
2. **Task 2: JSONL output capture + SEC-03 read-time redaction + pagination**
   - `2af82f9` (test) — 9 output tests + a 10-case redaction table + stubs. RED: `TestReadOutputRedactsAndCounts` failed
     on its own assertion (25 discovered, 9 failed).
   - `d6a4716` (feat) — implementation. GREEN: all pass under `-race`.
3. **Task 3: Boot interrupted sweep + age-based rotation + retention ticker**
   - `56e2ed9` (test) — 8 tests + stubs. RED: `TestSweepInterruptedTransitionsRunningOnly` failed on its own assertion
     (33 discovered, 6 failed).
   - `a0e7f9f` (feat) — implementation. GREEN: all pass under `-race`.

No REFACTOR commit was needed on any task — the GREEN implementations landed in their final shape, and per
`references/tdd.md` a REFACTOR commit is only made when changes are actually made.

## TDD Gate Compliance

| Task | RED         | GREEN       | REFACTOR      | RED evidence verdict                     | Status |
| ---- | ----------- | ----------- | ------------- | ---------------------------------------- | ------ |
| 1    | ✓ `fbc462d` | ✓ `433fe79` | — (no change) | `RED_EVIDENCE_OK` / `target_test_failed` | Pass   |
| 2    | ✓ `2af82f9` | ✓ `d6a4716` | — (no change) | `RED_EVIDENCE_OK` / `target_test_failed` | Pass   |
| 3    | ✓ `56e2ed9` | ✓ `a0e7f9f` | — (no change) | `RED_EVIDENCE_OK` / `target_test_failed` | Pass   |

No gate violations. Note on the Go RED shape: a Go test file cannot compile against types that do not exist, so each RED
commit carries the API surface as declarations whose methods return a `not implemented` sentinel. That is what makes the
failure an _assertion_ failure on the planned behavior rather than a compile/load crash — the distinction
`check tdd-red-evidence` exists to enforce (#3770). No behavior was implemented in any RED commit.

## Files Created/Modified

- `iac-runner/internal/runs/store.go` — `Meta`, `ListFilter`, `Store`, `NewStore`, `Dir`, `Create`, `Load`, `Update`,
  `List`, plus the `RunsDir`/`Now` accessors and the `writeMeta` atomic-write helper.
- `iac-runner/internal/runs/store_test.go` — 8 tests: round-trip (incl. `exit_code: 0` vs `null`), 0700/0600 modes,
  `ErrRunNotFound` for unknown/invalid/corrupt, 50-goroutine concurrent `Update`, writer/reader torn-read loop,
  descending order, filters + caps + skip-bad-dirs.
- `iac-runner/internal/runs/output.go` — `OutputLine`, `OutputPage`, `OutputWriter`, `OpenOutput`, `WriteLine`, `Close`,
  `ReadOutput`, plus the `windowCollector` and the two read paths.
- `iac-runner/internal/runs/output_test.go` — 9 tests incl. the 8 MiB+ line and the D-08 raw-file assertion.
- `iac-runner/internal/runs/redact.go` — `Redact`, the two anchored SEC-03 regexes, the PEM whole-line rule, and the
  lossless tokenizer.
- `iac-runner/internal/runs/redact_test.go` — 10-case table + a losslessness test.
- `iac-runner/internal/runs/retention.go` — `SweepInterrupted`, `Rotate`, `tickInterval`, `StartRetentionTicker`.
- `iac-runner/internal/runs/retention_test.go` — 8 tests with an injected clock, no sleeps longer than 150 ms.

## Final exported API (consumed by 17-05, 17-06, 17-07)

```go
package runs

// store.go
type Meta struct {
    RunID, Repo, Dir string
    Kind             contract.RunKind
    Status           contract.RunStatus
    ExitCode         *int
    StartedAt        time.Time
    FinishedAt       *time.Time
    ErrorCode        string
    PlanFile         string
}
type ListFilter struct { Repo string; Status contract.RunStatus; Limit int }
var ErrRunNotFound error

func NewStore(runsDir string, now func() time.Time) (*Store, error)
func (s *Store) RunsDir() string                 // additive — startup log records
func (s *Store) Now() time.Time                  // additive — shared clock for cross-package callers
func (s *Store) Dir(runID string) string         // "" for an invalid run id
func (s *Store) Create(m Meta) error
func (s *Store) Load(runID string) (Meta, error)
func (s *Store) Update(runID string, mutate func(*Meta) error) (Meta, error)
func (s *Store) List(f ListFilter) ([]Meta, error)

// output.go
type OutputLine struct { TS, Stream, Line string }   // json: ts, stream, line
type OutputPage struct { Lines []string; Page, PageSize, TotalLines, Redactions int }
func (s *Store) OpenOutput(runID string) (*OutputWriter, error)
func (w *OutputWriter) WriteLine(stream, line string) error
func (w *OutputWriter) Close() error
func (s *Store) ReadOutput(runID string, page, pageSize int) (OutputPage, error)

// redact.go
func Redact(line string) (string, int)

// retention.go
func (s *Store) SweepInterrupted() (int, error)
func (s *Store) Rotate(maxAge time.Duration) (int, error)
func (s *Store) StartRetentionTicker(ctx context.Context, retention time.Duration) func()
```

**17-06 still owes the `redaction.audit` slog record.** This package deliberately does no logging on the read path — it
only _reports_ `OutputPage.Redactions`. The handler owns the request-scoped logger, so the audit obligation of SEC-03 is
only half-discharged until 17-06 emits it. That is documented in `ReadOutput`'s doc comment so it cannot be lost.

**17-07 wiring contract:** call `SweepInterrupted()` once before the HTTP listener starts, then `Rotate(retention)` once
explicitly (so the boot reclaim is its own observable log record), then `StartRetentionTicker(ctx, retention)`. The
ticker deliberately does NOT rotate on start.

## The tokenization rule `Redact` ended up using

REQUIREMENTS.md specifies the SEC-03 patterns in anchored form (`^[A-Z0-9]{20}$`, `^[A-Za-z0-9/+=]{40}$`), so they
describe **whole tokens**, not substrings. `Redact` therefore:

1. **PEM first, whole-line.** If the line contains `-----BEGIN` anywhere, the entire line becomes `<redacted>` and the
   count is 1. There is no safe partial redaction of key material, and a PEM header means the surrounding bytes are key
   material.
2. **Otherwise, single-pass segmentation.** The line is split into alternating delimiter-runs and token-runs over the
   delimiter set `" \t\"'=,()[]{}:;"` — the punctuation tofu and shell-style output puts around values, so a credential
   in `key = "V"`, `[id=V]` or `{V, V}` is isolated as its own token. Every segment's text is kept, so concatenation
   reproduces the input byte-for-byte; that losslessness is asserted directly (`TestRedactIsLosslessForSecretFreeLines`,
   incl. tabs, runs of spaces, trailing spaces, and a delimiters-only line).
3. **`=` is a delimiter, with a re-test.** `=` had to be a delimiter for `AWS_SECRET_ACCESS_KEY=<key>` to expose the key
   as a token — but `=` is also a member of the AWS pattern's character class (base64 padding). So when a token is
   followed immediately by a pure-`=` delimiter run, the token **plus that run** is re-tested against the 40-char
   pattern before the bare token is; a padded key is caught and the padding is consumed into the marker.
4. **Boundaries are exact.** 19 and 41 uppercase characters pass through untouched (0 redactions); 20 and 40 do not.
   Each matching token contributes exactly 1 to the count, so a two-secret line reports 2.

## The long-line read path, as observed

Both paths exist and both are exercised by the test suite:

- **Primary — `bufio.Scanner`** with `sc.Buffer(make([]byte, 0, 64*1024), 8*1024*1024)`. 64 KiB start (the common tofu
  line is far under it), growing on demand to an 8 MiB ceiling. `TestWriteLineNoTruncation`'s 10 KB line and all the
  pagination tests go through here.
- **Fallback — `bufio.Reader.ReadString('\n')`**, entered only when the scanner returns `bufio.ErrTooLong`. The partial
  pass is discarded via `windowCollector.reset()` and the file is re-read from the top, so no line is counted twice.
  `ReadString` has no per-line limit at all, which is the honest read-side counterpart of the write side's no-truncation
  guarantee.
- **Observed:** `TestReadOutputHandlesLineBeyondScannerCeiling` writes an `8 MiB + 1 KiB` line followed by a short one,
  then asserts `TotalLines == 2`, a byte-exact `len()` on the huge line, and the correct content of the line after it.
  That assertion can only be satisfied by the fallback — the scanner cannot return that line at all — so the retry path
  is proven, not assumed. Cost of the fallback is one allocation per line for the whole file; it only triggers for a
  genuinely pathological run.

## Decisions Made

1. **The `flock` goes on `.meta.lock`, not on `meta.json`.** `writeMeta` finishes with `os.Rename`, which replaces
   `meta.json`'s inode. A lock held on the old file descriptor would be a lock on an unlinked inode that no subsequent
   opener can see — it would protect nothing while looking correct. The dedicated lock file is never renamed, so every
   participant locks the same inode for the lifetime of the run directory. This is the subtle bug the design avoids, and
   the reasoning is in the code.
2. **`Load` collapses three failures into `ErrRunNotFound`.** Missing file, syntactically invalid run id, and corrupt
   JSON all wrap the same sentinel. From the API's point of view a corrupt `meta.json` is operationally identical to a
   missing run, and returning `json: cannot unmarshal …` to a caller tells them nothing actionable while leaking the
   on-disk layout. The operator still sees the real cause — the raw file is right there under `/data`.
3. **`Update` reads inside the lock.** Loading before acquiring `LOCK_EX` would reopen exactly the lost-update window
   the lock exists to close.
4. **The maintenance passes walk `os.ReadDir`, not `List`.** `List` applies the RUN-05 _response_ caps (20/100). A
   capped sweep would leave older runs stale forever; a capped rotation would stop reclaiming disk once history passed
   100 runs. Same walk, deliberately different bound.
5. **An unparseable output record is surfaced as its raw text (redacted), not dropped.** The final line of a running job
   is routinely half-flushed; dropping it would read to the operator as missing output.
6. **`SweepInterrupted` leaves `ErrorCode` empty.** The run was cut short, it did not fail — there is no tofu error to
   attribute, and inventing one would send the operator hunting for a nonexistent failure. `status: interrupted` carries
   the whole diagnosis.
7. **`Rotate` skips `queued` and `running` unconditionally.** A live run's writer holds an open fd on `output.log`;
   removing the directory under it would silently discard the output of a job that is still executing.
8. **The ticker's stop function is `sync.Once`-guarded and the ticker does not rotate on start.** `main.go`'s shutdown
   exercises both exits (context cancel _and_ explicit stop), so an unguarded second `close` would panic during
   shutdown; and 17-07 calls `Rotate` once explicitly at boot so the startup reclaim is a distinct log record rather
   than an invisible side effect of the first tick.
9. **No new module dependency.** `syscall.Flock` is stdlib and the add-on is an amd64 Linux container (`arch: [amd64]`),
   so the Linux-only call is not a portability problem. `git diff -- iac-runner/go.mod iac-runner/go.sum` is empty,
   satisfying plan verification item 6.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 2 acceptance-criterion regex is unsatisfiable as written**

- **Found during:** Task 2 (JSONL output capture + redaction)
- **Issue:** The criterion `grep -E '^func Redact\(line string\) \(string, int\)$'` anchors the end of line immediately
  after the return list. No valid Go function declaration can match it — the opening `{` is required on the same line —
  so the check can never pass regardless of the implementation.
- **Fix:** Verified the criterion's actual intent (the exact signature is present and unchanged) with
  `grep -nE '^func Redact\(line string\) \(string, int\) \{$'`, which matches at `redact.go:65`. The signature is
  byte-identical to the plan's `<interfaces>` block; only the impossible `$` anchor was relaxed.
- **Files modified:** none (verification-only correction)
- **Verification:** `grep -nE '^func Redact\(line string\) \(string, int\) \{$' internal/runs/redact.go` → line 65. All
  11 other Task 2 criteria pass exactly as written.
- **Committed in:** n/a (no code change)

**2. [Rule 2 - Missing Critical] Two additive `Store` accessors for cross-package consumers**

- **Found during:** Task 1 (Store)
- **Issue:** `retention.go` and `output.go` share the package and reach `s.now` / `s.runsDir` directly, but 17-05's job
  runner, 17-06's handlers and 17-07's startup wiring live in _other_ packages and cannot. Without an accessor, 17-07
  cannot log the runs directory it is sweeping, and 17-06 cannot stamp responses from the same clock the store persists
  with — a test with an injected clock and a handler using `time.Now` would silently disagree.
- **Fix:** Added `func (s *Store) RunsDir() string` and `func (s *Store) Now() time.Time`, both read-only, both
  documented as existing for the downstream plans.
- **Files modified:** `iac-runner/internal/runs/store.go`
- **Verification:** `go build ./...` and `go vet ./...` clean; the Task 1 method-count criterion still returns exactly 6
  (neither name matches the `(Dir|Create|Load|Update|List)` alternation).
- **Committed in:** `433fe79` (Task 1 GREEN commit)

**3. [Rule 2 - Missing Critical] Three tests beyond the plan's minimums**

- **Found during:** Tasks 1-3
- **Issue:** Three behaviors in the plan's `<behavior>` and `<verification>` lists had no test that would catch a
  regression: `exit_code: 0` surviving the round-trip distinctly from `null` (the contract comment calls the difference
  out explicitly), `ReadOutput` on an invalid run id, and the `retention/4` cadence + floor arithmetic itself (only the
  ticker's _stop_ was testable in a short window).
- **Fix:** Added `TestStoreCreateLoadRoundTripKeepsExitCodeZero`, `TestReadOutputUnknownRunIsNotFound`, and
  `TestTickIntervalCadenceAndFloor` (which drove extracting the cadence into a testable `tickInterval` helper), plus
  `TestStartRetentionTickerStopsOnContextCancel` for the second shutdown path.
- **Files modified:** `store_test.go`, `output_test.go`, `retention_test.go`
- **Verification:** 25 tests total (plan minimum: 7 + 5 + 5 = 17), all pass under `-race`.
- **Committed in:** `fbc462d`, `2af82f9`, `56e2ed9` (the respective RED commits)

---

**Total deviations:** 3 auto-fixed (1 blocking plan-artifact defect, 2 missing-critical additions) **Impact on plan:**
No scope creep and no behavior outside the plan's `<interfaces>` contract. The one blocking item was a defect in the
plan's own verification regex, not in the code; the two additions close gaps that would otherwise have surfaced as
breakage in 17-05/17-06.

## Issues Encountered

- **No `go` binary on the host.** As established by the previous plan in this wave, all Go work ran inside
  `golang:1.25-alpine` with the host module and build caches bind-mounted, and nothing was installed on the host.
  `-race` additionally needs a C toolchain, so a thin derived image (`golang:1.25-alpine` + `gcc musl-dev`) was built
  once for the run. Resolved; no repo change.
- **`TestHealthzBothPass` fails in a bare container.** Confirmed environmental, not a regression: the test probes for a
  `tofu` binary on `PATH`. With a stub `tofu` on `PATH`, `go test ./...` reports **zero** failures across every package.
  Plan verification item 4 therefore holds; the failure is a property of the container, not of this plan.
- **The RED-evidence classifier parses TAP, not `go test` output.** `check tdd-red-evidence` expects `not ok N - <name>`
  lines plus `# tests/# pass/# fail` counters. A throwaway `go test -v` → TAP converter was used in the scratchpad to
  feed it. Resolved; no repo change, and worth remembering for the remaining Go TDD plans in this phase.

## User Setup Required

None — this package is filesystem-only. No external service, credential, or environment variable is involved.

## Next Phase Readiness

**Ready for 17-05 (tofu execution) and 17-06 (HTTP handlers).** Both consume the exported surface listed above and
neither needs to touch this package's internals.

Open obligations carried forward, all of them explicitly out of this plan's scope:

- **17-05** produces the output: it calls `OpenOutput`/`WriteLine`/`Close` and drives `Update` through
  `queued → running → succeeded|failed`, setting `PlanFile` on a successful plan run for the D-18 lookup.
- **17-06** owes the SEC-03 `redaction.audit` slog record built from `OutputPage.Redactions`, and projects `Meta` onto
  `contract.RunDetail` / `RunSummary` (a straight field-for-field copy by construction).
- **17-07** wires the boot sequence: `SweepInterrupted()` → explicit `Rotate(retention)` → `StartRetentionTicker`, all
  before the listener starts, and documents the `runs_retention_hours` behavior in DOCS.md.

No blockers.

## Self-Check: PASSED

- All 8 `key-files.created` entries verified present on disk with `[ -f ]`.
- All 6 task commits verified in `git log --oneline --all`: `fbc462d`, `433fe79`, `2af82f9`, `d6a4716`, `56e2ed9`,
  `a0e7f9f`.
- Plan `<verification>` re-run in the container: `go build ./...` exit 0, `go vet ./...` exit 0,
  `go test ./internal/runs/... -race -count=1` exit 0, `go test ./...` exit 0 with a `tofu` stub on `PATH`,
  `git diff -- iac-runner/go.mod iac-runner/go.sum` empty.
- All acceptance criteria for all three tasks re-run and passing (Task 2's criterion 9 with the corrected regex, see
  Deviation 1).
- No stubs, no skipped tests, no unrun `<verify>` blocks — nothing to record in a broken-windows ledger.

---

_Phase: 17-git-integration-apply-job-system_ _Completed: 2026-09-08_
