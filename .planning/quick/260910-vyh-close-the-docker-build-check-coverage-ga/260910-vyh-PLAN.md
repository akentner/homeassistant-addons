---
phase: quick-260910-vyh
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .pre-commit-config.yaml
  - Makefile
  - internal/validate-versions.sh
  - internal/validate-addon-config.py
autonomous: true
requirements: [VYH-A, VYH-B, VYH-C]

estimate:
  tokens: 45000
  raw_tokens: 45000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "Editing .github/workflows/opencode.yml to widen the author gate turns pre-commit red BEFORE the commit lands — proven on two independent tamper shapes (author clause deleted; CONTRIBUTOR promoted into the trusted set)."
    - "pre-commit run verify-opencode-gate reports Skipped for a changeset that touches neither .github/workflows/opencode.yml nor internal/verify-opencode-gate.py — the scoping is real, not accidental always_run."
    - "make docker-build-check applies the full hadolint ruleset to 10 Dockerfiles: the nine shipped add-ons AND tools/test-addon/Dockerfile."
    - "make docker-build-check still exits 1 for exactly one hadolint finding — the pre-existing authentik/Dockerfile:15 DL3008 — and for no new finding."
    - "A reader at any one of the four discovery sites learns which of the two deliberate add-on definitions that site implements and why the other one differs, without having to read the other three sites."
    - "make check-all exits 0 and makes no network call at run time."
    - ".github/workflows/opencode.yml is byte-identical to its HEAD blob (bb9d1162327da41f894504f96d3d257ebd74c0ed) when the plan finishes."
  artifacts:
    - ".pre-commit-config.yaml — new local hook id: verify-opencode-gate"
    - "Makefile — docker-build-check hadolint discovery widened to `*/ tools/*/`, plus definition comments above docker-build-check and validate-addons"
    - "internal/validate-versions.sh — definition comment extending the existing depth-2 block at lines 83-87"
    - "internal/validate-addon-config.py — definition comment extending the existing depth-2 block at lines 102-104"
  key_links:
    - "hook `files:` regex <-> the path internal/verify-opencode-gate.py reads by default (DEFAULT_WORKFLOW = .github/workflows/opencode.yml). If those two diverge, the hook fires on a file it does not read and guards nothing."
    - "`pass_filenames: false` <-> the verifier's argparse surface (--workflow / --job / --quiet only). A passed positional path is an argparse error, so pass_filenames must stay false."
    - "the trailing `/` produced by the `*/` and `tools/*/` globs <-> the `<addon_dir>Dockerfile` concatenation and the `%/` suffix-strip in the progress echo. A find-based list has no trailing slash and would break both."
    - "make check-all -> lint -> `pre-commit run --all-files` <-> the new hook's files regex matching under --all-files. This is the CI enforcement path (.github/workflows/lint.yml runs the same command); if the regex stopped matching, the gate would be locally-only."
---

<objective>
Close three separate holes left open around the add-on discovery mechanisms and the opencode job gate.

- **VYH-A** — Wire `internal/verify-opencode-gate.py` into `.pre-commit-config.yaml`. The verifier proves the truth table
  of the job-level `if:` in `.github/workflows/opencode.yml` over 72 fixture rows, but nothing currently runs it: a
  future edit that deletes the author clause would NOT go red at commit time. That gate is the only thing between a
  drive-by commenter on this PUBLIC repository and a job whose environment holds an API key.
- **VYH-B** — `make docker-build-check` runs hadolint with a stricter ruleset than the pre-commit hadolint hook
  (DL3008 and DL3006 are NOT suppressed there), but discovers only depth-1 directories, so
  `tools/test-addon/Dockerfile` never receives that ruleset. Widen the discovery, reusing an existing idiom.
- **VYH-C** — Make the two DELIBERATE definitions of "add-on" legible at all four discovery sites, so the next reader
  (human or agent) does not re-diagnose the difference as a repository defect. An earlier session already made exactly
  that mistake.

Purpose: two of the three deliverables are guards (a security regression guard and a lint-coverage guard); the third
prevents a recurring misdiagnosis that would otherwise "fix" the guards by unifying them.

Output: 4 modified files, 3 atomic commits, no new scripts, no renames.
</objective>

<critical_context>
## There is no bug here. There are two definitions, and both are correct.

VERIFIED at planning time — do NOT re-investigate, and do NOT "unify" anything:

| Site | Discovery | Definition it implements |
|---|---|---|
| `internal/validate-versions.sh:89-97` | `find . -mindepth 1 -maxdepth 2 -type d`, requires `config.yaml` + `build.yaml` | **must pass version validation** — includes `tools/test-addon/` |
| `internal/validate-addon-config.py:105-115` | top-level dirs with both files, PLUS an explicit `top.name == "tools"` nested pass | **must pass config-schema validation** — includes `tools/test-addon/` |
| `Makefile:75` `validate-addons` | `for addon_dir in */` (depth 1) | **is a shipped add-on** — the nine top-level dirs |
| `Makefile:117` `docker-build-check` | `for addon_dir in */` (depth 1) | currently **is a shipped add-on**; VYH-B moves it to **must pass Dockerfile linting** |

