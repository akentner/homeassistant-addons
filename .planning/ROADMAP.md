# Roadmap: Home Assistant Add-ons Repository

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-04-04)
- ✅ **v1.1 markdown-renderer** — Phases 4-6 (complete 2026-06-28)
- 📋 **v1.2 CI/CD Hardening** — Phase 8 (planned 2026-08-30; gap-closure `08-05-GAP-PLAN.md` awaiting Cloudflare setup)
- 🚧 **v1.3 opentofu-bridge** — Phases 9-15 (essentially complete 2026-09-05; Phase 15 release pending v1.2
  Cloudflare-setup prerequisite)
- 📋 **v1.4 iac-runner** — Phases 16-19 (planning 2026-09-06)

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
      HA-notification failure, missing job timeouts, action versions frozen by an accidental Renovate PR batch-close)
      plus the documentation drift found alongside them

> Phase 7 (`07-tolaria-add-on-scaffold`) has 3 plans and a CONTEXT from 2026-07-30 but no SUMMARY files and no entry in
> this roadmap or STATE.md. Its status is unresolved (Q-03 in `08-CONTEXT.md`). Phase 8 deliberately takes the next
> number rather than renumbering or absorbing it.

### 🚧 v1.3 opentofu-bridge (Phases 9-15) — PLANNING

**Milestone Goal:** Ship a Home Assistant Supervisor add-on (`terraform-bridge/`) that exposes the Supervisor HTTP API
as a bearer-authenticated, versioned JSON-over-HTTPS service, plus a co-located Go OpenTofu/Terraform provider
(`terraform-provider-homeassistant/`) so that Apps can be managed declaratively via `*.tf`. Both artifacts share the
repo's 3-file versioning scheme. Phase-1 scope: `homeassistant_addon` resource (CRUD) + `homeassistant_addon` data
source

- `homeassistant_supervisor_info` data source; `homeassistant_addon_repository` deferred to v1.4.

**Source:** `.planning/research/SUMMARY.md` (HIGH confidence on stack; MEDIUM on V1/V2 timeline; LOW on
SUPERVISOR_TOKEN-rotation-across-restart — empirical spike required in Phase 9).

- [x] **Phase 9: Bridge Foundation + Token Rotation Spike** — 4-file pattern, Go module, multi-stage Dockerfile,
      empirical verification of SUPERVISOR_TOKEN rotation and HA backup integration _(plans 01-04 complete; H-1 + §10
      spike scripts authored; live spike execution deferred pending per-call authorization for Supervisor restart +
      backup snapshot — see `09-SUMMARY.md`)_
- [x] **Phase 10: Auth Layer + Structured Logging + Healthcheck** — Bearer generation, hash-at-rest, constant-time
      (completed 2026-08-31) compare, rotation with grace, log masking, /healthz
- [ ] **Phase 11: Bridge Read API** — /v1/version, /v1/addons, /v1/addons/{slug}/info, /v1/info
- [ ] **Phase 12: Bridge Write API + Critical-Addon Safety + Concurrency + State Index** — install/uninstall/start/stop/
      options, critical-addon guard, per-slug mutex, /v1/state/index, force-destroy nonce
- [x] **Phase 13: Provider + Resource + Data Sources + Schema Handshake** — Provider compiles; version handshake;
      (completed 2026-09-05) `homeassistant_addon` CRUD round-trips against Bridge; data sources; prevent_destroy
      default; typed diagnostics
- [x] **Phase 14: Real-HA End-to-End Verification + Operator Documentation** — (completed 2026-09-05) Empirical
      apply/destroy cycle foundation; 12 per-error_code verify scenarios; operator docs based on captured diagnostics
- [x] **Phase 15: CI Hardening + Provider Install Workflow** — GitHub Actions build Bridge + test Provider workflows;
      (completed 2026-08-31) `make install-provider` verified in CI; release-cycle end-to-end

### 📋 v1.4 iac-runner (Phases 16-19) — PLANNING

**Milestone Goal:** Ship a Home Assistant Supervisor add-on (`iac-runner/`) that clones a Git repo (e.g.
`homelab-infra`), runs OpenTofu/Terraform `plan`/`apply` against homelab servers (Tailscale-reachable), persists state
in R2 (default), S3-compatible, or local backend, and surfaces run status + manual triggers as Home Assistant entities
via MQTT Discovery. Manual REST trigger only — webhook-Auto-Rollout deferred to v1.5.

**Source:** Conversation 2026-09-06. RESEARCH skipped by explicit decision (scope clear from conversation; patterns
reused from `terraform-bridge` and `markdown-renderer`). 32 requirements mapped across AUTHR/STBK/SEC/GIT/RUN/MQTT/OBS.

