# Research Summary: v1.3 opentofu-bridge

**Project:** homeassistant-addons / v1.3 opentofu-bridge
**Domain:** HA add-on (Bridge) + co-located Go Terraform/OpenTofu provider, exposing Supervisor HTTP API as versioned JSON for declarative add-on management
**Researched:** 2026-08-31
**Confidence:** HIGH for stack/architecture/feature surface; MEDIUM for V1/V2 Supervisor endpoint timeline; LOW for Supervisor-token-rotation-across-restart behaviour (empirical spike required)

---

## Summary

This milestone ships **two artifacts** from one repo: `terraform-bridge/` — an HA Supervisor add-on that wraps the
Supervisor HTTP API as a bearer-token-protected, versioned JSON-over-HTTPS service; and `terraform-provider-homeassistant/` —
a Go module that consumes that JSON via the `terraform-plugin-framework` so users can manage `homeassistant_addon`
resources declaratively in `*.tf` files. Both share the repo's 3-file versioning scheme (`config.yaml` subpatch +
`build.yaml` + README badge) and ship from one versioned release. Phase-1 scope (already fixed in PROJECT.md) covers
the `homeassistant_addon` resource (install / start / stop / uninstall / options CRUD) plus the bridge itself, bearer
auth, schema versioning, idempotent reads, and import. Two distinct auth flows exist and must not be confused:
**Bridge → Supervisor** uses the auto-injected `SUPERVISOR_TOKEN` (verified via `supervisor/api/middleware/security.py`);
**Provider → Bridge** uses a long-lived bearer that the Bridge generates at first startup and stores in
`/data/bridge-token` (chmod 600). Green-field provider — no existing `terraform-provider-homeassistant` exists on
GitHub, the Terraform Registry, or the OpenTofu Registry (verified).

---

## Stack Decisions

