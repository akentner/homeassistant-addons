---
status: complete
---

# Quick 261108-hmq: Summary

Codex CLI 0.167.0 added to coding-assistants 1.2.0-0 (commit on feat/coding-assistants-codex).

- Verified: amd64 docker build, `codex --version` in the image, verify scenarios `drift`, `docs`, `codex-state`
  (the latter with `CA_VERIFY_DOCKER_ARGS="--network host"`: the host firewall blocks container-to-host traffic to the
  supervisor stub), pre-commit, make validate-versions.
- Not verified: aarch64 build, interactive `codex login --device-auth`, Codex sandbox in the container,
  internal/update-codex-pins.sh against a new release, Renovate dry run.
- Deferred by decision: MCP sync to ~/.codex/config.toml, sandbox/approval defaults.
