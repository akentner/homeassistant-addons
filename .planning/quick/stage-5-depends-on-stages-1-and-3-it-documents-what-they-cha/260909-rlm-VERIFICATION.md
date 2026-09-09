---
quick_id: 260909-rlm
batch: 260909-rli
stage: 5
commit: 833c176e30b53c522201973de96abab9b5f0e792
verified_at: "2026-09-10"
verified_against_head: c43375f35fb024406fd0cf1c083c6baa3adbfae8
status: incomplete
verdict: gaps_found
score: 10/13 tested claims hold
findings:
  false: 3
  stale: 4
  imprecise: 4
files_verified:
  - .github/RELEASE.md
  - docs/AUTO_UPDATE_GUIDE.md
drift_since_commit: none in the two target files (git diff 833c176 HEAD -- both files = empty)
---

# Verification — 260909-rlm (Stage 5, docs truth pass)

## Verdict

**incomplete.** 3 FALSE, 4 STALE, 4 IMPRECISE.

The commit's central mechanism claims are **correct and correctly scoped**: the `GITHUB_TOKEN`
no-trigger statement, the `paths:`-filter scoping, `--no-tag`, the `update-version.py` tag-before-commit
ordering, the 15 mismatched tags, the `terraform-bridge/v0.2.0` proof, the six-of-nine tag-trigger count,
and the shipped reproduce command all survive direct testing against the workflows and against git
history. All four of the executor's mid-flight self-corrections (SUMMARY "Deviations from Plan" 1-4) are
sound — every line number it re-cited resolves to the construct it names, and both weaker phrasings
("an older version", no `notify-ha.sh` exclusivity) are the defensible ones.

But the pass **introduced two new false claims** and **left one pre-existing false claim standing**, and
four statements have gone stale — three of them because `260909-wgm` (`2ba51a2`, `c43375f`) turned the
pre-push hook advisory today, and one because two tags were created 3-7 minutes *after* this commit was
authored.

The two target files are byte-identical to `833c176` at HEAD, so every finding below is against text
that is live right now:

```
$ git diff 833c176 HEAD -- .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md
(empty)
$ wc -l .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md
264 .github/RELEASE.md
231 docs/AUTO_UPDATE_GUIDE.md
```

Per method discipline: I did **not** re-run the executor's 102 gates. Every claim below was tested by
reading the ground-truth file or executing a command; the command and its real output are quoted.

---

## Claim 1 — "A push made with the default GITHUB_TOKEN creates no workflow runs" — VERIFIED, correctly scoped

Three sites carry this claim, and all three scope it to *events the pushing workflow's own token
generates*, not to pushes in general:

- `.github/RELEASE.md:84-86` — "A push made **by a GitHub Actions workflow** with the default
  `GITHUB_TOKEN` creates no workflow runs at all"
- `.github/RELEASE.md:246` — "The workflow commits and pushes to `main` with the default `GITHUB_TOKEN`,
  and GitHub creates no workflow runs **for an event produced by that token**"
- `docs/AUTO_UPDATE_GUIDE.md:118` — "The workflow pushes to `main` using the default `GITHUB_TOKEN`, and
  GitHub creates **no** workflow runs **for an event produced by that token**"

None of the three generalises to human pushes. All three name the `workflow_dispatch` exception and cite
the GitHub doc URL. Ground truth for the mechanism being the one in play:

```
$ sed -n '59,68p' .github/workflows/auto-update.yml
      # NOTE: a push made with GITHUB_TOKEN creates NO workflow runs at all (documented
      # GitHub limitation) — not lint.yml, and not build-<addon>.yml, which triggers on
      # `push` to main with `paths: <addon>/**`. ...
      - name: Check and update add-ons
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

The measured evidence behind it is in `internal/dispatch-builds.sh:15-22` (commit `d3682f6` → zero
`build-meridian` runs; `amd64-meridian:1.68.0-0` → HTTP 404) and is recorded as measured in HANDOVER §1,
so not re-derived here.

**Status: VERIFIED.**

---

## Claim 2 — the `paths:` filter claim is scoped to a human push, with a working cross-reference — VERIFIED

`.github/RELEASE.md:80-86`:

> For the six add-ons with the tag-trigger disabled, pushing the tag alone does **not** build an image.
> **When a human pushes** step 2 of the release flow below ... that push is what fires the build, via the
> `paths:` filter.
>
> That scoping is load-bearing. A push made by a GitHub Actions workflow with the default `GITHUB_TOKEN`
> creates no workflow runs at all ... **See `## Auto-update path`** for how it does that.

Cross-reference target exists and says what the reference claims:

```
$ grep -n '^## Auto-update path' .github/RELEASE.md
238:## Auto-update path
```

`RELEASE.md:245-258` is that section, and it does explain "how it does that" — `dispatch-builds.sh` after
`git push`, `actions: write`, and the two error semantics. Every other cross-reference in the two files
also resolves: `### What a tag guarantees` (line 119, referenced from 103 and 260), `## Tag schema` (8),
`## Standard release flow` (162), `## Patch flow` (205), `docs/AUTO_UPDATE_GUIDE.md`, `.github/RELEASE.md`,
`docs/DEVELOPMENT.md` and `docs/WEBHOOK_SETUP.md` (both present in `docs/`).

**Status: VERIFIED.**

---

## Claim 3 — "base-image-update.yml has no git operations at all" — FAILS as stated in the commit message; the shipped text is narrower but misleading

Commit message (`833c176`):

> The one-tag rule covers the manual paths only (**base-image-update.yml has no git operations at all**;
> auto-update.yml passes --no-tag).

Ground truth:

```
$ grep -n 'git ' .github/workflows/base-image-update.yml
48:          git config user.name "github-actions[bot]"
49:          git config user.email "github-actions[bot]@users.noreply.github.com"
69:          BASE_SHA=$(git rev-parse HEAD)
85:            if git diff --quiet; then
94:            git add "$addon/build.yaml" "$addon/config.yaml" "$addon/README.md"
95:            git commit -m "chore($addon): bump base image, update to $new_version"
112:            git push
113:            ./internal/dispatch-builds.sh || ERRORS=1
```

The workflow configures a git identity, stages three files, commits, and pushes — and then dispatches
builds. The commit-message claim is flatly **FALSE**.

The shipped text is narrower and does not repeat it:

```
$ sed -n '124,125p' .github/RELEASE.md
- `.github/workflows/base-image-update.yml` drives `internal/update-base-image.py`, which performs no git operations of
  any kind — it edits files and nothing else. That workflow has therefore never produced a tag.
```

Both literal statements are true. The script really is git-free:

```
$ grep -n "git\|subprocess\|os.system" internal/update-base-image.py
37:def fetch_github_file(repo: str, path: str) -> str:
39:    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
59:    content = fetch_github_file(source_repo, source_file)
$ git log --all -S 'git tag' --oneline -- .github/workflows/base-image-update.yml internal/update-base-image.py
(empty — neither file has ever contained `git tag`)
```

The defect is the **"therefore"**: it derives the workflow's tag-freeness from the *script's*
git-freeness, which is an invalid inference (the workflow does its own git work three lines apart from
where it would tag) and invites exactly the false generalisation the commit message then makes.

**Status: IMPRECISE in the shipped doc; FALSE in the commit message.** Suggested wording:

> `.github/workflows/base-image-update.yml` commits and pushes its bumps itself (`base-image-update.yml:94-96`,
> `:112`) but never tags: `internal/update-base-image.py` performs no git operations at all, and no
> revision of either file has ever contained `git tag`.

---

## Claim 4 — "auto-update.yml passes `--no-tag`" — VERIFIED, and it is the only invocation

```
$ sed -n '117,127p' .github/workflows/auto-update.yml
            # --no-tag: this call runs BEFORE the git commit further down the loop, so
            # HEAD here is still the pre-bump commit and tagging it names the wrong
            # commit. ...
            python3 internal/update-version.py "$addon_name" "$latest_version" --no-tag || {
              echo "ERROR: update-version.py failed for $addon_name"
              ERRORS=1
              continue
            }
$ grep -c 'update-version.py' .github/workflows/auto-update.yml
1
```

Exactly one invocation, at line 123, and it carries `--no-tag`. Both citations of `auto-update.yml:123`
(`RELEASE.md:127`, `:260`, `AUTO_UPDATE_GUIDE.md:74`, `:134`) are exact.

Every other line citation introduced by this commit also resolves against the current 171-line
`auto-update.yml`: `workflow_dispatch:` 6, cron 4-5, concurrency 32-34, `actions: write` 49, `BASE_SHA`
77, loop 83, keys 90-91, `gh release view` 94, `sed` strip 103, `.args.VERSION` 106, skip 108-111,
CHANGELOG block 135-150, commit 154, `find` 157, push 166, dispatch 167, `exit $ERRORS` 171. That
confirms SUMMARY deviation 2.

**Status: VERIFIED.**

---

## Claim 5 — the tag statistics — numerator VERIFIED, denominator and complement STALE

The doc (`RELEASE.md:138-139`) says: "Measured on 2026-09-09: **15 of the 40** `<addon>/v*` tags ... The
other **25** agree with their tree."

HANDOVER §4 audit command, run today:

```
$ git tag -l '*/v*' | wc -l
42
$ for t in $(git tag -l '*/v*'); do ... done   # HANDOVER §4 audit
authentik/v2026.8.1 tag=2026.8.1 tree=2026.8.0
meridian/v1.58.1 tag=1.58.1 tree=1.57.1
meridian/v1.58.2 tag=1.58.2 tree=1.58.1
meridian/v1.58.3 tag=1.58.3 tree=1.58.2
meridian/v1.59.0 tag=1.59.0 tree=1.58.3
meridian/v1.60.0 tag=1.60.0 tree=1.59.0
meridian/v1.61.0 tag=1.61.0 tree=1.60.0
meridian/v1.62.5 tag=1.62.5 tree=1.62.3
meridian/v1.64.0 tag=1.64.0 tree=1.62.7
meridian/v1.65.0 tag=1.65.0 tree=1.64.0
meridian/v1.65.2 tag=1.65.2 tree=1.65.0
meridian/v1.66.0 tag=1.66.0 tree=1.65.2
meridian/v1.67.0-0 tag=1.67.0-0 tree=1.66.0
meridian/v1.68.0-0 tag=1.68.0-0 tree=1.66.0
terraform-bridge/v0.2.0 tag=0.2.0 tree=0.1.0
```

**Live numbers: 42 total, 15 mismatched, 27 correct.** The mismatch count 15 is unchanged; the total is
now 42 and the complement 27, because of the two tags created manually during the session:

```
$ git for-each-ref --format='%(refname:short) %(creatordate:iso)' refs/tags/authentik/v2026.8.2-0 refs/tags/meridian/v1.69.0-0
authentik/v2026.8.2-0  2026-09-09 23:05:39 +0200
meridian/v1.69.0-0     2026-09-09 23:05:39 +0200
$ git log -1 --format='%ci' 833c176
2026-09-09 23:02:16 +0200
```

Both tags were created **after** the commit was authored (22:59) and committed (23:02), so `40`/`25` were
correct at `833c176` and are wrong at HEAD → **STALE**, not FALSE.

Mitigating, and worth recording as the reason this is a low-severity STALE: the sentence carries an
explicit measurement date and the shipped reproduce command still works. Also verified: every mismatch
really is an *older* version (per HANDOVER §3.2, the doc correctly says "an older version" and not "the
previous version" — `meridian/v1.64.0 → 1.62.7` and both `v1.67.0-0`/`v1.68.0-0 → 1.66.0` would have
falsified the stronger claim). Confirms SUMMARY deviation 1. The doc also does not generalise the defect
as "off by two".

All three worked examples are exact: `authentik/v2026.8.1 → 2026.8.0`, `meridian/v1.59.0 → 1.58.3`,
`terraform-bridge/v0.2.0 → 0.1.0`.

**Status: numerator + examples VERIFIED; total and complement STALE.**

---

## Claim 6 — the `terraform-bridge/v0.2.0` example proves the defect is in the manual procedure — VERIFIED

```
$ ls -la terraform-bridge/.upstream.yaml
ls: Zugriff auf 'terraform-bridge/.upstream.yaml' nicht möglich: Datei oder Verzeichnis nicht gefunden
$ find . -maxdepth 2 -name .upstream.yaml | sort
./authentik/.upstream.yaml
./gatus/.upstream.yaml
./meridian/.upstream.yaml
./phone-logger/.upstream.yaml
$ git show terraform-bridge/v0.2.0:terraform-bridge/build.yaml | head -6
build_from:
  amd64: "ghcr.io/home-assistant/amd64-base:3.24"

