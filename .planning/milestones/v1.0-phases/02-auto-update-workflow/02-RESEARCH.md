# Phase 2: Auto-Update Workflow - Research

**Researched:** 2026-04-04 **Domain:** GitHub Actions — scheduled version-check workflow, gh CLI, yq, direct-to-main
commits **Confidence:** HIGH

## Summary

Phase 2 produces a single GitHub Actions workflow file (`.github/workflows/auto-update.yml`) that runs daily and on
`workflow_dispatch`. For each add-on directory containing `.upstream.yaml`, it reads the upstream repository from that
file, checks the latest GitHub Release tag via `gh release view --repo`, strips the version prefix using the
`version_strip` regex, compares against the current version in `build.yaml`, and calls `scripts/update-version.py` when
a new version is found. Commits go directly to `main` using `github-actions[bot]` identity.

The workflow toolchain is simple and well-supported. Both `gh` (v2.88.1) and `yq` (v4.52.4) are pre-installed on
`ubuntu-latest` runners — no setup steps required. The primary design constraint is that `update-version.py` returns
exit code 0 for both "files updated" and "nothing to do", so the workflow must detect whether files actually changed via
`git diff --quiet` rather than relying on the script's exit code.

A critical finding that contradicts CONTEXT.md decision D-07: pushes made with `GITHUB_TOKEN` do **not** trigger other
workflows (including `lint.yml`). This is a documented GitHub Actions limitation. The auto-update commits will not be
validated by lint automatically unless a PAT, GitHub App token, or `workflow_run` trigger is used.

**Primary recommendation:** Implement the workflow as a pure bash script inside the workflow YAML (no separate script
file). Use `gh release view --repo <upstream> --json tagName --jq .tagName` for version detection. Parse
`.upstream.yaml` with `yq`. Detect actual file changes with `git diff --quiet` before committing. Use a
`continue-on-error`-style per-addon error isolation pattern. Flag the D-07 conflict to the user before planning commits
this workflow.

---

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Dynamic discovery via `find . -maxdepth 2 -name .upstream.yaml` — no hardcoded add-on list.
- **D-02:** One commit per add-on update — not a batch commit.
- **D-03:** Commit message format: `chore({addon}): update to {version}`.
- **D-04:** Fail-safe mode — errors per add-on are logged; workflow continues; job exits non-zero if any error occurred.
- **D-05:** Commit author: `github-actions[bot]` with email `github-actions[bot]@users.noreply.github.com`.
- **D-06:** Workflow requires `permissions: contents: write` for `GITHUB_TOKEN` to push commits to `main`.
- **D-07:** Auto-update commits to `main` are intended to be picked up by the existing `lint.yml` push trigger.

### Claude's Discretion

- Shell scripting style (bash inline vs. composite action vs. separate script file) — choose based on local testability.
- Whether to use `gh release view` or GitHub REST API for version checking.
- How to parse the current version from `.upstream.yaml` for comparison (yq, grep, python).

### Deferred Ideas (OUT OF SCOPE)

- PR-based update flow (manual review step)
- Semantic version downgrade protection in the workflow
- Slack/notification on update

</user_constraints>

---

<phase_requirements>

## Phase Requirements

| ID      | Description                                                                                                | Research Support                                                                                                      |
| ------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| AUTO-01 | Workflow runs daily (cron) and checks each add-on's upstream for new releases via `gh release view --repo` | `gh release view --repo <owner/repo> --json tagName --jq .tagName` confirmed working; pre-installed on ubuntu-latest  |
| AUTO-02 | When new version detected, `scripts/update-version.py` is called to sync the 3-file version set            | Script CLI is `./scripts/update-version.py {addon} {version}`; exit 0 on success AND no-op; exit 1 on partial failure |
| AUTO-03 | Updated files committed directly to `main` (no PR, fully automatic)                                        | Requires `permissions: contents: write`; git config + git push with GITHUB_TOKEN confirmed viable                     |
| AUTO-04 | Workflow skips commit when no version change detected (prevents empty commits)                             | Must use `git diff --quiet` after running script; cannot rely on script exit code alone                               |
| AUTO-05 | Workflow authenticates via `GITHUB_TOKEN` — no additional secrets required                                 | GITHUB_TOKEN sufficient for `gh release view` (read) and `git push` (write with `contents: write`)                    |

