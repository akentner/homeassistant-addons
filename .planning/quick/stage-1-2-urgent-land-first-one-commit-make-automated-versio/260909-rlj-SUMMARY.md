---
phase: quick-260909-rlj
plan: 01
quick_id: 260909-rlj
subsystem: ci-cd
status: complete
tags: [github-actions, workflow-dispatch, auto-update, build-date, oci-labels]
requires:
  - .github/workflows/auto-update.yml
  - .github/workflows/base-image-update.yml
  - .github/workflows/_build-template.yml
provides:
  - internal/dispatch-builds.sh
  - "ADDON <name> <STATE> stdout contract (consumed by 260909-rln)"
  - steps.meta.outputs.BUILD_DATE
affects:
  - 260909-rll
  - 260909-rlm
  - 260909-rln
tech-stack:
  added: []
  patterns:
    - "workflow_dispatch as the GITHUB_TOKEN push-trigger workaround"
    - "event data routed through step-level env: rather than ${{ }} into a run body"
    - "command substitution (never mapfile < <(...)) so set -e can see a failure"
key-files:
  created:
    - internal/dispatch-builds.sh
  modified:
    - .github/workflows/auto-update.yml
    - .github/workflows/base-image-update.yml
    - .github/workflows/_build-template.yml
decisions:
  - "One commit, not three per-task commits — the item text and the plan's <verification> both mandate a single commit"
  - "Load-bearing-position comment placed above `git push` in both workflows, the only gate-legal slot"
  - "SC2155-avoidance comment reworded: the literal `export BASE_SHA=$(` is negative-greped by GATE-T1-11/GATE-T3-1"
metrics:
  duration: ~8 min
  completed: 2026-09-09
  tasks: 3
  files: 4
actuals:
  tokens: 6695
  tasks: 3
  commits: 1
plan_head_before: 440e030207fccd25117441446b7240c1292549a6
---

# Quick 260909-rlj: Dispatch Builds After Automated Version Bumps Summary

`internal/dispatch-builds.sh` (new, 755) creates one `workflow_dispatch` per changed add-on so automated version and
base-image bumps actually build the image they advertise, and `_build-template.yml` now derives `BUILD_DATE` with a
`date -u` fallback so the newly-reachable dispatch trigger cannot ship an empty
`org.opencontainers.image.created`.

## What Shipped

**Commit:** `6fbe7a4` — `fix(260909-rlj): dispatch builds after automated version bumps + BUILD_DATE fallback`
(4 files, 221 insertions, 8 deletions; measured `git rev-list --count 440e030..HEAD` = **1**).

### `internal/dispatch-builds.sh` (new, mode 755, 159 lines)

`#!/usr/bin/env bash` + `set -euo pipefail`, no shell functions (removes the SC2155 `local x=$(cmd)` trap by
construction). Header comment documents the cause, the measured evidence (`d3682f6` → zero `build-meridian` runs;
`amd64-meridian:1.68.0-0` HTTP 404 while `config.yaml` advertised it), the `workflow_dispatch` exception, and the
`docs.github.com/actions/using-workflows/triggering-a-workflow` link.

Observable contract (`<script_contract>`, inherited by sibling **260909-rln**):

| Surface | Behaviour |
|---|---|
| stdout | one `ADDON <name> <STATE>` line per candidate, in `sort -u` order |
| states | `DISPATCHED` / `DRY_RUN` / `SKIPPED_NO_WORKFLOW` / `SKIPPED_BAD_NAME` / `FAILED` |
| stderr | `INFO:` / `WARN:` / `ERROR:` only |
| exit | `0` on all-non-`FAILED` (skips included); `1` on any failed dispatch or missing `BASE_SHA` |

