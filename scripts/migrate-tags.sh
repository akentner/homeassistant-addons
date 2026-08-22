#!/usr/bin/env bash
# One-off migration: rename legacy 'vX.Y.Z' tags to the new '<addon>/vX.Y.Z' schema.
#
# Usage:
#   ./scripts/migrate-tags.sh --dry-run       # print what would change, no writes
#   ./scripts/migrate-tags.sh --apply-local   # rename + delete locally only
#   ./scripts/migrate-tags.sh --apply-origin  # also push deletions to origin
#
# Pre-requisites:
#   - git fetch --tags origin  (run beforehand so the mapping table is complete)
#   - git pull --rebase origin main  (so we operate on the latest main tip)
#   - HA-Store-Cache darf NICHT auf Tags zeigen, die wir gleich löschen
#     (siehe .github/RELEASE.md, Abschnitt 'Alte Tags')
#
# This script is INTENTIONALLY a one-shot, not a make target: tags are
# history-rewriting metadata and the migration is destructive. Re-run is
# safe (already-migrated tags are detected and skipped), but the script
# will refuse to operate on a working tree with uncommitted changes.

set -euo pipefail

DRY_RUN=1
APPLY_LOCAL=0
APPLY_ORIGIN=0

for arg in "$@"; do
    case "$arg" in
        --dry-run)       DRY_RUN=1 ;;
        --apply-local)   DRY_RUN=0; APPLY_LOCAL=1 ;;
        --apply-origin)  DRY_RUN=0; APPLY_LOCAL=1; APPLY_ORIGIN=1 ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        *)
            echo "❌ unknown argument: $arg" >&2
            sed -n '2,18p' "$0" >&2
            exit 2
            ;;
    esac
done

if [[ -n "$(git status --porcelain)" ]]; then
    echo "❌ Working tree is dirty — commit or stash before migrating tags." >&2
    exit 1
fi

# Mapping table — keep in sync with .github/RELEASE.md and the per-addon
# config.yaml/build.yaml. Each row: "<legacy_tag>|<new_tag>".
#
# A trailing "DEL" entry means the legacy tag should be deleted (phantom
# tag pointing at a docs-only or non-addon commit; no release image ever
# referenced it).
MAPPING=(
    # --- authentik ---
    "v2026.8.0|authentik/v2026.8.0"

    # --- coding-assistants ---
    "v1.0.0-alpha41|coding-assistants/v1.0.0-alpha41"
    "v1.0.0-alpha42|coding-assistants/v1.0.0-alpha42"
    "v1.0.0-alpha43|coding-assistants/v1.0.0-alpha43"
    "v1.0.0-alpha44|coding-assistants/v1.0.0-alpha44"
    "v1.0.0-alpha45|coding-assistants/v1.0.0-alpha45"
    # v1.62.7 is the race-condition artefact from auto-update.yml: the tag
    # message claims 'meridian: 1.62.7' but the commit it points at is a
    # coding-assistants bump. Re-tag under the real addon:
    "v1.62.7|coding-assistants/v1.0.0-alpha45"

    # --- gatus (no legacy tags existed — nothing to migrate here) ---

    # --- markdown-renderer ---
    "markdown-renderer/1.1.0-21|markdown-renderer/v1.1.0-21"
    "v1.1.0-21|markdown-renderer/v1.1.0-21"

    # --- meridian ---
    "v1.58.1|meridian/v1.58.1"
    "v1.58.2|meridian/v1.58.2"
    "v1.58.3|meridian/v1.58.3"
    "v1.59.0|meridian/v1.59.0"
    "v1.60.0|meridian/v1.60.0"
    "v1.61.0|meridian/v1.61.0"
    "v1.62.1|meridian/v1.62.1"
    "v1.62.3|meridian/v1.62.3"
    "v1.62.5|meridian/v1.62.5"
    # v1.62.6 is the race-condition artefact: tag claims 'meridian: 1.62.6'
    # but points at an authentik commit. Re-tag under authentik — its
    # config.yaml has been at 2026.8.0 since v2026.8.0 was tagged.
    "v1.62.6|authentik/v2026.8.0"
    # (v1.62.7 already listed under coding-assistants above.)

    # --- network-tools ---
    "v0.2.3-1|network-tools/v0.2.3-1"
    "v0.4.0|network-tools/v0.4.0"

    # --- phone-logger ---
    "v1.0.6|phone-logger/v1.0.6"
    "v1.0.7|phone-logger/v1.0.7"
    "v1.0.7-1|phone-logger/v1.0.7-1"
    "v1.0.8|phone-logger/v1.0.8"
    "v1.0.8-1|phone-logger/v1.0.8-1"

    # --- phantom tags: pointing at non-addon commits, delete ---
    "v1.0|DEL"
    "v1.57.1|DEL"
)

