---
quick_id: "260908-pfq"
slug: "make-the-pre-push-version-tag-hook-stop-demanding-a-release"
phase: quick
plan: "260908-pfq"
subsystem: infra
tags: [git-hooks, pre-push, bash, shellcheck, release-workflow, home-assistant-addons]

requires:
  - phase: "0a85a8a (subpatch tag support)"
    provides: "primary_tag / legacy_tag resolution in internal/check-version-tags.sh, which this item leaves untouched"
provides:
  - "LOCAL_BUILD_ADDONS allowlist + is_local_build helper in internal/check-version-tags.sh"
  - "Skip branch: allowlisted add-ons need no <addon>/v<version> release tag to push"
  - "Drift guard: an allowlisted add-on declaring a top-level image: key warns and is enforced anyway"
  - "Worktree-safe HOOK_TARGET derivation in internal/setup-hooks.sh (--git-common-dir)"
  - "Reinstalled .git/hooks/pre-push (was an 8-day / 6-commit stale copy with no primary_tag logic)"
  - "Documentation sync across docs/UPDATE_VERSION.md, .github/RELEASE.md, README.md, AGENTS.md"
affects: [release-workflow, iac-runner, terraform-bridge, update-version.py, phase-19-operator-runbook]

actuals:
  tokens: 2678
  tasks: 3
  commits: 3
plan_head_before: a4ca23f2079a8d9be59fcddc280dcec9b338d6d8

tech-stack:
  added: []
  patterns:
    - "Explicit hand-maintained allowlist over an inferred rule, when the inferable rule would cement an unsettled bug"
    - "Fail-safe drift guard: warn loudly, then fall through to enforcement — never a silent skip"
    - "set -e-safe bash membership helper: full `if [[ ]]; then return 0; fi`, called only as an `if` condition"
    - "Throwaway six-case fixture harness driving the real hook via its stdin contract inside mktemp -d"

key-files:
  created: []
  modified:
    - internal/check-version-tags.sh
    - internal/setup-hooks.sh
    - docs/UPDATE_VERSION.md
    - .github/RELEASE.md
    - README.md
    - AGENTS.md

key-decisions:
  - "Skip is an explicit two-entry allowlist (iac-runner, terraform-bridge), NOT `config.yaml has no image: key` — seven
    of nine add-ons lack that key and inferring the rule would cement a possible missing-key bug"
  - "Drift guard warns and enforces rather than hard-failing — a drifted entry with a valid tag must still be able to
    push"
  - "grep -qE '^image:...' rather than yq — the hook runs as a bare .git/hooks copy and must carry no tool dependency"
  - "internal/setup-hooks.sh line 25 GIT_ROOT and line 27 HOOK_SOURCE deliberately left unchanged; only HOOK_TARGET
    moved to --git-common-dir"
  - "Hook reinstalled via the script's own two operations (cp + chmod +x) rather than running setup-hooks.sh wholesale,
    whose trailing `pre-commit run --all-files` could obscure whether the install itself succeeded"

requirements-completed: []

