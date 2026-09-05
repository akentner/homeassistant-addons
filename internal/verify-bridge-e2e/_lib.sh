#!/usr/bin/env bash
# verify-bridge-e2e/_lib.sh — Phase 14 verify-suite shared library.
#
# Single sourced helper for every scenario in internal/verify-bridge-e2e/.
# Defines the host + slug + testdata locations, the bearer-token retrieval
# path, the preflight gate (D-10), and the state-snapshot + state-fingerprint
# helpers (D-16 + D-17). Mirrors the structural template from
# internal/verify-bridge-no-token-leak.sh (color helpers, exit discipline).
#
# Operators override BRIDGE_HOST / BRIDGE_PORT / BRIDGE_TOKEN via the env
# when the default ha-nextgen.akentner.ts.net host is not reachable from
# the workstation running the scenario.

# Path constants (do NOT use set -euo pipefail — this is a library file;
# the scenarios that source it set their own strict mode).
SCRIPT_DIR_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Host identity — Phase 14 D-01 locked the live target.
BRIDGE_HOST="${BRIDGE_HOST:-ha-nextgen.akentner.ts.net}"
BRIDGE_PORT="${BRIDGE_PORT:-8124}"
BRIDGE_URL="https://${BRIDGE_HOST}:${BRIDGE_PORT}"

# Test add-on identity — Phase 14 D-05 locked the slug.
TEST_ADDON_SLUG="local_test-addon"

# Repo + testdata paths (Plan 02 captures here; Plan 01 only needs the dirs).
REPO_ROOT="$(cd "${SCRIPT_DIR_LIB}/../.." && pwd)"
TESTDATA_DIR="${REPO_ROOT}/terraform-bridge/internal/testdata"

# Color helpers — verbatim from internal/verify-bridge-no-token-leak.sh.
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

# BRIDGE_TOKEN retrieval — Phase 10 CF-01 + Phase 14 D-08. Operators with
# the Bearer already in the env override via BRIDGE_TOKEN=...; the default
# path SSHes into the host and cats /usr/share/hassio/addons/data/terraform-
# bridge/initial-token (the Supervisor-managed location for the Bridge's
# /data mount). Failure is FATAL — the scenario cannot proceed with a
# missing or unreadable token.
retrieve_bridge_token() {
    if [[ -n "${BRIDGE_TOKEN:-}" ]]; then
        printf '%s' "${BRIDGE_TOKEN}"
        return 0
    fi

    local ssh_target
    ssh_target="${BRIDGE_HOST%.akentner.ts.net}"

    if ! command -v ssh >/dev/null 2>&1; then
        red "BRIDGE_TOKEN not set and 'ssh' not available on PATH"
        red "  remediation: set BRIDGE_TOKEN=<bearer> in the environment, then re-run"
        return 1
    fi

    local token
    if ! token="$(ssh -o BatchMode=yes -o ConnectTimeout=5 "${ssh_target}" \
            'cat /usr/share/hassio/addons/data/terraform-bridge/initial-token 2>/dev/null' \
            2>/dev/null)"; then
        red "failed to read /usr/share/hassio/addons/data/terraform-bridge/initial-token via ssh ${ssh_target}"
        red "  remediation: ensure SSH key auth works to ${ssh_target} OR set BRIDGE_TOKEN=<bearer> in env"
        return 1
    fi

    if [[ -z "${token}" ]]; then
        red "/data/initial-token on ${ssh_target} is empty (Bridge may not have started yet)"
        red "  remediation: start the Bridge add-on once so it writes /data/initial-token, then re-run"
        return 1
    fi

    printf '%s' "${token}"
}

# snapshot_state <scenario> — Phase 14 D-16. Copies the live
# /data/terraform.tfstate to /data/terraform.tfstate.bak.<scenario> via SSH.
# No-op when the live state file does not yet exist.
snapshot_state() {
    local scenario="$1"
    local ssh_target
    ssh_target="${BRIDGE_HOST%.akentner.ts.net}"

    ssh -o BatchMode=yes -o ConnectTimeout=5 "${ssh_target}" \
        "cp -f /data/terraform.tfstate /data/terraform.tfstate.bak.${scenario} 2>/dev/null || true" \
        2>/dev/null
}

# fingerprint_state <scenario> <when> — Phase 14 D-17. Calls
# GET /v1/state/index on the Bridge and writes the response to
# ${TESTDATA_DIR}/state-fingerprints/<scenario>-<when>.json.
fingerprint_state() {
    local scenario="$1"
    local when="$2"
    local token
    local out_dir="${TESTDATA_DIR}/state-fingerprints"
    local out_file="${out_dir}/${scenario}-${when}.json"

    mkdir -p "${out_dir}"

    token="$(retrieve_bridge_token)" || return 1

    if ! curl -fsS --max-time 10 \
            -H "Authorization: Bearer ${token}" \
            "${BRIDGE_URL}/v1/state/index" \
            -o "${out_file}" 2>/dev/null; then
        yellow "fingerprint_state: GET /v1/state/index failed (${scenario}-${when})"
        return 1
    fi
    return 0
}

# cleanup_scenario_baks — Phase 14 D-18. Removes /data/terraform.tfstate.bak.*
# files older than 7 days. NOT called by individual scenarios; Plan 03's
# 99-cleanup.sh owns the invocation. Defined here for proximity to
# snapshot_state.
cleanup_scenario_baks() {
    local ssh_target
    ssh_target="${BRIDGE_HOST%.akentner.ts.net}"

    ssh -o BatchMode=yes -o ConnectTimeout=5 "${ssh_target}" \
        "find /data -maxdepth 1 -name 'terraform.tfstate.bak.*' -mtime +7 -delete 2>/dev/null || true" \
        2>/dev/null
}

# preflight — Phase 14 D-10 gate. Checks the three prerequisites every
# scenario needs to actually exercise the live Bridge: `tofu` on PATH, the
# Provider binary built and installed, and the Bridge's /healthz endpoint
# returns 200. Returns 0 when all three pass; non-zero otherwise. Scenarios
# translate the non-zero into an exit 0 with a `skipped — <reason>`
# annotation (so the executor's pre-build environment and the operator's
# pre-rebuild workstation both see a clean pass instead of an unrelated
# CI failure).
preflight() {
    local reasons=()

    if ! command -v tofu >/dev/null 2>&1; then
        reasons+=("tofu not on PATH (install OpenTofu \u2265 1.12)")
    fi

    local provider_bin="${REPO_ROOT}/terraform-provider-homeassistant/terraform-provider-homeassistant"
    if [[ ! -x "${provider_bin}" ]]; then
        reasons+=("Provider binary not built at ${provider_bin} (run 'make install-provider')")
    fi

    if ! curl -fsS --max-time 5 -o /dev/null \
            "${BRIDGE_URL}/healthz" 2>/dev/null; then
        reasons+=("Bridge /healthz unreachable at ${BRIDGE_URL}")
    fi

    if (( ${#reasons[@]} > 0 )); then
        printf 'preflight failed:\n'
        for r in "${reasons[@]}"; do
            printf '  - %s\n' "${r}"
        done
        return 1
    fi
    return 0
}
