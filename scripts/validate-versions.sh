#!/bin/bash
# Pre-commit hook to validate versioning consistency
# Checks fritz-callmonitor2mqtt add-on versioning rules

set -e

ADDON_DIR="fritz-callmonitor2mqtt"
ERRORS=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Validating fritz-callmonitor2mqtt versioning..."

# Check if add-on directory exists
if [[ ! -d "$ADDON_DIR" ]]; then
    echo -e "${YELLOW}⚠️  $ADDON_DIR directory not found, skipping version validation${NC}"
    exit 0
fi

# Extract versions from files
CONFIG_VERSION=""
BUILD_VERSION=""
README_VERSION=""

# Read config.yaml version
if [[ -f "$ADDON_DIR/config.yaml" ]]; then
    CONFIG_VERSION=$(grep '^version:' "$ADDON_DIR/config.yaml" | sed 's/version: *"\([^"]*\)".*/\1/')
fi

# Read build.yaml version
if [[ -f "$ADDON_DIR/build.yaml" ]]; then
    BUILD_VERSION=$(grep 'VERSION:' "$ADDON_DIR/build.yaml" | sed 's/.*VERSION: *"\([^"]*\)".*/\1/')
fi

# Read README.md badge version
if [[ -f "$ADDON_DIR/README.md" ]]; then
    README_VERSION=$(grep 'version-v' "$ADDON_DIR/README.md" | sed 's/.*version-v\([^-]*\)-.*/\1/' | head -1)
fi

echo "📋 Found versions:"
echo "   config.yaml: $CONFIG_VERSION"
echo "   build.yaml:  $BUILD_VERSION"  
echo "   README.md:   $README_VERSION"

# Validation 1: config.yaml must have subpatch format (X.Y.Z-N)
if [[ -n "$CONFIG_VERSION" ]]; then
    if [[ ! "$CONFIG_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9]+$ ]]; then
        ERRORS+=("❌ config.yaml version '$CONFIG_VERSION' must use subpatch format X.Y.Z-N (e.g. 1.3.1-0)")
    fi
fi

# Validation 2: build.yaml must have standard format (X.Y.Z) without subpatch
if [[ -n "$BUILD_VERSION" ]]; then
    if [[ ! "$BUILD_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        ERRORS+=("❌ build.yaml VERSION '$BUILD_VERSION' must use standard format X.Y.Z (e.g. 1.3.1)")
    fi
fi

# Validation 3: Versions must be consistent (ignoring subpatch in config)
if [[ -n "$CONFIG_VERSION" ]] && [[ -n "$BUILD_VERSION" ]]; then
    CONFIG_BASE=$(echo "$CONFIG_VERSION" | sed 's/-[0-9]*$//')
    if [[ "$CONFIG_BASE" != "$BUILD_VERSION" ]]; then
        ERRORS+=("❌ Version mismatch: config.yaml base '$CONFIG_BASE' != build.yaml '$BUILD_VERSION'")
    fi
fi

# Validation 4: README version should match base version
if [[ -n "$README_VERSION" ]] && [[ -n "$BUILD_VERSION" ]]; then
    if [[ "$README_VERSION" != "$BUILD_VERSION" ]]; then
        ERRORS+=("❌ Version mismatch: README.md '$README_VERSION' != build.yaml '$BUILD_VERSION'")
    fi
fi

# Report results
if [[ ${#ERRORS[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ Version validation passed!${NC}"
    exit 0
else
    echo -e "${RED}💥 Version validation failed:${NC}"
    for error in "${ERRORS[@]}"; do
        echo -e "   $error"
    done
    echo ""
    echo -e "${YELLOW}📖 See docs/DEVELOPMENT.md for versioning guidelines${NC}"
    echo ""
    echo -e "${YELLOW}Expected format:${NC}"
    echo -e "   config.yaml: version: \"X.Y.Z-N\" (e.g. \"1.3.1-0\")"
    echo -e "   build.yaml:  VERSION: \"X.Y.Z\" (e.g. \"1.3.1\")"
    echo -e "   README.md:   version-vX.Y.Z (e.g. \"version-v1.3.1\")"
    exit 1
fi