coverage:
  - id: D1
    description:
      "Pushing a bump of iac-runner or terraform-bridge without a release tag succeeds and prints one ⊘ line per add-on
      saying why"
    verification:
      - kind: integration
        ref:
          "${TMPDIR}/vt-hook-fixture.sh case B — exit 0, exactly two ⊘ lines, both containing 'built locally by the
          Supervisor'"
        status: pass
    human_judgment: false
  - id: D2
    description:
      "Enforcement unchanged for the other seven add-ons, including the five keyless-but-not-allowlisted ones"
    verification:
      - kind: integration
        ref: "vt-hook-fixture.sh case A (network-tools, declares image:) — exit 1 + '404 on update'"
        status: pass
      - kind: integration
        ref: "vt-hook-fixture.sh case E (authentik, no image: key, not allowlisted) — exit 1 + '404 on update'"
        status: pass
      - kind: integration
        ref:
          "vt-hook-fixture.sh cases C and D — primary_tag ('tag coding-assistants/v1.0.0-2 exists') and legacy_tag
          ('legacy format') paths both exit 0"
        status: pass
      - kind: other
        ref:
          "git diff --stat internal/check-version-tags.sh — 70 insertions, 0 deletions; grep of the diff for
          primary_tag|legacy_tag|tag_exists|build_version=|config_version= returns 0 hits"
        status: pass
    human_judgment: false
  - id: D3
    description:
      "An allowlisted add-on that acquires an image: key is warned about by name and enforced anyway, never silently
      skipped"
    verification:
      - kind: integration
        ref: "vt-hook-fixture.sh case F — exit 1 + 'LOCAL_BUILD_ADDONS' + '404 on update'"
        status: pass
    human_judgment: false
  - id: D4
    description: "The hook that actually runs on a push is the one this item edited"
    verification:
      - kind: other
        ref:
          'diff "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push" internal/check-version-tags.sh
          — empty; test -x passes; grep -c primary_tag 0 → 8'
        status: pass
    human_judgment: false
  - id: D5
    description: "internal/setup-hooks.sh can install the hook from a linked worktree without breaking HOOK_SOURCE"
    verification:
      - kind: other
        ref:
          "Installer-integrity probe: eval of the script's own GIT_ROOT/HOOK_TARGET/HOOK_SOURCE lines resolves
          HOOK_SOURCE to an existing file and HOOK_TARGET's parent to an existing dir; negative control with GIT_ROOT
          deleted returns 1 while bash -n and a static grep both return 0"
        status: pass
    human_judgment: false
  - id: D6
    description: "The four documentation surfaces no longer claim the release tag is unconditional"
    verification:
      - kind: other
        ref:
          "Whitespace-normalised grep -F 'built locally by the Supervisor' across all five files; pre-commit run --files
          over the six touched paths exits 0"
        status: pass
    human_judgment: false
  - id: D7
    description: "Real repository gained no git tag and pushed nothing"
    verification:
      - kind: other
        ref:
          "Harness before/after count of `git tag -l '*/v*'` in the real repo — 39 = 39 on every run; no git tag / git
          push issued anywhere"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-09-08
status: complete
---

# Quick 260908-pfq: Pre-push tag requirement scoped to an explicit locally-built allowlist Summary

**`internal/check-version-tags.sh` now skips the `<addon>/v<version>` release-tag requirement for exactly `iac-runner`
and `terraform-bridge` via a hand-maintained `LOCAL_BUILD_ADDONS` array, warns-and-enforces if either ever declares
`image:`, leaves the `primary_tag`/`legacy_tag` path byte-identical for the other seven, and the stale 8-day-old
`.git/hooks/pre-push` copy was reinstalled so the change actually takes effect on a real push.**

## Performance

- **Duration:** ~22 min
- **Completed:** 2026-09-08T17:11Z
- **Tasks:** 3 of 3
- **Files modified:** 6 (93 insertions, 6 deletions)

## Accomplishments

- **The false-positive push blocker is gone for the two add-ons the Supervisor builds locally**, and it is _visible_
  rather than silent: each skipped add-on prints
  `⊘ <addon>: built locally by the Supervisor, never pulled from ghcr.io; release tag not required`.
- **Enforcement is provably unchanged for the other seven.** The edit is insert-only — 70 insertions, 0 deletions — and
  the whole `primary_tag` / `legacy_tag` / `tag_exists` region is absent from the diff. Fixture cases A, C, D and E were
  the regression fence and all four passed both before and after.
- **The drift hole is closed fail-safe.** An allowlisted add-on that acquires a top-level `image:` key gets a warning
  naming `LOCAL_BUILD_ADDONS` and the file to edit, then falls through to the normal tag check. Protection is restored
  automatically without anyone reading the warning.
- **The hook that runs on a push is now the hook in the repo.** `.git/hooks/pre-push` was a copy from 2026-08-31 23:30
  that predated `0a85a8a` entirely: `grep -c primary_tag` was **0** against 8 in the source. Any conclusion previously
  drawn from "the hook allowed/blocked this" was unsound. It is now byte-identical to the source and executable.
- **`internal/setup-hooks.sh` can do that job from a linked worktree at all**, which it could not before —
  `$GIT_ROOT/.git/hooks/pre-push` is unwritable where `.git` is a file.