`internal/`, `docs/` and `tools/` carry neither `config.yaml` nor `build.yaml`, so no mechanism picks them up — they are
excluded by the ABSENCE OF MARKER FILES, not by name. `terraform-provider-homeassistant/` has `build.yaml` but no
`config.yaml`, so it is excluded too (both are required).

## Live baseline measured at planning time (2026-09-10, HEAD 1a8406f)

| Fact | Observed |
|---|---|
| depth-1 dirs with `config.yaml` + `Dockerfile` | 9 — authentik, coding-assistants, gatus, iac-runner, markdown-renderer, meridian, network-tools, phone-logger, terraform-bridge |
| `make docker-build-check` | 9 `Checking` lines, exit **1**, sole finding `authentik/Dockerfile:15 DL3008` |
| `hadolint --ignore DL3018 --ignore DL3059 --ignore DL4006 --ignore DL3016 tools/test-addon/Dockerfile` | exit **0** (re-confirmed; impact of the gap is nil today) |
| `make validate-addons` | 9 `validation passed` lines |
| `./internal/validate-versions.sh` | `Found add-ons: ... 10 entries incl. tools/test-addon`, exit 0 |
| `python3 internal/validate-addon-config.py` | exit 0 |
| `make check-all` | exit **0**, 23 hooks Passed, offline |
| `python3 internal/verify-opencode-gate.py --quiet` | 5 PASS assertions over 72 rows, exit 0, 0.08 s |
| `git rev-parse HEAD:.github/workflows/opencode.yml` | `bb9d1162327da41f894504f96d3d257ebd74c0ed` |
| `pre-commit --version` | 4.6.2; a `files:`-scoped hook on a non-matching path prints `(no files to check)Skipped` (probed against `validate-dockerfile-args`) |

`docker-build-check` is NOT a member of `check-all` (`Makefile:268` is `check-all: lint validate-addons
validate-versions validate-dockerfiles`). Widening it therefore cannot turn `check-all` red, and the target already
being red is a true report, not a regression.

## The verifier's tamper behaviour, measured non-destructively at planning time

Both shapes produce a precise diagnostic and exit 1 (run against scratchpad COPIES; the live file was never touched):

| Tamper | Output line | Exit |
|---|---|---|
| author clause deleted entirely | `FAIL  A2 denial — 30 untrusted rows allowed: [('CONTRIBUTOR', '/oc'), ...]` | 1 |
| `CONTRIBUTOR` added to the trusted set | `FAIL  A2 denial — 6 untrusted rows allowed: [('CONTRIBUTOR', '/oc'), ...]` | 1 |

In both cases A1/A3/A4/A5 still PASS, so the failure is specific to the denial invariant — that is what makes the
assertions in Task 1 non-vacuous.

## Verifier CLI surface (read before writing the hook)

`internal/verify-opencode-gate.py` accepts **only** `--workflow <path>`, `--job <id>`, `--quiet`. There is NO positional
argument. Exit codes: 0 pass, 1 assertion failed, 2 workflow/`if:` unreadable, 3 verifier itself broken. It imports
`yaml` (PyYAML) from the system python3 — the sibling `validate-addon-config` hook already relies on that under
`language: system`, so it is available.
</critical_context>

<out_of_scope>
The executor MUST NOT do any of the following, even if it looks adjacent or trivially correct:

- Renaming `internal/`, `docs/` or `tools/`, or introducing any naming convention for non-add-on directories. The
  marker files (`config.yaml` + `build.yaml`) already guarantee everything a naming convention would.
- Unifying the two add-on definitions, or "fixing" either `internal/` discovery site to match the Makefile (or vice
  versa).
- Fixing `authentik/Dockerfile:15 DL3008`, or extending any hadolint `--ignore` list anywhere.
- Touching `zizmor.yml`, the `unpinned-uses` relaxation, or any of the 27 pre-existing zizmor deferrals.
- trivy / govulncheck / CodeQL / SBOM / SECURITY.md.
- Any change to `.github/workflows/**` — including `opencode.yml`, which is only ever TAMPERED TRANSIENTLY in Task 1's
  verification and MUST be restored byte-identical before the task ends.
- Any change to `internal/verify-opencode-gate.py`'s logic. (Naming its path in the hook's `files:` regex is a scoping
  decision, not an edit — that is allowed and required.)

**Adjacent finding, deliberately NOT closed here (surfaced for the user, no task):** the second half of
`docker-build-check` is the ARG-before-FROM check, which runs `internal/validate-dockerfile-args.sh`. That script
discovers with `find . -maxdepth 2 -name "Dockerfile"` (`internal/validate-dockerfile-args.sh:64`) — for FILES,
`maxdepth 2` means `./<dir>/Dockerfile`, so `tools/test-addon/Dockerfile` at depth 3 is NOT covered by it either.
Verified: that find returns exactly the nine shipped Dockerfiles. After this plan, `docker-build-check`'s hadolint half
covers 10 Dockerfiles and its ARG half covers 9. Closing that would also change `make check-all` (via
`validate-dockerfiles`), which is a fourth deliverable — out of scope. Task 2's comment records the boundary with the
file:line so it is not mistaken for an oversight.
</out_of_scope>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@.pre-commit-config.yaml
@Makefile
</context>

<tasks>

