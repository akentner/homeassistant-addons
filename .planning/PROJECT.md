# Home Assistant Add-ons Repository

## What This Is

A Home Assistant Add-ons repository providing containerized wrappers for upstream applications. The repository does not
contain application source code — Dockerfiles download upstream release artifacts at build time. Each add-on provides a
`config.yaml` manifest, Dockerfile, and `run.sh` entrypoint that bridges HA configuration (via bashio/options.json) to
the application. Currently hosts `fritz-callmonitor2mqtt` (FRITZ!Box → MQTT bridge), `phone-logger` (call logging with
adapter architecture), and `meridian` (Claude Max → local Anthropic-compatible API proxy on port 3456).

## Core Value

Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version tracking.

## Current Milestone: v1.4 iac-runner (planning)

**Goal:** Ship a Home Assistant Supervisor add-on (`iac-runner/`) that clones a Git repo (e.g. `homelab-infra`), runs
OpenTofu/Terraform `plan`/`apply` against homelab servers (Tailscale-reachable), persists state in R2 (default),
S3-compatible, or local backend, and surfaces run status + manual triggers as Home Assistant entities via MQTT
Discovery. Manual REST trigger only — webhook-Auto-Rollout deferred to v1.5.

**Architecture (decided 2026-09-06):**

- **`iac-runner/`** — Go HTTP service on port 8125 (separate from `terraform-bridge`'s 8124). Tailscale-bind-gate (same
  pattern as `terraform-bridge`, but no `SUPERVISOR_TOKEN` — `iac-runner` does not need Supervisor access;
  `hassio_api: true` is NOT set; only `homeassistant_api: true` for the MQTT service connection). Follows the standard
  4-file pattern. No `.upstream.yaml`. `host_network: true` for SSH access to homelab servers via Tailscale IPs.
- **Multi-backend state** — Options-driven: `r2` (Cloudflare R2 via S3-compatible API, default), `s3` (any
  S3-compatible), `local` (`/data/terraform.tfstate`). Locking via `use_lockfile = true` for R2/S3, file-based lock for
  local. R2 lockfile semantics verified empirically in Phase 16 spike (IRUN-H-1).
- **Git integration** — At startup, clones configured repos into `/data/repos/<name>/`. `POST /v1/repos/{name}/pull`
  runs `git pull` using SSH deploy keys from `/data/keys/<name>.key` (chmod 600, validated at startup) and `known_hosts`
  from `/data/keys/known_hosts`.
- **Apply workflow** — `POST /v1/plan` and `POST /v1/apply` start jobs (in-process serial per-repo mutex); returns
  `run_id`; status polled via `GET /v1/runs/{id}`. Stdout/stderr captured to `/data/runs/{run_id}/output.log`; secrets
  redacted from output before surfacing via API.
- **HA entities** — `services: ["mqtt:need"]` + MQTT Discovery for three sensors (`iac_runner_last_run_status`,
  `iac_runner_last_apply_at`, `iac_runner_last_error`) and two buttons (`iac_runner_run_plan`, `iac_runner_run_apply`).
  Button presses debounced (30s). MQTT button semantics verified in Phase 18 spike (IRUN-H-2).
- **Secrets** — SSH deploy keys, R2/S3 credentials stored as files under `/data/keys/` (chmod 600 enforced at startup);
  never logged; redacted from `tofu` output before API surfacing.

**Phase 16 scope (decided):** Scaffold + Bearer-auth + Tailscale-bind + three State-Backends (r2/s3/local) +
`/healthz` + `/v1/version` + `/data/keys/` chmod-600 enforcement + log-scrubbing.

**Source:** Conversation 2026-09-06. RESEARCH skipped by explicit decision (scope clear from conversation; patterns
reused from `terraform-bridge` and `markdown-renderer`). Requirements `AUTHR-01..04`, `STBK-01..05`, `SEC-01..03`,
`GIT-01..04`, `RUN-01..06`, `MQTT-01..06`, `OBS-01..03` (≈30 total) to be defined in step 9 of this workflow.

**Status (2026-09-06):** v1.4 planning. v1.3 is essentially complete (6 of 7 phases shipped: 9–14; Phase 15
CI/install-provider pending only because of the v1.2 Phase 8 gap-closure Cloudflare-setup blocker — `08-05-GAP-PLAN.md`
remains ready). v1.4 explicitly runs in parallel to v1.3 Phase 15 + v1.2 Phase 8 gap-closure per user decision
2026-09-06.

## Previous Milestone: v1.3 opentofu-bridge (ESSENTIALLY COMPLETE 2026-09-05)

