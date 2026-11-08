#!/bin/bash
# Refresh the OpenCode pins of the coding-assistants add-on (OPENCODE_VERSION and both SHA256 digests) in the
# Dockerfile ARG defaults and build.yaml args at once. Renovate can only bump OPENCODE_VERSION; the digests must be
# refreshed with this script on the same branch (scenario `drift` of verify-coding-assistants.sh checks the mirror).
#
# Usage: internal/update-opencode-pins.sh [VERSION]   (default: the OPENCODE_VERSION currently in build.yaml)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="${ROOT}/coding-assistants/Dockerfile"
BUILD_YAML="${ROOT}/coding-assistants/build.yaml"

VERSION="${1:-$(sed -nE 's/^  OPENCODE_VERSION: "([^"]+)"$/\1/p' "${BUILD_YAML}")}"
[[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "invalid version: '${VERSION}'" >&2; exit 1; }

digest() {
    local asset="$1" value
    value="$(gh api "repos/anomalyco/opencode/releases/tags/v${VERSION}" \
        --jq ".assets[] | select(.name == \"${asset}.tar.gz\") | .digest")"
    [[ "${value}" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "no sha256 digest for ${asset} in v${VERSION}" >&2; exit 1; }
    echo "${value#sha256:}"
}

X86_64="$(digest opencode-linux-x64)"
AARCH64="$(digest opencode-linux-arm64)"

sed -i -E \
    -e "s/^(ARG OPENCODE_VERSION=).*/\1${VERSION}/" \
    -e "s/^(ARG OPENCODE_SHA256_X86_64=).*/\1${X86_64}/" \
    -e "s/^(ARG OPENCODE_SHA256_AARCH64=).*/\1${AARCH64}/" "${DOCKERFILE}"
sed -i -E \
    -e "s/^(  OPENCODE_VERSION: ).*/\1\"${VERSION}\"/" \
    -e "s/^(  OPENCODE_SHA256_X86_64: ).*/\1\"${X86_64}\"/" \
    -e "s/^(  OPENCODE_SHA256_AARCH64: ).*/\1\"${AARCH64}\"/" "${BUILD_YAML}"

echo "OpenCode pins set to ${VERSION} (x86_64 ${X86_64:0:12}…, aarch64 ${AARCH64:0:12}…)"