- [x] **Phase 16: iac-runner Scaffold + Auth + State Backends + Healthcheck** — 4-file pattern, Go module (completed
      2026-09-06) (`golang:1.25-alpine` → HA base 3.24, multi-stage), Bearer-auth without `SUPERVISOR_TOKEN`,
      Tailscale-bind-gate, three state backends (r2/s3/local) with `use_lockfile` where applicable, `/healthz`,
      `/v1/version`, `/data/keys/` chmod-600 enforcement, log-scrubbing
- [ ] **Phase 17: Git Integration + Apply Job System** — repo clone at startup, SSH deploy-key pull endpoint,
      `POST /v1/plan` + `POST /v1/apply` with per-repo mutex, `GET /v1/runs/{id}` with paginated output, `tofu` output
      redaction, run-history rotation
- [ ] **Phase 18: MQTT Discovery + HA Sensoren + Buttons** — `mqtt:need` service connection, three sensors
      (`last_run_status`, `last_apply_at`, `last_error`) + two buttons (`run_plan`, `run_apply`) with 30s debounce;
      verified by IRUN-H-2 spike
- [ ] **Phase 19: E2E Verification + DOCS + Operator Runbook** — live-HA E2E with `local_file`-provider fixture,
      drift-test, idempotency, all three state backends verified, DOCS.md + README.md from observed behavior

## Phase Details

### Phase 9: Bridge Foundation + Token Rotation Spike

**Goal**: The `terraform-bridge/` add-on scaffolds into the repo following the 4-file pattern with a multi-stage Go
Dockerfile; the Go toolchain is locked for both Bridge and Provider; and the empirical low-confidence behaviors
(SUPERVISOR_TOKEN rotation across Supervisor restart + HA backup integration with `addon_config` mount) are verified and
documented before any auth or API work proceeds.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: TOFU-01, TOFU-02, TOFU-03, TOFU-05, AUTH-01, AUTH-06, OPS-02, OPS-05

**Success Criteria** (what must be TRUE):

1. The `terraform-bridge/` directory contains `config.yaml` (with `hassio_api: true`, `hassio_role: manager`,
   `ports: 8124/tcp: 8124`, **no** `ingress: true`), `build.yaml` (semver `X.Y.Z`), `Dockerfile` (multi-stage:
   `golang:1.25-alpine` → `ghcr.io/home-assistant/amd64-base:3.24`), and `run.sh`; no `.upstream.yaml` exists; the
   4-file pattern matches every other add-on in the repo
2. `terraform-provider-homeassistant/` is a Go module (Go 1.25) built from local source in the repo; same toolchain
   pinned via `go.mod` in both Bridge and Provider; `cd terraform-provider-homeassistant && go build ./...` succeeds
3. The Bridge image builds end-to-end via the multi-stage Dockerfile; `docker images terraform-bridge` reports size ≤ 30
   MiB; the container logs one JSON object per line to stdout on first start
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

- [x] `09-01-PLAN.md` — terraform-bridge/ 4-file scaffold (Go module, chi, slog, Dockerfile multi-stage, README, DOCS
      stub)
- [x] `09-02-PLAN.md` — terraform-provider-homeassistant/ Go module + TOFU-05/TOFU-03 cross-artifact version sync
- [x] `09-03-PLAN.md` — SIGTERM/SIGHUP signal handling + verify-bridge-scaffold.sh + verify-bridge-no-token-leak.sh +
      pre-commit hooks
- [x] `09-04-PLAN.md` — Empirical H-1 (SUPERVISOR_TOKEN rotation) and PITFALLS §10 (HA backup + addon_config) spikes +
      09-SUMMARY.md (checkpoint:human-verify resolved as deferred-execution; spike scripts committed and ready to run;
      live transcripts pending per-call authorization)

**UI hint**: no

### Phase 10: Auth Layer + Structured Logging + Healthcheck

**Goal**: The Bearer-token authentication primitive works end-to-end with predictable rotation semantics, log output
never leaks tokens, and the operational primitives (`/healthz`, structured JSON logs) are in place so every later phase
builds on a secure logging baseline.

**Depends on**: Phase 9

**Requirements**: AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-07, OPS-01, OPS-03

**Success Criteria** (what must be TRUE):

1. On first start, the Bridge generates a 256-bit Bearer token via `crypto/rand`, surfaces the plaintext exactly once
   via an add-on log line and the Options UI, and persists only its SHA-256 hash in `/data/bridge-token` (chmod 600); a
   restart does NOT surface the plaintext again
2. A request with `Authorization: Bearer <correct-token>` succeeds; a request with a wrong or missing token returns HTTP
   401 with a typed `error_code: "unauthorized"`; the comparison uses `crypto/subtle.ConstantTimeCompare` against the
   on-disk hash
