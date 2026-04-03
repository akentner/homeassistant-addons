# Phase 2: Auto-Update Workflow - Context

**Gathered:** 2026-04-04 **Status:** Ready for planning

<domain>
## Phase Boundary

A GitHub Actions workflow that runs daily (cron at 6:00 UTC) and on `workflow_dispatch`, reads `.upstream.yaml` from
each add-on directory, checks the latest upstream release on GitHub, updates the 3-file version set (`config.yaml`,
`build.yaml`, `README.md`) via `scripts/update-version.py`, and commits directly to `main`. No PR step, no manual review
— fully automatic.

Scope is limited to the workflow file itself. The update script (`scripts/update-version.py`) and `.upstream.yaml` files
are already in place and must not be changed as part of this phase.

</domain>

<decisions>
## Implementation Decisions

### Add-on Discovery

- **D-01:** Dynamic discovery via `find . -maxdepth 2 -name .upstream.yaml` — no hardcoded add-on list. The workflow
  iterates over all directories containing `.upstream.yaml`. New add-ons (e.g., `meridian`) are automatically covered
  without modifying the workflow.

### Commit Granularity

- **D-02:** One commit per add-on update — not a batch commit. Each updated add-on produces its own commit so history is
  clean and individual updates can be reverted independently.
- **D-03:** Commit message format: `chore({addon}): update to {version}` — matches the existing Conventional Commits
  style in this repository. Example: `chore(fritz-callmonitor2mqtt): update to 1.7.4`.

### Error Handling

- **D-04:** Fail-safe mode — if the upstream check fails for one add-on (network error, API unavailable, repo not
  found), the error is logged and the workflow continues processing the remaining add-ons. The job exits with a non-zero
  status (failure) so the error remains visible in the GitHub Actions UI and does not go unnoticed.

### Workflow Permissions & Identity

- **D-05:** Commit author: `github-actions[bot]` with email `github-actions[bot]@users.noreply.github.com` — standard
  GitHub Actions bot identity, no extra secrets or configuration required.
- **D-06:** Workflow requires `permissions: contents: write` in the job definition for the `GITHUB_TOKEN` to push
  commits to `main`.
- **D-07:** Auto-update commits to `main` are intentionally picked up by the existing `lint.yml` push trigger — this
  gives automatic validation of auto-generated changes at no extra setup cost.

### Claude's Discretion

- Shell scripting style inside the workflow (bash vs. composite action vs. separate script file) — Claude decides based
  on what makes the workflow easiest to test locally.
- Whether to use `gh release view` or the GitHub REST API for version checking — Claude uses whichever is more robust
  given the `GITHUB_TOKEN`-only constraint.
- How to parse the current version from `.upstream.yaml` for comparison (yq, grep, python) — Claude decides.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Tooling

- `scripts/update-version.py` — the version update script; downstream agents must understand its CLI interface
  (`./scripts/update-version.py {addon} {version} [--check-release] [--dry-run]`) before designing the workflow
- `fritz-callmonitor2mqtt/.upstream.yaml` — reference for `.upstream.yaml` schema (fields: `upstream.repository`,
  `upstream.version_pattern`, `upstream.version_strip`, `addon.version_pattern`)
- `phone-logger/.upstream.yaml` — second example of `.upstream.yaml`

### Existing CI

- `.github/workflows/lint.yml` — the only existing workflow; read to understand triggers and job structure to keep the
  new workflow consistent in style

### Requirements

- `.planning/REQUIREMENTS.md` §Auto-Update Workflow — AUTO-01 through AUTO-05 are the acceptance criteria

### Conventions

- `.planning/codebase/CONVENTIONS.md` — shell script conventions (bash, `set -e`, shellcheck ignores) and YAML
  formatting rules that apply to the new workflow file

</canonical_refs>