<task type="tracer" tdd="false">
  <name>Task 1: Wire the opencode gate verifier into pre-commit and prove it fails on a tampered gate (VYH-A)</name>
  <files>.pre-commit-config.yaml</files>
  <precondition>`.github/workflows/opencode.yml` is tracked and clean in both the worktree and the index — the tamper/restore proof depends on `git checkout --` restoring the exact HEAD blob. Assert with `git diff --quiet -- .github/workflows/opencode.yml && git diff --cached --quiet -- .github/workflows/opencode.yml`; if either exits non-zero, HALT and report instead of tampering.</precondition>
  <reversibility rating="reversible">A hook addition in one YAML file; `git revert` restores the prior state and nothing outside `.pre-commit-config.yaml` is written.</reversibility>
  <action>
Add ONE new hook to the EXISTING `repo: local` block introduced by the `# Custom validation hooks` comment, placed
immediately after the `validate-addon-config` hook and before `verify-bridge-scaffold` — `validate-addon-config` is the
sibling precedent for `language: system` plus `entry: python3 internal/...`, so keeping them adjacent groups the two
system-python hooks together.

Hook fields, exactly:
- `id: verify-opencode-gate`
- `name: Verify opencode.yml comment-trigger author gate`
- `description:` one line naming what is proven (the job-level author_association denial over 72 fixture rows)
- `entry: python3 internal/verify-opencode-gate.py --quiet`
- `language: system`
- `files: ^(\.github/workflows/opencode\.yml|internal/verify-opencode-gate\.py)$`
- `pass_filenames: false`

`pass_filenames: false` is REQUIRED, not stylistic: the script exposes no positional argument, so a passed path would be
an argparse error. Do not add `always_run`, `require_serial`, `additional_dependencies`, or `args:`.

**The scoping decision, which the comment must justify** (this is the trade-off the task was asked to state):
`files:` scoped to two paths, NOT `always_run: true`.
- The verifier reads exactly ONE file, so that file changing IS the complete trigger set. Every edit that widens the
  gate necessarily touches `.github/workflows/opencode.yml`, so the narrow scope still fails closed for the threat.
- `internal/verify-opencode-gate.py` is included so an edit to the guard itself re-proves it against the live workflow.
- Deliberate consequence of the narrow scope: DELETING `.github/workflows/opencode.yml` does not fire the hook, because
  pre-commit passes no deleted paths. That is the correct behaviour — a deleted workflow cannot be triggered at all, so
  there is nothing left to guard, whereas `always_run: true` would make the deletion unshippable (the verifier would
  exit 2, workflow unreadable) and turn a legitimate removal into a permanent red.
- Runtime is 0.08 s, so cost was NOT the reason; scope correctness was. The sibling `always_run` hooks
  (`validate-versions`, `validate-addon-config`) are always-run because they scan the whole repository for cross-file
  invariants; this one does not.
- CI coverage is unaffected: `make check-all` -> `lint` -> `pre-commit run --all-files` and
  `.github/workflows/lint.yml` both pass every file, so the regex matches and the hook runs there too.

Write that reasoning as a full-line YAML comment block directly above the `- id:` line, indented to match it (6
spaces), in the same WHY-density as the neighbouring `zizmor` and `gitleaks` comments. Keep every line at or under 120
characters and put a space after each `#`. State the PUBLIC-repo exposure the gate protects, the
`files:`-versus-`always_run` trade-off including the deletion consequence, and why `pass_filenames: false` is load
bearing.

Then run the adversarial verification below. Never `git add` or `git commit` while the workflow file is tampered; the
commit for this task stages ONLY `.pre-commit-config.yaml`.
  </action>
  <verify>
    <automated>
LOGDIR=$(mktemp -d); WF=.github/workflows/opencode.yml
BASE=$(git rev-parse "HEAD:$WF"); cp "$WF" "$LOGDIR/opencode.yml.bak"

# 0. the config itself is well-formed and lint-clean
pre-commit validate-config .pre-commit-config.yaml
pre-commit run yamllint --files .pre-commit-config.yaml > "$LOGDIR/yl.log" 2>&1; EC=$?
cat "$LOGDIR/yl.log"; test "$EC" -eq 0

# 1. the hook FIRES and PASSES on the untampered gate (status asserted, not just the word)
pre-commit run verify-opencode-gate --files "$WF" > "$LOGDIR/pass.log" 2>&1; EC=$?
cat "$LOGDIR/pass.log"; test "$EC" -eq 0
grep -q 'Passed' "$LOGDIR/pass.log"

# 2. the scoping is real: an unrelated path does not trigger it
pre-commit run verify-opencode-gate --files README.md > "$LOGDIR/skip.log" 2>&1; EC=$?
cat "$LOGDIR/skip.log"; test "$EC" -eq 0
grep -q 'Skipped' "$LOGDIR/skip.log"

# 3. tamper shape A - author clause deleted -> hook must FAIL for the denial invariant
python3 - <<'PY'
import pathlib, sys
p = pathlib.Path(".github/workflows/opencode.yml"); s = p.read_text()
old = ("      (github.event.comment.author_association == 'OWNER' ||\n"
       "      github.event.comment.author_association == 'MEMBER' ||\n"
       "      github.event.comment.author_association == 'COLLABORATOR') &&\n"
       "      (contains")
