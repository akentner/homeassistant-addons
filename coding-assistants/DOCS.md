# Coding Assistants — Configuration

## Options

### `log_level`

Log verbosity: `debug`, `info` (default), `warning`, `error`.

### `authorized_keys`

List of SSH public keys allowed to log in. One key per list entry.

```yaml
authorized_keys:
  - "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user@host"
  - "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user2@host"
```

At least one key is required to use SSH. The web terminal (ingress) is always available.

### `terminal_font_size`

Font size for the web terminal. Default: `16`.

### `terminal_theme`

Color theme for the web terminal. Options:

- `default` — browser default
- `solarized-dark`
- `solarized-light`
- `monokai`
- `tomorrow-night`
- `zenburn`

### `env_vars`

Environment variables injected into every session (SSH and web terminal). Use this for API keys and tool configuration.

```yaml
env_vars:
  - name: ANTHROPIC_API_KEY
    value: sk-ant-...
  - name: GITHUB_TOKEN
    value: ghp_...
  - name: OPENAI_API_KEY
    value: sk-...
```

### `zigbee2mqtt`

Dedicated integration for the [zigbee2mqtt MCP server](https://github.com/akentner/mcp2zigbee2mqtt). When enabled, the
MCP server is automatically registered in Claude Code and OpenCode — no manual `mcp_servers` entry required. MQTT
connection variables (`MQTT_BROKER_URL`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_BASE_TOPIC`) are also injected into
every session.

```yaml
zigbee2mqtt:
  enabled: true
  mqtt_broker_url: "mqtt://homeassistant:1883"
  mqtt_username: ""
  mqtt_password: ""
  mqtt_base_topic: "zigbee2mqtt"
  db_path: "/data/zigbee2mqtt-mcp.db"
  log_level: "info"
```

| Option            | Type     | Default                     | Description                                       |
| ----------------- | -------- | --------------------------- | ------------------------------------------------- |
| `enabled`         | bool     | `false`                     | Enable zigbee2mqtt MCP auto-registration          |
| `mqtt_broker_url` | string   | `mqtt://homeassistant:1883` | MQTT broker URL                                   |
| `mqtt_username`   | string   | `""`                        | MQTT username (leave empty if not required)       |
| `mqtt_password`   | password | `""`                        | MQTT password (masked in UI)                      |
| `mqtt_base_topic` | string   | `zigbee2mqtt`               | MQTT base topic used by your zigbee2mqtt instance |
| `db_path`         | string   | `/data/zigbee2mqtt-mcp.db`  | Path for the MCP server's SQLite database         |
| `log_level`       | string   | `info`                      | Log level: `debug`, `info`, `warning`, `error`    |

### `mcp_servers`

Manual MCP server registrations. Each entry is merged into Claude Code (`~/.claude.json`) and OpenCode (`opencode.json`)
on startup. Use this for MCP servers that do not have a dedicated config block above.

```yaml
mcp_servers:
  - name: my-server
    type: stdio
    command: /usr/local/bin/my-mcp-server
  - name: remote-server
    type: http
    url: http://192.168.1.10:9000/token
  - name: server-with-env
    type: stdio
    command: node
    args:
      - /opt/my-mcp/index.js
    env:
      - name: API_KEY
        value: secret
```

| Field     | Required   | Description                                            |
| --------- | ---------- | ------------------------------------------------------ |
| `name`    | yes        | Unique server name (used as key in config files)       |
| `type`    | yes        | `stdio` for local process, `http` for remote endpoint  |
| `command` | stdio only | Executable to run                                      |
| `url`     | http only  | Full URL including auth token if required              |
| `env`     | no         | List of `{name, value}` env vars passed to the process |

## SSH Access

Connect on the port mapped in the add-on's network settings (default: 2222):

```bash
ssh root@<ha-host> -p 2222
```

SSH host keys are generated on first start and stored in `/data/ssh` — they persist across restarts.

The SSH session **automatically attaches to the shared tmux session** (`main`) on login — no manual attach needed. Both
the web terminal and SSH sessions share the same tmux session, so you see the same panes in both.

If the auto-attach is bypassed (e.g. non-interactive use) or you detach and want to re-attach manually:

```bash
tmux attach -t main
# or, to create the session if it doesn't exist yet:
tmux new-session -A -s main -c /homeassistant
```

## Installed Tools

| Tool           | Purpose                |
| -------------- | ---------------------- |
| `claude`       | Claude Code CLI        |
| `opencode`     | OpenCode AI agent      |
| `copilot`      | GitHub Copilot CLI     |
| `git`, `gh`    | Git + GitHub CLI       |
| `jq`, `yq`     | JSON / YAML query      |
| `rg`           | ripgrep — fast search  |
| `fd`           | fast file finder       |
| `fzf`          | fuzzy finder           |
| `bat`          | syntax-highlighted cat |
| `lazygit`      | TUI git client         |
| `bun`          | JavaScript runtime     |
| `uv`, `uvx`    | Python package manager |
| `task`         | Taskfile runner        |
| `httpie`       | HTTP client            |
| `shellcheck`   | Shell script linter    |
| `make`         | Build tool             |
| `tmux`         | Terminal multiplexer   |
| `curl`, `wget` | HTTP utilities         |

## Upgrading `claude` and `opencode`

Both coding assistants can be upgraded inside a running container — no add-on rebuild required.

```bash
opencode upgrade        # downloads the latest release to ~/.opencode/bin
claude update           # reruns npm install -g @anthropic-ai/claude-code@latest
```

The opencode binary lives under `/root/.opencode/bin`, which the add-on symlinks into the persistent `/data` volume.
Upgrades therefore survive container restarts and rebuilds. The bundled version in the image is only used as the seed on
the very first start of an empty `/data` volume; delete `/data/opencode/bin/opencode` to fall back to it.

## tmux

The web terminal opens in a persistent tmux session (`main`). Reconnecting (SSH or web) reattaches to the same session.

Key bindings (prefix: `Ctrl-a`):

| Keys        | Action                  |
| ----------- | ----------------------- |
| `Ctrl-a \|` | Split pane horizontally |
| `Ctrl-a -`  | Split pane vertically   |
| `Ctrl-a c`  | New window              |
| `Ctrl-a r`  | Reload tmux config      |
| `Ctrl-a [`  | Enter scroll/copy mode  |
