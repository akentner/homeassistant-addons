---
type: quick
task_id: 260404-s1t
date: "2026-04-04"
duration_minutes: 5
completed_tasks: 2
total_tasks: 2
files_modified:
  - meridian/config.yaml
  - meridian/run.sh
key_decisions:
  - Boolean flags (passthrough, no_file_changes) exported only when true to match upstream unset=disabled semantics
  - map changed from [] to data:rw to make /data/workdir writable at runtime
tags:
  - meridian
  - config
  - run.sh
---

# Quick Task 260404-s1t: Meridian — Expose All Upstream Config Options

**One-liner:** All 10 upstream Meridian env vars now configurable via HA add-on UI, with correct schema types and
boolean unset=disabled semantics.

## What Was Done

Added all upstream Meridian configuration variables as HA add-on options so users can tune proxy behaviour through the
Home Assistant UI without modifying container internals.

### Task 1 — config.yaml (commit 0ed83c3)

Added 10 new entries to both the `options` (defaults) and `schema` (types) blocks:

| Option                 | Default         | Schema type                                     |
| ---------------------- | --------------- | ----------------------------------------------- |
| `passthrough`          | `false`         | `bool`                                          |
| `max_concurrent`       | `10`            | `int`                                           |
| `max_sessions`         | `1000`          | `int`                                           |
| `max_stored_sessions`  | `10000`         | `int`                                           |
| `workdir`              | `/data/workdir` | `str`                                           |
| `idle_timeout_seconds` | `120`           | `int`                                           |
| `telemetry_size`       | `1000`          | `int`                                           |
| `no_file_changes`      | `false`         | `bool`                                          |
| `sonnet_model`         | `sonnet[1m]`    | `list(sonnet\|sonnet[1m])`                      |
| `default_agent`        | `opencode`      | `list(opencode\|pi\|crush\|droid\|passthrough)` |

Also changed `map: []` to `map: - data:rw` to grant write access to `/data/workdir`.

### Task 2 — run.sh (commit 3ed58d3)

After the existing `MERIDIAN_HOST` export block, added:

- `mkdir -p "${MERIDIAN_WORKDIR}"` to create the workdir at startup
- Export of 8 string/numeric vars: `MERIDIAN_WORKDIR`, `MERIDIAN_MAX_CONCURRENT`, `MERIDIAN_MAX_SESSIONS`,
  `MERIDIAN_MAX_STORED_SESSIONS`, `MERIDIAN_IDLE_TIMEOUT_SECONDS`, `MERIDIAN_TELEMETRY_SIZE`, `MERIDIAN_SONNET_MODEL`,
  `MERIDIAN_DEFAULT_AGENT`
- Conditional export of boolean flags `MERIDIAN_PASSTHROUGH` and `MERIDIAN_NO_FILE_CHANGES` only when the config option
  is true (matching upstream's unset=disabled convention)

## Verification

- `make validate-addons` — passed for all three add-ons
- `shellcheck -e SC1091 -e SC2034 meridian/run.sh` — no errors

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- meridian/config.yaml: modified with 10 new options — FOUND
- meridian/run.sh: modified with 10 new env var exports — FOUND
- Commit 0ed83c3 (Task 1): FOUND
- Commit 3ed58d3 (Task 2): FOUND
