---
phase: 17-git-integration-apply-job-system
plan: 03
subsystem: infra
tags: [go, git, ssh, deploy-keys, error-taxonomy, backoff, opentofu]

requires:
  - phase: 17-git-integration-apply-job-system
    provides: "17-02's contract.ErrCodeGit* taxonomy (8 git_* constants) and contract.ErrCodeRunUnknownRepo"
  - phase: 16-iac-runner-foundation
    provides: "iac-runner module layout, internal/keys sentinel-error + FileMode house pattern, internal/statebackend Options-struct constructor pattern"
provides:
  - "internal/git package: RepoConfig, Error/Classify, Manager with clone/pull and an injectable CommandRunner"
  - "GIT-02 startup clone with skip-if-present and a 3-attempt 1s/5s backoff that never blocks startup"
  - "GIT-03 SSH-keyed pull with ref-vs-fast-forward semantics and a pinned known_hosts"
  - "GIT-04 stderr->git_* classifier producing an Options-field hint and never a raw stderr dump"
  - "The D-10/D-12 contradiction resolved in code, in favor of GIT-03/SC-3"
affects:
  [
    17-05 tofu execution (working-directory resolution via WorkTree/EnsureCloned),
    17-06 HTTP handlers (POST /v1/repos/{name}/pull, git_* -> HTTP status mapping),
    17-07 startup loop (CloneAll + SafeDirectoryWarning logging, Options parsing into []RepoConfig),
    19 live verification,
  ]

actuals:
  tokens: 15600
  tasks: 3
  commits: 10
plan_head_before: 5b41d49b68846986008b18b687a1245c28a2465a

tech-stack:
  added: []
  patterns:
    - "Injectable CommandRunner + injectable clock: every external-process interaction is unit-testable with no network, no SSH server and no real repository"
    - "Ordered first-match-wins stderr classification table mapping onto shared contract constants"
    - "Non-zero process exit is data (CommandResult.ExitCode), Go error reserved for could-not-start"
    - "Compile-time signature locks (var _ func(...) = Fn) instead of grep-based signature assertions"

key-files:
  created:
    - iac-runner/internal/git/repo.go
    - iac-runner/internal/git/errors.go
    - iac-runner/internal/git/manager.go
    - iac-runner/internal/git/errors_test.go
    - iac-runner/internal/git/manager_test.go
  modified:
    - .planning/config.json

key-decisions:
  - "D-10 vs D-12 resolved in favor of D-10: POST /v1/repos/{name}/pull on a pinned repo re-lands on the ref; D-12 survives only as an explicit-conflict guard for a caller that sets ff_only against a pinned repo"
  - "Classifier rule order refined so 'repository not found' / 'authentication failed' are consulted BEFORE git's generic 'Could not read from remote repository' line, which otherwise masks the real cause"
  - "The safe.directory guard runs once from NewManager and its failure is surfaced via SafeDirectoryWarning() rather than swallowed or made fatal"
  - "The D-13 curve keeps its third element (30s) declared while maxCloneAttempts=3 uses only 1s and 5s, because the plan's test contract fixes the sleep sequence at [1s, 5s]"
  - "A failed clone attempt removes the partial working tree before retrying, so attempt 2 fails on the real fault instead of 'destination path already exists'"
  - "HEAD resolution after a successful pull is best-effort and runs without credentials; a failed lookup yields an empty Head, never a failed pull"

patterns-established:
  - "CommandRunner seam: production DefaultCommandRunner via os/exec, tests inject a recorder returning scripted CommandResults"
  - "Hint templates carry a <name> placeholder that the Manager substitutes, so Classify stays repo-agnostic while every emitted hint names a concrete path"
  - "checkout --detach FETCH_HEAD as the single ref-landing primitive: correct for a SHA, a tag and a branch alike, so no ref-shape sniffing is needed"

requirements-completed: [GIT-02, GIT-03, GIT-04]

