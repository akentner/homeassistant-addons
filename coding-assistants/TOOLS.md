# Coding Assistants Container — Available Tools

This is a Home Assistant coding assistant container. The working directory is `/homeassistant` (HA configuration).
Persistent storage is at `/data`.

## Terminal & Navigation

- `tmux` — terminal multiplexer; session `main`, prefix `Ctrl-a`
- `zoxide` — frecency-based smart `cd`; use `z <partial>` instead of `cd`
- `yazi` / `ya` — terminal file manager
- `direnv` — auto-loads `.envrc` per directory

## Code & Git

- `git`, `lazygit`, `tig` — git; lazygit is the TUI, tig is log/blame viewer
- `delta` — syntax-highlighted diff pager (active as git pager)
- `difft` — structural diff tool (difftastic); use `difft <file1> <file2>`
- `gh` — GitHub CLI
- `git-submodule-changes <path>` — git diff stats for a repo or submodule as JSON
- `generate-commit-prompt` — generate an AI prompt for a commit message from staged changes
- `git-commit-with-ai` — generate commit message via HA Conversation Agent, then commit and push

## Search & Inspection

- `rg` (ripgrep), `fd`, `fzf` — fast file and content search
- `bat` — syntax-highlighted `cat` replacement
- `eza` — modern `ls` replacement
- `fx` — interactive JSON viewer/processor
- `btop` — resource monitor
- `ncdu` — interactive disk usage navigator
- `atuin` — shell history with TUI search (`Ctrl-r`)

## Languages & Runtimes

- `node`, `npm`, `bun` — JavaScript / TypeScript
- `python3`, `uv`, `uvx` — Python; prefer `uv` over pip
  - **Shebang:** `#!/usr/bin/python3` (kein `#!/usr/bin/env -S` — BusyBox `env` unterstützt `-S` nicht)
  - **Runtime-Deps:** `pip install --break-system-packages <pkg>`; vorinstalliert: `pyyaml`, `python-dotenv`,
    `paho-mqtt`, `httpie`, `websockets`
- `task` — Taskfile runner (`task <target>`)
- `make` — Makefile runner

## Home Assistant

- `ha` — HA supervisor CLI (uses `$SUPERVISOR_TOKEN`, injected automatically)
- `ha-api` — REST API tool; requires `$HA_URL` + `$HA_TOKEN`
- `ha-ws` — WebSocket API tool; requires `$HA_URL` + `$HA_TOKEN`
- `ha-check-logs [lines] [show-warnings]` — fetch and summarize HA core logs; e.g. `ha-check-logs 200 true`
- `ha-check-repairs` — list open HA repairs/issues
- `lovelace-sync <dashboard>` — push local `.storage/lovelace.<dashboard>` to HA via WebSocket without restart
- `sqlite3` — query HA database: `sqlite3 /homeassistant/home-assistant_v2.db`

## AI & MCP

- `claude` — Claude Code CLI
- `opencode` — OpenCode AI CLI
- `gh copilot` — GitHub Copilot CLI (`gh copilot suggest`, `gh copilot explain`)
- `fff-mcp` — fast file search MCP server (register in Claude Code / OpenCode config)
- `node /opt/mcp2zigbee2mqtt/dist/index.js` — Zigbee2MQTT MCP server; register as a `stdio` entry in `mcp_servers`
  config with `MQTT_BROKER_URL`, `MQTT_BASE_TOPIC`, and `DB_PATH` env vars

## Utilities

- `http` / `https` — HTTPie HTTP client
- `jq`, `yq` — JSON / YAML processing
- `tldr` — simplified man pages (`tldr <command>`)
- `shellcheck` — shell script linter
- `curl`, `wget` — HTTP download tools
- `mosquitto_pub` / `mosquitto_sub` — MQTT CLI clients (via `mosquitto-client`); Python-Alternative: `paho-mqtt`
- **apk install:** `apk update` vor jedem `apk add` ausführen — Index ist im laufenden Container nicht automatisch
  aktuell

## Key Paths

| Path                                  | Contents                                      |
| ------------------------------------- | --------------------------------------------- |
| `/homeassistant`                      | HA configuration directory (live, read-write) |
| `/homeassistant/home-assistant_v2.db` | HA SQLite database                            |
| `/data`                               | Persistent addon storage (survives restarts)  |
| `/share`                              | HA shared storage                             |
| `/media`                              | HA media storage                              |

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

`DB_PATH` must point to a writable location. `/data/` is the add-on persistent storage. Set `MQTT_USERNAME` and
`MQTT_PASSWORD` env entries if your MQTT broker requires authentication.

> Note: MCP2ZigBee2MQTT is built from the upstream `main` branch at Docker build time. There are no versioned releases —
> the installed version reflects the state of the upstream repo at the time the add-on image was built.
