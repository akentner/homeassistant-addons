---
quick_id: "260908-pfq"
slug: "make-the-pre-push-version-tag-hook-stop-demanding-a-release"
description:
  "Make internal/check-version-tags.sh skip the release-tag requirement for an explicit two-entry allowlist of
  locally-built add-ons (iac-runner, terraform-bridge), warn-and-enforce if an allowlisted add-on ever declares
  `image:`, leave primary_tag/legacy_tag enforcement intact for the other seven, and reinstall the stale
  .git/hooks/pre-push copy so the change actually takes effect"
date: "2026-09-08"
status: planned
type: execute
autonomous: true
depends_on: []
files_modified:
  - internal/check-version-tags.sh
  - internal/setup-hooks.sh
  - docs/UPDATE_VERSION.md
  - .github/RELEASE.md
  - README.md
  - AGENTS.md

must_haves:
  truths:
    - "Fixture case B: a commit bumping `iac-runner` and `terraform-bridge` to an untagged `99.99.99-0` makes the hook
      exit 0 and emit exactly two skip lines, one per allowlisted add-on, each containing `built locally by the
      Supervisor` — no tag for that version exists or could, so the pass can only come from the new skip branch"
    - "Fixture case E: a commit bumping `authentik` (no `image:` key but NOT allowlisted) to an untagged `99.99.99-0`
      still makes the hook exit 1 with the `404 on update` rationale — the five add-ons the user kept in scope are
      unaffected by this change"
    - "Fixture case F (drift guard): an allowlisted `iac-runner` whose config.yaml declares `image:` and whose version
      is untagged makes the hook print a warning naming `LOCAL_BUILD_ADDONS` and then still exit 1 with the `404 on
      update` rationale — it warns and enforces, it does not skip"
    - "Fixture case A: `network-tools` (declares `image:`) at an untagged `99.99.99-0` still exits 1 — the ghcr-404
      protection is unchanged"
    - "Fixture cases C and D: `coding-assistants` resolves via the untouched primary_tag path (`tag
      coding-assistants/v1.0.0-2 exists`) and the untouched legacy_tag path (`legacy format`), both exit 0"
    - "All six fixture cases report PASS and the harness exits 0 (verified RED baseline before the change: A, C, D, E
      PASS and B, F FAIL — see `## Fixture harness`)"
    - "`shellcheck -e SC1091 -e SC2034 internal/check-version-tags.sh internal/setup-hooks.sh` exits 0 (same ignore set
      as the pinned shellcheck hook in `.pre-commit-config.yaml`)"
    - '`diff "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push" internal/check-version-tags.sh`
      produces no output and the installed copy is executable — the hook that actually runs on a push is the one this
      plan edited'
    - "Installer integrity: re-evaluating `internal/setup-hooks.sh`'s own GIT_ROOT / HOOK_TARGET / HOOK_SOURCE
      assignment lines in a subshell resolves `HOOK_SOURCE` to an existing file and `HOOK_TARGET`'s parent to an
      existing directory. This fails if `GIT_ROOT` is deleted while editing `HOOK_TARGET` — verified during planning
      that the probe returns PASS/FAIL/PASS for the current, broken and post-edit forms respectively, and that both
      `bash -n` and a static grep for the `HOOK_SOURCE=` literal are blind to that break"
    - "The real repository gains no git tag and pushes nothing: the harness's own before/after count of `git tag -l
      '*/v*'` in the real repo is identical"
    - "The phrase `built locally by the Supervisor` is present (after whitespace normalisation) in all six touched files"
    - "`pre-commit run --files internal/check-version-tags.sh internal/setup-hooks.sh docs/UPDATE_VERSION.md
      .github/RELEASE.md README.md AGENTS.md` exits 0"
  artifacts:
    - "internal/check-version-tags.sh — `LOCAL_BUILD_ADDONS` array, `is_local_build` helper, skip branch, drift guard"
    - "internal/setup-hooks.sh — worktree-safe hook path derivation plus an install summary naming the exception"
    - "docs/UPDATE_VERSION.md — `## Pre-push hook` section states the allowlist exception"
    - ".github/RELEASE.md — the two paragraphs that assert unconditional refusal are scoped to non-allowlisted add-ons"
    - "README.md — the Repository Conventions bullet that asserts unconditional enforcement is scoped"
    - "AGENTS.md — the pre-push hook bullet names the allowlist so future agents do not reinstate the requirement"
  key_links:
    - "`LOCAL_BUILD_ADDONS` array → the hook's enforce-vs-skip decision. Membership is explicit and hand-maintained;
      absence of an `image:` key does NOT by itself grant a skip (see the revision note in `<objective>`)"
    - "An allowlist entry that gains an `image:` key → drift guard → warn on stdout and fall through to enforcement,
      never a silent skip"
    - "The new branch sits upstream of the untouched `primary_tag` / `legacy_tag` block, which is now reached by seven
      of nine add-ons plus any drifted allowlist entry — its logic is not edited"
    - "`internal/setup-hooks.sh` copies (does not symlink) the script to `.git/hooks/pre-push`, so the source edit is
      inert until reinstalled. The currently installed copy is from 2026-08-31 and predates `0a85a8a`, so it does not
      even contain `primary_tag` — reinstalling is a required task step, not a footnote"
---

<objective>
Stop `internal/check-version-tags.sh` from blocking a push over a missing `<addon>/v<version>` release tag for the two
add-ons the Home Assistant Supervisor builds locally from their Dockerfile: `iac-runner` and `terraform-bridge`. Neither
has an `image:` key, so the Supervisor never pulls them from ghcr.io and the 404-on-update the hook exists to prevent
cannot occur — the hook is pushing the developer toward a release that publishes nothing those add-ons consume.

