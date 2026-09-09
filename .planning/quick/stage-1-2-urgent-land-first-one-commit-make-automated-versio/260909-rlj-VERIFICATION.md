---
phase: quick-260909-rlj
verified: 2026-09-09T20:45:00Z
status: passed
score: 6/6 must-haves verified
covered_files:
  - ".github/workflows/_build-template.yml"
  - ".github/workflows/auto-update.yml"
  - ".github/workflows/base-image-update.yml"
  - ".planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio/260909-rlj-PLAN.md"
  - ".planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio/260909-rlj-SUMMARY.md"
  - "internal/dispatch-builds.sh"
covered_digest: "v1:sha256:9a995bbf848945d5be8064d753ab1ed6d32fd1f7755347520aed5f901fa4d68a"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "A dispatched build actually produces a run on GitHub and publishes the advertised image tag"
    addressed_in: "Quick item 260909-rlk (STAGE 3)"
    evidence: "internal/verify-image-availability.sh (delivered, mode 755) plus .github/workflows/verify-image-availability.yml scheduled in CI — an anonymous ghcr.io probe asserting that every config.yaml-advertised version is pullable. The plan's <verification> explicitly assigns this segment to rlk: 'Deliberately NOT verified here (requires a live GitHub run, and belongs to sibling 260909-rlk, STAGE 3)'."
---

# Quick 260909-rlj: Dispatch Builds After Automated Version Bumps — Verification Report

