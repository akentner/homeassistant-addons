# Quick Task Research: Integrate MCP2ZigBee2MQTT into coding-assistants

**Researched:** 2026-05-07 **Domain:** HA add-on integration — Node.js MCP server (TypeScript source, no releases)
**Confidence:** HIGH (all key facts verified from source)

---

## What Is MCP2ZigBee2MQTT?

[VERIFIED: github.com/ichbinder/MCP2ZigBee2MQTT]

An MCP (Model Context Protocol) server that bridges AI assistants (Claude, etc.) to ZigBee smart home devices via
Zigbee2MQTT. It exposes ZigBee device discovery, state monitoring, and command control as MCP tools over stdio
transport.

- **Runtime:** Node.js 20+ / TypeScript (compiled to `dist/index.js`)
- **npm package name:** `zigbee2mqtt-mcp-server` (v1.0.0)
- **Entry point after build:** `node dist/index.js`
- **MCP transport:** stdio (not HTTP — runs as a subprocess, not a server)
- **GitHub releases:** None published. No tags. Source-only repo.
- **Docker Hub images:** None published.

### Configuration (env vars)

| Env Var           | Default       | Purpose                                                      |
| ----------------- | ------------- | ------------------------------------------------------------ | ----- | ---- | ---- | ------ |
| `MQTT_BROKER_URL` | —             | MQTT broker connection string (e.g. `mqtt://localhost:1883`) |
| `MQTT_USERNAME`   | —             | MQTT auth username (optional)                                |
| `MQTT_PASSWORD`   | —             | MQTT auth password (optional)                                |
| `MQTT_BASE_TOPIC` | `zigbee2mqtt` | Root MQTT topic for Zigbee2MQTT messages                     |
| `DB_PATH`         | —             | SQLite database file path                                    |
| `LOG_LEVEL`       | `info`        | Verbosity: `silent                                           | error | warn | info | debug` |

### Key Dependencies (native build required)

`better-sqlite3` requires native compilation (`python3 make g++` at build time — same as upstream Dockerfile).

---

## Integration Approach

### The Challenge: No Releases

This repo has no GitHub releases and no published npm package. Unlike other tools in the Dockerfile (ttyd, eza, etc.
which download release artifacts), MCP2ZigBee2MQTT must be built from source at Docker build time.

**Pattern to follow:** Similar to `phone-logger` — download source tarball from a git ref and build in-container.

### Where to Integrate: coding-assistants vs. standalone add-on

Two options:

**Option A — Install inside coding-assistants Dockerfile (recommended for this task)**

MCP2ZigBee2MQTT is intended to be registered as an MCP server in Claude/OpenCode. The coding-assistants add-on already
handles MCP server registration. Install the binary into the container, then users register it via `mcp_servers` config
as a `stdio` entry pointing to `node /opt/mcp2zigbee2mqtt/dist/index.js`.

- Aligns with existing pattern: fff-mcp is already installed as a binary in the Dockerfile
- No new add-on directory needed
- Users configure MQTT credentials via `env_vars` in coding-assistants config

**Option B — New standalone add-on**

A separate `mcp2zigbee2mqtt/` add-on with its own lifecycle, requiring the full 4-file pattern plus `.upstream.yaml`.
Overkill unless the tool needs independent start/stop or persistent daemon behavior. MCP stdio servers don't run as
daemons — they're spawned on-demand by the client.

**Recommendation: Option A.** Install into coding-assistants Dockerfile as a build step (like fff-mcp), document in
TOOLS.md, and let users wire up via `mcp_servers` + `env_vars` config.

### Dockerfile Build Step (source build, no release)

```dockerfile
# MCP2ZigBee2MQTT — Zigbee2MQTT MCP server (TypeScript, no releases — build from source)
RUN apk add --no-cache --virtual .build-mcp2z2m python3 make g++ \
    && mkdir -p /opt/mcp2zigbee2mqtt \
    && curl -fsSL "https://github.com/ichbinder/MCP2ZigBee2MQTT/archive/refs/heads/main.tar.gz" \
        | tar xz -C /opt/mcp2zigbee2mqtt --strip-components=1 \
    && cd /opt/mcp2zigbee2mqtt \
    && npm ci \
    && npm run build \
    && npm prune --production \
    && apk del .build-mcp2z2m
```