coverage:
  - id: D1
    description: "For each configured repo the runner clones into /data/repos/<name>/ when that directory is absent or empty, and leaves an existing checkout untouched (GIT-02)"
    requirement: GIT-02
    verification:
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerCloneSkipsExistingWorkTree"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerCloneUnpinnedUsesBranchSingleBranch"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerWorkTreeAndIsCloned"
        status: pass
    human_judgment: false
  - id: D2
    description: "A clone that fails is retried three times with growing backoff and then gives up without preventing the add-on from starting (D-13, ROADMAP SC-2)"
    requirement: GIT-02
    verification:
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerCloneRetriesThreeTimesWithBackoff"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerCloneAllReportsPerRepoOutcomes"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerCloneRemovesPartialWorkTreeBetweenAttempts"
        status: pass
    human_judgment: false
  - id: D3
    description: "A repo whose clone never succeeded is reported as git_clone_missing when a caller later targets it, instead of producing an obscure tofu error (D-14)"
    requirement: GIT-02
    verification:
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerEnsureClonedReportsCloneMissing"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullOnMissingWorkTreeReportsCloneMissing"
        status: pass
    human_judgment: false
  - id: D4
    description: "A pull on an unpinned repo fast-forwards the configured branch; a pull on a repo pinned via ref lands exactly on that ref (GIT-03, D-10, D-11)"
    requirement: GIT-03
    verification:
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullUnpinnedRunsFastForward"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullPinnedFetchesAndChecksOut"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullUnpinnedUsesConfiguredBranch"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullFFOnlyOnPinnedRepoIsRefused"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every operator-caused git failure surfaces as a distinct git_* error_code plus a hint naming the Options field to fix, and never as a stack trace or raw stderr dump (GIT-04)"
    requirement: GIT-04
    verification:
      - kind: unit
        ref: "iac-runner/internal/git/errors_test.go#TestClassify (21 stderr cases, all six families + fallbacks)"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/errors_test.go#TestErrorMessageCarriesCodeAndHintButNotStderr"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullErrorBodyHasNoStderrDump"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullNonFastForwardIsTyped, TestManagerPullBadKeyIsTyped, TestManagerPullMissingRefIsTyped"
        status: pass
    human_judgment: false
  - id: D6
    description: "Git operations authenticate only with the repo's own deploy key at /data/keys/<name>.key and verify the host against /data/keys/known_hosts; they never fall back to an interactive prompt or an agent key (GIT-03)"
    requirement: GIT-03
    verification:
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerSSHEnvCarriesKeyAndKnownHosts"
        status: pass
      - kind: unit
        ref: "iac-runner/internal/git/manager_test.go#TestManagerPullCarriesSSHCredentials"
        status: pass
    human_judgment: true
    rationale: "The unit tests prove the constructed GIT_SSH_COMMAND string carries -i <key>, IdentitiesOnly=yes, StrictHostKeyChecking=yes, UserKnownHostsFile and BatchMode=yes, but they do not prove ssh HONORS them against a real remote. Only Phase 19's live verification against an actual git host closes that gap — in particular that a wrong deploy key is rejected rather than silently succeeding via an agent key."

duration: 21 min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 03: internal/git — SSH-keyed clone/pull with the git\_\* error taxonomy Summary

**A network-free-testable `internal/git` package: repo config with main-defaulting branches, an SSH-pinned clone with a 3-attempt backoff that never blocks startup, ref-vs-fast-forward pull semantics, and an ordered stderr classifier mapping all six operator-caused git failures onto the shared `git_*` taxonomy with an Options-field hint.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-09-08T10:18:05Z
- **Tasks:** 3 of 3
- **Files:** 5 created, 1 modified
- **Commits:** 10 — 3 RED + 3 GREEN + 1 deferred-items docs + 1 SUMMARY + 1 STATE/ROADMAP metadata + 1 count reconciliation (measured: `git rev-list --count 5b41d49..HEAD`)

## Accomplishments

