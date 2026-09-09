# Release Workflow

This document describes how to cut a release for any add-on in this repository.

For background on the 3-file versioning scheme (`config.yaml` / `build.yaml` / README badge) see `docs/DEVELOPMENT.md`.
For how the daily auto-update works see `docs/AUTO_UPDATE_GUIDE.md`.

## Tag schema

Every release cut through one of the two manual paths below — step 1 of `## Standard release flow`, or `## Patch flow` —
ships as one git tag named:

```text
<addon-name>/v<version>
```

Examples:

- `authentik/v2026.8.0`
- `coding-assistants/v1.0.0-alpha45`
- `gatus/v5.36.0`
- `markdown-renderer/v1.1.0-23`
- `meridian/v1.62.7`
- `network-tools/v0.4.0`
- `phone-logger/v1.0.6-0`

`<addon-name>` is exactly the directory name under the repo root. `<version>` is the value of `args.VERSION` in
`build.yaml`, with no further prefix — the `v` sits between the directory and the version by convention, not in the
version itself. CalVer is supported (`authentik/v2026.8.0`); pre-release and subpatch suffixes are preserved
(`v1.0.0-alpha45`, `v1.0.6-0`).

Every per-addon build workflow (`build-<addon>.yml`) triggers on a `push` to `main` with changes under `<addon>/**`. A
second trigger on `push` of a `<addon>/v*` tag exists in each file but is **commented out for all add-ons except
network-tools, terraform-bridge and iac-runner**:

| Add-on            | `paths:` on `main` | `<addon>/v*` tag | Supervisor image source |
| ----------------- | ------------------ | ---------------- | ----------------------- |
| authentik         | active             | disabled         | local build             |
| coding-assistants | active             | disabled         | ghcr pull               |
| gatus             | active             | disabled         | ghcr pull               |
| iac-runner        | active             | **active**       | local build             |
| markdown-renderer | active             | disabled         | ghcr pull               |
| meridian          | active             | disabled         | ghcr pull               |
| network-tools     | active             | **active**       | ghcr pull               |
| phone-logger      | active             | disabled         | ghcr pull               |
| terraform-bridge  | active             | **active**       | ghcr pull               |

The `Supervisor image source` column reports whether that add-on's `config.yaml` declares a top-level `image:` key:
`ghcr pull` means it does, so the Supervisor fetches the prebuilt image from ghcr.io; `local build` means it does not,
so the Supervisor builds the add-on's `Dockerfile` itself. This axis is independent of the tag-trigger split in the two
columns to its left — an add-on can have its tag trigger disabled and still be pulled, or enabled and still be built
locally.

This split is deliberate. In the six callers whose tag trigger is disabled, the `tags:` block holds the in-file comment
`# tag-trigger temporarily disabled (see .github/RELEASE.md)` — this section is what that comment resolves to. The three
add-ons with an active `tags:` block carry no such comment, so the comment is a marker of the disabled state rather than
a fixture of every caller.

### Why the split

Two commits, both on `main`, hold the rationale. They are quoted from their commit messages, not paraphrased:

- `287c79f` (`ci(build): temporarily disable tag-trigger in per-addon workflows`) disabled the tag trigger in all seven.
  After the historical tag migration, origin held 24 `<addon>/v<version>` tags pointing at commits that were no longer
  the source of truth for their add-on directory. Re-enabling tag pushes unconditionally would have re-fired a build for
  every one of those 24 tags — roughly 30 minutes of runner time rebuilding images that already existed, and overwriting
  the ghcr.io images the HA Supervisor was serving, possibly with different content if any Dockerfile argument had
  changed since.
- `60e7835` (`fix(network-tools): ship mdns_scan.py … ci(build-network-tools): re-enable tag-trigger`) re-enabled the
  tag trigger for network-tools only. That add-on had just two tags (`v0.4.0`, `v0.2.3-1`) and `v0.4.0` already pointed
  at near-current source, so the contained risk was much smaller than for the other six.

Both bullets are about CI triggers and nothing else. The tag-trigger split is a historical CI decision and must not be
read as the pull-versus-local-build split; that axis is the `Supervisor image source` column above, and it is driven
solely by the presence of a top-level `image:` key in `config.yaml`. Conflating the two axes is what made the
operational paragraph below assert one consequence for add-ons that do not share it.

### What this means operationally

For the six add-ons with the tag-trigger disabled, pushing the tag alone does **not** build an image. When a human
pushes step 2 of the release flow below (committing and pushing `config.yaml` / `build.yaml` / `README.md` to `main`),
that push is what fires the build, via the `paths:` filter.

That scoping is load-bearing. A push made by a GitHub Actions workflow with the default `GITHUB_TOKEN` creates no
workflow runs at all, so the `paths:` filter never fires for an automated version bump and the automated path has to ask
for its builds explicitly. See `## Auto-update path` for how it does that.