**Goal:** Ship a Home Assistant add-on that exposes the Supervisor API as a versioned HTTP service consumable by a
custom OpenTofu provider living in this repo, so that Apps (and eventually other HA resources) can be managed via
declarative `*.tf` configuration.

**Status:** Phases 9–14 SHIPPED (commit `b44f478 terraform-bridge 0.3.0 + provider 0.3.0 (Phase 11-14 program logic)`,
plus later phase commits). `terraform-bridge/v0.3.0` and `terraform-provider-homeassistant/v0.3.0` released. Only Phase
15 (CI hardening + provider install workflow) remains pending because of the v1.2 Phase 8 gap-closure blocker
(Cloudflare service token + 2 GitHub secrets needed); the phase itself is mechanically ready, just blocked.

## Previous Milestone: v1.1 markdown-renderer (COMPLETE 2026-06-28)

**Goal:** New `markdown-renderer` add-on that serves multiple Markdown directories as namespaced HTML endpoints via HA
Ingress, with extensible diagram rendering and optional Git sync.

**Target features:**

- Add-on Grundgerüst nach bestehendem 4-File-Pattern (config.yaml, build.yaml, Dockerfile, run.sh, .upstream.yaml)
- Multi-Directory Routing: je konfiguriertes Verzeichnis ein eigenes `/namespace/` unter Ingress
- Client-seitiges Markdown-Rendering (Docsify oder äquivalentes Tool nach Research)
- Mermaid + erweiterbare Diagram-Renderer eingebunden
- Optionale Git-Integration: pull beim Start / periodisch, falls Verzeichnis ein Git-Repo ist

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ `fritz-callmonitor2mqtt` add-on — bridges FRITZ!Box call monitor events to MQTT — existing
- ✓ `phone-logger` add-on — structured call logging with pluggable adapter architecture — existing
- ✓ 3-file version synchronization enforced by pre-commit hooks — existing
- ✓ CI/CD with YAML lint, shellcheck, structure validation, version validation via GitHub Actions — existing
- ✓ `make update-version` tooling for safe version bumping — existing
- ✓ `validate-versions` hook extended to cover `phone-logger` — Validated in Phase 01: quality-fixes
- ✓ `phone-logger/DOCS.md` adapter type corrected (`fritz_callmonitor`) — Validated in Phase 01: quality-fixes
- ✓ Hadolint re-enabled in `.pre-commit-config.yaml` with HA-specific ignore rules — Validated in Phase 01:
  quality-fixes
- ✓ Auto-update GitHub Actions workflow: daily upstream version check (06:00 UTC), fully automatic 3-file version update
  - commit to main via GITHUB_TOKEN — Validated in Phase 02: auto-update-workflow
- ✓ `meridian` add-on: Claude Max subscription → local Anthropic-compatible API proxy (port 3456), two-stage Dockerfile
  (bun + HA base), `claude login` via HA terminal, OAuth token persisted in `/data/.claude` — Validated in Phase 03:
  meridian-add-on
- ✓ `markdown-renderer` Grundgerüst + multi-namespace routing empirically verified (35 assertions pass, MULTI-01..06) —
  Validated in Phase 05: multi-namespace-dynamic-config
- ✓ `markdown-renderer` optional per-namespace git sync empirically verified (18 assertions pass, GIT-01..05) —
  Validated in Phase 06: git-integration
- ✓ `terraform-bridge` auth layer + structured logging + healthcheck landed — bearer token with SHA-256 hash-at-rest +
  atomic chmod 600 (AUTH-02), crypto/subtle.ConstantTimeCompare 401 path (AUTH-03), POST /v1/auth/rotate with 24h grace
  file (AUTH-04), two-layer log masking (AUTH-05), Tailscale-interface bind-address gate with 0.0.0.0 refusal (AUTH-07),
  per-request slog records with OPS-01 mandatory fields (OPS-01), GET /healthz probing Supervisor via 2s timeout
  SupervisorClient (OPS-03) — Validated in Phase 10: auth-layer-structured-logging-healthcheck
- ✓ `terraform-bridge` Bridge Read API (Phase 11) + Write API + Critical-Addon Safety + Concurrency + State Index (Phase
  12, 12-01+12-02+12-03) + Provider Resource + Data Sources + Schema Handshake (Phase 13, 13-01+13-02+13-03)
  - Real-HA E2E + Operator Docs (Phase 14, 14-01+14-02+14-03) all shipped end-to-end as `terraform-bridge/v0.3.0` +
    `terraform-provider-homeassistant/v0.3.0`. Phase 15 (CI hardening + provider install workflow) mechanically ready,
    blocked only on v1.2 Phase 8 gap-closure Cloudflare-setup prerequisite — Validated in Phases 11–14; Phase 15 partial
    (CI workflows + install target landed; full release pending user Cloudflare setup)