Purpose: remove a false-positive push blocker for exactly those two add-ons, without relaxing enforcement anywhere else,
and make both the skip and any future allowlist drift visible on stdout.

Output: an explicit allowlist plus skip branch and drift guard in the hook, a documentation sync across the surfaces
that describe the hook's contract, and a reinstall of the stale `.git/hooks/pre-push` copy so the change takes effect.

## Revision note — why an allowlist and not "config.yaml has no `image:` key"

The first version of this plan keyed the skip on the absence of a top-level `image:` key, as the task text asked. That
is now superseded. During planning it turned out that seven of nine add-ons lack the key, not the two the task text
named (`grep -L '^image:' */config.yaml`; `git log -S 'image:' -- <addon>/config.yaml` returns commits only for
`coding-assistants` and `network-tools` — the other seven never had it). The coordinator verified that independently and
added the consequence: six of those seven (`authentik`, `gatus`, `markdown-renderer`, `meridian`, `phone-logger`,
`terraform-bridge`) **do** have ghcr build workflows, so they publish images the Supervisor never pulls. That is either
deliberate CI-only building or a long-standing missing `image:` key. If it is the latter, the correct fix is adding
`image:` to them, and keying this hook on the key's absence would cement the bug behind a guard that stopped
complaining.

**User decision: restrict the skip to `iac-runner` and `terraform-bridge` only.** The other five keep their tag
requirement until the `image:`-key question is settled as its own piece of work. Implement the allowlist, not the
inferred rule.

Verified detail: `iac-runner` is the only add-on with neither an `image:` key nor a `build-<addon>.yml` workflow — for
it a release tag is inert in every direction. `terraform-bridge` is different and worth stating plainly: it has
`build-terraform-bridge.yml` with an **active** `terraform-bridge/v*` tag trigger, so a tag push there does still
publish an image to ghcr.io and trigger CI — just an image the Supervisor never pulls. Allowlisting it means the release
flow no longer nags for that tag, so that CI build has to be triggered another way (`workflow_dispatch`, or the existing
`paths:` trigger on `main`). That is a consequence of the decision, not an objection to it.

## Drift guard: loud warning plus enforcement, not a dedicated hard failure

A hand-maintained allowlist can go stale. The dangerous form is an allowlisted add-on that gains an `image:` key: from
then on the Supervisor pulls a prebuilt image, the 404 becomes possible again, and a silent skip would be exactly the
regression this plan is supposed to avoid.

**Chosen behaviour: print a loud warning naming `LOCAL_BUILD_ADDONS`, then fall through to the normal tag check.** The
warning is not itself a hard failure; the fall-through is what protects. Justification:

- It is fail-safe. The outcome for a drifted entry becomes identical to a non-allowlisted add-on: tag present → push
  proceeds, tag missing → push blocked with the existing 404 message. The protection is restored automatically, without
  depending on anyone reading the warning.
- A dedicated hard failure would be strictly worse. It would block a push even when a valid tag exists, punishing the
  developer for a bookkeeping error that has no consequence at that moment, and the only remedy would be editing the
  hook mid-push. Stale metadata is not a shippable defect; an unpulled image is.
- The warning still creates the pressure to fix it, because it prints on every affected push and names the array and the
  file to edit.

Known limitation, accepted: the other drift direction — an allowlist entry naming a directory that was renamed or
removed — is inert rather than detected, because the loop only iterates add-on directories that a push actually
modified. A stale name simply never matches. Detecting it would need a repo-wide sweep the hook does not otherwise do.
Recorded as T-pfq-06.

## The installed hook is stale — reinstalling is part of the work

`internal/setup-hooks.sh` **copies** the script to `.git/hooks/pre-push` rather than symlinking it, so editing
`internal/check-version-tags.sh` changes nothing about a real push until the copy is refreshed. Verified on the current
checkout:

- `.git/hooks/pre-push` is dated `2026-08-31 23:30`.
- `grep -c primary_tag .git/hooks/pre-push` → `0`; the same count against `internal/check-version-tags.sh` → `8`.
- Commit `0a85a8a` ("git tags now include subpatch, hook tolerates legacy format") is dated `2026-09-02`.

So the hook that ran on the push earlier today predates the subpatch work entirely and has none of the `primary_tag` /
`legacy_tag` logic. Task 3 therefore reinstalls it and verifies the installed copy matches the source.

Deliberately **out of scope** (do not expand this plan):

- `internal/update-version.py` still creates and pushes a `<addon>/v<version>` tag by default for every add-on,
  including the two allowlisted ones. Whether that should become conditional stays a separate decision.
- Whether the five add-ons that lack `image:` while publishing ghcr images should gain the key. That question is what
the allowlist exists to avoid prejudging.
</objective>

<execution_context> @~~/.claude/gsd-core/workflows/execute-plan.md @~~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@internal/check-version-tags.sh
@internal/setup-hooks.sh
@.pre-commit-config.yaml
@.github/RELEASE.md
@docs/UPDATE_VERSION.md

Grounding facts already verified against the working tree — do not re-derive:

- `internal/check-version-tags.sh` is 114 lines. `errored=0` is line 49; the `tag_exists` comment starts line 51; the
  per-add-on loop is lines 60-106. `build_version` is extracted line 67, `config_version` line 70, and line 71 is
  `[[ -z "$build_version" && -z "$config_version" ]] && continue`. `primary_tag` / `legacy_tag` are computed lines 77-78
  and consumed lines 80-87. `set -e` is active from line 9.
