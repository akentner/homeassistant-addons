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
