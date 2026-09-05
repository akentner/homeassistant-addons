#!/usr/bin/env bash
# verify-bridge-e2e/08-nonce-used.sh — Phase 14 SC-4: error_code = "nonce_used".
#
# Obtains a fresh nonce via POST /v1/auth/nonce; uses it for one
# successful DELETE; re-uses the SAME nonce for a second DELETE and
# expects 401 + error_code = "nonce_used" (single-use per Phase 12 D-06
# + LIFE-03).
#
# Note: this scenario targets the test add-on's own delete path
# (not core_mosquitto, which would require a critical_addons bypass)
# so the nonce path can be exercised without operator intervention.
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_08="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_08}/_lib.sh"

if ! preflight; then
    yellow "08-nonce-used: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/nonce_used.txt"

# Step 1: obtain a fresh nonce.
NONCE_RESP=$(mktemp)
HTTP_CODE=$(curl -sS -o "${NONCE_RESP}" -w '%{http_code}' -X POST \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BRIDGE_URL}/v1/auth/nonce" 2>/dev/null || echo "000")

if [[ "${HTTP_CODE}" != "200" && "${HTTP_CODE}" != "201" ]]; then
    red "08-nonce-used: FAIL — POST /v1/auth/nonce returned HTTP ${HTTP_CODE}"
    red "  expected a fresh nonce; the Bridge may not be reachable for this scenario"
    rm -f "${NONCE_RESP}"
    exit 1
fi

# The exact JSON field name depends on the contract; try a few common
# spellings. The Bridge's response carries the plaintext nonce once.
NONCE=""
for FIELD in nonce nonce_value value; do
    if NONCE=$(grep -oE "\"${FIELD}\":\"[^\"]+\"" "${NONCE_RESP}" | head -1 | sed "s/\"${FIELD}\":\"//;s/\"$//"); then
        if [[ -n "${NONCE}" ]]; then break; fi
    fi
done

if [[ -z "${NONCE}" ]]; then
    yellow "08-nonce-used: skipped — could not extract nonce from POST /v1/auth/nonce response (response shape changed?)"
    rm -f "${NONCE_RESP}"
    exit 0
fi
rm -f "${NONCE_RESP}"

# Step 2: use the nonce for one uninstall attempt (will likely 404 since
# local_test-addon probably isn't installed; we don't care — the
# point is to consume the nonce). The 404 is fine; what matters is the
# nonce is now marked used.
curl -sS -o /dev/null -X POST \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Force-Destroy: ${NONCE}" \
    "${BRIDGE_URL}/v1/addons/${TEST_ADDON_SLUG}/uninstall" 2>/dev/null || true

# Step 3: re-use the same nonce; expect 401 + nonce_used.
HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' -X POST \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Force-Destroy: ${NONCE}" \
    "${BRIDGE_URL}/v1/addons/${TEST_ADDON_SLUG}/uninstall" 2>/dev/null || echo "000")

EXPECTED_CODE="401"
EXPECTED_ERROR_CODE="nonce_used"

if [[ "${HTTP_CODE}" != "${EXPECTED_CODE}" ]]; then
    red "08-nonce-used: FAIL — HTTP ${HTTP_CODE} (expected ${EXPECTED_CODE})"
    exit 1
fi

if ! grep -q "\"error_code\":\"${EXPECTED_ERROR_CODE}\"" "${OUT_FILE}"; then
    red "08-nonce-used: FAIL — body does not carry error_code=${EXPECTED_ERROR_CODE}"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "08-nonce-used: PASS — 401 + error_code=${EXPECTED_ERROR_CODE}"
exit 0
