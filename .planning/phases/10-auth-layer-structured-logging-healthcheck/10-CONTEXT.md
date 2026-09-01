# Phase 10: Auth Layer + Structured Logging + Healthcheck - Context

**Gathered:** 2026-08-31 **Milestone:** v1.3 opentofu-bridge **Status:** Ready for planning

<domain>

## Phase Boundary

Land the Bridge's bearer-token authentication primitive (generation, validation, rotation with grace), structured JSON
logging with masking guarantees, `/healthz` endpoint, and bind-address enforcement on top of the Phase 9 scaffold. Every
later v1.3 phase depends on this being secure by construction.

Specifically this phase delivers: `crypto/rand`-generated 256-bit bearer token, SHA-256 hash persisted at
`/data/bridge-token` with `chmod 600`, `crypto/subtle.ConstantTimeCompare` validation, `POST /v1/auth/rotate` with a
24-hour grace window, structured per-request logs with mandatory OPS-01 fields, `GET /healthz` probing Supervisor, and a
bind-address gate that refuses non-Tailscale listeners unless an explicit subnet allow-list permits them.

**What this phase is NOT:** the read API (`/v1/version`, `/v1/addons`, `/v1/info` — Phase 11), write API + critical-
addon guard + per-slug mutex + force-destroy nonce (Phase 12), Provider resource skeletons (Phase 13), operator docs
(Phase 14), CI hardening (Phase 15). All of those land later.

</domain>

<decisions>

## Implementation Decisions

### Token issuance, format, and grace storage (Area 1)

- **D-01:** Plaintext token encoding = **base64url, 43 chars** (32 random bytes via `crypto/rand`). Matches the
  `kubectl create token` / GitHub PAT convention. URL-safe (no `+/=` chars) so it survives env vars, YAML strings, and
  HTTP headers without escaping. User pastes this verbatim into the Provider's `bearer_token` argument.
- **D-02:** Grace storage = **separate file** `/data/bridge-token.grace` containing `{prev_hash, grace_expires_at}`.
  Atomic via `chmod 600` + rename pattern. Primary hash stays in `/data/bridge-token`; grace file only exists when grace
  is active (deleted when grace_expires_at is past).
- **D-03:** `POST /v1/auth/rotate` response payload = `{new_token, grace_expires_at, old_token_valid_until}`. Both grace
  fields carry the same ISO-8601 instant; redundant on purpose so Provider consumers can use whichever the OpenTofu
  schema prefers without an extra hop.

### Tailscale interface detection + bind-address enforcement (Area 2)

- **D-04:** Tailscale detection = **`/sys/class/net` lookup** for any interface whose name starts with `tailscale`. No
  shell-out to `tailscale` CLI; no parsing of `ip addr`; works on Alpine/busybox without extra packages.
- **D-05:** What counts as a Tailscale interface = **interface name `tailscale*` only**. CGNAT range matching
  (100.64.0.0/10) is implicit because Tailscale always assigns 100.x; we don't double-check.
- **D-06:** New add-on option **`bind_allowed_subnets`** (list of CIDR strings, default `[]`) broadens the bind gate
  beyond Tailscale for setups where the Provider runs on a LAN device that can't reach Tailscale. Behavior:
  - `bind_address: "auto"` (default) — auto-detect the Tailscale IP via D-04.
  - `bind_address: "<explicit-IP>"` — accepted only if the IP belongs to a Tailscale interface (D-04) **or** falls
    inside one of the configured subnets in `bind_allowed_subnets`. Each entry is logged at startup
    (`bridge.listening=... iface=... subnet_allowed=192.168.0.0/16`).
  - `bind_address: "0.0.0.0"` is **always refused** at startup regardless of `bind_allowed_subnets`. This honors
    PITFALLS S-4 ("never bind to all interfaces without an explicit allow-list"); Phase 1 keeps the strict posture.
  - Startup refusal logs a clear error naming the refused address and the rationale. Per AGENTS.md "Live Systems" rule,
    the Bridge does not start at all when the configured bind is unsafe — no degraded mode.

### /healthz probe strategy (Area 3)

