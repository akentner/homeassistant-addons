# Milestones

## v1.0 MVP (Shipped: 2026-04-04)

**Phases completed:** 3 phases, 6 plans **Timeline:** 2026-04-03 → 2026-04-04 **Files changed:** 75 files, 8,740
insertions

**Key accomplishments:**

1. `validate-versions` pre-commit hook extended to cover all three add-ons (fritz-callmonitor2mqtt, phone-logger,
   meridian)
2. `phone-logger/DOCS.md` adapter type corrected (`fritz` → `fritz_callmonitor`)
3. hadolint v2.14.0 re-enabled in pre-commit with four HA-specific ignore rules (DL3006, DL3018, DL3059, DL4006); DL3016
   added for `npm install -g`
4. GitHub Actions auto-update workflow: daily upstream version check (06:00 UTC), fully automatic 3-file version
   update + commit to main via GITHUB_TOKEN, dynamic add-on discovery via `.upstream.yaml`
5. Meridian add-on: two-stage Dockerfile (oven/bun:1 build + HA amd64-base:3.22 runtime), GitHub tarball fetch at build
   time, auto-update wiring for rynfar/meridian
6. Meridian run.sh: OAuth token persisted via `/data/.claude` symlink, credential guard with actionable error message,
   port 3456 exposed on 0.0.0.0 for LAN/Tailscale

**Archive:**

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`

---

## v1.1 markdown-renderer (Complete: 2026-06-28)

**Phases completed:** 3 phases (4-6), 6 plans **Timeline:** 2026-04-04 → 2026-06-28

**Key accomplishments:**

1. `markdown-renderer` add-on scaffolded following the 4-file pattern (`config.yaml`, `build.yaml`, `Dockerfile`,
   `run.sh`, `.upstream.yaml`) consistent with every other add-on in the repo
2. Multi-namespace Docsify routing via nginx with per-namespace SPA isolation (per-namespace `index.html`,
   `_docsify/`, `index.md`); 35 MULTI-01..06 assertions verified empirically
3. Per-namespace optional git sync with `git config --global --add safe.directory '*'` for mounted-volume UID
   mismatch; 18 GIT-01..05 assertions verified empirically
4. Kroki integration for PlantUML/GraphViz/etc. fenced code blocks (` ```plantuml `, ` ```dot `, ` ```blockdiag `)
5. Mermaid 11 UMD + Docsify 4.13 vendored at build time (no runtime CDN dependency)

**Archive:**

- `.planning/milestones/v1.1-phases/`

---

## v1.3 opentofu-bridge (Essentially Complete: 2026-09-05)

**Phases planned:** 7 phases (9-15), 46 requirements **Planned:** 2026-08-31 **Status:** 6 of 7 phases SHIPPED
(9, 10, 11, 12, 13, 14); Phase 15 (CI hardening + provider install workflow) mechanically ready but blocked on
v1.2 Phase 8 gap-closure Cloudflare-setup prerequisite. `terraform-bridge/v0.3.0` and
`terraform-provider-homeassistant/v0.3.0` released.

**Key accomplishments:**

1. `terraform-bridge/` add-on: 4-file pattern, multi-stage Go Dockerfile (`golang:1.25-alpine` → HA base 3.24), Go
   module with chi router and structured slog logging; full Supervisor HTTP API surface (read + write + critical-addon
   safety + per-slug mutex + state index)
2. `terraform-provider-homeassistant/` Go module (`terraform-plugin-framework` v1.19.0, protocol v6); built from
   local source (documented exception to upstream-at-build-time rule); full `homeassistant_addon` CRUD + import +
   timeouts + `homeassistant_addon` data source + `homeassistant_supervisor_info` data source
3. Phase 10 auth layer: `crypto/rand` 256-bit token, SHA-256 hash-at-rest with `chmod 600`,
   `crypto/subtle.ConstantTimeCompare` validation, 24h grace rotation, two-layer AUTH-05 scrubbing (slog handler +
   chi middleware), `/healthz` with 2s Supervisor probe
4. Phases 11–14 empirical verification: 16 new tests in Phase 11, race-clean concurrency in Phase 12, full Provider
   resource + data sources in Phase 13, `tools/test-addon/` + `internal/verify-bridge-e2e/` (12 per-error_code
   scenarios) + operator docs in Phase 14
