---
phase: quick
plan: 260502-0kw
subsystem: coding-assistants
tags: [config, schema, mcp, optional-fields]
key-files:
  modified:
    - coding-assistants/config.yaml
decisions:
  - "Used ? suffix on key names (args?: and env?:) to mark fields optional — same pattern as command: str? and url: str?"
metrics:
  duration: "< 5 minutes"
  completed: "2026-05-02"
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 260502-0kw: Make args and env optional in mcp_servers schema

Make `args` and `env` optional in the `mcp_servers` schema in `coding-assistants/config.yaml` so that HA supervisor
accepts mcp_server entries that only specify `name`, `type`, and `url` (e.g. http-type MCP servers).

## What Was Done

Updated `coding-assistants/config.yaml` schema section for `mcp_servers`:

- `args:` → `args?:` (line 64)
- `env:` → `env?:` (line 66)

The `?` suffix on a key name in HA add-on schemas marks the field as optional, following the same pattern already used
for `command: str?` and `url: str?` in the same schema block. No runtime changes were needed — `run.sh` already handles
missing values with `(.env // [])` and `(.args // [])`.

## Verification

- `make validate-addons` — passed (all 4 add-ons)
- `make validate-versions` — passed (all 4 add-ons)

## Commits

| Task | Description                                      | Commit  |
| ---- | ------------------------------------------------ | ------- |
| 1    | Make args and env optional in mcp_servers schema | 1f17a3b |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- File `coding-assistants/config.yaml` exists and contains `args?:` and `env?:`
- Commit `1f17a3b` exists in git log
- Both `make validate-addons` and `make validate-versions` pass
