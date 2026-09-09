---
phase: quick-260909-wgm
plan: 01
type: execute
wave: 1
quick_id: 260909-wgm
depends_on: []
files_modified:
  - internal/check-version-tags.sh
  - internal/setup-hooks.sh
  - internal/verify-image-availability.sh
  - .planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
autonomous: true
requirements:
  - QUICK-260909-wgm-a
  - QUICK-260909-wgm-b
  - QUICK-260909-wgm-c
  - QUICK-260909-wgm-d
  - QUICK-260909-wgm-e

estimate:
  tokens: 55000
  raw_tokens: 55000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "A push whose range bumps a non-allowlisted add-on's version with no `<addon>/v<version>` tag prints a warning and the hook exits 0 (D-01, QUICK-260909-wgm-a)."
    - "A push touching an add-on on `LOCAL_BUILD_ADDONS` with no top-level `image:` key still prints the `⊘ … release tag not required` skip line and exits 0 — unchanged (D-02, QUICK-260909-wgm-b)."
    - "A push touching an allowlisted add-on that HAS a top-level `image:` key still prints the drift warning naming `LOCAL_BUILD_ADDONS`, then reports the missing tag advisorily, and exits 0 — the drift text no longer claims the requirement is applied (D-02, QUICK-260909-wgm-b)."
    - "The hook's header and its user-facing missing-tag message describe the measured mechanism: `internal/dispatch-builds.sh` + `workflow_dispatch` publish images, `.github/workflows/verify-image-availability.yml` is the control that catches a genuinely missing one, the tag is a release marker (D-03, QUICK-260909-wgm-c)."
    - "No blocking path remains: the comment-stripped script contains no non-zero exit and no leftover error-accumulator variable; the only exit is the terminal success (QUICK-260909-wgm-d)."
    - "`260909-rln-PLAN.md` is true again about this file: the pinned code hash matches the post-change file, and every claim about the file's baseline names quick task 260909-wgm (D-04, QUICK-260909-wgm-e)."
    - "`.git/hooks/pre-push` is byte-identical to the reworked `internal/check-version-tags.sh`, so the developer's next push actually gets the new behaviour."
  artifacts:
    - internal/check-version-tags.sh
    - internal/setup-hooks.sh
    - internal/verify-image-availability.sh
    - .planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
  key_links:
    - "hook stdin contract → `git diff --name-only $range` → `config.yaml`/`build.yaml` version extraction → `tag_exists` → warning → exit 0 (the one path the behavioural gate drives end-to-end)."
    - "`internal/verify-image-availability.sh`'s comment citation into this hook — a numeric line citation that this task's edit invalidates."
    - "`260909-rln-PLAN.md` GATE-G3-6 → `grep -v '^#' internal/check-version-tags.sh | sha256sum` — the pin this task's code change breaks."
    - "`internal/setup-hooks.sh`'s installed-hook description → the same enforcement claim, restated to the developer at install time."
---

<objective>
Downgrade the pre-push release-tag check from blocking to advisory, correct the two false
rationale claims it states, and re-pin the collision this creates in the pending batch item
`260909-rln`.

Purpose: batch item `260909-rll` added `--no-tag` to `.github/workflows/auto-update.yml`, so the
nightly bot no longer creates `<addon>/v<version>` tags — while `internal/check-version-tags.sh`
still exits 1 when one is missing. Every nightly bump therefore refuses the next human push until
someone tags by hand (it happened twice last session: `authentik/v2026.8.2-0`,
`meridian/v1.69.0-0`). The tag's remaining value is as a release marker, and a release marker must
not block a push (D-01).

Output: an advisory hook whose header and messages state the measured mechanism (D-03), a retained
`LOCAL_BUILD_ADDONS` allowlist and `image:`-drift guard whose wording stops claiming enforcement
(D-02), and a `260909-rln-PLAN.md` that is true again about this file (D-04).

This is one vertical slice, not a layered phase: Task 1 is the whole end-to-end change and carries
an end-to-end behavioural gate (pre-push stdin → exit status), so the tracer and the expansion
coincide. Task 2 is the documentation collision it creates.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/HANDOVER-260909-rli.md
@internal/check-version-tags.sh
@internal/setup-hooks.sh
</context>

<verified_environment>
Measured live at planning time (2026-09-09) at `git rev-parse HEAD` =
`74c8066e681a674e2dcbd4e0b11e97d69791dc0d`, working tree clean for every file below. Handover §3.7
is explicit that every line number and hash inside an existing plan is stale — nothing here was
copied from `260909-rln-PLAN.md`; all of it was re-measured. Do NOT re-derive these; do NOT
contradict them.

