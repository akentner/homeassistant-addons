# Multi-Add-on Auto-Update System

## 🚀 Overview

`.github/workflows/auto-update.yml` (workflow name `Auto Update`) watches upstream projects for new releases and bumps
the matching add-on's version files. Add-ons are not listed anywhere in the workflow: it discovers them by scanning the
tree for `.upstream.yaml`, so adding one needs no workflow edit.

Four add-ons are configured today — `authentik`, `gatus`, `meridian` and `phone-logger`. That list is derived, not
declared; reproduce it with:

```bash
find . -maxdepth 2 -name .upstream.yaml | sort
```

This document covers the workflow surface: discovery, the update loop, error handling, and the two `.upstream.yaml` keys
the workflow reads. For the release and tag contract — what a `<addon>/v<version>` tag means, and what it does not prove
— see `.github/RELEASE.md`.

## 📁 Add-on Setup

### Create a `.upstream.yaml` for each add-on

```text
your-addon/
├── config.yaml
├── build.yaml
├── Dockerfile
├── run.sh
└── .upstream.yaml  ← This file configures auto-updates
```

### Example `.upstream.yaml`

```yaml
upstream:
  # GitHub repository of the upstream project. READ by the workflow.
  repository: "owner/project-name"

  # Documents the shape of the upstream tag. NOT read by any code.
  version_pattern: "v*"

  # sed regex applied to the resolved release tag ("v1.0.3" -> "1.0.3"). READ by the workflow.
  version_strip: "^v"

addon:
  # Documents the intent that the add-on version follows upstream. NOT read by any code —
  # the behaviour is unconditional, see "What the workflow reads" below.
  version_pattern: "sync"
```

## 🔄 What happens automatically

### 1. **Daily Check** (6:00 UTC)

- System discovers all add-ons with `.upstream.yaml`
- Checks each configured upstream repository for new releases
- Compares current with available versions

### 2. **Sequential per-add-on update**

Add-ons are processed **sequentially**, in one shell loop: `while IFS= read -r` (`auto-update.yml:83`) reading from
`find . -maxdepth 2 -name .upstream.yaml | sort` (`auto-update.yml:157`). There is no build matrix and no per-add-on
job, so add-ons are handled one after another in sorted order.

For each add-on the loop:

- reads `.upstream.repository` and `.upstream.version_strip` from the file (`auto-update.yml:90-91`);
- resolves the upstream project's **latest release** with `gh release view --repo <repo> --json tagName --jq .tagName`
  (`auto-update.yml:94`) — the release, not a tag listing;
- applies `version_strip` as a `sed` regex to that tag (`auto-update.yml:103`);
- reads the add-on's current version from `.args.VERSION` in `{addon}/build.yaml` (`auto-update.yml:106`) and skips the
  add-on when the two already match (`auto-update.yml:108-111`);
- calls `internal/update-version.py <addon> <version> --no-tag` (`auto-update.yml:123`) to write the 3-file version set
  (`{addon}/config.yaml`, `{addon}/build.yaml`, `{addon}/README.md`);
- prepends the upstream release body to `{addon}/CHANGELOG.md`, but only when that body is non-empty, and runs prettier
  over the result (`auto-update.yml:135-150`). Prettier does not wrap bare URLs, so a release body containing one still
  lands a `CHANGELOG.md` that fails `markdownlint` MD034 and has to be hand-fixed afterwards. That is a known open
  defect, not a design choice — it is recorded as ledger item 10 in `.planning/WINDOWS.md`;
- creates one `git commit` **inside** the loop, subject `chore(<addon>): update to <version>` (`auto-update.yml:154`).

A single `git push` runs after the loop and only when at least one commit was made (`auto-update.yml:166`).

Runs are serialized against each other and against `base-image-update.yml` through the shared
`concurrency: group: addon-version-bump` (`auto-update.yml:32-34`), so two bump runs cannot race the same push.

### 3. **Error handling**

A per-add-on failure — an unreachable upstream release (`auto-update.yml:94-98`) or a failing
`internal/update-version.py` (`:123-127`) — prints an `ERROR:` line, sets `ERRORS=1`, and `continue`s to the next
add-on, so one add-on's failure does not stop the others. Those two are the only guarded failures. The step runs under
`set -eo pipefail` (`auto-update.yml:70`), so any other command failing aborts the step mid-loop and the remaining
add-ons are never processed: `yq eval` (`:90-91`), `npx --yes prettier@3.9.6` (`:148`) and `git add` / `git commit`
(`:153-154`) are all unguarded. When the loop does reach the end, the last statement of the step is `exit $ERRORS`
(`auto-update.yml:171`).

The failure signal is exactly two things: the `ERROR:` lines in the run log, and the non-zero job conclusion. Watch the
workflow run list, or subscribe to GitHub's own failed-run notifications.

The build dispatch described below adds two more outcomes:

- a changed directory with no `.github/workflows/build-<addon>.yml` is reported as a warning and does **not** fail the
  run — usually it is not an add-on directory at all;
- a dispatch that fails makes the run red, because the version bump is already on `main` at that point.

## 🎯 Manual Control

`auto-update.yml:6` declares a bare `workflow_dispatch:` with no `inputs:`, so the Actions UI offers no fields. A manual
run always processes every add-on that has a `.upstream.yaml`; there is no way to select one add-on or to force a
re-update of a version that already matches.

```text
Actions → "Auto Update" → "Run workflow"
```

To bump a single add-on, run the version script locally instead and follow `.github/RELEASE.md`:

```bash
make update-version ADDON=meridian VERSION=1.62.7
```

## 🔑 Why the workflow dispatches its own builds

