---
phase: 17-git-integration-apply-job-system
fixed_at: 2026-09-08T13:55:00Z
review_path: .planning/phases/17-git-integration-apply-job-system/17-REVIEW.md
iteration: 1
findings_in_scope: 17
fixed: 17
skipped: 0
status: all_fixed
---

# Phase 17: Code Review Fix Report

**Fixed at:** 2026-09-08T13:55:00Z **Source review:**
`.planning/phases/17-git-integration-apply-job-system/17-REVIEW.md` **Iteration:** 1

**Summary:**

- Findings in scope: 17 (CR-01..CR-03, WR-01..WR-14 — Info tier out of scope)
- Fixed: 17
- Skipped: 0

Every in-scope finding was confirmed correct on inspection. Two of them were fixed by the same code change as a critical
finding and are recorded against that commit (WR-09 with CR-02, WR-14 with CR-03). Nothing was applied blind: every fix
was read against the current source, and three of the review's suggested patches were deliberately changed — see
**Deviations from the suggested fixes**.

## Verification

All Go gates ran **inside the `golang:1.25-alpine` container** (no `go` on the host), with the host module cache
mounted, `gcc musl-dev` installed for `-race`, and a `tofu` stub on `PATH` for `handlers.TestHealthzBothPass`. Lint and
add-on validation ran in the **main checkout**.

| Gate                     | Where         | Result                                     |
| ------------------------ | ------------- | ------------------------------------------ |
| `go build ./...`         | container     | pass                                       |
| `go vet ./...`           | container     | pass                                       |
| `go test -race -count=2` | container     | pass (all 11 packages)                     |
| `make validate-versions` | main checkout | pass                                       |
| `make validate-addons`   | main checkout | pass                                       |
| `pre-commit run --all`   | main checkout | pass **except one pre-existing failure** ↓ |

**Pre-existing lint failure, not introduced here:** `prettier` reformats
`.planning/phases/17-git-integration-apply-job-system/17-REVIEW.md`. Verified by reverting that file to its committed
state and running `pre-commit run prettier --files <it>` on its own — it still fails. The review artifact was committed
without the hook (this repo has no installed `.git/hooks/pre-commit`), so the stated "baseline `make lint` exits 0" did
not hold for that file before my changes either. I left it untouched: it is the reviewer's artifact, not mine to
reformat. `iac-runner/DOCS.md` is prettier-clean (commit `af9d406` is the pure reflow of my own edits).

No Dockerfile was touched, so no `docker build` was required. No version was bumped, so the 3-file version scheme and
`build.yaml`'s `RUNNER_VERSION` are untouched. No branch was created, nothing was stashed, `.planning/milestone.lock`
was left alone, and **no git tag was created or pushed** during the WR-13 verification (proven below).

## Fixed Issues

### CR-01: Multi-line PEM private keys pass SEC-03 redaction almost intact

**Files modified:** `iac-runner/internal/runs/redact.go`, `iac-runner/internal/runs/output.go`,
`iac-runner/internal/runs/output_test.go` **Commit:** `8caa74f` **Status:** fixed

Redaction is now **stateful across lines**, which is the only shape that can satisfy the SEC-03 PEM rule. A `redactor`
latches on `-----BEGIN` and masks every following line until `-----END`, a line that cannot be PEM body, or a 256-line
runaway ceiling. `Redact` survives as the documented single-line entry point (and is what `redact_test.go` still
drives).

The latch is fed by `windowCollector`, which already walks every physical line in file order to compute `TotalLines` —
so no second pass and no buffering of the window's raw text was needed. Lines outside the requested page advance the
latch through a cheap `strings.Contains` path only, so the JSON decode and token scan stay proportional to the page, not
the file (the D-09/D-24 multi-megabyte-line case is unaffected).

Two regression tests drive the real `OpenOutput` → `WriteLine` → `ReadOutput` path with a full five-line OPENSSH key and
assert that **no** base64 body line survives, that the lines before and after the block are untouched, and that the raw
bytes under `/data` still hold the key (D-08). A second test requests `page=2, page_size=1` so the window _starts inside
the key body_ — the boundary case where the latch has to come from the scan of the skipped lines.

One implementation note worth keeping: the first version of the "is this a PEM body line?" test used a generic
`Word: value` regex for RFC 1421 headers, which also matched `Plan: 1 to add, 0 to change, 0 to destroy.` and kept the
latch alive past the key. The existing `TestReadOutputRedactsAndCounts` caught it. The keywords are now spelled out
(`Proc-Type`, `DEK-Info`).

