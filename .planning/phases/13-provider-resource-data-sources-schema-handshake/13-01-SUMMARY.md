---
phase: 13-provider-resource-data-sources-schema-handshake
plan: 01
subsystem: provider
tags: [terraform-plugin-framework, terraform-provider, bridge-integration, diagnostics, go]

# Dependency graph
requires:
  - phase: 12-bridge-write-api-safety-concurrency-index
    provides:
      "GET /v1/version, GET /v1/addons/{slug}/info, contract.VersionHandshake + contract.AddOnInfo +
      contract.ErrorResponse + contract.BridgeInfo types"
provides:
  - "terraform-provider-homeassistant Go module compiles + serves via providerserver.Serve at
    registry.terraform.io/akentner/homeassistant (PROV-01)"
  - "Provider.Configure calls Bridge GET /v1/version, enforces [min_provider_version, max_provider_version] window
    (PROV-03)"
  - "internal/client.Client mirrors Bridge's supervisor.Client (CF-16): bearer-token-injecting RoundTripper, body-drain
    on non-200, ErrAddonNotFound sentinel, BridgeError type wrapping non-200 contract.ErrorResponse"
  - "internal/diagnostics.MapError translates every Bridge error_code into typed Provider Diagnostic with per-error-code
    Summary (D-08), Detail carrying request_id (D-11), DOCS.md anchor URL (D-10); severity Error per D-09"
  - "internal/resource/homeassistant_addon Resource implements Read (calls /v1/addons/{slug}/info, returns empty state
    on 404 per CF-06), ImportStatePassthroughID accepting {slug} or {repository}/{slug} per PROV-08/CF-05,
    UseStateForUnknown() on `state` Computed attribute per PROV-10"
  - "internal/datasource thin stubs for homeassistant_addon (PROV-11) + homeassistant_supervisor_info (PROV-12)"
  - "Create / Update / Delete are explicit stubs returning not_implemented Diagnostic so Plan 02 can fill them without
    re-touching go.mod"
affects:
  - phase: 13-provider-resource-data-sources-schema-handshake
    context: "Plans 02 (CRUD + timeouts + pwned warning) and 03 (data sources + DOCS.md) build on this foundation"
  - phase: 14-real-ha-end-to-end-verification
    context: "End-to-end empirical verification (tofu init/plan/apply/destroy) against live Bridge"

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 74000 # chars/4 over files actually changed
  tasks: 1
  commits: 1

# Tech tracking
tech-stack:
  added:
    - terraform-plugin-framework-timeouts v0.5.0
  patterns:
    - "Bearer-injecting http.RoundTripper (CF-16 + PITFALLS S-1) — token never appears in error messages"
    - "Body-drain on non-200 BEFORE JSON decode (Phase 11 Rule-1 fix)"
    - "errors.Is sentinel pattern for 404 translation (CF-06 idempotency)"
    - "Provider.Configure stashes configured *client.Client in resp.ResourceData (framework's per-Resource handoff)"
    - "tfsdk.Config built directly from tftypes.Object for unit tests (avoids heavier terraform-plugin-testing acctest
      dep)"

key-files:
  created:
    - terraform-provider-homeassistant/internal/client/client.go
    - terraform-provider-homeassistant/internal/client/client_test.go
    - terraform-provider-homeassistant/internal/diagnostics/doc.go
    - terraform-provider-homeassistant/internal/diagnostics/map_error.go
    - terraform-provider-homeassistant/internal/diagnostics/map_error_test.go
    - terraform-provider-homeassistant/internal/provider/provider.go
    - terraform-provider-homeassistant/internal/provider/provider_test.go
    - terraform-provider-homeassistant/internal/provider/version.go
    - terraform-provider-homeassistant/internal/resource/attr_helpers.go
    - terraform-provider-homeassistant/internal/resource/homeassistant_addon.go
    - terraform-provider-homeassistant/internal/resource/homeassistant_addon_test.go
    - terraform-provider-homeassistant/internal/datasource/homeassistant_addon.go
    - terraform-provider-homeassistant/internal/datasource/homeassistant_supervisor_info.go
  modified:
    - terraform-provider-homeassistant/main.go
    - terraform-provider-homeassistant/go.mod
    - terraform-provider-homeassistant/go.sum

