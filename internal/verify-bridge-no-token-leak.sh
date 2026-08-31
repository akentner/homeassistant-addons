#!/usr/bin/env bash
# verify-bridge-no-token-leak.sh — Phase 9+10 no-token-leak invariant (D-12 + AUTH-05 + OPS-01).
#
# Runs the Bridge container with a fake SUPERVISOR_TOKEN in the env,
# captures stdout for ~10 seconds, and asserts:
#   1. The captured output contains NONE of: SUPERVISOR_TOKEN, Bearer,
#      bridge_token (Phase 9 D-12 boundary check; AUTH-01 + AUTH-05).
#   2. The fake token value itself is absent from stdout (S-1).
#   3. The bridge.token.issued record's plaintext appears EXACTLY ONCE
#      (CF-02 positive control) — proves the single-emission invariant
#      without leaking the token to a downstream log path.
#   4. The actor_token_fp field in that record equals SHA-256[8] of the
#      plaintext — positive control that the fingerprint helper
#      agrees with a fresh SHA-256.
#   5. A GET / produced an OPS-01 request-log record carrying the
#      mandatory fields (route, method).

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

# Phase 10 strengthening (AUTH-05 + CF-02 + OPS-01):
# Adapted from the plan's original check, which injected the FAKE_TOKEN
# as the bridge's own plaintext via an env override that is NOT part of
# the bridge's production code. We instead parse the bridge.token.issued
# record that the bridge emits on first start, extract its plaintext +
# actor_token_fp fields, and assert:
#   - The actor_token_fp equals SHA-256[8] of the plaintext
#     (positive control on the fingerprint helper).
#   - The plaintext appears EXACTLY ONCE in stdout (CF-02 exactly-once
#     invariant; second emission would leak the token to a downstream
#     log path).
ISSUED_RECORD=$(echo "${CAPTURED}" | grep -F '"msg":"bridge.token.issued"' || true)
if [[ -z "${ISSUED_RECORD}" ]]; then
    red "   FAIL: no bridge.token.issued record in stdout (CF-02 expectation)"
    FAIL=1
else
    PLAINTEXT=$(echo "${ISSUED_RECORD}" | grep -oE '"plaintext":"[^"]*"' | head -1 | sed 's/^"plaintext":"//; s/"$//')
    ACTOR_FP=$(echo "${ISSUED_RECORD}" | grep -oE '"actor_token_fp":"[^"]*"' | head -1 | sed 's/^"actor_token_fp":"//; s/"$//')
    if [[ -z "${PLAINTEXT}" || -z "${ACTOR_FP}" ]]; then
        red "   FAIL: bridge.token.issued record missing plaintext or actor_token_fp field"
        FAIL=1
    else
        EXPECTED_FP=$(printf '%s' "${PLAINTEXT}" | sha256sum | cut -c1-16)
        if [[ "${EXPECTED_FP}" = "${ACTOR_FP}" ]]; then
            echo "   PASS: actor_token_fp matches SHA-256[8] of bridge plaintext (positive control)"
        else
            red "   FAIL: actor_token_fp (${ACTOR_FP}) != SHA-256[8](plaintext) (${EXPECTED_FP})"
            FAIL=1
        fi
        COUNT=$(echo "${CAPTURED}" | grep -F -c -- "${PLAINTEXT}" || true)
        if (( COUNT == 1 )); then
            echo "   PASS: bridge plaintext appears exactly once in stdout (CF-02)"
        else
            red "   FAIL: bridge plaintext appears ${COUNT} times in stdout (want 1; CF-02)"
            FAIL=1
        fi
    fi
fi

# OPS-01 record check: confirm RequestLogger emitted a JSON line for GET /
# carrying the route= and method= fields. The Authorization header value
# is asserted-absent upstream by the SUPERVISOR_TOKEN/Bearer pattern checks.
if echo "${CAPTURED}" | grep -q '"msg":"http.request"' \
   && echo "${CAPTURED}" | grep -q '"route":"/"' \
   && echo "${CAPTURED}" | grep -q '"method":"GET"'; then
    echo "   PASS: GET / produced an OPS-01 request-log record"
else
    red "   FAIL: no OPS-01 request-log record found for GET /"
    FAIL=1
fi

if (( FAIL == 1 )); then
    red "verify-bridge-no-token-leak: FAIL"
    exit 1
fi

green "verify-bridge-no-token-leak: PASS"
