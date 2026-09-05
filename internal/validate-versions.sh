#!/bin/bash
# Pre-commit hook to validate versioning consistency
# Checks all add-on directories (any directory containing config.yaml + build.yaml)
#
# Supported formats:
#   Stable:     config X.Y.Z-N  | build X.Y.Z          | README contains vX.Y.Z
#   Pre-release: config X.Y.Z-{alpha|beta|rc}N | build X.Y.Z-{alpha|beta|rc}N | README contains vX.Y.Z-{alpha|beta|rc}N

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

GLOBAL_ERRORS=()

validate_addon() {
    local ADDON_DIR="$1"
    local ERRORS=()

    echo "Validating ${ADDON_DIR}..."

    local CONFIG_VERSION=""
    local BUILD_VERSION=""

    if [[ -f "$ADDON_DIR/config.yaml" ]]; then
        CONFIG_VERSION=$(grep '^version:' "$ADDON_DIR/config.yaml" | sed 's/version: *"\([^"]*\)".*/\1/')
    fi

    if [[ -f "$ADDON_DIR/build.yaml" ]]; then
        # Anchor VERSION: with leading-whitespace tolerance (it's nested under
        # args:). Unanchored grep would also match BRIDGE_VERSION: /
        # CHROMIUM_VERSION: etc., producing a multi-line BUILD_VERSION that
        # breaks the regex check below.
        BUILD_VERSION=$(grep -E '^[[:space:]]*VERSION:' "$ADDON_DIR/build.yaml" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')
    fi

    echo "   config.yaml: $CONFIG_VERSION"
    echo "   build.yaml:  $BUILD_VERSION"

    # Detect format and validate
    if [[ "$CONFIG_VERSION" =~ ^([0-9]+\.[0-9]+\.[0-9]+)-([0-9]+)$ ]]; then
        # Stable: X.Y.Z-N
        local CONFIG_BASE="${BASH_REMATCH[1]}"

        if [[ ! "$BUILD_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            ERRORS+=("[$ADDON_DIR] build.yaml VERSION '$BUILD_VERSION' must be X.Y.Z for stable releases")
        elif [[ "$CONFIG_BASE" != "$BUILD_VERSION" ]]; then
            ERRORS+=("[$ADDON_DIR] Version mismatch: config.yaml base '$CONFIG_BASE' != build.yaml '$BUILD_VERSION'")
        fi

        if [[ -f "$ADDON_DIR/README.md" ]]; then
            local README_VERSION
            README_VERSION=$(grep 'version-v' "$ADDON_DIR/README.md" | sed 's/.*version-v\([^-]*\)-.*/\1/' | head -1)
            echo "   README.md:   $README_VERSION"
            if [[ "$README_VERSION" != "$BUILD_VERSION" ]]; then
                ERRORS+=("[$ADDON_DIR] Version mismatch: README.md '$README_VERSION' != build.yaml '$BUILD_VERSION'")
            fi
        fi

    elif [[ "$CONFIG_VERSION" =~ ^([0-9]+\.[0-9]+\.[0-9]+)-(alpha|beta|rc)([0-9]+)$ ]]; then
        # Pre-release: X.Y.Z-{alpha|beta|rc}N — config and build must match exactly
        echo "   README.md:   (pre-release — checking for v${CONFIG_VERSION})"

        if [[ "$BUILD_VERSION" != "$CONFIG_VERSION" ]]; then
            ERRORS+=("[$ADDON_DIR] Version mismatch: config.yaml '$CONFIG_VERSION' != build.yaml '$BUILD_VERSION'")
        fi

        if [[ -f "$ADDON_DIR/README.md" ]] && ! grep -q "v${CONFIG_VERSION}" "$ADDON_DIR/README.md"; then
            ERRORS+=("[$ADDON_DIR] README.md does not contain v${CONFIG_VERSION}")
        fi

    elif [[ -n "$CONFIG_VERSION" ]]; then
        ERRORS+=("[$ADDON_DIR] config.yaml version '$CONFIG_VERSION' has invalid format")
        ERRORS+=("[$ADDON_DIR]   Stable:      X.Y.Z-N         (e.g. 1.3.1-0)")
        ERRORS+=("[$ADDON_DIR]   Pre-release: X.Y.Z-{alpha|beta|rc}N  (e.g. 1.0.0-alpha1)")
    fi

    GLOBAL_ERRORS+=("${ERRORS[@]}")
}

# Auto-discover any directory containing config.yaml + build.yaml. Scan
# recurses 2 levels deep so nested add-ons under `tools/` (e.g.
# `tools/test-addon/`, the Phase 14 verify suite's live test target) are
# picked up alongside top-level add-on directories. Depth 2 covers every
# nesting pattern used in this repo (top-level + tools/<name>/).
ADDON_DIRS=()
mapfile -t ADDON_DIRS < <(find . -mindepth 1 -maxdepth 2 -type d \
    \( -name .git -o -name node_modules \) -prune -o \
    -type d -print 2>/dev/null \
    | while read -r dir; do
        if [[ -f "$dir/config.yaml" ]] && [[ -f "$dir/build.yaml" ]]; then
            # strip leading "./" for cosmetic consistency with the old glob
            printf '%s\n' "${dir#./}"
        fi
    done | sort)

if [[ ${#ADDON_DIRS[@]} -eq 0 ]]; then
    echo -e "${YELLOW}No add-on directories found, skipping version validation${NC}"
    exit 0
fi

echo "Found add-ons: ${ADDON_DIRS[*]}"
echo ""

for addon in "${ADDON_DIRS[@]}"; do
    validate_addon "$addon"
    echo ""
done

# ── Cross-artifact Bridge/Provider sync (TOFU-05) ────────────────────────
# Bridge and Provider share one release cycle via the 3-file scheme.
# When both build.yaml files exist, their VERSION fields must match
# exactly. The check is conditional on both existing (pre-Phase-9
# repositories that migrate forward without the Provider don't fail).
BRIDGE_BUILD="terraform-bridge/build.yaml"
PROVIDER_BUILD="terraform-provider-homeassistant/build.yaml"
if [[ -f "$BRIDGE_BUILD" ]] && [[ -f "$PROVIDER_BUILD" ]]; then
    # Whitespace-tolerant (Wave 1 fix for BRIDGE_VERSION/CHROMIUM_VERSION prefix
    # collision — VERSION: is nested under args: in terraform-bridge/build.yaml).
    BRIDGE_VERSION=$(grep -E '^[[:space:]]*VERSION:' "$BRIDGE_BUILD" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')
    PROVIDER_VERSION=$(grep -E '^[[:space:]]*VERSION:' "$PROVIDER_BUILD" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')
    echo ""
    echo "Cross-artifact check (TOFU-05):"
    echo "   $BRIDGE_BUILD: $BRIDGE_VERSION"
    echo "   $PROVIDER_BUILD: $PROVIDER_VERSION"
    if [[ "$BRIDGE_VERSION" != "$PROVIDER_VERSION" ]]; then
        GLOBAL_ERRORS+=("[TOFU-05] Version mismatch: terraform-bridge '$BRIDGE_VERSION' != terraform-provider-homeassistant '$PROVIDER_VERSION'")
        GLOBAL_ERRORS+=("           Run: make update-version ADDON=terraform-bridge VERSION=$BRIDGE_VERSION")
    fi
fi

if [[ ${#GLOBAL_ERRORS[@]} -eq 0 ]]; then
    echo -e "${GREEN}Version validation passed for all add-ons!${NC}"
    exit 0
else
    echo -e "${RED}Version validation failed:${NC}"
    for error in "${GLOBAL_ERRORS[@]}"; do
        echo -e "   ${error}"
    done
    exit 1
fi
