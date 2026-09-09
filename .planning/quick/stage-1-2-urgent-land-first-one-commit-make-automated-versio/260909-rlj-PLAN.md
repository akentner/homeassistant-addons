---
phase: quick-260909-rlj
plan: 01
type: execute
wave: 1
quick_id: 260909-rlj
depends_on: []
files_modified:
  - internal/dispatch-builds.sh
  - .github/workflows/auto-update.yml
  - .github/workflows/base-image-update.yml
  - .github/workflows/_build-template.yml
autonomous: true
requirements:
  - QUICK-260909-rlj-a
  - QUICK-260909-rlj-b
  - QUICK-260909-rlj-c
estimate:
  tokens: 55000
  raw_tokens: 55000
  tasks: 3
  confidence: low
must_haves:
  truths:
    - "A version-bump commit pushed to main by auto-update.yml with the default GITHUB_TOKEN causes a build-<addon>.yml run to be created for the bumped add-on (today: zero runs)."
    - "A base-image bump commit pushed to main by base-image-update.yml causes the same dispatch (today: zero runs, and that job has no gh credentials at all)."
    - "A failed dispatch makes the bump job exit non-zero — the push has already landed, so a green run would hide exactly the broken state this change exists to prevent."
    - "A workflow_dispatch-triggered build stamps a non-empty RFC3339 BUILD_DATE, so org.opencontainers.image.created is never empty on the trigger this change makes reachable."
    - "internal/dispatch-builds.sh never invokes gh for a candidate with no .github/workflows/build-<name>.yml, and treats that as a warning that does not fail the run."
    - "Neither bump workflow's per-add-on loop changes: zero lines differ inside auto-update.yml's upstream loop and base-image-update.yml's add-on loop."
  artifacts:
    - "internal/dispatch-builds.sh — mode 755, #!/usr/bin/env bash, set -euo pipefail, shellcheck-clean with NO -e flags"
    - ".github/workflows/auto-update.yml — actions: write, BASE_SHA capture+export, dispatch call after git push, corrected NOTE comment"
    - ".github/workflows/base-image-update.yml — actions: write, GH_TOKEN env, BASE_SHA capture+export, dispatch call after git push, corrected NOTE comment"
    - ".github/workflows/_build-template.yml — meta-step HEAD_COMMIT_TIMESTAMP env, BUILD_DATE fallback, BUILD_DATE step output consumed at both former head_commit sites"
  key_links:
    - "git push (inside the UPDATES_MADE block) -> ./internal/dispatch-builds.sh on the immediately following line -> the closing fi"
    - "BASE_SHA capture at the top of the run step -> git diff --name-only BASE_SHA..HEAD candidate derivation"
    - "candidate name -> .github/workflows/build-<name>.yml existence test -> gh workflow run --ref"
    - "job permissions actions: write -> GitHub workflow_dispatch creation API"
    - "steps.meta.outputs.BUILD_DATE -> build-args BUILD_DATE and notify-ha started_at"
---

<objective>
Make automated version bumps trigger their own image build, and close the BUILD_DATE hole that
becoming-reachable opens.

