#!/usr/bin/env bash
# spike-h1-token-rotation.sh — Phase 9 H-1 (PITFALLS §H-1): does the
# per-add-on SUPERVISOR_TOKEN rotate across a Supervisor restart?
#
# Empirical evidence per CONTEXT.md D-15. This script exists to answer a
# LOW-confidence research question that gates every later v1.3 phase
# (PITFALLS H-1 → D-18 contingency → Phase 10 auth design).
#
# PRE-APPROVED in /gsd-discuss-phase as the procedure. Per AGENTS.md Live
# Systems rule, each live-system action is announced in the executor's
# output BEFORE the command runs. This script does NOT auto-execute on a
# fresh checkout — run it manually after announcing each step.
#
# Usage: ./internal/spike-h1-token-rotation.sh [haos-host]
# Default host: haos-op3050-1
#
# Output: verbatim shell transcript at /tmp/spike-h1-<run-id>.log (also
# streamed to stdout). The transcript contains ONLY sha256 fingerprints
# of the captured tokens, never the values themselves — satisfies
# PITFALLS S-1 even if the transcript is shared.

set -euo pipefail

HOST="${1:-haos-op3050-1}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
TRANSCRIPT="/tmp/spike-h1-${RUN_ID}.log"
STUB_SLUG="terraform-bridge-spike"

exec > >(tee -a "${TRANSCRIPT}") 2>&1

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
blue()   { printf '\033[0;34m%s\033[0m\n' "$*"; }

# Cleanup trap — uninstalls the stub add-on on any exit (success, error, or signal).
# Service-disrupting notice is in the script header for anyone reading the script
# (not just the run output).
cleanup() {
    local exit_code=$?
    yellow ""
    yellow "── Cleanup: uninstalling stub add-on (if installed) ──"
    ssh "${HOST}" sudo ha addons uninstall "${STUB_SLUG}" >/dev/null 2>&1 || true
    ssh "${HOST}" sudo rm -f "/tmp/${STUB_SLUG}.yaml" >/dev/null 2>&1 || true
    exit "${exit_code}"
}
trap cleanup EXIT

blue "================================================================"
blue "H-1 SPIKE — Phase 9 SUPERVISOR_TOKEN rotation across Supervisor restart"
blue "================================================================"
blue "Host:      ${HOST}"
blue "Run ID:    ${RUN_ID}"
blue "Transcript: ${TRANSCRIPT}"
blue ""
blue "⚠️  SERVICE-DISRUPTING — this script restarts HA Supervisor on ${HOST}."
blue "    Every add-on on that host restarts; HA Core restarts; live automations"
blue "    pause for ~30s + add-on respawn time. Run only when the user has"
blue "    explicitly approved a Supervisor restart (per AGENTS.md Live Systems rule)."
blue ""
yellow "Press Ctrl+C within 5s to abort if you have NOT announced this run yet..."
sleep 5
green ""
green "Announcement elapsed — proceeding."

# ── Step 1: build the stub image locally, push to host, install via Supervisor API ─
blue ""
blue "── Step 1: build & ship stub terraform-bridge image ──"
green "  docker build -t terraform-bridge-spike:latest terraform-bridge/"
docker build -t "terraform-bridge-spike:latest" \
             --build-arg "BRIDGE_VERSION=0.1.0" \
             terraform-bridge/ 2>&1 | tail -20
green ""
green "  docker save ... | ssh ${HOST} docker load"
docker save "terraform-bridge-spike:latest" | ssh "${HOST}" docker load
green ""
green "Step 1 complete: stub image built locally and loaded on ${HOST}."

# ── Step 1b: build a stub add-on config so Supervisor can install it ──────────────
blue ""
blue "── Step 1b: build a stub add-on config pointing at the loaded image ──"
green "  stub config: /tmp/${STUB_SLUG}.yaml"
cat > /tmp/${STUB_SLUG}.yaml <<EOF
name: "Spike Stub"
description: "H-1 spike stub for SUPERVISOR_TOKEN rotation test"
version: "0.0.1-0"
slug: "${STUB_SLUG}"
arch:
  - amd64
url: "https://github.com/akentner/homeassistant-addons"
startup: "application"
boot: "manual"
host_network: false
hassio_api: true
hassio_role: manager
ports: {}
options: {}
schema: {}
map:
  - type: addon_config
    read_only: false
    path: /addon_config
EOF
scp /tmp/${STUB_SLUG}.yaml "${HOST}:/tmp/"
green "Step 1b complete: stub config shipped to ${HOST}."