echo "============================================================"
echo " Tag migration plan"
echo "============================================================"
echo ""
printf '  %-40s  ->  %s\n' "LEGACY" "NEW"
echo "  ---------------------------------------------  ---------------------------------------------"
for row in "${MAPPING[@]}"; do
    legacy="${row%|*}"
    new="${row#*|}"
    if [[ "$new" == "DEL" ]]; then
        printf '  %-40s  ->  [DELETE]\n' "$legacy"
    else
        printf '  %-40s  ->  %s\n' "$legacy" "$new"
    fi
done
echo ""

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run — no changes. Use --apply-local (or --apply-origin) to execute."
    echo ""
    echo "Sanity check: legacy tag -> commit -> new tag (would-be) targets:"
    for row in "${MAPPING[@]}"; do
        legacy="${row%|*}"
        new="${row#*|}"
        if ! git rev-parse "$legacy" >/dev/null 2>&1; then
            printf '  ⚠️  %s does not exist locally — will be skipped\n' "$legacy"
            continue
        fi
        sha=$(git rev-parse --short "$legacy")
        if [[ "$new" == "DEL" ]]; then
            subject=$(git log -1 --format='%s' "$legacy")
            printf '  %s  %s  %s  [would delete]\n' "$legacy" "$sha" "$subject"
            continue
        fi
        if git rev-parse "$new" >/dev/null 2>&1; then
            existing_sha=$(git rev-parse --short "$new")
            if [[ "$existing_sha" == "$sha" ]]; then
                printf '  %s  %s  (new tag %s already points here — skip)\n' "$legacy" "$sha" "$new"
            else
                printf '  ❌ %s  %s  but new tag %s already exists pointing at %s — REFUSE\n' \
                    "$legacy" "$sha" "$new" "$existing_sha"
                exit 1
            fi
        else
            subject=$(git log -1 --format='%s' "$legacy")
            printf '  %s  %s  %s  [would retag -> %s]\n' "$legacy" "$sha" "$subject" "$new"
        fi
    done
    exit 0
fi

echo "Applying locally (use --apply-origin to also push deletions)..."
echo ""

for row in "${MAPPING[@]}"; do
    legacy="${row%|*}"
    new="${row#*|}"
    if ! git rev-parse "$legacy" >/dev/null 2>&1; then
        echo "  skip: $legacy does not exist locally"
        continue
    fi
    if [[ "$new" == "DEL" ]]; then
        echo "  delete: $legacy"
        git tag -d "$legacy"
        continue
    fi
    if git rev-parse "$new" >/dev/null 2>&1; then
        echo "  skip: $new already exists locally"
        continue
    fi
    echo "  retag: $legacy -> $new"
    git tag "$new" "$legacy"
    git tag -d "$legacy"
done

echo ""
echo "Local tag state after migration:"
git tag -l | sort

if [[ "$APPLY_ORIGIN" -eq 1 ]]; then
    echo ""
    echo "Pushing new tags and deleting legacy tags on origin..."
    echo "  (pushes go to refs/tags/<name>; deletions are git push origin :refs/tags/<name>)"
    echo ""

    # Collect new tags (all tags except phantom deletions)
    new_tags=()
    delete_tags=()
    for row in "${MAPPING[@]}"; do
        legacy="${row%|*}"
        new="${row#*|}"
        if [[ "$new" == "DEL" ]]; then
            delete_tags+=("$legacy")
        else
            new_tags+=("$new")
        fi
    done

    if [[ ${#new_tags[@]} -gt 0 ]]; then
        echo "  push: ${new_tags[*]}"
        git push origin "${new_tags[@]}"
    fi
    if [[ ${#delete_tags[@]} -gt 0 ]]; then
        echo "  delete: ${delete_tags[*]}"
        git push origin "${delete_tags[@]/#/:refs/tags/}"
    fi
    echo ""
    echo "✅ Migration complete on origin."
else
    echo ""
    echo "Local migration complete. Review with 'git tag -l', then push manually:"
    echo "  git push origin --tags"
    echo "  git push origin :refs/tags/v1.0 :refs/tags/v1.57.1"
fi
