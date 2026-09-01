---
quick_id: "260901-na1"
subsystem: ci
tags: [pre-commit, shellcheck, actionlint, prettier, python, terraform-bridge, phone-logger]

# Dependency graph
requires: []
provides:
  - "Green main branch lint/CI baseline for Renovate PRs #42-45 and all future PRs"
  - "validate-addon-config.py accepts both app_config (terraform-bridge) and addon_config (phone-logger, legacy)"
  - "verify-bridge-scaffold.sh docker-image-size regex handles spaced and unspaced Docker size units"
affects: [ci-cd-hardening, bridge-foundation, provider-install-workflow]

tech-stack:
  added: []
  patterns:
    - "Inline `# shellcheck disable=SC<code> # reason` comments for accepted info-level findings in throwaway spike
      scripts, per line, with reason"

key-files:
  created: []
  modified:
    - internal/validate-addon-config.py
    - internal/verify-bridge-scaffold.sh
    - internal/spike-h1-token-rotation.sh
    - internal/spike-pitfalls10-backup-addon-config.sh
    - .github/workflows/test-install-provider.yml
    - .github/RELEASE.md
    - README.md
    - docs/DEVELOPMENT.md
    - docs/WEBHOOK_SETUP.md
    - terraform-bridge/DOCS.md
    - terraform-bridge/internal/httpapi/handlers/version.go
    - terraform-provider-homeassistant/main.go
    - tools/test-bridge-fixture/go.mod
    - tools/test-bridge-fixture/main.go