- **D-07:** `GET /healthz` makes a **real `GET /supervisor/ping` call on every request** with a 2-second timeout. No
  caching. Supervisor ping is a cheap localhost round-trip; freshness matters more than p99 reduction for a tool polled
  by HA Supervisor at low frequency.
- **D-08:** **503 body = empty** (`Content-Length: 0`). Honors PITFALLS S-1 (error responses never leak internal state).
  Status code alone signals "Supervisor is down"; operator digs into HA logs for details.

### request_id + log masking (Area 4)

- **D-09:** `request_id` source = **chi's built-in `middleware.RequestID`** (honors inbound `X-Request-Id` from upstream
  proxies if present) with **crypto/rand UUID v4 fallback** when no inbound header is present. Honors external tracing
  while not blindly trusting spoofed headers. Stored in `r.Context()`; logger middleware reads it from context, not from
  `r.Header`.
- **D-10:** Log masking = **two layers**:
  1. A custom **`slog.Handler` wrapper** that scrubs sensitive keys (`Authorization`, `Bearer`, `bridge_token`,
     `SUPERVISOR_TOKEN`, `supervisor_token`, `bearer`, `token`, `password`) before serializing each record to JSON.
     Catches every `slog.Info/Error/Debug` call site.
  2. A chi middleware that **strips `Authorization` from the `r.Header` snapshot** before the request-logging middleware
     reads it; the request log only sees the scrubbed copy.
- **D-11:** AUTH-05 invariant unit test = a `bytes.Buffer` wired to the slog handler wrapper; a test runs handlers that
  emit crafted `Authorization`, `bridge_token`, `SUPERVISOR_TOKEN` keys (and a request carrying an
  `Authorization: Bearer <sentinel>` header) through the full middleware stack; assertion is that none of
  `{Authorization, Bearer, bridge_token, SUPERVISOR_TOKEN, <sentinel>}` substrings appear in the captured output.

### Rotation auth requirement + grace expiry check (Area 5)

- **D-12:** `POST /v1/auth/rotate` **requires an existing valid bearer token** (the same one used for any other
  authenticated endpoint). No anonymous rotation, no break-glass option in Phase 1. Recovery from total token loss =
  uninstall + reinstall the add-on (which forces fresh token generation on next start); documented in DOCS.md. The grace
  semantics mean an in-flight rotate cannot lock out a still-valid token within the 24-hour window.
- **D-13:** Grace expiry is **checked per-request** by comparing `time.Now().After(grace_expires_at)`. No background
  goroutine, no ticker, no file deletion on expiry — the file just becomes irrelevant. When grace expires, the next
  request with the old token reads `grace_expires_at`, sees it's past, and returns 401.

### Carried forward from REQUIREMENTS.md + Phase 9 CONTEXT (locked, not re-discussed)

- **CF-01:** Token generation = `crypto/rand` (32 bytes), at-rest hash = `crypto/sha256`, validation =
  `crypto/subtle.ConstantTimeCompare`. (STACK.md §Auth Library; Phase 9 D-11.)
- **CF-02:** Token file `/data/bridge-token` with `chmod 600`. Plaintext surfaces exactly once via add-on log (slog JSON
  record with a one-time marker) AND the Options UI; subsequent restarts do NOT re-surface.
- **CF-03:** 401 error body = `{"error_code": "unauthorized"}`. No upstream request body, no env, no token, no
  `request_id` echoed in the error body.
- **CF-04:** OPS-01 mandatory log fields per request: `ts`, `level`, `msg`, `request_id`, `route`, `method`, `status`,
  `duration_ms`. Single JSON object per line.
- **CF-05:** Logger = stdlib `log/slog` with `NewJSONHandler(os.Stdout, nil)`. Zero external deps for logging.
- **CF-06:** Router = chi v5 (already wired in Phase 9 at `terraform-bridge/internal/httpapi/router.go`). Middleware
  order: RequestID → Recoverer → request-logging → (per-route auth).
- **CF-07:** Bind = `:8124` (port 8124/tcp); the address component is what `bind_address` / `bind_allowed_subnets`
  decide. `config.yaml` already declares `ports: 8124/tcp: 8124` (Phase 9 D-09).