What skipping step 2 actually costs depends on the image source, not on the tag trigger:

- **Add-ons whose `config.yaml` declares a top-level `image:` key** are pulled by the Supervisor: coding-assistants,
  gatus, markdown-renderer, meridian, network-tools, phone-logger and terraform-bridge. For these, skipping step 2
  produces exactly the ghcr.io 404 that the versioning docs warn about, even when the tag exists on origin — the
  manifest advertises a version whose image tag was never published, and every install and update of that add-on fails
  on the pull.
- **`authentik` and `iac-runner` declare no `image:` key**, so the Supervisor builds them locally from their
  `Dockerfile` and a missing ghcr tag cannot produce a pull 404 for them at all. Their failure mode is a local build
  against whatever `main` currently holds: skip step 2 and the add-on is built from un-bumped source while its tag
  claims the new version.

`network-tools`, `terraform-bridge` and `iac-runner` are built twice when both the commit and the tag are pushed: once
by the `paths:` trigger and once by the active `tags:` trigger. Neither leg is authoritative for the version the tag
names — both read `build.yaml:args.VERSION` out of whatever ref they check out. Because the release procedure tags
before it commits (see `### What a tag guarantees` below), the tag's ref is the one that may still carry the older
version, which makes the tag-triggered leg the leg more likely to build stale content. The `paths:` leg on `main` is the
one that sees the bump.

### Re-enabling a tag trigger

To re-enable for an add-on:

1. Inspect `git ls-remote --tags origin <addon>/v\*` and check whether any tag points at a commit that is no longer the
   source of truth for `<addon>/**`. If yes, delete or move those tags first (rebuild cost compounds).
2. Edit `.github/workflows/build-<addon>.yml`: remove the leading `#` from the two commented lines in the `tags:` block.
3. Open a PR with the rationale and a roll-back plan if the rebuild would overwrite a published image unexpectedly.

The six callers carry the comment `# tag-trigger temporarily disabled (see .github/RELEASE.md)` for exactly this reason
— anyone reading the comment and following the pointer now lands on a real explanation.

### What a tag guarantees

The one-tag-per-release rule at the top of this section describes the manual paths only. Two automated paths ship
version bumps with no tag at all:

- `.github/workflows/base-image-update.yml` drives `internal/update-base-image.py`, which performs no git operations of
  any kind — it edits files and nothing else. That workflow has therefore never produced a tag.
- The daily `.github/workflows/auto-update.yml` passes `--no-tag` to `internal/update-version.py`
  (`auto-update.yml:123`), so an automated bump lands as a commit on `main` with no tag behind it. See
  `## Auto-update path`.

A `<addon>/v<version>` tag names an **intended** version. It does not prove that the tree it points at carries that
version. The mechanism is the ordering of the release procedure: `internal/update-version.py` tags `HEAD` (the
`--no-tag` guard at `internal/update-version.py:425` calls `create_and_push_tag`) and never commits the three files it
just edited — it prints a suggested `git add` / `git commit` for the operator instead
(`internal/update-version.py:443`). Step 1 of the release flow below therefore tags the pre-bump commit, and step 2
creates the bump commit afterwards. The `## Patch flow` snippet has the same ordering: `git tag` runs before the version
files are committed.

Measured on 2026-09-09: 15 of the 40 `<addon>/v*` tags in this repository point at a tree whose `build.yaml`
`args.VERSION` is an older version than the tag names. The other 25 agree with their tree. Three of the fifteen:

- `authentik/v2026.8.1` — the tree at that tag carries `2026.8.0`
- `meridian/v1.59.0` — the tree at that tag carries `1.58.3`
- `terraform-bridge/v0.2.0` — the tree at that tag carries `0.1.0`

`terraform-bridge` has no `.upstream.yaml`, so the daily auto-update never touches it and that tag was cut by hand. The
off-by-one is a defect in the documented manual procedure, not only in the bot.

Reproduce the count:

```bash
for tag in $(git tag -l '*/v*'); do
    addon=${tag%%/*}
    want=${tag#*/v}
    have=$(git show "$tag:$addon/build.yaml" | sed -n 's/^ *VERSION: *"\?\([^"]*\)"\?$/\1/p')
    case "$want" in "$have" | "$have"-*) ;; *) echo "MISMATCH $tag tree=$have" ;; esac
done
```

Reordering the release procedure so the commit precedes the tag is **not** done here. This section documents the defect;
it does not change `make release`.

## Standard release flow

1. **Bump the 3-file version set and push the tag** with one command:

   ```bash
   make release ADDON=authentik VERSION=2026.8.0
   ```

   Internally this invokes `internal/update-version.py`, which:

   - edits `authentik/config.yaml` → `version: "2026.8.0-0"`
   - edits `authentik/build.yaml` → `args.VERSION: "2026.8.0"`
   - edits the `vX.Y.Z` badge in `authentik/README.md`
   - creates the annotated tag `authentik/v2026.8.0`
   - pushes that tag to origin

   The Makefile then runs `make validate-versions` so a broken 3-file set fails the release before the tag reaches
   `origin`.

