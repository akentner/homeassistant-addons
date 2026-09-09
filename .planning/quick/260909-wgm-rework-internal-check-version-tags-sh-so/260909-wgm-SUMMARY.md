---
phase: quick-260909-wgm
plan: 01
quick_id: 260909-wgm
subsystem: internal-tooling
status: complete
tags: [git-hooks, release-tags, advisory-downgrade, plan-repin]
requires:
  - "260909-rll's --no-tag change to .github/workflows/auto-update.yml (the regression this fixes)"
provides:
  - "an advisory (never-blocking) pre-push release-tag report"
  - "a 260909-rln-PLAN.md that is true again about internal/check-version-tags.sh"
affects:
  - "260909-rln Task 3 item 6 — narrowed to the build.yml mention alone"
  - "260909-rln GATE-G3-6 — code hash re-pinned; first clause now a satisfied invariant"
tech-stack:
  added: []
  patterns:
    - "arithmetic-EXPANSION assignment (count=$((count + 1))) for set -e safe counters"
    - "content-anchor citations instead of numeric line ranges across files"
key-files:
  created: []
  modified:
    - internal/check-version-tags.sh
    - internal/setup-hooks.sh
    - internal/verify-image-availability.sh
    - .planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
decisions:
  - "D-01 applied as a downgrade, not a drop: the missing-tag branch still detects and reports, exit status is 0"
  - "D-02 applied: LOCAL_BUILD_ADDONS and the image: drift guard retained, enforcement wording removed"
  - "D-03 applied: header and message state only the measured mechanism"
  - "D-04 applied: 260909-rln re-pinned at 13 sites, and 260909-wgm deliberately NOT added to its depends_on"
metrics:
  duration: "~35 min"
  completed: 2026-09-09
actuals:
  tokens: 46000
  tasks: 2
  commits: 2
plan_head_before: a11f3a7feb466de08afe1107139d251a8605ce4a
---

# Quick 260909-wgm: Make the missing release tag advisory Summary

Downgraded the pre-push `<addon>/v<version>` release-tag check from blocking (`exit 1`) to
advisory (`exit 0` with a warning), replaced its two disproved rationale claims with the measured
mechanism, and re-pinned the collision this created in the pending batch item `260909-rln`.

## What changed and why

`260909-rll` added `--no-tag` to `.github/workflows/auto-update.yml`, so the nightly bot stopped
creating `<addon>/v<version>` tags — while `internal/check-version-tags.sh` still exited 1 when one
was missing. Every nightly bump therefore refused the next human push until someone tagged by hand
(it happened twice last session: `authentik/v2026.8.2-0`, `meridian/v1.69.0-0`). The tag's
remaining value is as a release marker, and a release marker must not block a push.

## Commits

| Commit    | Type  | What                                                                        |
| --------- | ----- | --------------------------------------------------------------------------- |
| `2ba51a2` | `fix` | hook advisory + rationale corrected + two citing files updated (Task 1)     |
| `cada24f` | `docs`| `260909-rln-PLAN.md` re-pinned at 13 sites (Task 2)                         |

Measured, not narrated: `git rev-list --count a11f3a7..HEAD` = **2**.
`git diff --shortstat a11f3a7..HEAD` = 4 files changed, 86 insertions(+), 52 deletions(-) —
exactly the four declared paths, nothing else.

## The recomputed code hash (verbatim)

```
old  grep -v '^#' internal/check-version-tags.sh | sha256sum
     5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249
new  grep -v '^#' internal/check-version-tags.sh | sha256sum
     07d060ea42b7b05984ac642b0cf581d57f089703c69d9b3ffd44d4bd930394c2

truncated form used in <gate_calibration>
old  5f310c2e…019249
new  07d060ea…0394c2
```

## The negative control, verbatim (the item's one earned behavioural claim)

