---
phase: quick-260909-rll
plan: 01
type: execute
wave: 2
quick_id: 260909-rll
depends_on: ["260909-rlj"]
files_modified:
  - .github/workflows/auto-update.yml
  - internal/update-version.py
  - .github/workflows/base-image-update.yml
autonomous: true
requirements:
  - QUICK-260909-rll-a
  - QUICK-260909-rll-b
  - QUICK-260909-rll-c
estimate:
  tokens: 42000
  raw_tokens: 42000
  tasks: 3
  confidence: low
must_haves:
  truths:
    - "auto-update.yml no longer creates or pushes any git tag: the single non-comment `internal/update-version.py` invocation in that workflow carries `--no-tag`, so the PRE-bump HEAD it runs against can no longer be tagged as if it were the bump."
    - "Nothing else in auto-update.yml's per-add-on loop changes: the region from the `while` line to the line before the AUTO-02 comment, and the region from the `ERROR: update-version.py failed for` line to the `-name .upstream.yaml` line, are both byte-identical to their pre-change baselines."
    - "The unpinned window between those two pinned regions is bounded in SIZE, not merely flanked: the contiguous comment run immediately above the call is at most 8 lines (the 2 frozen anchors plus at most 6 inserted rationale lines), and the acceptance window that greps it is derived from that run's real extent rather than a fixed line count."
    - "`internal/update-version.py` never again asserts that pushing the tag produces a build; the tag-push success output states the conditional (an active `tags:` trigger) and points at `.github/RELEASE.md`."
    - "`create_and_push_tag`'s docstring distinguishes the `paths:`-on-main trigger from the `tags:` trigger instead of conflating them, and no longer claims the tag is a prerequisite for the image existing."
    - "`--no-tag` is still accepted both before and after the two positionals, and `--help` still lists it — the flag's argparse surface is untouched."
    - "auto-update.yml and base-image-update.yml both declare a workflow-level `concurrency` block whose `group` is the byte-identical string `addon-version-bump` with `cancel-in-progress: false`, so the two bump workflows are mutually exclusive and neither can race the other's `git push`."
    - "auto-update.yml's existing 12-line concurrency rationale comment survives verbatim and contiguous, and the comment run above `concurrency:` is longer than 12 lines — the comment was extended, not replaced."
    - "The extension reconciles the frozen paragraph it follows: lines 17-19 reason about a `<addon>/v<version>` tag-collision risk, and after Task 1 this workflow creates no tag at all, so the extension states that explicitly (naming `--no-tag` and pointing at the call-site comment) and the frozen sentence reads as history rather than as a live claim."
    - "Every 260909-rlj gate over these two workflows still passes, with the single documented exception of GATE-T1-14 (see <sibling_supersession>)."
  artifacts:
    - ".github/workflows/auto-update.yml — `--no-tag` on the update-version.py call + a pre-bump-HEAD rationale comment above it; `group: addon-version-bump`; extended concurrency rationale comment"
    - "internal/update-version.py — corrected tag-push success output, corrected `create_and_push_tag` docstring, argparse surface unchanged"
    - ".github/workflows/base-image-update.yml — new workflow-level `concurrency` block (group `addon-version-bump`, `cancel-in-progress: false`) with a rationale comment, inserted above `jobs:`"
  key_links:
    - "auto-update.yml `--no-tag` -> update-version.py `if not args.no_tag:` guard at line 418 -> `create_and_push_tag` never runs in CI"
    - "auto-update.yml `group: addon-version-bump` == base-image-update.yml `group: addon-version-bump` -> one repo-scoped GitHub concurrency group -> the two bump workflows serialize"
    - "update-version.py tag-push output -> `.github/RELEASE.md` per-add-on `tags:`-trigger table"
    - "concurrency block position (above `jobs:`) -> every rlj line-ordering gate inside `jobs:` shifts uniformly and stays satisfied"
    - "Task 1's `--no-tag` -> Task 3's concurrency-comment extension states this workflow no longer tags -> the verbatim-frozen lines 17-19 ('the tag-collision risk is gone') read as history instead of as a claim about a tag that still exists"
---

<objective>
Stop `auto-update.yml` from tagging the wrong commit, stop `update-version.py` from claiming a
tag it just pushed produces a build, and serialize the two version-bump workflows against each
other with one shared concurrency group.

Root cause (proven, do NOT re-investigate): `auto-update.yml:89` calls
`internal/update-version.py` **before** the `git commit` on line 120. `update-version.py` tags
`HEAD` (line 418 -> `create_and_push_tag`), so the tag lands on the PRE-bump commit. Measured on
real history:

| tag | commit it points at | `build.yaml` VERSION at that commit |
|---|---|---|
| `meridian/v1.67.0-0` | `8c31d33` | `1.66.0` |
| `meridian/v1.68.0-0` | `9f45b96` | `1.66.0` |

`git merge-base --is-ancestor 9f45b96 d3682f6` exits 0 — the actual `1.68.0` bump commit
(`d3682f6`, 2026-09-09) is a descendant of the tagged commit, never the tagged commit itself.
Every auto-update tag is off by at least one, and `meridian/v1.68.0-0` is off by **two**: its
commit's `build.yaml` still reads `1.66.0`, not `1.67.0`. So never describe the tagged commit as
carrying "the previous version" — it carries *an older* version, and how much older is unbounded.

Purpose: the tag is a lie about which commit shipped a version, and the message
`update-version.py` prints after pushing it is a second lie (a build only fires for the three
add-ons with an active `tags:` trigger). Both mislead an operator debugging a missing image.
The shared concurrency group closes the remaining `git push` race: `base-image-update.yml` has
no concurrency protection at all today.
Output: three edited files, landing as ONE commit. No new files.
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
@internal/update-version.py
@.planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio/260909-rlj-PLAN.md
</context>

<verified_environment>
Measured on the current unmodified tree (2026-09-09, `8c6645f`). Do NOT re-derive; do NOT
contradict.

