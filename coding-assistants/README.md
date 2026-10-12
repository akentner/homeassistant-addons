# Home Assistant Add-on: Coding Assistants

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Terminal environment with Claude Code, OpenCode and GitHub Copilot CLI in herdr sessions — accessible via SSH and web
terminal.

## About

This add-on provides a persistent development terminal inside Home Assistant with three AI coding assistants
pre-installed:

- **Claude Code** (`claude`) — Anthropic's coding agent in the terminal
- **OpenCode** (`opencode`) — OpenCode AI agent
- **GitHub Copilot CLI** (`copilot`) — GitHub Copilot in the terminal

Sessions are managed by **herdr**: SSH and the web terminal attach to one shared session that survives disconnects. The
terminal is reachable via HA ingress (web) and SSH on a published port.

Access to your HA configuration directory (`/homeassistant`) is included so the assistants can read and modify your
automations, scripts, and configs directly.

## Features

- SSH server with public-key authentication (port configurable via HA network settings)
- Web terminal via HA ingress (no port forwarding needed)
- Persistent herdr session (workspaces, tabs, panes) shared between SSH and web terminal
- Claude Code with a persistent, self-updating install, persisted login state and the add-on's MCP servers registered
- herdr plugins (subagent-watch, claude-limits) linked for opt-in use, plus a web UI for your agents at `/services/`
  (Services tab) protected by a login password set through an add-on option
- Environment variables injected into every session (API keys, tokens)
- Full tool suite: `git`, `gh`, `jq`, `yq`, `rg`, `fd`, `fzf`, `bat`, `lazygit`, `bun`, `uv`, `task`, `httpie`,
  `shellcheck`

## Configuration

See [DOCS.md][docs] for all configuration options.

Quick start — minimal config:

```yaml
authorized_keys:
  - "ssh-ed25519 AAAAC3... user@host"
# claude_code_oauth_token: "<token>"
env_vars:
  - name: ANTHROPIC_API_KEY
    value: sk-ant-...
  - name: GITHUB_TOKEN
    value: ghp_...
```

[docs]: https://github.com/akentner/homeassistant-addons/blob/main/coding-assistants/DOCS.md
[release-shield]: https://img.shields.io/badge/version-v1.1.0-orange.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.1.0
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