Both runs use the identical throwaway fixture repo: two commits, the second bumping
`zzz-probe/config.yaml` to `9.9.9-9` and `zzz-probe/build.yaml` to `9.9.9`, with the pre-push
stdin line `refs/heads/main <head> refs/heads/main <base>` piped to the hook. `zzz-probe` is not
on `LOCAL_BUILD_ADDONS` and neither tag form exists, so the missing-tag branch is reached in both
runs. This fixture exists because no real add-on directory currently misses BOTH tag forms.

### Probe D — hook as it stands at `74c8066` (baseline, BLOCKING)

```
RC=1

❌ zzz-probe: no matching tag for version '9.9.9-9' (expected zzz-probe/v9.9.9-9)
   Legacy format zzz-probe/v9.9.9 also missing.

   The build workflow for zzz-probe triggers on a '<addon>/v*' tag push.
   Without zzz-probe/v9.9.9-9, HA-Store-Refresh sees the new version but the
   Docker image at ghcr.io doesn't exist → 404 on update.

   Fix options:
     make release ADDON=zzz-probe VERSION=9.9.9-9
     # or manually:
     git tag -a zzz-probe/v9.9.9-9 -m 'zzz-probe: 9.9.9-9'
     git push origin zzz-probe/v9.9.9-9

🚫 Pre-push check failed — see errors above
   To bypass this check (not recommended): git push --no-verify
```

### Probe A — hook at `HEAD` (ADVISORY)

```
RC=0

⚠️  zzz-probe: no release tag for version '9.9.9-9' (expected zzz-probe/v9.9.9-9)
   Legacy format zzz-probe/v9.9.9 also missing.

   This is advisory only — the push continues. The image is published by
   internal/dispatch-builds.sh via workflow_dispatch, not by this tag, and
   .github/workflows/verify-image-availability.yml is the control that
   catches a genuinely missing image. The tag is a release marker.

   Fix options:
     make release ADDON=zzz-probe VERSION=9.9.9-9
     # or manually:
     git tag -a zzz-probe/v9.9.9-9 -m 'zzz-probe: 9.9.9-9'
     git push origin zzz-probe/v9.9.9-9


ℹ️  1 add-on(s) above have no release tag. This is advisory
   only — the push continues.
```

`RC=1` → `RC=0` with the warning text present in both. Probe D is what makes this an earned claim
rather than an assumption: it proves the fixture actually reaches the missing-tag branch, so a
fixture that had silently stopped reaching it (broken version extraction, broken range derivation)
could not have passed the gate by accident.

The `ℹ️` summary line printing at all is the second earned fact: the counter reached 1 without
aborting, which is what the arithmetic-EXPANSION form (`missing_tags=$((missing_tags + 1))`) buys
under `set -e`. The arithmetic-COMMAND form would have exited non-zero on that first increment.

### The other two probes

| Probe | Fixture                                    | Result                                                            |
| ----- | ------------------------------------------ | ----------------------------------------------------------------- |
| B     | `iac-runner`, no top-level `image:` key    | `RC=0`, prints the `⊘ … release tag not required` line — unchanged |
| C     | `iac-runner` WITH a top-level `image:` key | `RC=0`, drift warning naming `LOCAL_BUILD_ADDONS`, then the advisory tag report; no `Enforcing` |

## Gate results

| Gate                    | Result                                                               |
| ----------------------- | -------------------------------------------------------------------- |
| `GATE-W-BEHAVIOUR`      | **PASS** (all four probes, incl. the exit-1 negative control)         |
| `GATE-S-SOURCE`         | **PASS** (5 region hashes byte-identical, all literals, shellcheck)   |
| `GATE-C-CITATIONS`      | **PARTIAL** — 1 clause unsatisfiable from a worktree, see below       |
| `pre-commit run --files` (3 scripts) | **PASS**                                                |
| `GATE-P-PIN`            | **PASS**                                                             |
| `GATE-P-CLAIMS`         | **PASS**                                                             |
| `GATE-P-HYGIENE`        | **PASS** — diff 44+26 = **70** changed lines (limit 90), frontmatter's 12 keys intact, `260909-wgm` absent from `depends_on`, `WINDOWS.md` untouched |