| Fact | Measured value |
|---|---|
| `auto-update.yml:89` | `python3 internal/update-version.py "$addon_name" "$latest_version" \|\| {` — no flags |
| `auto-update.yml` non-comment `internal/update-version.py` lines | 1 (line 89); with `--no-tag`: 0 |
| `auto-update.yml` loop | `while` at 55, `done < <(find … -name .upstream.yaml \| sort)` at 123, the `git commit` at 120 |
| edit window inside that loop | lines 87 (AUTO-02 comment), 88 (`--check-release` comment), 89 (the call) |
| `update-version.py` argparse | `--no-tag` / `--no-push` are **opt-out**; declared at 295-298; tag path 418-427 |
| `update-version.py` tag name | `<addon>/v<config_new>` — the subpatch-suffixed `config.yaml` version |
| `grep -c 'will trigger' internal/update-version.py` | **1** (line 275) |
| `grep -c 'tag is required' internal/update-version.py` | **1** (in the `create_and_push_tag` docstring) |
| `grep -c 'RELEASE\.md' internal/update-version.py` | **0** |
| `grep -c 'Pushed tag: {tag}' internal/update-version.py` | 1 (line 275; line 252 is `Pushed existing tag: {tag}` and does not match) |
| `create_and_push_tag` docstring sha256 | `1f1d918db6016c520cdd05548fe1a5b8304adb91b8b965148930952ae7a6ff1b` |
| that docstring's `paths:` / `tags:` / `RELEASE.md` counts | 0 / 0 / 0 |
| `internal/update-base-image.py` `git` operations | **none** — the only `git` substring hits are `raw.githubusercontent.com` URLs. base-image-update already pushes untagged bumps |
| `.upstream.yaml` present for | authentik, gatus, meridian, phone-logger (exactly 4) |
| active `tags:` trigger | `build-iac-runner.yml:9-10`, `build-network-tools.yml:9-10`, `build-terraform-bridge.yml:9-10` — none of the three has a `.upstream.yaml` |
| commented-out `tags:` trigger | the other six `build-*.yml` |
| `internal/check-version-tags.sh` callers | only `internal/setup-hooks.sh` (local pre-push hook). No CI job runs it. `LOCAL_BUILD_ADDONS=(iac-runner)` |
| that hook's blast radius | it only inspects add-on dirs changed in `remote_sha..local_sha` of the push being made. CI pushes run no hooks, and a CI bump is already on origin by the time a developer pushes — so dropping the tag cannot start blocking developer pushes |
| `auto-update.yml` concurrency | comment lines 8-19 (12 lines, sha256 `0540d26f95b79491675f4e3b1f3dbcd770400aa8c0fe056329af488263013eb0`), `concurrency:` at 20, `group: auto-update` at 21, `cancel-in-progress: false` at 22 |
| trailing `^#` run immediately above `concurrency:` | **12** |
| `base-image-update.yml` | **no** `concurrency:` block (`grep -c '^concurrency:$'` = 0); `jobs:` at line 8 |
| `.actionlint.yml` | only SC2086/SC2129/SC2001 excluded; `config-variables:` **empty** (any `vars.*` is flagged); only `ubuntu-latest` allowed |
| `pre-commit run actionlint --all-files` (v1.7.3) | PASSES |
| latest-release actionlint (`docker run --rm -v "$PWD":/repo --workdir /repo docker.io/rhysd/actionlint:latest -color`) | **1.7.12**, PASSES, rc=0 (image now cached locally; `docker` here is podman-emulated) |
| `make lint` (`pre-commit run --all-files`) | PASSES, all 21 hooks, rc=0 |
| `make validate-versions` | rc=0 |
| `python3 -m py_compile internal/update-version.py` | rc=0 |
| `--no-tag --dry-run meridian 1.99.0` / `meridian 1.99.0 --no-tag --dry-run` | both rc=0, and `git status --porcelain -- meridian` is empty afterwards |
| `python3 internal/update-version.py --help \| grep -c -- '--no-tag'` | 3 |
| local `actionlint` on PATH | **absent** — use the pre-commit hook + the container form above |
| `lint.yml:91-95` shell-lint step | ends in `\|\| echo "No shell scripts to check"`, which swallows the exit code. Repo-wide strict shellcheck exits 1 today (22 findings). **Do not gate on it; do not fix it here** |
| `.prettierignore` / `.markdownlint-cli2.yaml` | both exclude `.planning/` — this plan file is neither reformatted nor linted |
</verified_environment>

<locked_constraints>
Straight from the item text plus the sibling-coordination reading. Any deviation is a defect.

- **L-1** Do NOT re-investigate the off-by-one. It is proven in the objective table.
- **L-2** Task 1 adds `--no-tag` to the **existing** call on `auto-update.yml:89`, after the two
  positionals, plus a comment above it explaining that HEAD there is still the pre-bump commit.
- **L-3** Do **NOT** instead move the tag to after the commit, and do **NOT** introduce
  `git push --follow-tags`. `actions/checkout@v7` fetches no tags, so a combined push would be
  rejected non-atomically for an already-existing remote tag, return non-zero, and abort the step
  under `set -e` **before** the sibling's dispatch call runs — a real regression on the critical
  path, for a tag with no consumer. **Naming `--follow-tags` in a comment is explicitly
  ALLOWED** — GATE-T1-G's check for that literal is scoped to non-comment lines precisely so this
  rejected alternative can be documented at the call site without the gate rejecting correct work.
