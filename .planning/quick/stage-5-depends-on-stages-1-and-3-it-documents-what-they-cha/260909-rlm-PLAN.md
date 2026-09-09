---
phase: quick-260909-rlm
plan: 01
type: execute
wave: 3
quick_id: 260909-rlm
depends_on: ["260909-rlj", "260909-rll"]
files_modified:
  - .github/RELEASE.md
  - docs/AUTO_UPDATE_GUIDE.md
autonomous: true
requirements:
  - QUICK-260909-rlm-a
  - QUICK-260909-rlm-b
  - QUICK-260909-rlm-c
  - QUICK-260909-rlm-d
  - QUICK-260909-rlm-e
estimate:
  tokens: 48000
  raw_tokens: 48000
  tasks: 3
  confidence: low
must_haves:
  truths:
    - "`.github/RELEASE.md` no longer claims the auto-update path is equivalent to a manual `make release`: the `## Auto-update path` section states that a workflow push made with the default `GITHUB_TOKEN` creates no workflow runs, and names `internal/dispatch-builds.sh` as what fires the builds instead."
    - "The `paths:`-filter claim in `### What this means operationally` is scoped to a human push, and carries the `GITHUB_TOKEN` caveat plus a cross-reference to the `## Auto-update path` section."
    - "`## Tag schema` states that `Every release ships as one git tag` describes the manual release paths only — `base-image-update.yml` has never tagged, and since 260909-rll the daily auto-update passes `--no-tag` — and states the measured tag/tree misalignment (2026-09-09: 15 of the 40 `<addon>/v*` tags point at a tree whose `build.yaml` VERSION is the previous version) with a reproduce command."
    - "The false assertion that the tag-triggered build leg produces the canonical image for its tag is gone from `.github/RELEASE.md`."
    - "Every present-tense caller-coverage count in `.github/RELEASE.md` matches the tree: exactly 6 workflow files carry the `tag-trigger temporarily disabled` comment, and the document says six, not seven, and does not claim the comment is present in every caller."
    - "`docs/AUTO_UPDATE_GUIDE.md` describes the shipped `auto-update.yml`: sequential `while read` processing of the four `.upstream.yaml` add-ons, per-add-on failure setting `ERRORS=1` and continuing, a non-zero job exit as the only failure signal, a bare `workflow_dispatch:` with no inputs, workflow name `Auto Update`, `addon.version_pattern` read by no code, and the `GITHUB_TOKEN` no-trigger limitation plus the `internal/dispatch-builds.sh` dispatch."
    - "The accurate daily-discovery description (`### 1. **Daily Check** (6:00 UTC)` and its three bullets) survives verbatim."
    - "Every slash-containing file path written in either document resolves to a real file in the tree."
    - "`make lint` exits 0 and is converged: a second consecutive run leaves both files byte-identical."
  artifacts:
    - ".github/RELEASE.md — corrected `## Tag schema` (new tag-guarantee subsection), corrected first paragraph of `### What this means operationally`, corrected double-build paragraph, one-word caller-count fix, rewritten `## Auto-update path`"
    - "docs/AUTO_UPDATE_GUIDE.md — rewritten against the shipped workflow; the 6:00-UTC discovery section preserved"
  key_links:
    - ".github/RELEASE.md `## Auto-update path` -> `internal/dispatch-builds.sh` (must exist: 260909-rlj) -> `gh workflow run build-<addon>.yml`"
    - ".github/RELEASE.md `## Tag schema` -> `--no-tag` in `.github/workflows/auto-update.yml` (must exist: 260909-rll)"
    - "`### What this means operationally` -> cross-reference -> `## Auto-update path` (the two paragraphs must not contradict)"
    - "docs/AUTO_UPDATE_GUIDE.md -> `.github/RELEASE.md` (guide covers the workflow surface, RELEASE.md covers the release/tag contract)"
    - "doc caller count 'six' -> `grep -rl 'tag-trigger temporarily disabled' .github/workflows/` == 6"
    - "doc add-on list -> `find . -maxdepth 2 -name .upstream.yaml` == authentik gatus meridian phone-logger"
---

<objective>
Make the two CI documents describe what the workflows actually do.

`.github/RELEASE.md` carries the sentence that hid this batch's root-cause bug for months
(the auto-update path "is identical to a manual `make release` — only the trigger differs"),
plus a `paths:`-filter claim that is true for a human push and silently untrue for the bot push,
plus a tag-schema section read as a repo-wide invariant it never was, plus a caller count that is
off by one. `docs/AUTO_UPDATE_GUIDE.md` is substantially fiction: it documents parallel updates
with a matrix, automatic GitHub issue creation, two `workflow_dispatch` inputs, a monitoring
dashboard, a recommended `addon.version_pattern` value, a workflow name and an add-on name —
none of which exist in this repository.

Purpose: an operator debugging a missing image reads these two files first. Every false claim in
them costs an investigation. This is a documentation-truth item, not a behaviour change: nothing
outside these two markdown files is touched.
Output: two edited files, landing as ONE commit. No new files.

Requirements: QUICK-260909-rlm-a (auto-update path), -b (paths: claim scoping), -c (tag schema
truth), -d (caller count), -e (guide rewrite).
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@.github/RELEASE.md
@docs/AUTO_UPDATE_GUIDE.md
@.github/workflows/auto-update.yml
@.planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio/260909-rlj-PLAN.md
@.planning/quick/stage-4-depends-on-stage-1-same-workflow-files-fix-the-tag-o/260909-rll-PLAN.md
</context>

<verified_environment>
Measured on the current tree (2026-09-09) BEFORE any sibling in this batch landed. Do NOT
re-derive these; do NOT contradict them. Every number below is a gate baseline.

