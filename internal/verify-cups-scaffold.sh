#!/usr/bin/env bash
# verify-cups-scaffold.sh -- Phase 21 Plan 01 tracer smoke test for the cups/
# add-on. Proves the generated /etc/avahi/avahi-daemon.conf carries the
# D-07/D-10/D-11 fixes and that one fixture printer registers via lpadmin
# against a live cupsd. Mirrors verify-bridge-scaffold.sh /
# verify-litellm-scaffold.sh (DATA_DIR + options.json fixture, docker build,
# docker run -v mount, trap cleanup).
#
# Usage: bash internal/verify-cups-scaffold.sh [--keep]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# CUPS_ADDON_DIR points the test at a modified copy of cups/ (used to prove the checks can fail).
ADDON_DIR="${CUPS_ADDON_DIR:-${REPO_ROOT}/cups}"

STAMP="$(date +%s)"
IMAGE_NAME="cups-verify:${STAMP}"
CONTAINER_NAME="cups-verify-${STAMP}"
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

DATA_DIR="$(mktemp -d)"
cat > "${DATA_DIR}/options.json" <<'JSON'
{
  "avahi_reflector": false,
  "avahi_hostname": "cups-verify",
  "avahi_use_ipv6": false,
  "server_aliases": "cups-verify.example.ts.net",
  "admin_username": "verifyadmin",
  "admin_password": "verify-secret-pw",
  "printers": [
    {"name": "testprinter", "uri": "ipp://192.0.2.10:631/ipp/print", "enabled": true, "location": "Office"},
    {"name": "brlasertest", "uri": "socket://192.0.2.20:9100", "enabled": true, "driver": "brlaser", "driver_model": "MFC-7460DN"}
  ],
  "log_level": "info"
}
JSON

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

