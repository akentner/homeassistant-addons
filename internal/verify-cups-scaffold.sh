#!/usr/bin/env bash
# verify-cups-scaffold.sh -- Phase 21 Plan 01 tracer smoke test for the cups/
# add-on. Proves the generated /etc/avahi/avahi-daemon.conf carries the
# D-07/D-10/D-11 fixes and that one fixture printer registers via lpadmin
# against a live cupsd. Mirrors verify-bridge-scaffold.sh /
# verify-litellm-scaffold.sh (DATA_DIR + options.json fixture, docker build,
# docker run -v mount, trap cleanup).
#
# Usage: bash internal/verify-cups-scaffold.sh [--keep]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADDON_DIR="${REPO_ROOT}/cups"

STAMP="$(date +%s)"
IMAGE_NAME="cups-verify:${STAMP}"
CONTAINER_NAME="cups-verify-${STAMP}"
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

DATA_DIR="$(mktemp -d)"
cat > "${DATA_DIR}/options.json" <<'JSON'
{
  "avahi_reflector": false,
  "avahi_hostname": "cups-verify",
  "avahi_use_ipv6": false,
  "printers": [
    {"name": "testprinter", "uri": "ipp://192.0.2.10:631/ipp/print", "enabled": true}
  ],
  "log_level": "info"
}
JSON

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

cleanup() {
    if [[ "${KEEP}" == "0" ]]; then
        docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
        docker rmi "${IMAGE_NAME}" >/dev/null 2>&1 || true
        rm -rf "${DATA_DIR}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [[ ! -d "${ADDON_DIR}" ]]; then
    red "cups/ add-on directory not found: ${ADDON_DIR}"
    exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
    red "docker not found in PATH"
    exit 2
fi

BUILD_FROM=$(grep -E '^\s*amd64:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*amd64: "(.*)"/\1/')
VERSION=$(grep -E '^\s*VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*VERSION: "(.*)"/\1/')

yellow "Building ${IMAGE_NAME} from ${ADDON_DIR}/ (BUILD_FROM=${BUILD_FROM} VERSION=${VERSION})"
docker build -t "${IMAGE_NAME}" \
    --build-arg "BUILD_FROM=${BUILD_FROM}" \
    --build-arg "VERSION=${VERSION}" \
    "${ADDON_DIR}" >/dev/null
green "image built"

docker run --rm -d --name "${CONTAINER_NAME}" \
    -v "${DATA_DIR}:/data" \
    "${IMAGE_NAME}" >/dev/null

yellow "Waiting for cupsd inside the container to become ready..."
READY=0
for _ in $(seq 1 40); do
    if docker exec "${CONTAINER_NAME}" lpstat -r >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 1
done
if [[ "${READY}" != "1" ]]; then
    red "cupsd did not become ready in time"
    docker logs "${CONTAINER_NAME}" 2>&1 || true
    exit 1
fi
green "cupsd is ready"

# Give run.sh a moment to finish printer registration after cupsd came up.
sleep 2

FAIL=0

yellow "Checking /etc/avahi/avahi-daemon.conf..."
AVAHI_CONF=$(docker exec "${CONTAINER_NAME}" cat /etc/avahi/avahi-daemon.conf)
for assertion in "host-name=cups-verify" "use-ipv6=no" "enable-reflector=no"; do
    if echo "${AVAHI_CONF}" | grep -qF "${assertion}"; then
        green "   PASS: ${assertion}"
    else
        red "   FAIL: missing ${assertion}"
        FAIL=1
    fi
done

yellow "Checking printer registration..."
if docker exec "${CONTAINER_NAME}" lpstat -p testprinter 2>/dev/null | grep -q "testprinter"; then
    green "   PASS: testprinter registered"
else
    red "   FAIL: testprinter not registered"
    docker exec "${CONTAINER_NAME}" lpstat -p 2>&1 || true
    FAIL=1
fi

yellow "Checking for legacy-unicast reflector slot exhaustion (D-08)..."
CONTAINER_LOGS=$(docker logs "${CONTAINER_NAME}" 2>&1)
if echo "${CONTAINER_LOGS}" | grep -q "No slot available for legacy unicast reflection"; then
    red "   FAIL: reflector slot-exhaustion message present despite enable-reflector=no"
    FAIL=1
else
    green "   PASS: no reflector slot-exhaustion messages"
fi

if [[ "${FAIL}" == "1" ]]; then
    echo
    red "internal/verify-cups-scaffold.sh: FAILED"
    echo "--- container logs ---"
    echo "${CONTAINER_LOGS}"
    exit 1
fi

echo
green "internal/verify-cups-scaffold.sh: ALL CHECKS PASSED"