if old not in s: sys.exit("anchor drifted - ABORT, do not tamper")
p.write_text(s.replace(old, "      (contains"))
PY
pre-commit run verify-opencode-gate --files "$WF" > "$LOGDIR/failA.log" 2>&1; EC=$?
cat "$LOGDIR/failA.log"; test "$EC" -ne 0
grep -q 'Failed' "$LOGDIR/failA.log"
grep -q '30 untrusted rows allowed' "$LOGDIR/failA.log"
git checkout -- "$WF"

# 4. tamper shape B - CONTRIBUTOR promoted into the trusted set -> hook must FAIL
python3 - <<'PY'
import pathlib, sys
p = pathlib.Path(".github/workflows/opencode.yml"); s = p.read_text()
old = "author_association == 'COLLABORATOR')"
if old not in s: sys.exit("anchor drifted - ABORT, do not tamper")
new = ("author_association == 'COLLABORATOR' ||\n"
       "      github.event.comment.author_association == 'CONTRIBUTOR')")
p.write_text(s.replace(old, new))
PY
pre-commit run verify-opencode-gate --files "$WF" > "$LOGDIR/failB.log" 2>&1; EC=$?
cat "$LOGDIR/failB.log"; test "$EC" -ne 0
grep -q 'Failed' "$LOGDIR/failB.log"
grep -q '6 untrusted rows allowed' "$LOGDIR/failB.log"
git checkout -- "$WF"

# 5. the live workflow is byte-identical to HEAD again (fallback restore if git checkout was insufficient)
cmp -s "$WF" "$LOGDIR/opencode.yml.bak" || cp "$LOGDIR/opencode.yml.bak" "$WF"
test "$(git hash-object "$WF")" = "$BASE"
test "$BASE" = "bb9d1162327da41f894504f96d3d257ebd74c0ed"
git diff --quiet -- "$WF"
test -z "$(git status --porcelain -- "$WF")"

# 6. the CI enforcement path really reaches the hook (Passed, NOT Skipped)
pre-commit run --all-files verify-opencode-gate > "$LOGDIR/all.log" 2>&1; EC=$?
cat "$LOGDIR/all.log"; test "$EC" -eq 0
grep -q 'Passed' "$LOGDIR/all.log"
grep -q 'Skipped' "$LOGDIR/all.log" && { echo 'hook did not run under --all-files'; exit 1; } || true
    </automated>
  </verify>
  <done>
`.pre-commit-config.yaml` carries the `verify-opencode-gate` hook with `language: system`, `pass_filenames: false`, and
the two-path `files:` regex, plus a comment block stating the exposure, the `files:`-vs-`always_run` trade-off (including
that a workflow deletion deliberately does not fire), and why `pass_filenames: false` is required. The hook is proven to
print `Failed` on BOTH tamper shapes, with the failure attributable to the denial invariant (`30 untrusted rows allowed`
and `6 untrusted rows allowed` respectively), to print `Passed` on the real file, to print `Skipped` for `README.md`, and
to be reached by `pre-commit run --all-files`. `.github/workflows/opencode.yml` hashes to
`bb9d1162327da41f894504f96d3d257ebd74c0ed` and `git status --porcelain` for it is empty. Commit stages ONLY
`.pre-commit-config.yaml`: `ci(260910-vyh): run the opencode gate verifier from pre-commit`.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Widen docker-build-check hadolint discovery to the nested fixture and name the definition it implements (VYH-B + part of VYH-C)</name>
  <files>Makefile</files>
  <reversibility rating="reversible">A two-token glob change plus a comment block in one recipe; revert restores the depth-1 behaviour exactly.</reversibility>
  <action>
Two edits, both in `Makefile`, both inside/above the `docker-build-check` target (currently at line 117; re-read before
editing — the file changed twice today).