- `RepoConfig` with the four GIT-01 fields, `EffectiveBranch()` defaulting to `main`, `Pinned()` as the D-10 trigger, and `Validate()` rejecting bad names and `http(s)` URLs.
- `Error{Code,Message,Hint}` plus an ordered, case-insensitive `Classify()` covering all six recognizable git stderr families, never returning an empty code and never carrying raw stderr.
- `Manager` with `WorkTree`/`IsCloned`/`EnsureCloned`/`Clone`/`CloneAll`/`Pull`, an injectable `CommandRunner` and an injectable clock.
- The full GIT-03 credential contract in one place (`sshEnv`): repo-scoped deploy key, `IdentitiesOnly`, pinned `known_hosts` with `StrictHostKeyChecking=yes`, `BatchMode=yes`, `GIT_TERMINAL_PROMPT=0`.
- 35 tests, all against the injected runner — no network, no SSH server, no real repository, no real `git` process.

## Final exported API of `internal/git`

Consumed by 17-05 (working-directory resolution) and 17-06 (handlers).

```go
type RepoConfig struct { Name, URL, Branch, Ref string } // json: name/url/branch/ref
func (r RepoConfig) EffectiveBranch() string             // Branch, or "main"
func (r RepoConfig) Pinned() bool                        // Ref != ""
func (r RepoConfig) Validate() error

type CommandResult struct { Stdout, Stderr string; ExitCode int }
type CommandRunner func(ctx context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error)
func DefaultCommandRunner(ctx context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error)

type Error struct { Code, Message, Hint string }  // + unexported wrapped
func (e *Error) Error() string                    // "git: <code>: <message> (hint: <hint>)"
func (e *Error) Unwrap() error
func Classify(stderr string, exitCode int, fallback string) (string, string) // -> (code, hintTemplate)

type CloneOutcome struct { Name string; Skipped bool; Attempts int; Err error }
type PullOutcome  struct { Name, Mode, Head string }
const PullModeFastForward = "ff-only"
const PullModeRef         = "ref"

type Manager struct { /* unexported */ }
func NewManager(reposDir, keysDir string, repos []RepoConfig, run CommandRunner, sleep func(time.Duration)) (*Manager, error)
func (m *Manager) SafeDirectoryWarning() error            // ADDED beyond the plan's interface list
func (m *Manager) Repo(name string) (RepoConfig, bool)
func (m *Manager) Repos() []string                        // ADDED beyond the plan's interface list
func (m *Manager) WorkTree(name string) string
func (m *Manager) IsCloned(name string) bool
func (m *Manager) EnsureCloned(name string) error
func (m *Manager) Clone(ctx context.Context, name string) error
func (m *Manager) CloneAll(ctx context.Context) []CloneOutcome
func (m *Manager) Pull(ctx context.Context, name string, ffOnly bool) (PullOutcome, error)
```

Two additions beyond the plan's `<interfaces>` block, both consumed by 17-07:

- `SafeDirectoryWarning() error` — reports a failed `safe.directory` guard so startup can log it instead of swallowing it. Without this the guard's failure would be silently discarded (the guard must not be fatal, per ROADMAP SC-2).
- `Repos() []string` — the configured names in Options order, so the startup loop and the handlers can enumerate repos without exporting the internal map.

`DefaultCommandRunner` is a `func`, not a `var`. Callers can still pass it wherever a `CommandRunner` is expected (a compile-time assertion in `manager_test.go` locks that), but it cannot be monkey-patched globally — tests inject through `NewManager` instead.

## The D-10 / D-12 reconciliation as shipped

The two locked decisions genuinely contradict each other for the same request:

- **D-10:** when `ref` is set, both the startup clone and `POST /v1/repos/{name}/pull` run `git fetch origin <ref>` + checkout instead of `git pull --ff-only`.
- **D-12:** `git pull` with a non-empty `ref` is rejected with 400 `git_ref_pull_incompatible`.

**Shipped resolution — D-10 wins the default, D-12 becomes an explicit-conflict guard.** GIT-03 and ROADMAP SC-3 both word the endpoint as "runs `git pull --ff-only` **(or the configured ref)**", which is D-10's behavior; making D-12 unconditional would leave a pinned repo with no way to update at all. So:

| Request                                | Repo state       | Behavior                                                     |
| -------------------------------------- | ---------------- | ------------------------------------------------------------ |
| `Pull(ctx, name, ffOnly=false)`         | unpinned         | `git pull --ff-only origin <branch>`, `Mode: "ff-only"`      |
| `Pull(ctx, name, ffOnly=false)`         | pinned via `ref` | `git fetch origin <ref>` + `git checkout --detach FETCH_HEAD`, `Mode: "ref"` |
| `Pull(ctx, name, ffOnly=true)`          | unpinned         | identical to `ffOnly=false` — the request agrees with reality |
| `Pull(ctx, name, ffOnly=true)`          | pinned via `ref` | **refused**: `git_ref_pull_incompatible`, **zero git commands run** |

`ffOnly` carries the optional `ff_only` boolean of the request body (17-06 owns the wire, default `false`). Only the last row is a genuine contradiction: the caller explicitly asked for fast-forward semantics on a repo the operator explicitly pinned.

**Reverting to a strict D-12 is a one-line change** and is documented as such in `manager.go`: drop the `ffOnly &&` term so the guard fires on `cfg.Pinned()` alone. If the operator later prefers that, the tests to update are `TestManagerPullPinnedFetchesAndChecksOut` and `TestManagerPullFFOnlyOnPinnedRepoIsRefused`.

## The stderr → code rule table as shipped

Evaluated top to bottom, first match wins, against `strings.ToLower(stderr)`. Every code is a `contract.ErrCodeGit*` constant — there are no `git_*` string literals in the package.

| # | stderr substrings (lowercased)                                                                                 | code                   | hint                                                              |
| - | -------------------------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------- |
| 1 | `permission denied (publickey)`, `permission denied (public key)`                                              | `git_ssh_handshake`    | deploy key at `/data/keys/<name>.key` (chmod 600) + public half registered on the remote |
| 2 | `host key verification failed`, `no matching host key`                                                         | `git_ssh_handshake`    | add the remote's host key to `/data/keys/known_hosts`             |
| 3 | `could not resolve hostname`, `temporary failure in name resolution`                                           | `git_dns_failure`      | host part of the repo `url` Options field + DNS/Tailscale connectivity |
| 4 | `authentication failed`, `access denied`, `repository not found`                                               | `git_unauthorized`     | the repo `url` Options field + the key's repo access              |
| 5 | `could not read from remote repository`                                                                        | `git_ssh_handshake`    | `/data/keys/<name>.key` + the host key in `/data/keys/known_hosts` |
| 6 | `couldn't find remote ref`, `did not match any file(s) known to git`, `unknown revision`                       | `git_ref_not_found`    | the `ref` (or `branch`) Options field                             |
| 7 | `not possible to fast-forward`, `non-fast-forward`, `need to specify how to reconcile`, `diverging branches`, `divergent branches` | `git_non_fast_forward` | pin with `ref`, or delete `/data/repos/<name>/` and let the add-on re-clone |
| — | no match                                                                                                       | caller's fallback      | "git exited N with an error this add-on does not recognize — check the add-on log" |

**Ordering deviation from the plan's table (deviation Rule 1, below):** the plan grouped `could not read from remote repository` together with `permission denied (publickey)` as rule 1, ahead of `repository not found`. Real GitHub output for an unauthorized repo is `ERROR: Repository not found.` *followed by* `fatal: Could not read from remote repository.` — under the plan's order that classifies as `git_ssh_handshake` and sends the operator to check a deploy key that is actually fine. The generic line was therefore split out into rule 5, below the specific signals. Every `(substring → code)` pair the plan mandated still holds; only the precedence between two rules changed. `TestClassify/repository_not_found_is_unauthorized_even_with_the_generic_ssh_line` locks the behavior.

Fallback codes by call path: `Clone`/`cloneAttempt` pass `contract.ErrCodeGitCloneFailed`, the unpinned `Pull` path passes `contract.ErrCodeGitNonFastForward`, and the `fetch`/`checkout` ref path passes `contract.ErrCodeGitRefNotFound`. An empty fallback degrades to `git_clone_failed` rather than emitting `""` onto the wire.

## Was the `safe.directory` guard needed?

**Yes — implemented and covered by tests.** `NewManager` runs `git config --global --add safe.directory '*'` exactly once at construction, mirroring `markdown-renderer/run.sh:14`.

