---
phase: quick-260909-rll
plan: 01
quick_id: 260909-rll
subsystem: ci-cd
status: complete
tags: [github-actions, versioning, concurrency, git-tags, auto-update]
requires:
  - "260909-rlj (landed as 6fbe7a4): actions: write + build dispatch after git push in both bump workflows"
provides:
  - "auto-update.yml creates no git tag at all (--no-tag on the single non-comment update-version.py call)"
  - "shared repo-scoped concurrency group `addon-version-bump` across both version-bump workflows"
  - "update-version.py tag-push output and create_and_push_tag docstring state the tags:-trigger conditional instead of asserting a build"
affects:
  - "260909-rlm (STAGE 5): documents this end state in .github/RELEASE.md and docs/AUTO_UPDATE_GUIDE.md"
  - ".github/RELEASE.md is now cited from two places in internal/update-version.py — its per-add-on tags:-trigger table is load-bearing operator documentation"
tech-stack:
  added: []
  patterns:
    - "opt-out CLI flag used to suppress a side effect in CI while keeping it default-on for the local make release path"
    - "repo-scoped GitHub concurrency group shared by name across two workflows to make them mutually exclusive"
    - "flanking sha256 region pins around a small edit window, instead of one whole-region pin, to bound what an edit may touch"
key-files:
  created: []
  modified:
    - .github/workflows/auto-update.yml
    - .github/workflows/base-image-update.yml
    - internal/update-version.py
decisions:
  - "auto-update.yml passes --no-tag rather than relocating the tag call to after the git commit: actions/checkout@v7 fetches no tags, so a combined tag-and-branch push would be rejected non-atomically for an already-existing remote tag, return non-zero, and abort the step under set -e BEFORE the build dispatch runs — a real regression on the critical path, traded for a tag with no live consumer."
  - "git push --follow-tags explicitly rejected for the same reason; the rejection is documented at the call site so the next reader does not re-derive it."
  - "The 15-of-40 mis-pointing <addon>/v* tags already on origin are left in place — this item does not rewrite or delete published refs."
  - "The shared group is named addon-version-bump (not auto-update) so a third version-bumping workflow added later joins on merit rather than inheriting one workflow's name."
  - "cancel-in-progress: false is mandatory on both sides — true would let base-image-update abort an in-flight auto-update mid-push."
metrics:
  duration: ~25m
  completed: 2026-09-09
  tasks: 3
  files: 3
actuals:
  tokens: 8000        # chars/4 over the three files actually changed (31,982 chars)
  tasks: 3
  commits: 1          # MEASURED: git rev-list --count c495cbc..HEAD
  plan_head_before: c495cbc5e494d83759f94cb347fd600353f884b3
---

# Quick 260909-rll: Stop auto-update tagging the pre-bump commit + serialize both bump workflows Summary

`auto-update.yml` no longer creates any git tag (`--no-tag`), `update-version.py` no longer claims a pushed tag produces
a build, and both version-bump workflows now share the repo-scoped concurrency group `addon-version-bump`.

## What Was Built

Three edited files, one commit (`ce932fa`), per L-12.

### Task 1 — `auto-update.yml` stops tagging the pre-bump commit (tracer)

The single non-comment `internal/update-version.py` invocation now carries `--no-tag`. That call runs **before** the
`git commit` further down the per-add-on loop, so `HEAD` at that point is still the pre-bump commit; `update-version.py`
tagged that `HEAD`, putting every automated tag on the wrong commit.

A 6-line rationale comment sits immediately above the call (12-space indent, inside the `run: |` block) recording:
the pre-bump ordering, the measured proof, the out-of-band release path (`.github/RELEASE.md`), and the rejected
`git push --follow-tags` alternative.

The measured proof, cited verbatim in the comment — note the skew is **two** versions, not one:

| tag | commit | `meridian/build.yaml` VERSION at that commit |
|---|---|---|
| `meridian/v1.67.0-0` | `8c31d33` | `1.66.0` |
| `meridian/v1.68.0-0` | `9f45b96` | `1.66.0` |

The comment therefore says "an older version", never "the previous version".

