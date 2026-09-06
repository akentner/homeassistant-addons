# Phase 12: Bridge Write API + Critical-Addon Safety + Concurrency + State Index - Context

**Gathered:** 2026-09-02 **Milestone:** v1.3 opentofu-bridge **Status:** Ready for planning

<domain>

## Phase Boundary

Land the Bridge's full mutating write surface (install / uninstall / start / stop / options / nonce issuance / state
index) and the three safety primitives that make destructive operations safe: the `critical_addons` whitelist, the
per-slug write mutex, and the `X-Force-Destroy` nonce flow. Phase 1 of the Provider (Phase 13) consumes every endpoint
landed here.

Specifically this phase delivers:

- Five mutating endpoints wrapping Supervisor equivalents: `POST /v1/addons/{slug}/install`,
  `POST /v1/addons/{slug}/uninstall`, `POST /v1/addons/{slug}/start`, `POST /v1/addons/{slug}/stop`,
  `POST /v1/addons/{slug}/options`.
- One nonce-issuance endpoint: `POST /v1/auth/nonce` (returns a 60-second single-use token for `X-Force-Destroy`).
- One state-coverage endpoint: `GET /v1/state/index` (lists `*.tfstate` + `*.tfstate.backup` in `/data` with SHA-256
  digests so HA backup integration can claim coverage).
- In-process per-slug write mutex via `internal/mutex/`.
- `critical_addons` add-on option schema field (default `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`) wired
  to the install/uninstall/options handlers.

**What this phase is NOT:** the Provider Go module (Phase 13), `homeassistant_addon` resource CRUD (Phase 13), real-HA
end-to-end empirical verification (Phase 14), CI hardening (Phase 15). All of those land later.

</domain>

<decisions>

## Implementation Decisions

### Mutating endpoint surface (Area 1)

- **D-01:** Each mutating handler = new file under `terraform-bridge/internal/httpapi/handlers/` following the Phase 11
  filename convention (`install.go`, `uninstall.go`, `start.go`, `stop.go`, `options.go`, `nonce.go`, `state_index.go`).
  Each handler delegates to a new method on `supervisor.Client` for the Supervisor round-trip. Auth is enforced by the
  existing `/v1` chi subrouter (Phase 11).
- **D-02:** Each mutating handler takes a `ctx` bounded by an **explicit timeout** via `context.WithTimeout` — same
  pattern as Phase 11 `/v1/info` and `/v1/addons`:
  - Default 3s for install / uninstall / start / stop / options (matches Phase 11)
  - **D-03 exception:** install uses `install_job_timeout_seconds` from options (default 300 — see Area 4)
- **D-04:** All five handlers emit OPS-01 logs (existing chi middleware from Phase 10). On failure, they emit a
  `slog.Warn` with key `bridge_<endpoint>_upstream_failed` following the Phase-11 convention
  (`bridge_addons_upstream_failed` etc.). No `SUPERVISOR_TOKEN` value in any log path (PITFALLS S-1 invariant).

### X-Force-Destroy nonce storage — HYBRID (Area 2, decision from session discussion)