key-decisions:
  - "Timeouts Block declared in Resource schema (not lazy-imported) so Plan 02 fills timeout enforcement without
    re-touching go.mod"
  - "Provider Configure checks both Provider.version vs Bridge.min_provider_version (too-old) AND Bridge.schema_version
    vs Bridge.max_provider_version (too-new) per PROV-03 acceptance criteria"
  - "DataSource stubs live in internal/datasource/ (not inline in provider.go) to match the idiomatic framework layout +
    keep provider.go focused on Provider wiring"
  - "BridgeError decoded after body read (not before drain) — Phase 11 Rule-1 fix applied to Provider side"
  - "NewClient validates non-empty bearer_token early — RoundTrip rejects empty tokens defensively, but early validation
    surfaces a clear error at the right boundary"
  - "AddonResource type exported (was addonResource in draft) so tests can drive ResourceWithImportState +
    ResourceWithConfigure methods directly without type assertions"

patterns-established:
  - "Each new internal package carries a doc.go (package-level architecture comments) + its concrete implementation"
  - "Tests construct tfsdk.Config directly from tftypes.Object — avoids terraform-plugin-testing acctest dep at Plan 01
    scope"
  - "Error diagnostic with severity Error + canonical per-code Summary + Detail carrying request_id + DOCS.md anchor URL
    — D-08 + D-09 + D-10 + D-11 combined into one Detail string until the framework's Diagnostic type gains a Link field
    (deferred)"
  - "http.Client.Timeout + Transport-bound bearer token — tokenInjectingTransport struct shared across
    WithBaseURLForTest copy"
  - "Resource stubs use literal `not_implemented` Summary so verifier + Plan 02 grep is deterministic"

requirements-completed:
  - PROV-01
  - PROV-03
  - PROV-04
  - PROV-08
  - PROV-10
  - LIFE-04

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "Provider compiles + serves via providerserver.Serve at registry.terraform.io/akentner/homeassistant"
    requirement: PROV-01
    verification:
      - kind: automated
        ref: "go build ./... exits 0 (terraform-provider-homeassistant)"
        status: pass
      - kind: automated
        ref: "main.go:grep providerserver\\.Serve"
        status: pass
      - kind: automated
        ref: "main.go:grep newProvider"
        status: pass
    human_judgment: false
  - id: D2
    description: "Provider Configure calls Bridge GET /v1/version + enforces version window"
    requirement: PROV-03
    verification:
      - kind: automated
        ref: "TestProvider_Configure_Success (provider_test.go)"
        status: pass
      - kind: automated
        ref: "TestProvider_Configure_VersionBelowMin"
        status: pass
      - kind: automated
        ref: "TestProvider_Configure_VersionAboveMax"
        status: pass
      - kind: automated
        ref: "TestProvider_Configure_ClientConstructionFailure"
        status: pass
    human_judgment: false
  - id: D3
    description:
      "Resource Read calls /v1/addons/{slug}/info, returns empty state on 404, MapError diagnostics on other errors"
    requirement: PROV-04
    verification:
      - kind: automated
        ref: "TestResourceRead_Success (resource_test.go)"
        status: pass
      - kind: automated
        ref: "TestResourceRead_NotFoundReturnsEmpty"
        status: pass
      - kind: automated
        ref: "TestResourceRead_OtherErrorReturnsDiagnostic"
        status: pass
    human_judgment: false
  - id: D4
    description: "ImportState accepts {slug} (defaults repository=core) or {repository}/{slug}"
    requirement: PROV-08
    verification:
      - kind: automated
        ref: "TestResourceImport_PassthroughSingleSlug"
        status: pass
      - kind: automated
        ref: "TestResourceImport_PassthroughRepoSlashSlug"
        status: pass
      - kind: automated
        ref: "TestResourceImport_EmptyID + EmptySlugAfterSplit"
        status: pass
    human_judgment: false
  - id: D5
    description: "UseStateForUnknown plan modifier on state Computed attribute"
    requirement: PROV-10
    verification:
      - kind: automated
        ref: "TestResourceSchema_StateUsesUseStateForUnknown"
        status: pass
    human_judgment: false
  - id: D6
    description: "Typed diagnostics per Bridge error_code (LIFE-04 foundation): D-08 + D-09 + D-10 + D-11"
    requirement: LIFE-04
    verification:
      - kind: automated
        ref:
          "TestMapError_KnownCodes (10 codes: unauthorized, not_found, critical_addon_protected, prevented_destroy,
          already_installed, locked, nonce_expired, nonce_used, install_timeout, upstream_error)"
        status: pass
      - kind: automated
        ref: "TestMapError_UnknownCode (defensive fallback)"
        status: pass
      - kind: automated
        ref: "TestMapError_NilReturnsNil + NonBridgeError + WrappedBridgeError"
        status: pass
    human_judgment: false
  - id: D7
    description: "PITFALLS S-1 bearer-token-never-leaks across all Client + Provider error paths"
    requirement: LIFE-04
    verification:
      - kind: automated
        ref: "TestClient_BearerTokenNotInErrorMessage (4 scenarios: 401, 404, 502, malformed JSON)"
        status: pass
      - kind: automated
        ref:
          "TestProvider_Configure_BearerTokenNotInDiagnostic (3 scenarios: version_above_max, version_below_min,
          bad_url)"
        status: pass
    human_judgment: false
  - id: D8
    description: "Bridge regression check — Phase 11 + 12 tests still green"
    requirement: null
    verification:
      - kind: automated
        ref: "cd terraform-bridge && go test -count=1 -race ./..."
        status: pass
    human_judgment: false

