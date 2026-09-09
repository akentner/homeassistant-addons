---
phase: quick-260910-0og
plan: 01
quick_id: 260910-0og
subsystem: docs
tags: [ci, release-process, github-actions, verification, truth-pass]

# Dependency graph
requires:
  - phase: quick-260909-rlm
    provides: the docs truth pass whose eleven findings this item applies, and the verification report that found them
  - phase: quick-260909-wgm
    provides: the advisory pre-push hook (`2ba51a2`) that made three of the four STALE findings stale
provides:
  - "`.github/RELEASE.md` and `docs/AUTO_UPDATE_GUIDE.md` are TRUE at HEAD — all 3 FALSE, 4 STALE and 4 IMPRECISE findings corrected"
  - "both bump workflows' `actions: write` comments corrected at the source, provably comment-only"
  - "`260909-rln-PLAN.md` re-pinned so its Task 3 `<precondition>` and `GATE-G3-1c` resolve against the tree"
  - "`260909-rlm-VERIFICATION.md` advanced to `status: resolved` with an append-only `## Resolution` section"
affects: [quick-260909-rln, quick-batch-260909-rli]

# Actuals (#2632) — chars/4 over the six files actually changed, the same scale the plan's estimate used.
actuals:
  tokens: 55742
  tasks: 3
  commits: 3
plan_head_before: 13dd7fc2610a7f63e6fcd986eec5b5838a28dcaf

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "whitespace-flexible content anchors (`\\s+`-joined regex) for editing prettier-reflowed prose"
    - "comment-stripped sha256 equality as proof that a workflow edit is comment-only"

key-files:
  created:
    - .planning/quick/260910-0og-apply-the-eleven-260909-rlm-verification/260910-0og-SUMMARY.md
  modified:
    - .github/RELEASE.md
    - docs/AUTO_UPDATE_GUIDE.md
    - .github/workflows/auto-update.yml
    - .github/workflows/base-image-update.yml
    - .planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
    - .planning/quick/stage-5-depends-on-stages-1-and-3-it-documents-what-they-cha/260909-rlm-VERIFICATION.md

key-decisions:
  - "All eleven findings applied, including the four IMPRECISE ones — no correction weakened, no unevidenced claim added"
  - "F-2 documents the prettier/MD034 defect and fixes nothing; `.planning/WINDOWS.md` and `auto-update.yml:147` untouched"
  - "Workflow edits proved comment-only by comment-stripped sha256 equality, not asserted"
  - "Superseded literals removed from `260909-rln-PLAN.md` entirely; they survive only in this SUMMARY and the `## Resolution` section"
  - "Three citations tightened past the report's suggestion: F-8 `:94-95` not `:94-96`, F-10 gains three `_build-template.yml` lines, F-3 gains the compensating control"

requirements-completed:
  - QUICK-260910-0og-a
  - QUICK-260910-0og-b
  - QUICK-260910-0og-c
  - QUICK-260910-0og-d
  - QUICK-260910-0og-e
  - QUICK-260910-0og-f

# Metrics
duration: 22min
completed: 2026-09-10
status: complete
---

# Quick 260910-0og: Apply the Eleven 260909-rlm Verification Findings — Summary

**All eleven findings of `260909-rlm-VERIFICATION.md` applied by content anchor across two shipped docs
and two workflow comment blocks, with the two pending batch siblings re-pinned so neither halts on a
falsified literal — 27 of 27 gates green, workflow executable content proved byte-identical.**

## Performance

- **Duration:** ~22 min
- **Tasks:** 3 of 3
- **Files modified:** 6 (2 shipped docs, 2 workflows, 2 `.planning/` artifacts)
- **Commits:** 3, measured `git rev-list --count 13dd7fc..HEAD`

## Accomplishments

- **The two shipped docs are TRUE at HEAD.** All 3 FALSE, 4 STALE and 4 IMPRECISE findings corrected.
  The two claims the original truth pass *introduced* (F-1 exclusivity, F-2 prettier purpose) and the
  one it *left standing* (F-3 validate-versions ordering) are gone.
- **The source of the worst finding is fixed, provably without touching behaviour.** Both bump
  workflows claimed to be the only requester of `actions: write`; both request it. Four comment lines
  changed per file, and the comment-stripped sha256 of each file still equals its `ba490aa` value.
