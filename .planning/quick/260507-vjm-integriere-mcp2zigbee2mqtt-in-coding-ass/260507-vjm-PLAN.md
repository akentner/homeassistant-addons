---
phase: quick
plan: 260507-vjm
type: execute
wave: 1
depends_on: []
files_modified:
  - coding-assistants/Dockerfile
  - coding-assistants/TOOLS.md
  - coding-assistants/config.yaml
autonomous: true
requirements: []
must_haves:
  truths:
    - "MCP2ZigBee2MQTT is built and installed at /opt/mcp2zigbee2mqtt/dist/index.js in the container"
    - "TOOLS.md documents the tool with config example"
    - "config.yaml schema exposes per-server env list for mcp_servers entries"
  artifacts:
    - path: "coding-assistants/Dockerfile"
      provides: "MCP2ZigBee2MQTT source build step"
      contains: "/opt/mcp2zigbee2mqtt"
    - path: "coding-assistants/TOOLS.md"
      provides: "zigbee2mqtt-mcp-server usage documentation"
    - path: "coding-assistants/config.yaml"
      provides: "env list in mcp_servers schema"
  key_links:
    - from: "coding-assistants/Dockerfile"
      to: "github.com/ichbinder/MCP2ZigBee2MQTT"
      via: "curl source tarball + npm ci + npm run build"
      pattern: "mcp2zigbee2mqtt"
    - from: "coding-assistants/config.yaml mcp_servers schema"
      to: "run.sh env injection logic"
      via: "env list per server"
      pattern: "env"
---

<objective>
Integrate MCP2ZigBee2MQTT into the coding-assistants add-on so that AI assistants (Claude Code,
OpenCode) can control ZigBee devices via the Zigbee2MQTT MCP stdio server.

Purpose: Enable ZigBee device discovery, state monitoring, and control as MCP tools inside the coding-assistants
container.

Output:

- Dockerfile extended with MCP2ZigBee2MQTT source build step
- TOOLS.md updated with tool documentation and registration example
- config.yaml schema extended with per-server env list </objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/home/akentner/Projects/homeassistant-addons/coding-assistants/Dockerfile
@/home/akentner/Projects/homeassistant-addons/coding-assistants/TOOLS.md
@/home/akentner/Projects/homeassistant-addons/coding-assistants/config.yaml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add MCP2ZigBee2MQTT build step to Dockerfile</name>
  <files>coding-assistants/Dockerfile</files>
  <action>
Insert the following RUN block into coding-assistants/Dockerfile, after the fff-mcp section
(after line 61, before the eza block). Place it grouped with the other MCP tools.

nodejs and npm are already installed in the base apk layer — do not reinstall them. The build requires python3, make,
g++ only during the npm ci step (better-sqlite3 native module). Remove them with `apk del .build-mcp2z2m` after the
build to keep image size down.

Block to insert:

```dockerfile
# MCP2ZigBee2MQTT — Zigbee2MQTT MCP server for AI assistants (TypeScript, no releases — build from main)
RUN apk add --no-cache --virtual .build-mcp2z2m python3 make g++ \
    && mkdir -p /opt/mcp2zigbee2mqtt \
    && curl -fsSL "https://github.com/ichbinder/MCP2ZigBee2MQTT/archive/refs/heads/main.tar.gz" \
        | tar xz -C /opt/mcp2zigbee2mqtt --strip-components=1 \
    && cd /opt/mcp2zigbee2mqtt \
    && npm ci \
    && npm run build \
    && npm prune --omit=dev \
    && apk del .build-mcp2z2m
```

Note: python3 is already present in the base layer but the `--virtual` group ensures clean removal of make and g++ (the
other build deps) without touching the global python3.

After insertion, verify the file has no YAML or syntax issues by reviewing the surrounding context — the new block must
not change any existing line. </action> <verify> <automated>grep -n "mcp2zigbee2mqtt"
/home/akentner/Projects/homeassistant-addons/coding-assistants/Dockerfile</automated> </verify> <done> Dockerfile
contains the MCP2ZigBee2MQTT RUN block with source download, npm ci, npm run build, npm prune --omit=dev, and apk del
.build-mcp2z2m. Block is positioned after fff-mcp. </done> </task>

<task type="auto">
  <name>Task 2: Extend config.yaml mcp_servers schema with env list + add zigbee example</name>
  <files>coding-assistants/config.yaml</files>
  <action>
