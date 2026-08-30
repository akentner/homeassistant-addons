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
MCP server is automatically registered in OpenCode — no manual `mcp_servers` entry required. MQTT connection variables
(`MQTT_BROKER_URL`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_BASE_TOPIC`) are also injected into every session.

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

### `mycli`

Configures one or more MariaDB/MySQL connections for the bundled `mycli` client and `mcp-server-mysql` MCP server. When
enabled, each connection becomes a DSN alias in `/data/.myclirc` (chmod 600) and an auto-registered MCP server
(`mariadb-<name>`) for OpenCode. The active default connection is exposed as `MYCLI_HOST` / `MYCLI_PORT` / `MYCLI_USER`
/ `MYCLI_PASSWORD` / `MYCLI_DATABASE` env vars in every shell.

Connection names must match `[a-zA-Z0-9_-]+` and must be unique. Names are case-insensitive DSN aliases — pass them to
mycli via `mycli -D <name>`. Without an explicit `default`, the first entry is used.

```yaml
mycli:
  enabled: true
  default: homeassistant # optional; defaults to the first entry
  connections:
    - name: homeassistant
      host: core-mariadb
      port: 3306
      username: hass
      password: !secret mariadb_pw
      database: homeassistant
    - name: analytics
      host: 10.0.1.50
      port: 3306
      username: readonly
      password: !secret analytics_pw
      database: metrics
```

| Option        | Type     | Default     | Description                                                |
| ------------- | -------- | ----------- | ---------------------------------------------------------- |
| `enabled`     | bool     | `false`     | Enable the mycli / MariaDB-MCP integration                 |
| `default`     | string   | first entry | DSN alias used by bare `mycli` and by exported env vars    |
| `connections` | list     | `[]`        | Connection profiles                                        |
| `name`        | string   | —           | Connection name (DSN alias + MCP suffix), `[a-zA-Z0-9_-]+` |
| `host`        | string   | —           | MariaDB/MySQL hostname or IP                               |
| `port`        | int      | `3306`      | TCP port                                                   |
| `username`    | string   | —           | Database user                                              |
| `password`    | password | `""`        | Database password (masked in UI)                           |
| `database`    | string   | `""`        | Default database/schema                                    |

### `mcp_servers`

Manual MCP server registrations. Each entry is merged into OpenCode's `opencode.json` on startup. Use this for MCP
servers that do not have a dedicated config block above.

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
| `mycli`        | MariaDB/MySQL client   |
| `sqlite3`      | SQLite CLI for HA      |

## Upgrading `opencode`

`opencode` can be upgraded inside a running container — no add-on rebuild required.

```bash
opencode upgrade        # downloads the latest release to ~/.opencode/bin
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

## mycli

When at least one connection is configured in the `mycli:` option, the bundled `mycli` client connects on first run. The
default connection is set via `mycli.default` (or the first entry) and is also exposed in the shell as `MYCLI_HOST` /
`MYCLI_PORT` / `MYCLI_USER` / `MYCLI_PASSWORD` / `MYCLI_DATABASE`.

```bash
mycli                       # connect to the default connection
mycli -D analytics          # switch to the 'analytics' alias from /data/.myclirc
mycli schema                # show the schema of the default database
mycli -h db.example.com     # ad-hoc override (any standard mysql CLI flag works)
```

All connections are auto-registered as a `mariadb-<name>` MCP server, so OpenCode can run SQL against them without
leaving the assistant:

> "Use the `mariadb-homeassistant` MCP tools to list the last 24 hours of `sensor.*` state changes."

The connection credentials live in `/data/.myclirc` (chmod 600) and the per-connection wrapper scripts at
`/usr/local/bin/mariadb-<name>` (chmod 700). Both are recreated on every container start from the current add-on
configuration, so editing `mycli:` in the add-on options and restarting is enough to roll or rotate credentials.