### Task 2 — `update-version.py` stops asserting a build follows the tag push

- Tag-push success output: `🚀 Pushed tag: {tag} → build workflow will trigger` became the tag name plus the actual
  conditional (a build runs only where `build-<addon>.yml` has an active `tags:` trigger — three of nine do) with a
  pointer to `.github/RELEASE.md`.
- `create_and_push_tag` docstring: the `paths:`-on-push-to-main trigger (all nine add-ons) and the `tags:` trigger on
  `<addon>/v*` (only iac-runner, network-tools, terraform-bridge) are now named separately instead of conflated, and the
  false claim that the tag is what makes the image resolvable in ghcr.io is gone.

Behaviour is unchanged: argparse surface byte-identical, `create_and_push_tag`'s signature byte-identical, `--no-tag`
still opt-out and still accepted before and after the two positionals.

### Task 3 — one shared concurrency group across both bump workflows

- `auto-update.yml`: `group: auto-update` → `group: addon-version-bump`.
- `auto-update.yml`: the existing 12-line rationale comment was **extended** (lines 8-19 byte-identical and contiguous,
  12 lines appended after them). The extension explains the sharing and, per the plan, reconciles the frozen paragraph
  it follows: since this workflow now passes `--no-tag` and creates no tag at all, the frozen `<addon>/v<version>`
  tag-collision sentence at lines 17-19 is labelled as a history note rather than a live claim, pointing at the
  call-site comment for why.
- `base-image-update.yml`: a workflow-level `concurrency` block (`group: addon-version-bump`,
  `cancel-in-progress: false`) with an 8-line rationale comment, inserted after `on:` and above `jobs:`. This workflow
  had **no** concurrency protection at all before, so it could race `auto-update.yml`'s `git push`.

`internal/update-base-image.py` contains no git operations, so `base-image-update.yml` has never produced a tag.
Dropping auto-update's tag makes the two workflows consistent: both push an untagged bump commit and then explicitly
request a build.

## Verification Results

All 20 gates across the three tasks pass, re-run on the committed tree.

| Gate | Result | Note |
|---|---|---|
| GATE-T1-A | PASS | 1 non-comment `update-version.py` line, and it carries `--no-tag` |
| GATE-T1-B | PASS | Region A sha256 `c1d95350…cecd20` — byte-identical to pre-change baseline |
| GATE-T1-C | PASS | Region B sha256 `bfa308db…9b4ec6` — byte-identical to pre-change baseline |
| GATE-T1-D | PASS | whole-loop sha256 **differs** from rlj's pin — positive proof the edit landed at the intended site |
| GATE-T1-E | PASS | both anchor comments byte-identical |
| GATE-T1-F | PASS | call at line 123; contiguous comment run `r=8` (2 frozen anchors + 6 inserted), within the derived 3..8 window; run contains `pre-bump` and `RELEASE.md` |
| GATE-T1-G | PASS | 0 `follow-tags` on non-comment lines; all re-asserted rlj auto-update invariants (`d==p+1`, `k==d+1`, `d<e`, `b<w`) hold |
| GATE-T2-A | PASS | `will trigger` 0, `tag is required` 0, `RELEASE.md` ≥2, `Pushed tag: {tag}` exactly 1 |
| GATE-T2-B | PASS | docstring hash differs from `1f1d918d…`; contains `paths:`, `tags:`, `RELEASE.md`, `Returns True on success` |
| GATE-T2-C | PASS | signature + all four `add_argument` declarations byte-identical |
| GATE-T2-D | PASS | `py_compile` clean; `--help` still lists `--no-tag` |
| GATE-T2-E | PASS | `--no-tag` parses before AND after the positionals; `git status --porcelain -- meridian` empty afterwards |
| GATE-T3-A | PASS | single top-level `concurrency:`, `group: addon-version-bump`, `cancel-in-progress: false` |
| GATE-T3-B | PASS | frozen block starts at line 8 (`s == c-k`, proving append-after not prepend-before), lines 8-19 hash `0540d26f…13eb0`, run length `k=24 > 12`, appended lines contain `no-tag` |
| GATE-T3-C | PASS | `concurrency:` at 16 < `jobs:` at 20, 8 rationale lines (≥4) |
| GATE-T3-D | PASS | both files' `group:` lines byte-identical |
| GATE-T3-E | PASS | exactly one `GH_TOKEN` match remains in base-image-update.yml, still inside the step `env:` |
| GATE-T3-J | PASS | neither added comment block contains any L-10 forbidden literal |
| GATE-T3-F | PASS | rlj base-image ordering invariants intact |
| GATE-T3-G | PASS | base-image loop pin `2dace2d5…419cc` intact — nothing inside `jobs:` changed |
| GATE-T3-H | PASS | actionlint v1.7.3 (pre-commit, all files) + yamllint on both workflows |
| GATE-T3-I | PASS | latest-release actionlint 1.7.12, rc=0 |