- **CF-08:** `run.sh` does bashio setup then `exec /usr/bin/bridge`; binary owns its own stdout (Phase 9 D-10).
- **CF-09:** No CORS handling in Phase 10. S-3 (CSRF nonces, OPTIONS preflight) is a Phase 12 concern.

### the agent's Discretion

- Exact chi middleware order (RequestID → request-logger → Recoverer vs other permutations) — must satisfy CF-04 and
  CF-06.
- Whether `/healthz` returns `Cache-Control: no-store` (defensive) — agent's call; not in any locked requirement.
- Whether `/v1/auth/rotate` returns `Cache-Control: no-store` — same; default yes.
- Exact ISO-8601 format for `grace_expires_at` and `old_token_valid_until` (RFC 3339 with `Z` is the natural choice).
- Audit log line shape for the rotation event (`msg`, `actor_token_fp`, `old_token_fp`, `grace_expires_at`,
  `request_id`) — locked fields are the four listed; field naming is the agent's call.
- The single-scrub-list semantic: whether "Bearer" substring scrub triggers false positives on a legit log message that
  mentions "Bearer" (e.g., a future bridge debug log) — agent's call: scope the scrub to key-name based, not arbitrary
  substring; this is safer.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research (HIGH confidence)

- `.planning/research/STACK.md` §"Authentication middleware (custom)" (~20 LoC chi middleware with
  `ConstantTimeCompare`)
- `.planning/research/STACK.md` §"Auth Library: stdlib (`crypto/rand`, `crypto/subtle`) + `argon2id` for at-rest
  hashing" (32 bytes → base64url token, SHA-256 at rest, ConstantTimeCompare; argon2id NOT in Phase 1)
- `.planning/research/STACK.md` §"Why chi over stdlib net/http and others" (chi v5.3.2 chosen; RequestID middleware
  built-in)
- `.planning/research/PITFALLS.md` §"Pitfall S-1: SUPERVISOR_TOKEN leaked to Provider logs or error bodies" (re-auth
  invariant)
- `.planning/research/PITFALLS.md` §"Pitfall S-2: Bridge bearer token reuse after rotation" (24h grace + rotation hint)
- `.planning/research/PITFALLS.md` §"Pitfall S-3: CSRF on the Bridge HTTP API" (Phase 12 scope; not in Phase 10)
- `.planning/research/PITFALLS.md` §"Pitfall S-4: Bearer-token auth over plain HTTP only on internal Tailscale" (bind
  rule)
- `.planning/research/FEATURES.md` §"Open Question 7" (plain HTTP on Tailscale resolved; Phase 1 keeps strict bind)
- `.planning/research/ARCHITECTURE.md` §"Layer 2: Provider → Bridge" (token issuance lifecycle + grace semantics)
- `.planning/research/SUMMARY.md` §"Token compare" (ConstantTimeCompare vs SHA-256 hash)

### Repo conventions (HIGH confidence)

- `.planning/codebase/CONVENTIONS.md` — 120-char line length, YAML 2-space indentation, quoted strings for versions,
  snake_case for option names with logical prefix grouping
- `.pre-commit-config.yaml` — pre-commit hook chain (Phase 10 extends `internal/verify-bridge-no-token-leak.sh` from
  Phase 9 D-12 to assert the OPS-01 + AUTH-05 invariant more strongly)
- `.yamllint.yml`, `.shellcheckrc`, `.markdownlint.json` — linter configs

### Precedent (HIGH confidence)

- `authentik/Dockerfile` — multi-stage Go binary + HA base image pattern (already in Phase 9)
- `authentik/config.yaml` — `map: addon_config:rw` precedent (already in Phase 9)
- `authentik/run.sh` — bashio + `exec` pattern (already in Phase 9)
- `terraform-bridge/internal/httpapi/router.go` — Phase 9 chi router scaffold; Phase 10 extends in-place
- `terraform-bridge/internal/supervisor/token.go` — Phase 9 env reader; Phase 10 wraps in a Supervisor HTTP client
- `terraform-bridge/cmd/bridge/main.go` — Phase 9 bind `:8124`; Phase 10 replaces with bind_address logic
- `terraform-bridge/Dockerfile` — already has multi-stage build (Phase 9 D-07 / D-08)
- `internal/validate-versions.sh` — TOFU-05 cross-artifact version sync (Phase 9 D-20; no change in Phase 10)
- `internal/verify-bridge-no-token-leak.sh` — Phase 9 D-12 redaction assertion; Phase 10 strengthens with full AUTH-05
  invariant test