3. `POST /v1/auth/rotate` returns a new token; for the next 24 hours both the old and new tokens authenticate
   successfully; grace state persists across Bridge restart in `/data/bridge-token.grace`; after the grace window the
   old token returns 401
4. Bridge logs are one JSON object per line with fields `ts`, `level`, `msg`, `request_id`, `route`, `method`, `status`,
   `duration_ms`; the field names `bridge_token`, `Authorization`, and `SUPERVISOR_TOKEN` never appear in any log
   record; a unit test asserts this invariant by feeding crafted malicious headers and asserting none survive
5. `GET /healthz` (no auth required) returns HTTP 200 OK when Bridge can reach Supervisor (`/supervisor/info` round-trip
   ≤ 2s); returns HTTP 503 when Supervisor is unreachable; HA Supervisor's health-check polls this endpoint
6. The Bridge binds to `0.0.0.0:8124`; the add-on options schema exposes `bind_address` defaulting to "auto-detect
   Tailscale IP"; startup refuses to launch and logs a clear error if the detected interface is not a Tailscale
   interface (Phase-1 network-layer ACL boundary; TLS termination remains out of scope)

**Plans**: 3 plans in 3 waves

Plans:

- [ ] `10-01-PLAN.md` — TokenStore (crypto/rand + SHA-256 + chmod 600 + ConstantTimeCompare) + auth middleware (Bearer
      extraction + 401 typed error) + bind-address resolver (Tailscale /sys/class/net + bind_allowed_subnets + 0.0.0.0
      refusal) + Supervisor HTTP client (token-injecting RoundTripper, re-reads env per call) + /v1/whoami test
      endpoint + config.yaml schema for bind_address + bind_allowed_subnets
- [x] `10-02-PLAN.md` — Scrubbing slog.Handler wrapper (case-insensitive key-name mask: Authorization, Bearer,
      bridge_token, SUPERVISOR_TOKEN, supervisor_token, bearer, token, password → <redacted>) + chi RequestLogger
      middleware (OPS-01 fields: request_id, route, method, status, duration_ms; strips Authorization from
      r.Header.Clone() before logging) + GET /healthz (probes /supervisor/ping with 2s timeout; 200 + HealthResponse on
      success, 503 + empty body on failure) + AUTH-05 invariant unit tests + strengthened
      internal/verify-bridge-no-token-leak.sh (exactly-once plaintext + actor_token_fp positive control + OPS-01 field
      assertions) + pre-commit hook entry
- [ ] `10-03-PLAN.md` — TokenStore.Rotate() (new plaintext + atomic persist + grace file /data/bridge-token.grace chmod
      600 with 24-hour expiry) + POST /v1/auth/rotate handler (requires valid bearer per D-12; emits
      bridge.token.rotated audit record with fingerprints only) + DOCS.md operator procedure
      (issuance/rotation/recovery) + 10-SUMMARY.md

**UI hint**: no

### Phase 11: Bridge Read API

**Goal**: The Bridge exposes the read-only surface (`/v1/version`, `/v1/addons`, `/v1/addons/{slug}/info`, `/v1/info`)
that the Provider's Configure handshake and adoption logic depend on; reads are observable end-to-end without any write
operations.

**Depends on**: Phase 10

**Requirements**: BRIDGE-01, BRIDGE-02, BRIDGE-03, BRIDGE-10

**Success Criteria** (what must be TRUE):

1. `curl -H "Authorization: Bearer $TOKEN" http://<bridge>:8124/v1/version` returns JSON
   `{bridge_version, schema_version, min_provider_version, max_provider_version}`; `schema_version` follows semver and
   increments on every breaking Bridge API change
2. `GET /v1/addons` returns a JSON array of all installed add-ons (wrapping Supervisor `/apps` with V1 fallback to
   `/addons` when `SUPERVISOR_V2_API` flag is off); each entry includes `slug`, `name`, `version`, `state`, `started`
3. `GET /v1/addons/<slug>/info` returns the Supervisor `/apps/<slug>/info` payload (`version`, `state`, `started`,
   `options`, `boot`, `slug`, `repository`); unknown slugs return HTTP 404 + `error_code: "not_found"`
4. `GET /v1/info` (no auth) returns `{bridge_version, supervisor_version, uptime_seconds, state_file_path}` for use in
   `terraform_data` and `lifecycle.precondition` blocks

**Plans**: TBD

**UI hint**: no

### Phase 12: Bridge Write API + Critical-Addon Safety + Concurrency + State Index

**Goal**: All destructive and mutating operations work end-to-end against Supervisor with two-step confirmation for
uninstall/options-change, an unmodifiable critical-addon list, per-slug write serialization, and a state-index endpoint
that lets HA backup integration cover tfstate.

**Depends on**: Phase 11