**Item Goal:** Make automated version bumps trigger their build, and fix the BUILD_DATE that this makes reachable.
**Verified:** 2026-09-09T20:45:00Z
**Status:** passed
**Re-verification:** No — initial verification
**Delivered state verified against:** working tree at HEAD `c495cbc`. `git diff 6fbe7a4 HEAD` over the four declared
paths is **empty**, so the working tree is byte-identical to the item's commit — every measurement below is a
measurement of the delivered commit.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                   | Status     | Evidence                                                                                                                                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | An auto-update.yml bump commit causes a `build-<addon>.yml` run to be created for the bumped add-on      | ✓ VERIFIED | End-to-end simulated in a throwaway local clone: fake meridian version bump → `BASE_SHA` derive → fake `gh` received argv exactly `[workflow] [run] [build-meridian.yml] [--ref] [main]`, stdout `ADDON meridian DISPATCHED`, exit 0. See E2E below. |
| 2   | A base-image-update.yml bump commit causes the same dispatch (that job had no gh credentials at all)     | ✓ VERIFIED | `base-image-update.yml:47-48` now carries step-level `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (0 occurrences at baseline `440e030`); identical push→dispatch block at `99-102`; ordering harness `bi-ok` fired `DISPATCH_RAN exit=0`.        |
| 3   | A failed dispatch makes the bump job exit non-zero                                                      | ✓ VERIFIED | Extracted both real blocks verbatim and ran them with a failing dispatch stub: `au-dispfail` and `bi-dispfail` both → `STEP_EXIT=1`. Script itself returns 1 on a failed `gh` (S2).                                                              |
| 4   | A `workflow_dispatch`-triggered build stamps a non-empty RFC3339 BUILD_DATE                             | ✓ VERIFIED | Line 104 extracted verbatim and executed in three states: empty → `2026-09-09T20:29:38Z` (RFC3339 regex OK), unset → non-empty, set → exact passthrough. Reaches `org.opencontainers.image.created` in all 9 Dockerfiles.                        |
| 5   | The script never invokes `gh` for a candidate with no `build-<name>.yml`, and that is a non-fatal warning | ✓ VERIFIED | `SKIPPED_NO_WORKFLOW` + 5 `WARN:` stderr lines + exit 0 (S10). With a *failing* `gh` first on PATH, zero `gh` invocations occurred (S5 grep count = 0), so the skip is a real short-circuit, not a swallowed failure.                             |
| 6   | Neither bump workflow's per-add-on loop changes — zero lines differ                                     | ✓ VERIFIED | Both pinned sha256 invariants **independently recomputed and matching, at HEAD *and* at baseline `440e030`**. Regions are non-degenerate (69 and 30 lines). Corroborated by diff-hunk analysis. See dedicated section.                            |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

Every behavior-dependent truth above (state transitions, the abort-ordering invariant, the fallback) was closed with a
**real execution**, not a grep. Nothing in this report rests on symbol presence alone.

### 1. Load-Bearing Ordering — verified in BOTH directions

Read from the actual files, not the plan.

`auto-update.yml`:

```
147            if [ "$UPDATES_MADE" -eq 1 ]; then
148              git push
149              ./internal/dispatch-builds.sh || ERRORS=1
150            fi
...
153            exit $ERRORS
```

`base-image-update.yml` is structurally identical at `99-102` / `104`.

| Assertion                                | auto-update            | base-image             | Status |
| ---------------------------------------- | ---------------------- | ---------------------- | ------ |
| dispatch inside the `UPDATES_MADE` block | if=147 < push=148      | if=99 < push=100       | ✓      |
| dispatch == push + 1                     | 149 == 148+1           | 101 == 100+1           | ✓      |
| closing `fi` == dispatch + 1             | 150 == 149+1           | 102 == 101+1           | ✓      |
| `exit $ERRORS` strictly after `fi`       | 153 > 150              | 104 > 102              | ✓      |
| dispatch invocation count                | 1                      | 1                      | ✓      |

Static position is necessary but not sufficient, so I extracted both blocks verbatim into a harness with a stubbed
`git push` and a tracer `dispatch-builds.sh`, prefixed with the real `set -eo pipefail` / `ERRORS=0` /
`UPDATES_MADE=1`, and ran all three cases against **both** files:

| Case                            | auto-update                                  | base-image                                   | Meaning                                              |
| ------------------------------- | -------------------------------------------- | -------------------------------------------- | ---------------------------------------------------- |
| push 0, dispatch 0              | `GIT_PUSH_RAN` → `DISPATCH_RAN` → `STEP_EXIT=0` | same                                         | correct order; dispatch builds the **post**-bump tree |
| **push 1** (push fails)         | `GIT_PUSH_RAN exit=1` → `STEP_EXIT=1`, **no `DISPATCH_RAN` line** | same | `set -e` aborts before any dispatch; nothing is built for commits that never landed |
| push 0, **dispatch 1**          | `DISPATCH_RAN exit=1` → `STEP_EXIT=1`        | same                                         | `\|\| ERRORS=1` propagates; a broken dispatch cannot go green |

Both directions the item cared about are proven behaviorally, not asserted.

### 2. Per-Add-On Loop Invariants — recomputed against the merged tree

| Loop region                             | Pinned in plan | Recomputed at HEAD | Recomputed at baseline `440e030` | Region size | Match |
| --------------------------------------- | -------------- | ------------------ | -------------------------------- | ----------- | ----- |
| `auto-update.yml` `.upstream.yaml` loop | `7b7356ab…f2f8bc` | `7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc` | identical | 69 lines | ✓ |
| `base-image-update.yml` add-on loop     | `2dace2d5…b419cc` | `2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc` | identical | 30 lines | ✓ |

**Both match, and both match the pre-change baseline.** I explicitly guarded against the degenerate-region failure mode
(an awk range that matches nothing would also hash "consistently"): the regions are 69 and 30 lines respectively.

Independently corroborated by diff-hunk placement — `git diff 440e030 HEAD` on `auto-update.yml` produces hunks at old
lines 30, 39, 49 and 123, none of which changes a line inside the loop body (old 55-123); `base-image-update.yml`
produces hunks at old 14, 31 and 73, all outside old 64-93. This is the item's strongest scope guarantee and it holds.

### 3. `actions: write` Scope

| Check                                                  | Result                                             |
| ------------------------------------------------------ | -------------------------------------------------- |
| anchored `^ *actions: write$` in `auto-update.yml`     | exactly **1** (line 37)                            |
| anchored `^ *actions: write$` in `base-image-update.yml` | exactly **1** (line 21)                          |
| any `actions:` key anywhere else in `.github/workflows/` | **none** (only the two, plus their own comments)  |
| `git grep 'actions: *write' 440e030 -- .github/workflows/` | **no match** — no workflow had it before        |
| repository default                                     | remains read-only; the grant is job-level, not workflow- or repo-level |

Least privilege holds: the new scope exists in exactly the two jobs that create dispatches and nowhere else, and is
genuinely new to this repository.

### 4. `BASE_SHA` — a Measurement, Not an Assumption

Both files contain the two-line form, identically:

```
BASE_SHA=$(git rev-parse HEAD)
export BASE_SHA
```

`auto-update.yml:65-66`, `base-image-update.yml:57-58`. `$GITHUB_SHA` appears in **neither** file except inside the
explanatory comment that says why it was rejected. `GH_REPO` is set nowhere in the repo (per L-16 — `gh` resolves the
repo from `origin` inside the checkout). Capture and export are split, so no `export X=$(cmd)` SC2155 form exists.

This choice is also load-bearing under `actions/checkout`'s default `fetch-depth: 1`: `BASE_SHA` is the shallow root
that is actually present in the work tree, so `git diff "$BASE_SHA..HEAD"` resolves locally.

### 5. BUILD_DATE Fallback — executed, not inspected

Plumbing (all present in `_build-template.yml`):

| Element                                        | Line | Detail                                                                 |
| ---------------------------------------------- | ---- | ---------------------------------------------------------------------- |
| step-level `env` on the `meta` step            | 73-74 | `HEAD_COMMIT_TIMESTAMP: ${{ github.event.head_commit.timestamp }}` — also keeps event data off the shell command line |
| fallback assignment, after the `BUILD_FROM` guard (96-99) | 104 | `BUILD_DATE="${HEAD_COMMIT_TIMESTAMP:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"` |
| export via `$GITHUB_OUTPUT`                    | 110  | inside the existing `{ … } >> "$GITHUB_OUTPUT"` block                  |
| consumer — notify `started_at`                 | 140  | `${{ steps.meta.outputs.BUILD_DATE }}`                                 |
| consumer — `build-args`                        | 169  | `BUILD_DATE=${{ steps.meta.outputs.BUILD_DATE }}`                      |

`steps.meta.outputs.BUILD_DATE` consumer count = **2** (both former sites). The only non-comment
`head_commit.timestamp` reference left in the file is the `env:` binding at line 74 — both direct consumers are gone.
No step reordering: `meta` is still the first step after `checkout`.

**Behavioral proof** — line 104 extracted verbatim from the file and executed three times:

| Case                                        | Result                 | Assertion                        |
| ------------------------------------------- | ---------------------- | -------------------------------- |
| `HEAD_COMMIT_TIMESTAMP=''` (workflow_dispatch) | `2026-09-09T20:29:38Z` | `NON_EMPTY_OK` + `RFC3339_OK`    |
| `HEAD_COMMIT_TIMESTAMP` unset, under `set -u`  | `2026-09-09T20:29:38Z` | `NON_EMPTY_OK`                   |
| `HEAD_COMMIT_TIMESTAMP='2026-09-09T18:22:11Z'` (push) | `2026-09-09T18:22:11Z` | `PASSTHROUGH_OK` — no regression |

The empty-label hole is closed and the push path is unchanged. The hole was real: **all 9** add-on Dockerfiles declare
`ARG BUILD_DATE` and emit `org.opencontainers.image.created=${BUILD_DATE}`, so every dispatch-triggered image would
have shipped an empty `created` label without this fallback.

### 6. `<script_contract>` — Verified As Implemented

Sibling **260909-rln** must preserve this, so each clause was exercised rather than read.

| Clause                                      | Test                                                        | Result                                                                                          |
| ------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `DISPATCHED` + exact argv                   | fake `gh` succeeding, arg mode                              | `FAKEGH_ARGV: [workflow] [run] [build-meridian.yml] [--ref] [main]`; `ADDON meridian DISPATCHED`; exit 0 |
| `FAILED` → exit 1                           | fake `gh` exiting 1                                         | `ADDON meridian FAILED`, exit **1**                                                             |
| `DRY_RUN`                                   | `DRY_RUN=1 meridian nonexistent-addon`                      | `DRY_RUN: gh workflow run build-meridian.yml --ref main` then the two `ADDON` lines, exit 0     |
| `SKIPPED_NO_WORKFLOW`                       | `nonexistent-addon`                                         | state emitted, `WARN:` on stderr, exit 0                                                        |
| `SKIPPED_BAD_NAME` (traversal)              | `../../etc` with a **failing** `gh` first on PATH            | `ADDON ../../etc SKIPPED_BAD_NAME`, exit 0, and **0** `gh` invocations — the gate short-circuits |
| **`sort -u` ordering**                      | args deliberately reversed: `zzz-… meridian aaa-…`           | emitted `aaa-nonexistent`, `meridian`, `zzz-nonexistent` — sorted, not argv order               |
| dedupe                                      | `meridian meridian meridian`                                | exactly **1** `ADDON` line                                                                      |
| exit 1 when `BASE_SHA` required but unset   | derive mode, `BASE_SHA` unset                               | exit **1**, `ERROR:` + usage on stderr                                                          |
| empty range                                 | `BASE_SHA=$(git rev-parse HEAD)`                            | **0** `ADDON` lines, exit 0                                                                     |
| stdout discipline                           | grep `-vE '^(ADDON \|DRY_RUN: )'` on captured stdout        | `STDOUT_CLEAN_OK` — no stray lines                                                              |
| stderr discipline                           | grep `-vE '^(INFO\|WARN\|ERROR):'` on captured stderr       | `STDERR_CLEAN_OK` — no stray lines                                                              |

The `sort -u` ordering clause — the one the plan flags as easy to satisfy in prose and break in fact — was tested with
**deliberately reverse-sorted arguments**, which is the only input shape that distinguishes real sorting from
argv-order passthrough. It sorts.

Contract-relevant implementation properties, confirmed by reading:

- L-4 command substitution, not `mapfile < <(…)`: line 89 `changed_files=$(git diff --name-only "${BASE_SHA}..HEAD")`;
  zero `mapfile`/`readarray` occurrences. **Proven behaviorally**: an unresolvable `BASE_SHA` exits **128** (non-zero
  and non-127) with 0 `ADDON` lines — a `mapfile` process substitution would have yielded an empty list plus exit 0.
- L-17 no `… | while read` subshell: `done <<< "$candidates"` (line 154), zero `| while` matches — so `failed` survives.
- No `eval` anywhere; `gh` is invoked as direct argv inside an `if` (line 147), so one failed dispatch does not abort
  the remaining add-ons.

### End-to-End Simulation (the real flow)

Performed in a throwaway `git clone --local` so the repository was never mutated and nothing was ever dispatched:

| Scenario                                                         | Result                                                                                                                              |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Bump touching `meridian/build.yaml` + `meridian/config.yaml`, `BASE_SHA` = pre-bump HEAD, no args | `gh workflow run build-meridian.yml --ref main`; `ADDON meridian DISPATCHED`; exit 0                       |
| Bump touching **two** add-ons plus `internal/`, `Makefile` noise | `authentik` DISPATCHED, `internal` SKIPPED_NO_WORKFLOW, `Makefile` SKIPPED_BAD_NAME, `meridian` DISPATCHED — sorted, exit 0          |
| Derive set vs independently recomputed `git diff … \| cut -d/ -f1 \| sort -u` | `DERIVE_SET_MATCH_OK`                                                                                                |

The multi-add-on case is the realistic shape (a bump commit also touches non-add-on paths) and it classifies every
segment correctly while still dispatching both real add-ons.

### Required Artifacts

| Artifact                                 | Expected                                                        | Status     | Details                                                                                                 |
| ---------------------------------------- | --------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------- |
| `internal/dispatch-builds.sh`            | new, mode 755, `#!/usr/bin/env bash`, `set -euo pipefail`, shellcheck-clean | ✓ VERIFIED | 159 lines; filesystem `755` **and** git index `100755` (so the exec bit survives checkout); shebang line 1; `set -euo pipefail` line 57; header documents cause, measured evidence, the `workflow_dispatch` exception and the docs link |
| `.github/workflows/auto-update.yml`      | `actions: write`, BASE_SHA capture+export, dispatch after push, corrected NOTE | ✓ VERIFIED | all four present; NOTE at 47-53 names `build-<addon>.yml` and carries the docs link                     |
| `.github/workflows/base-image-update.yml` | same + `GH_TOKEN`                                              | ✓ VERIFIED | all five present; `GH_TOKEN` correctly placed between `- name:` (46) and `run:` (49)                    |
| `.github/workflows/_build-template.yml`  | meta-step env, BUILD_DATE fallback, output consumed at both former sites | ✓ VERIFIED | lines 73-74, 104, 110, 140, 169                                                                          |

