# Auto-Update Workflow Research
_Researched: 2026-04-03_

## Summary

A GitHub Actions workflow for daily upstream release checking is straightforward to implement using the GitHub REST API (`/repos/{owner}/{repo}/releases/latest`) and the existing `update-version.py` script. The hassio-addons organization uses a custom `repository-updater` action combined with Renovate for their add-on ecosystem, but for a small private repo, a self-contained shell-based workflow is the right approach. Direct commit + push (no PR) is feasible and commonly done for automated version bumps in single-maintainer repos.

## Findings

### GitHub Actions Patterns for Upstream Version Checking

**Pattern 1: GitHub API polling (shell-based)**
The most common self-contained approach is a workflow that:
1. Uses `curl https://api.github.com/repos/{owner}/{repo}/releases/latest | jq -r .tag_name` to get the current upstream version
2. Compares it against the version stored in the add-on's config file
3. Runs the update script if versions differ
4. Commits and pushes directly to main

This requires no external actions beyond `actions/checkout` and a GitHub token with `contents: write` permission.

**Pattern 2: Renovate bot**
The hassio-addons organization uses Renovate (confirmed via `renovate.json` in their workflows repo). Renovate supports a `regex` manager that can match version strings in arbitrary files using custom patterns, paired with a `github-releases` datasource. This is powerful but requires:
- Renovate app installed on the repository
- A `renovate.json` config file defining custom managers for each file pattern
- The 3-file version sync would need three separate regex rules

Renovate creates PRs by default. Auto-merge can be configured but adds complexity. **Verdict: overkill for this repo's scale.**

**Pattern 3: hassio-addons/repository-updater action**
The hassio-addons organization uses a custom action (`hassio-addons/repository-updater@v2`) that is dispatched via `workflow_call` from upstream add-on repos when they publish a new release. This is an event-driven (push-based) model, not a polling model. It assumes the upstream project is also maintained in the hassio-addons ecosystem. **Not applicable here** since upstreams are external repos.

### How the Existing `.upstream.yaml` Structure Fits

The `.upstream.yaml` format already captures everything needed for a polling workflow:
- `upstream.repository` — GitHub repo to check (e.g., `akentner/fritz-callmonitor2mqtt`)
- `upstream.version_pattern` — glob for tag filtering (e.g., `v*`)
- `upstream.version_strip` — regex to convert tag to version (e.g., `^v`)
- `addon.version_pattern: sync` — means use the upstream version directly

A workflow can `find` all directories containing `.upstream.yaml`, parse each with `yq`, call the GitHub API, compare, and invoke `update-version.py`.

### Version Comparison Strategy

The GitHub API endpoint `GET /repos/{owner}/{repo}/releases/latest` returns the most recent non-prerelease, non-draft release. The `tag_name` field contains the tag (e.g., `v1.7.4`). After stripping the prefix via `sed` or `python -c "import re; ..."`, compare against the current version in `build.yaml` (the `VERSION` arg, which is always bare semver without prefix).

If the versions differ, run `python scripts/update-version.py {addon} {new_version}`.

### Committing Without a PR

For automated version bumps in single-maintainer repos, committing directly to main is the standard approach. Key implementation details:
- Set `git config user.email "github-actions[bot]@users.noreply.github.com"` and `git config user.name "github-actions[bot]"` in the workflow
- Use the default `GITHUB_TOKEN` with `permissions: contents: write`
- Check `git diff --quiet` before committing to avoid empty commits
- Use `git push` — no force push needed since cron jobs run sequentially with concurrency control

### Handling Multiple Add-ons

Loop over `find . -name ".upstream.yaml" -maxdepth 2`. For each, extract the add-on name from the directory and parse the YAML. Commit all changed add-ons in a single commit or one commit per add-on — single commit is simpler.

### Concurrency and Idempotency

- Use `concurrency: group: auto-update` to prevent overlapping cron runs
- If two add-ons update simultaneously, a single-commit approach handles both cleanly
- If `update-version.py` returns exit code 0 with "No changes needed", skip that add-on

### `yq` in GitHub Actions

The `ubuntu-latest` runner ships `yq` (go-based version from mikefarah). Use `yq e '.upstream.repository' .upstream.yaml` syntax. The `.upstream.yaml` files do not use HA custom tags (`!secret`), so no `--unsafe` flag is needed here (unlike `config.yaml`).

### GitHub API Rate Limits

