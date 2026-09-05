#!/usr/bin/env bash
# verify-bridge-e2e/06-locked.sh — Phase 14 SC-4: error_code = "locked".
#
# Deliberately races two `tofu apply` operations against `local_test-addon`
# in parallel. The Bridge's per-slug mutex (CF-06, STATE-03) serializes
# them; the second one should succeed (NOT error 423 — that's the desired
# user-facing behavior, achieved via the Provider's try_lock_timeout
# middleware waiting on the in-flight op).
#
# This scenario proves the mutex works, not that 423 fires in normal
# Provider usage. The captured diagnostic is the SUCCESSFUL apply output
# from the racing scenario. The MapError switch maps 423 to "locked"
# when the per-slug mutex surface does fire (e.g. Supervisor's own
# slug-locked response during transient races).
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_06="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_06}/_lib.sh"

if ! preflight; then
    yellow "06-locked: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/locked.txt"

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
    dummy_setting = "default"
  }
}
EOF
)

WORK_DIR="/tmp/06-locked.work"
mkdir -p "${WORK_DIR}"
trap 'rm -rf "${WORK_DIR}"' EXIT

printf '%s\n' "${TF_CONTENT}" > "${WORK_DIR}/main.tf"

A_LOG="${WORK_DIR}/apply-a.log"
B_LOG="${WORK_DIR}/apply-b.log"

(
    cd "${WORK_DIR}"
    tofu init -upgrade -no-color >/dev/null 2>&1 || true

    # Race two applies in parallel. The per-slug mutex serializes; the
    # try_lock_timeout middleware waits. Both must exit 0.
    tofu apply -auto-approve -no-color \
        -var "bridge_url=${BRIDGE_URL}" \
        -var "bridge_token=${TOKEN}" > "${A_LOG}" 2>&1 &
    A_PID=$!

    tofu apply -auto-approve -no-color \
        -var "bridge_url=${BRIDGE_URL}" \
        -var "bridge_token=${TOKEN}" > "${B_LOG}" 2>&1 &
    B_PID=$!

    A_RC=0; wait "${A_PID}" || A_RC=$?
    B_RC=0; wait "${B_PID}" || B_RC=$?

    {
        echo "=== apply-A exit code: ${A_RC} ==="
        cat "${A_LOG}"
        echo ""
        echo "=== apply-B exit code: ${B_RC} ==="
        cat "${B_LOG}"
    } > "${OUT_FILE}"
)

# Both applies must succeed (mutex serializes; no destructive diff).
if grep -qE "Error|FAIL|another operation is in flight" "${OUT_FILE}"; then
    red "06-locked: FAIL — at least one apply raced into an error"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "06-locked: PASS — per-slug mutex serialized the racing applies without surface 423"
exit 0