# ── Step 2: install stub via Supervisor store/install API ─────────────────────────
blue ""
blue "── Step 2: install stub via Supervisor (${STUB_SLUG}) ──"
green "  ssh ${HOST} sudo ha addons install 'local_terraform-bridge-spike:latest' || true"
# The Supervisor install path is one of:
#   (a) 'ha addons install <repository>_<slug>:<tag>' if a repo is configured
#   (b) Manual Supervisor API call: POST /api/store/repositories then POST /api/addons/<slug>/install
#   (c) 'ha addons install <image>' for registry-loaded local images
# Per D-15, the 'ha addons install' CLI over SSH is the simplest. The exact
# reference varies by Supervisor version; we try the common forms and accept
# failure on the install attempt — the stub add-on may already be installed
# from a prior spike run, or the Supervisor API may reject the local image
# reference. The script's RESULT is independent of install success because
# we only need ONE running stub container to capture SUPERVISOR_TOKEN.
ssh "${HOST}" sudo ha addons install "local_${STUB_SLUG}:latest" || yellow "  (install command returned non-zero — stub may already be installed or local registry path differs)"
sleep 3
green "  ssh ${HOST} sudo ha addons start ${STUB_SLUG}"
ssh "${HOST}" sudo ha addons start "${STUB_SLUG}" || yellow "  (start returned non-zero — add-on may already be running or install failed)"
sleep 5
green "Step 2 complete: stub start attempted. Verifying add-on is running..."
ssh "${HOST}" sudo ha addons info "${STUB_SLUG}" || yellow "  (info command failed; SUPERVISOR_TOKEN capture will fail if the add-on is not running)"

# ── Step 3: capture SUPERVISOR_TOKEN from inside the stub container ──────────────
blue ""
blue "── Step 3: capture SUPERVISOR_TOKEN BEFORE Supervisor restart ──"
# /proc/1/environ is the kernel's view of PID 1 (the add-on's entrypoint).
# NULL-separated, so 'tr \\0 \\n' converts to one line per env var.
# We capture the sha256 fingerprint of the value, never the value itself,
# so the transcript can be shared without leaking the token.
CAPTURE_TOKEN() {
    local raw=""
    raw="$(ssh "${HOST}" sudo ha addons stdin "${STUB_SLUG}" \
        sh -c 'tr "\0" "\n" < /proc/1/environ | grep "^SUPERVISOR_TOKEN=" || true')"
    raw="${raw#SUPERVISOR_TOKEN=}"
    if [[ -z "${raw}" ]]; then
        echo ""
    else
        printf '%s' "${raw}" | sha256sum | cut -d' ' -f1
    fi
}

BEFORE_FP="$(CAPTURE_TOKEN)"
BEFORE_TS="$(date -u +%FT%TZ)"
if [[ -z "${BEFORE_FP}" ]]; then
    red "  ✗ BEFORE: token capture FAILED (empty result from stdin)"
    red "  This usually means the stub add-on is not running. See 'ha addons info ${STUB_SLUG}' above."
    echo "RESULT: inconclusive"
    exit 1
fi
green "  ✓ BEFORE: captured sha256=${BEFORE_FP} at ${BEFORE_TS}"

# ── Step 4: Supervisor restart (SERVICE-DISRUPTING) ──────────────────────────────
blue ""
blue "── Step 4: ⚠️  ha supervisor restart (SERVICE-DISRUPTING) ──"
yellow "  Sleeping 5s before issuing restart — press Ctrl+C NOW if you have NOT"
yellow "  announced this run to the user / on-call."
sleep 5
green "  ssh ${HOST} sudo ha supervisor restart"
ssh "${HOST}" sudo ha supervisor restart || red "  (restart returned non-zero; Supervisor may already be restarting)"
green "Supervisor restart issued at $(date -u +%FT%TZ)"
yellow "Waiting 60s for Supervisor to come back + add-on respawn + token re-injection..."
sleep 60

# ── Step 5: capture SUPERVISOR_TOKEN AFTER restart ───────────────────────────────
blue ""
blue "── Step 5: capture SUPERVISOR_TOKEN AFTER Supervisor restart ──"
# Add-on should respawn automatically (boot: manual may prevent auto-start;
# restart explicitly to be safe).
green "  ssh ${HOST} sudo ha addons start ${STUB_SLUG}"
ssh "${HOST}" sudo ha addons start "${STUB_SLUG}" 2>&1 || yellow "  (start failed; add-on may already be running)"
sleep 5
AFTER_FP="$(CAPTURE_TOKEN)"
AFTER_TS="$(date -u +%FT%TZ)"
if [[ -z "${AFTER_FP}" ]]; then
    red "  ✗ AFTER: token capture FAILED (empty result from stdin)"
    red "  Supervisor may not have re-injected the token yet, or the add-on did not respawn."
    echo "RESULT: inconclusive"
    exit 1
fi
green "  ✓ AFTER:  captured sha256=${AFTER_FP}  at ${AFTER_TS}"

# ── Step 6: compare fingerprints ─────────────────────────────────────────────────
blue ""
blue "── Step 6: compare fingerprints ──"
if [[ "${BEFORE_FP}" == "${AFTER_FP}" ]]; then
    RESULT="token_unchanged"
    green "  before sha256: ${BEFORE_FP}  at ${BEFORE_TS}"
    green "  after  sha256: ${AFTER_FP}  at ${AFTER_TS}"
    green "  → IDENTICAL — Supervisor did NOT rotate the per-add-on token across restart."
    green ""
    green "RESULT: ${RESULT}"
    blue ""
    blue "  D-18 implication: Phase 10 auth design MAY cache the token at startup."
    blue "  (Both designs are Phase-9-compatible; caching is the cheaper default.)"
else
    RESULT="token_rotated"
    yellow "  before sha256: ${BEFORE_FP}  at ${BEFORE_TS}"
    yellow "  after  sha256: ${AFTER_FP}  at ${AFTER_TS}"
    yellow "  → DIFFERENT — Supervisor DID rotate the per-add-on token across restart."
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