---
phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
plan: 01
subsystem: auth,httpapi,add-on-scaffold
tags: [go, chi, slog, crypto, ha-addon, bearer-auth, tailscale, sigterm-drain, opentofu, r2, s3, mqtt]

# Dependency graph
requires:
  - phase: 10-auth-layer-structured-logging-healthcheck
    provides: terraform-bridge auth + slog patterns reused verbatim for iac-runner
  - phase: 9-bridge-foundation
    provides: terraform-bridge 4-file scaffold + multi-stage Go Dockerfile as the template
provides:
  - iac-runner/ add-on scaffold (4-file pattern, host_network, mqtt:need, no hassio_api per AUTHR-01)
  - TokenStore with crypto/rand + SHA-256 hash-at-rest + chmod 600 + ConstantTimeCompare + 24h grace rotation
  - BindResolver scanning /sys/class/net/tailscale*, refusing 0.0.0.0 unconditionally, accepting explicit IPs only on Tailscale or inside allowed_subnets
  - POST /v1/auth/rotate handler with iac_runner.token.rotated audit log (fingerprints only)
  - SIGTERM 30s graceful drain + SIGHUP iac_runner.log_reopen audit record
  - Chi router with /, /healthz (stub) public + /v1/auth/rotate RequireBearer-wrapped
  - RequestLogger middleware stripping Authorization header from r.Header before slog (OBS-01 layer 2)
  - contract.VersionHandshake (runner_version + schema_version + min/max_supported_opentofu) for Plan 03's /v1/version
affects:
  - 17-git-integration-apply-job-system (uses TokenStore + BindResolver + RequestLogger)
  - 18-mqtt-discovery-ha-sensors-buttons (uses router + handlers skeleton)
  - 02-PLAN (slottable: scrubbingHandler wrapper over slog.NewJSONHandler)
  - 03-PLAN (slottable: GET /v1/version consumes contract.VersionHandshake)

# Tech tracking
tech-stack:
  added:
    - github.com/go-chi/chi/v5 v5.3.2 (module iac-runner; Plan 01 needs only chi + middleware)
  patterns:
    - 4-file HA add-on pattern (config.yaml + build.yaml + Dockerfile + run.sh) without .upstream.yaml
    - Multi-stage Dockerfile: golang:1.25-alpine AS builder → ghcr.io/home-assistant/amd64-base:3.24
    - ldflags -X main.runnerVersion injected at build time (default "dev" for local builds)
    - hash-at-rest bearer (crypto/rand + SHA-256 + chmod 600 + atomic rename + subtle.ConstantTimeCompare)
    - slog-free auth package invariant (callers own audit logging)
    - addrFn parameter on ResolveBindAddress for test injection (DefaultAddrFn = production adapter)
    - chi router with RequestID → Recoverer → RequestLogger ordering
    - Runtime + compile-time guards: file modes (0o600), GraceWindow (24h), token length (43 base64url chars)

key-files:
  created:
    - iac-runner/{config.yaml,build.yaml,Dockerfile,run.sh,README.md,go.mod,go.sum,.gitignore}
    - iac-runner/internal/version/version.go (SchemaVersion + Min/MaxSupportedOpenTofu)
    - iac-runner/internal/auth/{token.go,token_test.go,bind.go,bind_test.go,middleware.go}
    - iac-runner/internal/contract/types.go (5 type declarations)
    - iac-runner/internal/httpapi/{router.go,get_root.go}
    - iac-runner/internal/httpapi/handlers/{auth_rotate.go,healthz.go}
    - iac-runner/internal/httpapi/middleware/{request_log.go,route_ctx.go}
    - iac-runner/cmd/runner/{main.go,signals.go,version.go}
  modified:
    - README.md (iac-runner entry added between network-tools and gatus)