### Phase 9 decisions carried forward (locked)

- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-CONTEXT.md` §"D-08" (config.yaml
  `map: addon_config:rw`)
- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-CONTEXT.md` §"D-10..D-13" (logging baseline)
- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-CONTEXT.md` §"D-18..D-19" (H-1 + §10 spike results flow
  into Phase 10's env-reads-every-call pattern)
- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-DISCUSSION-LOG.md` (decision trail; audit reference)

### REQUIREMENTS traceability

- `.planning/REQUIREMENTS.md` §"AUTH — Auth & Security" (AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-07 — Phase 10 scope;
  AUTH-01, AUTH-06 already done in Phase 9)
- `.planning/REQUIREMENTS.md` §"OPS — Operations" (OPS-01, OPS-03 — Phase 10 scope; OPS-02, OPS-05 already in Phase 9)

### Live hosts (HIGH confidence)

- `haos-op3050-1` — SSH-reachable LAN/Tailscale host; H-1 spike target (Phase 9 D-14; deferred-execution per 09-SUMMARY)
- `authentik` add-on (already installed on a host) — §10 spike target via `map: addon_config:rw` (Phase 9 D-16)

### Live-system constraints (per AGENTS.md)

- `AGENTS.md` §"Live Systems — No Unsolicited Restarts / Service Disruption" — Phase 10 verification runs against a stub
  Bridge-shaped add-on (Phase 9 D-15 procedure); Supervisor restart requires explicit per-call authorization.

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `terraform-bridge/internal/httpapi/router.go` — chi router scaffold with single `GET /` (Phase 9). Phase 10 extends
  in-place: adds `RequestID`, `Recoverer`, request-logging middleware, plus routes `/healthz` (no auth),
  `/v1/auth/rotate` (auth-required), and (future) `/v1/*` placeholders (Phase 11+).
- `terraform-bridge/internal/supervisor/token.go` — `ReadSupervisorToken()` env reader (Phase 9). Phase 10 wraps in a
  `SupervisorClient` struct that takes the token-read function as a constructor arg so tests can inject a fake without
  touching env.
- `terraform-bridge/contract/types.go` — shared JSON types (Phase 9). Phase 10 adds `ErrorResponse` (with `ErrorCode`
  field), `RotateResponse`, `HealthResponse`, and `LogFields` constants.
- `internal/verify-bridge-no-token-leak.sh` — Phase 9 D-12 assertion script. Phase 10 strengthens with explicit AUTH-05
  unit test in Go (`internal/auth/handler_test.go` or similar); shell script keeps the integration-style check for "no
  token-like substrings in container stdout".
- `authentik/run.sh` — bashio + `exec` template; already mirrored in `terraform-bridge/run.sh` (Phase 9).

### Established Patterns

- **chi middleware chain pattern:** `r.Use(middleware.RequestID)` → `r.Use(middleware.Recoverer)` →
  `r.Use(requestLogger)` → per-route auth. Mirrors `STACK.md` §"Why chi" rationale.
- **`slog.Default()` + custom handler wrapper:** Phase 9 calls `slog.SetDefault(logger)` once in `main.go`. Phase 10
  replaces `NewJSONHandler(os.Stdout, nil)` with a wrapping `slog.NewJSONHandler(os.Stdout, ...)` then a
  `scrubbingHandler` that pre-filters sensitive keys before the inner handler serializes. The public `slog.*` API stays
  unchanged; only the underlying handler changes.
- **Atomic file write with `chmod 600`:** Phase 9 token file is `/data/bridge-token`; Phase 10 adds
  `/data/bridge-token.grace` using the same atomic-rename pattern (`tmpfile.Write → os.Rename(tmp, final)` then
  `os.Chmod(final, 0600)`).
- **Supervisor env re-read on every call:** Phase 9 `ReadSupervisorToken()` already does `os.Getenv` per call (per D-18
  contingency for H-1 token-rotation). Phase 10 Supervisor client reuses this pattern at the HTTP call level — no
  caching of the outbound client.

