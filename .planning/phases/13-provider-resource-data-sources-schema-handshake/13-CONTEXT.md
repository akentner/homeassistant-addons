# Phase 13: Provider + Resource + Data Sources + Schema Handshake - Context

**Gathered:** 2026-09-04 **Status:** Ready for planning **Milestone:** v1.3 opentofu-bridge

<domain>

## Phase Boundary

Land the `terraform-provider-homeassistant` Go module so it compiles, serves via `providerserver.Serve()`, and exposes
the `homeassistant_addon` resource (CRUD + Import + per-operation timeouts + `UseStateForUnknown`) plus both data
sources (`homeassistant_addon`, `homeassistant_supervisor_info`) against the Bridge endpoints delivered in Phases 11
and 12. Configure-time handshake via `GET /v1/version` enforces the schema-version window; typed Provider diagnostics on
Bridge errors carry an actionable message, the Bridge `request_id`, and a `DOCS.md#troubleshooting-<error_code>` URL.
`prevent_destroy = true` is documented as the recommended safety posture in DOCS.md but never forced.

Specifically this phase delivers:

- A real `Provider` (replacing the Phase 9 stub at `terraform-provider-homeassistant/main.go`) that wires `Metadata`,
  `Schema`, `Configure`, `DataSources`, and `Resources` against the existing `terraform-plugin-framework` v1.19.0
  dependency.
- A `Resource` implementation for `homeassistant_addon` with `Create`, `Read`, `Update`, `Delete`, plus
  `ImportStatePassthroughID` accepting `{slug}` or `{repository}/{slug}` and per-operation timeouts via
  `terraform-plugin-framework-timeouts`.
- Two `DataSource` implementations: `homeassistant_addon` (read-only by slug, returns full info for use in
  `terraform_data` and other resources' attribute references) and `homeassistant_supervisor_info` (for
  `lifecycle.precondition` blocks).
- A typed `diagnostics.MapError` helper that translates each Bridge `error_code` into a per-code Provider diagnostic,
  with severity (Error for 4xx/5xx; Warning for `pwned`), the Bridge `request_id`, and a
  `DOCS.md#troubleshooting-<error_code>` URL.
- An extension of `contract.AddOnInfo` with the four Supervisor fields that the current struct drops (`hostname`, `dns`,
  `ingress_url`, `ingress_entry`, `webui_url`) so the Provider schema can expose them as Computed attributes. Bridge
  passes Supervisor values 1:1 through `/v1/addons/{slug}/info`.
- `terraform-provider-homeassistant/DOCS.md` with installation, provider config, resource/data-source reference, full
  examples (with `prevent_destroy = true` prominent), and a per-`error_code` troubleshooting table whose anchors back
  the Diagnostic URLs above.

**What this phase is NOT:** real-HA end-to-end empirical verification (Phase 14), CI hardening + the
`make install-provider` workflow (Phase 15), the `homeassistant_addon_repository` resource (deferred to v1.4 per
FEATURES.md OQ-1). All of those land later.

</domain>

<decisions>

## Implementation Decisions

### `hostname` and other missing Supervisor fields (Area 1)

- **D-01:** `contract.AddOnInfo` is extended with five Supervisor fields that the Phase 9/11 struct dropped:
  `Hostname string`, `DNS []string`, `IngressURL string`, `IngressEntry string`, `WebUIURL string`. JSON tags follow
  Supervisor's snake_case wire format. Empty string / nil slice = Supervisor didn't set the field; Provider passes
  through verbatim (no fallback, no synthetic value). — **Reversibility:** `costly` — **rationale:** Provider schema
  lists these as Computed attributes; removing one later is a Provider schema change (consumers' state files would
  silently drop the attribute).
- **D-02:** Bridge `/v1/addons/{slug}/info` continues to pass Supervisor's payload through unmodified. The Bridge
  handler itself does no field-level massaging — Provider reads exactly what Supervisor sent. Empty-string `hostname`
  from Supervisor surfaces as empty-string `hostname` in Provider state.
