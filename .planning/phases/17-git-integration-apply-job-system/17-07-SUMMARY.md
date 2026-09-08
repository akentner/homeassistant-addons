---
phase: 17-git-integration-apply-job-system
plan: 07
subsystem: infra
tags: [go, opentofu, git, ssh, home-assistant-addon, slog, docker, hadolint, versioning]

# Dependency graph
requires:
  - phase: 16-iac-runner-scaffold
    provides: main.go startup pipeline (bind gate, state backend, keys validator, token store), signals.go 30s drain
  - phase: 17-01
    provides: config.yaml Options schema for the four Phase 17 fields + the tofu/git/openssh runtime in the Dockerfile
  - phase: 17-02
    provides: contract types (RunKind/RunStatus/RunDetail/error_code taxonomy), run-id and dir primitives
  - phase: 17-03
    provides: internal/git Manager (NewManager, CloneAll with the D-13 backoff, Pull, SafeDirectoryWarning)
  - phase: 17-04
    provides: internal/runs Store (NewStore, SweepInterrupted, Rotate, StartRetentionTicker, redaction)
  - phase: 17-05
    provides: internal/jobq Queue (New, Submit, Drain), DefaultExec with the D-16 kill-chain
  - phase: 17-06
    provides: pull/plan/apply handlers and the shared statusForCode error map
  - phase: 17-08
    provides: the six-argument httpapi.NewRouter with all five Phase 17 endpoints mounted
provides:
  - "A runnable iac-runner binary: the whole phase composes into one process that boots, clones, sweeps, serves and
    drains"
  - "Startup wiring in cmd/runner/main.go — the four Phase 17 Options, git.Manager, runs.Store, jobq.Queue, all threaded
    into httpapi.NewRouter (the TODO(17-07) nil,nil,nil seam is gone)"
  - "Extended SIGTERM drain: 25s http.Server.Shutdown + 5s jobq.Queue.Drain inside the existing 30s budget"
  - "A buildable container image — the OpenTofu SHA256 verification could never pass before this plan"
  - "iac-runner/DOCS.md as the Phase 17 operator reference (Options, five endpoints with curl, the real error_code/HTTP
    map, startup+shutdown records)"
  - "iac-runner at version 0.2.0-0 across all three version files, with NO git tag and NO push"
affects: [18-mqtt-discovery, 19-e2e-verification-docs-runbook]

actuals:
  tokens: 11400
  tasks: 4
  commits: 4
plan_head_before: e3c4e62f68affdf9fffa649f209a472cf0dcfa58

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Startup pipeline: every construction + best-effort startup action runs BEFORE the HTTP listener binds, so no
      client can observe a half-initialized runner"
    - "Split shutdown budget: one named constant per drain phase, summing to the existing deadline, both logged in
      shutdown_initiated"
    - "Options clamping at the edge: a hand-edited /data/options.json value outside the Supervisor schema range is
      corrected and logged, never trusted"
    - "One structured slog record per startup step, tabulated in DOCS.md so an operator greps rather than guesses"

key-files:
  created: []
  modified:
    - iac-runner/cmd/runner/main.go
    - iac-runner/cmd/runner/signals.go
    - iac-runner/Dockerfile
    - iac-runner/DOCS.md
    - iac-runner/README.md
    - iac-runner/config.yaml
    - iac-runner/build.yaml
    - internal/update-version.py

key-decisions:
  - "runs_retention_hours <= 0 is clamped to the 24h default with a runs_retention_invalid warning — the plan claimed
    17-04 refuses to start a ticker for 0, but it actually floors the interval at 1 minute and Rotate(0) would delete
    every terminal run on the first tick"
  - "A boot-time runStore.Rotate is called explicitly before arming the ticker, because 17-04's StartRetentionTicker
    deliberately does not rotate on start and names 17-07 as the caller"
  - "repos_loaded carries a key_issues list built from a presence-only check of /data/keys/<name>.key and known_hosts —
    a missing deploy key is named at boot but never fatal"
  - "The OpenTofu zip keeps its upstream filename so sha256sum -c can actually open it; a checksum that can never pass
    is worse than none because it looks like a guarantee"
  - "build.yaml RUNNER_VERSION was bumped by hand: it is a fourth version field that neither update-version.py nor
    validate-versions.sh knows about, so there is no supported tool path for it"
  - "The iac-runner/v0.2.0-0 tag is intentionally outstanding — creating it would fire the build-iac-runner image
    workflow while the v1.2 Cloudflare prerequisite is still open"
  - "The backend-credential env projection that internal/jobq/exec.go's comment attributes to 17-07 does not exist
    anywhere in the repo and was NOT invented here — no Phase 17 requirement covers it and Phase 19 SC-3 is where it
    gets designed"