5. Phase 15 CI scaffolding: `make install-provider` with `DESTDIR` override for OpenTofu `dev_overrides`;
   `.github/workflows/build-terraform-bridge.yml`, `test-terraform-provider.yml`, `test-install-provider.yml`
   (E2E with hermetic `tools/test-bridge-fixture/`)
6. Tailscale-bind-gate with explicit `0.0.0.0` refusal regardless of `bind_allowed_subnets` (AUTH-07); per-slug
   mutex for cross-host concurrent apply defense (STATE-03)
7. H-1 spike (SUPERVISOR_TOKEN rotation across Supervisor restart) verified empirically on haos-op3050-1
   (2026-08-31): `token_unchanged`. D-18 RESOLVED with defensive re-read-per-call design
   (`internal/supervisor/client.go:84-91`)

**Pending:** Phase 15 release blocked on v1.2 Phase 8 gap-closure Cloudflare-setup prerequisite. The phase itself
is mechanically ready (all code + CI workflows + install target committed); only the release cut requires
HA-notification infrastructure that lives in v1.2 Phase 8.

**Archive:**

- (not yet archived; will archive on `gsd-complete-milestone v1.3` after Phase 15 release)

---

## v1.4 iac-runner (Planning: 2026-09-06)

**Phases planned:** 4 phases (16-19), ~32 requirements **Planned:** 2026-09-06 **Status:** planning

**Goal:** Ship a Home Assistant Supervisor add-on (`iac-runner/`) that clones a Git repo (e.g. `homelab-infra`),
runs OpenTofu/Terraform `plan`/`apply` against homelab servers (Tailscale-reachable), persists state in R2 (default),
S3-compatible, or local backend, and surfaces run status + manual triggers as Home Assistant entities via MQTT
Discovery.

**Architecture (decided 2026-09-06):**

- **`iac-runner/`** — Go HTTP service on port 8125 (separate from `terraform-bridge`'s 8124). Tailscale-bind-gate
  (same pattern as `terraform-bridge`, but no `SUPERVISOR_TOKEN` — `iac-runner` does not need Supervisor access).
  Follows the standard 4-file pattern. No `.upstream.yaml`. `host_network: true` for SSH access to homelab servers
  via Tailscale IPs.
- **Multi-backend state** — Options-driven: `r2` (Cloudflare R2 via S3-compatible API, default), `s3` (any
  S3-compatible), `local` (`/data/terraform.tfstate`). Locking via `use_lockfile = true` for R2/S3 (native S3
  object lock; no DynamoDB required), file-based lock for local.
- **Git integration** — At startup, clones configured repos into `/data/repos/<name>/`. `POST /v1/repos/{name}/pull`
  runs `git pull` using SSH deploy keys from `/data/keys/<name>.key` (chmod 600, validated at startup) and
  `known_hosts` from `/data/keys/known_hosts`.
- **Apply workflow** — `POST /v1/plan` and `POST /v1/apply` start jobs (in-process serial per-repo mutex); returns
  `run_id`; status polled via `GET /v1/runs/{id}`. Stdout/stderr captured to `/data/runs/{run_id}/output.log`;
  secrets redacted from output before surfacing via API.
- **HA entities** — `homeassistant_api: true` + `services: ["mqtt:need"]`. MQTT Discovery for three sensors
  (`iac_runner_last_run_status`, `iac_runner_last_apply_at`, `iac_runner_last_error`) and two buttons
  (`iac_runner_run_plan`, `iac_runner_run_apply`). Button presses debounced (30s).

**Phase 16 scope (decided):** Scaffold + Bearer-auth + Tailscale-bind + three State-Backends (r2/s3/local) +
`/healthz` + `/v1/version` + `/data/keys/` chmod-600 enforcement + log-scrubbing.

**Source:** Conversation 2026-09-06. RESEARCH skipped by explicit decision (scope clear from conversation; patterns
reused from `terraform-bridge` and `markdown-renderer`).

---

_Last updated: 2026-09-06 — added v1.1 (complete), v1.3 (essentially complete, Phase 15 blocked on v1.2), v1.4
(planning) entries. The previous MILESTONES.md only listed v1.0, leaving v1.1 and v1.3's history implicit in
REQUIREMENTS.md and ROADMAP.md. Centralised milestone history here for at-a-glance repo history._