| Fact | Measured value |
|---|---|
| `.github/RELEASE.md` / `docs/AUTO_UPDATE_GUIDE.md` | 189 / 160 lines |
| `.prettierignore` | excludes **only** `.planning/` — both target files ARE reflowed (`proseWrap: always`, `printWidth: 120`) |
| `.markdownlint-cli2.yaml` globs / ignores | `**/*.md`; ignores `**/.planning/**` — both target files ARE linted |
| `.markdownlint.json` MD013 | `line_length` / `heading_line_length` / `code_block_line_length` = 120 (ERROR); **`tables: false`** — table rows are exempt |
| `make lint` on the unmodified tree | **PASSES**, all 21 hooks, rc=0, tree unmodified afterwards |
| `.upstream.yaml` files | exactly 4: `authentik`, `gatus`, `meridian`, `phone-logger` |
| `build-*.yml` callers | 9 |
| files containing `tag-trigger temporarily disabled` | **6** (authentik, coding-assistants, gatus, markdown-renderer, meridian, phone-logger) |
| active `tags:` trigger | 3 (`build-iac-runner.yml`, `build-network-tools.yml`, `build-terraform-bridge.yml`) |
| `build-<addon>.yml` files at commit `287c79f` | **7** — so `### Why the split`'s historical "all seven" / "the other six" are CORRECT; leave them |
| `auto-update.yml` name / trigger | `name: Auto Update`; `workflow_dispatch:` at line 6 is **bare — no `inputs:`** |
| `auto-update.yml` loop | SEQUENTIAL `while IFS= read -r` (line 55) over `find . -maxdepth 2 -name .upstream.yaml \| sort` (line 123). No matrix, no fail-fast key |
| `auto-update.yml` `.upstream.yaml` keys read | exactly two: `.upstream.repository` (62), `.upstream.version_strip` (63); plus `.args.VERSION` from `build.yaml` (78) |
| issue creation in `auto-update.yml` | **none** — `grep -ni issue` returns nothing; a per-add-on error sets `ERRORS=1` + `continue`, and line 131 `exit $ERRORS` |
| version discovery | `gh release view --repo "$upstream_repo" --json tagName --jq .tagName` (66) — the repo's *latest release*; `version_strip` then applied as a `sed` regex (75) |
| `version_pattern` readers repo-wide (excl. `.planning/`) | **one**: `internal/update-base-image.py:56`, reading a regex from `internal/base-image-config.yaml` — a different file for a different workflow. `addon.version_pattern` and `upstream.version_pattern` in `.upstream.yaml` are read by NOBODY |
| CHANGELOG step | lines 101-116, conditional on a non-empty `gh release view --json body`; formatted with `npx --yes prettier@3.9.6` |
| commit / push shape | one `git commit` per add-on INSIDE the loop (120); ONE `git push` after the loop (127), guarded by `UPDATES_MADE` |
| `internal/update-base-image.py` git operations | **none** — so `base-image-update.yml` has never produced a tag |
| `.github/scripts/notify-ha.sh` callers | only `_build-template.yml` (lines 134, 199). `auto-update.yml` does NOT notify HA |
| `docs/WEBHOOK_SETUP.md` | exists; documents the build-workflow webhook. (Its own "seven per-addon callers" count is wrong — **out of scope**, do not fix here) |
| tag/tree audit, 2026-09-09 | **15 of 40** `<addon>/v*` tags point at a tree whose `build.yaml` `args.VERSION` differs from the tag, each at the previous version. 25 of 40 are correct |
| measured mismatch examples | `authentik/v2026.8.1` -> tree has `2026.8.0`; `meridian/v1.59.0` -> `1.58.3`; `terraform-bridge/v0.2.0` -> `0.1.0` (**a manual release** — the defect is in the documented procedure, not only in the bot) |
| cause of the misalignment | `internal/update-version.py` tags `HEAD` (line 418 guard -> `create_and_push_tag`) and does NOT commit the 3-file edits (line 436 prints a suggested `git add`/`git commit`). RELEASE.md step 1 therefore tags the PRE-bump commit; step 2 commits afterwards. The `## Patch flow` snippet has the same ordering |
| shell used by the harness here | NOT bash — a bare `f() { ... }` collided with an alias. **Run every gate as `bash <<'GATE' ... GATE`** |
| grep artifact | `grep -o '.upstream.repository'` matched a line containing neither key (`.` is a wildcard). **Every literal gate below uses `grep -o -F`** |

**Gate baselines on the unmodified tree** (whitespace-normalized whole file, `grep -o -F`):

| Literal | `.github/RELEASE.md` | `docs/AUTO_UPDATE_GUIDE.md` |
|---|---|---|
| `identical to a manual` | 1 | — |
| `canonical image for the tag` | 1 | — |
| `The seven callers` | 1 | — |
| `in each caller carries` | 1 | — |
| `internal/dispatch-builds.sh` | 0 | 0 |
| `GITHUB_TOKEN` | 0 | 0 |
| `--no-tag` | 0 | 0 |
| `base-image-update` | 0 | — |
| `authentik/v2026.8.1` | 0 | — |
| `terraform-bridge/v0.2.0` | 0 | — |
| `git show` | 0 | — |
| `2026-09-09` | 0 | — |
| `six callers` | 0 | — |
| `docs.github.com/actions/using-workflows/triggering-a-workflow` | 0 | — |
| `workflow_dispatch` | 0 | 0 |
| `human` | 0 | — |
| `fail-fast` | — | 1 |
| `addon_name` | — | 1 |
| `force_update` | — | 1 |
| `fritz-callmonitor2mqtt` | — | 1 |
| `Auto-Update Add-ons when upstream releases` | — | 1 |
| `Matrix View` | — | 1 |
| `Automatic GitHub issues` | — | 1 |
| `Automatic Issues` | — | 1 |
| `Parallel Updates` | — | 1 |
| `version_pattern: "auto"` | — | **3** |
| `Unlimited number of add-ons` | — | 1 |
| `Parallel processing of all add-ons` | — | 1 |
| `commit and issue history` | — | 1 |
| `The system can be extended` | — | 1 |
| `Auto Update` (with a space) | — | 0 |
| `ERRORS=1` | — | 0 |
| `sequential` (case-insensitive) | — | 0 |
| `auto-update.yml` | 1 | 0 |
| `update-version.py` | 2 | 0 |
| `.upstream.version_strip` | 0 | 0 |
| `internal/base-image-config.yaml` | 0 | 0 |
| `RELEASE.md` | — | 0 |
| `gh release view` | — | 0 |
| `authentik` / `gatus` / `meridian` / `phone-logger` | — | 0 / 0 / 0 / 0 |
| `0 6 * * *` | — | 1 |
| `discovers all add-ons with` | — | 1 |
| `Checks each configured upstream repository` | — | 1 |
| `Compares current with available versions` | — | 1 |

Path-existence audit on the unmodified tree: every slash-containing `` `path.ext` `` token in the
two files resolves — 0 MISSING. That gate (Task 3) is what mechanically ties this item to its
dependencies: writing `internal/dispatch-builds.sh` into the prose only passes once 260909-rlj
has landed.
</verified_environment>

<locked_constraints>
Non-negotiable. Any deviation is a defect.

- **L-1** Do NOT re-derive any fact in `<verified_environment>`. Do NOT contradict one.
- **L-2** ONLY these two files change: `.github/RELEASE.md`, `docs/AUTO_UPDATE_GUIDE.md`. No new
  files. No workflow, script, `AGENTS.md`, `CLAUDE.md`, `docs/DEVELOPMENT.md`,
  `docs/WEBHOOK_SETUP.md` or `markdown-renderer/README.md` edits, even where those carry the same
  defect class.
- **L-3 (the load-bearing rule)** Every claim written must be checkable against the file it
  describes. Cite the file, and the line number or the identifier, for every mechanical claim.
  Do NOT replace one set of fictional statements with another.
- **L-4 (no verbatim fiction)** The corrected documents must NOT quote any removed false string
  verbatim — not as an example, not in a "previously this said …" note, not in a changelog line.
  When documenting an absence, describe the real mechanism positively (e.g. state what the single
  failure signal IS, rather than reproducing the removed sentence about what it is not).
  Negative gates in `<verify>` depend on this.
- **L-5** Do NOT state a number this repository cannot substantiate. Counts that are true only at
  a point in time (the 15-of-40 tag audit) MUST carry the measurement date `2026-09-09` and a
  reproduce command; counts derivable from the tree (six comment-carrying callers, four
  `.upstream.yaml` add-ons) MUST match the tree exactly.
- **L-6** Preserve the accurate content: `docs/AUTO_UPDATE_GUIDE.md` lines 41-47 — the
  `## 🔄 What happens automatically` heading, the `### 1. **Daily Check** (6:00 UTC)` heading and
  its three bullets — stay byte-identical.
- **L-7** Keep both files' existing house style: emoji-prefixed `##` headings in the guide, plain
  ATX headings in `RELEASE.md`, 120-char lines, `proseWrap: always`.
- **L-8** `make lint` reflows both files. Run it, let it rewrite, run it again until a second
  consecutive run leaves both files byte-identical. ALL prose gates run only AFTER convergence,
  and every prose gate normalizes newlines to spaces first so a reflow cannot move a matched
  phrase out of reach.
- **L-9** Every gate literal is matched with `grep -o -F` (fixed string). Never a bare regex —
  an unescaped `.` produced a false positive during planning.
