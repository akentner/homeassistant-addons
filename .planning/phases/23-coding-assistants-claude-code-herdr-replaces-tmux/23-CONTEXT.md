# Phase 23: coding-assistants: Claude Code + herdr (replaces tmux) - Context

**Gathered:** 2026-10-10
**Status:** Ready for planning

<domain>
## Phase Boundary

The `coding-assistants` add-on ships Claude Code next to opencode with the same MCP servers registered, and replaces
tmux with herdr (plus the subagent-watch, web-service and claude-limits plugins). Single add-on only. The full
locked decisions (native installer + `/opt/claude-initial` bootstrap, auth options, `~/.claude.json` `.mcpServers`
merge, tmux removal, pinned ARGs, web-service behind ingress) live in ROADMAP.md Phase 23 and are not re-litigated.

</domain>

<decisions>
## Implementation Decisions

### herdr session model
- **D-01:** SSH and ttyd attach to **one shared herdr session** (same model as the old tmux `main`): start dir
  `/homeassistant`, shell `fish`, attach-or-create semantics. Research must verify herdr has a native
  attach-or-create; otherwise wrap it in run.sh/profile logic.
- **D-02:** **No custom herdr keybindings/config.** herdr defaults only; the tmux prefix (Ctrl-a), Alt-+/- splits,
  resize and vi-copy bindings are NOT ported. `tmux.conf` is deleted.

### Claude Code defaults & context
- **D-03:** `TOOLS.md` is injected into `/data/.claude/CLAUDE.md` (persisted `~/.claude`) as a **marked block that
  run.sh rewrites on every start**; user content outside the block is preserved (mirrors the opencode `instructions`
  update).
- **D-04:** `claude update` stays allowed (binary in `/data/claude/bin`); **no settings.json defaults** and no
  permission/model add-on option. Settings stay user-controlled.

### herdr-web-service ingress
- **D-05:** Exposed at **`/services/`** next to `/terminal/` via nginx `proxy_pass` to the local service (no new
  port), with a link/tab in `index.html`. Research must verify the plugin's base-path/subpath behavior under the
  HA ingress prefix and WebSocket needs.

### Plugin installation & failure handling
- **D-06:** herdr installed as a **release binary**; the three plugins via **`git clone` at a pinned tag/commit**.
  Versions pinned via ARGs in `build.yaml` (e.g. `HERDR_VERSION`, one ref ARG per plugin).
- **D-07:** A plugin failing at runtime (e.g. claude-limits without credentials) → **log a warning and continue**;
  terminal/SSH must always stay usable.
- **D-08:** tmux removed **hard in one step** (package, `tmux.conf`, SSH auto-attach in bash+fish profile, ttyd
  attach); no fallback install. CHANGELOG/DOCS note + subpatch bump via `make update-version`.

### Claude's Discretion
- Exact ARG names, nginx location/rewrite details, run.sh bootstrap ordering, warning wording.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Add-on files to change
- `coding-assistants/Dockerfile` — tmux apt package, opencode installer + `/opt/opencode-initial` stash pattern, ttyd, `COPY tmux.conf`
- `coding-assistants/run.sh` — opencode bootstrap (l.42-53), MCP registration (l.63-242), tmux auto-attach in bash (l.283) and fish (l.344), ttyd start (l.440-450)
- `coding-assistants/nginx.conf` — `/terminal/` proxy pattern to copy for `/services/`
- `coding-assistants/config.yaml` — options/schema (password options for Claude token, `backup_exclude`)
- `coding-assistants/build.yaml` — pinned ARG location
- `coding-assistants/index.html`, `DOCS.md`, `TOOLS.md`, `README.md`, `CHANGELOG.md`, `tmux.conf` (to delete)

### Project rules
- `CLAUDE.md` (repo) — local `docker build` before committing Dockerfile changes; no Co-Authored-By; 3-file version sync via `make update-version`
- `.planning/ROADMAP.md` Phase 23 — locked decisions

### External (research to verify)
- herdr, `silencechung/herdr-subagent-watch`, `i-montes/herdr-web-service`, `martin-saldinger/herdr-claude-limits` — install method, attach semantics, base path, credential use

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- opencode persistence pattern in run.sh (stash in `/opt/*-initial`, copy into `/data`, symlink) — reuse for Claude Code
- MCP wrapper/registration blocks in run.sh — extend to also write `.mcpServers` into `~/.claude.json`

### Established Patterns
- Release binaries downloaded in Dockerfile (ttyd, lazygit, etc.); versions via build.yaml ARG
- nginx `/terminal/` WebSocket proxy block

### Integration Points
- ttyd command (run.sh l.440-450) and SSH profile hooks switch from tmux to herdr attach
- `backup_exclude` in config.yaml may need `.claude` cache entries

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-coding-assistants-claude-code-herdr-replaces-tmux*
*Context gathered: 2026-10-10*