Diff scope: `git diff --stat 440e030 6fbe7a4` touches exactly these four paths (221 insertions, 8 deletions) — no
collateral edits.

### Key Link Verification

| From                                   | To                                            | Via                                                        | Status | Details                                                                    |
| -------------------------------------- | --------------------------------------------- | ---------------------------------------------------------- | ------ | -------------------------------------------------------------------------- |
| `git push` (in `UPDATES_MADE`)         | `./internal/dispatch-builds.sh`               | immediately following line, then closing `fi`              | ✓ WIRED | verified statically *and* by execution in both directions, both files      |
| `BASE_SHA` capture at step top         | `git diff --name-only "$BASE_SHA..HEAD"`      | `export BASE_SHA` → script env                             | ✓ WIRED | E2E derive run reproduced the independently computed set                   |
| candidate name                         | `gh workflow run --ref`                       | `^[a-z0-9][a-z0-9._-]*$` shape gate → `-f` workflow test   | ✓ WIRED | traversal input reaches neither; 0 `gh` invocations measured               |
| job `permissions: actions: write`      | workflow_dispatch creation API                | job-level grant, both bump jobs                            | ✓ WIRED | exactly one grant each, new to the repo                                    |
| `steps.meta.outputs.BUILD_DATE`        | `build-args BUILD_DATE` + notify `started_at` | `$GITHUB_OUTPUT`                                           | ✓ WIRED | 2/2 consumers; chain continues into all 9 Dockerfiles' OCI `created` label |