**Requirements**: BRIDGE-04, BRIDGE-05, BRIDGE-06, BRIDGE-07, BRIDGE-08, BRIDGE-09, STATE-02, STATE-03, LIFE-01, LIFE-03

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
   `critical_addon`), 409 (`already_installed` — adopted as success by Provider), 423 (`locked`), 5xx transient
   (Provider retries per `terraform-plugin-framework-timeouts`)
5. Destructive Bridge operations (uninstall, options change) require the request header
   `X-Force-Destroy: <bridge_issued_nonce>`; the Bridge issues a fresh nonce via `POST /v1/auth/nonce` and accepts it
   once within 60 seconds; nonces older than 60 seconds or already-used return 401 + `error_code: "nonce_expired"` or
   `"nonce_used"`
6. Two concurrent Provider applies targeting the same slug are serialized by an in-process per-slug mutex; the second
   waits without erroring; `GET /v1/state/index` returns the list of currently-known state files in `/data` with their
   SHA-256 digests

**Plans**: TBD

**UI hint**: no

### Phase 13: Provider + Resource + Data Sources + Schema Handshake

**Goal**: The `terraform-provider-homeassistant` Go module compiles, serves via `providerserver.Serve()`, and exposes a
working `homeassistant_addon` resource (CRUD + import + timeouts) plus both data sources against the Bridge;
`prevent_destroy` defaults to true; Bridge errors surface as typed Provider diagnostics.

**Depends on**: Phase 12

**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04, PROV-05, PROV-06, PROV-07, PROV-08, PROV-09, PROV-10, PROV-11,
PROV-12, LIFE-02, LIFE-04, STATE-01

**Success Criteria** (what must be TRUE):