`GATE-S-SOURCE` confirmed all five pinned regions came out byte-identical, so both documented
`set -e` hazard properties are preserved: `is_local_build`
(`37e332d28832efcbd8e523f28bffc9184520c3e69b749616c1eb37afc87d0cb9`), `tag_exists`
(`61d94dced1fc82a611fea172d8d374cc8049823786a9d1e486f740de038a6b36`), the allowlist array
(`cfbe5d35d8b64b212ebe40d52189c4f42c5bd9f5c2e1dbd4f5bdb67d77ca80d7`), the collection loop
(`714847bbf5466932f5e90fc1b4ffcad4a6690cecef2d964d02c7b5840801343d`), and the version-extraction
block (`8e077b1e48533cf297ccb57cc5f345c7c23a5f619f07ac0e7b71c2cb94efa9f8`).

The comment-stripped body has **0** non-zero exits, **0** references to the old error accumulator,
and **0** arithmetic-COMMAND forms. Over-120-column line counts held at their measured baselines
(2 / 0 / 19) — nothing reflowed.

## MANDATORY orchestrator follow-up: reinstall the pre-push hook

**This is the one clause of `GATE-C-CITATIONS` that did not pass, and it is unsatisfiable from
inside this worktree rather than a defect in the work.**

Task 1 step 7 requires copying the reworked script over
`$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push`. From a linked worktree
that path resolves to the **main checkout's** shared git dir —
`/home/akentner/Projects/homeassistant-addons/.git/hooks/pre-push` — which is outside this
worktree. The worktree-isolation sandbox denied the `cp`, by design.

Failing gate output, verbatim:

```
FAIL installed hook differs from repo copy: /home/akentner/Projects/homeassistant-addons/.git/hooks/pre-push
GATE-C-CITATIONS-FAIL
```

Every other clause of that gate passed: the `check-version-tags.sh:121-126` numeric citation is
gone while the citation itself survives as a content anchor, the sibling's
`Output vocabulary, matching internal/check-version-tags.sh exactly` claim is undisturbed,
`internal/setup-hooks.sh` no longer contains `verifies v<version> tag exists` and now says
`never blocks the push`, all three scripts pass `bash -n` and `shellcheck -e SC1091 -e SC2034`,
and the install target is still executable.

**After merging this branch, run from the main checkout:**

```bash
cp internal/check-version-tags.sh "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"
chmod +x "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"
cmp -s internal/check-version-tags.sh "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push" && echo HOOK-INSTALLED
```

Do NOT run `internal/setup-hooks.sh` for this: it also runs `pre-commit run --all-files`, which is
red on this repo for pre-existing reasons unrelated to this task.

**Until that copy happens, the developer's next push still runs the OLD BLOCKING hook** — which is
the entire user-visible point of this item. The must-have truth "`.git/hooks/pre-push` is
byte-identical to the reworked `internal/check-version-tags.sh`" is therefore **NOT yet satisfied**
and is the item's one residual.

## The 13 `260909-rln-PLAN.md` sites, old claim → new claim

The plan brief named seven; the file carried 13 distinct sites once every literal the gates assert
was located by content anchor. All 13 were edited.

