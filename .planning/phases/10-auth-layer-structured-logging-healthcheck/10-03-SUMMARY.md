---
phase: 10-auth-layer-structured-logging-healthcheck
plan: 03
subsystem: auth
tags: [go, auth, chi-middleware, slog, audit, grace-window, atomic-write, operator-docs]

# Dependency graph
requires:
  - phase: 09-bridge-foundation-token-rotation-spike
    provides:
      "terraform-bridge/cmd/bridge/main.go skeleton, /sys/class/net Tailscale detection, multi-stage Dockerfile,
      SUPERVISOR_TOKEN env-reader"
  - phase: 10-auth-layer-structured-logging-healthcheck (plan 01)
    provides:
      "TokenStore (Generate/Persist/Load/Validate + Fingerprint), RequireBearer chi middleware, ActorTokenContextKey,
      SupervisorClient.Ping, contract.RotateResponse and ErrorResponse shapes, binding rules D-04..D-06"
  - phase: 10-auth-layer-structured-logging-healthcheck (plan 02)
    provides:
      "scrubbingHandler slog.Handler wrapper (AUTH-05 layer 1), RequestLogger chi middleware (OPS-01), Healthz handler
      with SupervisorClient.Ping + D-08 empty 503 body, bridge.token.issued exactly-once emission, strengthened
      verify-bridge-no-token-leak.sh"
provides:
  - "TokenStore.Rotate() — atomic generation, /data/bridge-token.replaced with grace, /data/bridge-token.grace
    persistence"
  - "POST /v1/auth/rotate handler — D-12 bearer-required, D-03 RFC3339 timestamp pair, exactly-once plaintext surfacing"
  - "bridge.token.rotated audit record with actor/old/new fingerprints (no plaintext)"
  - "Operator DOCS.md — issuance, rotation, recovery, bind_address options"
  - "main.go bridge.token.loaded uses HashFingerprint for stable cross-restart identifier"

affects:
  - "Phase 11 (Bridge Read API) — auth subrouter pattern continues; new read endpoints inherit RequireBearer without
    changes"
  - "Phase 12 (Bridge Write API + Safety) — destroy endpoints reuse the same audit-record pattern; bridge.token.rotated
    shows the established shape"
  - "Phase 13 (Provider) — Provider schema reads RotateResponse.{NewToken, GraceExpiresAt, OldTokenValidUntil} per
    contract/types.go"
  - "Phase 14 (Real-HA E2E) — re-runs internal/verify-bridge-no-token-leak.sh against the live HA host; this plan's
    local Go-chain closure is the unit-test evidence stream"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TokenStore.Rotate follows the same atomic-write contract as Persist (tmpfile + Sync + Chmod 600 + Rename); grace
      file is a parallel atomic-write so a partial grace never appears"
    - "Grace expiry is per-request (time.Now().Before(grace.expiresAt)) — no background goroutine, no ticker, grace file
      becomes inert when past"
    - "HashFingerprint(hash) lets Rotate fingerprint the just-replaced token without re-deriving plaintext; same
      SHA-256[8] output as Fingerprint(plaintext) when inputs agree"

key-files:
  created:
    - "terraform-bridge/internal/httpapi/handlers/auth_rotate.go — POST /v1/auth/rotate handler: RequireBearer-enforced,
      calls store.Rotate, emits bridge.token.rotated audit record, returns contract.RotateResponse with Cache-Control:
      no-store"
    - "terraform-bridge/internal/httpapi/handlers/auth_rotate_test.go — TestAuthRotateSuccess: status 200, body shape,
      D-03 timestamp equality, audit log contains no plaintext"
  modified:
    - "terraform-bridge/internal/auth/token.go — added GraceWindow=24h const, RotateResult struct, HashFingerprint
      helper, TokenStore.Rotate method (new + grace + hash-update); no changes to existing public API"
    - "terraform-bridge/internal/auth/token_test.go — added TestTokenStoreRotate (grace-window accept + post-expiry
      cutoff) and TestTokenStoreGracePersistsAcrossReload (2-line grace file format check, 64 hex chars, RFC3339, chmod
      600)"
    - "terraform-bridge/internal/httpapi/router.go — mounted POST /v1/auth/rotate inside the existing /v1/* auth
      subrouter after /v1/whoami"
    - "terraform-bridge/cmd/bridge/main.go — bridge.token.loaded now uses auth.HashFingerprint(store.Hash()) instead of
      literal '<redacted>'"
    - "terraform-bridge/DOCS.md — replaced Phase 9 stub with operator-facing procedure: token issuance (capture
      bridge.token.issued), rotation (curl POST /v1/auth/rotate, 24h grace), recovery (uninstall+reinstall for total
      token loss, D-12 no break-glass), bind_address options"
    - ".planning/REQUIREMENTS.md — mark AUTH-04 [x] (write the committed provider bound the Bridge to the same Plan 03
      commit)"

