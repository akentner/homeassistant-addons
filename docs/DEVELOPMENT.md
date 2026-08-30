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

Four secrets are threaded through the build workflow. `_build-template.yml` declares all four as optional `secrets:`
(`HA_BASE_URL`, `HA_WEBHOOK_ID`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`) and reads them by name in the
notify steps. Each caller passes them explicitly with named mappings. Missing callee secret declarations alone are not a
`startup_failure` cause when using `secrets: inherit`; named mappings are used here for least privilege. Do not use
`secrets: inherit` when least privilege is the goal. `GITHUB_TOKEN` is auto-injected and used directly by
`docker/login-action` to authenticate to `ghcr.io`.

| Secret                   | Required | Notes                                |
| ------------------------ | -------- | ------------------------------------ |
| `HA_BASE_URL`            | yes      | Public HA URL; no trailing slash     |
| `HA_WEBHOOK_ID`          | yes      | Random value; see WEBHOOK_SETUP.md   |
| `CF_ACCESS_CLIENT_ID`    | optional | Needed when HA is behind CF Access   |
| `CF_ACCESS_CLIENT_SECRET`| optional | Needed when HA is behind CF Access   |

The two `CF_ACCESS_*` secrets are optional because `notify-ha.sh` reads them at runtime and adds the matching
`CF-Access-Client-Id` / `CF-Access-Client-Secret` request headers to the POST only when both are set. When either is
unset the headers are omitted entirely, so LAN / split-horizon callers keep working unauthenticated. Without them, a
GitHub runner resolves the public DNS for `HA_BASE_URL` and is 302'd to the Cloudflare Access login page — see
`docs/WEBHOOK_SETUP.md` for the verification recipe that proves the Access app is scoped to `/api/webhook/*`.

### Job Timeouts

Every job in the repository declares an explicit `timeout-minutes` adjacent to its `runs-on:` block. No job inherits
GitHub's 360-minute default. The caps are sized per-job from measured runtimes, not guessed, with a multiplier that
absorbs a cold cache or one stalled leg without burning a multi-hour runner block.

| Workflow                | Job            | Cap | Derived from             |
| ----------------------- | -------------- | --- | ------------------------ |
| `_build-template.yml`   | `build`        | 45  | aarch64 QEMU leg 13m28s  |
| `auto-update.yml`       | `update`       | 20  | observed 8-28s           |
| `base-image-update.yml` | `update`       | 15  | observed 11-15s          |
| `lint.yml`              | `lint`         | 15  | observed 37-45s          |
| `lint.yml`              | `lint-results` | 5   | reporting only           |
| `opencode.yml`          | `opencode`     | 30  | no baseline; ceiling     |

**Invariant:** the number of `timeout-minutes:` declarations must equal the number of jobs. The check is:

```bash
grep -rh 'timeout-minutes:' .github/workflows/*.yml | wc -l   # must equal job count
```

(The build matrix gives each leg its own cap automatically; the count is per-`timeout-minutes` line, not per matrix
leg.) A new job that ships without a cap is a regression — the CI run inherits the 360-minute default and a hung
build can burn half a day of runner time before GitHub kills it.

The build cap (45 min) is far larger than the rest because the aarch64 leg runs under QEMU emulation at roughly 5x
amd64 wall time. The empirical basis for that leg is exactly one data point — the first ever successful
`Build Coding Assistants` run (`33314988015`, 13m28s) — so the cap absorbs a cold buildx cache rather than risking a
cancellation of a legitimate build. The matrix gives each arch its own cap rather than sharing one; do not collapse
them into a single value, or the amd64 leg would inherit the aarch64 bound.

**Re-deriving a cap:** when you add a new job or move an existing one to a slower runner, measure at least one real
run and multiply by ~3x, then round up to a 5-minute boundary. The empirical-basis comment adjacent to each
`timeout-minutes:` line names the measurement that justifies it — keep that comment in sync with the cap.

### Action Pinning

All action references in `.github/workflows/*.yml` use **floating-major pins**: `@v7`, `@v4`, `@v6`. Never exact patch
versions (`@v7.0.1`), never commit SHAs. Renovate raises majors against floating majors, so the repo gets a PR
when a major lands and the dependency drift stays visible.

The trap is mechanical: **closing a Renovate PR tells Renovate never to offer that exact version again.** Five PRs
were closed manually on 2026-07-27 between 18:10:30 and 18:10:40 — ten seconds for five PRs. The user has since
confirmed this was a mistake, not a decision. Three of those versions (`actions/checkout` v7.0.1,
`docker/build-push-action` v7.3.0, `docker/setup-qemu-action` v4.2.0) consequently have not been re-offered, and
the Node 20 deprecation warning that those bumps would have cleared would have persisted indefinitely. PRs `39` and
`40` exist only because newer versions appeared after the close (`docker/login-action` v4.5.1 → v4.6.0,
`docker/setup-buildx-action` v4.2.0 → v4.3.0).

If a Renovate bump is unwanted, record why in a comment and let it close itself on a future baseline. If a closed
bump is wanted later, apply it by hand or reopen the branch — do not ignore it. `.github/renovate.json` carries no
`ignoreDeps` / `allowedVersions` entries, by design: the accidental close is not encoded as policy.

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