# Metrics
duration: ~38min
completed: 2026-09-04
status: complete
---

# Phase 13 Plan 01: Provider + Resource + Data Sources + Schema Handshake Summary

**Tracer-level Provider scaffold: package layout, bearer-injecting Client, Configure handshake via /v1/version, typed
MapError diagnostics, Read-only homeassistant_addon Resource, two stub data sources — all building green against the
existing Bridge contract.**

## Performance

- **Duration:** ~38 min
- **Started:** 2026-09-04T19:25Z
- **Completed:** 2026-09-04T20:03Z
- **Tasks:** 1
- **Files modified:** 13 new + 2 modified (main.go, go.mod) — 1 atomic commit
- **Tests:** 39 across 4 *_test.go files (>=22 required)

## Accomplishments

- **Provider compiles + serves via providerserver.Serve** at `registry.terraform.io/akentner/homeassistant` (PROV-01);
  Phase 9 stub fully replaced.
- **Configure handshake**: GET /v1/version → window check on Provider.version vs Bridge.min_provider_version (too-old)
  AND Bridge.schema_version vs Bridge.max_provider_version (too-new) per PROV-03 + CF-02; typed Error diagnostics on
  failure.
- **internal/client.Client** mirrors Bridge's supervisor.Client verbatim (CF-16): `tokenInjectingTransport` for Bearer
  injection, `NewRequestWithContext` per call, `drainBody` AFTER status check (Phase 11 Rule-1), `BridgeError` wrapping
  non-200 `contract.ErrorResponse`, `ErrAddonNotFound` sentinel on 404. `TestClient_BearerTokenNotInErrorMessage` is the
  PITFALLS S-1 + T-13-04 regression guard.
- **internal/diagnostics.MapError** translates every Bridge `error_code` into typed Provider Diagnostic with severity
  Error (D-09), canonical per-code Summary from `doc.go` (D-08), Detail carrying `request_id: <id>` (D-11) + DOCS.md
  anchor URL (D-10). Defensive fallback for unknown codes.
- **internal/resource/homeassistant_addon** Resource: Schema declares slug (Required, RequiresReplace), repository
  (default "core"), options, start, boot, Computed version/state/started/hostname + per-operation timeouts Block
  (PROV-09); Read calls `Client.GetAddonInfo` and returns empty state on 404 (CF-06); ImportState accepts `{slug}` or
  `{repository}/{slug}` (PROV-08/CF-05); `state` Computed carries `UseStateForUnknown()` (PROV-10/CF-04);
  Create/Update/Delete return typed `not_implemented` stubs for Plan 02.
- **internal/datasource** stubs for `homeassistant_addon` (PROV-11) + `homeassistant_supervisor_info` (PROV-12) — thin
  enough for Plan 03 to fill in.
- **No Bridge source changes** — Provider consumes the existing /v1/version + /v1/addons/{slug}/info endpoints from
  Phases 11+12 unchanged.

## Task Commits

1. **Task 1 (tracer):** `a0ca39a` feat(13-01): Provider scaffolding + Client + Configure + MapError + Read-only Resource
   stub (16 files, +2965/-40)

## Files Created/Modified

### Created (13 files)

- `terraform-provider-homeassistant/internal/client/client.go` — bearer-injecting HTTP client (CF-16 mirror); 339 lines
- `terraform-provider-homeassistant/internal/client/client_test.go` — 12 httptest-based tests; 420 lines
- `terraform-provider-homeassistant/internal/diagnostics/doc.go` — 10 per-error-code constants + DocAnchor helper
  (D-08 + D-10); 125 lines
- `terraform-provider-homeassistant/internal/diagnostics/map_error.go` — typed Diagnostic switch (D-08..D-11); 134 lines
- `terraform-provider-homeassistant/internal/diagnostics/map_error_test.go` — table-driven 5 tests; 252 lines
- `terraform-provider-homeassistant/internal/provider/provider.go` — Provider type with
  Metadata/Schema/Configure/Resources/DataSources (PROV-01); 222 lines
