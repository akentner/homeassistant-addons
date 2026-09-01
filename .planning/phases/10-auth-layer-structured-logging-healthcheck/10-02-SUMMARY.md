---
phase: 10-auth-layer-structured-logging-healthcheck
plan: 02
subsystem: auth
tags: [go, chi, log-slog, scrubbing-handler, request-logger, supervisor-ping, ops-01, ops-03, auth-05]

# Dependency graph
requires:
  - phase: 10-auth-layer-structured-logging-healthcheck (plan 01)
    provides:
      TokenStore, RequireBearer chi middleware, SupervisorClient.Ping(ctx), HealthResponse contract, chi router scaffold
      with RequestID + Recoverer
provides:
  - "slog.Handler wrapper that scrubs sensitive key VALUES with <redacted> before delegating to the inner handler
    (AUTH-05 layer 1)"
  - "chi RequestLogger middleware that emits ONE structured slog record per HTTP request carrying OPS-01 fields
    (request_id, route, method, status, duration_ms) AND strips Authorization from r.Header before logging (AUTH-05
    layer 2)"
  - "GET /healthz handler probing Supervisor /supervisor/ping with a 2s context deadline; 200 + HealthResponse JSON on
    success, 503 + Content-Length: 0 on failure"
  - "router chain RequestID → Recoverer → RequestLogger globally; /healthz mounted at root (no auth); /v1/* under
    RequireBearer"
  - "main.go wraps slog handler with logging.NewScrubbingHandler and threads supClient into NewRouter"
  - "Strengthened verify-bridge-no-token-leak.sh with CF-02 exactly-once + actor_token_fp positive control + OPS-01
    record assertions"
affects:
  - "phase-10 plan 03 (rotation + grace) — every token-touching log record passes through the scrubbing handler"
  - "phase-11 read API — every /v1/* request now produces an OPS-01 record"
  - "phase-12 write API — /healthz is the HA Supervisor liveness probe target"
  - "phase-14 Real-HA E2E — verify script runs as a pre-commit hook; first-end-to-end on live HA relies on /healthz
    responding"

# Tech tracking
tech-stack:
  added:
    - "stdlib log/slog scrubbingHandler (no new external deps)"
  patterns:
    - "two-layer AUTH-05: slog.Handler wrapper scrubs every record; chi middleware strips Authorization from r.Header
      BEFORE the request-log snapshot is taken"
    - "chi route context extraction via chi.RouteCtxKey (split into a separate helper file to avoid name conflict with
      chi/v5/middleware)"
    - "key-name based scrubbing (strings.EqualFold) — log messages that mention 'Bearer' incidentally are preserved
      (CONTEXT §agent's Discretion)"
    - "OPS-01: statusRecorder wraps http.ResponseWriter to capture status code + bytes written for the post-request log
      record"
    - "OPS-03: /healthz 503 body ALWAYS empty (Content-Length: 0); one Warn slog record pre-write for forensics, no
      internal state in the failure response"

key-files:
  created:
    - terraform-bridge/internal/logging/scrubbing_handler.go
    - terraform-bridge/internal/logging/scrubbing_handler_test.go
    - terraform-bridge/internal/httpapi/middleware/request_log.go
    - terraform-bridge/internal/httpapi/middleware/request_log_test.go
    - terraform-bridge/internal/httpapi/middleware/route_ctx.go
    - terraform-bridge/internal/httpapi/handlers/healthz.go
    - terraform-bridge/internal/httpapi/handlers/healthz_test.go
  modified:
    - terraform-bridge/internal/httpapi/router.go
    - terraform-bridge/cmd/bridge/main.go
    - internal/verify-bridge-no-token-leak.sh
    - .pre-commit-config.yaml

key-decisions:
  - "Split chi.RouteCtxKey extraction into a separate route_ctx.go file so request_log.go's middleware package depends
    only on chi/v5/middleware, not chi/v5 directly (avoids name-collision aliasing gymnastics)"
  - "Used chi.RouteCtxKey (not RouteContextKey) — chi/v5.3.2 names the context key RouteCtxKey"
  - "Defined healthzTimeout as a `const healthzTimeout = 2 * time.Second` in handlers/healthz.go (plan's verification
    regex looked for `context.WithTimeout.*2\\*time.Second` literal — const extraction preserves semantics but moves the
    literal out of the call site)"
  - "Adapted the verify-script positive-control assertions to test against the bridge's auto-generated plaintext instead
    of the SUPERVISOR_TOKEN — the plan's literal check assumed a BRIDGE_TOKEN env-override that does not exist; we chose
    not to add one (out-of-scope architectural change) and instead parse the bridge.token.issued JSON record to extract
    plaintext + actor_token_fp. Same invariants tested, no architectural scope creep"
  - "RequestLogger uses slog.Default() so the scrubbingHandler wrapper installed in main.go applies automatically to
    every record (no separate logger to wire through chi context)"

