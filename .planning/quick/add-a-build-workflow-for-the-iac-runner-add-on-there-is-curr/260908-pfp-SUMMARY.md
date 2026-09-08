---
quick_id: "260908-pfp"
slug: "add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr"
date: "2026-09-08"
status: complete
subsystem: ci
tags: [github-actions, reusable-workflow, iac-runner, release-docs]

dependency_graph:
  requires:
    - ".github/workflows/_build-template.yml (workflow_call contract, unchanged)"
    - "iac-runner/config.yaml (arch, name, version)"
    - "iac-runner/build.yaml (build_from.amd64, args.VERSION)"
  provides:
    - "automated build path for iac-runner on push-to-main and on iac-runner/v* tag"
    - "ghcr.io/akentner/homeassistant-addons/amd64-iac_runner (once a trigger fires)"
    - "RELEASE.md tag-trigger table that is structurally true of every build-*.yml"
  affects:
    - "260908-pfo (its config.yaml bump will fire the new paths: trigger once this is on main)"
    - "260908-pfq (asks whether iac-runner should gain an image: key — still open, not decided here)"

tech_stack:
  added: []
  patterns:
    - "per-addon build caller delegating to _build-template.yml via jobs.<id>.uses"
    - "structural YAML assertions with python3 + PyYAML instead of yq (local yq is the jq wrapper)"

key_files:
  created:
    - ".github/workflows/build-iac-runner.yml"
  modified:
    - ".github/RELEASE.md"

decisions:
  - "No timeout-minutes on the caller job — actionlint v1.7.3 rejects the key on a reusable-workflow `uses:` job; the
    Phase-8 explicit-timeout rule is satisfied one level down by _build-template.yml's timeout-minutes: 45"
  - "Tag trigger shipped LIVE, not commented out — a dead trigger is the exact defect being fixed; terraform-bridge is
    the in-repo precedent for live-tag + no image: key"
  - "terraform-bridge table row added opportunistically — it closes a pre-existing documentation gap and the cross-check
    verifier cannot pass without it"

metrics:
  duration: "~10 min"
  completed: "2026-09-08"

actuals:
  tokens: 836
  tasks: 2
  commits: 2
plan_head_before: 457e67558308e7a8a287557d08fcc2ddb81a4562
---

# Quick 260908-pfp: Build Workflow for iac-runner — Summary

Added the missing `build-iac-runner.yml` caller (a structural clone of `build-terraform-bridge.yml` delegating to
`_build-template.yml`, with a **live** `iac-runner/v*` tag trigger) and corrected `.github/RELEASE.md`'s tag-trigger
table and prose so both are structurally true of every `build-*.yml` in the repo.

## What Changed

### Task 1 — `.github/workflows/build-iac-runner.yml` (new, 28 lines) — commit `6b7d53a`

`iac-runner` was the only add-on directory carrying `config.yaml` + `build.yaml` + `Dockerfile` with no matching
`build-<addon>.yml`, which is why the already-pushed `iac-runner/v0.2.1` tag fired nothing and no image was ever
published.