**Edit 1 — the discovery.** At `Makefile:121`, change
`for addon_dir in */; do \`
to
`for addon_dir in */ tools/*/; do \`
and change nothing else in the recipe.

This reuses the explicit-`tools/`-pass idiom that `internal/validate-addon-config.py:110-115` already uses, rather than
inventing a third mechanism. It is preferred over porting the `find`-based depth-2 shape from
`internal/validate-versions.sh:89-97` for one specific reason: the recipe concatenates the loop variable with
`Dockerfile` and `config.yaml` directly, and strips a trailing slash with `%/` for the progress echo. A glob yields the
trailing `/`; a `find` list does not, so a `find` port would silently look for `tools/test-addonDockerfile`. The glob
keeps the diff to two tokens and leaves the trailing-slash contract untouched. An unmatched `tools/*/` glob stays
literal in POSIX sh, and the `[ -f ... ]` guards then skip it — verified safe.

Measured effect (verified at planning time with the same loop body in a standalone `sh`): 10 entries in the existing
order — the nine shipped add-ons first, then `tools/test-addon`. `tools/test-bridge-fixture/` has no `config.yaml` and
is correctly skipped.

**Edit 2 — the comment.** Insert a comment block in the blank line ABOVE the `docker-build-check:` target line,
following the placement precedent of the `verify-images` policy comment at `Makefile:96-103` (Makefile-level comment,
not a recipe comment). It must say:

- Which definition this site implements AFTER the change: **must pass Dockerfile linting** — any directory carrying
  `config.yaml` + `Dockerfile`, top level or under `tools/`.
- WHY it is wider than `validate-addons` above: the fixture's `Dockerfile` is really built by the verify suite, so it
  must lint; it is deliberately nested under `tools/` so it is not advertised as a repository add-on, which is why it is
  not held to the shipped-add-on structural contract. (Describe the intent from the fixture's own `config.yaml`/`README`
  — `slug: local_test-addon`, "live test target for the Phase 14 verify suite". Do NOT assert anything about Supervisor
  internals.)
- That these are `two deliberate definitions`, both correct, and that unifying them is not a fix. Use that exact
  three-word phrase — Task 3 greps for it as the family marker across all four sites.
- Why the ruleset here is stricter than the pre-commit `hadolint` hook: DL3008 and DL3006 are NOT suppressed in this
  target, which is the whole reason the coverage gap mattered.
- The boundary that remains open: the ARG-before-FROM half of this same target runs
  `internal/validate-dockerfile-args.sh`, whose `find . -maxdepth 2 -name "Dockerfile"` (line 64) matches
  `./<dir>/Dockerfile` only, so the nested fixture is not covered by that half. Record it as a known, unclosed boundary
  with the file:line, not as an oversight.

Repo conventions: recipe lines use hard tabs; write `$` only where the recipe already has it — refer to the
concatenation in prose (for example `"<addon_dir>Dockerfile"`) so no `$` appears in the comment at all. Keep every
comment line at or under 120 characters.
  </action>
  <verify>
    <automated>
D=$(mktemp -d)
make docker-build-check > "$D/dbc.log" 2>&1; EC=$?
cat "$D/dbc.log"

# EXACTLY these ten Dockerfiles were linted - the nested fixture is in, and no shipped add-on
# dropped out. Set equality via diff, so a missing or an extra entry both fail loudly by name.
sed -n 's/^  Checking \(.*\)\.\.\.$/\1/p' "$D/dbc.log" | sort > "$D/got-addons.txt"
printf '%s\n' authentik coding-assistants gatus iac-runner markdown-renderer meridian \
  network-tools phone-logger terraform-bridge tools/test-addon | sort > "$D/want-addons.txt"
diff -u "$D/want-addons.txt" "$D/got-addons.txt"

# exit code unchanged in KIND: still 1, and the hadolint finding SET is still exactly the
# pre-existing authentik one - a new finding anywhere would show up as a diff line.
test "$EC" -eq 1
sed -n 's/^\(.*Dockerfile:[0-9]* DL[0-9]*\).*$/\1/p' "$D/dbc.log" | sort -u > "$D/got-findings.txt"
printf '%s\n' 'authentik/Dockerfile:15 DL3008' > "$D/want-findings.txt"
diff -u "$D/want-findings.txt" "$D/got-findings.txt"
grep -q '❌ 1 Dockerfile(s) failed hadolint check' "$D/dbc.log"

# the fixture passes the strict ruleset on its own (coverage widened without importing a new failure)
hadolint --ignore DL3018 --ignore DL3059 --ignore DL4006 --ignore DL3016 tools/test-addon/Dockerfile

# the definition comment landed in the block ABOVE THIS TARGET (site-anchored, not a global count)
grep -B 20 '^docker-build-check:' Makefile > "$D/dbc-comment.txt"
grep -q 'two deliberate definitions' "$D/dbc-comment.txt"
grep -q 'must pass Dockerfile linting' "$D/dbc-comment.txt"
grep -q 'validate-dockerfile-args' "$D/dbc-comment.txt"

# nothing else in check-all moved
make check-all > /dev/null 2>&1
    </automated>
  </verify>
  <done>
`make docker-build-check` prints 10 `Checking` lines — all nine shipped add-ons plus `tools/test-addon` — and still
exits 1 for exactly one hadolint finding, `authentik/Dockerfile:15 DL3008`. `tools/test-addon/Dockerfile` passes the
target's strict ruleset standalone. `Makefile` carries a comment above `docker-build-check` naming the
`must pass Dockerfile linting` definition, the phrase `two deliberate definitions`, the DL3008/DL3006 rationale, and the
unclosed `internal/validate-dockerfile-args.sh` boundary. `make check-all` exits 0. Commit:
`build(260910-vyh): lint the nested test-addon Dockerfile in docker-build-check`.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Name the shipped-add-on definition at validate-addons and cross-reference it from both internal/ discovery sites (VYH-C)</name>
  <files>Makefile, internal/validate-versions.sh, internal/validate-addon-config.py</files>
  <reversibility rating="reversible">Comment-only edits in three files; no executable line changes.</reversibility>
  <action>
Comment-only. Do not change a single executable line in any of the three files — Task 3's verification asserts the
discovery results are numerically identical to Task 2's baseline.

**Site 1 — `Makefile`, above `validate-addons:` (currently line 75).** Insert a Makefile-level comment block in the
blank line above the target. It must state:
- The definition: **is a shipped add-on** — the top-level directories this repository advertises, held to the structural
  required-files contract (`config.yaml` + `Dockerfile` + `run.sh`) and a parseable `name`.
- Why depth 1 is correct HERE and not an oversight: `tools/test-addon/` is nested precisely so it is not advertised as a
  repository add-on, and its `config.yaml` is already schema-validated by
  `internal/validate-addon-config.py`'s explicit `tools/` pass — so the fixture is covered where coverage means
  something, and excluded where "shipped" is the question.
- The phrase `two deliberate definitions`, plus the pointer that `docker-build-check` below implements the wider one on
  purpose.

**Site 2 — `internal/validate-versions.sh`, the existing comment block at lines 83-87.** That block already explains
depth-2 and names `tools/test-addon/`; what is missing is the NAME of the definition and the existence of a second one.
Extend it (do not rewrite it) with the definition name `must pass version validation` and one sentence saying the
Makefile's `validate-addons` target implements the narrower `is a shipped add-on` definition on purpose — `two
deliberate definitions`, both correct, do not unify them. Match the block's existing `#`-prefixed wrap width.

