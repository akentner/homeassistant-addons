#!/usr/bin/env bash
# verify-cups-mdns-live.sh -- live mDNS/AirPrint verifier for the cups add-on (D-07, D-10, D-11).
#
# Measures, from three vantage points, whether the add-on's Avahi daemon really claims the fixed
# `avahi_hostname` and whether the printer's `_ipp._tcp` service is resolvable by a LAN client:
#   1. in-container D-Bus  (the daemon's authoritative host name)
#   2. in-container config / log files (enable-reflector, use-ipv6, slot exhaustion)
#   3. this machine acting as a LAN client (avahi-resolve-host-name, avahi-browse -r)
# The vantage points disagree on a renamed daemon, which is exactly the bug this script makes measurable.
#
# READ-ONLY CONTRACT
# ------------------
# Only reads: `ha apps info --raw-json`, `ha host info --raw-json`, `docker ps` / `docker inspect` /
# `docker logs`, `docker exec` of pure readers (cat, ps, ls, grep, a python3 import of the shipped helper,
# dbus-send Get* methods, avahi-resolve*), and the avahi client tools on the machine running the script.
# It never issues a mutating Supervisor or docker verb and never signals a process.
#
# Usage: ./internal/verify-cups-mdns-live.sh [--assert] [--host H] [--slug S] [--host-ip IP]
#                                            [--settle-wait SECONDS] [--mask] [-h|--help]
#
# Output: one line per check -- `PASS|FAIL|INFO|SKIP <id>: <detail>` -- then `RESULT: PASS` or
# `RESULT: FAIL (<n> failed)`.
#
# Exit status: 0 = no FAIL line, 1 = at least one FAIL line, 2 = usage or prerequisite error.

set -euo pipefail
export LC_ALL=C

HOST="haos-op3050-1"
SLUG="72a005f5_cups"
HOST_IP=""
SETTLE_WAIT=0
MASK=0
MODE="assert"
ARGS=("$@")