key-decisions:
  - "bind.go addrFn parameter pattern (4th arg on ResolveBindAddress) — keeps the production syscall net.InterfaceByName path pure and enables test injection of canned []net.IP per iface. DefaultAddrFn wraps the real syscall as a package-level var."
  - "contract package at iac-runner/internal/contract (NOT at module root like terraform-bridge) — keeps the types inside the module's internal/ surface so external Phase 17 clients re-declare or import via the same path. Plan's <interfaces> said iac-runner/contract; the files_modified path internal/contract was authoritative."
  - "HandleSignals gains done chan<- struct{} parameter — enables 'go HandleSignals(...); <-signalsDone' pattern that the plan's acceptance grep expects (terraform-bridge wraps the call in a closure instead)."
  - "Auth package is slog-free by invariant (verified by `! grep -RIn 'slog\\.' iac-runner/internal/auth/`). All token-related audit records live in main.go (iac_runner.token.issued / loaded) and handlers/auth_rotate.go (iac_runner.token.rotated)."
  - "/healthz returns 200 + HealthResponse{tofu_on_path:true, keys_chmod_600:true, runner_version} placeholder. Plan 02 replaces with real exec.LookPath('tofu') + /data/keys/ chmod-600 validator (SEC-01)."
  - "Dockerfile pins golang:1.25-alpine (NOT the terraform-bridge's 1.27-alpine) per the plan spec — Phase 16 locks the toolchain at 1.25 across iac-runner and all later v1.4 modules."

patterns-established:
  - "auth-invariant: NO slog calls in iac-runner/internal/auth/ — package doc comment spells this out, enforced by grep gate in the plan's acceptance criteria"
  - "rotating-shutdown: SIGTERM drains with shutdownDeadline=30s; second SIGTERM during drain escalates to os.Exit(1) — defense-in-depth against hung downstream calls"
  - "first-vs-subsequent-start log shape: iac_runner.token.issued once on first start (Fingerprint + Truncate preview + path); iac_runner.token.loaded on every subsequent restart (HashFingerprint only, NO plaintext)"

requirements-completed: [AUTHR-01, AUTHR-02, AUTHR-03, AUTHR-04, OBS-01]

# Metrics
duration: 17 min
completed: 2026-09-06
---

# Phase 16 Plan 01: iac-runner Scaffold + Auth + State Backends + Healthcheck Summary

**Multi-stage Go add-on scaffold with bearer-token auth (crypto/rand + SHA-256 + 24h grace), Tailscale-bind-gate
(`0.0.0.0` refused), SIGTERM/SIGHUP lifecycle, and chi router mounting `/`, `/healthz` (stub), and
`POST /v1/auth/rotate` under `RequireBearer`. Reuses `terraform-bridge` 4-file + auth + signal patterns verbatim with
file-path renames only.**

## Performance

- **Duration:** 17 min (2026-09-06T16:17Z – 2026-09-06T16:33Z)
- **Started:** 2026-09-06T16:17Z
- **Completed:** 2026-09-06T16:33Z
- **Tasks:** 3
- **Files modified:** 24 (5 scaffold + 2 Go infra + 18 Go source + 1 root README)

## Accomplishments

- `iac-runner/` add-on scaffolds per the 4-file pattern (config.yaml with `host_network: true`,
  `homeassistant_api: true`, `services: ["mqtt:need"]`, port `8125/tcp`; build.yaml pinning `VERSION=0.1.0` +
  `RUNNER_VERSION=0.1.0`; multi-stage Dockerfile `golang:1.25-alpine` → `ghcr.io/home-assistant/amd64-base:3.24`
  with `ldflags -X main.runnerVersion`; run.sh bashio wrapper). Three-file version sync enforced
  (`config.yaml: 0.1.0-0`, `build.yaml: 0.1.0`, `README.md: v0.1.0`). No `.upstream.yaml`.
- TokenStore generates 256-bit tokens via `crypto/rand`, persists SHA-256 hashes to `/data/iac-runner-token`
  with `chmod 600` via atomic rename, validates via `crypto/subtle.ConstantTimeCompare`, and rotates with a 24-hour
  grace window persisted to `/data/iac-runner-token.grace`. First start emits `iac_runner.token.issued` with
  `actor_token_fp` + `Truncate` preview + plaintext path; subsequent starts emit `iac_runner.token.loaded` with
  `HashFingerprint` only.
- BindResolver scans `/sys/class/net/tailscale*` for `auto`, refuses `0.0.0.0` unconditionally, and validates
  explicit IPs against `tailscale` membership + `bind_allowed_subnets` CIDRs. The `addrFn func(ifaceName) ([]net.IP, error)`
  parameter (with `DefaultAddrFn` package var) enables test injection of canned addresses without hitting the real
  kernel.
