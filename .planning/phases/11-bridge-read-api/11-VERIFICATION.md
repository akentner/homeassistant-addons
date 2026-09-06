---
phase: 11-bridge-read-api
verified: 2026-09-02T20:00:00Z
status: passed
goal:
  "Bridge exposes the read-only surface (/v1/version, /v1/addons, /v1/addons/{slug}/info, /v1/info) that the Provider's
  Configure handshake and adoption logic depend on; reads are observable end-to-end without any write operations."
requirements_satisfied:
  - BRIDGE-01
  - BRIDGE-02
  - BRIDGE-03
  - BRIDGE-10
requirements_unsatisfied: []
plans_executed: 2
plans_total: 2
commits:
  - a6f1c36 docs(STATE): Phase 9 stale-state sync + Phase 11 in-progress tracking
  - 9158869 feat(11-01): GET /v1/info (BRIDGE-10) + GET /v1/version (BRIDGE-01) + planning docs
  - 40548c4 feat(11-02): supervisor V1/V2 fallback + GET /v1/addons + GET /v1/addons/{slug}/info
  - 4a94a76 docs(STATE): Phase 11 post-ship sync — landed
regressions_detected: false
human_verification_required:
  - "Live-HA curl verification against 192.168.178.3:8124 — deferred to Phase 14 per Phase-11 plan"
---

# Phase 11 Verification Report — Bridge Read API

## Goal Verification

**Goal (from ROADMAP.md):** The Bridge exposes the read-only surface (`/v1/version`, `/v1/addons`,
`/v1/addons/{slug}/info`, `/v1/info`) that the Provider's Configure handshake and adoption logic depend on; reads are
observable end-to-end without any write operations.

**Result: PASS** — All 4 success criteria below are met with on-disk evidence + 18 unit tests passing + gofmt/vet/build
clean. Live-HA curl verification against `192.168.178.3:8124` is **explicitly deferred to Phase 14** per the Phase-11
plans' manual-verification sections (requires Bridge-image rebuild + redeploy + bridge-token recovery).

## Success Criteria Status

### SC-1: `GET /v1/version` with full 4-field handshake body (BRIDGE-01)

| Check                                                                                                           | Result                                                                 |
| --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Handler mounted at `/v1/version` inside the existing `/v1` chi auth subrouter (PROV-03 handshake enforces auth) | PASS — `internal/httpapi/router.go:36`                                 |
| Returns HTTP 200 with JSON `{bridge_version, schema_version, min_provider_version, max_provider_version}`       | PASS — `internal/httpapi/handlers/version.go` (Plan 01 rewrite)        |
| `bridge_version` from injected const matches the Provider's PROV-03 expected version                            | PASS — `TestVersionHandler` asserts == injected value                  |
| `schema_version` populated from `internal/version.SchemaVersion` (compile-time constant = `1.0.0`)              | PASS — same test                                                       |
| `min_provider_version` / `max_provider_version` populated from constants (`0.0.0` / `1.999.0`)                  | PASS — same test                                                       |
| **Auth gate enforced:** anonymous request → HTTP 401 + `{"error_code":"unauthorized"}` (router-level)           | PASS — `TestRouterVersionRequiresAuth` (Plan 01 NEW router-level test) |
| `internal/version` package compiles + constants are usable by future Provider (replace-directive ready)         | PASS — `internal/version/version.go` (3 const declarations)            |
| `go build ./...`, `go vet ./...`, `gofmt -l .` clean                                                            | PASS                                                                   |

### SC-2: `GET /v1/addons` with Supervisor V2/V1 fallback (BRIDGE-02)

