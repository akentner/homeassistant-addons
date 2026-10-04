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
#   isolation  full add-on start under the LAN-mDNS isolation (D-11, Plan 21-08): avahi claims its unique
#              throwaway name but joins no mDNS group on any interface except lo; a non-isolated control
#              container (unique name) must join, or the control is reported SKIP (never a vacuous PASS)
#
# Every container is started through internal/cups-test-isolation.sh: it refuses to start a container whose
# options.json lacks an explicit non-default avahi_hostname and switches multicast off on the container's
# interfaces, so a test container can never announce the live host name `cups.local` on the real LAN.
# Do not run this verifier while a live proof is in progress (Plan 21-10).
#
# Usage: bash internal/verify-cups-avahi-guard.sh [--keep] [--scenario NAME]...
# Exit: 0 all assertions passed, 1 an assertion failed, 2 usage/environment error.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADDON_DIR="${REPO_ROOT}/cups"
# shellcheck source=internal/cups-test-isolation.sh
. "${SCRIPT_DIR}/cups-test-isolation.sh"

STAMP="$(date +%s)"
IMAGE_NAME="cups-guard-verify:${STAMP}"
CONTAINER_NAME="cups-guard-verify-${STAMP}"
ISO_CONTAINER_NAME="cups-guard-verify-iso-${STAMP}"
CTL_CONTAINER_NAME="cups-guard-verify-ctl-${STAMP}"
KEEP=0
SCENARIOS=()
ALL_SCENARIOS=(claim lost unsettled refuse isolation)

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

DATA_DIR="$(mktemp -d)"
ISO_DATA_DIR="$(mktemp -d)"
CTL_DATA_DIR="$(mktemp -d)"
FAIL=0

