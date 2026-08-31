# Roadmap: Home Assistant Add-ons Repository

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-04-04)
- ✅ **v1.1 markdown-renderer** — Phases 4-6 (complete 2026-06-28)
- 📋 **v1.2 CI/CD Hardening** — Phase 8 (planned 2026-08-30; gap-closure `08-05-GAP-PLAN.md` awaiting Cloudflare setup)
- 🚧 **v1.3 opentofu-bridge** — Phases 9-15 (planning 2026-08-31)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-04-04</summary>

- [x] Phase 1: Quality Fixes (2/2 plans) — completed 2026-04-03
- [x] Phase 2: Auto-Update Workflow (1/1 plan) — completed 2026-04-04
- [x] Phase 3: Meridian Add-on (3/3 plans) — completed 2026-04-04

Full details: [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 markdown-renderer (Phases 4-6) — COMPLETE 2026-06-28</summary>

- [x] Phase 4: Scaffold + Ingress Validation (3/3 plans) — completed 2026-06-27
- [x] Phase 5: Multi-Namespace + Dynamic Config (1/1 plan) — completed 2026-06-27
- [x] Phase 6: Git Integration (2/2 plans) — completed 2026-06-28

</details>

### 📋 v1.2 CI/CD Hardening (Phase 8)

- [ ] **Phase 8: CI/CD Hardening** — Close the three latent defects found by the 2026-08-30 GitHub Actions audit (silent
      HA-notification failure, missing job timeouts, action versions frozen by an accidental Renovate PR batch-close) plus
      the documentation drift found alongside them

> Phase 7 (`07-tolaria-add-on-scaffold`) has 3 plans and a CONTEXT from 2026-07-30 but no SUMMARY files and no entry in
> this roadmap or STATE.md. Its status is unresolved (Q-03 in `08-CONTEXT.md`). Phase 8 deliberately takes the next number
> rather than renumbering or absorbing it.

### 🚧 v1.3 opentofu-bridge (Phases 9-15) — PLANNING

**Milestone Goal:** Ship a Home Assistant Supervisor add-on (`terraform-bridge/`) that exposes the Supervisor HTTP API
as a bearer-authenticated, versioned JSON-over-HTTPS service, plus a co-located Go OpenTofu/Terraform provider
(`terraform-provider-homeassistant/`) so that Apps can be managed declaratively via `*.tf`. Both artifacts share the
repo's 3-file versioning scheme. Phase-1 scope: `homeassistant_addon` resource (CRUD) + `homeassistant_addon` data source
+ `homeassistant_supervisor_info` data source; `homeassistant_addon_repository` deferred to v1.4.

**Source:** `.planning/research/SUMMARY.md` (HIGH confidence on stack; MEDIUM on V1/V2 timeline; LOW on
SUPERVISOR_TOKEN-rotation-across-restart — empirical spike required in Phase 9).

- [x] **Phase 9: Bridge Foundation + Token Rotation Spike** — 4-file pattern, Go module, multi-stage Dockerfile,
      empirical verification of SUPERVISOR_TOKEN rotation and HA backup integration *(plans 01-04 complete;
      H-1 + §10 spike scripts authored; live spike execution deferred pending per-call authorization for
      Supervisor restart + backup snapshot — see `09-SUMMARY.md`)*
- [x] **Phase 10: Auth Layer + Structured Logging + Healthcheck** — Bearer generation, hash-at-rest, constant-time (completed 2026-08-31)
      compare, rotation with grace, log masking, /healthz
- [ ] **Phase 11: Bridge Read API** — /v1/version, /v1/addons, /v1/addons/{slug}/info, /v1/info
- [ ] **Phase 12: Bridge Write API + Critical-Addon Safety + Concurrency + State Index** — install/uninstall/start/stop/
      options, critical-addon guard, per-slug mutex, /v1/state/index, force-destroy nonce
- [ ] **Phase 13: Provider + Resource + Data Sources + Schema Handshake** — Provider compiles; version handshake;
      `homeassistant_addon` CRUD round-trips against Bridge; data sources; prevent_destroy default; typed diagnostics
- [ ] **Phase 14: Real-HA End-to-End Verification + Operator Documentation** — Empirical apply/destroy cycle against
      ha-nextgen (or haos-op3050-1); idempotency + drift observed; operator docs based on observed behavior
- [ ] **Phase 15: CI Hardening + Provider Install Workflow** — GitHub Actions build Bridge + test Provider workflows;
      `make install-provider` verified in CI; release-cycle end-to-end

## Phase Details

### Phase 9: Bridge Foundation + Token Rotation Spike

**Goal**: The `terraform-bridge/` add-on scaffolds into the repo following the 4-file pattern with a multi-stage Go
Dockerfile; the Go toolchain is locked for both Bridge and Provider; and the empirical low-confidence behaviors
(SUPERVISOR_TOKEN rotation across Supervisor restart + HA backup integration with `addon_config` mount) are verified
and documented before any auth or API work proceeds.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: TOFU-01, TOFU-02, TOFU-03, TOFU-05, AUTH-01, AUTH-06, OPS-02, OPS-05

**Success Criteria** (what must be TRUE):

1. The `terraform-bridge/` directory contains `config.yaml` (with `hassio_api: true`, `hassio_role: manager`,
   `ports: 8124/tcp: 8124`, **no** `ingress: true`), `build.yaml` (semver `X.Y.Z`), `Dockerfile` (multi-stage:
   `golang:1.25-alpine` → `ghcr.io/home-assistant/amd64-base:3.24`), and `run.sh`; no `.upstream.yaml` exists; the
   4-file pattern matches every other add-on in the repo
2. `terraform-provider-homeassistant/` is a Go module (Go 1.25) built from local source in the repo; same toolchain
   pinned via `go.mod` in both Bridge and Provider; `cd terraform-provider-homeassistant && go build ./...` succeeds
3. The Bridge image builds end-to-end via the multi-stage Dockerfile; `docker images terraform-bridge` reports size
   ≤ 30 MiB; the container logs one JSON object per line to stdout on first start
4. **Empirical spike (H-1) result is documented in `09-SUMMARY.md`:** restarting Supervisor either leaves
   `SUPERVISOR_TOKEN` stable or rotates it predictably; Bridge reads the token from env on every outbound Supervisor
   call (cheap) so a rotation is a non-error; logs include a `bridge.token_rotated=true` event when the value changes
   mid-process
5. **Empirical spike (PITFALLS §10) result is documented in `09-SUMMARY.md`:** HA backup integration includes files
   under `/data` mounted via `map: addon_config:rw` (the secondary state-copy mitigation is verified, not assumed)
6. `internal/validate-versions.sh` is extended to enforce that Bridge `build.yaml` and Provider `build.yaml` carry the
   same `X.Y.Z` portion; mismatched versions fail pre-commit
7. `run.sh` installs a SIGTERM trap that drains in-flight requests for up to 30s then exits, and a SIGHUP trap that
   reopens logs without restart; both behaviors are verified by running the container and sending the signals

**Plans**: 4 plans in 3 waves

Plans:
- [x] `09-01-PLAN.md` — terraform-bridge/ 4-file scaffold (Go module, chi, slog, Dockerfile multi-stage, README, DOCS stub)
- [x] `09-02-PLAN.md` — terraform-provider-homeassistant/ Go module + TOFU-05/TOFU-03 cross-artifact version sync
- [x] `09-03-PLAN.md` — SIGTERM/SIGHUP signal handling + verify-bridge-scaffold.sh + verify-bridge-no-token-leak.sh + pre-commit hooks
- [x] `09-04-PLAN.md` — Empirical H-1 (SUPERVISOR_TOKEN rotation) and PITFALLS §10 (HA backup + addon_config) spikes + 09-SUMMARY.md (checkpoint:human-verify resolved as deferred-execution; spike scripts committed and ready to run; live transcripts pending per-call authorization)

**UI hint**: no

### Phase 10: Auth Layer + Structured Logging + Healthcheck

**Goal**: The Bearer-token authentication primitive works end-to-end with predictable rotation semantics, log output
never leaks tokens, and the operational primitives (`/healthz`, structured JSON logs) are in place so every later
phase builds on a secure logging baseline.

**Depends on**: Phase 9

**Requirements**: AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-07, OPS-01, OPS-03

**Success Criteria** (what must be TRUE):

1. On first start, the Bridge generates a 256-bit Bearer token via `crypto/rand`, surfaces the plaintext exactly once
   via an add-on log line and the Options UI, and persists only its SHA-256 hash in `/data/bridge-token` (chmod 600);
   a restart does NOT surface the plaintext again
2. A request with `Authorization: Bearer <correct-token>` succeeds; a request with a wrong or missing token returns
   HTTP 401 with a typed `error_code: "unauthorized"`; the comparison uses `crypto/subtle.ConstantTimeCompare`
   against the on-disk hash
3. `POST /v1/auth/rotate` returns a new token; for the next 24 hours both the old and new tokens authenticate
   successfully; grace state persists across Bridge restart in `/data/bridge-token.grace`; after the grace window the
   old token returns 401
4. Bridge logs are one JSON object per line with fields `ts`, `level`, `msg`, `request_id`, `route`, `method`,
   `status`, `duration_ms`; the field names `bridge_token`, `Authorization`, and `SUPERVISOR_TOKEN` never appear in any
   log record; a unit test asserts this invariant by feeding crafted malicious headers and asserting none survive
5. `GET /healthz` (no auth required) returns HTTP 200 OK when Bridge can reach Supervisor (`/supervisor/info` round-trip
   ≤ 2s); returns HTTP 503 when Supervisor is unreachable; HA Supervisor's health-check polls this endpoint
6. The Bridge binds to `0.0.0.0:8124`; the add-on options schema exposes `bind_address` defaulting to "auto-detect
   Tailscale IP"; startup refuses to launch and logs a clear error if the detected interface is not a Tailscale
   interface (Phase-1 network-layer ACL boundary; TLS termination remains out of scope)

**Plans**: 3 plans in 3 waves

Plans:
- [ ] `10-01-PLAN.md` — TokenStore (crypto/rand + SHA-256 + chmod 600 + ConstantTimeCompare) + auth middleware (Bearer extraction + 401 typed error) + bind-address resolver (Tailscale /sys/class/net + bind_allowed_subnets + 0.0.0.0 refusal) + Supervisor HTTP client (token-injecting RoundTripper, re-reads env per call) + /v1/whoami test endpoint + config.yaml schema for bind_address + bind_allowed_subnets
- [x] `10-02-PLAN.md` — Scrubbing slog.Handler wrapper (case-insensitive key-name mask: Authorization, Bearer, bridge_token, SUPERVISOR_TOKEN, supervisor_token, bearer, token, password → <redacted>) + chi RequestLogger middleware (OPS-01 fields: request_id, route, method, status, duration_ms; strips Authorization from r.Header.Clone() before logging) + GET /healthz (probes /supervisor/ping with 2s timeout; 200 + HealthResponse on success, 503 + empty body on failure) + AUTH-05 invariant unit tests + strengthened internal/verify-bridge-no-token-leak.sh (exactly-once plaintext + actor_token_fp positive control + OPS-01 field assertions) + pre-commit hook entry
- [ ] `10-03-PLAN.md` — TokenStore.Rotate() (new plaintext + atomic persist + grace file /data/bridge-token.grace chmod 600 with 24-hour expiry) + POST /v1/auth/rotate handler (requires valid bearer per D-12; emits bridge.token.rotated audit record with fingerprints only) + DOCS.md operator procedure (issuance/rotation/recovery) + 10-SUMMARY.md

**UI hint**: no

### Phase 11: Bridge Read API

**Goal**: The Bridge exposes the read-only surface (`/v1/version`, `/v1/addons`, `/v1/addons/{slug}/info`, `/v1/info`)
that the Provider's Configure handshake and adoption logic depend on; reads are observable end-to-end without any
write operations.

**Depends on**: Phase 10

**Requirements**: BRIDGE-01, BRIDGE-02, BRIDGE-03, BRIDGE-10

**Success Criteria** (what must be TRUE):

1. `curl -H "Authorization: Bearer $TOKEN" http://<bridge>:8124/v1/version` returns JSON
   `{bridge_version, schema_version, min_provider_version, max_provider_version}`; `schema_version` follows semver
   and increments on every breaking Bridge API change
2. `GET /v1/addons` returns a JSON array of all installed add-ons (wrapping Supervisor `/apps` with V1 fallback to
   `/addons` when `SUPERVISOR_V2_API` flag is off); each entry includes `slug`, `name`, `version`, `state`,
   `started`
3. `GET /v1/addons/<slug>/info` returns the Supervisor `/apps/<slug>/info` payload (`version`, `state`, `started`,
   `options`, `boot`, `slug`, `repository`); unknown slugs return HTTP 404 + `error_code: "not_found"`
4. `GET /v1/info` (no auth) returns `{bridge_version, supervisor_version, uptime_seconds, state_file_path}` for use
   in `terraform_data` and `lifecycle.precondition` blocks

**Plans**: TBD

**UI hint**: no

### Phase 12: Bridge Write API + Critical-Addon Safety + Concurrency + State Index

**Goal**: All destructive and mutating operations work end-to-end against Supervisor with two-step confirmation for
uninstall/options-change, an unmodifiable critical-addon list, per-slug write serialization, and a state-index
endpoint that lets HA backup integration cover tfstate.

**Depends on**: Phase 11

**Requirements**: BRIDGE-04, BRIDGE-05, BRIDGE-06, BRIDGE-07, BRIDGE-08, BRIDGE-09, STATE-02, STATE-03, LIFE-01,
LIFE-03

**Success Criteria** (what must be TRUE):

1. `POST /v1/addons/<slug>/install` triggers Supervisor install; when Supervisor returns a `job_id`, Bridge polls
   `/jobs/<id>` and returns the final `apps/<slug>/info` payload to the caller; install of an already-installed add-on
   returns 409 `error_code: "already_installed"`
2. `POST /v1/addons/<slug>/start`, `/stop`, `/uninstall` each wrap their Supervisor equivalents and return the typed
   result (`204 No Content` for uninstall success); `POST /v1/addons/<slug>/options` first calls
   `/apps/<slug>/options/validate` and surfaces `valid` + `pwned` fields to the caller as typed diagnostics
3. Bridge refuses uninstall / restart / options-change for any slug in `critical_addons` (default
   `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`) with HTTP 403 + `error_code: "critical_addon_protected"`;
   the list is exposed as a Bridge options schema field
4. Bridge forwards Supervisor typed errors as HTTP responses: 404 (`not_found`), 403 (`prevented_destroy` or
   `critical_addon`), 409 (`already_installed` — adopted as success by Provider), 423 (`locked`), 5xx transient (Provider
   retries per `terraform-plugin-framework-timeouts`)
5. Destructive Bridge operations (uninstall, options change) require the request header
   `X-Force-Destroy: <bridge_issued_nonce>`; the Bridge issues a fresh nonce via `POST /v1/auth/nonce` and accepts it
   once within 60 seconds; nonces older than 60 seconds or already-used return 401 + `error_code: "nonce_expired"` or
   `"nonce_used"`
6. Two concurrent Provider applies targeting the same slug are serialized by an in-process per-slug mutex; the
   second waits without erroring; `GET /v1/state/index` returns the list of currently-known state files in `/data`
   with their SHA-256 digests

**Plans**: TBD

**UI hint**: no

### Phase 13: Provider + Resource + Data Sources + Schema Handshake

**Goal**: The `terraform-provider-homeassistant` Go module compiles, serves via `providerserver.Serve()`, and
exposes a working `homeassistant_addon` resource (CRUD + import + timeouts) plus both data sources against the
Bridge; `prevent_destroy` defaults to true; Bridge errors surface as typed Provider diagnostics.

**Depends on**: Phase 12

**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04, PROV-05, PROV-06, PROV-07, PROV-08, PROV-09, PROV-10, PROV-11,
PROV-12, LIFE-02, LIFE-04, STATE-01

**Success Criteria** (what must be TRUE):

1. `cd terraform-provider-homeassistant && go build ./...` succeeds with Go 1.25+; the Provider serves via
   `providerserver.Serve()` and supports OpenTofu ≥ 1.12 and Terraform ≥ 1.5 (protocol v6); Provider docs note the
   user must configure the OpenTofu local backend with `path = "/data/terraform.tfstate"` (or mirror the file via
   the add-on's share volume when running off-host)
2. Provider `Configure` calls Bridge `GET /v1/version` at startup and refuses to operate (typed diagnostic) when
   `schema_version < min_provider_version` or `schema_version > max_provider_version`
3. Resource `homeassistant_addon "test"` with required `slug` + optional `repository`, `url`, `options`
   (TypeMap<String>), `start` (default `true`), `boot` (`auto`/`manual`/`manual_only`); computed outputs
   `version`, `state`, `started`, `hostname`; Create calls `POST /install`, Update calls `POST /options`, Delete calls
   `POST /uninstall`; Read is idempotent and returns empty state on 404 (so Delete on a missing add-on is a no-op)
4. `terraform import homeassistant_addon.test <slug>` works against an existing add-on without prior installation
   (adoption); Create flow is adoption-aware (`GET info` first; only `POST /install` if missing); `409
   already_installed` is treated as success
5. Per-operation timeouts via `terraform-plugin-framework-timeouts` with DOCS.md defaults
   `create = 10m, update = 2m, delete = 5m`; `UseStateForUnknown()` plan modifier on the `state` attribute so
   spurious diffs do not appear on every refresh; import IDs accept `{slug}` or `{repository}/{slug}` formats
6. Data source `homeassistant_addon` returns the full info payload for read-only use in `terraform_data` and other
   resources' attribute references; data source `homeassistant_supervisor_info` is usable in
   `lifecycle.precondition` blocks
7. Bridge error responses surface as typed Provider diagnostics: 403 with `critical_addons` or
   `lifecycle.prevent_destroy = true` explanation; 423 with "another operation is in flight, retry in 30s"; 5xx with
   "transient Supervisor failure, retry per timeouts"; DOCS.md documents `lifecycle.prevent_destroy = true` as the
   default recommended option (Provider does not force it — users opt in)

**Plans**: TBD

**UI hint**: no

### Phase 14: Real-HA End-to-End Verification + Operator Documentation

**Goal**: Apply/destroy/idempotency/drift behaviors are empirically verified against a live Home Assistant host
(ha-nextgen or haos-op3050-1) using the built Provider and a Bridge add-on installed in production; the operator
documentation (Bridge `README.md` + `DOCS.md`) is written based on observed real-world behavior, including error
remediation and troubleshooting.

**Depends on**: Phase 13

**Requirements**: OPS-04

**Success Criteria** (what must be TRUE):

1. `make install-provider` installs the built Provider binary to
   `~/.terraform.d/plugins/registry.opentofu.org/akentner/homeassistant/<version>/linux_amd64/`; OpenTofu discovers it
   via the `dev_overrides` workflow; `tofu init/plan/apply` against Bridge on a real HA host installs a test add-on
   end-to-end without manual intervention
2. Drift behavior observed: changing `options` in `*.tf` and re-running `tofu apply` triggers Update; changing the
   `state` attribute does NOT trigger Update (`UseStateForUnknown()`); 404 on `GET info` triggers a recreate plan
   (not a destroy plan)
3. Idempotency proven: running `tofu apply` five consecutive times yields "No changes" on every run after the first;
   `lifecycle.prevent_destroy = true` blocks accidental destroy with a clear error
4. Error codes empirically mapped: each Bridge error response (403 `critical_addon`, 423 `locked`, 409
   `already_installed`, 5xx transient) produces the documented Provider diagnostic; observed behaviors are captured
   verbatim in `DOCS.md#troubleshooting`
5. Bridge `README.md` and `DOCS.md` are complete: install steps via HA add-on store, token issuance + rotation
   procedure, OpenTofu provider install command, an example `*.tf` file covering every resource attribute, every
   error code with documented remediation, and a troubleshooting section with at least three real observed issues

**Plans**: TBD

**UI hint**: no

### Phase 15: CI Hardening + Provider Install Workflow

**Goal**: The Bridge add-on and the Provider source are both built and tested by GitHub Actions on every push;
`make install-provider` is verified end-to-end in CI; the three-file versioning scheme is enforced across both
artifacts in a single release cycle.

**Depends on**: Phase 14

**Requirements**: TOFU-04

**Success Criteria** (what must be TRUE):

1. `.github/workflows/build-terraform-bridge.yml` builds the multi-stage Bridge image on push to `main` touching
   `terraform-bridge/**`; every job carries an explicit `timeout-minutes` (per Phase-8 pattern); image is pushed to
   `ghcr.io/akentner/homeassistant-addons/terraform-bridge`
2. `.github/workflows/test-terraform-provider.yml` runs `go test ./...`, `go vet ./...`, and `gofmt -l` against the
   Provider source on push to `main` touching `terraform-provider-homeassistant/**`; job has explicit `timeout-minutes`
3. CI verifies `make install-provider` end-to-end: builds the Provider, installs it to a temporary plugins directory,
   starts an ephemeral test Bridge fixture, runs `tofu init/plan` against it, and confirms the schema-version
   handshake succeeds — proving the install workflow is not broken by a future Provider release
4. Pushing the `<addon>/v<version>` git tag triggers both Bridge build and Provider test workflows; pre-commit
   `validate-versions.sh` blocks commits where Bridge `build.yaml` and Provider `build.yaml` versions drift; the
   existing pre-push hook (`internal/check-version-tags.sh`) extends cleanly to cover the new add-on

**Plans**: TBD

**UI hint**: no

## Progress

| Phase                                | Milestone | Plans Complete | Status      | Completed |
| ------------------------------------ | --------- | -------------- | ----------- | --------- |
| 1. Quality Fixes                     | v1.0      | 2/2            | Complete    | 2026-04-03 |
| 2. Auto-Update Workflow              | v1.0      | 1/1            | Complete    | 2026-04-04 |
| 3. Meridian Add-on                   | v1.0      | 3/3            | Complete    | 2026-04-04 |
| 4. Scaffold + Ingress Validation     | v1.1      | 3/3            | Complete    | 2026-06-27 |
| 5. Multi-Namespace + Dynamic Config  | v1.1      | 1/1            | Complete    | 2026-06-27 |
| 6. Git Integration                   | v1.1      | 2/2            | Complete    | 2026-06-28 |
| 8. CI/CD Hardening                   | v1.2      | 3/4 (1 partial + 1 gap-closure pending) | Gap closure pending | —  |
| 9. Bridge Foundation + Token Spike   | v1.3      | 3/4 | In Progress|  |
| 10. Auth + Logging + Healthcheck     | v1.3      | 3/3 | Complete   | 2026-08-31 |
| 11. Bridge Read API                  | v1.3      | 0/TBD          | Not started | —         |
| 12. Bridge Write API + Safety        | v1.3      | 0/TBD          | Not started | —         |
| 13. Provider + Resource + Data       | v1.3      | 0/TBD          | Not started | —         |
| 14. Real-HA E2E + Docs               | v1.3      | 0/TBD          | Not started | —         |
| 15. CI + Provider Install            | v1.3      | 0/TBD          | Not started | —         |

---

_Last updated: 2026-08-31 — Milestone v1.3 opentofu-bridge roadmap written (Phases 9-15, 46 requirements mapped, 7
phases). Phase 8 (CI/CD Hardening) continues in parallel; resume via `/gsd-execute-phase 8 --gaps-only` whenever the
Cloudflare service token + GitHub secrets are in place._