- **Why:** `/data/repos/<name>/` is created by this process, but the HA `/data` volume can end up owned by a different UID after a snapshot restore or a manual `docker cp`. Modern git then refuses **every** command in that checkout with "detected dubious ownership in repository" — which would classify as an unrecognized fallback error and produce a genuinely baffling operator experience.
- **Why the `*` wildcard is acceptable:** the add-on container is single-tenant and this process is the only reader of `/data/repos`, so `*` is not a meaningful privilege boundary here. The comment in `manager.go` says so explicitly.
- **Why it is not fatal:** ROADMAP SC-2 requires that startup proceed. The guard's failure is stored and exposed via `SafeDirectoryWarning()` for 17-07 to log, rather than swallowed (which would hide a real misconfiguration) or made fatal (which would violate SC-2).

## TDD Gate Compliance

Plan type is `execute`, but all three tasks carry `tdd="true"`, so each ran a full RED → GREEN cycle with machine-verified RED evidence.

| Task | RED commit | RED verdict | GREEN commit | REFACTOR |
| ---- | ---------- | ----------- | ------------ | -------- |
| 1 — RepoConfig + classifier | `19a4284` | `RED_EVIDENCE_OK` (target `TestClassify`, exit 1, 5/7 failing) | `5c4d5d2` | not needed |
| 2 — Manager + clone backoff | `23d7190` | `RED_EVIDENCE_OK` (target `TestManagerCloneRetriesThreeTimesWithBackoff`, exit 1, 14/22 failing) | `680dc9f` | not needed |
| 3 — Pull ref semantics | `9c6d815` | `RED_EVIDENCE_OK` (target `TestManagerPullPinnedFetchesAndChecksOut`, exit 1, 13/35 failing) | `24976da` | not needed |

No `refactor(17-03)` commit exists: per `tdd.md` REFACTOR is optional and commits only when changes are made. Each GREEN implementation was written directly in its final shape and no cleanup was identified afterwards.

**Two notes on how RED was achieved in Go, both deliberate:**

1. **Each RED commit includes compile-only stubs of the production file.** Go cannot run a test that references an undeclared symbol — it fails at build time, and `tdd.md` classifies a build/load failure as `INVALID_RED`. Declaring the types and methods with zero-value bodies makes the package compile so the target test fails on a *behavioral assertion*, which is what actually authorizes GREEN.
2. **`go test` output is not TAP,** which `gsd-tools check tdd-red-evidence` requires. A converter (`go test -json` → TAP, in the session scratchpad) produced the summary; every test name and count in it comes from the real run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Classifier rule order masked `repository not found` behind git's generic SSH line**

- **Found during:** Task 1
- **Issue:** The plan's rule table put `could not read from remote repository` in rule 1 alongside `permission denied (publickey)`, and `repository not found` in rule 4. GitHub emits `ERROR: Repository not found.` together with `fatal: Could not read from remote repository.` for an unauthorized repo, so first-match-wins would have returned `git_ssh_handshake` and pointed the operator at a deploy key that is not the problem.
- **Fix:** Split the generic line into its own rule below the specific signals (now rule 5). All plan-mandated `(substring → code)` mappings are preserved; only precedence changed.
- **Files modified:** `iac-runner/internal/git/errors.go`
- **Verification:** `TestClassify/repository_not_found_is_unauthorized_even_with_the_generic_ssh_line` asserts `git_unauthorized` for the combined stderr; the other 20 cases pin the rest of the table.
- **Commit:** `5c4d5d2`

**2. [Rule 3 — Blocker] No Go toolchain on the development host**

- **Found during:** Task 1 (first `go build`)
- **Issue:** `go` is not on `PATH` on this machine (`zsh: command not found: go`), so nothing in the plan's `<verify>` blocks could run. 17-01/17-02 evidently ran in an environment where it was available.
- **Fix:** Verification runs inside the locally-present `golang:1.25-alpine` image — the same base `iac-runner/Dockerfile` builds with — with the repo and the host module cache (`~/go/pkg/mod`) bind-mounted. No package was installed on the host and no new image was pulled. `-race` additionally installs `gcc musl-dev` inside the throwaway container, since race detection requires cgo.
- **Files modified:** none (wrapper scripts live in the session scratchpad)
- **Verification:** `go version` → `go1.25.14`; `go build ./...`, `go vet ./...`, `go test ./... -count=1` and `go test ./internal/git/... -race -count=1` all exit 0.
- **Commit:** n/a (tooling only)

