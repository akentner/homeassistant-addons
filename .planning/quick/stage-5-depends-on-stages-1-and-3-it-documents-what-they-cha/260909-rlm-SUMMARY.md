---
phase: quick-260909-rlm
plan: 01
quick_id: 260909-rlm
subsystem: ci-documentation
status: complete
tags: [documentation-truth, ci, release-process, auto-update]
requires:
  - "260909-rlj (internal/dispatch-builds.sh + actions: write + BASE_SHA wiring)"
  - "260909-rll (--no-tag in auto-update.yml)"
provides:
  - ".github/RELEASE.md describing the real auto-update path, the real paths:-filter scope, and the real tag guarantee"
  - "docs/AUTO_UPDATE_GUIDE.md describing the shipped auto-update.yml"
affects:
  - "260909-rln (STAGE 6) — its two owned regions of .github/RELEASE.md are untouched"
tech-stack:
  added: []
  patterns:
    - "every mechanical documentation claim cites file + current line number"
    - "point-in-time counts carry a measurement date and a reproduce command"
key-files:
  created: []
  modified:
    - .github/RELEASE.md
    - docs/AUTO_UPDATE_GUIDE.md
decisions:
  - "Declined to document sibling rlk's internal/verify-image-availability.sh guard: neither of this item's two files documents the CI verification surface, and describing a script whose shape this item cannot verify would manufacture the exact unchecked claim the item exists to remove."
  - "Stated the tag/tree misalignment as 'an older version' rather than 'the previous version' — the measurement does not support the stronger claim."
  - "Cited the CURRENT auto-update.yml line numbers, not the plan's pre-dependency ones; the file grew from 131 to 171 lines when rlj and rll landed."
  - "Wrote no exclusivity claim about notify-ha.sh callers: sibling rlk added a second caller after the plan's environment was measured."
metrics:
  duration: ~30min
  completed: 2026-09-09
actuals:
  tokens: 6603
  tasks: 3
  commits: 1
  plan_head_before: 0e50dd9da6e8b9685a16c95b76b1651913a7e97a
---

# Quick 260909-rlm: CI Documentation Truth Pass Summary

Replaced the false claims in `.github/RELEASE.md` and the substantially fictional
`docs/AUTO_UPDATE_GUIDE.md` with statements checkable against the workflows as they stand after
260909-rlj and 260909-rll landed — including the measured 15-of-40 tag/tree misalignment that
proves the off-by-one lives in the documented manual procedure, not only in the bot.

## What Was Built

One commit, `0b1a00c`, two files, 222 insertions / 76 deletions.

### `.github/RELEASE.md` — 189 → 264 lines