Root cause (proven, not re-investigated): `auto-update.yml` (cron 06:00 UTC) and
`base-image-update.yml` (cron 07:00 UTC) both commit and push to `main` with the default
`GITHUB_TOKEN`. GitHub creates no new workflow runs for such events, so every
`.github/workflows/build-<addon>.yml` — which triggers on `push` to `main` with
`paths: <addon>/**` — never fires. Evidence: commit `d3682f6` ("chore(meridian): update to
1.68.0") produced ZERO `build-meridian` runs; base-image commits `aaf6084` and `08dee0b`
produced ZERO runs for either sha; `amd64-meridian:1.68.0-0` measured HTTP 404 while
`meridian/config.yaml` already advertised it. `workflow_dispatch` is the documented exception:
a dispatch created with `GITHUB_TOKEN` DOES run.

Purpose: the repository's core value ("any upstream release is automatically reflected in the
add-on within 24 hours") is currently false at the image layer — the store advertises a version
whose image does not exist, which the HA Supervisor surfaces as "Unknown error".
Output: one new script, three edited workflows, landing as ONE commit.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@.github/workflows/auto-update.yml
@.github/workflows/base-image-update.yml
@.github/workflows/_build-template.yml
@internal/check-version-tags.sh
</context>

<verified_environment>
Measured on the current unmodified tree (2026-09-09, commit `8c6645f`). Do NOT re-derive these;
do NOT contradict them.

| Fact | Measured value |
|---|---|
| `internal/dispatch-builds.sh` | does not exist |
| `grep -c '^ *actions: write$'` in either bump workflow | 0 |
| `grep -c 'GH_TOKEN'` in `base-image-update.yml` | 0 |
| `grep -c 'head_commit\.timestamp'` in `_build-template.yml` | 2 (lines 132, 161) |
| `grep -c 'steps\.meta\.outputs\.BUILD_DATE'` in `_build-template.yml` | 0 |
| `grep -c 'manually trigger lint.yml'` in each bump workflow | 1 |
| `grep -c '^ *#.*build-'` in each bump workflow | 0 |
| anchored `^ *git push$` / `^ *exit \$ERRORS$` per bump workflow | exactly 1 each |
| `git push` unanchored in `auto-update.yml` | 2 (line 15 is prose in the concurrency comment — always anchor this grep) |
| first `fi` after `git push` | auto-update 128, base-image 78 (so `git push` / `fi` are adjacent today) |
| `pre-commit run --all-files` | PASSES, all 21 hooks, tree unmodified afterwards |
| CI-strict `find . -name '*.sh' -exec shellcheck {} +` (no `-e` flags) | **FAILS with 22 pre-existing findings** (SC2034/SC1091 in `internal/verify-*`, `coding-assistants/run.sh`, `check-version-tags.sh`, a `.planning/` script) |
| `lint.yml:92-95` | that step ends in `\|\| echo "No shell scripts to check"`, which swallows the non-zero exit — so CI's shellcheck step is non-blocking today |
| local `shellcheck` | 0.11.0; local `actionlint` NOT on PATH (use the pre-commit-managed v1.7.3) |
| local `yq` | python-yq 4.1.2, **no** `eval` subcommand — `yq eval --unsafe` from `CLAUDE.md` fails here; use `grep`/`python3 -c "import yaml..."` |
| `.prettierignore` / `.markdownlint-cli2.yaml` | both exclude `.planning/` — this plan file is not reformatted or linted |
| add-ons / build workflows | 9 add-on dirs, 9 `build-*.yml`, all with `workflow_dispatch:` at line 11 and no inputs |

Two consequences that shape the gates below:

1. A whole-repo strict `shellcheck` gate is **unsatisfiable** (22 pre-existing findings). The
   strict, no-`-e`-flags form is therefore gated on the NEW file only — which is exactly what
   the task text asks for. Fixing the 22 pre-existing findings, and un-swallowing
   `lint.yml:92-95`, are both out of scope for this item and for siblings rlk/rll/rlm/rln.
   Do not attempt either here.
2. `shellcheck` does not emit SC2154 for `${VAR:-default}` or for a bare `$VAR` sourced from the
   environment (verified with 0.11.0), so the `_build-template.yml` fallback will not trip
   actionlint's embedded shellcheck.
</verified_environment>

<locked_constraints>
Non-negotiable, straight from the item text. Any deviation is a defect.

- **L-1** Do NOT re-investigate the root cause. It is proven.
- **L-2** `internal/dispatch-builds.sh` is a NEW file, mode **755** (pre-commit's
  `check-shebang-scripts-are-executable` fails otherwise), shebang `#!/usr/bin/env bash`,
  `set -euo pipefail`.
- **L-3** No-argument mode derives the add-on set from `git diff --name-only $BASE_SHA..HEAD`
  piped through `cut -d/ -f1 | sort -u`.
- **L-4** Assign the `git diff` output to a variable via **command substitution**, never
  directly into a `mapfile < <(...)` process substitution: a process-substitution failure is
  invisible to `set -e` and would silently yield an empty list plus a green run.
- **L-5** A missing `build-<addon>.yml` is a WARN-and-continue, **never** an error.
- **L-6** A FAILED dispatch must `exit 1`.
- **L-7** `DRY_RUN=1` prints the `gh` commands instead of running them.
- **L-8** Header comment explains the cause, the `workflow_dispatch` exception, and links
  `https://docs.github.com/actions/using-workflows/triggering-a-workflow`.
- **L-9** `actions: write` added to the job `permissions` of BOTH bump workflows.
- **L-10** `BASE_SHA=$(git rev-parse HEAD)` captured at the start of the run step and exported.
  Do NOT rely on `$GITHUB_SHA`.
- **L-11** The dispatch call goes immediately AFTER `git push` and BEFORE `exit $ERRORS`, inside
  the existing `if [ "$UPDATES_MADE" -eq 1 ]` block, as `./internal/dispatch-builds.sh || ERRORS=1`.
- **L-12** `base-image-update.yml` additionally gets a step-level `env:` with
  `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`.
- **L-13** The stale NOTE comment in both files is corrected (it currently documents the
  GITHUB_TOKEN limitation but names only `lint.yml`, not the builds).
- **L-14** **ZERO lines change** in the per-add-on loops. That is the whole point.
- **L-15** `_build-template.yml`: step-level `env: HEAD_COMMIT_TIMESTAMP` on the `meta` step;
  `BUILD_DATE` set from it after the `BUILD_FROM` guard with `date -u +%Y-%m-%dT%H:%M:%SZ` as
  fallback; one added line in the existing `{ ... } >> "$GITHUB_OUTPUT"` block; lines 132 and 161
  read `${{ steps.meta.outputs.BUILD_DATE }}`. No step reordering.
- **L-16** `GH_REPO` is NOT set anywhere. The script runs inside the checkout, so `gh` resolves
  the repo from `origin`.
- **L-17** Shellcheck traps that apply: SC2086 quote everything; SC2155 never
  `local x=$(cmd)` (and never `export X=$(cmd)` — actionlint's shellcheck does not exclude
  SC2155); SC2001 no `echo | sed`; `pipefail` plus a filtering pipeline needs `|| var=""`;
  never `... | while read` (subshell loses counters).
</locked_constraints>

<script_contract>
The observable contract of `internal/dispatch-builds.sh`, referenced by every gate below.
Sibling item **260909-rln** (STAGE 6) rewrites this script into a single dispatch with a list —
this contract is the part to preserve across that rewrite.

**stdout**: exactly one line per candidate, `ADDON <name> <STATE>`, emitted in `sort -u` order of
the candidate names. That ordering is part of the contract, not an accident: the candidate list is
`sort -u`ed in BOTH argument mode and derive mode and is iterated in that order, so the `ADDON`
sequence is deterministic and gates may assert a fixed sequence — GATE-T1-5 asserts `meridian`
before `nonexistent-addon` for exactly this reason. A rewrite that batches candidates into one
dispatch must still emit the per-candidate lines in `sort -u` order. `<STATE>` is one of
`DISPATCHED`, `DRY_RUN`, `SKIPPED_NO_WORKFLOW`, `SKIPPED_BAD_NAME`, `FAILED`. In `DRY_RUN` mode a
candidate that has a workflow additionally prints the literal `gh` command it would have run,
prefixed `DRY_RUN: `. Gates parse only with `awk '$1=="ADDON"'`, so they never depend on prose
punctuation.

**stderr**: human `INFO:` / `WARN:` / `ERROR:` lines only.

**exit**: `0` when every candidate reached a non-`FAILED` state (including all skips); `1` when
any dispatch failed, when `BASE_SHA` is required but unset, or when `set -euo pipefail` aborts.
</script_contract>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end "a version bump dispatches its build" — auto-update path only</name>
  <files>internal/dispatch-builds.sh, .github/workflows/auto-update.yml</files>
  <precondition>Commit `80eb6b6` ("docs(release): scope the 404 rationale to image-pulling add-ons") is reachable from HEAD — the derive-path gate pins that sha as its left anchor rather than a relative `HEAD~N`, so a commit landing from a parallel session cannot change what the gate measures. Assert with `git rev-parse --verify 80eb6b6^{commit}` before running the gates; if it fails (rebase, shallow clone), substitute any other sha that is an ancestor of HEAD and whose range to HEAD is non-empty — the gate recomputes the expected set from the same sha, so any ancestor works.</precondition>
  <read_first>
`.github/workflows/auto-update.yml` in full (the loop you must not touch is lines 55-123; the
NOTE comment is 42-45; `permissions` is 31-32; `set -eo pipefail` is line 50; `git push` is 127).
`internal/check-version-tags.sh` lines 50-100 for the `LOCAL_BUILD_ADDONS` concept and for the
house style of a long "why" comment on a guard.
  </read_first>
  <behavior>
Behaviors the gates in `<verify>` assert, in the order they are written. Establish them before
declaring the task done.

- Given explicit add-on arguments and a `gh` that succeeds, the script dispatches
  `build-<addon>.yml` on the resolved ref, prints `ADDON <addon> DISPATCHED`, and exits 0. The
  argument vector handed to `gh` is exactly `workflow run build-<addon>.yml --ref <ref>`.
- Given a `gh` that fails, the script prints `ADDON <addon> FAILED` and exits **1** (L-6).
- Given `DRY_RUN=1`, no `gh` process runs; the `gh` command text is printed for a candidate that
  has a workflow, and is NOT printed for one that does not (L-7).
- Given a candidate with no `build-<name>.yml`, the state is `SKIPPED_NO_WORKFLOW`, a `WARN:` line
  goes to stderr, and the exit stays 0 (L-5).
- Given no arguments and a valid `BASE_SHA`, the derived candidate name set equals
  `git diff --name-only "$BASE_SHA..HEAD" | cut -d/ -f1 | sort -u` exactly (L-3).
- Given no arguments and an empty range, zero `ADDON` lines and exit 0.
- Given no arguments and an unset `BASE_SHA`, exit exactly 1 with an `ERROR:` line.
- Given an unresolvable `BASE_SHA`, exit non-zero — this is the observable proof that L-4 was
  honored, because the process-substitution form would have exited 0 with an empty list.
- Given a candidate that is not a well-formed add-on directory name, state `SKIPPED_BAD_NAME` and
  no `gh` invocation at all.
  </behavior>
  <action>
**Part 1 — create `internal/dispatch-builds.sh` (new file, chmod 755).**

Per L-2: shebang `#!/usr/bin/env bash`, then a header comment block, then `set -euo pipefail`.

Header comment (L-8) states, in prose: both bump workflows commit and push to `main` with the
default `GITHUB_TOKEN`; GitHub creates no workflow runs for such events; therefore every
`build-<addon>.yml` (`push` to `main`, `paths: <addon>/**`) never fires; the measured evidence
(`d3682f6` produced zero `build-meridian` runs, base-image commits `aaf6084` and `08dee0b`
produced zero runs for either sha, and `amd64-meridian:1.68.0-0` was HTTP 404 while
`meridian/config.yaml` already advertised it); that `workflow_dispatch` is the documented
exception because a dispatch created with `GITHUB_TOKEN` does run; and the link
`https://docs.github.com/actions/using-workflows/triggering-a-workflow`. The header also
documents the usage line `Usage: internal/dispatch-builds.sh [addon ...]`, the environment
contract (`BASE_SHA`, `DRY_RUN`, `REF`) and the stdout `ADDON <name> <STATE>` contract from
`<script_contract>` above, naming rln as the consumer of that contract.

Write the script with **no shell functions** — one top-level flow. That removes the SC2155
`local x=$(cmd)` trap by construction (L-17). Keep the usage text in a plain `USAGE` variable
reused by both the help path and the missing-`BASE_SHA` error.

Flow, in order:

1. `-h` / `--help` as the first argument prints `USAGE` and exits 0.
2. If `$#` is greater than 0: `candidates=$(printf '%s\n' "$@" | sort -u)`. `sort -u` dedupes
   because a dispatch builds the REF, not a commit, so two dispatches for one name are pure waste.
3. Otherwise: if `${BASE_SHA:-}` is empty, print an `ERROR:` line naming `BASE_SHA` plus `USAGE`
   to stderr and `exit 1`. Then, per L-4, capture `changed_files=$(git diff --name-only
   "${BASE_SHA}..HEAD")` as a plain command substitution assignment — under `set -e` a failing
   substitution aborts the script here, whereas `mapfile` reading a process substitution would
   swallow the failure and hand back an empty list plus a green run. Derive
   `candidates=$(printf '%s\n' "$changed_files" | cut -d/ -f1 | sort -u | grep -v '^$') || candidates=""`.
   The trailing `|| candidates=""` is mandatory: `pipefail` turns `grep`'s no-match exit 1 into a
   failed assignment that `set -e` would abort on (L-17). Add a one-line comment saying exactly that.
4. If `candidates` is empty, print an `INFO:` line to stderr saying there is nothing to dispatch,
   and `exit 0`.
5. Resolve the dispatch ref: prefer `$REF`, else `$GITHUB_REF_NAME`, else
   `git rev-parse --abbrev-ref HEAD`. If the result is empty or the literal `HEAD`, print an
   `ERROR:` line explaining the detached-HEAD case and telling the caller to set `REF`, then
   `exit 1`. Use the `${VAR:-}` form throughout so `set -u` never trips. Comment why this is a
   measurement rather than a hardcoded `main`.
6. `failed=0`. Iterate the candidate list with
   `while IFS= read -r addon; do ... done <<< "$candidates"`. A here-string is deliberately not a
   pipe: `... | while read` would run the body in a subshell and lose `failed` (L-17). Say so in a
   comment.
7. Per candidate, in order:
   - Skip an empty `addon`.
   - Defense-in-depth name-shape gate: `[[ "$addon" =~ ^[a-z0-9][a-z0-9._-]*$ ]]` (regex unquoted
     on the right of `=~`, or it becomes a literal match). On a non-match, emit
     `ADDON <addon> SKIPPED_BAD_NAME` on stdout, a `WARN:` line on stderr, and continue. Comment
     that the real security gate is step 3 of this list — an ill-formed name cannot resolve to an
     existing workflow file — and that this check exists so a traversal-shaped path is rejected
     with an accurate message instead of being reported as a missing workflow.
   - Build `workflow="build-${addon}.yml"`. If `.github/workflows/${workflow}` is not a regular
     file, emit `ADDON <addon> SKIPPED_NO_WORKFLOW` on stdout and a `WARN:` line on stderr, then
     continue (L-5). The WARN text must state that this is expected, not an error, and give both
     legitimate reasons: the path is not an add-on directory at all (the common case — a bump
     commit also touches `.planning`, `internal`, `.github` and root files), or the add-on is
     built locally by the Supervisor because its `config.yaml` declares no `image:` key, the same
     concept as `LOCAL_BUILD_ADDONS` in `internal/check-version-tags.sh`.
   - If `${DRY_RUN:-0}` is `1`: print the `gh` command line the script would have run, prefixed
     `DRY_RUN: `, plus `ADDON <addon> DRY_RUN`, then continue (L-7).
   - Otherwise run the dispatch as `if gh workflow run "$workflow" --ref "$ref"; then` … `else` …
     `fi`. The `if` form is required: a bare call returning non-zero would abort the loop under
     `set -e` before the remaining add-ons are dispatched. On success emit
     `ADDON <addon> DISPATCHED`; on failure emit an `ERROR:` line to stderr,
     `ADDON <addon> FAILED` to stdout, and set `failed=1`. Never echo `$GH_TOKEN` or
     `$GITHUB_TOKEN`; pass `gh`'s own stderr through unmodified.
   - Do not set `GH_REPO` anywhere (L-16).
8. `exit "$failed"` (L-6), with a comment: the push has already landed, so the repository is in
   exactly the broken state this script exists to prevent, and a green run would hide it.

Quote every expansion (SC2086). Do not use `echo | sed` anywhere (SC2001).

**Part 2 — wire `.github/workflows/auto-update.yml`.**

Four edits, and nothing else:

1. `permissions` (line 31-32): add `actions: write` alongside `contents: write`, with a short
   comment that creating a `workflow_dispatch` event requires it and that no other workflow in
   this repository has ever requested it (L-9).
2. In the `Check and update add-ons` run step, immediately after `set -eo pipefail` and before
   `ERRORS=0`, add **two** lines: `BASE_SHA=$(git rev-parse HEAD)` followed by a separate
   `export BASE_SHA`. The one-line `export BASE_SHA=$(...)` form is forbidden — it trips SC2155,
   and actionlint's embedded shellcheck excludes only SC2086/SC2129/SC2001 (L-17). Comment that
   capturing HEAD is a measurement, whereas `$GITHUB_SHA` would be an unverifiable assumption
   about what `actions/checkout` left in the work tree (L-10).
3. Inside the existing `if [ "$UPDATES_MADE" -eq 1 ]; then` block, on the line immediately after
   `git push` and before the closing `fi`, add `./internal/dispatch-builds.sh || ERRORS=1` (L-11).
   Comment that the position is load-bearing in both directions: under `set -e` a failed push
   aborts the step so nothing is dispatched for unpushed commits, and a dispatch placed before the
   push would build the pre-bump tree.
   **Put that comment ABOVE `git push`.** GATE-T1-12 asserts `git push`, the dispatch line and the
   closing `fi` are three consecutive lines (`d == p+1`, `k == d+1`), so neither slot adjacent to
   the dispatch call is free. Two admissible slots, both above `git push`, where the gate's two
   offsets shift together and still hold: (i) between `if [ "$UPDATES_MADE" -eq 1 ]; then` and
   `git push`, or (ii) appended to the existing
   `# Push once at the end — only if commits were made (AUTO-03)` block that already sits above the
   `if` (line 125 today). Pick either. A trailing comment on the dispatch line is also gate-legal
   but too short to carry the reasoning, so do not rely on it.
4. Rewrite the NOTE comment at lines 42-45 (L-13). The corrected text must say that a push made
   with `GITHUB_TOKEN` creates **no** workflow runs at all — naming `build-<addon>.yml` explicitly,
   not just the linter — and must point at the dispatch step below as the workaround. Keep the
   `https://docs.github.com/actions/using-workflows/triggering-a-workflow` link. Do not carry over
   any wording from the sentence that currently tells developers to kick off the linter by hand;
   a gate negative-greps that old sentence, so reusing its phrasing would fail the task.

**Do not touch lines 55-123.** Zero lines change between
`while IFS= read -r upstream_file; do` and the `done` line that reads
`-name .upstream.yaml` (L-14). A gate pins the sha256 of that exact region.
  </action>
  <verify>
    <automated>[ "$(stat -c %a internal/dispatch-builds.sh)" = "755" ] && [ "$(head -1 internal/dispatch-builds.sh)" = "#!/usr/bin/env bash" ] && grep -q '^set -euo pipefail$' internal/dispatch-builds.sh && grep -q 'workflow_dispatch' internal/dispatch-builds.sh && grep -q 'docs.github.com/actions/using-workflows/triggering-a-workflow' internal/dispatch-builds.sh && echo GATE-T1-1-PASS</automated>
    <automated>shellcheck internal/dispatch-builds.sh && echo GATE-T1-2-PASS</automated>
    <automated>d=$(mktemp -d) && printf '#!/bin/sh\nprintf "%%s\\n" "$@" >"$GH_ARGS"\nexit 0\n' >"$d/gh" && chmod 755 "$d/gh" && GH_ARGS="$d/args" PATH="$d:$PATH" REF=main ./internal/dispatch-builds.sh meridian >"$d/out" 2>"$d/err" && [ "$(awk '$1=="ADDON"{print $2, $3}' "$d/out")" = "meridian DISPATCHED" ] && [ "$(paste -sd' ' "$d/args")" = "workflow run build-meridian.yml --ref main" ] && rm -rf "$d" && echo GATE-T1-3-PASS</automated>
    <automated>d=$(mktemp -d) && printf '#!/bin/sh\nexit 1\n' >"$d/gh" && chmod 755 "$d/gh"; PATH="$d:$PATH" REF=main ./internal/dispatch-builds.sh meridian >"$d/out" 2>/dev/null; rc=$?; [ "$rc" -eq 1 ] && [ "$(awk '$1=="ADDON"{print $2, $3}' "$d/out")" = "meridian FAILED" ] && rm -rf "$d" && echo GATE-T1-4-PASS</automated>
    <automated>out=$(DRY_RUN=1 ./internal/dispatch-builds.sh meridian nonexistent-addon 2>/dev/null) && [ "$(printf '%s\n' "$out" | awk '$1=="ADDON"{print $2, $3}' | paste -sd'|' -)" = "meridian DRY_RUN|nonexistent-addon SKIPPED_NO_WORKFLOW" ] && printf '%s\n' "$out" | grep -q 'gh workflow run build-meridian.yml' && ! printf '%s\n' "$out" | grep -q 'build-nonexistent-addon.yml' && DRY_RUN=1 ./internal/dispatch-builds.sh nonexistent-addon 2>&1 1>/dev/null | grep -q '^WARN' && echo GATE-T1-5-PASS</automated>
    <automated>b=80eb6b6; git rev-parse --verify "$b^{commit}" >/dev/null && raw=$(git diff --name-only "$b..HEAD") && exp=$(printf '%s\n' "$raw" | cut -d/ -f1 | sort -u | grep -v '^$') && act=$(DRY_RUN=1 BASE_SHA="$b" ./internal/dispatch-builds.sh 2>/dev/null | awk '$1=="ADDON"{print $2}' | sort -u) && [ -n "$exp" ] && [ "$exp" = "$act" ] && echo GATE-T1-6-PASS</automated>
    <automated>o=$(mktemp) && DRY_RUN=1 BASE_SHA=HEAD ./internal/dispatch-builds.sh >"$o" 2>/dev/null && [ "$(awk '$1=="ADDON"' "$o" | wc -l)" -eq 0 ] && rm -f "$o" && echo GATE-T1-7-PASS</automated>
    <automated>( unset BASE_SHA; DRY_RUN=1 ./internal/dispatch-builds.sh >/dev/null 2>&1 ); rc=$?; [ "$rc" -eq 1 ] && echo GATE-T1-8-PASS</automated>
    <automated>DRY_RUN=1 BASE_SHA=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef ./internal/dispatch-builds.sh >/dev/null 2>&1; rc=$?; [ "$rc" -ne 0 ] && [ "$rc" -ne 127 ] && echo GATE-T1-9-PASS</automated>
    <automated>out=$(DRY_RUN=1 ./internal/dispatch-builds.sh '../../etc' 2>/dev/null) && [ "$(printf '%s\n' "$out" | awk '$1=="ADDON"{print $3}')" = "SKIPPED_BAD_NAME" ] && ! printf '%s\n' "$out" | grep -q 'gh workflow run' && echo GATE-T1-10-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; grep -q '^ *actions: write$' "$f" && grep -q 'BASE_SHA=\$(git rev-parse HEAD)' "$f" && grep -q '^ *export BASE_SHA$' "$f" && ! grep -q 'export BASE_SHA=\$(' "$f" && grep -q '^ *\./internal/dispatch-builds.sh' "$f" && [ "$(grep -n '^ *\./internal/dispatch-builds.sh' "$f" | tail -n +2 | wc -l)" -eq 0 ] && echo GATE-T1-11-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; p=$(grep -n '^ *git push$' "$f" | cut -d: -f1); d=$(grep -n '^ *\./internal/dispatch-builds.sh' "$f" | cut -d: -f1); e=$(grep -n '^ *exit \$ERRORS$' "$f" | cut -d: -f1); b=$(grep -n 'BASE_SHA=\$(git rev-parse HEAD)' "$f" | cut -d: -f1); w=$(grep -n 'while IFS= read -r upstream_file; do' "$f" | cut -d: -f1); [ -n "$p" ] && [ -n "$d" ] && [ -n "$e" ] && [ -n "$b" ] && [ -n "$w" ] && k=$(awk -v n="$d" 'NR>n && $0 ~ /^ *fi$/{print NR; exit}' "$f") && [ -n "$k" ] && [ "$d" -eq "$((p+1))" ] && [ "$k" -eq "$((d+1))" ] && [ "$d" -lt "$e" ] && [ "$b" -lt "$w" ] && echo GATE-T1-12-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -c 'manually trigger lint.yml' "$f")" -eq 0 ] && [ "$(grep -c '^ *#.*build-' "$f")" -ge 1 ] && grep -q 'docs.github.com/actions/using-workflows/triggering-a-workflow' "$f" && echo GATE-T1-13-PASS</automated>
    <automated>[ "$(awk 'index($0,"while IFS= read -r upstream_file; do"){f=1} f{print} index($0,"-name .upstream.yaml"){f=0}' .github/workflows/auto-update.yml | sha256sum | cut -d' ' -f1)" = "7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc" ] && echo GATE-T1-14-PASS</automated>
    <automated>pre-commit run --files internal/dispatch-builds.sh .github/workflows/auto-update.yml</automated>
  </verify>
  <done>
