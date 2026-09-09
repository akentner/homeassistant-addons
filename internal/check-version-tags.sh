#!/usr/bin/env bash
# Pre-push hook for the per-addon build workflows (.github/workflows/build-<addon>.yml):
# every workflow also triggers on `git push` of an `<addon>/v*` tag, so a matching
# tag must exist locally or on origin for every config.yaml/build.yaml change that
# lands in main. Without a matching tag the HA supervisor refresh sees the new version
# in the store but the image at ghcr.io does not exist -> 404 -> "Unknown error".
# Install via ./internal/setup-hooks.sh.

set -e

modified_addons=""

while IFS=' ' read -r local_ref local_sha remote_ref remote_sha; do
    [[ -n "$local_ref" ]] || continue
    [[ "$local_sha" == "0000000000000000000000000000000000000000" ]] && continue

    # Tag pushes do not introduce new file contents - the tag merely points at
    # an existing commit. The branch's working-tree build.yaml is irrelevant
    # for the snapshot the tag was created against, so checking it would
    # produce false positives when re-tagging an older commit whose
    # build.yaml has since moved on. Skip tag pushes entirely.
    if [[ "$local_ref" == refs/tags/* ]]; then
        continue
    fi

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

# Add-ons the Home Assistant Supervisor builds locally from their Dockerfile.
#
# Why an entry is on this list: the add-on's config.yaml declares no top-level
# `image:` key, so the Supervisor never pulls a prebuilt image from ghcr.io and
# builds the add-on locally instead. The 404-on-update this hook guards against
# therefore cannot occur, and an `<addon>/v<version>` release tag publishes
# nothing the Supervisor consumes.
#
# What takes an entry off this list: the add-on gaining a top-level `image:`
# key. From then on the Supervisor pulls a prebuilt image and the tag
# requirement genuinely applies again. The drift guard inside the loop below
# detects that case, warns and enforces anyway — but the array must still be
# corrected.
#
# Why this is an explicit allowlist and not a test for a missing `image:` key:
# authentik also lacks the key while publishing ghcr.io images via its build
# workflow, which may be a missing-key bug rather than intent. Inferring the
# rule from the key's absence would cement that bug behind a guard that
# stopped complaining. Full reasoning in
# .planning/quick/make-the-pre-push-version-tag-hook-stop-demanding-a-release/260908-pfq-PLAN.md
#
# Known limitation: an entry naming a renamed or removed directory is inert
# rather than detected — the loop below only iterates add-on directories that a
# push actually modified, so a stale name simply never matches.
LOCAL_BUILD_ADDONS=(
    iac-runner
)

# is_local_build: returns 0 if $1 is an exact member of LOCAL_BUILD_ADDONS,
# 1 otherwise. Call it only as an `if` condition — `set -e` is active, so a
# bare call returning 1 would abort the hook. The comparison is written as a
# full `if` rather than `[[ ... ]] && return 0` for the same reason: the `&&`
# form leaves a non-zero AND-OR list as the loop body's last statement on a
# non-match.
is_local_build() {
    local a
    for a in "${LOCAL_BUILD_ADDONS[@]}"; do
        if [[ "$a" == "$1" ]]; then
            return 0
        fi
    done
    return 1
}

# tag_exists: echoes 0 if the tag is reachable via local refs, origin remote
# refs (after `git fetch --tags`), or `git ls-remote` against origin.
tag_exists() {
    local t="$1"
    git rev-parse --verify --quiet "refs/tags/$t" >/dev/null 2>&1 \
        || git rev-parse --verify --quiet "refs/remotes/origin/$t" >/dev/null 2>&1 \
        || git ls-remote --exit-code --tags origin "refs/tags/$t" >/dev/null 2>&1
}

while IFS= read -r addon_dir; do
    [[ -n "$addon_dir" ]] || continue

    # Anchor VERSION: with leading-whitespace tolerance (it's nested under
    # args: in terraform-bridge/build.yaml). Unanchored grep also matches
    # BRIDGE_VERSION: / CHROMIUM_VERSION: etc., producing a multi-line
    # BUILD_VERSION that breaks the tag lookup below.
    build_version=$(grep -E '^[[:space:]]*VERSION:' "$addon_dir/build.yaml" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/' | head -1)
    # config.yaml carries the subpatch suffix (X.Y.Z-N). Grep tolerant of
    # quoted/unquoted values; head -1 protects against multi-line matches.
    config_version=$(grep -E '^[[:space:]]*version:' "$addon_dir/config.yaml" | sed -E 's/^[[:space:]]*version:[[:space:]]*"?([^"]+)"?.*/\1/' | head -1)
    [[ -z "$build_version" && -z "$config_version" ]] && continue

    # Add-ons built locally by the Supervisor need no release tag (see
    # LOCAL_BUILD_ADDONS above). config.yaml is re-read on every push so a
    # stale allowlist entry cannot silently disable the ghcr-404 guard.
    if is_local_build "$addon_dir"; then
        # Anchored at ^ and requiring a non-blank value: an indented sub-key,
        # a commented `# image:` line or an empty value cannot satisfy it, and
        # `image` is a top-level key in the HA add-on manifest so the anchor is
        # exact. grep, not yq: HA config.yaml needs `yq eval --unsafe` for its
        # custom tags, and this script runs as a bare .git/hooks copy that must
        # carry no tool dependency.
        if grep -qE '^image:[[:space:]]*[^[:space:]]' "$addon_dir/config.yaml"; then
            echo ""
            echo "⚠️  $addon_dir is on LOCAL_BUILD_ADDONS but its config.yaml declares"
            echo "   a top-level 'image:' key. The Supervisor now pulls a prebuilt"
            echo "   image from ghcr.io, so the release tag is required again."
            echo "   Enforcing the tag requirement despite the allowlist entry."
            echo "   Remove '$addon_dir' from LOCAL_BUILD_ADDONS in"
            echo "   internal/check-version-tags.sh."
            echo ""
        else
            echo "⊘ $addon_dir: built locally by the Supervisor, never pulled from ghcr.io; release tag not required"
            continue
        fi
    fi

    # Tag format changed to include the subpatch suffix so it matches the OCI
    # image tag (CONFIG_VERSION) the build workflow publishes. Older releases
    # only tagged <addon>/v<build_version> (no suffix) — accept both formats
    # so a transition doesn't break pushes for legacy addons.
    primary_tag="${addon_dir}/v${config_version}"
    legacy_tag="${addon_dir}/v${build_version}"

    if tag_exists "$primary_tag"; then
        echo "✓ $addon_dir: tag $primary_tag exists"
        continue
    fi
    if [[ "$primary_tag" != "$legacy_tag" ]] && tag_exists "$legacy_tag"; then
        echo "✓ $addon_dir: tag $legacy_tag exists (legacy format, no subpatch)"
        continue
    fi

    echo ""
    echo "❌ $addon_dir: no matching tag for version '$config_version' (expected $primary_tag)"
    if [[ -n "$build_version" && "$build_version" != "$config_version" ]]; then
        echo "   Legacy format $legacy_tag also missing."
    fi
    echo ""
    echo "   The build workflow for $addon_dir triggers on a '<addon>/v*' tag push."
    echo "   Without $primary_tag, HA-Store-Refresh sees the new version but the"
    echo "   Docker image at ghcr.io doesn't exist → 404 on update."
    echo ""
    echo "   Fix options:"
    echo "     make release ADDON=$addon_dir VERSION=$config_version"
    echo "     # or manually:"
    echo "     git tag -a $primary_tag -m '$addon_dir: $config_version'"
    echo "     git push origin $primary_tag"
    echo ""
    errored=1
done <<< "$modified_addons"

if [[ "$errored" -ne 0 ]]; then
    echo "🚫 Pre-push check failed — see errors above"
    echo "   To bypass this check (not recommended): git push --no-verify"
    exit 1
fi

exit 0