### CR-02: An apply silently reuses a stale plan artifact — including one built before a `pull`

**Files modified:** `iac-runner/internal/jobq/exec.go`, `iac-runner/internal/jobq/exec_test.go`,
`iac-runner/internal/jobq/queue_test.go`, `iac-runner/internal/runs/store.go`, `iac-runner/internal/runs/store_test.go`,
`iac-runner/internal/git/manager.go`, `iac-runner/DOCS.md` **Commit:** `a19dba4` **Status:** fixed: requires human
verification (data-integrity logic, and it changes which tofu command line an apply produces)

- `runs.Meta` gains `HeadSHA`, recorded at plan time from the working tree's `HEAD` via a new exported
  `git.Manager.Head` (a thin wrapper over the existing unexported `resolveHead`).
- `priorPlanFile` skips any artifact whose `HeadSHA` does not match the current `HEAD`, logging
  `jobq.plan_artifact_stale` with both SHAs — so the pull-then-apply case now plans inline instead of applying the
  previous revision's changes.
- Freshness that cannot be established at all (git could not answer, or the plan predates the field) is also a skip,
  logged as `jobq.plan_freshness_unknown`. Inline apply is a supported D-17 mode and is the only safe default here.
- A successful apply **consumes** the artifact: the file is removed and the owning plan run's `plan_file` is cleared, so
  `/v1/apply` stops being non-idempotent for a reason no error message explained.

Test-fixture change worth flagging: the package's `okGitRunner` now answers `rev-parse` with a fixed SHA, and the three
existing prior-plan tests seed that SHA. Without a `HeadSHA` the freshness gate correctly refuses the artifact, so those
tests would otherwise have been asserting the fallback.

**WR-09 landed in this same commit.** `runs.ListFilter` gains `Kind`, `Dir` and `DirSet`, and the lookup asks for
`Limit: 1` — so the RUN-05 response cap now bounds the _matches_ instead of the candidates. `DirSet` exists because D-23
spells the repo root as the empty `Dir`, so "unset" and "the root" have to be distinguishable;
`TestListDirFilterIsOptOut` pins that. `TestListFilterKindAndDirApplyBeforeTheLimit` is the WR-09 regression proper: the
wanted plan is the oldest run for the repo, behind five newer succeeded applies.

### CR-03: The whole container environment — including `SUPERVISOR_TOKEN` — is handed to every tofu child

**Files modified:** `iac-runner/internal/jobq/exec.go`, `iac-runner/internal/jobq/exec_test.go`,
`iac-runner/internal/git/manager.go`, `iac-runner/internal/git/manager_test.go`, `iac-runner/DOCS.md` **Commit:**
`58bd4e7` **Status:** fixed

`tofuEnv()` builds the child environment from a named allowlist (`PATH`, `HOME`, `TMPDIR`, `LANG`, `LC_ALL`, `TZ`) plus
the `TF_*` / `TOFU_*` knob namespaces, and `git.baseEnv()` does the same for git and the `ssh` it spawns (keeping
`GIT_SSH_COMMAND` and `GIT_TERMINAL_PROMPT=0`). No `os.Environ()` call remains in either package's spawn path.

Two tests assert the property directly with `t.Setenv`: a planted `SUPERVISOR_TOKEN` (and a planted
`R2_SECRET_ACCESS_KEY`) must not appear in any recorded `ExecSpec.Env` or in any recorded git environment, while `PATH`
and a planted `TF_LOG` must.

**I did not drop `homeassistant_api: true`** — the review offered that as a conditional. It is a locked project
decision, not an accident: `REQUIREMENTS.md` MQTT-01 and `PROJECT.md` both require it for the Phase 18 MQTT service
connection. So narrowing the child environment _is_ the fix, and `README.md`'s "no `SUPERVISOR_TOKEN` required" is now
true of the code again (the token is still injected into the container by the Supervisor — the runner simply never
passes it on and never uses it).

**WR-14 landed in this same commit.** The comment claiming `os.Environ()` carried "the backend credentials 17-07 exports
(AWS_ACCESS_KEY_ID and friends)" now states the truth: nothing exports them, the projection is deferred, and a future
projection appends to the allowlist rather than reintroducing inheritance. DOCS.md gained a "The tofu child environment"
section that says the same thing to operators, including the consequence for `tofu init` against r2/s3.

