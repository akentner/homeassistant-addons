---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 03
subsystem: infra
tags: [claude-code, mcp, home-assistant-addon, bashio, jq, verify-harness]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-01: /data/.claude.json persisted (mode 600) and symlinked from ~/.claude.json; Docker verify harness with stub Supervisor"
provides:
  - claude_mcp_merge helper in run.sh (guarded jq + cp merge of only .mcpServers, existing entries win)
  - Claude Code user-scope registration of mcp_servers (http and stdio), zigbee2mqtt (explicit env) and mariadb-<name> wrappers
  - harness scenarios mcp-servers and mcp-integrations (alias mcp)
affects: [23-08]

actuals:
  tokens: 4000
  tasks: 2
  commits: 2

plan_head_before: ec95a33099605270fd56e925f02fc43c69abac79
plan_head_after: e02478cb47c90657a87d8585d4737a494a9327f0
commits: 2

tech-stack:
  added: []
  patterns:
    - "Single-writer merge helper: jq into mktemp, cp over the target only after jq exit 0 and a non-empty temp file, otherwise warn and leave the file byte-identical; returns non-zero so callers must test it (run.sh runs under errexit)"
    - "Add-on defaults on the LEFT of jq object addition so existing entries win"

key-files:
  created: []
  modified:
    - coding-assistants/run.sh
    - internal/verify-coding-assistants.sh

key-decisions:
  - "claude_mcp_merge returns 1 after logging a warning and every call site tests it in an if, so a failed merge neither kills run.sh under errexit nor logs a false 'Registered N' line"
  - "zigbee2mqtt entry for Claude carries an explicit env object (Z2M_ENV_JSON); the OpenCode entry is left as is"
  - "Existing-entries-win freezes the first value the add-on wrote (no ledger file, user decision default 6); documented in plan 23-08"

requirements-completed: [D-04]

coverage:
  - id: D1
    description: "mcp_servers (http -> {type,url}; stdio -> {type,command,args,env}) are registered in /data/.claude.json; only .mcpServers is written, oauthAccount/projects survive, user-edited entries win, symlink and mode 600 kept, OpenCode registration unchanged"
    requirement: D-04
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh mcp-servers (containers A and B)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A corrupt .claude.json stays byte-identical, a warning is logged and run.sh still starts every service; no MCP secret in the container log"
    requirement: D-04
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh mcp-servers (container C, sha256 compare + log greps)"
        status: pass
    human_judgment: false
  - id: D3
    description: "zigbee2mqtt (explicit env with MQTT values) and one mariadb-<name> stdio entry per mycli connection registered for Claude Code; edits survive container re-creation; no MQTT/database secret in either container log"
    requirement: D-04
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh mcp-integrations"
        status: pass
    human_judgment: false
  - id: D4
    description: "Claude Code actually loads and starts the registered MCP servers (claude mcp list against live servers)"
    verification: []
    human_judgment: true
    rationale: "The harness proves the file content and shapes Claude itself writes; starting the servers needs real HA, MQTT and database endpoints"

duration: 30min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 03: MCP servers for Claude Code Summary

**One guarded `claude_mcp_merge` helper (jq into a temp file, `cp` only on success, existing entries win) feeds /data/.claude.json `.mcpServers` from the `mcp_servers` option, the zigbee2mqtt block (explicit env) and the per-connection mycli wrappers, proven by two new Docker harness scenarios.**

## Performance

- **Duration:** about 30 min (one image build, then cached rebuilds of the last layer)
- **Started:** 2026-10-11T15:50Z
- **Completed:** 2026-10-11T16:21Z
- **Tasks:** 2 (1 tracer, 1 auto)
- **Files modified:** 2

## Accomplishments

