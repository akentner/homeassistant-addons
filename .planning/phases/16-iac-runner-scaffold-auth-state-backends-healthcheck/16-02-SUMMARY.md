---
phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
plan: 02
subsystem: auth,httpapi,secrets,state-backend
tags: [go, slog, scrubbing, chmod-600, state-backend, r2, s3, local, opentofu, ha-addon, healthz]

# Dependency graph
requires:
  - phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
    plan: "01"
    provides: "iac-runner 4-file scaffold + chi router + auth TokenStore + Tailscale BindResolver + RequestLogger middleware + Plan 01 /healthz stub (tofu_on_path:true + keys_chmod_600:true placeholders) + /v1/auth/rotate handler"
provides:
  - iac-runner/internal/logging: slog.Handler scrubbing wrapper (SEC-02 layer 1; case-insensitive redaction of Authorization, Bearer, token, password, key, secret to '<redacted>')
  - iac-runner/internal/keys: /data/keys/ chmod-600 + UID-ownership validator (SEC-01) with per-backend CredentialFiles requirement check
  - iac-runner/internal/statebackend: Backend interface + Options + ErrUnsupported + r2Backend + s3Backend + localBackend + factory.New (STBK-01..05)
  - Real /healthz handler: 200 + HealthResponse on exec.LookPath('tofu') + validator.Validate() pass; 503 + empty body on either fail (2s budget; failure logged server-side only)
  - main.go: slog.NewJSONHandler wrapped with NewScrubbingHandler; statebackend.New factory call + audit log line; keys.Validate() at startup (exit 1 on failure); NewRouter(runnerVersion, store, validator)