args:
  VERSION: "0.1.0"
  BRIDGE_VERSION: "0.1.0"
```

`terraform-bridge` has no `.upstream.yaml`, so the daily loop (which iterates exactly that `find` output)
cannot ever have touched it, and its tag's tree carries `0.1.0` against a tag naming `0.2.0`. The
inference in `RELEASE.md:145-146` is sound.

Same command also verifies "Today that is four add-ons: `authentik`, `gatus`, `meridian` and
`phone-logger`" (`RELEASE.md:241-242`, `AUTO_UPDATE_GUIDE.md:9`).

**Status: VERIFIED.**

---

## Claim 7 — "update-version.py tags HEAD and leaves the three edited files uncommitted" — VERIFIED

```
$ grep -n "no_tag\|create_and_push_tag\|Commit: git add" internal/update-version.py
199:def create_and_push_tag(version: str, addon_name: str, push: bool = True, dry_run: bool = False) -> bool:
302:    parser.add_argument('--no-tag', dest='no_tag', action='store_true',
411:        if not args.no_tag:
425:    if not args.no_tag:
443:    print(f"   • Commit: git add {args.addon_name} && git commit -m 'chore: update {args.addon_name} to v{args.new_version}'")
444:    if args.no_tag:
```

Line 425 is the live guard (411 is inside the `--dry-run` early-return branch) and it calls
`create_and_push_tag` at 428. Ordering claim:

```
$ sed -n '260,263p' internal/update-version.py
    create_result = subprocess.run(
        ["git", "tag", "-a", tag, "-m", message],
```

`git tag -a <tag>` with no commit-ish → tags `HEAD`. And the script never commits: there is no
`git add`/`git commit` subprocess anywhere in it — only the printed suggestion at 443. Both cited line
numbers (425, 443) are exact, confirming SUMMARY deviation 3.

**Status: VERIFIED.**

---

## Claim 8 — the shipped reproduce command actually reproduces — VERIFIED

Executed verbatim from `RELEASE.md:150-157`:

```
$ for tag in $(git tag -l '*/v*'); do
      addon=${tag%%/*}; want=${tag#*/v}
      have=$(git show "$tag:$addon/build.yaml" | sed -n 's/^ *VERSION: *"\?\([^"]*\)"\?$/\1/p')
      case "$want" in "$have" | "$have"-*) ;; *) echo "MISMATCH $tag tree=$have" ;; esac
  done