### WR-01: `DefaultExec` trips its own "bounded join" on every job longer than 10s

**Files modified:** `iac-runner/internal/jobq/exec.go`, `iac-runner/internal/jobq/exec_test.go` **Commit:** `93a29ea`
**Status:** fixed: requires human verification (process/pipe lifecycle change)

The review's suggested patch — reap with `cmd.Wait()` first, then join — is correct about the ordering but not safe with
`cmd.StdoutPipe()`: `Wait` closes the pipes it created, which is exactly why the original code joined first, and the
tail output would have been lost to a race.

So stdout/stderr now go through `os.Pipe` files the runner owns and assigns to `cmd.Stdout` / `cmd.Stderr`. `Wait` does
not touch those, so the process can be reaped first and the scanners joined afterwards — when a `killGrace` bound
finally means what it says. On expiry the read ends are closed (that is what unblocks a scanner an orphaned grandchild
is holding open) and the join is then awaited to completion, so no scanner goroutine outlives the call. The D-16
SIGTERM→SIGKILL chain is untouched: `cmd.Cancel` and `cmd.WaitDelay` do not depend on pipe ownership.

`TestDefaultExecLongCommandJoinsCleanly` runs a command for ~3× `killGrace`, asserts both the first and the post-bound
line are captured, and asserts the WARN is **absent** from a captured slog buffer.
`TestDefaultExecGracefulExitNotKilled` still logs the warning — correctly: its script leaves a backgrounded `sleep`
holding the write end, which is the real orphan case the bound exists for.

### WR-02: The SEC-03 pattern set misses real R2 credential formats and credentials embedded in URLs

**Files modified:** `iac-runner/internal/runs/redact.go`, `iac-runner/internal/runs/redact_test.go`,
`iac-runner/DOCS.md` **Commit:** `dea2e71` **Status:** fixed

- `r2HexKeyRe` covers the shapes Cloudflare R2 actually issues (32-hex id, 64-hex secret).
- A pre-pass masks `scheme://user:password@` userinfo, because the tokenizer sees a URL as one token. A passwordless
  remote (`ssh://git@github.com/...`) deliberately does **not** match — masking it would hide which remote failed.
- `@` joins `tokenDelimiters` so a bare `user:secret@host` isolates the secret. `/` deliberately does **not**: it is in
  the AWS secret alphabet, and splitting there would stop `awsSecretKeyRe` from ever matching a real key.

All four of the review's probe lines are now test cases, plus the two negative cases above.

Two things to be explicit about:

1. **This is wider than ROADMAP SC-10's literal wording.** The spec enumerated the AWS shapes and the implementation
   matched it, so the spec is the incomplete artifact. I fixed the code because r2 is the default backend and the review
   is right that this is a live credential-disclosure path; **updating SC-10 / REQUIREMENTS.md is a follow-up I did not
   do** — a code-review fix should not silently rewrite a requirement.
2. **A pre-existing false positive is now pinned rather than fixed.** A 40-character hex git SHA is 40 characters of the
   base64-ish alphabet, so SC-10's AWS-secret pattern has _always_ masked it (`HEAD is now at <redacted>`). My probe
   test initially asserted the opposite and failed, which is how it surfaced. I left the behaviour alone (narrowing the
   40-char pattern is a separate spec question) and documented it in DOCS.md and in the test comment.

### WR-03: `?page=` arithmetic overflows and serves the wrong window

**Files modified:** `iac-runner/internal/httpapi/handlers/get_run.go`,
`iac-runner/internal/httpapi/handlers/get_run_test.go`, `iac-runner/internal/runs/output.go`,
`iac-runner/internal/runs/output_test.go` **Commit:** `2bde3a8` **Status:** fixed

`page` is clamped at `1 << 20` in the handler, where `page_size` was already capped, and the store carries its own guard
(`page > math.MaxInt/pageSize` → empty window) for callers that do not come through the handler. The store test drives
the review's exact reproduction value plus `math.MaxInt/pageSize + 1` and `math.MaxInt`, and asserts page 1 is
unaffected.

### WR-04: `url`, `ref` and `branch` reach git's argv unvalidated

