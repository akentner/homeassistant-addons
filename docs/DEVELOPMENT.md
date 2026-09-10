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

For manual version updates use the `update-version` tool. Full reference — input formats, tag format, pre-push hook,
cross-artifact bumping, worked examples — lives in **[`docs/UPDATE_VERSION.md`](UPDATE_VERSION.md)**. This section keeps
only the minimal pointer.

Quick reference:

```bash
# SemVer bump (resets subpatch to -0)
make update-version ADDON=<addon-name> VERSION=1.7.2

# Subpatch bump (preserves subpatch)
make update-version ADDON=<addon-name> VERSION=1.7.2-1
```

The tool updates `config.yaml`, `build.yaml`, and `README.md` badges, then creates and pushes the git tag.

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

Versioning is not the whole of it: see `## Security Scanning` below for the two security hooks that also run on every
commit and in CI.

## Security Scanning

Two security hooks run on every commit and, through `pre-commit run --all-files` in `.github/workflows/lint.yml`, in CI
as well. Both are also reached by `make check-all` via its `lint` target, so both must stay offline and deterministic.

### What runs

- **`gitleaks`** (pinned `rev: v8.30.1`) scans the **staged diff**, not the working tree, with `--redact` so that a hit
  never reaches the terminal log or the CI job log. Its allowlists live in `.gitleaks.toml`.
- **`zizmor`** (pinned `zizmor==1.30.1`) audits workflow and composite-action YAML under `.github/` for security
  problems `actionlint` does not look for at all: untrusted `${{ }}` interpolation into `run:` blocks, over-broad
  `permissions:`, mutable action refs, and credential persistence through `actions/checkout`. It carries `--offline` on
  its hook entry, and not cosmetically: zizmor performs online audits whenever `GH_TOKEN`, `GITHUB_TOKEN` or
  `ZIZMOR_GITHUB_TOKEN` is set, which would make a `check-all` member environment-dependent.

### What is not covered, and why

**CVEs in the built GHCR images are deliberately out of scope.** This repository contains no upstream application source
— every Dockerfile downloads its payload at build time — so the vulnerabilities live in the published images, not in the
working tree. A filesystem scan here would find almost nothing, and an image scan needs a built image plus a
network-fetched vulnerability database. That disqualifies it as a `check-all` member: see the policy comment above
`verify-images` in the `Makefile`, which requires every member to be offline, deterministic, and to fail only for
something in your own working tree.

Also not covered: Go-module vulnerability scanning, SAST, and SBOM generation.

**The secret scanner is a deliberate no-op in CI.** `lint.yml` runs `pre-commit run --all-files`, and nothing is ever
staged in CI, while the hook scans the staged diff. Git history was instead covered once, by a full-history
`gitleaks git` scan taken when the hook was introduced: it reported eight findings, all of them synthetic test fixtures
or planning documents quoting those fixtures, so no credential rotation was required. Those eight findings are the
entire reason `.gitleaks.toml` exists.

**Detection is narrower than the rule list suggests, so verify rather than assume.** A bare AWS access key id shape
(`AKIA` followed by sixteen uppercase alphanumerics) was measured as **not** detected by the v8.30.1 default ruleset in
file or diff scan mode — zero hits in ten random draws — even though the `aws-access-token` rule is present in that
ruleset and accepted by `--enable-rule`. A GitHub PAT shape (`ghp_` followed by thirty-six alphanumerics) is detected
ten times out of ten. Whenever the gitleaks pin or `.gitleaks.toml` changes, plant a control secret and confirm the hook
exits non-zero before trusting a green run.

### The `[extend]` stanza is mandatory

`.gitleaks.toml` begins with:

```toml
[extend]
useDefault = true
```

Do not remove it. A `.gitleaks.toml` carrying only allowlists **replaces** the built-in ruleset instead of extending it:
every rule silently disappears and the hook keeps reporting `Passed`, on every commit, forever. It is the single most
dangerous edit that can be made to that file, and it produces no error of any kind.

