#!/usr/bin/env bash
# spike-h1-token-rotation.sh — Phase 9 H-1 (PITFALLS §H-1):
# does the per-add-on SUPERVISOR_TOKEN rotate across a Supervisor restart?
#
# Empirical evidence per CONTEXT.md D-15. Gates Phase 10 auth design
# (cache-at-startup vs re-read-per-call — see D-18).
#
# Approach: read SUPERVISOR_TOKEN from /proc/1/environ of any running
# add-on container on the host (chosen by --addon), capture the
# sha256 fingerprint (NEVER the value), restart Supervisor, recapture,
# compare fingerprints. The hash-before vs hash-after is the empirical
# answer. SHA-256 fingerprints are non-reversible, so the transcript
# can be shared without leaking the actual token value (PITFALLS S-1).
#
# PRE-APPROVED in /gsd-discuss-phase. Per AGENTS.md Live Systems rule,
# the script's service-disrupting action (ha supervisor restart) is
# announced in the output BEFORE the command runs.
#
# Usage: ./internal/spike-h1-token-rotation.sh [haos-host [addon-slug]]
# Defaults: host=haos-op3050-1, addon=72a005f5_phone-logger
#
# Output: verbatim shell transcript at /tmp/spike-h1-<run-id>.log (also
# streamed to stdout). Token values never appear; only sha256 fingerprints.

set -euo pipefail

HOST="${1:-haos-op3050-1}"
ADDON_SLUG="${2:-72a005f5_phone-logger}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
TRANSCRIPT="/tmp/spike-h1-${RUN_ID}.log"

exec > >(tee -a "${TRANSCRIPT}") 2>&1

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
blue()   { printf '\033[0;34m%s\033[0m\n' "$*"; }

blue "================================================================"
blue "H-1 SPIKE — Phase 9 SUPERVISOR_TOKEN rotation across Supervisor restart"
blue "================================================================"
blue "Host:       ${HOST}"
blue "Target:     ${ADDON_SLUG}"
blue "Run ID:     ${RUN_ID}"
blue "Transcript: ${TRANSCRIPT}"
blue ""
blue "SERVICE-DISRUPTING — restarts HA Supervisor on ${HOST}."
blue "Every add-on restarts; HA Core restarts; live automations pause"
blue "for ~30s + add-on respawn. Run only with explicit user approval"
blue "(AGENTS.md Live Systems rule)."
blue ""

# Resolve the running docker container name for the add-on. HA Supervisor
# names add-on containers 'app_<slug>'. Verify the add-on is running first.
green "Pre-flight: verify ${ADDON_SLUG} is running on ${HOST}"
CONTAINER_NAME="app_${ADDON_SLUG}"
if ! ssh "${HOST}" "sudo docker ps --format '{{.Names}}' | grep -qx '${CONTAINER_NAME}'"; then
    red "  Container ${CONTAINER_NAME} is not running on ${HOST}"
    red "  Start the add-on (ha addons start ${ADDON_SLUG}) or pass a different slug."
    echo "RESULT: inconclusive"
    exit 1
fi
green "  Container ${CONTAINER_NAME} is running"

# Capture the SUPERVISOR_TOKEN fingerprint from inside the add-on container.
# We use 'docker exec ... env' (root on host) instead of reading /proc/1/environ
# because some container runtimes make /proc/<pid>/environ unreadable from
# inside the container's PID namespace even with --privileged.
CAPTURE_TOKEN() {
    local raw=""
    raw="$(ssh "${HOST}" "sudo docker exec ${CONTAINER_NAME} env" 2>/dev/null \
        | grep '^SUPERVISOR_TOKEN=' || true)"
    raw="${raw#SUPERVISOR_TOKEN=}"
    if [[ -z "${raw}" ]]; then
        echo ""
        return 1
    fi
    printf '%s' "${raw}" | sha256sum | cut -d' ' -f1
}

# Step 1: BEFORE fingerprint
blue ""
blue "Step 1: capture SUPERVISOR_TOKEN fingerprint BEFORE Supervisor restart"
BEFORE_FP="$(CAPTURE_TOKEN BEFORE || true)"
BEFORE_TS="$(date -u +%FT%TZ)"
if [[ -z "${BEFORE_FP}" ]]; then
    red "  BEFORE: token capture FAILED (empty)"
    echo "RESULT: inconclusive"
    exit 1
fi
green "  BEFORE: sha256=${BEFORE_FP}  at ${BEFORE_TS}"

