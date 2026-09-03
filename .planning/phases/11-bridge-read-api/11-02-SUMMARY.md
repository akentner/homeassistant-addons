---
phase: 11-bridge-read-api
plan: 02
subsystem: bridge-read-api
tags: [go, chi, supervisor-api, v1-v2-fallback, bearer-token, slog, addon-discovery]

# Dependency graph
requires:
  - phase: 11-bridge-read-api
    plan: 01
    provides:
      - supervisor.Client.GetSupervisorInfo(ctx) (Plan 01) — extended with ListAddons + GetAddonInfo + ErrNotFound following the same pattern in this plan
      - supervisor.testing.go: WithBaseURLForTest + TokenFnForTest — reused by new handler tests in package handlers
      - contract.AddOnInfo struct (Phase 9 skeletal) — handler passes it through verbatim after supervisor-side normalization
      - contract.ErrorResponse struct (Phase 9) — reused with bare {error_code: "..."}, no message on BRIDGE-03 404 path
      - NewRouter(bridgeVersion, store, supClient, startTime, stateFilePath) signature (Plan 01) — unchanged in this plan; only ADDS two route mounts inside the existing /v1 auth subrouter
      - chi route group r.Route("/v1", func(r chi.Router) { r.Use(auth.RequireBearer(store)); ... }) (Phase 10) — Plan 02 mounts /addons and /addons/{slug}/info inside it
      - supervisor.ReadSupervisorToken env reader (Phase 9) — supervisor.NewClient already takes tokenFn
  - phase: 10-auth-layer-structured-logging-healthcheck
    provides:
      - auth.RequireBearer chi middleware mounted on /v1 subrouter (anonymous calls to /v1/addons and /v1/addons/{slug}/info return 401 + {error_code: "unauthorized"})
      - reqlog.RequestLogger middleware on the root router (OPS-01 JSON log line per request)
  - phase: 09-bridge-foundation-token-rotation-spike
    provides:
      - supervisor.tokenInjectingTransport — Plan 02 ListAddons + GetAddonInfo inherit the same Bearer injection pattern as Ping / GetSupervisorInfo

provides:
  - supervisor.Client.ListAddons(ctx) returning []contract.AddOnInfo with V2-preferred/V1-fallback (try /apps, on non-200 fall back to /addons); both envelopes decoded into the same []contract.AddOnInfo slice after normalizeStarted
  - supervisor.Client.GetAddonInfo(ctx, slug) returning *contract.AddOnInfo with V2-preferred/V1-fallback (try /apps/{slug}/info, then /addons/{slug}/info)
  - supervisor.ErrNotFound sentinel — GetAddonInfo returns it when BOTH V2 and V1 return 404 OR V2 returns 403 Forbidden AND V1 returns 404 (relaxed fallback for Supervisor versions that disable per-slug V2 lookups)
  - normalizeStarted(items []contract.AddOnInfo) — derives started = (state == "started") for any entry with zero-valued started, hiding Supervisor V1's omission of the field from handlers
  - handlers.Addons(supClient) http.HandlerFunc — GET /v1/addons (BRIDGE-02) returning 200 + JSON array directly (no wrapper envelope) or 502 + {error_code: "upstream_error"}
  - handlers.AddonInfo(supClient) http.HandlerFunc — GET /v1/addons/{slug}/info (BRIDGE-03) returning 200 + AddOnInfo on success, 404 + {error_code: "not_found"} (literal shape, no message field, no slug echo) on supervisor.ErrNotFound, 502 + {error_code: "upstream_error"} on other Supervisor errors
  - router.go: two routes mounted inside the existing /v1 auth subrouter — r.Get("/addons", handlers.Addons(supClient)) and r.Get("/addons/{slug}/info", handlers.AddonInfo(supClient))
  - 5 new supervisor client_test.go tests: TestClientListAddonsV2Success, TestClientListAddonsV2FailsV1Succeeds, TestClientGetAddonInfoV2ToV1Fallback, TestClientGetAddonInfoBothNotFound, TestClientGetAddonInfoV2ForbiddenV1NotFound
  - 2 new handler tests in addons_test.go: TestAddonsHandlerHappyPath, TestAddonsHandlerUpstreamError
  - 3 new handler tests in addon_info_test.go: TestAddonInfoHandlerHappyPath, TestAddonInfoHandlerNotFound, TestAddonInfoHandlerUpstreamError