</phase_requirements>

---

## Standard Stack

### Core

| Tool    | Version (ubuntu-latest) | Purpose                           | Why Standard                                       |
| ------- | ----------------------- | --------------------------------- | -------------------------------------------------- |
| `gh`    | 2.88.1                  | Query upstream GitHub releases    | Pre-installed; native GitHub API; GITHUB_TOKEN     |
| `yq`    | 4.52.4                  | Parse `.upstream.yaml` fields     | Pre-installed; used already in `lint.yml` line 112 |
| `bash`  | system                  | Workflow inline script            | Required for `set -e`, loops, string ops           |
| `git`   | 2.53.0                  | Stage, commit, push version files | Pre-installed                                      |
| `jq`    | 1.7                     | Optional JSON parsing             | Pre-installed; fallback if yq unavailable          |
| Python3 | 3.x (system)            | Run `scripts/update-version.py`   | Already in repo; no install needed in workflow     |

### Alternatives Considered

| Instead of          | Could Use                              | Tradeoff                                                                     |
| ------------------- | -------------------------------------- | ---------------------------------------------------------------------------- |
| `gh release view`   | GitHub REST API via `curl`             | REST API requires manual auth header construction; `gh` is simpler           |
| `yq`                | Python `yaml` to parse upstream.yaml   | Python more portable locally; yq is more concise in bash context             |
| inline bash         | Separate `scripts/auto-update.sh`      | Separate script allows local testing; inline is simpler for single workflow  |
| `git push` (direct) | `stefanzweifel/git-auto-commit-action` | Action abstracts git details but adds external dependency; direct is simpler |

**Version verification (ubuntu-latest, as of 2026-04-04):**

```
yq:   4.52.4   (confirmed via actions/runner-images Ubuntu2404-Readme.md)
gh:   2.88.1   (confirmed via actions/runner-images Ubuntu2404-Readme.md)
git:  2.53.0   (confirmed via actions/runner-images Ubuntu2404-Readme.md)
jq:   1.7      (confirmed via actions/runner-images Ubuntu2404-Readme.md)
```

---

## Architecture Patterns

### Recommended Workflow Structure

```
.github/workflows/
└── auto-update.yml      # New workflow for this phase
.github/workflows/
└── lint.yml             # Existing; NOT triggered by auto-update commits (see Pitfall 1)
```

### Pattern 1: Per-Addon Loop with Fail-Safe

The workflow iterates over discovered `.upstream.yaml` files. Each iteration runs in a subshell or uses explicit error
trapping so one failure does not abort the loop. A flag variable tracks whether any error occurred; the job exits
non-zero at the end if the flag is set.

```yaml
# Inline bash — pseudo-code structure
- name: Check and update add-ons
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    set -e
    ERRORS=0
    while IFS= read -r upstream_file; do
      addon_dir=$(dirname "$upstream_file")
      addon_name=$(basename "$addon_dir")

      # Parse .upstream.yaml
      upstream_repo=$(yq eval '.upstream.repository' "$upstream_file")
      version_strip=$(yq eval '.upstream.version_strip' "$upstream_file")

      # Get latest upstream release tag
      latest_tag=$(gh release view --repo "$upstream_repo" --json tagName --jq .tagName 2>/dev/null) || {
        echo "ERROR: could not fetch release for $upstream_repo"
        ERRORS=1
        continue
      }

      # Strip version prefix (e.g. "^v" -> sed 's/^v//')
      # version_strip field contains a regex like "^v"; convert to sed expression
      latest_version=$(echo "$latest_tag" | sed "s/${version_strip}//")

      # Get current version from build.yaml (no subpatch, plain X.Y.Z)
      current_version=$(yq eval '.args.VERSION' "$addon_dir/build.yaml")

      if [ "$latest_version" = "$current_version" ]; then
        echo "INFO: $addon_name already at $current_version, skipping"
        continue
      fi

      echo "INFO: $addon_name needs update $current_version -> $latest_version"

      # Update the 3-file version set
      python3 scripts/update-version.py "$addon_name" "$latest_version" || {
        echo "ERROR: update-version.py failed for $addon_name"
        ERRORS=1
        continue
      }

      # Commit only if files actually changed
      if git diff --quiet; then
        echo "INFO: no file changes after update-version.py for $addon_name (already at $latest_version?)"
        continue
      fi

      git add "$addon_dir/config.yaml" "$addon_dir/build.yaml" "$addon_dir/README.md"
      git commit -m "chore($addon_name): update to $latest_version"
    done < <(find . -maxdepth 2 -name .upstream.yaml)

    git push
    exit $ERRORS
```