- `terraform-provider-homeassistant/internal/provider/provider_test.go` — 10 tests; 351 lines
- `terraform-provider-homeassistant/internal/provider/version.go` — semverLess/semverGreater helpers (PROV-03 window
  check); 81 lines
- `terraform-provider-homeassistant/internal/resource/attr_helpers.go` — timeoutsBlock() helper; 34 lines
- `terraform-provider-homeassistant/internal/resource/homeassistant_addon.go` — AddonResource with Read + Import +
  not_implemented stubs; 326 lines
- `terraform-provider-homeassistant/internal/resource/homeassistant_addon_test.go` — 12 tests; 533 lines
- `terraform-provider-homeassistant/internal/datasource/homeassistant_addon.go` — stub (PROV-11); 72 lines
- `terraform-provider-homeassistant/internal/datasource/homeassistant_supervisor_info.go` — stub (PROV-12); 46 lines

### Modified (3 files)

- `terraform-provider-homeassistant/main.go` — providerserver.Serve with `newProvider()` constructor (PROV-01)
- `terraform-provider-homeassistant/go.mod` — adds `terraform-plugin-framework-timeouts v0.5.0` (PROV-09)
- `terraform-provider-homeassistant/go.sum` — regenerated

## Decisions Made

- **Timeouts Block declared in Resource schema** (not just imported) so `go mod tidy` keeps the timeouts dep alive in
  this plan; Plan 02 fills in the actual timeout enforcement without re-touching go.mod.
- **Configure version-check uses both halves** of the acceptance-criteria shape: Provider.version vs
  Bridge.min_provider_version (too-old → "too old" diagnostic) AND Bridge.schema_version vs Bridge.max_provider_version
  (too-new → "too new" diagnostic). Both checks live in the Configure branch with explicit Summary text per branch.
- **BridgeError decoded AFTER body read** (not before drain) — the earlier "drain then read" order silently dropped the
  body. Phase 11 Rule-1 fix applied to Provider side; `drainBody` is now only called on connection-reuse paths.
- **DataSource stubs in `internal/datasource/`** (not inline in provider.go) — matches the framework's idiomatic package
  layout + keeps provider.go focused on the Provider wiring + Configure handshake. The plan's `files_modified`
  frontmatter did not list these files; this is a minor agent's-discretion addition (CONTEXT §the agent's Discretion
  §"Exact internal package layout inside `terraform-provider-homeassistant/`").
- **`AddonResource` exported** (was lowercase in the original draft) so the test file can drive
  `ResourceWithImportState.ImportState` + `ResourceWithConfigure.Configure` directly. Production callers
  (Provider.Resources) still wrap the value as the `resource.Resource` interface, so export adds no surface area beyond
  tests.
- **`TestProvider_Configure_BearerTokenNotInDiagnostic`** added beyond the plan's specified 7 tests — closes the
  PITFALLS S-1 + T-13-04 invariant at the Provider Configure layer (the plan only mandated it at the Client layer).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed `var _ contract.VersionHandshake` from main.go**

- **Found during:** Task 1 implementation
- **Issue:** Plan said to "replace" the Phase 9 drift-detection reference with actual contract usage in provider.go, but
  the plan's main.go rewrite did not explicitly remove the line. Leaving it in would mean `contract` was no longer
  imported in main.go, causing an unused-import build failure.
- **Fix:** Removed the line; the `replace terraform-bridge => ../terraform-bridge` directive's drift-detection now fires
  through the real `contract.VersionHandshake` consumption in `internal/provider/provider.go` (via `Client.GetVersion`)
  and `internal/client/client.go` (via the four typed method decoders).
- **Files modified:** terraform-provider-homeassistant/main.go

**2. [Rule 1 - Bug] `decodeError` drained body BEFORE reading it**

- **Found during:** Task 1 — `TestClient_GetVersion_Unauthorized` failed with `Err.ErrorCode = ""`
- **Issue:** `drainBody(resp)` consumed the body via `io.Copy`, then the subsequent `io.ReadAll(resp.Body)` returned an
  empty buffer — so the JSON decode saw `""` for every field. Phase 11 Rule-1 fix was applied backwards on the Provider
  side.
- **Fix:** Reordered `decodeError` to `io.ReadAll` first, then `drainBody` for connection-reuse.
- **Files modified:** terraform-provider-homeassistant/internal/client/client.go
- **Verification:** TestClient_GetVersion_Unauthorized now asserts Err.ErrorCode="unauthorized" +
  Err.RequestID="rid-401" successfully.