`internal/dispatch-builds.sh` exists at mode 755, is shellcheck-clean with NO `-e` flags, and
satisfies every clause of `<script_contract>`: fake-`gh` success yields
`ADDON meridian DISPATCHED` with argv `workflow run build-meridian.yml --ref main` and exit 0;
fake-`gh` failure yields `ADDON meridian FAILED` and exit **1**; `DRY_RUN=1 meridian
nonexistent-addon` yields exactly `meridian DRY_RUN` then `nonexistent-addon
SKIPPED_NO_WORKFLOW`, prints the `gh` command only for meridian, WARNs on stderr and exits 0;
the derived candidate set for `BASE_SHA=HEAD~1` equals the independently recomputed
`git diff --name-only | cut -d/ -f1 | sort -u`; an empty range yields zero `ADDON` lines and exit
0; an unset `BASE_SHA` exits exactly 1; an unresolvable `BASE_SHA` exits non-zero and non-127;
`../../etc` yields `SKIPPED_BAD_NAME` with no `gh` invocation.
`auto-update.yml` has exactly one `actions: write`, the two-line `BASE_SHA` capture+export with
no SC2155 form, exactly one `./internal/dispatch-builds.sh` invocation on the line immediately
after `git push` and immediately before the closing `fi` and before `exit $ERRORS`, the capture
above the loop, no trace of the old lint-only NOTE sentence, at least one comment line naming a
`build-` workflow, the docs link retained, and the upstream loop region hashing to
`7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc` (unchanged from baseline).
`pre-commit run --files` on both paths passes.
  </done>
  <reversibility rating="reversible">Adding `actions: write` broadens the bump job's token by one scope and is removed by reverting two lines; the new script has no callers outside the workflow it is wired into.</reversibility>
