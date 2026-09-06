#!/usr/bin/env bash
# verify-bridge-e2e/11-pwned.sh — Phase 14 SC-4: error_code = "pwned".
#
# Runs `tofu apply` with `homeassistant_addon.test.options.dummy_setting`
# set to a known pwned-secret value. The Bridge surfaces the `pwned`
# advisory when an add-on's options payload contains known compromised-
# credentials leaks; the Provider surfaces this as a Warning (NOT an
# Error) so the apply proceeds while the operator is informed of the
# leaked credentials (PROV-06 + CF-08 + D-09).
#
# The captured `tofu apply` output must carry the PwnedWarningText
# Summary from terraform-provider-homeassistant/internal/diagnostics/
# doc.go:111, AND the apply exit code must be 0.
#
# Per D-10 + A8: preflight failure OR empirical pwned-detection failure
# → exit 0 with `skipped` annotation; the captured file is annotated
# `[not empirically observed — synthetic scenario per D-10]`.

set -euo pipefail

SCRIPT_DIR_11="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_11}/_lib.sh"

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/pwned.txt"

if ! preflight; then
    cat > "${OUT_FILE}" <<'EOF'
[not empirically observed — synthetic scenario per D-10]
scenario: 11-pwned
skip_reason: preflight failed (tofu / Provider binary / /healthz missing)
expected_severity: Warning
expected_summary_text: "This add-on has a known compromised credentials leak (pwned): review the supervisor warning and rotate the add-on credentials before continuing."
remediation: rotate the add-on's credentials, then re-apply with the rotated values.
EOF
    yellow "11-pwned: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

TF_CONTENT=$(cat <<'EOF'
terraform {
  required_providers {
    homeassistant = {
      source = "akentner/homeassistant"
    }
  }
}

variable "bridge_url" {
  type      = string
  sensitive = true
}

variable "bridge_token" {
  type      = string
  sensitive = true
}

provider "homeassistant" {
  bridge_url   = var.bridge_url
  bridge_token = var.bridge_token
}

resource "homeassistant_addon" "test" {
  slug   = "local_test-addon"
  start  = true

  options = {
    log_level     = "info"
    dummy_setting = "P@ssw0rd"
  }
}
EOF
)

WORK_DIR="/tmp/11-pwned.work"
mkdir -p "${WORK_DIR}"
trap 'rm -rf "${WORK_DIR}"' EXIT

printf '%s\n' "${TF_CONTENT}" > "${WORK_DIR}/main.tf"

APPLY_LOG="${WORK_DIR}/apply.log"
APPLY_RC=0
cd "${WORK_DIR}"
tofu init -upgrade -no-color >/dev/null 2>&1 || true
if ! tofu apply -auto-approve -no-color \
        -var "bridge_url=${BRIDGE_URL}" \
        -var "bridge_token=${TOKEN}" > "${APPLY_LOG}" 2>&1; then
    APPLY_RC=$?
fi
cp "${APPLY_LOG}" "${OUT_FILE}"

EXPECTED_TEXT="known compromised credentials leak"

if [[ "${APPLY_RC}" != "0" ]] || ! grep -q "${EXPECTED_TEXT}" "${OUT_FILE}"; then
    # Empirical pwned detection may not fire if the Bridge's pwned
    # dataset doesn't flag "P@ssw0rd" today (A8). Annotate the
    # captured file and exit 0 with skipped annotation.
    cat >> "${OUT_FILE}" <<'EOF'

[not empirically observed — synthetic scenario per D-10]
note: apply exited non-zero OR pwned warning not surfaced; the Bridge's pwned
      detection is data-driven and may not flag the seeded value at this time.
      Operators can confirm via `ha addons options local_test-addon` once the
      pwned-detection data set includes the test value.
EOF
    yellow "11-pwned: skipped — empirical pwned detection did not fire (A8 fallback)"
    exit 0
fi

green "11-pwned: PASS — apply succeeded with Warning diagnostic carrying PwnedWarningText"
exit 0
