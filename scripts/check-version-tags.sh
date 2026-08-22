#!/usr/bin/env bash
# Pre-push hook for the per-addon build workflows (.github/workflows/build-<addon>.yml):
# every workflow also triggers on `git push` of an `<addon>/v*` tag, so a matching
# tag must exist locally or on origin for every config.yaml/build.yaml change that
# lands in main. Without a matching tag the HA supervisor refresh sees the new version
# in the store but the image at ghcr.io does not exist -> 404 -> "Unknown error".
# Install via ./scripts/setup-hooks.sh.

set -e

modified_addons=""

while IFS=' ' read -r local_ref local_sha remote_ref remote_sha; do
    [[ -n "$local_ref" ]] || continue
    [[ "$local_sha" == "0000000000000000000000000000000000000000" ]] && continue

    if [[ "$remote_sha" == "0000000000000000000000000000000000000000" ]]; then
        range="$local_sha^..$local_sha"
    elif git rev-list --count "$remote_sha..$local_sha" 2>/dev/null | grep -q '^0$'; then
        continue
    else
        range="$remote_sha..$local_sha"
    fi

    while IFS= read -r f; do
        [[ -n "$f" ]] || continue
        addon_dir=$(dirname "$f")
        if [[ -f "$addon_dir/config.yaml" && -f "$addon_dir/build.yaml" ]]; then
            modified_addons+="$addon_dir"$'\n'
        fi
    done < <(git diff --name-only "$range" 2>/dev/null || true)
done

modified_addons=$(printf '%s' "$modified_addons" | sort -u | grep -v '^$' || true)

if [[ -z "$modified_addons" ]]; then
    exit 0
fi

errored=0

while IFS= read -r addon_dir; do
    [[ -n "$addon_dir" ]] || continue

    # The git tag is named after the base version in build.yaml (args.VERSION),
    # NOT after config.yaml which carries an additional '-N' subpatch suffix.
    # update-version.py creates the tag from the make-release CLI argument,
    # which is the base version (matching build.yaml).
    version=$(grep 'VERSION:' "$addon_dir/build.yaml" | sed 's/.*VERSION: *"\([^"]*\)".*/\1/')
    [[ -z "$version" ]] && continue

    tag="${addon_dir}/v${version}"

    if git rev-parse --verify --quiet "refs/tags/$tag" >/dev/null 2>&1; then
        echo "✓ $addon_dir: tag $tag exists locally"
        continue
    fi

    if git rev-parse --verify --quiet "refs/remotes/origin/$tag" >/dev/null 2>&1; then
        echo "✓ $addon_dir: tag $tag exists on origin (remote ref)"
        continue
    fi

    if git ls-remote --exit-code --tags origin "refs/tags/$tag" 2>/dev/null | grep -q "$tag"; then
        echo "✓ $addon_dir: tag $tag exists on origin (ls-remote)"
        continue
    fi

    echo ""
    echo "❌ $addon_dir: version '$version' has no matching tag ($tag)"
    echo ""
    echo "   The build workflow for $addon_dir triggers on a '<addon>/v*' tag push."
    echo "   Without $tag, HA-Store-Refresh sees the new version but the"
    echo "   Docker image at ghcr.io doesn't exist → 404 on update."
    echo ""
    echo "   Fix options:"
    echo "     make release ADDON=$addon_dir VERSION=$version"
    echo "     # or manually:"
    echo "     git tag -a $tag -m '$addon_dir: $version'"
    echo "     git push origin $tag"
    echo ""
    errored=1
done <<< "$modified_addons"

if [[ "$errored" -ne 0 ]]; then
    echo "🚫 Pre-push check failed — see errors above"
    echo "   To bypass this check (not recommended): git push --no-verify"
    exit 1
fi

exit 0
