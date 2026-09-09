# Release Workflow

This document describes how to cut a release for any add-on in this repository.

For background on the 3-file versioning scheme (`config.yaml` / `build.yaml` / README badge) see `docs/DEVELOPMENT.md`.
For how the daily auto-update works see `docs/AUTO_UPDATE_GUIDE.md`.

## Tag schema

Every release ships as one git tag named:

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

This split is deliberate. The `tags:` block in each caller carries the in-file comment
`# tag-trigger temporarily disabled (see .github/RELEASE.md)` — this section is what that comment resolves to.

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

For the six add-ons with the tag-trigger disabled, pushing the tag alone does **not** build an image. Step 2 of the
release flow below (committing and pushing `config.yaml` / `build.yaml` / `README.md` to `main`) is what fires the
build, via the `paths:` filter.

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
by the `paths:` trigger and once by the active `tags:` trigger. The double-build is intentional — the tag-triggered leg
is the one that pulls `build.yaml:args.VERSION`, so it produces the canonical image for the tag.

### Re-enabling a tag trigger

To re-enable for an add-on:

1. Inspect `git ls-remote --tags origin <addon>/v\*` and check whether any tag points at a commit that is no longer the
   source of truth for `<addon>/**`. If yes, delete or move those tags first (rebuild cost compounds).
2. Edit `.github/workflows/build-<addon>.yml`: remove the leading `#` from the two commented lines in the `tags:` block.
3. Open a PR with the rationale and a roll-back plan if the rebuild would overwrite a published image unexpectedly.

The seven callers carry the comment `# tag-trigger temporarily disabled (see .github/RELEASE.md)` for exactly this
reason — anyone reading the comment and following the pointer now lands on a real explanation.

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

The daily `auto-update.yml` workflow calls the same `internal/update-version.py` for every add-on with a
`.upstream.yaml`. From the perspective of this document, that path is identical to a manual `make release` — only the
trigger differs.