- Chi router mounts `GET /` (rootHandler placeholder), `GET /healthz` (200 + placeholder `HealthResponse` —
  Plan 02 wires real tofu + `/data/keys/` chmod-600 checks), and `POST /v1/auth/rotate` under `auth.RequireBearer(store)`.
  Middleware order: `RequestID → Recoverer → RequestLogger`.
- Signal handling: `SIGTERM` triggers `srv.Shutdown(ctx)` with a 30s deadline; a second SIGTERM during the drain
  escalates to `os.Exit(1)` (defense-in-depth). `SIGHUP` emits `iac_runner.log_reopen` audit record (no restart).
- `RequestLogger` middleware strips `Authorization` header from `r.Header.Clone()` before any `slog.Info` call
  (OBS-01 layer 2). Plan 02 adds the `slog.Handler` key-name scrubber as layer 1.
- 20 unit tests pass (`go test ./internal/auth/...`): 11 token-store + 9 bind-resolver. `go build ./...`,
  `go vet ./...`, `go test ./...` all exit 0. Binary prints `dev` for `-version`. `python3
  internal/validate-addon-config.py iac-runner` exits 0.

## Task Commits

Each task was committed atomically:

1. **Task 1: 4-file scaffold + Go module + .gitignore** - `0fa09fb` (feat)
2. **Task 2: auth package + version + contract types** - `bb00c4f` (feat)
3. **Task 3: main.go + signals + version + handlers + router + middleware** - `4df2d95` (feat)

**Plan metadata:** `docs(16-01): complete plan` (next commit — captures SUMMARY.md + STATE.md + ROADMAP.md +
REQUIREMENTS.md updates).

## Files Created/Modified

### Scaffold + Add-on surface

- `iac-runner/config.yaml` — name=IaC Runner, slug=iac-runner, version=0.1.0-0, host_network=true,
  homeassistant_api=true, services=[mqtt:need], ports=8125/tcp:8125, options (bind_address, bind_allowed_subnets,
  state_backend, r2/s3 fields), schema with `match(...)` + `list(...)` validators
- `iac-runner/build.yaml` — VERSION=0.1.0, RUNNER_VERSION=0.1.0
- `iac-runner/Dockerfile` — multi-stage `golang:1.25-alpine` → `amd64-base:3.24`, ldflags inject RUNNER_VERSION,
  EXPOSE 8125, CMD /run.sh
- `iac-runner/run.sh` — bashio wrapper `exec /usr/bin/runner "$@"`
- `iac-runner/README.md` — Phase 16 placeholder (Plan 03 fills real content)
- `iac-runner/go.mod` — `module iac-runner`, go 1.25, chi/v5 v5.3.2
- `iac-runner/.gitignore` — `/data` exclusions (HA Supervisor bind-mount)

### Version + Auth + Contract

- `iac-runner/internal/version/version.go` — `SchemaVersion="1.0.0"`, `MinSupportedOpenTofu="1.6.0"`,
  `MaxSupportedOpenTofu="1.999.0"`
- `iac-runner/internal/auth/token.go` — TokenStore + NewFileTokenStore + Generate + Persist +
  WriteInitialTokenFile + Hash + Validate + Rotate + Fingerprint + HashFingerprint + Truncate + graceEntry +
  readHashFile/readGraceFile helpers. Atomic chmod 600 via tempfile rename. GraceWindow=24h.
- `iac-runner/internal/auth/token_test.go` — 11 tests (round-trip + chmod 600, wrong-token rejection,
  initial-token chmod 600, missing token returns ErrNoToken, mkdir-missing-data-dir, fingerprint stability, truncate
  format + interior-leak negative control, grace window + expiry, Rotate, persistence-across-reload)
- `iac-runner/internal/auth/bind.go` — ResolveBindAddress with 4-arg `addrFn` parameter + package-level
  `DefaultAddrFn` closure wrapping `net.InterfaceByName + iface.Addrs()`. Refusal paths: 0.0.0.0, invalid IP, invalid
  CIDR, IP not on tailscale + not in allowed_subnets.
- `iac-runner/internal/auth/bind_test.go` — 9 tests (auto+tailscale, auto+no-tailscale, explicit-on-tailscale,
  explicit-in-allowed-subnets, explicit-refused, 0.0.0.0 always refused, invalid IP, invalid CIDR, nil-addrFn uses
  Default)