patterns-established:
  - 'Pattern: chi middleware logger reads r.Header.Clone() + Del("Authorization") before reading any header value — even
    if the slog scrubber later fails, no record can ever contain the bearer plaintext'
  - "Pattern: statusRecorder pattern for capturing status + bytes while preserving http.Flusher/Hijacker interfaces (we
    only capture what we need; if a handler later needs Flusher, add explicit method forwarders here)"
  - "Pattern: verification scripts parse captured JSON log records with grep -oE for individual fields; this works
    without jq and stays readable"

requirements-completed: [AUTH-05, OPS-01, OPS-03]

# Metrics
duration: ~25 min
completed: 2026-08-31
---

# Phase 10 Plan 02: Auth Layer Operational Primitives Summary

**Two-layer log masking (slog scrubbing handler + chi Authorization strip), OPS-01 structured request log, and OPS-03
/healthz probing Supervisor via Plan 01 SupervisorClient.Ping with a 2s deadline — proves AUTH-05 by construction**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-31T18:46:00Z (approx)
- **Completed:** 2026-08-31T18:52:53Z
- **Tasks:** 3
- **Files modified:** 11 (7 new + 4 existing)

## Accomplishments

- Two-layer AUTH-05 invariant proven by unit test + 3 in-memory test cases. Layer 1 (slog scrubbing handler) catches
  every `slog.*` call site; layer 2 (chi middleware stripping `Authorization` from `r.Header` before the request-log
  snapshot) catches the request itself even if layer 1 fails. Layer 2 uses `r.Header.Clone().Del("Authorization")` so
  the original request header is left untouched for downstream handlers.
- RequestLogger emits one structured slog record per HTTP request with all OPS-01 fields: `ts` (slog default), `level`
  (slog default), `msg="http.request"`, `request_id` (read from chi's `middleware.GetReqID(r.Context())` honoring
  inbound `X-Request-Id`), `route` (chi route pattern or raw path on 404), `method`, `status` (via wrapped
  `statusRecorder`), `duration_ms`. Bytes, remote_addr, and user_agent also included for forensics.
- `/healthz` returns 200 + HealthResponse JSON when `SupervisorClient.Ping(ctx)` (Plan 01) succeeds within 2s; returns
  503 with empty body (`Content-Length: 0`, per D-08) and a single `slog.Warn("supervisor.ping_failed", ...)` record on
  failure. Wraps `r.Context()` in `context.WithTimeout(..., 2*time.Second)` so the overall budget is enforced even if
  Supervisor stalls.
- `main.go` swaps `slog.NewJSONHandler(os.Stdout, nil)` for
  `slog.New(logging.NewScrubbingHandler(slog.NewJSONHandler(os.Stdout, nil)))` — every record, including the existing
  `bridge.token.issued` plaintext surfacing on first start, flows through the scrubbing wrapper.
- `verify-bridge-no-token-leak.sh` now has 7 total assertions (was 4): the four Phase 9 substring checks plus three new
  positive controls — actor_token_fp matches SHA-256[8] of the bridge's auto-generated plaintext (proves the Fingerprint
  helper behaves correctly), the plaintext appears EXACTLY ONCE in stdout (CF-02 exactly-once invariant), and a
  `http.request` OPS-01 record is emitted for `GET /`.
- Pre-commit hook entry description updated; hook fires on `terraform-bridge/**` changes as before.

## Task Commits

Each task was committed atomically:

1. **Task 1: scrubbing slog.Handler wrapper + test** — `fb9fed0` (feat)
2. **Task 2: RequestLogger middleware + Healthz handler + tests** — `d80ee89` (feat)
3. **Task 3: Wire middleware + /healthz into router + main; strengthen verify script + pre-commit hook** — `8ce3035`
   (feat)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `terraform-bridge/internal/logging/scrubbing_handler.go` — slog.Handler wrapper; sensitiveKeys set with 8 entries;
  `NewScrubbingHandler(inner slog.Handler) slog.Handler`; full Handler interface (Enabled, Handle, WithAttrs, WithGroup)
- `terraform-bridge/internal/logging/scrubbing_handler_test.go` — 3 test functions covering masking, preservation, and
  value-substring non-interference
- `terraform-bridge/internal/httpapi/middleware/route_ctx.go` — chi.RouteCtxKey extraction helper (separate file to
  avoid chi import cycle in request_log.go)
- `terraform-bridge/internal/httpapi/middleware/request_log.go` — RequestLogger middleware with
  `r.Header.Clone().Del("Authorization")` per D-10 layer 2; statusRecorder wrapping http.ResponseWriter
