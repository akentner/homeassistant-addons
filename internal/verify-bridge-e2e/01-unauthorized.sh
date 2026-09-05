#!/usr/bin/env bash
# verify-bridge-e2e/01-unauthorized.sh — Phase 14 SC-4: error_code = "unauthorized".
#
# Sends GET /v1/version with a deliberately wrong bearer token and asserts
# the Bridge returns 401 + body.error_code == "unauthorized". Captures the
# full response body to diagnostics/unauthorized.txt.
#
# Per D-10: when the preflight gate finds the Bridge unreachable, the
# script exits 0 with a `skipped — <reason>` annotation. Operators on a
# workstation that has the Bridge reachable (post-rebuild) get the
# empirical capture; everyone else gets a clean pass.

set -euo pipefail

SCRIPT_DIR_01="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_01}/_lib.sh"

if ! preflight; then
    yellow "01-unauthorized: skipped — preflight failed (see reasons above)"
    exit 0
fi

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/unauthorized.txt"

WRONG_TOKEN="phase-14-wrong-token-do-not-use-in-prod"

HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' \
    --max-time 10 \
    -H "Authorization: Bearer ${WRONG_TOKEN}" \
    "${BRIDGE_URL}/v1/version" 2>/dev/null || echo "000")

EXPECTED_CODE="401"
EXPECTED_ERROR_CODE="unauthorized"

if [[ "${HTTP_CODE}" != "${EXPECTED_CODE}" ]]; then
    red "01-unauthorized: FAIL — HTTP ${HTTP_CODE} (expected ${EXPECTED_CODE})"
    exit 1
fi

if ! grep -q "\"error_code\":\"${EXPECTED_ERROR_CODE}\"" "${OUT_FILE}"; then
    red "01-unauthorized: FAIL — body does not carry error_code=${EXPECTED_ERROR_CODE}"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "01-unauthorized: PASS — 401 + error_code=${EXPECTED_ERROR_CODE}"
exit 0