Argument mode dedupes via `printf '%s\n' "$@" | sort -u`. Derive mode uses a plain command substitution
(`changed_files=$(git diff --name-only "${BASE_SHA}..HEAD")`) — deliberately **not** `mapfile < <(...)`, whose failure
is invisible to `set -e` and would return an empty list plus a green run. The `|| candidates=""` after the filtering
pipeline is load-bearing under `pipefail` (grep's no-match exit 1). The candidate loop uses a here-string, not a pipe,
so `failed` survives. `gh` is invoked as direct argv inside an `if`, never via `eval`, so a single failed dispatch does
not abort the remaining add-ons.

### `auto-update.yml` (4 edits) and `base-image-update.yml` (5 edits)

Both gained `actions: write` on the job `permissions`, a two-line `BASE_SHA=$(git rev-parse HEAD)` + `export BASE_SHA`
capture at the top of the run step, `./internal/dispatch-builds.sh || ERRORS=1` on the line immediately after
`git push` inside the existing `UPDATES_MADE` block, and a corrected NOTE comment that names `build-<addon>.yml`
explicitly (the old text claimed only `lint.yml` was affected and told developers to trigger it by hand).
`base-image-update.yml` additionally gained `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` — that job had no `gh` credentials
at all — and the docs link it was missing. No `GH_REPO` anywhere: the script runs inside the checkout and `gh` resolves
the repo from `origin`.

**Zero lines changed inside either per-add-on loop.** Both pinned sha256 invariants still match baseline:
`7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc` (auto-update upstream loop) and
`2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc` (base-image add-on loop).

### `_build-template.yml` (4 edits)

Step-level `env: HEAD_COMMIT_TIMESTAMP: ${{ github.event.head_commit.timestamp }}` on the `meta` step (which also keeps
event-supplied data off the shell command line — T-rlj-06); `BUILD_DATE="${HEAD_COMMIT_TIMESTAMP:-$(date -u
+%Y-%m-%dT%H:%M:%SZ)}"` after the `BUILD_FROM` guard; one added `echo "BUILD_DATE=$BUILD_DATE"` in the existing
`{ ... } >> "$GITHUB_OUTPUT"` block; and both former `head_commit.timestamp` consumers (`started_at`, the `BUILD_DATE=`
build-arg) now read `${{ steps.meta.outputs.BUILD_DATE }}`. No step reordering.

## Verification

**26 of 26 gates pass.** RED evidence was captured on the unmodified tree before any edit, reproducing the plan's
Run A calibration byte-for-byte:

```
GATE-T1-1 rc=1   GATE-T1-2 rc=2   GATE-T1-3 rc=127  GATE-T1-4 rc=1   GATE-T1-5 rc=127
GATE-T1-6 rc=1   GATE-T1-7 rc=127 GATE-T1-8 rc=1    GATE-T1-9 rc=1   GATE-T1-10 rc=127
GATE-T1-11 rc=1  GATE-T1-12 rc=1  GATE-T1-13 rc=1   GATE-T1-14 rc=0 (invariant, passes at baseline by design)
GATE-T2-1..4 rc=1                 GATE-T3-1..4 rc=1 GATE-T3-5 rc=0  (invariant, passes at baseline by design)
```

Post-implementation and again post-commit: all 23 work-proving gates `rc=0`, both invariants still `rc=0`, and the
three `pre-commit run --files` regression gates pass.

Plan `<verification>` steps 1-5:

| # | Check | Result |
|---|---|---|
| 1 | `pre-commit run --all-files` | PASS — every hook Passed/Skipped, tree unmodified afterwards |
| 2 | `shellcheck internal/dispatch-builds.sh` (no `-e` flags, CI-strict form) | silent |
| 3 | `python3 -c "import yaml..."` on the three workflows | `YAML_PARSE_OK` |
| 4 | `git diff --stat` | exactly the four declared paths, nothing else |
| 5 | Both loop-region sha256 invariants re-run | both match baseline |

The repo-wide strict shellcheck form was deliberately **not** run — it fails with pre-existing findings unrelated to
this change (already WINDOWS.md entry 3). `make update-version` was not involved; no add-on version changed, so
`validate-versions.sh` was a no-op pass.

## Deviations from Plan

### 1. [Process] One commit instead of three per-task commits

- **Found during:** Task 1 commit decision
- **Issue:** The executor protocol commits each task atomically; the plan's `<verification>` and the item title
  ("STAGE 1-2 URGENT LAND FIRST **ONE COMMIT**") both mandate a single commit.
- **Resolution:** Followed the plan. All three tasks landed as `6fbe7a4`.
- **Impact:** None on reversibility — a single `git revert 6fbe7a4` restores the prior behaviour of all four files.

### 2. [Rule 1 - Gate-driven fix] SC2155 comment contained the literal form its own gate forbids

- **Found during:** first full gate run, after all three tasks' edits
- **Issue:** `GATE-T1-11` and `GATE-T3-1` failed. Both assert `! grep -q 'export BASE_SHA=\$('`. My explanatory comment
  read "because \`export BASE_SHA=$(...)\` trips SC2155" — the comment itself matched the negative grep.
- **Fix:** Reworded to "Capture and export are two separate lines because combining them into a single export with a
  command substitution trips SC2155." Same reasoning, no forbidden literal. The gate was **not** weakened.
- **Files modified:** `.github/workflows/auto-update.yml`, `.github/workflows/base-image-update.yml`
- **Note:** This is the mirror-image of the defect the plan's own `<gate_calibration>` caught in GATE-T2-1 (a gate that
  invalidated itself by counting an expression a mandated comment names). Worth remembering as a class: when a gate
  negative-greps a literal, prose that *names* the literal trips it.