### Adding an allowlist entry for a legitimate false positive

When a test fixture or a planning document legitimately needs a synthetic credential shape, add a narrow
**path-and-rule-scoped** `[[allowlists]]` block to `.gitleaks.toml`: exact anchored `paths` regexes plus a `targetRules`
list naming only the rule ids that actually fire there. A repo-wide `regexes` allowlist is not an option, and neither is
a bare `^\.planning/` path prefix — planning documents are scanned even though `.prettierignore` excludes them, and a
real secret pasted into some future planning document must still trip the hook. Fingerprint allowlisting is avoided too:
a gitleaks fingerprint encodes a line number and goes stale on the next edit above it.

### Why `zizmor.yml` relaxes the pinning audit

`zizmor.yml` at the repository root relaxes exactly one audit, and only in one respect: `unpinned-uses` is configured
with `policies: {"*": ref-pin}`, so it requires a symbolic ref but not a commit hash. That mirrors this repository's own
documented policy — see `### Action Pinning` below, which makes floating-major refs deliberate and forbids SHA pins. The
audit is **not** disabled: a bare `@main` or a missing ref is still an error. If that pinning policy ever changes, this
relaxation must go with it. Every other audit stays enabled at full severity.

Twenty-seven pre-existing workflow findings — `template-injection` in `_build-template.yml` foremost among them — are
deferred through per-finding, line-anchored `ignore` entries in `zizmor.yml`, each carrying a comment that marks it a
deferral rather than a disposition. That keeps the hook red for every **new** finding, which a `--min-severity` floor or
an `|| true` wrapper would not do. Those entries match on the **basename** of the workflow file, not on its path. Being
line-anchored, they go stale when a workflow shifts lines: the finding reappears and the hook goes red. That is
deliberately fail-closed, so a stale suppression forces a re-triage instead of being carried along silently. The fixes
are tracked in the open Phase 8 "CI/CD Hardening" work.

The relaxation has a blind spot worth naming, because it already cost something. A `ref-pin` policy is satisfied by
_any_ symbolic ref, and `latest` is a symbolic ref — so `.github/workflows/opencode.yml` passed the `unpinned-uses`
audit for its whole life while carrying `anomalyco/opencode/github@latest`, a ref its upstream owner could repoint at
will, in a job holding `MINIMAX_API_KEY`. The audit that exists to catch mutable refs did not catch that one. The
relaxation is deliberately left untouched here: narrowing it (per-repository policies, or an explicit deny for `latest`
/ `main` / `master`) is an open follow-up, not part of the change that pinned that one workflow.

### Highest-value follow-up

A scheduled scan of the nine published GHCR images with results uploaded into GitHub Code Scanning. That is where the
CVEs actually are, and Code Scanning is the right home for findings nobody can fix inside a pre-commit hook. It belongs
to the open Phase 8 "CI/CD Hardening" work, not to the local hook set.

## GitHub Actions Reusable Build Workflows