| Fact | Measured value |
|---|---|
| `internal/check-version-tags.sh` | 183 lines, clean at `74c8066` |
| `grep -v '^#' internal/check-version-tags.sh \| sha256sum` | `5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249` — still equal to the value `260909-rln-PLAN.md` pins, so the pin is correct TODAY and Task 1 is what breaks it |
| `sha256sum internal/check-version-tags.sh` (whole file) | `d8616e29329fecd1414894b62da4f195222f8a860690dc031dd80ec47112cea0` |
| `is_local_build` region `sed -n '/^is_local_build()/,/^}/p'` | `37e332d28832efcbd8e523f28bffc9184520c3e69b749616c1eb37afc87d0cb9` |
| `tag_exists` region `sed -n '/^tag_exists()/,/^}/p'` | `61d94dced1fc82a611fea172d8d374cc8049823786a9d1e486f740de038a6b36` |
| array region `sed -n '/^LOCAL_BUILD_ADDONS=(/,/^)/p'` | `cfbe5d35d8b64b212ebe40d52189c4f42c5bd9f5c2e1dbd4f5bdb67d77ca80d7` (the array only — its column-1 comment block is ABOVE the range and is free to be reworded) |
| collection loop `sed -n '/^set -e$/,/^modified_addons=\$(printf/p'` | `714847bbf5466932f5e90fc1b4ffcad4a6690cecef2d964d02c7b5840801343d` |
| version-extraction region `sed -n '/^while IFS= read -r addon_dir/,/^    \[\[ -z "\$build_version"/p'` | `8e077b1e48533cf297ccb57cc5f345c7c23a5f619f07ac0e7b71c2cb94efa9f8` |
| comment-stripped `exit 1` count | **1** (the terminal blocking exit) |
| comment-stripped error-accumulator-variable count | **3** |
| comment-stripped arithmetic-COMMAND form `((`…`))` count | **0** — must stay 0, see the `set -e` hazard in Task 1 |
| `grep -c 'every workflow also triggers on'` | **1** (the false causal claim; `260909-rln`'s GATE-G3-6 negative-greps it) |
| `grep -cF '.github/workflows/build-'` | **1** (line 2 of the header; one of the **3** repo-wide references `260909-rln`'s G3-8 baseline records) |
| `grep -cF 'build.yml'` | **0** — and it must STAY 0: `.github/workflows/build.yml` does not exist yet, `260909-rln` creates it, and its GATE-G3-6 `grep -q 'build\.yml'` clause is work-proving for that item |
| `grep -c 'ghcr'` | **7** — GATE-G3-6 requires ≥1 to survive |
| add-ons where BOTH `<addon>/v<config_version>` and `<addon>/v<build_version>` are absent locally | **none** (gatus, phone-logger and iac-runner miss only the subpatch form and hit the legacy branch) — so the missing-tag branch is NOT reachable from any real add-on directory today, which is why the behavioural gate builds a throwaway fixture repo |
| behavioural baseline, untagged non-allowlisted add-on | hook **exit 1**, prints `❌ …`, then the aggregate failure line |
| behavioural baseline, `iac-runner` with no `image:` key | hook **exit 0**, prints the `⊘` skip line |
| behavioural baseline, `iac-runner` WITH a top-level `image:` key | hook **exit 1**, prints the drift warning and then the `❌` block |
| lines over 120 columns | `internal/check-version-tags.sh` **2** (lines 111 and 114, both inside the hash-pinned version-extraction region), `internal/setup-hooks.sh` **0**, `internal/verify-image-availability.sh` **19** — no hook enforces a column limit on shell files here, so the gate asserts non-increase, not zero |
| `internal/setup-hooks.sh` install-time claim | the literal `verifies v<version> tag exists` occurs **1**× |
| `.git/hooks/pre-push` | present and byte-identical to the repo file — so it will DRIFT the moment Task 1 edits the repo copy |
| `internal/verify-image-availability.sh` | cites `check-version-tags.sh:121-126` in a comment — a numeric citation that Task 1's edit shifts |
| `internal/setup-hooks.sh` | tells the developer the pre-push hook "verifies v<version> tag exists for any bumped addon" — the same enforcement claim, restated at install time |
| `shellcheck` / `pre-commit` on PATH | 0.11.0 / yes |
| `.prettierignore` + `.markdownlint-cli2.yaml` | both exclude `.planning/`, so neither plan file is reflowed or line-length-linted; files OUTSIDE it are |
| `260909-rln-PLAN.md` | 1591 lines; full stale hash literal ×**3**, truncated `5f310c2e…019249` ×**1**, `, unchanged from baseline, with` ×**1**, `hash-proven a comment-only change` ×**1**, `check-version-tags.sh:2` ×**2**, `lines 34-40` ×**1**, `lines 1-8` ×**1**, `header (lines 2-7)` ×**1**, `51-77` ×**1**, `260909-wgm` ×**0** |
| `.github/workflows/build.yml` exists | **false** — `260909-rln` has not landed; Task 1's precondition asserts this |
</verified_environment>

<locked_decisions>
Restated from the task brief. NOT open for revisiting.

- **D-01 Downgrade, do not drop.** The hook keeps detecting and reporting a missing release tag but
  MUST NOT fail the push. The missing-tag branch becomes a warning; the script's exit status for
  that condition is 0.
- **D-02 The allowlist and its drift guard stay.** `LOCAL_BUILD_ADDONS` and the top-level `image:`
  drift guard still carry correct information and are not deleted. The drift guard's wording must
  stop claiming an enforcement that no longer exists.
- **D-03 Correct the rationale in the same change.** Header comment AND user-facing message text
  describe the real mechanism: images come from `internal/dispatch-builds.sh` via
  `workflow_dispatch`, `.github/workflows/verify-image-availability.yml` is the guard that catches
  a genuinely missing image, and the tag is a release marker only. State only what the handover
  measured; invent no new rationale.
- **D-04 Re-pin the `260909-rln` collision in the same quick task.** `260909-rln-PLAN.md` must be
  true again about this file after Task 1: recomputed code hash substituted, every claim about the
  file's baseline corrected, and GATE-G3-6's other assertions dispositioned in writing rather than
  left as a silent no-op.

**One honest note on D-04's wording, resolved rather than revisited.** The brief says the
"comment-only" claims "become false the moment this task lands". Precisely: `260909-rln`'s OWN
Task-3 edit to this file remains comment-only — what becomes false is the BASELINE those claims are
measured against, because `260909-wgm`'s change is not comment-only. Task 2 therefore makes each
claim explicit about which tree it is relative to and names `260909-wgm` as the intervening change,
rather than deleting sentences that are still true of `260909-rln`'s own scope. Same outcome the
decision demands — every claim in that plan reads true — without introducing a fresh falsehood in
the other direction.
</locked_decisions>

<tasks>

<task type="auto">
  <name>Task 1: Make the missing release tag advisory and state the measured rationale</name>
  <files>internal/check-version-tags.sh, internal/setup-hooks.sh, internal/verify-image-availability.sh</files>
  <precondition>`git rev-parse HEAD` is `74c8066e681a674e2dcbd4e0b11e97d69791dc0d` or a descendant in which `grep -v '^#' internal/check-version-tags.sh | sha256sum` still equals `5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249`, `git status --porcelain -- internal/check-version-tags.sh internal/setup-hooks.sh internal/verify-image-availability.sh` is empty, and `[ -f .github/workflows/build.yml ]` is FALSE. If the hash differs, HALT and re-measure every region hash in `<verified_environment>` before editing — the gates below pin five regions and would reject correct work against a moved baseline. If `build.yml` exists, `260909-rln` landed first and HALT: its header rewrite and this one must then be reconciled in one pass instead of two.</precondition>
  <reversibility rating="reversible">One revert restores the blocking behaviour; no data, no remote state, no published artifact is touched.</reversibility>
  <read_first>
`internal/check-version-tags.sh` in full — all 183 lines, once. Extract in that single pass: the
header block, the column-1 comment block above the allowlist array, the two `set -e` hazard
comments on `is_local_build`, the drift-guard `echo` block inside the loop, the missing-tag `echo`
block, and the terminal aggregate block. Also `internal/setup-hooks.sh`'s closing "Before push:"
description, and the `config.yaml parsing` comment header in
`internal/verify-image-availability.sh` (the one carrying a numeric citation into this hook).
Handover §2.1 for what was measured false, §3.4/§3.5 for what the surviving control actually
proves.
  </read_first>
  <action>
Four edits in `internal/check-version-tags.sh`, plus two one-line prose corrections in its two
citing files. Nothing else in any of the three files changes.

**1. Rewrite the whole header comment block (D-03).** Replace every comment line between the
shebang and the blank line before `set -e`. Every replacement line MUST begin at column 1 — the
downstream pin in `260909-rln` uses `grep -v '^#'`, which strips only column-1 comments, so an
indented header line would be counted as code. Do not touch line 1, the shebang. The rewritten
header must state, and state only, these measured facts: the hook reports add-ons whose bumped
`config.yaml`/`build.yaml` version reaches `main` without a matching `<addon>/v<version>` tag; it
is advisory and never fails the push; images are published by `internal/dispatch-builds.sh` via
`workflow_dispatch`, driven by `.github/workflows/auto-update.yml` and
`.github/workflows/base-image-update.yml`; `.github/workflows/verify-image-availability.yml`
re-checks four times daily, with no registry credential, that every version a `config.yaml`
advertises is anonymously pullable from `ghcr.io`, and that check — not this hook — is what
catches a genuinely missing image; the tag's remaining role is as a release marker, and a release
marker must not block a push. Keep the existing `Install via ./internal/setup-hooks.sh.` sentence
verbatim. The header must retain the literal `ghcr` (a downstream gate requires it). It must NOT
contain any `.github/workflows/build-<addon>.yml` path, must NOT restate the deleted causal claim
that a tag push triggers a per-add-on workflow, and must NOT mention `build.yml` — that workflow
does not exist yet, `260909-rln` creates it, and naming it now would be a fresh false statement as
well as disarming that item's own work-proving clause.
Both prohibitions are file-WIDE, comments included — that is the point of them, so the two gates
below deliberately grep the whole file rather than the comment-stripped body, and there is no
legitimate comment that may carry either literal.
<!-- planner-discipline-allow: .github/workflows/build- -->
<!-- planner-discipline-allow: build.yml -->

**2. Reword the enforcement claim in the column-1 comment block above `LOCAL_BUILD_ADDONS`, and in
the drift-guard `echo` block inside the loop (D-02).** Both currently assert that the drift guard
applies the tag requirement anyway. Keep the array, keep the guard, keep the `grep -qE '^image:…'`
test and its `grep, not yq` justification exactly as they are. Change only the claim: the drift
guard detects the case, warns, and falls through to the advisory tag report — and the allowlist
entry must still be corrected by hand. The instruction to remove the add-on from the array stays.
Do not reintroduce any word asserting that the requirement is applied or upheld; a downstream gate
negative-greps the drift path's OUTPUT for that claim.

**3. Downgrade the missing-tag branch (D-01).** The branch keeps detecting and reporting; it stops
failing. Concretely: the per-add-on report becomes a warning — reuse the `⚠️` glyph already
established as the warn glyph in `internal/verify-image-availability.sh`, keep naming the expected
`<addon>/v<config_version>` tag and the legacy fallback, keep both `Fix options` lines
(`make release ADDON=… VERSION=…` and the manual `git tag -a` / `git push origin` pair, which
remain the right thing to do for a release marker), and replace the ghcr-404 causal paragraph with
the same corrected mechanism as the header: the image is published by `internal/dispatch-builds.sh`
via `workflow_dispatch`, `.github/workflows/verify-image-availability.yml` is what would catch a
genuinely missing image, and the tag is a release marker. The message must contain the literals
`release marker` and `verify-image-availability`.

**4. Remove the blocking machinery without leaving dead code.** The error-accumulator variable and
the terminal block that reads it and exits non-zero must both go — nothing blocks any more, so
leaving them would read as if something still did. Replace them with a coherent advisory
aggregate: an integer counter incremented in the missing-tag branch, and a terminal `if` that
prints one summary line stating the count and that it is advisory only and the push continues. The
script's last statement stays the existing terminal `exit 0`. <!-- planner-discipline-allow: errored --> <!-- planner-discipline-allow: exit 1 -->
**Two `set -e` hazards, both mandatory.** (a) Increment ONLY with the arithmetic-expansion
assignment form `count=$((count + 1))`. The arithmetic-command form aborts the hook under `set -e`
whenever the pre-increment value is 0 — which is exactly the first warning — and the behavioural
gate below would then see a non-zero exit and a missing summary line. Leave a short comment saying
so. (b) The two existing hazard properties are preserved unchanged and are pinned by region hash:
`is_local_build` is still called only as an `if` condition and still spells its comparison as a
full `if` rather than a `&&` return, and `tag_exists` is unchanged. Both function regions and their
comments must come out byte-identical.

**5. `internal/setup-hooks.sh` (D-03, one line).** Its closing "Before push:" bullet tells the
developer the hook verifies that the tag exists. Restate it as what the hook now does: warns when
the `v<version>` release marker is missing and never blocks the push. Leave the following two
`LOCAL_BUILD_ADDONS` explanation lines and every other line of that file alone.

**6. `internal/verify-image-availability.sh` (one comment line).** Its `config.yaml parsing`
comment header cites this hook by a numeric line range for the `grep, not yq` reasoning. Task 1
shifts those numbers. Replace the numeric citation with a content anchor naming the comment it
points at (the `image:` grep justification in `internal/check-version-tags.sh`) so the citation
cannot go stale again. Change nothing else in that file — it is a sibling deliverable from
`260909-rlk`, and its `Output vocabulary, matching internal/check-version-tags.sh exactly` claim
stays true because `⚠️` remains the warn glyph and `❌` remains the fail glyph in both scripts.

**7. Reinstall the hook.** `internal/setup-hooks.sh` installs the pre-push hook as a bare COPY, so
the repo edit does not reach the developer's next push on its own. Copy the reworked file over
`"$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"` and `chmod +x` it. Do
NOT run `internal/setup-hooks.sh` itself for this — it also runs `pre-commit run --all-files`,
which is red on this repo for pre-existing reasons unrelated to this task.

No tool dependency may be introduced anywhere in the hook: it runs as a bare `.git/hooks` copy,
which is why it uses `grep`/`sed` and no `yq` and no `python`. The comment saying so stays true.
Do not add a line over 120 columns to any of the three files, but do NOT reflow the ones already
there: `internal/check-version-tags.sh` carries **2** (both inside the hash-pinned
version-extraction region, so shortening them would trip the region gate) and
`internal/verify-image-availability.sh` carries **19**. No hook enforces a column limit on shell
files in this repo — prettier and markdownlint apply to Markdown only — so the gate asserts the
count does not RISE from those measured baselines.
  </action>
  <verify>
    <automated>set -u
p=$(mktemp) || exit 1
cat > "$p" <<'PROBE'
#!/usr/bin/env bash
set -u
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
hook=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); addon=$2; want_image=${3:-}
t=$(mktemp -d) || exit 99
cd "$t" || exit 99
git init -q -b main .
git config user.email probe@example.invalid
git config user.name probe
echo unrelated > README.md
git add -A
git commit -q -m base
mkdir -p "$addon"
{
    printf 'name: probe\nversion: "9.9.9-9"\n'
    if [ "$want_image" = image ]; then printf 'image: ghcr.io/example/%s\n' "$addon"; fi
} > "$addon/config.yaml"
printf 'args:\n  VERSION: "9.9.9"\n' > "$addon/build.yaml"
git add -A
git commit -q -m bump
head=$(git rev-parse HEAD) || exit 98
base=$(git rev-parse HEAD~1) || exit 98
case "$head$base" in *[!0-9a-f]* | ?????????????????????????????????????????????????????????????????????????????????) echo "PROBE-SETUP-BROKEN"; exit 98;; esac
cp "$hook" ./hook.sh
set +e
out=$(printf 'refs/heads/main %s refs/heads/main %s\n' "$head" "$base" | bash ./hook.sh 2>&1)
rc=$?
printf 'RC=%s\n%s\n' "$rc" "$out"
cd /
rm -rf "$t"
exit 0
PROBE
h=internal/check-version-tags.sh
old=$(mktemp); git show 74c8066:"$h" > "$old"
A=$(bash "$p" "$h" zzz-probe); B=$(bash "$p" "$h" iac-runner)
C=$(bash "$p" "$h" iac-runner image); D=$(bash "$p" "$old" zzz-probe)
bad=0
want() { printf '%s\n' "$2" | grep -qF "$3" || { echo "FAIL $1: missing [$3]"; bad=1; }; }
deny() { printf '%s\n' "$2" | grep -qF "$3" && { echo "FAIL $1: forbidden [$3]"; bad=1; }; }
rcis() { [ "$(printf '%s\n' "$2" | head -1)" = "RC=$3" ] || { echo "FAIL $1: $(printf '%s\n' "$2" | head -1) != RC=$3"; bad=1; }; }
rcis A "$A" 0; want A "$A" 'zzz-probe/v9.9.9-9'; want A "$A" 'release marker'
want A "$A" 'advisory'; want A "$A" 'verify-image-availability'; deny A "$A" 'Pre-push check failed'
rcis B "$B" 0; want B "$B" 'built locally by the Supervisor'; want B "$B" 'release tag not required'
rcis C "$C" 0; want C "$C" 'LOCAL_BUILD_ADDONS'; want C "$C" 'advisory'; deny C "$C" 'Enforcing'
rcis D "$D" 1
if [ "$bad" -eq 0 ]; then echo GATE-W-BEHAVIOUR-PASS; else echo GATE-W-BEHAVIOUR-FAIL; exit 1; fi</automated>
    <automated>set -u