- **L-4** Task 2 rewrites the tag-push success output so it states the conditional (a build fires
  only when the caller's `tags:` trigger is active) and points at `.github/RELEASE.md`. The tag
  name must still be printed.
- **L-5** Task 2 also rewrites the `create_and_push_tag` docstring so `paths:` (push to `main`,
  active for all nine add-ons) and `tags:` (`<addon>/v*`, active only for iac-runner,
  network-tools, terraform-bridge) are named separately and not conflated. Do not restate that
  the tag is what makes the image exist — it is not.
- **L-6** Do NOT change `update-version.py`'s argparse surface: no flag added, removed, renamed
  or re-defaulted. `--no-tag` stays opt-out.
- **L-7** Task 3 adds the group name `addon-version-bump` to BOTH workflows, byte-identical, each
  with `cancel-in-progress: false`.
- **L-8** In `auto-update.yml`, **EXTEND** the existing 12-line rationale comment (append after
  it, leaving those 12 lines byte-identical and contiguous). Do not replace, reflow, or reorder
  them.
- **L-9** In `base-image-update.yml`, the `concurrency:` block is workflow-level: after `on:`,
  **above** `jobs:`, with its own rationale comment of at least 4 comment lines immediately above
  it. Nothing inside `jobs:` may change in Task 3.
- **L-10** **Forbidden literals in any comment line this plan adds to either workflow** — the
  sibling has unanchored single-value greps that a second match turns into a multi-line value and
  breaks: `GH_TOKEN`, `BASE_SHA`, `while IFS= read -r upstream_file; do`,
  `while IFS= read -r addon; do`, `name: Check and update base images`,
  `manually trigger lint.yml`, `./internal/dispatch-builds.sh`. Substitutions: call the sibling's
  script "the build dispatch"; call the credential "the default workflow token". `GITHUB_TOKEN` is
  measured NOT to be a substring of `GH_TOKEN`'s pattern (verified: `printf 'GITHUB_TOKEN\n' |
  grep -c 'GH_TOKEN'` is 0, and `auto-update.yml` has exactly one `GH_TOKEN` match today despite
  its NOTE comment naming `GITHUB_TOKEN`), but it is still on the forbidden list because the
  substitution above reads better and costs nothing. **`follow-tags` is deliberately NOT on this
  list** (see L-3): GATE-T1-G's check for it is scoped to non-comment lines, so a comment may name
  the rejected `git push --follow-tags` alternative freely. Likewise `no-tag` is not forbidden —
  Task 3's comment extension is required to contain it.
- **L-11** Nothing in `internal/check-version-tags.sh`, `internal/setup-hooks.sh`,
  `internal/update-base-image.py`, `.github/RELEASE.md`, `docs/AUTO_UPDATE_GUIDE.md`, or any
  `build-*.yml` is touched. Re-enabling a `tags:` trigger is out of scope. Documenting the
  dropped tag is sibling **260909-rlm**.
- **L-12** One commit, exactly the three declared paths.
</locked_constraints>

<sibling_supersession>
**260909-rlj GATE-T1-14 is intentionally invalidated by Task 1. This is the only such case, and
it is not a defect.**

rlj pins the sha256 of `auto-update.yml`'s whole per-add-on loop region (`while IFS= read -r
upstream_file; do` through the `-name .upstream.yaml` line) to
`7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc`, asserting **its own** edits
stayed outside that loop (rlj L-14). That assertion was true and its gate passed at rlj's commit.
`auto-update.yml:89` — the line this item must change — sits **inside** that region, so the pin
cannot survive this item.

The replacement is NARROWER, and a verifier's mutation probe disproved the original claim that it is stronger: code injected into the unpinned window (between the AUTO-02 anchor and the --check-release anchor) passes ALL of GATE-T1-A..F, while rlj's single whole-loop pin caught it. Recomputing a hash proves the pin is correct; only mutation proves it CATCHES. The avoidable part of the loss is that Region A could end at the --check-release comment INCLUSIVE, leaving only comment text unpinned. Task 1 pins the two sub-regions that flank the
edit site, so the ONLY lines that can differ from the pre-change tree are the three-line window
[AUTO-02 comment … the call]:

| region | anchors | pinned sha256 |
|---|---|---|
| A | `while IFS= read -r upstream_file; do` .. line before the `Update the 3-file version set (AUTO-02)` comment | `c1d953504308eca666770a7ee73f6ec1cb7b90b64cf248a51cb7341677cecd20` |
| B | the `ERROR: update-version.py failed for` line .. the `-name .upstream.yaml` line | `bfa308db940b89735bfc146c31294b393eb3981a2efb0509066b9c65e99b4ec6` |

Both were measured PASSING on the unmodified tree and must still pass after this item. Task 1
additionally asserts the whole-loop sha256 **differs** from rlj's pin — positive proof the edit
landed at the intended site rather than somewhere else in the file.

**rlj's other eight gates over these two files all survive and are re-asserted here:**

- Line-ordering gates (GATE-T1-12, GATE-T3-3) use only relative comparisons (`d == p+1`,
  `k == d+1`, `d < e`, `b < w`). Task 1 inserts comment lines inside the loop and Task 3 inserts
  lines above `jobs:`; both shift `p`/`d`/`e`/`k` uniformly and neither crosses `b`/`w`.
- GATE-T1-13 / GATE-T3-4 need `grep -c '^ *#.*build-' >= 1` — additive only.
- GATE-T3-2 does `g=$(grep -n 'GH_TOKEN' … | cut -d: -f1)` and compares `$g` numerically, so a
  second `GH_TOKEN` match anywhere in the file would make `$g` multi-line and break it. That is
  what L-10 exists for. (`GITHUB_TOKEN` is measured not to match that pattern, so rlj's existing
  NOTE comment is not a second match — but Task 3's own comment must still avoid both, and
  GATE-T3-J asserts that scoped to the block Task 3 adds.)
- GATE-T3-1's `! grep -q 'GH_REPO'` and GATE-T3-5's base-image loop pin
  (`2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc`) are untouched by Task 3's
  above-`jobs:` insertion; both are re-asserted in Task 3.

Record this supersession in the SUMMARY so a later verifier that re-runs rlj's gate set knows
GATE-T1-14 is expected red and why.
</sibling_supersession>

<tasks>

<task type="tracer">
  <name>Task 1: Stop auto-update.yml tagging the pre-bump commit</name>
  <files>.github/workflows/auto-update.yml</files>
  <precondition>Sibling 260909-rlj has landed: `grep -q '^ *actions: write$' .github/workflows/auto-update.yml && grep -q '^ *\./internal/dispatch-builds.sh' .github/workflows/base-image-update.yml` exits 0. If it does not, halt — this item's rlj-invariant gates and the `d == p+1` ordering they re-assert have no meaning against a pre-rlj tree.</precondition>
  <action>
Single-line behavior change plus its rationale comment, both inside the per-add-on loop of
`.github/workflows/auto-update.yml`, at the existing invocation site (currently lines 87-89).

Edit 1 — append the opt-out flag AFTER both positionals, so the call reads exactly:

    python3 internal/update-version.py "$addon_name" "$latest_version" --no-tag || {

Keep the 12-space indentation, keep the trailing `|| {`, and do not touch the four lines of the
`|| { … }` error block that follow it (per L-2, and Region B pins them).

Edit 2 — insert a rationale comment immediately BELOW the existing
`# Do NOT pass --check-release …` line and ABOVE the call, at the same 12-space indentation, as
shell comment lines inside the `run: |` block.

**Length budget: AT MOST 6 comment lines** (a 4-line comment is comfortable; 6 is the ceiling).
GATE-T1-F accepts the contiguous comment run immediately above the call and asserts that run is
between 3 and 8 lines — 2 frozen anchors plus 1..6 inserted lines. Six is therefore the largest
comment the gate admits, and any comment within the budget is fully inside the accepted window no
matter which of its lines the required tokens land on. Do not exceed 6; do not insert a blank
line between the anchors and the call (a blank breaks the run and fails the gate).

The comment must state, in any order:

1. This call runs BEFORE the `git commit` further down the loop, so HEAD at this point is still
   the pre-bump commit — use the token "pre-bump" verbatim, GATE-T1-F greps the run for it.
2. Without the flag `update-version.py` tags that HEAD, i.e. the wrong commit.
3. The measured proof: `meridian/v1.68.0-0` points at `9f45b96`, whose `meridian/build.yaml`
   still reads VERSION 1.66.0. (`meridian/v1.67.0-0` -> `8c31d33` -> 1.66.0 is an equally valid
   citation. Either is fine; what is NOT fine is calling that "the previous version" — the
   1.68.0 tag is two versions stale. Write "an older version", or just cite the measured pair.)
4. Releases are tagged out of band; `.github/RELEASE.md` is the reference — the token
   `RELEASE.md` must appear in the run, GATE-T1-F greps for it too.

Naming the rejected `--follow-tags` alternative here is allowed (L-3): GATE-T1-G's check for that
literal is scoped to non-comment lines, so documenting the rejected route cannot self-invalidate
the gate. <!-- planner-discipline-allow: follow-tags -->

Keep every line under 120 characters, plain ASCII, one space after each `#`, no trailing
whitespace, no backticks (they buy nothing in a shell comment and only give actionlint's embedded
shellcheck something to think about).

L-10 applies to Edit 2's comment text. L-3 applies to the whole task: do not relocate the tag
call, do not add `--follow-tags`, do not touch `git push`.

Leave the two existing anchor comments (`# Update the 3-file version set (AUTO-02)` and the
`--check-release` one) byte-identical — the region gates locate themselves by grepping for them.
  </action>
  <verify>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -v '^[[:space:]]*#' "$f" | grep -c 'internal/update-version\.py')" -eq 1 ] && [ "$(grep -v '^[[:space:]]*#' "$f" | grep -c 'internal/update-version\.py .*--no-tag')" -eq 1 ] && echo GATE-T1-A-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -c '^ *while IFS= read -r upstream_file; do$' "$f")" -eq 1 ] && [ "$(grep -c 'Update the 3-file version set (AUTO-02)' "$f")" -eq 1 ] && s=$(grep -n '^ *while IFS= read -r upstream_file; do$' "$f" | cut -d: -f1) && u=$(grep -n 'Update the 3-file version set (AUTO-02)' "$f" | cut -d: -f1) && [ "$s" -lt "$u" ] && [ "$(sed -n "${s},$((u-1))p" "$f" | sha256sum | cut -d' ' -f1)" = "c1d953504308eca666770a7ee73f6ec1cb7b90b64cf248a51cb7341677cecd20" ] && echo GATE-T1-B-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -c 'ERROR: update-version.py failed for' "$f")" -eq 1 ] && [ "$(grep -c -- '-name .upstream.yaml' "$f")" -eq 1 ] && b=$(grep -n 'ERROR: update-version.py failed for' "$f" | cut -d: -f1) && e=$(grep -n -- '-name .upstream.yaml' "$f" | cut -d: -f1) && [ "$b" -lt "$e" ] && [ "$(sed -n "${b},${e}p" "$f" | sha256sum | cut -d' ' -f1)" = "bfa308db940b89735bfc146c31294b393eb3981a2efb0509066b9c65e99b4ec6" ] && echo GATE-T1-C-PASS</automated>
    <automated>[ "$(awk 'index($0,"while IFS= read -r upstream_file; do"){f=1} f{print} index($0,"-name .upstream.yaml"){f=0}' .github/workflows/auto-update.yml | sha256sum | cut -d' ' -f1)" != "7b7356ab16e89075cb44bd9ae13b94df53580b4b33a10e3f308e15d4b6f2f8bc" ] && echo GATE-T1-D-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -cF '# Update the 3-file version set (AUTO-02)' "$f")" -eq 1 ] && [ "$(grep -cF '# Do NOT pass --check-release (that flag is interactive and will hang the workflow)' "$f")" -eq 1 ] && echo GATE-T1-E-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; c=$(awk '!/^[[:space:]]*#/ && /internal\/update-version\.py/{print NR}' "$f"); [ "$(printf '%s\n' "$c" | grep -c .)" -eq 1 ] && r=$(awk -v n="$c" 'NR<n{ if ($0 ~ /^[[:space:]]*#/) {k++} else {k=0} } END{print k+0}' "$f") && [ "$r" -ge 3 ] && [ "$r" -le 8 ] && w=$(sed -n "$((c-r)),$((c-1))p" "$f") && printf '%s\n' "$w" | grep -q 'pre-bump' && printf '%s\n' "$w" | grep -q 'RELEASE\.md' && echo GATE-T1-F-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -v '^[[:space:]]*#' "$f" | grep -c 'follow-tags')" -eq 0 ] && [ "$(grep -c '^ *git push$' "$f")" -eq 1 ] && grep -q '^ *actions: write$' "$f" && grep -q '^ *export BASE_SHA$' "$f" && ! grep -q 'export BASE_SHA=\$(' "$f" && [ "$(grep -c 'manually trigger lint.yml' "$f")" -eq 0 ] && [ "$(grep -c '^ *#.*build-' "$f")" -ge 1 ] && p=$(grep -n '^ *git push$' "$f" | cut -d: -f1) && d=$(grep -n '^ *\./internal/dispatch-builds.sh' "$f" | cut -d: -f1) && e=$(grep -n '^ *exit \$ERRORS$' "$f" | cut -d: -f1) && b=$(grep -n 'BASE_SHA=\$(git rev-parse HEAD)' "$f" | cut -d: -f1) && w=$(grep -n 'while IFS= read -r upstream_file; do' "$f" | cut -d: -f1) && k=$(awk -v n="$d" 'NR>n && $0 ~ /^ *fi$/{print NR; exit}' "$f") && [ "$d" -eq "$((p+1))" ] && [ "$k" -eq "$((d+1))" ] && [ "$d" -lt "$e" ] && [ "$b" -lt "$w" ] && echo GATE-T1-G-PASS</automated>
    <automated>pre-commit run --files .github/workflows/auto-update.yml</automated>
  </verify>
  <done>`auto-update.yml`'s single non-comment `update-version.py` invocation carries `--no-tag`; a contiguous comment run of at most 6 inserted lines immediately above it names the pre-bump reasoning and `.github/RELEASE.md`, and GATE-T1-F's acceptance window is that run's measured extent (3..8 lines) rather than a fixed lookback, so the unpinned edit window is bounded in size; both flanking loop regions hash to their pre-change baselines while the whole-loop hash differs from rlj's pin; every re-asserted rlj auto-update invariant still passes; `pre-commit` is clean on the file.</done>
  <reversibility rating="reversible">Deleting ` --no-tag` from one line restores the previous behavior exactly; no state, no schema, no published artifact.</reversibility>