- Baseline `shellcheck -e SC1091 -e SC2034 internal/check-version-tags.sh` is already clean; any finding after the edit
  is caused by the edit.
- Add-ons declaring `image:`: `coding-assistants`, `network-tools`. The other seven do not.
- Current versions: `coding-assistants` config `1.0.0-2` / build `1.0.0`; `network-tools` config `0.5.0-1`; `authentik`
  config `2026.8.1-0` / build `2026.8.1`; `iac-runner` config `0.2.1-0`; `terraform-bridge` config `0.3.0-0`.
- Tags the fixture relies on: `coding-assistants/v1.0.0-2` (primary form) and `coding-assistants/v1.0.0` (legacy, no
  subpatch) both exist. Real-repo `git tag -l '*/v*' | wc -l` is currently 39.
- `authentik` currently passes the hook only via its legacy tag `authentik/v2026.8.1`, which is why fixture case E bumps
  it to `99.99.99-0` — otherwise the case would pass for the wrong reason.
- `git rev-parse --path-format=absolute --git-common-dir` resolves to the main repository's `.git` even from a linked
worktree (git 2.55 here). `git rev-parse --show-toplevel`-plus-`/.git` does not: in a linked worktree `.git` is a file,
so the existing derivation in `internal/setup-hooks.sh` cannot install the hook from one.
</context>

<!-- prettier-ignore-start -->

<tasks>

<task type="tracer">
  <name>Task 1: Allowlist-driven skip plus drift guard, proven by running the hook six ways</name>
  <files>internal/check-version-tags.sh</files>
  <action>
Two insertions into `internal/check-version-tags.sh`. Nothing else changes.

**(a) The allowlist and its membership helper.** Insert between line 49 (`errored=0`) and the `tag_exists` comment on
line 51, so the array is top-level, adjacent to the loop that reads it, and adding or removing an entry is a one-line
edit. Name the array `LOCAL_BUILD_ADDONS` and give it exactly two entries, `iac-runner` and `terraform-bridge`, one per
line. Comment it with: why an entry is on the list (no `image:` key in config.yaml, so the Supervisor builds it locally
from the Dockerfile and never pulls from ghcr.io, so the 404 this hook guards against cannot occur and a release tag
publishes nothing it consumes); what takes an entry off (the add-on gaining an `image:` key — from then on the
Supervisor pulls a prebuilt image and the tag requirement genuinely applies); and why this is an explicit allowlist
rather than a test for a missing `image:` key (six other add-ons also lack the key while publishing ghcr images, which
may be a missing-key bug rather than intent — inferring the rule would cement it). Point the comment at this plan file
for the full reasoning.

Add an `is_local_build` helper next to it that loops the array and returns 0 on an exact match, 1 otherwise. Write the
comparison as a full `if [[ "$a" == "$1" ]]; then return 0; fi` inside the loop — **not** `[[ ... ]] && return 0`. The
`&&` form leaves a non-zero AND-OR list as the last statement of the loop body on a non-match, which `set -e` (active
since line 9) treats as a fatal error. Call the helper only as an `if` condition, where a 1 return is exempt from
`set -e`.

**(b) The skip branch and drift guard.** Insert immediately after the empty-version guard on line 71, before the
`primary_tag` comment block. Placement after line 71 is deliberate: an add-on directory with no parseable version keeps
short-circuiting first, exactly as today, so precedence changes for nothing.

Structure it as: if the add-on is on the allowlist, then test its `config.yaml` for a top-level `image:` key with a
non-blank value using an anchored `grep -qE` written as an `if` condition (again `set -e`; a `$(grep ...)` capture would
need a `|| true`). Anchor with `^` and no leading-whitespace tolerance — `image` is a top-level key in the HA add-on
manifest, so the anchor is exact and cannot be satisfied by an indented sub-key, a commented `# image:` line, or an
empty value. Use `grep`, not `yq`: `CLAUDE.md` documents that HA `config.yaml` needs `yq eval --unsafe` for custom tags,
and the hook runs as a bare copy in `.git/hooks` that must carry no tool dependency. The rest of this script already
extracts `version:` and `VERSION:` with grep+sed.

- Key present (drift): print a multi-line warning and do **not** `continue` — fall through to the tag check below. The
  warning must name the add-on, state that the Supervisor now pulls a prebuilt image so the tag is required again,
  instruct the maintainer to remove the entry, and contain the literal string `LOCAL_BUILD_ADDONS` and the path
  `internal/check-version-tags.sh` so the fix is unambiguous. Say explicitly that the requirement is being enforced
  despite the allowlist entry.
- Key absent (normal skip): print exactly one line and `continue`. **The wording is pinned, not paraphrasable** — emit
  exactly this, with `$addon_dir` the only variable part:

  `⊘ $addon_dir: built locally by the Supervisor, never pulled from ghcr.io; release tag not required`

  Both the marker and the wording are load-bearing. Fixture case B counts occurrences of `⊘` to assert exactly two
  skips, and it greps `<addon>: built locally by the Supervisor` as one contiguous fixed string — so the phrase must be
  the first words after `: `, with nothing inserted between them. A compliant-sounding variant like
  `⊘ iac-runner: skipped — built locally by the Supervisor` would fail that needle. The marker also keeps the skip
  visually distinct from the existing `✓` tag-found line, and the phrase is what Task 2's presence check looks for.

