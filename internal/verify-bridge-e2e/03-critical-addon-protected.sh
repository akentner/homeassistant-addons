#!/usr/bin/env bash
# verify-bridge-e2e/03-critical-addon-protected.sh — Phase 14 SC-4: error_code = "critical_addon_protected".
#
# Issues POST /v1/addons/core_mosquitto/uninstall WITHOUT an X-Force-Destroy
# nonce. The Bridge's critical_addons list contains core_mosquitto by
# default; without the nonce, the Bridge must refuse with 403 +
# error_code = "critical_addon_protected" (LIFE-03 + CF-12).
#
# DO NOT modify the Bridge's critical_addons to include local_test-addon —
# the verify suite needs to uninstall the test add-on between iterations
# (Pitfall 4).

set -euo pipefail

SCRIPT_DIR_03="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_03}/_lib.sh"

if ! preflight; then
    yellow "03-critical-addon-protected: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/critical_addon_protected.txt"

HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' -X POST \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BRIDGE_URL}/v1/addons/core_mosquitto/uninstall" 2>/dev/null || echo "000")

EXPECTED_CODE="403"
EXPECTED_ERROR_CODE="critical_addon_protected"

if [[ "${HTTP_CODE}" != "${EXPECTED_CODE}" ]]; then
    red "03-critical-addon-protected: FAIL — HTTP ${HTTP_CODE} (expected ${EXPECTED_CODE})"
    exit 1
fi

if ! grep -q "\"error_code\":\"${EXPECTED_ERROR_CODE}\"" "${OUT_FILE}"; then
    red "03-critical-addon-protected: FAIL — body does not carry error_code=${EXPECTED_ERROR_CODE}"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "03-critical-addon-protected: PASS — 403 + error_code=${EXPECTED_ERROR_CODE}"
exit 0