| # | Site (located by anchor)                          | Old claim                                                                    | New claim                                                                                              |
| - | ------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 1 | `<verified_environment>` code-hash row             | code sha256 = `5f310c2e…019249`, "pins the hook's CODE"                      | `07d060ea…0394c2`, "re-pinned to the post-`260909-wgm` tree (that quick task made the hook advisory)"  |
| 2 | `<verified_environment>` G3-8 baseline row         | **3** deleted-caller refs, incl. `internal/check-version-tags.sh:2`          | **2**; `260909-wgm` removed the third, so this file is no longer among them                            |
| 3 | `GATE-G3-6-PASS` gate line                         | hard-coded `5f310c2eff…019249`                                              | hard-coded `07d060ea42…0394c2`                                                                          |
| 4 | `<gate_calibration>` `G3-6` row                    | `every workflow also triggers on` = **1**; sha256 `5f310c2e…019249`          | = **0**, **already satisfied**, now an invariant; `ghcr` an invariant; `build\.yml` the ONE work-proving clause; sha256 `07d060ea…0394c2` |
| 5 | `<done>` paragraph for this hook                   | "likewise untouched by every sibling … `5f310c2e…`, unchanged from baseline" | "untouched by every sibling … but reached by the NON-sibling `260909-wgm`" + new hash + "the post-`260909-wgm` baseline (NOT `5b41d49`)" |
| 6 | Task 3 action item 6                               | "header (lines 2-7) … this is the rationale correction D-01 requires"        | "header comment block … rationale ALREADY corrected by `260909-wgm`; the ONLY job left is the `build.yml` mention"; explicit do-NOT-revert-advisory-wording |
| 7 | Task 3 `<read_first>`                              | "`internal/check-version-tags.sh` lines 1-8 … and 51-77"                     | "its header comment block (already corrected by `260909-wgm`) and the `LOCAL_BUILD_ADDONS` array with its comment block" |
| 8 | Task 2 `<read_first>`                              | "`internal/check-version-tags.sh` lines 34-40"                               | "its add-on-directory test inside its collection loop … a region `260909-wgm` left byte-identical"     |
| 9 | `<gate_calibration>` `G3-8` row                    | "**3** at `5b41d49` (…, check-version-tags.sh:2)"                            | "**2** after quick task `260909-wgm` (…; it removed the third)"                                        |
| 10| `<success_criteria>` bullet                        | "is hash-proven a comment-only change;"                                      | "…comment-only change **relative to the post-`260909-wgm` tree** — that quick task, not a sibling, changed the hook's code and re-based G3-6's pin" |
| 11| Task 3 `<precondition>`                            | asserted only rll + rlm landed                                               | adds "**Quick task `260909-wgm` has landed** — `grep -qF 'release marker' …`; HALT on failure"          |
| 12| `<decisions>` closing paragraph                    | "executable behaviour is hash-pinned unchanged (G3-6)."                      | "…(G3-6) — against the post-`260909-wgm` tree, not `5b41d49`."                                          |
| 13| `<sibling_supersession>`                           | two subsections (§1 invalidated, §2 re-asserted)                             | new **§3 "A NON-sibling change that landed against `internal/check-version-tags.sh`"**; closing line now says "all three lists" |

Every eliminated literal is gone from that file in **both** full and truncated form, with no
parenthetical-history retention — the old values live here in this SUMMARY instead, which is the
only place the plan permits them. The generic meta-sentence warning against asserting "unchanged
from baseline" for a file a sibling can reach was **deliberately preserved**: a naive global
negative grep would have deleted a still-correct sentence, which is handover §3.6's exact defect
shape.

## GATE-G3-6 is now partly a no-op — read this before re-running batch `260909-rli`'s gate set

**Explicitly, so a verifier does not read it as coverage it no longer provides:**

`GATE-G3-6`'s first clause is `[ "$(grep -c 'every workflow also triggers on' "$f")" -eq 0 ]`.
That count was **1** at `74c8066` and is **0** at `HEAD` — `260909-wgm` deleted the false causal
claim as part of the header rewrite. The clause is therefore **a satisfied invariant, not
work-proving**, for `260909-rln` Task 3. It must stay 0, but its passing says nothing about
whether Task 3 did its job.

Clause-by-clause disposition, also written into the plan itself at the `G3-6` calibration row and
the done paragraph:

| Clause                          | Status after `260909-wgm`                                                          |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| `every workflow also triggers on` = 0 | **already satisfied** — invariant only, no longer work-proving                |
| `grep -q 'ghcr'`                | **invariant** — was and remains (7 occurrences at baseline, still ≥1)               |
| `grep -q 'build\.yml'`          | **the ONE clause still work-proving** — that workflow is `260909-rln`'s own deliverable and `260909-wgm` deliberately does not name it (naming it would have been a fresh false statement AND would have disarmed this clause) |
| code-only sha256                | **re-pinned** to `07d060ea…0394c2`, the post-`260909-wgm` baseline                 |