- `terraform-bridge/internal/httpapi/middleware/request_log_test.go` — 2 test functions: OPS-01 fields present +
  Authorization value stripped
- `terraform-bridge/internal/httpapi/handlers/healthz.go` — Healthz handler with `healthzTimeout = 2 * time.Second`
  const, 200 + JSON on success, 503 + empty body + Warn log on failure
- `terraform-bridge/internal/httpapi/handlers/healthz_test.go` — 2 test functions: response shape validation + 503 empty
  body on Ping failure (empty tokenFn)
- `terraform-bridge/internal/httpapi/router.go` — RequestLogger added between Recoverer and per-route RequireBearer;
  `/healthz` mounted at root (no auth); NewRouter signature takes supClient
- `terraform-bridge/cmd/bridge/main.go` — imports `internal/logging`; wraps slog handler with `NewScrubbingHandler`;
  removes `_ = supClient` placeholder; threads supClient into NewRouter
- `internal/verify-bridge-no-token-leak.sh` — strengthened with actor_token_fp + exactly-once + OPS-01 record checks
- `.pre-commit-config.yaml` — verify-bridge-no-token-leak entry description updated to reflect Phase 10 coverage

## Decisions Made

- **chi.RouteCtxKey (not RouteContextKey):** The plan's reference to `chi.RouteContextKey` is incorrect for chi/v5.3.2 —
  the actual export is `RouteCtxKey`. Used the correct symbol.
- **healthzTimeout extracted into a named const:** The plan's verify regex looked for
  `context.WithTimeout.*2\*time.Second` literal; the const is `const healthzTimeout = 2 * time.Second` and the call site
  uses the const name. Semantics preserved, code reads better, and the constant is self-documenting.
- **No BRIDGE_TOKEN env-var override in the bridge:** The plan's verification script would have computed
  `EXPECTED_FP = SHA-256[8](FAKE_TOKEN)` and checked the bridge emits a record whose actor_token_fp == EXPECTED_FP — but
  the bridge generates its OWN random token (no env override exists in Plan 01). Adding a BRIDGE_TOKEN env override
  would be an architectural change to TokenStore (Plan 03 territory) and a new auth-related code path; per AGENTS.md
  "challenge the approach" rule and the deviation rules, we adapted the script to test the same invariants against the
  bridge's actual plaintext (extract via JSON parse, then assert) rather than introducing the override. Same invariants
  proven (CF-02 exactly-once + actor_token_fp positive control); zero new auth surface.
