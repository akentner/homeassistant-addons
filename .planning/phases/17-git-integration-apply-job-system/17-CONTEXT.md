# Phase 17: Git Integration + Apply Job System - Context

**Gathered:** 2026-09-06 **Status:** Ready for planning

<domain>

## Phase Boundary

The `iac-runner` add-on clones configured Git repos at startup, exposes an SSH-keyed pull endpoint, and provides a
queued-job lifecycle for `tofu plan` / `tofu apply` with per-repo serialization, paginated run history, and
secret-redacted output. Manual REST trigger only — MQTT Discovery wiring and `/v1/runs/{id}/cancel` are deferred to
later phases.

Specifically this phase delivers:

- `config.yaml` Options additions: `repos` (list), `max_parallel_jobs`, `apply_timeout_minutes` (the latter two are new,
  governed by Phase 17 decisions; `runs_retention_hours` already on roadmap)
- Startup behavior: per-repo clone at `/data/repos/<name>/` with auto-retry backoff (1s/5s/30s, 3 attempts), failure
  surface as `git_clone_missing` on subsequent plan/apply (logged at boot, not fatal)
- `POST /v1/repos/{name}/pull` runs `git pull --ff-only` (or `git fetch + git checkout` when `ref` is set) using
  `/data/keys/<name>.key` + `/data/keys/known_hosts`; typed `git_*` errors with `error_code` taxonomy
- `POST /v1/plan` and `POST /v1/apply` queue a job (HTTP 202 + `Location: /v1/runs/{id}`); per-repo mutex serializes
  same-repo requests, `max_parallel_jobs` bounds total concurrent jobs, `apply_timeout_minutes` SIGTERMs the tofu
  process at expiry
- `GET /v1/runs/{id}` and `GET /v1/runs` return per-run JSON with paginated JSONL output lines, secret-redacted at read
  time per SEC-03 patterns
- Run metadata persisted as `/data/runs/{id}/meta.json` + `/data/runs/{id}/output.log`; `runs_retention_hours`
  background ticker (every `retention/4` hours) deletes old run dirs

**What this phase is NOT:** MQTT Discovery sensors/buttons (Phase 18), cancel endpoint (`POST /v1/runs/{id}/cancel`),
live progress streaming via Ingress/WebUI (v1.5 backlog), hermetic E2E verification on a real HA host (Phase 19),
web-side multi-repo UI (v1.5 deferred per PROJECT.md §Out of Scope).

</domain>

<decisions>

## Implementation Decisions

### Run metadata persistence

- **D-01:** Per-run directory `/data/runs/{run_id}/meta.json` (status, exit_code, started_at, finished_at, repo, kind) +
  `/data/runs/{run_id}/output.log` (JSONL stream). Writes use flock + atomic rename to prevent torn reads from
  concurrent writers.
- **D-02:** On boot, any run still marked `running` is transitioned to `interrupted` (its tofu process is gone with the
  previous run; the user gets a stable post-mortem status). The `interrupted` enum joins
  `queued|running|succeeded|failed` for `?status=` filter responses.
- **D-03:** Run dir naming: `{run_id}` is a 16-char base32-encoded `crypto/rand` token (collision-free at this workload;
  UUIDv4 acceptable alternative).

### Concurrent apply job cap

- **D-04:** New Options `max_parallel_jobs` with default `4`, range `1..32`, integer type. Implemented as a buffered
  channel semaphore wrapping the per-repo mutex map.
- **D-05:** Per-repo mutex held in a `sync.Map[string, *sync.Mutex]` (lazy create-on-first-use). Mutex is in-process
  only; cross-restart serialization is not guaranteed (matches RUN-06 spec).
- **D-06:** When `max_parallel_jobs` is saturated, new `POST /v1/plan` / `/v1/apply` requests return HTTP 503 with
  `error_code: "apply_capacity_exhausted"` + `Retry-After: 30` header (operator-facing knob to surface back-pressure,
  not silently queue).

### Output format + redaction timing

- **D-07:** `/data/runs/{run_id}/output.log` is JSONL with shape
  `{"ts":"<RFC3339>","stream":"stdout|stderr","line":"<raw>"}` per captured line. Raw output is preserved on disk for
  operator debug via `cat | jq`.