- **D-03:** `SchemaVersion` stays at `1.0.0` (no bump). Adding fields to `AddOnInfo` is purely additive; per
  `internal/version/version.go` policy, MINOR/PATCH are informational only and the
  `[min_provider_version, max_provider_version]` window stays unchanged.

### Adoption-aware Create flow (Area 2)

- **D-04:** Provider's `Create` calls `GET /v1/addons/{slug}/info` first (race-free adoption). On 200 → adopt the
  existing add-on (skip install; use the returned AddOnInfo as the initial state). On 404 → call
  `POST /v1/addons/{slug}/install`. On any other response → typed diagnostic. — **Reversibility:** `reversible` —
  Provider behavior change, no external contract shift.
- **D-05:** After either adoption or fresh install, if `start = true` (default per PROV-02) and the resulting
  `started = false`, Provider calls `POST /v1/addons/{slug}/start`. Convergent UX: a successful `terraform apply` leaves
  the add-on running.
- **D-06:** On adoption, if the user's `options` differ from `AddOnInfo.Options`, Provider calls
  `POST /v1/addons/{slug}/options` with the desired map. Same for `boot`: if desired ≠ returned, Provider sends the new
  value through the same `/options` endpoint (which accepts `boot:` as a top-level key alongside `options`). This makes
  the first `apply` fully convergent: a freshly-imported add-on whose options and boot don't match the user's `*.tf`
  ends up matching without a second apply.
- **D-07:** `423 error_code: locked` from Bridge → Provider retries within `terraform-plugin-framework-timeouts` budget.
  No custom backoff; the framework's existing retry pattern handles transient mutex contention.

### Diagnostic messages and error mapping (Area 3)