MISMATCH authentik/v2026.8.1 tree=2026.8.0
... (15 lines total, identical set to the HANDOVER §4 audit above) ...
MISMATCH terraform-bridge/v0.2.0 tree=0.1.0
=== MISMATCH count: 15 ===
```

Exactly 15 lines, no stderr noise, and the set matches the independent HANDOVER §4 audit line for line.
The prose number `15` it supports is correct; only the surrounding `40`/`25` have drifted (Claim 5).

**Status: VERIFIED.**

---

## Claim 9 — the tag-trigger count (six of nine) — VERIFIED

```
$ ls .github/workflows/build-*.yml | wc -l
9
$ grep -l '^    tags:' .github/workflows/build-*.yml
.github/workflows/build-iac-runner.yml
.github/workflows/build-network-tools.yml
.github/workflows/build-terraform-bridge.yml
$ grep -c 'tag-trigger temporarily disabled' .github/workflows/build-*.yml | grep -v ':0'
build-authentik.yml:1  build-coding-assistants.yml:1  build-gatus.yml:1
build-markdown-renderer.yml:1  build-meridian.yml:1  build-phone-logger.yml:1
```

Six disabled, three active. Matches HANDOVER §2.1 and every count the commit corrected:

- `RELEASE.md:33-34` "commented out for all add-ons except network-tools, terraform-bridge and iac-runner" ✓
- `RELEASE.md:54-57` "In the six callers whose tag trigger is disabled ... The three add-ons with an
  active `tags:` block carry no such comment" ✓ (verified by reading all nine `on:` blocks — the three
  active blocks are bare, no comment)
- `RELEASE.md:116` "The six callers carry the comment" ✓ (was "seven")
- `RELEASE.md:63` "disabled the tag trigger in all seven" ✓ — correctly left as a *historical* statement
  about commit `287c79f`, not converted to six
- `RELEASE.md:32` "Every per-addon build workflow ... triggers on a `push` to `main` with changes under
  `<addon>/**`" ✓ all nine
- `AUTO_UPDATE_GUIDE.md:119-120` same claim ✓

The `Supervisor image source` column is also exact:

```
$ for d in */; do d=${d%/}; [ -f "$d/config.yaml" ] && { grep -qE '^image:' "$d/config.yaml" && echo "$d ghcr pull" || echo "$d local build"; }; done
authentik local build      coding-assistants ghcr pull   gatus ghcr pull
iac-runner local build     markdown-renderer ghcr pull   meridian ghcr pull
network-tools ghcr pull    phone-logger ghcr pull        terraform-bridge ghcr pull
```

Seven `ghcr pull`, two `local build` — matching the table (36-46) and the two bullets at 90-98.

**Status: VERIFIED.**

---

## Claim 10 — statements about `verify-image-availability.yml` — vacuously satisfied, nothing softened

```
$ grep -n "verify-image\|grace\|403\|401\|fetch-depth\|four times daily\|credential" .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md
NO MATCHES
```

Neither file mentions the guard, its schedule, its credentials or its grace window, so none of the
load-bearing properties from HANDOVER §3.3/§3.4/§3.5 can have been softened. This matches the SUMMARY's
recorded decision ("Decision Held: rlk's Image-Availability Guard Not Documented") and I agree with it:
the guard's own file states both properties itself (`verify-image-availability.yml:51-58` "MANDATORY, not
an optimisation"; `:25-30` "no registry scope ... a correctness property, not a least-privilege nicety",
`permissions: contents: read`), and the docs neither repeat nor weaken them.

**Status: VERIFIED (no claim to falsify).**

---

## Claim 11 — the `actions: write` exclusivity claim — FALSE, and never true

`docs/AUTO_UPDATE_GUIDE.md:129-130` (introduced by this commit — `git blame` attributes both lines to
`833c176e`):

> Creating a dispatch requires the `actions: write` permission, which the job requests explicitly
> (`auto-update.yml:49`). **No other workflow in this repository asks for that scope.**

```
$ grep -rn "actions: *write" .github/workflows/
.github/workflows/base-image-update.yml:29:      # actions: write is required ...
.github/workflows/base-image-update.yml:33:      actions: write
.github/workflows/auto-update.yml:45:      # actions: write is required ...
.github/workflows/auto-update.yml:49:      actions: write
```

`base-image-update.yml:33` asks for the same scope. And it did so **before** this commit:

```
$ git log -1 --format='%h %ad %s' --date=iso 6fbe7a4
6fbe7a4 2026-09-09 22:11:49 +0200 fix(260909-rlj): dispatch builds after automated version bumps + BUILD_DATE fallback
$ git merge-base --is-ancestor 6fbe7a4 833c176 && echo "IS ancestor"
IS ancestor
```

So the sentence was false 48 minutes before it was written. It is a verbatim copy of the (equally false)
in-file comment at `auto-update.yml:47-48` / `base-image-update.yml:31-32` — i.e. precisely the
"repeat a workflow comment's assertion as fact" pattern this item existed to remove.

**Severity: FALSE.** Suggested wording:

> Creating a dispatch requires the `actions: write` permission, which the job requests explicitly
> (`auto-update.yml:49`). `base-image-update.yml:33` requests it for the same reason; no other workflow
> in this repository does.

(The two in-file comments should be corrected in the same pass — they are the source of the error.)

---

## Claim 12 — the prettier/lint purpose clause — FALSE, and known-false at write time

`docs/AUTO_UPDATE_GUIDE.md:76-77` (introduced by this commit — blame `833c176e`):

> prepends the upstream release body to `{addon}/CHANGELOG.md`, but only when that body is non-empty, and
> formats the result with prettier **so the lint workflow does not reject the commit**
> (`auto-update.yml:135-150`);

The mechanism half is true (`auto-update.yml:148` runs `npx --yes prettier@3.9.6 --write`). The purpose
clause is measurably false — prettier does not fix bare URLs, and `markdownlint` MD034 is what rejects
them:

```
$ git log --oneline --all --grep="bare URL" --format='%h %ad %s' --date=short
3cc13c2 2026-09-09 fix(authentik): wrap the bare URL auto-update prepended to CHANGELOG.md
8c31d33 2026-09-02 fix(authentik): wrap bare URL in angle brackets to satisfy MD034
6dc977a 2026-08-23 fix(changelog): wrap bare URLs in <...> for markdownlint MD034
b4fb815 2026-07-27 docs(authentik): wrap bare URLs in CHANGELOG to fix MD034
```

Four hand-fixes on record, the most recent (`3cc13c2`) **on the same day, after this commit**. The defect
is already recorded as measured and open in the ledger:

```
$ grep -n -A6 '"id": *10' .planning/WINDOWS.md
145: "... runs 'npx prettier --write' on it with the stated intent 'so lint.yml does not reject the
      commit' - but prettier does not fix bare URLs and markdownlint (MD034/no-bare-urls) is what
      rejects them. Measured: the 2026-09-09 authentik 2026.8.2 bump produced
      authentik/CHANGELOG.md:1 with a bare URL and 'make lint' exit 1. ..."
