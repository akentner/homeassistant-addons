---
phase: quick-260909-rln
plan: 01
quick_id: 260909-rln
subsystem: ci
status: complete
tags: [ci, github-actions, workflow-consolidation, docs-truth]
requires:
  - 260909-rlj # internal/dispatch-builds.sh (rewritten here)
  - 260909-rll # internal/update-version.py prose (rewritten here)
  - 260909-rlm # RELEASE.md + AUTO_UPDATE_GUIDE.md prose (reconciled here)
  - 260909-wgm # non-sibling: made check-version-tags.sh advisory
  - 260910-0og # non-sibling: corrected both target docs, re-pinned this plan
provides:
  - single-builder # .github/workflows/build.yml derives everything from add-on manifests
  - batched-dispatch # one gh workflow run per invocation, addons= comma list
  - tag-trigger-removal-record # .github/RELEASE.md § Tags do not trigger builds
affects:
  - 260909-rlk # build_from is now the authoritative arch source for the matrix
  - 260909-rll # a shared concurrency group must NOT be added to build.yml (D-07)
tech-stack:
  added: []
  patterns:
    - "derive-not-declare: per-add-on CI values read from config.yaml/build.yaml at run time"
    - "env-indirection: no GitHub expression inside a run: body, so the body is locally executable"
    - "two-implementations-one-answer: G2-5 asserts the script and the workflow agree on the add-on set"
key-files:
  created:
    - .github/workflows/build.yml
  modified:
    - internal/dispatch-builds.sh
    - .github/RELEASE.md
    - README.md
    - docs/DEVELOPMENT.md
    - docs/WEBHOOK_SETUP.md
    - docs/UPDATE_VERSION.md
    - docs/AUTO_UPDATE_GUIDE.md
    - internal/check-version-tags.sh
    - internal/update-version.py
    - .github/workflows/_build-template.yml
  deleted:
    - .github/workflows/build-authentik.yml
    - .github/workflows/build-coding-assistants.yml
    - .github/workflows/build-gatus.yml
    - .github/workflows/build-iac-runner.yml
    - .github/workflows/build-markdown-renderer.yml
    - .github/workflows/build-meridian.yml
    - .github/workflows/build-network-tools.yml
    - .github/workflows/build-phone-logger.yml
    - .github/workflows/build-terraform-bridge.yml
decisions:
  - "D-01 honoured: no tags: trigger anywhere — a */v* pattern would produce green no-op runs"
  - "D-02 honoured: RELEASE.md's per-caller trigger table is now a two-column Supervisor image source table"
  - "D-03 honoured: Task 1 landed build.yml dispatch-only; Task 2 is the whole switch-over as ONE revertible commit"
  - "D-04 honoured: zero add-on names, display names, descriptions or arch literals in any non-comment line of build.yml"
  - "D-07 honoured: no concurrency: block in build.yml"
metrics:
  duration: ~95m # 3 tasks (~55m) + the post-execution coverage fix (~40m)
  completed: 2026-09-10
  tasks: 3
commits: 5
plan_head_before: 89e837548f95ab504abc230e398d5a84bda36f8b
actuals:
  tokens: 32466 # chars/4 over the realized diff (129,866 chars), the estimateTokens scale
  tasks: 3
  commits: 5 # MEASURED: git rev-list --count 89e8375..HEAD
post_execution_fixes:
  - "D-08: build.yml's paths: filter was extension-scoped and missed every source-only push (205 files). Fixed in 2a19285."
---

# Quick 260909-rln: One `build.yml` Replacing Nine Per-Add-on Callers Summary

Nine structurally identical `build-<addon>.yml` callers replaced by a single `build.yml` whose `detect`
job derives the add-on set, the arch legs, the display name and the description from each add-on's own
`config.yaml` / `build.yaml`, plus a batched `internal/dispatch-builds.sh` and nine reconciled prose sites.

## What Changed