usage() {
    sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
    --assert) MODE="assert" ;;
    --host)
        [[ $# -ge 2 ]] || die "--host needs a value"
        HOST="$2"
        shift
        ;;
    --slug)
        [[ $# -ge 2 ]] || die "--slug needs a value"
        SLUG="$2"
        shift
        ;;
    --host-ip)
        [[ $# -ge 2 ]] || die "--host-ip needs a value"
        HOST_IP="$2"
        shift
        ;;
    --settle-wait)
        [[ $# -ge 2 ]] || die "--settle-wait needs a value"
        SETTLE_WAIT="$2"
        shift
        ;;
    --mask) MASK=1 ;;
    -h | --help)
        usage
        exit 0
        ;;
    *) die "unknown argument: $1 (see --help)" ;;
    esac
    shift
done

[[ "${SETTLE_WAIT}" =~ ^[0-9]+$ ]] || die "--settle-wait must be a non-negative integer"

# Rewrite every dotted-quad IPv4 and every IPv6 literal so output can be pasted into a committed document.
mask_stream() {
    sed -E \
        -e 's/[0-9]{1,3}(\.[0-9]{1,3}){3}/<IPv4>/g' \
        -e 's/([0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{0,4}/<IPv6>/g' \
        -e 's/[0-9a-fA-F:]*::[0-9a-fA-F:]*/<IPv6>/g'
}

# Re-exec through the masker so that every line, including stderr-free helper output, is masked.
if [[ "${MASK}" -eq 1 && -z "${_VERIFY_MDNS_MASKED:-}" ]]; then
    export _VERIFY_MDNS_MASKED=1
    set +e
    "$0" "${ARGS[@]}" | mask_stream
    status="${PIPESTATUS[0]}"
    exit "${status}"
fi

for tool in ssh jq timeout avahi-browse avahi-resolve-host-name avahi-resolve; do
    command -v "${tool}" >/dev/null 2>&1 || die "required tool not on PATH: ${tool}"
done

rssh() { ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" "$@"; }

# Run a command inside the add-on container; every argument is shell-quoted for the remote shell.
cexec() {
    local quoted
    quoted="$(printf '%q ' "$@")"
    rssh "docker exec ${CONTAINER} ${quoted}"
}

dbus_get() {
    cexec dbus-send --system --print-reply --dest=org.freedesktop.Avahi / "org.freedesktop.Avahi.Server.$1"
}

FAILS=0
pass() { printf 'PASS %s: %s\n' "$1" "${*:2}"; }
fail() {
    printf 'FAIL %s: %s\n' "$1" "${*:2}"
    FAILS=$((FAILS + 1))
}
info() { printf 'INFO %s: %s\n' "$1" "${*:2}"; }
skip() { printf 'SKIP %s: %s\n' "$1" "${*:2}"; }

# Step 1: ssh reachability.
rssh true >/dev/null 2>&1 || die "cannot reach ${HOST} via ssh (BatchMode)"

# Step 2: whitelisted add-on facts only. The options object carries credential fields and is never printed.
APP_INFO="$(rssh "ha apps info ${SLUG} --raw-json")" || die "ha apps info ${SLUG} failed on ${HOST}"
FACTS="$(printf '%s' "${APP_INFO}" | jq -r '[
    .data.state, .data.version,
    (.data.options.avahi_hostname // "cups"),
    (.data.options.avahi_use_ipv6 // false),
    (.data.options.avahi_reflector // false)] | @tsv')" || die "could not parse ha apps info output"
APP_INFO=""
IFS=$'\t' read -r APP_STATE APP_VERSION AVAHI_HOSTNAME USE_IPV6 REFLECTOR <<<"${FACTS}"
info addon "state=${APP_STATE} version=${APP_VERSION} avahi_hostname=${AVAHI_HOSTNAME} use_ipv6=${USE_IPV6}" \
    "reflector=${REFLECTOR}"
[[ "${APP_STATE}" == "started" ]] || die "add-on ${SLUG} is not started (state=${APP_STATE})"

# Step 3: container discovery tolerant of the app_ and addon_ naming prefixes.
CONTAINER="$(rssh "docker ps --format '{{.Names}}'" | grep -E "^(app|addon)_${SLUG}\$" | head -1 || true)"
[[ -n "${CONTAINER}" ]] || die "no running container matches ^(app|addon)_${SLUG}\$ on ${HOST}"

# Step 4: host LAN IPv4, learned with the add-on's own helper so both sides agree on the interface.
if [[ -z "${HOST_IP}" ]]; then
    HOST_IP="$(cexec python3 -c \
        "import sys; sys.path.insert(0, '/'); import generate_config as g; i = g.detect_primary_interface(); \
r = g.get_iface_ipv4(i) if i else None; print(r[0] if r else '')" 2>/dev/null || true)"
fi
[[ -n "${HOST_IP}" ]] || die "could not determine the host LAN IPv4 (use --host-ip)"

# Step 5: optional settle wait (after a restart) -- poll D-Bus GetState until the daemon reports running (int32 2).
if [[ "${SETTLE_WAIT}" -gt 0 ]]; then
    waited=0
    while [[ "${waited}" -lt "${SETTLE_WAIT}" ]]; do
        state_now="$(dbus_get GetState 2>/dev/null | sed -n 's/^ *int32 \([0-9]*\).*/\1/p' || true)"
        [[ "${state_now}" == "2" ]] && break
        sleep 2
        waited=$((waited + 2))
    done
fi

# Step 6: checks.
LIVE_CONF="$(cexec cat /etc/avahi/avahi-daemon.conf 2>/dev/null || true)"

if [[ "${REFLECTOR}" == "false" ]]; then
    if printf '%s\n' "${LIVE_CONF}" | grep -q '^enable-reflector=no'; then
        pass conf-reflector "live avahi-daemon.conf has enable-reflector=no"
    else
        fail conf-reflector "live avahi-daemon.conf lacks enable-reflector=no while avahi_reflector=false"
    fi
else
    skip conf-reflector "avahi_reflector=true"
fi

if [[ "${USE_IPV6}" == "false" ]]; then
    if printf '%s\n' "${LIVE_CONF}" | grep -q '^use-ipv6=no'; then
        pass conf-ipv6 "live avahi-daemon.conf has use-ipv6=no"
    else
        fail conf-ipv6 "live avahi-daemon.conf lacks use-ipv6=no while avahi_use_ipv6=false"
    fi
else
    skip conf-ipv6 "avahi_use_ipv6=true"
fi

SLOT_COUNT="$(rssh "docker logs ${CONTAINER} 2>&1 | grep -c 'No slot available for legacy unicast reflection'" ||
    true)"
SLOT_COUNT="${SLOT_COUNT//[^0-9]/}"
if [[ -z "${SLOT_COUNT}" ]]; then
    fail slot-exhaustion "could not count slot-exhaustion lines in the container log"
elif [[ "${SLOT_COUNT}" -eq 0 ]]; then
    pass slot-exhaustion "0 'No slot available for legacy unicast reflection' lines in the container log"
else
    fail slot-exhaustion "${SLOT_COUNT} 'No slot available for legacy unicast reflection' lines in the container log"
fi

DAEMON_STATE="$(dbus_get GetState 2>/dev/null | sed -n 's/^ *int32 \([0-9]*\).*/\1/p' || true)"
DAEMON_FQDN="$(dbus_get GetHostNameFqdn 2>/dev/null | sed -n 's/^ *string "\(.*\)".*/\1/p' || true)"
WANT_FQDN="${AVAHI_HOSTNAME}.local"
if [[ "${DAEMON_STATE}" == "2" && "${DAEMON_FQDN}" == "${WANT_FQDN}" ]]; then
    pass daemon-fqdn "D-Bus GetState=2 and GetHostNameFqdn=${DAEMON_FQDN}"
else
    fail daemon-fqdn "D-Bus GetState=${DAEMON_STATE:-unreadable} GetHostNameFqdn=${DAEMON_FQDN:-unreadable}," \
        "expected int32 2 and ${WANT_FQDN}"
fi

FWD_OUT="$(timeout 8 avahi-resolve-host-name -4 "${WANT_FQDN}" 2>/dev/null || true)"
FWD_IP="$(printf '%s\n' "${FWD_OUT}" | awk -v n="${WANT_FQDN}" '$1 == n { print $2; exit }')"
if [[ "${FWD_IP}" == "${HOST_IP}" ]]; then
    pass lan-forward-v4 "${WANT_FQDN} resolves to the host IPv4 from this LAN client"
else
    fail lan-forward-v4 "${WANT_FQDN} resolved to '${FWD_IP:-nothing}' from this LAN client, expected ${HOST_IP}"
fi

if [[ "${USE_IPV6}" == "false" ]]; then
    if [[ -z "${DAEMON_FQDN}" ]]; then
        skip lan-no-aaaa "no daemon fqdn could be read from D-Bus"
    else
        AAAA_OUT="$(timeout 8 avahi-resolve-host-name -6 "${DAEMON_FQDN}" 2>/dev/null || true)"
        AAAA_IP="$(printf '%s\n' "${AAAA_OUT}" | awk -v n="${DAEMON_FQDN}" '$1 == n { print $2; exit }')"
        if [[ -z "${AAAA_IP}" ]]; then
            pass lan-no-aaaa "${DAEMON_FQDN} publishes no AAAA record"
        else
            fail lan-no-aaaa "${DAEMON_FQDN} still publishes an AAAA record (${AAAA_IP}) although avahi_use_ipv6=false"
        fi
    fi
else
    skip lan-no-aaaa "avahi_use_ipv6=true"
fi

BROWSE_OUT="$(timeout 60 avahi-browse -t -r -p _ipp._tcp 2>/dev/null || true)"
ADDED="$(printf '%s\n' "${BROWSE_OUT}" | awk -F';' '$1 == "+" { n++ } END { print n + 0 }')"
RESOLVED="$(printf '%s\n' "${BROWSE_OUT}" | awk -F';' -v h="${WANT_FQDN}" -v ip="${HOST_IP}" \
    '$1 == "=" && $5 == "_ipp._tcp" && $7 == h && $8 == ip { n++ } END { print n + 0 }')"
if [[ "${RESOLVED}" -gt 0 ]]; then
    pass lan-service-resolve "${RESOLVED} resolved _ipp._tcp record(s) point at ${WANT_FQDN} / host IPv4"
else
    fail lan-service-resolve "no resolved _ipp._tcp record for ${WANT_FQDN} / ${HOST_IP}" \
        "(${ADDED} browse '+' line(s) seen: browse-works/resolve-fails)"
fi

REV_NOTE="shared-IP reverse lookup is answered by whichever of the host's avahi daemons replies first; not asserted"
REV_C="$(cexec timeout 8 avahi-resolve -a "${HOST_IP}" 2>/dev/null | awk '{ print $2; exit }' || true)"
REV_L="$(timeout 8 avahi-resolve -a "${HOST_IP}" 2>/dev/null | awk '{ print $2; exit }' || true)"
info reverse-container "${REV_C:-no answer} (${REV_NOTE})"
info reverse-lan "${REV_L:-no answer} (${REV_NOTE})"

if [[ "${FAILS}" -eq 0 ]]; then
    printf 'RESULT: PASS\n'
    exit 0
fi
printf 'RESULT: FAIL (%s failed)\n' "${FAILS}"
exit 1