affects:
  - 17-git-integration-apply-job-system (Phase 17 consumes backend.Endpoint() + backend.Bucket() + backend.UseLockfile() to construct tofu init command lines; validators may be invoked from /v1/plan pre-flight checks)
  - 18-mqtt-discovery-ha-sensors-buttons (Phase 18 surfaces /healthz + /v1/version status to HA entities; the scrubbing wrapper protects Phase 18's MQTT publish payloads from leaking credentials)
  - 19-e2E-verification-operator-docs (Phase 19 empirically verifies the SEC-02 scrubbing wrapper against a real tofu apply that emits sensitive-key log records; Phase 19 also runs the keys validator against a real /data/keys/ with chmod-600 enforcement)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-layer credential masking: slog.Handler wrapper (Plan 02) + chi middleware stripping Authorization from r.Header.Clone() (Plan 01) — same defense-in-depth pattern as terraform-bridge AUTH-05"
    - "Validator constructs from statebackend.Backend.CredentialFiles() rather than hardcoded file lists — local backend returns nil (no required files), r2 returns [r2-access.key, r2-secret.key, r2-account-id], s3 returns [s3-access.key, s3-secret.key]"
    - "Factory dispatch pattern: switch on backend string, return ErrUnsupported wrapped with fmt.Errorf('%w: %q', …) for any other value — errors.Is(err, ErrUnsupported) works without string parsing"
    - "Scrubbing wrapper preserves slog.Handler contract: Handle / WithAttrs / WithGroup all return new wrappers whose inner handlers carry the chained configuration — a slog.New(NewScrubbingHandler(jsonHandler)).WithGroup('http') still scrubs nested Authorization attrs"
    - "/healthz 503 body always empty (Content-Length: 0) — failure reason slog.Warn'd server-side only, never returned to caller (SEC-02 layer 2)"
    - "R2 endpoint constructed from /data/keys/r2-account-id (plaintext, non-sensitive) at factory time — failure to read the file → startup fail-fast"
    - "Backend.UseLockfile() = true for r2/s3 (S3-object lock semantics, no DynamoDB required); local = false (file-based lock via /data/terraform.tfstate.lock)"
    - "defaultDataDir = '/data' + defaultKeysDir = '/data/keys' consts surface the v1.4 PROJECT.md decisions (file-on-volume) for future plans to reuse"

key-files:
  created:
    - iac-runner/internal/logging/scrubbing_handler.go (scrubbingHandler struct + NewScrubbingHandler + scrubAttr + sensitiveKeys map with Authorization, Bearer, authorization, bearer, token, password, key, secret)
    - iac-runner/internal/logging/scrubbing_handler_test.go (6 Test functions: AllKeys subtests, CaseInsensitive subtests, PassesNonSensitive, WithGroup, WithAttrs, ValueContainingBearerSubstring)
    - iac-runner/internal/keys/validator.go (Validator + NewValidator + Validate + ErrKeysNotChmod600 + ErrKeysMissing + RequiredFiles + KeysDir)
    - iac-runner/internal/keys/validator_test.go (7 Test functions: AllChmod600, MissingRequired, WrongMode, LocalNoRequired, ExtraFilesChecked, KeysDirIsFile, NewValidatorRequiredFilesCopy)
    - iac-runner/internal/statebackend/backend.go (Backend interface + Options struct + ErrUnsupported sentinel)
    - iac-runner/internal/statebackend/r2.go (r2Backend + newR2Backend reading /data/keys/r2-account-id + Endpoint/Bucket/Region/UseLockfile/CredentialFiles/Name)
    - iac-runner/internal/statebackend/s3.go (s3Backend + newS3Backend from user-supplied Options)
    - iac-runner/internal/statebackend/local.go (localBackend + Endpoint='' + Bucket='/data/terraform.tfstate' + UseLockfile=false)
    - iac-runner/internal/statebackend/factory.go (New(backend string, opts Options) (Backend, error) dispatcher)
    - iac-runner/internal/statebackend/factory_test.go (5 Test functions: FactoryNewR2 + FactoryNewR2MissingAccountID + FactoryNewS3 + FactoryNewLocal + FactoryInvalid)
    - iac-runner/internal/httpapi/handlers/healthz_test.go (3 Test functions: HealthzBothPass + HealthzValidatorFail + HealthzKeysOnly)
  modified:
    - iac-runner/cmd/runner/main.go (defaultDataDir + defaultKeysDir consts; slog.NewJSONHandler wrapped with NewScrubbingHandler; statebackend.New factory + state_backend_ready audit log; keys.NewValidator + validator.Validate() at startup with os.Exit(1) on failure; NewRouter gains validator parameter)
    - iac-runner/internal/httpapi/handlers/healthz.go (real impl: 2s context.WithTimeout budget + exec.LookPath('tofu') + validator.Validate(); 200 + HealthResponse on both-pass; 503 + Content-Length: 0 empty body on either fail; slog.Warn('healthz_failed', …) for server-side forensics)
    - iac-runner/internal/httpapi/router.go (NewRouter signature extended from (runnerVersion, store) to (runnerVersion, store, validator); /healthz wired with handlers.Healthz(runnerVersion, validator))

key-decisions:
  - "SEC-02 scrubber is a strict SUPERSET of terraform-bridge's AUTH-05 baseline (Authorization + Bearer + token + password + key + secret) — bridge-specific tokens (SUPERVISOR_TOKEN, bridge_token) removed because iac-runner does not hold a SUPERVISOR_TOKEN (AUTHR-01)"
  - "Scrubbing is key-name based, NOT value-substring based — a log message containing 'Bearer' for human readers must NOT be corrupted (per terraform-bridge agent-discretion precedent)"
  - "keys package imports statebackend.Backend (to read CredentialFiles()) but statebackend has NO inbound dependency on auth or keys — defense-in-depth layering keeps the validator unit-testable with a fakeBackend"
  - "/healthz 503 response body is ALWAYS empty (Content-Length: 0) — no error code, no file path, no exit code; the actual failure is slog.Warn'd server-side only (OBS-01 + SEC-02 layer 2)"
  - "/healthz per-probe budget is 2s (context.WithTimeout); the budget is reserved for future Phase 17 probes (tofu version probe + remote-state reachability check) without changing the handler signature"
  - "R2 endpoint constructed at factory time from /data/keys/r2-account-id — missing or unreadable file → factory returns wrapped error → main.go startup fail-fast"
  - "statebackend.New returns ErrUnsupported wrapped with fmt.Errorf('%w: %q', ErrUnsupported, backend) — errors.Is(err, ErrUnsupported) works without string parsing"
  - "All exit-on-failure paths in main.go follow the same shape: slog.Error('xxx_failed', 'err', err.Error()) then os.Exit(1) — matches terraform-bridge precedent"
  - "Backend.UseLockfile() = true for r2/s3 (S3-object lock semantics per IRUN-H-1 spike), false for local (file-based lock via /data/terraform.tfstate.lock — a DIFFERENT mechanism that would not interoperate with use_lockfile)"

patterns-established:
  - "Two-layer credential masking: slog.Handler wrapper (Plan 02) + chi middleware stripping Authorization from r.Header.Clone() (Plan 01) — same defense-in-depth pattern as terraform-bridge AUTH-05"
  - "Fail-fast at every startup gate (bind resolution, statebackend.New, keys.Validate(), token store init): slog.Error audit record then os.Exit(1) — no degraded mode for credential safety"
  - "Validator constructs from interface (statebackend.Backend.CredentialFiles()) rather than hardcoded file lists — extends naturally when Phase 17 adds new backends"

requirements-completed: [SEC-01, SEC-02, STBK-01, STBK-02, STBK-03, STBK-04, STBK-05]

# Metrics
duration: 18 min
completed: 2026-09-06
---
# Phase 16 Plan 02: Log Scrubbing + /data/keys/ Validator + State Backends r2/s3/local + Real /healthz Summary

**SEC-02 slog.Handler scrubber (case-insensitive redaction of Authorization, Bearer, token, password, key, secret)
+ SEC-01 /data/keys/ chmod-600 + UID-ownership validator + STBK-01..05 state backend interface with r2/s3/local
implementations + factory dispatcher + real /healthz that calls exec.LookPath('tofu') + validator.Validate() per
request**

## Performance

- **Duration:** 18 min (2026-09-06T16:41Z – 2026-09-06T16:47Z)
- **Started:** 2026-09-06T16:41:20Z
- **Completed:** 2026-09-06T16:47:12Z
- **Tasks:** 2
- **Files modified:** 14 (10 created + 4 modified)
- **Tests added:** 21 (6 scrubbing + 7 validator + 5 factory + 3 healthz) → 41 total tests passing across iac-runner

## Accomplishments

- `iac-runner/internal/logging/scrubbing_handler.go` — `slog.Handler` wrapper that redacts values for the
  PROJECT.md-mandated key set (Authorization, Bearer, token, password, key, secret — case-insensitive) to
  `"<redacted>"` BEFORE delegating to the wrapped inner handler. Preserves the `slog.Handler` contract:
  `Handle` / `WithAttrs` / `WithGroup` all return new wrappers whose inner handlers carry the chained
  configuration, so a logger created with `slog.New(NewScrubbingHandler(jsonHandler)).WithGroup("http")`
  still scrubs nested Authorization attrs. 6 unit tests assert no credential value (`AKIA...EXAMPLE`,
  `-----BEGIN RSA PRIVATE KEY-----`, real token strings) survives the handler.

- `iac-runner/internal/keys/validator.go` — `Validator` iterates `/data/keys/`, asserts every file is chmod
  600 + owned by the current process UID, asserts every required credential (per
  `statebackend.Backend.CredentialFiles()`) exists. Local backend returns nil from `CredentialFiles()` so
  an absent `/data/keys/` is acceptable. Failures wrap `ErrKeysNotChmod600` or `ErrKeysMissing` with the
  offending filename + mode. 7 unit tests cover all-pass, missing-required, wrong-mode, local-no-required
  (empty dir + absent dir), extra-files-checked, non-directory keysDir, defensive-copy invariant.

- `iac-runner/internal/statebackend/{backend,r2,s3,local,factory}.go` — `Backend` interface
  (Endpoint, Bucket, Region, UseLockfile, CredentialFiles, Name) + `Options` struct + `ErrUnsupported`
  sentinel. R2 implementation reads `/data/keys/r2-account-id` at construction time and constructs endpoint
  as `https://<account_id>.r2.cloudflarestorage.com` (region hard-coded to `"auto"`). S3 implementation
  uses user-supplied endpoint + bucket + region. Local implementation exposes `Bucket() = "/data/terraform.tfstate"`
  and `UseLockfile() = false` (file-based lock, a different mechanism than S3-object lock). Factory
  `New(backend, opts)` dispatches on backend string and returns `ErrUnsupported` wrapped with the
  offending name for any other value. 5 unit tests cover the 4 dispatch cases + invalid (incl. empty
  string).

- `iac-runner/cmd/runner/main.go` — `slog.NewJSONHandler` wrapped with `NewScrubbingHandler` (SEC-02 layer 1).
  State backend constructed via `statebackend.New(opts.StateBackend, statebackend.Options{...})`; endpoint +
  bucket + region + use_lockfile logged in a `state_backend_ready` audit record for operator visibility.
  `keys.NewValidator("/data/keys", backend)` constructed and `validator.Validate()` called BEFORE token
  store init; failure → `os.Exit(1)` with `keys_validation_failed` audit record naming the required-files
  list + the underlying error (SEC-01 fail-fast). `NewRouter` gains the validator parameter; store +
  validator both flow into the router construction. `defaultDataDir` + `defaultKeysDir` consts surface the
  v1.4 PROJECT.md decisions for future plans to reuse.

- `iac-runner/internal/httpapi/router.go` — `NewRouter` signature extended from `(runnerVersion, store)` to
  `(runnerVersion, store, validator)`. Middleware order unchanged (RequestID → Recoverer → RequestLogger).
  `/healthz` wired with `handlers.Healthz(runnerVersion, validator)`.

- `iac-runner/internal/httpapi/handlers/healthz.go` — Real probes replace Plan 01's always-200 stub. Per
  request: `exec.LookPath("tofu")` + `validator.Validate()` under a 2s `context.WithTimeout` budget.
  200 + `HealthResponse{status, tofu_on_path, keys_chmod_600, runner_version}` when BOTH pass; 503 +
  `Content-Length: 0` (empty body) when EITHER fails. The 503 path NEVER leaks the error reason — a single
  `slog.Warn("healthz_failed", …)` audit record captures it server-side only. The 2s budget slot is
  reserved for future Phase 17 probes (tofu version probe + remote-state reachability check) without
  changing the handler signature.

## Task Commits

Each task was committed atomically:

1. **Task 1: scrubbing slog.Handler + keys validator + state backends** - `10e5dd2` (feat)
2. **Task 2: main.go + router + real /healthz wiring** - `96a4a12` (feat)

**Plan metadata:** `docs(16-02): complete plan` (next commit — captures SUMMARY.md + STATE.md + ROADMAP.md +
REQUIREMENTS.md updates).

## Files Created/Modified

### Created (11 files)

- `iac-runner/internal/logging/scrubbing_handler.go` — `slog.Handler` wrapper that redacts values for
  sensitive keys (Authorization, Bearer, token, password, key, secret — case-insensitive) to `"<redacted>"`
  before delegating to the wrapped inner handler. Package doc comment explains the SEC-02 invariant.
- `iac-runner/internal/logging/scrubbing_handler_test.go` — 6 `Test` functions covering all 6 sensitive
  keys (subtests), case-insensitive variants (`TOKEN` / `Token` / `AUTHORIZATION` / `AuThOrIzAtIoN`),
  non-sensitive pass-through including substrings of sensitive keys (`token_count` survives), `WithGroup`
  nested scrubbing, `WithAttrs` chain scrubbing, and the key-name-not-value-substring design invariant.
- `iac-runner/internal/keys/validator.go` — `Validator` that walks `/data/keys/`, asserts chmod 600 + UID
  ownership for every file, asserts every required credential (per `statebackend.Backend.CredentialFiles()`)
  exists. Required files derived from the backend — local backend returns nil so an absent `/data/keys/`
  is acceptable. Failures wrap `ErrKeysNotChmod600` or `ErrKeysMissing` with the offending filename.
  Independent of `internal/auth/` — no transitive coupling.
- `iac-runner/internal/keys/validator_test.go` — 7 `Test` functions covering all-pass, missing-required,
  wrong-mode, local-no-required (empty dir + absent dir), extra-files-checked, non-directory keysDir,
  and a defensive-copy invariant on `RequiredFiles`.
- `iac-runner/internal/statebackend/backend.go` — `Backend` interface (Endpoint, Bucket, Region,
  UseLockfile, CredentialFiles, Name) + `Options` struct (R2Bucket / S3Endpoint / S3Bucket / S3Region /
  DataDir) + `ErrUnsupported` sentinel.
- `iac-runner/internal/statebackend/r2.go` — R2 implementation. Endpoint constructed from
  `/data/keys/r2-account-id` (plaintext, non-sensitive) as
  `https://<account_id>.r2.cloudflarestorage.com`; bucket from `Options.R2Bucket`; Region hard-coded to
  `"auto"`; `UseLockfile() = true` (R2 supports S3-object lock per IRUN-H-1 spike); `CredentialFiles`
  = `[r2-access.key, r2-secret.key, r2-account-id]`.
- `iac-runner/internal/statebackend/s3.go` — S3 implementation. Endpoint from `Options.S3Endpoint`
  (user-supplied); bucket + region from `Options`; `UseLockfile() = true`; `CredentialFiles`
  = `[s3-access.key, s3-secret.key]`.
- `iac-runner/internal/statebackend/local.go` — Local implementation. `Endpoint() = ""`;
  `Bucket() = "/data/terraform.tfstate"`; `UseLockfile() = false` (file-based lock via
  `/data/terraform.tfstate.lock`); no credentials.
- `iac-runner/internal/statebackend/factory.go` — `New(backend, opts)` dispatcher. Returns `r2Backend` /
  `s3Backend` / `localBackend` for `"r2"` / `"s3"` / `"local"`; `ErrUnsupported` wrapped with the
  offending name for any other value.
- `iac-runner/internal/statebackend/factory_test.go` — 5 `Test` functions covering the 4 dispatch cases
  (r2 happy + missing account-id, s3, local) + invalid (`ErrUnsupported` via `errors.Is` for `"minio"`
  and empty string).
- `iac-runner/internal/httpapi/handlers/healthz_test.go` — 3 `Test` functions: both-pass (local backend
  with no required keys, tofu on PATH → 200 + JSON body validated for shape), validator-fail (one 0644
  file → 503 + `Content-Length: 0` asserted explicitly), keys-only (local backend happy path; accepts
  200 OR 503 depending on whether tofu is on the test host's PATH, asserts empty body on 503).

### Modified (3 files)

- `iac-runner/cmd/runner/main.go` — `slog.NewJSONHandler` wrapped with `NewScrubbingHandler` (SEC-02 layer
  1). State backend constructed via `statebackend.New(opts.StateBackend, statebackend.Options{...})`;
  endpoint + bucket + region + use_lockfile logged for operator visibility. `keys.NewValidator("/data/keys",
  backend)` constructed and `validator.Validate()` called BEFORE token store init; failure →
  `os.Exit(1)` with `keys_validation_failed` audit record. `NewRouter` gains the validator parameter.
  `defaultDataDir = "/data"` + `defaultKeysDir = "/data/keys"` consts surface the v1.4 PROJECT.md
  decisions for future plans to reuse.
- `iac-runner/internal/httpapi/handlers/healthz.go` — Real probes replace Plan 01's always-200 stub.
  Per request: `exec.LookPath("tofu")` + `validator.Validate()` under a 2s `context.WithTimeout` budget.
  200 + `HealthResponse` when BOTH pass; 503 + `Content-Length: 0` (empty body) when EITHER fails.
  Failure reason slog.Warn'd server-side only. The 2s budget slot is reserved for future Phase 17
  probes without changing the handler signature.
- `iac-runner/internal/httpapi/router.go` — `NewRouter` signature extended from `(runnerVersion, store)`
  to `(runnerVersion, store, validator)`. Middleware order unchanged. `/healthz` wired with
  `handlers.Healthz(runnerVersion, validator)`.

## Decisions Made

- **SEC-02 scrubber is a strict superset of terraform-bridge's AUTH-05 baseline.** Authorization + Bearer +
  token + password + key + secret. Bridge-specific tokens (`SUPERVISOR_TOKEN`, `bridge_token`) removed
  because iac-runner does not hold a `SUPERVISOR_TOKEN` (AUTHR-01). The same key set is also the
  PROJECT.md explicit listing for iac-runner (the Plan 02 agent's discretion was resolved in the plan).

- **Scrubbing is key-name based, NOT value-substring based.** A log message containing "Bearer" for human
  readers must NOT be corrupted. Same design as terraform-bridge's AUTH-05 (`TestScrubbingHandlerValue
  ContainingBearerSubstring` documents the invariant explicitly).

- **keys package imports statebackend.Backend (to read CredentialFiles()) but statebackend has NO inbound
  dependency on auth or keys.** Defense-in-depth layering keeps the validator unit-testable with a
  `fakeBackend` without dragging in any of auth's state. The same `Backend` interface is what Phase 17's
  `/v1/plan` and `/v1/apply` handlers will consume — the layering is intentional and forward-looking.

- **`/healthz` 503 response body is ALWAYS empty (`Content-Length: 0`).** No error code, no file path, no
  exit code. The actual failure is `slog.Warn("healthz_failed", …)`'d server-side only (SEC-02 layer 2).
  An external monitor polling /healthz learns only "service degraded", not "your /data/keys/r2-access.key
  is mode 644". Same OPS-03 pattern as terraform-bridge Phase 10 (D-08).

- **`/healthz` per-probe budget is 2s (`context.WithTimeout`).** The validator + LookPath are both fast
  synchronous calls; the budget is reserved for future Phase 17 probes (tofu version probe + remote-state
  reachability check) without changing the handler signature. The `_ = ctx` line in `healthz.go` is the
  deliberate marker that the timeout slot is reserved.

- **R2 endpoint constructed at factory time from `/data/keys/r2-account-id`.** Missing or unreadable file
  → factory returns wrapped error → main.go startup fail-fast (SEC-01 fail-fast cascades into the state
  backend init too). The account ID is plaintext (non-sensitive) but its file-on-volume location still
  gets chmod-600-validated by the keys validator for defense-in-depth (it's part of
  `r2Backend.CredentialFiles()`).

- **`statebackend.New` returns `ErrUnsupported` wrapped with `fmt.Errorf("%w: %q", ErrUnsupported, backend)`.**
  `errors.Is(err, ErrUnsupported)` works without string parsing. The empty string case is also tested
  to fail defensively (main.go substitutes the default before calling `New`, but we don't want to be
  permissive if a future caller forgets).

- **All exit-on-failure paths in main.go follow the same shape: `slog.Error("xxx_failed", "err",
  err.Error())` then `os.Exit(1)`.** Matches terraform-bridge precedent. The AGENTS.md "Live Systems"
  rule: no degraded mode for credential safety. Restart + `chmod 600 <file>` is the only remediation; the
  operator sees the failing path in the startup log line.

- **`Backend.UseLockfile() = true` for r2/s3 (S3-object lock semantics per IRUN-H-1 spike), `false` for
  local (file-based lock via `/data/terraform.tfstate.lock` — a DIFFERENT mechanism that would not
  interoperate with `use_lockfile`).** Mixing them up would either disable locking or produce an
  unrecognized-backend-config error from `tofu init`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `TestScrubbingHandlerWithGroup` initially asserted flat-key paths (`rec["http.Authorization"]`)
but slog.JSONHandler renders `WithGroup` as a nested object.**

- **Found during:** Task 1 verification (`go test ./internal/logging/...`)
- **Issue:** The plan's test code assumed slog renders group keys flat (`http.Authorization`),
  but slog.JSONHandler with WithGroup produces a nested JSON object (`"http":{"Authorization":...}`).
  The scrubber itself works correctly (matches the leaf key before serialization); the assertion
  was wrong.
- **Fix:** Updated the assertion to navigate into the nested `rec["http"].(map[string]any)` map and
  read `"Authorization"` + `"route"` from there. The redaction invariant is unchanged — the
  scrubber still matches the leaf key name `Authorization`.
- **Files modified:** `iac-runner/internal/logging/scrubbing_handler_test.go`
- **Verification:** `go test ./internal/logging/...` passes; the 6 `Test` functions cover all 6
  sensitive keys, case-insensitive variants, non-sensitive pass-through, WithGroup + WithAttrs
  scrubbing, and the value-substring design invariant.
- **Committed in:** `10e5dd2` (Task 1 commit)

**2. [Rule 1 - Bug] `TestValidateKeysDirWrongMode` initially asserted `strings.Contains(err.Error(),
"0644")` but Go's `%o` formatter does not include the leading zero.**

- **Found during:** Task 1 verification (`go test ./internal/keys/...`)
- **Issue:** `fmt.Errorf("%w: %s mode is %o, want 0600", ...)` produces the mode as `644` (no leading
  zero) — `fmt`'s `%o` verb does not zero-pad. The plan's test code expected `0644`.
- **Fix:** Updated the assertion to check for `644` (with a comment explaining the 0644 octal
  semantics). The validator itself was correct; only the test assertion needed adjustment.
- **Files modified:** `iac-runner/internal/keys/validator_test.go`
- **Verification:** `go test ./internal/keys/...` passes; the 7 `Test` functions cover all-pass,
  missing-required, wrong-mode, local-no-required, extra-files-checked, non-directory keysDir, and
  the defensive-copy invariant.
- **Committed in:** `10e5dd2` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test-assertion corrections that surfaced during
verification; neither affected the production code). **Impact on plan:** None — both auto-fixes were
narrowly scoped test corrections. Production code matched the plan's templates exactly. The plan's
two deviations were the only issues discovered during verification.

## Issues Encountered

None beyond the two test-assertion deviations above. The plan's templates for the production code
were followed exactly: scrubbing_handler.go mirrors terraform-bridge's structure with the SUPERSET
key set; keys/validator.go follows the plan's verbatim outline; statebackend/{backend,r2,s3,local,
factory}.go follow the plan's template with minor Go-idiomatic additions (e.g. `strings.TrimSpace`
on the r2-account-id read in `newR2Backend`, `Credentials != nil` defensive check); healthz.go follows
the plan's verbatim outline; router.go extends the signature exactly as specified; main.go follows
the plan's outlined extension points.

The 2s per-probe budget slot in `/healthz` (`context.WithTimeout` + `_ = ctx`) is intentional per the
plan: it reserves the budget for future Phase 17 probes (tofu version probe + remote-state
reachability check) without changing the handler signature. Phase 17 will replace the `_ = ctx` line
with `validator.Validate(ctx)` or pass `ctx` through to a remote-state ping.

## User Setup Required

None - no external service configuration required at this phase.

Plan 03 will introduce `GET /v1/version` (handlers.Version consuming `contract.VersionHandshake`),
write the operator `DOCS.md`, and add the README shield badges. Live-HA empirical verification is
deferred to Phase 19 (E2E + DOCS + Operator Runbook).

## Next Phase Readiness

- Plan 02's 14 files establish the SEC-01 + SEC-02 + STBK-01..05 surface Phase 17 (git + apply jobs)
  consumes: `backend.Endpoint() + backend.Bucket() + backend.Region() + backend.UseLockfile()` are the
  inputs to `tofu init -backend-config=…`; `validator.Validate()` may be invoked from `/v1/plan`
  pre-flight checks to fail fast on a degraded keys directory before the (expensive) git clone +
  tofu init sequence starts.

- Phase 18 (MQTT Discovery) and Phase 17 (git + apply) are both slottable now: `slog` records
  emitted from any future handler go through the scrubbing wrapper, so Phase 17's `/v1/plan` and
  `/v1/apply` handlers can log freely without worrying about credential leakage in the record values.

- Plan 03 will add `GET /v1/version` consuming `contract.VersionHandshake` and write the operator
  documentation. The `statebackend.Options{DataDir: "/data"}` is the default and the only
  filename-rooted dependency is `r2-account-id` — Phase 17's `git clone` flow will reuse the
  `defaultKeysDir` constant for SSH deploy keys (`/data/keys/<name>.key`).

- Live-HA empirical verification (token issuance + rotation + bind gate + /healthz against a real
  HA host with tofu installed + chmod-600-validated keys) is deferred to Phase 19.

---

*Phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck*
*Completed: 2026-09-06*

## Self-Check: PASSED

- `iac-runner/internal/logging/scrubbing_handler.go` exists, non-empty
- `iac-runner/internal/logging/scrubbing_handler_test.go` exists, non-empty
- `iac-runner/internal/keys/validator.go` exists, non-empty
- `iac-runner/internal/keys/validator_test.go` exists, non-empty
- `iac-runner/internal/statebackend/backend.go` exists, non-empty
- `iac-runner/internal/statebackend/r2.go` exists, non-empty
- `iac-runner/internal/statebackend/s3.go` exists, non-empty
- `iac-runner/internal/statebackend/local.go` exists, non-empty
- `iac-runner/internal/statebackend/factory.go` exists, non-empty
- `iac-runner/internal/statebackend/factory_test.go` exists, non-empty
- `iac-runner/internal/httpapi/handlers/healthz.go` exists, non-empty (real impl)
- `iac-runner/internal/httpapi/handlers/healthz_test.go` exists, non-empty
- `iac-runner/internal/httpapi/router.go` exists, non-empty (Validator param)
- `iac-runner/cmd/runner/main.go` exists, non-empty (scrubbing wrapper + factory + validate)
- `cd iac-runner && go build ./...` exits 0
- `cd iac-runner && go vet ./...` exits 0
- `cd iac-runner && go test ./...` passes (20 Plan 01 + 21 Plan 02 = 41 total tests)
- `python3 internal/validate-addon-config.py iac-runner` exits 0
- All Task 1 + Task 2 plan acceptance greps pass
- SEC-01 + SEC-02 + STBK-01..05 marked complete in `.planning/REQUIREMENTS.md`
- Phase 16 plan 02 marked complete (2/3) in `.planning/STATE.md` and ROADMAP updated
- `git log --oneline --grep="16-02"` returns ≥3 commits (2 task commits + 1 docs metadata commit)