- **D-08:** SEC-03 regex redaction (R2 access keys `^[A-Z0-9]{20}$`, AWS secret keys `^[A-Za-z0-9/+=]{40}$`, SSH
  private-key headers `-----BEGIN`) is applied at GET `/v1/runs/{id}` response time, NOT at write time. A
  `redaction.audit` slog record counts redactions per run.
- **D-09:** Output lines are written verbatim — no truncation. File size grows with verbose plans; OBS-03 pagination
  (default 100 lines, max 1000) keeps API responses bounded.

### `ref` semantics (GIT-01)

- **D-10:** When `ref` is set on a repo entry, both startup-clone and `POST /v1/repos/{name}/pull` execute
  `git fetch origin <ref> && git checkout FETCH_HEAD` (for SHAs) or `git checkout <ref>` (for branches/tags) instead of
  `git pull --ff-only`. The `branch` field is ignored when `ref` is non-empty.
- **D-11:** When `ref` is empty, behavior is the spec-default `git pull --ff-only` (or clone on first run).
- **D-12:** `git pull` with non-empty `ref` is rejected at parse time (400 `error_code: "git_ref_pull_incompatible"`) —
  `/pull` semantics mean fast-forward on the configured branch; `ref` is for explicit pinning only.

### Startup clone recovery

- **D-13:** On boot, if `/data/repos/<name>/` is missing or empty, attempt `git clone` with backoff: 1s, 5s, 30s (3
  attempts). After the third failure, log `git_clone_failed` with structured error (SSH handshake / DNS / etc.) and
  continue startup (no degraded mode per AGENTS.md Live Systems rule).
- **D-14:** Subsequent `/v1/plan` or `/v1/apply` targeting a repo whose clone failed returns
  `error_code: "git_clone_missing"` (404) so the operator knows the precondition isn't met.

### Apply timeout

- **D-15:** New Options `apply_timeout_minutes` with default `60`, range `5..1440`, integer type. The runner spawns the
  tofu process via `os/exec.CommandContext` with a context deadline derived from this Option.
- **D-16:** At expiry, the runner sends SIGTERM via the context; if the process is still alive after 10s grace, SIGKILL
  is sent. The run is marked `failed` with `error_code: "apply_timeout"`. The per-repo mutex and `max_parallel_jobs`
  slot are released via `defer` in the worker goroutine.

### Plan file lifecycle

- **D-17:** `/v1/apply` accepts requests without a matching prior `/v1/plan`. When no prior plan file exists for the
  same `(repo, dir)` tuple, the runner executes inline `tofu apply -no-color -auto-approve` (no `-out` flag, no plan
  file consumption).
- **D-18:** When a prior `/v1/plan` succeeded for the same `(repo, dir)` and its `meta.json` is still on disk,
  `/v1/apply` uses `tofu apply -no-color -auto-approve /data/runs/{plan_run_id}/plan.tfplan`. If the prior plan file is
  missing (e.g. retention swept it), falls back to inline apply.

### Error code taxonomy

- **D-19:** Stable `error_code` taxonomy (extend as new failure modes emerge):
  - `git_*`: `ssh_handshake`, `dns_failure`, `ref_not_found`, `unauthorized`, `non_fast_forward`, `clone_failed`,
    `clone_missing`, `ref_pull_incompatible`
  - `run_*`: `tofu_not_found`, `invalid_dir`, `unknown_repo`, `unknown_id`, `not_found`, `capacity_exhausted`
  - `apply_*`: `already_running`, `timeout`, `failed`
  - `auth_*`: `unauthorized` (existing AUTHR-02 reuse)
- **D-20:** New codes are additive — old API consumers keep working when new codes appear. Adding new codes requires
  updating `internal/contract/types.go`'s ErrorResponse constant set + the docs.

### `dir` validation

- **D-21:** Strict parse-time validation on `POST /v1/plan` and `/v1/apply`:
  - Reject leading `/` (must be relative path)
  - Reject any `..` segment (after `filepath.Clean`)
  - Reject null bytes
  - Reject empty string (operator must explicitly set `dir: ""` for repo root; or accept empty as root and document it)