Everything else in the loop must remain byte-for-byte identical — lines 63-71 and the whole region below the insertion
point, unchanged apart from the inserted block itself. Concretely, these must not move: the `VERSION:`-anchoring
comment, both version extractions, the empty-version guard, `primary_tag`, `legacy_tag`, the two `tag_exists` calls,
the failure message, `errored`, and the trailing exit block. That region is now reached by seven of nine add-ons plus
any drifted allowlist entry, so its behaviour must not change.

**Prove it by execution, not by grepping for the new branch.** Write the harness from
`## Fixture harness (throwaway — not committed)` at the bottom of this plan to `"${TMPDIR:-/tmp}/vt-hook-fixture.sh"`
and run it with `REPO` set to the repo root. It clones into a `mktemp -d`, copies the working-tree hook into the clone,
and drives six cases off pristine `origin/main` by feeding the hook the
`<local ref> <local sha> <remote ref> <remote sha>` line git supplies on stdin. It runs no `git tag` and no `git push`,
and it asserts the real repo's `*/v*` tag count is unchanged. All six cases must report PASS. The harness stays
throwaway — do not add it to `internal/`.
  </action>
  <verify>
    <automated>shellcheck -e SC1091 -e SC2034 internal/check-version-tags.sh && REPO="$PWD" bash "${TMPDIR:-/tmp}/vt-hook-fixture.sh"</automated>
  </verify>
  <done>
`shellcheck` with the repo ignore set exits 0. The harness exits 0 with PASS on all six cases: A (network-tools,
declares `image:`, untagged) exits 1 with the `404 on update` rationale; B (iac-runner + terraform-bridge, allowlisted,
untagged) exits 0 with exactly two `⊘` skip lines, one naming each add-on, both containing
`built locally by the Supervisor`; C exits 0 via `tag coding-assistants/v1.0.0-2 exists`; D exits 0 via `legacy format`;
E (authentik, no `image:` key but not allowlisted, untagged) exits 1 with the `404 on update` rationale; F (iac-runner
allowlisted but declaring `image:`, untagged) exits 1 with a warning naming `LOCAL_BUILD_ADDONS` and the `404 on update`
rationale. The harness's before/after real-repo tag counts are equal.
  </done>
  </task>

<task type="auto">
  <name>Task 2: Scope the four docs that still claim the release tag is unconditional</name>
  <files>docs/UPDATE_VERSION.md, .github/RELEASE.md, README.md, AGENTS.md</files>
  <action>
Four statements assert that the hook requires a tag for every bumped add-on. After Task 1 each is wrong for the two
allowlisted add-ons. Correct each in place with the smallest edit that states the exception, and use the exact phrase
`built locally by the Supervisor` in every one so the presence check below finds it.

1. `docs/UPDATE_VERSION.md` — the `## Pre-push hook` section, the canonical reference for this hook. Add the exception
   to the opening paragraph alongside the existing legacy-format sentence. State that the exempt set is an explicit
   allowlist in the script (`LOCAL_BUILD_ADDONS`), that it currently holds `iac-runner` and `terraform-bridge`, and that
   an entry is removed once its add-on declares `image:`. Also document the drift behaviour in one sentence: an
   allowlisted add-on that declares `image:` gets a warning and is enforced anyway.
2. `.github/RELEASE.md` — two places. In the numbered "Commit and push the version files" step, the sentence beginning
   `The internal/check-version-tags.sh pre-push hook verifies ...`. And under `## Manual repair`, the sentence
   `The pre-push hook will refuse a branch push until a tag named <addon>/v<version> exists for every modified config.yaml.`
   — "every modified config.yaml" is now false and must be scoped to add-ons not on the allowlist.
3. `README.md` — in the Repository Conventions "Three-file versioning scheme" bullet, the closing sentence
   `A pre-push hook enforces that any bumped version has a matching tag.` Scope it the same way.
4. `AGENTS.md` — the Version Updates bullet that currently notes only the hook's legacy-format tolerance. Add the
   allowlist exception so a future agent does not reinstate the unconditional requirement.

Name the two current members in `docs/UPDATE_VERSION.md` only, since that is the reference doc and the same paragraph
also explains how membership changes. In the other three, describe the rule and point at `LOCAL_BUILD_ADDONS` in
`internal/check-version-tags.sh` as the source of truth rather than duplicating the member list in four places.

Do not restate the nine-add-on `image:` survey or the missing-key question in any of these files — that is planning
context, unsettled, and would rot. Respect the repo's markdown conventions: 120-char prose wrap, and let `prettier`
settle the final wrapping rather than hand-aligning.
  </action>
  <verify>
    <automated>for f in internal/check-version-tags.sh docs/UPDATE_VERSION.md .github/RELEASE.md README.md AGENTS.md; do tr '\n' ' ' < "$f" | tr -s ' ' | grep -qF 'built locally by the Supervisor' || { echo "MISSING PHRASE: $f"; exit 1; }; done && pre-commit run --files docs/UPDATE_VERSION.md .github/RELEASE.md README.md AGENTS.md</automated>
  </verify>
  <done>
All
five files listed in the check contain `built locally by the Supervisor` after newline/whitespace normalisation (the
`tr` normalisation is required — `prettier` may wrap the phrase across a line boundary in the markdown files, which a
plain `grep` would miss). `docs/UPDATE_VERSION.md` names both current allowlist members and documents the drift
behaviour; the other three point at `LOCAL_BUILD_ADDONS` without duplicating the list. `pre-commit run --files` over the
four markdown paths exits 0 with no residual diff.
  </done>
  </task>