### 3. [Process, minor] Tracer feedback gate ran after expansion, not before

- **Issue:** Task 1 is `type="tracer"`. The protocol runs the tracer's `<verify>` end-to-end *before* any expansion
  task. I verified the script in isolation immediately (mode 755, `shellcheck` clean) but ran Task 1's full 14-gate set
  only after Tasks 2 and 3 were also edited.
- **Impact:** None materialised — Tasks 2 and 3 touch disjoint files (`_build-template.yml`,
  `base-image-update.yml`) and all 14 Task 1 gates pass. The failure mode the gate guards against (layering onto a
  broken foundation) did not occur; deviation 2's fix was in Task 1/3 territory and was caught by the gate suite anyway.
- **Recorded for honesty**, not as a defect in the shipped artifact.

No architectural changes (Rule 4) were needed. No auth gates. No package-manager installs — this item adds zero
dependencies (`gh`, `git`, `date`, `awk`, `sha256sum` are all pre-installed on `ubuntu-latest`).

## Scope Discipline

No creep into sibling territory, per the plan's `<success_criteria>`: no `--no-tag` (rll), no shared concurrency group
(rll), no doc rewrites (rlm), no `verify-image-availability.sh` (rlk), no collapsing of the nine `build-*.yml` files
(rln). The 22 pre-existing repo-wide shellcheck findings and the swallowed exit code at `lint.yml:94` were left alone —
both are explicitly out of scope for this item and already tracked as WINDOWS.md entry 3.

## Known Stubs

None. No hardcoded empty values, no placeholder text, no unwired data paths. Every branch of
`internal/dispatch-builds.sh` is exercised by a gate.

## Broken-Windows Ledger

One new `unrun-verify` entry appended (id 4): actionlint was verified only under the pre-commit-pinned **v1.7.3**.
`lint.yml` installs the latest release at run time, and that build could not be exercised locally — no `actionlint` on
PATH, no `go` toolchain to build it, and a network install is out of scope for this item. The three edited workflows
pass v1.7.3 and parse under PyYAML; latest-release actionlint remains CI-verified only.

WINDOWS.md entries 2 (python-yq has no `eval` subcommand) and 3 (`lint.yml:94` swallows shellcheck's exit code) were
both re-encountered exactly as recorded and needed no new entry.

## Threat Flags

None. The change's security-relevant surface is fully covered by the plan's `<threat_model>`: the one `high` threat
(T-rlj-02, candidate → `gh workflow run`) is mitigated by both gates it specifies — the `^[a-z0-9][a-z0-9._-]*$`
name-shape check (proven by GATE-T1-10, `../../etc` → `SKIPPED_BAD_NAME` with no `gh` invocation) and the
authoritative `.github/workflows/build-<name>.yml` regular-file test. `actions: write` stayed job-level in exactly the
two bump workflows; the repository default remains read-only.

## Handoff

- **260909-rll** — `auto-update.yml` and `base-image-update.yml` each now carry a `BASE_SHA` capture near the top of
  their run step and `./internal/dispatch-builds.sh || ERRORS=1` immediately after `git push`. `GATE-T1-12` /
  `GATE-T3-3` assert `d == p+1` and `k == d+1`; a shared concurrency group must not reorder either.
- **260909-rln** — preserve the `ADDON <name> <STATE>` stdout contract **including its `sort -u` ordering**. A batched
  rewrite that keeps the line format but loses the order satisfies the prose and still breaks `GATE-T1-5`.
- **260909-rlm** — the accurate statement is now: a `GITHUB_TOKEN` push creates no workflow runs at all, so the bump
  workflows create an explicit `workflow_dispatch` per changed add-on, which does run.
- **Not verified here** (needs a live GitHub run, belongs to **260909-rlk**): that a dispatched build actually publishes
  the advertised image tag.

## Self-Check: PASSED

- `internal/dispatch-builds.sh` — FOUND, mode 755
- `.github/workflows/auto-update.yml` — FOUND, modified
- `.github/workflows/base-image-update.yml` — FOUND, modified
- `.github/workflows/_build-template.yml` — FOUND, modified
- Commit `6fbe7a4` — FOUND in `git log`
- `git rev-list --count 440e030..HEAD` = 1, matching `commits: 1` in frontmatter
- Working tree clean of tracked modifications after commit; no untracked files left behind
