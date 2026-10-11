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

Every entry is also written to the shell profile files (`/etc/profile.d/00-coding-assistants.sh` and the fish `conf.d`
file in `/data/.config/fish`). For Claude Code credentials use the dedicated password options below instead: they are
exported into the process environment only and never reach a file.

### `claude_code_oauth_token`

Optional password. A long-lived Claude Code OAuth token (for example created with `claude setup-token` on a machine with
a browser). When set, it is exported as `CLAUDE_CODE_OAUTH_TOKEN` into the process environment of the processes the
add-on starts: the web terminal and the herdr server, and with it every herdr pane (SSH logins attach to those panes).
Claude Code then runs without an interactive login. A plain SSH shell obtained with the
[escape hatch](#plain-shell-instead-of-herdr) is not started by the add-on and should not be expected to have it.

The value is never written to the profile files, to `/data` or to the add-on log (the log only states that the variable
was exported). Leave the option empty to log in interactively with `claude login` instead, see
[Claude Code](#claude-code).

### `anthropic_api_key`

Optional password. An Anthropic API key, exported as `ANTHROPIC_API_KEY` into the same process environment as above
(and, like the OAuth token, never written to a file or the log).

Precedence and interplay:

- When both `anthropic_api_key` and `claude_code_oauth_token` are set, Claude Code uses the API key; the first
  interactive start asks once to approve it.
- An `env_vars` entry with the same name (`ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`) is applied afterwards and
  overrides the option. Such an entry is also written to the profile files, see `env_vars`.
- An empty option exports nothing, so Claude Code falls back to the credentials of `claude login`.

### `herdr_web_password`

Optional password. The login password of the herdr web UI at `/services/`, see [Web UI](#web-ui-services). It is handed
to the plugin's own `set-password` command over standard input on every start; only an argon2id hash is stored
(`auth.json`, mode 600, in the plugin's config directory below `/data/.config/herdr/plugins/config/`). The plain value
appears in no argument, file or log line.

- The plugin requires at least 6 characters, a symbol, a number and an uppercase letter. A value that does not meet
  these rules is rejected: the add-on log then shows a warning naming the unmet rule (never the value), the login stays
  as it was and everything else starts normally.
- The option is applied on every start. Changing it changes the password; removing it does **not** delete an existing
  hash, so the old password keeps working until you delete `auth.json` in the directory named above and restart the
  add-on (the login then answers 503 again).
- Without a password the web UI loads but every login attempt is refused with HTTP 503.

### `zigbee2mqtt`

Dedicated integration for the [zigbee2mqtt MCP server](https://github.com/akentner/mcp2zigbee2mqtt). When enabled, the
MCP server is automatically registered in OpenCode and Claude Code — no manual `mcp_servers` entry required. MQTT
connection variables (`MQTT_BROKER_URL`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_BASE_TOPIC`) are also injected into
every session. The Claude Code entry carries these values in its own `env` object, so it does not depend on the shell
environment.

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
(`mariadb-<name>`) for OpenCode and Claude Code. The active default connection is exposed as `MYCLI_HOST` / `MYCLI_PORT`
/ `MYCLI_USER` / `MYCLI_PASSWORD` / `MYCLI_DATABASE` env vars in every shell.

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

Manual MCP server registrations. Each entry is merged on startup into the configuration of both assistants: OpenCode
(`opencode.json`) and Claude Code (user scope, `.mcpServers` in `/data/.claude.json`). Use this for MCP servers that do
not have a dedicated config block above.

Entries of type `http` are registered for Claude Code only; the OpenCode registration handles `stdio` entries. For
Claude Code an `http` entry becomes `{type, url}`, any other entry a `stdio` server with `command`, `args` and `env`.

**Existing entries win.** The add-on only adds missing servers; an entry that already exists in `/data/.claude.json`
(from an earlier start or edited by you) is never overwritten. Your edits therefore survive restarts, but a changed
add-on option (for example a rotated token in an `http` URL) does not reach an existing Claude Code entry. To refresh an
entry, remove it and restart the add-on:

```bash
claude mcp remove <name> --scope user
```

(or delete the key from `.mcpServers` in `/data/.claude.json`). The add-on re-creates it from the current options on the
next start. OpenCode entries are merged the same way, see `opencode.json` in `/data/.config/opencode/`.

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

An interactive SSH login **automatically attaches to the shared herdr session** — no manual attach needed. The web
terminal and every SSH login attach to the same session, so you see the same workspaces, tabs and panes in all of them,
see [herdr](#herdr).

If you detached (`prefix+q`, default prefix `ctrl+b`) and want to attach again without reconnecting:

```bash
coding-assistants-attach
```

### Plain shell instead of herdr

The auto-attach only applies to interactive logins. `ssh root@<ha-host> -p 2222 <command>`, `scp` and `sftp` are not
affected. To get a plain shell for an interactive login (for example when herdr itself is broken), use one of:

```bash
ssh -t root@<ha-host> -p 2222 'CODING_ASSISTANTS_NO_ATTACH=1 bash -l'
ssh -t root@<ha-host> -p 2222 bash --noprofile
```

`CODING_ASSISTANTS_NO_ATTACH` is also set by the wrapper itself when it falls back to a plain `fish` shell because no
herdr server answers (the add-on log then explains why). Inside a herdr pane the variable `HERDR_ENV` is set, which
keeps nested shells from attaching again.

## Installed Tools

| Tool           | Purpose                |
| -------------- | ---------------------- |
| `claude`       | Claude Code            |
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
| `herdr`        | Terminal workspaces    |
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

## Claude Code

Claude Code (`claude`) is installed with Anthropic's native installer. The add-on sets no Claude settings and no
permission, model or hook defaults: Claude Code runs with its own defaults, and everything you configure in
`~/.claude/settings.json` is yours.

### Login

Either set `claude_code_oauth_token` / `anthropic_api_key` (see [Options](#options)) or log in interactively:

```bash
claude login
```

The credentials of an interactive login are stored in `/data/.claude/.credentials.json` and survive restarts.

### Updates

Claude Code updates itself (background updates and `claude update`). New versions are written to
`/data/.local/share/claude/versions`, and the launcher `~/.local/bin/claude` is re-created on every start so that it
points into that directory. The image only carries a seed of the version that was current at build time
(`/opt/claude-initial`):

- At every start the newest of "seed" and "persisted" wins. A persisted update is therefore kept across add-on updates
  and rebuilds; the seed is only copied in when it is strictly newer than everything persisted.
- The directory `.local/share/claude` is excluded from backups. After a restore the seed of the installed image is used
  until Claude updates itself again.

### Persisted state

| Path                        | Purpose                                                              |
| --------------------------- | -------------------------------------------------------------------- |
| `/data/.claude`             | `~/.claude` (mode 700): credentials, settings, projects, `CLAUDE.md` |
| `/data/.claude.json`        | `~/.claude.json` (mode 600): account state and MCP servers           |
| `/data/.local/share/claude` | installed Claude Code versions                                       |

`~/.claude` and `~/.claude.json` are symlinks into `/data`. Contents of the former layout (`/data/claude/.claude` and
`/data/claude/.claude.json`) are copied once on the first start, when the new paths do not exist yet; the old files are
never deleted.

### Tool context in `CLAUDE.md`

The tool description of the add-on (the same text OpenCode receives as instructions) is injected into
`/data/.claude/CLAUDE.md` between the markers `<!-- coding-assistants:begin -->` and `<!-- coding-assistants:end -->`.
The block is rewritten on every start; any text you write outside the markers is preserved.

### MCP servers

Claude Code receives the same MCP servers as OpenCode: the `mcp_servers` option, the `zigbee2mqtt` integration and the
`mariadb-<name>` servers of `mycli`. They are registered at user scope in `/data/.claude.json`. Existing entries are
never overwritten, which means your edits survive but old add-on values stay frozen; how to refresh an entry is
described under [`mcp_servers`](#mcp_servers). A `/data/.claude.json` that cannot be parsed is left untouched and the
add-on log shows a warning.

## herdr

[herdr](https://github.com/herdrdev/herdr) is the terminal workspace manager (workspaces, tabs, panes, mouse support).
The web terminal and every interactive SSH login attach to **one shared session**, so what you start in one client is
visible in all others and keeps running after you disconnect.

- The add-on starts the herdr server itself. The server and therefore every pane inherits the add-on environment: `PATH`
  (including `~/.local/bin`), `HA_URL`, `HA_TOKEN`, `SUPERVISOR_TOKEN` and the Claude variables from the options above.
  Panes run `fish`.
- Workspace `main` (working directory `/homeassistant`) exists before the first client attaches and is re-created when
  the session was emptied.
- The add-on ships **no herdr configuration and no custom key bindings**: herdr runs with its defaults. If you want to
  change something, create `/data/.config/herdr/config.toml` yourself; it persists.
- Restarting the add-on ends all programs running in the panes; herdr restores the saved layout (workspaces, tabs, panes
  and their directories) with fresh shells. Running processes and agent conversations are not carried over.

### First start

The first attach shows herdr's own onboarding dialog until you dismiss it. The add-on does not suppress or answer it.
herdr is mouse-first: panes, tabs and workspaces can be clicked, split borders dragged and menus opened with a right
click, so none of the keys below is required. The full documentation is at <https://herdr.dev/docs/>.

### Default keys

The prefix is `ctrl+b`.

| Keys             | Action                                           |
| ---------------- | ------------------------------------------------ |
| `prefix+q`       | Detach (the session and all agents keep running) |
| `prefix+?`       | Show help with all key bindings                  |
| `prefix+c`       | New tab                                          |
| `prefix+v`       | Split the pane to the right                      |
| `prefix+minus`   | Split the pane downwards                         |
| `prefix+h/j/k/l` | Move between panes                               |
| `prefix+w`       | Workspace navigation                             |
| `prefix+[`       | Copy mode                                        |

### Server respawn

If the herdr server stops or crashes, `run.sh` starts it again after about 3 seconds. `herdr server stop` therefore acts
as a restart of the server. After a clean stop herdr restores the saved layout with fresh shells; after a crash nothing
may have been saved, the session starts empty and the next client re-creates workspace `main`. While no server answers,
clients fall back to a plain `fish` shell instead of a dead connection.

### Updating herdr

`herdr update` replaces the binary only for the running container; the next start of a fresh container is back at the
bundled version. The bundled version is pinned in the image (`HERDR_VERSION` and the checksums in the `Dockerfile`,
mirrored in `build.yaml`); change the pin and rebuild to update it permanently.

## herdr plugins

Three herdr plugins are part of the image. They are checked out at pinned commits below `/opt/herdr-plugins/` (the
directory name is the repository name), and linked into herdr at every start (`herdr plugin list` shows them). They are
**linked but not configured**: the add-on never runs a plugin setup action and writes neither a herdr `config.toml` nor
a Claude `settings.json`. Everything below is an opt-in you run yourself.

| Plugin (id)                               | Pinned commit (source repository)                                                   |
| ----------------------------------------- | ----------------------------------------------------------------------------------- |
| subagent-watch (`subagent.watch`)         | `c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8` (`silencechung/herdr-subagent-watch`)    |
| claude-limits (`martin.claude-limits`)    | `9c0c9a1931ac91f9d865031e2dc58d66a7d1b594` (`martin-saldinger/herdr-claude-limits`) |
| web-service (`imontes.herdr-web-service`) | `e9082b3fb969064e89153a8c6b2170366982f7f9` (`i-montes/herdr-web-service`)           |

All plugins run as root inside the add-on, with the add-on environment (including `HA_TOKEN` and `SUPERVISOR_TOKEN`) of
the herdr server. The repositories have no tags, hence the commit pins. claude-limits carries no licence file upstream.

### subagent-watch

Shows what the sub-agents of a Claude Code session are doing, in a popup. Run it from the pane in question; it opens the
viewer for that pane's session:

```bash
herdr plugin action invoke subagent.watch.open
```

The optional wiring is the plugin's `setup` action. It **edits your own files**: it adds `SubagentStart` /
`SubagentStop` hooks to `~/.claude/settings.json` (that is `/data/.claude/settings.json`), and to herdr's `config.toml`
a `prefix+.` key binding for the popup plus sidebar rows. Before it writes, it makes a backup named
`<file name>.subagent-watch.bak` next to each file, validates the herdr config and restores it when the check fails. The
add-on never runs it; if you want it:

```bash
herdr plugin action invoke subagent.watch.setup    # opt in
herdr plugin action invoke subagent.watch.remove   # undo
```

The result of the setup is shown as a herdr notification; the details are in
`herdr plugin log list --plugin subagent.watch`.

### claude-limits

Shows the plan usage limits of Claude Code. A background poller (started by the plugin when herdr starts) reads the
OAuth access token from `/data/.claude/.credentials.json` and asks `api.anthropic.com` (and nothing else) for the usage
every few minutes.

**Caveat:** this works only with the credentials file of an interactive `claude login`. With `claude_code_oauth_token`
or `anthropic_api_key` there is no credentials file; the poller then only logs that no credentials were found.

The popup works without any configuration:

```bash
herdr plugin action invoke martin.claude-limits.show
```

To show the usage in the tab bar and bind it to a key, add this to `/data/.config/herdr/config.toml` and reload:

```toml
[ui]
tab_bar_right = [
  { type = "command", command = "/opt/herdr-plugins/herdr-claude-limits/bin/status.sh", interval_seconds = 10 },
]

[[keys.command]]
key = "prefix+u"
type = "plugin_action"
command = "martin.claude-limits.show"
```

```bash
herdr server reload-config
```

### web-service

Provides the [Web UI](#web-ui-services). Its actions are `imontes.herdr-web-service.status`, `.start` and `.stop`, for
example:

```bash
herdr plugin action invoke imontes.herdr-web-service.status
```

Do not run the plugin's own `setup` action: its wizard is built for public servers (tunnels, service units, installers
downloaded from the internet, a Claude status line) and is not needed here, because the add-on sets the password through
the `herdr_web_password` option and serves the UI through HA ingress.

### Changing a pin

Each pin is an `ARG HERDR_*_REF` in the `Dockerfile`, mirrored in `build.yaml` (the check
`internal/verify-coding-assistants.sh drift` fails when they differ). The web-service build also applies
`patches/herdr-web-service-subpath.patch` (see below); a moved pin makes the image build fail at that step, and the
patch must be re-validated with `internal/spike-herdr-web-service.sh` before the pin is changed.

## Web UI (/services/)

The web-service plugin runs a chat-style web client for your herdr agents. The add-on serves it through HA ingress at
`/services/` (the **Services** tab of the add-on page, next to the terminal). The plugin itself only listens on
`127.0.0.1:7340` inside the container.

- **Login:** a password is mandatory and comes from the option `herdr_web_password`; without it the login answers 503.
- **Sessions:** login sessions are not kept across add-on restarts, you log in again. Only the password hash persists.
- **Cookie:** the session cookie `hwv_session` is `HttpOnly` and `SameSite=Strict` with `Path=/`. Because HA serves all
  ingress add-ons on one origin, the browser also sends it to other paths of that origin; scripts cannot read it.
- **Patched client:** the stock client uses root-absolute URLs that cannot work below the ingress path. The image build
  applies a patch that makes them relative and removes the service worker, so push notifications and installing the UI
  as an app are not available.

### Blast radius and network exposure

- A logged-in browser can create sessions, type into **any** pane and start agents, as root inside the add-on, with
  read-write access to `/homeassistant` and the HA tokens in the environment. The blast radius is the same as that of
  the writable web terminal (`/terminal/`). Treat the password accordingly.
- Protection is HA ingress authentication plus the plugin password (argon2id hash, rate-limited logins).
- The add-on's nginx listens on port 8099, which is not published on the host. Other containers on the Home Assistant
  (`hassio`) network can reach that port directly, **bypassing HA authentication**: `/terminal/` is open to them without
  a login, `/services/` still requires the password. This was already true for the terminal before the web UI existed.
  nginx rewrites `Host` and `Origin` towards the plugin, so the plugin's own origin check does not apply to requests
  that come through nginx.

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

## Migrating from tmux

Earlier versions of this add-on used tmux for the persistent session. It was removed and replaced by [herdr](#herdr) in
one step: tmux is no longer installed, no tmux configuration is shipped and there is no switch to go back. Neither the
tmux prefix `Ctrl-a` nor its bindings were ported; herdr runs with its own defaults (prefix `ctrl+b`).

| Before (tmux)                    | Now (herdr)                                                                |
| -------------------------------- | -------------------------------------------------------------------------- |
| session `main`                   | the shared herdr session, workspace `main`                                 |
| `tmux attach -t main`            | log in via SSH or open the web terminal, or run `coding-assistants-attach` |
| window                           | tab                                                                        |
| `Ctrl-a c` (new window)          | `prefix+c` (new tab)                                                       |
| `Ctrl-a \|` (split side by side) | `prefix+v` (split right)                                                   |
| `Ctrl-a -` (split above/below)   | `prefix+minus` (split down)                                                |
| `Ctrl-a [` (scroll / copy mode)  | `prefix+[` (copy mode)                                                     |
| `Ctrl-a r` (reload config)       | `herdr server reload-config`                                               |
| `Ctrl-a d` (detach)              | `prefix+q`                                                                 |

- A tmux session that was running during the update ends with the add-on restart; nothing is carried over.
- An own `~/.tmux.conf` is ignored. Custom herdr settings go into `/data/.config/herdr/config.toml`, see
  [herdr](#herdr).
