#!/usr/bin/env bash
# verify-cups-avahi-guard.sh -- Phase 21 Plan 05 docker verifier for the avahi startup guard
# (cups/avahi-guard.sh) and its run.sh wiring. Builds the add-on image once, then runs the
# selected scenarios against real avahi-daemon / dbus-daemon processes:
#
#   claim      full add-on start: guard logs the claim, avahi's own log is visible, the claim is
#              logged before run.sh waits for cupsd, D-Bus reports the expected FQDN
#   lost       guard harness with the D-Bus query forced to a foreign host name: exactly three
#              attempts, then degrade-and-continue (RESULT=degraded, exit 0, avahi still running)
#   unsettled  guard harness with the query stuck in the "registering" state: one timeout line,
#              RESULT=unsettled, exit 0
#   refuse     full add-on start with avahi_hostname "cups-guard\n" (trailing newline): run.sh refuses
#              to start before any avahi/cupsd process, exits non-zero (CR-02, WR-04)
#
# Usage: bash internal/verify-cups-avahi-guard.sh [--keep] [--scenario NAME]...
# Exit: 0 all assertions passed, 1 an assertion failed, 2 usage/environment error.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADDON_DIR="${REPO_ROOT}/cups"

STAMP="$(date +%s)"
IMAGE_NAME="cups-guard-verify:${STAMP}"
CONTAINER_NAME="cups-guard-verify-${STAMP}"
KEEP=0
SCENARIOS=()
ALL_SCENARIOS=(claim lost unsettled refuse)

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

DATA_DIR="$(mktemp -d)"
FAIL=0

# shellcheck disable=SC2317,SC2329 # invoked through the EXIT trap
cleanup() {
    if [[ "${KEEP}" == "0" ]]; then
        docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
        docker rmi "${IMAGE_NAME}" >/dev/null 2>&1 || true
        rm -rf "${DATA_DIR}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep) KEEP=1 ;;
        --scenario)
            shift
            SCENARIOS+=("${1:-}")
            ;;
        *)
            red "unknown argument: $1"
            exit 2
            ;;
    esac
    shift
