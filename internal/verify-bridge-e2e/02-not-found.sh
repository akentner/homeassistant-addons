#!/usr/bin/env bash
# verify-bridge-e2e/02-not-found.sh — Phase 14 SC-4: error_code = "not_found".
#
# Sends GET /v1/addons/<random-nonexistent-slug>/info with the correct
# bearer and asserts the Bridge returns 404 + body.error_code == "not_found".
# The slug is suffixed with $(date +%s) so the test is repeatable across
# runs without ever colliding with a real add-on.
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_02="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_02}/_lib.sh"

if ! preflight; then
    yellow "02-not-found: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/not_found.txt"

NONEXISTENT_SLUG="nonexistent-slug-$(date +%s)"

HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BRIDGE_URL}/v1/addons/${NONEXISTENT_SLUG}/info" 2>/dev/null || echo "000")

EXPECTED_CODE="404"
EXPECTED_ERROR_CODE="not_found"

if [[ "${HTTP_CODE}" != "${EXPECTED_CODE}" ]]; then
    red "02-not-found: FAIL — HTTP ${HTTP_CODE} (expected ${EXPECTED_CODE})"
    exit 1
fi

if ! grep -q "\"error_code\":\"${EXPECTED_ERROR_CODE}\"" "${OUT_FILE}"; then
    red "02-not-found: FAIL — body does not carry error_code=${EXPECTED_ERROR_CODE}"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

if ! grep -q '"request_id"' "${OUT_FILE}"; then
    red "02-not-found: FAIL — body does not carry a request_id"
    exit 1
fi

green "02-not-found: PASS — 404 + error_code=${EXPECTED_ERROR_CODE} + request_id"
exit 0
