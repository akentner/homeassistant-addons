---
name: update-version
description: Bump an add-on's version in this repo via `make update-version` (3-file sync of config.yaml, build.yaml, README.md). Use for upstream version bumps and for add-on-only fixes (subpatch -N increments).
---

# update-version

Never edit version strings by hand. `make update-version` (wrapper for `internal/update-version.py`) keeps
`config.yaml`, `build.yaml` and `README.md` in sync. Pre-commit runs `internal/validate-versions.sh`.

## Pick the VERSION value

| Situation                        | VERSION          | config.yaml | build.yaml / README |
| -------------------------------- | ---------------- | ----------- | ------------------- |
| New upstream release             | `X.Y.Z`          | `X.Y.Z-0`   | `X.Y.Z`             |
| Add-on-only fix (same upstream)  | `X.Y.Z-N`        | `X.Y.Z-N`   | unchanged `X.Y.Z`   |
| Pre-release                      | `X.Y.Z-rcN` etc. | as given    | as given            |

Passing plain `X.Y.Z` for an unchanged upstream **resets the subpatch to `-0`** (a downgrade). For add-on-only
fixes read the current value (`yq eval --unsafe '.version' <addon>/config.yaml`) and pass `X.Y.Z-(N+1)`.

## Steps

1. Confirm the add-on name and target version with the user if unclear (version bumps are a critical task).
2. Dry run, no tag:
   ```bash
   make update-version ADDON=<addon> VERSION=<version> NO_TAG=yes   # or:
   ./internal/update-version.py <addon> <version> --dry-run --no-tag
   ```
3. Apply. By default the script **creates and pushes** the tag `<addon>/v<version>` to origin. That is outward-facing:
   use `NO_TAG=yes` (no tag) or `NO_PUSH=yes` (local tag only) unless the user asked for the tag.
   Optional: `CHECK_RELEASE=yes` verifies the upstream GitHub release exists.
4. Verify: `make validate-versions`.
5. Commit only the version files, e.g. `fix(<addon>): bump to <version>`. No `Co-Authored-By` / AI-attribution lines.

## Notes

- Add-on-only bumps (`-N`) are pushed to main; the build workflow triggers on the commit paths, not on the tag.
- Dockerfile package/base-image changes require a local `docker build` before committing.