patterns-established:
  - "Empirical boot verification: build the image locally, run it against a scratch /data with a crafted options.json,
    and record the actual slog records in the SUMMARY so the next phase greps for known strings"
  - "Broken acceptance-criteria greps are verified with a corrected pattern and recorded as deviations; code is never
    reshaped to satisfy a regex"

requirements-completed:
  [GIT-01, GIT-02, GIT-03, GIT-04, RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06, SEC-03, OBS-02, OBS-03]

coverage:
  - id: D1
    description:
      "Startup parses the four Phase 17 Options, validates per-repo deploy-key presence and logs a structured
      repos_loaded record with the count, names and key issues"
    requirement: GIT-01
    verification:
      - kind: integration
        ref:
          "docker run localhost/iac-runner:0.2.0-verify with a crafted /data/options.json — observed
          repos_loaded{count:1,repos:[homelab],key_issues:[...],max_parallel_jobs:2,apply_timeout_minutes:5,runs_retention_hours:1}"
        status: pass
      - kind: other
        ref:
          "grep -cE 'Repos \\[\\]git.RepoConfig|MaxParallelJobs int|ApplyTimeoutMinutes int|RunsRetentionHours int' = 4"
        status: pass
    human_judgment: false
  - id: D2
    description:
      "Startup clones every configured repo with the D-13 1s/5s/30s backoff; a failed clone is logged and does not
      prevent startup (D-14)"
    requirement: GIT-02
    verification:
      - kind: integration
        ref:
          "same container run with a nonexistent repo + no deploy key — observed
          git_clone_failed{repo:homelab,attempts:3,err:git_ssh_handshake} after ~7.1s, then listening"
        status: pass
    human_judgment: false
  - id: D3
    description: "SweepInterrupted runs at boot so no stale `running` run is ever observable over HTTP"
    requirement: OBS-02
    verification:
      - kind: unit
        ref: "iac-runner/internal/runs (17-04 suite) — go test ./... pass"
        status: pass
      - kind: other
        ref: "grep -cE 'runs.NewStore\\(|runStore.SweepInterrupted\\(|runStore.StartRetentionTicker\\(' = 3"
        status: pass
    human_judgment: false
  - id: D4
    description: "Retention ticker armed at boot (D-25) and stopped inside the SIGTERM drain"
    requirement: OBS-02
    verification:
      - kind: integration
        ref:
          "container run — observed runs_retention_started{runs_dir:/data/runs,retention_hours:1} at boot and
          runs_retention_stopped during the drain"
        status: pass
    human_judgment: false
  - id: D5
    description:
      "All five Phase 17 endpoints serve real work on port 8125 behind the auth gate — they answered HTTP 500 via chi's
      Recoverer before this plan"
    requirement: RUN-02
    verification:
      - kind: integration
        ref:
          "curl against the running container: /v1/version 200, pull 404 git_clone_missing, pull(unknown) 404
          run_unknown_repo, /v1/plan 404 git_clone_missing, /v1/apply 400 run_invalid_dir, /v1/runs 200, /v1/runs/{bad}
          404 run_unknown_id, ?status=bogus 400, no-auth 401"
        status: pass
      - kind: other
        ref: "grep -rn 'TODO(17-07)' iac-runner/cmd iac-runner/internal — no matches"
        status: pass
    human_judgment: false
  - id: D6
    description: "SIGTERM drain gives the HTTP server 25s and jobq.Queue.Drain 5s, then exits 0"
    verification:
      - kind: integration
        ref:
          "docker stop -t 35 — observed
          shutdown_initiated{deadline_seconds:30,http_drain_seconds:25,queue_drain_seconds:5} -> runs_retention_stopped
          -> shutdown_complete, container exit code 0"
        status: pass
    human_judgment: false
  - id: D7
    description: "hadolint DL3003 closed and the container image actually builds"
    verification:
      - kind: other
        ref: "make lint — exit 0, 'Lint Dockerfiles' Passed"
        status: pass
      - kind: integration
        ref:
          "docker build --build-arg RUNNER_VERSION=0.2.0 — image built, tofu 1.10.6 checksum verified, /v1/version
          reported runner_version 0.2.0"
        status: pass
    human_judgment: false
  - id: D8
    description: "Version bumped to 0.2.0-0 across config.yaml, build.yaml and the README badge with no tag and no push"
    verification:
      - kind: other
        ref:
          "make validate-versions pass; git tag --list 'iac-runner/v0.2.0*' empty; origin ahead-count unchanged at 66"
        status: pass
    human_judgment: false
  - id: D9
    description:
      "DOCS.md documents every Phase 17 Option and endpoint with curl examples, the full error_code/HTTP table, the
      redaction audit record and the startup/shutdown record table"
    requirement: OBS-03
    verification:
      - kind: other
        ref: "markdownlint-cli2 iac-runner/DOCS.md — 0 issues; the four option and five endpoint headers present"
        status: pass
    human_judgment: true
    rationale:
      "Lint and greps prove the sections exist and the statuses were cross-read from handlers/write_error.go, but
      whether the prose is sufficient for an operator who has never seen the add-on is a judgment call — ROADMAP Phase
      19 SC-6 rewrites these docs from observed behavior against a live HA host"
  - id: D10
    description: "End-to-end plan/apply against real infrastructure with a real state backend"
    verification: []
    human_judgment: true
    rationale:
      "Not attempted and not in scope: no tofu-authenticating credential env exists yet (see Issues Encountered), and
      ROADMAP Phase 19 SC-2/SC-3 own the live plan/apply/drift/idempotency cycle and the three-backend matrix"