## Deviations from Plan

### Blocked (not auto-fixable, not a work defect)

**1. Task 1 step 7 — hook reinstall could not be executed**

- **Found during:** Task 1, step 7
- **Issue:** the install target resolves outside the worktree; the isolation sandbox denied the
  `cp` with `Permission for this action was denied by the Claude Code auto mode classifier`.
- **Action taken:** none possible from here — the plan's own `<worktree_specific_warning>`
  anticipated exactly this. Not weakened, not worked around, not faked. Recorded above as a
  mandatory post-merge orchestrator step with the exact commands and the verbatim gate failure.
- **Rule:** neither Rule 1-3 (nothing broken, nothing missing, nothing blocking the task's other
  work) nor Rule 4 (no architectural decision) — an environmental constraint of the execution
  sandbox. Handover §3.6's guidance applied: report the specific gate and why it is unsatisfiable
  rather than weakening the work to satisfy it.

### Scope notes

**2. Thirteen sites edited in `260909-rln-PLAN.md`, not seven**

The plan's Task 2 action listed seven; the gates assert literals at 13 distinct sites (e.g.
`GATE-P-CLAIMS` requires `lines 34-40` = 0, which lives in that plan's **Task 2** `<read_first>`,
outside the seven the action text enumerated). All 13 were edited so every gate clause is
satisfied by correct work rather than by luck. Not a deviation in intent — the plan's own `<done>`
block already said "all four stale numeric line citations" and its item 3 already demanded the
G3-6 disposition; the action list simply under-counted the sites.

## Deliberately out of scope, named rather than dropped

- Adding the top-level `image:` key to `authentik` and `iac-runner` (handover §2.4) — a separate
  change with its own anonymous-pull verification. Adding it here would have moved `authentik`
  into the drift-guard path mid-rework.
- Any `.planning/WINDOWS.md` ledger entry. The plan forbids hand-editing that generated table and
  `GATE-P-HYGIENE` actively asserts `git status --porcelain -- .planning/WINDOWS.md` is empty, so
  appending an entry would have turned a green gate red. The `GATE-G3-6` no-op is recorded inside
  `260909-rln-PLAN.md` instead, which is what D-04 asks for. The unsatisfied hook-reinstall
  residual is recorded in this SUMMARY under its own heading.
- The real-push smoke check (plan `<verification>` step 7). Not run: this agent must not push, and
  it would have been a no-op anyway — no current add-on misses both tag forms, so a real push
  exercises only the `✓` and `⊘` paths. No tagless add-on was fabricated to "prove" it live; that
  is what the fixture is for.

## Known Stubs

None. No placeholder value, no hardcoded empty, no TODO/FIXME introduced in any of the four files.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern or schema change. The one security-
relevant fact is the deliberate weakening recorded as **T-wgm-01** in the plan's threat register
(`accept`): the local pre-push refusal is gone, and the compensating control —
`.github/workflows/verify-image-availability.yml`, four times daily, anonymous, no registry
credential — is unchanged and was not touched by this task. **T-wgm-02** (stale installed hook,
disposition `mitigate`) is the residual documented above and is NOT yet closed.

## Self-Check

Files verified present on disk:

- `internal/check-version-tags.sh` — FOUND
- `internal/setup-hooks.sh` — FOUND
- `internal/verify-image-availability.sh` — FOUND
- `.planning/quick/stage-6-.../260909-rln-PLAN.md` — FOUND

Commits verified in history (`git log --oneline a11f3a7..HEAD`):

- `2ba51a2` — FOUND
- `cada24f` — FOUND

`git status --porcelain` after cleanup: empty. The throwaway probe fixture was created inside the
worktree (the sandbox refuses `git init` outside it) and removed with `rm -rf` — never with
`git clean`, which is prohibited in a worktree.

## Self-Check: PASSED

With one declared residual, not a failure: `.git/hooks/pre-push` in the main checkout is still the
old blocking copy. See "MANDATORY orchestrator follow-up" above.