### Data-Flow Trace (Level 4)

| Artifact                 | Data Variable    | Source                                             | Produces Real Data                                      | Status     |
| ------------------------ | ---------------- | -------------------------------------------------- | ------------------------------------------------------- | ---------- |
| `dispatch-builds.sh`     | `candidates`     | `git diff --name-only "$BASE_SHA..HEAD"`           | Yes — matched an independent recomputation              | ✓ FLOWING  |
| `dispatch-builds.sh`     | `ref`            | `REF` → `GITHUB_REF_NAME` → `git rev-parse --abbrev-ref HEAD` | Yes — measured, not hardcoded to `main`; detached HEAD is a hard error | ✓ FLOWING |
| `_build-template.yml`    | `BUILD_DATE`     | `HEAD_COMMIT_TIMESTAMP` or `date -u`               | Yes — non-empty RFC3339 in every input state            | ✓ FLOWING  |
| Dockerfiles (all 9)      | OCI `created`    | `build-args BUILD_DATE`                            | Yes — `ARG BUILD_DATE` → `org.opencontainers.image.created` | ✓ FLOWING |

No static returns, no hardcoded literals, no mock-terminated chains.

### Behavioral Spot-Checks

| Behavior                          | Command                                                       | Result                            | Status |
| --------------------------------- | ------------------------------------------------------------- | --------------------------------- | ------ |
| YAML validity, three workflows    | `python3 -c "import yaml; yaml.safe_load(...)"`               | `YAML_PARSE_OK`                   | ✓ PASS |
| script `--help`                   | `./internal/dispatch-builds.sh --help`                        | usage printed, exit 0             | ✓ PASS |
| unresolvable `BASE_SHA`           | `BASE_SHA=deadbeef… ./internal/dispatch-builds.sh`            | exit 128, 0 `ADDON` lines         | ✓ PASS |
| BUILD_DATE fallback (3 states)    | line 104 extracted and executed                               | non-empty RFC3339 in all 3        | ✓ PASS |
| push/dispatch ordering (3 × 2)    | extracted blocks + stubs                                      | 6/6 as specified                  | ✓ PASS |
| E2E bump → dispatch (2 shapes)    | local clone + fake `gh`                                       | correct argv, correct states      | ✓ PASS |
| loop sha256 invariants (2)        | plan's own awk + `sha256sum`                                  | both match, at HEAD and baseline  | ✓ PASS |

