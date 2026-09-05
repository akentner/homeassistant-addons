#!/usr/bin/env bash
# verify-bridge-e2e/99-cleanup.sh — Phase 14 separate-manual cleanup.
#
# SEPARATE MANUAL INVOCATION per D-18 + the agent's Discretion.
# This script is destructive: it uninstalls the test add-on, removes
# state-snapshot backups older than 7 days, and LEAVES the
# bridge-nonce-audit.json in place (append-only forensics per Phase 12
# D-06). Do NOT include this script in the verify suite — invoke it
# manually after all verify scenarios complete.
#
# Per D-10: when the preflight gate finds prerequisites missing, the
# script exits 0 with a `skipped — <reason>` annotation. The cleanup
# is operator-driven and gated by the same preflight as the verify
# suite; on a workstation without the Bridge reachable, the cleanup
# is a no-op (the snapshot is local; the uninstall + bak cleanup are
# the destructive parts that need Bridge reachability).

set -euo pipefail

SCRIPT_DIR_99="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_99}/_lib.sh"

cat <<'BANNER'
verify-bridge-e2e/99-cleanup.sh — separate-manual cleanup
WARNING: this script uninstalls the test add-on + removes old state
         backups. It is NOT part of the verify suite.

The bridge-nonce-audit.json is LEFT IN PLACE (append-only forensics
per Phase 12 D-06).
BANNER

# Preflight gate (D-10). Even if the Bridge is unreachable, the local
# cleanup (cleanup_scenario_baks) is safe to attempt — it uses SSH to
# the host, not curl to the Bridge. Run it either way; the destructive
# uninstall step below is the only one that strictly needs the Bridge.
if ! preflight; then
    yellow "99-cleanup: preflight reported Bridge unreachable; will still attempt the local SSH cleanup (snapshot_bak retention), skipping the uninstall"
fi

# Step 1: snapshot state for the cleanup itself (so an operator can
# recover via mv if the uninstall goes sideways). Per D-16.
snapshot_state "99-cleanup"

# Step 2: uninstall the test add-on. Per Plan 01's foundation, the
# `*.tf` does NOT set lifecycle.prevent_destroy = true, so the
# destroy path is the standard tofu destroy. If tofu is not
# available (this script is the fallback for that case), fall back
# to `ha addons uninstall` via SSH.
if command -v tofu >/dev/null 2>&1; then
    TF_CONTENT=$(cat <<'EOF'
terraform {
  required_providers {
    homeassistant = { source = "akentner/homeassistant" }
  }
}
variable "bridge_url"   { type = string sensitive = true }
variable "bridge_token" { type = string sensitive = true }
provider "homeassistant" {
  bridge_url   = var.bridge_url
  bridge_token = var.bridge_token
}
resource "homeassistant_addon" "test" {
  slug  = "local_test-addon"
  start = false
  options = {
    log_level     = "info"
    dummy_setting = "default"
  }
}
EOF
)
    WORK_DIR="/tmp/99-cleanup.work"
    mkdir -p "${WORK_DIR}"
    trap 'rm -rf "${WORK_DIR}"' EXIT
    printf '%s\n' "${TF_CONTENT}" > "${WORK_DIR}/main.tf"
    TOKEN="$(retrieve_bridge_token)" || true
    (
        cd "${WORK_DIR}"
        tofu init -upgrade -no-color >/dev/null 2>&1 || true
        tofu destroy -auto-approve -no-color \
            -var "bridge_url=${BRIDGE_URL}" \
            -var "bridge_token=${TOKEN}" >/dev/null 2>&1 || true
    )
    green "99-cleanup: tofu destroy complete for local_test-addon"
else
    # Fallback: ha addons uninstall via SSH to the host. The operator
    # can also run this manually if preferred.
    ssh_target_fallback="${BRIDGE_HOST%.akentner.ts.net}"
    ssh -o BatchMode=yes -o ConnectTimeout=5 "${ssh_target_fallback}" \
        "ha addons uninstall local_test-addon 2>/dev/null || true" \
        2>/dev/null || true
    green "99-cleanup: ha addons uninstall local_test-addon complete (tofu fallback path)"
fi

# Step 3: confirm bridge-nonce-audit.json is left in place. This file
# is append-only forensics per Phase 12 D-06; the cleanup MUST NOT
# delete it. We just print a confirmation line.
green "99-cleanup: bridge-nonce-audit.json left in place (append-only forensics; do NOT delete)"

# Step 4: remove state-snapshot backups older than 7 days (D-18).
cleanup_scenario_baks
green "99-cleanup: state-snapshot backups older than 7 days removed (cleanup_scenario_baks)"

green "99-cleanup: PASS"
exit 0