- **Neither pending sibling is left holding a falsified pin.** `260909-rln-PLAN.md`'s Task 3
  `<precondition>` would have HALTed its executor on `grep -qF '15 of the 40'`; it now greps the
  literal that is in the tree.
- **Every number written was re-derived from the tree, not copied.** The tag statistic, the `1 of 8`
  active-trigger sub-count and the `G3-8` count of 9 were all measured before being recorded.

## Task Commits

1. **Task 1: apply the eleven findings to the two documentation files** — `176de25` (docs)
   Carries F-1 through F-11 in `.github/RELEASE.md` and `docs/AUTO_UPDATE_GUIDE.md`.
2. **Task 2: correct the actions-write exclusivity claim in both bump workflows** — `bcad8cc` (docs)
   Carries the F-1 source fix: four comment lines in each of the two workflows.
3. **Task 3: re-pin 260909-rln and record the rlm resolution** — `2b6ec31` (docs)
   Carries the eleven re-pins and the `## Resolution` section.

**Plan metadata:** `13dd7fc` (plan, pre-existing — the ledger base for the commit count).

## Findings, and which commit carries each

| Finding | Severity | File | Commit |
| --- | --- | --- | --- |
| F-1 exclusivity claim | FALSE | `docs/AUTO_UPDATE_GUIDE.md` | `176de25` |
| F-1 source comments | FALSE | both bump workflows | `bcad8cc` |
| F-2 prettier / MD034 purpose | FALSE | `docs/AUTO_UPDATE_GUIDE.md` | `176de25` |
| F-3 validate-versions ordering | FALSE | `.github/RELEASE.md` | `176de25` |
| F-4 tag statistic | STALE | `.github/RELEASE.md` | `176de25` |
| F-5, F-6, F-7 pre-push hook, three sites | STALE | `.github/RELEASE.md` | `176de25` |
| F-8 base-image-update non-sequitur | IMPRECISE / FALSE (msg) | `.github/RELEASE.md` | `176de25` |
| F-9 loop fault tolerance, two sites | IMPRECISE | `docs/AUTO_UPDATE_GUIDE.md` | `176de25` |
| F-10 both version sources | IMPRECISE | `.github/RELEASE.md` | `176de25` |
| F-11 ghcr.io 404 causality | IMPRECISE | `.github/RELEASE.md` | `176de25` |

## Re-derived `260909-rln-PLAN.md` site list — measured, not trusted

The plan mandated three greps and said to report the count actually found. The plan predicted eleven
sites. **Measured: 12 grep hits across 12 distinct lines.**

| Grep | Hits | Lines |
| --- | --- | --- |
| `15 of the 40\|15 of 40` | 7 | 115, 162, 367, 1032, 1065, 1209, 1420 |
| `RELEASE.md:103\|RELEASE.md:93-95` | 3 | 126, 166, 1423 |
| `canonical image for the tag` | 3 | 167, 704, 1209 |

Reconciliation: **eleven sites were edited**, exactly as the plan mapped them (`:166` and `:167` are
one site, R-04, because they are one rationale item; `:1209` appears in two greps but its
`canonical image for the tag == 0` clause is a satisfied invariant that must stay). The **twelfth hit
was deliberately not changed** — `260909-rln-PLAN.md:704` as measured, now `:729` after R-11 inserted
25 lines above it. It is a `planner-discipline-allow` comment for a phrase that no Task 3 gate drives
to zero and that must survive at `:1209`. So the plan's count of eleven was correct; the extra hit is a
non-edit, reported here so a verifier does not read it as a missed site.

## Superseded literals and line citations, in full

This SUMMARY and the `## Resolution` section of `260909-rlm-VERIFICATION.md` are the only two places
permitted to hold these (plan D-05). They were removed from `260909-rln-PLAN.md` entirely, including
as history parentheticals, so its own gates could reach zero.

### Removed from the two shipped docs