Relied on (measured by the requester, not re-run): `shellcheck internal/dispatch-builds.sh` with no `-e` flags clean;
`make lint` 21/21; `actionlint` 1.7.12 and v1.7.3 both exit 0 over the edited workflows.

### Probe Execution

Not applicable — this item declares no probes and the repository has no `scripts/*/tests/probe-*.sh`. The item's
verification contract is the 26 inline gates plus `pre-commit`, all of which were re-derived above by independent means
rather than by re-running the executor's gate strings.

### Requirements Coverage

Requirement IDs `QUICK-260909-rlj-a/b/c` are item-local (quick items are not registered in `REQUIREMENTS.md`); their
decomposition lives in the plan's `<source_coverage_audit>` as a-1…a-10, b-1…b-6, c-1…c-5.

| Group | Description                                        | Status      | Evidence                                                                             |
| ----- | -------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------ |
| a-1…a-10 | `internal/dispatch-builds.sh` and its contract  | ✓ SATISFIED | mode 755 + git 100755, shebang, `set -euo pipefail`, derive path, `sort -u` dedupe, WARN-and-continue, exit 1 on FAILED, `DRY_RUN`, header comment + docs link — each executed above |
| b-1…b-6 | Both bump workflows wired                        | ✓ SATISFIED | `actions: write` ×1 each; two-line `BASE_SHA` capture, no `$GITHUB_SHA`; dispatch at push+1 inside the `UPDATES_MADE` block; `GH_TOKEN` on base-image; NOTE corrected (0 `manually trigger lint.yml`, 1 comment naming `build-`, docs link present in both); loops byte-identical |
| c-1…c-5 | `_build-template.yml` BUILD_DATE                 | ✓ SATISFIED | env binding, fallback after the `BUILD_FROM` guard, one added `$GITHUB_OUTPUT` line, both consumers switched, no reordering |
| v-1…v-5 | Verification obligations                         | ✓ SATISFIED | strict shellcheck clean, derive correctness, WARN path, `pre-commit` green, shellcheck traps avoided (no `export X=$(…)`, no `| while read`, no `echo | sed`, `|| candidates=""` under `pipefail`) |