## Task Commits

1. **Task 1: Allowlist-driven skip plus drift guard** — `5869bb7` (feat)
2. **Task 2: Scope the four docs that claimed the tag was unconditional** — `0afe07f` (docs)
3. **Task 3: Worktree-safe setup-hooks.sh + reinstall the stale hook** — `812f028` (fix)

Measured: `git rev-list --count a4ca23f..HEAD` = **3**. No plan-metadata commit — per the batch dispatch, the
orchestrator owns the SUMMARY/PLAN commit and STATE.md/ROADMAP.md writes.

## Files Created/Modified

- `internal/check-version-tags.sh` — `LOCAL_BUILD_ADDONS` array (2 entries) + `is_local_build` helper inserted between
  `errored=0` and the `tag_exists` comment; skip branch + drift guard inserted immediately after the empty-version
  guard, upstream of the untouched tag-resolution block.
- `internal/setup-hooks.sh` — `HOOK_TARGET` now derives from `git rev-parse --path-format=absolute --git-common-dir`;
  the "Before push" install summary names the exception.
- `docs/UPDATE_VERSION.md` — `## Pre-push hook` paragraph states the allowlist, names both current members, gives the
  removal criterion, and documents warn-and-enforce.
- `.github/RELEASE.md` — release-flow step 2 and the `## Manual repair` note ("every modified `config.yaml`") both
  scoped.
- `README.md` — the Repository Conventions three-file-versioning bullet scoped.
- `AGENTS.md` — the version-tag bullet names the allowlist and tells a future agent not to reinstate the unconditional
  requirement.

Only `docs/UPDATE_VERSION.md` names the two current members; the other three point at `LOCAL_BUILD_ADDONS` in
`internal/check-version-tags.sh` as the single source of truth rather than duplicating the list in four places.

## Decisions Made

Carried from the plan, restated because they are the load-bearing ones:

- **The skip is an explicit allowlist, not `config.yaml has no image: key`.** Seven of nine add-ons lack that key, not
  the two the original task text implied. Six of those seven publish ghcr.io images via their build workflows, so their
  missing key may be a bug rather than intent — keying the hook on the key's absence would have cemented that bug behind
  a guard that stopped complaining. The user narrowed the skip to `iac-runner` and `terraform-bridge`; `authentik`,
  `gatus`, `markdown-renderer`, `meridian` and `phone-logger` keep their tag requirement until the `image:`-key question
  is settled as its own piece of work. **Fixture case E is the standing fence for that decision.**
- **`terraform-bridge`'s ghcr build now needs another trigger.** Unlike `iac-runner` (no `image:` key _and_ no build
  workflow — a release tag is inert in every direction), `terraform-bridge` has `build-terraform-bridge.yml` with an
  **active** `terraform-bridge/v*` tag trigger. Allowlisting it means the release flow no longer nags for that tag, so
  that CI build must be triggered via `workflow_dispatch` or the existing `paths:` trigger on `main`. This is a
  consequence of the decision, not a defect.
- **Drift → warn + fall through, not a dedicated hard failure.** A hard failure would block a push even when a valid tag
  exists, punishing a bookkeeping error with no consequence at that moment, and the only remedy would be editing the
  hook mid-push. The fall-through makes a drifted entry behave exactly like a non-allowlisted add-on.
- **`grep`, not `yq`.** HA `config.yaml` needs `yq eval --unsafe` for its custom tags (per `CLAUDE.md`), and the hook
  runs as a bare `.git/hooks` copy that must carry no tool dependency. The regex is `^`-anchored with a non-blank value
  required, so an indented sub-key, a `# image:` comment, or an empty value cannot satisfy it.
- **`GIT_ROOT` was NOT cleaned up.** It looks single-use after the `HOOK_TARGET` change but still feeds `HOOK_SOURCE`,
  and `--show-toplevel` is the correct derivation there because the source file lives in the working tree, not in
  `.git`. Deleting it would leave `HOOK_SOURCE=/internal/check-version-tags.sh`, the `[[ -f ]]` guard would take its
  `else` branch, and the installer would stop installing while still exiting 0. The installer-integrity probe exists
  specifically to catch that, and its negative control was re-run here (see Issues).

