---
phase: quick
plan: 260507-vjm
subsystem: coding-assistants
tags: [mcp, zigbee2mqtt, dockerfile, nodejs, typescript]
dependency_graph:
  requires: []
  provides: [mcp2zigbee2mqtt-in-container]
  affects: [coding-assistants/Dockerfile, coding-assistants/config.yaml, coding-assistants/TOOLS.md]
tech_stack:
  added: [MCP2ZigBee2MQTT (TypeScript, built from source)]
  patterns: [apk --virtual build deps with cleanup, subshell cd pattern for hadolint compliance]
key_files:
  modified:
    - coding-assistants/Dockerfile
    - coding-assistants/config.yaml
    - coding-assistants/TOOLS.md
decisions:
  - Use subshell `(cd /opt/mcp2zigbee2mqtt && ...)` pattern to satisfy DL3003 hadolint rule
  - Add `# hadolint ignore=DL3003` inline directive since subshell pattern still triggers warning
  - Keep `env` as non-optional list in schema (HA addon validation accepts missing optional lists)
metrics:
  duration: ~10 minutes
  completed: "2026-05-07"
  tasks_completed: 3
  files_changed: 3
---

# Phase quick Plan 260507-vjm: Integrate MCP2ZigBee2MQTT in coding-assistants Summary

**One-liner:** MCP2ZigBee2MQTT built from TypeScript source in the coding-assistants container, with per-server env
schema in config.yaml and full registration example in TOOLS.md.

## What Was Done

Integrated the MCP2ZigBee2MQTT stdio server into the coding-assistants add-on so AI assistants (Claude Code, OpenCode)
can control ZigBee devices via Zigbee2MQTT using the MCP protocol.

## Tasks Completed

| Task | Name                                                | Commit  | Files                         |
| ---- | --------------------------------------------------- | ------- | ----------------------------- |
| 1    | Add MCP2ZigBee2MQTT build step to Dockerfile        | 7a8b295 | coding-assistants/Dockerfile  |
| 2    | Extend config.yaml mcp_servers schema with env list | 51af09d | coding-assistants/config.yaml |
| 3    | Document MCP2ZigBee2MQTT in TOOLS.md                | f80e789 | coding-assistants/TOOLS.md    |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] hadolint DL3003 violation in Dockerfile**

- **Found during:** Task 1 commit
- **Issue:** `cd /opt/mcp2zigbee2mqtt` inside RUN block triggers DL3003 ("Use WORKDIR"). Subshell pattern
  `(cd ... && ...)` was tried but still triggered the warning. hadolint is active in pre-commit (not disabled as
  CLAUDE.md previously noted).
- **Fix:** Added `# hadolint ignore=DL3003` inline directive above the RUN block. This is the standard pattern already
  used in the Dockerfile for DL3013.
- **Files modified:** coding-assistants/Dockerfile
- **Commit:** 7a8b295 (incorporated into task commit, no separate commit needed)

**2. [Rule 1 - Bug] prettier reformatted TOOLS.md blockquote**

- **Found during:** Task 3 commit
- **Issue:** Prettier reformatted the `> Note:` blockquote to a single line (within 120 chars). Auto-applied by
  pre-commit hook.
- **Fix:** Re-staged prettier-modified file and committed the canonical prettier-formatted version.
- **Files modified:** coding-assistants/TOOLS.md
- **Commit:** f80e789

## Decisions Made

1. **hadolint DL3003 suppress via inline directive** — Using `# hadolint ignore=DL3003` is the established pattern in
   this repo (see `# hadolint ignore=DL3013` on line 21). The build tool ordering inside the subshell is intentional and
   correct.
2. **`env` field declared without optional marker** — HA addon schema validation accepts list fields that are absent
   from some `options` entries. Confirmed with `make validate-addons`. Existing ha-mcp and fff entries remain valid
   without the `env` key.
3. **No version bump** — The plan did not request a version increment. Functionality is baked into the image at build
   time; no add-on config.yaml `version:` change is warranted.

## Known Stubs

None. The zigbee2mqtt entry in `options.mcp_servers` contains real default values (uses the standard HA MQTT broker URL
`mqtt://homeassistant:1883`). Users can modify or remove it; it is a working template, not a placeholder.

## Threat Flags

No new threat surface beyond what was documented in the plan's `<threat_model>`. All three threat items (T-z2m-01,
T-z2m-02, T-z2m-03) were accepted risks per the plan.

## Self-Check: PASSED

- coding-assistants/Dockerfile: contains mcp2zigbee2mqtt build block at line 62-72
- coding-assistants/config.yaml: contains `env:` schema at lines 50 and 74, zigbee2mqtt example entry
- coding-assistants/TOOLS.md: 6 occurrences of "zigbee2mqtt" (>= 3 required)
- Commits 7a8b295, 51af09d, f80e789 exist in git log
- `make lint` passes all hooks: yamllint, shellcheck, prettier, hadolint, validate-addons