### Pattern 2: Git Identity Setup

Must precede any `git commit` call:

```yaml
- name: Configure git
  run: |
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
```

### Pattern 3: `gh release view` for Upstream Release Detection

The REQUIREMENTS.md (AUTO-01) explicitly specifies `gh release view --repo <upstream>`:

```bash
# Get the latest release tag name from an upstream repo
latest_tag=$(gh release view --repo "akentner/fritz-callmonitor2mqtt" \
  --json tagName --jq .tagName)
# Result: "v1.7.4"
```

`gh` authenticates via the `GH_TOKEN` environment variable, set to `${{ secrets.GITHUB_TOKEN }}`.

### Pattern 4: Version Prefix Stripping

The `.upstream.yaml` field `version_strip` contains a regex like `^v`. Apply it via `sed`:

```bash
version_strip=$(yq eval '.upstream.version_strip' "$upstream_file")
# version_strip = "^v"
latest_version=$(echo "$latest_tag" | sed "s/${version_strip}//")
# "v1.7.4" -> "1.7.4"
```

Note: bash parameter expansion (`${tag#v}`) handles the `^v` case with less flexibility. `sed` handles any regex pattern
that may appear in future `.upstream.yaml` files.

### Pattern 5: Detecting Actual File Changes (AUTO-04)

`update-version.py` returns exit 0 for both "updated all 3 files" and "nothing to do (already at target)". The workflow
must check git state:

```bash
# After running update-version.py:
if git diff --quiet; then
  echo "no changes — skipping commit"
  continue
fi
# Only reach here if files were actually modified
git add ...
git commit ...
```

### Anti-Patterns to Avoid

- **Using `set -e` globally without `|| true` guards on expected-failure commands:** `gh release view` returns non-zero
  if a repo has no releases. Wrap with `|| { ...; continue; }` pattern.
- **Relying on `update-version.py` exit code to gate commits:** The script returns 0 for no-op. Always check `git diff`.
- **Pushing inside the per-addon loop:** Accumulate commits and push once at the end to reduce API calls and avoid push
  failures on intermediate commits.
- **Using `git add -A`:** Stage only the three known version files per add-on to avoid accidentally staging unrelated
  changes.

---

## Don't Hand-Roll

| Problem                     | Don't Build                           | Use Instead                               | Why                                          |
| --------------------------- | ------------------------------------- | ----------------------------------------- | -------------------------------------------- |
| Fetch latest GitHub release | curl + GitHub REST API + JSON parsing | `gh release view --repo X --json tagName` | Pre-installed, handles auth, cleaner syntax  |
| Parse YAML in bash          | grep/awk hacks on .upstream.yaml      | `yq eval '.field' file.yaml`              | Pre-installed; handles YAML edge cases       |
| Update 3-file version set   | sed in-place on 3 files manually      | `scripts/update-version.py`               | Already exists; tested; handles all patterns |
| Commit changed files        | Custom git wrapper                    | Plain `git add / git commit / git push`   | Nothing complex needed                       |

**Key insight:** All the hard problems (YAML parsing, version file updating, GitHub API auth) are already solved by
pre-installed tools or the existing `update-version.py` script. The workflow is pure orchestration glue.

---

## Runtime State Inventory