cleanup() {
    if [[ "${KEEP}" == "0" ]]; then
        docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
        docker rmi "${IMAGE_NAME}" >/dev/null 2>&1 || true
        rm -rf "${DATA_DIR}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [[ ! -d "${ADDON_DIR}" ]]; then
    red "cups/ add-on directory not found: ${ADDON_DIR}"
    exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
    red "docker not found in PATH"
    exit 2
fi

BUILD_FROM=$(grep -E '^\s*amd64:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*amd64: "(.*)"/\1/')
VERSION=$(grep -E '^\s*VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*VERSION: "(.*)"/\1/')

yellow "Building ${IMAGE_NAME} from ${ADDON_DIR}/ (BUILD_FROM=${BUILD_FROM} VERSION=${VERSION})"
docker build -t "${IMAGE_NAME}" \
    --build-arg "BUILD_FROM=${BUILD_FROM}" \
    --build-arg "VERSION=${VERSION}" \
    "${ADDON_DIR}" >/dev/null
green "image built"

# Identical flags for the first start and for the recreation in the UUID-stability section.
start_container() {
    docker run --rm -d --name "${CONTAINER_NAME}" \
        -v "${DATA_DIR}:/data" \
        "${IMAGE_NAME}" >/dev/null
}

start_container

yellow "Waiting for cupsd inside the container to become ready..."
READY=0
for _ in $(seq 1 40); do
    if docker exec "${CONTAINER_NAME}" lpstat -r >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 1
done
if [[ "${READY}" != "1" ]]; then
    red "cupsd did not become ready in time"
    docker logs "${CONTAINER_NAME}" 2>&1 || true
    exit 1
fi
green "cupsd is ready"

# Give run.sh a moment to finish printer registration after cupsd came up.
# Polls rather than a fixed sleep: run.sh's own registration retry loop (up
# to 5 attempts x 1s on a transient lpadmin connection error -- observed here
# once the brlaser fixture below added a second, slower registration pass
# doing its own live `lpinfo -m` query) can outlast a short fixed sleep.
REG_SETTLED=0
for _ in $(seq 1 15); do
    if docker exec "${CONTAINER_NAME}" lpstat -v testprinter >/dev/null 2>&1 \
        && docker exec "${CONTAINER_NAME}" lpstat -v brlasertest >/dev/null 2>&1; then
        REG_SETTLED=1
        break
    fi
    sleep 1
done
[[ "${REG_SETTLED}" == "1" ]] || yellow "   NOTE: printer registration did not settle within 15s -- checks below may still fail"

FAIL=0

yellow "Checking /etc/avahi/avahi-daemon.conf..."
AVAHI_CONF=$(docker exec "${CONTAINER_NAME}" cat /etc/avahi/avahi-daemon.conf)
for assertion in "host-name=cups-verify" "use-ipv6=no" "enable-reflector=no"; do
    if echo "${AVAHI_CONF}" | grep -qF "${assertion}"; then
        green "   PASS: ${assertion}"
    else
        red "   FAIL: missing ${assertion}"
        FAIL=1
    fi
done

# allow-interfaces= is auto-detected at container startup from the default
# route in /proc/net/route (see generate_config.py's detect_primary_interface
# docstring) -- the exact interface name depends on Docker's own network
# assignment for this container, so only the KEY's presence is asserted, not a
# specific value.
if echo "${AVAHI_CONF}" | grep -qE '^allow-interfaces='; then
    green "   PASS: allow-interfaces= present (auto-detected primary interface)"
else
    red "   FAIL: missing allow-interfaces= -- avahi would listen on all interfaces"
    FAIL=1
fi

yellow "Checking /etc/cups/cupsd.conf network-scope fix..."
CUPSD_CONF=$(docker exec "${CONTAINER_NAME}" cat /etc/cups/cupsd.conf)
# In this test container (bridge network, not host_network), the interface
# detected via /proc/net/route is the container's own veth/eth0 -- a real,
# non-loopback IP assigned by Docker's network. Asserting it is no longer the
# stock "Listen localhost:631" line is sufficient proof the patch applied;
# proving actual LAN reachability requires the real haos-op3050-1 host.
if echo "${CUPSD_CONF}" | grep -qE '^Listen [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:631$'; then
    green "   PASS: cupsd Listen bound to a detected interface IP, not localhost-only"
else
    red "   FAIL: cupsd Listen is still localhost-only (or missing/malformed) -- AirPrint and the web UI would be unreachable from the LAN"
    FAIL=1
fi
if echo "${CUPSD_CONF}" | grep -qE '^\s*Allow from [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$'; then
    green "   PASS: top-level <Location /> scoped to the detected LAN subnet"
else
    red "   FAIL: missing 'Allow from <subnet>' in the top-level <Location /> block"
    FAIL=1
fi
if echo "${CUPSD_CONF}" | grep -A3 '<Location /admin>' | grep -q 'Require user @SYSTEM'; then
    green "   PASS: /admin still requires @SYSTEM auth (network scoping did not touch auth)"
else
    red "   FAIL: /admin auth requirement missing or altered -- this must never change"
    FAIL=1
fi

yellow "Checking cupsd LogLevel reflects the configured log_level option..."
# run.sh's own cupsctl call (step 9) has a 5x1s retry loop around the same
# transient "Unable to connect to server: Bad file descriptor" race
# lpadmin's step-7 retry already guards against -- poll rather than check
# once, so this does not race that retry window.
LOG_LEVEL_APPLIED=0
for _ in $(seq 1 10); do
    if docker exec "${CONTAINER_NAME}" grep -qE '^LogLevel info$' /etc/cups/cupsd.conf; then
        LOG_LEVEL_APPLIED=1
        break
    fi
    sleep 1
done
if [[ "${LOG_LEVEL_APPLIED}" == "1" ]]; then
    green "   PASS: cupsd.conf LogLevel reflects the fixture's configured log_level=info"
else
    red "   FAIL: cupsd.conf LogLevel does not reflect log_level=info"
    docker exec "${CONTAINER_NAME}" grep -i '^LogLevel' /etc/cups/cupsd.conf || true
    FAIL=1
fi

yellow "Checking cupsd error_log passthrough into the add-on's own log output..."
# Log-tail forwarding only starts after run.sh's UUID-fixup restart cycle
# (steps 6-8) completes -- steps 9-12 (log-level mapping + tail setup) run
# on the SECOND (post-fixup) cupsd instance. Poll rather than check once,
# since the fixup cycle's own stop/patch/restart takes a few seconds past
# this main container's initial (pre-fixup) readiness wait above.
ERROR_LOG_SEEN=0
for _ in $(seq 1 40); do
    # Captured into a variable, then grepped, rather than piping `docker
    # logs` directly into `grep -q` -- under this script's `set -o
    # pipefail`, `grep -q` exiting early on a match sends SIGPIPE to a
    # still-writing `docker logs`, which then reports a non-zero (141)
    # pipeline exit despite the match being found, making the `if` always
    # take the else branch. Capturing first avoids the live pipe entirely.
    MAIN_LOGS_SNAPSHOT=$(docker logs "${CONTAINER_NAME}" 2>&1)
    if echo "${MAIN_LOGS_SNAPSHOT}" | grep -qE '^[EWID] \['; then
        ERROR_LOG_SEEN=1
        break
    fi
    sleep 1
done
if [[ "${ERROR_LOG_SEEN}" == "1" ]]; then
    green "   PASS: cupsd error_log lines appear in the add-on's own log output"
else
    red "   FAIL: no cupsd error_log lines found in the add-on's own log output within 40s"
    FAIL=1
fi
if echo "${MAIN_LOGS_SNAPSHOT}" | grep -qE '"(GET|POST|PUT|HEAD) '; then
    red "   FAIL: access_log lines appear despite log_level=info (should only tail at the debug tier)"
    FAIL=1
else
    green "   PASS: access_log not tailed at the non-debug log_level=info fixture"
fi

yellow "Checking debug-tier log_level additionally tails access_log (separate lightweight container)..."
DEBUG_DATA_DIR="$(mktemp -d)"
python3 -c "
import json
with open('${DATA_DIR}/options.json') as f:
    d = json.load(f)
d['log_level'] = 'debug'
with open('${DEBUG_DATA_DIR}/options.json', 'w') as f:
    json.dump(d, f)
"
DEBUG_CONTAINER_NAME="${CONTAINER_NAME}-debug"
docker run --rm -d --name "${DEBUG_CONTAINER_NAME}" -v "${DEBUG_DATA_DIR}:/data" "${IMAGE_NAME}" >/dev/null
DEBUG_READY=0
for _ in $(seq 1 40); do
    if docker exec "${DEBUG_CONTAINER_NAME}" lpstat -r >/dev/null 2>&1; then
        DEBUG_READY=1
        break
    fi
    sleep 1
done
if [[ "${DEBUG_READY}" != "1" ]]; then
    red "   FAIL: debug-tier container did not become ready"
    FAIL=1
else
    # As in the main container's UUID-fixup cycle above: lpstat -r reports
    # the FIRST (pre-fixup) cupsd instance. Log-tail forwarding (run.sh
    # steps 9-12) only starts on the SECOND (post-fixup) instance, so wait
    # for run.sh's own post-fixup readiness log line before generating a
    # request and checking for tail evidence -- otherwise this reads the
    # pre-fixup instance's (tail-less) state.
    DEBUG_POST_FIXUP_SEEN=0
    for _ in $(seq 1 40); do
        # See the main container's error_log check above for why this
        # captures into a variable first rather than piping `docker logs`
        # straight into `grep -q` (pipefail + early-exit SIGPIPE).
        DEBUG_LOGS_SNAPSHOT=$(docker logs "${DEBUG_CONTAINER_NAME}" 2>&1)
        if echo "${DEBUG_LOGS_SNAPSHOT}" | grep -qF "cupsd is ready (post-fixup restart)"; then
            DEBUG_POST_FIXUP_SEEN=1
            break
        fi
        sleep 1
    done
    if [[ "${DEBUG_POST_FIXUP_SEEN}" != "1" ]]; then
        red "   FAIL: debug-tier container's post-fixup cupsd instance did not become ready within 40s"
        docker logs "${DEBUG_CONTAINER_NAME}" 2>&1 || true
        FAIL=1
    else
        docker exec "${DEBUG_CONTAINER_NAME}" lpstat -v >/dev/null 2>&1 || true
        DEBUG_ACCESS_LOG_SEEN=0
        for _ in $(seq 1 20); do
            DEBUG_LOGS_SNAPSHOT=$(docker logs "${DEBUG_CONTAINER_NAME}" 2>&1)
            if echo "${DEBUG_LOGS_SNAPSHOT}" | grep -qE '"(GET|POST|PUT|HEAD) '; then
                DEBUG_ACCESS_LOG_SEEN=1
                break
            fi
            sleep 1
        done
        DEBUG_LOGS=$(docker logs "${DEBUG_CONTAINER_NAME}" 2>&1)
        if echo "${DEBUG_LOGS}" | grep -qE '^[EWID] \['; then
            green "   PASS: error_log still tailed at the debug tier"
        else
            red "   FAIL: error_log not tailed at the debug tier"
            FAIL=1
        fi
        if [[ "${DEBUG_ACCESS_LOG_SEEN}" == "1" ]]; then
            green "   PASS: access_log additionally tailed at the debug tier"
        else
            red "   FAIL: access_log not tailed at the debug tier"
            FAIL=1
        fi
        DEBUG_LOG_LEVEL_APPLIED=0
        for _ in $(seq 1 10); do
            if docker exec "${DEBUG_CONTAINER_NAME}" grep -qE '^LogLevel debug$' /etc/cups/cupsd.conf; then
                DEBUG_LOG_LEVEL_APPLIED=1
                break
            fi
            sleep 1
        done
        if [[ "${DEBUG_LOG_LEVEL_APPLIED}" == "1" ]]; then
            green "   PASS: cupsd.conf LogLevel=debug applied for the debug tier"
        else
            red "   FAIL: cupsd.conf LogLevel not set to debug"
            FAIL=1
        fi
    fi
fi
docker rm -f "${DEBUG_CONTAINER_NAME}" >/dev/null 2>&1 || true
rm -rf "${DEBUG_DATA_DIR}" >/dev/null 2>&1 || true

yellow "Checking cupsd.conf ServerAlias (Host-header validation fix)..."
if echo "${CUPSD_CONF}" | grep -qF "ServerAlias cups-verify.example.ts.net"; then
    green "   PASS: ServerAlias emitted for the configured server_aliases value"
else
    red "   FAIL: missing 'ServerAlias cups-verify.example.ts.net' -- cupsd would reject that Host header with 400"
    FAIL=1
fi

yellow "Checking <Location /admin> gained the same Allow from lines as <Location /> (web admin fix)..."
ROOT_ALLOW=$(echo "${CUPSD_CONF}" | grep -A5 '<Location />' | grep -E '^\s*Allow from ' || true)
ADMIN_ALLOW=$(echo "${CUPSD_CONF}" | grep -A5 '<Location /admin>' | grep -E '^\s*Allow from ' || true)
if [[ -n "${ROOT_ALLOW}" && "${ROOT_ALLOW}" == "${ADMIN_ALLOW}" ]]; then
    green "   PASS: <Location /admin> carries the same Allow from line(s) as <Location />"
else
    red "   FAIL: <Location /admin> Allow from lines do not match <Location />'s"
    echo "--- <Location /> Allow lines ---"; echo "${ROOT_ALLOW}"
    echo "--- <Location /admin> Allow lines ---"; echo "${ADMIN_ALLOW}"
    FAIL=1
fi
if echo "${CUPSD_CONF}" | grep -A5 '<Location /admin/conf>' | grep -q 'Allow from'; then
    red "   FAIL: <Location /admin/conf> was unexpectedly widened -- must stay @SYSTEM-only"
    FAIL=1
else
    green "   PASS: <Location /admin/conf> untouched (no Allow from line)"
fi
if echo "${CUPSD_CONF}" | grep -A5 '<Location /admin/log>' | grep -q 'Allow from'; then
    red "   FAIL: <Location /admin/log> was unexpectedly widened -- must stay @SYSTEM-only"
    FAIL=1
else
    green "   PASS: <Location /admin/log> untouched (no Allow from line)"
fi

yellow "Checking admin account provisioning (admin_username/admin_password)..."
ADMIN_SHADOW=$(docker exec "${CONTAINER_NAME}" grep '^verifyadmin:' /etc/shadow 2>/dev/null || true)
if [[ -z "${ADMIN_SHADOW}" ]]; then
    red "   FAIL: 'verifyadmin' has no /etc/shadow entry -- account was not created"
    FAIL=1
else
    ADMIN_HASH=$(echo "${ADMIN_SHADOW}" | cut -d: -f2)
    if [[ "${ADMIN_HASH}" == "*" || "${ADMIN_HASH}" == "!" || -z "${ADMIN_HASH}" ]]; then
        red "   FAIL: 'verifyadmin' shadow entry is disabled/empty (${ADMIN_HASH}) -- login would never work"
        FAIL=1
    else
        green "   PASS: 'verifyadmin' has a valid, non-disabled shadow hash"
    fi
fi
if docker exec "${CONTAINER_NAME}" id -Gn verifyadmin 2>/dev/null | grep -qw lpadmin; then
    green "   PASS: 'verifyadmin' is a member of the lpadmin group (@SYSTEM auth)"
else
    red "   FAIL: 'verifyadmin' is not a member of lpadmin -- @SYSTEM auth would reject it"
    FAIL=1
fi
if echo "${CONTAINER_LOGS:-$(docker logs "${CONTAINER_NAME}" 2>&1)}" | grep -qF "verify-secret-pw"; then
    red "   FAIL: the plaintext admin_password appears in container logs"
    FAIL=1
else
    green "   PASS: admin_password never appears in container logs"
fi

yellow "Checking printer registration..."
if docker exec "${CONTAINER_NAME}" lpstat -p testprinter 2>/dev/null | grep -q "testprinter"; then
    green "   PASS: testprinter registered"
else
    red "   FAIL: testprinter not registered"
    docker exec "${CONTAINER_NAME}" lpstat -p 2>&1 || true
    FAIL=1
fi

# CI runners (and this docker-bridge test container) have no tailscale0
# interface, so the Tailscale Allow-from rule must gracefully skip here --
# proving the ABSENCE of the rule is the correct assertion in this
# environment. Actual presence is only provable on a host that really runs
# Tailscale (haos-op3050-1), verified empirically outside this script.
yellow "Checking Tailscale Allow rule graceful-skip (no tailscale0 in this environment)..."
if echo "${CUPSD_CONF}" | grep -qF "100.64.0.0/10"; then
    yellow "   NOTE: 100.64.0.0/10 Allow rule present -- this environment unexpectedly has tailscale0"
else
    green "   PASS: no 100.64.0.0/10 Allow rule (no tailscale0 interface in this environment, as expected)"
fi

yellow "Checking printer location (lpadmin -L)..."
if docker exec "${CONTAINER_NAME}" lpstat -l -p testprinter 2>/dev/null | grep -qF "Location: Office"; then
    green "   PASS: testprinter shows configured location 'Office'"
else
    red "   FAIL: testprinter does not show 'Location: Office'"
    docker exec "${CONTAINER_NAME}" lpstat -l -p testprinter 2>&1 || true
    FAIL=1
fi

yellow "Checking brlaser driver registration (D-14)..."
if docker exec "${CONTAINER_NAME}" lpstat -v brlasertest 2>/dev/null | grep -q "socket://192.0.2.20:9100"; then
    green "   PASS: brlasertest registered with the configured device uri"
else
    red "   FAIL: brlasertest not registered"
    docker exec "${CONTAINER_NAME}" lpstat -v 2>&1 || true
    FAIL=1
fi
# The strongest proof this printer is bound to the resolved brlaser PPD (not
# the generic.ppd fallback) is the PPD file CUPS wrote for it -- it must
# reference brlaser's own filter/NickName, never the generic driver.
BRLASER_PPD=$(docker exec "${CONTAINER_NAME}" cat /etc/cups/ppd/brlasertest.ppd 2>/dev/null || true)
if echo "${BRLASER_PPD}" | grep -qi "rastertobrlaser"; then
    green "   PASS: brlasertest.ppd references the brlaser filter (rastertobrlaser)"
else
    red "   FAIL: brlasertest.ppd does not reference brlaser -- may have registered with generic.ppd instead"
    FAIL=1
fi
if echo "${BRLASER_PPD}" | grep -qi "sample.drv"; then
    red "   FAIL: brlasertest.ppd unexpectedly references the generic sample.drv PPD"
    FAIL=1
fi

yellow "Checking for legacy-unicast reflector slot exhaustion (D-08)..."
CONTAINER_LOGS=$(docker logs "${CONTAINER_NAME}" 2>&1)
if echo "${CONTAINER_LOGS}" | grep -q "No slot available for legacy unicast reflection"; then
    red "   FAIL: reflector slot-exhaustion message present despite enable-reflector=no"
    FAIL=1
else
    green "   PASS: no reflector slot-exhaustion messages"
fi

yellow "Checking printer UUID stability across a container RECREATION..."

# Supervisor does not restart an add-on container in place: it removes it and
# starts a new one from the same image with the same /data mount. That is what
# resets /etc/cups (the container's writable layer) and makes cupsd assign
# fresh random printer UUIDs at registration -- the original bug path. A
# `docker restart` keeps the writable layer, so it cannot reproduce that and
# a UUID check built on it can pass with the fixup removed (WR-07). This
# section therefore recreates the container and compares the recreated
# container's UUIDs with the deterministic uuid5 value computed on the host
# from the printer name by generate_config.py itself.

# Expected UUID (urn:uuid:<uuid5>) for a printer name, computed on the host.
expected_printer_uuid() {
    python3 -c "
import sys
sys.path.insert(0, sys.argv[1])
import generate_config
print('urn:uuid:' + generate_config.compute_stable_printer_uuid(sys.argv[2]))
" "${ADDON_DIR}" "$1"
}

get_printer_uuid() {
    docker exec "${CONTAINER_NAME}" awk "/<Printer $1>/,/<\/Printer>/" /etc/cups/printers.conf \
        | grep '^UUID ' | awk '{print $2}' || true
}

# Poll for run.sh's literal post-fixup readiness line (step 8). Only after it
# is the SECOND cupsd instance (the one after the UUID patch) running; reading
# printers.conf earlier could observe a stale pre-fixup value. Returns 1 when
# the line does not appear (e.g. the fixup mechanism is absent).
wait_for_post_fixup() {
    local _ logs
    for _ in $(seq 1 40); do
        # Captured first: `docker logs | grep -q` would SIGPIPE docker under pipefail and report a false miss.
        logs=$(docker logs "${CONTAINER_NAME}" 2>&1 || true)
        if grep -qF "cupsd is ready (post-fixup restart)" <<<"${logs}"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

check_uuid() {
    # $1 = label, $2 = printer name, $3 = actual, $4 = expected
    if [[ "$3" == "$4" ]]; then
        green "   PASS: $1 $2 UUID equals the deterministic uuid5 value ($3)"
    else
        red "   FAIL: $1 $2 UUID '$3' != expected '$4'"
        FAIL=1
    fi
}

UUID_TESTPRINTER_EXPECTED=$(expected_printer_uuid testprinter)
UUID_BRLASERTEST_EXPECTED=$(expected_printer_uuid brlasertest)

# The first boot also runs the fixup cycle; wait for it before the baseline read.
wait_for_post_fixup || yellow "   NOTE: no post-fixup readiness line in the first container within 40s"
check_uuid "pre-recreation" testprinter "$(get_printer_uuid testprinter)" "${UUID_TESTPRINTER_EXPECTED}"
check_uuid "pre-recreation" brlasertest "$(get_printer_uuid brlasertest)" "${UUID_BRLASERTEST_EXPECTED}"

yellow "   recreating the container (stop, then start a new one with the same name and /data mount)..."
docker stop -t 15 "${CONTAINER_NAME}" >/dev/null 2>&1 || true
# --rm removes the stopped container; wait until the name is free (removal can be asynchronous).
for _ in $(seq 1 30); do
    if ! docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
start_container

RECREATE_READY=0
for _ in $(seq 1 40); do
    if docker exec "${CONTAINER_NAME}" lpstat -r >/dev/null 2>&1; then
        RECREATE_READY=1
        break
    fi
    sleep 1
done
if [[ "${RECREATE_READY}" != "1" ]]; then
    red "   FAIL: cupsd did not become ready in the recreated container"
    docker logs "${CONTAINER_NAME}" 2>&1 || true
    FAIL=1
else
    green "   PASS: cupsd ready in the recreated container (fresh writable layer, same /data mount)"

    yellow "   waiting for run.sh's post-fixup-restart readiness log line in the new container..."
    if wait_for_post_fixup; then
        green "   PASS: post-fixup cupsd instance confirmed ready via run.sh's own log line"
    else
        red "   FAIL: 'cupsd is ready (post-fixup restart)' did not appear within 40s -- the UUID fixup did not run"
        FAIL=1
    fi

    # Read regardless, so a missing/ineffective fixup also surfaces as a UUID mismatch.
    check_uuid "post-recreation" testprinter "$(get_printer_uuid testprinter)" "${UUID_TESTPRINTER_EXPECTED}"
    check_uuid "post-recreation" brlasertest "$(get_printer_uuid brlasertest)" "${UUID_BRLASERTEST_EXPECTED}"

    yellow "   Checking no regression: printer registration survives the recreation..."
    if docker exec "${CONTAINER_NAME}" lpstat -p testprinter 2>/dev/null | grep -q "testprinter"; then
        green "   PASS: testprinter registered after recreation"
    else
        red "   FAIL: testprinter not registered after recreation"
        FAIL=1
    fi
    if docker exec "${CONTAINER_NAME}" lpstat -v brlasertest 2>/dev/null | grep -q "socket://192.0.2.20:9100"; then
        green "   PASS: brlasertest registered with its device uri after recreation"
    else
        red "   FAIL: brlasertest not registered after recreation"
        FAIL=1
    fi

    # Refresh for the final failure-path debug dump below, so it reflects the
    # recreated container's output too, not just the first boot's.
    CONTAINER_LOGS=$(docker logs "${CONTAINER_NAME}" 2>&1)
fi

yellow "Checking print-history poller (Task C: print-history.jsonl)..."
if docker exec "${CONTAINER_NAME}" test -f /print-history-poller.py; then
    green "   PASS: /print-history-poller.py present in the image"
else
    red "   FAIL: /print-history-poller.py missing"
    FAIL=1
fi
# This check runs shortly after the UUID-stability section's container
# recreation above, which re-executes run.sh's entire boot sequence from
# scratch, including its step-9 cupsctl retry loop (which can take a few
# seconds) BEFORE step 11 (starting this poller) even runs -- so poll rather
# than check once, to not race that same boot.
POLLER_RUNNING=0
for _ in $(seq 1 15); do
    if docker exec "${CONTAINER_NAME}" sh -c 'ps aux | grep -v grep | grep -qF print-history-poller.py'; then
        POLLER_RUNNING=1
        break
    fi
    sleep 1
done
if [[ "${POLLER_RUNNING}" == "1" ]]; then
    green "   PASS: print-history-poller.py is running as a background process"
else
    red "   FAIL: print-history-poller.py is not running"
    FAIL=1
fi

# A real, instantly-completing print job directly against cupsd (a
# throwaway "verify-history-printer" using file:///dev/null -- distinct
# from this add-on's own testprinter/brlasertest fixtures above, whose
# device URIs are deliberately unreachable TEST-NET addresses and would
# never actually complete), so the poller has a real completed job to
# observe.
docker exec "${CONTAINER_NAME}" lpadmin -p verify-history-printer -v file:///dev/null -E -m drv:///sample.drv/generic.ppd >/dev/null 2>&1 || true
docker exec "${CONTAINER_NAME}" sh -c 'echo verify-history-payload > /tmp/verify-history.txt'
docker exec "${CONTAINER_NAME}" lp -d verify-history-printer -t "verify-history-job" /tmp/verify-history.txt >/dev/null 2>&1 || true

yellow "   waiting up to 40s for the poller to record the job in print-history.jsonl..."
HISTORY_SEEN=0
for _ in $(seq 1 40); do
    if [[ -f "${DATA_DIR}/print-history.jsonl" ]] && grep -qF "verify-history-printer" "${DATA_DIR}/print-history.jsonl"; then
        HISTORY_SEEN=1
        break
    fi
    sleep 1
done
if [[ "${HISTORY_SEEN}" == "1" ]]; then
    green "   PASS: print-history.jsonl recorded the verify-history-printer job"
    grep -F "verify-history-printer" "${DATA_DIR}/print-history.jsonl" | tail -1 > "${DATA_DIR}/.verify-history-line.json"
    if python3 -c "
import json
with open('${DATA_DIR}/.verify-history-line.json') as f:
    d = json.loads(f.read())
assert d.get('printer') == 'verify-history-printer', d
assert isinstance(d.get('job_id'), int), d
assert 'timestamp' in d, d
assert d.get('final_state') == 'completed', d
print('OK')
" | grep -q OK; then
        green "   PASS: print-history.jsonl line has the expected fields"
    else
        red "   FAIL: print-history.jsonl line missing expected fields"
        FAIL=1
    fi
else
    red "   FAIL: print-history.jsonl did not record the job within 40s"
    FAIL=1
fi

if [[ -f "${DATA_DIR}/print-history-state.json" ]]; then
    green "   PASS: print-history-state.json exists under /data"
else
    red "   FAIL: print-history-state.json missing under /data"
    FAIL=1
fi

if [[ "${FAIL}" == "1" ]]; then
    echo
    red "internal/verify-cups-scaffold.sh: FAILED"
    echo "--- container logs ---"
    echo "${CONTAINER_LOGS}"
    exit 1
fi

echo
green "internal/verify-cups-scaffold.sh: ALL CHECKS PASSED"
