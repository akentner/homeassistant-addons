# Phase 3: Meridian Add-on - Context

**Gathered:** 2026-04-04 **Status:** Ready for planning

<domain>
## Phase Boundary

Create the complete `meridian/` add-on directory: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`,
`DOCS.md`, `.upstream.yaml`. The add-on wraps the upstream `rynfar/meridian` TypeScript proxy, which exposes a local
Anthropic-compatible API on port 3456 backed by a Claude Max subscription.

No Meridian source lives in this repo — the Dockerfile fetches the upstream GitHub archive at build time. The add-on
handles: credential persistence across restarts, startup guard when credentials are absent, port exposure, and version
tracking via the 3-file scheme.

Also in scope: update `.pre-commit-config.yaml` so the `validate-versions` hook triggers on `meridian/` file changes.

</domain>

<decisions>
## Implementation Decisions

### Dockerfile Build Strategy

- **D-01:** Multi-stage build: `oven/bun:1` as build stage, `ghcr.io/home-assistant/amd64-base` as runtime stage.
  (Specified in MER-02; consistent with upstream Meridian Dockerfile pattern.)
- **D-02:** Source fetch: download the versioned GitHub archive tarball at build time —
  `https://github.com/rynfar/meridian/archive/refs/tags/v${VERSION}.tar.gz` — same pattern as `phone-logger`. No git
  clone, no npm registry.
- **D-03:** Runtime stage installs `nodejs` and `npm` via `apk add --no-cache nodejs npm`. Both are needed: `nodejs` to
  run `dist/cli.js`, `npm` to install `@anthropic-ai/claude-code` (which provides the `claude` CLI).
- **D-04:** `node_modules/` is copied from the bun build stage to the runtime stage (not re-installed at runtime).
  `dist/` is also copied from the build stage. Same pattern as zigbee2mqtt reference. This keeps startup fast and avoids
  network access at container start.

### run.sh — Credential Check and Startup

- **D-05:** On startup, `run.sh` creates the symlink `/root/.claude → /data/.claude` so the OAuth token directory
  persists across container restarts via the HA `/data` volume. (MER-05)
- **D-06:** Credential check: test for existence of `/data/.claude/.claude.json`. Presence means `claude login` was
  completed.
- **D-07:** When credentials are absent: print clear setup instructions via `bashio::log.error` explaining how to run
  `claude login` via the HA terminal add-on, then `exit 1`. Fail immediately — do not poll. HA marks the add-on as
  failed; user fixes it and restarts.
- **D-08:** `MERIDIAN_HOST=0.0.0.0` is exported so the proxy binds to all interfaces and is reachable from LAN and
  Tailscale. (MER-07)
- **D-09:** `run.sh` uses `#!/usr/bin/with-contenv bashio` shebang with `# shellcheck shell=bash` — standard HA add-on
  pattern, consistent with `fritz-callmonitor2mqtt/run.sh`.

### Supervisor / Process Management

- **D-10:** `run.sh` ends with `exec node dist/cli.js` (or equivalent supervisor script invocation). S6 in the HA base
  image wraps `run.sh` and manages restart policy — no custom S6 overlay directory needed. HA's add-on restart policy
  handles crash recovery at the container level.
- **D-11:** The upstream `bin/claude-proxy-supervisor.sh` is NOT used. The S6 + HA approach keeps the add-on consistent
  with the existing pattern in this repo.

### config.yaml Options Schema

- **D-12:** Two user-configurable options exposed:
  - `log_level` — list(debug|info|warning|error), default `info`. Passed as env var to control proxy verbosity.
  - `port` — int, default `3456`. Allows users with port conflicts to remap.
- **D-13:** Port 3456 declared in `config.yaml` `ports` section (e.g., `3456/tcp: Meridian proxy port`) so it is
  accessible from LAN and Tailscale and visible in the HA add-on UI. (MER-04)
- **D-14:** `url` field in `config.yaml` points to this repository: `https://github.com/akentner/homeassistant-addons` —
  consistent with the other two add-ons.

### Pre-commit Hook Coverage

- **D-15:** Update the `validate-versions` hook's `files:` pattern in `.pre-commit-config.yaml` to include `meridian`
  alongside `fritz-callmonitor2mqtt` and `phone-logger`. The script itself is already dynamic (find-based), but
  pre-commit only triggers on matching file paths. Pattern should become:
  `^(fritz-callmonitor2mqtt|phone-logger|meridian)/(config\.yaml|build\.yaml|README\.md)$`

### Hadolint Rules