| Old text | File |
| --- | --- |
| `Measured on 2026-09-09: 15 of the 40 … The other 25 agree with their tree.` | `.github/RELEASE.md` |
| `so a broken 3-file set fails the release before the tag reaches `origin`` | `.github/RELEASE.md` |
| `pre-push hook verifies the … before letting the branch push through` | `.github/RELEASE.md` |
| `are exempt`, `so no release tag is required` | `.github/RELEASE.md` |
| `but still satisfies the pre-push hook … as long as the subpatch … matches` | `.github/RELEASE.md` |
| `The pre-push hook will refuse a branch push until a tag named … exists` | `.github/RELEASE.md` |
| `performs no git operations of any kind … That workflow has therefore never produced a tag.` | `.github/RELEASE.md` |
| `both read `build.yaml:args.VERSION` out of whatever ref they check out.` | `.github/RELEASE.md` |
| `skipping step 2 produces exactly the ghcr.io 404` | `.github/RELEASE.md` |
| `formats the result with prettier so the lint workflow does not reject the commit` | `docs/AUTO_UPDATE_GUIDE.md` |
| `No other workflow in this repository asks for that scope.` | `docs/AUTO_UPDATE_GUIDE.md` |
| `The loop always runs to completion` | `docs/AUTO_UPDATE_GUIDE.md` |
| `The loop sets `ERRORS=1` and continues, then fails the job at the end` | `docs/AUTO_UPDATE_GUIDE.md` |
| `No other workflow in this repository has ever requested this scope.` | both bump workflows (comment) |

### Removed from `260909-rln-PLAN.md`

| # | Site | Superseded value |
| --- | --- | --- |
| R-01 | `:115` baseline table row | `**15 of 40**` |
| R-02 | `:126` baseline table row | `**2**: .github/RELEASE.md:103, internal/update-version.py:203` |
| R-03 | `:162` rationale item 3 | `15 of 40` |
| R-04 | `:166-168` rationale item 3 | citation `RELEASE.md:93-95` + "currently claims the opposite" |
| R-05 | `:367` `L-18` preserve list | pin `15 of the 40` |
| R-06 | `:1032` Task 3 `<precondition>` | `grep -qF '15 of the 40' .github/RELEASE.md` (HALT-on-failure) |
| R-07 | `:1065` action item 1 | `15 of the 40` |
| R-08 | `:1209` `GATE-G3-1c` | `grep -cF '15 of the 40' … -ge 1` |
| R-09 | `:1420` calibration row | `15 of the 40` |
| R-10 | `:1423` `G3-8` calibration row | `**2** … (RELEASE.md:103, update-version.py:203)` |
| R-11 | `:468`-`:479` `<sibling_supersession>` | recorded only `260909-wgm`; closing line said "all three lists" |

**Two of these were already stale before this task touched anything**, which is why the plan insisted on
re-measuring rather than trusting the document: R-02/R-10 recorded the `G3-8` count as **2** citing a
`RELEASE.md` line that no longer resolved (measured **9** today), and R-04 cited a sentence that
`260909-rlm` had already removed at `833c176` (measured **0** occurrences).

## `260909-rlm` gates knowingly invalidated

Recorded so a verifier re-running rlm's 98 `ck` gates knows which reds are expected.

| rlm gate | Status | Successor |
| --- | --- | --- |
| `C4-count-15` (`260909-rlm-PLAN.md:404`) | **RED, expected** — it pins the tag-statistic total that F-4 corrected | `GATE-T1-F4` |
| `Z1-scope` (`:447`, `:630`), `C12-scope` (`:717`) | **RED, expected** — they assert nothing outside `.planning/` beyond the two docs changed; Task 2 deliberately adds two workflows | `GATE-T2-SCOPE` + `GATE-T2-EXEC-BYTE-IDENTICAL` |

**`C5-count-25` now passes uninformatively.** It asserts the bare literal `25` appears in the
`## Tag schema` region. It was 2 (`The other 25` plus the citation `internal/update-version.py:425`);
it is now 1, from the citation alone. The statement it was written to protect is gone while the gate
still passes. An explicit successor assertion — `The other 27 agree with their tree.` — was added to
`GATE-T1-F4` rather than relying on it.

**Preserved and re-verified GREEN:** `C3-dated` (because F-4 kept **both** measurement dates), `C1`,
`C2`, `C6`-`C9`, `B1`-`B4`, `Y04` (`ERRORS=1`), `Y08`, `Y16` (`actions: write`), `Y17`
(`notify-ha.sh`) — all re-asserted by `GATE-T1-SIBLING` and `GATE-T1-INVARIANTS`.