- **D-08:** One explicit Diagnostic text per Bridge `error_code` (no generic fallback). Each code has its own sentence
  describing what the user should do (e.g., `critical_addon_protected` → "this add-on is in `critical_addons`; either
  remove it from the Bridge's `critical_addons` option or issue a nonce via `POST /v1/auth/nonce` and retry with
  `X-Force-Destroy`"). Implementation lives in `internal/diagnostics/map_error.go` as a single switch on the sentinel
  `error_code` string.
- **D-09:** Severity rule: `DiagnosticSeverity.Error` for every 4xx/5xx Bridge response; `DiagnosticSeverity.Warning`
  ONLY for the `pwned` field coming out of `/v1/addons/{slug}/options/validate` (PROV-06 explicit). All other
  Bridge-originated issues, including the transient `locked`, `nonce_expired`, `install_timeout`, and `upstream_error`,
  are Errors — the user must take action (retry, re-issue nonce, fix config) before apply can succeed.
- **D-10:** Every Provider diagnostic carries a `DOCS.md#troubleshooting-<error_code>` URL via the
  `tfprotov5.Diagnostic` `Link` field. Anchors are kebab-cased (`#troubleshooting-critical-addon-protected`,
  `#troubleshooting-nonce-expired`, etc.). IDE + CLI render these as clickable links.
- **D-11:** Every Provider diagnostic includes the Bridge's `request_id` (from `ErrorResponse.RequestID`) in the
  `Detail` field as `request_id: <id>`. Operator can grep Bridge logs for that id to correlate. — **Reversibility:**
  `reversible` — internal Diagnostic shape change.

### Provider DOCS.md structure (Area 4)

- **D-12:** `DOCS.md` lives at `terraform-provider-homeassistant/DOCS.md` (separate file inside the Provider module,
  mirroring the per-add-on DOCS pattern). Bridge's `DOCS.md` does not duplicate Provider content; it links to Provider's
  DOCS from the bridge usage section.
- **D-13:** Required DOCS.md sections, in order: (1) Installation (`make install-provider`, `dev_overrides` in
  `~/.terraformrc`, `tofu init`, `tofu plan`); (2) Provider Configuration (`endpoint`, `bearer_token` — sensitive); (3)
  Resource Reference (`homeassistant_addon` — full schema, defaults, Computed attributes); (4) Data Source Reference
  (both data sources); (5) Examples (full `apply` with `lifecycle.prevent_destroy = true` shown prominently and
  explained); (6) Troubleshooting (per-`error_code` table — see D-14).
- **D-14:** Troubleshooting section is a Markdown table per `error_code` with columns: HTTP status, Bridge condition
  (what triggered it), example Provider diagnostic text, remediation. Anchors per row back the Diagnostic URLs from
  D-10.
- **D-15:** `lifecycle.prevent_destroy = true` is shown in every full resource example AND accompanied by an inline
  note: "Comment this out to allow destroy; use `terraform destroy` carefully". Maximum transparency — user sees both
  the recommendation and how to opt out without needing to read separate docs. — **Reversibility:** `one-way` —
  **rationale:** Once users adopt `prevent_destroy = true` as the recommended default in DOCS.md examples, walking it
  back is a published-contract change (existing users may rely on the guidance when reasoning about their state files).
- **D-16:** Installation instructions are fully self-contained in DOCS.md (no "see Makefile" redirection). The section
  walks from `go install` / `make install-provider` through `~/.terraformrc` `dev_overrides`, `tofu init`, `tofu plan`,
  and the typical first-apply debugging flow.

### Carried forward from REQUIREMENTS.md + Phase 9/10/11/12 CONTEXT (locked, not re-discussed)

- **CF-01:** Provider is `terraform-provider-homeassistant`, uses `terraform-plugin-framework` v1.19.0 (protocol v6),
  supports OpenTofu ≥ 1.12 and Terraform ≥ 1.5. Serves via `providerserver.Serve()`. (PROV-01;
  `terraform-provider-homeassistant/go.mod` is already wired.)
- **CF-02:** Configure handshake — `Configure` calls `GET /v1/version` and refuses to operate with a typed diagnostic if
  `schema_version < min_provider_version` or `schema_version > max_provider_version`. (PROV-03;
  `contract.VersionHandshake` + `internal/version/version.go` exist.)
- **CF-03:** `terraform-plugin-framework-timeouts` provides per-operation timeouts. Defaults documented in DOCS.md:
  `create = 10m, update = 2m, delete = 5m`. (PROV-09.)
- **CF-04:** `UseStateForUnknown()` plan modifier on the `state` attribute so refreshes don't show spurious diffs.
  (PROV-10.)
- **CF-05:** `ImportStatePassthroughID` accepts `{slug}` (assumes `repository = "core"`) or `{repository}/{slug}` (any
  repo). (PROV-08.)
- **CF-06:** Read is idempotent — called after every operation. `GET /v1/addons/{slug}/info`; 404 returns empty state so
  Delete on missing add-on is a no-op. (PROV-04.)
- **CF-07:** Create-time flow uses `409 already_installed` as adoption signal — but in the Provider this is preempted by
  D-04 (GET first), so 409 is effectively unreachable on the Create path. Bridge's internal 409 handling (Phase 12 D-26)
  remains the safety net for concurrent Provider instances that race past the GET. (PROV-05.)
- **CF-08:** Update calls `POST /v1/addons/{slug}/options`; `pwned` warnings surface as Warning diagnostics (PROV-06,
  D-09).
- **CF-09:** Delete calls `POST /v1/addons/{slug}/uninstall`; success = 204; 404 = idempotent success. (PROV-07.)
- **CF-10:** Resource attributes (PROV-02): `slug` (Required String), `repository` (Optional String, default `"core"`),
  `url` (Optional String), `options` (Optional `TypeMap<String>`), `start` (Optional Bool, default `true`), `boot`
  (Optional `["auto","manual","manual_only"]`); Computed: `version`, `state`, `started`, `hostname` (and `dns`,
  `ingress_url`, `ingress_entry`, `webui_url` per D-01).
- **CF-11:** `homeassistant_addon` data source returns the full info payload for read-only use (PROV-11).
  `homeassistant_supervisor_info` data source is usable in `lifecycle.precondition` blocks (PROV-12) — body shape
  mirrors `/v1/info` (`bridge_version`, `supervisor_version`, `uptime_seconds`, `state_file_path`).
- **CF-12:** `prevent_destroy = true` is documented as the recommended option but NOT forced by the Provider — users opt
  in via lifecycle meta-arguments. (LIFE-02; D-15 carries this into DOCS.md examples.)
- **CF-13:** Bridge errors surface as typed Provider diagnostics per LIFE-04; explicit-text-per-error-code (D-08),
  severity rule (D-09), troubleshooting URL (D-10), and `request_id` correlation (D-11) implement this.
- **CF-14:** Provider shares the 3-file versioning scheme with Bridge (PROJECT.md §"Architecture"); build artifact
  versioning is locked via `internal/validate-versions.sh` and is not re-discussed here.
- **CF-15:** Bridge's per-slug mutex (Phase 12 D-12..D-16) is in-process only; Provider does NOT need its own
  cross-instance locking beyond what `terraform-plugin-framework-timeouts` provides (D-07).
- **CF-16:** Auth (Phase 10), logging (Phase 10), chi routing (Phase 11), Supervisor client pattern (Phase 11+12),
  contract types (Phase 9+11+12), and atomic file write with chmod 600 (Phase 10) are inherited unchanged — Phase 13
  only consumes the Bridge HTTP API from the outside; no Bridge source changes beyond the `AddOnInfo` struct extension
  in D-01.

### the agent's Discretion

- Exact internal package layout inside `terraform-provider-homeassistant/`. A reasonable default mirrors the Bridge's
  split: `internal/provider/`, `internal/resource/`, `internal/datasource/`, `internal/client/`,
  `internal/diagnostics/`. Agent may consolidate (single `internal/` tree) if it doesn't bloat.
- Exact shape of the `Client` struct in the Provider. Should mirror Bridge's `supervisor.Client` style:
  bearer-token-injecting Transport, `NewRequestWithContext`, per-call body-drain discipline (Phase 11 Rule-1 fix).
  Configured from the Provider's `endpoint` and `bearer_token` arguments during `Configure`.
- Whether `request_id` lives in `Detail` as raw text (`request_id: <id>`) or as a separate `tfprotov5` field if the
  framework exposes one (it doesn't today — Detail is the right place).
- The exact wording per `error_code` Diagnostic text. D-08 commits to "explicit per code"; the planner fills in the
  specific sentences. Suggested starting point in DOCS.md's troubleshooting table: `critical_addon_protected` → "this
  add-on is in `critical_addons`; either remove it from the Bridge's `critical_addons` option or issue a nonce via
  `POST /v1/auth/nonce` and retry with `X-Force-Destroy`".
- Whether the Provider emits a single combined diagnostic per Bridge error response or one per failed operation (e.g.,
  install + start in series — both fail). Recommendation: single error per Bridge round-trip; chain separate errors as
  additional diagnostics in order so the user sees the full failure list at once.
- Whether the data source `homeassistant_supervisor_info` exposes a `bridge_version` field that's also available via
  `/v1/version` (redundant). Recommendation: keep `bridge_version` in `/v1/info` body and let the data source surface
  both via two separate fields if useful, or just expose the `/v1/info` body 1:1 — agent's call.

### Folded Todos

None — `gsd-tools todo.match-phase 13` returned zero matches. Nothing from the existing backlog is being silently
dropped.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements traceability (HIGH confidence)

- `.planning/REQUIREMENTS.md` §"PROV — Provider" (PROV-01 through PROV-12) — every Resource / DataSource / Configure
  behavior this phase must implement
- `.planning/REQUIREMENTS.md` §"STATE — State Management" (STATE-01 only — STATE-02/03 already in Phase 12)
- `.planning/REQUIREMENTS.md` §"LIFE — Lifecycle & Safety" (LIFE-02, LIFE-04 only — LIFE-01/03 already in Phase 12)
- `.planning/REQUIREMENTS.md` §"OPS — Operations" — OPS-04 belongs to Phase 14; Phase 13 only needs to provide the
  Provider-side surface that OPS-04 will document

### Roadmap success criteria (HIGH confidence)

- `.planning/ROADMAP.md` §"Phase 13: Provider + Resource + Data Sources + Schema Handshake" — the seven
  empirical-falsifiable outcomes the phase must satisfy; SC-7's "DOCS.md documents lifecycle.prevent_destroy = true"
  maps directly to D-15
- `.planning/ROADMAP.md` §"Phase 12: Bridge Write API + Safety + Concurrency + Index" — Provider consumes every endpoint
  landed there (CF-07..CF-09)

### Repo conventions (HIGH confidence)

- `.planning/codebase/CONVENTIONS.md` — 120-char line limit, Go fmt via `gofmt -l .`, no manual imports ordering beyond
  `gofmt`'s output. The Provider module follows the same conventions; no exceptions.
- `.pre-commit-config.yaml` — the version-consistency hook (`internal/validate-versions.sh`) applies to the Provider's
  three files too once it joins the 3-file scheme (Phase 14 / 15 already extended it).
- `.yamllint.yml`, `.shellcheckrc`, `.markdownlint.json` — DOCS.md must pass markdownlint (MD013 120-char limit) and
  prettier.

### Precedent — Bridge implementation as template (HIGH confidence)

- `terraform-bridge/internal/supervisor/client.go` (Phases 11+12) — the canonical Go HTTP-client pattern in this repo.
  Provider's `Client` mirrors it: bearer-token-injecting Transport, `NewRequestWithContext`, body-drain on non-200,
  JSON-decode typed struct. Phase 13 reuses this shape, NOT copies it.
- `terraform-bridge/internal/httpapi/handlers/version.go` (Phase 11) — the shape the Provider's `Configure`-time
  `GET /v1/version` call must produce. Provider's response handling uses the same `contract.VersionHandshake` struct
  that already exists.
- `terraform-bridge/contract/types.go` (Phases 9+11+12) — `AddOnInfo`, `BridgeInfo`, `VersionHandshake`,
  `ErrorResponse`, `JobStatus`. Provider's `internal/client/` decodes these directly via the
  `replace terraform-bridge => ../terraform-bridge` directive already wired in
  `terraform-provider-homeassistant/go.mod:32`.
- `terraform-bridge/internal/httpapi/handlers/install.go` (Phase 12) — the canonical 1-second-tick polling loop pattern
  for async job completion. Provider doesn't poll itself (Bridge does, Phase 12 D-17) but the Provider's
  `terraform-plugin-framework-timeouts` budget of `create = 10m` must be ≥ Bridge's `install_job_timeout_seconds`
  default of 300s (5min).
- `terraform-bridge/internal/version/version.go` (Phase 11) — the SchemaVersion + MinProviderVersion +
  MaxProviderVersion semver policy. CF-02 + D-03 both reference it.

### Phase 12 decisions carried forward (locked)

- `.planning/phases/12-bridge-write-api-safety-concurrency-index/12-CONTEXT.md` §"CF-01..CF-11" — auth, slog convention,
  chi order, atomic write, supervisor env re-read-per-call, V2/V1 fallback, contract types, nonce + audit log
  discipline, error_code vocabulary
- `.planning/phases/12-bridge-write-api-safety-concurrency-index/12-RESEARCH.md` — supervisor HTTP API empirical
  contracts (sync vs async, `/jobs/{id}` shape, `OptionsValidateResponse` payload)

### Phase 10 decisions carried forward (locked)

- `.planning/phases/10-auth-layer-structured-logging-healthcheck/10-CONTEXT.md` §"D-01..D-13" — bearer token format,
  rotation + grace, `/healthz`, bind-gate, two-layer log masking. Provider's bearer_token argument follows the same
  `base64url, 43 chars` convention so what Bridge issues can be pasted verbatim.

### Phase 9 decisions carried forward (locked)

- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-CONTEXT.md` §"D-08" (config.yaml `map: addon_config:rw`
  — confirms `/data/terraform.tfstate` lives at that path and is included in HA backups) and §"D-10..D-13" (logging
  baseline)

### Live hosts / verification scope

- `haos-op3050-1` (Tailscale-reachable LAN host) and `ha-nextgen` — Phase 14's empirical verification hosts; Phase 13
  verification is unit-test only via the existing `tools/test-bridge-fixture/` (Phase 15) stdlib HTTP simulator.
- AGENTS.md §"Live Systems — No Unsolicited Restarts / Service Disruption" — Phase 14 owns the live-HA apply/destroy
  exercise; Phase 13 stays hermetic.

### Bridge config.yaml schema (current state)

- `terraform-bridge/config.yaml` — current `critical_addons` (default
  `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`), `install_job_timeout_seconds` (300),
  `try_lock_timeout_seconds` (5), `bind_address`, `bind_allowed_subnets` — Provider-side diagnostics must reference
  these defaults by name when explaining `critical_addon_protected` (D-08) and `locked` (D-08).

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `terraform-provider-homeassistant/main.go` (Phase 9 stub) — currently a placeholder with
  `var _ contract.VersionHandshake` to exercise the `replace` directive. Phase 13 replaces this file with the real
  Provider entry point (`providerserver.Serve(newProvider(), providerserver.ServeOpts{...})` where `newProvider()`
  returns a struct implementing `provider.Provider`).
- `terraform-provider-homeassistant/go.mod` (Phase 9) — already declares `terraform-plugin-framework v1.19.0` and the
  `replace terraform-bridge => ../terraform-bridge` directive. Phase 13 adds `terraform-plugin-framework-timeouts` to
  `require` (per PROV-09); no other new dependencies needed (the Provider's HTTP client uses `net/http` from stdlib).
- `terraform-bridge/contract/types.go` — `AddOnInfo` (will be extended per D-01), `VersionHandshake`, `ErrorResponse`,
  `BridgeInfo`, `NonceResponse`, `StateIndexResponse`. Provider imports these via the existing `replace` directive; no
  copy-paste.
- `terraform-bridge/internal/supervisor/testing.go` (Phase 11) — exposes `WithBaseURLForTest` and `TokenFnForTest`
  cross-package helpers. Phase 13's Provider tests reuse the same pattern (with the Provider's own `Client` type) so the
  simulator-based tests don't need a Bridge binary.
- `tools/test-bridge-fixture/` (Phase 15) — stdlib-only HTTP simulator that serves the Bridge contract on `:8124`. Phase
  13 unit tests stand up this simulator and exercise the full Provider Configure → Resource Create → Resource Read →
  Resource Update → Resource Delete → DataSource Read flow against it.
- `internal/validate-versions.sh` (Phase 9, extended Phase 14/15) — already covers the Provider's
  `terraform-provider-homeassistant/build.yaml` VERSION + the cross-artifact sync with the Bridge VERSION. Phase 13
  doesn't change this; version bumps are a `make update-version` step per AGENTS.md §"Critical Gotchas #1".

### Established Patterns

- **Bearer-token-injecting `http.RoundTripper`:** Phase 10's `tokenInjectingTransport` in
  `terraform-bridge/internal/supervisor/client.go`. Provider's `Client` implements the same shape — a custom Transport
  that adds `Authorization: Bearer <token>` from a function pointer (so tests can swap the token without touching env).
- **Body-drain on non-200:** Phase 11 Rule-1 (auto-fixed in 11-01-SUMMARY). Provider's `Client` follows the same drain
  discipline: StatusCode check FIRST, drain AFTER, decode LAST. Avoids connection leaks on non-200 responses.
- **V2-preferred / V1-fallback in supervisor calls:** Not relevant to the Provider (Provider talks to the Bridge, not to
  Supervisor directly). Phase 11+12 encapsulates this inside Bridge's `supervisor.Client`.
- **`slog` JSON baseline + scrubbingHandler:** Phase 10's `scrubbingHandler` masks sensitive keys. Provider uses Go's
  stdlib `log/slog` with the same scrubbing discipline if it emits any logs (Provider is mostly silent — it delegates
  operational logging to Bridge). If Provider emits anything, it MUST NOT log `bearer_token` or `endpoint` (PITFALLS S-1
  invariant).
- **Per-endpoint file convention (Bridge handlers):** Provider doesn't have a strict per-file convention to mirror, but
  each Resource + each DataSource in its own file is the idiomatic `terraform-plugin-framework` layout.
- **ErrorResponse body shape `{"error_code":"...","message":"...","request_id":"..."}`** — Phase 9+12 convention.
  Provider decodes exactly this; the `error_code` field drives D-08's diagnostic switch, the `request_id` flows into
  D-11's `Detail` field.
- **`lifecycle.prevent_destroy` meta-argument** — the idiomatic OpenTofu/Terraform pattern for blocking accidental
  destroy. Provider does not need custom code; users opt in via the meta-argument in their `*.tf` (LIFE-02 + D-15).

### Integration Points

- **HA Bridge HTTP API at `:8124`** (Phase 11+12):
  - `GET /v1/version` — Configure-time handshake (PROV-03, CF-02)
  - `GET /v1/info` — no-auth, for the `homeassistant_supervisor_info` data source (PROV-12, CF-11)
  - `GET /v1/addons/{slug}/info` — Read + adoption pre-check (PROV-04, D-04, CF-06)
  - `POST /v1/addons/{slug}/install` — Create (PROV-05, D-04, CF-07)
  - `POST /v1/addons/{slug}/options` — Update (PROV-06, D-06, CF-08)
  - `POST /v1/addons/{slug}/uninstall` — Delete (PROV-07, CF-09; requires `X-Force-Destroy` nonce per Phase 12
    D-05..D-08)
  - `POST /v1/auth/nonce` — Provider requests a nonce before Delete; the nonce is sent in `X-Force-Destroy` on the same
    request. Lifecycle: see CF-07's "concurrent Provider instances that race past the GET" scenario.
- **OpenTofu local backend** — Provider docs (D-13 + STATE-01) instruct users to configure
  `path = "/data/terraform.tfstate"` when running on the HA host, or to mirror via the add-on share volume off-host. The
  Provider itself doesn't read or write the state file — OpenTofu/Terraform does, via the configured backend.
- **HA backup integration** — Phase 9 §10 spike confirmed `addon_config:rw` mount contents (incl. `terraform.tfstate`)
  are auto-included in `ha backups new --app terraform-bridge`. Provider's DOCS.md (D-13) notes this in the installation
  section so operators know their state is backed up.
- **HA add-on Options UI** — the Bridge's bearer token surfaces once in the Options UI on first install (Phase 10 D-02
  invariant); Provider's DOCS.md installation section tells users to copy that token verbatim into the Provider's
  `bearer_token` argument.
- **CI / pre-commit / version sync** — `.github/workflows/test-terraform-provider.yml` (Phase 15) already exercises
  `gofmt -l .` + `go vet ./...` + `go test -count=1 ./...` on the Provider. Phase 13 doesn't change CI; the existing
  workflow is the verification gate.

</code_context>

<specifics>

## Specific Ideas

- **`start` follow-up is per Create, not per Read.** D-05 is explicit: after Create (install or adopt) the Provider
  brings the add-on to the desired running state in the same operation. Subsequent `terraform apply` with no config
  change is a no-op (Read sees `started = true`; no drift; nothing to do). This is what makes "apply → add-on runs" a
  one-shot experience rather than a multi-step dance.
- **`boot` is a top-level attribute in HA's add-on config schema, NOT inside `options`.** D-06's "send through the same
  `/options` endpoint" relies on Bridge's `POST /v1/addons/{slug}/options` accepting `boot:` as a top-level key
  alongside `options:` (it does — see Phase 12 install.go: the body is just `map[string]any` decoded straight to JSON).
  Provider's Update flow should treat `boot` as part of the options body when sending, but as a separate schema
  attribute when reading.
- **DOCS.md's troubleshooting table is the single source of truth for "what does this error mean".** D-08..D-10 together
  push the user-facing text + URL out of code into DOCS.md. If a future error_code is added (e.g., a new Phase 16+
  error), the only changes are: (a) add a row to the troubleshooting table with the matching anchor; (b) add a case to
  `internal/diagnostics/map_error.go`. No Provider code that references the error_code string directly.
- **`request_id` correlation flow:** user sees Provider diagnostic with `request_id: 7f2c8b...`, runs
  `ha addons logs terraform-bridge` (or HA UI → Settings → Add-ons → Terraform Bridge → Log), greps for
  `request_id=7f2c8b`, finds the matching slog record. The Bridge's request-logger middleware (Phase 10 D-09) writes
  exactly one structured JSON line per request with that `request_id`.
- **`prevent_destroy = true` is opt-in but visually prominent.** D-15 frames it as "every full resource example shows
  it, with an inline note explaining how to opt out". Users who copy-paste the example get the safety behavior; users
  who understand the trade-off can comment out the lifecycle block. This mirrors how the Terraform `aws_instance` docs
  recommend `prevent_destroy` for stateful resources.
- **The Provider's `bearer_token` argument is `Sensitive: true`.** Even though Provider is the only consumer, marking it
  sensitive keeps it out of state files and plan output (Terraform/OpenTofu behavior for sensitive arguments). This is
  consistent with Bridge's Options UI behavior (Phase 10 D-02).
- **`options` as `TypeMap<String>`** (PROV-02 explicit) means Provider can only send string-keyed, string-valued maps.
  HA add-on options that need nested objects (rare — most add-ons use flat string options) are out of scope; users would
  need to use `jsonencode()` or a separate escape mechanism. DOCS.md should note this in the resource reference section.

</specifics>

<deferred>

## Deferred Ideas

- **`homeassistant_addon_repository` resource** (FEATURES.md OQ-1) — managing add-on store repositories as Terraform
  resources. Deferred to v1.4 per REQUIREMENTS.md §"Out of Scope" and FEATURES.md OQ-1. Not in Phase 13.
- **`pwned` field as an attribute (not just a Warning)** — currently PROV-06 surfaces `pwned` as a Warning diagnostic.
  Surfacing it as a Computed attribute on the resource (so users can query it via `terraform output`) is a Phase 14+
  refinement.
- **`lifecycle` meta-argument enforcement at Provider level** — currently Provider trusts the user's `*.tf` lifecycle
  config. Enforcing `prevent_destroy = true` in the Provider (rather than just recommending in docs) would require
  either Provider-side resource schema validation or a custom validation hook. LIFE-02 explicitly leaves this opt-in;
  deferred unless a real failure mode emerges.
- **Provider-side `terraform state list`-style introspection over `GET /v1/state/index`** — STATE-02 makes the index
  available, but no Provider CLI command currently consumes it. Useful for "what state files does this Bridge know
  about" diagnostics. Out of scope for Phase 13.
- **CSRF / OPTIONS preflight on the Bridge** — PITFALLS S-3, deferred per Phase 12 CONTEXT §"Deferred Ideas". Phase 16+
  if a Tailscale Serve + browser-based Provider workflow emerges.
- **`install_job_timeout_seconds` overrides per-add-on** (Phase 12 §"Deferred Ideas") — single global for Phase 12/13;
  per-slug overrides become real if a slow add-on (`core_zigbee2mqtt` taking 6+ minutes to install) emerges in Phase
  14's real-HA verification.
- **`AddOnInfo` field coverage** — D-01 commits to the five currently-missing Supervisor fields. If Phase 14 surfaces
  another gap (e.g., a `translations` field, an `advanced_settings` block), it's a one-line struct extension like D-01.

### Reviewed Todos (not folded)

None — `gsd-tools todo.match-phase 13` returned zero matches.

</deferred>

---

_Phase: 13-provider-resource-data-sources-schema-handshake_ _Context gathered: 2026-09-04_