# Metrics
duration: 25 min
completed: 2026-09-08
status: complete
---

# Phase 17 Plan 07: main.go Wiring + DOCS/README + Version Bump Summary

**The eight isolated Phase 17 packages now compose into one runnable binary: it parses its Options, clones repos with
the D-13 backoff, sweeps interrupted runs, arms the retention ticker, serves all five endpoints on 8125 and drains
in-flight tofu jobs on SIGTERM — verified by booting the real container image, not by inspection.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-08T12:10:00Z
- **Completed:** 2026-09-08T12:35:00Z
- **Tasks:** 4 of 4
- **Files modified:** 8 (7 planned + `internal/update-version.py` per deviation Rule 3)

## Accomplishments

- **The `nil, nil, nil` seam is closed.** `httpapi.NewRouter(runnerVersion, store, keysValidator, gitMgr, runStore, q)`
  now receives real dependencies; the `TODO(17-07)` marker is gone and all five Phase 17 endpoints were exercised
  against a running container (previously they answered 500 through chi's `Recoverer`).
- **`Queue.Drain(ctx)` runs inside the SIGTERM window.** The existing 30s budget is split into two named constants —
  `httpDrainBudget = 25s` for `http.Server.Shutdown`, `queueDrainBudget = 5s` for the job drain — with the retention
  ticker stopped in between and a `nil` queue tolerated.
- **The container image is buildable for the first time.** The OpenTofu SHA256 verification could never pass (the zip
  was saved as `/tmp/tofu.zip` while `SHA256SUMS` names `tofu_<v>_linux_amd64.zip`), so `docker build` failed at stage 2
  regardless of the DL3003 fix. Both are fixed; `make lint` exits 0 and the phase has no remaining lint failures.
- **Empirical boot verification.** The built image was run against a scratch `/data` with a crafted `options.json`; the
  full startup record sequence, the nine endpoint responses and the shutdown sequence were observed and are transcribed
  below for Phase 19 to grep.
- **`iac-runner` is at 0.2.0-0** across `config.yaml`, `build.yaml` and the README badge, with **no git tag created and
  nothing pushed**.

## Observed boot records

Captured from `docker run localhost/iac-runner:0.2.0-verify` with `state_backend: local`, one repo (`homelab`, an SSH
URL that does not resolve to an accessible repo), no `/data/keys/` at all, `max_parallel_jobs: 2`,
`apply_timeout_minutes: 5`, `runs_retention_hours: 1`:

```json
{"msg":"bind_resolved","bind_address":"auto","bind_ip":"100.70.66.18","allowed_subnets":[]}
{"msg":"state_backend_ready","backend":"local","endpoint":"","bucket":"/data/terraform.tfstate","region":"","use_lockfile":false}
{"msg":"keys_validated","keys_dir":"/data/keys","required_files":null}
{"msg":"repos_loaded","count":1,"repos":["homelab"],"key_issues":["homelab: missing deploy key /data/keys/homelab.key","missing /data/keys/known_hosts"],"max_parallel_jobs":2,"apply_timeout_minutes":5,"runs_retention_hours":1}
{"level":"WARN","msg":"git_clone_failed","repo":"homelab","attempts":3,"err":"git: git_ssh_handshake: clone of repo homelab failed (hint: add the remote's host key to /data/keys/known_hosts)"}
{"msg":"runs_retention_started","runs_dir":"/data/runs","retention_hours":1}
{"msg":"jobq_ready","max_parallel_jobs":2,"apply_timeout_minutes":5}
{"msg":"iac_runner.token.issued","actor_token_fp":"...","preview":"sav...Biw","path":"/data/initial-iac-runner-token"}
{"msg":"starting","runner_version":"0.2.0","pid":76,"state_backend":"local"}
{"msg":"listening","bind_address":"100.70.66.18:8125"}
```

The clone gap between `repos_loaded` and `git_clone_failed` was 7.15s — the D-13 curve (attempt, 1s, attempt, 5s,
attempt, give up). Startup continued: D-14 holds.

Shutdown (`docker stop -t 35`, container exit code 0):

```json
{"msg":"shutdown_initiated","signal":"SIGTERM","deadline_seconds":30,"http_drain_seconds":25,"queue_drain_seconds":5}
{"msg":"runs_retention_stopped"}
{"msg":"shutdown_complete"}
```

Records that exist but did not fire in this run (no prior container state, no successful clone, no in-flight job):
`git_clone_succeeded`, `git_clone_skipped`, `runs_swept_interrupted`, `runs_rotated_at_boot`, `runs_retention_invalid`,
`git_safe_directory_guard_failed`, `jobq_drain_deadline_exceeded`, `iac_runner.log_reopen`. All are tabulated in
DOCS.md.

## Observed endpoint responses

Against the same running container, with the bearer from `/data/initial-iac-runner-token`:

| Request                                              | Status | `error_code`                    |
| ---------------------------------------------------- | ------ | ------------------------------- |
| `GET /healthz`                                       | 200    | —                               |
| `GET /v1/version`                                    | 200    | — (`runner_version: "0.2.0"`)   |
| `POST /v1/repos/homelab/pull`                        | 404    | `git_clone_missing`             |
| `POST /v1/repos/nope/pull`                           | 404    | `run_unknown_repo`              |
| `POST /v1/plan {"repo":"homelab","dir":"envs/prod"}` | 404    | `git_clone_missing`             |
| `POST /v1/apply {"repo":"homelab","dir":"../etc"}`   | 400    | `run_invalid_dir`               |
| `GET /v1/runs?limit=5`                               | 200    | — (`{"runs":[],"count":0,...}`) |
| `GET /v1/runs/NOTAVALIDID`                           | 404    | `run_unknown_id`                |
| `GET /v1/runs?status=bogus`                          | 400    | `run_invalid_dir`               |
| `GET /v1/runs` (no `Authorization`)                  | 401    | `unauthorized`                  |

Every response carried a typed body — none reached chi's `Recoverer`, which is the observable difference this plan
makes. Note that dir validation is evaluated before the clone-present check (`../etc` returned `run_invalid_dir`, not
`git_clone_missing`).

## Task Commits

1. **Tasks 1 + 2: main.go wiring + signals.go drain** — `b789ddd` (feat)
2. **Dockerfile: DL3003 + a checksum that can pass** — `32fdca2` (fix)
3. **Task 3: DOCS.md Phase 17 reference** — `01f2c51` (docs)
4. **Task 4: README + version bump 0.2.0-0** — `a6d352c` (chore)

Tasks 1 and 2 share one commit deliberately: Task 2 changes `HandleSignals`'s signature and Task 1 owns the call site,
so either half alone leaves the module non-compiling. Splitting them would have produced an unbuildable intermediate
commit, which is worse than a two-task commit.

## Files Created/Modified

- `iac-runner/cmd/runner/main.go` — four new Options fields + defaults, `git.NewManager` + `CloneAll`, `runs.NewStore` +
  `SweepInterrupted` + `Rotate` + `StartRetentionTicker`, `jobq.New`, the six-argument `httpapi.NewRouter`, and two
  helpers (`repoNames`, `repoKeyIssues`). 234 -> 457 lines.
- `iac-runner/cmd/runner/signals.go` — `httpDrainBudget`/`queueDrainBudget` constants, two new `HandleSignals`
  parameters, `stopRetention()` + `queue.Drain()` inside the SIGTERM branch.
- `iac-runner/Dockerfile` — `WORKDIR /tmp` replaces the in-`RUN` `cd /tmp`; the OpenTofu zip keeps its upstream filename
  so the SHA256 check can open it.
- `iac-runner/DOCS.md` — +307 lines: four Options sections, five endpoint sections with curl, the error_code table, an
  output-redaction section, a startup/shutdown record table, per-repo key steps in first-time setup.
- `iac-runner/README.md` — Phase 17 feature list (13 bullets) and the v0.2.0 badge/release link.
- `iac-runner/config.yaml` / `iac-runner/build.yaml` — `0.2.0-0` / `0.2.0` via the make script; `RUNNER_VERSION`
  hand-synced to `0.2.0`.
- `internal/update-version.py` — `NameError` fix (deviation Rule 3).

## Decisions Made

See `key-decisions` in the frontmatter. The two that will matter to a future reader:

- **The retention clamp is deliberate, not defensive noise.** `runs.tickInterval` floors the cadence at 1 minute, so
  `runs_retention_hours: 0` in a hand-edited `/data/options.json` would arm a ticker that calls `Rotate(0)` every minute
  — deleting every terminal run. main.go clamps to 24h and logs `runs_retention_invalid`.
- **No credential env was invented.** `internal/jobq/exec.go:91-93` claims 17-07 exports the backend credentials. It
  does not, and nothing else does either. Guessing at the variable names would have been a security decision made by an
  executor; it is recorded for Phase 19 instead (see Issues Encountered).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The OpenTofu SHA256 verification could never pass; the image was not buildable**

- **Found during:** the mandated local `docker build` after the DL3003 fix
- **Issue:** the zip was downloaded to `/tmp/tofu.zip` while `SHA256SUMS` names `tofu_${TOFU_VERSION}_linux_amd64.zip`.
  `sha256sum -c -` opens the filename from the checksum line, so the step always failed with
  `sha256sum: can't open 'tofu_1.10.6_linux_amd64.zip'` and stage 2 aborted. Present since 17-01 (`81b0f54`) —
  independent of the `cd /tmp` -> `WORKDIR /tmp` change, which resolves the cwd identically.
- **Fix:** download to the upstream filename and unzip from it.
- **Files modified:** `iac-runner/Dockerfile`
- **Verification:** `docker build` completes; `tofu version` runs in-stage; the resulting image serves `/v1/version`
  with `runner_version: "0.2.0"`.
- **Committed in:** `32fdca2`

**2. [Rule 3 - Blocker] `make update-version ... NO_TAG=yes` always exited 1**

- **Found during:** Task 4
- **Issue:** `internal/update-version.py` referenced an undefined `new_v` in two `print()` calls on the `--no-tag` path.
  All three version files were written correctly, then the script raised `NameError` and the make target failed with
  `Fehler 1`, skipping the chained `make validate-versions`. The plan mandates exactly this invocation, so the task
  could not complete without fixing it.
- **Fix:** use `config_new` (the subpatch-suffixed version the tag would carry) in the tag-push-failure hint, and make
  the final "Next steps" push line conditional so it no longer suggests pushing a tag that was deliberately skipped.
- **Files modified:** `internal/update-version.py` (outside `files_modified` — Rule 3 blocker)
- **Verification:** re-ran `make update-version ADDON=iac-runner VERSION=0.2.0-0 NO_TAG=yes NO_PUSH=yes` — idempotent,
  exit 0, chained `make validate-versions` passed.
- **Committed in:** `a6d352c`

**3. [Rule 1 - Bug] `build.yaml` `RUNNER_VERSION` left at 0.1.0 after the bump**

- **Found during:** Task 4
- **Issue:** the version script and `internal/validate-versions.sh` both know only `args.VERSION`. `RUNNER_VERSION` is a
  fourth field that feeds `-ldflags -X main.runnerVersion`, so a 0.2.0-0 add-on would have shipped a binary reporting
  `runner_version: "0.1.0"` from `/v1/version`, `/healthz` and the `starting` record.
- **Fix:** hand-set `RUNNER_VERSION: "0.2.0"`. Hand-editing is not a violation of the "never edit versions manually"
  rule: that rule protects the three hook-guarded fields, and this field has no supported tool path. The structural fix
  (teaching the script about sibling `*_VERSION` args) was deliberately NOT attempted here — `terraform-bridge` has the
  same drift (`BRIDGE_VERSION: "0.1.0"` vs `VERSION: "0.3.0"`) and whether those are meant to be in lock-step is not
  this plan's call. Logged in `deferred-items.md`.
- **Files modified:** `iac-runner/build.yaml`
- **Verification:** `make validate-versions` passes; the verify build reported `runner_version: "0.2.0"`.
- **Committed in:** `a6d352c`

**4. [Rule 2 - Missing critical] `runs_retention_hours <= 0` would delete every finished run**

- **Found during:** Task 1
- **Issue:** the plan's behavior spec says "the existing 17-04 implementation logs a warning and does not start a
  ticker" for `retention=0`. It does not: `tickInterval` floors the cadence at `minTickInterval = 1 * time.Minute` and
  starts normally, and `Rotate(0)` treats every terminal run as expired.
- **Fix:** clamp to the 24h schema default in main.go with a `runs_retention_invalid` warning naming both the configured
  and the applied value.
- **Files modified:** `iac-runner/cmd/runner/main.go`
- **Verification:** `go build` + `go vet` + `go test ./...` pass; the boot log shows the normal
  `runs_retention_started{retention_hours:1}` path for an in-range value.
- **Committed in:** `b789ddd`

**5. [Rule 2 - Missing critical] Three startup obligations assigned to 17-07 by earlier plans but absent from the task
actions**

- **Found during:** Task 1
- **Issue:** (a) `runs/retention.go:166` states "17-07 calls Rotate once explicitly at boot so the startup reclaim is a
  distinct, observable log record" and `StartRetentionTicker` deliberately does not rotate on start — without the
  explicit call, nothing reclaims until one full tick elapses. (b) `git/manager.go:177` states "17-07 logs it at
  startup" for `SafeDirectoryWarning()`, which is otherwise silently swallowed and would leave a later "dubious
  ownership" pull failure undiagnosable. (c) the plan's own `must_haves` truth requires `repos_loaded` to list "any
  per-repo key issues", but nothing in the codebase checks per-repo deploy keys (`keys.Validator` covers backend
  credential files only).