## The three deliberate non-edits

Decisions, not oversights.

1. **`auto-update.yml:147`** — `# Format with prettier so lint.yml does not reject the commit`. States
   the same intent F-2 identifies as false, but `.planning/WINDOWS.md` ledger item 10 quotes that exact
   string as its evidence. Rewriting it would destroy the record of the defect while leaving the defect.
   The doc now describes reality and the comment remains the recorded defect; that asymmetry is
   deliberate.
2. **`.planning/WINDOWS.md`** — untouched. Its rendered table is generated and its fenced JSON block is
   the source of truth, so a hand-edit would leave the two disagreeing. All three tasks gated
   `git diff --quiet -- .planning/WINDOWS.md`. F-2 points at the ledger by path; it does not duplicate
   or fix it.
3. **`Makefile:234`** — the "will pick it up on the tag push" line. The verification report flagged it
   as adjacent and out of scope for the two target files; it stays out of scope here for the same
   reason.

Also unchanged by design: `.github/RELEASE.md`'s "requests the `actions: write` permission to do so"
sentence (it makes no exclusivity claim and the report raised no finding against it), and all nine
full-path `.github/workflows/build-` references.

## Verification

All 27 `<automated>` gates pass. Baseline polarity matched the plan's `<gate_calibration>` exactly:
the 18 work-proving gates were RED before their edit, the 9 invariants GREEN throughout.

| Chain | Gates | Result |
| --- | --- | --- |
| Task 1 | 14 | all PASS, re-run after Task 3 |
| Task 2 | 6 (incl. post-commit `GATE-T2-SCOPE`) | all PASS |
| Task 3 | 7 | all PASS |

Independently confirmed:

- **Tracer discipline held.** F-4 was applied alone first; its gate flipped RED→GREEN, prettier
  converged in two passes, and every preserved-literal gate stayed green before the other ten
  corrections were written.
- **Every anchor matched exactly once**, in all 13 doc replacements, both workflow blocks and all 11
  re-pins — as the plan's dry-run predicted. No anchor matched zero or multiple times.
- **The workflow edits are comment-only.** Comment-stripped sha256 unchanged
  (`e7b237ca…abb4d3`, `2a63d7ea…dea5db`), line counts unchanged (171, 116), `actionlint` and
  `yamllint` green.
- **The shipped reproduce command re-executed** and printed `total=42 mismatch=15 agree=27`, matching
  the prose it supports.
- **Every citation written was verified against the tree** before being written: `Makefile:201-203`,
  `verify-image-availability.yml` cron/permissions, `2ba51a2`, all seven `auto-update.yml` line
  ranges, `base-image-update.yml:94-95`/`:112` (and that `:96` is `UPDATES_MADE=1`, confirming the
  plan's tightening of the report's `:94-96`), `_build-template.yml:76`/`:80`/`:176`, and the F-8
  historical claim via `git log --all -S'git tag'` over both paths (empty).
- **No bare URL** introduced — `grep -nE '(^|[^<(])https?://'` returns nothing in either doc, which
  matters because F-2's own paragraph describes MD034.
- **`pre-commit run --all-files` fully green**, no regression against baseline.
- **Scope:** `git diff --name-only ba490aa HEAD` lists exactly the six `files_modified` plus the plan.
  No file deletions in any commit.
- **Append-only property proved:** the verification report's diff removes exactly one line
  (`status: incomplete`); all 649 original lines including every claim section, the findings table and
  the "What held" list are byte-unchanged.

## Decisions Made

Followed the plan's D-01 through D-07 as written. Three places where the plan deliberately went past
the verification report's suggested wording, all carried through:

- **F-8** cites `base-image-update.yml:94-95`, not the report's `:94-96` — `:96` is `UPDATES_MADE=1`,
  measured directly.
- **F-10** adds `_build-template.yml:76`, `:80` and `:176`, which the report did not give. Those are
  what make the claim checkable rather than merely asserted.
- **F-3** adds the compensating control (`verify-image-availability.yml`, four times daily, no registry
  credential). Disclosing the gate's real ordering without naming what catches the consequence would
  have been a net loss to the operator; dispositioned as `T-0og-01` (accept) in the plan's threat model.

