---
phase: 02-auto-update-workflow
plan: "01"
subsystem: github-actions
tags: [auto-update, github-actions, workflow, upstream-versioning]
dependency_graph:
  requires:
    - scripts/update-version.py (version update tooling — pre-existing)
    - "{addon}/.upstream.yaml" (upstream config schema — pre-existing in both add-ons)
    - fritz-callmonitor2mqtt/build.yaml (current version source)
    - .actionlint.yml (shellcheck ignore rules)
  provides:
    - .github/workflows/auto-update.yml (scheduled auto-update workflow)
  affects:
    - fritz-callmonitor2mqtt/config.yaml (version bumped by workflow on new release)
    - fritz-callmonitor2mqtt/build.yaml (version bumped by workflow on new release)
    - fritz-callmonitor2mqtt/README.md (version badge updated by workflow on new release)
    - phone-logger/config.yaml (same, when phone-logger gets .upstream.yaml)
tech_stack:
  added:
    - GitHub Actions scheduled workflow (cron 0 6 * * *)
    - gh CLI (release version fetching via GH_TOKEN)
    - yq (yaml parsing, pre-installed on ubuntu-latest)
  patterns:
    - Dynamic add-on discovery via `find . -maxdepth 2 -name .upstream.yaml`
    - Per-addon error isolation with continue + ERRORS counter
    - Single push at end (not per-addon) to minimize API calls
    - Targeted shellcheck disable inline (SC2001 for dynamic sed regex)
key_files:
  created:
    - .github/workflows/auto-update.yml
  modified: []
decisions:
  - "Permissions block placed at job-level (not workflow-level) for minimum-privilege — only the update job needs contents:write"
  - "Inline shellcheck disable=SC2001 for sed line — version_strip is a dynamic regex from yaml config, ${var//search/replace} cannot substitute dynamic patterns"
  - "UPDATES_MADE flag gates the push — avoid empty pushes when all add-ons are already current"
  - "exit \$ERRORS at end ensures GitHub Actions marks the run failed if any add-on update failed, while still processing remaining add-ons"
metrics:
  duration: "262 seconds (~4 min 22 sec)"
  completed_date: "2026-04-03"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 02 Plan 01: Auto-Update Workflow Summary

**One-liner:** Scheduled GitHub Actions workflow using gh CLI + yq + update-version.py for zero-touch upstream version sync.

## What Was Built

Created `.github/workflows/auto-update.yml` — a daily scheduled workflow (06:00 UTC + `workflow_dispatch`) that:

1. **Discovers add-ons dynamically** via `find . -maxdepth 2 -name .upstream.yaml | sort` (no hardcoded list)
2. **Fetches latest upstream release** using `gh release view --repo` with GH_TOKEN (no extra secrets needed)
3. **Strips version prefix** with sed using `version_strip` regex from `.upstream.yaml` (e.g. `^v` → `1.7.3`)
4. **Compares to current** `build.yaml` VERSION field — skips if already at target
5. **Updates 3-file version set** via `python3 scripts/update-version.py "$addon_name" "$latest_version"`
6. **Detects actual changes** with `git diff --quiet` — skips commit if script was a no-op
7. **Stages only version files** (`config.yaml`, `build.yaml`, `README.md`) — never `git add -A`
8. **Commits per add-on** as `github-actions[bot]`, pushes once at end
9. **Continues on per-addon error** — ERRORS counter ensures non-zero exit if anything failed

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create auto-update.yml workflow | `3041179` | `.github/workflows/auto-update.yml` (created, 92 lines) |
| 2 | Lint validation — actionlint and yamllint pass | `3b67321` | `.github/workflows/auto-update.yml` (1 line added: SC2001 disable) |

## Requirements Fulfilled

| Requirement | Description | How |
|-------------|-------------|-----|
| AUTO-01 | Fetch latest upstream release tag | `gh release view --repo "$upstream_repo" --json tagName --jq .tagName` |
| AUTO-02 | Update 3-file version set | `python3 scripts/update-version.py "$addon_name" "$latest_version"` |
| AUTO-03 | Commit to main when new version found | `git commit -m "chore($addon_name): update to $latest_version"` + `git push` |
| AUTO-04 | No commit when already up to date | `git diff --quiet` check before staging/committing |
| AUTO-05 | Only GITHUB_TOKEN required | `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`, `permissions: contents: write` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SC2001 shellcheck error not suppressed by .actionlint.yml in pre-commit context**

- **Found during:** Task 2 (lint validation)
- **Issue:** Pre-commit's actionlint hook reported `SC2001:style` for the `sed "s/${version_strip}//"` line, even though `.actionlint.yml` has `SC2001` in `exclude-rules`. The pre-commit hook appears to use a different config discovery path than the standalone `actionlint` binary.
- **Fix:** Added `# shellcheck disable=SC2001` inline comment immediately above the `sed` command
- **Why sed is correct here:** `version_strip` is a dynamic regex from yaml config (e.g. `"^v"`). Bash parameter expansion `${var//pattern/replace}` does not support regex anchors or character classes — only glob-style patterns. `sed` is the appropriate tool.
- **Files modified:** `.github/workflows/auto-update.yml`
- **Commit:** `3b67321`

## Known Limitations (Documented in Workflow)

A comment in the workflow documents the GitHub-documented limitation:

> Pushes made with GITHUB_TOKEN do not trigger other GitHub Actions workflows. Auto-update commits will not be validated by lint.yml automatically. Developers can manually trigger lint.yml if validation is needed.

This is expected behavior per D-07 in the research and is not a blocker for the core auto-update functionality.

## Self-Check: PASSED

Files verified:

- [x] `.github/workflows/auto-update.yml` — exists at correct path
- [x] Commit `3041179` — exists in git log
- [x] Commit `3b67321` — exists in git log
- [x] `yamllint .github/workflows/auto-update.yml` — exits 0
- [x] `pre-commit run --files .github/workflows/auto-update.yml` — all hooks passed
- [x] All AUTO-0x requirement patterns present in file