**`.github/workflows/build.yml` (new, 180 lines).** One `detect` job plus one matrix `build` job calling
`_build-template.yml`. Three derivation branches: a push diff (`github.event.before`..`github.sha`,
filtered to the manifest paths, first path segment only), an explicit `addons` list, and
all-add-ons for an empty dispatch input. Every event value reaches the shell through the step's `env:`,
so the body contains no GitHub expression at all — which is both the injection mitigation (T-rln-01) and
what makes the body extractable and executable locally for the gates.

**The nine callers deleted** with `git rm`, staged as tracked deletions. `_build-template.yml` stays the
`workflow_call` target with its input/secret contract byte-unchanged (header comment only).

**`internal/dispatch-builds.sh` rewritten** into three passes: classify every candidate, run exactly one
`gh workflow run build.yml --ref <ref> -f addons=<sorted comma list>`, then print the `ADDON <name> <STATE>`
lines in the order pass 1 recorded them. Classification moved from a `build-<addon>.yml` existence test to
the `config.yaml` + `build.yaml` + `Dockerfile` triple. rlj's derive-mode pipeline is unchanged (D-05).

**Nine prose sites** corrected — see Deviations for why all nine were in scope.

## Verified Environment — Re-measured, Not Trusted (§3.7)

Every figure below was measured in this worktree before editing, not taken from the plan.

| Fact                                                         | Plan said        | Measured                                       |
| ------------------------------------------------------------ | ---------------- | ---------------------------------------------- |
| `ls .github/workflows/build-*.yml \| wc -l`                  | 9                | **9** ✓                                        |
| `build.yml` exists                                           | false            | **false** ✓                                    |
| add-ons with the manifest triple                             | 9                | **9** ✓                                        |
| total arch legs                                              | 10               | **10** ✓ (coding-assistants 2, eight others 1) |
| `build_from` keys vs `config.yaml` `arch:`                   | 9 of 9 agree     | **9 of 9 agree** ✓                             |
| `check-version-tags.sh` code-only sha256                     | `07d060ea…0394c2` | **`07d060ea…0394c2`** ✓                       |
| `update-version.py` `^def ` sha256                           | `1aca4cb3…6dc8c` | **`1aca4cb3…6dc8c`** ✓                         |
| latest actionlint                                            | v1.7.12          | **v1.7.12** ✓                                  |
| anchor `7cc82f5` shape                                       | one add-on       | **`gatus/config.yaml` only** ✓                 |
| anchor `8c6645f` shape                                       | `.planning`-only | **`.planning` only** ✓                         |
| top-level dirs                                               | (not recorded)   | **9 add-on, 4 non-add-on** (`docs`, `internal`, `terraform-provider-homeassistant`, `tools`), **5 dotdirs** |
| tracked files inside add-on dirs                             | (not recorded)   | **232**, of which **205** were unreachable by the drafted `paths:` filter — the D-08 gap |

### One measured divergence from the plan's re-pinned baseline — expected, not a defect

`G3-8`'s starting count. The plan (re-pinned by `260910-0og` at `ba490aa`) recorded **9 full-path
`.github/workflows/build-` references across four files**, including `internal/dispatch-builds.sh` ×2.
Measured at Task 3's start: **7 across three files** — `.github/RELEASE.md` ×3,
`docs/AUTO_UPDATE_GUIDE.md` ×3, `internal/update-version.py` ×1. The difference is exactly the two the
script carried: **Task 2 removed them before Task 3 measured.** `9 − 2 = 7`. The gate itself is `== 0` and
baseline-independent, so nothing needed adjusting. `gh workflow run build-` measured **2** (one in each
rlm-written doc), matching the plan.

Both counts are **0** at HEAD.

## Gate Results

**Task 1 — 10 gates.** All ten passed at commit `1063603`: G1-1, G1-2, G1-3, G1-4a, G1-4b, G1-4c, G1-4d,
G1-4e, G1-5, G1-6, G1-8, plus G1-7 (yamllint + actionlint v1.7.3 via pre-commit + actionlint v1.7.12
downloaded from the release API) and `pre-commit run --files`.

The detect body, extracted from the file with PyYAML and executed locally, reproduced all seven measured
outcomes of the plan's calibration Run B:

| Input                                          | Result                                                          |
| ---------------------------------------------- | --------------------------------------------------------------- |
| `ADDONS_INPUT=meridian`                        | `["meridian"]`, 1 amd64 leg, name+description byte-equal to config.yaml |
| `ADDONS_INPUT=coding-assistants`               | legs `amd64` then `aarch64`                                     |
| `ADDONS_INPUT=` (empty)                        | the nine add-ons, 10 legs                                       |
| push `7cc82f5^..7cc82f5`                       | `["gatus"]`                                                     |
| push `8c6645f^..8c6645f` (`.planning`-only)    | `[]` with `{"include":[]}`                                      |
| unresolvable `BEFORE_SHA`                      | `HEAD^` fallback, still `["gatus"]`                             |
| all-zero `BEFORE_SHA`                          | `HEAD^` fallback, still `["gatus"]`                             |
| `tools,nonexistent-addon,../../etc,.planning`  | `[]`, exit 0                                                    |

**Task 2 — 13 gates.** G2-1 … G2-7 all pass, including at HEAD. `G2-3b` captured the exact argv:
`workflow run build.yml --ref main -f addons=coding-assistants,meridian` — one process, one call.
`G2-5` confirmed the two independent implementations agree on all nine add-ons.
`G2-7`'s repo-wide latest-actionlint run is silent.

**Task 3 — 14 gates.** G3-1, G3-1b, G3-1c, G3-2, G3-3, G3-4, G3-5, G3-6, G3-7a, G3-7b, G3-7c, G3-8, G3-9,
G3-10 — all pass. `G3-6`'s code-only hash is byte-identical, proving the hook change is comment-only.

**Full `<verification>` block:** `pre-commit run --all-files` passes (all 21 hooks); repo-wide latest
actionlint silent; `yamllint -d relaxed .github/workflows/` → 0 errors (line-length warnings only, rc=0,
matching `lint.yml:81-84`); both workflows parse under PyYAML; `shellcheck internal/dispatch-builds.sh`
with **no** `-e` flags emits nothing; `git status --porcelain` clean; 20 paths total (11 modified/added,
9 deleted).

### Two Task-1 gates are commit-scoped and are expected red at HEAD

Both passed at their own commit (`1063603`) and are *structurally* unsatisfiable after Task 2 deletes the
callers. This is the same class as rlm's `D0-tree-is-six`, not a regression:

| Gate   | Why it cannot hold at HEAD                                            | Disposition                                                                                          |
| ------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `G1-2` | asserts **9** callers are present — it IS the L-14 ordering invariant, true only before Task 2 | Superseded at HEAD by `G2-1` (zero callers, all nine deletions staged). Passed at `1063603`.          |
| `G1-3` | reads `.github/workflows/build-meridian.yml`, which Task 2 deletes    | Re-asserted at HEAD against the deleted caller's recorded content (`git show c560b5e^:…`) — **PASS**. |

`G1-3`'s property (identical `uses`, `permissions`, four named `secrets:`, `fail-fast: false`, no
`timeout-minutes`, the four `matrix.*` `with:` inputs) therefore holds at HEAD, verified, not merely
asserted at an earlier commit.

## Sibling Gates Knowingly Invalidated — Expected Red

The five recorded in the plan's `<sibling_supersession>` § 1. A verifier re-running the batch's full gate
set should read these as expected, with these successors:

| Sibling gate                                                                   | Why it cannot survive                              | Successor                                               |
| ------------------------------------------------------------------------------ | -------------------------------------------------- | ------------------------------------------------------- |
| rlj `GATE-T1-5`, its `grep -q 'gh workflow run build-meridian.yml'` clause      | that workflow no longer exists                     | `G2-3a` (single `build.yml` form; ordering re-asserted) |
| rlm `D0-tree-is-six`                                                           | all nine callers deleted, so the count is 0        | `G2-1`                                                  |
| rlm `D0b`, `D1-says-six`, `D2-not-seven`, `X2-reenable-steps`                   | their `sed` range start anchor `### Re-enabling a tag trigger` is gone | `G3-1` (subsection absent AND recipe present) |
| rlm `E2-scoped-to-six`                                                         | the in-file-comment sentence was dropped           | `G3-1`'s `tag-trigger temporarily disabled == 0`        |