</task>

<task type="auto">
  <name>Task 2: BUILD_DATE fallback in _build-template.yml — close the hole Task 1 makes reachable</name>
  <files>.github/workflows/_build-template.yml</files>
  <read_first>
`.github/workflows/_build-template.yml` lines 68-107 (the `meta` step and its `GITHUB_OUTPUT`
block), line 132 (`started_at`) and line 161 (build-args `BUILD_DATE`).
  </read_first>
  <behavior>
- With `HEAD_COMMIT_TIMESTAMP` empty (the `workflow_dispatch` case Task 1 makes the normal trigger
  for version bumps), the `BUILD_DATE` expression from the file evaluates to a non-empty
  `YYYY-MM-DDTHH:MM:SSZ` string.
- With `HEAD_COMMIT_TIMESTAMP` set (the `push` case), the same expression passes the value through
  byte-for-byte.
- `github.event.head_commit.timestamp` survives in exactly one NON-COMMENT line: the `meta` step's
  `env:`. The explanatory comment from edit 2 names the expression as well, which is fine —
  GATE-T2-1 strips comment lines before asserting.
- `steps.meta.outputs.BUILD_DATE` is read in exactly two places: the `started_at` field and the
  `BUILD_DATE=` build-arg.
  </behavior>
  <action>