Note: Downloads from `main` branch (no tags/releases). The `apk del .build-mcp2z2m` removes build-only packages
(python3, make, g++) to keep image size down. `npm prune --production` removes devDependencies.

### MCP Registration Example (in HA add-on options)

Users add to `mcp_servers`:

```yaml
- name: zigbee2mqtt
  type: stdio
  command: node /opt/mcp2zigbee2mqtt/dist/index.js
  env:
    - name: MQTT_BROKER_URL
      value: mqtt://homeassistant:1883
    - name: MQTT_BASE_TOPIC
      value: zigbee2mqtt
    - name: DB_PATH
      value: /data/zigbee2mqtt-mcp.db
```

Or simpler: set `MQTT_BROKER_URL` etc. in `env_vars` globally, then just register the command.

---

## Pitfalls

### No Release Tagging — Build is Pinned to `main`

No version control: build always pulls `main`. If upstream breaks, the Docker build breaks. The `.upstream.yaml`
auto-update system cannot track this repo (requires tags matching `v*`). Either:

- Pin to a specific commit SHA in the curl URL (stable but manual)
- Accept `main`-tracking (simpler, fragile)
- Fork and tag releases yourself

Since coding-assistants has no `.upstream.yaml` (it's internally versioned), the `main`-tracking approach is acceptable
for now, but document it.

### Native Build Dependencies (better-sqlite3)

`better-sqlite3` compiles a native `.node` module. Alpine musl vs. glibc is handled correctly by `npm ci` inside Alpine
(same OS), but `apk add python3 make g++` must be present during `npm ci`. These are build-time only and can be removed
after with `apk del .build-mcp2z2m`.

### `nodejs` Already in Dockerfile — No Version Conflict

coding-assistants Dockerfile already installs `nodejs npm` via apk. The MCP2ZigBee2MQTT build will use the same node
binary. No conflict.

### MCP Schema: `env` Field on `mcp_servers`

The current `coding-assistants/config.yaml` schema for `mcp_servers` does NOT include an `env` list per server:

```yaml
mcp_servers:
  - name: str
    type: list(stdio|http)
    command: str?
    url: str?
```

The `run.sh` already handles env injection for stdio MCP servers (`env: ((.env // []) | ...)` in the jq transform), so
the runtime logic exists. But the HA options schema doesn't declare it yet. If per-server env support is wanted, the
schema needs extending. Otherwise, users set MQTT creds via the top-level `env_vars` list.

Check: `run.sh` line 78 — `env: ((.env // []) | map({ (.name): .value }) | add // {})` — the runtime handles `.env` per
server, but `config.yaml` schema doesn't expose it. **Minor schema gap** — not a blocker.

---

## Required Changes

| File                            | Change                                                                     |
| ------------------------------- | -------------------------------------------------------------------------- |
| `coding-assistants/Dockerfile`  | Add MCP2ZigBee2MQTT source build step                                      |
| `coding-assistants/TOOLS.md`    | Document the new MCP tool, config instructions                             |
| `coding-assistants/config.yaml` | Optionally add `env` list to `mcp_servers` schema (enables per-server env) |

No new add-on directory. No `build.yaml` or `.upstream.yaml` changes. No version file changes (tool is baked in at build
time, not version-tracked separately).

---

## Assumptions Log

| #   | Claim                                                                                    | Risk if Wrong                                                                                   |
| --- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| A1  | No Docker Hub image or npm package published for ichbinder/MCP2ZigBee2MQTT — source-only | If a package is later published, simpler install via `npx` or `npm install -g` becomes possible |
| A2  | `main` branch is stable enough for production use                                        | Upstream breaking change could break Docker build                                               |

---

## Sources

- [VERIFIED: github.com/ichbinder/MCP2ZigBee2MQTT] — repo README, package.json, Dockerfile
- [VERIFIED: github.com/ichbinder/MCP2ZigBee2MQTT/releases] — empty, confirmed no releases
- [VERIFIED: coding-assistants/Dockerfile] — existing build patterns
- [VERIFIED: coding-assistants/run.sh] — MCP registration logic (lines 66-108)
- [VERIFIED: coding-assistants/config.yaml] — current options schema