<task type="auto">
  <name>Task 3: Make setup-hooks.sh worktree-safe, then reinstall the stale pre-push hook and verify it</name>
  <files>internal/setup-hooks.sh</files>
  <action>
The installed `.git/hooks/pre-push` is a copy from 2026-08-31 that predates `0a85a8a` and contains no `primary_tag`
logic at all. Until it is refreshed, Task 1's edit has zero effect on a real push. Three parts.

**(a) Worktree-safe path derivation — change ONE of two consumers.** `internal/setup-hooks.sh` line 25 sets
`GIT_ROOT=$(git rev-parse --show-toplevel)`, and that variable feeds **two** consumers:

- line 26 `HOOK_TARGET="$GIT_ROOT/.git/hooks/pre-push"` — the one that is wrong
- line 27 `HOOK_SOURCE="$GIT_ROOT/internal/check-version-tags.sh"` — the one that is correct and must keep working

`HOOK_TARGET` is broken in a linked worktree (which is how this batch item executes): there `.git` is a file, not a
directory, so the path cannot be written and the installer cannot do the job this task needs from it. Change line 26
only, to `HOOK_TARGET="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"`, which resolves to the
main repository's `.git` from any worktree (git 2.55 here).

**Leave line 25 exactly as it is, and leave line 27 exactly as it is.** `HOOK_SOURCE` still needs `GIT_ROOT`, and
`--show-toplevel` is the right derivation for it — the source file lives in the working tree, not in `.git`. Do not
"clean up" the now-single-use `GIT_ROOT` by deleting the assignment: that would leave `HOOK_SOURCE` as
`/internal/check-version-tags.sh`, the `[[ -f "$HOOK_SOURCE" ]]` guard on line 28 would take its `else` branch, and the
installer would stop installing the hook while still exiting 0. Part (c)'s hand-rolled copy would mask it, so the
verify block below probes the script's own assignments to catch exactly this.

Change line 26 only — leave the rest of the script, including its `pre-commit run --all-files` sweep and its existing
messages, alone apart from part (b).

**(b) The install summary line.** The script's "Before push" bullet reads
`• Version-tag sync (verifies v<version> tag exists for any bumped addon)`. Qualify it: the check is skipped for the
add-ons on `LOCAL_BUILD_ADDONS` in `internal/check-version-tags.sh`, which are built locally by the Supervisor and never
pulled from ghcr.io.

**(c) Install and verify.** Refresh the installed hook using the same two operations the script performs — copy
`internal/check-version-tags.sh` over `"$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"` and
`chmod +x` it — rather than invoking `./internal/setup-hooks.sh` wholesale. Reason: the script ends with
`pre-commit run --all-files`, which is slow and can fail on matters unrelated to this item, and a failure there would
obscure whether the install itself succeeded. Note in the SUMMARY that the two are equivalent for the hook install and
that running the full script after merge is idempotent.

Be explicit in the SUMMARY that `.git/hooks/` is untracked local state that is never committed, so this step changes the
developer's local push behaviour immediately, before the item is merged — replacing a hook copy that was already stale
and wrong. If the item is later reverted, re-running `./internal/setup-hooks.sh` restores whatever the merged source
says.
  </action>
  <verify>
    <automated>shellcheck -e SC1091 -e SC2034 internal/setup-hooks.sh && bash -n internal/setup-hooks.sh && ( eval "$(grep -E '^(GIT_ROOT|HOOK_TARGET|HOOK_SOURCE)=' internal/setup-hooks.sh)"; test -f "$HOOK_SOURCE" && test -d "$(dirname "$HOOK_TARGET")" ) && HOOK="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push" && diff "$HOOK" internal/check-version-tags.sh && test -x "$HOOK" && tr '\n' ' ' < internal/setup-hooks.sh | tr -s ' ' | grep -qF 'built locally by the Supervisor' && echo "HOOK INSTALLED AND CURRENT"</automated>

  </verify>

  <done>
`shellcheck` on `internal/setup-hooks.sh` exits 0 and `bash -n` parses it.

**The installer-integrity probe passes.** It re-evaluates the script's own `GIT_ROOT` / `HOOK_TARGET` / `HOOK_SOURCE`
assignment lines in a subshell -- grepped straight out of the edited file, so it tests what the file actually says --
and requires `HOOK_SOURCE` to resolve to an existing file and `HOOK_TARGET`'s parent to be an existing directory. This
is the criterion that fails if part (a) broke `HOOK_SOURCE`. Verified during planning against three variants: current
form PASS, `GIT_ROOT` assignment deleted FAIL, post-edit form PASS. Two cheaper checks were tried and rejected as blind
to that break: `bash -n` alone accepts it (valid syntax either way), and a static grep for
`HOOK_SOURCE=.*internal/check-version-tags.sh` still matches, because the break leaves the literal intact and merely
makes `GIT_ROOT` empty.

`diff` between the installed `.git/hooks/pre-push` and `internal/check-version-tags.sh` produces no output, the
installed copy is executable, and `grep -c primary_tag "$HOOK"` is no longer 0. `internal/setup-hooks.sh` derives
`HOOK_TARGET` from `--path-format=absolute --git-common-dir`, still derives `HOOK_SOURCE` from `GIT_ROOT`, and its
"Before push" summary names the allowlist exception.
  </done>
  </task>

</tasks>

<!-- prettier-ignore-end -->

## Fixture harness (throwaway — not committed)

Write this to `"${TMPDIR:-/tmp}/vt-hook-fixture.sh"` and run it from the repo root with `REPO="$PWD"`. It only clones
and commits inside a `mktemp -d`; it runs no `git tag` and no `git push`, and it asserts the real repo's add-on tag
count is unchanged.