**Files modified:** `iac-runner/internal/git/repo.go`, `iac-runner/internal/git/manager.go`,
`iac-runner/internal/git/manager_test.go`, `iac-runner/internal/git/errors_test.go`, `iac-runner/DOCS.md` **Commit:**
`778090b` **Status:** fixed

`url` must now match the schema's `^(git@|ssh://).+$`; `ref` and `branch` must match
`^[A-Za-z0-9][A-Za-z0-9._/+-]{0,254}$`; and `clone` / `fetch` / `pull` pass `--` before their operands. Seven new
rejection cases cover `ext::sh -c …`, `file://`, and option-shaped url/ref/branch values.

I verified the `--` placements against **real git** in a throwaway container rather than trusting the synopsis, and also
verified that the separator is load-bearing: `git fetch origin --upload-pack=touch /tmp/PWNED2` **created the file**,
while `git fetch origin -- --upload-pack=touch /tmp/PWNED` was rejected as an invalid refspec.

Not done, deliberately: the Supervisor schema in `config.yaml` still types `ref`/`branch` as `str?`. Tightening it is a
manifest change with its own review surface, and the Go guard is the layer that matters for a hand-edited
`/data/options.json` — which is the threat the finding describes. DOCS.md now says explicitly that the runner's
validation is the stricter of the two.

### WR-05: No timeout on any git invocation

**Files modified:** `iac-runner/internal/git/manager.go`, `iac-runner/internal/git/manager_test.go`,
`iac-runner/cmd/runner/main.go`, `iac-runner/internal/httpapi/handlers/repos_pull.go`,
`iac-runner/internal/httpapi/handlers/repos_pull_test.go` **Commit:** `a9d585b` **Status:** fixed

`GIT_SSH_COMMAND` gains `ConnectTimeout=10` (per-attempt fail-fast), the startup sweep gets a 5-minute ceiling, and
`POST /v1/repos/{name}/pull` gets a 2-minute ceiling of its own — sized to sit inside the new server `WriteTimeout` from
WR-10. A new test asserts the pull handler hands `Pull` a context that actually _has_ a deadline.

### WR-06: Runs can become permanently stuck in `queued`, and their directories are never reclaimed

**Files modified:** `iac-runner/internal/jobq/queue.go`, `iac-runner/internal/jobq/queue_test.go`,
`iac-runner/internal/runs/retention.go`, `iac-runner/internal/runs/retention_test.go`, `iac-runner/DOCS.md` **Commit:**
`46259ce` **Status:** fixed: requires human verification (changes a tested boot-sweep contract — see below)

All three paths from the finding are fixed: the worker always attempts the terminal write when the `queued`→`running`
update fails; `Submit` removes the directory `MkdirAll` created when `store.Create` fails; and `Rotate` ages a directory
it cannot parse by the directory's own mtime (one being created right now is by definition not over-age, which the test
pins).