**Site 3 — `internal/validate-addon-config.py`, the existing comment at lines 102-104** (4-space indent, inside the
`else:` branch). Same treatment: extend with the definition name `must pass config-schema validation` and the same
one-sentence cross-reference including `two deliberate definitions`. Match the surrounding narrow wrap width and keep
the comment inside the `else:` block where it is.

Every site must be self-sufficient: a reader landing on any one of the four sites learns which definition applies there
and why the other differs, without opening the other three. Comments in English, WHY-density matching what is already
in those files.
  </action>
  <verify>
    <automated>
D=$(mktemp -d)

# each of the four sites is checked WHERE IT LIVES, anchored to its own target/comment block,
# so no global tally can stand in for a site that was actually left uncommented
grep -B 12 '^validate-addons:' Makefile > "$D/va-comment.txt"
grep -q 'two deliberate definitions' "$D/va-comment.txt"
grep -q 'is a shipped add-on' "$D/va-comment.txt"
grep -B 20 '^docker-build-check:' Makefile > "$D/dbc-comment.txt"
grep -q 'two deliberate definitions' "$D/dbc-comment.txt"
grep -q 'must pass Dockerfile linting' "$D/dbc-comment.txt"
grep -q 'two deliberate definitions' internal/validate-versions.sh
grep -q 'must pass version validation' internal/validate-versions.sh
grep -q 'two deliberate definitions' internal/validate-addon-config.py
grep -q 'must pass config-schema validation' internal/validate-addon-config.py

# behaviour unchanged in kind: the three populations are set-identical to the measured baseline
make validate-addons > "$D/va.log" 2>&1; EC=$?; cat "$D/va.log"; test "$EC" -eq 0
sed -n 's|^✅ \(.*\)/ validation passed$|\1|p' "$D/va.log" | sort > "$D/va-got.txt"
printf '%s\n' authentik coding-assistants gatus iac-runner markdown-renderer meridian \
  network-tools phone-logger terraform-bridge | sort > "$D/va-want.txt"
diff -u "$D/va-want.txt" "$D/va-got.txt"

./internal/validate-versions.sh > "$D/vv.log" 2>&1; EC=$?; cat "$D/vv.log"; test "$EC" -eq 0
grep -qx 'Found add-ons: authentik coding-assistants gatus iac-runner markdown-renderer meridian network-tools phone-logger terraform-bridge tools/test-addon' "$D/vv.log"

python3 internal/validate-addon-config.py > "$D/vac.log" 2>&1; EC=$?; cat "$D/vac.log"; test "$EC" -eq 0
grep -q 'Add-on config validation passed' "$D/vac.log"

make docker-build-check > "$D/dbc.log" 2>&1 || true
sed -n 's/^  Checking \(.*\)\.\.\.$/\1/p' "$D/dbc.log" | sort > "$D/dbc-got.txt"
printf '%s\n' authentik coding-assistants gatus iac-runner markdown-renderer meridian \
  network-tools phone-logger terraform-bridge tools/test-addon | sort > "$D/dbc-want.txt"
diff -u "$D/dbc-want.txt" "$D/dbc-got.txt"

# no executable line moved in either internal/ script (git status captured, not swallowed mid-pipe)
git diff -U0 -- internal/validate-versions.sh internal/validate-addon-config.py > "$D/idiff.txt"
grep -E '^[+-]' "$D/idiff.txt" | grep -v '^[+-][+-]' | grep -vE '^[+-][[:space:]]*#' \
  | grep -vE '^[+-][[:space:]]*$' > "$D/noncomment.txt" || true
cat "$D/noncomment.txt"; test ! -s "$D/noncomment.txt"

# repo gates stay green and offline
make check-all > /dev/null 2>&1
pre-commit run shellcheck --files internal/validate-versions.sh > "$D/sc.log" 2>&1; EC=$?
cat "$D/sc.log"; test "$EC" -eq 0
    </automated>
  </verify>
  <done>
All four discovery sites name the definition they implement and cross-reference the other, and all four carry the
`two deliberate definitions` marker (`Makefile` twice, each `internal/` script once). `make validate-addons` still
reports 9, `internal/validate-versions.sh` still reports the same 10 add-ons in the same order,
`internal/validate-addon-config.py` still exits 0, `make docker-build-check` still reports 10, and the diff for both
`internal/` scripts contains comment lines only. `make check-all` exits 0. Commit:
`docs(260910-vyh): name the two deliberate add-on definitions at all four discovery sites`.
  </done>
</task>

</tasks>