The workflow pushes to `main` using the default `GITHUB_TOKEN`, and GitHub creates **no** workflow runs for an event
produced by that token. Every `.github/workflows/build-<addon>.yml` triggers on a `push` to `main` filtered by
`paths: <addon>/**`, so none of them ever fires for an automated bump. Left at that, an automated update publishes a
manifest advertising a version whose image was never built.

`workflow_dispatch` is the documented exception: a dispatch event created with `GITHUB_TOKEN` does produce a run
(<https://docs.github.com/actions/using-workflows/triggering-a-workflow>). So the workflow calls
`internal/dispatch-builds.sh` immediately after its `git push` (`auto-update.yml:167`). The script derives the changed
add-on directories from `git diff --name-only "$BASE_SHA"..HEAD` — `BASE_SHA` being the pre-bump `HEAD` captured at the
start of the step (`auto-update.yml:77`) — and issues one `gh workflow run build-<addon>.yml --ref <ref>` per add-on.

Creating a dispatch requires the `actions: write` permission, which the job requests explicitly (`auto-update.yml:49`).
`base-image-update.yml:33` requests the same scope for the same reason; no other workflow in this repository does.

## 🏷️ Tags

This path creates **no** tags. `internal/update-version.py` is called with `--no-tag` (`auto-update.yml:123`), so an
automated bump lands as a commit on `main` and nothing else. Releases are tagged out of band — see `.github/RELEASE.md`
for the tag schema and for what a `<addon>/v<version>` tag does and does not prove about the tree it points at.

## 📋 What the workflow reads from `.upstream.yaml`

Exactly two keys:

| Key                       | Read at              | Effect                                                            |
| ------------------------- | -------------------- | ----------------------------------------------------------------- |
| `.upstream.repository`    | `auto-update.yml:90` | the GitHub repo whose latest release is resolved                  |
| `.upstream.version_strip` | `auto-update.yml:91` | `sed` regex applied to the release tag to obtain the bare version |

Everything else in the file is documentation of intent. In particular **both** `version_pattern` keys —
`upstream.version_pattern` and `addon.version_pattern` — are read by no code in this repository. The single
`version_pattern` reader is `internal/update-base-image.py:56`, and it reads a regex out of
`internal/base-image-config.yaml` for the unrelated base-image workflow.

The add-on versioning behaviour is therefore unconditional: the add-on version follows upstream, with the `config.yaml`
subpatch reset to `-0`. All four configured add-ons record `version_pattern: "sync"` under `addon:`, which matches that
behaviour; recording the `auto` value instead would change nothing, because nothing reads the key.

`version_strip` is the key that actually does work. The three shapes in use:

| Value         | Upstream tag       | Resulting version |
| ------------- | ------------------ | ----------------- |
| `^v`          | `v5.36.0`          | `5.36.0`          |
| `^version/`   | `version/2026.8.1` | `2026.8.1`        |
| `^meridian-v` | `meridian-v1.62.7` | `1.62.7`          |

## 🏗️ Adding a New Add-on

1. **Create add-on directory:**

   ```text
   my-new-addon/
   ├── config.yaml
   ├── build.yaml
   ├── Dockerfile
   ├── run.sh
   └── .upstream.yaml
   ```

2. **Configure `.upstream.yaml`:**

   ```yaml
   upstream:
     repository: "author/my-project"
     version_strip: "^v"
   ```

3. **Add a build workflow.** Create `.github/workflows/build-<addon>.yml` alongside the existing callers. Discovery
   alone is not enough: without that file the dispatch step skips the add-on with a warning and no image is ever built,
   even though the version bump lands on `main`.

4. **Done.** The next daily run picks the directory up — no workflow edit required.

## 📊 Monitoring & Status

Two places carry the whole story:

- **The `Auto Update` workflow runs.** The run list shows when add-ons were last checked; the job log shows one
  `INFO: checking <addon>` line per add-on, the version comparison, and any `ERROR:` line. A red run means at least one
  add-on failed or a build dispatch failed.
- **The commit history on `main`.** Every successful update is one commit with the subject
  `chore(<addon>): update to <version>`, touching only that add-on's three version files plus its `CHANGELOG.md`.

## 🔧 Advanced Configuration

### Adjust Schedule

The configured schedule is a single daily cron (`auto-update.yml:4-5`):

```yaml
schedule:
  - cron: "0 6 * * *" # Daily at 6:00 UTC
```

Other expressions are possible — `0 */12 * * *` for every twelve hours, `0 12 * * 1` for Mondays at 12:00 UTC — but they
are alternatives, not active configuration.

### Webhook Integration

`auto-update.yml` sends no webhook itself. The Home Assistant notification is sent by the build workflows: the reusable
`_build-template.yml` calls `.github/scripts/notify-ha.sh`, which is documented in `docs/WEBHOOK_SETUP.md`. Because the
dispatch step now makes those builds fire for automated bumps too, an automated update does reach that notification
path.

## ✅ Benefits

- **Discovery is automatic.** Any directory containing a `.upstream.yaml` is picked up by the next run; the workflow
  never has to be edited to add or remove an add-on.
- **An unreachable upstream or a failing version script does not stop the other add-ons.** Those two failures set
  `ERRORS=1` and `continue`, and the job still fails at the end. Any other command failing aborts the step under
  `set -e` — see the error-handling section above.
- **Every change is one reviewable commit.** Each update is a single commit on `main` scoped to one add-on, so the
  commit log on `main` is the audit trail.
- **The builds actually run.** The explicit dispatch closes the gap between a version bump landing on `main` and the
  matching image existing on ghcr.io.