done
[[ ${#SCENARIOS[@]} -eq 0 ]] && SCENARIOS=("${ALL_SCENARIOS[@]}")


pass() { green "   PASS: $*"; }
fail() {
    red "   FAIL: $*"
    FAIL=1
}

# check DESCRIPTION CONDITION-COMMAND...  -- PASS when the command succeeds.
check() {
    local description="$1"
    shift
    if "$@"; then
        pass "${description}"
    else
        fail "${description}"
    fi
}

# write_options AVAHI_HOSTNAME_JSON_VALUE -- options fixture; the value is raw JSON (quotes included).
write_options() {
    cat >"${DATA_DIR}/options.json" <<JSON
{
  "avahi_hostname": $1,
  "avahi_use_ipv6": false,
  "avahi_reflector": false,
  "printers": [],
  "log_level": "warning"
}
JSON
}

# Line number of the first line in $1 (a log) matching fixed string $2; empty when absent.
line_of() {
    printf '%s\n' "$1" | grep -nF -- "$2" | head -n 1 | cut -d: -f1
}

# count_of LOG PATTERN -- number of lines containing the fixed string.
count_of() {
    printf '%s\n' "$1" | grep -cF -- "$2" || true
}

if [[ ! -d "${ADDON_DIR}" ]]; then
    red "cups/ add-on directory not found: ${ADDON_DIR}"
    exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
    red "docker not found in PATH"
    exit 2
fi
scenario_refuse() {
    yellow "Scenario refuse: avahi_hostname with a trailing newline"
    write_options '"cups-guard\n"'
    local out status
    out=$(timeout 90 docker run --rm -v "${DATA_DIR}:/data" "${IMAGE_NAME}" 2>&1)
    status=$?

    check "container exits non-zero (status ${status})" test "${status}" -ne 0
    check "output contains 'generate_config.py failed'" grep -qF 'generate_config.py failed' <<<"${out}"
    if grep -qF '[avahi-guard]' <<<"${out}"; then
        fail "output contains an [avahi-guard] line (avahi must not start)"
    else
        pass "output contains no [avahi-guard] line"
    fi
}

for scenario in "${SCENARIOS[@]}"; do
    case " ${ALL_SCENARIOS[*]} " in
        *" ${scenario} "*) ;;
        *)
            red "unknown scenario: ${scenario} (known: ${ALL_SCENARIOS[*]})"
            exit 2
            ;;
    esac
done

BUILD_FROM=$(grep -E '^\s*amd64:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*amd64: "(.*)"/\1/')
VERSION=$(grep -E '^\s*VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*VERSION: "(.*)"/\1/')

yellow "Building ${IMAGE_NAME} from ${ADDON_DIR}/ (BUILD_FROM=${BUILD_FROM} VERSION=${VERSION})"
BUILD_LOG="${DATA_DIR}/build.log"
if ! docker build -t "${IMAGE_NAME}" \
    --build-arg "BUILD_FROM=${BUILD_FROM}" \
    --build-arg "VERSION=${VERSION}" \
    "${ADDON_DIR}" >"${BUILD_LOG}" 2>&1; then
    cat "${BUILD_LOG}"
    red "docker build failed"
    exit 2
fi
green "image built"

# Guard harness: a throwaway container that starts dbus, renders the real config, sources the real
# guard library, optionally replaces avahi_guard_query, and prints the outcome. The query override
# comes from the GUARD_QUERY_OUT environment variable; all AVAHI_GUARD_* tunables are passed with -e.
run_harness() {
    local query_out="$1"
    shift
    # shellcheck disable=SC2016 # the harness script must not expand on the host
    timeout 180 docker run --rm --entrypoint bash \
        -v "${DATA_DIR}:/data" \
        -e "GUARD_QUERY_OUT=${query_out}" \
        "$@" \
        "${IMAGE_NAME}" -c '
set -e
mkdir -p /var/run/dbus /var/run/avahi-daemon
dbus-daemon --system --fork
python3 /generate_config.py >/dev/null
. /avahi-guard.sh
avahi_guard_query() { echo "${GUARD_QUERY_OUT}"; }
avahi_guard_start
echo "EXIT=$?"
echo "RESULT=${AVAHI_GUARD_RESULT}"
if pgrep avahi-daemon >/dev/null 2>&1; then echo "DAEMON=running"; else echo "DAEMON=gone"; fi
' 2>&1
}

scenario_claim() {
    yellow "Scenario claim: full add-on start"
    write_options '"cups-guard"'
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    docker run -d --name "${CONTAINER_NAME}" -v "${DATA_DIR}:/data" "${IMAGE_NAME}" >/dev/null

    local logs="" claimed=0
    for _ in $(seq 1 90); do
        logs=$(docker logs "${CONTAINER_NAME}" 2>&1)
        if grep -qF '[avahi-guard] RESULT: claimed' <<<"${logs}"; then
            claimed=1
            break
        fi
        sleep 1
    done
    # Let run.sh reach its cupsd wait so the ordering assertion has both lines.
    sleep 3
    logs=$(docker logs "${CONTAINER_NAME}" 2>&1)

    check "guard logged 'RESULT: claimed' within 90 s" test "${claimed}" = "1"
    check "guard logged 'hostname claimed: cups-guard.local'" \
        grep -qF '[avahi-guard] INFO: hostname claimed: cups-guard.local' <<<"${logs}"
    check "avahi's own startup line is visible in the add-on log" \
        grep -qF 'Server startup complete. Host name is cups-guard.local' <<<"${logs}"

    local claim_line cupsd_line
    claim_line=$(line_of "${logs}" 'hostname claimed')
    cupsd_line=$(line_of "${logs}" '[run.sh] waiting for cupsd')
    if [[ -n "${claim_line}" && -n "${cupsd_line}" && "${claim_line}" -lt "${cupsd_line}" ]]; then
        pass "claim (line ${claim_line}) is logged before the cupsd wait (line ${cupsd_line})"
    else
        fail "claim line (${claim_line:-none}) not before the cupsd wait line (${cupsd_line:-none})"
    fi

    local fqdn
    fqdn=$(docker exec "${CONTAINER_NAME}" dbus-send --system --print-reply --dest=org.freedesktop.Avahi \
        / org.freedesktop.Avahi.Server.GetHostNameFqdn 2>/dev/null || true)
    check "D-Bus GetHostNameFqdn prints cups-guard.local" grep -qF 'cups-guard.local' <<<"${fqdn}"

    local conf
    conf=$(docker exec "${CONTAINER_NAME}" cat /etc/avahi/avahi-daemon.conf 2>/dev/null || true)
    check "generated avahi-daemon.conf contains publish-aaaa-on-ipv4=no" \
        grep -qF 'publish-aaaa-on-ipv4=no' <<<"${conf}"

    # D-10: with avahi_use_ipv6 false no IPv6 address record may be registered. Only meaningful when the
    # container has a routable (neither link-local nor loopback) IPv6 address; otherwise report SKIP.
    local routable_v6
    routable_v6=$(docker exec "${CONTAINER_NAME}" cat /proc/net/if_inet6 2>/dev/null \
        | awk '$1 !~ /^fe80/ && $1 != "00000000000000000000000000000001" { print $1 }' | head -n 1)
    if [[ -z "${routable_v6}" ]]; then
        yellow "   SKIP: no routable IPv6 address in the container; IPv6 registration check not applicable"
    elif grep -qE 'Registering new address record for [0-9a-fA-F]*:[0-9a-fA-F:]* on' <<<"${logs}"; then
        fail "avahi registered an IPv6 address record although avahi_use_ipv6 is false"
    else
        pass "no IPv6 address record registered (routable IPv6 present: ${routable_v6})"
    fi

    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

scenario_lost() {
    yellow "Scenario lost: query forced to a foreign host name"
    write_options '"cups-guard"'
    local out
    out=$(run_harness '2|cups-guard-2.local' -e AVAHI_GUARD_BACKOFFS="1 1" -e AVAHI_GUARD_HOLD=1)

    local lost_count
    lost_count=$(count_of "${out}" 'hostname lost')
    check "exactly three 'hostname lost' lines (got ${lost_count})" test "${lost_count}" = "3"
    check "RESULT=degraded" grep -qxF 'RESULT=degraded' <<<"${out}"
    check "EXIT=0" grep -qxF 'EXIT=0' <<<"${out}"
    check "final 'giving up after 3 attempts' line" grep -qF 'giving up after 3 attempts' <<<"${out}"
    check "avahi-daemon still running" grep -qxF 'DAEMON=running' <<<"${out}"
}

scenario_unsettled() {
    yellow "Scenario unsettled: query stuck in the registering state"
    write_options '"cups-guard"'
    local out
    out=$(run_harness '1|cups-guard.local' \
        -e AVAHI_GUARD_SETTLE_TIMEOUT=3 -e AVAHI_GUARD_BACKOFFS="" -e AVAHI_GUARD_HOLD=1)

    local timeout_count
    timeout_count=$(count_of "${out}" 'did not reach the running state')
    check "one 'did not reach the running state' line (got ${timeout_count})" test "${timeout_count}" = "1"
    check "RESULT=unsettled" grep -qxF 'RESULT=unsettled' <<<"${out}"
    check "EXIT=0" grep -qxF 'EXIT=0' <<<"${out}"
}

for scenario in "${SCENARIOS[@]}"; do
    case "${scenario}" in
        claim) scenario_claim ;;
        lost) scenario_lost ;;
        unsettled) scenario_unsettled ;;
        refuse) scenario_refuse ;;
    esac
done

if [[ "${FAIL}" == "0" ]]; then
    green "RESULT: PASS"
else
    red "RESULT: FAIL"
fi
exit "${FAIL}"