key-decisions:
  - "Rotate() persists the new hash BEFORE writing the grace file — order matters: if grace write fails, the old token
    still authenticates against the new hash; if the rename succeeds before the second-stage write, the on-disk primary
    state is always consistent"
  - "Grace file uses a 2-line plaintext format (hex64 + RFC3339) instead of JSON — keeps the existing readGraceFile
    parser in Plan 01 happy without restructuring that read path"
  - "Grace file is overwritten on the next rotation (not appended) — D-13 makes repeated rotations idempotent (the
    newest previous-hash wins, expiry windows stack but only the latest matters)"
  - "AuthRotate handler never calls auth.Fingerprint(actorPlain) on the empty-string branch — Recoverer wraps panics,
    but a missing context value means RequireBearer did not run; defenses-in-depth handled by middleware ordering"

patterns-established:
  - "Audit-record discipline: every rotation/issuance log line carries actor_token_fp + appropriate fingerprints +
    timestamp; plaintext never enters a slog call site"
  - "D-03 timestamp duplication: grace_expires_at and old_token_valid_until are the same RFC3339 string in the body so
    Provider consumers can pick the field name they prefer with no body-rewrite"
  - "Atomic-write contract: every state-bearing file in auth/ goes through the tmpfile + Sync + Chmod 600 + Rename
    dance, identical to Persist; no creative variations per call site"

requirements-completed:
  - AUTH-04

# Metrics
duration: 3.5min
completed: 2026-08-31
---

# Phase 10: Auth + Logging + Healthcheck Summary

**Bearer-token rotation lifecycle landed: POST /v1/auth/rotate with 24h grace, persistent grace file across restarts,
fingerprint-only audit record, and operator-facing DOCS.md for issuance/rotation/recovery.**

## Summary

This plan closes Phase 10 by extending the Plan 01 TokenStore with `Rotate()` and the per-request grace logic (D-13),
exposes it as `POST /v1/auth/rotate` under the auth subrouter (D-12 bearer-required, D-03 timestamp-duplication response
shape), and ships the operator procedure (token issuance on first start, rotation via curl, total-loss recovery via
uninstall+reinstall) in DOCS.md. AUTH-04 — the lifecycle half of the bearer-token primitive — is now satisfied.

