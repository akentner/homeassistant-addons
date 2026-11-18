---
phase: 01-bearer-api-listener
plan: 06
subsystem: release
tags: [admin-ui, release, sync, versioning, consumers, docker]
status: complete
requires:
  - "01-01..01-05: lib/skeleton VERSION 0.10.0 with make_api_server, OptionToken, GeneratedToken, serve(server, *more), R-16, lock refreshed in every skeleton commit"
provides:
  - "admin-ui add-on 0.4.0-0 (config 0.4.0-0, build 0.4.0, README v0.4.0) with a 0.4.0-0 CHANGELOG section; the 0.3.1-0 heading is restored"
  - "lib 0.10.0 in all four registered consumers (eight copies, eight stamps at version 0.10.0)"
  - "Consumer subpatch bumps: coding-assistants 1.3.2-1, haos-monitor 0.8.3-1, ntfy 2.38.1-1, secrets-sync 0.7.6-1, each with a CHANGELOG entry"
  - "Local images local/admin-ui:0.4.0-0, local/haos-monitor:0.8.3-1, local/ntfy:2.38.1-1, local/secrets-sync:0.7.6-1, local/coding-assistants:1.3.2-1 (not committed)"
affects: [phase-close-out, marketplace-repo-proxy, ntfy-phase-25]
actuals:
  tokens: 30400
  tasks: 2
  commits: 2
plan_head_before: bbdc43e50adae0969cc9ea95925b9454f8f413cd
plan_head_after: d8304a86eab8cb27f8fe153313083c4ebfebd548
tech-stack:
  added: []
  patterns:
    - "Release by sync: make sync-admin-ui (--all) replaces make release-admin-ui-lib when the source VERSION already equals the release; the release target's checks run explicitly"
    - "Bump set derived from git status after the sync, never hard-coded; explicit X.Y.Z-(N+1) so update-version only touches config.yaml"
    - "Sync and consumer bumps in one commit, so no commit changes a consumer's image content under its old tag"
key-files:
  created:
    - .planning/workstreams/admin-ui-bearer-api/phases/01-bearer-api-listener/deferred-items.md
  modified:
    - admin-ui/config.yaml
    - admin-ui/build.yaml
    - admin-ui/README.md
    - admin-ui/CHANGELOG.md
    - admin-ui/tests/test_addon_scaffold.py
    - coding-assistants/app/web/admin_ui/ (LIB.stamp, __init__.py, api.py, server.py, tokens.py)
    - coding-assistants/app/web/static/vendor/admin-ui/ (LIB.stamp, VERSION)
    - haos-monitor/app/web/admin_ui/, haos-monitor/app/web/static/vendor/admin-ui/ (same files)
    - ntfy/app/web/admin_ui/, ntfy/app/web/static/vendor/admin-ui/ (same files)
    - secrets-sync/app/web/admin_ui/, secrets-sync/app/web/static/vendor/admin-ui/ (same files)
    - coding-assistants/config.yaml
    - coding-assistants/CHANGELOG.md
    - haos-monitor/config.yaml
    - haos-monitor/CHANGELOG.md
    - ntfy/config.yaml
    - ntfy/CHANGELOG.md
    - secrets-sync/config.yaml
    - secrets-sync/CHANGELOG.md
key-decisions:
  - "Images built with the exact make -n build-addon command minus --progress=plain, because the host has no docker buildx plugin (Rule 3); the Makefile is unchanged and the fix is deferred"
  - "admin-ui/lib.lock not staged: the sync reported it up to date (version 0.10.0)"
requirements-completed: [AUB-06]
duration: 16min
completed: 2026-11-18
---

# Phase 01 Plan 06: Release admin-ui 0.4.0-0 and lib 0.10.0 Summary

**Release commit for admin-ui 0.4.0-0 (bearer API listener, OptionToken with at least 16 characters, GeneratedToken,
R-16), then a sync of lib 0.10.0 into coding-assistants, haos-monitor, ntfy and secrets-sync with subpatch bumps
(1.3.2-1, 0.8.3-1, 2.38.1-1, 0.7.6-1). All five images built locally and the real-container scaffold verify passed.
Nothing was tagged or pushed.**

## Performance

- **Duration:** about 16 min
- **Started:** 2026-11-18T13:57:05Z
- **Completed:** 2026-11-18T14:13Z
- **Tasks:** 2
- **Files modified:** 41 (5 admin-ui, 36 consumer files)

## Accomplishments

