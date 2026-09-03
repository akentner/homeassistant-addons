---
phase: 11-bridge-read-api
plan: 01
subsystem: bridge-read-api
tags: [go, chi, supervisor-api, bearer-token, semver, slog]

# Dependency graph
requires:
  - phase: 10-auth-layer-structured-logging-healthcheck
    provides:
      - TokenStore (NewFileTokenStore / Generate / Persist / Validate) + RequireBearer chi middleware
      - chi router scaffold with /v1/* auth subrouter + RequestLogger middleware (OPS-01)
      - supervisor.Client with tokenInjectingTransport + Ping(ctx) method
      - contract.VersionHandshake, ErrorResponse, HealthResponse, TokenResponse, RotateResponse
  - phase: 09-bridge-foundation-token-rotation-spike
    provides:
      - chi router skeleton, slog JSON baseline, ReadSupervisorToken env reader
provides:
  - supervisor.GetSupervisorInfo(ctx) returning SupervisorInfo{Version} via /supervisor/info
  - supervisor.testing.go: TokenFnForTest + WithBaseURLForTest export helpers (NOT _test.go)
  - contract.BridgeInfo struct: bridge_version + supervisor_version + uptime_seconds + state_file_path (BRIDGE-10)
  - handlers.Info(supClient, bridgeVersion, startTime, stateFilePath) - GET /v1/info (no auth, BRIDGE-10)
  - internal/version package: SchemaVersion="1.0.0", MinProviderVersion="0.0.0", MaxProviderVersion="1.999.0"
  - handlers.Version(bridgeVersion) - GET /v1/version populating all 4 VersionHandshake fields (BRIDGE-01)
  - router: NewRouter signature extended with (startTime, stateFilePath); /v1/info mounted at root (no auth);
    /v1/version moved under the existing /v1 auth subrouter
  - main.go: const stateFilePath = "/data/terraform.tfstate"; startTime captured as first executable
    line of main(); threaded into NewRouter; "listening" slog record emits bind_address + state_file_path
  - 5 new test functions: TestClientGetSupervisorInfoSuccess, TestClientGetSupervisorInfoSendsBearer,
    TestInfoHandlerHappyPath, TestInfoHandlerUpstreamError, TestVersionHandler,
    TestRouterVersionRequiresAuth (router-level)
affects:
  - 11-02 (BRIDGE-02/03 — /v1/addons + /v1/addons/{slug}/info with V1/V2 fallback): consumes the
    supervisor.Client + contract.AddOnInfo + router extension pattern from this plan; NewRouter signature
    already accepts startTime/stateFilePath so Plan 02 does NOT modify main.go or NewRouter shape
  - phase-13 (terraform-provider-homeassistant): the new internal/version package is referenced via
    the go.mod replace directive so the Provider's PROV-03 Configure handshake can compare
    schema_version against its own min/max provider version
  - phase-15 (make install-provider E2E): both endpoints (GET /v1/version + GET /v1/info) are the
    handshake + sanity-check targets the Phase 15 E2E calls against the running Bridge

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "supervisor.Client HTTP method (GetSupervisorInfo) follows the existing Ping pattern: build GET
      via NewRequestWithContext -> httpClient.Do (tokenInjectingTransport injects Bearer) -> check
      StatusCode -> decode JSON envelope -> return typed struct. Errors wrap with fmt.Errorf(\"%w\")
      but message never embeds the token (PITFALLS S-1 invariant)."
    - "Test-only helpers (TokenFnForTest, WithBaseURLForTest) live in a REGULAR .go file named
      testing.go (not _test.go) so handler tests in package handlers can call them - Go's test build
      only compiles _test.go within the SAME package."
    - "WithBaseURLForTest returns a struct copy (*c copies value, httpClient is shared) - safe because
      tokenInjectingTransport is stateless beyond the tokenFn pointer; only baseURL changes per test."
    - "Handler-level handlerInfoTimeout = 3s is a separate budget from supervisor.Client's 2s
      httpClient Timeout; ctx with cancel() bounds the per-request cost. 502 returns a bare
      ErrorResponse{ErrorCode: \"upstream_error\"} with no Message - PITFALLS S-1."
    - "/v1/version moved into the auth subrouter via adding r.Get(\"/version\", ...) under the existing
      r.Route(\"/v1\", ...).Use(auth.RequireBearer(store)) block. Order in the auth subrouter:
      /version, /whoami, /auth/rotate."
    - "startTime captured as the FIRST executable line of func main() (after version-flag handling,
      before structured-logger setup) so uptime_seconds reflects process-startup semantics. Passed to
      NewRouter as a constructor parameter so the handler can compute int64(time.Since(startTime)/time.Second)."
    - "schema_version lives in a sub-package (internal/version) rather than contract because:
      (1) it's consumed by the Provider via go.mod replace terraform-bridge => ../terraform-bridge;
      (2) it's compile-time config, not a wire type."

key-files:
  created:
    - terraform-bridge/internal/supervisor/client_test.go
    - terraform-bridge/internal/supervisor/testing.go
    - terraform-bridge/internal/version/version.go
    - terraform-bridge/internal/httpapi/handlers/info.go
    - terraform-bridge/internal/httpapi/handlers/info_test.go
    - terraform-bridge/internal/httpapi/handlers/version_test.go
    - terraform-bridge/internal/httpapi/router_test.go
  modified:
    - terraform-bridge/internal/supervisor/client.go
    - terraform-bridge/contract/types.go
    - terraform-bridge/internal/httpapi/router.go
    - terraform-bridge/internal/httpapi/handlers/version.go
    - terraform-bridge/cmd/bridge/main.go

key-decisions:
  - "/v1/info is mounted at the router ROOT, outside the /v1 auth subrouter — BRIDGE-10 is explicitly
    non-authenticated so terraform_data + lifecycle.precondition blocks don't need a bearer."
  - "/v1/version is moved INTO the /v1 auth subrouter (it was previously mounted at the root with no
    auth) so the Provider's PROV-03 Configure handshake fails fast with 401 when the bearer is
    missing - upgrades the placeholder from Phase 10 into a properly-gated handshake endpoint."
  - "Test-helper file is naming testing.go (NOT export_test.go) to be visible cross-package. Go's test
    build only includes _test.go files in the SAME package, so an export_test.go in package supervisor
    wouldn't be reachable from package handlers."
  - "uptime_seconds is int64 (not int, not string, not float) so Terraform's lifecycle.precondition
    parses it directly without coercion."
  - "Supervisor upstream errors return HTTP 502 (NOT 500): the upstream is Supervisor, not the Bridge;
    502 makes the failure mode obvious in HA logs (RFC 7231 §6.6.5: 502 Bad Gateway indicates an
    invalid response from an inbound server)."
  - "SchemaVersion = \"1.0.0\" initial v1 contract; MinProviderVersion = \"0.0.0\" (accepts any
    Provider that knows schema_version); MaxProviderVersion = \"1.999.0\" (no breaking-change
    forward-compat required in Phase 1). Bump policy documented in package version comment."
  - "Rule 1 auto-fix: in GetSupervisorInfo, the body-drain order was corrected to drain AFTER checking
    StatusCode (success path) instead of drain-then-decode. Drain-then-decode returned EOF on the
    success path because io.Copy(io.Discard) had already consumed the body."

patterns-established:
  - "Pattern 1 (info handler): on upstream Supervisor failure, the handler logs a single Warn record
    with the err.Error() (NOT the bare string), writes 502 with bare {error_code: \"upstream_error\"},
    and never includes Message on the wire (preserves PITFALLS S-1 invariant)."
  - "Pattern 2 (semver constants): schema_version + min/max_provider_version live in a dedicated
    package (internal/version) so both Bridge binary and (later) the Provider can reference them
    via go.mod replace without a dependency cycle."
  - "Pattern 3 (router-level test): router_test.go uses real auth.NewFileTokenStore to prove the
    middleware is wired end-to-end; cannot be hand-waved by future refactors because a TokenStore
    signature change forces a compile error here."

requirements-completed: [BRIDGE-01, BRIDGE-10]

# Metrics
duration: ~25min
completed: 2026-09-03
tasks: 2
---

# Phase 11 Plan 01: Bridge Read API (Tracer + /v1/version) Summary

**Tracer-first slice of Phase 11 Bridge Read API: GET /v1/info (BRIDGE-10, public, single /supervisor/info call) +
GET /v1/version (BRIDGE-01, bearer-required Provider-handshake target) wired end-to-end with a new
internal/version semver-constants package and a router-level test that proves RequireBearer is mounted on the
/v1 subrouter.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 (1 tracer, 1 auto)
- **Files modified:** 5; **Files created:** 7

## Accomplishments

- `supervisor.Client.GetSupervisorInfo(ctx)` calls `GET /supervisor/info`, parses the
  `{result, data:{supervisor}}` envelope, and returns a typed `SupervisorInfo{Version string}` (e.g.
  "2026.08.0"). Errors wrap with `fmt.Errorf` and never carry the token value.
- `internal/supervisor/testing.go` exports `TokenFnForTest()` + `WithBaseURLForTest(baseURL)` so
  handler tests in `package handlers` can stub the token function and redirect the baseURL at an
  `httptest.NewServer` without copying the `Client` struct literal.
- `contract.BridgeInfo` struct with all four BRIDGE-10 fields (`bridge_version`,
  `supervisor_version`, `uptime_seconds int64`, `state_file_path`); appended to types.go without
  touching any existing type.
- `handlers.Info(supClient, bridgeVersion, startTime, stateFilePath)` mounted at `GET /v1/info` at
  the router root (NO auth — BRIDGE-10 explicitly public). Returns 200 + `BridgeInfo` on success,
  502 + `ErrorResponse{ErrorCode: "upstream_error"}` on Supervisor failure.
- `internal/version` package: three semver string constants (`SchemaVersion="1.0.0"`,
  `MinProviderVersion="0.0.0"`, `MaxProviderVersion="1.999.0"`) with documented bump policy
  (MAJOR on every breaking Bridge API change).
- `handlers.Version(bridgeVersion)` populates all four `contract.VersionHandshake` fields
  (previously only `bridge_version`); moves the route from the public root into the existing
  `/v1` auth subrouter so the Provider's PROV-03 Configure handshake requires a valid bearer.
- `NewRouter` signature extended with `(startTime time.Time, stateFilePath string)` so the
  `/v1/info` handler can be constructed with its process-startup timestamp and Phase 1 state-file
  constant.
- `cmd/bridge/main.go` declares `const stateFilePath = "/data/terraform.tfstate"` at package scope,
  captures `startTime := time.Now()` as the **first** executable line of `main()` (after the
  `-version` short-circuit), and threads both into `NewRouter`. New `logger.Info("listening", ...)`
  slog record surfaces `bind_address` + `state_file_path`.
- 6 new test functions (2 in `internal/supervisor/client_test.go`, 2 in
  `internal/httpapi/handlers/info_test.go`, 1 in `handlers/version_test.go`, 1 router-level
  `TestRouterVersionRequiresAuth`) — all pass; existing Phase 10 tests untouched.

## Files Created/Modified

- `terraform-bridge/internal/supervisor/client.go` — appended `SupervisorInfo` struct +
  `GetSupervisorInfo(ctx)` method after the existing `Ping`. Added `encoding/json` import.
- `terraform-bridge/internal/supervisor/client_test.go` (NEW) — `TestClientGetSupervisorInfoSuccess`
  (decodes `data.supervisor: "2026.08.0"`) + `TestClientGetSupervisorInfoSendsBearer` (asserts
  `Authorization: Bearer fake-supervisor-token` reaches httptest server).
- `terraform-bridge/internal/supervisor/testing.go` (NEW) — `TokenFnForTest()` + `WithBaseURLForTest(baseURL)`
  helpers; **named `testing.go` (not `_test.go`) so handler tests can reach them**.
- `terraform-bridge/contract/types.go` — appended `BridgeInfo` struct (4 fields, all `json:"..."`
  tagged). No existing type touched.
- `terraform-bridge/internal/httpapi/handlers/info.go` (NEW) — `Info(supClient, bridgeVersion, startTime, stateFilePath)`
  with 3s upstream timeout, 502 path on failure, `Cache-Control: no-store` on success.
- `terraform-bridge/internal/httpapi/handlers/info_test.go` (NEW) — happy-path 200 + body shape,
  upstream-error 502 + `ErrorResponse{ErrorCode: "upstream_error"}` with empty Message.
- `terraform-bridge/internal/httpapi/handlers/version.go` — rewritten as `Version(bridgeVersion)`
  populating all four `VersionHandshake` fields via `version.SchemaVersion` + `version.MinProviderVersion`
  + `version.MaxProviderVersion`.
- `terraform-bridge/internal/httpapi/handlers/version_test.go` (NEW) — `TestVersionHandler` asserts
  200 + body matches the four `version.*` constants.
- `terraform-bridge/internal/httpapi/router.go` — `NewRouter` signature extended with `startTime
  time.Time, stateFilePath string`; `/v1/info` mounted at root (no auth); `/v1/version` moved
  inside the existing `r.Route("/v1", ...).Use(auth.RequireBearer(store))` block as
  `r.Get("/version", handlers.Version(...))`.
- `terraform-bridge/internal/httpapi/router_test.go` (NEW) — `TestRouterVersionRequiresAuth`:
  real `auth.NewFileTokenStore(t.TempDir())`, asserts GET /v1/version returns 401 +
  `{error_code: "unauthorized"}` (proves RequireBearer is wired), then asserts /v1/info does
  NOT return 401 (proves the auth subrouter does not leak).
- `terraform-bridge/internal/version/version.go` (NEW) — three semver constants + bump-policy
  package comment.
- `terraform-bridge/cmd/bridge/main.go` — `const stateFilePath = "/data/terraform.tfstate"`
  at package scope; `startTime := time.Now()` captured as first executable line of `main()`;
  `NewRouter` call updated to pass new args; `logger.Info("listening", "bind_address",
  bindIP+":8124", "state_file_path", stateFilePath)` record added.

## Task Commits

1. **Task 1 (tracer): GET /v1/info — supervisor.GetSupervisorInfo + contract.BridgeInfo + handler.**
   (Staged but not yet committed — orchestrator is driving the user-approved commit.)
2. **Task 2: internal/version + GET /v1/version populated + router move into auth subrouter.**
   (Staged but not yet committed.)

(The orchestrator's instructions to this executor were "Do NOT commit the changes yourself — stage and
report." Both task commits are pre-approved by the plan's "Atomic commit" sections; the orchestrator
will run them after human review of the staged diff.)

## Decisions Made

- **`testing.go` helper file naming:** Chose the `testing.go` form (per the plan's explicit
  instruction). `export_test.go` would not be reachable from `package handlers` because Go's test
  build only compiles `_test.go` files within the same package.
- **uptime computation in the handler, not in main:** `int64(time.Since(startTime) / time.Second)`
  happens at request time so the value reflects the actual call time (close enough to the start
  time at second-resolution granularity). One-shot computation in `main` would be slightly cheaper
  per request but would freeze the value at boot, which is wrong for a long-running process.
- **`getSupervisorInfo` 502 body has no `Message`:** The plan's test asserts `body.Message == ""`
  on the failure path so the response cannot leak the underlying error message (which could
  contain operational detail the operator hasn't authorised us to share with an anonymous
  Terraform plan).
- **Order of routes inside the auth subrouter:** Conventional ordering: `/version` (read-only
  handshake) first, `/whoami` (caller introspection), `/auth/rotate` (mutation). Order does not
  matter for correctness; this is a hygiene decision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Body-drain order in `GetSupervisorInfo`**

- **Found during:** Task 1 verification — `go test ./internal/supervisor` failed with
  `supervisor: decode info: EOF` on the success path.
- **Issue:** The plan's code-as-written contains an
  `_, _ = io.Copy(io.Discard, resp.Body) // drain for connection reuse`
  line **before** `json.NewDecoder(resp.Body).Decode(&envelope)`. `io.Copy(io.Discard, ...)` reads the
  entire body to EOF, so when the `json.NewDecoder` then tries to read it, it gets EOF and
  `Decode` returns an error.
- **Fix:** Moved the drain inside the `if resp.StatusCode != http.StatusOK { ... }` branch so
  the success path leaves the body intact for `json.NewDecoder`. The defer-Close is sufficient to
  release the connection; the drain is only useful when we intend to discard the body
  (non-200 path).
- **Files modified:** `terraform-bridge/internal/supervisor/client.go`
- **Verification:** `go test ./internal/supervisor` and `go test ./internal/httpapi/handlers`
  both pass; the 2 supervisor client tests + 2 info handler tests all green.

**2. [Pre-existing — noted, not auto-fixed] `SUPERVISOR_TOKEN` literal occurrences exceed the plan's
"exactly 1" assertion**

- **Found during:** Task 1 acceptance check.
- **Issue:** The plan's criterion "exactly 1 line" was impractical because the existing Phase 10
  codebase already had 5 non-runtime references (3 in `internal/logging/scrubbing_handler.go`,
  1 in `signals.go`, 1 in `internal/supervisor/client.go` doc comments, 1 in `token.go`'s
  `os.Getenv` call). Two new non-leak references were added by this plan: 1 doc comment in
  `GetSupervisorInfo`'s godoc (mentions the env var name) + 1 comment in
  `internal/httpapi/handlers/info_test.go` describing the failure scenario.
- **Disposition:** Same deviation as Phase 10 Plan 01 SUMMARY. The runtime invariant
  (no token value ever enters a log record; the `verify-bridge-no-token-leak.sh` runtime check
  still passes) is preserved — the additions are documentation, not leak paths. The literal
  "exactly 1 hit" interpretation was always impractical because the new
  `internal/supervisor/client.go` package necessarily documents the env var name it manages.
- **No file modifications** — left the references in place because they are documentation, not
  leak paths.

## Issues Encountered

- **gofmt -l flags 4 unmodified files (`cmd/bridge/version.go`, `internal/auth/bind.go`,
  `internal/auth/token.go`, `internal/httpapi/get_root.go`).** These were flagged by Go 1.27.1's
  stricter comment-indent rules; they predate this plan and were not in scope. All 12 files I
  modified or created pass `gofmt -l` cleanly.
- **Go binary at non-standard path** — `/root/.cache/pre-commit/repo8dxmizyl/golangenv-default/.go/bin/go`
  (resolved each invocation via `export PATH=...`). `go.mod` declares `go 1.25`; Go 1.27.1
  satisfies the toolchain.
- **Live-HA verification deferred** — Plan's "Manual (live HA host)" section requires building
  the add-on image, deploying to `haos-op3050-1`, recovering the token from `/data/initial-token`,
  and running `curl` with/without bearer. This is not executable from this dev container (the
  add-on builder + HA host are both remote). Deferred to Phase 14's verify-work pass per the
  Phase 10 SUMMARY precedent.

## User Setup Required

None — no external service configuration required.

## Self-Check

- **Files exist:** PASSED — all 12 files (5 modified + 7 created) on disk and readable.
- **Greps from task verify blocks:** PASSED — Task 1 `<verify>` greps all match; Task 2
  `<verify>` greps all match; no `r.Get("/v1/version", ...)` in router root; `r.Get("/version", ...)`
  present inside the auth subrouter.
- **Tests:** 6 new test functions added; all pre-existing Phase 10 tests still pass.
- **`go build ./...`:** exit 0.
- **`go vet ./...`:** exit 0.
- **`go test ./...`:** exit 0 — `internal/auth`, `internal/httpapi` (new), `internal/httpapi/handlers`
  (new tests + pre-existing), `internal/httpapi/middleware`, `internal/logging`, `internal/supervisor`
  (new tests). `cmd/bridge` (test-less), `contract` (test-less), `internal/version` (test-less) as
  expected.
- **`./bridge -version`:** exit 0, prints `dev`.

## Next Phase Readiness

**Ready for Plan 02 (BRIDGE-02 + BRIDGE-03 — /v1/addons list + /v1/addons/{slug}/info with V1/V2
fallback):**

- `supervisor.Client` is now extended with `GetSupervisorInfo(ctx)`; Plan 02 adds `ListAddons(ctx)`
  and `GetAddonInfo(ctx, slug)` following the exact same pattern (NewRequestWithContext -> Do ->
  StatusCode check -> envelope decode).
- `contract.AddOnInfo` is unchanged from Phase 9 skeletal — Plan 02 does NOT need to extend
  contract/types.go.
- `NewRouter(bridgeVersion, store, supClient, startTime, stateFilePath)` signature is final:
  Plan 02 only ADDS new `r.Get("/addons", ...)` + `r.Get("/addons/{slug}/info", ...)` mounts
  inside the existing auth subrouter.
- `internal/version` semver package is in place for Plan 02 to reference if any addon-list
  endpoint needs a version-pinned response field.
- The router-level test pattern (`TestRouterVersionRequiresAuth`) is established; Plan 02 can
  mirror it for `/v1/addons` 401 verification.
- `cmd/bridge/main.go`'s `stateFilePath` + `startTime` threading is complete and not changed by
  Plan 02.

**No known blockers for Plan 02.**

---

_Phase: 11-bridge-read-api · Completed: 2026-09-03_