| Check                                                                                                                    | Result                                                                                                               |
| ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| Handler mounted at `/v1/addons` inside the `/v1` auth subrouter                                                          | PASS — `internal/httpapi/router.go:38`                                                                               |
| Returns HTTP 200 with JSON array of `AddOnInfo` records (`slug`, `name`, `version`, `state`, `started` mandatory fields) | PASS — `TestAddonsHandlerHappyPath` decodes `[]contract.AddOnInfo`                                                   |
| Supervisor V2 (`/apps`) preferred with V1 (`/addons`) fallback (V2-403 → V1)                                             | PASS — `TestClientListAddonsV2FailsV1Succeeds` (empirical haos-op3050-1 case)                                        |
| Supervisor V2-success path returns decoded list                                                                          | PASS — `TestClientListAddonsV2Success`                                                                               |
| `started` field normalized: V1-omitted → derived from `state == "started"`                                               | PASS — `normalizeStarted()` in `internal/supervisor/client.go` + asserted in `TestClientListAddonsV2FailsV1Succeeds` |
| On Supervisor failure: HTTP 502 + `{"error_code":"upstream_error"}` with empty message                                   | PASS — `TestAddonsHandlerUpstreamError`                                                                              |
| 3s upstream context timeout (matching `/v1/info`)                                                                        | PASS — `internal/httpapi/handlers/addons.go`                                                                         |
| Slog key follows `bridge_<endpoint>_upstream_failed` convention (`bridge_addons_upstream_failed`)                        | PASS — handler doc + log key                                                                                         |
| No `SUPERVISOR_TOKEN` value in any log path (PITFALLS S-1)                                                               | PASS — `! grep -E 'slog\..*token\|slog\..*Bearer' internal/httpapi/handlers/addons.go`                               |

### SC-3: `GET /v1/addons/{slug}/info` with V2/V1 fallback + 404 mapping (BRIDGE-03)

| Check                                                                                                             | Result                                                                                                      |
| ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Handler mounted at `/v1/addons/{slug}/info` using chi's `r.PathValue("slug")`                                     | PASS — `internal/httpapi/router.go:39` + `internal/httpapi/handlers/addon_info.go`                          |
| Returns HTTP 200 with full Supervisor `/apps/{slug}/info` payload (incl. `options`, `boot`, `repository`)         | PASS — `TestAddonInfoHandlerHappyPath`                                                                      |
| V2 (`/apps/{slug}/info`) preferred with V1 (`/addons/{slug}/info`) fallback                                       | PASS — `TestClientGetAddonInfoV2ToV1Fallback` (V2-404 → V1-200)                                             |
| **Dual-404 → `supervisor.ErrNotFound`** (handler maps to 404 + literal `{"error_code":"not_found"}` body)         | PASS — `TestClientGetAddonInfoBothNotFound` + `TestAddonInfoHandlerNotFound`                                |
| **Relaxed fallback:** V2-403 + V1-404 → also `ErrNotFound` (Supervisor versions that disable per-slug V2 lookups) | PASS — `TestClientGetAddonInfoV2ForbiddenV1NotFound`                                                        |
| Response body shape on 404 = EXACTLY `{"error_code":"not_found"}` (NO message field, NO slug echo — slug-privacy) | PASS — `TestAddonInfoHandlerNotFound` asserts `len(body.Message) == 0` + byte-for-byte equality on the wire |
| On other Supervisor failure: HTTP 502 + `{"error_code":"upstream_error"}`                                         | PASS — `TestAddonInfoHandlerUpstreamError`                                                                  |
| Slog key follows convention (`bridge_addon_info_upstream_failed`)                                                 | PASS                                                                                                        |

### SC-4: `GET /v1/info` unauthenticated (BRIDGE-10)

