#!/usr/bin/env bash
# verify-bridge-e2e/04-prevented-destroy.sh — Phase 14 SC-4: error_code = "prevented_destroy".
#
# Embeds a `*.tf` with `lifecycle.prevent_destroy = true` on
# `homeassistant_addon.test` against `local_test-addon`, runs `tofu destroy`,
# and asserts the Provider's typed Diagnostic carries the
# `ErrPreventedDestroyText` Summary from
# `terraform-provider-homeassistant/internal/diagnostics/doc.go`.
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_04="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_04}/_lib.sh"

if ! preflight; then
    yellow "04-prevented-destroy: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/prevented_destroy.txt"

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

  lifecycle {
    prevent_destroy = true
  }
}
EOF
)

WORK_DIR="/tmp/04-prevented-destroy.work"
mkdir -p "${WORK_DIR}"
trap 'rm -rf "${WORK_DIR}"' EXIT

printf '%s\n' "${TF_CONTENT}" > "${WORK_DIR}/main.tf"

(
    cd "${WORK_DIR}"
    tofu init -upgrade -no-color >/dev/null 2>&1 || true
    # Run destroy; the Provider's typed Diagnostic should surface via stderr.
    tofu destroy -auto-approve -no-color \
        -var "bridge_url=${BRIDGE_URL}" \
        -var "bridge_token=${TOKEN}" \
        > "${OUT_FILE}" 2>&1 || true
)

EXPECTED_TEXT="lifecycle.prevent_destroy = true is set on this resource"
if ! grep -q "${EXPECTED_TEXT}" "${OUT_FILE}"; then
    red "04-prevented-destroy: FAIL — captured output does not carry the prevented_destroy Summary text"
    red "  expected: ${EXPECTED_TEXT}"
    red "  captured: ${OUT_FILE}"
    exit 1
fi

green "04-prevented-destroy: PASS — Diagnostic Summary matches ErrPreventedDestroyText"
exit 0
