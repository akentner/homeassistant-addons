---
phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
plan: 03
subsystem: auth, httpapi, docs, ci
tags: [go, chi, bearer-auth, opentofu, r2, s3, hadolint, yamllint, markdownlint, mqtt]

# Dependency graph
requires:
  - phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
    plan: "01"
    provides: "iac-runner 4-file scaffold + TokenStore + Tailscale BindResolver + /v1/auth/rotate handler + contract.VersionHandshake struct + internal/version semver constants + cmd/runner/version.go runnerVersion ldflags variable"
  - phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
    plan: "02"
    provides: "slog scrubbing wrapper (SEC-02) + /data/keys/ chmod-600 validator (SEC-01) + statebackend r2/s3/local + factory + real /healthz + extended NewRouter(runnerVersion, store, validator)"
provides:
  - GET /v1/version mounted under RequireBearer-wrapped /v1 subrouter (Phase 16 SC#8 runner-version handshake)
  - handlers.Version(runnerVersion) http.HandlerFunc consuming contract.VersionHandshake + internal/version constants
  - handlers/version_test.go: 3 test functions (field presence, compile-time defaults, chi integration: missing/wrong/valid bearer)
  - iac-runner/DOCS.md operator reference (every config option + /data/keys/ chmod-600 + bearer issuance + 24h rotation + 3 backends + use_lockfile semantics + every /v1/* endpoint)
  - iac-runner/README.md user-facing intro with shields (v0.1.0 + experimental + amd64) + install + first-time bearer retrieval + link to DOCS.md
  - .pre-commit-config.yaml extended with iac-runner in validate-dockerfile-args regex (yamllint + hadolint remain global, cover iac-runner implicitly)
affects:
  - 17-git-integration-apply-job-system (Phase 17 /v1/plan + /v1/apply consume GET /v1/version for client capability negotiation; DOCS.md is the operator reference for Phase 17 deployment)
  - 18-mqtt-discovery-ha-sensors-buttons (Phase 18 surfaces /healthz + /v1/version status via HA sensor entities; DOCS.md is the install reference)
  - 19-e2E-verification-operator-docs (Phase 19 empirical exercise against live HA host tests the full surface including /v1/version auth + body shape)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Constructor pattern for handler functions returning http.HandlerFunc: handlers.Version(runnerVersion string) — receives compile-time state via closure, no module-level globals"
    - "Chi integration test pattern: spin up httptest.NewServer(chi.NewRouter()), drive with http.DefaultClient, table-driven test cases (missing/wrong/valid bearer) assert both status code and ErrorResponse/VersionHandshake body shape"
    - "README shields pattern: minimal set (release + project-stage + amd64) — no maintenance/license shields per experimental add-on status; link to DOCS.md for full operator reference"
    - "DOCS.md operator-runbook structure (mirrors terraform-bridge/DOCS.md): Overview → Install → First-time setup → Configuration (every option with example) → State backend credential files → HTTP API → State backend use_lockfile semantics → Log scrubbing"
    - "Pre-commit wiring pattern: yamllint + hadolint hooks are global (no files restriction) so iac-runner is covered implicitly; only validate-dockerfile-args (which has a regex file filter) needs an explicit iac-runner addition"

key-files:
  created:
    - iac-runner/internal/httpapi/handlers/version.go (handlers.Version(runnerVersion) http.HandlerFunc returning contract.VersionHandshake)
    - iac-runner/internal/httpapi/handlers/version_test.go (3 Test funcs: field presence, compile-time defaults, chi integration 401/401/200)
    - iac-runner/DOCS.md (180-line operator reference with every config option + 3 backends + every endpoint)
  modified:
    - iac-runner/internal/httpapi/router.go (r.Get(\"/version\", handlers.Version(runnerVersion)) added inside RequireBearer-wrapped /v1 subrouter before /auth/rotate)
    - iac-runner/README.md (replaced Plan 01 placeholder with user-facing intro: shields + About + Features + Install + First-time setup + Configuration link to DOCS.md)
    - .pre-commit-config.yaml (iac-runner added to validate-dockerfile-args regex `^(phone-logger|meridian|iac-runner)/Dockerfile$`; yamllint + hadolint remain global)

key-decisions:
  - "handlers.Version(runnerVersion string) constructor signature mirrors terraform-bridge's handlers.Version(bridgeVersion string) — same pattern reused across both add-ons; version constants come from internal/version package, never hardcoded in the handler"
  - "Chi integration test (TestVersionRequiresBearer) constructs a fresh chi.NewRouter + auth.RequireBearer(store) + handlers.Version() inside version_test.go itself — this avoids importing the httpapi package from the handlers package (which would cycle on handlers import); the test exercises the production wire shape end-to-end via httptest.Server + http.DefaultClient"
  - "TestVersionRequiresBearer uses t.TempDir() + auth.NewFileTokenStore + store.Persist(plaintext) to construct a TokenStore with a known hash — Persist writes the SHA-256 to disk atomically; the test then verifies the on-disk hash matches SHA-256(plaintext) before driving the HTTP layer (defensive sanity against silent test-data drift)"
  - "DOCS.md structure mirrors terraform-bridge/DOCS.md section ordering (Install → Configuration → credential files → HTTP API → state-management → log scrubbing) for consistency across add-ons; this lets operators familiar with one add-on find information in the other by analogy"
  - "README.md uses minimal shield set (release + project-stage + amd64) — no maintenance/license shields per experimental project stage; link to DOCS.md for the full operator reference (the README is intentionally terse so DOCS.md owns the long-form content)"
  - "Pre-commit config: iac-runner explicitly added only to validate-dockerfile-args regex (which has a file restriction); yamllint + hadolint hooks remain file-unrestricted so they cover iac-runner implicitly without re-listing every add-on (preserves the original hooks + adds auditability of the iac-runner Dockerfile)"

patterns-established:
  - "Markdown table compact-spacing: `| ------ | ------ | ------- |` (spaces around pipes) instead of `|------|------|-------|` (tight) — markdownlint-cli2 MD060 enforces this; future markdown files in this repo should follow this style"
  - "Markdown line length: 120-char ceiling enforced by .markdownlint.json MD013; long URLs / inline code may push past 120 — refactor by splitting the line or shortening the inline code rather than disabling MD013"
  - "state_backend prose convention: use `state_backend: \"r2\"` colon syntax (matches the acceptance grep regex), not `state_backend = \"r2\"` equals syntax — keeps DOCS.md grep-able for the plan's automated checks"

requirements-completed: [AUTHR-01, AUTHR-02, AUTHR-03, AUTHR-04, STBK-01, STBK-02, STBK-03, STBK-04, STBK-05, SEC-01, SEC-02, OBS-01]

# Metrics
duration: 5 min
completed: 2026-09-06
---

# Phase 16 Plan 03: /v1/version handler + DOCS.md + README.md + pre-commit wiring Summary

**Phase 16 SC#8 runner-version handshake endpoint (`GET /v1/version`) emitting `contract.VersionHandshake`
(runner_version + schema_version + min/max_supported_opentofu) under the RequireBearer-wrapped /v1 subrouter, complete
operator `DOCS.md`, user-facing `README.md` shields + install + first-time setup, and `.pre-commit-config.yaml` wiring
for iac-runner/Dockerfile validation.**

## Performance

- **Duration:** 5 min (2026-09-06T16:49:57Z – 2026-09-06T16:55:13Z)
- **Started:** 2026-09-06T16:49:57Z
- **Completed:** 2026-09-06T16:55:13Z
- **Tasks:** 2
- **Files modified:** 6 (3 created + 3 modified)
- **Tests added:** 3 new Test functions (TestVersionAllFieldsPresent, TestVersionUsesCompileTimeDefaults,
  TestVersionRequiresBearer with 3 subtests) → 44 total tests passing across iac-runner

## Accomplishments

- `GET /v1/version` mounted under the RequireBearer-wrapped /v1 subrouter in `iac-runner/internal/httpapi/router.go`.
  `handlers.Version(runnerVersion string)` is the http.HandlerFunc constructor — emits
  `contract.VersionHandshake{ RunnerVersion, SchemaVersion, MinSupportedOpenTofu, MaxSupportedOpenTofu }` as JSON,
  sourced from `internal/version.SchemaVersion + Min/MaxSupportedOpenTofu` constants and the `cmd/runner/version.go`
  ldflags-injected `runnerVersion` variable.
- `handlers/version_test.go` covers (a) all 4 JSON fields present + non-empty, (b) compile-time defaults from
  `internal/version` (verifies the bump policy in `internal/version/version.go` is honored), and (c) chi integration
  test: `httptest.NewServer(chi.NewRouter())` wrapping the version handler with `auth.RequireBearer(store)` — asserts
  missing/wrong/valid bearer token returns 401+unauthorized / 401+unauthorized / 200+VersionHandshake. The integration
  test uses `t.TempDir()` + `auth.NewFileTokenStore` + `store.Persist(plaintext)` to construct a TokenStore with a known
  SHA-256 hash; a sanity assertion confirms the on-disk hash matches `SHA-256(plaintext)`.
- `iac-runner/DOCS.md` (180 lines) is the operator reference: Overview → Install → First-time setup (bearer retrieval
  via `iac_runner.token.issued` log line + `/data/initial-iac-runner-token` chmod-600 file) → Configuration (every
  option with example: `bind_address`, `bind_allowed_subnets`, `state_backend`, `r2_bucket`, `s3_endpoint`, `s3_bucket`,
  `s3_region`) → State backend credential files (per-backend chmod-600 tables for r2/s3/local) → HTTP API (endpoint
  table + JSON body shapes for /healthz, /v1/auth/rotate, /v1/version) → State backend `use_lockfile` semantics (R2/S3
  use S3-object-lock, local uses file lock) → Log scrubbing (key-name mask for
  Authorization/Bearer/token/password/key/secret).
- `iac-runner/README.md` (replaced Plan 01 placeholder) is the user-facing intro: shields (v0.1.0 + experimental +
  amd64) + About (port 8125, Phase 16/17/18 roadmap) + Features (256-bit bearer auth + 3 state backends +
  `use_lockfile` + Tailscale-bind-gate + /data/keys/ chmod-600 + log scrubbing + SIGTERM drain) + Install (HA add-on
  store via akentner/homeassistant-addons repo) + First-time setup
  (`sudo ha addons logs iac-runner | grep iac_runner.token.issued`) + Configuration (link to DOCS.md).
- `.pre-commit-config.yaml` extended: `iac-runner` added to the `validate-dockerfile-args` regex
  (`^(phone-logger|meridian|iac-runner)/Dockerfile$`). The yamllint + hadolint hooks remain file-unrestricted and thus
  cover iac-runner implicitly. The explicit addition to validate-dockerfile-args makes the iac-runner Dockerfile
  coverage auditable in the config file (matches the original phone-logger + meridian pattern).
- `go build / vet / test ./...` all exit 0 (44 tests across the module: 20 Plan 01 + 21 Plan 02 + 3 Plan 03).
  `make validate-addons` exits 0 (iac-runner auto-discovered + validated alongside the 8 other add-ons).
  `npx markdownlint-cli2 iac-runner/DOCS.md iac-runner/README.md` exits 0 (0 issues).

## Task Commits

Each task was committed atomically:

1. **Task 1: GET /v1/version handler + router mount + tests** - `d151cd6` (feat)
2. **Task 2: Operator DOCS.md + README shields + pre-commit config** - `e87b296` (docs)

**Plan metadata:** `docs(16-03): complete plan` (next commit — captures SUMMARY.md + STATE.md + ROADMAP.md +
REQUIREMENTS.md updates).

## Files Created/Modified

### Created (3 files)

- `iac-runner/internal/httpapi/handlers/version.go` — `Version(runnerVersion string) http.HandlerFunc` constructor
  returning `contract.VersionHandshake{runnerVersion, schema_version, min/max_supported_opentofu}` as JSON. Imports
  `iac-runner/internal/contract` + `iac-runner/internal/version`. Package doc comment explains SC#8 + RequireBearer
  mounting. Slog-free per the existing handler invariant (no slog calls).
- `iac-runner/internal/httpapi/handlers/version_test.go` — 3 Test functions:
  - `TestVersionAllFieldsPresent`: status=200, Content-Type=application/json, all 4 fields non-empty
  - `TestVersionUsesCompileTimeDefaults`: confirms SchemaVersion + Min/MaxSupportedOpenTofu match `internal/version`
    constants (not hardcoded literals)
  - `TestVersionRequiresBearer`: chi integration test with 3 subtests (missing header / wrong token / valid token)
    asserting 401+unauthorized / 401+unauthorized / 200+JSON via `httptest.NewServer` + `http.DefaultClient`
- `iac-runner/DOCS.md` — 180-line operator reference. Sections: Overview → Install → First-time setup → Configuration
  (bind_address, bind_allowed_subnets, state_backend with all 3 values r2/s3/local, r2_bucket, s3_endpoint, s3_bucket,
  s3_region) → State backend credential files (per-backend chmod-600 tables) → HTTP API table + curl + JSON body shapes
  for /healthz, /v1/auth/rotate, /v1/version → use_lockfile semantics (R2/S3 + file lock for local) → Log scrubbing
  invariant.

### Modified (3 files)

- `iac-runner/internal/httpapi/router.go` — Added `r.Get("/version", handlers.Version(runnerVersion))` inside the
  RequireBearer-wrapped `/v1` subrouter, before the `r.Post("/auth/rotate", ...)` mount. Package doc comment updated to
  list the new endpoint.
- `iac-runner/README.md` — Replaced Plan 01 placeholder (which referenced DOCS.md as "written in Plan 03") with the full
  user-facing intro: shields + About + Features + Install + First-time setup + Configuration link to DOCS.md. 3 shields:
  release (v0.1.0), project-stage (experimental), amd64.
- `.pre-commit-config.yaml` — `iac-runner` appended to the `validate-dockerfile-args` hook's
  `files: ^(phone-logger|meridian|iac-runner)/Dockerfile$` regex. The yamllint + hadolint hooks remain file-unrestricted
  (global) so they cover iac-runner implicitly without modifying the original hook entries.

## Decisions Made

- **`handlers.Version(runnerVersion string)` constructor signature mirrors terraform-bridge's pattern** — same signature
  shape across both add-ons lets operators / consumers expect a uniform contract for the `/v1/version` surface. Internal
  constants come from the `internal/version` package so the bump policy in `internal/version/version.go` is honored
  (Plan 02's `SEC-02 scrubber` precedent: cross-package constant enforcement beats hardcoded literals).
- **Chi integration test (TestVersionRequiresBearer) constructed inside the `handlers` package itself** — avoids
  importing `httpapi` from `handlers` (which would cycle on the `handlers` import). The test exercises the same chi
  router shape as `httpapi.NewRouter` but stays local to the handlers package. Uses `t.TempDir()` +
  `auth.NewFileTokenStore` + `store.Persist(plaintext)` for a self-contained TokenStore; the on-disk hash is
  sanity-checked against `SHA-256(plaintext)` so a test-data drift surfaces as a clear failure rather than a silent
  chi 401.
- **DOCS.md structure mirrors terraform-bridge/DOCS.md** — same section ordering (Install → Configuration → credential
  files → HTTP API → state-management → log scrubbing) for consistency across the two add-ons. Operators familiar with
  one add-on can navigate the other by analogy. The `use_lockfile` and `/data/keys/` sections are iac-runner-specific
  (terraform-bridge uses Supervisor for state).
- **README.md uses minimal shield set** — 3 shields (release, project-stage, amd64), no maintenance/license shields. The
  README is intentionally terse (~50 lines) so DOCS.md owns the long-form operator reference. This matches the
  experimental project stage signaled by the project-stage shield.
- **Pre-commit config: iac-runner added ONLY to `validate-dockerfile-args`** — the `validate-dockerfile-args` hook has a
  regex file filter that explicitly enumerates add-ons; the `yamllint` + `hadolint` hooks are global with no file
  restriction and thus cover iac-runner implicitly. This is the minimal touch that satisfies the plan's acceptance
  criterion (`grep -cE 'iac-runner' .pre-commit-config.yaml` >= 1) without modifying the original hook entries (per MUST
  NOT DO item 5: "DO NOT modify other add-ons' pre-commit config entries — append iac-runner paths only").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added chi integration test (TestVersionRequiresBearer) for the 401 path beyond the plan's verbatim
template**

- **Found during:** Task 1 verification (`go test ./internal/httpapi/handlers/...`)
- **Issue:** The plan's verbatim `version_test.go` template included two Test functions (`TestVersionAllFieldsPresent` +
  `TestVersionUsesCompileTimeDefaults`) that exercise the handler in isolation (without auth middleware). The plan's
  MUST DO item 2 explicitly required "Also assert 401 when no token (via a chi test server)" — the verbatim template did
  NOT cover that case. The chi integration test was a gap between the MUST DO requirement and the plan's code template.
- **Fix:** Added `TestVersionRequiresBearer` that constructs
  `chi.NewRouter() + auth.RequireBearer(store) + handlers.Version()`, spins up `httptest.NewServer`, and runs a 3-case
  table-driven test (missing header / wrong token / valid token) asserting the exact 401+unauthorized / 401+unauthorized
  / 200+JSON contract per AUTHR-04. TokenStore is built with
  `t.TempDir() + auth.NewFileTokenStore + store.Persist(plaintext)` — a sanity assertion confirms the on-disk SHA-256
  hash matches `SHA-256(plaintext)` so a test-data drift surfaces as a clear failure.
- **Files modified:** `iac-runner/internal/httpapi/handlers/version_test.go`
- **Verification:** `go test ./internal/httpapi/handlers/...` passes (3 Test functions: AllFieldsPresent,
  UsesCompileTimeDefaults, RequiresBearer with 3 subtests). The chi integration test proves the RequireBearer-wrapped
  mount is wired correctly per AUTHR-04.
- **Committed in:** `d151cd6` (Task 1 — `feat(16-03): GET /v1/version handler with auth + tests` — amended after initial
  commit to include the chi test)

**2. [Rule 1 - Bug] DOCS.md initial draft had `state_backend = "r2"` equals syntax which fails the plan's acceptance
grep `state_backend:\s*"r2"` colon syntax**

- **Found during:** Task 2 verification (acceptance grep audit)
- **Issue:** The plan's acceptance grep uses `state_backend:\s*"r2"` colon syntax (YAML), but the plan's own `<action>`
  template used `state_backend = "r2"` equals syntax (key-value) in the bullet points. My initial draft followed the
  action template's equals syntax; the acceptance grep returned 0 matches for all 3 values.
- **Fix:** Updated the `state_backend` bullet points + `r2_bucket` + `s3_endpoint` etc. sections to use colon syntax:
  `state_backend: "r2"` instead of `state_backend = "r2"`. The fix preserves the YAML-stylized form so the DOCS.md is
  grep-able for downstream automation while still being valid Markdown prose.
- **Files modified:** `iac-runner/DOCS.md`
- **Verification:** `grep -cE 'state_backend:\s*"r2"|state_backend:\s*"s3"|state_backend:\s*"local"' iac-runner/DOCS.md`
  returns 5 (3 bullet values + `r2_bucket` + `s3_endpoint` references); markdownlint-cli2 exits 0.
- **Committed in:** `e87b296` (Task 2 — `docs(16-03): operator DOCS.md + README shields + pre-commit wiring`)

**3. [Rule 1 - Bug] DOCS.md initial draft had 3 lines > 120 chars (line_length ceiling per .markdownlint.json MD013)**

- **Found during:** Task 2 verification (`awk 'length > 120'` audit before markdownlint-cli2 run)
- **Issue:** Three lines were 121/124/125 chars long, exceeding the 120-char ceiling enforced by `.markdownlint.json`
  (`MD013: line_length: 120`). Two were paragraph lines (`endpoint as...` and the `/healthz` table row) and one was an
  inline-code span that pushed past 120 chars.
- **Fix:** Split the long paragraph line into 2 lines by moving `where <account_id> is read from` onto a continuation
  line; shortened the `/healthz` table cell description from "200 + JSON when tofu on PATH AND `/data/keys/` chmod-600
  passes; 503 + empty body otherwise" to "200 + JSON when tofu on PATH AND `/data/keys/` chmod-600 passes; 503 empty
  body otherwise" (4-char saving); replaced the `/v1/version` table cell with a shorter description ("Returns runner +
  schema + min/max supported OpenTofu versions") that fits within 120 chars.
- **Files modified:** `iac-runner/DOCS.md`
- **Verification:** `awk 'length > 120' iac-runner/DOCS.md iac-runner/README.md` returns no output (all lines <= 120
  chars). `npx markdownlint-cli2 iac-runner/DOCS.md iac-runner/README.md` exits 0 (0 issues).
- **Committed in:** `e87b296` (Task 2)

**4. [Rule 1 - Bug] DOCS.md initial draft had MD060 table-column-style violations (pipes missing spaces)**

- **Found during:** Task 2 verification (`npx markdownlint-cli2 iac-runner/DOCS.md`)
- **Issue:** Tables used tight pipe syntax (`|------|------|-------|`) without spaces around the `|` characters.
  markdownlint-cli2's MD060 rule enforces the "compact" or "aligned" table style; the tight syntax triggers errors for
  "Table pipe is missing space to the right/left" and "Table pipe does not align with header".
- **Fix:** Updated all tables in DOCS.md to use compact-with-spaces syntax: `| ------ | ------ | ------- |` (spaces
  around pipes). All cells (headers + separator + body rows) follow the same pattern. The markdownlint config does not
  enable `MD013 line_length` for tables (`tables: false`) so the wider separators do not trigger line-length warnings.
- **Files modified:** `iac-runner/DOCS.md` (3 tables: R2 backend required files, S3 backend required files, HTTP API
  endpoint table)
- **Verification:** `npx markdownlint-cli2 iac-runner/DOCS.md iac-runner/README.md` exits 0 (0 issues).
- **Committed in:** `e87b296` (Task 2)

---

**Total deviations:** 4 auto-fixed (all Rule 1 — bug fixes for spec/code mismatches discovered during verification; all
narrowly scoped to existing or new task content). **Impact on plan:** All auto-fixes were necessary to satisfy the
plan's own acceptance criteria and the project's markdownlint / line-length conventions. No scope creep. The chi
integration test is the most substantive addition (proves the AUTHR-04 mount invariant end-to-end); the DOCS.md
formatting fixes are mechanical corrections.

## Issues Encountered

None beyond the four deviations above. The plan's templates for production code (handlers/version.go + router.go edit)
were followed exactly: the version handler mirrors terraform-bridge's handler with the `terraform-bridge/contract` →
`iac-runner/internal/contract` and `terraform-bridge/internal/version` → `iac-runner/internal/version` import paths
swapped; the router edit is a one-line addition (`r.Get("/version", handlers.Version(runnerVersion))`) inside the
existing RequireBearer-wrapped /v1 subrouter.

The Go binary is at `/tmp/opencode/go-install/go/bin/go` (not on `$PATH`); the build/test invocations use the explicit
PATH prefix `export PATH="/tmp/opencode/go-install/go/bin:$PATH"` so the executor can run on hosts where Go is not
installed system-wide. This is environment-specific to the executor; the iac-runner go.mod still uses the standard
`go 1.25` directive and works with any Go 1.25+ toolchain.

## User Setup Required

None — no external service configuration required at this phase. Phase 16 is now complete end-to-end: bearer auth
(AUTHR-01..04) + state backends (STBK-01..05) + secrets handling (SEC-01..02) + observability (OBS-01) all delivered
with full test coverage + operator documentation.

Live-HA empirical verification (token issuance + rotation + bind gate + /healthz + /v1/version against a real HA host
with tofu installed + chmod-600-validated keys + a real Tailscale interface) is deferred to Phase 19 per the established
pattern (each phase defers empirical exercise to the E2E phase).

## Next Phase Readiness

- **Phase 16 closure:** all 12 Phase 16 requirements (AUTHR-01..04 + STBK-01..05 + SEC-01..02 + OBS-01) are satisfied
  end-to-end with full test coverage (44 tests across the module) and complete operator documentation (DOCS.md +
  README.md + .pre-commit-config.yaml wiring).
- **Phase 17 (Git Integration + Apply Job System) is slottable:** Plan 17 will consume
  `statebackend.Backend.Endpoint() + Bucket() + Region() + UseLockfile()` to construct `tofu init -backend-config=…`
  command lines. The `/v1/version` endpoint can be used by client capability negotiation (Phase 17 clients may check
  `min_supported_opentofu` before sending a `tofu plan` request to ensure compatibility).
- **Phase 18 (MQTT Discovery + HA Sensors + Buttons) is slottable:** Phase 18 will surface `/healthz` + `/v1/version`
  status to HA entities. The DOCS.md is the install reference for operators deploying the Phase 18 MQTT Discovery
  wiring.
- **Live-HA empirical verification** (token issuance + rotation + bind gate + /healthz + /v1/version against a real HA
  host) is deferred to Phase 19 (E2E Verification + Operator Runbook) per the established pattern.

---

_Phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck_ _Completed: 2026-09-06_

## Self-Check: PASSED

- `iac-runner/internal/httpapi/handlers/version.go` exists, non-empty
- `iac-runner/internal/httpapi/handlers/version_test.go` exists, non-empty (3 Test functions + 3 subtests)
- `iac-runner/internal/httpapi/router.go` mounted `/v1/version` under RequireBearer-wrapped /v1 subrouter
- `iac-runner/DOCS.md` exists, non-empty (180 lines)
- `iac-runner/README.md` exists, non-empty (replaced Plan 01 placeholder with shields + intro)
- `.pre-commit-config.yaml` contains `iac-runner` (1 occurrence in `validate-dockerfile-args` regex)
- `cd iac-runner && go build ./...` exits 0
- `cd iac-runner && go vet ./...` exits 0
- `cd iac-runner && go test ./...` passes (44 tests: 20 Plan 01 + 21 Plan 02 + 3 Plan 03)
- `python3 internal/validate-addon-config.py iac-runner` exits 0
- `make validate-addons` exits 0 (iac-runner auto-discovered + validated)
- `npx markdownlint-cli2 iac-runner/DOCS.md iac-runner/README.md` exits 0 (0 issues)
- `awk 'length > 120' iac-runner/DOCS.md iac-runner/README.md` returns no output (all lines ≤ 120 chars)
- Plan acceptance greps all pass (verify bash snippets from PLAN.md `<verify>` blocks)
- `git log --oneline --grep="16-03"` returns 3 commits (2 task commits + this docs metadata commit)
- Root `README.md` `iac-runner` entry present (from Plan 01, verified by `grep -cE 'iac-runner' README.md` = 2)
- Phase 16 plan 03 marked complete (3/3) in `.planning/STATE.md` and ROADMAP updated
- All 12 Phase 16 requirements (AUTHR-01..04 + STBK-01..05 + SEC-01..02 + OBS-01) marked `[x]` complete in
  `.planning/REQUIREMENTS.md`
- `.planning/phases/16-iac-runner-scaffold-auth-state-backends-healthcheck/16-03-SUMMARY.md` exists with all required
  frontmatter fields (phase, plan, subsystem, tags, requires, provides, affects, tech-stack, key-files, key-decisions,
  patterns-established, requirements-completed, duration, completed)