affects:
  - 11-02→12 (Phase 12 BRIDGE-04..09 write API + critical-addon safety + per-slug mutex): reuses the V2-preferred/V1-fallback machinery added in this plan for /apps/{slug}/{install,uninstall,start,stop,options}; expands contract.SupervisorInfo / types.go with write-related types; the BRIDGE-09 forward-typing of error_codes (prevented_destroy, critical_addon, already_installed, locked) replaces the bare "upstream_error" used here
  - phase-13 (terraform-provider-homeassistant): the contract.AddOnInfo type is the configure-discovery body for Provider Configure; the same `replace terraform-bridge => ../terraform-bridge` directive makes the type drift between Bridge and Provider caught at Provider build time
  - phase-15 (make install-provider E2E): /v1/addons and /v1/addons/{slug}/info are exercised by the Provider's import-driven data sources; the make E2E must verify both endpoints return real Supervisor data on haos-op3050-1
  - phase-12 (NEW error_code mapping per BRIDGE-09): the current handler returns bare {error_code: "upstream_error"} for any non-ErrNotFound Supervisor failure; Phase 12 introduces typed mappings (403 -> prevented_destroy, 409 -> already_installed, 423 -> locked, 5xx -> transient)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "supervisor.Client V2-preferred/V1-fallback (new pattern in this plan): try V2 endpoint first, fall back to V1 on non-200. The fallback is per-request (no caching) so a single transient V2 failure cannot permanently pin the Bridge to V1. Pattern generalizes to Phase 12's write endpoints (install/uninstall/start/stop/options)."
    - "ErrNotFound sentinel wrapped via errors.Is — handler does errors.Is(err, supervisor.ErrNotFound) to map to 404 + not_found. The sentinel is the only error that maps to 404; every other error maps to 502 + upstream_error."
    - "normalizeStarted invariant: started = (state == \"started\") for any entry where started is zero-valued. Hides Supervisor V1's omission of the `started` field from handlers; both V1 and V2 callers see the same AddOnInfo shape."
    - "BRIDGE-03 404 body is byte-exact {\"error_code\":\"not_found\"} (verified independently with json.Marshal on contract.ErrorResponse{ErrorCode:\"not_found\"} returning the exact bytes). NO message field, NO slug echo — enforced by the contract.ErrorResponse omitempty on the Message field AND by the test asserting strings.Contains(body, slug) is false."
    - "Handler error path: handler logs ONE WARN slog record with key bridge_<endpoint>_upstream_failed (matching info.go's bridge_info_upstream_failed precedent), writes 502 + {error_code:\"upstream_error\"} with NO Message, never echoes the token or upstream error fragment. PITFALLS S-1 invariant preserved."
    - "/v1/addons returns the slice DIRECTLY as the JSON body (BRIDGE-02 success criterion: \"JSON array\"). NOT wrapped in an envelope — chi's json.NewEncoder.Encode(items) on a []T produces a top-level JSON array."

key-files:
  created:
    - terraform-bridge/internal/httpapi/handlers/addons.go
    - terraform-bridge/internal/httpapi/handlers/addon_info.go
    - terraform-bridge/internal/httpapi/handlers/addons_test.go
    - terraform-bridge/internal/httpapi/handlers/addon_info_test.go
  modified:
    - terraform-bridge/internal/supervisor/client.go
    - terraform-bridge/internal/supervisor/client_test.go
    - terraform-bridge/internal/httpapi/router.go