- *_RequestLogger uses slog.Default() rather than a passed-in *slog.Logger:*_ This keeps the chi middleware factory
  signature minimal and piggy-backs on the scrubbing handler wrapped around `slog.Default()` in main.go. If a future
  caller wants to inject a different logger, the signature can grow `RequestLogger(logger *slog.Logger)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] chi.RouteContextKey does not exist in chi/v5.3.2 — actual symbol is chi.RouteCtxKey**

- **Found during:** Task 2 compilation (`go test ./...` first run)
- **Issue:** Plan's reference context used `chi.RouteContextKey`; chi/v5.3.2 names the context key `RouteCtxKey`. Build
  error: `undefined: chi.RouteContextKey`
- **Fix:** Renamed symbol in `route_ctx.go` to `chi.RouteCtxKey`
- **Files modified:** terraform-bridge/internal/httpapi/middleware/route_ctx.go
- **Verification:** `go test ./internal/httpapi/middleware/...` exits 0; both new tests pass
- **Committed in:** d80ee89 (Task 2 commit)

**2. [Rule 1 - Bug] `var rec httptest.ResponseRecorder` zero-value has nil `*bytes.Buffer` Body — panics on
json.NewEncoder**

- **Found during:** Task 2 (`go test ./internal/httpapi/handlers/...`)
- **Issue:** Test used `var rec httptest.ResponseRecorder`, but the zero-value's `Body *bytes.Buffer` field is nil.
  `json.NewEncoder(rec.Body)` dereferenced nil. `httptest.NewRecorder()` is the constructor that initializes Body.
- **Fix:** Switched to `rec := httptest.NewRecorder()` (which initializes Body to a fresh *bytes.Buffer)
- **Files modified:** terraform-bridge/internal/httpapi/handlers/healthz_test.go
- **Verification:** `go test ./internal/httpapi/handlers/...` exits 0
- **Committed in:** d80ee89 (Task 2 commit)

### Plan-document deviations (not auto-fixes)

**3. [Plan adaptation] verify-bridge-no-token-leak.sh positive-control assertions rewritten to test against the bridge's
auto-generated plaintext**

- **Found during:** Task 3 — reading the plan's bash carefully against the actual TokenStore API
- **Issue:** The plan wrote `EXPECTED_FP=$(printf '%s' "${FAKE_TOKEN}" | sha256sum | cut -c1-16)` then asserted the
  bridge emitted a record whose `actor_token_fp == EXPECTED_FP`. But `FAKE_TOKEN` is the SUPERVISOR_TOKEN (set as
  container env). The bridge never reads SUPERVISOR_TOKEN as its own bearer token; it calls `store.Generate()` (Plan 01)
  which uses `crypto/rand`. The expected fingerprint would never match — the assertion would FAIL by design, breaking
  the pre-commit hook on every commit.
- **Fix:** Adapted the script to parse the `bridge.token.issued` record from the captured JSON output, extract its
  `plaintext` and `actor_token_fp` fields with `grep -oE`, then assert:
  - `actor_token_fp == SHA-256[8](plaintext)` (positive control)
  - `plaintext` appears exactly once in stdout (CF-02)
  - `http.request` OPS-01 record present for `GET /` Same invariants proven; no architectural change required.
- **Files modified:** internal/verify-bridge-no-token-leak.sh
- **Verification:** Ran the assertion logic against synthetic positive-case JSON (pass) and synthetic token-leak JSON
  (fail). All 7 strengthened assertions behave correctly. The actual `docker run` integration requires Docker (not
  podman — overlay mount fails in this dev environment); the script will run end-to-end in CI / on a docker-capable
  host. Validation locally: `bash -n` and grep / positive-control logic exercised.
- **Committed in:** 8ce3035 (Task 3 commit)

---

**Total deviations:** 3 (2 auto-fixed compilation bugs, 1 plan-adaptation with documented rationale) **Impact on plan:**
Both bug-fixes necessary for compilation. The verify-script adaptation preserves every invariant the plan asked for
(exactly-once + positive control + OPS-01 record) while not introducing a new auth-related code path (BRIDGE_TOKEN env
override) that would belong to Plan 03 and was not part of the plan's locked decisions. Zero scope creep.

## Issues Encountered

- Dev environment podman/overlay mount error when attempting `docker build` (`no such device`) — the integration
  verify-script smoke test could not be run end-to-end here. The script's syntax is valid (`bash -n` clean) and its
  assertion logic is proven against synthetic log output that mirrors what the bridge emits. Real docker (CI / arm64
  runner) will execute it as documented.
- `git fetch origin` showed local `main` is 35 commits behind `origin/main` (mostly CI-only / Meridian auto-bump
  commits). Per the execute-phase instruction "this phase only commits locally" and AGENTS.md "no push", did not rebase
  or push. Orchestrator handles sync.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 03 (rotation + grace window) can be picked up next; `/v1/auth/rotate` will mount under the existing `/v1`
  RequireBearer subrouter at `terraform-bridge/internal/httpapi/router.go`. Every record emitted by the rotation flow
  automatically passes through the scrubbing handler installed in main.go.
- Phase 11 (Read API) needs no changes to the logging or `/healthz` layers; new handlers mount under `/v1/*` and emit
  OPS-01 records automatically.
- Phase 12 (Write API + safety + concurrency) needs the same — nothing in this plan constrains write semantics; the
  OPS-01 records will carry the correct status codes (401/403/409/423) and the AUTH-05 invariant keeps holding.
- Phase 14 (Real-HA E2E) is where the verify-bridge-no-token-leak.sh script is run for real against a freshly-built HA
  add-on container, with explicit per-call user authorization per AGENTS.md "Live Systems" rule.

## Self-Check

**Status:** PASSED

All claimed files exist; all claimed commit hashes are present in `main`:

```
FOUND: terraform-bridge/internal/logging/scrubbing_handler.go
FOUND: terraform-bridge/internal/logging/scrubbing_handler_test.go
FOUND: terraform-bridge/internal/httpapi/middleware/route_ctx.go
FOUND: terraform-bridge/internal/httpapi/middleware/request_log.go
FOUND: terraform-bridge/internal/httpapi/middleware/request_log_test.go
FOUND: terraform-bridge/internal/httpapi/handlers/healthz.go
FOUND: terraform-bridge/internal/httpapi/handlers/healthz_test.go
FOUND: .planning/phases/10-auth-layer-structured-logging-healthcheck/10-02-SUMMARY.md

FOUND: fb9fed0  (Task 1 — scrubbing handler)
FOUND: d80ee89  (Task 2 — RequestLogger + Healthz + tests)
FOUND: 8ce3035  (Task 3 — router/main wiring + verify script + pre-commit)
```

`go build ./...`, `go vet ./...`, `go test ./...` all exit 0 in `terraform-bridge/`; the `internal/validate-versions.sh`
pre-commit hook continues to pass.

---

_Phase: 10-auth-layer-structured-logging-healthcheck_ _Completed: 2026-08-31_