- **Fix:** added the boot `Rotate` (`runs_rotated_at_boot`), a `git_safe_directory_guard_failed` warning, and a
  presence-only `repoKeyIssues` helper feeding `repos_loaded.key_issues`.
- **Files modified:** `iac-runner/cmd/runner/main.go`
- **Verification:** observed in the boot log —
  `key_issues:["homelab: missing deploy key /data/keys/homelab.key","missing /data/keys/known_hosts"]`.
- **Committed in:** `b789ddd`

**6. [Rule 1 - Bug] The plan's DOCS.md error_code table had the wrong HTTP statuses**

- **Found during:** Task 3
- **Issue:** the plan's table assigns 502 to most `git_*` codes, 500 to `run_tofu_not_found`, 500 to `apply_timeout` and
  400 + `internal` to a bad `?status=`. The shipped map in `handlers/write_error.go` is 403 (`git_ssh_handshake`,
  `git_unauthorized`), 409 (`git_non_fast_forward`), 404 (`git_ref_not_found`, `git_clone_missing`), 400
  (`git_ref_pull_incompatible`), 502 (`git_dns_failure`, `git_clone_failed`), 503 (`run_tofu_not_found`,
  `run_capacity_exhausted`, `apply_capacity_exhausted`), 504 (`apply_timeout`, `plan_timeout`) — and a bad `?status=`
  returns `run_invalid_dir`. Publishing the plan's table would have shipped documentation that contradicts the code.