Per L-15, four edits to the `meta` step and its two downstream consumers. The `meta` step already
runs before both — no reordering.

1. Add a step-level `env:` block to the `Resolve version and base image from build.yaml` step
   (`id: meta`, line 71-72), between `id: meta` and `run:`, containing
   `HEAD_COMMIT_TIMESTAMP: ${{ github.event.head_commit.timestamp }}`. Routing the expression
   through `env:` rather than interpolating it into the run block is also what keeps event-supplied
   data out of the shell command line (see `T-rlj-06` in `<threat_model>`).
2. After the `BUILD_FROM` guard (the `if` whose error message contains `no build_from`) and before
   the `{ ... } >> "$GITHUB_OUTPUT"` block, set `BUILD_DATE` from the env var with
   `date -u +%Y-%m-%dT%H:%M:%SZ` as the fallback, using the `${VAR:-default}` form. Comment why:
   `github.event.head_commit.timestamp` is empty under `workflow_dispatch`, which
   `internal/dispatch-builds.sh` now makes the normal trigger for automated version bumps, and an
   empty value would ship an empty `org.opencontainers.image.created` label.
3. Add one line to the existing `{ ... } >> "$GITHUB_OUTPUT"` block echoing
   `BUILD_DATE=$BUILD_DATE`, alongside the existing `VERSION` / `CONFIG_VERSION` / `BUILD_FROM` /
   `PLATFORM` lines.
4. Change the `started_at` field (line 132) and the `BUILD_DATE=` build-arg (line 161) to read
   `${{ steps.meta.outputs.BUILD_DATE }}`. After this, `github.event.head_commit.timestamp` appears
   exactly once in **non-comment** lines — the `env:` added by edit 1. The counting gate strips
   comment lines first (`grep -v '^ *#'`), so the explanatory comment from edit 2 is free to name
   the expression; do not contort its wording to satisfy the count.

Touch nothing else in this file. No new step, no reordering, no change to the tag list, the
notify-ha payloads beyond `started_at`, or the other build-args.
  </action>
  <verify>
    <automated>t=.github/workflows/_build-template.yml; grep -q '^ *HEAD_COMMIT_TIMESTAMP: ' "$t" && [ "$(grep -v '^ *#' "$t" | grep 'head_commit\.timestamp' | grep -vc '^ *HEAD_COMMIT_TIMESTAMP: ')" -eq 0 ] && grep 'started_at' "$t" | grep -q 'steps\.meta\.outputs\.BUILD_DATE' && grep '^ *BUILD_DATE=' "$t" | grep -q 'steps\.meta\.outputs\.BUILD_DATE' && echo GATE-T2-1-PASS</automated>
    <automated>t=.github/workflows/_build-template.yml; grep -q 'HEAD_COMMIT_TIMESTAMP:-' "$t" && grep -q 'date -u +%Y-%m-%dT%H:%M:%SZ' "$t" && grep -q 'echo "BUILD_DATE=\$BUILD_DATE"' "$t" && echo GATE-T2-2-PASS</automated>
    <automated>t=.github/workflows/_build-template.yml; m=$(grep -n 'HEAD_COMMIT_TIMESTAMP: ' "$t" | cut -d: -f1); v=$(grep -n 'VERSION=\$(yq eval' "$t" | head -1 | cut -d: -f1); g=$(grep -n 'no build_from' "$t" | cut -d: -f1); a=$(grep -n 'HEAD_COMMIT_TIMESTAMP:-' "$t" | cut -d: -f1); o=$(grep -n 'GITHUB_OUTPUT' "$t" | head -1 | cut -d: -f1); [ -n "$m" ] && [ -n "$v" ] && [ -n "$g" ] && [ -n "$a" ] && [ -n "$o" ] && [ "$m" -lt "$v" ] && [ "$g" -lt "$a" ] && [ "$a" -lt "$o" ] && echo GATE-T2-3-PASS</automated>
    <automated>s=$(mktemp) && grep -m1 'HEAD_COMMIT_TIMESTAMP:-' .github/workflows/_build-template.yml >"$s" && printf 'printf %%s "$BUILD_DATE"\n' >>"$s" && HEAD_COMMIT_TIMESTAMP= bash "$s" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' && HEAD_COMMIT_TIMESTAMP=2026-01-02T03:04:05Z bash "$s" | grep -Fxq '2026-01-02T03:04:05Z' && rm -f "$s" && echo GATE-T2-4-PASS</automated>
    <automated>pre-commit run --files .github/workflows/_build-template.yml</automated>
  </verify>
  <done>
Outside comment lines, the only line referencing `head_commit.timestamp` is the `meta` step's
`HEAD_COMMIT_TIMESTAMP:` env entry — the `started_at` line and the `BUILD_DATE=` build-arg no
longer reference it (both did at baseline), and both now reference
`steps.meta.outputs.BUILD_DATE` (neither did at baseline). The `env:` precedes the `meta` run block, the
`BUILD_DATE` assignment sits after the `BUILD_FROM` guard and before the `GITHUB_OUTPUT` block,
and the block exports `BUILD_DATE`. The real expression extracted from the file yields an
`RFC3339`-`Z` timestamp when `HEAD_COMMIT_TIMESTAMP` is empty and passes a set value through
unchanged. `pre-commit run --files` on the template passes.
  </done>
  <reversibility rating="reversible">Four localised line edits; reverting restores the previous (empty-under-dispatch) behaviour exactly.</reversibility>
</task>

<task type="auto">
  <name>Task 3: Wire the second dispatch call site — base-image-update.yml</name>
  <files>.github/workflows/base-image-update.yml</files>
  <read_first>
`.github/workflows/base-image-update.yml` in full (`permissions` 15-16, NOTE comment 34-36, the
`Check and update base images` step from 37, `set -eo pipefail` 39, the loop 45-74, `git push` 77,
`exit $ERRORS` 80). Also re-read the four edits Task 1 made to `auto-update.yml` — this task is
the same shape plus the `GH_TOKEN` env, and the two files should read consistently.
  </read_first>
  <action>
