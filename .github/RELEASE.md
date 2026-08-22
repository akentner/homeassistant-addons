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

Every per-addon build workflow (`build-<addon>.yml`) triggers on:

- `push` to `main` with changes under `<addon>/**`, AND
- `push` of any tag matching `<addon>/v*`

so each release is built exactly once, regardless of whether it was triggered by a commit or by a manual tag push.

## Standard release flow

1. **Bump the 3-file version set and push the tag** with one command:

   ```bash
   make release ADDON=authentik VERSION=2026.8.0
   ```

   Internally this invokes `scripts/update-version.py`, which:

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

   The `scripts/check-version-tags.sh` pre-push hook verifies the `<addon>/v<version>` tag already exists locally or on
   origin before letting the branch push through.

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

This bypasses `update-version.py` but still satisfies the pre-push hook (`scripts/check-version-tags.sh`) as long as the
subpatch in `config.yaml` matches the tag suffix.

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
   `config.yaml`.

## Auto-update path

The daily `auto-update.yml` workflow calls the same `scripts/update-version.py` for every add-on with a
`.upstream.yaml`. From the perspective of this document, that path is identical to a manual `make release` — only the
trigger differs.
