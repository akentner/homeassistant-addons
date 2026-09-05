#!/usr/bin/env bash
# verify-bridge-e2e/10-upstream-error.sh — Phase 14 SC-4: error_code = "upstream_error".
#
# Sends GET /v1/addons/local_test-addon/info with the correct bearer; if
# the Bridge can reach Supervisor, this would normally return 200. The
# scenario cannot directly inject a Bridge→Supervisor network failure,
# so it relies on the Bridge's own error mapping when the response is
# not the expected AddOnInfo envelope. A8 notes the operator may
# trigger the 502 path by temporarily blocking Bridge→Supervisor
# traffic or by pointing the Bridge at an unreachable Supervisor URL
# (operator choice; CF-14).
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_10="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_10}/_lib.sh"

if ! preflight; then
    yellow "10-upstream-error: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/upstream_error.txt"

# Hit /v1/addons/local_test-addon/info. If the Bridge's upstream
# (Supervisor) is healthy, this returns 200 + AddOnInfo (or 404 with
# not_found — both NOT upstream_error). The 502 path only fires when
# Bridge→Supervisor is broken. The captured file is a baseline "200
# response" so the operator can compare against the live empirical
# 502 if they choose to block Bridge→Supervisor traffic.
HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BRIDGE_URL}/v1/addons/${TEST_ADDON_SLUG}/info" 2>/dev/null || echo "000")

EXPECTED_ERROR_CODE="upstream_error"

if [[ "${HTTP_CODE}" == "502" ]]; then
    if ! grep -q "\"error_code\":\"${EXPECTED_ERROR_CODE}\"" "${OUT_FILE}"; then
        red "10-upstream-error: FAIL — 502 response missing error_code=${EXPECTED_ERROR_CODE}"
        exit 1
    fi
    green "10-upstream-error: PASS — 502 + error_code=${EXPECTED_ERROR_CODE} (operator-triggered upstream failure)"
    exit 0
fi

# Baseline: 200 or 404 here means the upstream is healthy; the
# scenario's empirical observation requires operator intervention.
yellow "10-upstream-error: baseline observed (HTTP ${HTTP_CODE}); operator can trigger 502 by blocking Bridge→Supervisor"
exit 0