- **Fix:** the table documents the real map, cross-read from `write_error.go` and confirmed against the live container
  responses. The four codes that are terminal run states rather than responses are marked as such.
- **Files modified:** `iac-runner/DOCS.md`
- **Verification:** each documented status matches the observed endpoint table above; `markdownlint-cli2` clean.
- **Committed in:** `01f2c51`

### Documentation-contract deviations

**7. `must_haves.artifacts[DOCS.md].contains` expects `iac_runner.redaction.audit`; the real record is
`redaction.audit`.** `handlers/redaction_audit.go:52` emits `slog.InfoContext(ctx, "redaction.audit", ...)` with no
`iac_runner.` prefix. DOCS.md documents the true name — writing the prefixed form would have sent operators grepping for
a string that never appears.

**8. Verification item 9 ("`git diff --stat` for `iac-runner/{config.yaml,build.yaml,Dockerfile}` is empty after Task 4
ran") is superseded.** `config.yaml` is untouched by hand as required, but `build.yaml` MUST change (it carries the
version) and the `Dockerfile` MUST change (the DL3003 fix was explicitly assigned to this plan by the Wave 2 post-merge
gate and both files are listed in `files_modified`). Treated as an internally inconsistent criterion.

### Broken acceptance-criteria greps (verified with corrected patterns; code unchanged)

