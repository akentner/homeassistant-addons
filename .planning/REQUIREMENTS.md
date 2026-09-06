# Requirements: v1.3 opentofu-bridge

**Milestone:** v1.3 opentofu-bridge

**Goal:** Ship a Home Assistant add-on that exposes the Supervisor HTTP API as a versioned, bearer-authenticated
JSON-over-HTTPS service, plus a co-located OpenTofu/Terraform provider, so that Apps (and eventually other HA resources)
can be managed via declarative `*.tf` configuration.

**Scope:** Phase 1 = `homeassistant_addon` resource (install/start/stop/uninstall + options CRUD), `homeassistant_addon`
data source, `homeassistant_supervisor_info` data source, schema-version handshake, bearer-token auth, idempotent reads,
import, timeouts. Phase 2+ deferred (see "Out of Scope").

---

## Requirements

### TOFU — Milestone-Wide Conventions

- [x] **TOFU-01**: `terraform-bridge/` add-on follows the established 4-file pattern (`config.yaml`, `build.yaml`,
      `Dockerfile`, `run.sh`) consistent with every other add-on in the repo; no `.upstream.yaml` because there is no
      external upstream project
- [x] **TOFU-02**: `terraform-provider-homeassistant/` is a Go module built from **local source** in the repo
      (documented exception to the "Dockerfiles must download upstream at build time" rule); same Go toolchain (≥ 1.25)
      for both Bridge and Provider
- [x] **TOFU-03**: Bridge and Provider share one release cycle via the existing 3-file scheme: Bridge `config.yaml` uses
      `X.Y.Z-N` (subpatch), Provider `build.yaml` uses `X.Y.Z`;
      `make update-version ADDON=terraform-bridge VERSION=X.Y.Z` bumps both atomically and creates the
      `<addon>/v<version>` git tag
- [ ] **TOFU-04**: A Makefile target (`make install-provider`) installs the built Provider binary into
      `~/.terraform.d/plugins/<host>/akentner/homeassistant/<version>/` so OpenTofu discovers it via the dev_overrides
      workflow
- [x] **TOFU-05**: `internal/validate-versions.sh` is extended to enforce that Bridge `build.yaml` and Provider
      `build.yaml` carry the same `X.Y.Z` portion; mismatched versions fail pre-commit

### AUTH — Auth & Security

- [x] **AUTH-01**: Bridge → Supervisor uses `SUPERVISOR_TOKEN` auto-injected by Supervisor when `hassio_api: true` is
      set in `config.yaml`; the token is **never** logged, **never** sent to the Provider, and **never** accepted from a
      non-loopback source
- [x] **AUTH-02**: Bridge generates a 256-bit bearer token on first start using `crypto/rand`; stores its SHA-256 hash
      in `/data/bridge-token` with `chmod 600`; surfaces the plaintext token exactly once via add-on log + Options UI on
      first start and on subsequent rotation
- [x] **AUTH-03**: Provider → Bridge requests must include `Authorization: Bearer <token>`; Bridge validates with
      `crypto/subtle.ConstantTimeCompare` against the on-disk hash
- [x] **AUTH-04**: Bridge exposes `POST /v1/auth/rotate` returning a new token plus a 24-hour grace window where the old
      token still authenticates successfully; grace state is persisted in `/data/bridge-token.grace`
- [x] **AUTH-05**: Bearer token never appears in Bridge logs (Authorization header masked by request-logging
      middleware); a `bridge_token` field in any log record is forbidden and enforced by a unit test
- [x] **AUTH-06**: Bridge declares `hassio_role: manager` in `config.yaml` so it can read other add-ons' `options`
      (which Supervisor redacts for non-manager apps per `supervisor/api/middleware/security.py`)
- [x] **AUTH-07**: Bridge listener binds to `0.0.0.0:<port>` (default `8124/tcp`); for Phase 1 the network layer
      (Tailscale ACL or LAN) enforces access control, not the Bridge itself; TLS termination is documented as
      out-of-scope for Phase 1

### BRIDGE — Bridge HTTP API

- [ ] **BRIDGE-01**: Bridge exposes `GET /v1/version` returning JSON
      `{bridge_version, schema_version,     min_provider_version, max_provider_version}`; the schema_version follows
      semver and is incremented on every breaking Bridge API change
- [ ] **BRIDGE-02**: Bridge exposes `GET /v1/addons` (list all installed add-ons), wrapping Supervisor `/apps` (V2
      preferred) with fallback to `/addons` (V1) when `SUPERVISOR_V2_API` feature flag is off
- [ ] **BRIDGE-03**: Bridge exposes `GET /v1/addons/{slug}/info`, wrapping Supervisor `/apps/{slug}/info`; response
      includes `version`, `state`, `started`, `options`, `boot`, `slug`, `repository`
- [ ] **BRIDGE-04**: Bridge exposes `POST /v1/addons/{slug}/install`, wrapping Supervisor `/store/apps/{slug}/install`;
      when Supervisor returns a `job_id`, Bridge polls `/jobs/{id}` until completion and returns the final
      `apps/{slug}/info` payload to the caller
- [ ] **BRIDGE-05**: Bridge exposes `POST /v1/addons/{slug}/uninstall`, wrapping Supervisor `/apps/{slug}/uninstall`;
      returns `204 No Content` on success