- **L-10** Run every gate under `bash <<'GATE' … GATE`. The harness shell is not bash and
  clobbers short function names with aliases.
</locked_constraints>

<ownership_boundary>
Sibling **260909-rln** (STAGE 6) also edits `.github/RELEASE.md` and runs AFTER this item. It
deletes the nine `build-<addon>.yml` callers, replaces them with one `build.yml`, and removes tag
triggers entirely.

**rln owns — do NOT touch:**

| Region | Lines (pre-change) | Content |
|---|---|---|
| the per-caller tag-trigger status table | 35-45 | the 9-row `Add-on / paths: / tag / image source` table |
| `### Re-enabling a tag trigger` | 97-105 | the heading and numbered steps 1-3 |

**This item claims:**

| Region | Lines (pre-change) | Item |
|---|---|---|
| `## Tag schema` intro + a NEW subsection | 8-29 (+ insert) | (c) — the durable home for the tag truth |
| the "in-file comment is in every caller" sentence | 53-54 | (d2) — one clause, same defect class as (d) |
| `### What this means operationally`, 1st paragraph | 77-79 | (b) |
| the double-build paragraph | 93-95 | (c) — surgical, one paragraph |
| the word `seven` in the closing paragraph of rln's section | 106 | (d) — **the only edit inside rln's region: one word** |
| `## Auto-update path` | 185-189 | (a) |