- admin-ui was bumped through `make update-version ADDON=admin-ui VERSION=0.4.0 NO_TAG=yes` to 0.4.0-0 / 0.4.0 /
  v0.4.0. `EXPECTED_VERSION = "0.4.0"`. The CHANGELOG has a `## [0.4.0-0] - 2026-11-18` section (listener,
  `OptionToken` "at least 16 characters", `GeneratedToken`, `serve(server, *more)`, R-16, lib 0.10.0). The broken line
  `- 2026-11-05` is restored as `## [0.3.1-0] - 2026-11-05`.
- `make sync-admin-ui` printed eight `UPDATED` lines (four consumers, two copies each) and `up to date
  admin-ui/lib.lock`. A second sync changed nothing (E14).
- Bump set derived from `git status` after the sync: coding-assistants, haos-monitor, ntfy, secrets-sync. Each
  `make update-version ADDON=<c> VERSION=X.Y.Z-(N+1) NO_TAG=yes` updated only config.yaml ("1/3 files needed
  updating"; build.yaml and README "No changes needed"), and validation passed.
- CHANGELOG entries: haos-monitor and secrets-sync above the first version heading. coding-assistants below
  `## [Unreleased]`. ntfy inside its add-on section below `# Changelog` (line 134), above `## [2.37.2-8]`.

## Task Commits

1. **Task 1: admin-ui 0.4.0-0 with release notes**: `cc1e5fd` (feat). Only admin-ui files.
2. **Task 2: sync lib 0.10.0 into consumers with subpatch bumps**: `d8304a8` (chore). 36 files: 8 copy directories
   plus config.yaml and CHANGELOG.md of each of the four consumers. lib.lock unchanged.

All pre-commit hooks ran and passed on both commits, including Validate Add-on Versioning and the admin-ui drift
check. `--no-verify` was not used.

## Verification (commands and results)

| Step | Command | Result |
| --- | --- | --- |
| T1 | `make validate-versions` | exit 0 |
| T1 | `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_addon_scaffold.py admin-ui/tests/test_docs.py -q` | 36 passed |
| T1 | `tr -s ' \n' '  ' < admin-ui/CHANGELOG.md \| grep -c 'at least 16 characters'` | 1 |
| T1 | `pre-commit run prettier / markdownlint-cli2 --files admin-ui/CHANGELOG.md` | passed (prettier reflowed once, then clean) |
| T1 | commit-scope check (last commit on admin-ui/config.yaml is 0.4.0-0, only admin-ui/ files) | ok |
| T2.1 | consumer paths clean; `make check-admin-ui-sync` (non-strict) | exit 0, `OK admin-ui lock: 0.10.0`, 8 WARN behind 0.9.1, no FAIL |
| T2.2 | `make sync-admin-ui` (ADDON unset) | exit 0, 8 UPDATED, lock up to date |
| T2.3 | `make check-admin-ui-sync STRICT=yes` / `check-admin-ui-rules` / `test-admin-ui` / `test-admin-ui-consumers` | all exit 0; test-admin-ui 322 node + 463 pytest; consumers 19 node + 397 + 66 + 247 pytest |
| T2.4 | second `make sync-admin-ui`, status+diff compared | identical (E14) |
| T2.5 | 4x `make update-version ADDON=<c> VERSION=<next> NO_TAG=yes` | exit 0 each, only config.yaml changed |
| T2.6 | prettier / markdownlint-cli2 on the four CHANGELOGs, `make validate-versions` | passed / passed / exit 0 |
| T2.7 | `uv run --python 3.12 --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` | 463 passed (Python 3.12.15) |
| T2.8 | builds (see deviation 1), strictly one at a time, `docker ps` empty before each | admin-ui, haos-monitor, ntfy, secrets-sync, coding-assistants (TIMEOUT 1800, background): all exit 0 |
| T2.8 | image content check (`find` api.py in admin-ui/haos-monitor/ntfy/secrets-sync images under the bumped tags) | all four contain api.py |
| T2.8 | `cat /opt/coding-assistants/static/vendor/admin-ui/VERSION` in `local/coding-assistants:1.3.2-1` | 0.10.0 |
| T2.9 | `bash internal/verify-admin-ui-scaffold.sh` (no `admin-ui-verify` container before) | exit 0, "All admin-ui scaffold verifications passed." |
| T2.10 | `make check-admin-ui-sync STRICT=yes`, `check-admin-ui-rules`, `test-admin-ui`, `test-admin-ui-consumers`, `validate-versions` | all exit 0, no FAIL line |
| T2.10 | eight LIB.stamp files start with `version 0.10.0`; `head -n1 admin-ui/lib.lock` | ok; `version 0.10.0` |
| T2.10 | E13 lock-ordering check (bash) | ok, 9 skeleton commits all touch lib.lock |
| T2.10 | D-12 bump gate (bash) | ok: coding-assistants haos-monitor ntfy secrets-sync; changed config.yaml set = admin-ui + those four |
| T2.10 | tag check (no `admin-ui/v*`, no tag on any phase commit) | ok (re-run after commit 2: 23 phase commits, no tag) |

The `<verify>` one-liners use `for c in $commits` word splitting, so they were run under `bash` (script file). The
agent shell is zsh, which does not split an unquoted variable. The logic is unchanged.

## Decisions Made

- `admin-ui/lib.lock` was not staged: the sync left it unchanged.
- The release used `make sync-admin-ui` instead of `make release-admin-ui-lib`, as the plan prescribes. The checks
  that target would have run were run explicitly (T2.1, T2.3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `make build-addon` fails without the docker buildx plugin**

- **Found during:** Task 2, step 8 (first build, admin-ui)
- **Issue:** The target passes `--progress=plain`. This host has docker 29.9.3 without buildx
  (`/usr/lib/docker/cli-plugins` only has docker-compose; package `docker-buildx` not installed), so the legacy builder
  rejects the flag: `unknown flag: --progress`, exit 125, before any build step.
- **Fix:** No package install (Rule 3 exclusion) and no Makefile change. A scratchpad wrapper took the exact command
  that `make -s -n build-addon ADDON=<a> TIMEOUT=<s>` prints, dropped only the `--progress=plain` line (an output-format
  flag), and ran it. Build args (`BUILD_FROM`, `VERSION`, `BUILD_VERSION`, ...), the timeout and the tag
  `local/<addon>:<config version>` are identical to the make target. None of the five Dockerfiles uses a BuildKit-only
  feature (no `# syntax`, `RUN --mount`, `COPY --from`, `--chmod`).
- **Commands run (one at a time):** `build-legacy.sh admin-ui`, `build-legacy.sh haos-monitor`,
  `build-legacy.sh ntfy`, `build-legacy.sh secrets-sync`, `build-legacy.sh coding-assistants 1800` (background,
  waited for). All exit 0, "Successfully tagged local/<addon>:<new version>".
- **Files modified:** none in the repo. Logged in `deferred-items.md`.
- **Commit:** n/a (build-only)

**2. [Rule 3 - Tooling] Verify one-liners run under bash**

- **Found during:** Task 2 git gates
- **Issue:** Under zsh, `for c in $commits` iterates once over the whole string, and `git show` fails with "file name
  too long".
- **Fix:** The same commands ran unchanged from a bash script.
- **Commit:** n/a

**Total deviations:** 2 auto-fixed (tooling and environment). **Impact:** none on the released content. The images
are the same as `make build-addon` would produce; only the build log format differs (legacy builder).

## Issues Encountered

- Hand-off from 01-05 (`ERROR_STATUS` pin needs `unauthorized` when a consumer adopts the listener): not triggered.
  No consumer adopts the listener in this plan, and `make test-admin-ui-consumers` passed (ntfy contract tests
  included). Nothing changed.
- Broken-windows ledger: `.planning/WINDOWS.md` sits at the repo root. Workstream rule: write under `.planning/` only
  below the workstream directory. So the build deviation was not appended there; it lives in `deferred-items.md`.

## Known Stubs

None.

## Threat Flags

None. No new network, auth or file surface. Release metadata and generated copies only. T-01-28: no tag, push, PR or
merge. Every bump used `NO_TAG=yes`, and CHECK_RELEASE and NO_PUSH were never set.

## User Setup Required

None. Local images were left in place; the plan did not ask for cleanup.

## Next Phase Readiness

- Phase 01 is ready for close-out and verification. The branch holds the release; push, PR and merge are left to the
  user.
- Open: `make build-addon` needs buildx on this host (deferred-items.md). E10 / A8 from 01-05 still needs human
  confirmation at verification.

## Self-Check: PASSED

- FOUND: 01-06-SUMMARY.md, deferred-items.md, admin-ui/CHANGELOG.md
- FOUND: cc1e5fd, d8304a8 (ancestors of HEAD)