```bash
#!/usr/bin/env bash
# Throwaway proof harness for internal/check-version-tags.sh. Do NOT commit.
# Runs the WORKING-TREE hook against a temp clone. Creates/pushes no tag.
set -u
REPO="${REPO:-$PWD}"
BEFORE=$(git -C "$REPO" tag -l '*/v*' | wc -l)
WORK=$(mktemp -d)
git clone --quiet "$REPO" "$WORK/clone" || exit 1
cp "$REPO/internal/check-version-tags.sh" "$WORK/clone/internal/check-version-tags.sh"
cd "$WORK/clone" || exit 1
git config user.email fixture@local
git config user.name fixture
FAILED=0
LAST_OUT=""

new_case() { git checkout --quiet -B "fixture-$1" origin/main; }

# bump <addon> <config_version> <build_version>
bump() {
    sed -i -E "0,/^version:/s|^version:.*|version: \"$2\"|" "$1/config.yaml"
    sed -i -E "0,/^[[:space:]]*VERSION:/s|^([[:space:]]*)VERSION:.*|\1VERSION: \"$3\"|" "$1/build.yaml"
}

# run_case <label> <expected_exit> [needle ...] -- every needle must match
run_case() {
    local label="$1" want="$2"
    shift 2
    local out rc flat n ok=1
    out=$(printf 'refs/heads/main %s refs/heads/main %s\n' \
        "$(git rev-parse HEAD)" "$(git rev-parse HEAD~1)" \
        | bash internal/check-version-tags.sh 2>&1)
    rc=$?
    LAST_OUT="$out"
    flat=$(printf '%s' "$out" | tr '\n' ' ' | tr -s ' ')
    [[ "$rc" == "$want" ]] || ok=0
    for n in "$@"; do
        printf '%s' "$flat" | grep -qF -- "$n" || ok=0
    done
    if [[ "$ok" == 1 ]]; then
        echo "PASS  $label (exit $rc)"
    else
        echo "FAIL  $label (exit $rc, want $want)"
        printf '%s\n' "$out"
        FAILED=1
    fi
}

# A: declares image:, untagged -> must STILL BLOCK (ghcr 404 guard intact)
new_case a
bump network-tools 99.99.99-0 99.99.99
git commit --quiet -am "fixture A" || FAILED=1
run_case "A network-tools (image:) untagged -> blocked" 1 "404 on update"

# B: both allowlisted add-ons, untagged -> PASS via skip branch, exactly 2 skips
new_case b
bump iac-runner 99.99.99-0 99.99.99
bump terraform-bridge 99.99.99-0 99.99.99
git commit --quiet -am "fixture B" || FAILED=1
run_case "B allowlisted pair untagged -> skipped" 0 \
    "iac-runner: built locally by the Supervisor" \
    "terraform-bridge: built locally by the Supervisor"
SKIPS=$(printf '%s\n' "$LAST_OUT" | grep -cF '⊘' || true)
if [[ "$SKIPS" != 2 ]]; then
    echo "FAIL  B expected exactly 2 skip lines, got $SKIPS"
    FAILED=1
fi

# C: declares image:, primary subpatch tag exists -> untouched primary_tag path
new_case c
printf '\n# fixture\n' >> coding-assistants/build.yaml
git commit --quiet -am "fixture C" || FAILED=1
run_case "C coding-assistants (image:) primary tag -> ok" 0 \
    "tag coding-assistants/v1.0.0-2 exists"

# D: declares image:, only legacy no-subpatch tag exists -> legacy_tag path
new_case d
bump coding-assistants 1.0.0-9 1.0.0
git commit --quiet -am "fixture D" || FAILED=1
run_case "D coding-assistants (image:) legacy tag -> ok" 0 "legacy format"

# E: no image: key but NOT allowlisted -> must still BLOCK
new_case e
bump authentik 99.99.99-0 99.99.99
git commit --quiet -am "fixture E" || FAILED=1
run_case "E authentik (no image:, not allowlisted) -> blocked" 1 \
    "authentik" "404 on update"

# F: allowlisted BUT config.yaml now declares image: -> stale allowlist.
#    Must warn and fall through to enforcement. Exit 1 + the drift warning
#    prove it enforced instead of skipping; no negative grep needed.
new_case f
bump iac-runner 99.99.99-0 99.99.99
printf '\nimage: "ghcr.io/fixture/{arch}-iac_runner"\n' >> iac-runner/config.yaml
git commit --quiet -am "fixture F" || FAILED=1
run_case "F iac-runner allowlisted + image: -> warn and enforce" 1 \
    "LOCAL_BUILD_ADDONS" "404 on update"

AFTER=$(git -C "$REPO" tag -l '*/v*' | wc -l)
echo "---"
echo "real-repo addon tags before=$BEFORE after=$AFTER"
[[ "$BEFORE" == "$AFTER" ]] || { echo "FAIL  harness mutated real-repo tags"; FAILED=1; }
echo "throwaway clone: $WORK/clone"
exit "$FAILED"
```

Notes for the executor:

- Cases A, B, E and F use `99.99.99-0` on purpose. No tag for that version exists or plausibly could, so an outcome
  there can only come from the branch under test, never from a pre-existing tag.
- Case C changes only `build.yaml` (an appended comment) so `config_version` stays at the already-tagged `1.0.0-2`; the
  hook still collects the directory because the diff touches a dir holding both `config.yaml` and `build.yaml`.
