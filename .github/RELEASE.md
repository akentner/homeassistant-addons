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

A single workflow, `.github/workflows/build.yml`, builds every add-on in this repository. It triggers on a `push` to
`main` that touches `**/config.*`, `**/build.*` or `**/Dockerfile`, and derives the add-on list, the architecture legs,
the display name and the description from each add-on's own `config.yaml` and `build.yaml` — so nothing about an add-on
is configured in CI, and CI cannot drift from what the add-on store advertises.

| Add-on            | Supervisor image source |
| ----------------- | ----------------------- |
| authentik         | local build             |
| coding-assistants | ghcr pull               |
| gatus             | ghcr pull               |
| iac-runner        | local build             |
| markdown-renderer | ghcr pull               |
| meridian          | ghcr pull               |
| network-tools     | ghcr pull               |
| phone-logger      | ghcr pull               |
| terraform-bridge  | ghcr pull               |

The `Supervisor image source` column reports whether that add-on's `config.yaml` declares a top-level `image:` key:
`ghcr pull` means it does, so the Supervisor fetches the prebuilt image from ghcr.io; `local build` means it does not,
so the Supervisor builds the add-on's `Dockerfile` itself. That axis says nothing about how or when the image is built;
it is driven solely by the presence of that one key.

### Tags do not trigger builds

Pushing an `<addon>/v*` tag builds nothing at all. `build.yml` carries no `tags:` trigger, and the per-caller `tags:`
blocks that used to carry one were deleted along with the callers. A single shared `*/v*` pattern was considered and
rejected, for four reasons in descending order of weight:

1. **It would produce green no-op runs.** `build.yml` derives its add-on set by diffing `github.event.before` against
   `github.sha`. On a newly created tag ref `github.event.before` is all zeros, so the derivation falls back to a
   single-commit diff of the commit the tag points at — which, in the flow documented below, is the commit taken
   _before_ the version files were changed. The run would report success and build nothing. A green no-op is strictly
   worse than no trigger at all, because it looks like a build happened.
2. **Making it work would need a second derivation path** — parsing the add-on name out of `GITHUB_REF_NAME` — that is,
   new untested code in the one file whose failure now breaks every add-on's build at once.
3. **The trigger it would preserve was already wrong.** The release procedure creates the tag before it commits the
   version files, so a tag-triggered build checks out the pre-bump tree and republishes the previous image. See
   `### What a tag guarantees` below for the measured rate; across the three add-ons whose tag trigger was still live it
   was 1 of 8.
4. **The double build disappears.** `iac-runner`, `network-tools` and `terraform-bridge` used to build twice per release
   — once via `paths:`, once via `tags:` — for no benefit.

The tag is now purely a release marker. `internal/check-version-tags.sh` still reports a version bump that reaches
`main` without one, and `<addon>/v<version>` is still what a GitHub Release page hangs off. The image is published by
the bump commit's own `build.yml` run, by the bump workflows' `internal/dispatch-builds.sh` dispatch, or by an explicit
`workflow_dispatch` — see `### Rebuilding on demand` and `## Auto-update path`.

### Why the split

History, kept because it is the reason the tags exist at all. Two commits on `main` hold the rationale, quoted from
their commit messages rather than paraphrased:

- `287c79f` (`ci(build): temporarily disable tag-trigger in per-addon workflows`) disabled the tag trigger in all seven.
  After the historical tag migration, origin held 24 `<addon>/v<version>` tags pointing at commits that were no longer
  the source of truth for their add-on directory. Re-enabling tag pushes unconditionally would have re-fired a build for
  every one of those 24 tags — roughly 30 minutes of runner time rebuilding images that already existed, and overwriting
  the ghcr.io images the HA Supervisor was serving.
- `60e7835` (`fix(network-tools): ship mdns_scan.py … ci(build-network-tools): re-enable tag-trigger`) re-enabled the
  tag trigger for network-tools only, which had just two tags (`v0.4.0`, `v0.2.3-1`) and a much smaller blast radius.