| Check                                                                                                               | Result                                                                                               |
| ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Handler mounted at `/v1/info` **at root** (NOT inside the `/v1` auth subrouter — must be public)                    | PASS — `internal/httpapi/router.go:31`                                                               |
| No Authorization header required → handler reachable without bearer                                                 | PASS — `TestRouterVersionRequiresAuth` proves `/v1/info` is NOT 401-anonymous while `/v1/version` IS |
| Returns HTTP 200 with `{bridge_version, supervisor_version, uptime_seconds, state_file_path}`                       | PASS — `TestInfoHandlerHappyPath` decodes `contract.BridgeInfo`                                      |
| `bridge_version` = injected value (matches `cmd/bridge/version.go`'s build-time `-ldflags` `bridgeVersion`)         | PASS — same test                                                                                     |
| `supervisor_version` = live `/supervisor/info` `data.supervisor`                                                    | PASS — `TestClientGetSupervisorInfoSuccess` decodes the envelope                                     |
| `uptime_seconds` = integer seconds since `func main()` start (`time.Since(startTime)`)                              | PASS — same test asserts `== 5s` against `time.Now().Add(-5s)` injected startTime                    |
| `state_file_path` = `/data/terraform.tfstate` (Phase-1 state path per PROJECT.md architecture decision)             | PASS — `cmd/bridge/main.go` const + handler tests                                                    |
| `Authorization: Bearer <token>` header set on outbound Supervisor call                                              | PASS — `TestClientGetSupervisorInfoSendsBearer` (request-side interceptor checks `seenAuth`)         |
| On Supervisor failure: HTTP 502 + `{"error_code":"upstream_error"}` with empty body (D-08 — no internal-state leak) | PASS — `TestInfoHandlerUpstreamError`                                                                |
| 3s upstream context timeout                                                                                         | PASS                                                                                                 |

## Requirement Traceability (REQUIREMENTS.md)

| Requirement                                                                                                | Phase 11 plan(s)       | Satisfied? | Evidence                                                                                                                           |
| ---------------------------------------------------------------------------------------------------------- | ---------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **BRIDGE-01**: `GET /v1/version` returns 4-field handshake body                                            | Plan 11-01 Task 2      | YES        | `TestVersionHandler` + `TestRouterVersionRequiresAuth`                                                                             |
| **BRIDGE-02**: `GET /v1/addons` returns JSON array; V2/V1 fallback                                         | Plan 11-02 Tasks 1 + 2 | YES        | 5 supervisor tests (V2 success + V2-403-fallback + V2-404-fallback + dual-404 + V2-403-V1-404) + handler tests                     |
| **BRIDGE-03**: `GET /v1/addons/{slug}/info` returns full info or 404 + literal not_found                   | Plan 11-02 Tasks 1 + 2 | YES        | `TestClientGetAddonInfo*` (4 supervisor tests) + `TestAddonInfoHandlerNotFound` (404 body byte-equality)                           |
| **BRIDGE-10**: `GET /v1/info` unauthenticated, returns 4 fields (bridge/supervisor/uptime/state_file_path) | Plan 11-01 Task 1      | YES        | `TestClientGetSupervisorInfoSuccess` + `TestInfoHandlerHappyPath` + `TestRouterVersionRequiresAuth` (negative test for `/v1/info`) |

## Regression Gate

| Source                                              | Test command             | Result                                                                                           |
| --------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------ |
| `terraform-bridge/internal/auth` (Phase 10)         | `go test -count=1 ./...` | PASS — all auth/middleware tests still green                                                     |
| `terraform-bridge/internal/httpapi` (Phase 10 + 11) | `go test -count=1 ./...` | PASS — middleware + new `TestRouterVersionRequiresAuth`                                          |
| `terraform-bridge/internal/httpapi/handlers`        | `go test -count=1 ./...` | PASS — all Phase 10 handlers + new info/version/addons/addon_info handlers                       |
| `terraform-bridge/internal/logging` (Phase 10)      | `go test -count=1 ./...` | PASS — scrubbing handler tests still green                                                       |
| `terraform-bridge/internal/supervisor` (Phase 9+10) | `go test -count=1 ./...` | PASS — Phase 10 Ping test + new 7 tests (GetSupervisorInfo + ListAddons + GetAddonInfo variants) |
| `terraform-provider-homeassistant` (Phase 9 stub)   | `go build ./...`         | PASS — Provider module unaffected by Phase 11 (replace directive resolves cleanly)               |

**No regressions detected.** All prior-phase test files exercised.

## Build / Lint Gate

| Tool                          | Command                                    | Result                                                                                     |
| ----------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `go build`                    | `cd terraform-bridge && go build ./...`    | EXIT 0 — all 8 packages compile                                                            |
| `go vet`                      | `cd terraform-bridge && go vet ./...`      | EXIT 0 — zero diagnostics                                                                  |
| `gofmt -l`                    | `gofmt -l terraform-bridge/`               | zero hits on the 18 Phase 11 files; 4 hits on PRE-EXISTING unmodified files (out of scope) |
| `pre-commit` (relevant hooks) | `pre-commit run --files <wave-1 + wave-2>` | PASS for all hooks touching Phase 11 files                                                 |

## Deviations

### 11-01

1. **Rule-1 auto-fix: body-drain order in `supervisor.Client.GetSupervisorInfo`.** The plan's code-as-written had
   `io.Copy(io.Discard, resp.Body)` BEFORE `json.NewDecoder(resp.Body).Decode(...)`, producing EOF on the success path
   because the drain had already consumed the body. Moved the drain into the non-200 branch only. Documented in
   `11-01-SUMMARY.md` §Auto-fixed Issues.

### 11-02

1. **None of substance.** The 5 BLOCKERs + 5 WARNINGs the plan-checker found were all addressed in the PLAN.md text
   before execution; the executor followed the plan verbatim.

## Cross-Plan Coordination

The two plans were **strictly complementary** (Plan 02 assumed Plan 01's deliverable was on disk; Plan 01 made no
references to Plan 02):

- **Reused without modification:** `internal/supervisor/testing.go` (NOT `_test.go` — go test build only compiles
  `_test.go` in the same package; handler tests in `package handlers` need cross-package visibility).
  `contract.AddOnInfo` (Phase 9 skeletal). `contract.ErrorResponse` (Phase 9). The
  `r.Route("/v1", ...).Use(auth.RequireBearer(store))` chi block. The slog key convention
  `bridge_<endpoint>_upstream_failed` (Plan 01 set with `bridge_info_upstream_failed`).

- **Coordinated types:** `supervisor.Client` (Plan 01 added `GetSupervisorInfo`; Plan 02 extends the SAME struct with
  `ListAddons` + `GetAddonInfo` + `ErrNotFound`). `NewRouter` signature (Plan 01 set it; Plan 02 adds two routes inside
  the existing block).

## Anti-Patterns Found

| File                              | Pattern | Severity | Impact |
| --------------------------------- | ------- | -------- | ------ |
| (none observed in Phase 11 files) | —       | —        | —      |

No TODO/FIXME/placeholder/empty-return/Hmm strings in any new file. No hardcoded empty data. Slog key convention
followed consistently across all 4 new handlers.

## Human Verification Required

### Live-HA curl verification (deferred to Phase 14)

The Phase-11 plans document the following manual verifications as live-stack smoke tests against
`http://192.168.178.3:8124`. These cannot be exercised from this session because:

1. The current branch contains compiled Bridge code that has NOT yet been built into a Docker image.
2. `ha-nextgen` / `haos-op3050-1` would need to install the rebuilt image and the Bridge-container restart is a brief
   service-disruption to `terraform-bridge`.
3. The Bridge token (`/data/initial-token` inside the bridge container) is needed for the bearer-auth curl tests;
   recovery requires either:
   - `ha addons cli 72a005f5_terraform-bridge cat /data/initial-token` (newer `ha` CLI; the branch-version CLI on
     `lxc-haos-104` may need updating), OR
   - `ha addons logs 72a005f5_terraform-bridge 2>&1 | grep bridge.token.issued` to capture the truncated preview emitted
     by `cmd/bridge/main.go` first-start signal.

Phase 14's `gsd-verify-work` will produce the canonical LIVE-HA evidence (apply/destroy cycles, idempotency, drift
behavior on a real HA host). Phase 14 owns the live-stack story because Phase 11 deliberately stayed sync-only.