- **D-16:** Add `DL3016` to the hadolint ignore list in `.pre-commit-config.yaml`. This rule flags `npm install -g`
  without a pinned version — necessary for `@anthropic-ai/claude-code` in the runtime stage. Existing rules (DL3006,
  DL3018, DL3059, DL4006) remain unchanged and cover the bun build stage patterns.

### Version Tracking

- **D-17:** `.upstream.yaml` watches `rynfar/meridian`, `version_pattern: "v*"`, `version_strip: "^v"`,
  `addon.version_pattern: "sync"` — identical structure to existing add-ons. (MER-08)
- **D-18:** Initial version set to current latest upstream release (v1.26.6 as of 2026-04-04): `config.yaml` →
  `1.26.6-0`, `build.yaml` → `1.26.6`, `README.md` badges → `v1.26.6`.

### Agent's Discretion

- Exact error message text for the credential-missing guard in `run.sh` — format and wording of the `claude login`
  instructions
- Whether to set `restart: unless-stopped` or equivalent in `config.yaml` or leave at HA default
- `build.yaml` base image version tag (e.g., `amd64-base:3.22` vs latest at time of creation)
- `DOCS.md` content structure and configuration reference format

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Upstream Project

- `https://github.com/rynfar/meridian` — upstream Meridian project (read Dockerfile, bin/docker-entrypoint.sh,
  bin/claude-proxy-supervisor.sh for understanding auth flow and runtime invocation)
- Specifically: `bin/docker-entrypoint.sh` — shows symlink logic for `.claude.json` persistence; informs D-05/D-06

### Requirements

- `.planning/REQUIREMENTS.md` §Meridian Add-on — MER-01 through MER-08 are the acceptance criteria for this phase

### Existing Add-on Patterns (read before writing any file)

- `fritz-callmonitor2mqtt/Dockerfile` — reference for multi-stage build, ARG/ENV pattern, label block
- `fritz-callmonitor2mqtt/config.yaml` — reference for config.yaml schema structure, options/schema sections
- `fritz-callmonitor2mqtt/build.yaml` — reference for build.yaml format
- `fritz-callmonitor2mqtt/run.sh` — reference for bashio shebang, config reading, env var export pattern
- `fritz-callmonitor2mqtt/.upstream.yaml` — canonical `.upstream.yaml` structure
- `phone-logger/Dockerfile` — reference for GitHub archive tarball download pattern in Dockerfile

### External Reference

- `https://github.com/zigbee2mqtt/hassio-zigbee2mqtt/blob/master/common/Dockerfile` — reference for multi-stage HA
  add-on Dockerfile with npm/pnpm build stage + HA base runtime stage; node_modules copy pattern

### Tooling

- `scripts/validate-versions.sh` — version validation script; downstream must understand it to verify meridian is
  discovered correctly after the pre-commit `files:` pattern update (D-15)
- `.pre-commit-config.yaml` — must be updated for D-15 (validate-versions files pattern) and D-16 (DL3016 ignore)

### Conventions

- `.planning/codebase/CONVENTIONS.md` — versioning rules, Dockerfile label block, YAML quoting, snake_case config
  options, shell script shebang conventions

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Patterns

- **GitHub tarball fetch pattern** (`phone-logger/Dockerfile`):
  `curl -fsSL "https://github.com/owner/repo/archive/refs/tags/v${VERSION}.tar.gz" | tar xz --strip-components=1` — copy
  directly
- **bashio config read + export** (`fritz-callmonitor2mqtt/run.sh`): `VAR=$(bashio::config 'key'); export VAR` — one
  assign, one export
- **Standard label block** (both Dockerfiles): identical OCI + HA label block at bottom — copy as-is
- **`.upstream.yaml` structure** (`fritz-callmonitor2mqtt/.upstream.yaml`): complete template to copy and adjust fields

### Pre-commit Hook Requiring Update

- `.pre-commit-config.yaml` line: `files: ^(fritz-callmonitor2mqtt|phone-logger)/(config\.yaml|build\.yaml|README\.md)$`
  → must add `|meridian` to this regex (D-15)

### Integration Points

- `repository.yaml` — may need updating if Meridian add-on requires explicit registration (check if HA auto-discovers or
  if this file needs an entry)
- `Makefile` — `validate-addons` target may need to pick up the new add-on directory

</code_context>

<specifics>
## Specific Ideas

- Reference Dockerfile from `zigbee2mqtt/hassio-zigbee2mqtt` confirmed the multi-stage tarball+copy pattern as the
  established approach for Node.js HA add-ons
- User wants `log_level` + `port` as the two configurable options (not zero-config)
- S6 / HA restart handles crash recovery — no upstream supervisor script in the container

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

_Phase: 03-meridian-add-on_ _Context gathered: 2026-04-04_
