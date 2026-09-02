# Version Update Tool

Single source of truth for the `internal/update-version.py` script and its conventions. If you find yourself reaching
for `sed` to edit a version anywhere in an addon's `config.yaml`, `build.yaml`, or `README.md` — stop, use the tool.

## What the tool does

The script keeps three files in sync and creates the matching git tag:

| File          | Field updated            | Example              |
| ------------- | ------------------------ | -------------------- |
| `config.yaml` | top-level `version:`     | `version: "1.0.0-2"` |
| `build.yaml`  | nested `args.VERSION`    | `VERSION: "1.0.0"`   |
| `README.md`   | shield badge + tree link | `v1.0.0`             |

After updating files, it **creates and pushes the git tag `<addon>/v<config_version>`** (subpatch-suffixed) by default.
See [Git tag format](#git-tag-format) below for why.

## Choosing the right `VERSION=` value

The format of the input determines the bump category. Pick wrong and the tool will silently do the wrong thing:

- `X.Y.Z` — **resets subpatch to `-0`** (e.g. `1.0.0-2` → `1.0.0-0`). Use for an upstream binary/library update, a new
  feature, or breaking change (SemVer).
- `X.Y.Z-N` — **preserves the existing subpatch** (e.g. `1.0.0-1` → `1.0.0-2`). Use for a local-only change
  (Dockerfile-only, ConfigFlow-only, DOCS-only).
- `X.Y.Z-{alpha|beta|rc}N` — pre-release. `build.yaml` carries the matching suffix too.

⚠️ **Critical:** passing `VERSION=1.0.0` on an addon whose `config.yaml` is already `1.0.0-2` will **silently reset the
subpatch to `-0`**. If you want to preserve an existing subpatch (the common case for local-only fixes after a SemVer
release), always pass the full `X.Y.Z-N`.

## Concrete examples

```bash
# Upstream release / SemVer bump: resets subpatch to -0
make update-version ADDON=<addon-name> VERSION=1.7.2

# Local-only fix / subpatch bump: pass the full X.Y.Z-N — preserves the subpatch
make update-version ADDON=<addon-name> VERSION=1.0.0-2

# Subpatch bump without touching the git tag (e.g. iterating locally; tag is pushed later)
make update-version ADDON=<addon-name> VERSION=1.0.0-2 NO_TAG=yes NO_PUSH=yes

# With GitHub release verification (head-checks that v1.7.2 exists on GitHub first)
make update-version ADDON=<addon-name> VERSION=1.7.2 CHECK_RELEASE=yes

# Skip tag creation entirely (e.g. emergency patch; tag must be created/pushed manually)
make update-version ADDON=<addon-name> VERSION=1.7.2 NO_TAG=yes

# Dry-run (shows what would change without modifying files)
# IMPORTANT: --dry-run MUST go to the script directly. `make ... --dry-run` is broken
# because make intercepts --dry-run and exits without invoking the script.
./internal/update-version.py <addon-name> 1.7.2 --dry-run
#                                                     ^^^^^^^^^^ pass to the script, NOT to make
```

## Git tag format

Tag format is `<addon>/v<config_version>` — subpatch is included so the git tag uniquely identifies the release,
matching the OCI image tag (`CONFIG_VERSION`) that the build workflow publishes. See
`.github/workflows/_build-template.yml:75-78`.

Examples:

- `coding-assistants/v1.0.0-2` — subpatch-suffixed (current standard)
- `coding-assistants/v1.0.0` — legacy format, still accepted by the pre-push hook for backwards compatibility

The tag is created and pushed to `origin` by default. If you skip with `NO_TAG=yes` or `NO_PUSH=yes`, you must create
and push the tag later — without it, the HA supervisor refresh sees the new version in the store but the image at
`ghcr.io` does not exist → 404 → "Unknown error, see supervisor logs".

## Pre-push hook

A pre-push hook (`internal/check-version-tags.sh`, installed by `make init`) verifies that any addon whose
`config.yaml`/`build.yaml` is being pushed has a matching `<addon>/v<config_version>` tag locally or on origin. For
backwards compatibility the hook also accepts the legacy `<addon>/v<build_version>` format (no subpatch) so older addons
don't break their pushes during the transition. Bypass with `git push --no-verify` only in emergencies.

Tag lookup chain (in order):

1. Local `refs/tags/<tag>` (after `git fetch --tags`)
2. Local `refs/remotes/origin/<tag>`
3. Network fallback: `git ls-remote origin refs/tags/<tag>`

The script's `create_and_push_tag` uses the same chain and skips creation (never force-pushes) if the tag exists
anywhere. Force-push would re-associate an existing SemVer tag with a subpatch commit and publish the wrong image.

## No-op behaviour

If `config.yaml` is already at the target version, the script is a no-op (prints warnings, exits 0). This is the
canonical way to **confirm** a subpatch bump — the manual-editing instruction is deprecated; prefer the tool even for
subpatch-only changes so the bump is recorded the same way as a SemVer bump.

## Cross-artifact bumping (terraform-bridge)

When bumping `terraform-bridge`, the script also touches `terraform-provider-homeassistant/build.yaml`'s `VERSION` field
with the same `X.Y.Z`. The Provider has no `config.yaml`, no `README.md`, and no git tag of its own — it's a co-located
Go module, not a separately-released add-on. Both Bridge and Provider share one release cycle.

## Worked example — subpatch bump (the common case after a SemVer release)

```bash
# Edit code in coding-assistants/ (Dockerfile, run.sh, DOCS.md, …)

# Confirm the bump without touching the tag yet
make update-version ADDON=coding-assistants VERSION=1.0.0-2 NO_TAG=yes NO_PUSH=yes

# When ready to ship:
./internal/update-version.py coding-assistants 1.0.0-2
# → updates files (no-op since already at target)
# → creates local tag coding-assistants/v1.0.0-2
# → pushes tag to origin

# Build workflow fires on the tag push (or on push to main with files in
# coding-assistants/**), publishes the image at ghcr.io/.../1.0.0-2.
```
