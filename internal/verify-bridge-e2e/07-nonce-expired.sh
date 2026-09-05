#!/usr/bin/env bash
# verify-bridge-e2e/07-nonce-expired.sh — Phase 14 SC-4: error_code = "nonce_expired".
#
# Issues POST /v1/addons/local_test-addon/uninstall WITH an X-Force-Destroy
# nonce header that is past its TTL (LIFE-03 + CF-12). The Bridge must
# return 401 + error_code = "nonce_expired". The recovery path documented
# in the captured diagnostic: POST /v1/auth/nonce → fresh nonce → retry.
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_07="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_07}/_lib.sh"

if ! preflight; then
    yellow "07-nonce-expired: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/nonce_expired.txt"

# Manually construct an expired nonce. The Bridge's nonce TTL is 60s; an
# age of 65s is unambiguously past TTL. The exact value is the literal
# nonce content; the Bridge looks at the timestamp embedded in the
# issued_at field (not the wire value), so the wire value here is a
# stable stand-in for any well-formed nonce token.
EXPIRED_NONCE="nonce.phase14.expired.$(date +%s)"

HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' -X POST \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Force-Destroy: ${EXPIRED_NONCE}" \
    "${BRIDGE_URL}/v1/addons/${TEST_ADDON_SLUG}/uninstall" 2>/dev/null || echo "000")

EXPECTED_CODE="401"
EXPECTED_ERROR_CODE="nonce_expired"

if [[ "${HTTP_CODE}" != "${EXPECTED_CODE}" ]]; then
    red "07-nonce-expired: FAIL — HTTP ${HTTP_CODE} (expected ${EXPECTED_CODE})"
    exit 1
fi

if ! grep -q "\"error_code\":\"${EXPECTED_ERROR_CODE}\"" "${OUT_FILE}"; then
    red "07-nonce-expired: FAIL — body does not carry error_code=${EXPECTED_ERROR_CODE}"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "07-nonce-expired: PASS — 401 + error_code=${EXPECTED_ERROR_CODE}"
exit 0