h=internal/check-version-tags.sh
bad=0
body() { grep -v '^[[:space:]]*#' "$h"; }
no()  { c=$(body | grep -cF "$1"); [ "$c" -eq 0 ] || { echo "FAIL code contains [$1] ${c}x"; bad=1; }; }
yes() { grep -qF "$1" "$h" || { echo "FAIL absent [$1]"; bad=1; }; }
reg() { g=$(sed -n "$2" "$h" | sha256sum | cut -d' ' -f1); [ "$g" = "$3" ] || { echo "FAIL region $1 moved: $g"; bad=1; }; }
no 'exit 1'
no 'errored'
[ "$(grep -c 'every workflow also triggers on' "$h")" -eq 0 ] || { echo "FAIL stale causal clause present"; bad=1; }
[ "$(grep -cF '.github/workflows/build-' "$h")" -eq 0 ] || { echo "FAIL deleted-caller path present"; bad=1; }
[ "$(grep -cF 'build.yml' "$h")" -eq 0 ] || { echo "FAIL names build.yml, which does not exist yet"; bad=1; }
for l in 'internal/dispatch-builds.sh' 'workflow_dispatch' 'verify-image-availability.yml' 'ghcr' 'release marker' './internal/setup-hooks.sh'; do yes "$l"; done
reg is_local_build '/^is_local_build()/,/^}/p' 37e332d28832efcbd8e523f28bffc9184520c3e69b749616c1eb37afc87d0cb9
reg tag_exists '/^tag_exists()/,/^}/p' 61d94dced1fc82a611fea172d8d374cc8049823786a9d1e486f740de038a6b36
reg allowlist_array '/^LOCAL_BUILD_ADDONS=(/,/^)/p' cfbe5d35d8b64b212ebe40d52189c4f42c5bd9f5c2e1dbd4f5bdb67d77ca80d7
reg collect_loop '/^set -e$/,/^modified_addons=\$(printf/p' 714847bbf5466932f5e90fc1b4ffcad4a6690cecef2d964d02c7b5840801343d
reg version_extract '/^while IFS= read -r addon_dir/,/^    \[\[ -z "\$build_version"/p' 8e077b1e48533cf297ccb57cc5f345c7c23a5f619f07ac0e7b71c2cb94efa9f8
[ "$(body | grep -cE '(^|[^$])\(\(')" -eq 0 ] || { echo "FAIL arithmetic-command form present (set -e hazard)"; bad=1; }
awk 'NR==1{next} /^$/{exit} !/^#/{c++} END{exit (c>0)?1:0}' "$h" || { echo "FAIL header line not starting at column 1"; bad=1; }
bash -n "$h" || bad=1
shellcheck -e SC1091 -e SC2034 "$h" || bad=1
if [ "$bad" -eq 0 ]; then echo GATE-S-SOURCE-PASS; else echo GATE-S-SOURCE-FAIL; exit 1; fi</automated>
    <automated>set -u