# shellcheck disable=SC2317,SC2329 # invoked through the EXIT trap
cleanup() {
    if [[ "${KEEP}" == "0" ]]; then
        docker rm -f "${CONTAINER_NAME}" "${ISO_CONTAINER_NAME}" "${CTL_CONTAINER_NAME}" >/dev/null 2>&1 || true
        docker rmi "${IMAGE_NAME}" >/dev/null 2>&1 || true
        rm -rf "${DATA_DIR}" "${ISO_DATA_DIR}" "${CTL_DATA_DIR}" >/dev/null 2>&1 || true
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

# write_options AVAHI_HOSTNAME_JSON_VALUE [DIR] -- options fixture; the value is raw JSON (quotes included).
write_options() {
    cat >"${2:-${DATA_DIR}}/options.json" <<JSON
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
    out=$(CUPS_TEST_TIMEOUT=90 cups_isolated_run "${IMAGE_NAME}" --rm -v "${DATA_DIR}:/data" 2>&1)
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
    CUPS_TEST_TIMEOUT=180 cups_isolated_bash "${IMAGE_NAME}" '
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
' --rm \
        -v "${DATA_DIR}:/data" \
        -e "GUARD_QUERY_OUT=${query_out}" \
        "$@" 2>&1
}

# wait_for_claim CONTAINER -- poll up to 90 s for the guard's claim line; sets CLAIM_LOGS, returns 0 on claim.
wait_for_claim() {
    local container="$1" _
    CLAIM_LOGS=""
    for _ in $(seq 1 90); do
        CLAIM_LOGS=$(docker logs "${container}" 2>&1)
        if grep -qF '[avahi-guard] RESULT: claimed' <<<"${CLAIM_LOGS}"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# non_lo_joins LOG -- avahi "Joining mDNS multicast group" lines for any interface other than lo.
non_lo_joins() {
    local joins
    joins=$(grep -F 'Joining mDNS multicast group on interface' <<<"$1" || true)
    grep -vE 'on interface lo\.' <<<"${joins}" || true
}

scenario_claim() {
    yellow "Scenario claim: full add-on start"
    write_options '"cups-guard"'
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    cups_isolated_run "${IMAGE_NAME}" -d --name "${CONTAINER_NAME}" -v "${DATA_DIR}:/data" >/dev/null

    local logs="" claimed=0
    if wait_for_claim "${CONTAINER_NAME}"; then
        claimed=1
    fi
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

    # The D-10 IPv6 registration check lives in the isolation scenario's control container: an isolated
    # avahi registers no address records at all, so the check would pass vacuously here.

    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

# D-11: the isolated container joins no mDNS group on a real interface; a non-isolated control does.
scenario_isolation() {
    yellow "Scenario isolation: no LAN mDNS from a test container (D-11)"
    local iso_name ctl_name
    iso_name=$(cups_test_hostname iso)
    ctl_name=$(cups_test_hostname ctl)
    write_options "\"${iso_name}\"" "${ISO_DATA_DIR}"
    write_options "\"${ctl_name}\"" "${CTL_DATA_DIR}"
    docker rm -f "${ISO_CONTAINER_NAME}" "${CTL_CONTAINER_NAME}" >/dev/null 2>&1 || true

    cups_isolated_run "${IMAGE_NAME}" -d --name "${ISO_CONTAINER_NAME}" -v "${ISO_DATA_DIR}:/data" >/dev/null
    local claimed=0
    if wait_for_claim "${ISO_CONTAINER_NAME}"; then
        claimed=1
    fi
    check "isolated container: guard logged 'RESULT: claimed' within 90 s" test "${claimed}" = "1"

    local fqdn logs joins
    fqdn=$(docker exec "${ISO_CONTAINER_NAME}" dbus-send --system --print-reply --dest=org.freedesktop.Avahi \
        / org.freedesktop.Avahi.Server.GetHostNameFqdn 2>/dev/null || true)
    check "isolated container: avahi is running with the name ${iso_name}.local" \
        grep -qF "${iso_name}.local" <<<"${fqdn}"
    logs=$(docker logs "${ISO_CONTAINER_NAME}" 2>&1)
    joins=$(non_lo_joins "${logs}")
    if [[ -z "${joins}" ]]; then
        pass "isolated container: avahi joined no mDNS multicast group on any interface except lo"
    else
        fail "isolated container: avahi joined mDNS on a real interface: $(head -n 1 <<<"${joins}")"
    fi
    docker rm -f "${ISO_CONTAINER_NAME}" >/dev/null 2>&1 || true

    # Negative control: without the isolation avahi must join, otherwise the assertion above proves nothing.
    cups_lan_run "${IMAGE_NAME}" -d --name "${CTL_CONTAINER_NAME}" -v "${CTL_DATA_DIR}:/data" >/dev/null
    local ctl_claimed=0
    if wait_for_claim "${CTL_CONTAINER_NAME}"; then
        ctl_claimed=1
    fi
    sleep 3
    logs=$(docker logs "${CTL_CONTAINER_NAME}" 2>&1)
    joins=$(non_lo_joins "${logs}")
    if [[ "${ctl_claimed}" != "1" ]]; then
        fail "control container: guard did not log 'RESULT: claimed' within 90 s"
    elif [[ -n "${joins}" ]]; then
        pass "a non-isolated container does join mDNS (the assertion can fail): $(head -n 1 <<<"${joins}")"
    else
        yellow "   SKIP: control container joined no mDNS group -- this environment offers no multicast-capable non-loopback interface"
    fi

    # D-10 (moved from the claim scenario): with avahi_use_ipv6 false no IPv6 address record may be registered.
    # Only meaningful in a non-isolated container with a routable (neither link-local nor loopback) IPv6 address.
    local routable_v6
    routable_v6=$(docker exec "${CTL_CONTAINER_NAME}" cat /proc/net/if_inet6 2>/dev/null \
        | awk '$1 !~ /^fe80/ && $1 != "00000000000000000000000000000001" { print $1 }' | head -n 1)
    if [[ -z "${routable_v6}" ]]; then
        yellow "   SKIP: no routable IPv6 address in the control container; IPv6 registration check not applicable"
    elif grep -qE 'Registering new address record for [0-9a-fA-F]*:[0-9a-fA-F:]* on' <<<"${logs}"; then
        fail "avahi registered an IPv6 address record although avahi_use_ipv6 is false"
    else
        pass "no IPv6 address record registered (routable IPv6 present: ${routable_v6})"
    fi
    docker rm -f "${CTL_CONTAINER_NAME}" >/dev/null 2>&1 || true
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
        isolation) scenario_isolation ;;
    esac
done

if [[ "${FAIL}" == "0" ]]; then
    green "RESULT: PASS"
else
    red "RESULT: FAIL"
fi
exit "${FAIL}"