<threat_model>
ASVS level 1; blocking threshold `high` (from `workflow.security_asvs_level: 1`, `workflow.security_block_on: high`).

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| public GitHub comment -> `opencode` job env | An untrusted commenter's `author_association` and comment body cross into a job whose environment holds an API key. The job-level `if:` is the only control. VYH-A guards it. |
| working tree -> commit -> `main` (public) | A transiently tampered security workflow could be committed if Task 1's restore is skipped. Local-only boundary, but the artifact is public. |
| local repo contents -> hook execution | `language: system` hooks execute repo-resident scripts with the developer's privileges on every matching commit. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-vyh-01 | Tampering | `.github/workflows/opencode.yml` during Task 1's adversarial verification | high | mitigate | Backup `cp` before the first tamper; `git checkout --` after EACH shape; `cmp`-guarded fallback restore from the backup; `git hash-object` asserted equal to the literal HEAD blob `bb9d1162327da41f894504f96d3d257ebd74c0ed`; `git status --porcelain` for the path asserted empty; both tamper scripts `sys.exit` if their anchor text drifted rather than writing a guess; explicit action rule that the Task 1 commit stages ONLY `.pre-commit-config.yaml` and that no `git add`/`git commit` may run while tampered. |
| T-vyh-02 | Tampering | the `opencode` job gate, future edits | high | mitigate | The whole point of VYH-A: `files:` covers the workflow AND the verifier, so any widening edit re-runs the 72-row truth table; proven red on two independent tamper shapes before the hook is trusted. |
| T-vyh-03 | Repudiation | hook bypass via `git commit --no-verify` | low | accept | Not closable at the pre-commit layer. `.github/workflows/lint.yml` runs `pre-commit run --all-files`, and the new hook's regex matches under `--all-files` (asserted in Task 1 step 6), so a bypassed commit still goes red before merge. |
| T-vyh-04 | Elevation of Privilege | `language: system` hook executing `internal/verify-opencode-gate.py` | low | accept | Same trust model as the three existing `repo: local` script/system hooks; the script is repo-resident, offline, stdlib + PyYAML, and reads one file. No new privilege is introduced. |
| T-vyh-05 | Information Disclosure | verifier output in terminal / CI logs | low | accept | Output is assertion names plus `author_association`/comment-body fixtures — all synthetic constants in the script. No secret is read. `gitleaks` remains active on the staged diff; no credential-shaped literal appears in any commit message or comment written by this plan. |
| T-vyh-06 | Denial of Service | hook latency on every matching commit | low | accept | Measured 0.08 s, offline. Narrow `files:` scoping means it does not run at all on the overwhelming majority of commits. |
| T-vyh-07 | Spoofing | `CONTRIBUTOR` reported by `renovate[bot]` | medium | mitigate | Already shipped by 260910-vh7 (CONTRIBUTOR excluded from the trusted set). VYH-A converts that decision from a comment into an enforced invariant — tamper shape B is exactly this regression, and it is proven to fail closed. |
| T-vyh-SC | Tampering | npm/pip/cargo installs | high | mitigate | **Not applicable by construction:** this plan performs no package-manager install. The hook uses `language: system` with NO `additional_dependencies`, so pre-commit resolves and fetches nothing; the verifier's only third-party import (`PyYAML`) is already required by the existing `validate-addon-config` hook. No `[ASSUMED]`/`[SUS]` package exists, so no legitimacy checkpoint is required. Any future edit adding `additional_dependencies` here re-opens this row. |
</threat_model>

<source_coverage_audit>
Quick task — no ROADMAP phase, no `REQUIREMENTS.md` IDs, no `RESEARCH.md`, no `CONTEXT.md` with `D-NN` decisions. The
single source is the orchestrator's `<constraints>` + `<research_already_done>`. Audited item by item:

| Source item | Status | Where |
|---|---|---|
| (a) wire `verify-opencode-gate.py` into pre-commit | COVERED | Task 1 |
| (a) justify the trigger scoping, state the trade-off, prefer narrowest that fails closed | COVERED | Task 1 action ("The scoping decision") + the hook comment it mandates |
| (b) close the `docker-build-check` hadolint coverage gap for `tools/test-addon` | COVERED | Task 2 Edit 1 |
| (b) reuse an existing discovery idiom, not a third mechanism | COVERED | Task 2 action — the explicit `tools/` pass idiom from `validate-addon-config.py` |
| (b) keep depth-1 behaviour and trailing-slash handling intact | COVERED | Task 2 action + `verify` (10 lines, all nine shipped names asserted individually) |
| (c) comment both Makefile sites | COVERED | Task 2 Edit 2 (`docker-build-check`) + Task 3 Site 1 (`validate-addons`) |
| (c) comment the two `internal/` discovery sites | COVERED | Task 3 Sites 2 and 3 — both already explain depth-2 but neither names its definition nor the existence of a second one; that is the delta |
| (c) say WHICH definition each site implements and WHY they differ | COVERED | four mandated definition names + the `two deliberate definitions` marker, all grep-asserted |
| adversarial verification for (a): fail on tamper, pass on real, restore byte-identical | COVERED | Task 1 verify steps 1-5, T-vyh-01 |
| adversarial verification for (b): fixture present, nine shipped present, counted, exit kind unchanged | COVERED | Task 2 verify |
| `make check-all` exits 0 and stays offline | COVERED | Tasks 2 and 3 verify |
| out-of-scope list stated so the executor cannot drift | COVERED | `<out_of_scope>` |
| commits atomic per task; no docs artifacts committed | COVERED | one commit message per task's `<done>`; no `.planning/` path in any `files_modified` |

