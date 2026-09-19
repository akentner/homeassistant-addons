#!/usr/bin/env bash
# Verify the litellm/ add-on image builds, is ≤ 500 MiB, and has all required OCI labels.
# Manual invocation: bash internal/verify-litellm-scaffold.sh
set -euo pipefail

ADDON_DIR="litellm"
IMAGE_TAG="litellm-verify:local"
MAX_SIZE_MIB=500

# Load VERSION + LITELLM_VERSION from build.yaml (simple yq-free parsing — same pattern as
# other repo verifiers)
VERSION=$(grep -E '^  VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^  VERSION: "(.*)"/\1/')
LITELLM_VERSION=$(grep -E '^  LITELLM_VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^  LITELLM_VERSION: "(.*)"/\1/')
BUILD_FROM=$(grep -E '^      amd64:' "${ADDON_DIR}/build.yaml" | sed -E 's/^      amd64: "(.*)"/\1/')

echo "==> Building ${IMAGE_TAG} from ${ADDON_DIR}/ (VERSION=${VERSION} LITELLM_VERSION=${LITELLM_VERSION} BUILD_FROM=${BUILD_FROM})"

if ! docker build \
    --build-arg "BUILD_FROM=${BUILD_FROM}" \
    --build-arg "VERSION=${VERSION}" \
    --build-arg "LITELLM_VERSION=${LITELLM_VERSION}" \
    --tag "${IMAGE_TAG}" \
    "${ADDON_DIR}/"; then
    echo "✗ image build failed"
    exit 1
fi
echo "✓ image built"

# Image size (MiB)
SIZE_BYTES=$(docker image inspect "${IMAGE_TAG}" --format '{{.Size}}')
SIZE_MIB=$((SIZE_BYTES / 1024 / 1024))
if [ "${SIZE_MIB}" -gt "${MAX_SIZE_MIB}" ]; then
    echo "✗ image size ${SIZE_MIB} MiB exceeds ${MAX_SIZE_MIB} MiB threshold (D-32)"
    exit 1
fi
echo "✓ image size ${SIZE_MIB} MiB (≤ ${MAX_SIZE_MIB} MiB)"

# OCI labels (D-06 — full label block per authentik/Dockerfile lines 78-103)
REQUIRED_LABELS=(
    "io.hass.name"
    "io.hass.description"
    "io.hass.arch"
    "io.hass.type"
    "io.hass.version"
    "maintainer"
    "org.opencontainers.image.title"
    "org.opencontainers.image.description"
    "org.opencontainers.image.version"
)
for label in "${REQUIRED_LABELS[@]}"; do
    if ! docker image inspect "${IMAGE_TAG}" --format "{{index .Config.Labels \"${label}\"}}" | grep -q .; then
        echo "✗ missing OCI label: ${label}"
        exit 1
    fi
    echo "✓ OCI label present: ${label}"
done

echo ""
echo "All litellm scaffold verifications passed."
