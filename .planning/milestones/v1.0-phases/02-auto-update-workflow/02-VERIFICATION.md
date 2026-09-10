---
phase: 02-auto-update-workflow
verified: 2026-04-04T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 02: Auto-Update Workflow Verification Report

**Phase Goal:** A daily GitHub Actions workflow detects upstream releases and commits version updates to main without
manual intervention. **Verified:** 2026-04-04 **Status:** ✓ PASSED **Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                     | Status     | Evidence                                                                                                                                                                          |
| --- | ----------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Workflow runs daily at 06:00 UTC and on workflow_dispatch                                 | ✓ VERIFIED | `cron: "0 6 * * *"` at line 5; `workflow_dispatch:` at line 6                                                                                                                     |
| 2   | Each add-on with .upstream.yaml is checked for a new upstream release                     | ✓ VERIFIED | `find . -maxdepth 2 -name .upstream.yaml \| sort` (line 85); both `fritz-callmonitor2mqtt` and `phone-logger` discovered dynamically                                              |
| 3   | When a new version is found, all three version files are updated and committed to main    | ✓ VERIFIED | `python3 scripts/update-version.py "$addon_name" "$latest_version"` (line 68); `git add config.yaml build.yaml README.md` (line 81); `git commit` (line 82); `git push` (line 89) |
| 4   | When already up to date, no commit is produced (no empty commits)                         | ✓ VERIFIED | Version compare at line 59 (`continue` if equal); `git diff --quiet` at line 75 (`continue` if no changes); `UPDATES_MADE` gate on push (line 88)                                 |
| 5   | If one add-on's upstream check fails, the error is logged and remaining add-ons processed | ✓ VERIFIED | `ERRORS=1; continue` at lines 48–49 (fetch failure) and lines 70–71 (update-version.py failure); loop continues to next add-on                                                    |
| 6   | Job exits non-zero if any per-addon error occurred                                        | ✓ VERIFIED | `exit $ERRORS` at line 93; `ERRORS` accumulates any per-addon failure count                                                                                                       |
| 7   | Only GITHUB_TOKEN is used — no PAT or additional secrets required                         | ✓ VERIFIED | `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (line 28); `permissions: contents: write` at job level (line 12); no other `secrets.` references                                          |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact                            | Provides                       | Exists | Substantive              | Wired                                                       | Status     |
| ----------------------------------- | ------------------------------ | ------ | ------------------------ | ----------------------------------------------------------- | ---------- |
| `.github/workflows/auto-update.yml` | Scheduled auto-update workflow | ✓      | ✓ (93 lines, full logic) | ✓ (invoked by GitHub Actions scheduler + workflow_dispatch) | ✓ VERIFIED |

**Artifact detail:** File contains the full implementation — triggers, permissions, git identity setup, discovery loop,
gh release fetch, version compare, update-version.py invocation, change detection, staging, commit, push, and error
fail-safe. No stubs or placeholder sections found.

---

### Key Link Verification

| From                                | To                          | Via                                                                 | Status  | Details                                                                                                                                                                                    |
| ----------------------------------- | --------------------------- | ------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.github/workflows/auto-update.yml` | `scripts/update-version.py` | `python3 scripts/update-version.py "$addon_name" "$latest_version"` | ✓ WIRED | Line 68; script exists at `scripts/update-version.py`; CLI interface matches (positional args: `addon_name`, `new_version`)                                                                |
| `.github/workflows/auto-update.yml` | `{addon}/.upstream.yaml`    | `find . -maxdepth 2 -name .upstream.yaml`                           | ✓ WIRED | Line 85; both `fritz-callmonitor2mqtt/.upstream.yaml` and `phone-logger/.upstream.yaml` discovered; `upstream.repository` and `upstream.version_strip` fields read correctly via `yq eval` |
| `.github/workflows/auto-update.yml` | `git push` (to main)        | `GITHUB_TOKEN` with `contents: write` permission                    | ✓ WIRED | `permissions: contents: write` at line 11–12; `git push` at line 89; gated by `UPDATES_MADE` flag                                                                                          |

---

### Data-Flow Trace (Level 4)

This phase produces a GitHub Actions workflow (not a data-rendering component). Level 4 data-flow trace is applied to
the core logic path instead of a UI component:

| Step                | Variable          | Source                                                                 | Produces Real Data                                  | Status    |
| ------------------- | ----------------- | ---------------------------------------------------------------------- | --------------------------------------------------- | --------- |
| Upstream repo       | `upstream_repo`   | `yq eval '.upstream.repository'` from `.upstream.yaml`                 | ✓ Non-null (e.g. `akentner/fritz-callmonitor2mqtt`) | ✓ FLOWING |
| Version strip regex | `version_strip`   | `yq eval '.upstream.version_strip'` from `.upstream.yaml`              | ✓ Non-null (e.g. `^v`)                              | ✓ FLOWING |
| Latest release tag  | `latest_tag`      | `gh release view --repo "$upstream_repo" --json tagName --jq .tagName` | ✓ Real GitHub API call                              | ✓ FLOWING |
| Stripped version    | `latest_version`  | `echo "$latest_tag" \| sed "s/${version_strip}//"`                     | ✓ Derived from real tag                             | ✓ FLOWING |
| Current version     | `current_version` | `yq eval '.args.VERSION' "$addon_dir/build.yaml"`                      | ✓ Real file read                                    | ✓ FLOWING |
| Update result       | (exit code)       | `python3 scripts/update-version.py "$addon_name" "$latest_version"`    | ✓ Writes to all 3 version files                     | ✓ FLOWING |