2. **Commit and push the version files** (config.yaml / build.yaml / README.md are not auto-committed by the script):

   ```bash
   git add authentik/config.yaml authentik/build.yaml authentik/README.md
   git commit -m "chore(authentik): update to 2026.8.0"
   git push origin main
   ```

   The `internal/check-version-tags.sh` pre-push hook verifies the `<addon>/v<version>` tag already exists locally or on
   origin before letting the branch push through. Add-ons on the `LOCAL_BUILD_ADDONS` allowlist in that script are
   exempt — they are built locally by the Supervisor and never pulled from ghcr.io, so no release tag is required. The
   allowlist now holds exactly one add-on, `iac-runner`. That array is the source of truth for the current membership —
   read it, do not trust this sentence, when the membership matters.

3. **Optional: GitHub Release page.** If you have the `gh` CLI and want the release notes rendered on the GitHub
   Releases UI:

   ```bash
   make release ADDON=authentik VERSION=2026.8.0 GITHUB_RELEASE=yes
   ```

   This invokes `gh release create authentik/v2026.8.0 --generate-notes` after the tag is pushed. If `gh` is not
   installed it prints the command for manual execution.

## Patch flow (subpatch bump without `make update-version`)

For local-only fixes that do not change the upstream-tracked version, just edit the subpatch directly:

```bash
# Edit config.yaml from 2026.8.0-0 to 2026.8.0-1, build.yaml stays at 2026.8.0
# Then:
git tag authentik/v2026.8.0-1
git push origin authentik/v2026.8.0-1
```

This bypasses `update-version.py` but still satisfies the pre-push hook (`internal/check-version-tags.sh`) as long as
the subpatch in `config.yaml` matches the tag suffix.

## Manual repair

If the tag and the 3-file set ever drift, the canonical fix order is:

1. Confirm `config.yaml` / `build.yaml` / README badge agree (see `docs/DEVELOPMENT.md` for the rules).
2. Recreate the tag locally on the matching commit:

   ```bash
   git tag -d authentik/v2026.8.0   # local
   git tag authentik/v2026.8.0 <commit-sha>
   git push origin :refs/tags/authentik/v2026.8.0   # delete on remote
   git push origin authentik/v2026.8.0              # re-create on remote
   ```

   The pre-push hook will refuse a branch push until a tag named `<addon>/v<version>` exists for every modified
   `config.yaml`, except for add-ons on the `LOCAL_BUILD_ADDONS` allowlist in `internal/check-version-tags.sh` — now a
   single entry, `iac-runner`, which the Supervisor builds locally and which therefore needs no release tag. The array
   in that script stays the source of truth for the current membership.

## Auto-update path

The daily `.github/workflows/auto-update.yml` workflow — workflow name `Auto Update`, schedule `0 6 * * *` — calls the
same `internal/update-version.py` for every add-on that has a `.upstream.yaml`. Today that is four add-ons: `authentik`,
`gatus`, `meridian` and `phone-logger`. From the perspective of this document the path is **not** interchangeable with a
manual `make release`, for two reasons.

**1. Its own push cannot start a build, so it asks for the builds explicitly.** The workflow commits and pushes to
`main` with the default `GITHUB_TOKEN`, and GitHub creates no workflow runs for an event produced by that token — so the
`paths:` filter in `.github/workflows/build-<addon>.yml` never fires for an automated bump. `workflow_dispatch` is the
documented exception: a dispatch created with `GITHUB_TOKEN` does run
(<https://docs.github.com/actions/using-workflows/triggering-a-workflow>). The workflow therefore runs
`internal/dispatch-builds.sh` immediately after its `git push` (`auto-update.yml:166-167`), and requests the
`actions: write` permission to do so (`auto-update.yml:49`). That script derives the changed add-on directories from
`git diff --name-only "$BASE_SHA"..HEAD` and issues one `gh workflow run build-<addon>.yml --ref <ref>` per add-on. Two
of its error semantics matter when reading a run log:

- A candidate directory with no `.github/workflows/build-<addon>.yml` is reported as a warning and does **not** fail the
  run. This is the common case, because a bump commit also touches non-add-on paths.
- A dispatch that fails makes the job exit non-zero. The bump is already on `main` by then, so a green run would hide a
  manifest advertising an image that was never built.

**2. It creates no tag.** The call passes `--no-tag` (`auto-update.yml:123`). See `## Tag schema` — and in particular
`### What a tag guarantees` — for what a `<addon>/v<version>` tag does and does not prove.

For the discovery loop, the per-add-on error handling and the `.upstream.yaml` keys the workflow actually reads, see
`docs/AUTO_UPDATE_GUIDE.md`.