Everything else rlj, rll and rlm assert over these files is re-asserted here and is **green** — including
rlj's `GATE-T1-6` property (`G2-4`), rll's `GATE-T2-A/B/C/D/E` (`G3-7a/b/c`), and rlm's `A*`, `B*`, `C*`,
`H*`, `X1`, `N*`, `Y*`, `K*`, `L1` (`G3-1b`, `G3-1c`, `G3-2`, `G3-10`).

Also re-verified green after this item: `260910-0og`'s `GATE-T1-F4` (`15 of the 42` + both dates survive
in `.github/RELEASE.md`) and its `C3-dated` preservation. `260910-0og`'s
`GATE-T1-G38-COUNT-UNCHANGED` (asserts 9) is **expected red** — driving that count to 0 is this item's job.

## POST-EXECUTION FINDING — the `paths:` filter under-triggered (fixed in `2a19285`)

Found by the coordinator after the three tasks landed and **before** the merge; confirmed by
measurement, fixed on the branch, and recorded in the plan as **D-08**. This is a defect in the
plan as drafted, not a trade-off the plan weighed — it silently under-triggered.

**The gap.** The nine deleted callers triggered on `paths: <addon>/**`. The plan specified — and
Task 2 shipped — `**/config.*`, `**/build.*`, `**/Dockerfile`. But every add-on's Dockerfile COPYs
non-manifest files, so those files were build inputs that no longer triggered a build:

| Add-on | Non-manifest build inputs (measured from its Dockerfile) |
| --- | --- |
| `terraform-bridge`, `iac-runner` | **`COPY . .`** — the entire Go module (`iac-runner/Dockerfile:25`) |
| `coding-assistants` | 5 CLI scripts, `index.html`, `info.html`, `nginx.conf` |
| `gatus` | `run.sh`, `generate_config.py`, `nginx.conf` |
| `network-tools` | `arping_scan.py`, `mdns_scan.py`, `run.sh`, `nginx.conf` |
| `markdown-renderer` | `run.sh`, `generate_nginx.py`, `_git_sync.py` |
| `meridian` | `run.sh`, `nginx.conf` |
| `phone-logger` | `run.sh`, `generate_config.py` |
| `authentik` | `run.sh` (19 `COPY` lines total) |

**Measurement.** Of the 232 tracked files inside the nine add-on directories, **205 were reachable
by the deleted callers and unreachable by the shipped filter.** Real history holds ~12 qualifying
commits. Consequence: a human pushing source-only changes got no build, the store kept advertising
the same version, and the image behind it went stale — the failure class this batch exists to
close, inverted.

**Proven on real history**, by extracting the detect body and executing it (the plan's own
instrument):

| Case | Old derivation | New derivation |
| --- | --- | --- |
| `9caad88` — 4 Go files under `iac-runner/`, no manifest (real) | `[]` **← the gap** | `["iac-runner"]` |
| `meridian/run.sh` only (constructed; no such commit exists in history) | `[]` **← the gap** | `["meridian"]` + full 1-leg matrix |
| `terraform-bridge/internal/auth/bind.go` only (constructed) | — | `["terraform-bridge"]` |
| `8c6645f` — `.planning`-only (real) | `[]` | `[]` ✓ must not build |
| `7cc82f5` — single manifest (real) | `[gatus]` | `["gatus"]` ✓ no regression |

**The fix, two parts.** (1) `paths:` is directory-scoped: `"*/**"` then `"!.*/**"`, `"!docs/**"`,
`"!internal/**"`, `"!terraform-provider-homeassistant/**"`, `"!tools/**"`. (2) The push derivation
drops the manifest regex and takes the first path segment of every changed file, leaving the
manifest triple as the only acceptance test — byte-for-byte the definition
`internal/dispatch-builds.sh` uses, so **D-05's documented asymmetry is dissolved, not described**.