bad=0
[ "$(grep -cF 'check-version-tags.sh:121-126' internal/verify-image-availability.sh)" -eq 0 ] || { echo "FAIL stale numeric citation survives"; bad=1; }
grep -qF 'check-version-tags.sh' internal/verify-image-availability.sh || { echo "FAIL citation dropped entirely"; bad=1; }
grep -qF 'Output vocabulary, matching internal/check-version-tags.sh exactly' internal/verify-image-availability.sh || { echo "FAIL vocabulary claim disturbed"; bad=1; }
grep -qiF 'never blocks' internal/setup-hooks.sh || { echo "FAIL setup-hooks still describes a blocking check"; bad=1; }
[ "$(grep -cF 'verifies v<version> tag exists' internal/setup-hooks.sh)" -eq 0 ] || { echo "FAIL setup-hooks enforcement wording survives"; bad=1; }
long() { c=$(awk 'length($0) > 120' "$1" | wc -l); [ "$c" -le "$2" ] || { echo "FAIL $1 over-120 lines rose to $c (baseline $2)"; bad=1; }; }
for f in internal/check-version-tags.sh internal/setup-hooks.sh internal/verify-image-availability.sh; do
  bash -n "$f" || bad=1
  shellcheck -e SC1091 -e SC2034 "$f" || bad=1
done
long internal/check-version-tags.sh 2
long internal/setup-hooks.sh 0
long internal/verify-image-availability.sh 19
t="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"
cmp -s internal/check-version-tags.sh "$t" || { echo "FAIL installed hook differs from repo copy: $t"; bad=1; }
[ -x "$t" ] || { echo "FAIL installed hook not executable"; bad=1; }
if [ "$bad" -eq 0 ]; then echo GATE-C-CITATIONS-PASS; else echo GATE-C-CITATIONS-FAIL; exit 1; fi</automated>
    <automated>pre-commit run --files internal/check-version-tags.sh internal/setup-hooks.sh internal/verify-image-availability.sh</automated>
  </verify>
  <done>