- Case E bumps `authentik` rather than reading its current version, because `authentik` at `2026.8.1-0` passes today
  only via its legacy tag `authentik/v2026.8.1` — leaving it alone would pass the case for the wrong reason.
- Case F asserts on exit code plus two positive needles and deliberately uses no "must not contain" check. Exit 1 can
  only originate from `iac-runner` (it is the only add-on that case touches), and the `LOCAL_BUILD_ADDONS` needle proves
  the drift branch fired, so together they prove enforcement rather than a skip without any negative grep.
- A broken fixture fails closed: if a `git commit` finds nothing staged, the diff range is empty, the hook exits 0
  silently, and the needle check fails the case rather than reporting a false PASS.
- `git clone` copies the repo's tags, so the primary/legacy positive paths are exercisable offline; `tag_exists`'
  `git ls-remote origin` fallback resolves against the local clone source, so no network is needed.

**Verified RED baseline (harness extracted from this plan, `shellcheck`-clean, run against the unmodified hook on the
current `main` working tree).** Observed output:

```text
PASS  A network-tools (image:) untagged -> blocked (exit 1)
FAIL  B allowlisted pair untagged -> skipped (exit 1, want 0)
FAIL  B expected exactly 2 skip lines, got 0
PASS  C coding-assistants (image:) primary tag -> ok (exit 0)
PASS  D coding-assistants (image:) legacy tag -> ok (exit 0)
PASS  E authentik (no image:, not allowlisted) -> blocked (exit 1)
FAIL  F iac-runner allowlisted + image: -> warn and enforce (exit 1, want 1)
---
real-repo addon tags before=39 after=39
```

Harness exit was 1. B is the bug being fixed. F already exits 1 for the right _reason_ today (no tag) but fails on the
missing `LOCAL_BUILD_ADDONS` needle, which is what gives that case its discriminating power — the needle, not the exit
code, detects the drift branch. **A, C, D and E already pass and must still pass after the edit**: they are the
regression fence, especially E, which is the user's decision that the five non-allowlisted keyless add-ons stay
enforced. The GREEN target for Task 1 is all six cases PASS, harness exit 0, real-repo tag count still equal. If A, C, D
or E flips to FAIL, the edit reached past the new branch into the `primary_tag` / `legacy_tag` region and must be
narrowed.

<threat_model>

## Trust Boundaries

| Boundary                                    | Description                                                                                                                                     |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| developer workstation → `origin` (git push) | `internal/check-version-tags.sh`, installed as `.git/hooks/pre-push`, is the guard that decides whether a branch push crosses                   |
| `LOCAL_BUILD_ADDONS` → hook control flow    | a hand-maintained in-script allowlist decides whether the guard enforces or skips; membership is an assertion about the world that can go stale |
| in-repo `config.yaml` → drift guard         | repo-controlled file content decides whether an allowlist entry is still trustworthy                                                            |
| HA Supervisor → ghcr.io (image pull)        | the failure the hook exists to prevent (404 on update) lives here, and only for add-ons the Supervisor actually pulls                           |
| source script → `.git/hooks/pre-push` copy  | the guard that runs is a stale copy, not the tracked file; the two drift silently                                                               |

## STRIDE Threat Register

