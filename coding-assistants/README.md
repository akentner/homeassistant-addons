# Home Assistant Add-on: Coding Assistants

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Terminal environment with OpenCode and GitHub Copilot CLI — accessible via SSH and web terminal.

## About

This add-on provides a persistent development terminal inside Home Assistant with two AI coding assistants
pre-installed:

- **OpenCode** (`opencode`) — OpenCode AI agent
- **GitHub Copilot CLI** (`copilot`) — GitHub Copilot in the terminal

Sessions are managed by **tmux** and survive disconnects. The terminal is reachable via HA ingress (web) and SSH on a
published port.

Access to your HA configuration directory (`/homeassistant`) is included so the assistants can read and modify your
automations, scripts, and configs directly.

## Features

- SSH server with public-key authentication (port configurable via HA network settings)
- Web terminal via HA ingress (no port forwarding needed)
- Persistent tmux session shared between SSH and web terminal
- Environment variables injected into every session (API keys, tokens)
- Full tool suite: `git`, `gh`, `jq`, `yq`, `rg`, `fd`, `fzf`, `bat`, `lazygit`, `bun`, `uv`, `task`, `httpie`,
  `shellcheck`

## Configuration

See [DOCS.md][docs] for all configuration options.

Quick start — minimal config:

```yaml
authorized_keys:
  - "ssh-ed25519 AAAAC3... user@host"
env_vars:
  - name: ANTHROPIC_API_KEY
    value: sk-ant-...
  - name: GITHUB_TOKEN
    value: ghp_...
```

[docs]: https://github.com/akentner/homeassistant-addons/blob/main/coding-assistants/DOCS.md
[release-shield]: https://img.shields.io/badge/version-v1.0.0-orange.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.0.0
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