### Local state changed before merge — read this

`.git/hooks/` is **untracked local state and is never committed.** Reinstalling the pre-push hook changed the
developer's local push behaviour _immediately_, before this item is merged — but what it replaced was already stale and
wrong (no `primary_tag` logic at all), so the net effect is strictly an improvement even if this item were reverted. If
it is reverted, re-running `./internal/setup-hooks.sh` restores whatever the merged source says. The reinstall used the
script's own two operations (`cp` + `chmod +x`) rather than invoking the script wholesale, because the script ends with
`pre-commit run --all-files` — slow, and a failure there would obscure whether the install itself succeeded. The two are
equivalent for the hook install, and running the full script after merge is idempotent.

### Explicitly out of scope (do not expand)

- `internal/update-version.py` still creates and pushes an `<addon>/v<version>` tag by default for **every** add-on,
  including the two allowlisted ones. Whether that should become conditional stays a separate decision.
- Whether the five keyless-but-enforced add-ons should gain an `image:` key. That question is what the allowlist exists
  to avoid prejudging.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The plan's fixture harness silently tested the unmodified hook for cases B through F**

- **Found during:** Task 1 (first GREEN run — `shellcheck` clean, yet B and F failed byte-identically to the recorded
  RED baseline, and case F produced no drift warning at all).
- **Issue:** The harness copies the working-tree hook into the clone **once**, before any case. Case A then runs
  `git commit -am "fixture A"`, and `-a` stages _every_ tracked modification — including the copied
  `internal/check-version-tags.sh`. Every subsequent `new_case` does `git checkout --quiet -B "fixture-$1" origin/main`,
  which restores that path from `origin/main` — i.e. the **pre-edit** hook. So cases B–F executed the original script.
  This is why the recorded RED baseline looked correct (it was measuring the original hook, which is what RED wants)
  while GREEN was structurally unreachable.
- **Fix:** Moved the `cp` inside `new_case` so the working-tree hook is restored after every checkout, with a comment
  stating why. Additionally added an optional `HOOK_SRC` env override (defaults to
  `$REPO/internal/check-version-tags.sh`) so the _same, fixed_ harness can prove the RED baseline against the pre-edit
  hook via `git show HEAD:internal/check-version-tags.sh`.
- **Files modified:** `${TMPDIR}/vt-hook-fixture.sh` — **throwaway, not committed**, per the plan's instruction that the
  harness stays out of `internal/`. No repository file was changed by this fix.
- **Verification:** With the fixed harness and `HOOK_SRC` pointed at the pre-edit hook: A, C, D, E **PASS**; B, F
  **FAIL** — the plan's recorded RED baseline reproduced through the corrected instrument, proving the six cases
  genuinely discriminate. With `HOOK_SRC` defaulted to the edited hook: all six **PASS**, harness exit 0.
- **Committed in:** n/a (throwaway file outside the repo).

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in the verification instrument, not in a deliverable). **Impact on
plan:** None on scope. It materially strengthened the proof: without the fix, a GREEN result was impossible to obtain,
and — more dangerously — a _later_ variant of the same harness could have reported PASS for the wrong reason. All six
cases are now demonstrated to flip from FAIL to PASS as a direct consequence of the hook edit.

## Issues Encountered

1. **First Task 3 verification failed only on the phrase check.** My initial `setup-hooks.sh` bullet split
   `built locally by the Supervisor` across two `echo` lines. After `tr '\n' ' '` the flattened text reads
   `... by the" echo " Supervisor ...`, so the contiguous `grep -F` needle could never match. Rewrote the bullet to keep
   the phrase inside a single `echo` string. Worth noting as a general trap: the plan's own phrase-presence check is
   whitespace-normalised specifically to survive `prettier` reflow in Markdown, but it cannot survive a shell string
   boundary.