`!.*/**` covers every dotdir as a class and is *provably* safe rather than convenient: the
derivation's name-shape gate requires `^[a-z0-9]`, so no add-on directory can begin with a dot. It
is also necessary — GitHub's `*` matches a leading dot, so `.planning/**` matches `*/**`, and this
repo commits to `.planning/` constantly.

**Negation semantics were verified, not assumed** (docs.github.com workflow-syntax, fetched
2026-09-10): order matters and a `!` after a positive match excludes; at least one non-`!` pattern
is required (satisfied by `*/**`); `*`/`[`/`!`-leading patterns must be quoted in YAML (all six
are).

**Bonus, measured — the new filter is strictly better in BOTH directions.** The old one also
matched `.planning/config.json`, `.github/**` manifests, `tools/test-addon/*` and
`terraform-provider-homeassistant/build.yaml`, spinning ~15 s no-op `detect` jobs. The new one
excludes all four. `T-rln-05`'s disposition therefore improved from `accept` to `mitigate`.

### Gates moved

| Gate | Change |
| --- | --- |
| `L-2` | RE-POINTED: pins the six directory-scoped patterns, positive-first |
| `G2-2` | RE-POINTED: asserts the new `paths:` list and that no negation precedes the positive pattern |
| **`G2-2b`** | **NEW.** Implements GitHub's documented ordered-negation matcher and asserts the net filter over all 537 tracked files: all 232 add-on files included; every dotdir, non-add-on dir and root file excluded; and every add-on reachable via a NON-manifest file — the property the old filter lacked |
| **`G2-2c`** | **NEW.** Regression probe for the gap itself: `9caad88` must derive `["iac-runner"]`. Fails the moment an extension filter returns to the push branch |
| `G3-3` | RE-POINTED: the positive clause asserted the literal `**/config.*` in README; now asserts `*/**` and `run.sh`, and **negative**-greps `**/config.*` so the gap cannot reappear in prose |
| `T-rln-05` | RE-POINTED, disposition `accept` → `mitigate` |
| `a-2`, `a-4` | RE-POINTED in the coverage audit, each recording that the item text's literal wording is what proved to under-trigger |
| `must_haves.truths` | Gained the coverage truth that was missing |
| `D-05` | Asymmetry paragraph corrected — the asymmetry no longer exists |
| line-178 claim | The false "coverage after removal is complete" claim corrected in the plan |

### Mutation-proven (§3.1 — a passing gate proves correctness, only mutation proves it catches)

Six probes in a scratch clone. Control passes before and after; each mutation fails for its own
correct reason:

| Mutation | Result |
| --- | --- |
| revert to the drafted extension-scoped `paths:` | `MISCLASSIFIED 211` |
| drop `!.*/**` | `MISCLASSIFIED 228`, naming dotdir files |
| negate an add-on directory (`!meridian/**`) | `MISCLASSIFIED 10`, all `meridian/` |
| put negations before the positive pattern | `POSITIVE-PATTERN-FIRST VIOLATED` |
| forget to negate `docs` | `MISCLASSIFIED 5`, all `docs/` |
| revert the push derivation to the manifest regex | G2-2c: expected `["iac-runner"]`, got `[]` |

A first attempt at these probes was **invalid** and is recorded rather than hidden: it used
`git checkout -- build.yml` inside the clone to reset between mutations, which restored the clone's
*committed* (still-drafted) file because the fix was uncommitted at the time — so mutations 3-5 all
silently re-tested mutation 1. Corrected by resetting from a pristine copy of the working-tree file.

## Deviations from Plan

### None affecting the plan's instructions

All three tasks executed as written, in the mandated L-14 order, as three commits. The fourth and
fifth commits are the SUMMARY/ledger commit and the post-execution D-08 fix above.

### Two adjacent falsified claims found OUTSIDE the declared paths — deliberately not fixed