146: "status": "open",
```

Again a workflow comment's stated *intent* (`auto-update.yml:147`) reproduced in docs as an *outcome* —
the same failure shape as Claim 11, and this one has a live operational cost.

**Severity: FALSE.** Suggested wording:

> prepends the upstream release body to `{addon}/CHANGELOG.md`, but only when that body is non-empty, and
> runs prettier over the result (`auto-update.yml:135-150`). Prettier does not wrap bare URLs, so a
> release body containing one still fails `markdownlint` MD034 and needs a hand-fix — see ledger item 10.

---

## Claim 13 — the pre-push hook description — STALE (three sites), caused by `260909-wgm`

`internal/check-version-tags.sh` was reworked today by `2ba51a2` / `c43375f`. At HEAD it is advisory:

```
$ sed -n '1,4p;192,198p' internal/check-version-tags.sh
#!/usr/bin/env bash
# Pre-push advisory: reports every add-on whose bumped config.yaml/build.yaml
# version is about to reach main without a matching `<addon>/v<version>` tag.
# It reports only — it never fails the push.
...
if [[ "$missing_tags" -ne 0 ]]; then
    echo ""
    echo "ℹ️  $missing_tags add-on(s) above have no release tag. This is advisory"
    echo "   only — the push continues."
fi

exit 0
```

At `833c176` it blocked:

```
$ git show 833c176:internal/check-version-tags.sh | sed -n '177,181p'
if [[ "$errored" -ne 0 ]]; then
    echo "🚫 Pre-push check failed — see errors above"
    echo "   To bypass this check (not recommended): git push --no-verify"
    exit 1