Five edits, and nothing else:

1. `permissions` (line 15-16): add `actions: write` alongside `contents: write`, same comment
   rationale as Task 1 (L-9).
2. Add a step-level `env:` block to the `Check and update base images` step, between its `- name:`
   and its `run:`, containing `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (L-12). This job has no `gh`
   credentials at all today; mirror the block `auto-update.yml` already carries at lines 47-48.
   Do NOT add `GH_REPO` (L-16).
3. Immediately after `set -eo pipefail` and before `ERRORS=0`, add the two lines
   `BASE_SHA=$(git rev-parse HEAD)` and, separately, `export BASE_SHA`. The one-line `export
   BASE_SHA=$(...)` form is forbidden (SC2155) (L-10, L-17).
4. Inside the existing `if [ "$UPDATES_MADE" -eq 1 ]; then` block, on the line immediately after
   `git push` and before the closing `fi`, add `./internal/dispatch-builds.sh || ERRORS=1`, with
   the same load-bearing-position comment as Task 1 (L-11).
   **Put that comment ABOVE `git push`** — GATE-T3-3 asserts the same three consecutive lines
   (`d == p+1`, `k == d+1`), so neither slot adjacent to the dispatch call is free. Unlike
   `auto-update.yml`, this file has NO comment above its `if` (line 76 follows a blank line), so the
   two admissible slots are: (i) a new comment line between `if [ "$UPDATES_MADE" -eq 1 ]; then` and
   `git push`, or (ii) a new comment line immediately above the `if`. Both are above `git push`, so
   the gate's two offsets shift together and still hold.
5. Rewrite the NOTE comment at lines 34-36 (L-13) with the same corrected content as Task 1: a
   `GITHUB_TOKEN` push creates no workflow runs at all, naming `build-<addon>.yml` explicitly, and
   the dispatch step below is the workaround. This file's NOTE is currently missing the
   documentation link that `auto-update.yml` carries — add
   `https://docs.github.com/actions/using-workflows/triggering-a-workflow` here too. Do not carry
   over any wording from the sentence that currently tells developers to kick off the linter by
   hand; a gate negative-greps that old sentence.

**Do not touch lines 45-74.** Zero lines change between `while IFS= read -r addon; do` and the
closing `)` of the process substitution that feeds it (L-14). A gate pins the sha256 of that
exact region. In particular, leave the embedded `python3` heredoc that enumerates
`internal/base-image-config.yaml` completely alone.
  </action>
  <verify>
    <automated>f=.github/workflows/base-image-update.yml; grep -q '^ *actions: write$' "$f" && grep 'GH_TOKEN' "$f" | grep -q 'secrets.GITHUB_TOKEN' && grep -q 'BASE_SHA=\$(git rev-parse HEAD)' "$f" && grep -q '^ *export BASE_SHA$' "$f" && ! grep -q 'export BASE_SHA=\$(' "$f" && ! grep -q 'GH_REPO' "$f" && grep -q '^ *\./internal/dispatch-builds.sh' "$f" && [ "$(grep -n '^ *\./internal/dispatch-builds.sh' "$f" | tail -n +2 | wc -l)" -eq 0 ] && echo GATE-T3-1-PASS</automated>
    <automated>f=.github/workflows/base-image-update.yml; n=$(grep -n 'name: Check and update base images' "$f" | cut -d: -f1); g=$(grep -n 'GH_TOKEN' "$f" | cut -d: -f1); [ -n "$n" ] && [ -n "$g" ] && r=$(awk -v s="$n" 'NR>s && $0 ~ /^ *run: \|/{print NR; exit}' "$f") && [ -n "$r" ] && [ "$g" -gt "$n" ] && [ "$g" -lt "$r" ] && echo GATE-T3-2-PASS</automated>
    <automated>f=.github/workflows/base-image-update.yml; p=$(grep -n '^ *git push$' "$f" | cut -d: -f1); d=$(grep -n '^ *\./internal/dispatch-builds.sh' "$f" | cut -d: -f1); e=$(grep -n '^ *exit \$ERRORS$' "$f" | cut -d: -f1); b=$(grep -n 'BASE_SHA=\$(git rev-parse HEAD)' "$f" | cut -d: -f1); w=$(grep -n 'while IFS= read -r addon; do' "$f" | cut -d: -f1); [ -n "$p" ] && [ -n "$d" ] && [ -n "$e" ] && [ -n "$b" ] && [ -n "$w" ] && k=$(awk -v n="$d" 'NR>n && $0 ~ /^ *fi$/{print NR; exit}' "$f") && [ -n "$k" ] && [ "$d" -eq "$((p+1))" ] && [ "$k" -eq "$((d+1))" ] && [ "$d" -lt "$e" ] && [ "$b" -lt "$w" ] && echo GATE-T3-3-PASS</automated>
    <automated>f=.github/workflows/base-image-update.yml; [ "$(grep -c 'manually trigger lint.yml' "$f")" -eq 0 ] && [ "$(grep -c '^ *#.*build-' "$f")" -ge 1 ] && grep -q 'docs.github.com/actions/using-workflows/triggering-a-workflow' "$f" && echo GATE-T3-4-PASS</automated>
    <automated>[ "$(awk 'index($0,"while IFS= read -r addon; do"){f=1} f{print} f && $0 ~ /^ *\)$/{f=0}' .github/workflows/base-image-update.yml | sha256sum | cut -d' ' -f1)" = "2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc" ] && echo GATE-T3-5-PASS</automated>
    <automated>pre-commit run --files .github/workflows/base-image-update.yml</automated>
  </verify>
  <done>
`base-image-update.yml` has exactly one `actions: write`, a `GH_TOKEN` env bound to
`secrets.GITHUB_TOKEN` on the `Check and update base images` step (between its `- name:` and its
`run:`), no `GH_REPO`, the two-line `BASE_SHA` capture+export with no SC2155 form and above the
loop, exactly one `./internal/dispatch-builds.sh` invocation on the line immediately after
`git push` and immediately before the closing `fi` and before `exit $ERRORS`, no trace of the old
lint-only NOTE sentence, at least one comment line naming a `build-` workflow, the docs link now
present, and the add-on loop region hashing to
`2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc` (unchanged from baseline).
`pre-commit run --files` on the file passes.
  </done>
  <reversibility rating="reversible">Same shape as Task 1's workflow edits; a single revert restores the prior behaviour.</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GitHub Actions job -> GitHub Actions API | the bump job now creates `workflow_dispatch` events with the default `GITHUB_TOKEN`, which requires broadening the job token by one scope |
| commit contents -> `gh` argument vector | add-on names are derived from `git diff --name-only`, i.e. from paths in a commit, and are interpolated into a workflow filename passed to `gh` |
| GitHub event payload -> build shell | `github.event.head_commit.timestamp` is event-supplied data consumed by the `meta` step |

## STRIDE Threat Register