Every criterion is a property of the finished tree, and every absolute number it names was measured
at `74c8066` and recorded in `<verified_environment>`.

`GATE-W-BEHAVIOUR` is the load-bearing one and it is calibrated, not asserted: run against the
UNMODIFIED tree it fails exactly eight assertions — probe A's exit status, its three required
literals and its forbidden aggregate line, plus probe C's exit status, its `advisory` literal and
its forbidden enforcement literal — while probes B and D pass. Probe D is the negative control: it
runs the hook as it stands at `74c8066` through the identical fixture and requires exit **1**, so a
fixture that stopped reaching the missing-tag branch (for example because the version extraction
or the diff derivation broke) cannot silently pass the whole gate. Handover §3.1: a recomputed
hash proves a pin correct, never that it catches — this probe is why the behavioural claim is
earned rather than assumed.

`GATE-S-SOURCE` proves the source-level shape: zero non-zero exits and zero error-accumulator
references in the COMMENT-STRIPPED body (comments stripped at any indentation, per handover §3.6,
so a mandated explanatory comment cannot self-invalidate the gate), the false causal clause and the
deleted-caller path both gone, `build.yml` still absent, the six required literals present, five
regions byte-identical by hash (`is_local_build`, `tag_exists`, the allowlist array, the collection
loop, the version-extraction block), the arithmetic-COMMAND form absent, every header line at
column 1, and `bash -n` plus `shellcheck -e SC1091 -e SC2034` clean.

`GATE-C-CITATIONS` proves the two citing files and the installed copy: the numeric citation into
this hook is gone while the citation itself survives as an anchor, the sibling's output-vocabulary
claim is undisturbed, `internal/setup-hooks.sh` no longer describes a verifying/blocking check,
all three files stay inside 120 columns, and `.git/hooks/pre-push` is byte-identical to the repo
copy and executable — without which the developer's next push still gets the old blocking hook.

`pre-commit run --files` over the three files is green.

No gate greps for a glyph: handover §3.6 records `grep -c '⚠️'` failing because this repo's glyph
carries VS16 (U+FE0F). Every assertion is over ASCII prose or an exit status.
  </done>
</task>

<task type="auto">
  <name>Task 2: Re-pin the 260909-rln collision this change creates</name>
  <files>.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md</files>
  <precondition>Task 1 is committed, and `grep -v '^#' internal/check-version-tags.sh | sha256sum` differs from `5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249` (if it still matches, Task 1 changed no code and there is nothing to re-pin — HALT and re-check Task 1). `.github/workflows/build.yml` still does not exist, i.e. `260909-rln` has not landed; if it has, HALT — the plan is history at that point and must be reconciled against the shipped tree instead of re-pinned.</precondition>
  <read_first>
`.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md` —
read only the regions this task edits, located by content anchor rather than line number
(handover §3.7): its `<verified_environment>` table row for this hook's code hash, the closing
paragraph of `<decisions>` that calls Task 3 comment/prose-only, `<sibling_supersession>`, Task 3's
precondition and read_first blocks, Task 3's action item for this hook's header, Task 3's
verify line ending in `GATE-G3-6-PASS`, the done paragraph about this hook, the
`<gate_calibration>` rows for `G3-6` and `G3-8`, and the `<success_criteria>` bullet that calls
this a hash-proven comment-only change.
  </read_first>
  <action>
Make `260909-rln-PLAN.md` true again about `internal/check-version-tags.sh` (D-04). Compute the new
value ONCE — `grep -v '^#' internal/check-version-tags.sh | sha256sum | cut -d' ' -f1` — and use it
everywhere below. Seven sites, all located by content anchor; do not trust or reuse any line number
printed in that file or in this plan.

**1. The pin, three full occurrences plus one truncated.** Substitute the new hash in the
verified_environment table row, in the `GATE-G3-6-PASS` gate line, and in the done
paragraph; substitute the matching truncated form (first eight characters, ellipsis, last six) in
the `<gate_calibration>` `G3-6` row. The stale value must survive nowhere in the file, in either
form — not even as parenthetical history. <!-- planner-discipline-allow: 5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249 --> <!-- planner-discipline-allow: 5f310c2e…019249 -->

**2. The baseline claims.** At each site that asserts this file's non-comment lines are unchanged
from baseline, or that it is untouched by every sibling, or that it is among the files whose
measured baselines still hold, name quick task `260909-wgm` as the intervening change and state
that the pin's baseline is the post-`260909-wgm` tree. The absolute claim in the done paragraph
must go: its non-comment lines are NOT unchanged from `5b41d49`. <!-- planner-discipline-allow: , unchanged from baseline, with -->
Do NOT touch the generic sentence elsewhere in that plan warning that nothing should assert
"unchanged from baseline" for a file a sibling can reach — that sentence is meta-text about the
rule and it is still correct.

**3. GATE-G3-6's other assertions, dispositioned in writing.** Say plainly, at the `G3-6` row in
gate_calibration and in the done paragraph, which clauses are still work-proving for
`260909-rln` and which `260909-wgm` already satisfied: the false-causal-clause count is **already
satisfied** (driven from 1 to 0 by `260909-wgm`) and survives only as an invariant that must stay
0; `grep -q 'ghcr'` was and remains an invariant; `grep -q 'build\.yml'` is the one clause still
work-proving, because that workflow is `260909-rln`'s own deliverable and `260909-wgm` deliberately
does not name it; the hash is re-pinned to the new baseline. The point of writing this down is that
a gate which silently became a no-op reads as coverage it no longer provides.

**4. Narrow Task 3's action item for this hook's header — the highest-value edit here.** As
written, that item tells the executor to rewrite the header to correct the rationale, to keep the
ghcr-404 failure mode intact, and to avoid one specific phrasing. After `260909-wgm` the rationale
is already corrected and the failure-mode framing has already changed: the surviving control is
`.github/workflows/verify-image-availability.yml`, and the hook is advisory. Rewrite the item so
its remaining job is unambiguous and minimal — add the `build.yml` mention to the already-corrected
header, do not re-litigate the rationale, do not restore any blocking language, and do not revert
`260909-wgm`'s advisory wording. Keep the item's two mechanical constraints, which still apply
verbatim: every header line begins at column 1 (because the pin strips only column-1 comments), and
the shebang is untouched. Keep its instruction that nothing below the header changes — that is
still right; what changed is what "below the header" now contains.