- **D-05:** Nonce storage = **in-memory cache for single-use enforcement + append-only /data/bridge-nonce-audit.json for
  forensic journal**. Two layers:
  1. **In-memory map:** `map[nonce]nonceEntry{issuedAt time.Time, used bool}` guarded by `sync.RWMutex`. On every
     `X-Force-Destroy` header validation, the handler reads the entry, marks `used = true`, returns success.
  2. **Append-only journal:** `/data/bridge-nonce-audit.json` with `chmod 600` (same atomic-rename pattern as
     `bridge-token`). Each line =
     `{"nonce_fp": "...", "issued_at": ..., "used_at": ..., "actor_token_fp": "...", "request_id": "...", "operation": "uninstall"}`.
     The Journal does NOT participate in single-use enforcement — it only exists for forensics ("did this nonce get
     used? by whom? for what op?").
- **D-06:** Nonce lifecycle:
  - `POST /v1/auth/nonce` (auth-required) → cache entry + journal append → returns `{nonce, expires_at}`.
  - On any destructive request (uninstall, options-change) with `X-Force-Destroy: <nonce>`:
    - Lookup cache entry. Missing → `401 error_code: nonce_expired` (covers both "never issued" and "issued in a
      previous process — cache didn't survive restart"). The journal entry alone is NOT sufficient for acceptance.
    - Found and `used == true` → `401 error_code: nonce_used`.
    - Found and `now > issuedAt + 60s` → `401 error_code: nonce_expired` (delete from cache, GC).
    - Found, unused, in-window → mark `used = true`, append journal event (with `used_at`), proceed to destructive op.
- **D-07:** Cache GC runs every 30s in a background goroutine started by `main.go`; removes entries where
  `now > issuedAt + 60s + 5s_grace`. Stops on SIGTERM (Phase 9 signals.go).
- **D-08:** Cache loss-on-Bridge-restart = acceptable. Caller sees `401 nonce_expired` and re-requests via
  `POST /v1/auth/nonce`. The 60-second TTL makes the cost negligible. The journal entries persisted to disk let the
  operator answer "did this nonce issue / use cross-restart?" via grep — not via acceptance semantics.

### `critical_addons` enforcement scope (Area 3, decision from session discussion)

- **D-09:** `critical_addons: list` = new add-on option in `config.yaml` schema (Phase-1 minimal scope):
  ```yaml
  options:
    critical_addons:
      - "core_mosquitto"
      - "core_zigbee2mqtt"
      - "core_esphome"
  schema:
    critical_addons:
      - "str?"
  ```
  Empty list (or field removed) = protection disabled. Per default value above. Validated at startup (logged
  `bridge.critical_addons=... count=N`).
- **D-10:** Operations blocked for any slug in `critical_addons`:
  - `POST /v1/addons/{slug}/uninstall` → `403 error_code: critical_addon_protected` (BEFORE the nonce check; nonces do
    not protect against destroying critical add-ons).
  - `POST /v1/addons/{slug}/options` → same `403 critical_addon_protected`.
  - **Allowed even on critical slugs:** `install` (idempotent re-install OK), `start`, `stop`, GETs (`info`, `list`).
  - SPEC ROADMAP.md SC-3 also mentions `restart` as blocked; we map `restart` to `install` because Supervisor's
    `install` flow already includes a stop-and-reinstall for upgrades (the config.yaml `version` semver bump is what
    triggers the restart, not a separate Bridge endpoint).
- **D-11:** `critical_addons` enforcement happens in the handler, not in `supervisor.Client`. The check is a pure
  function over the slug list + options config — no upstream round-trip required, so it lives before any auth/state
  allocation.

### Per-slug write mutex strategy (Area 4, decision from session discussion)

- **D-12:** Per-slug mutex via `map[string]*sync.Mutex` guarded by an outer `sync.RWMutex` for map access. Located in a
  new package `terraform-bridge/internal/mutex/`. Constructor returns a `Manager` interface; the handler receives it via
  `NewRouter`'s signature extension.
- **D-13:** Acquisition = `TryAcquire(slug, ctx)`:
  - Look up or create the per-slug `*sync.Mutex` under map lock (read-then-upgrade-to-write on miss).
  - Drop map lock. Call `lock acquisition with timeout`: spawn a goroutine that drives `lock.Lock()` and signals done;
    the main goroutine selects on `<-done` vs `<-ctx.Done()`.
  - Default timeout = 5 seconds (`try_lock_timeout_seconds` schema option, default 5).
  - On timeout: return `423 error_code: locked` per BRIDGE-09. Handler emits `slog.Warn` with `bridge.slug_lock_timeout`
    and the requested slug (slog invariant: NO token value).
  - On success: return a `Release(slug)` closure that the handler defers.
- **D-14:** The mutex is **per-slug**, NOT global. Two concurrent `/install core_mosquitto` requests serialize against
  each other; `/install core_mosquitto` and `/install core_zigbee2mqtt` run in parallel. No cross-slug lock ordering
  required.
- **D-15:** Single-request scope only. The mutex is acquired at handler entry and released at handler exit. There is no
  "cross-request write transaction"; each request is a single Supervisor call + response.
- **D-16:** The mutex does NOT cover read endpoints (`info`, `list`, `version`, `whoami`, `state/index`, `auth/nonce`).
  Reads remain concurrent regardless of any in-flight writes.

### Supervisor job polling (Area 5, decision from session discussion)

- **D-17:** Install handler polls `/jobs/{id}` with **linear 1-second interval** (NOT exponential backoff).
  - Total budget bounded by `install_job_timeout_seconds` (D-03 / Area 1).
  - Each poll request carries its own 3-second sub-timeout via `context.WithTimeout(parent, 3*time.Second)`.
  - On `Done=true`: decode the result, return the final `addons.info` payload (per BRIDGE-04) as 200 + JSON.
  - On `Done=false` and budget remaining: sleep 1s, loop.
  - On budget exhausted: return `504 error_code: install_timeout` + log `bridge.install_polling_timeout` with slug +
    elapsed-seconds.
- **D-18:** Polling loop is in the handler, not `supervisor.Client`. Client exposes `GetJobStatus(ctx, jobID)` →
  `(JobStatus, error)`. Handler drives the loop and the budget.
- **D-19:** The other four mutating endpoints (uninstall / start / stop / options) do NOT poll — Supervisor's sync
  endpoints already block until complete (per HA architecture: these are `asyncio.shield`-awaited server-side; confirmed
  in BRIDGE-06's requirement text).

### State index endpoint scope (Area 6, decision from session discussion)

- **D-20:** `GET /v1/state/index` enumerates **all `*.tfstate` and `*.tfstate.backup` files** in `/data` with their
  SHA-256 digests. Files named `*.tfstate.lock` are SKIPPED (ephemeral lock files, never user-relevant).
- **D-21:** Response shape:
  ```json
  {
    "files": [
      { "name": "terraform.tfstate", "size_bytes": 4096, "sha256": "abc123..." },
      { "name": "terraform.tfstate.backup", "size_bytes": 4096, "sha256": "def456..." }
    ]
  }
  ```
- **D-22:** Implementation: a new package `terraform-bridge/internal/state/` exposing
  `Index(dir string) ([]FileEntry, error)`. Uses `filepath.Glob` for the patterns + `crypto/sha256` for the digest. The
  handler is auth-required (mounted under `/v1`).
- **D-23:** Empty result set is valid (`files: []`). Errors per-file are accumulated and surfaced as a `skipped` field
  on the response (e.g., permission denied on one file doesn't fail the whole endpoint).
- **D-24:** The endpoint is `GET` only — no body, no query params. POST is a 405 from chi.

### Error mapping convention (Area 7)

- **D-25:** The five BRIDGE-09 error codes (`not_found`, `prevented_destroy`, `critical_addon`, `already_installed`,
  `locked`, plus our additions `nonce_expired`, `nonce_used`, `install_timeout`, `upstream_error`) all map Supervisor
  HTTP status to Bridge HTTP status as documented in SC-4. The mapping lives in a single helper
  `internal/supervisor.MapError` that returns either `supervisor.ErrNotFound`, `supervisor.ErrCriticalAddon`,
  `supervisor.ErrAlreadyInstalled`, `supervisor.ErrLocked`, `supervisor.ErrTransient` (5xx), or one of the new errors.
  Handlers map sentinel → bridge HTTP code via a single switch.
- **D-26:** `409 already_installed` is **NOT treated as an error in handlers** — it's an adoption signal. The install
  handler does NOT short-circuit on 409; it falls through to `GET /v1/addons/{slug}/info` and returns 200 + the info
  payload. The Provider (Phase 13) sees this as success-as-adoption and the lifecycle is well-formed.

### CSRF handling — DEFERRED (noted, see deferred section)

The SPEC attributes `nonce_used` / `nonce_expired` to the destructive-operation flow (LIFE-03), which is a stronger
defense than the CORS preflight pattern. CORS support in Phase 12 would be a no-op given the strict Tailscale bind
gating (Phase 10 D-04..D-06). PITFALLS S-3 (OPTIONS preflight) is deferred to a potential Phase 16 / Phase 2 add — see
deferred section.

### Carried forward from REQUIREMENTS.md + Phase 9/10/11 CONTEXT (locked, not re-discussed)

- **CF-01:** Auth primitives from Phase 10: `crypto/rand` (32 bytes), base64url token (43 chars), SHA-256 at-rest,
  `crypto/subtle.ConstantTimeCompare` validation. `POST /v1/auth/rotate` grace window 24h. (D-01..D-13 of 10-CONTEXT.)
- **CF-02:** 401 body = `{"error_code": "unauthorized"}`, no upstream request body, no env, no token, no `request_id`
  echoed. (CF-03 of 10-CONTEXT.)
- **CF-03:** OPS-01 mandatory log fields per request: `ts`, `level`, `msg`, `request_id`, `route`, `method`, `status`,
  `duration_ms`. (CF-04 of 10-CONTEXT.)
- **CF-04:** Slog key convention `bridge_<endpoint>_<event>` (Phase 11 — `bridge_info_upstream_failed` et al.). New
  Phase-12 handlers MUST use the same prefix.
- **CF-05:** Router chi v5, middleware order: RequestID → Recoverer → request-logger → (per-route auth). All new
  Phase-12 endpoints are mounted INSIDE the existing `/v1` chi subrouter to inherit `RequireBearer`. (CF-06 of
  10-CONTEXT.)
- **CF-06:** Bind = `:8124` with `bind_address` + `bind_allowed_subnets` enforcement from Phase 10 D-04..D-06. No
  Phase-12 change.
- **CF-07:** Supervisor V2-preferred / V1-fallback machinery from Phase 11 lives inside `supervisor.Client`; Phase 12
  extends with `Install(ctx, slug)`, `Uninstall(ctx, slug)`, `Start(ctx, slug)`, `Stop(ctx, slug)`,
  `Options(ctx, slug, opts)`, `GetJobStatus(ctx, jobID)`, `ValidateOptions(ctx, slug, opts)`. The handlers call these
  new methods; the V2/V1 fallback is encapsulated inside the client.
- **CF-08:** Atomic file write with `chmod 600` pattern from Phase 9/10: same template for any new file in `/data`
  (notably the nonce audit journal — D-05).
- **CF-09:** Contract types live in `terraform-bridge/contract/types.go` (NOT `internal/contract/` per CONTEXT D-03
  "non-`internal` package path"). Phase 12 adds: `NonceResponse{nonce string, expires_at string}`,
  `StateIndexResponse{files []StateFileEntry}`, `StateFileEntry{name string, size_bytes int64, sha256 string}`,
  `JobStatus` already exists with `{job_id, done, result}` (Phase 9 stub; Phase 12 fills out the `result` shape based on
  Supervisor's actual payload).
- **CF-10:** Bridge reads `SUPERVISOR_TOKEN` on every outbound request via the RoundTrip function-pointer pattern
  (`internal/supervisor/client.go:84-91`). No new change.
- **CF-11:** STATE-02 enables HA backup integration coverage — Phase 9 spike §10 already proved `addon_config:rw`
  content is included in `ha backups new --app <slug>` output. The state index endpoint just makes the coverage
  observable from the Provider side.

### the agent's Discretion

- Exact internal package layout for the mutex manager (`internal/mutex/manager.go` with `TryAcquire/ Release` methods,
  or a smaller surface).
- Whether `nonce_entry` in cache stores the full nonce string or only `sha256[8]` (PITFALLS S-1 prefers hash, but memory
  cost of full 43-char nonce is negligible; agent's call).
- Whether `install_job_timeout_seconds` schema option is per-add-on (e.g., longer timeouts for known-slow add-ons) or
  single global value; default is single global with future per-slug override as a Phase 13+ concern.
- Whether `critical_addons` handler check short-circuits BEFORE or AFTER the per-slug mutex acquisition (Phase 12 plan
  MUST short-circuit BEFORE — documented decision; agent confirms in plan).

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research (HIGH confidence)

- `.planning/research/STACK.md` §"chi v5 middleware" — for new router signatures / handler registration patterns
- `.planning/research/STACK.md` §"Go: `sync` package (Mutex + Map + Pool)" — for the per-slug mutex map
- `.planning/research/PITFALLS.md` §"Pitfall S-1: SUPERVISOR_TOKEN leaked to logs" — invariant for nonce + audit code
- `.planning/research/PITFALLS.md` §"Pitfall S-3: CSRF" — informing the deferred CORS decision
- `.planning/research/PITFALLS.md` §"Pitfall §10: HA backup + addon_config" — STATE-02's empirical foundation
- `.planning/research/FEATURES.md` §"Open Question 6: tfstate in HA backups" — STATE-02 motivation
- `.planning/research/ARCHITECTURE.md` §"Layer 2: Provider → Bridge — destructive op flow" — write endpoints

### Repo conventions (HIGH confidence)

- `.planning/codebase/CONVENTIONS.md` — 120-char line length, YAML 2-space, snake_case option names
- `.pre-commit-config.yaml` — all hook names that Phase 12 must keep green
- `.yamllint.yml`, `.shellcheckrc`, `.markdownlint.json` — linter configs

### Precedent (HIGH confidence)

- `terraform-bridge/internal/httpapi/router.go` (Phase 11) — chi router signature, `/v1` auth subrouter pattern
- `terraform-bridge/internal/httpapi/handlers/addons.go`, `addon_info.go` (Phase 11) — new handler file template
- `terraform-bridge/internal/supervisor/client.go` (Phase 11) — method-extension pattern for new Supervisor calls
- `terraform-bridge/internal/supervisor/testing.go` (Phase 11) — `WithBaseURLForTest`, `TokenFnForTest` cross-package
  test helpers
- `terraform-bridge/contract/types.go` (Phase 11) — JSON type conventions (`error_code`, `omitempty`, RFC3339 strings)
- `terraform-bridge/internal/auth/token.go` (Phase 10) — atomic-write + chmod-600 + per-request-expiry patterns for the
  nonce audit journal (D-05)
- `terraform-bridge/internal/auth/middleware.go` (Phase 10) — `RequireBearer` chi middleware (inherited by all Phase-12
  mutating endpoints via the `/v1` subrouter)

### Phase 10/11 decisions carried forward (locked)

- `.planning/phases/10-auth-layer-structured-logging-healthcheck/10-CONTEXT.md` D-01..D-13 (token, grace, /healthz,
  bind-gate, two-layer log masking)
- `.planning/phases/10-auth-layer-structured-logging-healthcheck/10-CONTEXT.md` CF-01..CF-09 (auth invariants + slog
  convention + chi order + atomic file write + supervisor env re-read-per-call)
- `.planning/phases/11-bridge-read-api/11-VERIFICATION.md` — proven handler patterns, error-body shape, slog key
  convention
- `.planning/phases/11-bridge-read-api/11-01-SUMMARY.md` §"Auto-fixed Issues" — body-drain order pattern from
  supervisor.Client; Phase 12 supervisors methods MUST apply same drain discipline
- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-SUMMARY.md` — supervisor_api_v2 fallback decisions

### REQUIREMENTS traceability

- `.planning/REQUIREMENTS.md` §"BRIDGE — Bridge HTTP API" (BRIDGE-04, BRIDGE-05, BRIDGE-06, BRIDGE-07, BRIDGE-08,
  BRIDGE-09)
- `.planning/REQUIREMENTS.md` §"STATE — State & Concurrency" (STATE-02, STATE-03)
- `.planning/REQUIREMENTS.md` §"LIFE — Lifecycle & Safety" (LIFE-01, LIFE-03)

### Live hosts (HIGH confidence)

- `haos-op3050-1` — SSH-reachable LAN/Tailscale host for empirical Phase-14 E2E tests later
- `ha-nextgen` — alternative Tailscale host (per AGENTS.md Live-System rule, established in Phase 9)

### Live-system constraints (per AGENTS.md)

- `AGENTS.md` §"Live Systems — No Unsolicited Restarts / Service Disruption" — Phase 14 owns the live-HA install
  /uninstall exercise; Phase 12 verification is unit-test only. The empirical flow of
  `POST /v1/addons/X/install → poll /jobs/{id} → GET /apps/X/info` cannot be exercised in this dev container because
  there's no Supervisor the Bridge can be configured to talk to.

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `terraform-bridge/internal/supervisor/client.go` — Phase 11 added `GetSupervisorInfo`, `ListAddons`, `GetAddonInfo`.
  Phase 12 extends the SAME struct with `Install`, `Uninstall`, `Start`, `Stop`, `Options`, `ValidateOptions`,
  `GetJobStatus` + the `ErrAlreadyInstalled`, `ErrCriticalAddon`, `ErrLocked`, `ErrTransient`, `ErrPreventedDestroy`
  sentinels.
- `terraform-bridge/internal/supervisor/testing.go` (Phase 11) — `WithBaseURLForTest` + `TokenFnForTest` helpers. Phase
  12 reuses unchanged.
- `terraform-bridge/internal/auth/token.go` (Phase 10) — `TokenStore.Rotate` (Phase 10 plan 03) shows the
  atomic-write-with-chmod-600 + per-request-expiry pattern that `internal/nonce/journal.go` (D-05) reuses.
- `terraform-bridge/contract/types.go` — Phase 9 stub `JobStatus` + Phase 11 `AddOnInfo`, `VersionHandshake`,
  `ErrorResponse`, `TokenResponse`, `RotateResponse`, `HealthResponse`, `BridgeInfo`. Phase 12 adds `NonceResponse`,
  `StateIndexResponse`, `StateFileEntry`.
- `terraform-bridge/internal/httpapi/handlers/addons.go` (Phase 11) — handler template for V2/V1 fallback pattern, 3s
  ctx timeout, 502 + `upstream_error` on Supervisor failure, 200 + JSON on success. Phase 12 mutating handlers follow
  the same template (with nonce check + critical_addons check + mutex insert at the front).

### Established Patterns

- **Chi-middleware-inherited auth:** All Phase-12 mutating endpoints are mounted INSIDE the existing
  `r.Route("/v1", ...).Use(auth.RequireBearer(store))` block — Bearer check is implicit; handlers can assume
  `r.Context()` carries an authenticated principal.
- **Handler-file-per-endpoint convention:** Each Phase-11 endpoint = its own handler file with its own test file. Phase
  12 follows: `install.go`, `uninstall.go`, `start.go`, `stop.go`, `options.go`, `nonce.go`, `state_index.go` (7 new
  files).
- **Atomic file write with chmod 600:** From Phase 9 D-08 + Phase 10 plan 03's grace file. Phase 12 nonce audit journal
  uses the same pattern.
- **Slog key convention:** `bridge_<endpoint>_<event>` — Phase 11 introduced with `bridge_info_upstream_failed`. Phase
  12: `bridge_install_upstream_failed`, `bridge_uninstall_upstream_failed`, etc.
- **V2-preferred-then-V1-fallback for Supervisor calls:** Phase 11 encapsulated this in `supervisor.Client`. Phase 12's
  new methods (e.g., `Options(ctx, slug, opts)`) follow the same pattern — try V2, fall back to V1 on non-200. Same
  relaxed-fallback semantics as `GetAddonInfo` (V2-403 → V1-200 on already-installed could return ErrAlreadyInstalled).
- **ErrorResponse body shape:** `{"error_code": "...", "message": "..."}` — Phase 9 stub. Phase 12's new handlers emit
  exactly this; `Message` is empty for non-slug-echo'ing codes like `nonce_expired`.

### Integration Points

- **HA Supervisor's `/store/apps/{slug}/install`, `/apps/{slug}/uninstall`, `/apps/{slug}/start`, `/apps/{slug}/stop`,
  `/apps/{slug}/options`, `/jobs/{id}`, `/apps/{slug}/options/validate`** — Supervisor HTTP endpoints that Phase 12
  wraps via `supervisor.Client` methods. All require Bearer auth (auto-injected via the RoundTrip function-pointer).
- **HA add-on Options UI:** `config.yaml` schema gains `critical_addons` (list of str) and `install_job_timeout_seconds`
  (int, optional — defaults to 300) and `try_lock_timeout_seconds` (int, optional — defaults to 5). HA's persistent
  options store `/data/options.json` carries these across restarts.
- **Supervisor's `/jobs/{id}` polling:** Already exists (Phase 9 / 10 contracts referenced). Phase 12 polls it in a
  1-second-tick loop bounded by `install_job_timeout_seconds`.
- **Provider schema handshake:** Phase 11's `/v1/version` endpoint is the Configure-time version check; Phase 12's
  `/v1/auth/nonce` becomes the destruction-gate primitive in the Provider's Update + Delete paths.
- **Add-on volume `/data`:** persists `bridge-token`, `bridge-token.grace`, and now `bridge-nonce-audit.json`
  (append-only forensic journal).
- **HA backup integration (Phase 9 §10 spike result):** files under `/data` are auto-included in
  `ha backups new --app <slug>`. STATE-02's `GET /v1/state/index` is the Provider's way of observing what gets backed up
  without shell access.

</code_context>

<specifics>

## Specific Ideas

- **Critical_addons handler check should short-circuit BEFORE mutex acquisition.** Rationale: a malicious Provider
  request for `uninstall core_mosquitto` must be 403'd as cheaply as possible — never spend a 5s mutex-acquire timeout
  before rejecting. The check is just `_, blocked := slices.Contains(criticalAddons, slug); if blocked { return 403 }`.
  (The planner/agent MUST confirm this in the plan; if it can't justify BEFORE-mutex, document the trade-off.)
- **`/v1/auth/nonce` should be audit-logged at `slog.Info` (not Warn)** with `actor_token_fp` + `nonce_fp` +
  `request_id`. Issuance is normal operation, not an error.
- **`/v1/state/index` could expose `size_bytes` to help operators spot runaway state files** (e.g., a Provider bug that
  pushes 100MB of state); agent's call whether `size_bytes` is in.
- **The mutex map can grow unbounded if a buggy Provider targets thousands of slugs.** Phase 12 plan should consider: is
  the bound `len(map) <= 1000` ever exceeded in practice? Probably no; Phase 14 E2E will exercise the realistic scale.
  If unbounded growth becomes a concern, add a one-shot GC that prunes entries with no acquirer (> 5min stale). Out of
  Phase 12 scope.
- **`install_job_timeout_seconds` schema field is PER-BRIDGE-INSTANCE, not per-slug.** A long install of
  `core_zigbee2mqtt` vs `core_mosquitto` shares the same timeout. If per-slug overrides become a real need, Phase 13+
  can add `install_job_timeout_overrides: map[string]int`.

</specifics>

<deferred>

## Deferred Ideas

- **CSRF / OPTIONS preflight handling (PITFALLS S-3, originally Phase 12 scope in 10-CONTEXT):** The `X-Force-Destroy`
  nonce + the strict Tailscale-bind gate (Phase 10 D-04..D-06) cover the actual threat surfaces. PITFALLS S-3 CORS
  preflight is deferred to Phase 16 / Phase 2 (after Phase 15). Documented here so it doesn't get silently lost.
- **Atomic multi-resource transactions** (e.g., uninstall A then immediately install B as one logical op): out of Phase
  12 scope. The per-slug mutex serializes within a slug; cross-slug atomicity is the Provider's job via
  `terraform-plugin-framework-timeouts` + `lifecycle` blocks (Phase 13).
- **Auto-cancellation of stale install jobs** (e.g., if Provider closes mid-install, the Supervisor job might linger):
  Supervisor handles this internally per HA architecture. Out of Bridge scope.
- **Per-add-on timeout overrides** (`install_job_timeout_overrides: map<string,int>`): out of Phase 12 scope. Phase 13+
  if a real use case emerges.
- **`homeassistant_addon_repository` resource + critical_addons cross-check** (FEATURES OQ-1, deferred to v1.4): not
  relevant here.
- **TLS termination for plain-HTTP-on-Tailscale** (Phase 2 feature per PITFALLS S-4): Tailscale Serve handles this
  natively; Bridge does not.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 12` returned zero matches at context-gather time (the only open todo, "H-1
re-verification," is not Phase-12 scope and was reviewed as out-of-scope).

</deferred>

---

_Phase: 12-bridge-write-api-safety-concurrency-index_ _Context gathered: 2026-09-02_