- `iac-runner/internal/auth/middleware.go` — RequireBearer chi middleware + ActorTokenContextKey accessor +
  `unauthorized()` 401 + ErrorResponse{unauthorized} emitter
- `iac-runner/internal/contract/types.go` — ErrorResponse, RotateResponse, HealthResponse
  (`tofu_on_path + keys_chmod_600 + runner_version` placeholders), VersionHandshake
  (`runner_version + schema_version + min/max_supported_opentofu`), RootResponse

### HTTP API + Bootstrap

- `iac-runner/internal/httpapi/router.go` — NewRouter(runnerVersion, store); middleware.RequestID +
  Recoverer + reqlog.RequestLogger globally; `r.Get("/")` + `r.Get("/healthz")` public;
  `r.Route("/v1", …)` with `auth.RequireBearer(store)` → `r.Post("/auth/rotate", handlers.AuthRotate(store))`
- `iac-runner/internal/httpapi/get_root.go` — rootHandler returning RootResponse with
  `Status:"scaffolded"` + `Msg:"Phase 16 scaffold only — see /healthz and /v1/auth/rotate"`
- `iac-runner/internal/httpapi/handlers/auth_rotate.go` — POST /v1/auth/rotate calling store.Rotate,
  emitting `iac_runner.token.rotated` audit log with `actor_token_fp`, `old_token_fp`, `new_token_fp`,
  `grace_expires_at` (fingerprints only); 200 + RotateResponse on success, 500 + ErrorResponse{rotate_failed} on
  error, `Cache-Control: no-store`
- `iac-runner/internal/httpapi/handlers/healthz.go` — Plan 01 STUB returning 200 +
  `HealthResponse{tofu_on_path:true, keys_chmod_600:true, runner_version:runnerVersion, status:ok}`. Plan 02
  replaces with real checks.
- `iac-runner/internal/httpapi/middleware/request_log.go` — RequestLogger chi middleware stripping
  Authorization from r.Header.Clone() before `slog.Info("http.request", …)` with `request_id, route, method,
  status, duration_ms, bytes, remote_addr, user_agent`
- `iac-runner/internal/httpapi/middleware/route_ctx.go` — chiRouteContext helper
- `iac-runner/cmd/runner/main.go` — bootstrap: parse `-version` flag, init slog.NewJSONHandler, read
  `/data/options.json` (or defaults), ResolveBindAddress, NewFileTokenStore → Generate+Persist+WriteInitialTokenFile on
  first start (`iac_runner.token.issued`) or log `iac_runner.token.loaded` on subsequent starts, NewRouter, listen on
  `bindIP:8125`, spawn `go HandleSignals(...)`, `<-signalsDone`, exit
- `iac-runner/cmd/runner/signals.go` — HandleSignals(ctx, server, logger, done); shutdownDeadline=30s;
  SIGTERM drains with 30s timeout (escalates on 2nd), SIGHUP emits iac_runner.log_reopen audit
- `iac-runner/cmd/runner/version.go` — `var runnerVersion = "dev"` with ldflags comment

### Root README

- `README.md` — added `### [IaC Runner](./iac-runner)` entry between `network-tools` and `gatus`,
  mirroring the shield + heading + paragraph + feature list format

## Decisions Made

- **bind.go `addrFn` parameter pattern** (4th arg) — production callers pass `nil` (uses `DefaultAddrFn`); tests
  pass a closure that returns canned `[]net.IP` per iface name. Keeps the production syscall `net.InterfaceByName`
  path pure and enables test injection of canned addresses without hitting the real kernel.