The known Phase 17 defect class, fourth through seventh instances:

| #   | Criterion                                                                    | Why it cannot match                                                                                                              | Corrected verification                                                                                                                          |
| --- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `httpapi\.NewRouter\(runnerVersion, store, validator, gitMgr, runStore, q\)` | Phase 16 named the variable `keysValidator`; the plan's own action block D writes `keysValidator` too                            | `grep -E 'httpapi\.NewRouter\(runnerVersion, store, keysValidator, gitMgr, runStore, q\)'` — 1 match, and `go build` is the real signature lock |
| 2   | `^func HandleSignals\(.*queue \*jobq\.Queue`                                 | gofmt wraps a six-parameter signature across lines, so `func HandleSignals(` and `queue *jobq.Queue,` are never on the same line | `grep -nE '^func HandleSignals\(\|queue \*jobq\.Queue,'` — lines 79 and 84                                                                      |
| 3   | `^version: "0\.2\.0"$` in `build.yaml`                                       | `build.yaml` has no top-level `version:` key; the version lives at `args.VERSION` (per the repo CLAUDE.md)                       | `grep -E '^\s*VERSION: "0\.2\.0"$' iac-runner/build.yaml` — 1 match; `make validate-versions` passes                                            |
| 4   | `git diff --stat iac-runner/config.yaml iac-runner/Dockerfile` = 0 lines     | The Dockerfile fix is mandated by this plan (see deviation 8)                                                                    | `git diff --stat iac-runner/config.yaml` = 0 lines — the part that is actually a real invariant                                                 |