</task>

<task type="auto">
  <name>Task 2: Stop update-version.py claiming a pushed tag produces a build</name>
  <files>internal/update-version.py</files>
  <action>
Two prose corrections in `internal/update-version.py`. No behavior change, no argparse change
(L-6), no new imports.

Edit 1 — the tag-push success output at line 275. Today it prints the tag name followed by a
clause asserting a build happens. Split it into the tag name plus a correct conditional, e.g.:

    print(f"🚀 Pushed tag: {tag}")
    print("   A build runs only if that add-on's build-<addon>.yml has an active 'tags:'")
    print("   trigger — six of the nine have it commented out. See .github/RELEASE.md.")

The `Pushed tag: {tag}` f-string must survive (a gate counts it), and `.github/RELEASE.md` must
appear here. Keep the existing return-value logic and the surrounding `if push_result.returncode
!= 0:` branch untouched.

Edit 2 — the `create_and_push_tag` docstring (lines 199-209). It currently conflates two
independent triggers and asserts the tag is what makes the image resolvable, which is false for
six of nine add-ons. Rewrite the body so it names them separately, e.g.:

    """Create an annotated git tag for the new version and push it to origin.

    Tag format is '<addon>/v<version>' (e.g. 'authentik/v2026.8.0'). The tag names the
    release; it is not what builds the image. Each .github/workflows/build-<addon>.yml
    carries two independent triggers and they must not be conflated:

    - `paths:` on a push to main — active for all nine add-ons.
    - `tags:` on '<addon>/v*' — active only for iac-runner, network-tools and
      terraform-bridge; commented out for the other six.

    So for most add-ons pushing this tag creates no workflow run at all. See
    .github/RELEASE.md for the per-add-on table.

    Returns True on success.
    """