**3. [Rule 3 — Blocker] Executor protected-branch assertion vs. the instruction to stay on `main`**

- **Found during:** pre-flight, before Task 1
- **Issue:** The orchestrator dispatched this plan in sequential mode with an explicit instruction to stay on `main` and not create or switch branches, but the executor's pre-commit assertion halts on a protected/default branch. `gsd-tools query git.base-branch --is-protected main` returns `true`, so no task could have been committed.
- **Fix:** Set the documented escape hatch `git.allow_default_branch_commits: true` in `.planning/config.json`. This matches the project's existing `git.branching_strategy: "none"` and the fact that 17-01 (`81b0f54`) and 17-02 (`5b41d49`) are already committed directly on `main`. No branch was created, removed or switched; no `git stash`, `git clean` or ref rewrite was used.
- **Files modified:** `.planning/config.json`
- **Verification:** all seven plan commits landed on `main` with hooks enabled and no `--no-verify`.
- **Commit:** included in the docs commit `a6afb32`'s neighborhood — the config change is staged with this SUMMARY's metadata commit.

### Acceptance criteria that could not be satisfied as literally written

Three `<acceptance_criteria>` regexes are anchored with `$` immediately after an exported Go signature, e.g.:

```
^func Classify\(stderr string, exitCode int, fallback string\) \(string, string\)$
```

No valid Go declaration can match these: the language's semicolon-insertion rule requires the opening `{` on the signature line, so the line always ends in ` {`. The same applies to the `NewManager` and `Pull` criteria. The plan's own `<automated>` verify blocks use the loose forms (`^func Classify\(`, `^func NewManager\(`, `^func (m \*Manager) Pull(`) for two of the three, and those pass.

Rather than skip the intent, the exact signatures are locked at **compile time**, which is strictly stronger than a grep — drift becomes a build failure:

```go
var _ func(string, int, string) (string, string)                                     = Classify
var _ func(string, string, []RepoConfig, CommandRunner, func(time.Duration)) (*Manager, error) = NewManager
var _ CommandRunner                                                                  = DefaultCommandRunner
var _ func(context.Context, string, bool) (PullOutcome, error)                       = (&Manager{}).Pull
```

**Total deviations:** 3 auto-fixed (1 × Rule 1 bug, 2 × Rule 3 blocker) + 3 unsatisfiable acceptance regexes replaced with stronger compile-time equivalents. **Impact:** none on the shipped contract. Every behavioral requirement of the plan is implemented; one classifier precedence was corrected, and the verification path moved into a container without changing what is verified.

## Verification

All commands run from `iac-runner/` inside the toolchain container described above.

| Command                                              | Result |
| ---------------------------------------------------- | ------ |
| `go build ./...`                                     | exit 0 |
| `go vet ./...`                                        | exit 0 |
| `gofmt -l internal/git/`                              | empty (package is gofmt-clean) |
| `go test ./internal/git/... -count=1`                 | exit 0 — 35 test functions, 40 table sub-cases, 75 PASS lines, 0 FAIL |
| `go test ./internal/git/... -race -count=1`           | exit 0 |
| `go test ./... -count=1`                              | exit 0 — no Phase 16 or 17-02 suite regressed |
| `! grep -rE 'exec\.Command' internal/git/*_test.go`   | pass — no test spawns a real git process |
| `grep -c 'contract.ErrCode' internal/git/*.go`        | 79 (>= 10 required) |

Plan-level `<success_criteria>`: all six met. Task-level `<acceptance_criteria>`: all operative checks pass (see the note above on the three unsatisfiable regexes).

## Authentication Gates

None. This plan shells out to `git` only through an injected fake in tests; no real remote, deploy key or credential was needed.

## Known Stubs

None. No hardcoded empty values, placeholder text, `TODO`/`FIXME` markers or skipped tests exist in the five shipped files (`grep -nE 'TODO|FIXME|placeholder|t\.Skip' iac-runner/internal/git/*.go` → no matches).