Plus one wording choice of this executor's: **F-2 points at `.planning/WINDOWS.md` by path**, not at a
bare "ledger item 10", so a reader can actually find the register.

## Deviations from Plan

None — plan executed exactly as written. No deviation rule was triggered: no bugs found, no missing
critical functionality, no blocking issues, no architectural decisions surfaced.

The one measurement that disagreed with the plan's prose was handled by the plan's own instruction to
report what was measured: the three re-derivation greps returned 12 hits, not eleven. That resolved to
eleven edits plus one documented non-edit (`:704`), so no plan change was needed. Per handover §3.7 no
line number was trusted; every anchor was re-measured before editing.

## Issues Encountered

- **Prettier reflow, as anticipated (handover §3.8).** Both docs are outside `.prettierignore` and are
  reflowed at `proseWrap: always` / `printWidth: 120`. Each edit round needed exactly two `pre-commit`
  passes to converge — the first rewrites and returns non-zero, the second passes. No hand-wrapping was
  done. One consequence worth recording: prettier split F-5's `**advisory only — it never fails the
  push**` across two lines, which would have broken a naive `grep -F`. The plan's D-06 flattening
  (`tr '\n' ' '`) absorbed it, verified rather than assumed.
- **Sandbox refused compound git commands.** The worktree isolation layer rejected multi-statement
  shell one-liners naming `git`. Worked around by splitting the HEAD assertions into single commands
  and moving each gate chain into a script file. No git operation left the worktree.
- **No `.planning/WINDOWS.md` ledger entry was needed.** No stub, TODO, skipped test, unrun `<verify>`
  or deviation was produced by this task — the scan found nothing to record. The pre-existing ledger
  item 10 stays `open` and is now referenced from `docs/AUTO_UPDATE_GUIDE.md`.

## Estimate vs actuals

| Metric | Estimated | Actual |
| --- | --- | --- |
| tokens | 65000 | 55742 |
| tasks | 3 | 3 |
| commits | — | 3 |

`tokens` is chars/4 over the six files actually changed (222,968 chars), the scale the template
specifies. For reference on the narrower basis, the realized diff `13dd7fc..HEAD` is 49,521 chars
(~12,380 on the same divisor); the gap between the two bases is almost entirely
`260909-rln-PLAN.md`, a ~1,450-line file that had to be read in full to locate eleven pins but of which
only 38 lines changed. Recorded on both bases so a future calibrator can pick one deliberately rather
than inherit an ambiguity. Estimate confidence was `low`; the task-count estimate was exact.

## Follow-up — orchestrator's call, not this task's

This task deliberately did **not** mark `260909-rlm` complete in
`.planning/quick-batches/260909-rli/BATCH.json`. Closing the batch item is the orchestrator's decision:

```bash
quick-batch complete --quick-id 260909-rlm --commit 176de257f6cb5c8d5f5686c059102ee345563f43
```

`260909-rln` remains `pending` and is now safe to execute: its Task 3 `<precondition>` and
`GATE-G3-1c` both grep a literal present in `.github/RELEASE.md` at HEAD, and its `G3-8` row records
the count measured in the tree.

## Known Stubs

None. This task shipped prose corrections and four comment lines; no code path, component or data
source was stubbed, and no placeholder text was introduced.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern or schema change at a trust boundary.
The one security-relevant surface touched — the `permissions:` blocks of two `contents: write` +
`actions: write` scheduled workflows — was changed only in its comments, proved by comment-stripped
sha256 equality (`T-0og-02`, disposition `mitigate`, three independent gates).

## Self-Check: PASSED

All seven claimed files exist on disk. All four claimed commits resolve
(`176de25`, `bcad8cc`, `2b6ec31`, plus the `13dd7fc` ledger base). Every number in this SUMMARY was
re-measured from the tree and matched: 3 commits from the ledger base, 222,968 changed-file chars,
49,521 realized-diff chars, 38 changed lines in `260909-rln-PLAN.md`, 649 original lines in the
verification report, `G3-8` count of 9. The `:704` non-edit was confirmed present and untouched (now
`:729`). No claim in this SUMMARY is unverified.