Step 2.5 SKIPPED — this is a greenfield workflow creation phase, not a rename/refactor/migration.

---

## Environment Availability

| Dependency         | Required By                         | Available | Version | Fallback         |
| ------------------ | ----------------------------------- | --------- | ------- | ---------------- |
| `gh` (GitHub CLI)  | AUTO-01: upstream release detection | ✓ (CI)    | 2.88.1  | curl + REST API  |
| `yq`               | Parse `.upstream.yaml` fields       | ✓ (CI)    | 4.52.4  | python3 yaml     |
| `python3`          | Run `scripts/update-version.py`     | ✓ (CI)    | 3.x     | —                |
| `git`              | Commit and push version changes     | ✓ (CI)    | 2.53.0  | —                |
| `GITHUB_TOKEN`     | AUTO-05: all auth (read + write)    | ✓ (CI)    | auto    | PAT (not needed) |
| `yq` (dev machine) | Local workflow testing              | ✗ (local) | —       | python3 yaml     |

**Missing dependencies with no fallback:** None — all required tools are available in the CI environment.

**Missing dependencies with fallback (local only):** `yq` is not installed on the developer machine. Local testing of
the workflow script requires either installing `yq` via `snap install yq` or substituting `python3 -c "import yaml..."`.
This does not block CI execution.

---

## Common Pitfalls

### Pitfall 1: GITHUB_TOKEN Push Does Not Trigger lint.yml (Contradicts D-07)

**What goes wrong:** CONTEXT.md decision D-07 states that auto-update commits will be "picked up by the existing
`lint.yml` push trigger." This is incorrect. GitHub's documented behavior is: "events triggered by the GITHUB_TOKEN,
with the exception of workflow_dispatch and repository_dispatch, will not create a new workflow run." Pushes by
GITHUB_TOKEN to `main` will NOT trigger `lint.yml`.

**Source:** Official GitHub Docs — Triggering a workflow
(https://docs.github.com/actions/using-workflows/triggering-a-workflow)

**Why it happens:** GitHub prevents recursive workflow loops; GITHUB_TOKEN pushes are treated as bot activity and
excluded from triggering event-based workflows.

**Impact:** Low for this project. The push from `lint.yml` when developers push manually still runs. Auto-update commits
are not linted automatically.

**Options to resolve (if desired, not in scope for this phase):**

1. Use a PAT stored as a repository secret instead of GITHUB_TOKEN for the push step.
2. Add a `workflow_run` trigger to `lint.yml` that fires after `auto-update.yml` completes.
3. Accept the current behavior — auto-update commits are not linted automatically (simplest, low risk for mechanical
   version bumps).

**Recommendation for planner:** Document this discrepancy in the plan. Do not try to implement PAT or workflow_run in
this phase unless the user explicitly re-decides. The phase deliverable is correct regardless of whether D-07 holds.

### Pitfall 2: update-version.py Exit Code Does Not Signal "No-Op"

**What goes wrong:** Workflow assumes `exit 0` from `update-version.py` means files were changed, and proceeds to
`git commit`, creating an empty commit.

**Why it happens:** The script returns `exit 0` for both "all 3 files updated" and "no files needed updating (already at
target version)". The return code is not a signal of file modification.

**How to avoid:** Always follow `update-version.py` with `git diff --quiet` check. Only proceed to `git add/commit` if
`git diff` reports changes.

**Warning signs:** Empty commits like `chore(fritz-callmonitor2mqtt): update to 1.7.3` when version was already 1.7.3.

### Pitfall 3: version_strip Regex Applied Incorrectly

**What goes wrong:** The `version_strip` field in `.upstream.yaml` contains a regex like `^v`. If applied naively with
`${tag#v}` (bash glob), it works for `^v` but would silently fail for any other pattern. If applied as a literal string
with sed `s/^v//`, it strips the `^` character.

**How to avoid:** Treat the `version_strip` value as a sed-compatible regex: `sed "s/${version_strip}//"`. This handles
`^v` correctly (`sed 's/^v//'`) and any future pattern.