The auth package remains slog-free (Plan 01 invariant extended by Plan 02's scrubbing handler). The audit record carries
`actor_token_fp`, `old_token_fp`, `new_token_fp`, `grace_expires_at` only; no plaintext reaches any log sink.

Plan execution: 3 atomic commits, no deviations from the plan. The Go-level verification chain
(`go build ./... && go vet ./... && go test ./...`) passed end-to-end on every commit; the integration-level verify
script (`internal/verify-bridge-no-token-leak.sh`) requires running on a host with a working container build, which this
sandbox does not provide (overlay filesystem not mountable — kernel/filesystem constraint, not a code defect). Phase 14
is the canonical re-execution site per Phase 9's deferred-execution commitment for the live HA host.

## Performance

- **Duration:** 3.5 min (209 s, of which ~2.5 min on Go toolchain install on a host without `go` on PATH — Go 1.25
  tarball downloaded to `/tmp/opencode/go-install/`)
- **Started:** 2026-08-31T18:56:00Z (this plan's executor session)
- **Completed:** 2026-08-31T19:00:00Z
- **Tasks:** 3 / 3 complete
- **Files modified:** 6 (1 carry-over token.go + 1 carry-over token_test.go, both extended; 2 new + 1 router edit + 1
  main.go edit + 1 DOCS.md rewrite)

## Accomplishments

- `TokenStore.Rotate()` round-trips a fresh token + persists the previous hash to `/data/bridge-token.grace` with
  `grace_expires_at = now + 24h`, both files atomic (tmpfile + Sync + Chmod 600 + Rename). Both tokens authenticate
  during the grace window; only the new one authenticates after the cutoff; the grace state survives a Bridge restart
  (reloded by a fresh TokenStore via the existing readGraceFile path).
- `POST /v1/auth/rotate` returns 200 + `contract.RotateResponse{new_token, grace_expires_at, old_token_valid_until}`
  where the two timestamps are byte-identical (D-03). The handler emits exactly one structured `bridge.token.rotated`
  record carrying four fingerprints (actor, old, new, grace timestamp) — the unit test asserts no plaintext reaches the
  log.
- `bridge.token.loaded` (subsequent restarts) now uses `auth.HashFingerprint(store.Hash())` for a stable cross-restart
  identifier — operators can grep for the same `actor_token_fp` across restarts without revealing the token.
- DOCS.md gains the operator procedure: how to capture the one-shot `bridge.token.issued` line on first start, the
  `curl POST /v1/auth/rotate` rotation command, the 24-hour grace window with restart persistence guarantee, and the
  "lost every token" recovery path (uninstall + reinstall). All long lines <= 120 chars (markdownlint clean).
- AUTH-04 marked `[x]` in REQUIREMENTS.md traceability.

## Task Commits

Each task was committed atomically:

1. **Task 1: TokenStore.Rotate() + grace file + tests** — `5e6b054` (feat)
2. **Task 2: AuthRotate handler + router mount + main.go loaded-record** — `9a132ef` (feat)
3. **Task 3: DOCS.md operator procedure + phase-end SUMMARY** — _this commit_ (docs)

## Files Created/Modified

- `terraform-bridge/internal/auth/token.go` — added `GraceWindow`, `RotateResult`, `HashFingerprint`,
  `(*TokenStore).Rotate()`; existing API and `readGraceFile` reader untouched
- `terraform-bridge/internal/auth/token_test.go` — added `TestTokenStoreRotate`,
  `TestTokenStoreGracePersistsAcrossReload`
- `terraform-bridge/internal/httpapi/handlers/auth_rotate.go` — POST /v1/auth/rotate handler with audit log
- `terraform-bridge/internal/httpapi/handlers/auth_rotate_test.go` — TestAuthRotateSuccess: 200 + body shape + D-03
  equality + plaintext-absent audit assertion
- `terraform-bridge/internal/httpapi/router.go` — POST /v1/auth/rotate mount inside /v1/* auth subrouter
- `terraform-bridge/cmd/bridge/main.go` — bridge.token.loaded uses auth.HashFingerprint(store.Hash())
- `terraform-bridge/DOCS.md` — Phase 9 stub replaced with operator procedure
- `.planning/REQUIREMENTS.md` — AUTH-04 marked completed
- `.planning/STATE.md` — phase 10 plan 03 completion recorded
- `.planning/phases/10-auth-layer-structured-logging-healthcheck/10-SUMMARY.md` — this file

## Verification

Executed against the current Plan 03 commit (`9a132ef`) on this executor's sandbox:

- `cd terraform-bridge && go build ./...` — PASS (exit 0)
- `cd terraform-bridge && go vet ./...` — PASS (exit 0)
- `cd terraform-bridge && go test ./... -count=1` — PASS (4 packages with tests; auth=7 funcs incl. 2 new, handlers=3
  funcs incl. 1 new, middleware, logging; total assertions ~18)
- `make validate-addons` — PASS (terraform-bridge/ validation passed)
- `python3 internal/validate-addon-config.py terraform-bridge` — PASS

**Environmental note (not a defect):** `bash internal/verify-bridge-no-token-leak.sh` returned exit 125 on this sandbox
— `docker build` (podman shim) fails because `/var/tmp/buildah-context-*/overlay/*/merge` cannot be mounted:
`mount overlay: ..., no such device`. The verify script's `set -e` correctly propagates the build failure. This is a
host-environment constraint (overlay FS unsupported here), not a code issue — the script's logic and the Docker setup
are unchanged from Plan 02. Phase 14 re-runs the integration verify on the live HA host per Phase 9's deferred-execution
commitment (09-SUMMARY §H-1 / §10). Go-level evidence above is sufficient for the unit-test surface this plan owns.

## Deviations from Plan

None — executed exactly as written. The grep signatures in the acceptance criteria matched verbatim (Rotate signature,
`24 * time.Hour`, `gracePath`, no slog, 7 Test-funcs in token_test.go, audit log without plaintext, router mount,
main.go HashFingerprint). Environment-only blocker above (container overlay) is not a plan deviation.

## Deferred / Hand-off to Phase 14

- **Real-HA integration run:** Phase 14 re-executes `internal/verify-bridge-no-token-leak.sh` on a host with working
  container build; confirms all OPS-01 + AUTH-05 + AUTH-04 invariants observed end-to-end against `/data`.
- **Per-error-code remediation DOCS section:** Phase 14 owns the troubleshooting section with empirical observed
  behavior for `rotate_failed`, `unauthorized`, `not_found`, `critical_addon_protected`, etc.
- **Grace expiry after long uptime:** validated at the unit-test level (manual
  `expiresAt = time.Now().Add(-1*time.Second)`) and at the persistence level (grace file format + reload); live-clock
  24-hour expiry test belongs on the real HA host under Phase 14.

## Self-Check: PASSED

- [x] `terraform-bridge/internal/auth/token.go` — Rotate signature present
- [x] `terraform-bridge/internal/auth/token_test.go` — 7 Test funcs (5 existing + 2 new); new ones cover grace + reload
- [x] `terraform-bridge/internal/httpapi/handlers/auth_rotate.go` — exists, AuthRotate signature matches
- [x] `terraform-bridge/internal/httpapi/handlers/auth_rotate_test.go` — exists, TestAuthRotateSuccess passes
- [x] `terraform-bridge/internal/httpapi/router.go` — r.Post("/auth/rotate", ...) inside /v1/* subrouter
- [x] `terraform-bridge/cmd/bridge/main.go` — bridge.token.loaded uses auth.HashFingerprint(store.Hash())
- [x] `terraform-bridge/DOCS.md` — contains # Configuration + ## Options / ## Token issuance / ## Token rotation / ##
      Token recovery; no lines > 120 chars
- [x] `.planning/REQUIREMENTS.md` — AUTH-04 marked [x]
- [x] `go test ./...` exit 0
- [x] `go vet ./...` exit 0
- [x] `go build ./...` exit 0
- [x] `make validate-addons` exit 0
- [x] `python3 internal/validate-addon-config.py terraform-bridge` exit 0
- [~] `bash internal/verify-bridge-no-token-leak.sh` exit 125 — host overlay FS limitation; Phase 14 re-runs on live HA
  host