**Planner capability contributions applied:**
- `security` (mandatory) — `<threat_model>` above, ASVS 1 / block-on-high.
- `api-coverage` — detector input would be an empty phase scope (quick task: no ROADMAP section, no pre-existing
  PLAN.md), which yields `{"skipped": true, "reason": "no_input"}`. Per the contribution's own branch, a `skipped`
  payload is not a `detected:false` verdict and the checkpoint is skipped for this run rather than asserting one.
  Substantively: this plan integrates no external API — it edits a Makefile, a pre-commit config, and three comments.
- `assumption-delta` — no ROADMAP phase to resolve; `phase_unresolved` -> skipped, non-blocking either way. No
  singular->plural / required->optional / derived->chosen transition is introduced: the two add-on definitions already
  both existed, and this plan names them rather than generalizing either.
- `schema-gate` — no ORM/schema files in scope. Skipped silently.
</source_coverage_audit>

<gate_preflight>
Every gate in this plan was RUN at planning time against unmodified HEAD, so none of them can pass for the wrong
reason. Recorded verdicts:

| Gate | Verdict at HEAD | Meaning |
|---|---|---|
| add-on set diff (`want-addons.txt` vs `got-addons.txt`) | **RED**, sole diff line `< tools/test-addon` | goes green ONLY when Task 2's widening lands; nothing else can satisfy it |
| hadolint finding set diff | **GREEN** (`authentik/Dockerfile:15 DL3008` only) | this is the no-new-failure invariant; it must STAY green |
| `❌ 1 Dockerfile(s) failed hadolint check` | **GREEN** | exit-kind is unchanged, not merely exit-code-equal |
| `two deliberate definitions` above `docker-build-check` | **RED** (exit 1) | goes green only when Task 2's comment lands |
| `two deliberate definitions` above `validate-addons` | **RED** (exit 1) | goes green only when Task 3's comment lands |
| both tamper shapes vs the verifier | **exit 1** with `30 untrusted rows allowed` / `6 untrusted rows allowed` | the Task 1 failure assertions are attributable to the denial invariant, not to a crash |
| `python3 internal/verify-opencode-gate.py --quiet` on the real file | **exit 0**, 5 PASS | the pass assertion is not vacuous either |

**Note for the plan checker on comment-text discipline:** three literals that `<verify>` greps for
(`two deliberate definitions`, `must pass Dockerfile linting`, `is a shipped add-on`) also appear in `<action>` bodies.
That is intentional and permitted: these are POSITIVE presence greps whose target IS the prose the executor is
instructed to write — naming the exact phrase is what makes the gate site-anchored and checkable. Discipline forbids
this only for NEGATIVE greps; the sole negative-grep literal in this plan is `Skipped`, which appears in no `<action>`
body (verified). The `two deliberate definitions` greps are also deliberately comment-counting: at these four sites the
comment IS the deliverable, so there is nothing else to assert. Each one is paired with a behaviour assertion (set-equal
add-on populations) so the docs task cannot go green while silently changing discovery.
</gate_preflight>

<verification>
Whole-plan gate, run once after Task 3:

```bash
D=$(mktemp -d)
make check-all                                    # exit 0, offline

make docker-build-check > "$D/dbc.log" 2>&1 || true
sed -n 's/^  Checking \(.*\)\.\.\.$/\1/p' "$D/dbc.log" | sort > "$D/got.txt"
printf '%s\n' authentik coding-assistants gatus iac-runner markdown-renderer meridian \
  network-tools phone-logger terraform-bridge tools/test-addon | sort > "$D/want.txt"
diff -u "$D/want.txt" "$D/got.txt"

test -z "$(git status --porcelain -- .github/workflows/opencode.yml)"
test "$(git hash-object .github/workflows/opencode.yml)" = "bb9d1162327da41f894504f96d3d257ebd74c0ed"

git log --oneline -3                              # three atomic commits
git show --name-only --format= HEAD~2 HEAD~1 HEAD > "$D/committed.txt"
test -z "$(grep '^\.planning/' "$D/committed.txt" || true)"
```
</verification>

<success_criteria>
- `verify-opencode-gate` is in `.pre-commit-config.yaml`, runs on `.github/workflows/opencode.yml` and on the verifier
  itself, skips otherwise, and is proven RED on both tamper shapes and GREEN on the real file.
- `.github/workflows/opencode.yml` is byte-identical to `bb9d1162327da41f894504f96d3d257ebd74c0ed`.
- `make docker-build-check` covers 10 Dockerfiles including `tools/test-addon/Dockerfile`, still exits 1 for exactly the
  pre-existing `authentik/Dockerfile:15 DL3008`, and for no new finding.
- All four discovery sites name their definition and cross-reference the other; `make validate-addons` still reports 9
  and `internal/validate-versions.sh` still reports the same 10 in the same order.
- `make check-all` exits 0 and stays offline.
- Three atomic commits; no `.planning/` artifact committed by the executor.
</success_criteria>

<output>
Create `.planning/quick/260910-vyh-close-the-docker-build-check-coverage-ga/260910-vyh-SUMMARY.md` when done.
</output>
