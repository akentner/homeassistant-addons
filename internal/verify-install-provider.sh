#!/usr/bin/env bash
# verify-install-provider.sh — hermetic E2E verifier for
# `make install-provider` (Phase 15, Plan 02). The script:
#
#   1. Resolves the repo root via BASH_SOURCE so it works from any cwd.
#   2. Reads the Provider VERSION from terraform-provider-homeassistant/build.yaml
#      using a whitespace-tolerant regex (mirrors internal/validate-versions.sh:114).
#   3. Creates a temp DESTDIR (mktemp -d) and installs `trap ... EXIT` so the
#      temp dir is removed on success AND failure (no /tmp/verify-install-*
#      leftovers in CI).
#   4. Invokes `make install-provider DESTDIR="$TMP/"` — the Makefile target
#      installed by Plan 01. The target's `_PLUGIN_DIR` becomes
#      $TMP$HOME/.terraform.d/plugins/localhost/akentner/homeassistant/$VERSION,
#      so we resolve the binary by `find`-ing the version-component suffix.
#   5. Asserts the binary is executable + non-empty, and runs
#      `$BINARY -version` as a bonus signal (tolerating non-zero exit because
#      Phase 9's stub does not wire a -version flag — that lands in v1.4).
#
# Usage:
#   bash internal/verify-install-provider.sh        # hermetic temp DESTDIR
#   bash internal/verify-install-provider.sh --keep # skip EXIT cleanup for debug
#
# Required: bash 4+, make, go, find, awk.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROVIDER_BUILD="${REPO_ROOT}/terraform-provider-homeassistant/build.yaml"
PROVIDER_SRC="${REPO_ROOT}/terraform-provider-homeassistant"

KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

# Resolve /tmp prefix for the trap so cleanup is hermetic even if mktemp
# fails after the trap is installed.
TMP=""
cleanup() {
    if [[ "${KEEP}" == "0" && -n "${TMP}" && -d "${TMP}" ]]; then
        rm -rf "${TMP}"
    fi
}
trap cleanup EXIT

# Pre-flight
if [[ ! -f "${PROVIDER_BUILD}" ]]; then
    red "Provider build manifest not found: ${PROVIDER_BUILD}"
    red "Run /gsd-execute-phase 9 plan 01 first."
    exit 2
fi

if ! command -v make >/dev/null 2>&1; then
    red "make not found in PATH"
    exit 2
fi

if ! command -v go >/dev/null 2>&1; then
    red "go not found in PATH"
    exit 2
fi

# Whitespace-tolerant version extraction — the Bridge's build.yaml nests
# VERSION under args: with two-space indent; the Provider's build.yaml has
# VERSION at column 0. The regex matches both layouts.
PROVIDER_VERSION=$(grep -E '^[[:space:]]*VERSION:' "${PROVIDER_BUILD}" \
    | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')
if [[ -z "${PROVIDER_VERSION}" ]]; then
    red "Could not extract VERSION from ${PROVIDER_BUILD}"
    exit 1
fi
yellow "verify-install-provider — provider version: ${PROVIDER_VERSION}"
echo

TMP="$(mktemp -d -t verify-install-XXXXXX)"
echo "   temp DESTDIR: ${TMP}"
echo

yellow "Stage 1: make install-provider DESTDIR=${TMP}/"
(
    cd "${REPO_ROOT}"
    make install-provider "DESTDIR=${TMP}/"
)

# The Makefile target's _PLUGIN_DIR resolves to
# ${DESTDIR}${HOME}/.terraform.d/plugins/localhost/akentner/homeassistant/${PROVIDER_VERSION}.
# We don't know what ${HOME} is on this machine, so we resolve the binary
# by the documented dev_overrides path component.
PLUGIN_SUFFIX=".terraform.d/plugins/localhost/akentner/homeassistant/${PROVIDER_VERSION}/terraform-provider-homeassistant"
BINARY="$(find "${TMP}" -path "*/${PLUGIN_SUFFIX}" -type f 2>/dev/null | head -1 || true)"

if [[ -z "${BINARY}" ]]; then
    red "   FAIL: binary not found at */${PLUGIN_SUFFIX} under ${TMP}"
    echo "   find results:"
    find "${TMP}" -type f 2>/dev/null | sed 's/^/      /' || true
    exit 1
fi
green "   PASS: binary located at ${BINARY}"

# Executable + non-empty
if [[ ! -x "${BINARY}" ]]; then
    red "   FAIL: binary at ${BINARY} is not executable"
    exit 1
fi
green "   PASS: binary is executable"

SIZE=$(wc -c < "${BINARY}")
if (( SIZE == 0 )); then
    red "   FAIL: binary at ${BINARY} is zero bytes"
    exit 1
fi
echo "   binary size: ${SIZE} bytes"
green "   PASS: binary is non-empty"

# Bonus: try `-version`. Phase 9's stub does not wire it, so a non-zero
# exit is downgraded to a warning, not a failure. The strict requirement
# was "binary exists + executable + non-empty".
if "${BINARY}" -version >/dev/null 2>&1; then
    VER_OUT="$("${BINARY}" -version 2>&1 || true)"
    green "   PASS: ${BINARY} -version succeeded"
    echo "          ${VER_OUT}"
else
    yellow "   WARN: ${BINARY} -version exited non-zero (Phase 9 stub does not wire -version)"
fi

echo
green "verify-install-provider: PASS"
echo "Provider version: ${PROVIDER_VERSION}"
echo "Binary path:      ${BINARY}"
echo "Binary size:      ${SIZE} bytes"
