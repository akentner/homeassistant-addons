#!/bin/bash
# Refresh the Codex CLI pins of the coding-assistants add-on (CODEX_VERSION and both SHA256 digests) in the
# Dockerfile ARG defaults and build.yaml args at once. Renovate can only bump CODEX_VERSION; the digests must be
# refreshed with this script on the same branch (scenario `drift` of verify-coding-assistants.sh checks the mirror).
#
# Usage: internal/update-codex-pins.sh [VERSION]   (default: the CODEX_VERSION currently in build.yaml)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="${ROOT}/coding-assistants/Dockerfile"
BUILD_YAML="${ROOT}/coding-assistants/build.yaml"

VERSION="${1:-$(sed -nE 's/^  CODEX_VERSION: "([^"]+)"$/\1/p' "${BUILD_YAML}")}"
[[ "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "invalid version: '${VERSION}'" >&2; exit 1; }

digest() {
    local arch="$1" value
    value="$(gh api "repos/openai/codex/releases/tags/rust-v${VERSION}" \
        --jq ".assets[] | select(.name == \"codex-${arch}-unknown-linux-musl.tar.gz\") | .digest")"
    [[ "${value}" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "no sha256 digest for ${arch} in rust-v${VERSION}" >&2; exit 1; }
    echo "${value#sha256:}"
}

X86_64="$(digest x86_64)"
AARCH64="$(digest aarch64)"

sed -i -E \
    -e "s/^(ARG CODEX_VERSION=).*/\1${VERSION}/" \
    -e "s/^(ARG CODEX_SHA256_X86_64=).*/\1${X86_64}/" \
    -e "s/^(ARG CODEX_SHA256_AARCH64=).*/\1${AARCH64}/" "${DOCKERFILE}"
sed -i -E \
    -e "s/^(  CODEX_VERSION: ).*/\1\"${VERSION}\"/" \
    -e "s/^(  CODEX_SHA256_X86_64: ).*/\1\"${X86_64}\"/" \
    -e "s/^(  CODEX_SHA256_AARCH64: ).*/\1\"${AARCH64}\"/" "${BUILD_YAML}"

echo "Codex pins set to ${VERSION} (x86_64 ${X86_64:0:12}…, aarch64 ${AARCH64:0:12}…)"
