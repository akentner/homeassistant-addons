# Quick 261108-hmq: Add OpenAI Codex CLI to coding-assistants

Decisions are binding as given by the user (release binary with SHA256 pins mirrored in build.yaml, Renovate for
CODEX_VERSION, CODEX_HOME=/data/.codex, openai_api_key option, AGENTS.md marker block, version in greeting,
MCP/sandbox config out of scope, docs + minor bump via make update-version).

Tasks: (1) Dockerfile/build.yaml pins + drift check; (2) run.sh/attach/config.yaml persistence and auth; (3) Renovate
manager + internal/update-codex-pins.sh; (4) docs, bump, verification scenario `codex-state`.