| Element             | Value                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `name`              | `Build IaC Runner`                                                                           |
| `on.push.branches`  | `[main]`                                                                                     |
| `on.push.paths`     | `["iac-runner/**"]`                                                                          |
| `on.push.tags`      | `["iac-runner/v*"]` — **live, not commented out**                                            |
| `workflow_dispatch` | present                                                                                      |
| `jobs.build.uses`   | `./.github/workflows/_build-template.yml`                                                    |
| `permissions`       | exactly `contents: read` + `packages: write` (T-pfp-01)                                      |
| `with.addon-name`   | `iac-runner` (also drives the underscore image slug `amd64-iac_runner`)                      |
| `with.archs`        | `'["amd64"]'` — equals `config.yaml` `arch`, and `build.yaml` has `build_from.amd64`         |
| `secrets:`          | all four of `HA_BASE_URL`, `HA_WEBHOOK_ID`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` |

No `timeout-minutes`, no re-derived image name/version/`BUILD_FROM`, no build steps, no leading file comment — all of
that stays in the template, matching all eight existing callers.

### Task 2 — `.github/RELEASE.md` (3 edits) — commit `af3dda2`

1. The bolded clause now reads `commented out for all add-ons except network-tools, terraform-bridge and iac-runner`
   (anchor substring preserved verbatim).
2. Two table rows added, alphabetically placed: `iac-runner` and `terraform-bridge`, both `active` / `**active**`.
3. The "built twice" sentence now names all three live-trigger add-ons instead of only `network-tools`, keeping the
   `build.yaml:args.VERSION` rationale and the "built twice" phrase intact.

Left untouched as instructed: the "Why the split" rationale and the "Re-enabling a tag trigger" steps.

## Verification Results

All local; nothing published.

| Check                                                              | Result                                                                 |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| `pre-commit run actionlint --all-files` (precondition, pre-change) | Passed (baseline green)                                                |
| `pre-commit run actionlint --all-files` (post-change)              | Passed                                                                 |
| `pre-commit run yamllint --files .../build-iac-runner.yml`         | Passed                                                                 |
| Task 1 structural verifier                                         | `OK: build-iac-runner.yml matches the caller contract`                 |
| Task 1 verifier **negative control** on `build-authentik.yml`      | `FAIL: on.push.tags lacks live authentik/v* glob` (exit 1)             |
| `pre-commit run prettier --files .github/RELEASE.md` (1st)         | Passed (no reformat needed — rows kept column alignment)               |
| `pre-commit run prettier --files .github/RELEASE.md` (2nd)         | Passed                                                                 |
| Task 2 table/prose cross-check                                     | `OK: RELEASE.md table and prose match every build-*.yml trigger state` |
| Exactly one row per `build-*.yml` (no more, no fewer)              | True — both sets are the same 9 add-ons                                |
| Longest line in the new workflow                                   | 111 chars (the `addon-description`), under the 120 budget              |
| `make validate-addons`                                             | All 9 add-ons passed, `iac-runner` included                            |

The negative control is the load-bearing result: the verifier reads the **parsed** `on.push.tags` key, so a
commented-out block counts as disabled. It reports OK on `build-terraform-bridge.yml` / the new file and fails on
`build-authentik.yml`, which proves "live" is measured rather than pattern-matched. A grep cannot make that distinction.

### Nothing published — explicitly confirmed

- No tag created or pushed. `iac-runner/v0.2.1` exists but points at the pre-existing `455920f`, not at either of this
  item's commits.
- No `gh workflow run`, no `workflow_dispatch`, no real build, no image write.

## Deviations from Plan

**1. [Path adaptation, not a rule deviation] Verification commands re-rooted to the worktree**

- **Found during:** Task 1 precondition
- **Issue:** The plan's verify blocks hardcode `cd /home/akentner/Projects/homeassistant-addons`, the main checkout.
  This item executed in the isolated worktree `.claude/worktrees/agent-a1268f7d03de24f94`, and the harness correctly
  refuses commands that redirect a worktree-isolated agent's git operations at the shared checkout.
- **Fix:** Ran every command from the worktree root instead. The two `python3` verifiers were written to the scratchpad
  byte-identical to the plan and invoked as `python3 <file> [addon]`, because the harness guard also rejects the
  `python3 - <<'PY'` heredoc form as unverifiable. Verifier logic is unchanged — no assertion was relaxed, added or
  reworded.
- **Files modified:** none (tooling only)

**2. [Observation, no action taken] Prettier did not need a reformat pass**

The plan predicted the first prettier invocation might exit 1 while auto-fixing table alignment, which is why the verify
block separates the two calls with `;`. In practice both invocations passed — the new rows were written pre-aligned to
the existing column widths. Not a defect; the two-call structure was still run as specified.

**3. [Environment note] Pre-commit hooks are not installed in this checkout**

`.git/hooks/pre-commit` does not exist (`make init` has not been run here), so both commits were made without hook
execution. `--no-verify` was **not** passed at any point. The hook set was instead run manually and green: `actionlint`,
`yamllint`, `prettier`, plus `make validate-addons`. Also noted: `markdownlint` is not a pre-commit hook id in this repo
(it runs only in the CI `lint.yml` workflow), so it could not be invoked locally.

**4. [Path adaptation] SUMMARY.md written inside the worktree**

The dispatch specified the main-checkout path `.planning/quick/<slug>/260908-pfp-SUMMARY.md`, but the harness refuses
writes from a worktree-isolated agent to the shared checkout. The file is therefore at the same relative path inside the
worktree and left uncommitted, per the "do not commit batch artifacts" constraint.

## Known Stubs

None. Both deliverables are complete — one YAML workflow caller and three Markdown edits. No placeholder values, no
TODO/FIXME, no unwired data path.

## Out of Scope — Left As-Is Deliberately

- **`.github/RELEASE.md:82`** still says "The seven callers carry the comment `# tag-trigger temporarily disabled`" when
  only six now do. This inaccuracy pre-dates the item and was explicitly excluded from scope; the Task 2 verifier does
  not anchor on it, so it fails no criterion. Worth a one-line fix in a later docs pass.