The run.sh already handles per-server env injection (`.env // []` jq path), but the HA schema
does not declare the `env` field. Add it to the mcp_servers schema so HA validates and exposes it
in the UI.

In the `schema.mcp_servers` list entry, add after `url: str?`:

```yaml
env:
  - name: str
    value: str
```

Also add a zigbee2mqtt example entry to `options.mcp_servers` (after the fff entry) so users have a working template:

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

Preserve all existing entries. 2-space YAML indentation, no trailing spaces, LF line endings. </action> <verify>
<automated>grep -n "zigbee2mqtt\|env:"
/home/akentner/Projects/homeassistant-addons/coding-assistants/config.yaml</automated> </verify> <done> config.yaml
schema contains `env: [{name: str, value: str}]` under mcp_servers. options contains zigbee2mqtt example entry with env
list. File passes yamllint. </done> </task>

<task type="auto">
  <name>Task 3: Document MCP2ZigBee2MQTT in TOOLS.md</name>
  <files>coding-assistants/TOOLS.md</files>
  <action>
Extend the "AI & MCP" section in coding-assistants/TOOLS.md. After the `fff-mcp` line, add:

```markdown
- `node /opt/mcp2zigbee2mqtt/dist/index.js` — Zigbee2MQTT MCP server; register as a `stdio` entry in `mcp_servers`
  config with `MQTT_BROKER_URL`, `MQTT_BASE_TOPIC`, and `DB_PATH` env vars
```

Then add a new subsection at the end of the file (before any existing closing content, after the Key Paths table):

````markdown
## MCP Server Registration Examples

### zigbee2mqtt (Zigbee device control)

Add to `mcp_servers` in the add-on options:

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
````

`DB_PATH` must point to a writable location. `/data/` is the add-on persistent storage. Set `MQTT_USERNAME` and
`MQTT_PASSWORD` env entries if your MQTT broker requires authentication.

> Note: MCP2ZigBee2MQTT is built from the upstream `main` branch at Docker build time. There are no versioned releases —
> the installed version reflects the state of the upstream repo at the time the add-on image was built.

```

Ensure line length stays at or below 120 characters per the markdownlint config. Use ATX headers.
  </action>
  <verify>
    <automated>grep -n "zigbee2mqtt\|mcp2zigbee" /home/akentner/Projects/homeassistant-addons/coding-assistants/TOOLS.md</automated>
  </verify>
  <done>
    TOOLS.md contains zigbee2mqtt entry in AI & MCP section and a "MCP Server Registration Examples"
    section at the bottom with full YAML config example. All lines within 120 chars.
  </done>
</task>

</tasks>

<verification>
After all tasks:

1. `grep -n "mcp2zigbee2mqtt" coding-assistants/Dockerfile` — build block present
2. `grep -n "env:" coding-assistants/config.yaml` — env schema present in mcp_servers
3. `grep -c "zigbee2mqtt" coding-assistants/TOOLS.md` — at least 3 matches
4. `make lint` from repo root — pre-commit hooks pass (yamllint, shellcheck, markdownlint, prettier)
</verification>

<success_criteria>
- Dockerfile builds without error (MCP2ZigBee2MQTT source build completes, binary at /opt/mcp2zigbee2mqtt/dist/index.js)
- config.yaml schema declares env list under mcp_servers, validated by make validate-addons
- TOOLS.md documents the tool with a complete registration example
- make lint passes (YAML, markdown, shell linting all green)
</success_criteria>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Docker build → GitHub (ichbinder/MCP2ZigBee2MQTT) | Untrusted source tarball fetched over HTTPS at build time |
| MCP stdio server → MQTT broker | MQTT credentials passed as env vars to subprocess |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-z2m-01 | Tampering | Dockerfile curl from main branch | accept | No releases exist; HTTPS fetch mitigates MITM. Document in TOOLS.md that build tracks main. |
| T-z2m-02 | Information Disclosure | MQTT_PASSWORD in mcp_servers env | accept | Stored in HA options (encrypted at rest by HA supervisor). No plaintext on disk. |
| T-z2m-03 | Elevation of Privilege | npm ci native build (better-sqlite3) | accept | Build runs inside Docker layer; apk del removes build tools after compilation. |
</threat_model>

<output>
After completion, create `.planning/quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass/260507-vjm-SUMMARY.md`
</output>
```