- **D-22:** On validation failure, return 400 with `error_code: "run_invalid_dir"` and an actionable message ("dir must
  be a relative path under the repo working tree; leading '/' and '..' segments are forbidden").
- **D-23:** Empty `dir` is allowed and means the repo root (`/data/repos/<name>/`). Documented in DOCS.md as the "no
  subdir" case.

### Output line length

- **D-24:** No per-line truncation. Output lines are written verbatim to `/data/runs/{run_id}/output.log`. OBS-03
  pagination handles large outputs at the API layer (default 100 lines, max 1000).
- **D-25:** Disk-usage bound: `runs_retention_hours` rotation prevents unbounded growth across runs. A single
  pathological run can still grow large; the `runs_retention_hours` defaults to 24h so worst-case disk usage is
  `max_parallel_jobs × avg-run-size × retention-period-hours`.

### the agent's Discretion

- Exact `run_id` generation (base32 from `crypto/rand` is the default; UUIDv4 acceptable)
- Internal package layout for the new packages (`internal/git/`, `internal/runs/`, `internal/jobq/` are likely
  candidates)
- Whether to publish a `/v1/repos/{name}/status` endpoint that surfaces clone-state at runtime (not required by any
  spec, but helpful for HA MQTT Phase 18 to consume)
- File permissions on `/data/runs/` and per-run directories (chmod 700 default; chmod 600 on the log file matches the
  SEC-01 keys pattern)
- Whether the `max_parallel_jobs` semaphore is implemented as a buffered channel, a counting semaphore struct, or
  `golang.org/x/sync/semaphore`
- Exact backoff curve for the 3-attempt startup clone (1s/5s/30s is the default; 1s/3s/10s or 5s/30s/120s acceptable)

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary + success criteria (HIGH confidence)

- `.planning/ROADMAP.md` §"Phase 17: Git Integration + Apply Job System" — the 11 success criteria (SC-1..SC-11) the
  phase must satisfy
- `.planning/REQUIREMENTS.md` §"GIT — Git Integration" GIT-01..04 — schema, startup clone, pull, error taxonomy
- `.planning/REQUIREMENTS.md` §"RUN — Runner HTTP API" RUN-01..06 — version endpoint, plan/apply, runs pagination,
  per-repo mutex semantics
- `.planning/REQUIREMENTS.md` §"SEC — Secrets" SEC-03 — output redaction patterns + audit record
- `.planning/REQUIREMENTS.md` §"OBS — Observability" OBS-02..03 — output capture format + runs pagination
- `.planning/PROJECT.md` §"Current Milestone: v1.4 iac-runner" — locked architecture decisions (port 8125,
  Tailscale-bind-gate, manual REST trigger only, multi-backend state)

### Prior phases (locked, not re-discussed)

- `.planning/phases/15-ci-hardening-provider-install-workflow/15-CONTEXT.md` — pattern for hermetic Go verifier scripts
  (`internal/verify-*.sh`) Phase 17 may reuse for end-to-end runner verification
- `.planning/codebase/CONVENTIONS.md` — 120-char line limit, YAML 2-space indent, snake_case option names, shellcheck
  SC1091/SC2034 ignored
- `.planning/codebase/ARCHITECTURE.md` — 4-file add-on pattern (config.yaml / build.yaml / Dockerfile / run.sh)

### Existing iac-runner code (HIGH confidence)

- `iac-runner/config.yaml` — current schema fields (bind_address, bind_allowed_subnets, state_backend, r2__, s3__);
  Phase 17 adds `repos`, `max_parallel_jobs`, `apply_timeout_minutes`
- `iac-runner/internal/contract/types.go` — ErrorResponse shape with `error_code` field; extend with new status enums
  (`interrupted`) and new codes per D-19
- `iac-runner/internal/httpapi/router.go` — chi router with `r.Route("/v1", ...)` block ready for new endpoints
  (`/v1/repos/{name}/pull`, `/v1/plan`, `/v1/apply`, `/v1/runs/{id}`, `/v1/runs`)
- `iac-runner/cmd/runner/main.go` — startup pipeline (read options → resolve bind → init state backend → validate keys →
  token store → router → server); Phase 17 adds git-clone-on-startup step after keys validation
- `iac-runner/internal/auth/middleware.go` — `auth.RequireBearer(store)` used inside the `/v1` subroute; new endpoints
  inherit this automatically
- `iac-runner/internal/keys/validator.go` — `keys.NewValidator(dir, backend)` pattern for fail-fast startup validation;
  Phase 17 may add a parallel `git.Validator` for `/data/keys/<name>.key` per-repo existence
- `iac-runner/internal/logging/scrubbing_handler.go` — slog.Handler wrapper; new code paths that log inherit scrubbing
  automatically

### Established patterns (HIGH confidence)

- **Per-slug mutex map** (Phase 12, terraform-bridge) — `sync.Map` of per-resource mutexes; Phase 17 applies the same
  pattern to per-repo mutexes (`sync.Map[string, *sync.Mutex]`)
- **`slog` JSON + scrubbing** (SEC-02) — apply per-run via `slog.With("run_id", id, "repo", name, "kind", kind)` and the
  worker logs scrubbing-inherited
- **HTTP-typed errors** (AUTHR-02 + Phase 12) — every 4xx/5xx returns `contract.ErrorResponse` with a stable
  `error_code`; Phase 17's error_code taxonomy extends this contract
- **File-on-volume** (PROJECT.md locked) — credentials + state + run metadata all live as files under `/data/`; no
  embedded DBs in v1.4 (Phase 16 STBK-01..05 chose file-state over Terraform Cloud)

### State backend integration

- `iac-runner/internal/statebackend/backend.go` — `Backend` interface; Phase 17 run dir layout is independent of state
  backend (tofu's own state lives where the backend puts it; runner only cares about run metadata
  - output capture)
- `iac-runner/internal/statebackend/factory.go` — three backends (r2/s3/local); per-run `tofu init` / `tofu plan` /
  `tofu apply` invocations inherit the configured backend via `terraform { backend "<name>" { ... } }` in the user's
  repo (out of runner's control)

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- **`contract.ErrorResponse`** (`iac-runner/internal/contract/types.go`) — typed error body; Phase 17 error responses
  reuse this shape directly
- **`httpapi.NewRouter(runnerVersion, store, validator)`** (`iac-runner/internal/httpapi/router.go`) — chi router; Phase
  17 extends the `/v1` subroute with new endpoints, no signature change required if dependencies are threaded as
  constructor params
- **`keys.NewValidator(dir, backend)`** (`iac-runner/internal/keys/validator.go`) — fail-fast startup validator pattern;
  Phase 17 may add a `git.NewRepoValidator(dir, repoList)` for `/data/keys/<name>.key` per-repo existence
- **`logging.NewScrubbingHandler`** (`iac-runner/internal/logging/scrubbing_handler.go`) — slog.Handler wrapper; new
  code paths inherit scrubbing via `slog.With(...)` chains
- **`auth.RequireBearer(store)`** (`iac-runner/internal/auth/middleware.go`) — middleware applied at the `/v1` subroute;
  new endpoints inherit auth automatically
- **`statebackend.Factory`** (`iac-runner/internal/statebackend/factory.go`) — three backend impls with factory pattern;
  Phase 17 doesn't extend this but invokes tofu with the user's repo's backend config (transparent to runner)

### Established Patterns

- **Chi router with `/v1` subroute + auth middleware** — `/v1` is wrapped with `auth.RequireBearer(store)`; Phase 17
  endpoints live inside this subroute and inherit the auth gate
- **Constructor-injected handlers** — `handlers.Healthz(runnerVersion, validator)` pattern;
  `handlers.Version(runnerVersion)` pattern; Phase 17 follows with `handlers.ReposPull(gitMgr)` / `handlers.Plan(jobq)`
  / `handlers.Apply(jobq)` / `handlers.GetRun(runs)` / `handlers.ListRuns(runs)`
- **ErrorResponse per error site** — every handler returns `contract.ErrorResponse` with a typed code; handler-level
  error wrapping lives in the handler, not in middleware
- **Lifecycle via `cmd/runner/signals.go`** — SIGTERM 30s drain + SIGHUP log-reopen; Phase 17 worker goroutines register
  with the drain coordinator so in-flight apply jobs get 30s grace before hard exit
- **`/data/keys/` chmod-600 enforcement** (SEC-01) — keys.Validator ensures credentials are chmod 600 before the runner
  accepts traffic; Phase 17's git deploy keys + `known_hosts` extend the required-file list per configured repo

### Integration Points

- **Phase 18 MQTT Discovery** — Phase 18 subscribes to job-status changes via an internal channel or poll loop on
  `runs`. Phase 17 exposes the run-status-changed event surface (decision deferred to Phase 18 planner whether to use a
  Go channel, an `http.Handler` callback, or `slog.Default().Info("run.status", ...)` records that a subscriber tails)
- **Phase 19 Live-HA empirical verification** — Phase 19 will run `tofu init/plan/apply` against a real HA host; Phase
  17's `/data/repos/` clone + `/v1/plan`/`/v1/apply` endpoints are the Phase 19 verification surface
- **State backend** — tofu runs in the user's repo with their configured backend; runner doesn't manage tofu state
  directly. Run output includes tofus's own state-locking messages (the user sees them via the run's output_lines)

</code_context>

<specifics>

## Specific Ideas

- **JSONL output for debuggability** — `cat /data/runs/{id}/output.log | jq` should give the operator a clean stream of
  `{ts, stream, line}` records. This is the only format where the user can grep one tofu-process's stderr across pages
  of a long apply.
- **`runs_retention_hours` + `runs/retention-hours/4` ticker cadence** — already on ROADMAP; Phase 17 keeps that
  pattern. Default 24h retention, ticker every 6h.
- **Per-repo mutex + global semaphore** — RUN-06 says applies on the same repo serialize; Phase 17 extends with a global
  cap (`max_parallel_jobs`) so a misconfigured fleet of repos can't overwhelm the homelab Tailscale subnet.
- **`apply_timeout_minutes` SIGTERM-first, SIGKILL-after-10s** — gives tofu a chance to release its state-lock cleanly
  (R2/S3 lockfile release is a single S3 DELETE; local-lock is unlink). 10s grace is short enough to keep mutex-release
  timely, long enough for the lock-release RPC to complete.
- **`interrupted` status on boot** — distinguishes "tofu process died unexpectedly" (interrupt from SIGKILL/SIGTERM
  during a previous run) from `failed` (tofu exited non-zero). Operators see both in HA UI; the distinction matters for
  runbook-driven diagnosis.
- **`/v1/plan` is optional** — operators who want preview-before-apply call both; operators who trust their IaC just
  call `/v1/apply` directly. The runner supports both modes via D-17/D-18.
- **Ref pin overrides branch on pull** — if both `branch` and `ref` are set, `ref` wins; the runner surfaces a
  startup-time log warning so the operator knows their config is being interpreted as a pin.

### Post-decision refinements worth noting

- **`max_parallel_jobs` is independent of repo count** — a single repo with `max_parallel_jobs: 1` serializes
  everything; a single repo with `max_parallel_jobs: 4` is the same as before (per-repo mutex is already 1). The Option
  matters when there are 2+ repos AND the operator wants to bound total parallelism.
- **`apply_timeout_minutes` applies to `/v1/apply` only** — `/v1/plan` is bounded by its own implicit timeout (same
  value reused for symmetry, or shorter default like 10 minutes). Either way the runner surfaces a `plan_timeout`
  error_code if exceeded.

</specifics>

<deferred>

## Deferred Ideas

- **Ingress / WebUI with live progress streaming** (v1.5 backlog) — scope creep flagged during discuss-phase. PROJECT.md
  §"Out of Scope" already defers "Multi-Repo UI" to v1.5; live-output SSE over Ingress is a new capability (no Ingress
  integration exists in Phase 16's scaffold; the Phase 18 MQTT Discovery is the v1.4 HA-side UI for status). Owner:
  future v1.5 milestone.
- **`POST /v1/runs/{id}/cancel` endpoint** — could be added in a future phase or as Phase 19 E2E follow-up. Not required
  by any spec success criterion; the `apply_timeout_minutes` SIGTERM path covers the "I want to stop a runaway apply"
  use case for v1.4.
- **Real-HA empirical verification** — Phase 19 owns it. Phase 17 ships unit-tested code; the live homelab verification
  is its own phase.
- **Web-side multi-repo UI** — PROJECT.md §"Out of Scope" explicit deferral. v1.4 supports one or more configured repos
  via Options; no UI for listing/switching repos.
- **Cross-restart mutex persistence** — RUN-06 spec locks in-process mutex; restart-during-apply means the next start
  sees `running` status and the boot transition marks it `interrupted` (D-02). No cross-restart resume.
- **Approval-gate before `tofu apply`** — PROJECT.md §"Out of Scope" explicit deferral. Manual REST trigger IS the
  approval gate for v1.4.

</deferred>

---

_Phase: 17-git-integration-apply-job-system_ _Context gathered: 2026-09-06_
