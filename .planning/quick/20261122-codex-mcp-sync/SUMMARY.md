---
status: complete
---

# Quick: Codex MCP sync (coding-assistants 1.3.3-4)

- New helper `coding-assistants/codex-mcp-merge` (Python, tomllib): appends missing `[mcp_servers.*]` tables to
  `/data/.codex/config.toml`; existing entries and user settings win; unparsable file stays untouched; no secrets logged.
- `run.sh`: `codex_mcp_merge` called for the `mcp_servers` option and Zigbee2MQTT (explicit env).
- Tests: `coding-assistants/tests/test_codex_mcp_merge.py`. Docs: DOCS.md, CHANGELOG.md. Version 1.3.3-4.
- Not covered (deferred): mariadb-mcp connections are still not registered in Codex.