**3. [Rule 2 - Missing Critical] `NewClient` validates non-empty bearer_token early**

- **Found during:** Task 1 — `TestClient_EmptyBearerRejected` failed (returned nil error instead of validation error)
- **Issue:** Plan said RoundTrip rejects empty tokens, but a missing bearer at NewClient time surfaces a confusing panic
  later instead of a clean validation error at the right boundary.
- **Fix:** Added explicit `if bearerToken == "" { return nil, error }` after the host validation in NewClient.
- **Files modified:** terraform-provider-homeassistant/internal/client/client.go
- **Verification:** TestClient_EmptyBearerRejected passes; production users get a clear error at provider-configuration
  time.

**4. [Rule 3 - Blocking] Added `timeouts.Value` field to `addonResourceModel` struct**

- **Found during:** Task 1 — Resource tests failed with "Object defines fields not found in struct: timeouts"
- **Issue:** Plan declared the timeouts Block in the Resource schema (to keep the dep alive) but the addonResourceModel
  struct did not have a corresponding field — the framework rejects struct targets that are missing schema fields.
- **Fix:** Added `Timeouts timeouts.Value` field to addonResourceModel with the matching tfsdk tag.
- **Files modified:** terraform-provider-homeassistant/internal/resource/homeassistant_addon.go
- **Verification:** Resource tests pass; the field is currently unused (Plan 02 fills in the timeout enforcement).

**5. [Rule 2 - Missing Critical] Tests construct `tfsdk.Config` directly from `tftypes.Object`**

- **Found during:** Task 1 — provider_test.go Configure tests needed `tfsdk.Config.Set(ctx, map)` which doesn't exist
- **Issue:** The cleanest unit-test path for Configure is to build the `tftypes.Value` for the Config directly, avoiding
  the heavier `terraform-plugin-testing` `acctest` dependency that Plan 01 doesn't otherwise need.
- **Fix:** Added a `buildConfig(t, schema, endpoint, bearerToken)` helper that constructs `tftypes.Object` +
  `tftypes.NewValue` for each test. Same approach for Resource tests (`buildState`, `addonModelType`).
- **Files modified:** terraform-provider-homeassistant/internal/provider/provider_test.go,
  terraform-provider-homeassistant/internal/resource/homeassistant_addon_test.go
- **Verification:** Configure + Read + ImportState tests pass.

---

**Total deviations:** 5 auto-fixed (1 blocking, 3 missing-critical, 1 bug) — all necessary for compilation, correctness,
or to honor acceptance-criteria invariants. **Impact:** No scope creep; all deviations are corrections to the plan's
literal implementation rather than changes to its intent.

## Issues Encountered

None — all issues resolved as auto-fixed deviations above.

## Verification Results

```
go build ./... → ok
go vet ./... → ok
go test -count=1 -race ./... → all packages green:
  terraform-provider-homeassistant/internal/client      (12 tests)
  terraform-provider-homeassistant/internal/diagnostics (5 tests)
  terraform-provider-homeassistant/internal/provider    (10 tests)
  terraform-provider-homeassistant/internal/resource    (12 tests)

gofmt -l . → empty (Provider tree fully formatted)

Bridge regression:
  cd terraform-bridge && go test -count=1 -race ./... → all green

Negative-assertion greps:
  ! grep 'var _ contract.VersionHandshake' main.go → 0 matches (Phase 9 stub replaced)
  TestClient_BearerTokenNotInErrorMessage → guards bearer-never-leaks invariant
  TestProvider_Configure_BearerTokenNotInDiagnostic → guards bearer-never-leaks at Provider layer
```

## Next Phase Readiness

**Phase 13 Plan 02 ready to begin.** Provider scaffolding compiled, Resource.Read works end-to-end against an httptest
server mocking the Bridge contract, Configure-time handshake enforced. Plan 02 expands the Resource to full CRUD:

- **Create** — adoption-aware flow per D-04..D-06 (GET info first, fall through to install, follow up with start)
- **Update** — options via /v1/addons/{slug}/options + `pwned` Warning diagnostic per CF-08 + D-09
- **Delete** — X-Force-Destroy nonce guard per CF-09 + LIFE-03
- **Timeouts enforcement** — read from the `Timeouts` field that Plan 01 wired into the schema and `addonResourceModel`

No blockers for Plan 02. The `not_implemented` Summary literal in Create/Update/Delete stubs is grep-deterministic so
Plan 02 can grep for these stubs to confirm its expansion replaces every Plan 01 placeholder.

---

_Phase: 13-provider-resource-data-sources-schema-handshake_ _Completed: 2026-09-04_