The rewritten docstring must contain the literals `paths:`, `tags:` and `RELEASE.md` (gates grep
for all three), must not restate that the tag is a prerequisite for the image, and must keep the
`Returns True on success.` line. Keep the module's conventions: 4-space indent, lines under 120
characters, no type-hint or signature change.
  </action>
  <verify>
    <automated>p=internal/update-version.py; [ "$(grep -c 'will trigger' "$p")" -eq 0 ] && [ "$(grep -c 'tag is required' "$p")" -eq 0 ] && [ "$(grep -c 'RELEASE\.md' "$p")" -ge 2 ] && [ "$(grep -c 'Pushed tag: {tag}' "$p")" -eq 1 ] && echo GATE-T2-A-PASS</automated>
    <automated>p=internal/update-version.py; d=$(awk '/^def create_and_push_tag/{f=1} f{print; if ($0=="    \"\"\"") exit}' "$p"); [ -n "$d" ] && [ "$(printf '%s\n' "$d" | sha256sum | cut -d' ' -f1)" != "1f1d918db6016c520cdd05548fe1a5b8304adb91b8b965148930952ae7a6ff1b" ] && printf '%s\n' "$d" | grep -q 'RELEASE\.md' && printf '%s\n' "$d" | grep -q 'paths:' && printf '%s\n' "$d" | grep -q 'tags:' && printf '%s\n' "$d" | grep -q 'Returns True on success' && echo GATE-T2-B-PASS</automated>
    <automated>p=internal/update-version.py; grep -q '^def create_and_push_tag(version: str, addon_name: str, push: bool = True, dry_run: bool = False) -> bool:$' "$p" && [ "$(grep -c "add_argument('--no-tag'" "$p")" -eq 1 ] && [ "$(grep -c "add_argument('--no-push'" "$p")" -eq 1 ] && [ "$(grep -c "add_argument('--dry-run'" "$p")" -eq 1 ] && [ "$(grep -c "add_argument('--check-release'" "$p")" -eq 1 ] && echo GATE-T2-C-PASS</automated>
    <automated>python3 -m py_compile internal/update-version.py && [ "$(python3 internal/update-version.py --help | grep -c -- '--no-tag')" -ge 1 ] && echo GATE-T2-D-PASS</automated>
    <automated>python3 internal/update-version.py --no-tag --dry-run meridian 1.99.0 >/dev/null && python3 internal/update-version.py meridian 1.99.0 --no-tag --dry-run >/dev/null && [ -z "$(git status --porcelain -- meridian)" ] && echo GATE-T2-E-PASS</automated>
    <automated>pre-commit run --files internal/update-version.py</automated>
  </verify>
  <done>`internal/update-version.py` no longer asserts a build follows the tag push and no longer claims the tag is a prerequisite; the tag name is still printed; `.github/RELEASE.md` is referenced from both the output and the docstring; the docstring names `paths:` and `tags:` separately; the argparse surface and `create_and_push_tag`'s signature are byte-identical; `--no-tag` still parses before and after the positionals with no side effects.</done>
  <reversibility rating="reversible">Prose-only; `git checkout` of the one file restores it.</reversibility>
</task>

<task type="auto">
  <name>Task 3: Serialize both bump workflows on one shared concurrency group</name>
  <files>.github/workflows/auto-update.yml, .github/workflows/base-image-update.yml</files>
  <action>
Give both version-bump workflows the same repo-scoped GitHub concurrency group so they cannot
overlap. `base-image-update.yml` has no concurrency block today, so it has no protection against
a non-fast-forward `git push` race against `auto-update.yml`, and both could ask for a build of
the same ref.

Edit 1 — `.github/workflows/auto-update.yml`: change `group: auto-update` to
`group: addon-version-bump`. Leave `concurrency:` and `cancel-in-progress: false` as they are.

Edit 2 — `.github/workflows/auto-update.yml`: **append** to the existing rationale comment (L-8).
Leave lines 8-19 byte-identical and contiguous; add the new lines after line 19 and before
`concurrency:`. They must explain: the group is now shared with
`.github/workflows/base-image-update.yml` (cron 07:00 UTC), which commits and pushes version
bumps to `main` the same way; before sharing, that workflow had no concurrency block at all, so
an overlap reproduced the same non-fast-forward race described above, just across workflows
instead of within one; one repo-scoped group makes the two mutually exclusive and also stops both
runs from asking for a build of the same ref; the crons are an hour apart and this workflow is
observed at 8-28s, so the queueing cost is negligible.

The extension must ALSO reconcile the paragraph it follows. Frozen lines 17-19 read "With the new
`<addon>/v<version>` tag schema the tag-collision risk is gone, but the git-push race remains" —
after Task 1 this workflow creates **no tag at all**, so that sentence reasons about a tag that no
longer exists. L-8 forbids editing it, so the extension is the only place it can be reconciled:
state that as of Task 1 this workflow passes `--no-tag` and creates no tag, that the tag-schema
sentence above is therefore history and not a live claim, and point at the call-site comment in
the per-add-on loop for the reason. The token `no-tag` must appear in the extension — GATE-T3-B
greps the appended lines for it. This is in scope for THIS item and must not be deferred to
sibling 260909-rlm, which owns `.github/RELEASE.md` and `docs/AUTO_UPDATE_GUIDE.md`, not this
workflow's inline comments.

Edit 3 — `.github/workflows/base-image-update.yml`: insert a workflow-level block after the `on:`
mapping and above `jobs:` (L-9) — one blank line, then at least four `^#` rationale comment lines,
then:

    concurrency:
      group: addon-version-bump
      cancel-in-progress: false

then one blank line before `jobs:`. The rationale must cover: both workflows commit version bumps
to `main` and push them, so an overlap yields a non-fast-forward push (or a green run that pushed
the wrong content); the group name is deliberately shared with
`.github/workflows/auto-update.yml` because a repo-scoped group is what makes the two mutually
exclusive; it also stops both runs from asking for a build of the same ref;
`cancel-in-progress: false` so the second run queues rather than aborting either.

Both comment blocks: **L-10's forbidden-literal list applies verbatim** — read it in
`<locked_constraints>` before writing either comment, and phrase the rationale with the
substitutions L-10 prescribes. Keep each line under 120 characters, plain ASCII (use `-`, not an
em dash, matching the existing block), one space after `#`, no trailing whitespace, no tabs.
Nothing inside either file's `jobs:` mapping changes in this task.
  </action>
  <verify>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -v '^[[:space:]]*#' "$f" | grep '^  group:')" = "  group: addon-version-bump" ] && [ "$(grep -c '^  cancel-in-progress: false$' "$f")" -eq 1 ] && [ "$(grep -c '^concurrency:$' "$f")" -eq 1 ] && echo GATE-T3-A-PASS</automated>
    <automated>f=.github/workflows/auto-update.yml; [ "$(grep -cxF '# Serialize auto-update runs so two of them cannot race for the same' "$f")" -eq 1 ] && [ "$(grep -c '^concurrency:$' "$f")" -eq 1 ] && s=$(grep -nxF '# Serialize auto-update runs so two of them cannot race for the same' "$f" | cut -d: -f1) && c=$(grep -n '^concurrency:$' "$f" | cut -d: -f1) && [ "$s" -lt "$c" ] && [ "$(sed -n "${s},$((s+11))p" "$f" | sha256sum | cut -d' ' -f1)" = "0540d26f95b79491675f4e3b1f3dbcd770400aa8c0fe056329af488263013eb0" ] && k=$(awk -v n="$c" 'NR<n{ if ($0 ~ /^#/) {k++} else {k=0} } END{print k+0}' "$f") && [ "$k" -gt 12 ] && [ "$s" -eq "$((c-k))" ] && [ "$(sed -n "$((s+12)),$((c-1))p" "$f" | grep -c 'no-tag')" -ge 1 ] && echo GATE-T3-B-PASS</automated>
    <automated>f=.github/workflows/base-image-update.yml; c=$(grep -n '^concurrency:$' "$f" | cut -d: -f1); j=$(grep -n '^jobs:$' "$f" | cut -d: -f1); [ "$(grep -c '^concurrency:$' "$f")" -eq 1 ] && [ -n "$c" ] && [ -n "$j" ] && [ "$c" -lt "$j" ] && [ "$(grep -c '^  group: addon-version-bump$' "$f")" -eq 1 ] && [ "$(grep -c '^  cancel-in-progress: false$' "$f")" -eq 1 ] && k=$(awk -v n="$c" 'NR<n{ if ($0 ~ /^#/) {k++} else {k=0} } END{print k+0}' "$f") && [ "$k" -ge 4 ] && echo GATE-T3-C-PASS</automated>
    <automated>a=$(grep -h '^  group: ' .github/workflows/auto-update.yml || true); b=$(grep -h '^  group: ' .github/workflows/base-image-update.yml || true); [ "$a" = "  group: addon-version-bump" ] && [ "$b" = "  group: addon-version-bump" ] && echo GATE-T3-D-PASS</automated>
    <automated>f=.github/workflows/base-image-update.yml; grep -q '^ *actions: write$' "$f" && ! grep -q 'GH_REPO' "$f" && [ "$(grep -c 'GH_TOKEN' "$f")" -eq 1 ] && grep 'GH_TOKEN' "$f" | grep -q 'secrets.GITHUB_TOKEN' && n=$(grep -n 'name: Check and update base images' "$f" | cut -d: -f1) && g=$(grep -n 'GH_TOKEN' "$f" | cut -d: -f1) && r=$(awk -v s="$n" 'NR>s && $0 ~ /^ *run: \|/{print NR; exit}' "$f") && [ "$g" -gt "$n" ] && [ "$g" -lt "$r" ] && echo GATE-T3-E-PASS</automated>
    <automated>ok=1; for f in .github/workflows/auto-update.yml .github/workflows/base-image-update.yml; do c=$(grep -n '^concurrency:$' "$f" | cut -d: -f1); if [ -z "$c" ]; then ok=0; elif awk -v n="$c" 'NR<n{ if ($0 ~ /^#/) {b=b"\n"$0} else {b=""} } END{print b}' "$f" | grep -qE 'GH_TOKEN|BASE_SHA|IFS= read|dispatch-builds|Check and update base images|manually trigger lint'; then ok=0; fi; done; [ "$ok" -eq 1 ] && echo GATE-T3-J-PASS</automated>
    <automated>f=.github/workflows/base-image-update.yml; p=$(grep -n '^ *git push$' "$f" | cut -d: -f1); d=$(grep -n '^ *\./internal/dispatch-builds.sh' "$f" | cut -d: -f1); e=$(grep -n '^ *exit \$ERRORS$' "$f" | cut -d: -f1); b=$(grep -n 'BASE_SHA=\$(git rev-parse HEAD)' "$f" | cut -d: -f1); w=$(grep -n 'while IFS= read -r addon; do' "$f" | cut -d: -f1); [ -n "$p" ] && [ -n "$d" ] && [ -n "$e" ] && [ -n "$b" ] && [ -n "$w" ] && k=$(awk -v n="$d" 'NR>n && $0 ~ /^ *fi$/{print NR; exit}' "$f") && [ "$d" -eq "$((p+1))" ] && [ "$k" -eq "$((d+1))" ] && [ "$d" -lt "$e" ] && [ "$b" -lt "$w" ] && echo GATE-T3-F-PASS</automated>
    <automated>[ "$(awk 'index($0,"while IFS= read -r addon; do"){f=1} f{print} f && $0 ~ /^ *\)$/{f=0}' .github/workflows/base-image-update.yml | sha256sum | cut -d' ' -f1)" = "2dace2d53d8b7c7a697999e0db87256667bcfe245826ee88284ef74bdab419cc" ] && echo GATE-T3-G-PASS</automated>
    <automated>pre-commit run actionlint --all-files && pre-commit run yamllint --files .github/workflows/auto-update.yml .github/workflows/base-image-update.yml && echo GATE-T3-H-PASS</automated>
    <automated>docker run --rm -v "$PWD":/repo --workdir /repo docker.io/rhysd/actionlint:latest -color && echo GATE-T3-I-PASS</automated>
  </verify>
  <done>Both bump workflows declare a workflow-level `concurrency` block whose `group` is the byte-identical string `addon-version-bump` with `cancel-in-progress: false`; `auto-update.yml`'s original 12 rationale lines are preserved verbatim and contiguous, sit at the TOP of the comment run (proving append-after, not prepend-before), and the run is now longer than 12 lines, with the appended lines naming `no-tag` so the frozen tag-schema sentence at 17-19 reads as history; `base-image-update.yml`'s block sits above `jobs:` with at least four rationale lines and its `jobs:` mapping is unchanged (loop pin `2dace2d5…` intact, single `GH_TOKEN` match, rlj ordering preserved); both actionlint v1.7.3 and latest-release actionlint pass.</done>
  <reversibility rating="reversible">Reverting is a rename back to `group: auto-update` plus deleting one block; no external state.</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GitHub Actions scheduled run -> `main` | Two cron workflows commit and push to the default branch with the default workflow token. Nothing here changes the credential or its scope. |
| `git tag` / `git push origin <tag>` -> `origin` refs | Task 1 removes this write from the CI path entirely; the local `make update-version` path keeps it. |
| CI stdout -> operator | The messages Task 2 corrects are the operator's primary signal about whether an image will exist. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-rll-01 | Repudiation | dropped `<addon>/v<version>` tag on the auto-update path | low | accept | The tag it replaces pointed at the WRONG commit (`meridian/v1.67.0-0` -> `8c31d33`, `build.yaml` still `1.66.0`), so it was worse than absent: an auditor reading it drew a false conclusion. The surviving record is the `chore(<addon>): update to <version>` commit and its 3-file diff. Real releases still tag via `make update-version` with no `--no-tag`. |
| T-rll-02 | Tampering | `internal/check-version-tags.sh` ghcr-404 pre-push guard | low | accept | The hook only inspects add-on dirs changed in the `remote_sha..local_sha` range of the push being made. CI pushes run no hooks, and a CI bump is already on origin before any developer push, so its range never contains one. No behavior change; the guard's coverage of developer-initiated bumps is untouched. |
| T-rll-03 | Denial of Service | shared `addon-version-bump` concurrency group | low | mitigate | A hung run could block the other workflow. Both carry explicit `timeout-minutes` caps (auto-update 20, base-image 15), so the queue always drains. The crons are an hour apart and auto-update is observed at 8-28s. `cancel-in-progress: false` is mandatory (L-7) — `true` would let base-image abort an in-flight auto-update mid-push. |
| T-rll-04 | Information Disclosure | new comment blocks in two workflows | low | mitigate | L-10 forbids naming any credential identifier in the added comments, and the rationale text is required to refer to "the default workflow token" instead. GATE-T3-E asserts exactly one `GH_TOKEN` match remains in `base-image-update.yml`. |
| T-rll-05 | Elevation of Privilege | workflow permissions / secrets | low | accept | This item adds no `permissions:` key, no secret, no `vars.*` reference, no `run:` step, and no network call. `.actionlint.yml`'s empty `config-variables:` and single-runner allowlist are therefore not exercised; latest-release actionlint (1.7.12) is run as a gate anyway. |
| T-rll-06 | Spoofing | `workflow_dispatch` of the same ref by two overlapping runs | medium | mitigate | This is the concrete race the shared group closes: two bump runs could each push and then request a build of a ref the other had moved. Serializing the group makes the second run observe the first run's pushed HEAD. |
| T-rll-SC | Tampering | npm/pip/cargo installs | n/a | accept | Zero new package-manager installs and zero new dependencies. `python3`, `git`, `awk`, `sed`, `sha256sum` and `pre-commit` are already present; the latest-actionlint gate pulls a pinned-by-name OCI image that is already cached locally. No `Package Legitimacy Audit` is required and no legitimacy checkpoint is inserted. |
</threat_model>

<source_coverage_audit>
Single source: the item description. No ROADMAP phase, no REQUIREMENTS IDs, no RESEARCH.md, no
CONTEXT.md D-XX decisions apply to a quick-batch item.

| Source item | Status | Where |
|---|---|---|
| (a) `--no-tag` at `auto-update.yml:89` + pre-bump-HEAD comment | COVERED | Task 1, edits 1-2 |
| (a) no-live-consumer reasoning recorded, not re-litigated | COVERED | `<verified_environment>` rows 12-16, T-rll-01/02 |
| (a) explicit refusal to tag-after-commit / `--follow-tags` | COVERED | L-3, GATE-T1-G (`follow-tags` count == 0 over non-comment lines only, so a comment may name the rejected alternative) |
| (b) line-275 message reduced to the conditional + RELEASE.md pointer | COVERED | Task 2 edit 1, GATE-T2-A |
| (b) `create_and_push_tag` docstring un-conflated (lines 199-209) | COVERED | Task 2 edit 2, GATE-T2-B |
| (c) shared group `addon-version-bump` in BOTH workflows | COVERED | Task 3 edits 1+3, GATE-T3-A/C/D |
| (c) EXTEND auto-update's 12-line comment, do not replace | COVERED | L-8, GATE-T3-B (verbatim pin + run-start pin + run length > 12) |
| (c) extension reconciles frozen lines 17-19 (no tag is created any more) | COVERED | Task 3 edit 2, GATE-T3-B (`no-tag` in the appended lines) |
| (c) base-image gets a concurrency block where it had none | COVERED | Task 3 edit 3, GATE-T3-C |
| VERIFY: actionlint v1.7.3 **and** latest release | COVERED | GATE-T3-H (v1.7.3), GATE-T3-I (1.7.12) |
| VERIFY: empty `config-variables`, `ubuntu-latest`-only | COVERED | no `vars.*` and no runner change added (T-rll-05); both actionlint gates would flag either |
| VERIFY: `python3 -m py_compile internal/update-version.py` | COVERED | GATE-T2-D |
| VERIFY: `make validate-versions` + `make lint` | COVERED | `<verification>` |
| VERIFY: `--no-tag` accepted before AND after the positionals | COVERED | GATE-T2-E (both orderings, plus a clean-tree assertion) |

Deliberately excluded (belongs to a sibling or is an explicit non-goal): re-enabling any `tags:`
trigger; rewriting `.github/RELEASE.md` / `docs/AUTO_UPDATE_GUIDE.md` (260909-rlm); the
`verify-image-availability` script (260909-rlk); collapsing the nine `build-*.yml` (260909-rln);
un-swallowing `lint.yml:91-95` and the 22 pre-existing shellcheck findings (separate ledger item,
out of scope for every item in this batch).
</source_coverage_audit>

<verification>
After all three tasks, from the repo root:

```bash
make validate-versions                 # expect rc=0 (baseline rc=0)
make lint                              # expect rc=0, all 21 hooks Passed (baseline rc=0)
python3 -m py_compile internal/update-version.py
docker run --rm -v "$PWD":/repo --workdir /repo docker.io/rhysd/actionlint:latest -color
git diff --stat                        # expect exactly the three declared paths
```

Then re-run every `GATE-*-PASS` from the three tasks and confirm each prints and exits 0.

**Expected red, by design:** rlj's `GATE-T1-14` (auto-update loop-region sha256 ==
`7b7356ab…f2f8bc`). See `<sibling_supersession>` — Task 1's `GATE-T1-B`/`GATE-T1-C`/`GATE-T1-D`
triple replaces it and is NARROWER - not stronger: a mutation probe showed the unpinned window admits undetected code, which rlj's pin caught. See the corrected note above. Every other rlj gate over these two files is
re-asserted inside Tasks 1 and 3 and must be green.

Deliberately NOT verified here (needs a live GitHub run): that a real auto-update run creates no
tag and that the two workflows actually queue behind one another. The first is provable from the
next auto-update run's log plus `git ls-remote --tags origin`; the second only from two
overlapping runs. Neither is reachable from this repo checkout, and the image-availability
question belongs to sibling 260909-rlk.
</verification>

<success_criteria>
- Every `GATE-*-PASS` marker across the three tasks prints, and every gate exits 0.
- `make lint` and `make validate-versions` both rc=0; both actionlint versions clean.
- `git diff --stat` shows exactly `.github/workflows/auto-update.yml`,
  `.github/workflows/base-image-update.yml`, `internal/update-version.py` — one commit.
- No new file, no deleted file, no `.upstream.yaml` or `build-*.yml` touched.
- `internal/update-version.py` behavior is byte-for-byte equivalent: argparse surface unchanged,
  `create_and_push_tag`'s signature unchanged, only two prose blocks differ.
- The SUMMARY records the GATE-T1-14 supersession explicitly, so a verifier re-running rlj's gate
  set knows that one red is expected and why.
- No scope creep into rlk/rlm/rln territory: no image-availability script, no doc rewrite, no
  `build.yml` consolidation, no `tags:` trigger re-enabled, no `lint.yml` change.
</success_criteria>

<handoff_notes>
For 260909-rlm (STAGE 5), which documents this end state:

- After this item, `auto-update.yml` creates **no** git tag at all. `base-image-update.yml` never
  did (`internal/update-base-image.py` has no git operations). Both bump workflows are therefore
  consistent: they push an untagged version-bump commit and then explicitly request a build.
- The historical mis-tagging is documentable from the repo itself:
  `git show "$(git rev-list -n1 meridian/v1.67.0-0):meridian/build.yaml"` prints a file whose
  VERSION is still `1.66.0` (one version stale), and the same command for `meridian/v1.68.0-0`
  (`9f45b96`) also prints `1.66.0` — **two** versions stale. The skew is "at least one", not
  exactly one, so do not describe a tagged commit as carrying "the previous version". Existing
  wrong tags are left in place — this item does not rewrite or delete published refs.
- `.github/RELEASE.md` is now cited from two places in `internal/update-version.py` (the tag-push
  output and the `create_and_push_tag` docstring), so its per-add-on `tags:`-trigger table is
  load-bearing operator documentation and must stay accurate.
- The shared concurrency group is named `addon-version-bump` and is repo-scoped; a third
  version-bumping workflow added later must join the same group or it reopens the push race.
</handoff_notes>

<output>
Create `.planning/quick/stage-4-depends-on-stage-1-same-workflow-files-fix-the-tag-o/260909-rll-SUMMARY.md` when done.
</output>