ASVS level 1; blocking threshold `high`. No `critical` or `high` threat is left undisposed.

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-rlj-01 | Elevation of Privilege | `actions: write` on the two bump jobs | medium | mitigate | Scope stays **job-level** in exactly those two workflows — not workflow-level, not the repository default (which remains read-only). No other job gains it. The dispatch target set is bounded by the `build-*.yml` files present in the checked-out `.github/workflows/`. |
| T-rlj-02 | Tampering | `internal/dispatch-builds.sh` candidate -> `gh workflow run` | high | mitigate | Two independent gates: (a) a name-shape check `^[a-z0-9][a-z0-9._-]*$` rejects traversal- and metacharacter-shaped candidates with `SKIPPED_BAD_NAME`; (b) the authoritative gate — `.github/workflows/build-<name>.yml` must be a regular file, so a crafted name resolves to nothing and is skipped. Every expansion is quoted (SC2086), and `gh` is invoked as a direct argv, never through `eval` or a shell string. Proven by GATE-T1-10. In derive mode a third, structural barrier sits upstream of both gates: `cut -d/ -f1` keeps only the first path segment, so a derived candidate is incapable of containing `/` before the name-shape check even runs — a traversal-shaped path cannot survive derivation at all. Rating stays `high` rather than being downgraded because argument mode (`printf '%s\n' "$@" \| sort -u`) has no `cut` and therefore no structural barrier, resting on gates (a) and (b) alone. |
| T-rlj-03 | Information Disclosure | dispatch failure output | low | mitigate | The script never echoes `$GH_TOKEN` / `$GITHUB_TOKEN`; `gh`'s own stderr is passed through unmodified (`gh` redacts its token). The `ERROR:` line names only the workflow and the ref. |
| T-rlj-04 | Denial of Service | one commit fanning out into many dispatches | low | accept | Bounded above by the number of `build-*.yml` files (9). Every non-add-on top-level path — the common case for a bump commit that also touches `.planning`/`internal`/`.github` — is discarded by the file-existence gate before any API call. `sort -u` removes duplicates. Accepted: the ceiling is the same as a normal multi-add-on push. |
| T-rlj-05 | Repudiation | dispatch-triggered builds lose `head_commit` context | low | mitigate | Task 2 restores an attributable `org.opencontainers.image.created` (either the push timestamp or the measured build instant); `BUILD_REF=${{ github.sha }}` already records the exact bump commit, and `--ref` pins the branch. |
| T-rlj-06 | Tampering | `github.event.head_commit.timestamp` interpolated into a shell context | medium | mitigate | Task 2 moves the expression out of the `run:` body and into the step's `env:`, so event-supplied data reaches the shell as an environment value rather than as text spliced into a command line. This removes the `${{ }}`-into-shell injection shape from the only place in this change that consumes event data. |
| T-rlj-07 | Spoofing | dispatch aimed at a ref the operator did not intend | low | mitigate | The ref is **measured** (`REF`, else `GITHUB_REF_NAME`, else `git rev-parse --abbrev-ref HEAD`) and a detached-HEAD or empty result is a hard `exit 1` rather than a silent fallback to `main`. |
| T-rlj-SC | Tampering | npm/pip/cargo installs | n/a | accept | This item introduces **zero** new package-manager installs and zero new dependencies. `gh`, `git`, `date`, `awk` and `sha256sum` are all pre-installed on `ubuntu-latest`. No `Package Legitimacy Audit` is required, and no legitimacy checkpoint is inserted. |
</threat_model>

<assumption_delta_decision>
The `assumption-delta scan` probe could not be run for this item: it resolves a ROADMAP phase
section, and a quick-batch item has none (`skipped` / `phase_unresolved`). Per the hook, a skipped
probe does not fire the checkpoint. Recording the signal anyway, because it is real and it names
the handoff to sibling **260909-rln**:

- **Pluralization observed:** what used to be "the add-on whose `paths:` a push matched" (one
  implicit source, one trigger) becomes "a set of add-on names, computed by a script, dispatched
  from two independent call sites".
- **Noun that is now primary:** *the set of add-ons to build*, not *the add-on a push touched*.
- **Decision: `add-alongside`.** Both bump workflows call the same script independently, and nine
  `build-<addon>.yml` workflows remain. This is accepted debt for this item, chosen because
  promoting now would require collapsing the nine build workflows — which is exactly the scope of
  **260909-rln** (STAGE 6: one `build.yml` plus a single list-dispatch), and rln explicitly depends
  on this item.
- **What would force the promote:** rln landing. The `ADDON <name> <STATE>` stdout contract in
  `<script_contract>` is the interface rln must preserve when it rewrites the script.

Non-blocking, advisory, recorded only.
</assumption_delta_decision>

<hook_dispositions>
- **api-coverage** (`workflow.api_coverage_gate`): the detector reads a phase scope
  (`PHASE_DIR/*-PLAN.md` + the ROADMAP phase section). A quick-batch item has neither, so the probe
  yields `skipped` rather than a verdict; per the hook, the checkpoint is skipped and no
  `COVERAGE.md` is fabricated. For the record, the external surface touched here is a **single**
  GitHub Actions API verb — creating a `workflow_dispatch` event, via `gh workflow run` — and it is
  integrated. No other endpoint of that API is in scope for this item.
- **assumption-delta** (`workflow.assumption_delta`): probe skipped (no phase section); the signal
  is recorded voluntarily in `<assumption_delta_decision>` above. Advisory, non-blocking.
- **schema-gate** (`workflow.schema_push_detection`): no ORM/schema-relevant paths (no Payload,
  Prisma, Drizzle, Supabase or TypeORM files) are in scope. Skipped silently — no `[BLOCKING]`
  push task injected.
- **security** (`workflow.security_enforcement`): `<threat_model>` present above, ASVS level 1,
  blocking threshold `high`. The one `high` threat (T-rlj-02) is disposed `mitigate` with a
  specific, gate-backed mitigation.
</hook_dispositions>

<source_coverage_audit>
Every requirement in the item description maps to a task. No item is deferred, simplified, or
staged as a "v1".

| # | Source requirement (from the item text) | Task | Gate |
|---|---|---|---|
| a-1 | NEW FILE `internal/dispatch-builds.sh`, mode 755 | T1 | GATE-T1-1 |
| a-2 | shebang `#!/usr/bin/env bash`, `set -euo pipefail` | T1 | GATE-T1-1 |
| a-3 | usage `internal/dispatch-builds.sh [addon ...]` | T1 | GATE-T1-8 (error path prints it), GATE-T1-5 |
| a-4 | no-arg mode derives from `git diff --name-only $BASE_SHA..HEAD \| cut -d/ -f1 \| sort -u` | T1 | GATE-T1-6 (independently recomputed) |
| a-5 | command substitution, NOT `mapfile < <(...)` | T1 | GATE-T1-9 (unresolvable sha must exit non-zero) |
| a-6 | `sort -u` dedupes | T1 | GATE-T1-6 |
| a-7 | missing `build-<addon>.yml` is WARN + continue, never an error | T1 | GATE-T1-5 |
| a-8 | a FAILED dispatch must exit 1 | T1 | GATE-T1-4 |
| a-9 | `DRY_RUN=1` prints the `gh` commands instead of running them | T1 | GATE-T1-5 |
| a-10 | header comment: cause + `workflow_dispatch` exception + docs link | T1 | GATE-T1-1 |
| b-1 | `actions: write` in both bump workflows | T1, T3 | GATE-T1-11, GATE-T3-1 |
| b-2 | `BASE_SHA=$(git rev-parse HEAD)` captured at step start and exported, not `$GITHUB_SHA` | T1, T3 | GATE-T1-11/12, GATE-T3-1/3 |
| b-3 | `./internal/dispatch-builds.sh \|\| ERRORS=1` after `git push`, before `exit $ERRORS`, inside the `UPDATES_MADE` block | T1, T3 | GATE-T1-12, GATE-T3-3 |
| b-4 | `env: GH_TOKEN` on base-image-update's run step | T3 | GATE-T3-1, GATE-T3-2 |
| b-5 | stale NOTE comment corrected in both files | T1, T3 | GATE-T1-13, GATE-T3-4 |
| b-6 | per-add-on loops untouched — zero lines change | T1, T3 | GATE-T1-14, GATE-T3-5 (sha256 pinned) |
| c-1 | step-level `env: HEAD_COMMIT_TIMESTAMP` on the `meta` step | T2 | GATE-T2-1, GATE-T2-3 |
| c-2 | `BUILD_DATE` set after the `BUILD_FROM` guard with `date -u` fallback | T2 | GATE-T2-2, GATE-T2-3, GATE-T2-4 |
| c-3 | one added line in the `{ ... } >> $GITHUB_OUTPUT` block | T2 | GATE-T2-2 |
| c-4 | line 132 `started_at` and line 161 build-arg read `steps.meta.outputs.BUILD_DATE` | T2 | GATE-T2-1 |
| c-5 | no reordering needed | T2 | GATE-T2-3 (ordering asserted by line number) |
| v-1 | `shellcheck internal/dispatch-builds.sh` with NO `-e` flags | T1 | GATE-T1-2 |
| v-2 | `DRY_RUN=1 BASE_SHA=<sha>` derives correctly | T1 | GATE-T1-6 |
| v-3 | `DRY_RUN=1 ... meridian nonexistent-addon` shows the WARN path | T1 | GATE-T1-5 |
| v-4 | `pre-commit run --all-files` passes | all | `<verification>` |
| v-5 | shellcheck traps SC2086 / SC2155 / SC2001 / pipefail / no `\| while read` | T1, T3 | GATE-T1-2, GATE-T1-11, GATE-T3-1, `pre-commit run --files` |