### Process deviation

**9. Tasks 1 and 2 are one commit (`b789ddd`).** Rationale in Task Commits above: the signature change and its call site
are inseparable without producing a non-compiling intermediate commit.

---

**Total deviations:** 5 auto-fixed (2x Rule 1 code bugs, 1x Rule 3 blocker, 2x Rule 2 missing-critical), 1 documentation
correction (Rule 1), plus 4 broken-grep records, 2 superseded contract items and 1 commit-granularity choice.

**Impact on plan:** No scope creep — every fix is inside a `files_modified` path except `internal/update-version.py`,
which the plan's own mandated command required. Two of the fixes (the Dockerfile checksum, the `--no-tag` `NameError`)
were latent blockers that would have surfaced as CI failures on the release commit rather than here.

## Issues Encountered

**The tofu child process receives no backend credentials.** `internal/jobq/exec.go:91-93` passes `os.Environ()` and its
comment attributes the credential export to this plan. No such export exists anywhere: `statebackend.Backend` offers
`CredentialFiles()` (used only by the SEC-01 keys validator), `run.sh` exports nothing, and `main.go` sets no variables.
Consequences, addressing the two threat notes 17-05 handed over:

- **Credential-env minimality (confirmed):** the exported credential env is empty. No `/data/keys/` content is projected
  into any spawned process. That is the minimum by construction, so the threat note is closed in the conservative
  direction — but it also means `tofu init` against the `r2`/`s3` backends cannot authenticate unless the operator's own
  IaC repo supplies credentials by some other route.
- **Process-spawn surface (confirmed and bounded):** exactly two binaries are spawned. `tofu` is resolved once via
  `exec.LookPath` at `jobq.New` and thereafter invoked by absolute path with an argv the caller never controls
  (`init`/`plan`/`apply` plus fixed flags; the only user-influenced value is the validated `dir`, which becomes
  `cmd.Dir`, never an argument). `git` is invoked with an explicit `GIT_SSH_COMMAND` pinning `IdentitiesOnly=yes`,
  `StrictHostKeyChecking=yes`, `BatchMode=yes` and `GIT_TERMINAL_PROMPT=0`. No shell is involved anywhere.

No Phase 17 requirement covers the projection and ROADMAP Phase 19 SC-3 is the three-backend matrix that will exercise
it against a real bucket, so the design (which variables, from which key file, scrubbed from which logs) is left to
Phase 19 rather than guessed at here. Recorded in `deferred-items.md`.

**`make lint` needed two runs the first time.** The `prettier` hook reformatted six pre-existing `.planning/` markdown
files (table padding in `STATE.md`, `WINDOWS.md`, `ROADMAP.md` and three prior summaries) and reported "files were
modified by this hook". This is the normal auto-fix flow, not a failure: the second run passed. Those reformats are
included in the metadata commit.

**`main.go` is 457 lines.** The plan cites an "AGENTS.md 250-line cap" as the trigger for extracting a `helpers.go`. No
such cap exists in `AGENTS.md` or `.planning/codebase/CONVENTIONS.md` (which sets a 120-character line limit, not a file
limit), and the plan's own acceptance greps require the Options struct, all four constructions and the router call to be
in `cmd/runner/main.go`. Kept in one file; a future split is a cosmetic choice, not a rule violation.