key-decisions:
  - "pre-commit's prettier hook (JoC0de/pre-commit-prettier) fails in this sandboxed environment because its git+file://
    self-install is blocked by npm's EALLOWGIT restriction; ran prettier@3.9.6 directly via `npx --yes` instead,
    producing byte-identical output since both read the same .prettierrc.yaml"
  - "actionlint and shellcheck installed standalone via `uv tool install actionlint-py` / `uv tool install
    shellcheck-py` since pre-commit's own bootstrapped environments for these were not needed once the CLIs were
    available directly on PATH"

requirements-completed: []

# Metrics
duration: 20min
completed: 2026-09-01
---

# Quick Task 260901-na1: Fix 6 pre-existing lint failures on main Summary

**Fixed all 6 diagnosed pre-existing lint failures on `main` (trailing newlines, markdown formatting, shellcheck
SC2029/SC2012 spike-script suppressions, actionlint SC2086 quoting, and two real bugs: `validate-addon-config.py`
`app_config` gap and `verify-bridge-scaffold.sh` docker-size regex) — 3 atomic commits, zero logic changes to throwaway
spike scripts, terraform-bridge `/data`/token-leak bug (item 7) left untouched as instructed.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-09-01T14:47:00Z
- **Completed:** 2026-09-01T15:06:00Z
- **Tasks:** 3
- **Files modified:** 15 (non-`.planning`) + 8 `.planning/*` files auto-touched by end-of-file-fixer (left uncommitted,
  per `.planning/` gitignore constraint)

## Accomplishments

- Task 1: Added missing trailing newlines to 5 non-planning files and reformatted 5 markdown files via prettier — purely
  mechanical, zero content changes.
- Task 2: Added inline `shellcheck disable=SC2029`/`SC2012` suppressions with reason comments to the two throwaway Phase
  9 spike scripts, and quoted `$BRIDGE_PORT` in `test-install-provider.yml` to clear actionlint SC2086.
- Task 3: Fixed two real bugs — `VALID_MAP_TYPES` now includes `app_config` (terraform-bridge) alongside legacy
  `addon_config` (phone-logger); `verify-bridge-scaffold.sh`'s docker-image-size parser now uses a regex that handles
  both `"55.1 MB"` and `"55.1MB"` Docker size formats.

## Task Commits

Each task was committed atomically directly on `main`:

1. **Task 1: Mechanical auto-fixes — trailing newlines + markdown formatting** - `5f85217` (fix)
2. **Task 2: CI-config lint fixes — shellcheck suppressions + actionlint quoting** - `6366bb8` (fix)
3. **Task 3: Real bugs — validator map-type gap + docker-size regex parsing** - `87dc714` (fix)

_No separate plan-metadata commit — `.planning/` is gitignored in this repo, so STATE.md/SUMMARY.md are not committed._

## Files Created/Modified

- `internal/validate-addon-config.py` - Added `"app_config"` to `VALID_MAP_TYPES`
- `internal/verify-bridge-scaffold.sh` - Regex-based docker image size value/unit parsing (handles spaced and unspaced
  units)
- `internal/spike-h1-token-rotation.sh` - 2 inline `SC2029` suppressions (no logic change)
- `internal/spike-pitfalls10-backup-addon-config.sh` - 1 trailing newline + 5 inline `SC2029` + 1 inline `SC2012`
  suppressions (no logic change)
- `.github/workflows/test-install-provider.yml` - Quoted `"$BRIDGE_PORT"` in fixture-start `run:` block
- `.github/RELEASE.md`, `README.md`, `docs/DEVELOPMENT.md`, `docs/WEBHOOK_SETUP.md`, `terraform-bridge/DOCS.md` -
  Prettier reformatting only
- `terraform-bridge/internal/httpapi/handlers/version.go`, `terraform-provider-homeassistant/main.go`,
  `tools/test-bridge-fixture/go.mod`, `tools/test-bridge-fixture/main.go` - Trailing newline only

## Decisions Made

- **Prettier via direct npx instead of pre-commit hook:** The repo's pre-commit prettier hook
  (`JoC0de/pre-commit-prettier`) bootstraps by `npm install`-ing itself from a `git+file://` URL. This sandboxed
  environment's npm has `EALLOWGIT` fetch restrictions that reject non-root git-type package installs, so the hook
  errored before ever touching the target files. Ran `npx --yes prettier@3.9.6 --write/--check` directly against the
  same 5 files instead — both approaches read `.prettierrc.yaml` and produce identical output; verified with a clean
  `--check` pass afterward.
- **Standalone CLI tools via `uv tool install`:** `actionlint` and `shellcheck` aren't preinstalled in this environment;
  installed both as standalone `uv tool install` packages (`actionlint-py`, `shellcheck-py`) rather than relying on
  pre-commit's own hook-environment bootstrap for them, since the plan's verification commands invoke the CLIs directly
  (`shellcheck ...`, `actionlint ...`), not `pre-commit run`.

## Deviations from Plan

**1. [Rule 3 - Blocking] Substituted prettier's pre-commit hook invocation with direct `npx` invocation**

- **Found during:** Task 1
- **Issue:** `pre-commit run prettier --files ...` failed with `npm error code EALLOWGIT` — the hook's git-based
  self-install is blocked by this sandbox's npm policy, unrelated to the target files or repo config.
- **Fix:** Ran `npx --yes prettier@3.9.6 --write <files>` then `--check <files>` to confirm a clean pass. Same prettier
  version pinned in `.pre-commit-config.yaml` (`v3.9.6`), same `.prettierrc.yaml` config picked up automatically —
  output is equivalent to what the hook would have produced.
- **Files modified:** `.github/RELEASE.md`, `README.md`, `docs/DEVELOPMENT.md`, `docs/WEBHOOK_SETUP.md`,
  `terraform-bridge/DOCS.md`
- **Verification:** `npx --yes prettier@3.9.6 --check <files>` → "All matched files use Prettier code style!"
- **Committed in:** `5f85217` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — tooling substitution, no plan-scope change) **Impact on plan:** Zero
impact on the fix content; the plan's tool-driven, non-hand-edited constraint was honored by using the exact same
underlying prettier binary/config, just invoked directly instead of through pre-commit's git-bootstrapped wrapper.

## Issues Encountered

- `pre-commit`, `yamllint`, `shellcheck`, `actionlint` were not preinstalled in this environment. Installed via
  `uv tool install pre-commit`, `uv tool install yamllint`, `uv tool install shellcheck-py`, and
  `uv tool install actionlint-py` (all network-available, no slopsquat risk — well-known, widely-used PyPI wrapper
  packages for pinned upstream tools already referenced in this repo's own `.pre-commit-config.yaml`/Makefile).
- No `docker` binary in this environment — per the task constraints, item 6 (`verify-bridge-scaffold.sh`) was verified
  only via the standalone Python regex snippet specified in the plan's Task 3, not the real hook. Both `"55.1 MB"` and
  `"55.1MB"` produced identical byte counts (57776537), confirming the fix.
- `pre-commit install` (git hook) was never run in this environment (only `pre-commit run <hook> --all-files` was
  invoked directly), so plain `git commit` did not trigger pre-commit hooks automatically. All required verification was
  instead run manually and confirmed passing before each commit, per the plan's own verification steps.

## User Setup Required

None - no external service configuration required.

## Verification Results

All from repo root, matching the plan's `<verification>` block:

1. `pre-commit run end-of-file-fixer --all-files` → Passed (clean, no changes) after fix.
   `npx --yes prettier@3.9.6 --check <5 files>` → "All matched files use Prettier code style!" (substituted for the
   pre-commit prettier hook per the documented deviation above).
2. `shellcheck -e SC1091 -e SC2034 internal/spike-h1-token-rotation.sh internal/spike-pitfalls10-backup-addon-config.sh`
   → exit 0. `actionlint .github/workflows/test-install-provider.yml` → exit 0.
3. `python3 internal/validate-addon-config.py` → "Add-on config validation passed." (exit 0).
4. Standalone docker-size regex check: both `"55.1 MB"` and `"55.1MB"` → `57776537` (identical).
5. `make check-all` equivalents run individually: `yamllint -d relaxed` (repo-wide) → exit 0 (only pre-existing
   line-length warnings, out of scope); `shellcheck -e SC1091 -e SC2034` (repo-wide `*.sh`) → zero findings;
   `internal/validate-versions.sh` → "Version validation passed for all add-ons!". `verify-bridge-scaffold.sh` itself
   needs `docker` (unavailable here) — step 4 stands in, per the task's explicit constraint.
6. `git diff b11b5ad..HEAD -- terraform-bridge/` → only `DOCS.md` prettier formatting and a trailing newline in
   `version.go` — the `/data` mkdir / token-leak bug (item 7) was not touched.

## Next Phase Readiness

- `main` branch lint/CI state is now clean for all 6 originally diagnosed failures; open Renovate PRs #42-45 and future
  PRs should show accurate (non-pre-existing-noise) CI status once these commits are pushed.
- Item 7 (terraform-bridge `/data` mkdir / no-token-leak bug) remains open and untouched — deferred to a separate
  `/gsd:debug` session as instructed.
- Commits remain local on `main` (not pushed) — user to review and push per the task constraints.

---

_Quick task: 260901-na1_ _Completed: 2026-09-01_

## Self-Check: PASSED

All 5 modified source files and the SUMMARY.md confirmed present on disk; all 3 task commit hashes (`5f85217`,
`6366bb8`, `87dc714`) confirmed present in `git log --oneline --all`.
