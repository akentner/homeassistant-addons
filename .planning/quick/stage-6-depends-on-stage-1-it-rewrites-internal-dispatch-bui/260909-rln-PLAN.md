---
phase: quick-260909-rln
plan: 01
type: execute
wave: 3
quick_id: 260909-rln
depends_on:
  - 260909-rlj
  - 260909-rlm
files_modified:
  - .github/workflows/build.yml
  - .github/workflows/_build-template.yml
  - internal/dispatch-builds.sh
  - internal/check-version-tags.sh
  - internal/update-version.py
  - .github/RELEASE.md
  - README.md
  - docs/DEVELOPMENT.md
  - docs/WEBHOOK_SETUP.md
  - docs/UPDATE_VERSION.md
  - docs/AUTO_UPDATE_GUIDE.md
files_deleted:
  - .github/workflows/build-authentik.yml
  - .github/workflows/build-coding-assistants.yml
  - .github/workflows/build-gatus.yml
  - .github/workflows/build-iac-runner.yml
  - .github/workflows/build-markdown-renderer.yml
  - .github/workflows/build-meridian.yml
  - .github/workflows/build-network-tools.yml
  - .github/workflows/build-phone-logger.yml
  - .github/workflows/build-terraform-bridge.yml
autonomous: true
requirements:
  - QUICK-260909-rln-a
  - QUICK-260909-rln-b
  - QUICK-260909-rln-c
  - QUICK-260909-rln-d
  - QUICK-260909-rln-e
estimate:
  tokens: 78000
  raw_tokens: 78000
  tasks: 3
  confidence: low
must_haves:
  truths:
    - "A push to main that changes exactly one add-on's config.yaml produces build legs for exactly that one add-on — today one build-<addon>.yml run, afterwards one build.yml run whose matrix contains only that add-on."
    - "coding-assistants builds two arch legs and every other add-on exactly one, with the leg set read from <addon>/build.yaml build_from keys (falling back to config.yaml arch:) — no workflow file, input or matrix literal carries an arch list (D-04)."
    - "addon-display-name and addon-description reaching _build-template.yml are read from <addon>/config.yaml name:/description:, so the 8-of-9 description drift measured on the deleted callers cannot recur (D-04)."
    - "An automated version bump issues exactly ONE workflow_dispatch naming every changed add-on, and never a dispatch whose addons value is empty — empty means all nine (D-05)."
    - "Pushing an <addon>/v* tag builds nothing at all; the version-bump commit's paths: trigger, the bump workflows' dispatch, or an explicit workflow_dispatch are the only build paths (D-01)."
    - "No file outside .planning/ references .github/workflows/build-<addon>.yml as a live path (D-06)."
    - "No prose a sibling wrote one or two waves earlier survives describing per-add-on dispatch: 260909-rlm's `## Auto-update path` in .github/RELEASE.md and its docs/AUTO_UPDATE_GUIDE.md rewrite both describe ONE build.yml dispatch carrying a list, and 260909-rll's two internal/update-version.py prose blocks no longer claim a per-caller `tags:` trigger exists (D-06, L-18)."
    - "git revert of the switch-over commit restores all nine callers and today's exact build behaviour in one step, with build.yml left in place and still dispatchable (D-03)."
  artifacts:
    - ".github/workflows/build.yml — one detect job plus one matrix build job calling _build-template.yml; clean under actionlint v1.7.3 (pre-commit-pinned) AND the latest release, and under yamllint with the repo config"
    - "the nine .github/workflows/build-*.yml deleted; _build-template.yml's workflow_call input/secret contract byte-unchanged (header comment only)"
    - "internal/dispatch-builds.sh — exactly one `gh workflow run build.yml --ref <ref> -f addons=<sorted comma list>` per invocation, with the `ADDON <name> <STATE>` stdout contract and its sort -u ordering preserved"
    - ".github/RELEASE.md — per-caller tag-trigger table replaced, tag-trigger removal recorded with its measured rationale, 'Re-enabling a tag trigger' replaced by an on-demand rebuild recipe"
    - "README.md, docs/DEVELOPMENT.md, docs/WEBHOOK_SETUP.md, docs/UPDATE_VERSION.md, docs/AUTO_UPDATE_GUIDE.md, internal/check-version-tags.sh, internal/update-version.py — no live reference to a deleted caller, no claim that a tag push builds an image, no description of a per-add-on dispatch"
  key_links:
    - "detect step `env:` -> the run body: no GitHub expression is interpolated into the shell, which is also what makes the extraction gate executable locally"
    - "<addon>/build.yaml build_from keys -> matrix include arch legs -> archs input -> _build-template.yml's fromJSON(inputs.archs) -> its PLATFORM case"
    - "<addon>/config.yaml name:/description: -> matrix display_name/description -> BUILD_NAME / BUILD_DESCRIPTION build-args"
    - "needs.detect.outputs.addons != '[]' -> whether the build job exists at all: an empty include list is a hard matrix error, not zero jobs"
    - "internal/dispatch-builds.sh -f addons=<list> -> build.yml workflow_dispatch inputs.addons -> the explicit-list branch of the derivation"
    - "the nine deleted callers -> internal/dispatch-builds.sh's classification source, which becomes the config.yaml/build.yaml/Dockerfile triple instead of a build-<addon>.yml existence test"
---

<objective>
Replace the nine structurally identical per-add-on build workflows with ONE builder that derives
the add-on list, the arch legs and the add-on metadata from the add-ons' own manifests.

Purpose: the nine callers are 28-line copies differing only in `name`, one `paths` glob, three
`with:` values and the arch list. That duplication has already drifted — **8 of 9
`addon-description` values in the callers differ from the add-on's own `config.yaml`
`description:`** (measured, see `<verified_environment>`), so today's images carry stale OCI
descriptions. The arch lists have not drifted yet (9 of 9 agree with `build_from`), which is
exactly why this is the right moment to make drift structurally impossible rather than waiting
for it to bite.

Output: one new `.github/workflows/build.yml`, nine deleted callers, a batched
`internal/dispatch-builds.sh`, and the eight documentation/comment sites that the deletion
would otherwise leave asserting a mechanism that no longer exists — two of which are written by
siblings one and two waves earlier and are false only from wave 3 onward (D-06).
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@.github/workflows/_build-template.yml
@.github/RELEASE.md
@internal/check-version-tags.sh
</context>

<verified_environment>
Measured on the current unmodified tree (2026-09-09, `git log -1` = `5b41d49`). Do NOT re-derive
these; do NOT contradict them.