## Known Stubs

None. No hardcoded empty values, placeholders or unwired components were introduced. The credential-env gap above is a
pre-existing absence in `internal/jobq`, not a stub added by this plan.

## Plan verification results

| #   | Check                                                  | Result                                                                                                                                                                                                                                                  |
| --- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `go build ./...`                                       | exit 0                                                                                                                                                                                                                                                  |
| 2   | `go vet ./...`                                         | exit 0                                                                                                                                                                                                                                                  |
| 3   | `go test ./...`                                        | all 9 test packages ok; `-race` (CGO, gcc in-container) also clean                                                                                                                                                                                      |
| 4   | `python3 internal/validate-addon-config.py iac-runner` | passed                                                                                                                                                                                                                                                  |
| 5   | `yamllint iac-runner/config.yaml`                      | exit 0 (also `build.yaml`)                                                                                                                                                                                                                              |
| 6   | `./internal/validate-dockerfile-args.sh`               | passed                                                                                                                                                                                                                                                  |
| 7   | `markdownlint-cli2 iac-runner/DOCS.md`                 | 0 issues (also README.md)                                                                                                                                                                                                                               |
| 8   | no tag, nothing pushed                                 | `git tag --list 'iac-runner/v0.2.0*'` empty; origin ahead-count 66 before and after                                                                                                                                                                     |
| 9   | `config.yaml`/`build.yaml`/`Dockerfile` diff empty     | superseded — see deviation 8                                                                                                                                                                                                                            |
| 10  | all 7 `files_modified` paths changed                   | confirmed via `git diff --stat e3c4e62..HEAD` (8 paths incl. the Rule 3 file)                                                                                                                                                                           |
| 11  | ROADMAP SC-1..SC-11 map to shipped artifacts           | SC-1 (17-01 schema), SC-2/3/4 (17-03 + wiring, empirically observed), SC-5/6 (17-05/17-06, observed 404/400 paths), SC-7/8 (17-08, observed), SC-9 (17-05 mutex, unit-tested), SC-10 (17-04 + 17-08 `redaction.audit`), SC-11 (17-04 + the wiring here) |
| —   | `make lint`                                            | exit 0 — hadolint DL3003 closed; no lint failures remain in the phase                                                                                                                                                                                   |
| —   | local `docker build`                                   | image built (project CLAUDE.md requirement) and smoke-run end-to-end                                                                                                                                                                                    |

## Self-Check: PASSED

- All 8 modified files exist on disk and appear in `git diff --stat e3c4e62..HEAD`.
- All 4 task commits exist: `b789ddd`, `32fdca2`, `01f2c51`, `a6d352c`.
- `grep -rn 'TODO(17-07)' iac-runner/cmd iac-runner/internal` returns no matches.
- Every task acceptance criterion passes, except the four regex-defective ones verified with corrected patterns above.

## Outstanding operator action

**The `iac-runner/v0.2.0-0` tag is intentionally not created and nothing was pushed.** When ready to publish the image:

```bash
git fetch origin && git status -sb          # confirm the branch is not behind
make update-version ADDON=iac-runner VERSION=0.2.0-0   # no NO_* flags: creates + pushes the tag
```

Pushing that tag fires the `build-iac-runner` image workflow, which is why it is deferred while the v1.2 Cloudflare
prerequisite recorded in ROADMAP.md is still open.

## User Setup Required

None for this plan. For runtime use, an operator must place per-repo SSH deploy keys at `/data/keys/<repo-name>.key` and
a `known_hosts` at `/data/keys/known_hosts` (both chmod 600) — now documented in DOCS.md's first-time setup, and
reported at boot in `repos_loaded.key_issues` when missing.

## Next Phase Readiness

Phase 17 is code-complete: all 8 plans have summaries and the binary composes end-to-end. Ready for Phase 18 (MQTT
Discovery), which needs the run store and job queue this plan constructed.

Two items travel forward to Phase 19:

- The backend-credential env projection (see Issues Encountered) must be designed before SC-3's three-backend matrix can
  pass.
- No `tofu plan`/`apply` has ever run against real infrastructure. Everything proven here is startup, routing, error
  taxonomy and shutdown; the actual OpenTofu execution path is unit-tested against an injected `ExecFunc` only.

---

_Phase: 17-git-integration-apply-job-system_ _Completed: 2026-09-08_