| Threat ID | Category    | Component                                                                   | Severity | Disposition | Mitigation Plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --------- | ----------- | --------------------------------------------------------------------------- | -------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-pfq-01  | Tampering   | `LOCAL_BUILD_ADDONS` — adding an entry disables the guard for that add-on   | low      | accept      | This is the protection deliberately given up, and the allowlist is what keeps it narrow: exactly `iac-runner` and `terraform-bridge`, down from the seven that the superseded `image:`-absence rule would have exempted. Editing the array is a visible source change in a tracked file, reviewable in a diff — unlike the previous design, where deleting a key from a config.yaml would have silently moved an add-on out of scope. The guard is a developer-convenience nag, not a security control; `git push --no-verify` already bypasses it and is documented                                                                                                                                                                                                                                                       |
| T-pfq-02  | DoS         | HA Supervisor update path for the seven non-allowlisted add-ons             | high     | mitigate    | Enforcement must stay fully intact for all seven. Proven by execution, not inspection: fixture case A (`network-tools`, declares `image:`) and case E (`authentik`, no key, not allowlisted) both require exit 1 plus the `404 on update` rationale, and cases C and D require the untouched primary_tag and legacy_tag paths to still resolve. Everything in the loop apart from the inserted block is unmodified: the `VERSION:`-anchoring comment, both version extractions, the empty-version guard, `primary_tag`, `legacy_tag`, both `tag_exists` calls, the failure message, `errored`, and the trailing exit block. (Stated as an enumeration, not a line range -- insertion (b) lands after line 71, so any single range would span it.) Case E is the specific fence for the five add-ons the user kept in scope |
| T-pfq-03  | Spoofing    | a stale allowlist entry that has since gained an `image:` key               | medium   | mitigate    | An entry claiming "built locally" for an add-on the Supervisor now pulls would reintroduce the 404. The drift guard re-reads `config.yaml` on every push and, on finding a top-level `image:`, warns and falls through to the normal tag check instead of skipping — fail-safe, so protection is restored without anyone reading the warning. Fixture case F proves it: exit 1 plus a warning naming `LOCAL_BUILD_ADDONS`                                                                                                                                                                                                                                                                                                                                                                                                  |
| T-pfq-04  | Tampering   | the drift guard's `image:` regex (false negative → silent skip)             | medium   | mitigate    | `^`-anchored `grep -qE` requiring a non-blank value: an indented sub-key, a commented `# image:` line, or an empty value cannot satisfy it, and `image` is a top-level HA manifest key so the anchor is exact. `yq` is rejected because HA `config.yaml` needs `--unsafe` for custom tags (per `CLAUDE.md`) and the hook must carry no tool dependency as a bare `.git/hooks` copy                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| T-pfq-05  | Repudiation | release traceability for the two allowlisted add-ons                        | low      | accept      | Without the nag, `iac-runner` and `terraform-bridge` can ship a version bump with no tag marking which commit produced it. Compensating controls remain: `validate-versions.sh` still enforces the 3-file version sync on every commit, and `make release` / `update-version.py` still create and push the tag by default (explicitly left unchanged). Only the push-time refusal is relaxed, and only for two add-ons. Noted consequence: `terraform-bridge` has an active `v*` tag trigger, so its ghcr build now needs `workflow_dispatch` or the `paths:` trigger instead of the release nag                                                                                                                                                                                                                           |
| T-pfq-06  | Tampering   | allowlist as maintenance burden — new locally-built add-ons and stale names | low      | accept      | The deliberate trade for not weakening enforcement repo-wide. A future add-on with no `image:` key gets no automatic exemption: it will be nagged until someone adds it to the array, which is the intended prompt to decide whether it should instead have an `image:` key. The other drift direction — an entry naming a renamed or removed directory — is inert rather than detected, since the loop only iterates add-on directories a push actually modified; detecting it would need a repo-wide sweep the hook does not otherwise do. Both are documented in the array's comment and in `docs/UPDATE_VERSION.md`                                                                                                                                                                                                    |
| T-pfq-07  | Tampering   | `.git/hooks/pre-push` diverging from the tracked source                     | medium   | mitigate    | Verified real: the installed copy is dated 2026-08-31 and contains zero occurrences of `primary_tag` against 8 in the source, so the guard that ran on today's push predates `0a85a8a` entirely. Any conclusion drawn from "the hook allowed/blocked this" is unsound while they diverge. Task 3 reinstalls the copy and verifies with `diff` plus an executable-bit check, and makes `internal/setup-hooks.sh` able to do this from a linked worktree at all                                                                                                                                                                                                                                                                                                                                                              |
| T-pfq-08  | Tampering   | the verification harness writing to the real repository                     | medium   | mitigate    | The harness runs entirely inside `mktemp -d`, copies the hook into a clone, and issues no `git tag` or `git push` at any point. It captures `git tag -l '*/v*'` in the real repo before and after and fails if the counts differ — observed equal at 39 in the recorded RED baseline                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| T-pfq-SC  | Tampering   | npm/pip/cargo installs                                                      | low      | n/a         | This plan installs no packages. It invokes only `shellcheck` and `pre-commit`, both already pinned in `.pre-commit-config.yaml`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

Blocking threshold is `high`: T-pfq-02 is the only high-severity entry and is dispositioned `mitigate` with runnable
proofs (fixture cases A and E) rather than an assertion.

</threat_model>

<verification>
1. `shellcheck -e SC1091 -e SC2034 internal/check-version-tags.sh internal/setup-hooks.sh` exits 0.
2. `REPO="$PWD" bash "${TMPDIR:-/tmp}/vt-hook-fixture.sh"` reports PASS for all six cases A-F, reports equal
   before/after real-repo tag counts, and exits 0.
3. `HOOK="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"; diff "$HOOK"
   internal/check-version-tags.sh` produces no output, and `test -x "$HOOK"` succeeds.
4. `pre-commit run --files internal/check-version-tags.sh internal/setup-hooks.sh docs/UPDATE_VERSION.md
   .github/RELEASE.md README.md AGENTS.md` exits 0.
5. `git diff --stat` touches exactly the six files in `files_modified` — no add-on `config.yaml`, `build.yaml` or
   `README.md` version is modified by this item, and no fixture script is added to `internal/`.
6. Manual read-back: the diff of `internal/check-version-tags.sh` adds only the `LOCAL_BUILD_ADDONS` array, the
   `is_local_build` helper, and the skip-plus-drift branch; the `primary_tag` / `legacy_tag` region is absent from the
   diff.
</verification>

<success_criteria>

- Pushing a branch that bumps `iac-runner` or `terraform-bridge` no longer demands a release tag, and prints one visible
  `⊘` line per add-on saying why instead of passing silently.
- Pushing a branch that bumps any of the other seven add-ons without a matching tag still fails with the unchanged
  ghcr-404 message, and the primary/legacy subpatch tag resolution still works for them. `authentik` and the other four
  keyless-but-not-allowlisted add-ons are explicitly unaffected, per the user's decision.
- An allowlisted add-on that acquires an `image:` key is warned about by name and enforced anyway — never silently
  skipped.
- Adding or removing an exempt add-on is a one-line edit to a single clearly-named array, with the criterion for
  membership and for removal stated in the comment above it.
- The hook that actually runs on a push is the one this item edited: `diff` against `.git/hooks/pre-push` is empty,
  replacing a copy that was six commits and eight days stale.
- The SUMMARY records: the superseded `image:`-absence design and why the user narrowed it to two add-ons; that
  `terraform-bridge`'s ghcr build now needs `workflow_dispatch` or the `paths:` trigger rather than the release nag;
  that `.git/hooks/` is untracked local state changed before merge; and that `internal/update-version.py`'s
  unconditional tagging plus the missing-`image:`-key question for the five remain out of scope. </success_criteria>

<output>
Create `.planning/quick/make-the-pre-push-version-tag-hook-stop-demanding-a-release/260908-pfq-SUMMARY.md` when done.
</output>