| Item | Region | Change |
| --- | --- | --- |
| (c) | `## Tag schema` intro | one-tag-per-release scoped to the two manual paths |
| (c) | new `### What a tag guarantees` | the durable home for the tag truth (see below) |
| (d2) | the in-file-comment coverage clause | scoped to the six callers whose trigger is disabled; states that the three with an active `tags:` block carry no such comment |
| (b) | `### What this means operationally`, 1st para | `paths:`-filter claim scoped to a human push, plus the `GITHUB_TOKEN` caveat and a cross-reference to `## Auto-update path` |
| (c) | the double-build paragraph | the tag-triggered leg no longer "produces the canonical image for the tag"; it is the leg more likely to build stale content, because both legs read `build.yaml:args.VERSION` from whatever ref they check out |
| (d) | closing paragraph of the re-enable section | `The seven callers` → `The six callers` (one word, inside rln's region, as planned) |
| (a) | `## Auto-update path` | body replaced: not interchangeable with `make release`, for two named reasons |

`### What a tag guarantees` establishes, in order: the one-tag rule covers the manual paths only
(`base-image-update.yml` drives `internal/update-base-image.py`, which performs no git operations
at all; `auto-update.yml` passes `--no-tag` at line 123); a tag names an *intended* version because
`internal/update-version.py` tags `HEAD` at the `--no-tag` guard (`internal/update-version.py:425`)
and never commits the three files it edited, printing a suggested `git add` / `git commit` instead
(`internal/update-version.py:443`); the dated measurement (15 of 40 mismatched, 25 correct, with
`authentik/v2026.8.1`, `meridian/v1.59.0` and `terraform-bridge/v0.2.0` as the three examples);
a runnable `bash` reproduce block; and an explicit statement that reordering `make release` is not
done here.

### `docs/AUTO_UPDATE_GUIDE.md` — 160 → 231 lines

Rewritten against the shipped workflow. Fourteen fictional strings removed (parallel/matrix
processing, the `fail-fast` key, automatic GitHub issue creation in two places, the matrix status
view, both `workflow_dispatch` input names, the stale `fritz-callmonitor2mqtt` example, the fake
workflow name, the recommended `auto` version-pattern value, the unlimited-add-ons and
parallel-processing benefits, the issue-history claim, and the speculative webhook extension).

Replaced with the measured behaviour: the sequential `while IFS= read -r` loop
(`auto-update.yml:83`) over `find . -maxdepth 2 -name .upstream.yaml | sort`
(`auto-update.yml:157`); the per-step citations for `gh release view` (94), the `sed` strip (103),
`.args.VERSION` (106), `--no-tag` (123), the CHANGELOG block (135-150), the per-add-on commit
(154), the single push (166) and `exit $ERRORS` (171); the bare inputless `workflow_dispatch:` at
line 6 and the real workflow name `Auto Update`; a new section on the `GITHUB_TOKEN` no-trigger
limitation and the `internal/dispatch-builds.sh` dispatch with `actions: write`
(`auto-update.yml:49`); a `## 🏷️ Tags` section stating this path creates no tags; and a
`## 📋 What the workflow reads from .upstream.yaml` section naming the only two keys any code reads
plus the single real `version_pattern` reader (`internal/update-base-image.py:56` over
`internal/base-image-config.yaml`).

The `## 🔄 What happens automatically` heading, the `### 1. **Daily Check** (6:00 UTC)` heading and
its three bullets are byte-identical (L-6), verified by gates K1-K5.

## Verification Results

`make lint` required **one** reflow iteration: the first run failed with prettier reporting both
files modified, the second run passed all 21 hooks with rc=0 and left both files byte-identical
(gate `C2-converged`).

| Gate block | Checks | Result |
| --- | --- | --- |
| Task 1 (`.github/RELEASE.md`) | 40 | 40 PASS, 0 FAIL |
| Task 2 (`docs/AUTO_UPDATE_GUIDE.md`) | 47 | 47 PASS, 0 FAIL |
| Task 3 (lint convergence, paths, cross-refs) | 15 | 15 PASS, 0 FAIL |
| Task 1 + Task 2 re-run AFTER lint convergence | 87 | 87 PASS, 0 FAIL |

Notable gate values: `C4a-tokens-found` = 73 slash/extension tokens extracted,
`C4-no-invented-paths` = 0 missing; `X1-table-rows` = 9 (rln's tag-trigger table intact);
`X2-reenable-steps` = 1 (rln's re-enable steps intact); `H1-history-seven` = 1 (the historical
"all seven" statement about commit `287c79f` preserved); `C12-scope` = 0 files changed outside the
two declared markdown files.

The published reproduce block was executed before publication and returns exactly 15 MISMATCH
lines against the current tree.

## Deviations from Plan

The plan's `<verified_environment>` was measured before 260909-rlj and 260909-rll landed. Four
claims it authorised are no longer accurate against the tree, and the plan's own L-3 ("every claim
must be checkable against the file it describes") required using the measured value instead.

**1. [Rule 1 - stale fact] "each at the previous version" → "an older version"**

- **Found during:** Task 1, before writing the (c) subsection.
- **Issue:** the plan's `<verified_environment>` and its Task 1 action both instruct stating that
  the 15 mismatched tags each point at "the previous version".
- **Evidence:** the audit output shows `meridian/v1.62.5` → tree `1.62.3`, `meridian/v1.64.0` →
  tree `1.62.7`, and both `meridian/v1.67.0-0` and `meridian/v1.68.0-0` → tree `1.66.0`. Those are
  not the immediately-previous version, so the stronger claim is unsupported.
- **Fix:** wrote "is an older version than the tag names". The two numbers the plan does require
  (15 mismatched, 25 correct) are stated exactly, per L-5.

**2. [Rule 1 - stale fact] auto-update.yml line numbers**

- **Found during:** Task 1 `read_first`.
- **Issue:** the plan cites the loop at 55, `find` at 123, the two keys at 62-63, `gh release view`
  at 66, the `sed` strip at 75, `build.yaml` at 78, `update-version.py` at 89, the CHANGELOG block
  at 101-116, the commit at 120, the push at 127 and `exit $ERRORS` at 131. The file is now 171
  lines, not 131, because rlj added the `actions: write` scope, the `BASE_SHA` capture, the
  `GITHUB_TOKEN` NOTE and the dispatch call, and rll added the concurrency block and `--no-tag`.
- **Fix:** cited the current numbers throughout both documents — loop 83, keys 90-91,
  `gh release view` 94, `sed` 103, `.args.VERSION` 106, `--no-tag` 123, CHANGELOG 135-150, commit
  154, `find` 157, push 166, dispatch 167, `exit $ERRORS` 171, plus `workflow_dispatch:` 6,
  concurrency 32-34, `actions: write` 49 and `BASE_SHA` 77.

**3. [Rule 1 - stale fact] `internal/update-version.py` line numbers**

- **Issue:** the plan cites "line 418 guard → `create_and_push_tag`" and "line 436 prints a
  suggested `git add` / `git commit`".
- **Evidence:** `grep -n 'no_tag\|create_and_push_tag\|Commit: git add' internal/update-version.py`
  puts the guard at 425 and the commit hint at 443.
- **Fix:** cited 425 and 443.

**4. [Rule 2 - avoided an unsupportable claim] no exclusivity claim about `notify-ha.sh`**

- **Issue:** the plan's environment states the script's callers are "only `_build-template.yml`
  (lines 134, 199)" and item 10 is written from that.
- **Evidence:** `grep -rn 'notify-ha.sh' .github/workflows/` now also returns
  `verify-image-availability.yml:103` (added by sibling rlk), and the `_build-template.yml` call
  sites moved to 142 and 207.
- **Fix:** wrote that `auto-update.yml` sends no webhook and that `_build-template.yml` calls the
  script, with no "only" and no line numbers. Neither statement can go stale from another
  caller appearing.

Sentence-level rewording that is not a factual deviation: the (d2) clause was restructured to
"In the six callers whose tag trigger is disabled, the `tags:` block holds the in-file comment …"
rather than patched in place, because the original clause order could not be scoped without
reading awkwardly. It satisfies gates `E1-clause-rescoped` (0) and `E2-scoped-to-six` (1).

## Decision Held: rlk's Image-Availability Guard Not Documented

Sibling 260909-rlk landed `internal/verify-image-availability.sh` and
`.github/workflows/verify-image-availability.yml`. This item deliberately does not mention them.
Neither `.github/RELEASE.md` nor `docs/AUTO_UPDATE_GUIDE.md` documents the CI verification surface,
rlk's own plan owns its documentation, and describing a script whose behaviour this item did not
verify would manufacture exactly the class of unchecked claim the item exists to remove. Recorded
as a decision, not a gap.

## Ownership Boundary Respected

Sibling 260909-rln owns the 9-row per-caller tag-trigger table and the `### Re-enabling a tag
trigger` steps. Both survive unchanged (`X1-table-rows` = 9, `X2-reenable-steps` = 1). The only
edit inside rln's region is the single word `seven` → `six` on the closing paragraph, exactly as
the plan specified, so a later rewrite of that paragraph discards it harmlessly.

## Known Stubs

None. No stub values, placeholder text, skipped tests or unrun `<verify>` blocks were introduced.
All three task gate blocks were executed to completion.

## Threat Flags

None. Documentation-only change; no executable, workflow, container, network listener or credential
handling was touched. Only the `GITHUB_TOKEN` name and its already-public no-trigger behaviour were
written — no secret value, webhook ID or HA URL was added.

## Self-Check: PASSED

- `.github/RELEASE.md` — FOUND, 264 lines
- `docs/AUTO_UPDATE_GUIDE.md` — FOUND, 231 lines
- commit `0b1a00c` — FOUND on `worktree-agent-acb8afebaff9a1cac`
- `git rev-list --count 0e50dd9..HEAD` = 1 (matches `actuals.commits`)
- `git status --short` — clean, no untracked files
- `git diff --diff-filter=D --name-only HEAD~1 HEAD` — empty, no deletions