| Fact | Measured value |
|---|---|
| `ls .github/workflows/build-*.yml \| wc -l` | **9** (the glob does not match `_build-template.yml`) |
| `[ -f .github/workflows/build.yml ]` | false |
| `archs` per caller | `'["amd64", "aarch64"]'` for coding-assistants only; `'["amd64"]'` for the other eight |
| caller `archs` vs `build.yaml` `build_from` keys | **9 of 9 agree** — no arch drift today |
| caller `addon-display-name` vs `config.yaml` `name:` | **9 of 9 agree** |
| caller `addon-description` vs `config.yaml` `description:` | **1 of 9 agrees** (gatus). The other eight have drifted; e.g. iac-runner's caller says "OpenTofu runner … with R2/S3/local state backends" while its `config.yaml` says "OpenTofu/Terraform runner … against R2/S3/local state backends." |
| `build_from` keys per add-on | `coding-assistants: [amd64, aarch64]`; all eight others `[amd64]`; identical to each `config.yaml` `arch:` |
| add-ons with NO top-level `image:` key | `authentik`, `iac-runner` (Supervisor builds them locally) |
| `<addon>/v*` tags whose tagged commit's `build.yaml` VERSION != the tag's base version | **15 of 40**, because `RELEASE.md` step 1 creates the tag BEFORE step 2 commits the bump. For the three add-ons whose tag trigger is currently ACTIVE the rate is 1 of 8 (`terraform-bridge/v0.2.0`, tagged at `build.yaml` VERSION 0.1.0) |
| local `python3` / PyYAML | 3.14.7 / PyYAML 6.0.3 — available |
| local `yq` | python-yq, **no `eval` subcommand**: nothing that must run locally may use `yq eval` |
| local `jq` | 1.8.2 |
| local `actionlint` | **NOT on PATH**. pre-commit pins `rev: v1.7.3`; `lint.yml:60-66` installs the latest at run time (currently **v1.7.12**). Both must pass. |
| `yamllint` / `shellcheck` | 1.38.0 / 0.11.0 |
| `PyYAML` and the `on:` key | `yaml.safe_load` parses the workflow key `on:` as the **boolean `True`** (YAML 1.1). Every gate below therefore reads it as `d.get('on', d.get(True))`. A gate written as `d['on']` raises `KeyError` and would report a false failure. |
| `.actionlint.yml` | excludes only SC2086/SC2129/SC2001 in `run:` blocks; `config-variables:` is **empty** so any `vars.*` is flagged; only `ubuntu-latest` allowed |
| `lint.yml:91-95` shell-lint step | ends in `\|\| echo "No shell scripts to check"` — **non-blocking**. Do not write a gate that depends on repo-wide strict shellcheck passing (22 pre-existing findings, per sibling rlj). |
| non-add-on paths matched by the new `paths:` globs | `.planning/config.json`, `terraform-provider-homeassistant/build.yaml`, `tools/test-addon/{config.yaml,build.yaml,Dockerfile}` — all three are rejected by the derivation (see `<gate_calibration>` S5/S6), so they cost a ~15 s no-op `detect` job and never a build |
| `.prettierignore` / `.markdownlint-cli2.yaml` | both exclude `.planning/` — this plan file is not reformatted or linted |
| live full-path references to a deleted caller (`.github/workflows/build-`, excluding the nine files and `.planning/`) | **3**: `.github/RELEASE.md:103`, `internal/update-version.py:203`, `internal/check-version-tags.sh:2` |
| `grep -v '^#' internal/check-version-tags.sh \| sha256sum` | `5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249` (pins the hook's CODE while its header comment is rewritten) |

**Two measured facts about GitHub Actions itself**, both established with the real linters against
a working prototype (see `<gate_calibration>`), because both shape the design:

1. `actionlint` DOES validate a local `uses: ./.github/workflows/_build-template.yml` call site
   against the callee's declared inputs — a misspelt `addon-display-name` is reported as
   `[workflow-call]`. The actionlint gate therefore has real teeth on the exact thing most likely
   to break: the four `with:` inputs.
2. A `uses:` job may NOT declare `timeout-minutes` — actionlint v1.7.12 reports
   `only following keys are allowed: "name", "uses", "with", "secrets", "needs", "if", and
   "permissions"`. `strategy` IS accepted in practice (the prototype lints clean under both
   v1.7.3 and v1.7.12 with a dynamic `matrix:`). Do not "fix" the missing timeout on the build
   job: the 45-minute cap lives in `_build-template.yml` and adding one here is a lint error.
</verified_environment>

<decisions>
The item text names two things that MUST be decided explicitly and recorded rather than handled
incidentally. Both are decided here, with the alternative and the reason.

## D-01 — The three active `tags:` triggers are REMOVED ENTIRELY. No shared `*/v*` pattern.

Alternative considered: a single shared `tags: - "*/v*"` block in `build.yml`.
**Rejected**, for four reasons, in descending order of weight:

1. **It would produce green no-op runs.** The detect job derives the add-on set from a diff
   between `github.event.before` and `github.sha`. For a newly created tag ref
   `github.event.before` is `0000000000000000000000000000000000000000`, so the derivation would
   fall back to a single-commit diff of whatever commit the tag points at — which for the
   documented release flow is the PRE-bump commit that changed nothing under an add-on
   directory. The run would report success and build nothing. A green no-op is strictly worse
   than no trigger, because it looks like a build happened.
2. **Making it work needs a second derivation path** (parse the add-on name out of
   `GITHUB_REF_NAME`), i.e. new untested code in the one file whose failure breaks all nine
   builds at once.
3. **The trigger it would preserve is already wrong.** Measured: 15 of 40 `<addon>/v*` tags
   point at a commit whose `build.yaml` VERSION is not the tag's version, because
   `RELEASE.md`'s own flow creates and pushes the tag (step 1) BEFORE the version files are
   committed (step 2). A tag-triggered build therefore checks out the pre-bump tree and
   republishes the PREVIOUS `CONFIG_VERSION` image. `RELEASE.md:93-95` currently claims the
   opposite ("the tag-triggered leg … produces the canonical image for the tag"); that claim is
   false and is corrected by D-02.
4. **The double-build disappears.** `iac-runner`, `network-tools` and `terraform-bridge`
   currently build twice per release (paths + tag) for no benefit.

Coverage after removal is complete: `paths:` on `main` covers human pushes;
`internal/dispatch-builds.sh` covers the automated bumps whose pushes create no runs at all
(sibling rlj); `workflow_dispatch` with the `addons` input covers ad-hoc rebuilds and is a
strictly better manual path than pushing a tag.

**What this means for `internal/check-version-tags.sh`** (called out explicitly, as the item
requires): the hook's header currently justifies itself with a causal chain — *the tag triggers
the build, therefore a missing tag means a missing image, therefore a ghcr 404*. The middle link
is deleted here, and it was already broken for six of nine add-ons whose tag trigger was
commented out. The hook's **ghcr-404 rationale survives intact**, because the 404 is caused by a
version bump landing without any build, not by the absence of a tag; what changes is the
mechanism that prevents it (the bump commit's `paths:` build, or a dispatch). The hook keeps its
value as the release-bookkeeping guarantee — *no version bump reaches `main` without its release
tag* — and its behaviour, including `LOCAL_BUILD_ADDONS`, is unchanged. Only the header prose is
corrected (D-06), and the code is hash-pinned to prove it.

## D-02 — `.github/RELEASE.md`: the per-caller tag-trigger table is replaced, not annotated.

In a one-workflow world there is no per-add-on `tags:` block, so the table's two trigger columns
(`paths: on main`, `<addon>/v* tag`) have no referent. The `Supervisor image source` column does
still describe a real per-add-on property (presence of a top-level `image:` key) and is kept.
Concretely: the table becomes two columns, the "Why the split" section is compressed into a
short history note that keeps the two commit citations (`287c79f`, `60e7835`) as the reason the
tags exist at all, "What this means operationally" is rewritten around the bump commit rather
than the tag, and "Re-enabling a tag trigger" — which instructs the reader to edit a file that no
longer exists — is replaced by an on-demand rebuild recipe
(`gh workflow run build.yml -f addons=<name>` / `internal/dispatch-builds.sh <name>`).

## D-03 — Validation path: offline extraction gates + a dispatch-only first commit + a mandated post-merge dispatch proof.

The item requires a validation path that does not involve pushing a broken builder to `main`, and
names three candidates. All three were evaluated against this repository:

- **`act` — rejected.** It cannot evaluate `on.push.paths`, has no meaningful
  `github.event.before`, has partial reusable-workflow support, and would attempt the real
  `docker/build-push-action` step (measured 13m28s for the emulated aarch64 leg) with
  `push: true` hardcoded in the template. It would validate strictly less than gate G1-4 below
  and cost far more.
- **Test branch — rejected, and the reason is a hard GitHub constraint.** `workflow_dispatch` is
  only dispatchable for a workflow that already exists on the **default** branch, so a
  branch-only `build.yml` cannot be dispatched at all. The only way to fire it from a branch is
  to add that branch to `on.push.branches`, which runs the real build job and overwrites
  published `:latest` / `:<version>` GHCR tags; gating the build job on `github.ref_name` to
  prevent that also skips matrix expansion and the reusable-workflow call, so it would validate
  nothing beyond the detect job that G1-4 already validates exactly. A temporary trigger edit
  that must be remembered and removed is itself a footgun.
- **`workflow_dispatch`-only first landing — ADOPTED, in the only form a quick-batch item can
  take.** Task 1 lands `build.yml` with `workflow_dispatch:` as its ONLY trigger and the nine
  callers untouched, so at that commit `main`'s build behaviour is byte-for-byte today's and
  `build.yml` is inert until someone dispatches it. Task 2 is the entire switch-over — add the
  `push:` trigger, delete the nine, rewrite the script — as ONE commit. A true two-merge
  sequence is impossible here (a quick-batch item merges once), so what this buys is precise and
  worth stating plainly: **the whole risk surface is one revertible commit.**
  `git revert <task-2-sha>` restores all nine callers and today's behaviour while leaving
  `build.yml` present and dispatchable for iteration.

The residual risk the offline gates cannot cover is `startup_failure` from the dynamic matrix
expression, the call-site `permissions`, or the named `secrets:` mappings —
`docs/DEVELOPMENT.md:96-99` records that these surface only at run time. That residual is closed
by the mandatory post-merge dispatch proof in `<verification>`, which is exactly the
workflow_dispatch-first proof, executed immediately after the merge instead of before it.

## D-04 — Per-add-on metadata is DERIVED in `detect` and passed through the existing `workflow_call` inputs.

The item requires that `addon-display-name`, `addon-description` and the arch list come from
`config.yaml` / `build.yaml` "rather than passed as inputs, otherwise the duplication merely
moves into the new workflow". The duplication requirement is honoured by construction: the detect
job reads all three from the add-on's own manifests and carries them in the matrix, so
`config.yaml` is the single source and `build.yml` contains **zero** hand-authored add-on names,
display names, descriptions or arch lists — gate G1-6 asserts exactly that, computing the
forbidden literals from the manifests rather than hardcoding them.

They still travel through `_build-template.yml`'s existing `workflow_call` inputs, because the
item also requires "Keep `_build-template.yml` as the workflow_call target — only the nine callers
disappear", and because making those two inputs optional would edit the same `meta` step that
sibling rlj edits, in the same region, for no gain. The alternative reading ("the template should
read config.yaml itself") is therefore rejected as a conflict with an explicit instruction in the
same item.

Consequence to expect and NOT treat as a bug: because the callers had drifted, switching to
`config.yaml` changes `BUILD_DESCRIPTION` — and hence `org.opencontainers.image.description` — for
**8 of 9 add-ons** on their next build. That is the fix, not a regression: `config.yaml` is what
the add-on store shows the user.

## D-05 — `internal/dispatch-builds.sh` keeps rlj's derivation verbatim; only classification and batching change.

rlj's **L-3** locks the derive-mode expression to `git diff --name-only $BASE_SHA..HEAD` piped
through `cut -d/ -f1 | sort -u`, unfiltered, and rlj's GATE-T1-6 asserts the derived set equals an
independently recomputed copy of exactly that pipeline. This plan does NOT change it, even though
`build.yml`'s `paths:` filter is narrower. The asymmetry is deliberate and safe in one direction
only: the script is *more* eager than the paths filter (a README-only bump path can still produce
a dispatch), never less, so no build can be missed. Gate G2-8 re-runs rlj's GATE-T1-6 unchanged.

What does change: (a) the per-candidate classification test, because
`.github/workflows/build-<name>.yml` no longer exists — it becomes the
`config.yaml` + `build.yaml` + `Dockerfile` triple, the same definition `lint.yml:107-117`,
`Makefile:201` and `check-version-tags.sh:37` already use; and (b) N dispatches become one.

## D-06 — Comment and documentation truth is part of this change, not a follow-up.

Deleting the nine files falsifies eight prose sites outside `.planning/`. `README.md`,
`docs/DEVELOPMENT.md`, `docs/WEBHOOK_SETUP.md`, `docs/UPDATE_VERSION.md`,
`docs/AUTO_UPDATE_GUIDE.md`, `internal/check-version-tags.sh`, `internal/update-version.py` and
`_build-template.yml`'s header are therefore in scope for Task 3, beyond the item's declared file
list. Rationale: shipping a commit that deletes nine files alongside a README asserting those nine
files build the images is the exact drift this batch exists to remove.

**Two of those sites are WRITTEN by siblings one and two waves before this item, not merely
inherited from the pre-batch tree** — which is why they are declared paths of this item rather
than someone else's problem:

- **260909-rll (wave 1)** rewrites `internal/update-version.py`'s tag-push output and
  `create_and_push_tag`'s docstring so that both describe the per-caller `tags:` trigger
  correctly — "a build runs only if that add-on's caller has an active `tags:` trigger, six of
  nine have it commented out". True at wave 1. False at wave 3, where neither a caller nor a
  `tags:` trigger exists anywhere.
- **260909-rlm (wave 2)** writes `.github/RELEASE.md`'s `## Auto-update path` and rewrites
  `docs/AUTO_UPDATE_GUIDE.md`. Both describe per-add-on dispatch — one dispatch per add-on
  naming that add-on's own workflow file, and `SKIPPED_NO_WORKFLOW` meaning "that build workflow
  file is missing". Task 2 falsifies both, and rlm's text plants live full-path references to
  files Task 2 deletes. rlm correctly declared `docs/WEBHOOK_SETUP.md` out of ITS scope while this
  item claims it; this is the mirror-image case — rlm writes the text, this item reconciles it —
  so `docs/AUTO_UPDATE_GUIDE.md` is a declared file of this item.

Every edit in Task 3 is comment/prose only. `internal/check-version-tags.sh`'s executable
behaviour is hash-pinned unchanged (G3-6). `internal/update-version.py`'s is held by SCOPED
INVARIANTS rather than a hash (G3-7): rll adds print statements to that file and this item must
then rewrite them, so any whole-file or whole-AST pin is invalidated by correct work — see
`<sibling_supersession>`. L-18 lists the sibling literals Task 3 must preserve.

## D-07 — No `concurrency:` block in `build.yml`.

Today's nine callers have none. Sibling rll (STAGE 4) owns the shared concurrency group and this
item must not pre-empt that decision; more importantly `cancel-in-progress` on a job that pushes
images to GHCR would abort a half-published multi-arch build. Out of scope, deliberately.
</decisions>

<locked_constraints>
Non-negotiable. Any deviation is a defect.

- **L-1** `build.yml` is the ONLY new workflow file. `_build-template.yml` stays the
  `workflow_call` target and its `on.workflow_call` inputs/secrets block is **byte-unchanged** —
  the only permitted edit to that file is its header comment (Task 3).
- **L-2** `build.yml`'s `paths:` are exactly `"**/config.*"`, `"**/build.*"`, `"**/Dockerfile"`
  and `branches:` is exactly `[main]`. No `tags:` key anywhere in the file (D-01).
- **L-3** The arch legs come from `<addon>/build.yaml` `build_from` keys, falling back to
  `<addon>/config.yaml` `arch:`. Never from a workflow input, a matrix literal or a hardcoded
  per-add-on list.
- **L-4** `addon-display-name` / `addon-description` come from `<addon>/config.yaml` `name:` /
  `description:`. No add-on name, display name, description or arch list may appear in a
  non-comment line of `build.yml` (G1-6).
- **L-5** The supported arch set is `amd64 aarch64`, iterated in that order; an add-on that does
  not declare one of them gets no leg for it, and a declared-but-unsupported arch produces a
  `::warning::` rather than a silent drop.
- **L-6** NO GitHub expression (`${{ ... }}`) inside the detect step's `run:` body. Every event
  value arrives via the step's `env:`. This is both the injection rule (see `T-rln-01`) and what
  makes the extraction gate G1-4 executable. **Do not write the expression delimiters in a
  comment inside that body either** — G1-5 greps the extracted body and cannot distinguish a
  comment from code.
- **L-7** `fetch-depth: 0` on the detect job's checkout.
- **L-8** The `nobuild` escape hatch: the detect job carries an `if:` that skips the run when the
  head commit message contains `nobuild`, written so a `workflow_dispatch` (where
  `github.event.head_commit` is null) is never skipped.
- **L-9** The build job MUST NOT declare `timeout-minutes` (actionlint error, measured). The
  detect job MUST declare one. Both jobs declare `permissions`.
- **L-10** `strategy.fail-fast: false` on the build job, matching every current caller's
  effective behaviour via the template.
- **L-11** The build job must not exist when nothing is to be built: guard it with
  `if: ${{ needs.detect.outputs.addons != '[]' }}`. An empty `include` list is a hard matrix
  error, not zero jobs.
- **L-12** `internal/dispatch-builds.sh` issues **exactly one** `gh workflow run build.yml` per
  invocation and **never** one with an empty `addons` value — empty means all nine.
- **L-13** The script's `ADDON <name> <STATE>` stdout contract from rlj's `<script_contract>` is
  preserved in full, **including the `sort -u` ordering** and the five-value `<STATE>` set. Only
  the meaning of `SKIPPED_NO_WORKFLOW` shifts (no add-on manifest at that path), which the script
  header must state.
- **L-14** Task ordering is load-bearing: Task 1 must land `build.yml` with `workflow_dispatch:`
  as its only trigger and all nine callers intact; Task 2 must add the `push:` trigger, delete the
  nine and rewrite the script in ONE commit. At no commit boundary may an automated bump dispatch
  a workflow that does not exist (D-03).
- **L-15** Both actionlint versions must pass: the pre-commit-pinned v1.7.3 and the latest
  release resolved at run time (v1.7.12 today), the same pair `lint.yml` enforces.
- **L-16** Shell traps that apply to the script rewrite: quote every expansion (SC2086); never
  `local x=$(cmd)` / `export X=$(cmd)` (SC2155); no `echo | sed` (SC2001); `pipefail` plus a
  filtering pipeline needs `|| var=""`; never `... | while read` (subshell loses counters).
- **L-17** Nothing that must run locally may use `yq eval` (local `yq` is python-yq). Use
  `python3` + PyYAML.
- **L-18** **Sibling-gate literals — PRESERVE.** Siblings rll (wave 1) and rlm (wave 2) write
  prose into three files this item then rewrites, and their gates grep for literals inside it.
  Task 3 rewrites sentences in those regions; it must not remove any literal below. Per file:
  - `internal/update-version.py` (rll `GATE-T2-A/B/C/D/E`): the f-string `Pushed tag: {tag}`; at
    least two `RELEASE.md` references; `Returns True on success.`; the literals `paths:` and
    `tags:` inside `create_and_push_tag`'s docstring; the four `add_argument` declarations; and
    `create_and_push_tag`'s signature line byte-unchanged.
  - `.github/RELEASE.md` (rlm `A*`, `B*`, `C*`, `H*`, `X1`): inside `## Tag schema` —
    `--no-tag`, `base-image-update`, `2026-09-09`, `15 of the 40`, `authentik/v2026.8.1`,
    `meridian/v1.59.0`, `terraform-bridge/v0.2.0`, `git show`; inside
    `### What this means operationally` — `human`, `GITHUB_TOKEN` and the cross-reference
    `Auto-update path`; inside `## Auto-update path` — `internal/dispatch-builds.sh`,
    `GITHUB_TOKEN`, `workflow_dispatch`,
    `docs.github.com/actions/using-workflows/triggering-a-workflow`, `--no-tag`,
    `docs/AUTO_UPDATE_GUIDE.md`, `Auto Update`; the heading `### Why the split` and its `all
    seven` historical clause (a TRUE statement about commit `287c79f`, which stays); and all nine
    `| <addon> ` table rows.
  - `docs/AUTO_UPDATE_GUIDE.md` (rlm `N01`-`N14`, `Y01`-`Y18`, `K1`-`K6`, `L1`): notably
    `internal/dispatch-builds.sh`, `GITHUB_TOKEN`, `workflow_dispatch`, `actions: write`,
    `notify-ha.sh`, `--no-tag`, `RELEASE.md`, `ERRORS=1`, `gh release view`,
    `upstream.repository`, `upstream.version_strip`, `internal/base-image-config.yaml`,
    `version_pattern: "sync"`, `Auto Update`, `0 6 * * *`, the four add-on names, the headings
    `## 🔄 What happens automatically` and `### 1. **Daily Check** (6:00 UTC)`, and rlm's
    120-column line limit.
  Do NOT restate a measured figure rlm already wrote — cross-reference its subsection instead of
  producing a second copy that can drift. The ONLY permitted exceptions are the five entries in
  `<sibling_supersession>` § 1, each of which is knowingly invalidated and recorded there.
</locked_constraints>

<script_contract>
The observable contract of `internal/dispatch-builds.sh` after this rewrite. The parts marked
**PRESERVED** are rlj's contract verbatim and are asserted by G2-3; the parts marked **CHANGED**
are the intended consequence of collapsing nine dispatch targets into one.

- **PRESERVED — stdout**: exactly one line per candidate, `ADDON <name> <STATE>`, emitted in
  `sort -u` order of the candidate names. `<STATE>` is one of `DISPATCHED`, `DRY_RUN`,
  `SKIPPED_NO_WORKFLOW`, `SKIPPED_BAD_NAME`, `FAILED`. Gates parse only with
  `awk '$1=="ADDON"'`, so no gate depends on prose punctuation.
- **PRESERVED — stderr**: human `INFO:` / `WARN:` / `ERROR:` lines only.
- **PRESERVED — exit**: `0` when every candidate reached a non-`FAILED` state (including all
  skips); `1` when the dispatch failed, when `BASE_SHA` is required but unset, or when
  `set -euo pipefail` aborts.
- **PRESERVED — derive mode**: `git diff --name-only "$BASE_SHA..HEAD" | cut -d/ -f1 | sort -u`,
  unfiltered (D-05).
- **CHANGED — one dispatch**: a single `gh workflow run build.yml --ref "$ref" -f addons="$list"`
  for all dispatchable candidates, where `$list` is their names comma-joined in `sort -u` order.
  Because one dispatch carries one outcome, classification happens FIRST for every candidate, the
  dispatch runs ONCE, and only then are the `ADDON` lines printed — in `sort -u` order — with the
  resolved state. Every dispatchable candidate shares `DISPATCHED` or shares `FAILED`.
- **CHANGED — classification source**: `SKIPPED_NO_WORKFLOW` is now decided by the absence of the
  `<name>/config.yaml` + `<name>/build.yaml` + `<name>/Dockerfile` triple, not by the absence of
  `.github/workflows/build-<name>.yml`. The state NAME is kept because rlj's gates and this
  plan's G2-3 assert the five-value set.
- **CHANGED — DRY_RUN output**: exactly ONE `DRY_RUN: ` line per invocation (the single `gh`
  command it would have run, naming every dispatchable candidate), and zero such lines when no
  candidate is dispatchable. rlj's GATE-T1-5 clause `grep -q 'gh workflow run build-meridian.yml'`
  is intentionally superseded — that workflow no longer exists. Its ordering clause
  (`meridian DRY_RUN` before `nonexistent-addon SKIPPED_NO_WORKFLOW`) is NOT superseded and is
  re-asserted by G2-3.
</script_contract>

<sibling_supersession>
This item runs at **wave 3**. Siblings **260909-rlj** (wave 0), **260909-rll** (wave 1) and
**260909-rlm** (wave 2) all land first, and all three mutate artifacts this item then rewrites.
Two consequences, both recorded HERE rather than left for a verifier to find as an undisposed red
gate.

**The wave-3 baseline rule this section exists to enforce:** a hash or a count measured against
today's tree is not a baseline for a task that runs three waves later. Every absolute number in
`<gate_calibration>` was measured at `5b41d49` and is therefore an upper bound, not a fact, for
any file a sibling touches first. Gates in this plan are written as `== 0` / `>= 1` properties, or
as hashes over regions no sibling can reach, precisely so this cannot bite.

## 1. Sibling gates this item knowingly invalidates

| Sibling gate | What it asserts | Why it cannot survive | Replacement |
|---|---|---|---|
| rlj `GATE-T1-5`, its `grep -q 'gh workflow run build-meridian.yml'` clause | the dry-run line names that add-on's own workflow | Task 2 deletes that workflow | `G2-3a` asserts the single `gh workflow run build.yml` form and re-asserts rlj's ORDERING clause (`meridian DRY_RUN` before `nonexistent-addon SKIPPED_NO_WORKFLOW`) unchanged |
| rlm `D0-tree-is-six` | six caller files carry the disabled-trigger comment | Task 2 deletes all nine callers, so the count is 0 | nothing: the claim is about a world with caller files. `G2-1` asserts the deletion instead |
| rlm `D0b`, `D1-says-six`, `D2-not-seven`, `X2-reenable-steps` | all four read the region `### Re-enabling a tag trigger` .. `## Standard release flow` | D-02 replaces that whole subsection with the rebuild-on-demand recipe, so the region's start anchor disappears and rlm's `sed` range returns empty | `G3-1` asserts the subsection is gone AND the recipe is present |
| rlm `E2-scoped-to-six` | `six callers` appears in `## Tag schema` .. `### Why the split` | Task 3 item 1 drops the in-file-comment sentence rlm had rescoped, because that comment no longer exists in any file | `G3-1`'s `tag-trigger temporarily disabled == 0` is the strictly stronger successor |

## 2. Sibling properties this item re-asserts rather than supersedes

- **rlj `GATE-T1-6`** (the derived candidate set equals an independently recomputed
  `git diff --name-only "$BASE_SHA..HEAD" | cut -d/ -f1 | sort -u`): the PROPERTY is preserved
  verbatim (D-05) and re-asserted by `G2-4`. `G2-4` uses base `7cc82f5` where rlj used `80eb6b6`
  — a different anchor, chosen because it is a stable single-add-on commit still reachable at
  wave 3. Both sides of the comparison are recomputed from the same pipeline, so rlj's gate also
  still passes verbatim at its own anchor; only the anchor differs, and the difference is
  deliberate. D-05's phrase "re-run unchanged" means the assertion, not the literal command line.
- **rll `GATE-T2-A/B/C/D/E`** over `internal/update-version.py`: Task 3 item 7 edits the same two
  prose blocks rll just wrote, so every rll literal must survive (L-18). `G3-7a`/`G3-7b`/`G3-7c`
  re-assert them, including the argparse surface and the `create_and_push_tag` signature.
- **rlm `A1`-`A8`** (`## Auto-update path`), **`B1`-`B4`** (`### What this means operationally`),
  **`C1`-`C9`** (`## Tag schema`), **`H0`/`H1`** (`### Why the split`), **`X1`** (nine add-on
  rows), and every `docs/AUTO_UPDATE_GUIDE.md` gate (`N01`-`N14`, `Y01`-`Y18`, `K1`-`K6`, `L1`):
  all preserved. Task 3 rewrites sentences inside those regions without removing their literals;
  `G3-1b`, `G3-1c` and `G3-10` re-assert the ones the rewrites come closest to.

**Why `G3-7` is a scoped-invariant gate and not a hash.** The first draft pinned
`internal/update-version.py`'s docstring-stripped AST. That pin is unachievable: rll splits one
`print(f"...")` into three statements (a non-docstring change that moves the AST), and this item
must then rewrite those same statements again. A re-derived hash would also be a standing
liability — it would need re-measuring every time any sibling touched a line. `G3-7` therefore
asserts what the pin actually meant: the argparse surface, every `^def ` signature line, the
`create_and_push_tag` signature, `py_compile`, and both `--no-tag` orderings running clean with a
clean tree. Those cannot be invalidated by an unrelated prose edit, and they say what they mean.

Record both lists in the SUMMARY so a verifier re-running the batch's full gate set knows which
reds are expected and why.
</sibling_supersession>

<reference_implementation>
This is not illustrative. It is the exact prototype used for `<gate_calibration>` Run B: it lints
clean under actionlint v1.7.3 AND v1.7.12 with this repository's `.actionlint.yml`, clean under
`yamllint -c .yamllint.yml`, and its detect body — extracted from the file with PyYAML exactly as
gate G1-4 does — produced the six measured outcomes in `<gate_calibration>` against the real
repository. Task 1 lands it with `on:` reduced to `workflow_dispatch:` only (L-14); Task 2 adds
the `push:` block shown here.

Treat it as the starting point. Improve comments freely, but do not restructure the derivation, the
`env:` indirection, the output shape or the job wiring without re-running every gate — the shape is
what was measured, not the intent.

```yaml
# One builder for every add-on in this repository.
#
# Replaces the nine per-add-on callers, which were structurally identical and
# differed only in name, the paths glob, three `with:` values and the arch
# list. Every per-add-on value is now DERIVED from the add-on's own manifests,
# so CI configuration cannot drift from what the add-on store advertises.
name: Build Add-on

on:
  push:
    branches:
      - main
    paths:
      - "**/config.*"
      - "**/build.*"
      - "**/Dockerfile"
  workflow_dispatch:
    inputs:
      addons:
        description: "Add-on names to build, comma- or space-separated. Empty builds every add-on."
        required: false
        type: string
        default: ""

jobs:
  detect:
    name: Detect add-ons to build
    if: ${{ github.event_name != 'push' || !contains(github.event.head_commit.message, 'nobuild') }}
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    outputs:
      addons: ${{ steps.detect.outputs.addons }}
      matrix: ${{ steps.detect.outputs.matrix }}
    steps:
      - uses: actions/checkout@v7
        with:
          # The derivation diffs two commits, so the full history is required.
          fetch-depth: 0

      - name: Derive add-on build matrix
        id: detect
        env:
          EVENT_NAME: ${{ github.event_name }}
          BEFORE_SHA: ${{ github.event.before }}
          HEAD_SHA: ${{ github.sha }}
          ADDONS_INPUT: ${{ inputs.addons }}
        run: |
          set -euo pipefail

          # Architectures this builder can map to a docker platform.
          SUPPORTED_ARCHS="amd64 aarch64"

          if [ "$EVENT_NAME" = "push" ]; then
            base="${BEFORE_SHA:-}"
            if [ -z "$base" ] || ! git rev-parse --verify --quiet "${base}^{commit}" >/dev/null 2>&1; then
              base="${HEAD_SHA}^"
              echo "::notice::event before-sha unusable, diffing ${base} instead"
            fi
            changed=$(git diff --name-only "${base}..${HEAD_SHA}")
            # Keep only the manifest paths the push trigger filters on, then the
            # first path segment. The trailing fallback is mandatory: pipefail
            # turns grep's no-match exit 1 into a failed assignment that set -e
            # would abort on.
            candidates=$(printf '%s\n' "$changed" \
              | grep -E '^[^/]+/(config|build)\.[^/]+$|^[^/]+/Dockerfile$' \
              | awk -F/ 'NF {print $1}' | sort -u) || candidates=""
          elif [ -n "${ADDONS_INPUT:-}" ]; then
            candidates=$(printf '%s' "$ADDONS_INPUT" | tr ',' ' ' | tr -s ' \t\n' '\n' | sed '/^$/d' | sort -u)
          else
            candidates=$(for c in */config.yaml; do
              if [ -f "$c" ]; then printf '%s\n' "${c%/config.yaml}"; fi
            done | sort -u)
          fi

          matrix_file=$(mktemp)
          accepted_file=$(mktemp)
          CANDIDATES="$candidates" SUPPORTED_ARCHS="$SUPPORTED_ARCHS" \
          MATRIX_FILE="$matrix_file" ACCEPTED_FILE="$accepted_file" python3 - <<'PY'
          import json
          import os
          import re
          import sys

          import yaml

          supported = os.environ["SUPPORTED_ARCHS"].split()
          names = [c.strip() for c in os.environ["CANDIDATES"].splitlines() if c.strip()]
          name_re = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
          include = []
          accepted = []

          for n in names:
              if not name_re.match(n):
                  print(f"::warning::ignoring '{n}': not a well-formed add-on directory name")
                  continue
              paths = {k: f"{n}/{k}" for k in ("config.yaml", "build.yaml", "Dockerfile")}
              if not all(os.path.isfile(p) for p in paths.values()):
                  print(f"::notice::ignoring '{n}': not an add-on directory")
                  continue
              with open(paths["config.yaml"], encoding="utf-8") as fh:
                  cfg = yaml.safe_load(fh) or {}
              with open(paths["build.yaml"], encoding="utf-8") as fh:
                  bld = yaml.safe_load(fh) or {}
              declared = list((bld.get("build_from") or {}).keys())
              if not declared:
                  declared = list(cfg.get("arch") or [])
                  print(f"::warning::{n}: no build_from in build.yaml, using config.yaml arch: {declared}")
              for a in declared:
                  if a not in supported:
                      print(f"::warning::{n}: declares unsupported arch '{a}', skipping that leg")
              legs = [a for a in supported if a in declared]
              if not legs:
                  print(f"::warning::ignoring '{n}': declares no supported architecture")
                  continue
              display_name = cfg.get("name")
              description = cfg.get("description")
              if not display_name or not description:
                  print(f"::error::{n}/config.yaml is missing name: or description:")
                  sys.exit(1)
              accepted.append(n)
              for a in legs:
                  include.append({
                      "addon": n,
                      "arch": a,
                      "archs": json.dumps([a]),
                      "display_name": display_name,
                      "description": description,
                  })

          with open(os.environ["MATRIX_FILE"], "w", encoding="utf-8") as fh:
              fh.write(json.dumps({"include": include}, separators=(",", ":")))
          with open(os.environ["ACCEPTED_FILE"], "w", encoding="utf-8") as fh:
              fh.write("\n".join(accepted))
          PY

          addons=$(jq -R -s -c 'split("\n") | map(select(length > 0))' <"$accepted_file")
          matrix=$(cat "$matrix_file")
          {
            echo "addons=$addons"
            echo "matrix=$matrix"
          } >>"$GITHUB_OUTPUT"
          echo "::notice::building $addons ($(jq '.include | length' "$matrix_file") legs)"

  build:
    needs: detect
    if: ${{ needs.detect.outputs.addons != '[]' }}
    name: ${{ matrix.addon }} (${{ matrix.arch }})
    strategy:
      fail-fast: false
      matrix: ${{ fromJSON(needs.detect.outputs.matrix) }}
    uses: ./.github/workflows/_build-template.yml
    permissions:
      contents: read
      packages: write
    with:
      addon-name: ${{ matrix.addon }}
      addon-display-name: ${{ matrix.display_name }}
      addon-description: ${{ matrix.description }}
      archs: ${{ matrix.archs }}
    secrets:
      HA_BASE_URL: ${{ secrets.HA_BASE_URL }}
      HA_WEBHOOK_ID: ${{ secrets.HA_WEBHOOK_ID }}
      CF_ACCESS_CLIENT_ID: ${{ secrets.CF_ACCESS_CLIENT_ID }}
      CF_ACCESS_CLIENT_SECRET: ${{ secrets.CF_ACCESS_CLIENT_SECRET }}
```

Notes on two non-obvious choices, both measured:

- `name: ${{ matrix.addon }} (${{ matrix.arch }})` exists because a matrix job's default display
  name concatenates every matrix value — including the full description — which would make the
  post-merge arch-leg proof unreadable.
- `"archs": json.dumps([a])` hands the template a one-element JSON array per leg, so the
  cross-product-with-skip happens once, in `detect`, where the declaration is readable. The
  template's own `no build_from.<arch>` guard then becomes unreachable for every add-on that
  declares `build_from` — that unreachability IS the structural guarantee the item asks for. It
  stays reachable, correctly, for the `config.yaml arch:` fallback path: an add-on with an arch in
  `config.yaml` but no `build_from` cannot be built at all, and the template's existing explicit
  error is the right way to say so.
</reference_implementation>

<!--
Comment-text discipline (#429): Task 3 rewrites specific SENTENCES in nine files, so its
<action> has to quote each sentence verbatim to anchor the edit unambiguously. Every negative
grep below targets a REPOSITORY file; none of them reads this plan (`.planning/` is excluded from
the one repo-wide sweep, G3-8), so no literal quoted here can invalidate its own gate.

Second discipline rule, learned from G3-3's original form: a negative grep must target the whole
LIVE-CLAIM sentence, never the bare noun phrase inside it. `per-add-on workflows` is the natural
wording for a historically correct replacement ("the nine per-add-on workflows were replaced by
build.yml"), so G3-3 greps the full clause `Images are built by the per-add-on workflows` and
pairs it with a POSITIVE assertion that README names `build.yml` and the `**/config.*` glob. The
same rule produced G3-8's full-path convention and G3-10's `gh workflow run build-` command form:
in every case the forbidden string is a live instruction, not a noun.
-->
<!-- planner-discipline-allow: tag-trigger temporarily disabled -->
<!-- planner-discipline-allow: Re-enabling a tag trigger -->
<!-- planner-discipline-allow: per-add-on workflows -->
<!-- planner-discipline-allow: per-addon callers -->
<!-- planner-discipline-allow: seven per-addon -->
<!-- planner-discipline-allow: fires on the tag push -->
<!-- planner-discipline-allow: every workflow also triggers on -->
<!-- planner-discipline-allow: per-addon build workflows -->
<!-- planner-discipline-allow: invoked by build-<addon>.yml -->
<!-- planner-discipline-allow: build-<addon>.yml -->
<!-- planner-discipline-allow: per-addon `tags:` pattern -->
<!-- planner-discipline-allow: Images are built by the per-add-on workflows -->
<!-- planner-discipline-allow: gh workflow run build- -->
<!-- planner-discipline-allow: canonical image for the tag -->
<!-- planner-discipline-allow: will trigger -->
<!-- planner-discipline-allow: tag is required -->
<!-- planner-discipline-allow: .github/workflows/build- -->

<tasks>

<task type="tracer">
  <name>Task 1: End-to-end "dispatch a build for any add-on by name" — one dispatchable path, nine callers untouched</name>
  <files>.github/workflows/build.yml</files>
  <precondition>Sibling 260909-rlj has landed: `internal/dispatch-builds.sh` exists and is executable, and `grep -q HEAD_COMMIT_TIMESTAMP .github/workflows/_build-template.yml` succeeds. If either fails, HALT — this item rewrites rlj's script and has no base without it. Also assert `git rev-parse --verify 7cc82f5^{commit}` and `git rev-parse --verify 8c6645f^{commit}` succeed; gate G1-4d pins those two shas as its diff anchors (one add-on changed / `.planning`-only) rather than a relative `HEAD~N`, so a commit from a parallel session cannot change what it measures. If a sha is unreachable, substitute any commit with the same shape and recompute the expectation from it, as G1-4d already does.</precondition>
  <read_first>
`.github/workflows/build-coding-assistants.yml` and `.github/workflows/build-meridian.yml` in full
(28 lines each — the two-arch and one-arch shapes). `.github/workflows/_build-template.yml` lines
9-46 (the `workflow_call` input and secret contract this file must satisfy) and 63-66 (the arch
matrix that consumes `archs`). `<reference_implementation>` above in full.
  </read_first>
  <action>
Create `.github/workflows/build.yml` from `<reference_implementation>` with ONE modification: the
`on:` block contains **only** `workflow_dispatch:` with its `addons` input. Do NOT add the `push:`
block yet, and do NOT delete any caller — that is Task 2 (L-14, D-03). At this commit `main`'s
build behaviour must be indistinguishable from today's, with `build.yml` present but inert until
dispatched.

Everything else lands as written: the derivation, the `env:` indirection (L-6), `fetch-depth: 0`
(L-7), the `nobuild` guard (L-8), the detect `timeout-minutes` and the absence of one on the build
job (L-9), `fail-fast: false` (L-10), the `addons != '[]'` guard (L-11), both `permissions` blocks,
and the four named `secrets:` mappings copied from the callers.

Two discipline rules that the gates depend on, stated so no gate can reject correct work:

- Inside the detect step's `run:` body, do not write the GitHub expression delimiters at all —
  not in code (L-6) and not in a comment. G1-5 greps the extracted body and cannot tell the
  difference. Explain the `env:` indirection in a comment ABOVE the `env:` block instead, where
  the extraction never reaches.
- G1-6 forbids every add-on directory name and every `config.yaml` `name:` value from appearing in
  a NON-COMMENT line of `build.yml`. Mentioning an add-on in a comment is allowed and encouraged
  (for example noting which add-on is the two-arch case), but such a mention must sit on its own
  full-line comment — a trailing comment on a value line shares that line and trips the gate.

Verify the two actionlint versions yourself before declaring done: the pre-commit-pinned v1.7.3
via `pre-commit run actionlint --files .github/workflows/build.yml`, and the latest release
resolved the way `lint.yml:60-66` does (`curl` the release API for the tag name, download the
`linux_amd64` tarball to a temp dir, run it). `actionlint` is not on PATH (measured), so the
second one must be fetched. If the fetch fails for lack of network, the task is NOT done: record
it and stop rather than declaring a gate satisfied that never ran.
  </action>
  <verify>
    <automated>f=.github/workflows/build.yml; python3 -c "
import sys, yaml
d = yaml.safe_load(open('$f'))
on = d.get('on', d.get(True))
assert set(on) == {'workflow_dispatch'}, on
wd = on['workflow_dispatch']
i = wd['inputs']['addons']
assert i.get('required') is False and i.get('default') == '' and i.get('type') == 'string', i
assert 'jobs' in d and set(d['jobs']) == {'detect', 'build'}, list(d.get('jobs', {}))
print('GATE-G1-1-PASS')"</automated>
    <automated>[ "$(ls .github/workflows/build-*.yml 2>/dev/null | wc -l)" -eq 9 ] && echo GATE-G1-2-PASS</automated>
    <automated>python3 -c "
import yaml
b = yaml.safe_load(open('.github/workflows/build.yml'))['jobs']['build']
c = yaml.safe_load(open('.github/workflows/build-meridian.yml'))['jobs']['build']
assert sorted(b['secrets']) == sorted(c['secrets']), (sorted(b['secrets']), sorted(c['secrets']))
assert b['permissions'] == c['permissions'], (b['permissions'], c['permissions'])
assert b['uses'] == c['uses'], b['uses']
assert b['strategy']['fail-fast'] is False, b['strategy']
assert 'timeout-minutes' not in b, 'timeout-minutes is a lint error on a uses: job'
assert b['with'] == {'addon-name': '\${{ matrix.addon }}', 'addon-display-name': '\${{ matrix.display_name }}', 'addon-description': '\${{ matrix.description }}', 'archs': '\${{ matrix.archs }}'}, b['with']
print('GATE-G1-3-PASS')"</automated>
    <automated>s=$(mktemp) && o=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && env GITHUB_OUTPUT="$o" EVENT_NAME=workflow_dispatch BEFORE_SHA= HEAD_SHA= ADDONS_INPUT=meridian bash "$s" >/dev/null && python3 -c "
import json, yaml
out = dict(l.split('=', 1) for l in open('$o').read().splitlines() if '=' in l)
assert json.loads(out['addons']) == ['meridian'], out['addons']
inc = json.loads(out['matrix'])['include']
cfg = yaml.safe_load(open('meridian/config.yaml'))
assert len(inc) == 1 and inc[0]['arch'] == 'amd64' and inc[0]['archs'] == '[\"amd64\"]', inc
assert inc[0]['display_name'] == cfg['name'] and inc[0]['description'] == cfg['description'], inc
print('GATE-G1-4a-PASS')" && rm -f "$s" "$o"</automated>
    <automated>s=$(mktemp) && o=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && env GITHUB_OUTPUT="$o" EVENT_NAME=workflow_dispatch BEFORE_SHA= HEAD_SHA= ADDONS_INPUT=coding-assistants bash "$s" >/dev/null && python3 -c "
import json
out = dict(l.split('=', 1) for l in open('$o').read().splitlines() if '=' in l)
inc = json.loads(out['matrix'])['include']
assert [e['arch'] for e in inc] == ['amd64', 'aarch64'], inc
assert {e['addon'] for e in inc} == {'coding-assistants'}, inc
print('GATE-G1-4b-PASS')" && rm -f "$s" "$o"</automated>
    <automated>s=$(mktemp) && o=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && env GITHUB_OUTPUT="$o" EVENT_NAME=workflow_dispatch BEFORE_SHA= HEAD_SHA= ADDONS_INPUT= bash "$s" >/dev/null && python3 -c "
import glob, json, os
out = dict(l.split('=', 1) for l in open('$o').read().splitlines() if '=' in l)
exp = sorted(os.path.dirname(p) for p in glob.glob('*/config.yaml')
             if os.path.isfile(os.path.dirname(p) + '/build.yaml') and os.path.isfile(os.path.dirname(p) + '/Dockerfile'))
assert json.loads(out['addons']) == exp, (json.loads(out['addons']), exp)
assert len(exp) == 9, exp
assert len(json.loads(out['matrix'])['include']) == 10, len(json.loads(out['matrix'])['include'])
print('GATE-G1-4c-PASS')" && rm -f "$s" "$o"</automated>
    <automated>s=$(mktemp) && o=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && one=$(git rev-parse 7cc82f5) && pln=$(git rev-parse 8c6645f) && raw1=$(git show --name-only --format= "$one") && exp1=$(printf '%s\n' "$raw1" | grep -E '^[^/]+/(config|build)\.[^/]+$|^[^/]+/Dockerfile$' | awk -F/ 'NF {print $1}' | sort -u | paste -sd, -) && [ -n "$exp1" ] && r() { : >"$o"; env GITHUB_OUTPUT="$o" EVENT_NAME=push BEFORE_SHA="$1" HEAD_SHA="$2" ADDONS_INPUT= bash "$s" >/dev/null; grep '^addons=' "$o" | cut -d= -f2-; } && a=$(r "$(git rev-parse "$one"^)" "$one") && b=$(r "$(git rev-parse "$pln"^)" "$pln") && c=$(r deadbeefdeadbeefdeadbeefdeadbeefdeadbeef "$one") && d=$(r 0000000000000000000000000000000000000000 "$one") && [ "$a" = "[\"$exp1\"]" ] && [ "$b" = "[]" ] && [ "$c" = "$a" ] && [ "$d" = "$a" ] && rm -f "$s" "$o" && echo GATE-G1-4d-PASS</automated>
    <automated>s=$(mktemp) && o=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && env GITHUB_OUTPUT="$o" EVENT_NAME=workflow_dispatch BEFORE_SHA= HEAD_SHA= ADDONS_INPUT='tools,nonexistent-addon,../../etc,.planning' bash "$s" >/dev/null; rc=$?; [ "$rc" -eq 0 ] && [ "$(grep '^addons=' "$o" | cut -d= -f2-)" = "[]" ] && [ "$(grep '^matrix=' "$o" | cut -d= -f2-)" = '{"include":[]}' ] && rm -f "$s" "$o" && echo GATE-G1-4e-PASS</automated>
    <automated>s=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && ! grep -q '\${{' "$s" && bash -n "$s" && rm -f "$s" && echo GATE-G1-5-PASS</automated>
    <automated>python3 -c "
import glob, os, re, yaml
body = [l for l in open('.github/workflows/build.yml').read().splitlines() if not re.match(r'^\s*#', l)]
body = '\n'.join(body)
bad = []
for p in sorted(glob.glob('*/config.yaml')):
    d = os.path.dirname(p)
    cfg = yaml.safe_load(open(p)) or {}
    for lit in (d, cfg.get('name') or '', cfg.get('description') or ''):
        if lit and lit in body:
            bad.append((d, lit[:40]))
assert not bad, bad
assert '[\"amd64\", \"aarch64\"]' not in body and \"'[\\\"amd64\\\"]'\" not in body, 'hand-authored arch list'
print('GATE-G1-6-PASS')"</automated>
    <automated>yamllint -c .yamllint.yml .github/workflows/build.yml && pre-commit run actionlint --files .github/workflows/build.yml && d=$(mktemp -d) && V=$(curl -s https://api.github.com/repos/rhysd/actionlint/releases/latest | jq -r .tag_name) && [ -n "$V" ] && [ "$V" != "null" ] && curl -sL "https://github.com/rhysd/actionlint/releases/download/${V}/actionlint_${V#v}_linux_amd64.tar.gz" | tar xz -C "$d" actionlint && "$d/actionlint" .github/workflows/build.yml && echo "GATE-G1-7-PASS (latest=$V)" && rm -rf "$d"</automated>
    <automated>python3 -c "
import yaml
d = yaml.safe_load(open('.github/workflows/build.yml'))
det = d['jobs']['detect']
assert isinstance(det.get('timeout-minutes'), int), det.get('timeout-minutes')
assert det['permissions'] == {'contents': 'read'}, det['permissions']
assert 'nobuild' in det['if'], det['if']
assert 'head_commit' in det['if'], det['if']
ck = [s for s in det['steps'] if 'checkout' in str(s.get('uses', ''))][0]
assert ck['with']['fetch-depth'] == 0, ck
env = [s for s in det['steps'] if s.get('id') == 'detect'][0]['env']
assert set(env) == {'EVENT_NAME', 'BEFORE_SHA', 'HEAD_SHA', 'ADDONS_INPUT'}, sorted(env)
assert det['outputs'] == {'addons': '\${{ steps.detect.outputs.addons }}', 'matrix': '\${{ steps.detect.outputs.matrix }}'}, det['outputs']
b = d['jobs']['build']
assert b['needs'] == 'detect' or b['needs'] == ['detect'], b['needs']
assert b['if'].strip() == \"\${{ needs.detect.outputs.addons != '[]' }}\", b['if']
print('GATE-G1-8-PASS')"</automated>
    <automated>pre-commit run --files .github/workflows/build.yml</automated>
  </verify>
  <done>
`.github/workflows/build.yml` exists with `workflow_dispatch:` as its ONLY trigger and an
`addons` input (`required: false`, `type: string`, `default: ""`), and all nine
`.github/workflows/build-*.yml` are still present and unmodified.

Its build job matches `build-meridian.yml`'s call site on `uses`, `permissions` and the four
named `secrets:`, carries `fail-fast: false`, declares NO `timeout-minutes`, and passes exactly
the four `matrix.*` expressions as `with:` inputs. Its detect job declares
`timeout-minutes`, `permissions: {contents: read}`, `fetch-depth: 0`, a `nobuild` head-commit
guard, and exactly the four `env:` keys; the build job is guarded on
`needs.detect.outputs.addons != '[]'`.

The detect step's `run:` body, extracted from the file with PyYAML, contains no GitHub expression
delimiters, parses under `bash -n`, and produces: `["meridian"]` with one amd64 leg whose
display name and description are byte-equal to `meridian/config.yaml`; `coding-assistants` with
legs `amd64` then `aarch64`; empty input yielding the nine add-ons and 10 legs; the `7cc82f5`
diff yielding exactly `gatus`; the `.planning`-only `8c6645f` diff yielding `[]`; an unresolvable
and an all-zero `BEFORE_SHA` both falling back to the single-commit diff and still yielding
`gatus`; and `tools,nonexistent-addon,../../etc,.planning` yielding `[]` with exit 0.

No add-on directory name, `config.yaml` `name:` value, `config.yaml` `description:` value or
hand-authored arch-list literal appears in any non-comment line of the file. `yamllint`,
actionlint v1.7.3 (via pre-commit), the latest actionlint release, and
`pre-commit run --files` all pass.
  </done>
  <reversibility rating="reversible">A new, additive workflow file whose only trigger is a manual dispatch. Nothing references it yet; deleting the file restores the previous state exactly.</reversibility>
</task>

<task type="auto">
  <name>Task 2: The switch-over — push trigger, nine callers deleted, one batched dispatch — as ONE revertible commit</name>
  <files>.github/workflows/build.yml, internal/dispatch-builds.sh</files>
  <precondition>Task 1 is committed and `internal/dispatch-builds.sh` exists, is executable, and still dispatches per-add-on workflows (rlj's shape). If the script is missing, HALT: there is nothing to rewrite and deleting the nine callers would leave the bump workflows dispatching files that do not exist.</precondition>
  <read_first>
`internal/dispatch-builds.sh` in full — this task rewrites its classification and dispatch, and
must preserve every clause of `<script_contract>` marked PRESERVED. Also
`internal/check-version-tags.sh` lines 34-40 for the repository's existing definition of "this
path is an add-on directory" (`config.yaml` and `build.yaml` both present), which this rewrite
adopts and extends with `Dockerfile` so the script and `build.yml` classify identically.
  </read_first>
  <behavior>
Behaviours the gates assert, in the order written. Establish them before declaring the task done.

- Two dispatchable candidates and a `gh` that succeeds: exactly ONE `gh` process runs, its argv is
  exactly `workflow run build.yml --ref main -f addons=coding-assistants,meridian`, both
  candidates print `DISPATCHED`, exit 0. The comma list is in `sort -u` order.
- A `gh` that fails: every dispatchable candidate prints `FAILED` and the exit is 1.
- `DRY_RUN=1 meridian nonexistent-addon`: stdout is exactly `meridian DRY_RUN` then
  `nonexistent-addon SKIPPED_NO_WORKFLOW` (ordering preserved from rlj's contract), exactly one
  `DRY_RUN: ` line naming `build.yml`, no occurrence of the string `build-meridian.yml`, a `WARN:`
  on stderr, exit 0.
- Every candidate skipped: **zero** `gh` processes run and zero `DRY_RUN: ` lines print. An empty
  `addons` value would mean "build all nine" (L-12), so the script must never reach `gh`.
- `../../etc`: `SKIPPED_BAD_NAME`, no `gh` invocation.
- Unset `BASE_SHA` in derive mode: exit exactly 1. Unresolvable `BASE_SHA`: exit non-zero and
  non-127.
- The derive-mode candidate set still equals `git diff --name-only "$BASE_SHA..HEAD" | cut -d/ -f1
  | sort -u` exactly — rlj's GATE-T1-6 re-run unchanged (D-05).
- The set the script classifies as dispatchable, given every top-level add-on directory, equals
  `build.yml`'s own empty-input `addons` output. Two independent implementations, one answer.
  </behavior>
  <action>
**Part 1 — `.github/workflows/build.yml`: add the `push:` trigger.** Insert the `push:` block from
`<reference_implementation>` above the existing `workflow_dispatch:` — `branches: [main]` and the
three `paths` globs, and NO `tags:` key (D-01, L-2). Nothing else in the file changes.

**Part 2 — delete all nine callers** in the same commit:
`.github/workflows/build-authentik.yml`, `build-coding-assistants.yml`, `build-gatus.yml`,
`build-iac-runner.yml`, `build-markdown-renderer.yml`, `build-meridian.yml`,
`build-network-tools.yml`, `build-phone-logger.yml`, `build-terraform-bridge.yml`. Use
`git rm` so the deletion is staged. `_build-template.yml` is NOT deleted (L-1).

**Part 3 — rewrite `internal/dispatch-builds.sh`** to issue one dispatch. Keep the file's
structure, `set -euo pipefail`, no-shell-functions style, mode 755 and every shellcheck
discipline rule from L-16. Three changes and nothing else:

1. **Classification.** Replace the `.github/workflows/build-<addon>.yml` regular-file test with a
   test that all three of `<addon>/config.yaml`, `<addon>/build.yaml` and `<addon>/Dockerfile` are
   regular files. Keep the state name `SKIPPED_NO_WORKFLOW` (L-13) and keep the WARN-and-continue
   semantics (rlj's L-5). The WARN text must state the new reason — the path is not an add-on
   directory, which is the common case for a bump commit that also touches `.planning`,
   `internal`, `.github` and root files. Add a comment recording WHY the triple and not just
   `config.yaml`: it is the same definition `lint.yml`, the `release` target in `Makefile` and
   `check-version-tags.sh` already use, and using the identical triple is what keeps this script
   from ever being MORE restrictive than `build.yml` — a script that skipped an add-on
   `build.yml` would have accepted is a silently missing image, whereas the reverse is only a
   harmless no-op run.
2. **Two passes instead of one.** Because one dispatch carries one outcome, the loop can no longer
   print as it goes. Classify every candidate first, accumulating two parallel newline-separated
   lists in `sort -u` order — the candidate name and its state, with dispatchable candidates in a
   `PENDING` state — then run the single dispatch, then print the `ADDON` lines in that same order
   with `PENDING` resolved to `DISPATCHED`, `FAILED` or `DRY_RUN`. Do NOT re-sort at print time:
   the input list is already `sort -u`ed in both modes, and re-sorting would hide an ordering bug
   rather than prevent one. Comment that the ordering is contract, not cosmetics, and name rln's
   G2-3 and rlj's GATE-T1-5 as the assertions that depend on it.
3. **One dispatch.** Build `addon_list` as the dispatchable names comma-joined in that order, and
   invoke `gh workflow run build.yml --ref "$ref" -f addons="$addon_list"` inside an `if` (a bare
   call returning non-zero would abort under `set -e` before the states can be printed). Guard it:
   when `addon_list` is empty the script must NOT call `gh` at all — comment that an empty
   `addons` input means "build every add-on" in `build.yml`, so an empty-list dispatch would turn
   a no-op into nine full builds. Under `DRY_RUN=1`, print the single command it would have run
   prefixed `DRY_RUN: ` and skip the invocation.

Also update the header comment: the dispatch target is now `build.yml`, one dispatch with a list;
the `ADDON <name> <STATE>` contract and its ordering are unchanged; `SKIPPED_NO_WORKFLOW` now
means "no add-on manifest at that path". Keep rlj's root-cause paragraph and the
`https://docs.github.com/actions/using-workflows/triggering-a-workflow` link. When referring to
the removed callers in prose, write them as `build-<addon>.yml` **without** the
`.github/workflows/` prefix — the repo-wide gate G3-8 negative-greps the full-path form
specifically so that historical prose stays possible while a live path reference to a deleted file
cannot survive.

Do NOT change the derive-mode pipeline, the ref resolution, the `-h`/`--help` path, the
`BASE_SHA`-unset error, the name-shape check or the exit semantics (D-05, L-13).
  </action>
  <verify>
    <automated>[ "$(ls .github/workflows/build-*.yml 2>/dev/null | wc -l)" -eq 0 ] && [ -f .github/workflows/build.yml ] && [ -f .github/workflows/_build-template.yml ] && idx=$(git ls-files -- '.github/workflows/build-*.yml') && [ -z "$idx" ] && echo GATE-G2-1-PASS</automated>
    <automated>python3 -c "
import re, yaml
d = yaml.safe_load(open('.github/workflows/build.yml'))
on = d.get('on', d.get(True))
assert set(on) == {'push', 'workflow_dispatch'}, on
p = on['push']
assert p['branches'] == ['main'], p
assert p['paths'] == ['**/config.*', '**/build.*', '**/Dockerfile'], p
assert 'tags' not in p, p
src = [l for l in open('.github/workflows/build.yml').read().splitlines() if not re.match(r'^\s*#', l)]
assert not [l for l in src if re.match(r'^\s*tags:', l)], 'tags key present'
print('GATE-G2-2-PASS')"</automated>
    <automated>out=$(DRY_RUN=1 ./internal/dispatch-builds.sh meridian nonexistent-addon 2>/dev/null) && [ "$(printf '%s\n' "$out" | awk '$1=="ADDON"{print $2, $3}' | paste -sd'|' -)" = "meridian DRY_RUN|nonexistent-addon SKIPPED_NO_WORKFLOW" ] && $(printf '%s\n' "$out" | awk '/^DRY_RUN: /{n++} END{exit !(n==1)}') && printf '%s\n' "$out" | grep -q 'gh workflow run build\.yml' && ! printf '%s\n' "$out" | grep -q 'build-meridian\.yml' && DRY_RUN=1 ./internal/dispatch-builds.sh nonexistent-addon 2>&1 1>/dev/null | grep -q '^WARN' && echo GATE-G2-3a-PASS</automated>
    <automated>d=$(mktemp -d) && printf '#!/bin/sh\nprintf "%%s\\n" "$@" >"$GH_ARGS"\necho x >>"$GH_CALLS"\nexit 0\n' >"$d/gh" && chmod 755 "$d/gh" && GH_ARGS="$d/args" GH_CALLS="$d/calls" PATH="$d:$PATH" REF=main ./internal/dispatch-builds.sh meridian coding-assistants >"$d/out" 2>/dev/null && [ "$(wc -l <"$d/calls")" -eq 1 ] && [ "$(paste -sd' ' "$d/args")" = "workflow run build.yml --ref main -f addons=coding-assistants,meridian" ] && [ "$(awk '$1=="ADDON"{print $2, $3}' "$d/out" | paste -sd'|' -)" = "coding-assistants DISPATCHED|meridian DISPATCHED" ] && rm -rf "$d" && echo GATE-G2-3b-PASS</automated>
    <automated>d=$(mktemp -d) && printf '#!/bin/sh\necho x >>"$GH_CALLS"\nexit 1\n' >"$d/gh" && chmod 755 "$d/gh"; GH_CALLS="$d/calls" PATH="$d:$PATH" REF=main ./internal/dispatch-builds.sh meridian coding-assistants >"$d/out" 2>/dev/null; rc=$?; [ "$rc" -eq 1 ] && [ "$(wc -l <"$d/calls")" -eq 1 ] && [ "$(awk '$1=="ADDON"{print $3}' "$d/out" | sort -u)" = "FAILED" ] && rm -rf "$d" && echo GATE-G2-3c-PASS</automated>
    <automated>d=$(mktemp -d) && printf '#!/bin/sh\necho x >>"$GH_CALLS"\nexit 0\n' >"$d/gh" && chmod 755 "$d/gh"; GH_CALLS="$d/calls" PATH="$d:$PATH" REF=main ./internal/dispatch-builds.sh nonexistent-addon tools >"$d/out" 2>/dev/null; rc=$?; [ "$rc" -eq 0 ] && [ ! -s "$d/calls" ] && [ "$(awk '$1=="ADDON"{print $3}' "$d/out" | sort -u)" = "SKIPPED_NO_WORKFLOW" ] && [ "$(grep -c '^DRY_RUN: ' "$d/out")" -eq 0 ] && rm -rf "$d" && echo GATE-G2-3d-PASS</automated>
    <automated>out=$(DRY_RUN=1 ./internal/dispatch-builds.sh '../../etc' 2>/dev/null) && [ "$(printf '%s\n' "$out" | awk '$1=="ADDON"{print $3}')" = "SKIPPED_BAD_NAME" ] && ! printf '%s\n' "$out" | grep -q 'gh workflow run' && echo GATE-G2-3e-PASS</automated>
    <automated>( unset BASE_SHA; DRY_RUN=1 ./internal/dispatch-builds.sh >/dev/null 2>&1 ); [ "$?" -eq 1 ] && echo GATE-G2-3f-PASS</automated>
    <automated>DRY_RUN=1 BASE_SHA=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef ./internal/dispatch-builds.sh >/dev/null 2>&1; rc=$?; [ "$rc" -ne 0 ] && [ "$rc" -ne 127 ] && echo GATE-G2-3g-PASS</automated>
    <automated>b=7cc82f5; git rev-parse --verify "$b^{commit}" >/dev/null && raw=$(git diff --name-only "$b..HEAD") && exp=$(printf '%s\n' "$raw" | cut -d/ -f1 | sort -u | grep -v '^$') && act=$(DRY_RUN=1 BASE_SHA="$b" ./internal/dispatch-builds.sh 2>/dev/null | awk '$1=="ADDON"{print $2}' | sort -u) && [ -n "$exp" ] && [ "$exp" = "$act" ] && echo GATE-G2-4-PASS</automated>
    <automated>s=$(mktemp) && o=$(mktemp) && python3 -c "
import yaml
wf = yaml.safe_load(open('.github/workflows/build.yml'))
st = [x for x in wf['jobs']['detect']['steps'] if x.get('id') == 'detect'][0]
open('$s', 'w').write(st['run'])" && env GITHUB_OUTPUT="$o" EVENT_NAME=workflow_dispatch BEFORE_SHA= HEAD_SHA= ADDONS_INPUT= bash "$s" >/dev/null && wf=$(grep '^addons=' "$o" | cut -d= -f2- | jq -r '.[]' | sort | paste -sd, -) && dirs=$(for c in */config.yaml; do if [ -f "$c" ]; then printf '%s\n' "${c%/config.yaml}"; fi; done) && sc=$(DRY_RUN=1 ./internal/dispatch-builds.sh $dirs 2>/dev/null | awk '$1=="ADDON" && $3=="DRY_RUN"{print $2}' | sort | paste -sd, -) && [ -n "$wf" ] && [ "$wf" = "$sc" ] && rm -f "$s" "$o" && echo "GATE-G2-5-PASS ($wf)"</automated>
    <automated>shellcheck internal/dispatch-builds.sh && [ "$(stat -c %a internal/dispatch-builds.sh)" = "755" ] && ! grep -q '\.github/workflows/build-' internal/dispatch-builds.sh && grep -q 'build\.yml' internal/dispatch-builds.sh && echo GATE-G2-6-PASS</automated>
    <automated>yamllint -c .yamllint.yml .github/workflows/build.yml && pre-commit run --files .github/workflows/build.yml internal/dispatch-builds.sh && d=$(mktemp -d) && V=$(curl -s https://api.github.com/repos/rhysd/actionlint/releases/latest | jq -r .tag_name) && [ -n "$V" ] && [ "$V" != "null" ] && curl -sL "https://github.com/rhysd/actionlint/releases/download/${V}/actionlint_${V#v}_linux_amd64.tar.gz" | tar xz -C "$d" actionlint && "$d/actionlint" && rm -rf "$d" && echo GATE-G2-7-PASS</automated>
  </verify>
  <done>
Zero `.github/workflows/build-*.yml` files remain, all nine deletions are staged,
`build.yml` and `_build-template.yml` are both present, and `build.yml`'s `on:` is exactly
`push` (branches `[main]`, the three manifest globs, **no** `tags`) plus `workflow_dispatch`, with
no `tags:` key on any non-comment line.

`internal/dispatch-builds.sh` is mode 755, shellcheck-clean with NO `-e` flags, contains no
`.github/workflows/build-` path and does reference `build.yml`. Its observable behaviour:
`DRY_RUN=1 meridian nonexistent-addon` prints `meridian DRY_RUN` then
`nonexistent-addon SKIPPED_NO_WORKFLOW` with exactly one `DRY_RUN: ` line naming
`gh workflow run build.yml`, no `build-meridian.yml` anywhere, a `WARN:` on stderr and exit 0;
two dispatchable candidates cause exactly ONE `gh` process with argv
`workflow run build.yml --ref main -f addons=coding-assistants,meridian` and two `DISPATCHED`
lines; a failing `gh` yields `FAILED` for both and exit 1; an all-skipped candidate list causes
ZERO `gh` processes, zero `DRY_RUN: ` lines and exit 0; `../../etc` yields `SKIPPED_BAD_NAME` with
no invocation; unset `BASE_SHA` exits exactly 1 and an unresolvable one exits non-zero non-127.

rlj's derive-mode assertion still holds unchanged, and the dispatchable set the script computes for
every add-on directory is byte-equal to `build.yml`'s own empty-input `addons` output. `yamllint`,
`pre-commit run --files` and a whole-repository run of the latest actionlint all pass.
  </done>
  <reversibility rating="costly">This is the switch-over. A single `git revert` of this commit restores all nine callers, removes the push trigger and restores the per-add-on dispatch, leaving `build.yml` present and dispatchable — but between landing and revert, an automated bump could dispatch a builder that does not work, which is why `<verification>`'s post-merge dispatch proof is mandatory before the next 06:00 UTC cron.</reversibility>
</task>

<task type="auto">
  <name>Task 3: Record the tag-trigger decision in RELEASE.md and retire the eight prose sites the deletion falsified</name>
  <files>.github/RELEASE.md, README.md, docs/DEVELOPMENT.md, docs/WEBHOOK_SETUP.md, docs/UPDATE_VERSION.md, docs/AUTO_UPDATE_GUIDE.md, internal/check-version-tags.sh, internal/update-version.py, .github/workflows/_build-template.yml</files>
  <precondition>**Siblings rll and rlm have landed** — assert all four, and HALT on any failure, because this task edits prose they wrote and L-18 pins their literals: `grep -qF '15 of the 40' .github/RELEASE.md` (rlm's Tag-schema subsection), `grep -qF 'internal/dispatch-builds.sh' docs/AUTO_UPDATE_GUIDE.md` (rlm's Task 2 rewrite), `grep -qF 'Pushed tag: {tag}' internal/update-version.py` and `grep -c 'will trigger' internal/update-version.py` returning 0 (rll's Task 2). **The nine-row add-on table in `.github/RELEASE.md` is still intact** — `grep -c -E '^\| (authentik|coding-assistants|gatus|iac-runner|markdown-renderer|meridian|network-tools|phone-logger|terraform-bridge) ' .github/RELEASE.md` is 9; G3-2 rewrites that table into two columns and cannot do so if rlm left it in another shape. **Then MEASURE, do not assume, the two counts this task drives to zero** — `grep -rnIF '.github/workflows/build-' --exclude-dir=.planning --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir='.venv*' . | wc -l` (3 at `5b41d49`, higher after rlm plants more; the `-I` and the two extra excludes are mandatory — `py_compile`, which G3-7c and rll's own gate both run, leaves a `.pyc` under `internal/__pycache__/` that still carries the pre-edit docstring, and `grep -rn` counts a binary match as a line) and `grep -cF 'gh workflow run build-' .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md` — and record both in the SUMMARY as the measured starting point. `.github/RELEASE.md` should still contain the headings `### Why the split`, `### What this means operationally` and `### Re-enabling a tag trigger`; if any is gone, do NOT guess — re-read the file, locate whatever now describes the tag-trigger split, and edit that instead. Every anchor below is heading or phrase text, never a line number, for exactly this reason.</precondition>
  <read_first>
`.github/RELEASE.md` in full **as it stands after rlm** — the tag schema and rlm's new
tag-guarantee subsection, the nine-row trigger table, the two rationale subsections, the
re-enabling recipe, and `## Auto-update path` (which rlm wrote and this task must reconcile).
`docs/AUTO_UPDATE_GUIDE.md` in full, likewise post-rlm — specifically whatever section now
documents the `GITHUB_TOKEN` limitation and the dispatch, the error-handling section, and the
"adding a new add-on" steps. `internal/check-version-tags.sh` lines 1-8 (the header being
corrected) and 51-77 (the `LOCAL_BUILD_ADDONS` block, which must NOT change).
`internal/update-version.py` — `create_and_push_tag`'s docstring AND its tag-push success output,
both **as rll rewrote them**, not as they read at `5b41d49`. `docs/DEVELOPMENT.md` lines 87-92,
128-140 and 180-190. `<sibling_supersession>` and L-18 above: they tell you which literals in
those files are load-bearing for a sibling's gate.
  </read_first>
  <action>
Nine prose sites — the eight in D-06 plus `.github/RELEASE.md`. All are comments or
documentation: no executable behaviour changes in this task. `internal/check-version-tags.sh` is
hash-pinned to prove it; `internal/update-version.py` is held by scoped invariants instead,
because rll rewrote two of its string literals one wave ago and this task rewrites them again
(`<sibling_supersession>`).

1. **`.github/RELEASE.md` — the mandated record (D-01, D-02).** In the `## Tag schema` section,
   replace the paragraph beginning "Every per-addon build workflow" and the nine-row trigger table
   with: one sentence stating that a single `build.yml` builds every add-on and derives the add-on
   list, arch legs, display name and description from the add-on's own `config.yaml` /
   `build.yaml`; and a two-column table (`Add-on` | `Supervisor image source`) preserving today's
   nine rows and both `local build` values (`authentik`, `iac-runner`). Keep the paragraph that
   explains what the `Supervisor image source` column means. Drop the sentence about the
   `# tag-trigger temporarily disabled` in-file comment — that comment no longer exists anywhere.
   Add a subsection whose heading is exactly `### Tags do not trigger builds` (gate G3-1 greps
   that heading verbatim) carrying D-01's decision and its four reasons. For the tag/version
   off-by-one, CROSS-REFERENCE rlm's tag-guarantee subsection rather than restating its numbers
   (L-18): rlm already wrote the dated `15 of the 40` measurement with a `git show` reproduce
   command, and a second copy is a second thing to drift. For the three add-ons whose trigger was
   live the rate is 1 of 8, which rlm did not write and this subsection may state. State
   plainly that the tag is now a release marker only, that `internal/check-version-tags.sh` still
   enforces it, and that the image is published by the bump commit's `paths:` build, by the bump
   workflows' dispatch, or by an explicit `workflow_dispatch`.
   Compress `### Why the split` into a short history note — **keep the heading itself and its
   `all seven` clause**, which is a true historical statement about commit `287c79f` and is
   pinned by rlm's `H0`/`H1` (L-18) — that KEEPS both commit citations (`287c79f`, `60e7835`) as
   the reason the tags and the split ever existed, and rewrite
   `### What this means operationally` around the bump commit instead of the tag — the ghcr-404
   consequence and the `image:`-key axis both survive unchanged; what dies is the claim that
   pushing the tag alone builds anything, and the double-build paragraph naming
   `network-tools`, `terraform-bridge` and `iac-runner`.
   Replace the whole `### Re-enabling a tag trigger` subsection (it instructs the reader to edit a
   file that no longer exists) with a rebuild-on-demand recipe: `gh workflow run build.yml -f
   addons=<name>` for one add-on, an empty `addons` for all of them, and
   `internal/dispatch-builds.sh <name> ...` as the local equivalent.
   Dropping the in-file-comment sentence and this subsection removes both of rlm's `six callers`
   occurrences and its re-enable steps; that is recorded and dispositioned in
   `<sibling_supersession>` § 1 and is not a defect.
   **Also reconcile `## Auto-update path`, which rlm wrote one wave ago and Task 2 falsifies.**
   Its current body describes the dispatch as one run per add-on naming that add-on's own workflow
   file, states the skip reason as a missing build workflow file, and carries a live full-path
   reference to a file Task 2 deletes. Rewrite exactly those three claims: ONE
   `gh workflow run build.yml --ref <ref> -f addons=<sorted comma list>` naming every changed
   add-on; the skip reason is "that path is not an add-on directory" (no
   `config.yaml` + `build.yaml` + `Dockerfile` triple); and the full-path form goes away under the
   prose convention below. Every other literal in that section is pinned by L-18 and must survive
   verbatim — `internal/dispatch-builds.sh`, `GITHUB_TOKEN`, `workflow_dispatch`, the
   docs.github.com trigger link, `--no-tag`, `docs/AUTO_UPDATE_GUIDE.md` and `Auto Update`. Keep
   rlm's failure semantics intact: a skip warns without failing the run, a failed dispatch exits
   non-zero. Likewise, when rewriting `### What this means operationally`, keep rlm's `human`
   scoping, its `GITHUB_TOKEN` caveat and its `Auto-update path` cross-reference (L-18).
2. **`README.md`** — in the Repository Conventions bullet, replace the clause that currently
   begins `Images are built by the per-add-on workflows` (naming `build-<addon>.yml` and a
   `push` to `main` touching `<addon>/**`) with the single-`build.yml` statement, and name the
   narrower manifest-path trigger explicitly — the replacement must contain the literal
   `**/config.*`, which is what G3-3 asserts positively. Keep the rest of the bullet (the
   ghcr-404 warning, the pre-push hook, `LOCAL_BUILD_ADDONS`) intact. Note the gate shape:
   G3-3 negative-greps only that one long live-claim clause, never the bare noun phrase
   "per-add-on workflows" — a historically correct sentence is free to use it (for example
   "the nine per-add-on workflows were replaced by `build.yml`"), here and in any file.
3. **`docs/DEVELOPMENT.md`** — three edits. (a) In `## GitHub Actions Reusable Build Workflows`,
   replace the "Seven per-addon callers (`build-<addon>.yml`) only set addon-name, display name,
   description, the arch matrix, and HA webhook secrets" sentence with the derived-metadata
   description: one `build.yml` caller whose `detect` job reads all four from the add-on's
   manifests. (b) Add a row to the Job Timeouts table for the new job — `| \`build.yml\` |
   \`detect\` | 5 | ... |` — and note in that section that a reusable-workflow call job cannot
   declare `timeout-minutes`, so `build.yml`'s build job inherits the template's 45. (c) In
   `### Trigger Pitfalls`, remove the claim that a per-addon `tags:` pattern can trigger a build
   (D-01) and replace the "Manual `workflow_dispatch` on a representative caller" advice with a
   dispatch of `build.yml` scoped by the `addons` input. Leave the `3925f58` observation and the
   historical run id `32633538391` alone — they are records of past events and remain true.
4. **`docs/WEBHOOK_SETUP.md`** — replace "seven per-addon `build-<addon>.yml` callers, each
   invoking the reusable `_build-template.yml`" with the one-`build.yml`-caller statement. The
   two-events-per-leg behaviour is unchanged.
5. **`docs/UPDATE_VERSION.md`** — the code-block comment "Build workflow fires on the tag push (or
   on push to main with files in coding-assistants/**)" is now false in both halves. Replace it
   with the manifest-path trigger, and note that pushing the tag builds nothing.
6. **`internal/check-version-tags.sh` header (lines 2-7)** — this is the rationale correction
   D-01 requires. The corrected header must say: this hook guards the release-tag bookkeeping for
   version bumps reaching `main`; the ghcr-404 failure mode it exists to prevent is UNCHANGED (a
   pulled add-on whose `config.yaml` advertises a version whose image was never published); but
   the image is published by the bump commit's `build.yml` run or by
   `internal/dispatch-builds.sh`, NOT by the tag — tags no longer trigger any workflow. Do not
   reuse the phrasing "every workflow also triggers on" (gate G3-6 negative-greps it). Change
   NOTHING below the header: the `LOCAL_BUILD_ADDONS` array, its comment block and every function
   stay as they are, and G3-6 pins the hash of the file's non-comment lines to prove it. Two
   mechanical constraints on that hash, so a correct rewrite cannot trip it: `grep -v '^#'`
   excludes only comments that start in column 1, so **every rewritten header line must begin at
   column 1** — an indented comment would be counted as code and change the hash. It also
   excludes line 1, the shebang, which is instead covered by `bash -n` and `shellcheck` in the
   same gate plus `check-shebang-scripts-are-executable` in pre-commit; do not touch it.
7. **`internal/update-version.py` — TWO prose blocks, both written by rll one wave ago.** Read
   them before editing; the pre-batch wording this plan was drafted against is gone.
   (a) The **tag-push success output**: rll made it state that a build runs only if that add-on's
   own caller has an active `tags:` trigger, and that six of nine have it commented out. After
   Task 2 neither the caller nor the trigger exists, so the whole conditional is false. Replace
   it with the truth — the tag is a release marker; the image is published by the bump commit's
   `build.yml` run, by `internal/dispatch-builds.sh`, or by an explicit `workflow_dispatch` — and
   keep pointing at `.github/RELEASE.md`. The f-string `Pushed tag: {tag}` must survive verbatim
   (rll's `GATE-T2-A` counts it).
   (b) The **`create_and_push_tag` docstring**: rll rewrote it to name the `paths:` and `tags:`
   triggers separately per caller. Keep both literals `paths:` and `tags:` and the closing
   `Returns True on success.` line (rll's `GATE-T2-B` greps all four), and keep the file's total
   `RELEASE.md` count at two or more (`GATE-T2-A`) — but correct what they now describe: there is
   one `build.yml`, its `paths:` trigger is on the manifest globs rather than an add-on directory,
   and there is NO `tags:` trigger anywhere, so pushing this tag creates no workflow run for any
   add-on. Say what the tag IS: the release marker `internal/check-version-tags.sh` enforces and
   that `<addon>/v<version>` release notes hang off.
   Both blocks are string literals only: no statement added or removed beyond splitting or
   joining print calls, no signature, argparse or import change. Apply the prose convention below
   — rll's docstring cites the deleted caller by full path, and that reference must not survive.
   G3-7 holds this file by scoped invariants (argparse surface, every `^def ` signature line,
   `create_and_push_tag`'s signature, `py_compile`, both `--no-tag` orderings on a clean tree),
   NOT by an AST hash; `<sibling_supersession>` records why a hash is unachievable here.
8. **`.github/workflows/_build-template.yml` header line 3** — "invoked by build-<addon>.yml with
   the per-addon inputs below" becomes "invoked by build.yml, once per add-on and arch leg, with
   inputs derived from the add-on's config.yaml / build.yaml". Header comment ONLY: L-1 forbids any
   change to the `workflow_call` block, and G3-9 pins its parsed shape.

9. **`docs/AUTO_UPDATE_GUIDE.md` — the second sibling-written site (D-06).** rlm rewrote this
   whole file one wave ago against the per-add-on world. Four passages are falsified by Task 2 and
   are the only ones to change; leave every other correction rlm made alone.
   (a) The `GITHUB_TOKEN` section: it says the bot push creates no runs so that add-on's own
   caller's `paths:` filter never fires, and that the script issues one dispatch of that caller
   per changed add-on directory. Both halves move to `build.yml`: it is `build.yml`'s `paths:`
   filter that does not fire for a bot push, and the script issues exactly ONE
   `gh workflow run build.yml --ref <ref>` carrying every changed add-on as a comma list. Keep
   the `workflow_dispatch`-is-the-exception point, the docs.github.com link, `actions: write` and
   the `.github/RELEASE.md` cross-reference (L-18).
   (b) The error-handling section's dispatch semantics: the skip reason is no longer a missing
   build workflow file but a path with no `config.yaml` + `build.yaml` + `Dockerfile` triple. Keep
   "warns without failing" and "a failed dispatch fails the run" exactly as rlm scoped them.
   (c) The "adding a new add-on" steps: rlm's closing step says the add-on also needs its own
   build workflow file or the dispatch skips it. That requirement is GONE and its replacement is
   strictly simpler — the manifest triple is all that is needed and `build.yml` picks the add-on
   up with no workflow edit at all. Say so; it is the item's payoff, visible right where a reader
   adds an add-on.
   (d) The webhook paragraph: "the per-add-on build workflows" send the HA notification via
   `_build-template.yml`. It is now `build.yml` calling that template. Keep the `notify-ha.sh`
   reference and the `docs/WEBHOOK_SETUP.md` pointer (L-18).
   Anchor every edit on phrase text, not a line number, and if rlm's phrasing differs from the
   descriptions above, edit whatever now makes each claim. Respect rlm's 120-column limit
   (its `L1` gate) and its emoji-prefixed heading style.

Two rules that keep the gates satisfiable, both learned from earlier plans in this repository:

- When prose needs to refer to the removed callers historically, write `build-<addon>.yml` WITHOUT
  the `.github/workflows/` prefix, and never write a `gh workflow run` of a per-add-on workflow
  even historically — G3-8 negative-greps the full-path form repo-wide and the per-add-on dispatch
  command form in the two files rlm wrote, precisely so that history stays writable while a live
  path reference to a deleted file, or a live instruction to dispatch one, cannot survive.
- Run `pre-commit run --files` on every touched path before declaring done: prettier rewraps
  Markdown at 120 columns and markdownlint enforces it, so hand-wrapped prose will otherwise fail
  the commit rather than this task's own gates.
  </action>
  <verify>
    <automated>f=.github/RELEASE.md; [ "$(grep -c '| active *|' "$f")" -eq 0 ] && [ "$(grep -c 'tag-trigger temporarily disabled' "$f")" -eq 0 ] && [ "$(grep -c 'Re-enabling a tag trigger' "$f")" -eq 0 ] && [ "$(grep -c '^### Tags do not trigger builds$' "$f")" -ge 1 ] && [ "$(grep -cF 'build.yml' "$f")" -ge 1 ] && [ "$(grep -c 'Supervisor image source' "$f")" -ge 1 ] && grep -q '287c79f' "$f" && grep -q '60e7835' "$f" && echo GATE-G3-1-PASS</automated>
    <automated>f=.github/RELEASE.md; a=$(sed -n '/^## Auto-update path$/,$p' "$f"); [ "$(printf '%s' "$a" | wc -c)" -ge 200 ] && [ "$(printf '%s\n' "$a" | grep -cF 'gh workflow run build-')" -eq 0 ] && [ "$(printf '%s\n' "$a" | grep -cF 'build.yml')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF 'internal/dispatch-builds.sh')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF 'GITHUB_TOKEN')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF 'workflow_dispatch')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF 'docs.github.com/actions/using-workflows/triggering-a-workflow')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF 'docs/AUTO_UPDATE_GUIDE.md')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF 'Auto Update')" -ge 1 ] && [ "$(printf '%s\n' "$a" | grep -cF -- '--no-tag')" -ge 1 ] && echo GATE-G3-1b-PASS</automated>
    <automated>f=.github/RELEASE.md; [ "$(grep -cF '15 of the 40' "$f")" -ge 1 ] && [ "$(grep -cF 'terraform-bridge/v0.2.0' "$f")" -ge 1 ] && [ "$(grep -cF 'git show' "$f")" -ge 1 ] && [ "$(grep -cF 'base-image-update' "$f")" -ge 1 ] && [ "$(grep -c '^### Why the split$' "$f")" -eq 1 ] && [ "$(grep -cF 'all seven' "$f")" -eq 1 ] && [ "$(grep -cF 'canonical image for the tag' "$f")" -eq 0 ] && o=$(sed -n '/^### What this means operationally$/,/^## Standard release flow$/p' "$f") && [ "$(printf '%s' "$o" | wc -c)" -ge 200 ] && [ "$(printf '%s\n' "$o" | grep -cF 'human')" -ge 1 ] && [ "$(printf '%s\n' "$o" | grep -cF 'GITHUB_TOKEN')" -ge 1 ] && [ "$(printf '%s\n' "$o" | grep -cF 'Auto-update path')" -ge 1 ] && echo GATE-G3-1c-PASS</automated>
    <automated>f=.github/RELEASE.md; for a in authentik coding-assistants gatus iac-runner markdown-renderer meridian network-tools phone-logger terraform-bridge; do grep -q "| $a " "$f" || { echo "MISSING ROW $a"; exit 1; }; done; [ "$(grep -c 'local build' "$f")" -ge 2 ] && echo GATE-G3-2-PASS</automated>
    <automated>[ "$(grep -cF 'Images are built by the per-add-on workflows' README.md)" -eq 0 ] && [ "$(grep -cF '`build.yml`' README.md)" -ge 1 ] && [ "$(grep -cF '**/config.*' README.md)" -ge 1 ] && [ "$(grep -cF 'gh workflow run build-' README.md)" -eq 0 ] && echo GATE-G3-3-PASS</automated>
    <automated>f=docs/DEVELOPMENT.md; [ "$(grep -c 'per-addon callers' "$f")" -eq 0 ] && [ "$(grep -c 'per-addon .tags:. pattern' "$f")" -eq 0 ] && [ "$(grep -cF '| `build.yml`' "$f")" -ge 1 ] && grep -q '32633538391' "$f" && echo GATE-G3-4-PASS</automated>
    <automated>[ "$(grep -c 'seven per-addon' docs/WEBHOOK_SETUP.md)" -eq 0 ] && [ "$(grep -cF 'build.yml' docs/WEBHOOK_SETUP.md)" -ge 1 ] && [ "$(grep -c 'fires on the tag push' docs/UPDATE_VERSION.md)" -eq 0 ] && [ "$(grep -cF 'build.yml' docs/UPDATE_VERSION.md)" -ge 1 ] && echo GATE-G3-5-PASS</automated>
    <automated>f=internal/check-version-tags.sh; [ "$(grep -c 'every workflow also triggers on' "$f")" -eq 0 ] && grep -q 'build\.yml' "$f" && grep -q 'ghcr' "$f" && [ "$(grep -v '^#' "$f" | sha256sum | cut -d' ' -f1)" = "5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249" ] && bash -n "$f" && shellcheck -e SC1091 -e SC2034 "$f" && echo GATE-G3-6-PASS</automated>
    <automated>p=internal/update-version.py; [ "$(grep -c 'per-addon build workflows' "$p")" -eq 0 ] && [ "$(grep -cF '.github/workflows/build-' "$p")" -eq 0 ] && [ "$(grep -c 'Pushed tag: {tag}' "$p")" -eq 1 ] && [ "$(grep -c 'RELEASE\.md' "$p")" -ge 2 ] && [ "$(grep -c 'Returns True on success' "$p")" -eq 1 ] && [ "$(grep -c 'will trigger' "$p")" -eq 0 ] && [ "$(grep -c 'tag is required' "$p")" -eq 0 ] && d=$(awk '/^def create_and_push_tag/{f=1} f{print; if ($0=="    \"\"\"") exit}' "$p") && printf '%s\n' "$d" | grep -q 'paths:' && printf '%s\n' "$d" | grep -q 'tags:' && printf '%s\n' "$d" | grep -q 'RELEASE\.md' && echo GATE-G3-7a-PASS</automated>
    <automated>p=internal/update-version.py; grep -q '^def create_and_push_tag(version: str, addon_name: str, push: bool = True, dry_run: bool = False) -> bool:$' "$p" && [ "$(grep '^def ' "$p" | sha256sum | cut -d' ' -f1)" = "1aca4cb3b74201a73fc290e606db9f63c2626c30c2ba80ce1fb5b1254b66dc8c" ] && [ "$(grep -c "add_argument('--no-tag'" "$p")" -eq 1 ] && [ "$(grep -c "add_argument('--no-push'" "$p")" -eq 1 ] && [ "$(grep -c "add_argument('--dry-run'" "$p")" -eq 1 ] && [ "$(grep -c "add_argument('--check-release'" "$p")" -eq 1 ] && echo GATE-G3-7b-PASS</automated>
    <automated>python3 -m py_compile internal/update-version.py && [ "$(python3 internal/update-version.py --help | grep -c -- '--no-tag')" -ge 1 ] && python3 internal/update-version.py --no-tag --dry-run meridian 1.99.0 >/dev/null && python3 internal/update-version.py meridian 1.99.0 --no-tag --dry-run >/dev/null && [ -z "$(git status --porcelain -- meridian)" ] && echo GATE-G3-7c-PASS</automated>
    <automated>[ "$(grep -rnIF '.github/workflows/build-' --exclude-dir=.planning --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir='.venv*' . | wc -l)" -eq 0 ] && [ "$(grep -rnIF 'gh workflow run build-' --exclude-dir=.planning --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir='.venv*' . | wc -l)" -eq 0 ] && echo GATE-G3-8-PASS</automated>
    <automated>t=.github/workflows/_build-template.yml; [ "$(grep -c 'invoked by build-<addon>.yml' "$t")" -eq 0 ] && grep -q 'HEAD_COMMIT_TIMESTAMP' "$t" && python3 -c "
import yaml
d = yaml.safe_load(open('$t'))
wc = d.get('on', d.get(True))['workflow_call']
assert {k: (v.get('required'), v.get('type'), v.get('default')) for k, v in wc['inputs'].items()} == {
    'addon-name': (True, 'string', None),
    'addon-display-name': (True, 'string', None),
    'addon-description': (True, 'string', None),
    'archs': (False, 'string', '[\"amd64\", \"aarch64\"]'),
    'notify-ha': (False, 'boolean', True)}, wc['inputs']
assert sorted(wc['secrets']) == ['CF_ACCESS_CLIENT_ID', 'CF_ACCESS_CLIENT_SECRET', 'HA_BASE_URL', 'HA_WEBHOOK_ID'], sorted(wc['secrets'])
print('GATE-G3-9-PASS')"</automated>
    <automated>g=docs/AUTO_UPDATE_GUIDE.md; [ "$(grep -cF 'gh workflow run build-' "$g")" -eq 0 ] && [ "$(grep -cF '.github/workflows/build-' "$g")" -eq 0 ] && [ "$(grep -cF 'build.yml' "$g")" -ge 1 ] && [ "$(grep -cF 'internal/dispatch-builds.sh' "$g")" -ge 1 ] && [ "$(grep -cF 'GITHUB_TOKEN' "$g")" -ge 1 ] && [ "$(grep -cF 'workflow_dispatch' "$g")" -ge 1 ] && [ "$(grep -cF 'actions: write' "$g")" -ge 1 ] && [ "$(grep -cF 'notify-ha.sh' "$g")" -ge 1 ] && [ "$(grep -cF -- '--no-tag' "$g")" -ge 1 ] && [ "$(grep -cF 'RELEASE.md' "$g")" -ge 1 ] && [ "$(grep -cF 'docs.github.com/actions/using-workflows/triggering-a-workflow' "$g")" -ge 1 ] && [ "$(grep -cF 'ERRORS=1' "$g")" -ge 1 ] && [ "$(grep -cF '### 1. **Daily Check** (6:00 UTC)' "$g")" -eq 1 ] && [ "$(awk 'length($0) > 120 && $0 !~ /^\|/ {c++} END {print c+0}' "$g")" -eq 0 ] && echo GATE-G3-10-PASS</automated>
    <automated>pre-commit run --files .github/RELEASE.md README.md docs/DEVELOPMENT.md docs/WEBHOOK_SETUP.md docs/UPDATE_VERSION.md docs/AUTO_UPDATE_GUIDE.md internal/check-version-tags.sh internal/update-version.py .github/workflows/_build-template.yml</automated>
  </verify>
  <done>
Every criterion below is a PROPERTY of the finished tree, not a delta from a number measured at
`5b41d49`. Siblings rll and rlm rewrite three of these files before this task runs, so the
`<precondition>` measures the starting counts and the SUMMARY records them; nothing here asserts
"unchanged from baseline" for a file a sibling can reach.

`.github/RELEASE.md`: zero `| active |` trigger-status rows, zero
`tag-trigger temporarily disabled` mentions, no `Re-enabling a tag trigger` section, exactly one
`### Tags do not trigger builds` heading, at least one `build.yml` mention, all nine add-on rows
present with both `local build` values, both commit citations `287c79f` / `60e7835` retained, and
`### Why the split` still present with its one `all seven` historical clause. `## Auto-update path`
describes ONE `build.yml` dispatch carrying a list, contains no per-add-on dispatch command and no
deleted-caller path, and still carries every rlm literal L-18 pins (G3-1, G3-1b, G3-1c).

`docs/AUTO_UPDATE_GUIDE.md`: names `build.yml`, contains no per-add-on dispatch command and no
deleted-caller path, keeps every rlm literal L-18 pins, keeps the 6:00-UTC discovery heading
intact and stays inside 120 columns (G3-10).

`README.md`, `docs/DEVELOPMENT.md`, `docs/WEBHOOK_SETUP.md` and `docs/UPDATE_VERSION.md` — none of
which any sibling in this batch touches, so their baselines DO still hold — no longer carry the
falsified sentences (each baseline 1, each now 0) and each names `build.yml`; `README.md` also
names the manifest-path trigger literal `**/config.*` (baseline 0); `docs/DEVELOPMENT.md` has a
Job Timeouts row for `build.yml` (baseline 0) and still records the historical run `32633538391`.

`internal/check-version-tags.sh` — likewise untouched by every sibling (rll's L-11 excludes it
explicitly) — no longer claims a tag triggers a workflow, still names the ghcr failure mode, and
its non-comment lines hash to
`5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249`, unchanged from baseline, with
every rewritten header line starting at column 1 and the shebang untouched.

`internal/update-version.py` satisfies the scoped invariants that replace the abandoned AST pin:
`python3 -m py_compile` clean; every `^def ` signature line hashing to
`1aca4cb3b74201a73fc290e606db9f63c2626c30c2ba80ce1fb5b1254b66dc8c`; `create_and_push_tag`'s
signature line byte-exact; exactly one `add_argument` for each of `--no-tag`, `--no-push`,
`--dry-run`, `--check-release`; `--help` still listing `--no-tag`; both flag orderings running
`--dry-run` clean with `git status --porcelain -- meridian` empty afterwards. Its prose no longer
claims a tag triggers a build, carries no deleted-caller path, and preserves every rll literal —
`Pushed tag: {tag}`, two or more `RELEASE.md` references, `Returns True on success.`, and `paths:`
plus `tags:` inside the docstring (G3-7a/b/c).

`_build-template.yml`'s header no longer names the deleted callers while its `workflow_call`
inputs and secrets parse to exactly the pinned shape and rlj's `HEAD_COMMIT_TIMESTAMP` survives.

Repo-wide, outside `.planning/`: ZERO `.github/workflows/build-` path references and ZERO
`gh workflow run build-` instructions. `pre-commit run --files` passes on all nine paths.

The five sibling gates in `<sibling_supersession>` § 1 are expected red and recorded in the
SUMMARY with their disposition; every other sibling gate over these files is green.
  </done>
  <reversibility rating="reversible">Comment and documentation text only; two hash gates prove no executable line changed. A revert restores the previous prose.</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| GitHub event payload -> detect shell | `github.event.before`, `github.sha`, `github.event_name` and the `workflow_dispatch` `addons` input are attacker-influenceable strings that reach a shell and then a Python process |
| commit contents -> matrix values | add-on names come from paths in a commit; display name and description come from a file in the tree, and both land in a `with:` input and then in a docker `build-args` line |
| dispatch input -> build target set | `addons=` decides which add-ons build; empty means ALL |
| repository default token -> GHCR | unchanged from today: `packages: write` at the call site, `GITHUB_TOKEN` used by `docker/login-action` |

## STRIDE Threat Register

ASVS level 1; blocking threshold `high`. No `critical` or `high` threat is left undisposed.

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-rln-01 | Tampering | event data reaching the detect `run:` body | high | mitigate | L-6: NO GitHub expression is interpolated into the run body — `EVENT_NAME`, `BEFORE_SHA`, `HEAD_SHA` and `ADDONS_INPUT` arrive through the step's `env:`, so event-supplied text is an environment value, never text spliced into a command line. Gate G1-5 asserts the extracted body contains no expression delimiters at all, which makes the property machine-checked rather than reviewed. |
| T-rln-02 | Tampering | candidate name -> filesystem paths and matrix values | high | mitigate | Three independent barriers: (a) in push mode `awk -F/ '{print $1}'` keeps only the first path segment, so a derived candidate cannot contain `/` at all; (b) a name-shape gate `^[a-z0-9][a-z0-9._-]*$` rejects traversal- and metacharacter-shaped names (proved by G1-4e, which feeds `../../etc` and `.planning` and gets `[]`); (c) the authoritative gate — the `config.yaml`/`build.yaml`/`Dockerfile` triple must exist as regular files, so a crafted name resolves to nothing. Barrier (a) is absent in dispatch mode, which is why (b) and (c) are not optional. |
| T-rln-03 | Elevation of Privilege | one workflow now able to build every add-on | medium | accept | The dispatch surface widens from "one add-on per workflow" to "any subset, or all". The actor set does not change: creating a `workflow_dispatch` still needs `actions: write` on the repository, which only the two bump jobs (sibling rlj) and repository writers hold. The worst outcome is a rebuild of already-published images from the same source, which is the same authority a writer has today by pushing nine dispatches. Accepted. |
| T-rln-04 | Denial of Service | an empty `addons` value fanning out to all nine add-ons | medium | mitigate | L-12 plus gate G2-3d: with every candidate skipped the script performs ZERO `gh` invocations rather than one with an empty list. Empty-means-all remains reachable only by a deliberate human dispatch. |
| T-rln-05 | Denial of Service | the widened `paths:` globs firing on non-add-on files | low | accept | `.planning/config.json`, `terraform-provider-homeassistant/build.yaml` and `tools/test-addon/*` match the globs and cost a ~15 s `detect` job that derives `[]` and skips the build job (measured, G1-4e/S6). The narrower `*/config.*` form was considered and rejected: the item specifies the `**/` globs, and the derivation already rejects the extra matches structurally. |
| T-rln-06 | Repudiation | which add-on/arch a run built | low | mitigate | `name: ${{ matrix.addon }} (${{ matrix.arch }})` puts the add-on and arch in the job title, and the detect step emits a `::notice::` naming the derived set and leg count — both are what the post-merge proof reads. |
| T-rln-07 | Information Disclosure | dispatch failure output | low | mitigate | Inherited from rlj and unchanged: the script never echoes `$GH_TOKEN` / `$GITHUB_TOKEN`, passes `gh`'s stderr through unmodified, and its `ERROR:` line names only the workflow, the ref and the add-on list. |
| T-rln-08 | Spoofing | a build published from an unintended ref | low | mitigate | Unchanged from rlj: the ref is measured (`REF`, else `GITHUB_REF_NAME`, else `git rev-parse --abbrev-ref HEAD`) and a detached HEAD is a hard exit 1, never a silent fallback to `main`. |
| T-rln-SC | Tampering | npm/pip/cargo installs | n/a | accept | This item introduces ZERO new package-manager installs and zero new dependencies. `git`, `awk`, `sort`, `jq`, `python3` + PyYAML and `gh` are all pre-installed on `ubuntu-latest`; PyYAML and jq are also present locally (measured). No `Package Legitimacy Audit` is required and no legitimacy checkpoint is inserted. |
</threat_model>

<hook_dispositions>
- **api-coverage** (`workflow.api_coverage_gate`): the detector resolves a phase scope
  (`PHASE_DIR/*-PLAN.md` plus the ROADMAP phase section). A quick-batch item has neither, so the
  probe yields `skipped`, not a verdict; per the hook the checkpoint is skipped and no
  `COVERAGE.md` is fabricated. For the record, the external surface touched is one GitHub Actions
  API verb — creating a `workflow_dispatch` event via `gh workflow run` — inherited from sibling
  rlj and already integrated. No other endpoint is in scope.
- **assumption-delta** (`workflow.assumption_delta`): probe skipped (no ROADMAP phase section).
  The signal is real and recorded voluntarily in `<assumption_delta_decision>` below. Advisory,
  non-blocking.
- **schema-gate** (`workflow.schema_push_detection`): no ORM/schema-relevant paths (no Payload,
  Prisma, Drizzle, Supabase or TypeORM files) in scope. Skipped silently — no `[BLOCKING]` push
  task injected.
- **security** (`workflow.security_enforcement`): `<threat_model>` present, ASVS level 1, blocking
  threshold `high`. Both `high` threats (T-rln-01, T-rln-02) are disposed `mitigate` with
  gate-backed mitigations (G1-5, G1-4e).
</hook_dispositions>

<assumption_delta_decision>
Sibling rlj recorded a `pluralization` signal and deliberately chose `add-alongside`, naming this
item as what would force the promote. This item is that promote, so the decision is recorded as
resolved rather than re-opened:

- **Noun that is now primary:** *the set of (add-on, arch) legs to build*, computed from the
  add-ons' own manifests. The old primary — "the add-on whose `paths:` a push matched", one
  implicit source per workflow file — is demoted to one branch of the derivation (the push
  branch), alongside the explicit-list branch and the all-add-ons branch.
- **Decision: `promote`.** The nine per-add-on workflows are deleted rather than kept alongside
  `build.yml`, and the arch list, display name and description are promoted from hand-authored
  workflow inputs to derived manifest reads (D-04).
- **The invariant test the hook suggests, accepted and implemented:** G2-5 asserts that the
  add-on set `internal/dispatch-builds.sh` computes equals the set `build.yml` computes — two
  independent implementations of the same identity. It goes red the moment a future change
  re-introduces a per-add-on special case in either place.
</assumption_delta_decision>

<source_coverage_audit>
Every requirement in the item description maps to a task and a gate. Nothing is deferred,
simplified or staged as a "v1".

| # | Source requirement (from the item text) | Req id | Task | Gate |
|---|---|---|---|---|
| a-1 | NEW `.github/workflows/build.yml`, one builder for all add-ons | a | T1 | GATE-G1-1 |
| a-2 | trigger on push to main with `**/config.*`, `**/build.*`, `**/Dockerfile` | a | T2 | GATE-G2-2 |
| a-3 | `detect-changed-addons` job deriving the list from `git diff` and emitting a JSON array via `jq -R -s -c` | a | T1 | GATE-G1-4d, GATE-G1-4c |
| a-4 | derivation = changed manifest paths, then `awk -F/ 'NF {print $1}' \| sort -u` | a | T1 | GATE-G1-4d (independently recomputed from the same commit) |
| a-5 | build job matrix over the detected add-ons crossed with `[amd64, aarch64]`, SKIPPING undeclared legs | b | T1 | GATE-G1-4b (2 legs), GATE-G1-4a (1 leg), GATE-G1-4c (10 legs / 9 add-ons) |
| b-1 | arch list from `build.yaml` `build_from` keys, falling back to `config.yaml` `arch:`, NEVER a workflow input | b | T1 | GATE-G1-6 (no arch literal), GATE-G1-4a/b/c |
| b-2 | `addon-display-name` / `addon-description` read from `config.yaml`, not passed as hand-authored inputs | b | T1 | GATE-G1-4a (byte-equal to config.yaml), GATE-G1-6 (no name/description literal) |
| c-1 | keep `_build-template.yml` as the `workflow_call` target; only the nine callers disappear | c | T1, T2, T3 | GATE-G1-3, GATE-G2-1, GATE-G3-9 |
| c-2 | delete the nine `build-*.yml` | c | T2 | GATE-G2-1 |
| c-3 | `workflow_dispatch` with an `addons` input, empty means all | c | T1 | GATE-G1-1, GATE-G1-4c |
| c-4 | THEN update `internal/dispatch-builds.sh` to one dispatch with a list | c | T2 | GATE-G2-3b (exactly one `gh` call, exact argv) |
| c-5 | `nobuild` commit-message escape hatch | c | T1 | GATE-G1-8 |
| c-6 | `fetch-depth: 0` | c | T1 | GATE-G1-8 |
| d-1 | DECIDE EXPLICITLY: what happens to the three active `tags:` triggers | d | — | D-01, recorded in `<decisions>`; enforced by GATE-G2-2 (no `tags:` key) |
| d-2 | DECIDE EXPLICITLY: what becomes of the `.github/RELEASE.md` tag-trigger table | d | T3 | D-02; GATE-G3-1, GATE-G3-2 |
| d-3 | say explicitly what tag removal means for `check-version-tags.sh`'s rationale | d | T3 | D-01 closing paragraph; GATE-G3-6 |
| e-1 | actionlint under BOTH the pre-commit-pinned v1.7.3 and the latest release | e | T1, T2 | GATE-G1-7, GATE-G2-7 |
| e-2 | yamllint | e | T1, T2 | GATE-G1-7, GATE-G2-7 |
| e-3 | validate before `main` — test branch, `act`, or a `workflow_dispatch`-only first landing | e | T1 | D-03 (decided: dispatch-only first landing + offline extraction gates; `act` and test branch rejected with reasons); GATE-G1-1 + GATE-G1-2 enforce the ordering |
| e-4 | after merge, prove exactly ONE add-on builds and the right arch legs run | e | — | `<verification>` post-merge proof (cannot run pre-merge, D-03); stated as the item's one human-verified residual in `<success_criteria>`; offline equivalents GATE-G1-4a/b/d |
| f-1 | (beyond the declared file list) the prose the deletion falsifies | d | T3 | D-06; GATE-G3-3 … GATE-G3-9 |
| f-2 | (beyond the declared file list) the prose SIBLINGS write one and two waves earlier that Task 2 then falsifies — rlm's `## Auto-update path` and `docs/AUTO_UPDATE_GUIDE.md`, rll's two `internal/update-version.py` blocks | d | T3 | D-06; GATE-G3-1b, GATE-G3-7a, GATE-G3-8, GATE-G3-10 |

**Nothing missing. Nothing deferred. No phase split needed** — one new ~150-line workflow (already
written and measured in `<reference_implementation>`), three localised changes to an existing
~130-line script, and nine prose edits sit inside one agent's context.

**One addition beyond the item's declared `Files:` list**, flagged rather than smuggled: the eight
prose sites in D-06 (`README.md`, `docs/DEVELOPMENT.md`, `docs/WEBHOOK_SETUP.md`,
`docs/UPDATE_VERSION.md`, `docs/AUTO_UPDATE_GUIDE.md`, `internal/check-version-tags.sh`,
`internal/update-version.py`, `_build-template.yml`'s header). At least three carry live
`.github/workflows/build-` PATH references to files this item deletes, and two of the eight —
`docs/AUTO_UPDATE_GUIDE.md` and (inside `.github/RELEASE.md`) `## Auto-update path` — are written
by sibling rlm one wave before this item, so leaving them would ship a commit that deletes nine
files next to freshly written prose instructing the reader to dispatch them. Every edit is
comment/prose only; one hash gate and one scoped-invariant gate prove no executable line changes.
If the developer prefers them as a follow-up item, drop Task 3's items 2-9 and keep item 1
(`RELEASE.md`), which the item text mandates — but note that items 1's `## Auto-update path`
reconciliation and item 9 are then the deferred part, and gates G3-8 and G3-10 have to be dropped
with them.
</source_coverage_audit>

<gate_calibration>
Every gate in this plan was executed before the plan was finalised, against the real repository at
`5b41d49`, in both directions. This closes both failure modes named in the batch constraints.

**Run A — unmodified tree.** Every work-proving gate fails. Measured baselines, in gate order:

| Gate | Baseline observation |
|---|---|
| G1-1, G1-3, G1-4a-e, G1-5, G1-6, G1-8 | `.github/workflows/build.yml` does not exist — every one errors |
| G1-2 | `ls .github/workflows/build-*.yml \| wc -l` = **9** (this gate is an INVARIANT for T1: it must pass at baseline and fail the moment a caller is deleted early) |
| G2-1 | 9 callers present, `build.yml` absent → fails |
| G2-2 | no `build.yml` → fails |
| G2-3a-g, G2-5, G2-6 | `internal/dispatch-builds.sh` does not exist yet (sibling rlj creates it) → fail |
| G2-4 | rlj's own gate; passes only after rlj lands, and must keep passing here |
| G3-1 | `\| active \|` rows = **9**; `tag-trigger temporarily disabled` = **2**; `Re-enabling a tag trigger` = **1**; `### Tags do not trigger builds` = **0**; literal `build.yml` in RELEASE.md = **0** |
| G3-3 | `Images are built by the per-add-on workflows` in README.md = **1**; `**/config.*` = **0**; `gh workflow run build-` = **0**. The gate deliberately negative-greps only that whole live-claim clause, never the bare noun phrase `per-add-on workflows`, which a historically correct replacement sentence would legitimately use |
| G3-4 | `per-addon callers` = **1**; `per-addon \`tags:\` pattern` = **1**; `\| \`build.yml\`` = **0** |
| G3-5 | `seven per-addon` = **1**; `fires on the tag push` = **1** |
| G3-6 | `every workflow also triggers on` = **1**; code-only sha256 = `5f310c2e…019249` |
| G3-7 | `per-addon build workflows` = **1**; `^def ` signature-line sha256 = `1aca4cb3…4b66dc8c`; the four `add_argument` counts = 1 each; `py_compile` rc=0. **The docstring-stripped AST hash originally pinned here (`883f0834…866e0b`) was measured correct at `5b41d49` and then ABANDONED** — rll splits one `print(f"…")` into three statements and this item rewrites them again, so the pin is invalidated by correct work in two independent places. See `<sibling_supersession>` |
| G3-1b, G3-1c | rlm has not landed at `5b41d49`: `## Auto-update path` is 263 bytes with no dispatch mention, and `15 of the 40` is absent (**0**) — both gates fail. They stay work-proving after rlm, because the sentences this item rewrites are the ones rlm writes |
| G3-7a/b/c | `G3-7a` is work-proving (the falsified prose is present at baseline). `G3-7b` and `G3-7c` are INVARIANTS in the same class as `G1-2`: both measured **rc=0 on the unmodified tree** and both must stay rc=0 — they go red the moment a `^def ` signature, the argparse surface, `--help`, or the two `--no-tag --dry-run` orderings move. That is the point: they hold the executable surface still while the prose changes |
| G3-10 | `docs/AUTO_UPDATE_GUIDE.md` at `5b41d49` contains **0** of `build.yml`, `internal/dispatch-builds.sh`, `GITHUB_TOKEN`, `workflow_dispatch`, `actions: write`, `notify-ha.sh`, `--no-tag`, `ERRORS=1`, `RELEASE.md` and the docs.github.com link (all measured) → fails. rlm plants all ten; this gate's remaining teeth after rlm are its two negative clauses, which rlm's own text trips |
| G3-8 | full-path `.github/workflows/build-` references outside `.planning/` = **3** at `5b41d49` (RELEASE.md:103, update-version.py:203, check-version-tags.sh:2), and **higher at wave 3**: rlm plants at least one more in `.github/RELEASE.md`'s `## Auto-update path` and at least one in `docs/AUTO_UPDATE_GUIDE.md`, and rll's docstring may add one. `gh workflow run build-` = **0** at `5b41d49`, ≥1 in each of those two files after rlm. The gate is `== 0`, so it is baseline-independent; Task 3's `<precondition>` measures the actual starting counts rather than trusting these |
| G3-9 | `invoked by build-<addon>.yml` = **1** |

**Run B — the spec implemented literally.** `<reference_implementation>` was written to a scratch
tree carrying symlinks to the nine real add-on directories, this repository's `.actionlint.yml` and
`.yamllint.yml`, a copy of `_build-template.yml` and copies of the nine callers. Measured results:

- actionlint **v1.7.3** and actionlint **v1.7.12** (the current `latest`): both clean, rc=0, on
  both the dispatch-only (T1) and the full-trigger (T2) variants.
- `yamllint -c .yamllint.yml`: clean.
- G1-1, G1-2, G1-3, G1-5, G1-6: all print PASS.
- The detect body EXTRACTED FROM THE FILE with PyYAML, executed locally with a synthetic
  `GITHUB_OUTPUT`, produced: `addons=["meridian"]` with 1 amd64 leg and the config.yaml display
  name and description verbatim; `coding-assistants` with legs `amd64` then `aarch64`; empty input
  → the nine add-ons and **10** legs; `7cc82f5` (parent..commit) → `["gatus"]`; `8c6645f`
  (`.planning`-only) → `[]` with `{"include":[]}`; unresolvable and all-zero `BEFORE_SHA` → the
  `HEAD^` fallback, still `["gatus"]`; `tools,nonexistent-addon,../../etc,.planning` → `[]`, rc=0.
- G2-2 on the full-trigger variant: PASS.

**Failability checks — three gates were deliberately broken to prove they reject wrong work:**

| Gate | Injected defect | Result |
|---|---|---|
| G1-1 | the T2 (push-trigger) file handed to the T1 gate | `AssertionError` — proves it enforces the L-14 ordering, not just parseability |
| G1-3 | `addon-display-name` misspelt as `addon-display-nam` | actionlint v1.7.12 reports both `[workflow-call]` errors (missing required input, undefined input) — the actionlint gate validates the call site, it is not a syntax check |
| G1-6 | `addon-display-name: "Meridian Claude Max Proxy"` hardcoded | `AssertionError: [('meridian', 'Meridian Claude Max Proxy')]` — the anti-duplication gate has teeth |
| — | `timeout-minutes: 45` added to the `uses:` build job | actionlint errors; this is why L-9 forbids it, and it is a measurement rather than a belief |

**Three defects this calibration caught and removed from the plan, stated so they are not
reintroduced:**

1. `yaml.safe_load` parses the workflow key `on:` as the **boolean `True`** (YAML 1.1). Every
   draft gate that wrote `d['on']` raised `KeyError` on a perfectly correct file — a gate that
   rejects correct work. All of them now read `d.get('on', d.get(True))`.
2. A repo-wide `grep -c 'build-<addon>.yml' == 0` gate would have rejected correct historical
   prose (a sentence such as "the nine `build-<addon>.yml` callers were replaced") — failure mode
   2 exactly. It is replaced by G3-8, which greps the full-PATH form `.github/workflows/build-`
   only, paired with an explicit prose convention in Task 3 so history stays writable.
3. G1-6's forbidden-literal list is COMPUTED from `*/config.yaml` at gate time rather than
   hardcoded, and it strips full-line comments first — Task 3's own action text names add-ons in
   prose, and Task 1 explicitly permits naming them in comments. A whole-file literal grep would
   have been self-invalidating. Task 1's action states the one remaining rule (no trailing
   comments on value lines) rather than leaving the executor to discover it via a failing gate.
4. The original G2-3e chained four assertions and then read `$?` after a `;`, so a failure in the
   first three would have left `$? == 1` and the gate would have printed PASS. It is split into
   three self-contained gates (G2-3e/f/g).
5. **Every absolute number above was measured at `5b41d49`, and this item runs at wave 3.** For
   any file a sibling touches first — `.github/RELEASE.md`, `docs/AUTO_UPDATE_GUIDE.md`,
   `internal/update-version.py`, `internal/dispatch-builds.sh`, `_build-template.yml` — those
   numbers are upper bounds, not facts. Two gates were rewritten because of it: G3-7 traded its
   whole-AST hash for scoped invariants, and G3-8 gained a measured `<precondition>` instead of a
   `<done>` claiming a baseline of 3. The files no sibling touches (`README.md`,
   `docs/DEVELOPMENT.md`, `docs/WEBHOOK_SETUP.md`, `docs/UPDATE_VERSION.md`,
   `internal/check-version-tags.sh`) keep their measured baselines, and `<done>` says which is
   which. The general rule: **prefer a property over a pinned number whenever a sibling can reach
   the file** — a hash that must be re-measured whenever a sibling moves is a standing liability.
</gate_calibration>

<verification>
Run after all three tasks, before handing the item back:

1. `pre-commit run --all-files` — the real actionlint v1.7.3 gate, the real markdownlint/prettier
   gate and the real `check-shebang-scripts-are-executable` gate in one command.
2. The latest actionlint over the whole repository, the way `lint.yml:60-66` does it: resolve the
   latest tag from the release API, download the `linux_amd64` tarball, run `actionlint` with no
   arguments from the repository root. Must be silent.
3. `yamllint -d relaxed` over the workflows, matching `lint.yml:81-84`.
4. `python3 -c "import yaml,sys;[yaml.safe_load(open(f)) for f in sys.argv[1:]]"
   .github/workflows/build.yml .github/workflows/_build-template.yml` — both still parse. Do NOT
   use `yq eval`; the local `yq` is python-yq and has no such subcommand.
5. `shellcheck internal/dispatch-builds.sh` with NO `-e` flags. Must emit nothing. Do not run the
   whole-repo form: it fails with 22 pre-existing findings unrelated to this change.
6. `git status --porcelain` — exactly the eleven modified/added paths in `files_modified` and the
   nine deletions in `files_deleted`. Nothing else.
7. Re-run every `GATE-*` in all three tasks once more, in order, after the last commit.

**MANDATORY POST-MERGE PROOF — a human step, and it cannot be run before the merge.** It is the
item's ONLY human-verified residual and no gate substitutes for it; it is therefore restated as a
`<success_criteria>` bullet so the item cannot be reported complete with the proof unrun. A new
workflow file is only dispatchable once it exists on the default branch (D-03), so this is the
first moment the dynamic matrix, the call-site permissions and the named secrets are evaluated by
GitHub at all. Do this BEFORE the next 06:00 UTC `auto-update` cron:

1. `gh workflow run build.yml -f addons=coding-assistants` then `gh run watch`. Expect exactly two
   build jobs, named `coding-assistants (amd64)` and `coding-assistants (aarch64)`, both green,
   and a `::notice::` from `detect` reporting `["coding-assistants"]` and 2 legs.
2. `gh workflow run build.yml -f addons=meridian` — expect exactly ONE leg, `meridian (amd64)`.
3. Then the item's own end-to-end proof: make one trivial `config.yaml` change (a subpatch bump on
   any single add-on), push it to `main`, and confirm ONE `Build Add-on` run whose matrix contains
   only that add-on, with one arch leg for every add-on except `coding-assistants`.
4. Confirm the published tag exists: `docker manifest inspect
   ghcr.io/akentner/homeassistant-addons/amd64-<slug>:<config version>` (sibling 260909-rlk's
   `internal/verify-image-availability.sh` automates exactly this check).

**If any step fails:** `git revert <task-2-commit>` restores all nine callers, removes the push
trigger and restores the per-add-on dispatch in one step, leaving `build.yml` in place and still
dispatchable for iteration. Do not attempt a forward fix on `main` while the builder is broken —
the nine callers are the working fallback and reverting to them costs one command.

Commit as **three** commits, in this order (L-14): the dispatch-only `build.yml`; the switch-over
(push trigger + nine deletions + script rewrite); the prose truth restoration. Suggested subjects:
`ci(260909-rln): add single build.yml builder, dispatch-only`,
`ci(260909-rln)!: replace nine per-add-on build workflows with build.yml`,
`docs(260909-rln): retire per-caller build/tag-trigger documentation`.

Deliberately NOT verified here: that a dispatched build publishes the advertised image tag
automatically on every bump — that belongs to sibling **260909-rlk** (STAGE 3), which builds
`internal/verify-image-availability.sh` for exactly that purpose and reads `config.yaml` `arch:`
as its active-arch list, the same manifest this item makes authoritative for the build matrix.
</verification>

<success_criteria>
- Every `GATE-*-PASS` marker in all three tasks prints, and every gate exits 0.
- `pre-commit run --all-files` passes, and the latest actionlint over the whole repository is
  silent.
- `ls .github/workflows/build-*.yml` lists nothing; `build.yml` and `_build-template.yml` both
  exist; `_build-template.yml`'s `workflow_call` inputs and secrets parse to the pinned shape.
- `build.yml` contains no `tags:` key and no add-on name, display name, description or arch-list
  literal on any non-comment line.
- The detect body extracted from `build.yml` reproduces all seven measured outcomes in
  `<gate_calibration>` Run B, and contains no GitHub expression delimiters.
- `internal/dispatch-builds.sh` performs exactly one `gh workflow run build.yml` per invocation,
  never one with an empty `addons` value, and preserves the `ADDON <name> <STATE>` contract
  including its `sort -u` ordering; rlj's derive-mode assertion still passes unchanged.
- The set the script classifies as dispatchable equals `build.yml`'s own empty-input `addons`
  output (G2-5) — the two implementations agree.
- Zero `.github/workflows/build-` path references and zero `gh workflow run build-` instructions
  outside `.planning/` — measured at task start rather than assumed, because rlm plants more of
  both one wave earlier. `internal/check-version-tags.sh` is hash-proven a comment-only change;
  `internal/update-version.py` is proven a prose-only change by scoped invariants instead of a
  hash (G3-7a/b/c), for the reason recorded in `<sibling_supersession>`.
- Three commits in the L-14 order, twenty paths total (11 modified/added, 9 deleted), no scope
  creep into rlj/rlk/rll/rlm territory: no `--no-tag`, no shared concurrency group, no
  `verify-image-availability` script, no change to either bump workflow, no change to
  `_build-template.yml` beyond its header comment.
- Every sibling gate over the files this item rewrites is green EXCEPT the five in
  `<sibling_supersession>` § 1, and the SUMMARY records those five with their disposition so a
  verifier re-running the batch's gate set does not read them as regressions.
- **The post-merge dispatch proof in `<verification>` is the item's one human-verified residual
  and NO gate covers it.** The item is not complete until it has been run: the two dispatches
  (`coding-assistants` → two green legs named per arch; `meridian` → exactly one) plus the
  single-add-on push proof. Until then the SUMMARY must carry it as an explicit outstanding
  obligation, with its deadline (before the next 06:00 UTC `auto-update` cron) and the revert
  command. It cannot be promoted to a `checkpoint:` task inside this item: a `workflow_dispatch`
  is only dispatchable once the file exists on the default branch (D-03), so the proof is
  unreachable from here — which is exactly why it is stated as a residual rather than gated.
</success_criteria>

<handoff_notes>
- **The post-merge dispatch proof in `<verification>` is not optional.** It is the only step that
  evaluates the dynamic matrix, the reusable-workflow call-site permissions and the named secrets
  on GitHub's side; `docs/DEVELOPMENT.md:96-99` records that these three fail only at run time and
  that actionlint passing does not prove them. Run it before the next 06:00 UTC cron.
- **For a verifier re-running the whole batch's gate set:** five sibling gates are expected red
  and each is dispositioned in `<sibling_supersession>` § 1 — rlj's `GATE-T1-5` dry-run-target
  clause, rlm's `D0-tree-is-six`, its `D0b`/`D1-says-six`/`D2-not-seven`/`X2-reenable-steps`
  region gates, and its `E2-scoped-to-six`. Everything else rlj, rll and rlm assert over these
  files is re-asserted here and must be green.
- **Two files in this item are prose a sibling wrote days-of-waves ago, not legacy text:**
  `docs/AUTO_UPDATE_GUIDE.md` and `.github/RELEASE.md`'s `## Auto-update path` (both rlm), plus
  `internal/update-version.py`'s two prose blocks (rll). If this item is ever re-planned or
  re-ordered, that coupling is the first thing to re-check: a baseline measured before those
  siblings land is not a baseline for this item.
- **Expect changed image descriptions.** Because `addon-description` now comes from `config.yaml`,
  `org.opencontainers.image.description` changes for 8 of 9 add-ons on their next build. That is
  the fix (D-04), not a regression.
- **For 260909-rlk (STAGE 3):** this item makes `build.yaml` `build_from` keys the authoritative
  arch source for the build matrix, with `config.yaml` `arch:` as the fallback. rlk reads
  `config.yaml` `arch:` as its active-arch list. They agree today (9 of 9 measured); if they ever
  diverge, `build_from` is what actually gets built and `arch:` is what the Supervisor offers —
  a divergence is a bug in the add-on, and a shared guard would be a good follow-up ticket.
- **For 260909-rll (STAGE 4):** a shared concurrency group must NOT be added to `build.yml`
  (D-07). `cancel-in-progress` on a job that pushes multi-arch images to GHCR can abort a
  half-published manifest.
- **Out of scope everywhere in this batch, still worth a ticket:** `lint.yml:91-95` ends in
  `|| echo "No shell scripts to check"`, which swallows shellcheck's exit code, so the repository's
  strictest shell gate is non-blocking and already carries 22 findings. And `tools/test-addon`
  carries a full add-on manifest triple one level too deep to ever be built — harmless today
  because the derivation only looks at first path segments, but it is a trap for anyone who later
  "fixes" the derivation to recurse.
</handoff_notes>

<output>
Create `.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-SUMMARY.md` when done.
</output>