No static returns or hardcoded empty values in any data path.

---

### Behavioral Spot-Checks

Runtime execution requires a GitHub Actions environment with `gh` CLI credentials and an upstream repo with releases.
Cannot be run in the local shell without a live GitHub session. Verified structurally instead:

| Behavior                                   | Verification Method                           | Result                                                                                           | Status |
| ------------------------------------------ | --------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------ |
| yamllint passes                            | `yamllint auto-update.yml`                    | Exit 0, no errors                                                                                | ✓ PASS |
| pre-commit (actionlint via hook) passes    | `pre-commit run --files ...`                  | All hooks passed                                                                                 | ✓ PASS |
| `.upstream.yaml` fields match yq queries   | Manual schema verification                    | `upstream.repository`, `upstream.version_strip`, `addon.version_pattern` present in both add-ons | ✓ PASS |
| `update-version.py` CLI matches invocation | `grep add_argument scripts/update-version.py` | Positional args `addon_name`, `new_version` match workflow call                                  | ✓ PASS |
| Commits exist in git log                   | `git log --oneline`                           | `3041179` (create workflow), `3b67321` (SC2001 fix) both present                                 | ✓ PASS |

---

### Requirements Coverage

| Requirement | Description                                                  | Status      | Evidence                                                                                            |
| ----------- | ------------------------------------------------------------ | ----------- | --------------------------------------------------------------------------------------------------- |
| AUTO-01     | Daily cron + gh release view to check each add-on's upstream | ✓ SATISFIED | `cron: "0 6 * * *"` (line 5); `gh release view --repo "$upstream_repo"` (line 46)                   |
| AUTO-02     | update-version.py called to sync 3-file version set          | ✓ SATISFIED | `python3 scripts/update-version.py "$addon_name" "$latest_version"` (line 68)                       |
| AUTO-03     | Updated files committed directly to main (no PR)             | ✓ SATISFIED | `git commit` (line 82) + `git push` (line 89); no PR step present                                   |
| AUTO-04     | Skip commit when no version change detected                  | ✓ SATISFIED | Version equality check (line 59) + `git diff --quiet` guard (line 75)                               |
| AUTO-05     | GITHUB_TOKEN only — no additional secrets                    | ✓ SATISFIED | Only `secrets.GITHUB_TOKEN` referenced (line 28); `permissions: contents: write` grants push access |

**Orphaned requirements:** None. All 5 requirements declared in PLAN frontmatter are accounted for. No additional Phase
2 requirements found in REQUIREMENTS.md traceability table.

---

### Anti-Patterns Found

| File                                | Line | Pattern                                                                   | Severity | Impact                                                                                                                                                          |
| ----------------------------------- | ---- | ------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.github/workflows/auto-update.yml` | 67   | `# Do NOT pass --check-release` (comment)                                 | ℹ️ Info  | None — this is a protective documentation comment explaining why `--check-release` must NOT be used in CI. The actual invocation at line 68 correctly omits it. |
| `.github/workflows/auto-update.yml` | 80   | `# Stage only the three known version files (never git add -A)` (comment) | ℹ️ Info  | None — protective documentation comment. Actual `git add` at line 81 correctly lists specific files.                                                            |

**No blocker or warning anti-patterns found.**

- No `return null` / `return {}` / `return []` stubs
- No TODO/FIXME/PLACEHOLDER comments
- No hardcoded add-on list (discovery is dynamic via `find`)
- No `git add -A` in actual code (only in a comment)
- No `--check-release` in actual invocation (only in a warning comment)
- No extra secrets beyond `GITHUB_TOKEN`

---

### Human Verification Required

#### 1. End-to-End Trigger Test (Up-to-Date Case)

**Test:** In the GitHub Actions UI, trigger the workflow manually via `workflow_dispatch` when all add-ons are already
at their current upstream versions. **Expected:** Workflow completes with exit 0, log shows
`INFO: {addon} already at {version}, skipping` for each add-on, no commit is produced in the repository. **Why human:**
Requires live GitHub Actions environment with `gh` CLI authenticated via `GITHUB_TOKEN` and active upstream
repositories.

#### 2. End-to-End Trigger Test (New Version Case)

**Test:** Simulate a new upstream release by temporarily setting `current_version` in `build.yaml` to an older version,
then triggering `workflow_dispatch`. **Expected:** Workflow detects the version delta, calls `update-version.py`,
commits `chore({addon}): update to {version}` to main, and pushes. **Why human:** Requires a live GitHub environment and
would mutate the repository.

#### 3. Error Isolation Behavior

**Test:** Modify `.upstream.yaml` for one add-on to reference a non-existent repository, trigger `workflow_dispatch`.
**Expected:** Workflow logs `ERROR: could not fetch release for {bad_repo}`, continues processing other add-ons, exits
with non-zero code, and GitHub Actions UI shows the run as failed. **Why human:** Requires a live GitHub Actions
environment; the error path involves the `gh` CLI exit code and `ERRORS=1` accumulation.

---

### Gaps Summary

No gaps found. All 7 observable truths are verified, all 5 requirements are satisfied, key links are wired, and data
flows through real sources. The workflow passes `yamllint` and pre-commit (including actionlint via hook). The only
items deferred to human verification are live end-to-end execution tests that require a live GitHub Actions environment
with `GITHUB_TOKEN`.

---

_Verified: 2026-04-04_ _Verifier: the agent (gsd-verifier)_