**Nothing missing. Nothing deferred. No phase split needed** — one new ~130-line script plus 13
localised workflow line edits sits well inside one agent's context.
</source_coverage_audit>

<gate_calibration>
Every gate in this plan was executed twice before the plan was finalised, against the real
repository at commit `8c6645f`. This closes both failure modes named in the batch constraints.

**Run A — unmodified tree.** All 23 work-proving gates fail (`rc != 0`):

```
g01=1 g02=2 g03=127 g04=1 g05=127 g06=1 g07=127 g08=1 g09=1 g10=127 g11=1 g12=1
g13=1 g16=1 g17=1 g18=1 g19=1 g21=1 g22=1 g23=1 g24=1
```

**Run B — the spec in `<tasks>` implemented literally** (a prototype script written from Task 1's
action, plus the three workflows edited exactly as Tasks 1-3 describe). All 26 gates pass,
`rc=0` across the board. The prototype was also clean under `shellcheck` with **no** `-e` flags,
and `pre-commit run --files` on all four paths passed every hook including actionlint v1.7.3. The
tree was restored afterwards (`git status` clean of tracked modifications).

**The three gates that deliberately pass in BOTH runs, and why they are not unfailable:**

| Gate | Role |
|---|---|
| GATE-T1-14, GATE-T3-5 | Loop-region sha256 **invariants**. They must pass at baseline — that is the assertion (L-14: zero lines change). They fail the moment any line inside a loop is touched, which is the only thing they are asked to detect. Run B passing them is the positive evidence that the spec'd edits stay outside both loops. |
| the three `pre-commit run --files` gates | **Regression** gates, not work-proving gates. Each is paired with work-proving gates in the same task, so no task's completion rests on one alone. |

**One real defect this calibration caught**, worth stating so it is not reintroduced: the first
draft of GATE-T2-1 counted `head_commit.timestamp` occurrences with a bare `grep -c` while Task 2
instructs a comment that names the same expression — the gate invalidated itself. It now strips
comment lines and asserts per-site instead of counting (see Task 2 edit 4).
</gate_calibration>

<verification>
Run after all three tasks, before committing:

1. `pre-commit run --all-files` — measured PASSING at baseline with the tree left unmodified, so
   any failure here is caused by this change. This is the real actionlint gate (pre-commit pins
   v1.7.3; `lint.yml` installs the latest at run time — both must pass) and the real
   `check-shebang-scripts-are-executable` gate.
2. `shellcheck internal/dispatch-builds.sh` — no `-e` flags, the CI-strict form. Must emit
   nothing. Do **not** run the whole-repo form; it fails with 22 pre-existing findings unrelated
   to this change (see `<verified_environment>`).
3. `python3 -c "import yaml,sys;[yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/auto-update.yml .github/workflows/base-image-update.yml .github/workflows/_build-template.yml`
   — the three edited workflows still parse. (Local `yq` is python-yq with no `eval` subcommand;
   do not use `yq eval` here.)
4. `git diff --stat` — exactly four paths: the new script plus the three workflows. Nothing else.
5. Re-run both loop-invariant hash gates (GATE-T1-14, GATE-T3-5) as the final check that L-14 held
   across all three tasks.

Commit as **one** commit (this item is explicitly "one commit"), e.g.
`fix(260909-rlj): dispatch builds after automated version bumps + BUILD_DATE fallback`.

Deliberately NOT verified here (requires a live GitHub run, and belongs to sibling **260909-rlk**,
STAGE 3): that a dispatched build actually publishes the advertised image tag. `rlk` builds
`internal/verify-image-availability.sh` for exactly that.
</verification>

<success_criteria>
- Every `GATE-*-PASS` marker in the three tasks prints, and every gate exits 0.
- `pre-commit run --all-files` passes with the tree unmodified afterwards.
- `shellcheck internal/dispatch-builds.sh` (no `-e` flags) is silent.
- `git diff --stat` shows exactly the four declared paths.
- Both loop-region sha256 values still match their baselines
  (`7b7356ab...f2f8bc` for auto-update, `2dace2d5...b419cc` for base-image).
- In `_build-template.yml`, with comment lines stripped first (`grep -v '^ *#'` — the form
  GATE-T2-1 uses), the `meta` step's `HEAD_COMMIT_TIMESTAMP:` env line is present and is the ONLY
  remaining line referencing `github.event.head_commit.timestamp`. Comment lines are deliberately
  exempt: Task 2 edit 2 mandates a comment that names the expression, so an unqualified whole-file
  count would reject correct work. `steps.meta.outputs.BUILD_DATE` is read at both former
  `head_commit` sites — the `started_at` field and the `BUILD_DATE=` build-arg.
- One commit, four paths, no scope creep into rlk/rll/rlm/rln territory: no `--no-tag`, no shared
  concurrency group, no doc rewrites, no `verify-image-availability` script, no collapsing of the
  nine `build-*.yml` files.
</success_criteria>

<handoff_notes>
For the siblings that follow, so they do not re-derive this:

- **260909-rll** (STAGE 4) edits the same two bump workflows. After this item, `auto-update.yml`
  and `base-image-update.yml` each contain a `BASE_SHA` capture near the top of their run step and
  a `./internal/dispatch-builds.sh || ERRORS=1` line immediately after `git push`. rll's shared
  concurrency group must not reorder either.
- **260909-rln** (STAGE 6) rewrites `internal/dispatch-builds.sh` into a single dispatch with a
  list. Preserve the `ADDON <name> <STATE>` stdout contract in `<script_contract>` — the gates in
  this plan (and any rln gate that reuses them) parse it with `awk '$1=="ADDON"'`. **Including its
  ordering:** one line per candidate in `sort -u` order. GATE-T1-5 asserts `meridian` before
  `nonexistent-addon`, so a batched rewrite that keeps the line format but loses the order
  satisfies the contract's prose and still breaks the gate.
- **260909-rlm** (STAGE 5) documents the end state. The accurate statement after this item is:
  a `GITHUB_TOKEN` push creates no workflow runs at all, and the bump workflows therefore create
  an explicit `workflow_dispatch` per changed add-on, which does run.
- Out of scope everywhere in this batch, but worth a future ticket: `lint.yml:92-95` ends in
  `|| echo "No shell scripts to check"`, which swallows shellcheck's exit code — the repo's
  strictest shell gate is currently non-blocking and already has 22 findings.
</handoff_notes>

<output>
Create `.planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio/260909-rlj-SUMMARY.md` when done.
</output>