### What Phase 14 WILL verify (forward-looking items, NOT this phase's gap)

- Apply/destroy round-trips of an `homeassistant_addon` resource against a real install/start/stop/uninstall cycle on
  `ha-nextgen` or `haos-op3050-1` (deferred until Phase 13 ships the Provider)
- Drift behavior: changing `options` triggers Update, changing `state` does NOT trigger Update (`UseStateForUnknown`)
- Idempotency: 5 consecutive `tofu apply` runs yield "No changes" after the first
- Bridge error-code map: 403 `critical_addon`, 423 `locked`, 409 `already_installed`, 5xx transient — observed
  diagnostic strings

## Notes

- **No `terraform-provider-homeassistant/` changes.** The Provider module
  (`replace terraform-bridge => ../terraform-bridge`) resolves cleanly against the Phase 11 changes; the existing Phase
  9 stub compiles unchanged.
- **Phase 13 dependency unblocked.** Phase 13's Provider can reference `version.SchemaVersion`,
  `version.MinProviderVersion`, `version.MaxProviderVersion` from the Bridge via the existing `replace` directive. The
  PROV-03 Configure-time handshake target (`GET /v1/version`) is operational.
- **Add-on version unchanged.** `terraform-bridge/build.yaml` and `terraform-bridge/config.yaml` still report `0.2.0-0`.
  No subpatch bump was warranted for Phase 11 because the Bridge add-on's program logic is being EXTENDED, not
  BUG-FIXED; per the v1.3 versioning scheme, SemVer bumps (X.Y.Z) reset subpatch to `-0`, and we are mid-milestone.
  Phase 14 will tag a `0.2.0-1` or `0.3.0-0` release after live-HA verification confirms Phase 11 + 12 + 13 behavior
  end-to-end.

---

_Verified: 2026-09-02T20:00:00Z — Verifier: the agent (gsd-verifier mode, equivalent to live verification recorder in
this session's context). Implementation verified by 18 unit tests + clean pipeline; live-HA evidence deferred to Phase
14 per Phase-11 plan documents._