Both are now false *because of* Task 2, so they are in the blast radius — but fixing them would add a
21st path against the explicit `<success_criteria>` bullet ("twenty paths total … no scope creep") and,
for the README one, would contradict Task 3 item 2's explicit instruction to keep the rest of that bullet
intact. Both are recorded in `.planning/WINDOWS.md` rather than silently dropped.

**1. `Makefile:234` — the higher-severity one.** `make release` prints:

> `✅ Release $$TAG complete. The build workflow for $(ADDON) will pick it up on the tag push.`

After this item, **nothing** picks it up on the tag push. This is runtime output that will actively mislead
an operator into believing an image is being built. `260909-rlm`'s verification flagged it as adjacent and
out of scope; `260910-0og` deferred it again for the same reason. It is now false rather than merely
imprecise, which is a severity increase this item causes. **Recommend a follow-up item; it is a one-line
`echo` change.**

**2. `README.md:161`** — "A pre-push hook **enforces** that any bumped version has a matching tag."
`260909-wgm` made `internal/check-version-tags.sh` advisory (it never fails a push), so `enforces` is
wrong. Not caused by this item, and Task 3 item 2 explicitly mandated keeping the rest of that bullet
intact, so it was left alone.

## Known Stubs

None. No hardcoded empty values, no placeholder text, no unwired components. Every gate in all three tasks
was executed against the real tree with the real linters; none was weakened, skipped or stubbed.

## Expected Side Effect — Not a Regression

`org.opencontainers.image.description` changes for **8 of 9 add-ons** on their next build, because
`addon-description` now comes from `config.yaml` and eight of the deleted callers had drifted from it.
That is the fix (D-04): `config.yaml` is what the add-on store shows the user. Measured example —
`coding-assistants`' caller said "Terminal with Claude Code, OpenCode, and GitHub Copilot CLI" while its
`config.yaml` says "Terminal with OpenCode and GitHub Copilot CLI — SSH + web terminal". Only `gatus`
agreed.

## OUTSTANDING OBLIGATION — The Post-Merge Dispatch Proof

**This item is NOT complete until this has been run.** It is the only human-verified residual and no gate
substitutes for it: a `workflow_dispatch` is only dispatchable once the workflow exists on the **default**
branch (D-03), so the dynamic matrix expression, the reusable-workflow call-site `permissions` and the
named `secrets:` mappings are evaluated by GitHub for the first time only after merge.
`docs/DEVELOPMENT.md` records that all three fail *only* at run time and that actionlint passing does not
prove them.

**Deadline: before the next 06:00 UTC `auto-update` cron**, which would otherwise be the first thing to
exercise the new dispatch path unattended.

1. `gh workflow run build.yml -f addons=coding-assistants` then `gh run watch` — expect exactly **two**
   build jobs named `coding-assistants (amd64)` and `coding-assistants (aarch64)`, both green, and a
   `::notice::` from `detect` reporting `["coding-assistants"]` and 2 legs.
2. `gh workflow run build.yml -f addons=meridian` — expect exactly **one** leg, `meridian (amd64)`.
3. End-to-end: one trivial `config.yaml` subpatch bump on a single add-on, pushed to `main`. Confirm ONE
   `Build Add-on` run whose matrix contains only that add-on.
