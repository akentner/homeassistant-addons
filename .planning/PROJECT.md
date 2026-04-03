# Home Assistant Add-ons Repository

## What This Is

A Home Assistant Add-ons repository providing containerized wrappers for upstream applications. The repository does not
contain application source code — Dockerfiles download upstream release artifacts at build time. Each add-on provides a
`config.yaml` manifest, Dockerfile, and `run.sh` entrypoint that bridges HA configuration (via bashio/options.json) to
the application. Currently hosts `fritz-callmonitor2mqtt` (FRITZ!Box → MQTT bridge) and `phone-logger` (call logging
with adapter architecture). A third add-on, `meridian` (Claude Max → local API proxy), is in active development.

## Core Value

Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version tracking.

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

### Active

<!-- Current scope. Building toward these. -->

- [ ] `meridian` add-on: Claude Max subscription → local Anthropic-compatible API proxy (port 3456), source fetched from
      GitHub at build time, `claude login` via HA terminal, token persisted in `/data`

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Multi-arch builds (arm64, armv7) — added complexity without clear need; both hosts are x86_64 (op3050, LXC)
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
- **Auto-update gap**: Resolved — `.github/workflows/auto-update.yml` now implements daily upstream version sync.
  `.upstream.yaml` files in both existing add-ons are fully wired.

## Constraints

- **Tech stack**: HA base images (`ghcr.io/home-assistant/`) only — no generic Alpine/Python/Node base images for add-on
  containers
- **Pattern consistency**: New add-ons must follow the established 4-file pattern (config.yaml, build.yaml, Dockerfile,
  run.sh) + `.upstream.yaml`
- **No bundled source**: Dockerfiles must download upstream code at build time, not copy local source
- **Meridian auth**: `claude login` requires interactive terminal — handled via HA terminal add-on, not automation

## Key Decisions

| Decision                                              | Rationale                                                      | Outcome   |
| ----------------------------------------------------- | -------------------------------------------------------------- | --------- |
| Download upstream at build time, no bundled source    | Keeps repo lean; version updates are a Dockerfile ARG change   | ✓ Good    |
| `claude login` via HA terminal for Meridian           | Avoids OAuth token in plaintext config; simpler setup          | — Pending |
| Meridian source from GitHub (not npm) at build time   | Consistent with existing add-on pattern; no node_modules bloat | — Pending |
| Fully automatic auto-update merge (no manual PR step) | Upstream releases are trusted (own projects + meridian)        | ✓ Good    |

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

_Last updated: 2026-04-04 after Phase 02: auto-update-workflow complete_