**Verification:** `echo "v1.7.4" | sed "s/^v//"` produces `1.7.4`. Correct.

### Pitfall 4: gh release view Fails for Repos With No Releases

**What goes wrong:** `gh release view --repo owner/repo` exits non-zero if the repo has no GitHub Releases (only tags,
or no releases at all). With `set -e` in the script, this aborts the entire workflow.

**How to avoid:** Wrap the `gh release view` call with `|| { echo "ERROR: ..."; ERRORS=1; continue; }`. The `continue`
skips to the next add-on; `ERRORS=1` ensures the job reports failure without halting processing of remaining add-ons.

### Pitfall 5: Pushing Fails When No Commits Were Made

**What goes wrong:** If all add-ons are already up to date, the `git push` at the end of the loop has nothing to push
and may still succeed (no-op push), or the workflow may error if the remote and local are identical.

**How to avoid:** Gate the final `git push` on whether any commits were actually made. Track a `UPDATES_MADE` flag
alongside `ERRORS`.

### Pitfall 6: actionlint Will Lint the New Workflow

**What goes wrong:** The new `auto-update.yml` is linted by `actionlint` in `lint.yml`. Shellcheck rules `SC2086`,
`SC2129`, `SC2001` are already relaxed for GitHub Actions workflows via `.actionlint.yml`. However, other shellcheck
warnings may cause CI failures.

**How to avoid:** Confirm `.actionlint.yml` relaxed rules apply to all workflows. Quote all variable expansions
properly. Use `shellcheck disable` comments only as last resort.

---

## Code Examples

### Full Version Detection Pattern

```bash
# Source: gh CLI docs (https://cli.github.com/manual/gh_release_view)
# Get latest tag from upstream repo
latest_tag=$(gh release view \
  --repo "akentner/fritz-callmonitor2mqtt" \
  --json tagName \
  --jq .tagName)
# Returns: "v1.7.4"
```

### yq Field Extraction from .upstream.yaml

```bash
# Source: yq docs (https://mikefarah.gitbook.io/yq)
# yq 4.x syntax (pre-installed on ubuntu-latest)
upstream_repo=$(yq eval '.upstream.repository' "./.upstream.yaml")
version_strip=$(yq eval '.upstream.version_strip' "./.upstream.yaml")
# upstream_repo = "akentner/fritz-callmonitor2mqtt"
# version_strip = "^v"
```

### Current Version Extraction from build.yaml

```bash
# build.yaml has: args: { VERSION: "1.7.3" }
current_version=$(yq eval '.args.VERSION' "$addon_dir/build.yaml")
# current_version = "1.7.3"
```

### Git Identity + Commit Pattern

```bash
# Source: GitHub Actions community discussions
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# After update-version.py runs:
if ! git diff --quiet; then
  git add "$addon_dir/config.yaml" "$addon_dir/build.yaml" "$addon_dir/README.md"
  git commit -m "chore($addon_name): update to $latest_version"
fi
```

### Workflow Trigger Block (matching existing lint.yml style)

```yaml
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:
```

### Permissions Block (required for push to main)

```yaml
permissions:
  contents: write
```

### GH_TOKEN Environment Variable for gh CLI

```yaml
- name: Check and update add-ons
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    ...
```

---

## State of the Art

| Old Approach          | Current Approach                            | When Changed | Impact                              |
| --------------------- | ------------------------------------------- | ------------ | ----------------------------------- |
| curl + REST API       | `gh release view --json`                    | ~2021        | Simpler; handles auth automatically |
| python-yq (PyPI)      | `yq` (Go binary, mikefarah)                 | ~2020        | Pre-installed on ubuntu-latest      |
| `actions/checkout@v2` | `actions/checkout@v4` (or v6 per this repo) | 2023         | Performance improvements; see note  |

**Note on checkout version:** `lint.yml` uses `actions/checkout@v6`. This is consistent to use for the new workflow as
well.

**Deprecated/outdated:**

