# Phase 10: Auth Layer + Structured Logging + Healthcheck - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-31
**Phase:** 10-auth-layer-structured-logging-healthcheck
**Areas discussed:** Token format + grace storage, Tailscale interface detection, /healthz probe strategy,
request_id + masking middleware, Rotation auth requirement + grace expiry check

---

## Token format + grace storage

| Option | Description | Selected |
|--------|-------------|----------|
| Token format: base64url, 43 chars (Recommended) | 32 random bytes → base64url; URL-safe; GitHub PAT / kubectl convention | ✓ |
| Token format: hex, 64 chars | 50% longer; no canonical advantage for opaque tokens | |
| Token format: base64 standard with padding | Adds padding hazards in env vars / YAML; base64url is strictly better | |
| Grace storage: separate file `/data/bridge-token.grace` (Recommended) | Primary hash at `/data/bridge-token`; previous hash moves to `.grace` with expiry; atomic writes via rename | ✓ |
| Grace storage: multi-line in single file | Partial-write risk; harder to `chmod 600` only the active hash | |
| Rotation response: `{new_token, grace_expires_at, old_token_valid_until}` (Recommended) | Caller updates stored token; old token keeps working until expiry; matches FEATURES.md | ✓ |
| Rotation response: only new_token | Loses explicit grace_expires_at signal for OpenTofu `lifecycle.precondition` | |

**User's choice:** All three recommended options.
**Notes:** User moved decisively through the questions; base64url and separate-file patterns are consistent with
Phase 9's existing file conventions (e.g. `/data/bridge-token` chmod 600 pattern).

---

## Tailscale interface detection

| Option | Description | Selected |
|--------|-------------|----------|
| Detection: `/sys/class/net` + interface name (Recommended) | Match `tailscale*` in `/sys/class/net`; zero deps; works on Alpine/busybox | ✓ |
| Detection: `tailscale ip -4` CLI | Requires `tailscale` CLI inside container; extra Dockerfile step | |
| Detection: parse `ip addr show tailscale0` | Brittle shell parsing | |
| Scope: interface name `tailscale*` only (Recommended) | Implicit CGNAT detection via Tailscale's automatic 100.x assignment | ✓ |
| Scope: interface name OR IP in 100.64.0.0/10 | Catches edge cases but harder to reason about | |
| Scope: strict tailscale0 + 100.64/10 | Breaks on customized interface names | |
| Override: refuse unless Tailscale IP (Recommended) | Strict reading of S-4; Phase 1 keeps discipline | (revised — see below) |

**User's choice:** `/sys/class/net` + interface name `tailscale*` only. Override behavior **revised** by user's
free-text input.
**Notes:** User asked (in German): "Da tofu potenziell von einem 192.168.x.x Geräte kommen kann, kann man vllt. eine
allow_list oder allow_subnet konfigurieren?" — i.e., since the Provider could run from a 192.168.x.x device, maybe
configure an `allow_list` or `allow_subnet`. Refined design captured as D-06: new `bind_allowed_subnets` option
(list of CIDRs, default `[]`) plus explicit rule that `bind_address: "0.0.0.0"` is always refused regardless. The
strict-refusal default stays; users opt into broader binding by listing subnets.

---

## /healthz probe strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Probe: hit Supervisor on every call (Recommended) | Always fresh; cheap localhost round-trip; honors ≤ 2s budget literally | ✓ |
| Probe: cache reachability with short TTL | Masks flapping for TTL window | |
| Probe: every-call + circuit breaker on repeated failures | Balances freshness vs load; complexity unwarranted for low-frequency polling | |
| 503 body: empty (Content-Length: 0) (Recommended) | Honors PITFALLS S-1 (error responses don't leak internal state) | ✓ |
| 503 body: `{error_code: "supervisor_unreachable"}` JSON | Consistent with AUTH-03 typed-error precedent | |
| 503 body: full upstream Supervisor error | Diverges from S-1 | |

**User's choice:** Probe on every call; empty 503 body.
**Notes:** Two recommendations on the same area gave the user a coherent "fresh + minimal" stance — appropriate for
a liveness probe that should be boring.

---

## request_id + masking middleware

| Option | Description | Selected |
|--------|-------------|----------|
| request_id: chi `middleware.RequestID` + crypto/rand UUID v4 fallback (Recommended) | Honors inbound X-Request-Id for external tracing; cryptographic fallback for fresh IDs | ✓ |
| request_id: ULID via onsi/golang-ulid | Sortable but adds dep; marginal value for single-process log | |
| request_id: always fresh crypto/rand UUID | Avoids spoofing but loses correlation with upstream traces | |
| Mask: slog Handler wrapper (Recommended) | Catches every slog call site; consistent across all log paths | ✓ |
| Mask: chi middleware scrubs before logging | Misses direct `slog.Info("token", token)` in handlers | |
| Mask: grep-style post-hoc scrub | Brittle; misses structurally subtle leaks | |
| Test: bytes.Buffer + crafted headers assertion (Recommended) | Unit-testable; fast; covers both attribute and header paths | ✓ |
| Test: integration test against running container | Slower; harder to maintain | |
| Test: both unit + integration | Strongest but heaviest | |

**User's choice:** chi middleware.RequestID + slog Handler wrapper + bytes.Buffer unit test. All three recommended
selections.
**Notes:** Two-layer masking (slog Handler + chi middleware) is captured as D-10 even though the question wording
showed a single-option choice — the wrapper alone misses inbound header values, so both layers are needed for
D-11's test invariant to hold under all log paths.

---

## Rotation auth requirement + grace expiry check

| Option | Description | Selected |
|--------|-------------|----------|
| /v1/auth/rotate auth: require existing valid bearer (Recommended) | Standard practice; total loss recovery = uninstall + reinstall | ✓ |
| /v1/auth/rotate auth: no auth on rotation | Anyone on Tailscale can lock out the Provider | |
| /v1/auth/rotate auth: optional break-glass string | Recovers from total loss without uninstall but adds config surface | |
| Grace expiry: check per-request (Recommended) | One clock read per request; no goroutine lifecycle | ✓ |
| Grace expiry: background ticker deletes grace file | Less per-request work; introduces goroutine + SIGTERM lifecycle | |

**User's choice:** Both recommended.
**Notes:** The "require existing bearer" choice has a real cost (total token loss = reinstall), but the user
accepted that trade-off in exchange for stricter security posture. Recovery procedure documented in DOCS.md per
the specifics section of CONTEXT.md.

---

## the agent's Discretion

Captured in CONTEXT.md §"the agent's Discretion":

- Exact chi middleware order (RequestID → request-logger → Recoverer vs other permutations)
- Cache-Control headers on `/healthz` and `/v1/auth/rotate`
- Exact ISO-8601 format for `grace_expires_at` and `old_token_valid_until`
- Audit log line shape for the rotation event
- Scrub-list semantic (key-name based vs substring)

---

## Deferred Ideas

Captured in CONTEXT.md §"Deferred Ideas":

- CSRF nonces (S-3) — Phase 12
- `critical_addons` list (LIFE-01) — Phase 12
- `X-Force-Destroy` nonce (LIFE-03) — Phase 12
- Per-slug write mutex (STATE-03) — Phase 12
- Auto-rotation cadence — Phase 2+ (manual only by default per Phase 9 deferred-ideas)
- Provider integration test for rotation — Phase 13
- Tailscale HTTPS termination — v1.5
- `homeassistant_addon_repository` resource — v1.4