- ✓ `iac-runner` add-on scaffold + Bearer-auth + Tailscale-bind + three State-Backends (r2/s3/local) + `/healthz` +
  `/v1/version` + `/data/keys/` chmod-600 enforcement + log-scrubbing all landed. 4-file pattern (port 8125, no
  `hassio_api`, `homeassistant_api` for `mqtt:need`); TokenStore with crypto/rand + SHA-256 + chmod 600 atomic rename +
  ConstantTimeCompare + 24h grace (AUTHR-02); Tailscale-bind with 0.0.0.0 refusal (AUTHR-03); POST /v1/auth/rotate with
  grace persistence (AUTHR-04); Backend interface + r2/s3/local with use_lockfile=true for cloud + file-lock for local
  (STBK-01..05); slog.Handler scrubber redacts Authorization/Bearer/token/password/key/secret (SEC-02); /data/keys/
  chmod-600 validator with os.Exit(1) on failure (SEC-01); per-request slog record with Authorization strip (OBS-01). 44
  unit tests across 5 packages. Live-HA empirical exercise deferred to Phase 19 — Validated in Phase 16:
  iac-runner-scaffold-auth-state-backends-healthcheck

### Active

<!-- Current scope. Building toward these. -->

### v1.4 iac-runner (Phase 16 complete; Phases 17–19 pending)

**Phase 16 (complete 2026-09-06):** Scaffold + Bearer-auth + Tailscale-bind + three State-Backends (r2/s3/local) +
`/healthz` + `/v1/version` + `/data/keys/` chmod-600 enforcement + log-scrubbing. See Validated entry above.

- Git integration: clone configured repos at startup; SSH deploy keys from `/data/keys/` (Phase 17)
- Manual REST triggers: `POST /v1/plan`, `POST /v1/apply` → `GET /v1/runs/{id}` for status; per-repo mutex for serial
  applies (Phase 17)
- HA entities via MQTT Discovery: 3 sensors (last_run_status, last_apply_at, last_error) + 2 buttons (run_plan,
  run_apply) with 30s debounce (Phase 18)
- Output redaction (SEC-03) + paginated `GET /v1/runs/{id}` (OBS-02, OBS-03) (Phase 17)
- Live-HA empirical exercise + operator runbook (Phase 19)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Multi-arch builds (arm64, armv7) — added complexity without clear need; both hosts are x86_64 (op3050, LXC)
- HA Camera Entity Integration in markdown-renderer — deferred to v1.2; image hash refresh requires HA API proxying
- Web-Editor / In-Browser-Editing für markdown-renderer — out of scope v1.1; read-only viewer first
- PDF Export für markdown-renderer — out of scope v1.1; HTML-Rendering priorisiert
- Unit tests for `generate_config.py` / `update-version.py` — low risk, infrequent changes, no framework chosen
- Binary integrity verification (SHA checksums) — trusted GitHub Releases source, personal/private deployment
- Git-Webhook-Auto-Rollout für iac-runner — deferred to v1.5; auto-apply needs an approval-gate + secrets-in-CI design
  pass
- Ansible-Support für iac-runner — deferred to v1.5 or v1.6 (separate add-on `iac-runner-ansible` or second mode in same
  add-on; design decision deferred)
- Multi-Repo UI für iac-runner — v1.4 supports one configured repo via Options; multi-repo as field exists but no UI
- Approval-Gate vor `tofu apply` — manual trigger IS the approval gate; explicit approval flow deferred to v1.5+
- HA WebSocket-basierte Custom-Integration für iac-runner — MQTT Discovery covers the use case; WebSocket would require
  a Custom-Component in HA Core

## Context

- **Infrastructure**: Three HA hosts reachable via SSH on Tailscale (`haos-op3050-1`, `lxc-haos-104`, `hassio-n2plus`);
  all x86_64
- **Upstream source pattern**: All apps download release artifacts at Docker build time — no app source lives in this
  repo. This is intentional: the repo wraps upstream, it doesn't fork it.
- **Meridian specifics**: Originally named `opencode-claude-max-proxy`, renamed to `meridian`. Requires `claude login`
  (OAuth) for first-time auth. The HA terminal approach (one-time manual login, token persisted in `/data`) was chosen
  over credential injection to avoid handling OAuth tokens as plain config values.
- **v1.0 state**: All three add-ons fully scaffolded and passing CI. Meridian requires one-time `claude login` via HA
  terminal; subsequent restarts use persisted token in `/data/.claude`.
