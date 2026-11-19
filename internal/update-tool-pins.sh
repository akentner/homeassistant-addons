#!/bin/bash
# Refresh the pinned GitHub release tools of the coding-assistants add-on (yq, ha CLI, ttyd, fff, eza, delta, difftastic,
# yazi, atuin, tealdeer, lazygit). The *_VERSION values in build.yaml are the source (Renovate bumps them); this script
# copies them into the Dockerfile ARG defaults and refreshes both *_SHA256_X86_64 pins in Dockerfile and build.yaml from
# the GitHub release asset digests (ttyd publishes none: its SHA256SUMS release asset is used instead).
# Scenario `drift` of verify-coding-assistants.sh checks that Dockerfile and build.yaml stay in sync.
#
# Usage: internal/update-tool-pins.sh [PREFIX...]   (default: every tool, e.g. `YQ DELTA` for a subset)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKERFILE="${ROOT}/coding-assistants/Dockerfile"
BUILD_YAML="${ROOT}/coding-assistants/build.yaml"

# PREFIX|repository|tag prefix|asset name ({v} = bare version)
TOOLS=(
    "YQ|mikefarah/yq|v|yq_linux_amd64"
    "HA_CLI|home-assistant/cli||ha_amd64"
    "TTYD|tsl0922/ttyd||ttyd.x86_64"
    "FFF|dmtrKovalenko/fff|v|fff-mcp-x86_64-unknown-linux-gnu"
    "EZA|eza-community/eza|v|eza_x86_64-unknown-linux-gnu.tar.gz"
    "DELTA|dandavison/delta||delta-{v}-x86_64-unknown-linux-gnu.tar.gz"
    "DIFFTASTIC|Wilfred/difftastic||difft-{v}-x86_64-unknown-linux-gnu.tar.gz"
    "YAZI|sxyazi/yazi|v|yazi-x86_64-unknown-linux-musl.zip"
    "ATUIN|atuinsh/atuin|v|atuin-x86_64-unknown-linux-musl.tar.gz"
    "TEALDEER|tealdeer-rs/tealdeer|v|tealdeer-linux-x86_64-musl"
    "LAZYGIT|jesseduffield/lazygit|v|lazygit_{v}_linux_x86_64.tar.gz"
)

WANT=" $* "
for entry in "${TOOLS[@]}"; do
    IFS='|' read -r prefix repo tagprefix asset <<<"${entry}"
    [[ "$#" -eq 0 || "${WANT}" == *" ${prefix} "* ]] || continue
    version="$(sed -nE "s/^  ${prefix}_VERSION: \"([^\"]+)\"\$/\1/p" "${BUILD_YAML}")"
    [[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "${prefix}: invalid version '${version}'" >&2; exit 1; }
    asset="${asset//\{v\}/${version}}"
    tag="${tagprefix}${version}"
    if [[ "${prefix}" == "TTYD" ]]; then
        digest="$(curl -fsSL "https://github.com/${repo}/releases/download/${tag}/SHA256SUMS" \
            | awk -v a="${asset}" '$2 == a { print $1 }')"
    else
        digest="$(gh api "repos/${repo}/releases/tags/${tag}" \
            --jq ".assets[] | select(.name == \"${asset}\") | .digest" | sed 's/^sha256://')"
    fi
    [[ "${digest}" =~ ^[0-9a-f]{64}$ ]] || { echo "${prefix}: no sha256 for ${asset} in ${tag}" >&2; exit 1; }
    sed -i -E \
        -e "s/^(ARG ${prefix}_VERSION=).*/\1${version}/" \
        -e "s/^(ARG ${prefix}_SHA256_X86_64=).*/\1${digest}/" "${DOCKERFILE}"
    sed -i -E "s/^(  ${prefix}_SHA256_X86_64: ).*/\1\"${digest}\"/" "${BUILD_YAML}"
    echo "${prefix} pinned to ${version} (${digest:0:12}…)"
done
