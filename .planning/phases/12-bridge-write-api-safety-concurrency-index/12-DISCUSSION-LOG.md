# Phase 12: Discussion Log

**Phase:** 12-bridge-write-api-safety-concurrency-index **Gathered:** 2026-09-02 **Milestone:** v1.3 opentofu-bridge

## Areas discussed

### Area A — Force-Destroy-Nonce storage + TTL

**Question:** Wo lebt das nonce-state? In-memory map, /data persistiert, oder hybrid?

**Options presented:**

1. **In-Memory (lost on restart)** — simple, no I/O on hot path, GC in 30s
2. **/data/bridge-nonce.json (survives restart)** — survives Bridge restart, costs file-rotation
3. **Hybrid: in-memory cache + /data audit journal (append-only)** — two layers, single-use tracking in memory +
   forensics via append journal

**User choice:** Option 3 — Hybrid

**Notes:** Practical compromise. Single-use tracking stays in-memory (clean, no race with filesystem); journal captures
`nonce_fp`, `actor_token_fp`, `request_id`, `issued_at`, `used_at` for forensics. Nonce lost on restart = caller sees
`401 nonce_expired` and re-requests via `POST /v1/auth/nonce`. With 60-second TTL the cost is negligible.

**Captured decisions:** 12-CONTEXT.md §D-05 (storage), §D-06 (lifecycle), §D-07 (GC), §D-08 (restart-loss rationale)

---

### Area B — Critical_Addons enforcement scope

**Question:** Welche Operations werden für kritische Add-ons blockiert?

**Options presented:**

1. **Konservativ: uninstall + options-change** — middle-ground; start/stop/info bleiben offen
2. **Aggressiv: alle mutating ops** (incl. stop) — strikter, weniger operativer Freiraum
3. **Whitelist + Ops-Granularität als schema option** — Operator konfigurierbar; default
   `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`

**User choice:** Option 3 — Whitelist + schema option

**Notes:** `critical_addons` als list-schema-field im add-on options. Operator kann die Liste anpassen oder leeren (leer
= Schutz disabled). Blockierte Ops: uninstall + options-change (per Phase-12 ROADMAP.md SC-3). Start/Stop/Reads/ Install
bleiben offen. Trade-off: mehr Konfiguration-Komplexität gegen Operator-Flexibilität.

**Captured decisions:** 12-CONTEXT.md §D-09 (schema), §D-10 (blockierte Ops), §D-11 (Hander-Placement)

---

### Area C — Per-Slug Mutex + Deadlock-Strategie

**Question:** Wie verhindern wir Deadlocks im per-slug mutex-Modell?

**Options presented:**

1. **Alphanumeric sort (einfach, formal beweisbar)** — multi-slug ops lock alphabetically; kein Timeout
2. **Single-flight queue + cancellation** — channel per slug; FIFO + simple, aber kein cross-slug parallelism
3. **Map + per-request timeout** — `TryLock(5s)` returns 423 on miss; Provider retry per timeouts

**User choice:** Option 3 — Map + per-request timeout

**Notes:** Per-slug `map[string]sync.Mutex` mit 5s default try-lock. Bei miss: `423 error_code: locked`. Vermeidet
deadlocks ohne globale lock-order-constraint. Trade-off: zusätzlicher Code in `TryAcquire` (goroutine + select on ctx),
aber Provider-side terraform-plugin-framework-timeouts (Phase 13) sind der outer guard.

**Captured decisions:** 12-CONTEXT.md §D-12 (map structure), §D-13 (TryAcquire semantics), §D-14 (per-slug only), §D-15
(single-request scope), §D-16 (reads excluded)

---

### Area D — Supervisor-Job polling timeout + interval

**Question:** Wie soll Bridge Supervisor-jobs pollen?

**Options presented:**

1. **Linear poll, 5min Default** — simple, robust, fits install-types ≤ 5min
2. **Exponential backoff, 10min Default** — more flexible for slow add-ons, more complex
3. **Linear poll, konfigurierbar per option** — operator tunes per-deployment

**User choice:** Option 3 — Linear poll + per option configurable

**Notes:** Linear poll (1s tick) bounded by `install_job_timeout_seconds` add-on option (default 300 = 5min).
Provider-side timeout (terraform-plugin-framework-timeouts, default 10m Phase 13) ist outer guard. Trade-off: schema
complexity vs deployment flexibility.

**Captured decisions:** 12-CONTEXT.md §D-17 (polling loop), §D-18 (placement — handler, not client), §D-19 (only install
polls; uninstall/start/stop are sync)

---

### Area E — State-Index scope

**Question:** Welche Dateien indexiert `/v1/state/index`?

**Options presented:**

1. **terraform.tfstate (+ backup immer)** — single-workflow default; minimal
2. **Glob _.tfstate + *.tfstate.backup*_ — multi-state-workflow support
3. ***.tfstate (ohne backup)** — Phase 1 minimal; defer backup listing

**User choice:** Option 2 — Glob *.tfstate + *.tfstate.backup

**Notes:** Multi-state-workflow support out of the box. SHA-256 über alle files. Skip `*.tfstate.lock` (ephemeral).
Trade-off: etwas mehr SHA-256 compute, aber für HA-Backup-coverage-Beweis ist das Minimum.

**Captured decisions:** 12-CONTEXT.md §D-20 (scope), §D-21 (response shape), §D-22 (`internal/state/` package), §D-23
(per-file error handling), §D-24 (GET only)

---

## Deferred Ideas

- **CSRF / OPTIONS preflight (PITFALLS S-3):** The `X-Force-Destroy` nonce + strict Tailscale-bind gate cover the threat
  surfaces. CORS preflight deferred to Phase 16 / Phase 2. Captured in 12-CONTEXT.md §"Deferred Ideas".
- **Per-add-on install-timeout overrides:** Single global for Phase 12; Phase 13+ if needed.

## Cross-Phase Coordination

- **Reuse from Phase 11:** `supervisor.Client` pattern, contract type conventions, chi `/v1` auth subrouter, slog key
  convention, error body shape. Documented in 12-CONTEXT.md §CF-01..CF-11.
- **Reuse from Phase 10:** atomic-write + chmod-600 + per-request-expiry pattern (for the nonce audit journal).
- **Reuse from Phase 9:** supervisor_api_v2 fallback machinery + the empirical H-1 / §10 spike results.

## Open items for downstream agents

- Phase 12 **planner** must place `critical_addons` check BEFORE mutex acquisition (per CF-explicit section + Specifics
  item).
- Phase 12 **executor** must commit the journal entry to disk atomically (not with deferred fsync that loses data on
  crash).
- Phase 12 **planner** must verify that `/v1/auth/nonce` is itself auth-required (otherwise anon nonce issuance =
  trivial CSRF bypass).
- Phase 13 **planner** (next phase) will reference 12-CONTEXT.md §"the agent's Discretion" for adopt_409 semantics
  - provider-side installation flow integration.
