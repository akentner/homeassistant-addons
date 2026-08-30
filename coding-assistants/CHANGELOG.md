# Changelog

All notable changes to the **Coding Assistants** add-on are documented in this file. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/), and this add-on uses pre-release SemVer (`X.Y.Z-alphaN`) until a stable
1.0.0 is shipped.

This add-on has no upstream — every entry below is hand-written by the maintainers.

## [Unreleased]

### Added

- **MariaDB / MySQL client with autocompletion** via a new `mycli:` add-on option (one or more named connections,
  persisted to `/data/.myclirc`). The bundled `mycli` TUI client connects on first run, with per-connection DSN aliases
  (`mycli -D <name>`) and `MYCLI_HOST/PORT/USER/PASSWORD/DATABASE` env vars. Each connection also auto-registers a
  `mariadb-<name>` MCP server (`mcp-server-mysql`) so OpenCode can run SQL against the configured databases without
  leaving the assistant. The MCP server is wired through per-connection wrapper scripts at
  `/usr/local/bin/mariadb-<name>` (chmod 700) so the assistant only sees the connections you configured.

### Removed

- **Claude Code CLI** — Claude Code (`claude`) is no longer bundled in this add-on. The associated Claude-specific
  integrations are dropped: `~/.claude` / `~/.claude.json` / `~/.agents` symlink persistence, TOOLS.md injection into
  Claude Code's `CLAUDE.md`, `mcpServers` registration in Claude's `~/.claude.json`, `claude --version` in MOTD/web-UI,
  the `versions.json` `claude` field, and the cleanup-pass against the host's `/homeassistant/.claudecode/.claude.json`.
  Existing `/data/claude/` contents are left on disk for inspection but are no longer symlinked or read by the add-on.

## [1.0.0-alpha45] - 2026-08-21

### Added

- Initial public pre-alpha. Bundles Claude Code, OpenCode and the GitHub Copilot CLI into a single container exposed via
  SSH and the `ttyd` web terminal.

[Unreleased]: https://github.com/akentner/homeassistant-addons/compare/coding-assistants/v1.0.0-alpha45...HEAD
[1.0.0-alpha45]: https://github.com/akentner/homeassistant-addons/tree/coding-assistants/v1.0.0-alpha45
