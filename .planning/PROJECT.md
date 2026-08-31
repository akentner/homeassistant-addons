# Home Assistant Add-ons Repository

## What This Is

A Home Assistant Add-ons repository providing containerized wrappers for upstream applications. The repository does not
contain application source code — Dockerfiles download upstream release artifacts at build time. Each add-on provides a
`config.yaml` manifest, Dockerfile, and `run.sh` entrypoint that bridges HA configuration (via bashio/options.json) to
the application. Currently hosts `fritz-callmonitor2mqtt` (FRITZ!Box → MQTT bridge), `phone-logger` (call logging with
adapter architecture), and `meridian` (Claude Max → local Anthropic-compatible API proxy on port 3456).

## Core Value

Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version tracking.

## Current Milestone: v1.3 opentofu-bridge (in planning)

**Goal:** Ship a Home Assistant add-on that exposes the Supervisor API as a versioned HTTP service consumable by a
custom OpenTofu provider living in this repo, so that Apps (and eventually other HA resources) can be managed via
declarative `*.tf` configuration.

**Architecture (decided 2026-08-31):**

- **Bridge add-on (`terraform-bridge/`)** — HA Supervisor add-on that wraps the Supervisor HTTP API and exposes a
  stable, idempotent JSON-over-HTTP surface. Follows the standard 4-file pattern (`config.yaml`, `build.yaml`,
  `Dockerfile`, `run.sh`). No `.upstream.yaml` (no external upstream project).
- **OpenTofu provider (`terraform-provider-homeassistant/`)** — Go module at repo top-level, BUILT IN THIS REPO rather
  than downloaded from an upstream tag at build time. Reason: the provider schema and the Bridge API must evolve
  together; an out-of-tree provider would require cross-repo coordination that is overkill for a private tool. Both
  artifacts share the same version (3-file scheme).
- **Auth model (preliminary):** Add-on → Supervisor: SUPERVISOR_TOKEN (auto-injected by Supervisor). External Provider →
  Bridge: a long-lived bearer token generated and rotated by the Bridge, surfaced through the add-on's config UI.
- **State backend:** Local Terraform state file in the add-on volume (`/data/terraform.tfstate`). Remote backend
  (S3-compatible, etc.) deferred until multiple users / CI apply runs demand it.

**Phase 1 scope (decided):** `homeassistant_addon` resource — install/start/stop/uninstall + options-schema CRUD.
Optional in Phase 1: `homeassistant_addon_repository` for managing store repositories.

**Source:** TBD — `.planning/phases/09-opentofu-bridge-scaffold/` will be created by `gsd-roadmapper` after this
milestone plan is approved. Requirements `TOFU-01..NN` to be defined in step 9 of this workflow.

**Status (2026-08-31):** v1.2 ci-cd-hardening (Phase 8) running in parallel — `08-05-GAP-PLAN.md` remains ready for
`/gsd-execute-phase 8 --gaps-only` whenever the Cloudflare service token and GitHub secrets are in place. Per explicit
user decision, v1.3 starts parallel to v1.2 rather than waiting for Phase 8 closure.

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
- ✓ CI hardening + Provider install workflow (TOFU-04) — `make install-provider` with DESTDIR override builds
  `terraform-provider-homeassistant` from local source and installs to `${DESTDIR}${HOME}/.terraform.d/plugins/localhost/akentner/homeassistant/<version>/` for OpenTofu dev_overrides; `internal/verify-install-provider.sh` hermetic shell verifier; `.github/workflows/build-terraform-bridge.yml` (Bridge image build on push + tag, GHCR push via reusable `_build-template.yml`); `.github/workflows/test-terraform-provider.yml` (gofmt -l + go vet + go test on Provider, explicit `timeout-minutes: 10`); `.github/workflows/test-install-provider.yml` E2E (build + install + ephemeral fixture + `tofu init` + `tofu plan` with handshake check, `timeout-minutes: 15`); `GET /v1/version` Bridge handler + `tools/test-bridge-fixture/` stdlib-only HTTP simulator for the E2E handshake test — Validated in Phase 15: ci-hardening-provider-install-workflow

### Active

<!-- Current scope. Building toward these. -->

### v1.3 opentofu-bridge (planning)

- `terraform-bridge` add-on — HTTP/REST service wrapping the Supervisor API, consumable by an external OpenTofu provider
- `terraform-provider-homeassistant` Go module — co-located in this repo, shares 3-file versioning with the bridge
- Phase-1 resource: `homeassistant_addon` (CRUD: install, start, stop, uninstall, options update)
- Bearer-token auth for Provider → Bridge (token generated/rotated by the add-on)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Multi-arch builds (arm64, armv7) — added complexity without clear need; both hosts are x86_64 (op3050, LXC)
- HA Camera Entity Integration in markdown-renderer — deferred to v1.2; image hash refresh requires HA API proxying
- Web-Editor / In-Browser-Editing für markdown-renderer — out of scope v1.1; read-only viewer first
- PDF Export für markdown-renderer — out of scope v1.1; HTML-Rendering priorisiert
- Unit tests for `generate_config.py` / `update-version.py` — low risk, infrequent changes, no framework chosen
- Binary integrity verification (SHA checksums) — trusted GitHub Releases source, personal/private deployment

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

| Decision                                               | Rationale                                                                                                              | Outcome |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | ------- |
| Download upstream at build time, no bundled source     | Keeps repo lean; version updates are a Dockerfile ARG change                                                           | ✓ Good  |
| `claude login` via HA terminal for Meridian            | Avoids OAuth token in plaintext config; simpler setup                                                                  | ✓ Good  |
| Meridian source from GitHub (not npm) at build time    | Consistent with existing add-on pattern; no node_modules bloat                                                         | ✓ Good  |
| Fully automatic auto-update merge (no manual PR step)  | Upstream releases are trusted (own projects + meridian)                                                                | ✓ Good  |
| v1.3: Bridge add-on + Provider co-located in this repo | Provider and Bridge must evolve together; cross-repo versioning overhead is unjustified for a private tool             | ✓ Good  |
| v1.3: Bearer token for Provider → Bridge auth          | mTLS needs a CA inside the container; OAuth adds a UI surface for one client. Bearer is the smallest correct primitive | ✓ Good  |
| v1.3: Local state backend in `/data/terraform.tfstate` | Single-user / single-host setup today; remote backend only worth the complexity when CI or multi-host applies arrive   | ✓ Good  |

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

_Last updated: 2026-08-31 — Milestone v1.3 Phase 15 complete: CI hardening + Provider install workflow (TOFU-04) — 11
atomic commits across 3 plans: Makefile `install-provider` target + hermetic `verify-install-provider.sh`; three
GitHub Actions workflows (Bridge build + Provider test + E2E `tofu init`/`tofu plan` handshake check); `GET /v1/version`
handler on Bridge + `tools/test-bridge-fixture/` CI-only simulator. Phase 15 is the LAST phase of v1.3 milestone —
milestone complete pending live-HA E2E verification (Phase 14, deferred) and Phase 9 H-1/§10 spike transcripts (still
needed for PROV-03 contingency resolution). v1.2 Phase 8 gap-closure (08-05) still pending user Cloudflare setup —
`/gsd-execute-phase 8 --gaps-only`._
