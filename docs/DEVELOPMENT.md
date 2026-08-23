# Development Guidelines

## Versioning Rules

Each add-on follows a specific versioning scheme for better management.

### Version Format per File

| File          | Format    | Example   | Purpose                      |
| ------------- | --------- | --------- | ---------------------------- |
| `config.yaml` | `X.Y.Z-N` | `1.3.1-0` | Add-on version with subpatch |
| `build.yaml`  | `X.Y.Z`   | `1.3.1`   | Upstream binary version      |
| `README.md`   | `vX.Y.Z`  | `v1.3.1`  | Badge display version        |

### Rules

1. **config.yaml**:

   - Always use subpatch format: `"X.Y.Z-N"`
   - New upstream versions start with `-0`
   - Add-on-only fixes increment: `-1`, `-2`, etc.

2. **build.yaml**:

   - Upstream version only, no subpatch: `"X.Y.Z"`
   - Matches the Docker image version

3. **README.md**:
   - Badge shows main version: `version-vX.Y.Z`
   - Release link shows main version: `tree/vX.Y.Z`

### Example of Correct Versioning

```yaml
# config.yaml
version: "1.3.1-0"

# build.yaml
VERSION: "1.3.1"

# README.md
[release-shield]: https://img.shields.io/badge/version-v1.3.1-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.3.1
```

### Why This Structure?

- **Upstream-Sync**: Add-on version follows upstream with `-0` reset
- **Add-on-Fixes**: Local fixes can be incremented independently
- **Clarity**: Clear separation between add-on and binary version
- **Maintainability**: Better version control and update management

## Version Update Tool

For manual version updates an automated tool is available:

```bash
# Simple version update
make update-version ADDON=<addon-name> VERSION=1.7.2

# With GitHub Release Check
make update-version ADDON=<addon-name> VERSION=1.7.2 CHECK_RELEASE=yes

# Dry-run mode (show only, no changes)
./internal/update-version.py <addon-name> 1.7.2 --dry-run
```

The tool automatically updates:

- `config.yaml`: `version: "1.7.2-0"`
- `build.yaml`: `VERSION: "1.7.2"`
- `README.md`: Badges and release links

## Auto-Update System

Add-ons using `version_pattern: "sync"` in `.upstream.yaml` benefit from:

- Automatic detection of new upstream versions
- Automatic update of `config.yaml`
- Automatic reset of subpatch to `-0`

## Pre-commit Validation

A pre-commit hook automatically validates:

- Correct versioning in all files
- Consistency between version entries
- Compliance with the subpatch format

## GitHub Actions Reusable Build Workflows

Builds run through a local reusable workflow. The template `.github/workflows/_build-template.yml` defines a single job
that resolves the per-arch base image from `build.yaml`, logs into GHCR, and builds/pushes the multi-arch image. Seven
per-addon callers (`build-<addon>.yml`) only set addon-name, display name, description, the arch matrix, and HA webhook
secrets.

### Permissions Contract

The repository default workflow permissions are read-only. Caller and template jobs must explicitly declare
`contents: read` and `packages: write`, otherwise the run aborts with `startup_failure` and zero jobs are scheduled.
`actionlint` and `make lint` passing do not prove call-site permission correctness — the error surfaces only at run
time.

| Component             | `contents` | `packages` | Notes                                   |
| --------------------- | ---------- | ---------- | --------------------------------------- |
| Repo default          | read       | read       | Read-only workflow permission baseline. |
| Caller job            | `read`     | `write`    | Required at every call site.            |
| `_build-template.yml` | `read`     | `write`    | Required for GHCR push via Buildx.      |

### Secrets Contract

`_build-template.yml` declares `HA_BASE_URL` and `HA_WEBHOOK_ID` as optional `secrets:` and reads them by name in the
notify steps. Each caller passes them explicitly with named mappings. Missing callee secret declarations alone are not a
`startup_failure` cause when using `secrets: inherit`; named mappings are used here for least privilege. Do not use
`secrets: inherit` when least privilege is the goal. `GITHUB_TOKEN` is auto-injected and used directly by
`docker/login-action` to authenticate to `ghcr.io`.

### Trigger Pitfalls

GitHub does not evaluate `paths` filters for tag pushes; the per-addon `tags:` pattern is evaluated independently, so a
matching addon tag (for example `network-tools/v*`) can still trigger a build even when the push changes only
`.github/workflows/**`. A pure branch push to `main` that changes only workflow files will not match the add-on `paths:`
filters. Manual `workflow_dispatch` on a representative caller is the reliable end-to-end verification — the verified
run for `build-network-tools.yml` is `32633538391`, which passed.

This repository has also observed a trigger coupling that is not explained by the simple path rules: commit `3925f58`
changed only `scripts/check-version-tags.sh`, yet five per-addon Build runs were scheduled. Do not infer filter behavior
from one run; inspect the run list and the event payload when debugging triggers. Treat a representative dispatch as
service-affecting because it can push images to GHCR and send HA webhooks.

### Verification Checklist

- Inspect scheduled jobs reliably with `gh run view <run-id> --json jobs` — the web UI hides zero-job runs but the API
  exposes them, which is how a `startup_failure` is diagnosed.
- Confirm each caller sets `permissions: { contents: read, packages: write }` at the job level.
- Confirm the template sets the same two permissions on its single job.
- Confirm HA secrets are passed by name (`HA_BASE_URL`, `HA_WEBHOOK_ID`), not via `inherit`.
- For workflow-only edits, use `workflow_dispatch` on a representative caller to exercise the reusable workflow
  end-to-end before relying on a tag push.