Both bullets are about CI triggers and nothing else. Neither is about the pull-versus-local-build split; that axis is
the `Supervisor image source` column above, driven solely by the presence of a top-level `image:` key in `config.yaml`.

### What this means operationally

The build is fired by the **bump commit**, never by the tag. When a human pushes step 2 of the release flow below
(committing and pushing `config.yaml` / `build.yaml` / `README.md` to `main`), that push is what fires `build.yml`, via
its manifest-path filter.

That scoping is load-bearing. A push made by a GitHub Actions workflow with the default `GITHUB_TOKEN` creates no
workflow runs at all, so the `paths:` filter never fires for an automated version bump and the automated path has to ask
for its builds explicitly. See `## Auto-update path` for how it does that.

What skipping step 2 actually costs depends on the image source:

- **Add-ons whose `config.yaml` declares a top-level `image:` key** are pulled by the Supervisor: coding-assistants,
  gatus, markdown-renderer, meridian, network-tools, phone-logger and terraform-bridge. For these, skipping step 2
  leaves `config.yaml` off `main`, so the store keeps advertising the old version and nothing breaks yet — what it
  leaves behind is a version that was never built. The ghcr.io 404 the versioning docs warn about arrives when that bump
  commit later lands with no build behind it: the manifest then advertises a version whose image tag was never
  published, and every install and update of that add-on fails on the pull.
- **`authentik` and `iac-runner` declare no `image:` key**, so the Supervisor builds them locally from their
  `Dockerfile` and a missing ghcr tag cannot produce a pull 404 for them at all. Their failure mode is a local build
  against whatever `main` currently holds: skip step 2 and the add-on is built from un-bumped source while its tag
  claims the new version.

There is exactly one build per bump now, and it reads its version out of the ref it checks out: both
`build.yaml:args.VERSION` (`_build-template.yml:76`) and `config.yaml:version` (`_build-template.yml:80`), and it is
`config.yaml:version` that becomes the published OCI image tag (`_build-template.yml:176`). The bump commit on `main` is
the ref that carries the new version; a tag cut before that commit does not (see `### What a tag guarantees` below),
which is one of the reasons tags no longer trigger anything.

### Rebuilding on demand

To rebuild an add-on's image without changing a file:

```bash
gh workflow run build.yml -f addons=network-tools        # one add-on
gh workflow run build.yml -f addons=gatus,meridian       # several
gh workflow run build.yml                                # every add-on
internal/dispatch-builds.sh network-tools                # local equivalent
```

An **empty** `addons` input builds every add-on, so omit it only when that is what you want.
`internal/dispatch-builds.sh` is the same path the bump workflows take: it issues exactly one dispatch naming every
add-on it was given, and `DRY_RUN=1` prints the command instead of running it.

### What a tag guarantees

The one-tag-per-release rule at the top of this section describes the manual paths only. Two automated paths ship
version bumps with no tag at all:

- `.github/workflows/base-image-update.yml` commits and pushes its own bumps (`base-image-update.yml:94-95` and `:112`)
  but never tags one: `internal/update-base-image.py` performs no git operations at all, and no revision of either file
  has ever contained `git tag`.
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

Measured 2026-09-09 and re-measured 2026-09-10: 15 of the 42 `<addon>/v*` tags in this repository point at a tree whose
`build.yaml` `args.VERSION` is an older version than the tag names. The other 27 agree with their tree. Two tags were
cut by hand between the two measurements, so the total moved while the mismatch count did not. Three of the fifteen:

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

   The Makefile then runs `make validate-versions` (`Makefile:201-203`). Note the ordering: `update-version.py` has
   already created and pushed the tag by the time validation runs, so a broken 3-file set is only reported after the
   fact — this step cannot stop a bad tag from reaching `origin`. The control that catches the consequence is
   `.github/workflows/verify-image-availability.yml`, which re-checks four times daily, with no registry credential,
   that every version a `config.yaml` advertises is anonymously pullable from ghcr.io.