2. **`prettier` reflowed `docs/UPDATE_VERSION.md` on the first `pre-commit` run** (exit 1, "files were modified by this
   hook"), then passed clean on the second. Anticipated by the plan; the phrase check was re-run _after_ the reflow and
   still matched in all five files.

3. **Negative control on the installer-integrity probe re-run here, not just trusted from planning.** With the
   `GIT_ROOT=` line stripped from a temp copy: the probe returns **1**
   (`HOOK_SOURCE=[/internal/check-version-tags.sh]`), while `bash -n` returns **0** and a static
   `grep -qE 'HOOK_SOURCE=.*internal/check-version-tags.sh'` also returns **0** — both blind to the break, exactly as
   the plan claimed. The probe is the only one of the three that catches it.

4. **`gsd-tools windows append` could not write to `.planning/WINDOWS.md`** — it errors with "Ledger table region could
   not be located … refusing to write", despite the file looking structurally intact (most plausibly `prettier`
   realigned the rendered table's column padding and the region detector does not tolerate that). The tool's own error
   forbids hand-editing the rendered table, so the Rule-1 deviation above is recorded **in this SUMMARY only**, not in
   the cross-phase ledger. Logged in [`deferred-items.md`](./deferred-items.md) and deliberately **not** fixed —
   pre-existing, unrelated to this item's six files, and repairing it means touching cross-phase planning state this
   quick item does not own.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data paths were introduced.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern, or schema change at a trust boundary. The one
security-relevant change — narrowing the pre-push guard's scope — is the item's stated purpose and is dispositioned in
the plan's threat register (T-pfq-01 `accept`, T-pfq-02 `mitigate` with fixture cases A and E as runnable proof).

## Verification Results

| #   | Check                                                        | Result                                                                                                         |
| --- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| 1   | `shellcheck -e SC1091 -e SC2034` on both scripts             | exit 0                                                                                                         |
| 2   | Fixture harness, six cases A–F                               | all PASS, exit 0                                                                                               |
| 3   | `diff` installed `.git/hooks/pre-push` vs source; `test -x`  | empty diff, executable, `primary_tag` 0 → 8                                                                    |
| 4   | `pre-commit run --files` over all six touched paths          | exit 0                                                                                                         |
| 5   | `git diff --stat a4ca23f..HEAD`                              | exactly the 6 `files_modified`; no add-on `config.yaml`/`build.yaml`/`README.md`; no fixture in `internal/`    |
| 6   | Diff of `check-version-tags.sh` vs the tag-resolution region | 70 insertions / 0 deletions; 0 hits for `primary_tag\|legacy_tag\|tag_exists\|build_version=\|config_version=` |
| 7   | Real-repo `git tag -l '*/v*' \| wc -l`                       | 39 before, 39 after, on every harness run; no `git tag`, no `git push`                                         |

## User Setup Required

None. One **operational note** rather than setup: `terraform-bridge`'s ghcr.io image build no longer has the release nag
pushing its `terraform-bridge/v*` tag, so trigger it via `workflow_dispatch` or the `paths:` trigger on `main` when that
image needs rebuilding.

## Next Phase Readiness

- The pre-push guard no longer blocks `iac-runner` version bumps, which unblocks the outstanding `iac-runner/v0.2.0-0`
  release decision from Phase 17 (still intentionally untagged — pushing that tag fires `build-iac-runner` while the
  v1.2 Phase 8 Cloudflare prerequisite is open; that constraint is unrelated to this item and unchanged).
- Two follow-ups are recorded as deliberately out of scope: `update-version.py`'s unconditional tagging, and the
  missing-`image:`-key question for the five enforced add-ons.
- `.planning/WINDOWS.md` is currently un-writable via `gsd-tools windows append` (see Issues #4). Anyone running
  `/gsd-ship` should know the ledger cannot accept new entries until that is repaired.

## Self-Check: PASSED

- All six modified files exist and are tracked: `internal/check-version-tags.sh`, `internal/setup-hooks.sh`,
  `docs/UPDATE_VERSION.md`, `.github/RELEASE.md`, `README.md`, `AGENTS.md`.
- All three commits exist in `git log`: `5869bb7`, `0afe07f`, `812f028`.
- Measured commit count `a4ca23f..HEAD` = 3, matching `actuals.commits`.
- No file deletions in the range; no git tag created; tag count 39 unchanged.

---

_Quick item: 260908-pfq_ _Completed: 2026-09-08_