No orphaned requirements.

### Anti-Patterns Found

| File                                     | Line | Pattern | Severity | Impact |
| ---------------------------------------- | ---- | ------- | -------- | ------ |
| —                                        | —    | none    | —        | —      |

Zero `TBD`/`FIXME`/`XXX` debt markers and zero `TODO`/`HACK`/`PLACEHOLDER` markers across all four delivered files, so
the debt-marker gate does not fire. No stubs, no hardcoded empty values, no unwired paths.

Explicitly **not** reported as regressions of this item, per the verification brief: the 22 pre-existing repo-wide
strict-shellcheck findings, and `lint.yml:94-95` swallowing that step's exit code. Both predate the item and are out of
its declared scope (already tracked as WINDOWS.md entry 3).

### Deferred Items

| # | Item                                                                        | Addressed In        | Evidence                                                                                                                                              |
| - | --------------------------------------------------------------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | A dispatched build actually produces a run and publishes the advertised tag | Quick item 260909-rlk | `internal/verify-image-availability.sh` (delivered, 755) + `.github/workflows/verify-image-availability.yml` scheduled in CI; the plan assigns this segment to rlk by name |

This is the only segment of truths 1-2 that no local test can close, and it is deferred rather than a gap for three
concrete reasons:

1. The plan explicitly scopes it out and names the sibling that owns it.
2. Sibling rlk has **landed** (commit `64a3cce`) with a scheduled anonymous ghcr.io probe that detects exactly the
   downstream symptom — an advertised version whose image is not pullable.