2. **Commit and push the version files** (config.yaml / build.yaml / README.md are not auto-committed by the script):

   ```bash
   git add authentik/config.yaml authentik/build.yaml authentik/README.md
   git commit -m "chore(authentik): update to 2026.8.0"
   git push origin main
   ```

   The `internal/check-version-tags.sh` pre-push hook reports every add-on whose bumped `config.yaml` version is about
   to reach `main` with no matching `<addon>/v<version>` tag locally or on origin. Since `2ba51a2` it is **advisory only
   — it never fails the push**: the tag does not cause the build (`internal/dispatch-builds.sh` does, via
   `workflow_dispatch`), and a release marker must not block a push. Add-ons on the `LOCAL_BUILD_ADDONS` allowlist in
   that script are skipped entirely — they are built locally by the Supervisor and never pulled from ghcr.io, so no
   release tag is expected. The allowlist now holds exactly one add-on, `iac-runner`. That array is the source of truth
   for the current membership — read it, do not trust this sentence, when the membership matters.

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

This bypasses `update-version.py`. The pre-push hook (`internal/check-version-tags.sh`) reports a missing tag only when
the subpatch in `config.yaml` has no matching tag suffix, and it is advisory either way — it never blocks the push.

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

   The pre-push hook will report, but not block, a branch push whose modified `config.yaml` has no tag named
   `<addon>/v<version>`; it says nothing at all for add-ons on the `LOCAL_BUILD_ADDONS` allowlist in
   `internal/check-version-tags.sh` — now a single entry, `iac-runner`, which the Supervisor builds locally and which
   therefore needs no release tag. The array in that script stays the source of truth for the current membership.

## Auto-update path

The daily `.github/workflows/auto-update.yml` workflow — workflow name `Auto Update`, schedule `0 6 * * *` — calls the
same `internal/update-version.py` for every add-on that has a `.upstream.yaml`. Today that is four add-ons: `authentik`,
`gatus`, `meridian` and `phone-logger`. From the perspective of this document the path is **not** interchangeable with a
manual `make release`, for two reasons.

**1. Its own push cannot start a build, so it asks for the builds explicitly.** The workflow commits and pushes to
`main` with the default `GITHUB_TOKEN`, and GitHub creates no workflow runs for an event produced by that token — so
`build.yml`'s `paths:` filter never fires for an automated bump. `workflow_dispatch` is the documented exception: a
dispatch created with `GITHUB_TOKEN` does run (<https://docs.github.com/actions/using-workflows/triggering-a-workflow>).
The workflow therefore runs `internal/dispatch-builds.sh` immediately after its `git push` (`auto-update.yml:166-167`),
and requests the `actions: write` permission to do so (`auto-update.yml:49`). That script derives the changed add-on
directories from `git diff --name-only "$BASE_SHA"..HEAD` and issues exactly **one** dispatch —
`gh workflow run build.yml --ref <ref> -f addons=<comma list>` — naming every changed add-on in one call. Two of its
error semantics matter when reading a run log:

- A candidate directory that is not an add-on directory — no `config.yaml` + `build.yaml` + `Dockerfile` triple — is
  reported as a warning and does **not** fail the run. This is the common case, because a bump commit also touches
  non-add-on paths.
- A dispatch that fails makes the job exit non-zero. The bump is already on `main` by then, so a green run would hide a
  manifest advertising an image that was never built.

**2. It creates no tag.** The call passes `--no-tag` (`auto-update.yml:123`). See `## Tag schema` — and in particular
`### What a tag guarantees` — for what a `<addon>/v<version>` tag does and does not prove.

For the discovery loop, the per-add-on error handling and the `.upstream.yaml` keys the workflow actually reads, see
`docs/AUTO_UPDATE_GUIDE.md`.