Builds run through a local reusable workflow. The template `.github/workflows/_build-template.yml` defines a single job
that resolves the per-arch base image from `build.yaml`, logs into GHCR, and builds/pushes the multi-arch image. One
caller, `.github/workflows/build.yml`, invokes it once per add-on and arch leg. That caller hand-authors none of the
per-add-on values: its `detect` job reads the add-on list, the arch legs (from `build.yaml` `build_from`, falling back
to `config.yaml` `arch:`), the display name and the description out of the add-on's own manifests, and passes them
through the template's existing `workflow_call` inputs. The HA webhook secrets are still mapped by name at the call
site.

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
(`HA_BASE_URL`, `HA_WEBHOOK_ID`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`) and reads them by name in the notify
steps. Each caller passes them explicitly with named mappings. Missing callee secret declarations alone are not a
`startup_failure` cause when using `secrets: inherit`; named mappings are used here for least privilege. Do not use
`secrets: inherit` when least privilege is the goal. `GITHUB_TOKEN` is auto-injected and used directly by
`docker/login-action` to authenticate to `ghcr.io`.

| Secret                    | Required | Notes                              |
| ------------------------- | -------- | ---------------------------------- |
| `HA_BASE_URL`             | yes      | Public HA URL; no trailing slash   |
| `HA_WEBHOOK_ID`           | yes      | Random value; see WEBHOOK_SETUP.md |
| `CF_ACCESS_CLIENT_ID`     | optional | Needed when HA is behind CF Access |
| `CF_ACCESS_CLIENT_SECRET` | optional | Needed when HA is behind CF Access |

The two `CF_ACCESS_*` secrets are optional because `notify-ha.sh` reads them at runtime and adds the matching
`CF-Access-Client-Id` / `CF-Access-Client-Secret` request headers to the POST only when both are set. When either is
unset the headers are omitted entirely, so LAN / split-horizon callers keep working unauthenticated. Without them, a
GitHub runner resolves the public DNS for `HA_BASE_URL` and is 302'd to the Cloudflare Access login page — see
`docs/WEBHOOK_SETUP.md` for the verification recipe that proves the Access app is scoped to `/api/webhook/*`.

### Job Timeouts

Every job in the repository declares an explicit `timeout-minutes` adjacent to its `runs-on:` block. No job inherits
GitHub's 360-minute default. The caps are sized per-job from measured runtimes, not guessed, with a multiplier that
absorbs a cold cache or one stalled leg without burning a multi-hour runner block.

| Workflow                | Job            | Cap | Derived from            |
| ----------------------- | -------------- | --- | ----------------------- |
| `_build-template.yml`   | `build`        | 45  | aarch64 QEMU leg 13m28s |
| `build.yml`             | `detect`       | 5   | manifest reads only     |
| `auto-update.yml`       | `update`       | 20  | observed 8-28s          |
| `base-image-update.yml` | `update`       | 15  | observed 11-15s         |
| `lint.yml`              | `lint`         | 15  | observed 37-45s         |
| `lint.yml`              | `lint-results` | 5   | reporting only          |
| `opencode.yml`          | `opencode`     | 30  | no baseline; ceiling    |

One documented exception: a job that is a reusable-workflow call (`uses:`) may **not** declare `timeout-minutes` —
actionlint rejects it, because only `name`, `uses`, `with`, `secrets`, `needs`, `if` and `permissions` are allowed
there. `build.yml`'s `build` job is such a call, so it carries no cap of its own and every leg inherits the template's
45 instead. Do not "fix" the apparent omission; it is a lint error.

**Invariant:** the number of `timeout-minutes:` declarations must equal the number of jobs, minus any reusable-workflow
call jobs. The check is:

```bash
grep -rh 'timeout-minutes:' .github/workflows/*.yml | wc -l   # must equal job count
```

(The build matrix gives each leg its own cap automatically; the count is per-`timeout-minutes` line, not per matrix
leg.) A new job that ships without a cap is a regression — the CI run inherits the 360-minute default and a hung build
can burn half a day of runner time before GitHub kills it.

The build cap (45 min) is far larger than the rest because the aarch64 leg runs under QEMU emulation at roughly 5x amd64
wall time. The empirical basis for that leg is exactly one data point — the first ever successful
`Build Coding Assistants` run (`33314988015`, 13m28s) — so the cap absorbs a cold buildx cache rather than risking a
cancellation of a legitimate build. The matrix gives each arch its own cap rather than sharing one; do not collapse them
into a single value, or the amd64 leg would inherit the aarch64 bound.

**Re-deriving a cap:** when you add a new job or move an existing one to a slower runner, measure at least one real run
and multiply by ~3x, then round up to a 5-minute boundary. The empirical-basis comment adjacent to each
`timeout-minutes:` line names the measurement that justifies it — keep that comment in sync with the cap.

### Action Pinning

All action references in `.github/workflows/*.yml` use **floating-major pins**: `@v7`, `@v4`, `@v6`. Never exact patch
versions (`@v7.0.1`), never commit SHAs. Renovate raises majors against floating majors, so the repo gets a PR when a
major lands and the dependency drift stays visible.

The trap is mechanical: **closing a Renovate PR tells Renovate never to offer that exact version again.** Five PRs were
closed manually on 2026-07-27 between 18:10:30 and 18:10:40 — ten seconds for five PRs. The user has since confirmed
this was a mistake, not a decision. Three of those versions (`actions/checkout` v7.0.1, `docker/build-push-action`
v7.3.0, `docker/setup-qemu-action` v4.2.0) consequently have not been re-offered, and the Node 20 deprecation warning
that those bumps would have cleared would have persisted indefinitely. PRs `39` and `40` exist only because newer
versions appeared after the close (`docker/login-action` v4.5.1 → v4.6.0, `docker/setup-buildx-action` v4.2.0 → v4.3.0).

If a Renovate bump is unwanted, record why in a comment and let it close itself on a future baseline. If a closed bump
is wanted later, apply it by hand or reopen the branch — do not ignore it. `.github/renovate.json` carries no
`ignoreDeps` / `allowedVersions` entries, by design: the accidental close is not encoded as policy.

**One documented exception:** `.github/workflows/opencode.yml` pins `anomalyco/opencode/github` to the exact tag
`@v1.18.30`, not a floating major. Upstream publishes no major tag at all — `git/ref/tags/v1` and `git/ref/tags/v1.18`
both return 404 — so `@v1` is not a ref that exists. The previous value was `@latest`, which is mutable: the upstream
owner could repoint it and change what executes while `MINIMAX_API_KEY` is already in the job environment. An exact tag
is the only immutable option that is not a commit SHA, and Renovate's `github-actions` manager still raises bumps
against exact tags, so drift stays visible the same way it does for the floating majors. If upstream ever starts
publishing a major tag, this pin should go back to `@v1`. The other half of that workflow's hardening — the
`author_association` gate on its comment trigger — is guarded by `internal/verify-opencode-gate.py`, which re-derives
the gate's truth table from the workflow file and turns red if the author clause is ever removed.

### Trigger Pitfalls

GitHub does not evaluate `paths` filters for tag pushes at all. No workflow in this repository triggers on a tag any
more, so pushing an `<addon>/v*` tag schedules nothing — see `.github/RELEASE.md`, `### Tags do not trigger builds`, for
why that trigger was removed rather than shared. A pure branch push to `main` that changes only workflow files does not
match `build.yml`'s `paths:` filter either — that filter is `"*/**"` with the non-add-on top-level directories negated,
so it covers every file inside an add-on directory (a `run.sh` or Go-source change rebuilds the image) and nothing
outside one. `workflow_dispatch` of `build.yml`, scoped by its `addons` input
(`gh workflow run build.yml -f addons=network-tools`), is the reliable end-to-end verification — the verified run for
the network-tools build is `32633538391`, which passed.

This repository has also observed a trigger coupling that is not explained by the simple path rules: commit `3925f58`
changed only `scripts/check-version-tags.sh`, yet five per-addon Build runs were scheduled. Do not infer filter behavior
from one run; inspect the run list and the event payload when debugging triggers. Treat a dispatch as service-affecting
because it can push images to GHCR and send HA webhooks.

### Verification Checklist

- Inspect scheduled jobs reliably with `gh run view <run-id> --json jobs` — the web UI hides zero-job runs but the API
  exposes them, which is how a `startup_failure` is diagnosed.
- Confirm each caller sets `permissions: { contents: read, packages: write }` at the job level.
- Confirm the template sets the same two permissions on its single job.
- Confirm HA secrets are passed by name (`HA_BASE_URL`, `HA_WEBHOOK_ID`), not via `inherit`.
- For workflow-only edits, use `workflow_dispatch` on a representative caller to exercise the reusable workflow
  end-to-end before relying on a tag push.