fi
```

Three sites in `RELEASE.md` therefore describe a gate that no longer exists. All three are **pre-existing**
(blame: `b21683fa`, `616e4548`, `2670a9a2`) — this commit did not touch them — but they are false at HEAD
and they are in one of the two files this item owns:

| Line | Text at HEAD | Reality at HEAD |
| --- | --- | --- |
| `RELEASE.md:189-190` | "the pre-push hook **verifies** the `<addon>/v<version>` tag already exists locally or on origin **before letting the branch push through**" | The hook reports and exits 0 unconditionally; it never gates the push |
| `RELEASE.md:233` | "The pre-push hook **will refuse a branch push** until a tag named `<addon>/v<version>` exists for every modified `config.yaml`" | It refuses nothing |
| `RELEASE.md:216-217` | "still **satisfies** the pre-push hook ... **as long as** the subpatch in `config.yaml` matches the tag suffix" | The conditional implies a gate; at HEAD nothing can fail it |

Distinguishing this from a never-true claim, per the mandate: these were **TRUE when `833c176` landed**
and became false ~5 hours later. **STALE, not FALSE.**

Also checked, and clean: the deleted ghcr-404 tag rationale is **not** repeated anywhere. The only two
`404` mentions explicitly deny the tag→404 link:

```
$ grep -n "404" .github/RELEASE.md docs/AUTO_UPDATE_GUIDE.md
.github/RELEASE.md:92:  produces exactly the ghcr.io 404 ... even when the tag exists on origin — the
.github/RELEASE.md:96:  `Dockerfile` and a missing ghcr tag cannot produce a pull 404 for them at all.
```

The `LOCAL_BUILD_ADDONS` statements at `:190-193` and `:234-236` remain correct
(`check-version-tags.sh:89-91` holds exactly `iac-runner`).

**Status: STALE ×3.**

Suggested wording for `:189-190`:

> The `internal/check-version-tags.sh` pre-push hook reports every add-on whose bumped `config.yaml`
> version is about to reach `main` with no matching `<addon>/v<version>` tag. Since `2ba51a2` it is
> **advisory only — it never fails the push**: the tag does not cause the build (that is
> `internal/dispatch-builds.sh` via `workflow_dispatch`), and a release marker must not block a push.

---

## Additional findings outside the enumerated list

### A. `RELEASE.md:178-179` — FALSE (pre-existing, survived the truth pass)

> The Makefile then runs `make validate-versions` so a broken 3-file set fails the release **before the
> tag reaches `origin`**.

```
$ grep -n -A16 "^update-version:" Makefile | sed -n '14,16p'
201-	./internal/update-version.py $(ADDON) $(VERSION) $$ARGS
202-	@echo "🔍 Running validation..."
203-	@make validate-versions
```

`make release` → `make update-version` → `update-version.py` (which creates **and pushes** the tag,
`internal/update-version.py:271-274`) → *then* `make validate-versions`. Validation runs strictly
**after** the tag is on origin, so it cannot fail the release before that. Blame: `2670a9a2`,
pre-existing.

This is the most consequential surviving falsehood because it sits 40 lines below the new
`### What a tag guarantees` section, whose entire argument is that step 1's ordering is the defect — and
it tells the operator the ordering is safety-gated. Suggested wording:

> The Makefile then runs `make validate-versions`. Note the ordering: `update-version.py` has already
> pushed the tag by then, so this validation reports a broken 3-file set — it cannot prevent the tag from
> reaching `origin`.

(Adjacent, out of scope for these two files but the same class: `Makefile:234` still prints "The build
workflow for $(ADDON) will pick it up on the tag push", which is false for six of the nine add-ons.)

### B. `AUTO_UPDATE_GUIDE.md:88-89` and `:226` — IMPRECISE

> One add-on's failure therefore does not stop the others. **The loop always runs to completion**

True for the two failures the sentence names (`gh release view` at 94-98, `update-version.py` at 123-127
— both guarded with `|| { ...; continue; }`). The step runs under `set -eo pipefail`
(`auto-update.yml:70`), so an **unguarded** failure aborts the loop mid-way: `yq eval` at 90-91,
`npx --yes prettier@3.9.6` at 148, `git add`/`git commit` at 153-154. "always" overstates. Suggested:
"An unreachable release or a failing `update-version.py` is caught per add-on and the loop continues; any
other command failing aborts the step under `set -e`."

### C. `RELEASE.md:101-102` — IMPRECISE

> both read `build.yaml:args.VERSION` out of whatever ref they check out

Correct as far as it goes (`_build-template.yml:69` bare `actions/checkout@v7`, `:76` reads
`.args.VERSION`), and the conclusion is sound. But the *published OCI image tag* comes from
`config.yaml:version` (`CONFIG_VERSION`, `_build-template.yml:80`, "drives the OCI image tag"), not from
`args.VERSION`. Naming both would make the paragraph's point stronger, not weaker.

### D. `RELEASE.md:90-94` — IMPRECISE (pre-existing)

> For these, skipping step 2 produces exactly the ghcr.io 404 ... the manifest advertises a version whose
> image tag was never published

If step 2 is skipped, `config.yaml` never reaches `main`, so the store keeps advertising the *old*
version and no user-visible 404 occurs until the bump commit lands later without a build. The 404 is
caused by a commit landing un-built, not by the commit being withheld. Blame `80eb6b67`, pre-existing;
low priority.

---

## Findings table

| # | Severity | Location | Claim | Reality | Suggested wording |
| --- | --- | --- | --- | --- | --- |
| 1 | **FALSE** | `docs/AUTO_UPDATE_GUIDE.md:130` (new in `833c176`) | "No other workflow in this repository asks for that scope" | `base-image-update.yml:33` requests `actions: write`, added by `6fbe7a4` which is an ancestor of `833c176` — false when written | "`base-image-update.yml:33` requests it for the same reason; no other workflow in this repository does." Fix the source comments at `auto-update.yml:47-48` and `base-image-update.yml:31-32` too |
| 2 | **FALSE** | `docs/AUTO_UPDATE_GUIDE.md:76-77` (new in `833c176`) | prettier runs "so the lint workflow does not reject the commit" | Prettier does not wrap bare URLs; MD034 rejects them. Four hand-fixes (`b4fb815`, `6dc977a`, `8c31d33`, `3cc13c2`); ledger item 10 open | "runs prettier over the result … Prettier does not wrap bare URLs, so a release body containing one still fails `markdownlint` MD034 and needs a hand-fix — see ledger item 10." |
| 3 | **FALSE** | `.github/RELEASE.md:178-179` (pre-existing `2670a9a2`) | `make validate-versions` "fails the release before the tag reaches `origin`" | `Makefile:201-203` — the tag is pushed by `update-version.py` before validation runs | "Note the ordering: `update-version.py` has already pushed the tag, so this validation reports a broken 3-file set — it cannot prevent the tag reaching `origin`." |
| 4 | **STALE** | `.github/RELEASE.md:138-139` (new in `833c176`) | "15 of the **40** … other **25** agree" | 42 tags / 15 mismatched / 27 agree; the two new tags were created 3 min after the commit. Numerator, examples and reproduce command all still exact | "Measured 2026-09-10: 15 of the 42 … The other 27 agree" — or drop the total and keep only "15 tags … , reproduce below" |
| 5 | **STALE** | `.github/RELEASE.md:189-190` (pre-existing) | hook "verifies … before letting the branch push through" | `check-version-tags.sh:198` — `exit 0` unconditionally since `2ba51a2` | "…reports every add-on missing its tag. Advisory only since `2ba51a2` — it never fails the push." |
| 6 | **STALE** | `.github/RELEASE.md:233` (pre-existing) | "will refuse a branch push until a tag … exists" | Refuses nothing | "will report, but not block, a branch push whose `config.yaml` has no matching tag" |
| 7 | **STALE** | `.github/RELEASE.md:216-217` (pre-existing) | "still satisfies the pre-push hook … as long as the subpatch matches" | Nothing can fail the hook; the conditional implies a gate | "The hook reports a match when the subpatch in `config.yaml` matches the tag suffix, and does not block either way." |
| 8 | **IMPRECISE** (doc) / **FALSE** (commit message) | `.github/RELEASE.md:124-125`; `833c176` message | "base-image-update.yml has no git operations at all" (message); "…drives `update-base-image.py`, which performs no git operations of any kind … **therefore** never produced a tag" (doc) | The script is git-free ✓, and neither file ever held `git tag` ✓ — but the workflow itself commits and pushes at `:94-96`, `:112`. The "therefore" is a non-sequitur | "commits and pushes its bumps itself (`:94-96`, `:112`) but never tags: `update-base-image.py` performs no git operations, and no revision of either file has ever contained `git tag`." |
| 9 | **IMPRECISE** | `docs/AUTO_UPDATE_GUIDE.md:88-89`, `:226` | "The loop always runs to completion" | Only the two guarded failures continue; `yq` (90-91), `npx prettier` (148) or `git commit` (154) abort the step under `set -eo pipefail` | "…is caught per add-on and the loop continues; any other command failing aborts the step under `set -e`." |
| 10 | **IMPRECISE** | `.github/RELEASE.md:101-102` | "both read `build.yaml:args.VERSION` out of whatever ref they check out" | True, but the published image tag comes from `config.yaml:version` (`CONFIG_VERSION`, `_build-template.yml:80`) | "…both read `build.yaml:args.VERSION` **and `config.yaml:version`** out of whatever ref they check out — and the latter is the published image tag." |
| 11 | **IMPRECISE** | `.github/RELEASE.md:90-94` (pre-existing) | "skipping step 2 produces exactly the ghcr.io 404" | Skipping step 2 keeps the old version in the store; the 404 comes from a bump commit landing un-built | "…is what makes the later bump commit land with no image behind it, producing exactly the ghcr.io 404 …" |

## What held (no finding)

- `GITHUB_TOKEN` no-trigger mechanism, all three sites, correctly scoped to workflow-token events
- `paths:`-filter claim scoped to a human push; cross-reference target exists and delivers
- `--no-tag` at `auto-update.yml:123`, the only `update-version.py` invocation in the workflow
- All 18 `auto-update.yml` line citations, both `update-version.py` citations (425, 443), `update-base-image.py:56`
- `update-version.py` tags `HEAD` (`git tag -a` with no commit-ish) and never commits the edited files
- 15 mismatched tags; all three worked examples; the shipped reproduce command (executed: exactly 15 lines)
- "an older version" rather than "the previous version"; no "off by two" generalisation
- `terraform-bridge` has no `.upstream.yaml`; its tag's tree carries `0.1.0`
- Six-of-nine tag triggers disabled; three active carry no comment; historical "all seven" correctly preserved
- Seven `image:` keys / two local-build add-ons; the `Supervisor image source` column is exact
- Four `.upstream.yaml` add-ons; only two keys read; both `version_pattern` keys inert; `update-base-image.py:56` the sole reader; all three `version_strip` shapes correct
- Concurrency group shared with `base-image-update.yml`; bare inputless `workflow_dispatch:`; workflow name `Auto Update`; cron `0 6 * * *`
- `dispatch-builds.sh` semantics: `gh workflow run build-<addon>.yml --ref <ref>`, `SKIPPED_NO_WORKFLOW` warns and exits 0, a failed dispatch exits 1 → `ERRORS=1` → non-zero job
- `auto-update.yml` sends no webhook; `_build-template.yml` calls `notify-ha.sh` with no exclusivity claim (correct — `verify-image-availability.yml:103` is a second caller); notify legs are gated on `inputs.notify-ha`, not on event type, so dispatch-triggered builds do reach it
- No claim about the image-availability guard, so none of its load-bearing properties softened
- The deleted ghcr-404 tag rationale is not repeated anywhere
- All four SUMMARY "Deviations from Plan" self-corrections are sound
- Both target files are byte-identical to `833c176` at HEAD

---

_Verified 2026-09-10 against HEAD `c43375f`. No files were edited; nothing committed._