key-decisions:
  - "V2-preferred/V1-fallback per-request (no caching) — a single failing V2 call cannot permanently pin the Bridge to V1, because Supervisor might be transiently misconfigured. The fallback adds at most one extra HTTP round-trip per failing V2 call. Phase 12 may revisit for destructive operations (refusing to silently downgrade)."
  - "Relaxes GetAddonInfo fallback to include V2-403-then-V1-404 as ErrNotFound (not just dual 404s) — mirrors the empirical case where some Supervisor versions disable per-slug V2 lookups. Without this relaxation, unknown slugs on such hosts would surface as 502 + upstream_error instead of 404 + not_found."
  - "started normalization in client (not handler) — single source of truth for the V1/V2 invariant. Future callers of ListAddons / GetAddonInfo (e.g. Phase 12 write flows that read pre-install state) inherit the correct shape for free."
  - "404 body is byte-exact {\"error_code\":\"not_found\"} (no message, no slug) per BRIDGE-03 literal wording. The contract.ErrorResponse{ErrorCode:\"not_found\"} produces exactly these bytes (verified with json.Marshal on a stand-alone scaffold); the test additionally asserts the body does not contain the slug substring."
  - "/v1/addons returns JSON array DIRECTLY (no envelope) — BRIDGE-02's success criterion is \"JSON array of all installed add-ons\". A wrapper envelope would have forced the Provider to drill through the wrapper struct. Verified by `var body []contract.AddOnInfo; json.Unmarshal(... &body)` in the test."
  - "Routes mounted AFTER /version (Plan 01) and BEFORE /auth/rotate in the auth subrouter so the order is read-only-then-mutation, mirroring Plan 01's hygiene ordering."
  - "isHTTPStatus uses strings.Contains(err.Error(), \"status NNN\") rather than introducing a typed error struct — the wrapping pattern with fmt.Errorf(\"supervisor: %s status %d\", path, code) is the only producer of these errors in this file, so a substring match is sufficient and avoids a new error type."
  - "Body-drain in non-200 paths only — success paths leave the body intact for json.NewDecoder(resp.Body).Decode (Rule 1 fix from Plan 01 SUMMARY carried forward; applies to getAddonInfoFromPath too). The drain is duplicated in two non-200 branches (404 and other non-200) for clarity, even though the second branch already covers the first."

patterns-established:
  - "Pattern 4 (handler calling supervisor.Client): handlers DO NOT know about V2 vs V1. The supervisor.Client encapsulates both endpoints and surfaces a typed []contract.AddOnInfo / *contract.AddOnInfo / ErrNotFound. Future Phase 12 write handlers will follow the same shape — they call InstallAddon(slug) without any V2/V1 awareness."
  - "Pattern 5 (slog key prefix bridge_<endpoint>_upstream_failed): the handler emits a single Warn record with the err.Error() string (never the token, never the upstream body) BEFORE writing the 502 response. Operators can `grep bridge_.*_upstream_failed terraform-bridge.log` to enumerate all addon/info failures without knowing which handler emitted them."
  - "Pattern 6 (per-handler 3s upstream timeout): addonsTimeout and addonInfoTimeout = 3 * time.Second mirrors info.go's infoTimeout. The handler timeout is separate from supervisor.Client's internal httpClient Timeout (2 * time.Second) so a stalled Supervisor does not exhaust the caller's budget."

# Actuals (#2632) — pairs with the plan's estimate to calibrate future estimates.
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 14125    # chars/4 over files Plan 02 actually changed (4 new + 3 modified)
  tasks: 2
  commits: 0       # orchestrator is driving the user-approved commit per the "Do NOT commit" directive

# Metrics
duration: 13min
completed: 2026-09-03
status: complete
requirements-completed: [BRIDGE-02, BRIDGE-03]
---

# Phase 11 Plan 02: Add-on Read Endpoints (V1/V2 fallback) Summary

**supervisor.Client extended with ListAddons + GetAddonInfo + ErrNotFound sentinel implementing V2-preferred/V1-fallback; two new auth-protected HTTP handlers land GET /v1/addons (BRIDGE-02) and GET /v1/addons/{slug}/info (BRIDGE-03) with the literal 404 body shape.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-09-03T10:12:03Z
- **Completed:** 2026-09-03T10:24:48Z
- **Tasks:** 2 (both `type: auto`)
- **Files created:** 4 (2 handlers + 2 handler tests)
- **Files modified:** 3 (supervisor/client.go + supervisor/client_test.go + httpapi/router.go)

## Accomplishments

