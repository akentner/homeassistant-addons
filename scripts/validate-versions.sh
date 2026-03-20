#!/bin/bash
# Pre-commit hook to validate versioning consistency
# Checks all add-on directories (any directory containing config.yaml + build.yaml)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

GLOBAL_ERRORS=()

validate_addon() {
    local ADDON_DIR="$1"
    local ERRORS=()

    echo "Validating ${ADDON_DIR}..."

    local CONFIG_VERSION=""
    local BUILD_VERSION=""
    local README_VERSION=""

    if [[ -f "$ADDON_DIR/config.yaml" ]]; then
        CONFIG_VERSION=$(grep '^version:' "$ADDON_DIR/config.yaml" | sed 's/version: *"\([^"]*\)".*/\1/')
    fi

    if [[ -f "$ADDON_DIR/build.yaml" ]]; then
        BUILD_VERSION=$(grep 'VERSION:' "$ADDON_DIR/build.yaml" | sed 's/.*VERSION: *"\([^"]*\)".*/\1/')
    fi

    if [[ -f "$ADDON_DIR/README.md" ]]; then
        README_VERSION=$(grep 'version-v' "$ADDON_DIR/README.md" | sed 's/.*version-v\([^-]*\)-.*/\1/' | head -1)
    fi

    echo "   config.yaml: $CONFIG_VERSION"
    echo "   build.yaml:  $BUILD_VERSION"
    echo "   README.md:   $README_VERSION"

    if [[ -n "$CONFIG_VERSION" ]]; then
        if [[ ! "$CONFIG_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9]+$ ]]; then
            ERRORS+=("[$ADDON_DIR] config.yaml version '$CONFIG_VERSION' must use subpatch format X.Y.Z-N (e.g. 1.3.1-0)")
        fi
    fi

    if [[ -n "$BUILD_VERSION" ]]; then
        if [[ ! "$BUILD_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            ERRORS+=("[$ADDON_DIR] build.yaml VERSION '$BUILD_VERSION' must use standard format X.Y.Z (e.g. 1.3.1)")
        fi
    fi

    if [[ -n "$CONFIG_VERSION" ]] && [[ -n "$BUILD_VERSION" ]]; then
        local CONFIG_BASE="${CONFIG_VERSION%-[0-9]*}"
        if [[ "$CONFIG_BASE" != "$BUILD_VERSION" ]]; then
            ERRORS+=("[$ADDON_DIR] Version mismatch: config.yaml base '$CONFIG_BASE' != build.yaml '$BUILD_VERSION'")
        fi
    fi

    if [[ -n "$README_VERSION" ]] && [[ -n "$BUILD_VERSION" ]]; then
        if [[ "$README_VERSION" != "$BUILD_VERSION" ]]; then
            ERRORS+=("[$ADDON_DIR] Version mismatch: README.md '$README_VERSION' != build.yaml '$BUILD_VERSION'")
        fi
    fi

    GLOBAL_ERRORS+=("${ERRORS[@]}")
}

# Auto-discover add-on directories (contain both config.yaml and build.yaml)
ADDON_DIRS=()
for dir in */; do
    dir="${dir%/}"
    if [[ -f "$dir/config.yaml" ]] && [[ -f "$dir/build.yaml" ]]; then
        ADDON_DIRS+=("$dir")
    fi
done

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

if [[ ${#GLOBAL_ERRORS[@]} -eq 0 ]]; then
    echo -e "${GREEN}Version validation passed for all add-ons!${NC}"
    exit 0
else
    echo -e "${RED}Version validation failed:${NC}"
    for error in "${GLOBAL_ERRORS[@]}"; do
        echo -e "   ${error}"
    done
    echo ""
    echo -e "${YELLOW}Expected format:${NC}"
    echo -e "   config.yaml: version: \"X.Y.Z-N\" (e.g. \"1.3.1-0\")"
    echo -e "   build.yaml:  VERSION: \"X.Y.Z\" (e.g. \"1.3.1\")"
    echo -e "   README.md:   version-vX.Y.Z (e.g. \"version-v1.3.1\")"
    exit 1
fi
