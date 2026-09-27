---
phase: quick-260927-wzn
plan: 260927-wzn
subsystem: infra
tags: [python, bash, git, shellcheck, make, update-version, ci]

# Dependency graph
requires: []
provides:
  - "internal/update-version.py no longer tags a commit that doesn't contain the version bump it names"
  - "internal/verify-update-version-tag-timing.sh regression test wired into make check-all"
  - "docs/UPDATE_VERSION.md + docs/DEVELOPMENT.md describe the corrected commit-before-tag ordering"
affects: [internal/update-version.py, make check-all, docs/UPDATE_VERSION.md, docs/DEVELOPMENT.md]

# Actuals (#2632)
actuals:
  tokens: 4700
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "git status --porcelain scoped to a fixed file list, used as a commit-precondition gate before a destructive/irreversible git operation (tagging)"
    - "RED-before-GREEN regression test proven against a saved pre-fix copy of the script under test, via an env-var override (UPDATE_VERSION_PY) rather than a git checkout of history"

key-files:
  created:
    - internal/verify-update-version-tag-timing.sh
  modified:
    - internal/update-version.py
    - Makefile
    - docs/UPDATE_VERSION.md
    - docs/DEVELOPMENT.md

key-decisions:
  - "files_have_uncommitted_changes() checks git status --porcelain scoped to exactly the version files (config.yaml/build.yaml/README.md, plus terraform-bridge's co-located Provider build.yaml) so an unrelated dirty file elsewhere in the tree never blocks or falsely permits tagging"
  - "Deferred-tag path exits 0 (not 1) — the file edits still succeeded; only the irreversible/networked tag+push step is withheld until the tree is provably clean"
  - "Regression test script defines cleanup() with a `# shellcheck disable=SC2317` (matching this repo's existing SC2029/SC2012 inline-disable convention) — pre-commit's pinned shellcheck-py v0.10.0.1 flags a trap-only-invoked function as unreachable; this is a known false positive, not a real issue"

requirements-completed: []

coverage:
  - id: D1
    description: "update-version.py refuses to tag while the version-bump files it just wrote are uncommitted, and tags correctly once they're committed"
    verification:
      - kind: other
        ref: "internal/verify-update-version-tag-timing.sh (bash script, proven RED against pre-fix copy, GREEN against fixed script)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Regression test wired into make check-all so this class of bug cannot silently regress"
    verification:
      - kind: other
        ref: "make check-all"
        status: pass
    human_judgment: false
  - id: D3
    description: "docs/UPDATE_VERSION.md and docs/DEVELOPMENT.md describe the corrected commit-before-tag flow"
    verification:
      - kind: other
        ref: "make lint (prettier/markdownlint on both files)"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-09-28
status: complete
---

# Quick Task 260927-wzn: Fix `internal/update-version.py` Tag-Timing Bug Summary

**`update-version.py` now defers git-tag creation until the version-bump files it just wrote are committed, closing the exact bug that mis-tagged `cups/v0.1.0-12` and `cups/v0.1.0-13` in the same day — proven via a RED-before-GREEN regression test wired into `make check-all`.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3/3
- **Files modified:** 4 (1 created: `internal/verify-update-version-tag-timing.sh`)

## Accomplishments

- Added `files_have_uncommitted_changes()` to `internal/update-version.py` and branched `main()`'s tag-decision tail on it: a dirty working tree (for exactly `config.yaml`/`build.yaml`/`README.md`, plus `terraform-bridge`'s co-located Provider `build.yaml`) defers tagging with a clear "commit first, then re-run" message instead of tagging the stale pre-bump commit
- Wrote `internal/verify-update-version-tag-timing.sh`, a pure-git/no-Docker/no-network regression test using a throwaway `mktemp -d` repo, and proved it RED against a saved pre-fix copy of the script (exact failing assertions below) before proving it GREEN against the fixed script
- Wired the new test into `Makefile`'s `check-all` target (plus `.PHONY`) so the tag-timing invariant is enforced on every `make check-all` run going forward
- Corrected `docs/UPDATE_VERSION.md` (new "Commit-before-tag ordering" section, updated "What the tool does" bullet, "No-op behaviour" note, and worked example with the missing commit step) and `docs/DEVELOPMENT.md`'s pointer sentence to describe the fixed two-step commit-then-tag flow

## Task Commits

Each task was committed atomically:

1. **T1: Fix the tag-timing bug in `internal/update-version.py`** - `c2c0d57` (fix)
2. **T2: Regression test proving the fix + wire into `make check-all`** - `56df260` (test)
3. **T3: Correct `docs/UPDATE_VERSION.md` and `docs/DEVELOPMENT.md`** - `79fce8b` (docs)

_Note: Docs artifacts (this SUMMARY, STATE.md) are committed separately by the orchestrator, not part of these task commits._

## RED Proof (T2, mandatory before trusting the test)

Ran `UPDATE_VERSION_PY=<pre-fix-copy> bash internal/verify-update-version-tag-timing.sh` against the unmodified pre-fix script (saved to the session scratchpad before any T1 edit). It exited **1** with exactly the expected failures:

```
[0;31mFAIL: script did not report refusing to tag on a dirty working tree[0m
[0;31mFAIL: tag fakeaddon/v1.0.0-1 exists after the uncommitted run -- this is the exact bug[0m
...
[0;31mFAIL: tag points at <initial-sha>, expected the bump commit <bump-sha>[0m
[0;31mFAIL: the tagged commit's config.yaml reads 'version: "1.0.0-0"', not 1.0.0-1[0m

[0;31mSOME CHECKS FAILED[0m
exit=1
```

This is the exact real-world failure mode from `260927-r2j`/`260927-vbk`: a tag was created and pushed against a commit whose `config.yaml` still read the OLD version. The test genuinely catches the bug, not a test that would have passed regardless.

## GREEN Proof (against the fixed script)

```
[0;32mPASS: script refused to tag while version files are uncommitted[0m
[0;32mPASS: no tag was created while the bump was uncommitted[0m
[0;32mPASS: tag fakeaddon/v1.0.0-1 now exists[0m
[0;32mPASS: tag points at the bump commit (<sha>), not the stale initial commit[0m
[0;32mPASS: the tagged commit's config.yaml actually contains 1.0.0-1[0m

[0;32mALL CHECKS PASSED[0m
exit=0
```

`make check-all` (all validators: lint, validate-addons, validate-versions, validate-dockerfiles, verify-update-version-tag-timing) exits 0 end to end.

## Files Created/Modified

- `internal/update-version.py` - new `files_have_uncommitted_changes()` helper; `main()`'s tag-decision tail defers tagging while version files are uncommitted, tags correctly once clean
- `internal/verify-update-version-tag-timing.sh` - new regression test (pure git, temp repo, no Docker/network), executable
- `Makefile` - new `verify-update-version-tag-timing` target, added to `.PHONY` and `check-all`
- `docs/UPDATE_VERSION.md` - new "Commit-before-tag ordering" section (with the `260927-r2j`/`260927-vbk` incident history), corrected worked example, updated "What the tool does" bullet and "No-op behaviour" note
- `docs/DEVELOPMENT.md` - "Version Update Tool" pointer section links to the new section

## Decisions Made

- `files_have_uncommitted_changes()` is scoped to exactly the version files per add-on (not a blanket `git status --porcelain` on the whole tree) so an unrelated in-progress edit elsewhere never blocks or falsely permits tagging
- The deferred-tag path returns exit code 0, not 1 — the file edits themselves still succeeded; only the tag+push step (irreversible once pushed) is withheld
- Existing-tag skip/never-force-push logic inside `create_and_push_tag()`, the argparse surface, and the `terraform-bridge` → Provider cross-artifact bump were left untouched per the plan's explicit scope boundary

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] shellcheck SC2317 false positive on the trap-only `cleanup()` function**
- **Found during:** Task 2 (first commit attempt for `internal/verify-update-version-tag-timing.sh`)
- **Issue:** pre-commit's pinned `shellcheck-py` v0.10.0.1 flagged `cleanup()` (invoked only indirectly via `trap cleanup EXIT`) as "Command appears to be unreachable" — a well-known shellcheck false positive for trap-only functions, blocking the commit
- **Fix:** Reformatted `cleanup()` to a multi-line body (matching this repo's other `verify-*.sh` scripts) and added `# shellcheck disable=SC2317 # intentional: only invoked indirectly via trap ... EXIT below`, following the exact inline-disable convention already used elsewhere in `internal/` (e.g. `# shellcheck disable=SC2029` in `spike-h1-token-rotation.sh`)
- **Files modified:** `internal/verify-update-version-tag-timing.sh`
- **Verification:** Re-ran `pre-commit run shellcheck --files internal/verify-update-version-tag-timing.sh` (Passed); re-ran both the RED proof (still failed identically against the pre-fix copy) and the GREEN proof (still `ALL CHECKS PASSED`) to confirm the reformatting didn't change test behavior
- **Committed in:** `56df260` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to get a clean commit through the repo's pre-commit gate; no behavioral change to the test itself — purely a shellcheck-satisfying reformat plus a documented, precedented suppression.

## Issues Encountered

None beyond the shellcheck deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `internal/update-version.py` is safe to use for any future `make update-version` invocation; the two-step commit-then-tag flow is now the documented and enforced default
- The still-outstanding real-world mis-pointing of `cups/v0.1.0-13` (flagged in `260927-vbk`'s SUMMARY) is explicitly out of scope for this task — it remains a one-off manual cleanup for the operator
- No CI workflow changes were needed or made; `.github/workflows/auto-update.yml` already passes `--no-tag` (from `260909-rll`) and is unaffected

---

## Self-Check: PASSED

- FOUND: internal/update-version.py
- FOUND: internal/verify-update-version-tag-timing.sh (executable)
- FOUND: docs/UPDATE_VERSION.md
- FOUND: docs/DEVELOPMENT.md
- FOUND: commit c2c0d57 (T1)
- FOUND: commit 56df260 (T2)
- FOUND: commit 79fce8b (T3)

_Quick task: 260927-wzn_
_Completed: 2026-09-28_