**One change beyond the three suggested sub-fixes, flagged for a human:** the boot sweep now rewrites `queued` →
`interrupted`, not just `running`. Rationale: the queue is in-process only (D-05 — "a restart mid-apply does not resume
anything"), so a persisted `queued` run has no worker after a restart, and because `Rotate` deliberately never touches a
queued run its directory was exempt from retention _permanently_ — which is the finding's second bullet. The sweep runs
before the listener opens and before the queue exists, so it cannot race a live submission. This **flips an explicit
assertion**: `TestSweepInterruptedTransitionsRunningOnly` became `TestSweepInterruptedTransitionsActiveRuns`. If the
"running only" wording is a locked decision rather than an implementation detail, this is the one change to reconsider.

On test honesty: the terminal-write fix is asserted through captured slog records (`jobq.status_update_failed` +
`jobq.fail_update_failed`) rather than through a `failed` meta.json. The only way to make `Update` fail without
dependency injection is to corrupt `meta.json`, and in _that_ scenario the terminal write genuinely cannot land either —
so the assertion is on the attempt plus the release discipline. The test comment says so.

### WR-07: A malformed `/data/options.json` is silently half-applied

**Files modified:** `iac-runner/cmd/runner/main.go`, `iac-runner/DOCS.md` **Commit:** `46c3806` **Status:** fixed

A parse failure is now `os.Exit(1)` with an `options_parse_failed` record (added to the DOCS startup table), and an
unreadable-but-present file is fatal too. A _missing_ file stays legal — that is a plain `docker run` with no Supervisor
volume, where the defaults are the whole configuration.

### WR-08: Same-repo waiters occupy `max_parallel_jobs` slots, starving other repos

**Files modified:** `iac-runner/internal/jobq/queue.go`, `iac-runner/internal/jobq/serialization_test.go`,
`iac-runner/DOCS.md` **Commit:** `0e74eb2` **Status:** fixed: requires human verification (concurrency reordering)

I did not take the review's "minimum" (a smaller `lockWait`): that would fail a legitimately queued apply after 5
minutes when applies are budgeted at up to 60, i.e. it trades starvation for spurious `apply_already_running`. I took
its "cleanest form" instead.

`work()` hands the admission slot back **before** waiting on the repo mutex and takes a fresh slot only for the
execution window, so `max_parallel_jobs` bounds _running tofu processes_. A per-repo admission bound (also
`max_parallel_jobs`) replaces what the held slot used to provide, so one repo still cannot accrue unbounded goroutines
and run directories — and a single repo refuses its Nth submission exactly where it did before. Only the collateral
refusal of _other_ repos is gone.

No deadlock is introduced: a slot is only ever held by a job that already owns its repo mutex and is executing, so there
is no cycle. `TestSameRepoWaiterDoesNotStarveOtherRepos` proves repo `b` both gets admitted and _enters exec_ while repo
`a`'s second job is still `queued`, then proves repo `a`'s third submission is still refused, and finally re-asserts the
RUN-06 per-repo occupancy peak of 1 and the global peak of ≤ `max_parallel_jobs`. The whole `serialization_test.go`
suite (the seven RUN-06 angles) passes unchanged at `-race -count=3`.

DOCS.md's `max_parallel_jobs` section now states both halves of the semantics, which is the part the review asked for
"at minimum".

### WR-09: D-18 silently degrades to inline apply once a repo has 100 newer succeeded runs

**Files modified:** `iac-runner/internal/runs/store.go`, `iac-runner/internal/runs/store_test.go`,
`iac-runner/internal/jobq/exec.go` **Commit:** `a19dba4` (same change as CR-02 — the artifact lookup is one code path)
**Status:** fixed

See CR-02 above for the detail. Committed together because CR-02's freshness gate and WR-09's filter push-down are the
same `priorPlanFile` query and the same `ListFilter` type; splitting them would have produced a non-compiling
intermediate commit.

### WR-10: No request body limit and no server read/idle timeouts

**Files modified:** `iac-runner/internal/httpapi/handlers/plan.go`, `iac-runner/internal/httpapi/handlers/plan_test.go`,
`iac-runner/internal/httpapi/handlers/repos_pull.go`, `iac-runner/cmd/runner/main.go` **Commit:** `9caad88` **Status:**
fixed

Bodies are capped at 64 KiB through a shared `limitBody` helper (nil-body safe, so direct handler tests keep working),
and `http.Server` now sets `ReadTimeout` 30s, `WriteTimeout` 5m and `IdleTimeout` 120s alongside the existing
`ReadHeaderTimeout`.

On the review's caveat about `WriteTimeout`: I sized it at 5 minutes rather than exempting a route. It has to clear two
things — a `GET /v1/runs/{id}` page of up to 1000 verbatim tofu lines (D-09/D-24 forbids truncating a multi-megabyte
line) and the synchronous pull, itself bounded at 2 minutes by WR-05's handler deadline. Both fit with room to spare on
a LAN/Tailscale path.

### WR-11: DOCS.md documents an HTTP 423 `locked` response that does not exist

**Files modified:** `iac-runner/DOCS.md` **Commit:** `fe4d8c6` **Status:** fixed

**Direction chosen: docs → code.** The implemented RUN-06 serialize-and-wait behaviour is deliberate, correct, and
already documented accurately two sections earlier in the same file; `423` and a `locked` code exist nowhere in the
taxonomy. Inventing them would be a contract change (D-20) in service of a sentence nobody implemented. The sentence now
states the real contract: 202 + serialize, with a terminal `apply_already_running` only if the lock is held past
`apply_timeout_minutes`.

### WR-12: DOCS.md promises a `redaction.audit` record per request; the code is silent on zero redactions

**Files modified:** `iac-runner/DOCS.md` **Commit:** `ca5d7e4` **Status:** fixed

**Direction chosen: docs → code.** The early return is a deliberate, argued anti-noise decision (`redaction_audit.go`)
with its own assertion (`TestAuditRedactionsSilentWhenNothingRedacted`) — a running apply is polled repeatedly, and a
zero record per poll would bury the ones that matter. The docs now say "emitted only when at least one redaction
happened; no record means nothing was withheld".

I did **not** take the review's alternative (emit at DEBUG for the zero case). That would only be right if SC-10
actually requires distinguishing "nothing redacted" from "redaction never ran", and the requirement does not say so —
the sentence in DOCS.md was the only source of that claim.

### WR-13: `update-version.py` can create and push a `<addon>/v` tag when `config.yaml` cannot be parsed

**Files modified:** `internal/update-version.py` **Commit:** `a570ff6` **Status:** fixed

The guard sits immediately after the three `update_*()` calls, so both the dry-run announcement and the real tag path
are covered, and it fires before `create_and_push_tag` can ever see an empty version.

Verified in a **throwaway git repo under the scratch directory**, never in this repository:

- pre-fix script, real run: created the local tag `broken-addon/v` and printed it as the push target
- pre-fix script, dry run: `🏷️  Would also create and push tag broken-addon/v`
- post-fix, both paths: exit 1, `❌ Could not determine the config.yaml version … refusing to tag`, no tag created

Happy path re-checked in the real repo with `--dry-run` (no writes): `iac-runner 0.2.0-0 → 0.2.1-0`, tag
`iac-runner/v0.2.1-0`. `git tag -l` in this repository is unchanged at 45 tags and contains no `*/v` entry.

### WR-14: `exec.go` documents a backend-credential env projection that does not exist

**Files modified:** `iac-runner/internal/jobq/exec.go`, `iac-runner/DOCS.md` **Commit:** `58bd4e7` (folded into CR-03,
as the review suggested) **Status:** fixed

The comment states the current truth and points at the deferral; DOCS.md tells operators the same, including the
consequence (`tofu init` against r2/s3 authenticates only if their own IaC supplies credentials another way). The
`deferred-items.md` entry was left alone — it is the correct record of the gap, and the review explicitly filed only the
stale _comment_ as the defect.

## Skipped Issues

None. All 17 in-scope findings were confirmed and fixed.

## Deviations from the suggested fixes

Three of the review's proposed patches were changed on inspection. All three are cases where the finding was right and
the suggestion would have introduced a new problem:

1. **WR-01** — reaping before joining is right, but not with `cmd.StdoutPipe()`, whose pipes `Wait` closes. Switched to
   runner-owned `os.Pipe` files so the ordering is safe.
2. **WR-08** — a smaller `lockWait` trades starvation for spurious `apply_already_running` on legitimately queued
   applies. Took the "cleanest form" (slot handoff + per-repo admission bound).
3. **CR-03** — `homeassistant_api: true` was **not** dropped: MQTT-01 requires it for Phase 18.

And one correction to a claim inside a finding: WR-02's probe implies a 40-char hex git SHA is not redacted today. It is
— the SC-10 40-char pattern has always matched it. Pinned as a test case with a comment rather than "fixed", because
narrowing that pattern is a spec question.

## Follow-ups this fix pass did not take

- **REQUIREMENTS.md SC-10 does not describe the shipped redaction set** (R2 hex shapes, URL userinfo, cross-line PEM).
  The code is now stronger than the requirement; the requirement should catch up.
- **`config.yaml`'s Supervisor schema still types `ref`/`branch` as `str?`** (WR-04 fixed the Go guard, which is the
  layer the finding is about).
- **`iac-runner/DOCS.md` and `README.md` were edited without a version bump.** Per CLAUDE.md a bump is a 3-file atomic
  operation via `make update-version` (plus a hand-sync of `build.yaml`'s `RUNNER_VERSION`); whether these fixes warrant
  `0.2.0-1` is a release decision, not a review-fix decision. `make validate-versions` passes as-is.
- **Info-tier findings IN-01..IN-09 were out of scope** (`fix_scope: critical_warning`) and are untouched. IN-02 (the
  duplicated scan-buffer constants) is worth noting: CR-03 added a second small duplication of the same kind
  (`tofuEnvKeep` / `envKeep` in two packages), deliberately, because the two allowlists are not the same set.

---

_Fixed: 2026-09-08T13:55:00Z_ _Fixer: Claude (gsd-code-fixer)_ _Iteration: 1_