The default `GITHUB_TOKEN` allows 1,000 requests per hour per repository. With 2 add-ons checked daily, this is negligible. No authentication issues expected.

## Recommended Approach

**Self-contained shell-based GitHub Actions workflow** — no external tools beyond `yq` (already on runner) and `python3` (already on runner).

Workflow outline:
```yaml
name: Auto-Update Add-ons

on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:

concurrency:
  group: auto-update
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      - name: Check and update add-ons
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          UPDATED=""
          for upstream_file in $(find . -name ".upstream.yaml" -maxdepth 2); do
            addon_dir=$(dirname "$upstream_file")
            addon_name=$(basename "$addon_dir")
            repo=$(yq e '.upstream.repository' "$upstream_file")
            strip_pattern=$(yq e '.upstream.version_strip // ""' "$upstream_file")

            # Get latest upstream release tag via GitHub CLI
            latest_tag=$(gh release view --repo "$repo" --json tagName -q .tagName 2>/dev/null || echo "")
            if [ -z "$latest_tag" ]; then
              echo "No release found for $repo, skipping"
              continue
            fi

            # Strip prefix (e.g. "^v" -> strip leading v)
            latest_version=$(echo "$latest_tag" | sed 's/^v//')

            # Get current version from build.yaml
            current_version=$(yq e '.args.VERSION' "$addon_dir/build.yaml")

            if [ "$latest_version" = "$current_version" ]; then
              echo "$addon_name is up to date ($current_version)"
              continue
            fi

            echo "Updating $addon_name: $current_version -> $latest_version"
            python scripts/update-version.py "$addon_name" "$latest_version"
            UPDATED="$UPDATED $addon_name"
          done

          if [ -n "$UPDATED" ]; then
            git add -A
            git commit -m "chore: update$(echo $UPDATED | sed 's/ / addon /g') to upstream version"
            git push
          fi
```

Note: Use `gh release view` (GitHub CLI, available on `ubuntu-latest`) instead of raw `curl` — it handles auth automatically via `GH_TOKEN` and is cleaner than parsing JSON manually.

The `version_strip` pattern in `.upstream.yaml` is a regex (e.g., `^v`), but since all current add-ons just strip a leading `v`, a simple `sed 's/^v//'` works. If more complex stripping is ever needed, invoke Python for the regex substitution.

## Gotchas / Risks

**Pre-commit hooks not running in CI commit.** The workflow uses `git commit` directly — pre-commit hooks don't run unless explicitly invoked. Since `validate-versions.sh` is a pre-commit hook, the workflow should either call `make validate-versions` before committing or accept that the validation only happens locally. The risk is low: `update-version.py` is well-tested and produces valid output.

**Empty commit if update-version.py makes no changes.** The script exits 0 even when "No changes needed." Always check `git diff --quiet --cached` before committing. Without this check, the workflow would create an empty commit and trigger the push, which then triggers lint CI unnecessarily.

**Commit triggering lint workflow.** A push to main from the workflow will trigger the existing `lint.yml` workflow. This is fine — it validates the change. However, to avoid infinite loops (if lint.yml ever triggers auto-update), ensure the auto-update workflow is only triggered by `schedule` and `workflow_dispatch`, not `push`.

**`version_strip` regex vs shell sed.** The `.upstream.yaml` spec says `version_strip` is a regex (e.g., `^v`). The simple `sed 's/^v//'` works for the current add-ons. If a future add-on uses a more complex pattern (e.g., `^release-`), the sed command would need updating. A more robust implementation would use Python to apply the regex properly: `python3 -c "import re, sys; print(re.sub(r'${strip}', '', sys.argv[1]))" "$latest_tag"`.

**GitHub API unavailability.** If `gh release view` fails (repo has no releases, network issue), the script skips with a message. This is the right behavior — don't fail the entire workflow over one add-on.

**Direct push to main bypasses branch protection.** If branch protection rules require PRs, the `GITHUB_TOKEN` push will fail. The current repo has no branch protection rules (small personal repo), but this should be kept in mind if protection is added later. A `[skip ci]` commit message suffix can be added to prevent lint re-runs if desired.

**Meridian's rapid release cadence.** Meridian releases multiple times per day (v1.26.0 through v1.26.5 all on April 3). A daily cron at 6:00 UTC would only catch the latest release per day, skipping intermediates — which is desirable behavior (pin to stable, not every micro-release). No special handling needed.