- **Whether `iac-runner/config.yaml` should gain an `image:` key.** It has none, so the HA Supervisor builds the add-on
  locally and never pulls the ghcr image. `terraform-bridge` is exact precedent for that same combination (no `image:`
  key, live tag trigger, published ghcr image), so this workflow is consistent with existing repo practice. The question
  belongs to sibling item `260908-pfq`.

## Follow-Up for the Developer (not part of this item)

Adding the workflow does **not** retroactively fire the existing `iac-runner/v0.2.1` tag — GitHub only evaluates
triggers for new ref pushes. To publish an image from that exact tag, either run the workflow via `workflow_dispatch`
(safest — no tag surgery, builds from the dispatched ref) or delete and re-push the tag. Both publish an image and are
therefore excluded from this item's verification.

Once this lands on `main`, sibling `260908-pfo`'s bump of `iac-runner/config.yaml` to `0.2.1-1` will fire the new
`paths:` trigger and publish `amd64-iac_runner:0.2.1-1` — the intended outcome. Note the STATE.md Phase-17 decision that
the `iac-runner/v0.2.0-0` tag is intentionally outstanding while the v1.2 Phase 8 Cloudflare prerequisite is open; this
item does not change that posture, since it pushes nothing.

## Threat Model Outcome

`T-pfp-01` (Elevation of Privilege) was the one `mitigate` disposition and is satisfied: the caller job's `permissions`
map is asserted to be exactly `{contents: read, packages: write}` — no `id-token`, no `contents: write`, no
`actions: write` — so a future widened scope fails Task 1's verifier. The `accept`/`transfer` items required no code:
the file defines no `run:` step, never echoes a secret, and references no third-party action (every `docker/*` and
`actions/*` pin stays in the untouched `_build-template.yml`). No packages were installed at any layer, so no
package-legitimacy gate applied.

## No Threat Flags

The change introduces no new network endpoint, auth path, file-access pattern or schema at a trust boundary beyond what
the threat register already covers.

## Commits

| Commit    | Type   | Message                                                                |
| --------- | ------ | ---------------------------------------------------------------------- |
| `6b7d53a` | `ci`   | `ci(iac-runner): add build workflow delegating to _build-template.yml` |
| `af3dda2` | `docs` | `docs(release): correct the tag-trigger status table and prose`        |

Measured: `git rev-list --count 457e6755..HEAD` = **2**. Working tree clean; no untracked leftovers.

Commit type `ci` for Task 1 follows in-repo precedent (`287c79f` `ci(build): …`, `60e7835` `ci(build-network-tools): …`)
rather than the generic `chore`; no commit-message format is enforced in this repo.

## Self-Check: PASSED

- `FOUND: .github/workflows/build-iac-runner.yml`
- `FOUND: .github/RELEASE.md` (modified, 6 insertions / 4 deletions)
- `FOUND: 6b7d53a` in `git log`
- `FOUND: af3dda2` in `git log`
- Both structural verifiers re-run against the committed state: both print `OK` and exit 0