- `claude_mcp_merge` in run.sh: assigns only `.mcpServers = ($add + (.mcpServers // {}))`, copies back with `cp` (keeps the symlink target and mode 600) only after jq exit 0 and `-s` on the temp file, otherwise logs `Could not merge MCP servers (N entries) ... leaving it untouched` and returns 1. Only counts are logged.
- `mcp_servers` call site: http entries become `{type:"http",url}`, everything else `{type:"stdio",command,args,env}` (tolerant `(.args // [])` / `(.env // [])`); the OpenCode merge above it is unchanged.
- zigbee2mqtt call site: `{type:"stdio",command:"node",args:[...],env:$Z2M_ENV_JSON}`; mycli call site: one `mariadb-<name>` stdio entry per connection (env empty, the wrapper bakes in MYSQL_*), logged as `Registered N mariadb-mcp server(s) in Claude Code config`.
- Harness `mcp-servers` (29 checks over containers A/B/C: preserved keys, user edit wins, exact entry shapes, symlink and mode, OpenCode regression, corrupt file byte-identical via sha256, warning logged, no secrets in logs) and `mcp-integrations` (12 checks incl. edits surviving a container re-creation). The prefix `mcp` expands to both.

## Task Commits

1. **Task 1 (tracer): shared merge helper + mcp_servers registration, harness mcp-servers** - `3f5a5c6` (feat). The scenario was run first against the unmodified run.sh and failed for the intended reason (no `.mcpServers` entries, no warning), then passed.
2. **Task 2: zigbee2mqtt (explicit env) and mariadb wrappers, harness mcp-integrations** - `e02478c` (feat)

## Files Created/Modified

- `coding-assistants/run.sh` - `claude_mcp_merge` and its three call sites
- `internal/verify-coding-assistants.sh` - scenarios `mcp-servers`, `mcp-integrations`, header docs

## Decisions Made

See `key-decisions`. No option or schema change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] False success log after a failed merge**
- **Found during:** Task 1 (design of the call site)
- **Issue:** the plan's literal wording logs `Registered N MCP server(s)` unconditionally after the merge; after the corrupt-file guard fired that line would claim success.
- **Fix:** the helper returns 1 after its warning and each call site logs "Registered" only inside `if claude_mcp_merge ...; then`, which also keeps a failed merge from tripping errexit.
- **Files modified:** coding-assistants/run.sh
- **Commit:** 3f5a5c6

**Total deviations:** 1 auto-fixed (1 bug). **Impact:** none on scope.

## Deferred Items

- **Pre-existing ordering defect (not fixed, by plan):** run.sh appends the `MQTT_*` / `MYCLI_*` exports to `/etc/profile.d/00-coding-assistants.sh` and to the fish `conf.d` file before those files are truncated and rewritten later in the script, so the appended lines are lost. The existing OpenCode zigbee2mqtt entry carries no env and depends on those exports; the Claude entry avoids the problem with its explicit env. Fixing the ordering needs its own change.
- **Stale defaults (T-23-07, accepted):** existing-entries-win freezes the first value the add-on wrote (for example a rotated ha-mcp URL) until the user edits or deletes the entry. Documentation lands in plan 23-08.
- **Schema gap:** `config.yaml` has no `args` / `env` for `mcp_servers` although DOCS.md documents them; the tolerant jq mapping handles both, the schema is unchanged.

## Issues Encountered

- The plan's `read_first` pointed at `git show fbb1f56:...` for the earlier Claude jq; not needed, the shapes follow the plan text and the harness proves them.
- Development loop used a manually built `coding-assistants-verify:dev` image with `CA_VERIFY_IMAGE`; the final `bash internal/verify-coding-assistants.sh mcp claude` run built its own image and passed.

## Verification Results

- `bash internal/verify-coding-assistants.sh mcp claude` -> exit 0, 66 PASS, no FAIL (mcp-servers 17, mcp-integrations 12, claude-* 37)
- `shellcheck -e SC1091 -e SC2034 coding-assistants/run.sh internal/verify-coding-assistants.sh` -> clean
- Acceptance greps: `^claude_mcp_merge() {` present, `-s` guard inside the helper, `claude_mcp_merge ` count 4 (>= 3), `Z2M_ENV_JSON` used beyond its definition
- Pre-commit hooks passed on both commits

## Known Stubs

None.

## Threat Flags

None - no new endpoints or trust boundaries beyond the plan's threat model (T-23-05 and T-23-06 mitigated and asserted by the harness, T-23-07 accepted).

## Next Phase Readiness

Plan 23-08 can document the existing-entries-win limitation and the Claude registration. The harness keeps its `mcp` alias for later regression runs.

## Self-Check: PASSED

- FOUND: coding-assistants/run.sh, internal/verify-coding-assistants.sh
- FOUND commits: 3f5a5c6, e02478c