- **Auto-update**: `.github/workflows/auto-update.yml` runs daily at 06:00 UTC, discovers add-ons via `.upstream.yaml`,
  and commits 3-file version updates directly to main.

## Constraints

- **Tech stack**: HA base images (`ghcr.io/home-assistant/`) only — no generic Alpine/Python/Node base images for add-on
  containers
- **Pattern consistency**: New add-ons must follow the established 4-file pattern (config.yaml, build.yaml, Dockerfile,
  run.sh) + `.upstream.yaml`
- **No bundled source**: Dockerfiles must download upstream code at build time, not copy local source
  - **Exception (v1.3 opentofu-bridge):** `terraform-provider-homeassistant/` is built from local source because the
    provider and the bridge must version together
- **Meridian auth**: `claude login` requires interactive terminal — handled via HA terminal add-on, not automation

## Key Decisions

| Decision                                               | Rationale                                                                                                                                                                                   | Outcome |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Download upstream at build time, no bundled source     | Keeps repo lean; version updates are a Dockerfile ARG change                                                                                                                                | ✓ Good  |
| `claude login` via HA terminal for Meridian            | Avoids OAuth token in plaintext config; simpler setup                                                                                                                                       | ✓ Good  |
| Meridian source from GitHub (not npm) at build time    | Consistent with existing add-on pattern; no node_modules bloat                                                                                                                              | ✓ Good  |
| Fully automatic auto-update merge (no manual PR step)  | Upstream releases are trusted (own projects + meridian)                                                                                                                                     | ✓ Good  |
| v1.3: Bridge add-on + Provider co-located in this repo | Provider and Bridge must evolve together; cross-repo versioning overhead is unjustified for a private tool                                                                                  | ✓ Good  |
| v1.3: Bearer token for Provider → Bridge auth          | mTLS needs a CA inside the container; OAuth adds a UI surface for one client. Bearer is the smallest correct primitive                                                                      | ✓ Good  |
| v1.3: Local state backend in `/data/terraform.tfstate` | Single-user / single-host setup today; remote backend only worth the complexity when CI or multi-host applies arrive                                                                        | ✓ Good  |
| v1.4: New milestone, not Phase 16 in v1.3              | Different runtime semantics (HTTP service vs long-running executor), different auth needs (SSH keys vs Supervisor-Token), different state model. Name + scope don't fit a single milestone. | ✓ Good  |
| v1.4: Multi-backend state (r2 default + s3 + local)    | User already has Cloudflare R2; R2 supports `use_lockfile = true` (no DynamoDB). User explicitly requested all three backends.                                                              | ✓ Good  |
| v1.4: SSH deploy keys in `/data/keys/{repo}.key`       | Personal/private deployment; per-repo SSH keys too long for HA Options UI; matches `terraform-bridge`'s `/data/initial-token` pattern (file-on-volume instead of config).                   | ✓ Good  |
| v1.4: Manual REST trigger only, no webhook             | Manual trigger = implicit human approval gate; auto-rollout needs an approval flow + secrets-in-CI design pass (deferred to v1.5).                                                          | ✓ Good  |
| v1.4: HA entities via MQTT Discovery (not WebSocket)   | MQTT Discovery is the standard HA add-on integration path; no custom integration install needed. WebSocket would require a Custom-Component in HA Core (more setup, less portable).         | ✓ Good  |
| v1.4: 4 phases (16–19), not 7 like v1.3                | Concerns group more naturally: scaffold/auth/state → git/apply-jobs → MQTT/HA → E2E/docs. 17 + 18 may parallelize after Phase 16 stabilises the contracts.                                  | ✓ Good  |
| v1.4: RESEARCH skipped                                 | Scope clear from conversation; patterns reused from `terraform-bridge` (HTTP/auth/Go) and `markdown-renderer` (git integration). Research would re-validate what is already decided.        | ✓ Good  |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):

1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):

1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

---

_Last updated: 2026-09-06 — Phase 16 (iac-runner Scaffold + Auth + State Backends + Healthcheck) COMPLETE 12/12
requirements validated. v1.4 Phases 17–19 remain. v1.3 essentially complete (6 of 7 phases shipped: 9–14; Phase 15 CI
hardening mechanically ready, blocked on v1.2 Phase 8 gap-closure Cloudflare-setup prerequisite —
`/gsd-execute-phase 8 --gaps-only` when ready). v1.4 runs in parallel to v1.3 Phase 15 by user decision 2026-09-06. v1.4
roadmap: 4 phases (16–19), ~32 requirements across AUTHR/STBK/SEC/GIT/RUN/MQTT/OBS categories. RESEARCH skipped by
explicit decision (scope clear from conversation). Phase 16 ready to plan via `/gsd-plan-phase 16`._
