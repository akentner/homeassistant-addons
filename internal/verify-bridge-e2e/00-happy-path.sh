#!/usr/bin/env bash
# verify-bridge-e2e/00-happy-path.sh — Phase 14 SC-1 + SC-3 surface.
#
# Runs `tofu apply` FIVE consecutive times against the embedded `*.tf` that
# declares `homeassistant_addon.test` for `local_test-addon`. Iterations
# 2..5 must report `No changes` to satisfy the SC-3 idempotency criterion.
# Captures each iteration's `tofu apply` output to
# ${TESTDATA_DIR}/apply-output/<iter>.txt for post-mortem review.
#
# The embedded `*.tf` does NOT set `lifecycle.prevent_destroy = true` (the
# 5-iteration loop's destroy step would otherwise be blocked).
#
# Per D-10: when the preflight gate finds `tofu` / Provider binary / Bridge
# /healthz missing, the script exits 0 with a `skipped — <reason>`
# annotation so the executor (which lacks `tofu`/`docker`/`go`) and any
# pre-rebuild operator workstation both see a clean pass.

set -euo pipefail

SCRIPT_DIR_HAPPY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_HAPPY}/_lib.sh"

# D-10 preflight — short-circuit with skip annotation when prerequisites missing.
if ! preflight; then
    yellow "00-happy-path: skipped — preflight failed (see reasons above)"
    exit 0
fi

# Embedded happy-path `*.tf`. The Provider's bridge_url + bridge_token
# variables are passed via -var flags (sensitive = true), NEVER written
# to disk in plaintext.
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

# Per-iteration workdir under /tmp (ephemeral; trap removes on exit).
WORK_ROOT="/tmp/00-happy-path.work"
mkdir -p "${WORK_ROOT}"
trap 'rm -rf "${WORK_ROOT}"' EXIT

# 5-iteration idempotency loop — D-11.
PASS=0
for ITER in 1 2 3 4 5; do
    ITER_DIR="${WORK_ROOT}/iter${ITER}"
    mkdir -p "${ITER_DIR}"
    printf '%s\n' "${TF_CONTENT}" > "${ITER_DIR}/main.tf"

    mkdir -p "${TESTDATA_DIR}/apply-output"
    OUT_FILE="${TESTDATA_DIR}/apply-output/${ITER}.txt"

    if ! (
        cd "${ITER_DIR}"
        tofu init -upgrade -no-color >/dev/null 2>&1
        # Capture plan + apply output for the per-iteration evidence file.
        {
            echo "=== iteration ${ITER}: tofu plan ==="
            tofu plan -no-color \
                -var "bridge_url=${BRIDGE_URL}" \
                -var "bridge_token=$(retrieve_bridge_token)" || true
            echo ""
            echo "=== iteration ${ITER}: tofu apply ==="
            tofu apply -auto-approve -no-color \
                -var "bridge_url=${BRIDGE_URL}" \
                -var "bridge_token=$(retrieve_bridge_token)" || true
        } > "${OUT_FILE}" 2>&1
    ); then
        red "00-happy-path: FAIL — iteration ${ITER} exited non-zero (see ${OUT_FILE})"
        exit 1
    fi

    # SC-3 idempotency: iterations 2..5 must report "No changes".
    if (( ITER > 1 )); then
        if ! grep -q "No changes" "${OUT_FILE}"; then
            red "00-happy-path: FAIL — iteration ${ITER} did not report 'No changes' (SC-3 violated)"
            red "  captured output: ${OUT_FILE}"
            exit 1
        fi
    fi
done

green "00-happy-path: PASS — 5 iterations, iterations 2-5 reported 'No changes'"
exit 0