| Concern | Choice | Version | Rationale | Source |
|---|---|---|---|---|
| **Bridge language** | Go (single static binary) | go 1.25 | Schema types **shared** with Provider via Go submodule (drift caught at `go build`); same toolchain in CI; ~12 MiB static binary on HA base Alpine | [STACK.md#why-go](.planning/research/STACK.md) |
| **Bridge base image** | `ghcr.io/home-assistant/amd64-base` | 3.24 (Alpine 3.24) | Smallest footprint; no Python/Node runtime needed | [STACK.md](.planning/research/STACK.md) |
| **Bridge build stage** | `golang:1.25-alpine` | multi-stage | Standard `COPY --from` pattern (precedent: authentik Dockerfile) | [STACK.md](.planning/research/STACK.md) |
| **HTTP router** | `github.com/go-chi/chi/v5` | v5.3.2 | Stdlib-compatible, ~1000 LOC, modular middleware (RequestID, Recoverer, Logger, Timeout); mirrors Supervisor URL hierarchy | [pkg.go.dev/go-chi/chi/v5](https://pkg.go.dev/github.com/go-chi/chi/v5) |
| **JSON** | stdlib `encoding/json` | stdlib | Sufficient for JSON Schema emission | [STACK.md](.planning/research/STACK.md) |
| **Supervisor client** | roll-your-own `net/http` | stdlib | No Go client exists (verified via pkg.go.dev); ~10 endpoints ≈ 200-300 LoC; injected `SUPERVISOR_TOKEN` from env | [STACK.md](.planning/research/STACK.md) |
| **Token generation** | `crypto/rand` (256-bit) | stdlib | Random secrets; no KDF needed | [STACK.md](.planning/research/STACK.md) |
| **Token compare** | `crypto/subtle.ConstantTimeCompare` | stdlib | Timing-safe against hashed-on-disk form | [STACK.md](.planning/research/STACK.md) |
| **Token-at-rest hashing** | `crypto/sha256` | stdlib | Sufficient for random secrets (argon2 reserved for future password-derived use) | [STACK.md](.planning/research/STACK.md) |
| **Provider framework** | `github.com/hashicorp/terraform-plugin-framework` | v1.19.0 (MPL-2.0, protocol 6) | HashiCorp-recommended for new providers; typed schema eliminates SDKv2 panics | [pkg.go.dev/terraform-plugin-framework](https://pkg.go.dev/github.com/hashicorp/terraform-plugin-framework) |
| **Provider scaffolding** | `providerserver.Serve()` | transitive | Standard plugin entry point | [STACK.md](.planning/research/STACK.md) |
| **Timeouts module** | `terraform-plugin-framework-timeouts` | matches framework | `terraform-plugin-framework` 1.x feature | [developer.hashicorp.com/.../timeouts](https://developer.hashicorp.com/terraform/plugin/framework/resources/timeouts) |
| **State backend** | OpenTofu local backend → `/data/terraform.tfstate` | OpenTofu ≥ 1.12 | Bridge does **not** touch tfstate; CLI handles locking (`flock` on local file) | [STACK.md](.planning/research/STACK.md), [opentofu.org/docs/intro/whats-new](https://opentofu.org/docs/intro/whats-new/) |
| **OpenTofu compatibility** | 1.12+ | verified | Protocol v5 (SDKv2) and v6 (framework) both supported | [opentofu.org/docs/intro/whats-new](https://opentofu.org/docs/intro/whats-new/) |

**Explicitly rejected** (see STACK.md §"What we explicitly REJECT"):

- **Python (FastAPI + `aiohasupervisor`)** — schema drift risk across languages outweighs official-client benefit.
- **Bun/Node** — heavier runtime, no upside over static Go.
- **Hand-rolled `tfproto6`** — would re-implement `terraform-plugin-framework` in ~2000 LoC.

---

## Feature Scope

### Phase 1 (must ship, fixed in PROJECT.md)

| Resource / capability | Bridge endpoint | Notes |
|---|---|---|
| `homeassistant_addon` (resource) | `/v1/addons/<slug>...` | CRUD: Create = install + optional start; Read = info; Update = options; Delete = uninstall |
| `homeassistant_addon` (data source) | `GET /v1/addons/<slug>` | Read by slug for `outputs` without managing |
| `homeassistant_supervisor_info` (data source, optional) | `GET /supervisor/info` | Cheap; useful for `lifecycle.precondition` |
| Bridge `/v1/version` | n/a | Version handshake: `bridge_version`, `schema_version`, `min_provider_version`, `max_provider_version` |
| Bearer-token issuance + rotation | `POST /v1/auth/rotate` | Token in `/data/bridge-token`, chmod 600, surfaced via add-on Options UI |
| Job polling passthrough | `GET /v1/jobs/<job_id>` | Forward Supervisor `job_id` so Provider polls via Bridge (WAL on Bridge for restart resilience) |
| Options pre-validation | `POST /v1/addons/<slug>/options/validate` | Bridge calls Supervisor validate before apply for typed errors |
| Lifecycle meta-arguments | Provider-side | `prevent_destroy`, `ignore_changes`, `replace_triggered_by`, `precondition`, `postcondition`, `for_each`, `depends_on` all supported by framework |
| `terraform import` | Provider-side | `ImportStatePassthroughID` by slug; adoption in Create (no-op if already installed) |
| Schema-versioned handshake | Provider `Configure` | Provider calls `/v1/version` at startup, refuses if schema_version unsupported |

### Phase 2+ (defer per PROJECT.md / FEATURES.md)

| Feature | Why defer | Notes |
|---|---|---|
| `homeassistant_addon_repository` | One-call CRUD; no lifecycle complexity | `add_repository`, `remove_repository`, `repositories_list` |
| `homeassistant_addon_update` action | Pin / roll forward / roll back versions | `POST /store/addons/<slug>/update` |
| Provider Actions (start/stop/restart/rebuild/stdin) | Separate TF 1.5+ `action` blocks | Framework Actions API |
| `homeassistant_backup` | Backups prerequisite for safe upgrades | `backups.py` |
| `homeassistant_addon_stats` data source | Live CPU/memory | `apps.py:stats` |
| HTTP state backend on Bridge | Optional S3-style remote state | Free `LOCK`/`UNLOCK` via `http` backend, but doubles auth surface |
| Tailscale HTTPS termination | If exposed beyond tailnet | Bridge itself can run Tailscale Serve; CF Access layer for public exposure |
| HA Core / Supervisor / Host resources | Disruptive; requires explicit user ack | Never in Phase 1 |
| Core-entity resources (automation, script, scene, area, zone, device, dashboard) | Different API surface (HA Core REST, not Supervisor); huge scope | Separate provider or sub-app |

### Anti-features (do NOT build in any phase)

| Anti-feature | Why avoid | Do instead |
|---|---|---|
| Write to `/config`, `/share`, `/media`, `/data` from Bridge | Pass-through only; filesystem writes are the add-on's job | Bridge stays at Supervisor scope |
| Restart HA Core from Provider | Breaks every running add-on | Phase-3+ `homeassistant_core` with `prevent_destroy` default + precondition |
| Modify host OS from Provider | Larger blast radius than Core restart | Phase-3 `homeassistant_host` with precondition gate |
| Run Provider binary inside HA Supervisor | Couples lifecycles | Provider is separate Go binary on dev/CI host |
| Auto-rotate bearer without grace period | In-flight requests get 401 | Manual rotation only; rotation returns both old (grace) + new token |
| Embed `tofu` binary in the Bridge | Duplicates user-side binary | User runs `tofu` from workstation |
| Provider-managed Supervisor self-update | Circular dependency | Provider is read-only against non-app Supervisor endpoints |

---

## Architecture

### Topology (one paragraph)

The Provider runs on a developer laptop or CI runner and speaks to the Bridge over HTTPS using a bearer token;
the Bridge runs as an HA Supervisor add-on (`hassio_api: true`, `hassio_role: manager`, `ports: 8124/tcp: 8124`,
**no ingress** — Ingress is browser-only) and authenticates to Supervisor via the auto-injected `SUPERVISOR_TOKEN`
on `http://supervisor/<path>`. The Bridge is a thin Go HTTP service (~25-30 MB compressed image) wrapping chi v5
middleware (request-ID, logger, recoverer, 60s timeout, custom bearer auth) around a minimal `net/http` Supervisor
client that proxies `/v1/*` to Supervisor endpoints. The Provider is built locally from
`terraform-provider-homeassistant/` (Go module, `terraform-plugin-framework` v1.19.0), installed to
`~/.local/share/terraform/plugins/registry.terraform.io/akentner/homeassistant/<version>/linux_amd64/`, and speaks to
the Bridge on port 8124. State lives on the Provider host under the local backend (default) — the Bridge does not
touch state; OpenTofu serializes via `flock`. Token file at `/data/bridge-token` (chmod 600) plus optional audit log
at `/data/bridge.jsonl` (structured JSON, one line per request). Both Bridge and Provider share the repo's 3-file
versioning scheme and ship from one tagged release; `validate-versions.sh` will be extended to enforce that
`terraform-bridge/config.yaml` and `terraform-provider-homeassistant/build.yaml` versions move together.

### Build order (synthesized from ARCHITECTURE.md §"Build Order" + PITFALLS.md §"Implications for Roadmap")

The two source files propose **different phase counts**: FEATURES suggests 3 phases (addon / repository / backup),
ARCHITECTURE suggests 6 phases (Bridge skeleton → Provider skeleton → Provider reads all → write ops → HTTP state
backend → polish), PITFALLS suggests 7 phases (09.1 Bridge scaffold → 09.2 Auth+CSRF → 09.3 Bridge API + WAL →
09.4 Provider + safety → 09.5 State + drift + versioning → 09.6 CI+testing → 09.7 DOCS). **Resolution:** the
PITFALLS 7-phase structure is the most defensible because each phase addresses a specific pitfall class with
testable acceptance criteria; ARCHITECTURE's 6 phases merge too many concerns. The recommended roadmap structure
below is the PITFALLS phasing with FEATURES-aligned feature tags.

| # | Phase | Why this order | Addresses | Pitfalls |
|---|---|---|---|---|
| 1 | Bridge scaffold + token emission | Establishes privilege boundary (`hassio_role: manager`); everything depends on it | S-1, S-4, S-5, H-1, H-3, H-4, V-3, O-1 |
| 2 | Auth + CSRF + Tailscale binding | Auth must exist before any write testing | S-2, S-3, S-4 |
| 3 | Bridge API surface + concurrency + WAL + timeouts | Provider depends on Bridge concurrency/job-tracker correctness | ST-1, ST-2, H-2, H-5, O-3 |
| 4 | Provider scaffold + `homeassistant_addon` + safety | Resource implementation; depends on Bridge API stable | I-1, I-2, I-3, D-1, D-2, D-3, T-1, T-2, T-4, T-5, O-2 |
| 5 | State + drift + versioning handshake | Drift is a Provider concern; handshake depends on Provider existing | ST-4, V-1, V-2 |
| 6 | CI + testing | Tests both Provider and Bridge; can run in parallel with #5 | O-2, O-3, T-2, T-3 |
| 7 | Operations + DOCS.md | Depends on everything settled | O-1, ST-3, D-1, D-2 runbook |

### Key contracts

1. **Version handshake (`/v1/version`)** — Bridge returns `{bridge_version, schema_version, min_provider_version,
   max_provider_version}`. Provider compares at startup; mismatch → hard error in `Configure`. Defense-in-depth:
   Bridge also embeds `min_schema_version` on every `/v1/*` route and returns 400 on `X-Bridge-Schema` mismatch.
   *(See [ARCHITECTURE.md §"Schema Versioning"](.planning/research/ARCHITECTURE.md) and PITFALLS V-1, V-2.)*

2. **Schema coupling** — Bridge and Provider share Go types via `terraform-bridge/contract/` submodule imported by
   both. Drift caught at `go build` of Provider. *(See [STACK.md §"Bridge ↔ Provider Schema Sharing"](.planning/research/STACK.md).)*

3. **Async job contract** — Supervisor ops (`install`, `uninstall`, `update`) return `job_id`. Bridge **forwards
   `job_id` directly** to the Provider (does not invent its own job tracking) and exposes `GET /v1/jobs/<id>` as
   passthrough. Bridge maintains a write-ahead log at `/data/jobs.jsonl` so it can re-attach in-flight jobs after
   a Bridge restart. Provider polls via Bridge until `state ∈ {done, error}` with bounded timeout (default 10m for
   install). *(See [PITFALLS ST-2](.planning/research/PITFALLS.md) and [ARCHITECTURE.md §"Async Supervisor jobs"](.planning/research/ARCHITECTURE.md).)*

4. **Idempotent Create (adoption)** — Provider's Create flow: `GET /apps/<slug>/info` first; if installed → adopt
   existing, write to state, return success; if not installed → `POST /store/<slug>/install` with `background:
   false`, poll job, then Read. NEVER call `POST /install` after initial install unless resource is missing.
   *(See [PITFALLS I-1, I-2](.planning/research/PITFALLS.md).)*

5. **Drift key** — Provider uses a **normalized options hash** (SHA-256 of sorted keys, secrets stripped) as the
   drift key, NOT the `state` field. `state` flutters between `startup`/`started`/`stopped` during restarts; users
   who find this noisy add `lifecycle.ignore_changes = [state]`. Hard drift = 404 → framework's
   `resp.State.RemoveResource()` so TF plans to recreate, not destroy. *(See [FEATURES.md §"Drift detection strategy"](.planning/research/FEATURES.md)
   and [PITFALLS ST-4, I-3](.planning/research/PITFALLS.md).)*

6. **State backend (Phase 1)** — OpenTofu local backend at `/data/terraform.tfstate` (file lives on Provider host;
   `/data` in the Bridge container is for `bridge-token`, audit log, WAL only). OpenTofu's built-in `flock`
   serializes same-host concurrent applies; cross-host applies are explicitly out of scope in Phase 1 (Bridge
   per-slug mutex is defence-in-depth). *(See [PITFALLS ST-1, T-3](.planning/research/PITFALLS.md).)*

7. **Safety — destructive ops** — Provider bakes `lifecycle.prevent_destroy = true` into the resource schema by
   default; user can opt out per-resource. Provider maintains a `critical_addons` list
   (`mosquitto`, `core_mosquitto`, `zigbee2mqtt`, `zwave-js-ui`, `esphome` by default) that turns destroy plans into
   **errors**, not warnings. Two-step nonce confirmation for uninstall via `POST /destructive/preview` →
   `X-Confirm-Nonce`. *(See [PITFALLS D-1, D-2](.planning/research/PITFALLS.md).)*

### Reconciled research conflicts

- **V1 vs V2 Supervisor endpoints.** STACK recommends V1 (`/addons/...`) as pragmatic for broad compatibility;
  PITFALLS V-3 notes V1 routes carry `Deprecated 2026.05` / `Deprecated 2026.03` / `Remove: 2023` comments in
  Supervisor source (`supervisor/api/__init__.py`). **Resolution:** Bridge prefers **V2 (`/apps/...`)** when
  `SUPERVISOR_V2_API` flag is on; falls back to V1 transparently. Bridge re-reads `/supervisor/info` on every
  request (cheap) so it auto-upgrades within seconds of HA flipping the flag. Provider unchanged. *(See
  [PITFALLS V-3](.planning/research/PITFALLS.md), [ARCHITECTURE.md §"Phase 1 endpoint inventory"](.planning/research/ARCHITECTURE.md).)*

- **Bridge language.** STACK recommends Go (rejects Python / Bun / hand-rolled tfproto6). ARCHITECTURE contains
  Python pseudo-code in the topology diagram but its recommendations section consistently assumes the Go
  approach. **Resolution:** Go per STACK; ARCHITECTURE's Python snippets are illustrative only, not prescriptive.

- **Auth complexity.** STACK describes a minimal bearer-token middleware (constant-time compare, hashed-on-disk).
  PITFALLS adds: CSRF tokens on POST/DELETE (S-3), Tailscale-interface binding (S-4), grace-period token rotation
  (S-2), state file backup redaction, audit log redaction. **Resolution:** all of PITFALLS's additions ship with
  Phase 1 because they're cheap (<100 LoC combined) and the privilege-concentration risk is the dominant threat
  in this domain.

- **State backend.** STACK = local only. ARCHITECTURE proposes local in Phase 1, HTTP backend as Phase 1 alt.
  PITFALLS focuses on `/data` wipe on reinstall. **Resolution:** local backend in Phase 1 (mandatory for
  correctness — Bridge never touches tfstate); HTTP backend deferred to Phase 2. Both agree `/data` wipe is
  the dominant state hazard; mitigation: secondary copy via `map: [addon_config:rw]` so HA backup integration
  covers state. *(See [PITFALLS ST-3](.planning/research/PITFALLS.md).)*

- **Phase count.** FEATURES = 3 (addon/repository/backup); ARCHITECTURE = 6; PITFALLS = 7. **Resolution:**
  PITFALLS's 7-phase structure is recommended because each phase has testable acceptance criteria tied to specific
  pitfalls; FEATURES's 3-phase model conflates scaffold + auth + concurrency in one step. ARCHITECTURE's 6-phase
  model is acceptable if the team prefers fewer phases (would merge PITFALLS 09.1 + 09.2 + 09.3).

---

## Watch Out For

Top pitfalls ranked by blast-radius, each tied to the phase that prevents it. Full Prevention Matrix in
[PITFALLS.md §12](.planning/research/PITFALLS.md).

| # | Pitfall | Blast radius | Phase | Prevention in one line |
|---|---|---|---|---|
| 1 | **S-1: `SUPERVISOR_TOKEN` leak into Provider logs or error bodies** | Catastrophic — full Supervisor control | Phase 1 | Bridge reads `SUPERVISOR_TOKEN` only into outbound `http.Client.Transport`; error middleware returns `{error_code, message, job_id?}` only — never upstream request/response/env |
| 2 | **S-4: Bearer-token over plain HTTP, Bridge accidentally bound to `0.0.0:0`** | Token traverses non-Tailscale network | Phase 1 | Add-on option `bind_address` defaults to "auto-detect Tailscale IP"; reject startup if `iface != tailscale*`; log `bridge.listening=...iface=...` |
| 3 | **D-1: `terraform apply` uninstalls critical add-on (mosquitto, zigbee2mqtt)** | Device outages, loss of trust | Phase 4 | Bake `lifecycle.prevent_destroy = true` into schema default; `critical_addons` list turns destroy plans into **errors**; Bridge writes destructive log |
| 4 | **ST-3: State file in `/data` wiped on add-on reinstall** | "All resources need to be created" → re-install attempts → errors | Phase 1 + Phase 7 | Declare `map: [addon_config:rw]` so HA backup integration covers state; loud DOCS.md warning + `/state/export|import` endpoints; bridge startup warn if state missing but addon_config copy exists |
| 5 | **ST-2: Bridge restart during apply loses intermediate job state** | Provider sees 404 on `GET /jobs/<id>`, falsely reports install failure | Phase 3 | Bridge maintains WAL at `/data/jobs.jsonl`; on startup re-attaches in-flight jobs; Bridge forwards Supervisor `job_id` directly (no Bridge-side job tracking) |
| 6 | **I-1 / I-2: "Already installed" treated as error / Provider always creates new** | Bootstrap against existing HA install broken; re-install resets user's options to defaults | Phase 4 | Create flow: `GET /apps/<slug>/info` first → adopt if installed; **never** call `POST /install` after initial install unless resource is missing; options-changed-but-installed → `POST /apps/<slug>/options` not re-install |
| 7 | **V-3: Supervisor API V1 routes deprecated/removed** | Provider breaks every HA release until Bridge updated | Phase 1 | Bridge prefers V2 (`/apps/...`) when `SUPERVISOR_V2_API` flag on; V1 fallback; re-read flag on every request |
| 8 | **H-1: `SUPERVISOR_TOKEN` rotation across Supervisor restart** (LOW confidence — needs empirical spike) | Intermittent mid-operation failures | Phase 1 (spike) | Empirical verification in Phase 09.1 spike; if token changes, Bridge re-reads env each call (cheap) and treats change as non-error; logs `bridge.token_rotated=true` |
| 9 | **T-2: Provider lacks `ImportState` → adoption friction kills greenfield users** | Tool only works on empty HA installs | Phase 4 | Mandatory `ResourceWithImportState` with `ImportStatePassthroughID` by slug; Create flow is adoption in lockstep |
| 10 | **S-3: CSRF on Bridge HTTP API** | Authorized requests fired by something other than Provider | Phase 2 | Custom `X-CSRF-Token` header on POST/DELETE; Bridge refuses mutating requests without it; `OPTIONS` preflight from non-Tailscale origin returns no CORS headers |

---

## Open Questions

These need user / `gsd-discuss-phase` input before plan-phase locks down:

1. **Phase-1 stretch: include `homeassistant_addon_repository`?** PROJECT.md marks it optional in Phase 1.
   FEATURES.md recommends deferring (Phase-1 budget better spent hardening `homeassistant_addon`). The repo
   default in v1.0 was: pick scope over completeness → **recommend defer** to Phase 2.

2. **Options schema translation.** Supervisor exposes the add-on's option schema as `ATTR_SCHEMA` (voluptuous
   JSON-schema). FEATURES recommends Phase 1 fallback: `options = TypeMap<String>` + Bridge-side validation via
   `apps/<slug>/options/validate`. Dynamic typed schema is a Phase-2 concern. **Recommend: confirm Phase 1 = static
   TypeMap<String> + server-side validation.** Trade-off: less compile-time safety, but ships sooner.

3. **V1 vs V2 priority in Phase 1 code path.** RESOLVED via reconciliation above (prefer V2 with V1 fallback). No
   user input needed.

4. **`pwned` secrets surface.** Supervisor's `apps/<slug>/options/validate` returns `{valid, pwned}`. FEATURES
   suggests surfacing as a warning diagnostic in Create/Update. **Recommend: yes, as Provider warning (not error)
   in Phase 1; promote to error in Phase 2.**

5. **`start` semantics on Create.** PROJECT.md silent. FEATURES recommends `start = true` default with opt-out
   for staged rollouts. **Recommend: confirm `start = true` default; document opt-out in DOCS.md.**

6. **HA backup integration behaviour with `addon_config` mount.** PITFALLS §10 marks this MEDIUM confidence —
   verify empirically in Phase 09.1 spike whether HA's backup integration includes `addon_config` paths by
   default. Affects whether the secondary state-copy mitigation in pitfall ST-3 actually works.

7. **Tailscale HTTPS vs plain HTTP on tailnet.** ARCHITECTURE §"TLS posture" lists both options. Recommendation:
   Phase 1 supports both (Provider `endpoint` is user-supplied); Bridge speaks plain HTTP. **Recommend: confirm
   plain HTTP acceptable for Phase 1; defer TLS termination to Bridge or reverse proxy.**

8. **`state` field noise in plan output.** FEATURES recommends `UseStateForUnknown()` plan modifier + users add
   `lifecycle.ignore_changes = [state]` if noisy. **Recommend: default `UseStateForUnknown()`; document
   `ignore_changes` in DOCS.md as the standard escape hatch.** No user input needed.

9. **Empirical spike: `SUPERVISOR_TOKEN` rotation across Supervisor restart.** Pitfall H-1 — LOW confidence,
   must verify in Phase 09.1 spike. Affects whether the Bridge needs to re-read token per call or once at
   startup.

---

## Sources

Aggregated from all four research files; URLs verified 2026-08-31.

### Primary (HIGH confidence — code/docs read directly)

- [home-assistant/supervisor](https://github.com/home-assistant/supervisor) `supervisor/api/__init__.py` — endpoint registration, V1/V2 split, `/jobs/{uuid}` route
- [home-assistant/supervisor `supervisor/api/apps.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/apps.py) — `info_data` redaction, async.shield, install background_task, `ATTR_SCHEMA`
- [home-assistant/supervisor `supervisor/api/store.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/store.py) — install + repository endpoints, `_extract_app`
- [home-assistant/supervisor `supervisor/api/middleware/security.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/middleware/security.py) — token validation, role checks, V1/V2 patterns, `_V1_LEGACY_ERROR_KEY_MAP`
- [home-assistant/supervisor `supervisor/api/utils.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/utils.py) — `extract_supervisor_token`, `background_task`
- [home-assistant/supervisor `supervisor/const.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/const.py) — `AppState`, `AppBoot`, `AppBootConfig`, `INGRESS_DYNAMIC_PORT_MIN/MAX`, `HEADER_TOKEN`
- [home-assistant-libs/python-supervisor-client](https://github.com/home-assistant-libs/python-supervisor-client) — Apache-2.0, Python-only; **confirmed no Go equivalent exists**
- [developers.home-assistant.io/docs/api/supervisor/endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/) — every Phase 1 endpoint
- [developers.home-assistant.io/docs/add-ons/configuration](https://developers.home-assistant.io/docs/add-ons/configuration) — `config.yaml` schema, `hassio_role`, `map:`, `ports`, `host_network`, `ingress`
- [developers.home-assistant.io/docs/add-ons/communication](https://developers.home-assistant.io/docs/add-ons/communication) — `SUPERVISOR_TOKEN` injection, `{REPO}_{SLUG}` DNS, supervisor hostname

### Terraform / OpenTofu (HIGH confidence)

- [developer.hashicorp.com/terraform/plugin/framework](https://developer.hashicorp.com/terraform/plugin/framework) — recommended for new providers
- [developer.hashicorp.com/terraform/plugin/framework/resources/timeouts](https://developer.hashicorp.com/terraform/plugin/framework/resources/timeouts) — `terraform-plugin-framework-timeouts` module
- [developer.hashicorp.com/terraform/plugin/framework/resources/import](https://developer.hashicorp.com/terraform/plugin/framework/resources/import) — `ImportStatePassthroughID`, multi-attribute parsing
- [developer.hashicorp.com/terraform/plugin/framework/resources/plan-modification](https://developer.hashicorp.com/terraform/plugin/framework/resources/plan-modification) — `RequiresReplace()`, `UseStateForUnknown()`
- [developer.hashicorp.com/terraform/plugin/framework/diagnostics](https://developer.hashicorp.com/terraform/plugin/framework/diagnostics) — severity, `Summary` + `Detail`, `Append`
- [developer.hashicorp.com/terraform/plugin/framework/resources/state-upgrade](https://developer.hashicorp.com/terraform/plugin/framework/resources/state-upgrade) — `ResourceWithStateUpgrade`, `PriorSchema`, `RawState`
- [developer.hashicorp.com/terraform/plugin/framework/migrating/benefits](https://developer.hashicorp.com/terraform/plugin/framework/migrating/benefits) — typed vs SDKv2 type assertion
- [developer.hashicorp.com/terraform/language/meta-arguments/lifecycle](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) — `create_before_destroy`, `prevent_destroy`, `ignore_changes`, `replace_triggered_by`, `precondition`, `postcondition`
- [developer.hashicorp.com/terraform/language/backend/http](https://developer.hashicorp.com/terraform/language/backend/http) — `LOCK`/`UNLOCK` verbs, `423 Locked` semantics
- [developer.hashicorp.com/terraform/language/state/locking](https://developer.hashicorp.com/terraform/language/state/locking) — lock semantics, force-unlock nonce
- [opentofu.org/docs/intro/whats-new](https://opentofu.org/docs/intro/whats-new/) — 1.12 release notes, no breaking protocol changes since 1.0
- [opentofu.org/docs/language/state/locking](https://opentofu.org/docs/language/state/locking/) — local backend `flock`-style advisory locking
- [opentofu.org/docs/language/import](https://opentofu.org/docs/language/import/) — `import` block syntax
- [opentofu.org/docs/language/resources/behavior](https://opentofu.org/docs/language/resources/behavior/) — lifecycle semantics, drift detection

### Go libraries (HIGH confidence)

- [pkg.go.dev/terraform-plugin-framework](https://pkg.go.dev/github.com/hashicorp/terraform-plugin-framework) — v1.19.0, 2026-03-10, requires Go 1.25+, MPL-2.0, protocol v6
- [pkg.go.dev/terraform-plugin-sdk/v2](https://pkg.go.dev/github.com/hashicorp/terraform-plugin-sdk/v2) — v2.40.1, 2026-04-28, recommends framework for new providers
- [pkg.go.dev/go-chi/chi/v5](https://pkg.go.dev/github.com/go-chi/chi/v5) — v5.3.2, 2026-08-20, MIT, 17,309 importers
- [pkg.go.dev/golang.org/x/crypto/argon2](https://pkg.go.dev/golang.org/x/crypto/argon2) — v0.55.0, 2026-08-11, BSD-3 (reserved, not used in Phase 1)
- [github.com/home-assistant/docker-base](https://github.com/home-assistant/docker-base) — Alpine 3.22/3.23/3.24, Python 3.12-3.14, Debian trixie, Ubuntu 22-26

### Secondary (MEDIUM confidence — verified for reference patterns)

- [goauthentik/terraform-provider-authentik](https://github.com/goauthentik/terraform-provider-authentik) — 138 stars, framework-based, REST + bearer-token shape (same pattern as Bridge needs)
- [authentik_user resource docs](https://raw.githubusercontent.com/goauthentik/terraform-provider-authentik/main/docs/resources/user.md) — schema conventions: `Required` / `Optional` / `Sensitive` / `Computed`
- [tailscale.com/kb/1312/tailscale-serve](https://tailscale.com/kb/1312/tailscale-serve) — Serve forwards `Tailscale-User-*` identity headers but **does not perform app-layer CSRF**; "listen on localhost" best practice

### Tertiary (LOW confidence — verified absence or needs empirical validation)

- GitHub topic [terraform-provider-homeassistant](https://github.com/topics/terraform-provider-homeassistant) — **zero repositories**, confirms green-field
- Terraform Registry search `homeassistant` — no providers indexed
- OpenTofu Registry search `homeassistant` — empty
- Token rotation across Supervisor restart — not explicitly documented; **must verify empirically in Phase 09.1 spike**
- V1 endpoint removal timeline — Supervisor source has "Remove: 2023", "Deprecated 2026.05", "Deprecated 2026.03" comments; exact dates not committed
- HA backup integration with `addon_config` mount — **verify in Phase 09.1 spike**

### In-repo (HIGH confidence)

- `meridian/config.yaml` + `meridian/run.sh` — long-running add-on pattern, `ports:` mapping, bashio, SUPERVISOR_TOKEN + `Authorization: Bearer` pattern
- `network-tools/config.yaml` + `network-tools/run.sh` — `host_network: true` pattern (not used by Bridge)
- `markdown-renderer/config.yaml` + `markdown-renderer/run.sh` — `ingress: true` pattern (rejected for Bridge; Ingress is browser-only)
- `internal/validate-versions.sh` — 3-file versioning scheme; **extend** to enforce Bridge+Provider version lock-step
- `internal/update-version.py` + `make update-version` — version bumping + `<addon>/v<version>` tag creation
- `.planning/phases/08-ci-cd-hardening/08-03-SUMMARY.md` — Cloudflare Access service-token auth pattern (negative-edge probe, 3xx fail-fast, no `-L`); reuse for Phase-2 if Bridge exposed beyond Tailscale

---

_Research completed: 2026-08-31 | Ready for roadmap: yes — recommended phase structure (7 phases) ready for `gsd-roadmapper`_