1. `cd terraform-provider-homeassistant && go build ./...` succeeds with Go 1.25+; the Provider serves via
   `providerserver.Serve()` and supports OpenTofu ≥ 1.12 and Terraform ≥ 1.5 (protocol v6); Provider docs note the user
   must configure the OpenTofu local backend with `path = "/data/terraform.tfstate"` (or mirror the file via the
   add-on's share volume when running off-host)
2. Provider `Configure` calls Bridge `GET /v1/version` at startup and refuses to operate (typed diagnostic) when
   `schema_version < min_provider_version` or `schema_version > max_provider_version`
3. Resource `homeassistant_addon "test"` with required `slug` + optional `repository`, `url`, `options`
   (TypeMap<String>), `start` (default `true`), `boot` (`auto`/`manual`/`manual_only`); computed outputs `version`,
   `state`, `started`, `hostname`; Create calls `POST /install`, Update calls `POST /options`, Delete calls
   `POST /uninstall`; Read is idempotent and returns empty state on 404 (so Delete on a missing add-on is a no-op)
4. `terraform import homeassistant_addon.test <slug>` works against an existing add-on without prior installation
   (adoption); Create flow is adoption-aware (`GET info` first; only `POST /install` if missing);
   `409 already_installed` is treated as success
5. Per-operation timeouts via `terraform-plugin-framework-timeouts` with DOCS.md defaults
   `create = 10m, update = 2m, delete = 5m`; `UseStateForUnknown()` plan modifier on the `state` attribute so spurious
   diffs do not appear on every refresh; import IDs accept `{slug}` or `{repository}/{slug}` formats
6. Data source `homeassistant_addon` returns the full info payload for read-only use in `terraform_data` and other
   resources' attribute references; data source `homeassistant_supervisor_info` is usable in `lifecycle.precondition`
   blocks
7. Bridge error responses surface as typed Provider diagnostics: 403 with `critical_addons` or
   `lifecycle.prevent_destroy = true` explanation; 423 with "another operation is in flight, retry in 30s"; 5xx with
   "transient Supervisor failure, retry per timeouts"; DOCS.md documents `lifecycle.prevent_destroy = true` as the
   default recommended option (Provider does not force it — users opt in)

**Plans**: TBD

- [x] 13-01-PLAN.md
- [x] 13-02-PLAN.md
- [x] 13-03-PLAN.md

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
   `state` attribute does NOT trigger Update (`UseStateForUnknown()`); 404 on `GET info` triggers a recreate plan (not a
   destroy plan)
3. Idempotency proven: running `tofu apply` five consecutive times yields "No changes" on every run after the first;
   `lifecycle.prevent_destroy = true` blocks accidental destroy with a clear error
4. Error codes empirically mapped: each Bridge error response (403 `critical_addon`, 423 `locked`, 409
   `already_installed`, 5xx transient) produces the documented Provider diagnostic; observed behaviors are captured
   verbatim in `DOCS.md#troubleshooting`
5. Bridge `README.md` and `DOCS.md` are complete: install steps via HA add-on store, token issuance + rotation
   procedure, OpenTofu provider install command, an example `*.tf` file covering every resource attribute, every error
   code with documented remediation, and a troubleshooting section with at least three real observed issues

**Plans**:

- [x] 14-01-PLAN.md
- [x] 14-02-PLAN.md
- [x] 14-03-PLAN.md

**UI hint**: no

### Phase 15: CI Hardening + Provider Install Workflow

**Goal**: The Bridge add-on and the Provider source are both built and tested by GitHub Actions on every push;
`make install-provider` is verified end-to-end in CI; the three-file versioning scheme is enforced across both artifacts
in a single release cycle.

**Depends on**: Phase 14

**Requirements**: TOFU-04

**Success Criteria** (what must be TRUE):

1. `.github/workflows/build-terraform-bridge.yml` builds the multi-stage Bridge image on push to `main` touching
   `terraform-bridge/**`; every job carries an explicit `timeout-minutes` (per Phase-8 pattern); image is pushed to
   `ghcr.io/akentner/homeassistant-addons/terraform-bridge`
2. `.github/workflows/test-terraform-provider.yml` runs `go test ./...`, `go vet ./...`, and `gofmt -l` against the
   Provider source on push to `main` touching `terraform-provider-homeassistant/**`; job has explicit `timeout-minutes`
3. CI verifies `make install-provider` end-to-end: builds the Provider, installs it to a temporary plugins directory,
   starts an ephemeral test Bridge fixture, runs `tofu init/plan` against it, and confirms the schema-version handshake
   succeeds — proving the install workflow is not broken by a future Provider release
4. Pushing the `<addon>/v<version>` git tag triggers both Bridge build and Provider test workflows; pre-commit
   `validate-versions.sh` blocks commits where Bridge `build.yaml` and Provider `build.yaml` versions drift; the
   existing pre-push hook (`internal/check-version-tags.sh`) extends cleanly to cover the new add-on

**Plans**: 3 plans

Plans:

- [ ] `15-01-PLAN.md` — `make install-provider` target (TOFU-04) + dev_overrides hint
- [ ] `15-02-PLAN.md` — Bridge build + Provider test GitHub Actions workflows + tag triggers + hermetic verifier
- [ ] `15-03-PLAN.md` — `/v1/version` handler + test Bridge fixture + E2E CI verification workflow

**UI hint**: no

### Phase 16: iac-runner Scaffold + Auth + State Backends + Healthcheck

**Goal**: The `iac-runner/` add-on scaffolds into the repo following the 4-file pattern with a multi-stage Go Dockerfile
(no `SUPERVISOR_TOKEN` needed); Bearer-auth and Tailscale-bind-gate mirror the proven `terraform-bridge` pattern; the
three state backends (r2 default, s3, local) are wired and selectable from Options; `/healthz` and `/v1/version` are
exposed; secrets under `/data/keys/` are validated at startup.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: AUTHR-01, AUTHR-02, AUTHR-03, AUTHR-04, STBK-01, STBK-02, STBK-03, STBK-04, STBK-05, SEC-01, SEC-02,
OBS-01

**Plans**: 3 plans in 3 waves

Plans:

- [x] 16-01-PLAN.md — Scaffold + Auth + Bind + Signal + /v1/auth/rotate (AUTHR-01..04, OBS-01 layer 2)
- [x] 16-02-PLAN.md — Log scrubbing + /data/keys/ validator + state backends r2/s3/local + real /healthz (SEC-01,
      SEC-02, STBK-01..05)
- [x] 16-03-PLAN.md — GET /v1/version + operator DOCS.md + README + pre-commit config

**Success Criteria** (what must be TRUE):

1. The `iac-runner/` directory contains `config.yaml` (with `host_network: true`, `homeassistant_api: true`,
   `services: ["mqtt:need"]`, `ports: 8125/tcp: 8125`, **no** `hassio_api: true`, **no** `ingress: true`), `build.yaml`
   (semver `X.Y.Z`), `Dockerfile` (multi-stage: `golang:1.25-alpine` → HA amd64-base 3.24), and `run.sh`; no
   `.upstream.yaml` exists; the 4-file pattern matches every other add-on in the repo
2. Bearer-token auth follows the `terraform-bridge` pattern: 256-bit token via `crypto/rand`, SHA-256 hash stored at
   `/data/iac-runner-token` (chmod 600), validation via `crypto/subtle.ConstantTimeCompare`, plaintext surfaced exactly
   once via add-on log line + Options UI on first start; restart does NOT re-emit the plaintext
3. The add-on binds to `0.0.0.0:8125`; startup auto-detects the first `tailscale*` interface in `/sys/class/net` and
   binds to its IPv4 address; explicit IP accepted only if Tailscale- or `bind_allowed_subnets`-allowed;
   `bind_address: "0.0.0.0"` always refused
4. Options schema exposes `state_backend: list(match(^(r2|s3|local)$))` defaulting to `r2`; backend-specific options
   (`r2_bucket`, `s3_endpoint`, etc.) are validated against the chosen backend at startup; wrong/missing credentials
   cause startup failure with a clear error message (no degraded mode)
5. State-backend Go interface has three implementations (`r2`, `s3`, `local`); for `r2`/`s3` the add-on is configured to
   invoke `tofu` with `use_lockfile = true`; for `local` the lock is file-based via `/data/terraform.tfstate.lock`. R2
   lockfile semantics verified empirically (IRUN-H-1 spike result documented in `16-SUMMARY.md`)
6. `POST /v1/auth/rotate` returns a new token; for 24 hours both old and new authenticate; grace state persists in
   `/data/iac-runner-token.grace` (chmod 600) across restart
7. `GET /healthz` (no auth) returns HTTP 200 OK when `tofu` binary is on PATH and `/data/keys/` chmod-600 check passes;
   HTTP 503 otherwise
8. `GET /v1/version` returns JSON `{runner_version, schema_version, min_supported_opentofu, max_supported_opentofu}`;
   `schema_version` follows semver and is reserved for future cross-version compatibility
9. `run.sh` installs a SIGTERM trap that drains in-flight requests for up to 30s then exits, and a SIGHUP trap that
   reopens logs without restart; both behaviors verified by running the container and sending the signals
10. Every credential file under `/data/keys/` is validated for `chmod 600` ownership at startup; non-conforming files
    cause startup failure with a clear error message (no degraded mode)
11. `slog.Handler` wrapper scrubs every log record (case-insensitive key-name mask for `Authorization`, `Bearer`,
    `token`, `password`, `key`, `secret` → `<redacted>`); a unit test asserts the invariant; chi middleware strips
    `Authorization` from request-log snapshot

**Plans**: TBD

**UI hint**: no

### Phase 17: Git Integration + Apply Job System

**Goal**: The add-on clones configured Git repos at startup, exposes `POST /v1/repos/{name}/pull` for SSH-keyed
git-pull, and provides `POST /v1/plan`, `POST /v1/apply`, `GET /v1/runs/{id}`, `GET /v1/runs` for OpenTofu job
lifecycle. Concurrent applies on the same repo are serialized; cross-repo applies run in parallel. `tofu` stdout/stderr
is captured and secret-redacted.

**Depends on**: Phase 16

**Requirements**: GIT-01, GIT-02, GIT-03, GIT-04, RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06, SEC-03, OBS-02, OBS-03

**Success Criteria** (what must be TRUE):

1. Options schema accepts a list of `repos` entries; each entry has `name` (URI-safe identifier), `url` (SSH URL like
   `git@github.com:akentner/homelab-infra.git`), `branch` (default `main`), `ref` (optional commit/tag pin); schema
   validation rejects malformed entries with a typed diagnostic
2. At startup, for each configured repo, the add-on clones into `/data/repos/<name>/` if absent; existing directories
   are left untouched (caller triggers `/v1/repos/{name}/pull` to refresh); clone failures are logged but do not prevent
   startup
3. `POST /v1/repos/{name}/pull` runs `git pull --ff-only` (or the configured ref) using the SSH deploy key
   `/data/keys/<name>.key` and `known_hosts` from `/data/keys/known_hosts`; non-fast-forward pulls and auth failures
   surface as typed HTTP 409 / 403 errors with actionable messages
4. Git errors (SSH handshake, DNS failure, ref not found) surface as typed HTTP responses with `error_code: "git_*"` and
   a hint pointing at the relevant Options field; no stack traces in the response body
5. `POST /v1/plan` starts `tofu init -input=false && tofu plan -no-color -out=/data/runs/{run_id}/plan.tfplan` as a
   background job; returns HTTP 202 with `{run_id, status: "queued"}` and a `Location: /v1/runs/{run_id}` header
6. `POST /v1/apply` starts `tofu apply -no-color -auto-approve` (with or without prior plan file); returns HTTP 202 with
   `{run_id, status: "queued"}`
7. `GET /v1/runs/{id}` returns JSON with status (`queued|running|succeeded|failed`), `exit_code`, `started_at`,
   `finished_at`, and paginated `output_lines` (default 100, max 1000); `tofu` stdout/stderr captured per-run to
   `/data/runs/{run_id}/output.log` is secret-redacted before surfacing (SEC-03)
8. `GET /v1/runs` returns the last N runs (default 20, max 100) ordered by `started_at desc`; supports `?repo=<name>`
   and `?status=<status>` filters
9. Two concurrent `POST /v1/apply` calls targeting the same repo are serialized by an in-process per-repo mutex; the
   second call returns HTTP 202 with `status: "queued"` but waits in line until the first finishes; cross-repo applies
   proceed in parallel; mutex released on job exit (success, failure, or crash recovery)
10. Output redaction covers R2 access keys `^[A-Z0-9]{20}$`, AWS secret keys `^[A-Za-z0-9/+=]{40}$`, SSH private-key
    headers `-----BEGIN`; a `redaction.audit` log record counts redactions per-run
11. `runs_retention_hours` Options field (default 24) controls run-output rotation; old run files are deleted by a
    background ticker that runs every `runs_retention_hours / 4` (default 6h)

**Plans**: 7/8 plans executed in 6 waves

Plans:

- [x] 17-01-PLAN.md — Options schema + tofu/git/ssh runtime binaries
- [x] 17-02-PLAN.md — contract types + run-id/dir primitives
- [x] 17-03-PLAN.md — internal/git: clone, pull, git_* taxonomy
- [x] 17-04-PLAN.md — internal/runs: store, JSONL output, redaction, retention
- [x] 17-05-PLAN.md — internal/jobq: semaphore, per-repo mutex, tofu exec
- [x] 17-06-PLAN.md — pull + plan/apply handlers
- [x] 17-08-PLAN.md — runs handlers + router mount
- [ ] 17-07-PLAN.md — main.go wiring + DOCS/README + version bump

**UI hint**: no

### Phase 18: MQTT Discovery + HA Sensoren + Buttons

**Goal**: The add-on publishes MQTT Discovery for three sensors and two buttons (verified by IRUN-H-2 spike); button
presses are debounced (30s) and trigger internal `POST /v1/plan` / `POST /v1/apply` calls. Job-status changes publish
MQTT state updates so HA entities stay current without polling.

**Depends on**: Phase 17

**Requirements**: MQTT-01, MQTT-02, MQTT-03, MQTT-04, MQTT-05, MQTT-06, MQTT-07

**Success Criteria** (what must be TRUE):

1. `config.yaml` declares `homeassistant_api: true` and lists `mqtt:need` in `services`; on startup the add-on reads
   broker URL + credentials from the Supervisor-provided MQTT service object (via `bashio::services`); if the MQTT
   service is not available, the add-on logs a warning and continues without entities (apply endpoints still work —
   apply is decoupled from entity visibility)
2. MQTT Discovery config for `sensor.iac_runner_last_run_status` is published on startup with
   `state_topic: <prefix>/status`, `value_template: "{{ value_json.status }}"`, and
   `options: ["idle", "running", "success", "failed"]`; icon is `mdi:terraform`; sensor appears in HA UI within one
   polling cycle after add-on start
3. MQTT Discovery config for `sensor.iac_runner_last_apply_at` is published with `device_class: timestamp`,
   `state_topic: <prefix>/last_apply_at`; value is the ISO 8601 timestamp of the last completed apply (success or
   failure)
4. MQTT Discovery config for `sensor.iac_runner_last_error` is published with `state_topic: <prefix>/last_error`; value
   is the truncated (≤ 255 chars) last error message; cleared on next successful apply
5. MQTT Discovery config for `button.iac_runner_run_plan` is published with `command_topic: <prefix>/run_plan/command`,
   `payload_press: "PRESS"`; the add-on subscribes to this topic and internally calls `POST /v1/plan` on receipt
   (verified by IRUN-H-2 spike in `18-SUMMARY.md`)
6. MQTT Discovery config for `button.iac_runner_run_apply` is published with
   `command_topic: <prefix>/run_apply/command`, `payload_press: "PRESS"`; subscribed by the add-on; debounced to one
   press per 30 seconds (subsequent presses within the window are logged and ignored)
7. After every job-status change (`queued` → `running` → `succeeded`/`failed`), the add-on publishes the new status to
   `<prefix>/status`, `<prefix>/last_apply_at` (only on `succeeded`/`failed`), and `<prefix>/last_error` (only on
   `failed`); the three sensors stay current in HA without polling

**Plans**: TBD

**UI hint**: no (entities appear in HA automatically; no add-on Ingress panel)

### Phase 19: E2E Verification + DOCS + Operator Runbook

**Goal**: Every v1.4 requirement is empirically verified against a live HA host (`ha-nextgen` or `haos-op3050-1`) with a
`local_file`-provider fixture (no real homelab servers destroyed). Drift, idempotency, and all three state backends are
exercised. Operator documentation (`README.md` + `DOCS.md`) is written from observed behavior, not theory.

**Depends on**: Phase 18

**Requirements**: (validates all v1.4 requirements; introduces no new REQ-IDs)

**Success Criteria** (what must be TRUE):

1. `make install-runner`-equivalent (or direct `docker run` against the built image) installs the add-on in a real HA
   host; `/v1/version` returns 200; `/healthz` returns 200 within 2s
2. End-to-end plan + apply + drift + idempotency cycle against a `local_file`-provider fixture: apply succeeds, re-apply
   shows "No changes", in-place modification triggers a diff, manual drift introduction (state edit) triggers recreate
   plan, destroy succeeds
3. State-backend matrix: all three backends (r2, s3, local) verified end-to-end against a real R2 bucket (test bucket,
   not the production homelab state), a real S3-compatible endpoint (can use R2 again with different bucket name), and a
   local file. Lockfile semantics exercised: a manual second `tofu apply` against the same backend returns HTTP 423
   (`locked`) — proven for all three backends
4. MQTT entities empirically verified in HA UI: three sensors + two buttons appear; pressing `run_apply` triggers a
   `tofu apply` end-to-end; `last_apply_at` updates after the apply completes; debounce works (second press within 30s
   is ignored)
5. Token rotation end-to-end: `POST /v1/auth/rotate` returns new token, old token still authenticates within 24h grace,
   new token works, old token stops working after grace (or grace file is deletable for instant revocation)
6. `README.md` and `DOCS.md` are complete: install steps via HA add-on store, SSH-Deploy-Key-Setup, R2-Bucket- Konfig,
   MQTT-Service-Konfig, an example workflow covering every Option field, every error code with documented remediation,
   troubleshooting section with at least three real observed issues

**Plans**: TBD

**UI hint**: no

## Progress

| Phase                               | Milestone | Plans Complete                                                | Status              | Completed  |
| ----------------------------------- | --------- | ------------------------------------------------------------- | ------------------- | ---------- |
| 1. Quality Fixes                    | v1.0      | 2/2                                                           | Complete            | 2026-04-03 |
| 2. Auto-Update Workflow             | v1.0      | 1/1                                                           | Complete            | 2026-04-04 |
| 3. Meridian Add-on                  | v1.0      | 3/3                                                           | Complete            | 2026-04-04 |
| 4. Scaffold + Ingress Validation    | v1.1      | 3/3                                                           | Complete            | 2026-06-27 |
| 5. Multi-Namespace + Dynamic Config | v1.1      | 1/1                                                           | Complete            | 2026-06-27 |
| 6. Git Integration                  | v1.1      | 2/2                                                           | Complete            | 2026-06-28 |
| 8. CI/CD Hardening                  | v1.2      | 3/4 (1 partial + 1 gap-closure pending)                       | Gap closure pending | —          |
| 9. Bridge Foundation + Token Spike  | v1.3      | 4/4                                                           | Complete            | 2026-08-31 |
| 10. Auth + Logging + Healthcheck    | v1.3      | 3/3                                                           | Complete            | 2026-08-31 |
| 11. Bridge Read API                 | v1.3      | 2/2                                                           | Complete            | 2026-09-02 |
| 12. Bridge Write API + Safety       | v1.3      | 3/3                                                           | SHIPPED             | 2026-09-04 |
| 13. Provider + Resource + Data      | v1.3      | 3/3                                                           | Complete            | 2026-09-05 |
| 14. Real-HA E2E + Docs              | v1.3      | 3/3                                                           | Complete            | 2026-09-05 |
| 15. CI + Provider Install           | v1.3      | 0/3 (mechanically ready, blocked on v1.2 Phase 8 gap-closure) | Mechanically Ready  | —          |
| 16. iac-runner Scaffold + Auth      | v1.4      | 3/3                                                           | Complete            | 2026-09-06 |
| 17. Git + Apply Jobs                | v1.4      | 7/8 | In Progress|  |
| 18. MQTT + HA Entities              | v1.4      | 0/TBD                                                         | Planned             | —          |
| 19. E2E + DOCS                      | v1.4      | 0/TBD                                                         | Planned             | —          |

---

_Last updated: 2026-09-06 — Milestone v1.4 iac-runner roadmap written (Phases 16-19, 32 requirements mapped across
AUTHR/STBK/SEC/GIT/RUN/MQTT/OBS, 4 phases). RESEARCH skipped by explicit decision; patterns reused from
`terraform-bridge` (HTTP/auth/Go) and `markdown-renderer` (git integration). v1.3 essentially complete (6 of 7 phases
shipped: 9, 10, 11, 12, 13, 14; Phase 15 mechanically ready, blocked on v1.2 Phase 8 gap-closure Cloudflare- setup
prerequisite). Phase 8 gap-closure (`08-05-GAP-PLAN.md`) continues in parallel; resume via
`/gsd-execute-phase 8 --gaps-only` whenever the Cloudflare service token + GitHub secrets are in place. Phase 16 ready
to plan via `/gsd-plan-phase 16`._