**Left alone deliberately:** lines 31-33 (accurate today), lines 47-51 (the image-source column
explanation, accurate), `### Why the split` 56-73 (its "all seven" / "the other six" are
*historical* statements about commit `287c79f`, where there really were 7 callers — correct as
written), lines 99-105 (rln's steps).

**Survivability rule:** put the durable truth for (c) inside `## Tag schema`, which rln does not
touch, so it survives even if rln deletes the double-build paragraph and the whole
tag-trigger discussion. Item (d)'s fix is deliberately one word so that a later rewrite of that
paragraph discards it harmlessly rather than producing a conflict.
</ownership_boundary>

<source_coverage_audit>
Quick-batch mode: there is no ROADMAP goal, `REQUIREMENTS.md` entry, `RESEARCH.md` or
`CONTEXT.md` for this item, so the sources are the item description and the orchestrator's
verified facts. Every source item is COVERED — nothing deferred, nothing silently dropped.

| Source | Item | Covered by | Gate |
|---|---|---|---|
| item text (a) | RELEASE.md:185-189 false equivalence; point at `internal/dispatch-builds.sh` | Task 1, edit (a) | A1..A8 |
| item text (b) | RELEASE.md:75-79 "is what fires the build" scoped to human pushes | Task 1, edit (b) | B1..B3 |
| item text (c) | Tag schema: auto-update no longer tags; not a repo-wide invariant; base-image never tagged | Task 1, edit (c) | C1, C2 |
| orchestrator fact (c+) | the defect is in the DOCUMENTED manual procedure: 15 of 40 tags off by one; RELEASE.md:93-95 asserts the opposite | Task 1, edits (c) and (c-surgical) | C3..C9, B4 |
| item text (d) | "The seven callers" vs the 6 files that carry the comment | Task 1, edit (d) | D0, D1, D2 |
| in-family extension (d2) | the adjacent claim that the comment sits in EVERY caller (6 of 9) | Task 1, edit (d2) | E1, E2 |
| item text (e) | AUTO_UPDATE_GUIDE.md brought in line: parallelism, issues, dispatch inputs, monitoring sections, `auto` pattern, workflow name, stale add-on name | Task 2, corrections 1-5 | N01..N14, Y01..Y18 |
| item text (e) | keep the accurate 6:00-UTC discovery description (lines 41-47) | Task 2, L-6 | K1..K6 |
| item text (e) | document the `GITHUB_TOKEN` no-trigger limitation and the new dispatch | Task 2, correction 6 | Y05..Y08, Y16 |
| item text VERIFY | `make lint` passes, run to convergence; markdownlint clean | Task 3 | C1, C2, C3 |
| item text VERIFY | every claim checkable against the file it describes | L-3 + Task 3 | C4a, C4, C5..C11 |
| sibling rlk (STAGE 3) | "consider whether the image-availability guard deserves a mention" | **Considered, declined.** rlk adds `internal/verify-image-availability.sh` + a workflow + a Makefile target. Neither of this item's two files documents the CI verification surface, and rlk's own plan owns its documentation. Mentioning a script this item cannot verify the shape of would manufacture exactly the class of unchecked claim L-3 forbids. Recorded here so the omission is a decision, not a gap. | — |
| sibling rln (STAGE 6) | the tag-trigger table and `### Re-enabling a tag trigger` | **Excluded by ownership**, see `<ownership_boundary>` — rln alone can resolve them | X1, X2 |
| out of scope | `docs/WEBHOOK_SETUP.md` "seven per-addon callers" (9 today), `markdown-renderer/README.md:50` citing a `.upstream.yaml` that does not exist, `AGENTS.md:83-87` + `CLAUDE.md:308-310` repeating the inert `version_pattern` keys | **Not gaps** — all four are the same defect class but outside this item's two declared files (L-2). Flagged for a follow-up item; do NOT fix here. | — |
</source_coverage_audit>

<tasks>

<task type="tracer">
  <name>Task 1: Correct .github/RELEASE.md — items (a), (b), (c), (d), (d2)</name>
  <files>.github/RELEASE.md</files>
  <precondition>Both dependencies have landed: `test -x internal/dispatch-builds.sh` succeeds (260909-rlj), `grep -c -F -e '--no-tag' .github/workflows/auto-update.yml` is at least 1 AND `grep -c -F -e 'internal/dispatch-builds.sh' .github/workflows/auto-update.yml` is at least 1 (260909-rll and 260909-rlj wired). If any assertion fails, HALT — the prose this task writes would assert behaviour the tree does not yet have, which is the exact defect this item exists to remove.</precondition>
  <read_first>
`.github/RELEASE.md` in full (189 lines). `.github/workflows/auto-update.yml` in full (131
lines) — you cite its line numbers. `internal/dispatch-builds.sh` header comment and its
`ADDON <name> <STATE>` stdout contract, plus the `<script_contract>` block of
`.planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio/260909-rlj-PLAN.md`
(states, exit semantics, WARN-vs-error). `internal/update-version.py` lines 404-443 (the
`--no-tag` guard and the printed next-steps) for item (c)'s mechanism claim.
  </read_first>
  <action>
Re-read `<ownership_boundary>` before the first edit. Five scoped edits, in this order. Per L-3
every mechanical claim cites its file and line/identifier; per L-4 none of the removed sentences
is quoted back.

**(c) `## Tag schema` — QUICK-260909-rlm-c.** Scope the opening invariant and add ONE new `###`
subsection at the end of the section (immediately before `## Standard release flow`). The prose
must establish, in this order:

1. The one-tag-per-release rule describes the MANUAL paths only — `## Standard release flow`
   step 1 and `## Patch flow`. Two automated paths ship untagged version bumps: `base-image-update.yml`,
   because `internal/update-base-image.py` performs no git operations at all and therefore never
   tagged; and, since 260909-rll, the daily `auto-update.yml`, which passes `--no-tag` to
   `internal/update-version.py`. Cross-reference `## Auto-update path`.
2. A `<addon>/v*` tag names an INTENDED version; it does not prove its tree carries that version.
   Mechanism: `internal/update-version.py` tags `HEAD` and does not commit the three edited files
   (it prints a suggested `git add` / `git commit` instead), so step 1 tags the pre-bump commit
   and step 2 creates the bump commit afterwards. The `## Patch flow` snippet has the same
   ordering.
3. The measurement, dated `2026-09-09`: 15 of the 40 `<addon>/v*` tags point at a tree whose
   `build.yaml` `args.VERSION` is the previous version; 25 are correct. Give exactly the three
   measured examples `authentik/v2026.8.1` (tree has `2026.8.0`), `meridian/v1.59.0` (tree has
   `1.58.3`) and `terraform-bridge/v0.2.0` (tree has `0.1.0`), and say explicitly that
   `terraform-bridge` has no `.upstream.yaml` — it is a manual release, so this is a defect in the
   documented procedure, not only in the bot.
   Do NOT overstate: name both numbers (15 mismatched, 25 correct).
4. A fenced `bash` reproduce block a reader can run, built on `git show "$tag:$addon/build.yaml"`
   over `git tag -l '*/v*'`. Keep every line of the block at 120 chars or fewer (MD013 applies to
   code blocks).
5. One sentence stating that reordering the release procedure so the commit precedes the tag is
   NOT done here — this pass documents the defect, it does not change `make release`.

**(b) `### What this means operationally`, first paragraph (77-79) — QUICK-260909-rlm-b.**
Keep the claim, scope it: pushing the three version files to `main` fires the `paths:` filter
**when a human pushes it**. Add that a push made by a GitHub Actions workflow with the default
`GITHUB_TOKEN` creates no workflow runs at all, so the automated path must dispatch its builds
explicitly, and cross-reference the `## Auto-update path` section by name. The word `human` and
the token name must both appear in this section.

**(c-surgical) the double-build paragraph (93-95).** Rewrite that ONE paragraph. The double build
itself is real (both triggers are active for those three add-ons); the claim that the
tag-triggered leg produces the canonical image for its tag is not — both legs read
`build.yaml:args.VERSION` from the ref they check out, and per (c) the tag's ref may carry the
previous version, so the tag-triggered leg is the leg MORE likely to build stale content. State
that instead. Do not touch the adjacent `### Re-enabling a tag trigger` heading or its steps.

**(d) line 106 — QUICK-260909-rlm-d.** Change the caller count from seven to six and nothing else
on that line. Six workflow files carry that comment (`grep -rl` in `<verified_environment>`).
This is the only edit inside rln's region; keep it to the one word. The resulting line must read
`The six callers carry the comment …` — gate `D1-says-six` matches that exact opening phrase.

**(d2) lines 53-54.** The sentence there asserts the in-file comment is present in *every*
caller. It is present in six of nine; the three add-ons with an active `tags:` block carry no such
comment. Scope the clause so the sentence says the comment sits in the six callers whose trigger
is disabled. The rewritten sentence MUST contain the literal two-word phrase `six callers` — gate
`E2-scoped-to-six` matches it, and `C9-doc-says-six` requires `six callers` at least twice in the
file (once here, once from (d)). Same defect class as (d), two lines from a claim being fixed —
leaving it would violate L-3.

**(a) `## Auto-update path` (185-189) — QUICK-260909-rlm-a.** Replace the entire body of the
section (keep the heading). The new body must establish:

1. What the workflow is: `auto-update.yml`, workflow name `Auto Update`, cron `0 6 * * *`, calling
   `internal/update-version.py` for each of the four `.upstream.yaml` add-ons (name them).
2. Why it is NOT equivalent to a manual `make release` — reason one: the workflow commits and
   pushes to `main` with the default `GITHUB_TOKEN`, and GitHub creates no workflow runs for
   events pushed with that token, so the `paths:` filter in `build-<addon>.yml` does not fire.
   The workflow therefore runs `internal/dispatch-builds.sh` immediately after `git push`; that
   script derives the changed add-on directories from `git diff --name-only "$BASE_SHA"..HEAD`
   and issues one `gh workflow run build-<addon>.yml --ref <ref>` per add-on.
   `workflow_dispatch` is the documented exception — a dispatch created with `GITHUB_TOKEN` DOES
   run. State the two error semantics from the script contract: a candidate with no
   `.github/workflows/build-<addon>.yml` is a warning that does not fail the run, and a failed
   dispatch makes the job exit non-zero because the bump is already on `main` and a green run
   would hide a manifest advertising an image that does not exist.
   Link `https://docs.github.com/actions/using-workflows/triggering-a-workflow`.
3. Why it is NOT equivalent — reason two: the path creates no tags (`--no-tag`); cross-reference
   `## Tag schema`.
4. A closing pointer to `docs/AUTO_UPDATE_GUIDE.md` for the discovery, error-handling and
   configuration surface.

Do NOT restate the false equivalence in any form, including a softened one.
  </action>
  <verify>
    <automated>
bash <<'GATE'
set -u
R=.github/RELEASE.md
F=0
nr() { sed -n "$1" "$R" | tr "\n" " " | tr -s " "; }
occ() { printf "%s" "$1" | grep -o -F -e "$2" | wc -l | tr -d " "; }
ck() { if [ "$2" -"$3" "$4" ]; then echo "PASS $1 ($2)"; else echo "FAIL $1 got=$2 want=$3 $4"; F=1; fi; }

# --- precondition: dependencies landed (baselines 0/0/0 before rlj+rll) ---
ck P1-rlj-script "$(test -x internal/dispatch-builds.sh && echo 1 || echo 0)" eq 1
ck P2-rll-notag "$(grep -c -F -e '--no-tag' .github/workflows/auto-update.yml)" ge 1
ck P3-rlj-wired "$(grep -c -F -e 'internal/dispatch-builds.sh' .github/workflows/auto-update.yml)" ge 1

# Every region below is asserted non-empty BEFORE any `eq 0` gate reads it. A silently failed
# `sed` would otherwise make every negative gate pass for the wrong reason. Measured region
# sizes on the unmodified tree: A 262, B 1588, C 6036, D 752, E 2254, WhySplit 1524 chars.
# --- (a) ## Auto-update path : baselines 0,0,0,0,1,0,0,0 ---
A=$(nr '/^## Auto-update path$/,$p')
ck A0-region-nonempty "$(printf '%s' "$A" | wc -c | tr -d ' ')" ge 100
ck A1-dispatch-script "$(occ "$A" 'internal/dispatch-builds.sh')" ge 1
ck A2-token "$(occ "$A" 'GITHUB_TOKEN')" ge 1
ck A3-wf-dispatch "$(occ "$A" 'workflow_dispatch')" ge 1
ck A4-docs-link "$(occ "$A" 'docs.github.com/actions/using-workflows/triggering-a-workflow')" ge 1
ck A5-no-false-equivalence "$(occ "$A" 'identical to a manual')" eq 0
ck A6-notag-xref "$(occ "$A" '--no-tag')" ge 1
ck A7-guide-xref "$(occ "$A" 'docs/AUTO_UPDATE_GUIDE.md')" ge 1
ck A8-real-name "$(occ "$A" 'Auto Update')" ge 1

# --- (b) ### What this means operationally : baselines 0,0,0,1 ---
B=$(nr '/^### What this means operationally$/,/^### Re-enabling a tag trigger$/p')
ck B0-region-nonempty "$(printf '%s' "$B" | wc -c | tr -d ' ')" ge 100
ck B1-human-scope "$(occ "$B" 'human')" ge 1
ck B2-token-caveat "$(occ "$B" 'GITHUB_TOKEN')" ge 1
ck B3-xref "$(occ "$B" 'Auto-update path')" ge 1
ck B4-no-canonical-claim "$(occ "$B" 'canonical image for the tag')" eq 0

# --- (c) ## Tag schema : baselines all 0 ---
C=$(nr '/^## Tag schema$/,/^## Standard release flow$/p')
ck C0-region-nonempty "$(printf '%s' "$C" | wc -c | tr -d ' ')" ge 100
ck C1-notag "$(occ "$C" '--no-tag')" ge 1
ck C2-baseimage "$(occ "$C" 'base-image-update')" ge 1
ck C3-dated "$(occ "$C" '2026-09-09')" ge 1
ck C4-count-15 "$(occ "$C" '15 of the 40')" ge 1
ck C5-count-25 "$(occ "$C" '25')" ge 1
ck C6-example-1 "$(occ "$C" 'authentik/v2026.8.1')" ge 1
ck C7-example-2 "$(occ "$C" 'meridian/v1.59.0')" ge 1
ck C8-example-3 "$(occ "$C" 'terraform-bridge/v0.2.0')" ge 1
ck C9-reproduce "$(occ "$C" 'git show')" ge 1

# --- (d) caller count agrees with the tree : baselines 6 / 0 / 1 ---
TREE=$(grep -rl -F -e 'tag-trigger temporarily disabled' .github/workflows/ | wc -l | tr -d " ")
ck D0-tree-is-six "$TREE" eq 6
D=$(nr '/^### Re-enabling a tag trigger$/,/^## Standard release flow$/p')
ck D0b-region-nonempty "$(printf '%s' "$D" | wc -c | tr -d ' ')" ge 100
ck D1-says-six "$(occ "$D" 'The six callers carry the comment')" ge 1
ck D2-not-seven "$(occ "$D" 'The seven callers')" eq 0

# --- (d2) coverage clause scoped : baselines 1 / 0 ---
E=$(nr '/^## Tag schema$/,/^### Why the split$/p')
ck E0-region-nonempty "$(printf '%s' "$E" | wc -c | tr -d ' ')" ge 100
ck E1-clause-rescoped "$(occ "$E" 'in each caller carries')" eq 0
ck E2-scoped-to-six "$(occ "$E" 'six callers')" ge 1

# --- rln's regions untouched : baselines 9 / 1 ---
ck X1-table-rows "$(grep -c -E '^\| (authentik|coding-assistants|gatus|iac-runner|markdown-renderer|meridian|network-tools|phone-logger|terraform-bridge) ' $R)" eq 9
ck X2-reenable-steps "$(occ "$D" 'git ls-remote --tags origin')" eq 1

# --- historical statements preserved : baseline 1 (region 1524 chars) ---
W=$(nr '/^### Why the split$/,/^### What this means operationally$/p')
ck H0-region-nonempty "$(printf '%s' "$W" | wc -c | tr -d ' ')" ge 100
ck H1-history-seven "$(occ "$W" 'all seven')" eq 1

# --- scope. Three hazards closed at once:
#   1. `git status --porcelain` (never a bare `git diff`, which reports nothing once a change is
#      committed and would pass vacuously) so staged AND unstaged AND untracked all count. Its
#      output is captured with its exit status checked, so a failed git cannot read as clean.
#   2. No relative `HEAD~N` anchor: with parallel sessions committing in this repo, HEAD~1 could
#      be a sibling item's commit. This gate is deliberately about the UNCOMMITTED tree and
#      halts loudly if the tree is clean - run it BEFORE the commit.
#   3. Z0 asserts the target file IS in the changed set, so "nothing was done" fails instead of
#      passing. Baseline today: Z0 = 0 (FAIL, correct), Z1 = 0 (PASS). ---
RAW=$(git status --porcelain --untracked-files=all) || { echo "FAIL scope: git status failed"; exit 1; }
CHANGED=$(printf '%s\n' "$RAW" | sed 's/^...//')
[ -n "$CHANGED" ] || { echo "FAIL scope: working tree is clean - run this gate BEFORE committing"; exit 1; }
ck Z0-release-changed "$(printf '%s\n' "$CHANGED" | grep -c -F -e '.github/RELEASE.md')" ge 1
ck Z1-scope "$(printf '%s\n' "$CHANGED" | grep -v -E '(^|/)\.planning/' | grep -v -E '^\.gsd/' | grep -v -F -e '.github/RELEASE.md' | grep -v -F -e 'docs/AUTO_UPDATE_GUIDE.md' | grep -c .)" eq 0

[ "$F" -eq 0 ] && echo "TASK1 ALL GATES PASS"
exit "$F"
GATE
    </automated>
  </verify>
  <done>All Task 1 gates print PASS. `.github/RELEASE.md` carries no false equivalence for the auto-update path, the `paths:` claim is scoped to human pushes with the token caveat, `## Tag schema` states the untagged automated paths plus the dated 15-of-40 measurement with a reproduce command, the canonical-image-for-the-tag claim is gone, and both caller-coverage claims match the 6 files the tree actually holds. rln's table (9 rows) and re-enable steps are intact.</done>
</task>

<task type="auto">
  <name>Task 2: Rewrite docs/AUTO_UPDATE_GUIDE.md against the shipped workflow — item (e)</name>
  <files>docs/AUTO_UPDATE_GUIDE.md</files>
  <precondition>Same as Task 1: `test -x internal/dispatch-builds.sh` succeeds and `grep -c -F -e '--no-tag' .github/workflows/auto-update.yml` is at least 1. HALT if either fails.</precondition>
  <read_first>
`docs/AUTO_UPDATE_GUIDE.md` in full (160 lines) — note which headings you must keep (L-6).
`.github/workflows/auto-update.yml` in full; you cite its line numbers throughout.
The four `.upstream.yaml` files (`authentik`, `gatus`, `meridian`, `phone-logger`) — note that
`phone-logger`'s is flatter (no comments) but structurally valid, `repository` correctly nested
under `upstream:`. `internal/dispatch-builds.sh` for the dispatch description.
`.github/RELEASE.md` AFTER Task 1 — the two documents must not contradict each other.
  </read_first>
  <action>
Rewrite the file so every statement is checkable against `.github/workflows/auto-update.yml` or
the four `.upstream.yaml` files. Per L-4, do not quote any removed claim verbatim anywhere —
describe the real mechanism positively instead. Requirement QUICK-260909-rlm-e.

**Keep byte-identical (L-6):** the `## 🔄 What happens automatically` heading, the
`### 1. **Daily Check** (6:00 UTC)` heading, and its three bullets (discovers add-ons with
`.upstream.yaml`, checks each configured upstream repository, compares current with available
versions). That description IS accurate.

**Corrections required, each replacing a fiction with the measured behaviour:**

1. **Processing model.** Rewrite the `### 2.` sub-heading and its body. Processing is SEQUENTIAL:
   one `while IFS= read -r` loop (`auto-update.yml:55`) over
   `find . -maxdepth 2 -name .upstream.yaml | sort` (line 123). There is no matrix and no
   per-add-on job, so the parallelism claim and the matrix fail-tolerance key it cited describe
   nothing in this repository. State what the loop actually does per add-on: read
   `.upstream.repository` and `.upstream.version_strip` (62-63), resolve the latest UPSTREAM
   RELEASE via `gh release view --repo … --json tagName --jq .tagName` (66), apply
   `version_strip` as a `sed` regex (75), compare against `.args.VERSION` in `build.yaml` (78),
   call `internal/update-version.py` (89) with `--no-tag`, prepend the upstream release body to
   `{addon}/CHANGELOG.md` only when that body is non-empty (101-116), and `git commit` per add-on
   INSIDE the loop (120) with ONE `git push` after it (127).
2. **Error handling.** Rewrite the `### 3.` body. No issue is opened anywhere: `grep -ni issue`
   over `auto-update.yml` returns nothing. The real mechanism is the only thing to document — a
   per-add-on failure prints an `ERROR:` line, sets `ERRORS=1`, and `continue`s to the next
   add-on; the loop completes; line 131 `exit $ERRORS` makes the job red. So one add-on's failure
   does not stop the others (that part of the old claim was true), and the failure signal is the
   run log plus the non-zero job conclusion. Add the dispatch failure semantics from
   `internal/dispatch-builds.sh`: a missing `build-<addon>.yml` warns without failing; a failed
   dispatch fails the run.
3. **Manual control.** Merge the two sub-sections into one. `auto-update.yml:6` is a bare
   `workflow_dispatch:` with no `inputs:`, so Actions offers no fields: a manual run always
   processes every `.upstream.yaml` add-on. Remove the per-add-on selection sub-section entirely,
   including its two input names — neither exists. Use the REAL workflow name `Auto Update` in
   the Actions-menu snippet. The add-on named in the current per-add-on snippet is a `fritz-…`
   service from a sibling project and is not in this repository; the four real add-ons are
   `authentik`, `gatus`, `meridian`, `phone-logger`, and `find . -maxdepth 2 -name .upstream.yaml`
   is the command that lists them.
4. **Configuration surface.** In BOTH the example `.upstream.yaml` (21-39) and
   `## 📋 Supported Configurations` (80-98) and the new-add-on template (113-121): the only keys
   the workflow reads are `upstream.repository` and `upstream.version_strip`.
   `addon.version_pattern` and `upstream.version_pattern` are read by no code — the single
   `version_pattern` reader in the repository is `internal/update-base-image.py:56`, which reads a
   regex from `internal/base-image-config.yaml` for a different workflow. Behaviour is
   unconditionally the sync strategy (the add-on version follows upstream, subpatch reset to
   `-0`). All four `.upstream.yaml` files set the sync value; none uses the auto value, and no
   code would honour it if one did. Every example in the file must therefore show the sync value,
   and the recommendation annotation on the auto value goes away. Say plainly that the two
   `version_pattern` keys are inert documentation of intent, and that `version_strip` is what
   actually transforms the tag — with the three real examples (`^v`, `^version/`,
   `^meridian-v`) drawn from the four files.
5. **Monitoring.** Rewrite `## 📊 Monitoring & Status` to the two things that exist: the workflow
   run list and log for `Auto Update`, and the commit history on `main` (one commit per updated
   add-on, subject `chore(<addon>): update to <version>`). Delete the per-add-on matrix-status
   bullet and the entire second sub-section about opened issues — neither describes anything in
   the repository.
6. **New GITHUB_TOKEN section (required by the item).** Add a section documenting the limitation
   and the dispatch, because in-file workflow comments are currently the only place it is written
   down: the workflow's own `git push` uses the default `GITHUB_TOKEN`; GitHub creates no workflow
   runs for such events, so `build-<addon>.yml`'s `paths:` filter never fires for a bot bump;
   `internal/dispatch-builds.sh` runs immediately after the push and issues one
   `gh workflow run build-<addon>.yml --ref <ref>` per changed add-on directory (derived from
   `git diff --name-only "$BASE_SHA"..HEAD`), which works because `workflow_dispatch` is the
   documented exception. Note the job needs `actions: write` for that. Link
   `https://docs.github.com/actions/using-workflows/triggering-a-workflow` and cross-reference
   `.github/RELEASE.md`.
7. **Tags.** State that this path creates no tags — `--no-tag` — and point at `.github/RELEASE.md`
   `## Tag schema` for what a tag does and does not prove.
8. **Adding a new add-on.** The `Done!` step is incomplete: the add-on is discovered by the next
   daily run, but it also needs `.github/workflows/build-<addon>.yml` or the dispatch will skip it
   with a warning and no image will be built. Say so.
9. **Schedule.** Scope the cron block: the configured schedule is the single
   `- cron: "0 6 * * *"` at `auto-update.yml:4-5`; the other cron lines are illustrative
   alternatives, not active configuration. Keep the `0 6 * * *` literal.
10. **Webhook.** Replace the speculative extension paragraph. The truth: `auto-update.yml` sends
    no webhook; the per-add-on build workflows do, via `_build-template.yml` calling
    `.github/scripts/notify-ha.sh`, documented in `docs/WEBHOOK_SETUP.md`. Since the dispatch now
    makes those builds fire for bot bumps, an automated update does reach that notification path.
11. **Closing summary.** Rewrite the benefits paragraph. Drop the unlimited-add-ons and
    parallel-processing claims and the claim of an issue history. What is defensible: discovery is
    automatic (any directory with a `.upstream.yaml` is picked up with no workflow edit), one
    add-on's failure does not stop the others, and every change is one reviewable commit on
    `main`.

Structural rules: keep the emoji-prefixed `##` heading style; keep every line at 120 chars or
fewer including fenced code blocks; write `yaml` / `text` / `bash` language tags on fences as the
file already does.
  </action>
  <verify>
    <automated>
bash <<'GATE'
set -u
G=docs/AUTO_UPDATE_GUIDE.md
F=0
NG=$(tr "\n" " " < $G | tr -s " ")
occ() { printf "%s" "$1" | grep -o -F -e "$2" | wc -l | tr -d " "; }
occi() { printf "%s" "$1" | grep -o -i -F -e "$2" | wc -l | tr -d " "; }
ck() { if [ "$2" -"$3" "$4" ]; then echo "PASS $1 ($2)"; else echo "FAIL $1 got=$2 want=$3 $4"; F=1; fi; }

# Non-emptiness first: an unreadable file would make every `eq 0` gate below pass for the wrong
# reason. Normalized size on the unmodified tree: 3759 chars.
ck G0-nonempty "$(printf '%s' "$NG" | wc -c | tr -d ' ')" ge 1000

# --- fiction removed (every baseline was 1, except version_pattern-auto which was 3) ---
ck N01-parallel-heading "$(occ "$NG" 'Parallel Updates')" eq 0
ck N02-failfast "$(occ "$NG" 'fail-fast')" eq 0
ck N03-auto-issues-bullet "$(occ "$NG" 'Automatic GitHub issues')" eq 0
ck N04-auto-issues-section "$(occ "$NG" 'Automatic Issues')" eq 0
ck N05-matrix-view "$(occ "$NG" 'Matrix View')" eq 0
ck N06-input-1 "$(occ "$NG" 'addon_name')" eq 0
ck N07-input-2 "$(occ "$NG" 'force_update')" eq 0
ck N08-stale-addon "$(occ "$NG" 'fritz-callmonitor2mqtt')" eq 0
ck N09-fake-wf-name "$(occ "$NG" 'Auto-Update Add-ons when upstream releases')" eq 0
ck N10-auto-pattern "$(occ "$NG" 'version_pattern: "auto"')" eq 0
ck N11-unlimited "$(occ "$NG" 'Unlimited number of add-ons')" eq 0
ck N12-parallel-benefit "$(occ "$NG" 'Parallel processing of all add-ons')" eq 0
ck N13-issue-history "$(occ "$NG" 'commit and issue history')" eq 0
ck N14-speculative "$(occ "$NG" 'The system can be extended')" eq 0

# --- reality present (every baseline was 0) ---
ck Y01-real-wf-name "$(occ "$NG" 'Auto Update')" ge 1
ck Y02-workflow-file "$(occ "$NG" 'auto-update.yml')" ge 1
ck Y03-sequential "$(occi "$NG" 'sequential')" ge 1
ck Y04-errors-var "$(occ "$NG" 'ERRORS=1')" ge 1
ck Y05-bare-dispatch "$(occ "$NG" 'workflow_dispatch')" ge 1
ck Y06-token "$(occ "$NG" 'GITHUB_TOKEN')" ge 1
ck Y07-dispatch-script "$(occ "$NG" 'internal/dispatch-builds.sh')" ge 1
ck Y08-docs-link "$(occ "$NG" 'docs.github.com/actions/using-workflows/triggering-a-workflow')" ge 1
ck Y09-notag "$(occ "$NG" '--no-tag')" ge 1
ck Y10-release-xref "$(occ "$NG" 'RELEASE.md')" ge 1
ck Y11-updver "$(occ "$NG" 'update-version.py')" ge 1
ck Y12-gh-release-view "$(occ "$NG" 'gh release view')" ge 1
ck Y13-repo-key "$(occ "$NG" 'upstream.repository')" ge 1
ck Y14-strip-key "$(occ "$NG" 'upstream.version_strip')" ge 1
ck Y15-other-pattern-reader "$(occ "$NG" 'internal/base-image-config.yaml')" ge 1
ck Y16-actions-write "$(occ "$NG" 'actions: write')" ge 1
ck Y17-webhook-truth "$(occ "$NG" 'notify-ha.sh')" ge 1
ck Y18-sync-value "$(occ "$NG" 'version_pattern: "sync"')" ge 1

# --- the doc's add-on list equals the tree's ---
EXPECT=$(find . -maxdepth 2 -name .upstream.yaml | sed 's|^\./||; s|/\.upstream\.yaml$||' | sort)
ck Y19-tree-count "$(printf '%s\n' "$EXPECT" | wc -l | tr -d ' ')" eq 4
for a in $EXPECT; do ck "Y20-names-$a" "$(occ "$NG" "$a")" ge 1; done

# --- accurate content preserved verbatim (L-6) ---
ck K1-happens-heading "$(grep -c -F -e '## 🔄 What happens automatically' $G)" eq 1
ck K2-daily-heading "$(grep -c -F -e '### 1. **Daily Check** (6:00 UTC)' $G)" eq 1
ck K3-bullet-1 "$(occ "$NG" 'discovers all add-ons with')" ge 1
ck K4-bullet-2 "$(occ "$NG" 'Checks each configured upstream repository')" ge 1
ck K5-bullet-3 "$(occ "$NG" 'Compares current with available versions')" ge 1
ck K6-cron "$(occ "$NG" '0 6 * * *')" ge 1

# --- line length (MD013 is an ERROR at 120; tables are exempt) ---
ck L1-max-line "$(awk 'length($0) > 120 && $0 !~ /^\|/ {c++} END {print c+0}' $G)" eq 0

# --- scope, same three hazards as Task 1. Baseline today: Z0 = 0 (FAIL, correct), Z1 = 0 ---
RAW=$(git status --porcelain --untracked-files=all) || { echo "FAIL scope: git status failed"; exit 1; }
CHANGED=$(printf '%s\n' "$RAW" | sed 's/^...//')
[ -n "$CHANGED" ] || { echo "FAIL scope: working tree is clean - run this gate BEFORE committing"; exit 1; }
ck Z0-guide-changed "$(printf '%s\n' "$CHANGED" | grep -c -F -e 'docs/AUTO_UPDATE_GUIDE.md')" ge 1
ck Z1-scope "$(printf '%s\n' "$CHANGED" | grep -v -E '(^|/)\.planning/' | grep -v -E '^\.gsd/' | grep -v -F -e '.github/RELEASE.md' | grep -v -F -e 'docs/AUTO_UPDATE_GUIDE.md' | grep -c .)" eq 0

[ "$F" -eq 0 ] && echo "TASK2 ALL GATES PASS"
exit "$F"
GATE
    </automated>
  </verify>
  <done>All Task 2 gates print PASS. `docs/AUTO_UPDATE_GUIDE.md` describes the sequential loop, the real error path (`ERRORS=1` plus a non-zero job exit), the inputless `workflow_dispatch`, the real workflow name `Auto Update`, the two `.upstream.yaml` keys that are actually read plus where the only real `version_pattern` reader lives, the `GITHUB_TOKEN` limitation with the `internal/dispatch-builds.sh` dispatch, `--no-tag`, and the four real add-on names — and none of the removed claims survives in any form. The 6:00-UTC discovery section is byte-identical.</done>
</task>

<task type="auto">
  <name>Task 3: Converge make lint, then prove every path and cross-reference resolves</name>
  <files>.github/RELEASE.md, docs/AUTO_UPDATE_GUIDE.md</files>
  <read_first>
Both files as Tasks 1 and 2 left them. `.prettierrc.yaml` (`printWidth: 120`,
`proseWrap: always`) and `.markdownlint.json` (MD013 at 120, `tables: false`).
  </read_first>
  <action>
Run `make lint`. Prettier WILL reflow both files on the first run (they are outside
`.planning/`, which is the only `.prettierignore` entry) and the hook will report a failure
because it modified files. Re-run until a run exits 0 and a second consecutive run leaves both
files byte-identical — that is the convergence condition in L-8, and it is asserted by the gate
below rather than assumed.

Then fix anything the linters flag: markdownlint MD013 is an ERROR at 120 chars for body text,
headings and fenced code blocks (table rows are exempt via `tables: false`). If prettier's reflow
has split a phrase across a line break, do NOT re-word to satisfy a gate — every prose gate
normalizes newlines to spaces first, so a reflow cannot break one. Re-word only for a real lint
error.

Finally, re-run the Task 1 and Task 2 gate blocks in full against the converged files, and settle
the two cross-document invariants: `.github/RELEASE.md` must point at
`docs/AUTO_UPDATE_GUIDE.md` for the workflow surface and the guide must point back at
`.github/RELEASE.md` for the release/tag contract, and neither may state a different value for
the same fact (add-on count, workflow name, dispatch semantics).
  </action>
  <verify>
    <automated>
bash <<'GATE'
set -u
F=0
ck() { if [ "$2" -"$3" "$4" ]; then echo "PASS $1 ($2)"; else echo "FAIL $1 got=$2 want=$3 $4"; F=1; fi; }

# --- lint converged: run once (may rewrite), snapshot, run again, compare ---
make lint >/dev/null 2>&1 || true
SNAP=$(sha256sum .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md)
make lint; RC=$?
ck C1-make-lint-rc "$RC" eq 0
AFTER=$(sha256sum .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md)
ck C2-converged "$([ "$SNAP" = "$AFTER" ] && echo 1 || echo 0)" eq 1

# --- markdownlint specifically (hook 13 of make lint), re-asserted standalone ---
ck C3-markdownlint "$(pre-commit run markdownlint-cli2 --files .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md >/dev/null 2>&1 && echo 0 || echo 1)" eq 0

# --- every slash-containing `path.ext` token resolves (baseline: 0 MISSING).
# The token list is captured and asserted non-empty first: an extraction that silently yields
# nothing would report 0 MISSING and pass for the wrong reason. Both docs reference at least 7
# slash-paths today, so a below-5 token count means the probe, not the docs, is broken. ---
TOKENS=$(grep -ohE '`[A-Za-z0-9_./{}<>-]+\.(md|yml|yaml|py|sh)`' .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md || true)
ck C4a-tokens-found "$(printf '%s\n' "$TOKENS" | grep -c .)" ge 5
MISSING=$(printf '%s\n' "$TOKENS" | tr -d '`' | sort -u | while read -r p; do
      case "$p" in */*) ;; *) continue;; esac
      case "$p" in *'<addon>'*|*'{addon}'*|*'<name>'*|*'<repo>'*) continue;; esac
      [ -e "$p" ] || echo "$p"
    done | grep -c .)
ck C4-no-invented-paths "$MISSING" eq 0

# --- cross-references in both directions : baselines 1 / 0 ---
ck C5-release-to-guide "$(grep -c -F -e 'docs/AUTO_UPDATE_GUIDE.md' .github/RELEASE.md)" ge 1
ck C6-guide-to-release "$(grep -c -F -e 'RELEASE.md' docs/AUTO_UPDATE_GUIDE.md)" ge 1

# --- the two docs agree with the tree on the two derived counts : baselines 4 / 6 / 0 ---
ck C7-tree-addons "$(find . -maxdepth 2 -name .upstream.yaml | wc -l | tr -d ' ')" eq 4
ck C8-tree-callers "$(grep -rl -F -e 'tag-trigger temporarily disabled' .github/workflows/ | wc -l | tr -d ' ')" eq 6
ck C9-doc-says-six "$(tr "\n" " " < .github/RELEASE.md | tr -s " " | grep -o -F -e 'six callers' | wc -l | tr -d ' ')" ge 2

# --- both docs name the real workflow : baselines 0 / 0 ---
ck C10-name-release "$(grep -c -F -e 'Auto Update' .github/RELEASE.md)" ge 1
ck C11-name-guide "$(grep -c -F -e 'Auto Update' docs/AUTO_UPDATE_GUIDE.md)" ge 1

# --- scope, same three hazards as Task 1; here BOTH files must be in the changed set.
# Baseline today: C12a = 0 and C12b = 0 (both FAIL, correct), C12 = 0 (PASS) ---
RAW=$(git status --porcelain --untracked-files=all) || { echo "FAIL scope: git status failed"; exit 1; }
CHANGED=$(printf '%s\n' "$RAW" | sed 's/^...//')
[ -n "$CHANGED" ] || { echo "FAIL scope: working tree is clean - run this gate BEFORE committing"; exit 1; }
ck C12a-release-changed "$(printf '%s\n' "$CHANGED" | grep -c -F -e '.github/RELEASE.md')" ge 1
ck C12b-guide-changed "$(printf '%s\n' "$CHANGED" | grep -c -F -e 'docs/AUTO_UPDATE_GUIDE.md')" ge 1
ck C12-scope "$(printf '%s\n' "$CHANGED" | grep -v -E '(^|/)\.planning/' | grep -v -E '^\.gsd/' | grep -v -F -e '.github/RELEASE.md' | grep -v -F -e 'docs/AUTO_UPDATE_GUIDE.md' | grep -c .)" eq 0

[ "$F" -eq 0 ] && echo "TASK3 ALL GATES PASS"
exit "$F"
GATE
    </automated>
  </verify>
  <done>`make lint` exits 0 and is converged (a second consecutive run leaves both files byte-identical). markdownlint is clean on both files. Every slash-containing file path written in either document resolves to a real file. Both documents cross-reference each other, agree on the workflow name, and agree with the tree on the four `.upstream.yaml` add-ons and the six comment-carrying callers. Nothing outside the two markdown files changed. Re-running the Task 1 and Task 2 gate blocks after convergence still yields all PASS.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator -> documentation | The only boundary in scope. An operator debugging a missing image acts on what these two files claim; a false claim is an operational hazard, which is why this item exists. |
| (no code boundary) | Documentation-only change. No executable, workflow, container, network listener or credential handling is touched (L-2), so no new data path crosses a trust boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-rlm-01 | Tampering | `.github/RELEASE.md` operational guidance | medium | mitigate | A wrong procedure is a tampered instruction an operator executes. L-3 requires every mechanical claim to cite the file and line it describes, and the Task 3 gate rejects any path that does not resolve. Item (c) explicitly states the tag-vs-tree defect rather than leaving a procedure that silently produces mislabelled tags. |
| T-rlm-02 | Information Disclosure | `GITHUB_TOKEN` / secret names in prose | low | mitigate | Only the token's NAME and its documented no-trigger behaviour are written, both already public in `auto-update.yml:48` and in GitHub's own docs. No secret value, no `secrets.*` value, no webhook ID, no HA URL is added to either file. |
| T-rlm-03 | Repudiation | the 15-of-40 tag audit claim | low | mitigate | The claim is dated `2026-09-09` and shipped with a reproduce command built on `git tag -l` + `git show`, so a reader can re-derive it instead of trusting the sentence. L-5 forbids an undated point-in-time count. |
| T-rlm-04 | Denial of Service | `make lint` convergence loop | low | accept | Prettier rewrites both files on the first run; the Task 3 gate bounds this by asserting convergence on a second consecutive run rather than looping unbounded. Worst case is a failed gate, not a hung run. |
| T-rlm-SC | Tampering | npm/pip/cargo installs | low | accept | **No package installs in this item.** No `package.json`, `requirements.txt` or lockfile is touched; `make lint` uses the already-installed pre-commit hook environments. The package-legitimacy gate is therefore not applicable and no `RESEARCH.md` legitimacy table is required. |

ASVS level 1, block-on `high`: no `high` or `critical` threat is present, so nothing here blocks.
</threat_model>

<verification>
1. Dependency preconditions hold: `internal/dispatch-builds.sh` is executable and referenced from
   `.github/workflows/auto-update.yml`, and that workflow passes `--no-tag`. Without both, this
   item's prose would be false on arrival.
2. Task 1 gate block: all PASS.
3. Task 2 gate block: all PASS.
4. Task 3 gate block: all PASS, including `make lint` rc=0 AND convergence, markdownlint clean,
   zero unresolvable paths, bidirectional cross-references, and tree-count agreement.
5. Re-run the Task 1 and Task 2 gate blocks after lint convergence — reflow must not have broken
   any of them (they normalize newlines, so this is a check, not a repair step).
6. `git status --porcelain --untracked-files=all`, filtered of `.planning/` and `.gsd/`, lists
   exactly `.github/RELEASE.md` and `docs/AUTO_UPDATE_GUIDE.md` — and lists BOTH, so "nothing was
   done" cannot pass. Run every gate block BEFORE the commit; the scope gates deliberately read
   the uncommitted tree rather than a relative `HEAD~N` range, because sibling items in this batch
   commit in parallel and `HEAD~1` may not be this item's parent.
7. rln's two owned regions survive: the 9-row tag-trigger table still has 9 rows, and
   `### Re-enabling a tag trigger` still holds its three numbered steps.
</verification>

<success_criteria>
- One commit, two files: `docs(ci): make RELEASE.md and AUTO_UPDATE_GUIDE.md describe the real workflows`.
- Items (a) through (e) all delivered; (d2) delivered as the in-family extension of (d).
- Every gate in all three tasks passes on the converged tree.
- No claim written that cannot be checked against the file it describes; no removed false string
  quoted verbatim anywhere in either document.
- rln's table and `### Re-enabling a tag trigger` steps untouched; the only edit inside rln's
  region is the single word on line 106.
</success_criteria>

<output>
Create `.planning/quick/stage-5-depends-on-stages-1-and-3-it-documents-what-they-cha/260909-rlm-SUMMARY.md` when done.

Record in the summary: the converged line counts of both files, the number of `make lint`
iterations convergence required, the final Task 1/2/3 gate output, and any claim you chose to
word differently from this plan (with the file:line evidence that made the plan's wording wrong).
</output>