**5. Task 3's `<precondition>` and `<read_first>`.** Add a `260909-wgm` landed-check to the
precondition — `grep -qF 'release marker' internal/check-version-tags.sh` — with a HALT on failure,
because rewriting a header that has not been corrected yet would produce a different edit than the
one the narrowed item describes. In `<read_first>`, replace the two numeric line-range citations
into this hook with content anchors (the header block; the allowlist array and its comment block).
Do NOT add `260909-wgm` to that plan's `depends_on` — it is not a member of batch `260909-rli`, and
a precondition assertion is the mechanism that fits.

**6. The G3-8 baseline record, two sites.** Both record this hook's line 2 as one of three
repo-wide references to a deleted caller. `260909-wgm` removed it, so the starting count is now
two and this file is no longer among them. Correct both records and drop the numeric citation of
this hook; the gate itself is a `== 0` property and needs no change. <!-- planner-discipline-allow: check-version-tags.sh:2 -->

**7. `<sibling_supersession>`.** Add a short subsection recording that a NON-sibling change,
quick task `260909-wgm`, landed against `internal/check-version-tags.sh` between that plan being
written and Task 3 running; that it re-based G3-6's hash and pre-satisfied G3-6's first clause; and
that Task 3's remaining scope in that file is the `build.yml` mention. Keep it consistent with the
section's existing framing: the wave-3 baseline rule it already states is precisely what caught
this.

**One rule covering every literal above:** an eliminated literal may not be retained anywhere in
that file as parenthetical history, a "was previously" note, or a quoted before/after pair — the
gates are file-wide and would read the history as the defect. Describe what changed in prose that
does not contain the old string; the SUMMARY is where the old values are recorded verbatim.

Do not reformat, rewrap or otherwise touch any other part of the file — `.planning/` is
`.prettierignore`d and markdownlint-excluded, so nothing reflows it and a stray rewrap would bury
the real diff. Do not touch its frontmatter. Do not hand-edit `.planning/WINDOWS.md`'s generated
table (handover §5); no ledger entry is in this task's scope.
  </action>
  <verify>
    <automated>set -u
F=.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
new=$(grep -v '^#' internal/check-version-tags.sh | sha256sum | cut -d' ' -f1)
short="$(printf '%s' "$new" | cut -c1-8)…$(printf '%s' "$new" | cut -c59-64)"
bad=0
[ "$new" != 5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249 ] || { echo "FAIL Task 1 changed no code"; bad=1; }
[ "$(grep -cF '5f310c2eff61fd1d511ca692ea7b1bb694b1bc510580baac2608107954019249' "$F")" -eq 0 ] || { echo "FAIL stale full hash survives"; bad=1; }
[ "$(grep -cF '5f310c2e…019249' "$F")" -eq 0 ] || { echo "FAIL stale truncated hash survives"; bad=1; }
[ "$(grep -cF "$new" "$F")" -ge 3 ] || { echo "FAIL new hash present $(grep -cF "$new" "$F")x, want >=3"; bad=1; }
[ "$(grep -cF "$short" "$F")" -ge 1 ] || { echo "FAIL truncated form [$short] absent"; bad=1; }
grep -F 'GATE-G3-6-PASS' "$F" | grep -qF "$new" || { echo "FAIL G3-6 gate line does not carry the new hash"; bad=1; }
if [ "$bad" -eq 0 ]; then echo GATE-P-PIN-PASS; else echo GATE-P-PIN-FAIL; exit 1; fi</automated>
    <automated>set -u
F=.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
bad=0
[ "$(grep -cF '260909-wgm' "$F")" -ge 6 ] || { echo "FAIL provenance named $(grep -cF '260909-wgm' "$F")x, want >=6"; bad=1; }
[ "$(grep -cF ', unchanged from baseline, with' "$F")" -eq 0 ] || { echo "FAIL absolute baseline claim survives"; bad=1; }
[ "$(grep -cF 'unchanged from baseline' "$F")" -ge 1 ] || { echo "FAIL the generic meta-sentence about that phrase was deleted too"; bad=1; }
[ "$(grep -cF 'check-version-tags.sh:2' "$F")" -eq 0 ] || { echo "FAIL stale G3-8 line citation survives"; bad=1; }
[ "$(grep -cF 'lines 34-40' "$F")" -eq 0 ] || { echo "FAIL stale line range 1 survives"; bad=1; }
[ "$(grep -cF 'lines 1-8' "$F")" -eq 0 ] || { echo "FAIL stale line range 2 survives"; bad=1; }
[ "$(grep -cF 'header (lines 2-7)' "$F")" -eq 0 ] || { echo "FAIL stale line range 3 survives"; bad=1; }
[ "$(grep -cF '51-77' "$F")" -eq 0 ] || { echo "FAIL stale line range 4 survives"; bad=1; }
grep -F 'already satisfied' "$F" | grep -qF 'G3-6' || { echo "FAIL G3-6 no-op disposition not stated"; bad=1; }
r=$(sed -n '/check-version-tags\.sh. header/,/update-version\.py. — TWO prose blocks/p' "$F")
[ "$(printf '%s\n' "$r" | wc -l)" -ge 5 ] || { echo "FAIL item-6 region anchors no longer resolve"; bad=1; }
printf '%s\n' "$r" | grep -qF '260909-wgm' || { echo "FAIL item 6 not narrowed against 260909-wgm"; bad=1; }
printf '%s\n' "$r" | grep -qF 'build.yml' || { echo "FAIL item 6 no longer names its remaining job"; bad=1; }
printf '%s\n' "$r" | grep -qF 'column 1' || { echo "FAIL item 6 dropped the column-1 constraint"; bad=1; }
if [ "$bad" -eq 0 ]; then echo GATE-P-CLAIMS-PASS; else echo GATE-P-CLAIMS-FAIL; exit 1; fi</automated>
    <automated>set -u
F=.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md
bad=0
python3 -c "
import yaml, sys
d = yaml.safe_load(open('$F').read().split('---')[1])
need = ['phase','plan','type','wave','depends_on','files_modified','files_deleted','autonomous','requirements','must_haves','quick_id','estimate']
missing = [k for k in need if k not in d]
assert not missing, missing
assert '260909-wgm' not in (d['depends_on'] or []), 'wgm must not be added to depends_on'
print('frontmatter-ok')" || bad=1
ns=$(git diff --numstat -- "$F") || { echo "FAIL git diff failed"; bad=1; ns=""; }
sum=$(printf '%s\n' "$ns" | awk '{s+=$1+$2} END{print s+0}')
[ "$sum" -le 90 ] || { echo "FAIL diff larger than a targeted re-pin: $ns"; bad=1; }
[ "$(git status --porcelain -- .planning/WINDOWS.md)" = "" ] || { echo "FAIL WINDOWS.md hand-edited"; bad=1; }
pre-commit run --files "$F" .planning/quick/260909-wgm-rework-internal-check-version-tags-sh-so/260909-wgm-PLAN.md || bad=1
if [ "$bad" -eq 0 ]; then echo GATE-P-HYGIENE-PASS; else echo GATE-P-HYGIENE-FAIL; exit 1; fi</automated>
  </verify>
  <done>
