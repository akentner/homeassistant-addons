---
status: complete
---

# Quick: persist Codex state started without CODEX_HOME

- Cause: root's login shell is bash; non-interactive SSH commands (remote app-server) do not read /etc/profile.d,
  so Codex used /root/.codex (ephemeral container layer). Evidence: /data/.codex stale since Nov 20,
  /root/.codex written Nov 22 (fresh installation_id, app-server-daemon, auth.json).
- Fix: run.sh merges a leftover /root/.codex into /data/.codex (no overwrite) and symlinks /root/.codex -> /data/.codex.
- Version bump deferred: -4 is taken by PR #125.