# Step 2: Supervisor restart (SERVICE-DISRUPTING)
blue ""
blue "Step 2: ha supervisor restart (SERVICE-DISRUPTING)"
yellow "  Sleeping 10s before issuing restart — press Ctrl+C NOW if you have NOT"
yellow "  announced this run to the user / on-call."
sleep 10
green "  ssh ${HOST} sudo ha supervisor restart"
ssh "${HOST}" sudo ha supervisor restart 2>&1 || yellow "  (restart returned non-zero — Supervisor may already be restarting)"
green "Supervisor restart issued at $(date -u +%FT%TZ)"

# Step 3: wait for Supervisor + add-on to come back
blue ""
blue "Step 3: wait for Supervisor + add-on to come back online"
yellow "  Polling for Supervisor availability (max 120s)..."
WAITED=0
MAX_WAIT=120
SUPERVISOR_UP=""
while [[ ${WAITED} -lt ${MAX_WAIT} ]]; do
    if ssh "${HOST}" "sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^hassio_supervisor$'" 2>/dev/null; then
        SUPERVISOR_UP=yes
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    yellow "    ...${WAITED}s elapsed"
done
if [[ -z "${SUPERVISOR_UP}" ]]; then
    red "  Supervisor did not come back within ${MAX_WAIT}s"
    echo "RESULT: inconclusive"
    exit 1
fi
green "  Supervisor back online after ${WAITED}s"

# Wait for our target add-on container to respawn
yellow "  Waiting for ${CONTAINER_NAME} to respawn (max 60s)..."
WAITED=0
ADDON_UP=""
while [[ ${WAITED} -lt 60 ]]; do
    if ssh "${HOST}" "sudo docker ps --format '{{.Names}}'" 2>/dev/null | grep -qx "${CONTAINER_NAME}"; then
        ADDON_UP=yes
        break
    fi
    sleep 3
    WAITED=$((WAITED + 3))
done
if [[ -z "${ADDON_UP}" ]]; then
    red "  ${CONTAINER_NAME} did not respawn within 60s after Supervisor restart"
    echo "RESULT: inconclusive"
    exit 1
fi
green "  ${CONTAINER_NAME} respawned after ${WAITED}s"

# Give Supervisor a few more seconds to inject the new token
sleep 5

# Step 4: AFTER fingerprint
blue ""
blue "Step 4: capture SUPERVISOR_TOKEN fingerprint AFTER Supervisor restart"
AFTER_FP="$(CAPTURE_TOKEN AFTER || true)"
AFTER_TS="$(date -u +%FT%TZ)"
if [[ -z "${AFTER_FP}" ]]; then
    red "  AFTER: token capture FAILED (empty)"
    echo "RESULT: inconclusive"
    exit 1
fi
green "  AFTER:  sha256=${AFTER_FP}  at ${AFTER_TS}"

# Step 5: compare
blue ""
blue "Step 5: compare fingerprints"
if [[ "${BEFORE_FP}" == "${AFTER_FP}" ]]; then
    RESULT="token_unchanged"
    green "  before sha256: ${BEFORE_FP}  at ${BEFORE_TS}"
    green "  after  sha256: ${AFTER_FP}  at ${AFTER_TS}"
    green "  IDENTICAL — Supervisor did NOT rotate the per-add-on token across restart."
    green ""
    green "RESULT: ${RESULT}"
    blue ""
    blue "  D-18 implication: Phase 10 auth design MAY cache the token at startup."
    blue "  (Both designs are Phase-9-compatible; caching is the cheaper default.)"
else
    RESULT="token_rotated"
    yellow "  before sha256: ${BEFORE_FP}  at ${BEFORE_TS}"
    yellow "  after  sha256: ${AFTER_FP}  at ${AFTER_TS}"
    yellow "  DIFFERENT — Supervisor DID rotate the per-add-on token across restart."
    yellow ""
    yellow "RESULT: ${RESULT}"
    blue ""
    blue "  D-18 implication: Phase 10 auth design MUST re-read"
    blue "  os.Getenv('SUPERVISOR_TOKEN') on every outbound Supervisor call"
    blue "  (cheap) AND log bridge.token_rotated=true when the value changes"
    blue "  mid-process. Plan 03's signals.go SIGHUP handler is the natural hook."
fi
TIME_DELTA_S=$(($(date -d "${AFTER_TS}" +%s) - $(date -d "${BEFORE_TS}" +%s)))
green ""
green "Time delta before/after capture: ${TIME_DELTA_S} seconds"
echo ""
echo "TRANSCRIPT DONE: ${TRANSCRIPT}"
echo "RESULT: ${RESULT}"