`GATE-P-PIN` proves the pin is re-based: the stale value survives in neither the full nor the
truncated form, the recomputed value appears at least three times, its truncated form at least
once, and the `GATE-G3-6-PASS` line itself carries it. The gate recomputes the hash rather than
hard-coding one, so it cannot be satisfied by pasting a number — and it refuses to pass at all if
Task 1 left the code hash unchanged, which would mean this task had nothing to do.

`GATE-P-CLAIMS` proves the prose is true again: `260909-wgm` is named at six or more sites, the
absolute "unchanged from baseline" claim about this file is gone while the generic meta-sentence
about that phrase is deliberately preserved (a naive global negative grep would have deleted a
correct sentence — handover §3.6's exact defect shape), all four stale numeric line citations into
this hook are gone, G3-6's no-op clause is dispositioned in a sentence that names it, and the
narrowed action item still resolves by anchor while naming `260909-wgm`, its remaining `build.yml`
job and its surviving column-1 constraint.

`GATE-P-HYGIENE` proves nothing else moved: that plan's frontmatter still parses and still carries
all twelve keys, `260909-wgm` was NOT added to its `depends_on`, the whole diff is under 90 changed
lines (a targeted re-pin, not a rewrap), `.planning/WINDOWS.md` is untouched, and `pre-commit` is
green over both plan files.

Not asserted here, and deliberately so: nothing in this task claims `260909-rln`'s gates are
"stronger" or "weaker" than before. Handover §3.1 — recomputing a hash proves a pin is correct,
never that it catches. The only catch-claim in this plan is Task 1's probe D negative control.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer workstation → `origin` | `git push` crosses it; this hook runs entirely on the near side and gates nothing on the far side |
| repository tree → `.git/hooks/pre-push` | the hook is installed as a bare COPY, so the two can drift |
| `ghcr.io` (anonymous) → Home Assistant Supervisor | the only boundary where a missing image becomes user-visible; nothing in this task runs there |

The realistic threat surface is small and this section says so rather than manufacturing findings:
a local git hook, no network call except the developer's own `git ls-remote origin`, no credential
read, no untrusted input (stdin comes from `git` itself), no package-manager install anywhere in
scope. The one genuine consideration is the deliberate weakening of a control, recorded as
T-wgm-01 with its compensating control named explicitly.

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-wgm-01 | Denial of Service (add-on update availability) | `internal/check-version-tags.sh` missing-tag branch | low | accept | **This is the change, made explicit.** What stops being enforced: the local pre-push refusal to publish a `config.yaml` version bump with no release tag — now advisory only. What is still enforced, and was measured this session: `.github/workflows/verify-image-availability.yml` runs four times daily and probes every version each `config.yaml` advertises anonymously, with no registry credential, because an authenticated probe would certify an image the Supervisor cannot pull (handover §3.4); it distinguishes `token 200 + manifest 200` from `manifest 404` and reports `token 403/401` as ambiguous rather than claiming to know which (§3.5). Accepted because the tag never caused the build in the first place: six of nine `build-<addon>.yml` files have their `tags:` trigger commented out, images come from `internal/dispatch-builds.sh`, and `amd64-authentik:2026.8.2-0` / `amd64-meridian:1.69.0-0` were both measured HTTP 200 on 2026-09-09 (§2.1) |
| T-wgm-02 | Tampering (stale local copy) | `.git/hooks/pre-push` | low | mitigate | The installed hook is a bare copy and is currently byte-identical to the repo file; editing only the repo file leaves the developer still blocked. Task 1 step 7 reinstalls it and `GATE-C-CITATIONS` asserts `cmp -s` plus the executable bit |
| T-wgm-03 | Repudiation (a guard that reads as coverage it no longer provides) | `260909-rln-PLAN.md` GATE-G3-6 | low | mitigate | Task 2 item 3 dispositions each clause in writing — which one is still work-proving, which two are now invariants, which is re-pinned — and `GATE-P-CLAIMS` asserts the disposition sentence exists |
| T-wgm-04 | Information disclosure | hook stdout | low | accept | The hook echoes add-on directory names, version strings and tag names only. It reads no credential and no `/data` path; its only network call is `git ls-remote origin`, using the developer's existing git credentials, with stderr suppressed |
| T-wgm-SC | Tampering (supply chain) | npm/pip/cargo installs | n/a | n/a | **Not applicable, stated rather than fabricated:** this task adds no dependency of any kind. No package manager runs, no `RESEARCH.md` Package Legitimacy Audit is required, and no install checkpoint fires. The three edited scripts use only `git`, `grep`, `sed`, `sha256sum` and `bash` builtins — the no-tool-dependency constraint the hook already documents |
</threat_model>

<capability_checkpoint_declarations>
Confirmed against this task's actual scope, one line each, per the brief:

- **api-coverage:** does not fire. No external API or SDK integration is in scope — a local git
  hook and a plan document. No `COVERAGE.md` matrix is produced.
- **assumption-delta:** does not fire. No singular→plural, required→optional or derived→chosen
  transition. The one transition here is enforced→advisory for a local gate, which is D-01 itself
  and is recorded as T-wgm-01 with its compensating control.
- **schema-gate:** does not fire. No ORM, migration or schema file is touched.
- **package-legitimacy gate:** does not fire. No package-manager install task exists (see
  T-wgm-SC).
</capability_checkpoint_declarations>

<source_coverage_audit>
Four source types, every item mapped to a task. Nothing deferred, nothing silently dropped.

| Source | Item | Covered by |
|---|---|---|
| GOAL (task brief) | missing `<addon>/v*` tag warns instead of blocking the push | Task 1 edit 3 + 4 (D-01) — `GATE-W-BEHAVIOUR` probes A and C |
| GOAL | correct the now-false rationale in the header comment and in the messages | Task 1 edits 1 + 3 (D-03) — `GATE-S-SOURCE` literal set |
| GOAL | re-pin the collision this creates in pending batch item `260909-rln` | Task 2 (D-04) — `GATE-P-PIN`, `GATE-P-CLAIMS` |
| REQ | QUICK-260909-wgm-a advisory exit status | Task 1 edits 3 + 4 |
| REQ | QUICK-260909-wgm-b allowlist and drift guard retained, enforcement wording dropped | Task 1 edit 2 (D-02) — probes B and C |
| REQ | QUICK-260909-wgm-c measured rationale in header and message | Task 1 edits 1, 3, 5 |
| REQ | QUICK-260909-wgm-d no dead blocking code | Task 1 edit 4 — comment-stripped negative greps |
| REQ | QUICK-260909-wgm-e `260909-rln-PLAN.md` true again | Task 2, all seven sites |
| RESEARCH (`HANDOVER-260909-rli.md` plays the research role — there is no `RESEARCH.md`) | §2.1 both halves of the rationale disproved | Task 1 edits 1 + 3 |
| RESEARCH | §2.1 recommendation 3, downgrade rather than drop; coordinate with `260909-rln` | Task 1 (downgrade) + Task 2 (coordination) |
| RESEARCH | §3.4/§3.5 what the surviving control does and does not prove | `<threat_model>` T-wgm-01, quoted rather than re-derived |
| RESEARCH | §3.6 gates that reject correct work | every negative gate strips comments or asserts an exit status; no glyph grep; the generic meta-sentence in `260909-rln` explicitly protected |
| RESEARCH | §3.7 cross-wave staleness | `<verified_environment>` re-measured at planning time; Task 2 replaces four stale line citations with anchors |
| RESEARCH | §3.8 `.prettierignore` excludes `.planning/`, files outside it are reflowed | 120-column gate on the three scripts; no reflow of either plan file |
| RESEARCH | §3.1 a hash proves correctness, not catching | probe D negative control; the done block refuses any "stronger gate" claim |
| CONTEXT | D-01 downgrade, do not drop | Task 1 edits 3 + 4 |
| CONTEXT | D-02 allowlist and drift guard stay, wording corrected | Task 1 edit 2 |
| CONTEXT | D-03 correct the rationale in the same change | Task 1 edits 1, 3, 5 |
| CONTEXT | D-04 re-pin `260909-rln` in the same quick task | Task 2 |
| MUST-NOT-BREAK | no tool dependency in the hook | Task 1 closing constraint; `GATE-C-CITATIONS` shellcheck over all three files |
| MUST-NOT-BREAK | both `set -e` hazard properties preserved | Task 1 edit 4(b); two region hashes + the arithmetic-command-form gate |
| MUST-NOT-BREAK | `bash -n`, `shellcheck -e SC1091 -e SC2034`, `pre-commit` green | `GATE-S-SOURCE`, `GATE-C-CITATIONS`, the `pre-commit run --files` gate |
| MUST-NOT-BREAK | no dead code reading as if it still blocks | Task 1 edit 4; comment-stripped negative greps |
| MUST-NOT-BREAK | `.planning/WINDOWS.md` generated table not hand-edited | `GATE-P-HYGIENE` |

No item is MISSING. Nothing is deferred. Two items are deliberately OUT of scope and are named
rather than dropped silently: adding the top-level `image:` key to `authentik` and `iac-runner`
(handover §2.4 — a separate change with its own anonymous-pull verification, and adding it here
would move `authentik` into the drift-guard path mid-rework), and any `.planning/WINDOWS.md`
ledger entry (handover §5 — the table is generated; the G3-6 no-op is recorded inside
`260909-rln-PLAN.md` instead, which is what D-04 asks for).
</source_coverage_audit>

<verification>
Run in order, after both tasks, before handing the item back:

1. All four Task 1 gates and all three Task 2 gates, in task order. Each prints exactly one
   `…-PASS` token and exits 0.
2. `pre-commit run --files internal/check-version-tags.sh internal/setup-hooks.sh internal/verify-image-availability.sh`
   — green.
3. The negative control on its own, as the single strongest statement this plan can make: the
   fixture that returns exit 1 for the hook at `74c8066` must return exit 0 for the hook at `HEAD`,
   with the warning text present in both. Record both outputs verbatim in the SUMMARY.
4. `cmp -s internal/check-version-tags.sh "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"`
   — silent. Without this the developer's next push still runs the old blocking copy.
5. `git status --porcelain` shows exactly the four declared files and nothing else.
5a. Expect `end-of-file-fixer` to fail once and FIX a file rather than reject it (handover §3.8) —
   re-stage and re-run. It already did this to this plan file once during planning; a second
   abort on the same path means something else is wrong.
6. Two atomic commits, in this order:
   - `fix(hooks): make the missing release tag advisory and correct the rationale`
   - `docs(260909-rln): re-pin the check-version-tags hash and correct the comment-only claims`
7. Real-push smoke check, and it is expected to be a no-op: the current tree has no add-on whose
   primary AND legacy tags are both absent, so a real push exercises the `✓` and `⊘` paths only.
   Do not fabricate a tagless add-on to "prove" it live — that is what the fixture is for.
</verification>

<success_criteria>
- A push whose range bumps a non-allowlisted add-on with no matching release tag prints a warning
  naming the expected tag and exits 0. Proven by probe A against probe D's exit-1 control, not
  asserted.
- The allowlist skip path is byte-for-byte the behaviour it was: same `⊘` line, exit 0.
- The drift path warns, names `LOCAL_BUILD_ADDONS`, reports the missing tag advisorily, exits 0,
  and no longer claims the requirement is applied anyway.
- The hook's header and its missing-tag message state only what was measured: dispatch-driven
  `workflow_dispatch` publishing, `verify-image-availability.yml` as the surviving control, tag as
  release marker. No `.github/workflows/build-<addon>.yml` path survives in the file, and
  `build.yml` is deliberately NOT named — that literal remains `260909-rln`'s work to add.
- Five pinned regions are byte-identical, the arithmetic-command form is absent, and both
  documented `set -e` hazards still hold.
- Nothing blocks and nothing reads as if it does: the comment-stripped body has no non-zero exit
  and no leftover error accumulator; the advisory counter and its summary line are the coherent
  replacement.
- `internal/setup-hooks.sh` and `internal/verify-image-availability.sh` no longer assert something
  about this hook that stopped being true, and the second file's citation can no longer go stale
  with a line-number shift.
- `.git/hooks/pre-push` matches the repo file and is executable.
- `260909-rln-PLAN.md` carries the recomputed hash in all four places, names `260909-wgm` at every
  site whose baseline it changed, dispositions GATE-G3-6's clauses in writing, narrows its
  header-rewrite item to the one job left, and carries no stale numeric citation into this hook —
  with its frontmatter and everything outside those seven sites untouched.
- `bash -n`, `shellcheck -e SC1091 -e SC2034` and `pre-commit run --files` are green on every
  touched path; all three scripts stay inside 120 columns.
</success_criteria>

<output>
Create `.planning/quick/260909-wgm-rework-internal-check-version-tags-sh-so/260909-wgm-SUMMARY.md`
when done. It must record, verbatim: the recomputed code hash; probe D's exit-1 output next to
probe A's exit-0 output; the seven `260909-rln-PLAN.md` sites edited with their old and new claim;
and the explicit note that GATE-G3-6's false-causal-clause assertion is now a satisfied invariant
rather than work-proving, so a verifier re-running batch `260909-rli`'s gate set does not read it
as coverage.
</output>