- `actions/checkout@v2`: Use v4 minimum (v6 per this repo's convention).
- Direct PAT in workflow env: Use `secrets.GITHUB_TOKEN` for write access within the same repo.

---

## Open Questions

1. **D-07 Conflict: Should lint.yml be triggered for auto-update commits?**

   - What we know: GITHUB_TOKEN pushes do not trigger other workflows (documented GitHub limitation).
   - What's unclear: Whether the user considers this a blocker or acceptable.
   - Recommendation: Surface this in the plan as a known discrepancy. Implement without PAT for now (D-05 requires
     GITHUB_TOKEN only). Document that auto-update commits will not be automatically linted.

2. **Single push vs. per-commit push**

   - What we know: D-02 requires one commit per add-on. Nothing in the decisions specifies one push per commit.
   - What's unclear: Whether pushing once at the end (batching commits) or after each commit is preferred.
   - Recommendation: Push once at the end of the loop. This is simpler and reduces API calls. If a mid-loop failure
     occurs, commits made before the failure are still present locally but not pushed — this is acceptable for the error
     handling model in D-04.

3. **update-version.py is interactive when --check-release is used**
   - What we know: The `--check-release` flag triggers `input()` if a release is not found. This would hang a workflow.
     The workflow must NOT use `--check-release`.
   - What's unclear: Nothing — `--check-release` is clearly a developer convenience flag.
   - Recommendation: Call `update-version.py` without `--check-release` in the workflow. The `gh release view` step
     already verified the release exists before calling the script.

---

## Project Constraints (from CLAUDE.md)

| Constraint                                                                      | Applies To                                                |
| ------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Workflow files use kebab-case names                                             | New file must be `auto-update.yml`                        |
| YAML: 2-space indent, 120-char limit                                            | Workflow YAML must comply                                 |
| Shell: `#!/bin/bash` + `set -e` convention                                      | Inline workflow scripts follow same style                 |
| shellcheck ignores: SC1091, SC2034 globally; SC2086, SC2129, SC2001 for Actions | `.actionlint.yml` already relaxes these                   |
| No hardcoded add-on lists                                                       | D-01 (dynamic discovery) aligns with this                 |
| Commit format: `chore({scope}): ...`                                            | D-03 format matches existing Conventional Commits style   |
| Git commits in English                                                          | Commit messages must be English                           |
| Versions never edited manually                                                  | Script `update-version.py` must be called, not manual sed |

---

## Sources

### Primary (HIGH confidence)

- GitHub Actions runner-images Ubuntu2404-Readme.md — confirmed yq 4.52.4, gh 2.88.1, git 2.53.0, jq 1.7 on
  ubuntu-latest
- `gh` CLI docs (https://cli.github.com/manual/gh_release_view) — `--repo`, `--json tagName`, `--jq .tagName` flags
  confirmed
- GitHub Docs — Triggering a workflow (https://docs.github.com/actions/using-workflows/triggering-a-workflow) —
  GITHUB_TOKEN push does not trigger other workflows; confirmed with GITHUB_TOKEN docs

### Secondary (MEDIUM confidence)

- alexbelgium/hassio-addons `99-run.sh` — pattern: per-addon loop with jq config parsing, string comparison for version
  check, `git add -A && git commit && git push` per-addon
- `scripts/update-version.py` source code — exit code analysis: 0 for "updated" AND "no-op"; 1 for partial failure only.
  Confirmed no interactive prompts unless `--check-release` is passed.

### Tertiary (LOW confidence)

- Community discussion about GITHUB_TOKEN triggering — multiple GitHub community discussions confirm the limitation,
  consistent with official docs

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — tools confirmed pre-installed on ubuntu-latest via official runner-images repo
- Architecture: HIGH — patterns derived from reading actual source files + official gh CLI docs
- Pitfalls: HIGH for P1 (GITHUB_TOKEN/D-07 conflict, documented official limitation), HIGH for P2 (update-version.py
  exit code, read from source), MEDIUM for P3-P6 (derived from code analysis + community patterns)

**Research date:** 2026-04-04 **Valid until:** 2026-07-04 (stable toolchain — gh/yq versions change slowly; GITHUB_TOKEN
behavior is stable policy)