4. **NEW, added by the D-08 fix and the one proof no offline gate can substitute for:** a
   **source-only** push — e.g. a comment line in `meridian/run.sh`, or any file under
   `iac-runner/internal/` — with **no manifest change**. Confirm a `Build Add-on` run fires and
   that its matrix contains only that add-on. This is the exact case that produced NO run before
   `2a19285`, and it is the only way to observe GitHub's own evaluation of the `"*/**"` +
   `!`-negation filter (the offline `G2-2b` proves the set under GitHub's *documented* algorithm,
   which is a different thing from GitHub's implementation).
5. **Also new:** confirm the negations hold live — push a `.planning/`-only commit and a
   `docs/`-only commit and confirm **no** `Build Add-on` run appears for either. If a run does
   appear, the filter is over-triggering (harmless no-op, but it means `!.*/**` did not behave as
   documented and the plan's D-08 justification needs revisiting).
6. `docker manifest inspect ghcr.io/akentner/homeassistant-addons/amd64-<slug>:<config version>`
   (sibling `260909-rlk`'s `internal/verify-image-availability.sh` automates this).

**If any step fails — USE THIS EXACT COMMAND:**

```bash
git revert --no-edit 2a19285 c560b5e     # newest first
```

**Do NOT use `git revert c560b5e` alone.** It was the documented handle until the D-08 fix
(`2a19285`) landed on the same `build.yml` and `internal/dispatch-builds.sh` regions. Both forms
were measured in a scratch clone:

| Command | Result |
| --- | --- |
| `git revert --no-edit c560b5e` | **CONFLICTS** on `.github/workflows/build.yml` and `internal/dispatch-builds.sh` |
| `git revert --no-edit 2a19285 c560b5e` | **Clean.** Nine callers restored; `build.yml` present with `workflow_dispatch` as its only trigger (i.e. back to the Task-1 state, still dispatchable for iteration); `internal/dispatch-builds.sh` back to rlj's per-add-on shape |

Do **not** attempt a forward fix on `main` while the builder is broken — the nine callers are the
working fallback and reverting to them costs one command.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern or schema change at a trust boundary beyond
the `<threat_model>` register. Both `high` threats are mitigated as planned and gate-backed:

- **T-rln-01** (event data reaching the detect shell) — `G1-5` proves the extracted run body contains no
  `${{` at all; every event value arrives via `env:`.
- **T-rln-02** (candidate name reaching filesystem paths) — `G1-4e` feeds `../../etc` and `.planning` and
  gets `[]` with exit 0; three barriers (first-path-segment `awk`, name-shape regex, manifest-triple test).
- **T-rln-SC** — zero new package-manager installs and zero new dependencies. No legitimacy checkpoint
  required.

`build.yml`'s `detect` job declares `permissions: {contents: read}` only; `packages: write` lives on the
build call site alone, exactly as the deleted callers had it.

## Commits

| Task | Commit    | Scope                                                                             |
| ---- | --------- | --------------------------------------------------------------------------------- |
| 1    | `1063603` | `ci`: add single build.yml builder, dispatch-only (1 file, +173)                   |
| 2    | `c560b5e` | `ci!`: the switch-over — push trigger, nine deletions, batched dispatch (11 files) |
| 3    | `1b8bd8f` | `docs`: retire per-caller build/tag-trigger documentation (9 files)                |
| —    | `121e569` | `docs`: SUMMARY + two WINDOWS ledger entries (2 files)                            |
| —    | `2a19285` | `fix`: directory-scoped paths filter + unfiltered push derivation (9 files) — the D-08 coverage fix |

`c560b5e` keeps its sha and remains the switch-over commit holding all nine deletions; the D-08 fix
is additive on top rather than an amend, precisely so that sha stays valid as a reference. See the
revert table above for the command that now works.

## Self-Check: PASSED

- `.github/workflows/build.yml` — FOUND
- nine `.github/workflows/build-*.yml` — absent from worktree AND from the index (`git ls-files` empty)
- `.github/workflows/_build-template.yml` — FOUND
- `internal/dispatch-builds.sh` — FOUND, mode 755, shellcheck-clean with no exclusions
- commits `1063603`, `c560b5e`, `1b8bd8f` — all three FOUND in `git log`
- `git rev-list --count 89e8375..HEAD` = **5**, matching the `commits:` frontmatter
- `git diff --stat 89e8375..HEAD` = **21 files** (20 code/doc paths + the PLAN.md correction);
  the 11-modified/9-deleted code contract is unchanged by the D-08 fix, which touched only files
  already in the set
- `git status --porcelain` clean before each commit
- the revert command in this SUMMARY was **executed** in a scratch clone, not asserted:
  `git revert --no-edit 2a19285 c560b5e` → rc=0, nine callers restored
- `G2-2b` and `G2-2c` were **mutation-probed**, not merely observed passing
