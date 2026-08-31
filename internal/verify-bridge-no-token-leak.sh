#!/usr/bin/env bash
# verify-bridge-no-token-leak.sh — Phase 9 no-token-leak invariant (D-12).
#
# Runs the Bridge container with a fake SUPERVISOR_TOKEN in the env,
# captures stdout for ~10 seconds, and asserts that the captured
# output contains NONE of: SUPERVISOR_TOKEN, Bearer, bridge_token.
#
# This is the load-bearing check for the AUTH-01 source-tree invariant:
# "Bridge reads SUPERVISOR_TOKEN via env; never logs it, never sends it
#  to the Provider, never accepts it from a non-loopback source."
#
# Phase 10 OPS-01 adds request-middleware that explicitly strips the
# Authorization header and the bridge_token field from log records; this
# Phase 9 script enforces the broader invariant "no token-like substrings
# in stdout" at the boundary, which holds because the Bridge doesn't
# have any logging that references tokens yet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BRIDGE_DIR="${REPO_ROOT}/terraform-bridge"

IMAGE_NAME="terraform-bridge:leak-$(date +%s)"
CONTAINER_NAME="terraform-bridge-leak-test"
FAKE_TOKEN="phase-9-fake-supervisor-token-do-not-use-in-prod"

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }

cleanup() {
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    docker rmi  "${IMAGE_NAME}"       >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ ! -d "${BRIDGE_DIR}" ]]; then
    red "Bridge directory not found: ${BRIDGE_DIR}"
    exit 2
fi

BRIDGE_VERSION="$(grep -E '^[[:space:]]*VERSION:' "${BRIDGE_DIR}/build.yaml" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')"

docker build -t "${IMAGE_NAME}" \
             --build-arg "BRIDGE_VERSION=${BRIDGE_VERSION}" \
             "${BRIDGE_DIR}" >/dev/null 2>&1

# Run with a fake SUPERVISOR_TOKEN. Touch GET / once during the capture
# window so any request-logging middleware (Phase 10 OPS-01) also has a
# chance to write a line we'd be checking.
docker run --rm -d --name "${CONTAINER_NAME}" \
           -e "SUPERVISOR_TOKEN=${FAKE_TOKEN}" \
           -p 8124:8124 "${IMAGE_NAME}"
sleep 2
curl -sS --max-time 5 "http://localhost:8124/" >/dev/null 2>&1 || true
sleep 8

CAPTURED=$(docker logs "${CONTAINER_NAME}" 2>&1)
echo "   captured ${#CAPTURED} bytes of container output"

FAIL=0
for PATTERN in 'SUPERVISOR_TOKEN' 'Bearer' 'bridge_token'; do
    if echo "${CAPTURED}" | grep -F -q -- "${PATTERN}"; then
        red "   FAIL: pattern '${PATTERN}' found in container stdout"
        echo "${CAPTURED}" | grep -F -- "${PATTERN}" | head -3
        FAIL=1
    else
        echo "   PASS: no '${PATTERN}' in stdout"
    fi
done

# Also verify the fake token itself (not just the variable name) doesn't
# appear.  PITFALLS S-1 calls this out specifically.
if echo "${CAPTURED}" | grep -F -q -- "${FAKE_TOKEN}"; then
    red "   FAIL: fake token value found in container stdout"
    echo "${CAPTURED}" | grep -F -- "${FAKE_TOKEN}" | head -3
    FAIL=1
else
    echo "   PASS: fake token value not present in stdout"
fi

if (( FAIL == 1 )); then
    red "verify-bridge-no-token-leak: FAIL"
    exit 1
fi

green "verify-bridge-no-token-leak: PASS"