- [ ] **BRIDGE-06**: Bridge exposes `POST /v1/addons/{slug}/start`, wrapping Supervisor `/apps/{slug}/start` (which is
      `asyncio.shield`-awaited and synchronous from the caller's perspective)
- [ ] **BRIDGE-07**: Bridge exposes `POST /v1/addons/{slug}/stop`, wrapping Supervisor `/apps/{slug}/stop`
- [ ] **BRIDGE-08**: Bridge exposes `POST /v1/addons/{slug}/options`, wrapping Supervisor `/apps/{slug}/options`; calls
      `/apps/{slug}/options/validate` first and surfaces Supervisor's `valid` + `pwned` fields to the caller as typed
      diagnostics
- [ ] **BRIDGE-09**: Bridge forwards typed Supervisor errors as HTTP responses: 404 (`not_found`), 403
      (`prevented_destroy` or `critical_addon`), 409 (`already_installed` — adopted as success by Provider), 423
      (`locked`), 5xx transient (Provider retries per `terraform-plugin-framework-timeouts`)
- [ ] **BRIDGE-10**: Bridge exposes `GET /v1/info` (non-authenticated, useful for `terraform_data` or precondition
      checks) returning `{bridge_version, supervisor_version, uptime_seconds, state_file_path}`

### PROV — Provider

- [x] **PROV-01**: Provider is `terraform-provider-homeassistant`, uses `terraform-plugin-framework` v1.19.0 (protocol
      v6), supports OpenTofu ≥ 1.12 and Terraform ≥ 1.5; serves via `providerserver.Serve()`
- [x] **PROV-02**: Resource `homeassistant_addon` schema: `slug` (Required, String), `repository` (Optional, String,
      default `"core"`), `url` (Optional, String — explicit repository URL), `options` (Optional, `TypeMap<String>` —
      see Open Question 2), `start` (Optional, Bool, default `true` — see Open Question 5), `boot` (Optional,
      `["auto", "manual", "manual_only"]`); Computed: `version`, `state`, `started`, `hostname`
- [x] **PROV-03**: Provider `Configure` calls Bridge `GET /v1/version` at startup and refuses to operate if
      `schema_version < min_provider_version` or `schema_version > max_provider_version` (typed diagnostic)
- [x] **PROV-04**: Resource Read is idempotent — called after every operation; calls Bridge
      `GET /v1/addons/{slug}/info`; returns empty state when 404 (so Delete on missing add-on is a no-op)
- [x] **PROV-05**: Resource Create: calls Bridge `POST /v1/addons/{slug}/install`; on `409 already_installed` treats it
      as success (adoption); follows up with `/start` when `start = true`; handles async `job_id` polling via Bridge
- [x] **PROV-06**: Resource Update: computes the `options` diff and calls Bridge `POST /v1/addons/{slug}/options`;
      surfaces `pwned` warnings as Provider warning diagnostics (not errors) — see Open Question 4
- [x] **PROV-07**: Resource Delete: calls Bridge `POST /v1/addons/{slug}/uninstall`; returns success on `204` and treats
      `404` as already-gone (idempotent)
- [x] **PROV-08**: Resource implements `ResourceWithImportState` with `ImportStatePassthroughID`; accepted ID formats:
      `{slug}` (assumes `repository = "core"`) and `{repository}/{slug}` (any repo)
- [x] **PROV-09**: Resource supports per-operation timeouts via `terraform-plugin-framework-timeouts`; defaults in
      DOCS.md: `create = 10m`, `update = 2m`, `delete = 5m`
- [x] **PROV-10**: Resource applies `UseStateForUnknown()` plan modifier to the `state` attribute so plan output does
      not show spurious diffs on every refresh (see Open Question 8)
- [x] **PROV-11**: Data source `homeassistant_addon` (read-only by slug, returns full info) for use in `terraform_data`
      and other resources' attribute references without managing the add-on
- [ ] **PROV-12**: Data source `homeassistant_supervisor_info` (read-only) for use in `lifecycle.precondition` blocks

### STATE — State Management

- [ ] **STATE-01**: Provider documentation instructs users to configure the OpenTofu local backend with
      `path = "/data/terraform.tfstate"` (when running on the HA host) or to mirror the state file via the add-on's
      share volume when running off-host
- [ ] **STATE-02**: Bridge exposes `GET /v1/state/index` listing currently-known state files and their SHA-256 digests
      (HA backup integration aid; see Open Question 6 and PITFALLS §10)
- [ ] **STATE-03**: Bridge serializes write operations (install / uninstall / options / start / stop) per-slug via an
      in-process mutex, preventing two concurrent Providers from corrupting Supervisor's job state

### LIFE — Lifecycle & Safety

- [ ] **LIFE-01**: Bridge `config.yaml` schema exposes `critical_addons: list` (default
      `["core_mosquitto",     "core_zigbee2mqtt", "core_esphome"]`); Bridge refuses uninstall / restart / options-change
      on any add-on in this list with `403 critical_addon_protected`
- [ ] **LIFE-02**: Provider resource `homeassistant_addon` exposes a `prevent_destroy = true` default in DOCS.md
      examples; Provider does NOT force this — users opt in via lifecycle meta-arguments
- [ ] **LIFE-03**: Destructive Bridge operations (uninstall, options change) require the request header
      `X-Force-Destroy: <bridge_issued_nonce>` (Bridge issues a fresh nonce via `POST /v1/auth/nonce` and accepts it
      once within 60 seconds); protects against CSRF / scripted attacks even within Tailscale
- [ ] **LIFE-04**: Provider surfaces typed diagnostics on Bridge errors: `403` → error with explicit "this add-on is in
      `critical_addons` or `lifecycle.prevent_destroy = true`"; `423` → "another operation is in flight, retry in 30s";
      `5xx` → "transient Supervisor failure, retry per timeouts"

### OPS — Operations

- [x] **OPS-01**: Bridge emits structured JSON log records to stdout (one record per line) with `ts`, `level`, `msg`,
      `request_id`, `route`, `method`, `status`, `duration_ms`; logs include the Supervisor call name
      (`supervisor.method = "apps.install"`) but never the Authorization header or token
- [x] **OPS-02**: Bridge handles `SIGTERM` gracefully — drains in-flight requests up to 30 seconds, then exits; handles
      `SIGHUP` to rotate logs without restart
- [x] **OPS-03**: Bridge exposes `GET /healthz` (non-authenticated) returning `200 OK` if it can reach Supervisor (used
      by HA Supervisor's health-check and by external monitors)
- [ ] **OPS-04**: Bridge README.md and DOCS.md document: install (HA add-on store), token issuance + rotation
      (`cat /data/bridge-token`), OpenTofu provider install (`make install-provider`), example `*.tf` file, every
      resource attribute with example values, every error code with remediation, troubleshooting section
- [x] **OPS-05**: Bridge Dockerfile is multi-stage: `golang:1.25-alpine` builds a static binary, which is copied into
      `ghcr.io/home-assistant/amd64-base:3.24`; image size target ≤ 60 MiB uncompressed, ≤ 30 MiB compressed _(revised
      2026-08-31 from ≤ 30 MiB — HA base 3.24 alone is 49 MiB uncompressed; compressed size is ~22 MiB which is under
      the original target; documented deviation in 09-01-SUMMARY + 09-04-SUMMARY)_

---

## Traceability (filled by `gsd-roadmapper`)

**Coverage:** 46/46 v1.3 requirements mapped ✓ — no orphans, no duplicates.

| Phase                                                         | Requirements                                                                                                                           | Count |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----- |
| **Phase 9: Bridge Foundation + Token Rotation Spike**         | TOFU-01, TOFU-02, TOFU-03, TOFU-05, AUTH-01, AUTH-06, OPS-02, OPS-05                                                                   | 8     |
| **Phase 10: Auth + Logging + Healthcheck**                    | AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-07, OPS-01, OPS-03                                                                            | 7     |
| **Phase 11: Bridge Read API**                                 | BRIDGE-01, BRIDGE-02, BRIDGE-03, BRIDGE-10                                                                                             | 4     |
| **Phase 12: Bridge Write API + Safety + Concurrency + Index** | BRIDGE-04, BRIDGE-05, BRIDGE-06, BRIDGE-07, BRIDGE-08, BRIDGE-09, STATE-02, STATE-03, LIFE-01, LIFE-03                                 | 10    |
| **Phase 13: Provider + Resource + Data + Handshake**          | PROV-01, PROV-02, PROV-03, PROV-04, PROV-05, PROV-06, PROV-07, PROV-08, PROV-09, PROV-10, PROV-11, PROV-12, LIFE-02, LIFE-04, STATE-01 | 15    |
| **Phase 14: Real-HA E2E + Operator Docs**                     | OPS-04                                                                                                                                 | 1     |
| **Phase 15: CI + Provider Install**                           | TOFU-04                                                                                                                                | 1     |

### Per-requirement mapping

| REQ-ID    | Phase                                                     |
| --------- | --------------------------------------------------------- |
| AUTH-01   | Phase 9: Bridge Foundation + Token Rotation Spike         |
| AUTH-02   | Phase 10: Auth + Logging + Healthcheck                    |
| AUTH-03   | Phase 10: Auth + Logging + Healthcheck                    |
| AUTH-04   | Phase 10: Auth + Logging + Healthcheck                    |
| AUTH-05   | Phase 10: Auth + Logging + Healthcheck                    |
| AUTH-06   | Phase 9: Bridge Foundation + Token Rotation Spike         |
| AUTH-07   | Phase 10: Auth + Logging + Healthcheck                    |
| BRIDGE-01 | Phase 11: Bridge Read API                                 |
| BRIDGE-02 | Phase 11: Bridge Read API                                 |
| BRIDGE-03 | Phase 11: Bridge Read API                                 |
| BRIDGE-04 | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| BRIDGE-05 | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| BRIDGE-06 | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| BRIDGE-07 | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| BRIDGE-08 | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| BRIDGE-09 | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| BRIDGE-10 | Phase 11: Bridge Read API                                 |
| LIFE-01   | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| LIFE-02   | Phase 13: Provider + Resource + Data + Handshake          |
| LIFE-03   | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| LIFE-04   | Phase 13: Provider + Resource + Data + Handshake          |
| OPS-01    | Phase 10: Auth + Logging + Healthcheck                    |
| OPS-02    | Phase 9: Bridge Foundation + Token Rotation Spike         |
| OPS-03    | Phase 10: Auth + Logging + Healthcheck                    |
| OPS-04    | Phase 14: Real-HA E2E + Operator Docs                     |
| OPS-05    | Phase 9: Bridge Foundation + Token Rotation Spike         |
| PROV-01   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-02   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-03   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-04   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-05   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-06   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-07   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-08   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-09   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-10   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-11   | Phase 13: Provider + Resource + Data + Handshake          |
| PROV-12   | Phase 13: Provider + Resource + Data + Handshake          |
| STATE-01  | Phase 13: Provider + Resource + Data + Handshake          |
| STATE-02  | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| STATE-03  | Phase 12: Bridge Write API + Safety + Concurrency + Index |
| TOFU-01   | Phase 9: Bridge Foundation + Token Rotation Spike         |
| TOFU-02   | Phase 9: Bridge Foundation + Token Rotation Spike         |
| TOFU-03   | Phase 9: Bridge Foundation + Token Rotation Spike         |
| TOFU-04   | Phase 15: CI + Provider Install                           |
| TOFU-05   | Phase 9: Bridge Foundation + Token Rotation Spike         |

### Coverage gaps and resolutions

**None.** All 46 v1.3 requirements are mapped to exactly one phase. Two structural decisions taken during mapping:

- **STATE-03 (per-slug write mutex)** assigned to Phase 12, not Phase 11/13 — mutex is defense-in-depth for cross-host
  concurrent applies and must exist BEFORE Provider surfaces destructive operations; pairing it with the write endpoints
  it serializes keeps the safety gate atomic.
- **OPS-04 (operator docs)** assigned to Phase 14, not Phase 15 — documentation requires empirically observed behavior
  (every error code with remediation, troubleshooting section), so docs can only be written after the real-HA E2E run.
  Phase 15 retains the CI/install-provider workflow where the make target lives.

---

## v1.4 iac-runner Requirements

**Milestone:** v1.4 iac-runner

**Goal:** Ship a Home Assistant Supervisor add-on (`iac-runner/`) that clones a Git repo (e.g. `homelab-infra`), runs
OpenTofu/Terraform `plan`/`apply` against homelab servers (Tailscale-reachable), persists state in R2 (default),
S3-compatible, or local backend, and surfaces run status + manual triggers as Home Assistant entities via MQTT
Discovery.

**Scope:** Phase 16 = scaffold + auth + state backends + healthz. Phase 17 = git integration + apply job system. Phase
18 = MQTT Discovery + HA entities. Phase 19 = E2E verification + operator docs.

---

### AUTHR — iac-runner Bearer-Auth (no SUPERVISOR_TOKEN)

- [x] **AUTHR-01**: Add-on does NOT declare `hassio_api: true` in `config.yaml`; the add-on does not need Supervisor
      access (`iac-runner` calls `tofu`/`git`/`aws` itself; no Supervisor calls). Only `homeassistant_api: true` is set,
      solely for the MQTT service connection
- [x] **AUTHR-02**: Bearer-token auth follows the proven `terraform-bridge` pattern: 256-bit token via `crypto/rand`;
      SHA-256 hash stored at `/data/iac-runner-token` with `chmod 600`; validation via
      `crypto/subtle.ConstantTimeCompare`; plaintext surfaced exactly once via add-on log line + Options UI on first
      start (and on subsequent rotation); restart does NOT re-emit the plaintext
- [x] **AUTHR-03**: Add-on listener binds to `0.0.0.0:8125` (separate from `terraform-bridge`'s 8124); startup
      auto-detects the first `tailscale*` interface in `/sys/class/net` and binds to its IPv4 address; an explicit IP is
      accepted only if it belongs to a Tailscale interface OR falls inside one of `bind_allowed_subnets`;
      `bind_address: "0.0.0.0"` is always refused regardless of `bind_allowed_subnets` (per `terraform-bridge` AUTH-07
      pattern)
- [x] **AUTHR-04**: Add-on exposes `POST /v1/auth/rotate` with the same 24-hour grace semantics as `terraform-bridge`;
      for 24 hours both the old and the new token authenticate successfully; grace state persisted in
      `/data/iac-runner-token.grace` and survives restart

### STBK — State Backend (R2 / S3 / local)

- [x] **STBK-01**: Add-on options schema exposes `state_backend: list(match(^(r2|s3|local)$))` defaulting to `r2`;
      selected backend drives which credentials are required at startup
- [x] **STBK-02**: When `state_backend = r2`: add-on reads R2 access key from `/data/keys/r2-access.key`, secret key
      from `/data/keys/r2-secret.key`, account ID from `/data/keys/r2-account-id` (plaintext, non-sensitive), bucket
      from Options (`r2_bucket`); endpoint constructed as `https://<account_id>.r2.cloudflarestorage.com`
- [x] **STBK-03**: When `state_backend = s3`: add-on reads credentials from `/data/keys/s3-access.key` +
      `/data/keys/s3-secret.key`, endpoint from Options (`s3_endpoint`), bucket + region from Options
- [x] **STBK-04**: When `state_backend = local`: add-on writes/reads state from `/data/terraform.tfstate`; no external
      credentials required; HA backup covers the state file automatically
- [x] **STBK-05**: For R2 and S3 backends, OpenTofu is invoked with `use_lockfile = true` so locking uses the native S3
      object-lock semantics (no DynamoDB required). For local backend, locking is file-based via
      `/data/terraform.tfstate.lock`. Apply fails fast with HTTP 423 (`locked`) when another apply holds the lock

### SEC — Secrets / Credentials Handling

- [x] **SEC-01**: All credential files under `/data/keys/` are validated at startup for `chmod 600` ownership (current
      process UID); non-conforming files cause startup failure with a clear error message (no degraded mode); missing
      files cause startup failure per `STBK-01..04` requirements
- [x] **SEC-02**: Add-on emits structured JSON logs with a scrubbing `slog.Handler` wrapper (case-insensitive key-name
      mask for `Authorization`, `Bearer`, `token`, `password`, `key`, `secret` → `<redacted>`) — same pattern as
      `terraform-bridge` AUTH-05; a unit test asserts no credential field ever survives the handler
- [ ] **SEC-03**: `tofu` stdout/stderr captured per-run to `/data/runs/{run_id}/output.log` is redacted for
      credential-like patterns before being surfaced via `GET /v1/runs/{id}` (e.g. R2 access keys `^[A-Z0-9]{20}$`, AWS
      secret keys `^[A-Za-z0-9/+=]{40}$`, SSH private-key headers `-----BEGIN`); a `redaction.audit` log record counts
      redactions per-run

### GIT — Git Integration

- [ ] **GIT-01**: Add-on options schema accepts a list of `repos` entries; each entry has `name` (URI-safe identifier),
      `url` (SSH URL like `git@github.com:akentner/homelab-infra.git`), `branch` (default `main`), `ref` (optional
      commit/tag pin)
- [ ] **GIT-02**: At startup, for each configured repo, the add-on clones into `/data/repos/<name>/` if absent; existing
      directories are left untouched (caller is responsible for triggering `POST /v1/repos/{name}/pull`)
- [ ] **GIT-03**: `POST /v1/repos/{name}/pull` runs `git pull --ff-only` (or the configured ref) using the SSH deploy
      key `/data/keys/<name>.key` and `known_hosts` from `/data/keys/known_hosts`; non-fast-forward pulls and auth
      failures surface as typed HTTP 409 / 403 errors with actionable messages
- [ ] **GIT-04**: Git errors (SSH handshake, DNS failure, ref not found) are surfaced as typed HTTP responses with
      `error_code: "git_*"` and a hint pointing at the relevant Options field; no stack traces in the response body

### RUN — Runner HTTP API

- [ ] **RUN-01**: Add-on exposes `GET /v1/version` returning JSON
      `{runner_version, schema_version, min_supported_opentofu, max_supported_opentofu}` — no provider handshake (no
      external Provider binary consumes this API in v1.4; schema_version reserved for future use)
- [ ] **RUN-02**: Add-on exposes `POST /v1/plan` accepting JSON `{repo: "<name>", dir: "<subpath>"}`; starts
      `tofu init -input=false && tofu plan -no-color -out=/data/runs/{run_id}/plan.tfplan` as a background job; returns
      HTTP 202 with `{run_id, status: "queued"}` and a `Location: /v1/runs/{run_id}` header
- [ ] **RUN-03**: Add-on exposes `POST /v1/apply` accepting the same body as `/v1/plan`; starts
      `tofu apply -no-color -auto-approve /data/runs/{run_id}/plan.tfplan` (or `tofu apply -no-color -auto-approve`
      inline when no plan was provided); returns HTTP 202 with `{run_id, status: "queued"}`
- [ ] **RUN-04**: Add-on exposes `GET /v1/runs/{id}` returning JSON
      `{run_id, repo, kind: "plan|apply", status:     "queued|running|succeeded|failed", exit_code, started_at, finished_at, output_lines: [...], page, page_size}`;
      `output_lines` are paginated (default 100 lines, max 1000); secret-redacted per SEC-03
- [ ] **RUN-05**: Add-on exposes `GET /v1/runs` returning the last N runs (default 20, max 100) ordered by
      `started_at desc`; supports `?repo=<name>` and `?status=<status>` filters
- [ ] **RUN-06**: Two concurrent `POST /v1/apply` calls targeting the same repo are serialized by an in-process per-repo
      mutex; the second call returns HTTP 202 with `status: "queued"` but waits in line until the first finishes;
      cross-repo applies proceed in parallel; mutex is released on job exit (success, failure, or crash recovery)

### MQTT — HA MQTT Discovery (Sensors + Buttons)

- [ ] **MQTT-01**: Add-on `config.yaml` declares `homeassistant_api: true` and lists `mqtt:need` in the `services`
      array; on startup the add-on reads the broker URL + credentials from the Supervisor-provided MQTT service object
      (via `bashio::services`); if the MQTT service is not available, the add-on logs a warning and continues without
      entities (apply endpoints still work)
- [ ] **MQTT-02**: On startup, the add-on publishes MQTT Discovery config for `sensor.iac_runner_last_run_status` with
      `state_topic: <prefix>/status`, `value_template: "{{ value_json.status }}"`, and
      `options: ["idle", "running", "success", "failed"]`; the sensor's icon is `mdi:terraform`
- [ ] **MQTT-03**: On startup, the add-on publishes MQTT Discovery config for `sensor.iac_runner_last_apply_at` with
      `device_class: timestamp`, `state_topic: <prefix>/last_apply_at`; value is the ISO 8601 timestamp of the last
      completed apply (success or failure)
- [ ] **MQTT-04**: On startup, the add-on publishes MQTT Discovery config for `sensor.iac_runner_last_error` with
      `state_topic: <prefix>/last_error`; value is the truncated (≤ 255 chars) last error message; cleared on next
      successful apply
- [ ] **MQTT-05**: On startup, the add-on publishes MQTT Discovery config for `button.iac_runner_run_plan` with
      `command_topic: <prefix>/run_plan/command`, `payload_press: "PRESS"`; the add-on subscribes to this topic and
      internally calls `POST /v1/plan` on receipt (verified by IRUN-H-2 spike in Phase 18)
- [ ] **MQTT-06**: On startup, the add-on publishes MQTT Discovery config for `button.iac_runner_run_apply` with
      `command_topic: <prefix>/run_apply/command`, `payload_press: "PRESS"`; subscribed by the add-on; debounced to one
      press per 30 seconds (subsequent presses within the window are logged and ignored)
- [ ] **MQTT-07**: After every job-status change (`queued` → `running` → `succeeded`/`failed`), the add-on publishes the
      new status to `<prefix>/status`, `<prefix>/last_apply_at` (only on `succeeded`/`failed`), and
      `<prefix>/last_error` (only on `failed`); the three sensors stay current in HA without polling

### OBS — Observability (Logs, Output, Run History)

- [x] **OBS-01**: Add-on emits one structured JSON log record per HTTP request with fields `ts`, `level`, `msg`,
      `request_id`, `route`, `method`, `status`, `duration_ms` — same pattern as `terraform-bridge` OPS-01;
      `Authorization` header is stripped before request-log snapshot (chi middleware)
- [ ] **OBS-02**: `tofu` stdout/stderr for each run is captured line-by-line to `/data/runs/{run_id}/output.log` (one
      line per capture, prefixed with `ts`); the file is rotated/deleted 24 hours after the run completes (configurable
      via `runs_retention_hours`, default 24)
- [ ] **OBS-03**: `GET /v1/runs/{id}` returns paginated `output_lines`; `page` and `page_size` query parameters allow
      incremental fetching for long apply outputs; the file-on-disk is the source of truth, not an in-memory buffer

---

### v1.4 iac-runner Traceability

**Coverage:** 32/32 v1.4 requirements mapped ✓ — no orphans, no duplicates.

| Phase                                                        | Requirements                                                                                                                               | Count |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ----- |
| **Phase 16: Scaffold + Auth + State Backends + Healthcheck** | AUTHR-01, AUTHR-02, AUTHR-03, AUTHR-04, STBK-01, STBK-02, STBK-03, STBK-04, STBK-05, SEC-01, SEC-02, OBS-01                                | 12    |
| **Phase 17: Git Integration + Apply Job System**             | GIT-01, GIT-02, GIT-03, GIT-04, RUN-01, RUN-02, RUN-03, RUN-04, RUN-05, RUN-06, SEC-03, OBS-02, OBS-03                                     | 13    |
| **Phase 18: MQTT Discovery + HA Sensoren + Buttons**         | MQTT-01, MQTT-02, MQTT-03, MQTT-04, MQTT-05, MQTT-06, MQTT-07                                                                              | 7     |
| **Phase 19: E2E Verification + DOCS + Operator Runbook**     | (validates all v1.4 requirements against a live HA host with a `local_file`-provider fixture; writes operator docs from observed behavior) | 0     |

### Per-requirement mapping

| REQ-ID   | Phase                                                    |
| -------- | -------------------------------------------------------- |
| AUTHR-01 | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| AUTHR-02 | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| AUTHR-03 | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| AUTHR-04 | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| GIT-01   | Phase 17: Git Integration + Apply Job System             |
| GIT-02   | Phase 17: Git Integration + Apply Job System             |
| GIT-03   | Phase 17: Git Integration + Apply Job System             |
| GIT-04   | Phase 17: Git Integration + Apply Job System             |
| MQTT-01  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| MQTT-02  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| MQTT-03  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| MQTT-04  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| MQTT-05  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| MQTT-06  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| MQTT-07  | Phase 18: MQTT Discovery + HA Sensoren + Buttons         |
| OBS-01   | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| OBS-02   | Phase 17: Git Integration + Apply Job System             |
| OBS-03   | Phase 17: Git Integration + Apply Job System             |
| RUN-01   | Phase 17: Git Integration + Apply Job System             |
| RUN-02   | Phase 17: Git Integration + Apply Job System             |
| RUN-03   | Phase 17: Git Integration + Apply Job System             |
| RUN-04   | Phase 17: Git Integration + Apply Job System             |
| RUN-05   | Phase 17: Git Integration + Apply Job System             |
| RUN-06   | Phase 17: Git Integration + Apply Job System             |
| SEC-01   | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| SEC-02   | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| SEC-03   | Phase 17: Git Integration + Apply Job System             |
| STBK-01  | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| STBK-02  | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| STBK-03  | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| STBK-04  | Phase 16: Scaffold + Auth + State Backends + Healthcheck |
| STBK-05  | Phase 16: Scaffold + Auth + State Backends + Healthcheck |

### Coverage gaps and resolutions

**None.** All 32 v1.4 requirements are mapped to exactly one phase. Two structural decisions taken during mapping:

- **SEC-03 (output redaction) assigned to Phase 17**, not Phase 16 — there is no per-run output to redact until
  `/v1/plan`/`/v1/apply` exist (Phase 17). The Phase 16 log-scrubbing (SEC-02) covers the static credential paths; Phase
  17 extends the scrubbing to dynamically captured `tofu` output.
- **Phase 19 has zero new requirements** — it validates every prior requirement against a live HA host and writes
  operator documentation from observed behavior (same pattern as v1.3 Phase 14).

---

## Out of Scope (deferred to later milestones)

- `homeassistant_addon_repository` resource — **defer to v1.4** per FEATURES.md and Open Question 1
- `homeassistant_addon_update` action (version pin/roll-forward/rollback) — **defer to v1.4**
- Provider Actions (start/stop/restart/rebuild/stdin) — **defer to v1.4**
- `homeassistant_backup` resource — **defer to v1.4**
- `homeassistant_addon_stats` data source (live CPU/memory) — **defer to v1.5**
- HTTP state backend on Bridge (`LOCK`/`UNLOCK` verbs) — **defer to v1.5**
- Tailscale HTTPS termination / Cloudflare Access for Bridge — **defer to v1.5**
- `homeassistant_core` / `homeassistant_supervisor` / `homeassistant_host` resources — **defer to v1.6+** (disruptive;
  require explicit user-acknowledgement gate; never in Phase 1)
- HA Core-entity resources (`homeassistant_automation`, `homeassistant_script`, `homeassistant_scene`,
  `homeassistant_area`, `homeassistant_zone`, `homeassistant_device`, `homeassistant_dashboard`) — **defer to v2.x**;
  different API surface (HA Core REST, not Supervisor) — separate provider or sub-app

## Out of Scope (anti-features; do NOT build in any phase)

- Writing to `/config`, `/share`, `/media`, `/data` from Bridge — pass-through only; filesystem writes are the add-on's
  job
- Restarting HA Core from Provider — breaks every running add-on
- Modifying host OS from Provider — larger blast radius than Core restart
- Running the Provider binary inside HA Supervisor — couples lifecycles
- Auto-rotating bearer without grace period — in-flight requests get 401
- Embedding `tofu` binary in the Bridge — duplicates user-side binary
- Provider-managed Supervisor self-update — circular dependency

- [ ] **ADD-01**: Add-on follows established 4-file pattern (config.yaml, build.yaml, Dockerfile, run.sh) plus
      .upstream.yaml, consistent with existing add-ons in the repo
- [ ] **ADD-02**: Docsify 4.13.1 and Mermaid 11.15.0 UMD build are vendored into the Docker image at build time via
      `curl`; no CDN requests at runtime
- [ ] **ADD-03**: `.upstream.yaml` pins version_pattern to `v4.*` to prevent auto-update to Docsify v5 RC
- [ ] **ADD-04**: README.md includes version shield badges; DOCS.md documents all config options with examples

### INGRESS — HA Ingress + Single Namespace

- [ ] **INGRESS-01**: Add-on exposes a Docsify SPA via HA Ingress with a panel entry in the HA sidebar (`ingress: true`,
      `panel_icon: mdi:text-box-multiple`)
- [ ] **INGRESS-02**: Docsify `basePath` is set to `window.location.pathname` in generated `index.html` (never a static
      absolute path) so HA Ingress routing works correctly for all `.md` file fetches
- [ ] **INGRESS-03**: All static assets (Docsify JS, Mermaid JS, CSS) are referenced with relative paths in generated
      HTML (e.g., `../_docsify/docsify.min.js`); no absolute `/`-prefixed paths
- [ ] **INGRESS-04**: Per-namespace trailing-slash redirect (`location = /ns { return 301 /ns/; }`) and
      `absolute_redirect off` in nginx server block prevent broken `window.location.pathname` values
- [ ] **INGRESS-05**: Mermaid UMD diagrams in fenced code blocks (` ```mermaid `) render correctly inside Docsify via
      inline `doneEach` lifecycle hook calling `mermaid.run()`

### MULTI — Multi-Namespace Routing

- [x] **MULTI-01**: User configures multiple directories as a list of objects in HA options; each object has `name`
      (URI-safe string) and `path` (absolute path inside the container)
- [x] **MULTI-02**: Each configured directory is served as an independent Docsify SPA under `/name/` via nginx;
      namespaces are isolated (separate index.html, separate markdown root)
- [x] **MULTI-03**: Landing page at the Ingress root (`/`) lists all configured namespaces as clickable cards with name
      and path; generated at startup from config
- [x] **MULTI-04**: `generate_nginx.py` reads `/data/options.json` at startup and generates `/tmp/nginx.conf` +
      per-namespace `/tmp/docroots/{name}/index.html`; run.sh invokes it before starting nginx
- [x] **MULTI-05**: Namespace name validation rejects names that are empty, non-URI-safe, or conflict with reserved
      nginx locations (`_docsify`, `api`)
- [x] **MULTI-06**: Paths from `/share`, `/config`, and `/media` are supported as namespace directory sources;
      config.yaml `map:` includes `share:rw`, `config:rw`, `media:rw`

### KROKI — Kroki Diagram Service

- [ ] **KROKI-01**: Add-on supports any diagram format that Kroki supports (PlantUML, Mermaid, GraphViz, etc.) via
      fenced code blocks (` ```plantuml `, ` ```dot `, ` ```blockdiag `, etc.) in addition to inline Mermaid
- [ ] **KROKI-02**: HA options schema exposes a `kroki_url` string option with default `"https://kroki.io"` (the public
      Kroki web service); users can override to point at a self-hosted Kroki instance or compatible service
- [ ] **KROKI-03**: A fenced code block whose language identifier is not `mermaid` is rendered as an `<img>` tag whose
      `src` points at `{kroki_url}/{format}/{output_format}/<base64-encoded diagram source>` (Kroki's URL scheme);
      default output_format is `svg`
- [ ] **KROKI-04**: Diagram rendering happens at page-load time via Docsify `doneEach` lifecycle hook; the rendered
      `<img>` tags replace the raw `<pre><code>` blocks in the DOM after Docsify has rendered the markdown
- [ ] **KROKI-05**: If the Kroki service is unreachable for a specific diagram, the original code block remains visible
      (graceful degradation); errors are logged to the browser console but do not break the Docsify SPA

### GIT — Git Integration

- [x] **GIT-01**: Each namespace entry supports an optional `git_pull: bool` flag; when true, run.sh executes
      `git pull --ff-only` on the directory at startup before nginx starts
- [x] **GIT-02**: `git config --global --add safe.directory '*'` is executed in run.sh before any git operation to
      handle mounted volume UID mismatch (git 2.35.2+ requirement)
- [x] **GIT-03**: Namespaces without `git_pull: true` are served without any git operations; git integration is fully
      optional per namespace
- [x] **GIT-04**: Each namespace supports a `git_pull_interval: int` option (seconds, 0 = disabled) for periodic
      background git pull; run.sh spawns a background loop when interval > 0
- [x] **GIT-05**: Startup is not blocked if a git directory is unreachable; git pull errors are logged but do not
      prevent the namespace from being served

### CI — CI/CD Hardening (v1.2, Phase 8)

<!-- Added 2026-08-30 from the GitHub Actions audit. All runs were green; these are the defects that a green run-status
     column cannot show — one fails silently, one has no failure mode until it triggers, one is only a warning. -->

- [x] **CI-01**: Every job in every workflow declares an explicit `timeout-minutes`; no job relies on GitHub's
      360-minute default. The number of declarations equals the number of jobs (currently 6)
- [x] **CI-02**: The add-on build job is bounded such that a hung aarch64 QEMU leg cannot consume a 6-hour runner block;
      the cap is derived from the measured 13m28s emulated build, not guessed
- [x] **CI-03**: No action in any workflow targets the deprecated Node 20 runtime; the "Node.js 20 is deprecated"
      annotation no longer appears on build runs — closed by `grep -c 'Node.js 20 is deprecated'` returning `0` on the
      verification build (`gh run view 33319080212`, amd64 3m54s + aarch64 11m1s, both `success`)
- [x] **CI-04**: `actions/checkout` sits at one single major version across every workflow that uses it (no v4/v6/v7
      split) — closed by `grep -rh 'actions/checkout@' .github/workflows/ | sort -u` returning exactly one unique line
      (`actions/checkout@v7`), 5 occurrences total
- [ ] **CI-05**: Home Assistant receives and observably processes the `started` notification for a real add-on build —
      the receiving automation's `last_triggered` advances, since HA returns 200 for any webhook ID whether registered
      or not
- [ ] **CI-06**: Home Assistant receives the `finished` notification carrying `conclusion` and `image_tag`
- [ ] **CI-07**: The webhook path remains protected; an unauthenticated POST from the public internet is still
      redirected to the Cloudflare Access login and does not reach HA
- [ ] **CI-08**: A notification failure can never fail a build, but it is reported actionably — a `3xx` fails fast
      naming the Access policy instead of three identical retries against a non-transient condition
- [x] **CI-09**: No document references the removed `.github/workflows/build.yml`; the build trigger and the
      `<addon>/v<version>` tag schema are described as they actually are, and no doc advertises a capability the code
      lacks
- [x] **CI-10**: The per-add-on tag-trigger state is documented with its rationale, so the in-workflow comment pointing
      at `.github/RELEASE.md` resolves to a real explanation

---

## Future Requirements

<!-- Deferred — revisit in v1.2 -->

- SSH key handling for private git repos (HTTPS-only repos in v1.1; credential-free pull only)
- HA Camera Entity image proxying with hash-based cache expiry (`homeassistant_api`)
- Web editor / in-browser Markdown editing
- PDF export
- Multi-arch builds (arm64, armv7)
- Periodic git sync via external webhook trigger
- Per-namespace Docsify theme customization

---

## Out of Scope

<!-- Explicit exclusions with reasoning -->

- **SSH credentials for private repos** — Handling SSH keys in a personal add-on adds complexity and security surface
  without clear need; HTTPS public repos cover the primary use case for v1.1
- **Web editor** — Read-only viewer first; editing Markdown in the browser requires backend write access and conflict
  handling
- **PDF export** — HTML rendering is the stated goal; PDF adds Pandoc/Weasyprint and build latency
- **Multi-arch** — Both HA hosts are x86_64; consistent with all existing add-ons in this repo
- **HA state integration** — Camera entities, sensor values, entity state in Markdown deferred to v1.2; requires
  `homeassistant_api` proxying

---

## Traceability

| REQ-ID     | Phase                                     | Plan                                                                                                                |
| ---------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| ADD-01     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| ADD-02     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| ADD-03     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| ADD-04     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-01 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-02 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-03 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-04 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-05 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| MULTI-01   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-02   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-03   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-04   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-05   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-06   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| KROKI-01   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-02   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-03   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-04   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-05   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| GIT-01     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario A, 18 assertions)                                              |
| GIT-02     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario A — `git config --global` ran at startup)                      |
| GIT-03     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario C — no git pull/clone in logs)                                 |
| GIT-04     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario D — 4 git pull invocations during 15s window)                  |
| GIT-05     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario B — unreachable URL, WARNING in logs, container stays running) |
| CI-01      | Phase 8: CI/CD Hardening                  | 08-01 (Tasks 1-3: 6 caps across 5 workflow files; invariant = declarations equal job count)                         |
| CI-02      | Phase 8: CI/CD Hardening                  | 08-01 (Task 1: build job capped at 45 min, derived from the measured 13m28s aarch64 leg)                            |
| CI-03      | Phase 8: CI/CD Hardening                  | 08-02 (Task 1 + Task 3: 4 Docker actions bumped; verified by absence of the Node 20 annotation on a real build)     |
| CI-04      | Phase 8: CI/CD Hardening                  | 08-02 (Task 2: all 5 `actions/checkout` references unified on one major)                                            |
| CI-05      | Phase 8: CI/CD Hardening                  | 08-05 (gap-closure — Task 5 #4: HA-side `last_triggered` advances; 08-03 partial covered Tasks 2-4 only)            |
| CI-06      | Phase 8: CI/CD Hardening                  | 08-05 (gap-closure — Task 5 #5: end-to-end build log shows two `HA notification OK` notices and zero 302 warnings)  |
| CI-07      | Phase 8: CI/CD Hardening                  | 08-03 partial (Task 5 #2 negative edge probe PASSED — HTTP 302 to Access login); 08-05 Task 5 #4 re-confirms        |
| CI-08      | Phase 8: CI/CD Hardening                  | 08-03 partial (Task 2 script logic in place — `^3` branch precedes `LAST_ERR`, no `-L`, always `exit 0`)            |
| CI-09      | Phase 8: CI/CD Hardening                  | 08-04 (Tasks 1-2: 9 drift instances incl. the false `HA_WEBHOOK_SECRET` capability claim)                           |
| CI-10      | Phase 8: CI/CD Hardening                  | 08-04 (Task 3: per-add-on tag-trigger table + rationale from 287c79f / 60e7835)                                     |

---

_Last updated: 2026-08-31 — v1.3 opentofu-bridge requirements added (TOFU-01..05, AUTH-01..07, BRIDGE-01..10,
PROV-01..12, STATE-01..03, LIFE-01..04, OPS-01..05 = 46 reqs); traceability filled by `gsd-roadmapper` mapping every req
to exactly one phase across the 7-phase v1.3 roadmap (Phases 9-15) — no orphans, no duplicates._