### Integration Points

- **HA Supervisor (`/supervisor/ping`):** used by `/healthz`. Bridge reads `SUPERVISOR_TOKEN` via the existing
  env-reader, builds an `http.Client` with `Authorization: Bearer <token>` injected via a custom `Transport`, calls
  `http://supervisor/ping` with a 2s timeout.
- **HA add-on Options UI:** `config.yaml` `schema:` block expands from `{}` (Phase 9) to declare `bind_address` and
  `bind_allowed_subnets`. The token itself appears in the Options UI via a "sensitive" field marker so HA redacts it
  from cloud backup.
- **HA Supervisor's health-check:** HA Supervisor polls `/healthz` for liveness; the success criterion depends on this
  endpoint returning 200 within budget. Phase 10 surfaces `503` only when Supervisor itself is unreachable, not when
  Bridge can't talk to the Provider.
- **Pre-commit + verify scripts:** `internal/verify-bridge-no-token-leak.sh` extends; new
  `internal/verify-bridge-auth.sh` exercises /healthz + /v1/auth/rotate round-trip end-to-end.
- **Add-on volume `/data`:** persists `/data/bridge-token` and `/data/bridge-token.grace` across restarts;
  `/data/options.json` carries `bind_address` and `bind_allowed_subnets` (HA's persistent add-on options store).

</code_context>

<specifics>

## Specific Ideas

- The "exactly once" plaintext surfacing should log a single, distinct slog record that an operator can grep for
  (suggested `msg: "bridge.token.issued"` with `actor_token_fp: <sha256[8]>` for traceability). Subsequent restarts log
  `msg: "bridge.token.loaded"` without surfacing the plaintext — explicit distinction so an operator can tell "fresh
  install" from "normal restart" at a glance.
- The `/healthz` 503 path should log a single `slog.Warn` record with `supervisor.ping_failed=true` and the underlying
  error message BEFORE writing the 503 response — gives operators a forensic trail without leaking the error to the
  health-check caller.
- The `bind_allowed_subnets` option is a Phase-1 escape hatch for "Provider on a non-Tailscale LAN device". It is
  intentionally narrower than just `bind_address: "0.0.0.0"` so the operator has to type out each subnet they intend to
  expose — disincentivizes "open everything" reflex.
- D-06's "always refuse `0.0.0.0`" is the strict reading of PITFALLS S-4. Phase 2 may revisit if the user adopts
  Tailscale Serve or a CF Access path.
- D-12's "rotate requires existing bearer" leaves a recovery gap for total token loss. The recovery path (uninstall +
  reinstall add-on) is documented in DOCS.md alongside the rotation procedure.

</specifics>

<deferred>

## Deferred Ideas

- **CSRF nonces (S-3, Phase 12):** OPTIONS preflight handling, `X-CSRF-Token` for state-mutating endpoints. Phase 10
  does NOT add CORS / OPTIONS handling — that's the Phase 12 critical-addon / force-destroy-nonce work.
- **`critical_addons` list (LIFE-01, Phase 12):** not in Phase 10 scope.
- **`X-Force-Destroy` nonce (LIFE-03, Phase 12):** not in Phase 10 scope.
- **Per-slug write mutex (STATE-03, Phase 12):** not in Phase 10 scope (no write endpoints yet).
- **Auto-rotation cadence (S-2 prevention):** Phase 9 deferred-ideas note says "manual only by default". Phase 10 ships
  manual rotation; optional schedule via add-on option is Phase 2+ per FEATURES.md.
- **Provider integration test for rotation (S-2 detection):** Phase 13 (alongside Provider schema).
- **Tailscale HTTPS termination (PITFALLS S-4 Phase 2):** deferred to v1.5 per REQUIREMENTS.md out-of-scope.
- **`homeassistant_addon_repository` resource (FEATURES.md OQ-1):** deferred to v1.4; not relevant here.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 10` returned zero matches. Nothing from the existing backlog is being silently
dropped.

</deferred>

---

_Phase: 10-auth-layer-structured-logging-healthcheck_ _Context gathered: 2026-08-31_
