#!/usr/bin/env bash
# verify-bridge-e2e/05-already-installed.sh — Phase 14 SC-4: error_code = "already_installed".
#
# Runs `tofu apply` TWICE consecutively against `local_test-addon`.
# Iteration 1 installs; iteration 2 (adoption-aware per PROV-05) reports
# `already_installed` to the Provider, which treats it as success and
# re-Reads the state (Create falls through to GET info). Captures
# iteration-2's `tofu apply` output and asserts the apply succeeded
# with no destructive diff.
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_05="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_05}/_lib.sh"

if ! preflight; then
    yellow "05-already-installed: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/already_installed.txt"

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

WORK_DIR="/tmp/05-already-installed.work"
mkdir -p "${WORK_DIR}"
trap 'rm -rf "${WORK_DIR}"' EXIT

printf '%s\n' "${TF_CONTENT}" > "${WORK_DIR}/main.tf"

ITER1_LOG="${WORK_DIR}/iter1.log"
ITER2_LOG="${WORK_DIR}/iter2.log"

(
    cd "${WORK_DIR}"
    tofu init -upgrade -no-color >/dev/null 2>&1 || true

    # Iteration 1: install. Capture for post-mortem only; we assert against iter 2.
    if ! tofu apply -auto-approve -no-color \
            -var "bridge_url=${BRIDGE_URL}" \
            -var "bridge_token=${TOKEN}" > "${ITER1_LOG}" 2>&1; then
        red "05-already-installed: FAIL — iteration 1 (install) failed"
        red "  log: ${ITER1_LOG}"
        exit 1
    fi

    # Iteration 2: adoption path. The Provider's adoption flow (Phase 12
    # D-26) treats `already_installed` as success. Apply must exit 0
    # and the diff must be empty.
    if ! tofu apply -auto-approve -no-color \
            -var "bridge_url=${BRIDGE_URL}" \
            -var "bridge_token=${TOKEN}" > "${ITER2_LOG}" 2>&1; then
        red "05-already-installed: FAIL — iteration 2 (adoption) failed"
        red "  log: ${ITER2_LOG}"
        exit 1
    fi
)

cp "${ITER2_LOG}" "${OUT_FILE}"

# Iteration 2 must report no changes (adoption sees the resource already
# present, so the plan is empty / reports "No changes").
if ! grep -qE "No changes|already installed|adoption" "${OUT_FILE}"; then
    red "05-already-installed: FAIL — iteration 2 did not report No changes / adoption"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "05-already-installed: PASS — adoption path: iteration 2 reported no destructive diff"
exit 0
