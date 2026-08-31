#!/usr/bin/env bash
# verify-bridge-scaffold.sh — Phase 9 success-criterion smoke test for the
# terraform-bridge add-on scaffold. Mirrors the verify-*.sh pattern from
# earlier phases (verify-git-integration.sh, verify-ha-notify.sh).
#
# This script is the runnable evidence that the Phase 9 success criteria
# hold; its output is captured to 09-SUMMARY.md per D-17. Three stages:
#   Stage 1: build + assert image size + assert JSON line on stdout
#   Stage 2: SIGTERM drain (exit within 30s)
#   Stage 3: SIGHUP reopen (process stays alive)
#
# Usage:
#   ./internal/verify-bridge-scaffold.sh        # full run
#   ./internal/verify-bridge-scaffold.sh --keep # leave containers + image for debugging
#
# Required: docker, curl, jq (jq only for the JSON assertion).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BRIDGE_DIR="${REPO_ROOT}/terraform-bridge"

IMAGE_NAME="terraform-bridge:verify-$(date +%s)"
CONTAINER_NAME_1="terraform-bridge-sigterm"
CONTAINER_NAME_2="terraform-bridge-sighup"
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

cleanup() {
    if [[ "${KEEP}" == "0" ]]; then
        docker rm -f "${CONTAINER_NAME_1}" "${CONTAINER_NAME_2}" >/dev/null 2>&1 || true
        docker rmi  "${IMAGE_NAME}"                   >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# Pre-flight
if [[ ! -d "${BRIDGE_DIR}" ]]; then
    red "Bridge directory not found: ${BRIDGE_DIR}"
    red "Run /gsd-execute-phase 9 plan 01 first."
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    red "docker not found in PATH"
    exit 2
fi

BRIDGE_VERSION="$(grep -E '^[[:space:]]*VERSION:' "${BRIDGE_DIR}/build.yaml" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')"
yellow "Phase 9 scaffold verify — bridge version: ${BRIDGE_VERSION}"
echo

# Stage 1: build + size + JSON stdout assertion
yellow "Stage 1: docker build + size + first stdout line"
docker build -t "${IMAGE_NAME}" \
             --build-arg "BRIDGE_VERSION=${BRIDGE_VERSION}" \
             "${BRIDGE_DIR}" >/dev/null 2>&1

IMG_SIZE_HUMAN=$(docker images "${IMAGE_NAME}" --format '{{.Size}}')
IMG_SIZE_BYTES=$(docker images "${IMAGE_NAME}" --format '{{.Size}}' \
                 | python3 -c 'import sys; s=sys.stdin.read().strip(); v=float(s.split()[0]); u=s.split()[1].upper(); mult={"B":1,"KB":1024,"MB":1024**2,"GB":1024**3}; print(int(v*mult[u]))')
MAX_BYTES=$((30 * 1024 * 1024))
echo "   docker image size: ${IMG_SIZE_HUMAN} (${IMG_SIZE_BYTES} bytes; cap = ${MAX_BYTES})"
if (( IMG_SIZE_BYTES > MAX_BYTES )); then
    red "   FAIL: image exceeds the 30 MiB cap (OPS-05)"
    exit 1
fi
green "   PASS: image size within cap"

docker run --rm -d --name "${CONTAINER_NAME_1}" -p 8124:8124 "${IMAGE_NAME}"
sleep 1
curl -sS --max-time 5 http://localhost:8124/ > /tmp/_bridge-get_root.json
if ! jq -e '.bridge_version and .status and .msg' /tmp/_bridge-get_root.json >/dev/null; then
    red "   FAIL: GET / did not return the required JSON keys"
    cat /tmp/_bridge-get_root.json
    exit 1
fi
green "   PASS: GET / returns placeholder JSON"

CONTAINER_LOGS=$(docker logs "${CONTAINER_NAME_1}" 2>&1)
JSON_LINE_COUNT=$(echo "${CONTAINER_LOGS}" | grep -c '^{' || true)
echo "   container stdout JSON-line count: ${JSON_LINE_COUNT}"
if (( JSON_LINE_COUNT < 1 )); then
    red "   FAIL: container produced no JSON line on stdout"
    exit 1
fi
green "   PASS: container emitted structured log records"

# Stage 2: SIGTERM drain
yellow "Stage 2: SIGTERM drain (must exit within 30s)"
SIGTERM_START=$(date +%s)
docker kill --signal=SIGTERM "${CONTAINER_NAME_1}"
for _ in $(seq 1 30); do
    if ! docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME_1}" 2>/dev/null | grep -q true; then
        break
    fi
    sleep 1
done
SIGTERM_END=$(date +%s)
SIGTERM_DURATION=$((SIGTERM_END - SIGTERM_START))
echo "   drained in ${SIGTERM_DURATION}s (cap = 30s)"
if (( SIGTERM_DURATION > 30 )); then
    red "   FAIL: SIGTERM drain exceeded 30s deadline (OPS-02)"
    exit 1
fi
green "   PASS: SIGTERM drain completed within deadline"

# Stage 3: SIGHUP reopen (process stays alive)
yellow "Stage 3: SIGHUP reopen (process must stay alive)"
docker run --rm -d --name "${CONTAINER_NAME_2}" -p 8124:8124 "${IMAGE_NAME}"
sleep 1
docker kill --signal=SIGHUP "${CONTAINER_NAME_2}"
sleep 3
if docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME_2}" 2>/dev/null | grep -q true; then
    green "   PASS: container still running after SIGHUP (log reopen is non-fatal)"
else
    red "   FAIL: container exited after SIGHUP; SIGHUP must NOT terminate the process"
    docker logs "${CONTAINER_NAME_2}"
    exit 1
fi

echo
green "Phase 9 scaffold verify: ALL STAGES PASSED"
echo "Image size:       ${IMG_SIZE_HUMAN} (cap 30 MiB) — PASS"
echo "JSON stdout:      ${JSON_LINE_COUNT} JSON line(s) — PASS"
echo "SIGTERM drain:    ${SIGTERM_DURATION}s (cap 30s) — PASS"
echo "SIGHUP reopen:    process stayed alive — PASS"