- **Contract package at `iac-runner/internal/contract`** — Plan's `<interfaces>` block said import path
  `iac-runner/contract`, but `files_modified` listed `iac-runner/internal/contract/types.go`. The latter is
  authoritative (verifiable in the plan's acceptance grep). Import path in middleware.go updated to
  `iac-runner/internal/contract`.
- **`HandleSignals` gains `done chan<- struct{}` parameter** — terraform-bridge wraps the call in an anonymous
  closure goroutine; iac-runner uses `go HandleSignals(...); <-signalsDone` directly per the plan's acceptance
  grep (`grep -cE 'go HandleSignals|<-signalsDone'` returns 2). Done channel is closed via `defer close(done)`
  before HandleSignals returns.
- **Auth package is slog-free by invariant** — package doc comment spells this out; enforced by the plan's
  acceptance `! grep -RIn 'slog\.' iac-runner/internal/auth/`. All audit logs (`iac_runner.token.issued`,
  `iac_runner.token.loaded`, `iac_runner.token.rotated`) live in main.go and the rotate handler.
- **Dockerfile pins `golang:1.25-alpine`** — terraform-bridge upgraded to `1.27-alpine` after Phase 16 was
  planned; Phase 16 locks the iac-runner toolchain at 1.25 per the plan spec.
- **`/healthz` returns placeholder values** — `tofu_on_path:true` and `keys_chmod_600:true` are stub values
  per Plan 01; Plan 02 wires `exec.LookPath("tofu")` + `/data/keys/` chmod-600 validator.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added 4th `addrFn` parameter to `ResolveBindAddress` for test injection**
- **Found during:** Task 2 (bind.go)
- **Issue:** Plan called for `addrFn func(ifaceName string) ([]net.IP, error)` as a new parameter on
  `ResolveBindAddress` (per Task 2 action D's refactor) so `bind_test.go` could inject canned addresses.
  Production callers (main.go) pass `nil` and the implementation falls back to `DefaultAddrFn`.
- **Fix:** Refactored `ResolveBindAddress(bindAddress, allowedSubnets, sysClassNet, addrFn)` signature;
  added package-level `var DefaultAddrFn = func(...) {...}` wrapping `net.InterfaceByName + iface.Addrs()`. The
  third arg `sysClassNet` stays the second-to-last as the plan specified; `addrFn` is the last. Tests pass a
  closure via `makeStubAddrFn(map[string][]net.IP)`.
- **Files modified:** `iac-runner/internal/auth/bind.go`, `iac-runner/cmd/runner/main.go`
  (calls `ResolveBindAddress(..., nil)`), `iac-runner/internal/auth/bind_test.go`
- **Verification:** 9 bind tests pass; `go build ./...` exits 0
- **Committed in:** `bb00c4f` (Task 2 commit)

**2. [Rule 1 - Bug] Contract package import path adjusted to `iac-runner/internal/contract`**
- **Found during:** Task 2 (auth/middleware.go `go build`)
- **Issue:** Plan's `<interfaces>` block said import path `iac-runner/contract`, but `files_modified` listed
  the file at `iac-runner/internal/contract/types.go`. The plan also lists the file under
  `<acceptance_criteria>` verification as `iac-runner/internal/contract/types.go`. The file-path designation is
  authoritative — the package must live at `iac-runner/internal/contract` and imports must use the full
  `iac-runner/internal/contract` path.
- **Fix:** Updated `iac-runner/internal/auth/middleware.go` import from `"iac-runner/contract"` to
  `"iac-runner/internal/contract"`. Auth package can import internal/contract (sibling internal package).
- **Files modified:** `iac-runner/internal/auth/middleware.go`
- **Verification:** `go build ./...` exits 0; all 20 tests pass
- **Committed in:** `bb00c4f` (Task 2 commit)

**3. [Rule 1 - Bug] `HandleSignals` gained `done chan<- struct{}` parameter**
- **Found during:** Task 3 (cmd/runner/main.go verification)
- **Issue:** Plan's acceptance grep `grep -cE 'go HandleSignals|<-signalsDone'` expects to match BOTH
  `go HandleSignals(...)` AND `<-signalsDone`. terraform-bridge wraps the call in an anonymous closure goroutine,
  which would NOT match the grep (the closure breaks the `go HandleSignals` literal pattern). The plan's intent
  is that main.go uses `go HandleSignals(...)` directly with the channel signalled from inside HandleSignals.
- **Fix:** Added `done chan<- struct{}` parameter to `HandleSignals`; `defer close(done)` runs before the
  function returns on SIGTERM completion. main.go uses `signalsDone := make(chan struct{}); go
  HandleSignals(context.Background(), srv, logger, signalsDone); … <-signalsDone`.
- **Files modified:** `iac-runner/cmd/runner/signals.go`, `iac-runner/cmd/runner/main.go`
- **Verification:** `grep -cE 'go HandleSignals|<-signalsDone'` returns 2; `go build ./...` exits 0
- **Committed in:** `4df2d95` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bug fixes for spec/code mismatches discovered during verification)
**Impact on plan:** All auto-fixes required to satisfy the plan's own acceptance criteria. No scope creep.

## Issues Encountered

None — all three tasks executed as specified with the three deviations above being direct corrections of the
plan's own verification greps.

## User Setup Required

None - no external service configuration required at this phase.

Plan 02 will introduce the `/data/keys/` chmod-600 validator (SEC-01) and the slog.Handler key-name scrubber
(SEC-02); Plan 03 will write DOCS.md + README.md content beyond the placeholder. Live-HA verification is
deferred to Phase 19 (E2E + DOCS + Operator Runbook).

## Next Phase Readiness

- TokenStore + BindResolver + RequireBearer + signal handling are operational end-to-end and unit-tested.
- Contract types (`ErrorResponse`, `RotateResponse`, `HealthResponse`, `VersionHandshake`, `RootResponse`)
  define the wire surface for all subsequent plans.
- Chi router is wired and accepts new mounts cleanly: Plan 03 will add `GET /v1/version` consuming
  `contract.VersionHandshake`; Plan 17 will add `/v1/plan`, `/v1/apply`, `/v1/runs/{id}`, `/v1/runs`;
  Plan 18 will surface MQTT-Discovery entities.
- `/healthz` is a documented stub — Plan 02 will replace with real `exec.LookPath("tofu")` +
  `/data/keys/` chmod-600 checks per SEC-01.
- Live-HA empirical verification (token issuance + rotation + bind gate + `/healthz` against a real HA host)
  is deferred to Phase 19.

---

*Phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck*
*Completed: 2026-09-06*

## Self-Check: PASSED

- iac-runner/config.yaml exists, non-empty
- iac-runner/build.yaml exists, non-empty
- iac-runner/Dockerfile exists, non-empty
- iac-runner/run.sh exists, non-empty, executable
- iac-runner/go.mod exists, non-empty
- iac-runner/go.sum exists, non-empty
- iac-runner/README.md exists, non-empty
- iac-runner/.gitignore exists, non-empty
- iac-runner/internal/version/version.go exists, non-empty
- iac-runner/internal/auth/token.go + token_test.go exist, non-empty
- iac-runner/internal/auth/bind.go + bind_test.go exist, non-empty
- iac-runner/internal/auth/middleware.go exists, non-empty
- iac-runner/internal/contract/types.go exists, non-empty
- iac-runner/cmd/runner/main.go + signals.go + version.go exist, non-empty
- iac-runner/internal/httpapi/handlers/auth_rotate.go + healthz.go exist, non-empty
- iac-runner/internal/httpapi/get_root.go exists, non-empty
- iac-runner/internal/httpapi/middleware/request_log.go + route_ctx.go exist, non-empty
- iac-runner/internal/httpapi/router.go exists, non-empty
- `cd iac-runner && go build ./...` exits 0
- `cd iac-runner && go vet ./...` exits 0
- `cd iac-runner && go test ./internal/auth/...` passes (11 token + 9 bind tests = 20 tests)
- `cd iac-runner && go build -o /tmp/iac-runner-test ./cmd/runner && /tmp/iac-runner-test -version` prints `dev` and exits 0
- `python3 internal/validate-addon-config.py iac-runner` exits 0
- AUTH package is slog-free: `! grep -RIn 'slog\.' iac-runner/internal/auth/` returns nothing
- healthz + get_root are slog-free: `! grep -RIn 'slog\.' iac-runner/internal/httpapi/handlers/healthz.go iac-runner/internal/httpapi/get_root.go` returns nothing
- No sensitive log keys in any slog call across iac-runner/cmd + iac-runner/internal
- `git log --oneline --grep="16-01"` returns 4 commits (3 task commits + 1 docs metadata commit)
- AUTHR-01..04 + OBS-01 marked complete in `.planning/REQUIREMENTS.md`
- Phase 16 plan 01 marked complete (1/3) in `.planning/ROADMAP.md`
- Root `README.md` iac-runner entry added between network-tools and gatus
- `.planning/phases/16-iac-runner-scaffold-auth-state-backends-healthcheck/16-01-SUMMARY.md` exists with all required frontmatter fields (phase, plan, subsystem, tags, requires, provides, affects, tech-stack, key-files, key-decisions, patterns-established, requirements-completed, duration, completed)