3. The dominant failure mode is **loud by this item's own design**: if `actions: write` + `GITHUB_TOKEN` were
   insufficient, `gh workflow run` exits non-zero → `ERRORS=1` → the bump job goes red (truth 3, verified by
   execution). A silent failure would require GitHub to accept a dispatch and then not run it, contradicting the
   documented behavior that L-1 pins as proven — and rlk's guard backstops even that.

The first live cron run (06:00 / 07:00 UTC) is the natural confirmation and will fail visibly if the premise is wrong.

### Human Verification Required

None. Every must-have was closed by direct execution, and the single externally-dependent segment is deferred to a
landed sibling with a loud-failure design as its backstop.

### Judgment on the Two Disclosed Deviations

**1. One commit instead of three per-task commits — correct, not a deviation from the contract that governs.**
The item title says "ONE COMMIT" and the plan's `<verification>` says "Commit as **one** commit (this item is
explicitly 'one commit')." The executor followed the item and the plan over the generic executor protocol, which is the
right precedence. Verified: `git rev-list --count 440e030..6fbe7a4` is 1 and the commit contains exactly the four
declared paths. **No effect on delivered state.** Reversibility is intact — one `git revert 6fbe7a4` restores all four
files, and because the four files are one coherent mechanism (the script is useless without its callers, and the
BUILD_DATE fallback only matters once dispatch is reachable) a single atomic commit is arguably *safer* here than three
partial ones, each of which would have been an incoherent intermediate state.

**2. Tracer gates run after expansion rather than before Tasks 2-3 — a real process lapse with no effect on the
delivered state.** The lapse is genuine: a `tracer` exists to prove the foundation before anything is layered on it,
and running its 14 gates late forfeits that guarantee prospectively. But the risk it guards against (layering onto a
broken foundation) is a *process* risk whose materialization would be visible in the artifact, and I verified the
artifact independently: all 14 gate-equivalent properties hold, and — more to the point — I re-derived the tracer's
substance from scratch by executing the script's every reachable state rather than re-running the executor's gate
strings. The foundation is sound as delivered. **No effect on delivered state.**

Worth carrying forward as a note, not a defect: deviation 2's own fix (the SC2155 comment that tripped its own negative
grep, `GATE-T1-11`/`GATE-T3-1`) is evidence that the gate suite *did* catch cross-task damage even when run late — but
it caught it after the fact. Had a Task 2/3 edit broken the script contract, the late ordering would have made
attribution harder, not the defect undetectable.

### Gaps Summary

None. All 6 must-have truths verified, all 4 artifacts substantive and wired, all 5 key links connected with data
flowing end to end, zero anti-patterns, zero debt markers, and the per-add-on loops byte-identical to baseline by
independently recomputed sha256.

The item's stated goal is achieved in the codebase: an automated version bump now creates an explicit
`workflow_dispatch` for each changed add-on (the documented exception to the `GITHUB_TOKEN`-creates-no-runs
limitation), a failed dispatch turns the bump job red instead of hiding a repository that advertises an unbuilt image,
and the `BUILD_DATE` hole that making `workflow_dispatch` reachable would otherwise have opened in all nine images is
closed with a proven `date -u` fallback.

The scope discipline the item demanded held exactly: four files, both per-add-on loops untouched at the byte level.

---

_Verified: 2026-09-09T20:45:00Z_
_Verifier: Claude (gsd-verifier)_
