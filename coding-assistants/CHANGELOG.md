# Changelog

All notable changes to the **Coding Assistants** add-on are documented in this file. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/), and this add-on uses pre-release SemVer (`X.Y.Z-alphaN`) until a stable
1.0.0 is shipped.

This add-on has no upstream — every entry below is hand-written by the maintainers.

## [Unreleased]

### Changed

- **amd64 only:** the add-on is no longer built or published for aarch64 (not needed; the emulated aarch64 CI build took
  about 20 minutes). The Dockerfile and the aarch64 pins stay, so re-enabling is a one-line change in `build.yaml`
  (`build_from`) plus `aarch64` in the `arch:` list of `config.yaml`. Existing aarch64 images stay in the registry but
  receive no updates.
- **OpenCode 2** replaces OpenCode 1 as a pinned release binary (`OPENCODE_VERSION`, per-architecture SHA256 digests;
  the 1.x installer cannot install 2.x). A persisted OpenCode 1.x binary in `/data/opencode/bin` is replaced by the
  bundled one on the first start; a newer persisted version is kept. MCP servers are written to `mcp.servers` of
  `opencode.json`; entries of the OpenCode 1 layout are moved there once (`enabled` becomes `disabled`). Renovate bumps
  `OPENCODE_VERSION` (2.x releases); digests are refreshed with `internal/update-opencode-pins.sh`.
- **OpenCode server password:** OpenCode 2 always requires one (basic auth, user `opencode`; it used to be open). The
  new optional `opencode_password` option sets it; otherwise a password is generated once into
  `/data/.opencode-password`. The old `OPENCODE_SERVER_PASSWORD` is not used by OpenCode 2 — if you set it via
  `env_vars`, switch to the option. The image grows by roughly 130 MB (the OpenCode 2 binary is about 260 MB unpacked).

### Added

- **OpenAI Codex CLI** (`codex`) as a pinned static release binary (`CODEX_VERSION`, per-architecture SHA256 digests;
  image about 110 MB larger). `CODEX_HOME=/data/.codex` persists login and config; the TOOLS.md context is injected into
  `/data/.codex/AGENTS.md` as a marked block; new optional `openai_api_key` option (exported as `OPENAI_API_KEY` only
  when set); sessions and logs are excluded from backups. Version shown in the greeting and web UI. Renovate bumps
  `CODEX_VERSION`; digests are refreshed with `internal/update-codex-pins.sh`. MCP sync and sandbox defaults for Codex
  are not part of this change.
- **MariaDB / MySQL client with autocompletion** via a new `mycli:` add-on option (one or more named connections,
  persisted to `/data/.myclirc`). The bundled `mycli` TUI client connects on first run, with per-connection DSN aliases
  (`mycli -D <name>`) and `MYCLI_HOST/PORT/USER/PASSWORD/DATABASE` env vars. Each connection also auto-registers a
  `mariadb-<name>` MCP server (`mcp-server-mysql`) so OpenCode can run SQL against the configured databases without
  leaving the assistant. The MCP server is wired through per-connection wrapper scripts at
  `/usr/local/bin/mariadb-<name>` (chmod 700) so the assistant only sees the connections you configured.
- **Claude Code** (`claude`) is bundled again, installed with the native installer. Updates (`claude update` and
  background updates) are persisted under `/data/.local/share/claude/versions` and the launcher points into that
  directory on every start; the image only carries a seed that is used when it is newer than the persisted version.
  `~/.claude` and `~/.claude.json` live in `/data/.claude` and `/data/.claude.json`. Legacy `/data/claude/.claude*`
  contents are copied there once when the new paths do not exist and are not deleted. The TOOLS.md context is injected
  into `/data/.claude/CLAUDE.md` as a marked block that is rewritten on every start (text outside the markers is
  preserved). The add-on sets no Claude settings or permission defaults.
- **Claude Code authentication options** `claude_code_oauth_token` and `anthropic_api_key` (optional passwords). They
  are exported as `CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` into the process environment only, never written to a
  file or the log. With both set the API key wins; an `env_vars` entry of the same name overrides the option.
- **MCP registration for Claude Code**: the `mcp_servers` option, the `zigbee2mqtt` integration and the `mariadb-<name>`
  servers of `mycli` are now also registered in `/data/.claude.json` (user scope). Existing entries win, so edits
  survive but changed add-on values do not reach an existing entry; remove the entry
  (`claude mcp remove <name> --scope user`) and restart to refresh it.
- **herdr** 0.9.3 (checksum-pinned release binary) as the terminal workspace manager. The add-on starts the herdr server
  (restarted automatically if it stops) with the add-on environment; SSH and the web terminal attach to one shared
  session with workspace `main` at `/homeassistant`. No herdr configuration or key bindings are shipped.
- **herdr plugins** linked at every start from commit-pinned checkouts below `/opt/herdr-plugins/`: subagent-watch,
  claude-limits and web-service. They are not configured by the add-on; DOCS.md documents the opt-in steps.
- **Web UI at `/services/`** (new **Services** tab) through the existing ingress port, served by the herdr-web-service
  plugin with a client patched for the ingress sub-path. The login password is set by the new optional password option
  `herdr_web_password`; without it the login is refused.
- Escape hatch for SSH: `CODING_ASSISTANTS_NO_ATTACH=1` or `bash --noprofile` give a plain shell instead of herdr.

### Changed

- SSH logins and the web terminal attach to the shared **herdr** session instead of the previous terminal multiplexer
  session. The MOTD, the landing page and `versions.json` show the Claude Code and herdr versions.

### Removed

- **tmux** — the package, its system-wide configuration and the `Ctrl-a` key bindings are gone; nothing is ported and
  there is no fallback. See "Migrating from tmux" in DOCS.md.

## [1.0.0-alpha45] - 2026-08-21

### Added

- Initial public pre-alpha. Bundles Claude Code, OpenCode and the GitHub Copilot CLI into a single container exposed via
  SSH and the `ttyd` web terminal.

[Unreleased]: https://github.com/akentner/homeassistant-addons/compare/coding-assistants/v1.0.0-alpha45...HEAD
[1.0.0-alpha45]: https://github.com/akentner/homeassistant-addons/tree/coding-assistants/v1.0.0-alpha45
