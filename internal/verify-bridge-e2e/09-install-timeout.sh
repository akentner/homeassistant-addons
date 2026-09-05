#!/usr/bin/env bash
# verify-bridge-e2e/09-install-timeout.sh — Phase 14 SC-4: error_code = "install_timeout".
#
# Synthetic scenario per D-10. Provoking a real install_timeout requires
# N parallel installs to exhaust Supervisor's install job slots; the
# live host cannot tolerate this setup without operator coordination.
#
# This script therefore exits 0 with a `skipped` annotation per D-10
# and writes a stub to testdata/diagnostics/install_timeout.txt with
# the canonical "not empirically observed" header so Plan 03's DOCS.md
# troubleshooting entry remains traceable to the skip decision.

set -euo pipefail

SCRIPT_DIR_09="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_09}/_lib.sh"

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/install_timeout.txt"

cat > "${OUT_FILE}" <<'EOF'
[not empirically observed — synthetic scenario per D-10]
scenario: 09-install-timeout
skip_reason: would require N parallel installs to exhaust Supervisor's install job slots;
             the host cannot tolerate this setup without operator coordination.
expected_http: 504
expected_error_code: install_timeout
expected_summary_text: "Install polling exceeded the timeout; the Supervisor job may continue server-side."
remediation: lower install_job_timeout_seconds in the Bridge's options, or investigate why
             the Supervisor install is taking longer than expected (slow repository pull, etc.).
EOF

yellow "09-install-timeout: skipped — would require N parallel installs to exhaust Supervisor job slots"
exit 0