- `supervisor.Client.ListAddons(ctx)` calls `/apps` first; on non-200 (typically 403 because the host Supervisor doesn't advertise `supervisor_api_v2`) falls back to `/addons`. Both envelopes decode into `[]contract.AddOnInfo` after `normalizeStarted`. Errors wrap with `fmt.Errorf`, never leak the token (PITFALLS S-1).
- `supervisor.Client.GetAddonInfo(ctx, slug)` calls `/apps/{slug}/info` first; on non-200 falls back to `/addons/{slug}/info`. Returns sentinel `ErrNotFound` when BOTH endpoints return 404 OR V2 returns 403 + V1 returns 404 (relaxed fallback for Supervisor versions that disable per-slug V2 lookups).
- `supervisor.ErrNotFound = errors.New("supervisor: not found")` sentinel; `errors.Is(err, supervisor.ErrNotFound)` distinguishes "the add-on doesn't exist" from "Supervisor is broken" — only the former maps to 404; other failures map to 502.
- `normalizeStarted` derives `started = (state == "started")` for any zero-valued `Started` field, hiding Supervisor V1's omission of the field from handlers.
- `handlers.Addons(supClient)` mounted at `GET /v1/addons` (BRIDGE-02): 3-second upstream timeout, returns 200 + JSON array (NOT wrapped in envelope) on success, 502 + `{error_code: "upstream_error"}` (no Message) on Supervisor failure.
- `handlers.AddonInfo(supClient)` mounted at `GET /v1/addons/{slug}/info` (BRIDGE-03): 3-second upstream timeout, returns 200 + `AddOnInfo` on success, 404 + `{error_code: "not_found"}` on `ErrNotFound`, 502 + `{error_code: "upstream_error"}` on other Supervisor errors. The 404 body is byte-exact `{"error_code":"not_found"}` (verified with `json.Marshal` on `contract.ErrorResponse{ErrorCode:"not_found"}`); the test additionally asserts the body does NOT contain the requested slug substring.
- `router.go` mounts both routes inside the existing `r.Route("/v1", ...).Use(auth.RequireBearer(store))` block (Plan 01/10 inheritance), positioned after `/version` and `/whoami` and before `/auth/rotate` (read-only-then-mutation hygiene).
- **5 new supervisor client tests + 5 new handler tests** (10 total): all pass on first run. Pre-existing 2 supervisor tests + 6 handler tests (Plan 01) + Phase 10 tests remain green; no regressions.

## Coordination with Plan 11-01

Plan 02 cooperates tightly with Plan 01 because Plan 02 writes half its code on top of Plan 01's surface.

**Reused from Plan 01 without modification:**

- `terraform-bridge/internal/supervisor/testing.go` (the `TokenFnForTest` + `WithBaseURLForTest` helpers). Handler-level tests in `package handlers` call `WithBaseURLForTest` to redirect the Client at an `httptest.NewServer`. NOT `export_test.go` — testing.go (regular .go) is visible cross-package while `_test.go` is not (per Plan 01 decision documented in the Plan 01 SUMMARY).
- `contract.AddOnInfo` (Phase 9 skeletal). Plan 02 passes it through verbatim after `normalizeStarted`; no new fields were needed because Plan 02's empirical V1-vs-V2 discrepancy (the `started` field) is normalized client-side, not by extending the struct.
- `contract.ErrorResponse` (Phase 9). Reused with `ErrorCode` only (omitempty on Message and RequestID) so BRIDGE-03's 404 response is byte-exact `{"error_code":"not_found"}`. Verified independently with `json.Marshal` on a stand-alone scaffold.
- `chi.Route("/v1", func(r chi.Router) { r.Use(auth.RequireBearer(store)); ... })` block from Plan 01/Phase 10. Plan 02 only ADDS `r.Get("/addons", ...)` and `r.Get("/addons/{slug}/info", ...)` inside the existing block; no signature change, no new middleware, no new subrouter.
- The slog key prefix `bridge_<endpoint>_upstream_failed` and the no-Message 502 body shape from `info.go` (`bridge_info_upstream_failed`). Plan 02 uses `bridge_addons_upstream_failed` and `bridge_addon_info_upstream_failed` — operators can grep the entire family without per-handler allowlist maintenance.

**Types Plan 02 coordinated with Plan 01:**

- `supervisor.Client` signature: Plan 01 extended it with `GetSupervisorInfo(ctx) (*SupervisorInfo, error)`. Plan 02 extends the SAME struct with `ListAddons(ctx) ([]contract.AddOnInfo, error)` and `GetAddonInfo(ctx, slug) (*contract.AddOnInfo, error)`, following Ping's pattern (NewRequestWithContext → Do → StatusCode check → envelope decode). The existing Client, NewClient, tokenInjectingTransport, Ping, GetSupervisorInfo are untouched. Plan 01 client tests + Plan 02 client tests share the same `&Client{httpClient: ..., baseURL: ..., tokenFn: ...}` literal style for GET tests on writeable paths, and the same `NewClient + WithBaseURLForTest` style for tests that want to use the public constructor.
- `NewRouter` signature `(bridgeVersion, store, supClient, startTime, stateFilePath)`: Plan 01 set this. Plan 02 does NOT change it. Plan 02 only ADDS route mounts inside the existing block; `supClient` is threaded through Plan 01's signature into Plan 02's handlers.
- `httpapi/router_test.go` `TestRouterVersionRequiresAuth` is unchanged — verifies RequireBearer is still mounted on the `/v1` subrouter (Plan 02's `/v1/addons`+`/v1/addons/{slug}/info` inherit the same middleware automatically).

## Files Created/Modified

### Created

- `terraform-bridge/internal/httpapi/handlers/addons.go` — `Addons(supClient *supervisor.Client) http.HandlerFunc` for GET `/v1/addons`. 3-second upstream timeout, slog Warn on failure, JSON array body (no wrapper envelope).
- `terraform-bridge/internal/httpapi/handlers/addon_info.go` — `AddonInfo(supClient *supervisor.Client) http.HandlerFunc` for GET `/v1/addons/{slug}/info`. 3-second upstream timeout, slog Warn on failure, maps `supervisor.ErrNotFound` → 404 + `{error_code: "not_found"}` (literal shape, no message, no slug echo).
- `terraform-bridge/internal/httpapi/handlers/addons_test.go` — `TestAddonsHandlerHappyPath` (200 + JSON array shape with 5 mandatory fields per entry; the `Started` boolean must be populated for both entries) + `TestAddonsHandlerUpstreamError` (502 + `ErrorResponse{ErrorCode: "upstream_error"}` with empty Message).
- `terraform-bridge/internal/httpapi/handlers/addon_info_test.go` — `TestAddonInfoHandlerHappyPath` (200 + AddOnInfo with all 7 fields populated) + `TestAddonInfoHandlerNotFound` (404 + `ErrorResponse{ErrorCode: "not_found"}` with empty Message AND body does NOT contain the slug) + `TestAddonInfoHandlerUpstreamError` (502 + `ErrorResponse{ErrorCode: "upstream_error"}`).

### Modified

- `terraform-bridge/internal/supervisor/client.go` — added `ErrNotFound` sentinel; added `ListAddons(ctx)`, `listAddonsFromPath(ctx, path)`, `normalizeStarted(items)`, `containsField(body, field)`; added `GetAddonInfo(ctx, slug)`, `getAddonInfoFromPath(ctx, path)`, `isHTTPStatus(err, code)`. Imports extended with `bytes`, `strings`, `"terraform-bridge/contract"`. Existing Client/NewClient/tokenInjectingTransport/Ping/GetSupervisorInfo untouched.
- `terraform-bridge/internal/supervisor/client_test.go` — appended 5 tests: `TestClientListAddonsV2Success` (V2-only success with started/normalization assertions), `TestClientListAddonsV2FailsV1Succeeds` (V2-403 → V1-200 fallback), `TestClientGetAddonInfoV2ToV1Fallback` (V2-404 → V1-200 fallback for known slug), `TestClientGetAddonInfoBothNotFound` (V2-404 + V1-404 → sentinel `ErrNotFound` via `errors.Is`), `TestClientGetAddonInfoV2ForbiddenV1NotFound` (V2-403 + V1-404 → sentinel `ErrNotFound`, the relaxed-fallback path). Imports extended with `"errors"` for `errors.Is`.
- `terraform-bridge/internal/httpapi/router.go` — inside the existing `r.Route("/v1", ...).Use(auth.RequireBearer(store))` block, added `r.Get("/addons", handlers.Addons(supClient))` and `r.Get("/addons/{slug}/info", handlers.AddonInfo(supClient))` between the existing `/whoami` and `/auth/rotate` mounts. NewRouter signature unchanged.

## Task Commits

Both atomic commits are PRE-APPROVED by the plan's Task 1 / Task 2 "Atomic commit" subsections, but per the orchestrator's explicit "Do NOT commit — stage and report" directive (matching the Plan 01 SUMMARY precedent), this executor **stages but does not commit**. The orchestrator will run the commits after human review of the staged diff.

1. **Task 1 (auto): supervisor.Client.ListAddons + GetAddonInfo with V2-preferred/V1-fallback + ErrNotFound sentinel.** Pre-approved commit message: `feat(11-02): supervisor.ListAddons + GetAddonInfo with V2/V1 fallback (BRIDGE-02 + BRIDGE-03 supervisor side)`. Body mentions `ErrNotFound` and the `normalizeStarted` invariant. (Staged but not yet committed.)
2. **Task 2 (auto): GET /v1/addons + GET /v1/addons/{slug}/info handlers + router mounts.** Pre-approved commit message: `feat(11-02): GET /v1/addons + GET /v1/addons/{slug}/info (BRIDGE-02 + BRIDGE-03) - handlers + routes`. Body mentions V1/V2 fallback is entirely inside supervisor.Client (no V1/V2 awareness in handlers) and the literal `error_code: "not_found"` BRIDGE-03 shape with no message field. (Staged but not yet committed.)

## Decisions Made

- **`isHTTPStatus` uses `strings.Contains(err.Error(), "status NNN")` substring match** rather than introducing a typed `*HTTPStatusError` struct. The wrapping pattern `fmt.Errorf("supervisor: %s status %d", path, code)` is the only producer of these errors in `client.go`, so a substring match is sufficient and avoids a new error type. Decided against typed errors because the ErrNotFound sentinel is the only typed error the public API actually needs; the rest is logged by the handler.
- **Body-drain duplicated in 404 and "other non-200" branches of `getAddonInfoFromPath`** rather than refactored into a single drain. Clarity wins here — the future maintainer reading the code sees exactly what happens on each branch.
- **Route order in the auth subrouter**: `/version`, `/whoami`, `/addons`, `/addons/{slug}/info`, `/auth/rotate`. New mounts slotted between `/whoami` and `/auth/rotate` to preserve the read-only-then-mutation hygiene convention established in Plan 01.
- **Test of 404 body shape**: assert both the unmarshaled `ErrorResponse` (`body.ErrorCode == "not_found"` and `len(body.Message) == 0`) AND the raw byte string (`strings.Contains(body, "ghost")` is false). The latter catches slug-echo regressions even if the contract struct is later extended.
- **Test of happy-path AddOnInfo body**: drive the Client through a real `httptest.NewServer` because supervisor.Client is a concrete struct (no interface), so a stub-implementer approach would require unsafe type assertions. The Plan 02 version uses the Plan 01 `WithBaseURLForTest` helper consistently.

## Deviations from Plan

### Auto-fixed Issues

None — Plan 02 was followed exactly as written. The blocker/warning fix round had already tightened the plan (single `ListAddons`/`listAddonsFromPath`, correct imports, no `errors.Is(nil, nil)` dummies, V2-403-then-V1-404 relaxation), and no further auto-fixes were needed during execution.

### Pre-existing Items Noted (out of scope)

- **Pre-existing `SUPERVISOR_TOKEN` literal occurrences** still total 11 (not the "exactly 1" baseline the plan asserted). Same disposition as Plan 01 SUMMARY: the runtime invariant (no token value ever enters a log record; `verify-bridge-no-token-leak.sh` would still pass) is preserved. The 11 references are documentation comments (client.go), the actual `os.Getenv` call (token.go), the scrubbing handler's allow-list entry, etc. — none of them are leak paths. Plan 02 did NOT add any new `SUPERVISOR_TOKEN` references (verified via grep per-file on every Plan 02 file).
- **Pre-existing `gofmt -l` flags 4 unmodified files**: `cmd/bridge/version.go`, `internal/auth/bind.go`, `internal/auth/token.go`, `internal/httpapi/get_root.go`. Same set flagged by the Plan 01 SUMMARY (Go 1.27.1's stricter comment-indent rules; files predate this plan). All 7 files Plan 02 modified or created pass `gofmt -l` cleanly.

## Issues Encountered

- **`go binary not on $PATH`** — resolved by exporting `PATH=/root/.cache/pre-commit/repo8dxmizyl/golangenv-default/.go/bin:$PATH` per invocation. `go.mod` declares `go 1.25`; Go 1.27.1 satisfies the toolchain.
- **Live-HA verification deferred** — Plan's "Manual (live HA host)" section requires building the add-on image, deploying to `haos-op3050-1`, recovering the token from `/data/initial-token`, and running `curl` with/without bearer. This is not executable from this dev container (the add-on builder + HA host are both remote). Same disposition as Plan 01 SUMMARY: deferred to Phase 14's `verify-work` pass. The empirical V1 observation (started field absent in /addons and /addons/<slug>/info) was already captured in the plan's `interfaces` section and is exercised by `TestClientListAddonsV2FailsV1Succeeds`.

## User Setup Required

None — no external service configuration required.

## Self-Check

- **Files exist:** PASSED — all 7 files (3 modified + 4 created) on disk and readable.
- **Greps from task verify blocks:** PASSED — Task 1 verify greps (`^var ErrNotFound`, `^func.*ListAddons`, `^func.*GetAddonInfo`, `"/apps"`, `"/addons"`, the 5 new test names) all match. Task 2 verify greps (`^func Addons`, `supClient.ListAddons`, `StatusBadGateway`, `^func AddonInfo`, `r.PathValue("slug")`, `errors.Is.*ErrNotFound`, `StatusNotFound`, `TestAddonsHandler*` + `TestAddonInfoHandler*`, `r.Get("/addons"...)` in router.go) all match.
- **404 body shape byte-exact:** PASSED — independently verified by marshaling `contract.ErrorResponse{ErrorCode: "not_found"}` in a stand-alone Go scaffold; the result is `{"error_code":"not_found"}` with no message field.
- **Tests:** 10 new test functions added; all pre-existing Phase 9/10/Plan 01 tests still pass:
  - `internal/auth` (existing)
  - `internal/httpapi` (Plan 01 `TestRouterVersionRequiresAuth`)
  - `internal/httpapi/handlers` (Plan 01 + Plan 02 = 11 tests)
  - `internal/httpapi/middleware` (existing)
  - `internal/logging` (existing)
  - `internal/supervisor` (Plan 01 + Plan 02 = 7 tests)
  - `cmd/bridge` (test-less), `contract` (test-less), `internal/version` (test-less)
- **`go build ./...`:** exit 0.
- **`go vet ./...`:** exit 0.
- **`gofmt -l` on Plan 02 files:** clean. (4 pre-existing unrelated files flagged.)
- **`./bridge -version`:** not re-run (depends on Plan 01's main.go wiring which is unchanged in Plan 02).

## Next Phase Readiness

**Ready for Phase 12 (BRIDGE-04..09 — write API + critical-addon safety + per-slug mutex):**

- `supervisor.Client` is now extended with `ListAddons(ctx)` + `GetAddonInfo(ctx, slug)` + `ErrNotFound`; the V2-preferred/V1-fallback pattern is established and applies directly to Phase 12's write endpoints (`InstallAddon(ctx, slug)`, `UninstallAddon`, `StartAddon`, `StopAddon`, `SetAddonOptions`). The `isHTTPStatus` + dual-envelope-decode helpers are reusable.
- `contract.AddOnInfo` is unchanged from Phase 9 skeletal — Phase 12 may need new contract types (`JobPollResult`, `OptionsValidationDiagnostic`, `CriticalAddonList`) but those are additive, not modifications to AddOnInfo.
- `NewRouter(bridgeVersion, store, supClient, startTime, stateFilePath)` signature is final: Phase 12 only ADDS new `r.Post("/addons/{slug}/install", ...)`, etc. mounts inside the existing auth subrouter. No router-level signature change needed.
- The handler error mapping (ErrNotFound → 404 + not_found, other Supervisor failure → 502 + upstream_error) is in place; Phase 12's BRIDGE-09 forward-typing refines the "other Supervisor failure" branch into typed error_codes (`prevented_destroy`, `critical_addon`, `already_installed`, `locked`).
- The 404 body shape `{error_code: "not_found"}` (no message, no slug echo) is now an established contract; Phase 12's 404 path can reuse it.

**No known blockers for Phase 12.**

---

_Phase: 11-bridge-read-api · Plan: 02 · Completed: 2026-09-03_