The one intentionally-unused value is `cloneBackoff`'s third element (`30 * time.Second`), which `maxCloneAttempts = 3` never reaches. It is declared because D-13 names it as part of the curve and the plan's test contract simultaneously fixes the observable sleep sequence at `[1s, 5s]`; the code comment explains this and notes it becomes live the moment the attempt budget is raised. This is a documented decision, not a stub.

## Threat Flags

| Flag                       | File                             | Description                                                                                                                                                                                                                              |
| -------------------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| threat_flag: file_access   | `iac-runner/internal/git/manager.go` | `NewManager` runs `git config --global --add safe.directory '*'`, which relaxes git's ownership check process-wide for the container. Justified as single-tenant (documented in code), but it is a real widening of git's trust model and worth an explicit look during Phase 17 security review. |
| threat_flag: file_access   | `iac-runner/internal/git/manager.go` | `WorkTree()` joins `reposDir` with a repo name. Escape is prevented only by `RepoConfig.Validate()`'s regex, enforced in `NewManager`. Any future path that constructs a `Manager` or a work-tree path without that validation would reintroduce traversal. |
| threat_flag: auth_path     | `iac-runner/internal/git/manager.go` | `sshEnv()` is the sole enforcement point for the GIT-03 credential contract. Unit tests assert the constructed `GIT_SSH_COMMAND` string, not that `ssh` honors it — a wrong-key rejection has not been observed against a live remote (see coverage entry D6; Phase 19 owns this). |

## Issues Encountered

None blocking. Two environment findings were logged to `.planning/phases/17-git-integration-apply-job-system/deferred-items.md` rather than fixed here (scope boundary):

1. Six files in other `iac-runner` packages are not gofmt-clean (pre-existing, from Phase 16 / 17-01 / 17-02). `internal/git/` is clean.
2. `internal/httpapi/handlers.TestHealthzBothPass` fails in a bare toolchain container because it probes for a `tofu` binary via `exec.LookPath`. With a stub `tofu` on `PATH` the suite is green. Making that test `t.Skip` when `tofu` is absent would make the suite hermetic.

## Next Phase Readiness

`internal/git` is complete and consumable. Ready for `17-04` (run storage). Downstream consumers:

- **17-05** — call `EnsureCloned(repo)` before executing tofu (D-14), and `WorkTree(repo)` joined with the validated `dir` as the working directory.
- **17-06** — map `*git.Error.Code` onto HTTP status: `git_clone_missing` → 404, `git_non_fast_forward` → 409, `git_ssh_handshake`/`git_unauthorized` → 403, `git_ref_pull_incompatible` → 400 (GIT-03/SC-3). Accept the optional `ff_only` boolean and pass it to `Pull`.
- **17-07** — unmarshal the `repos` Options list straight into `[]RepoConfig`, build the `Manager`, log `SafeDirectoryWarning()`, run `CloneAll` at startup and log each failed outcome as `git_clone_failed` without aborting (SC-2). Document all eight `git_*` codes in `DOCS.md` per D-20.
- **Phase 19** — live verification is the only thing that can close coverage entry D6: prove `ssh` actually honors the pinned key and `known_hosts` against a real remote.

## Self-Check: PASSED

- All 5 created files exist on disk (`repo.go` 78, `errors.go` 141, `manager.go` 439, `errors_test.go` 351, `manager_test.go` 714 lines).
- All 7 commits verified present in `git log`: `19a4284`, `5c4d5d2`, `23d7190`, `680dc9f`, `9c6d815`, `24976da`, `a6afb32`.
- `git rev-list --count 5b41d49..HEAD` = 10, matching the `commits: 10` frontmatter (measured, not narrated): the 7 code+docs commits listed above, plus this SUMMARY's own commit, the STATE/ROADMAP metadata commit, and the commit that reconciled this count. The reconciliation was amended rather than re-committed so the number is stable.
- All task `<acceptance_criteria>` re-run and passing (except the three regexes that are unsatisfiable in valid Go, replaced with compile-time locks).
- Plan-level `<verification>` steps 1-6 all re-run and passing.