Plan-level verification:

| Check | Result |
|---|---|
| `make validate-versions` | rc=0 |
| `make lint` (`pre-commit run --all-files`) | rc=0, all 21 hooks Passed |
| `python3 -m py_compile internal/update-version.py` | rc=0 |
| latest actionlint (1.7.12, verbose) | 0 errors in 17 files, both edited workflows confirmed linted |
| `git diff --stat` | exactly the three declared paths, 45 insertions / 8 deletions |
| commit count | 1 (`ce932fa`), measured from ledger base `c495cbc` |
| deletions in commit | none |
| untracked files | none |

## Sibling Supersession — rlj GATE-T1-14 is expected RED

**A verifier re-running 260909-rlj's gate set will see `GATE-T1-14` fail. This is intentional and is not a defect.**

rlj pinned the sha256 of `auto-update.yml`'s whole per-add-on loop region to
`7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc`, asserting rlj's own edits stayed outside that loop.
`auto-update.yml`'s `update-version.py` call — the line this item had to change — sits **inside** that region, so the
pin could not survive.

Measured transition, both values verified on this tree:

| | loop-region sha256 |
|---|---|
| before this item (rlj's pin, green at rlj's commit) | `7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc` |
| after this item | `cdaa8113a8f5e52c67778094835ba3feed0d278b39eb63ed8de03c2ef97780bb` |

The replacement is **strictly stronger**, not weaker:

- `GATE-T1-B` pins Region A (`while` line → line before the AUTO-02 comment) to `c1d95350…cecd20`.
- `GATE-T1-C` pins Region B (the `ERROR: update-version.py failed for` line → the `-name .upstream.yaml` line) to
  `bfa308db…9b4ec6`.
- `GATE-T1-E` pins both anchor comments byte-for-byte, separately.
- `GATE-T1-F` bounds the remaining unpinned window in SIZE (comment run 3..8 lines), not merely by flanking it.
- `GATE-T1-D` asserts the whole-loop hash *differs* from rlj's pin — positive proof the edit landed where intended.

Net effect: the only lines that may differ from the pre-change tree are the window
[AUTO-02 comment … the call], and its size is itself gated. Every other rlj gate over these two workflows was
re-asserted inside Tasks 1 and 3 and is green (see the gate table above).

## Deviations from Plan

### Commit granularity: one commit, not one per task

**[Plan-mandated override of the default executor protocol — not an auto-fix]**

The executor default is one atomic commit per task. The plan's `L-12` locked constraint, its `<objective>`
("landing as ONE commit") and its `<success_criteria>` ("one commit") all mandate a single commit. Sibling 260909-rlj
landed as exactly one commit (`6fbe7a4`), confirming the batch convention.

Resolution: all three tasks were verified independently (Task 1's gates ran to green, then the tracer feedback gate
re-ran them end-to-end before expanding; Task 2's and Task 3's gates ran to green after their edits) and then committed
together as `ce932fa`. Files were staged individually — never `git add .`/`-A`.

### No other deviations

No Rule 1/2/3 auto-fixes were needed. No Rule 4 architectural question arose. No authentication gates. No package
installs. Every locked constraint L-1 through L-12 held as written.

Two pre-existing conditions were observed and deliberately **not** touched, per L-11 and the plan's exclusion list:

- `internal/update-version.py` has 6 lines over 119 characters (lines 53, 66, 147, 155, 303, 443). None is a line this
  item wrote. Out of scope.
- Repo-wide strict shellcheck exits 1 today from 22 pre-existing findings, and `lint.yml`'s shell-lint step ends in
  `|| echo`, which swallows the exit code. Not gated on, not fixed here — it belongs to a separate ledger item.

## Known Stubs

None. The committed additions contain no `TODO`, `FIXME`, placeholder, or stubbed value (scanned).

## Threat Flags

None. This item adds no `permissions:` key, no secret, no `vars.*` reference, no `run:` step, and no network call. It
*removes* one write to `origin` refs from the CI path (`git push origin <tag>`), narrowing the CI credential's exercised
surface. `GATE-T3-E` confirms exactly one `GH_TOKEN` match remains in `base-image-update.yml`, still scoped to the step
`env:`, and `GATE-T3-J` confirms neither added comment names a credential identifier.

## Broken-Windows Ledger

Three entries appended to `.planning/WINDOWS.md`:

| Kind | Description |
|---|---|
| `unrun-verify` | That a real auto-update run creates no tag — provable only from the next run's log plus `git ls-remote --tags origin`; not reachable from a repo checkout |
| `unrun-verify` | That the two bump workflows actually queue behind the shared group — needs two overlapping live GitHub runs |
| `deviation` | rlj `GATE-T1-14` is intentionally red (`7b7356ab` → `cdaa8113`), replaced by the narrower `GATE-T1-B`/`C`/`D` triple |

## Not Verified (needs a live GitHub run)

Both are outside a repo checkout by nature and are recorded as ledger entries above:

1. That a real auto-update run creates no tag.
2. That the two workflows actually serialize.

The image-availability question belongs to sibling 260909-rlk.

## Handoff Notes for 260909-rlm (STAGE 5)

- After this item `auto-update.yml` creates **no** git tag. `base-image-update.yml` never did
  (`internal/update-base-image.py` has no git operations). Both bump workflows are now consistent: push an untagged
  version-bump commit, then explicitly request a build.
- The historical mis-tagging is documentable from the repo itself:
  `git show "$(git rev-list -n1 meridian/v1.67.0-0):meridian/build.yaml"` prints VERSION `1.66.0` (one version stale),
  and the same for `meridian/v1.68.0-0` (`9f45b96`) also prints `1.66.0` — **two** versions stale. The skew is
  "at least one", not exactly one, so do not describe a tagged commit as carrying "the previous version".
- The defect was never bot-only: 15 of 40 `<addon>/v*` tags point at a tree whose `build.yaml` VERSION differs, each at
  an older version. `terraform-bridge/v0.2.0 → 0.1.0` proves the documented **manual** release procedure is affected
  too, because terraform-bridge has no `.upstream.yaml` at all. Existing wrong tags are left in place.
- `.github/RELEASE.md` is now cited from two places in `internal/update-version.py` (the tag-push output and the
  `create_and_push_tag` docstring), so its per-add-on `tags:`-trigger table is load-bearing operator documentation and
  must stay accurate.
- The shared concurrency group is `addon-version-bump`, repo-scoped. A third version-bumping workflow added later must
  join the same group or it reopens the push race.
- `internal/check-version-tags.sh` is a LOCAL pre-push hook run by no CI job, and its `LOCAL_BUILD_ADDONS` holds only
  `iac-runner`. It inspects only add-on dirs changed in the `remote_sha..local_sha` range of the push being made, so
  dropping the CI tag cannot start blocking developer pushes.

## Self-Check: PASSED

- `.github/workflows/auto-update.yml` — FOUND, modified
- `.github/workflows/base-image-update.yml` — FOUND, modified
- `internal/update-version.py` — FOUND, modified
- Commit `ce932fa` — FOUND in `git log`
- `git rev-list --count c495cbc..HEAD` = 1, matches `actuals.commits: 1`
- Working tree clean; no untracked files; no deletions in the commit
- No files created and no files deleted, as specified
