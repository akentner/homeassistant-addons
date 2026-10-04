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
# Usage: ./internal/verify-cups-mdns-live.sh [--assert | --diagnose [--out FILE] |
#                                            --watch MINUTES | --watch-seconds N [--interval SECONDS]
#                                            [--quiet-since SPEC]]
#                                            [--host H] [--slug S] [--host-ip IP] [--settle-wait SECONDS]
#                                            [--mask] [-h|--help]
#
# --assert (default) output: one line per check -- `PASS|FAIL|INFO|SKIP <id>: <detail>` -- then `RESULT: PASS`
# or `RESULT: FAIL (<n> failed)`. Exit status: 0 = no FAIL line, 1 = at least one FAIL line, 2 = usage or
# prerequisite error.
#
# --diagnose output: nine evidence sections, each a header line `EVIDENCE E<n> <name>` followed by its body and
# optional `HINT E<n>: <sentence>` lines. The RAW transcript goes to --out (default
# ${TMPDIR:-/tmp}/cups-mdns-diagnose-<epoch>.log, keep it out of the repository); stdout is the same text passed
# through the IP masker so it can be pasted into a committed document. Exit status 0 unless a prerequisite fails (2).
#
# --watch MINUTES (--watch-seconds N is the primitive, --watch is MINUTES*60) repeats the --assert checks every
# --interval SECONDS (default 120, minimum 1) for the given duration, without restarting anything. Each round prints
# `WATCH round=<n> t=+MM:SS age=+MM:SS` (t = time since the watch started, age = age of the add-on container), the
# check lines, `WATCH round=<n> quiet=yes|NO:<names>|unknown` and `WATCH round=<n> verdict=PASS|FAIL(<k>)`. Mutually
# exclusive with --diagnose. --settle-wait applies once, before round 1. Extra per-round checks (watch only):
# `continuity` (the add-on container's StartedAt must not change and the add-on must stay started) and
# `host-name-conflict` (no `Host name conflict` line in the container log since the container start). The first
# failing round also prints a `WATCH CONTEXT` block with the matching container-log lines.
#
# After the last round: `WATCH MILESTONES: age+2m=.. age+10m=.. age+30m=..` (PASS/FAIL of the first round at or
# beyond that container age, NOT-REACHED otherwise), `WATCH QUIET-WINDOW: since=<ISO> container-start=<ISO>
# covers-container-start=yes|no events=OK|UNVERIFIED|UNAVAILABLE`, `WATCH SUMMARY: ...` and exactly one result line:
#   WATCH RESULT: PASS                  exit 0  every round passed, every round was quiet, local events verified
#   WATCH RESULT: FAIL                  exit 1  a quiet round failed (the summary names the first one)
#   WATCH RESULT: INVALID               exit 3  a local cups container was running, or was created/started, inside
#                                               the quiet window: the observation proves nothing about the add-on
#   WATCH RESULT: PASS-UNVERIFIED-QUIET exit 4  all rounds passed and were quiet but the local container-event
#                                               history could not be verified (never a closing PASS)
# Exit status 2 stays "usage or prerequisite error".
#
# --quiet-since SPEC sets where the quiet window (checked post hoc with `docker events --since`) starts:
# `container-start` (default: the add-on container's StartedAt, so the gap between the restart and the first round is
# covered), `watch-start`, or an epoch / ISO timestamp (the moment the operator's quiet promise began). The window is
# `covers-container-start=no` when it opens after the container start; that earlier period is then covered only by
# the host-name-conflict and continuity checks. The events history is verified (events=OK) only for podman with a
# persistent event logger or when the output shows events near the window start; a plain docker engine with an empty
# answer is UNVERIFIED.
#
# QUIET-WINDOW RULE (D-11): do not run podman/docker verifiers (verify-cups-*.sh) or start any cups container on this
# workstation while a live proof is in progress -- a local container that announces the host name `cups` on the real
# LAN makes the live avahi rename itself, which is not an add-on defect.
set -euo pipefail
export LC_ALL=C

HOST="haos-op3050-1"
SLUG="72a005f5_cups"
HOST_IP=""
SETTLE_WAIT=0
WATCH_SECONDS=""
INTERVAL=120
QUIET_SINCE="container-start"
MASK=0
MODE="assert"
OUT=""
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
    --diagnose) MODE="diagnose" ;;
    --out)
        [[ $# -ge 2 ]] || die "--out needs a value"
        OUT="$2"
        shift
        ;;
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
    --watch)
        [[ $# -ge 2 ]] || die "--watch needs a value (minutes)"
        [[ "$2" =~ ^[0-9]+$ && "$2" -ge 1 ]] || die "--watch must be a positive integer (minutes)"
        WATCH_SECONDS=$(($2 * 60))
        shift
        ;;
    --watch-seconds)
        [[ $# -ge 2 ]] || die "--watch-seconds needs a value"
        [[ "$2" =~ ^[0-9]+$ ]] || die "--watch-seconds must be a non-negative integer"
        WATCH_SECONDS="$2"
        shift
        ;;
    --interval)
        [[ $# -ge 2 ]] || die "--interval needs a value"
        [[ "$2" =~ ^[0-9]+$ && "$2" -ge 1 ]] || die "--interval must be an integer >= 1 (seconds)"
        INTERVAL="$2"
        shift
        ;;
    --quiet-since)
        [[ $# -ge 2 ]] || die "--quiet-since needs a value"
        case "$2" in
        container-start | watch-start) ;;
        *) date -u -d "$2" +%s >/dev/null 2>&1 || [[ "$2" =~ ^[0-9]{9,}$ ]] ||
            die "--quiet-since must be container-start, watch-start, an epoch or an ISO timestamp" ;;
        esac
        QUIET_SINCE="$2"
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
if [[ -n "${WATCH_SECONDS}" ]]; then
    [[ "${MODE}" != "diagnose" ]] || die "--watch/--watch-seconds and --diagnose are mutually exclusive"
    MODE="watch"
elif [[ "${QUIET_SINCE}" != "container-start" ]]; then
    die "--quiet-since is only valid with --watch/--watch-seconds"
fi

# Rewrite every dotted-quad IPv4 and every IPv6 literal so output can be pasted into a committed document.
mask_stream() {
    sed -u -E \
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
    (.data.options.avahi_reflector // false),
    (.data.version_latest | tostring), (.data.watchdog | tostring), (.data.boot | tostring),
    (.data.hostname | tostring)] | @tsv')" || die "could not parse ha apps info output"
APP_INFO=""
IFS=$'\t' read -r APP_STATE APP_VERSION AVAHI_HOSTNAME USE_IPV6 REFLECTOR APP_VLATEST APP_WATCHDOG APP_BOOT \
    APP_HOSTNAME <<<"${FACTS}"
if [[ "${MODE}" != "diagnose" ]]; then
    info addon "state=${APP_STATE} version=${APP_VERSION} avahi_hostname=${AVAHI_HOSTNAME} use_ipv6=${USE_IPV6}" \
        "reflector=${REFLECTOR}"
fi
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

# ---------------------------------------------------------------------------------------------------------------
# --diagnose: nine read-only evidence sections (E1..E9).
# ---------------------------------------------------------------------------------------------------------------
section() { printf 'EVIDENCE E%s %s\n' "$1" "$2"; }
hint() { printf 'HINT E%s: %s\n' "$1" "${*:2}"; }

# Remote reader: one line per running container process that is an avahi-daemon or mdns-repeater. Containers
# without a shell or without ps are skipped silently.
scan_avahi_processes() {
    rssh sh -s <<'REMOTE' 2>/dev/null || true
for c in $(docker ps --format '{{.Names}}'); do
    docker exec "$c" ps -o args </dev/null 2>/dev/null | grep -E 'avahi-daemon|mdns-repeater' | grep -v grep |
        sed "s/^/$c: /"
done
REMOTE
}

diagnose() {
    local hostinfo host_name boot_us boot_utc
    hostinfo="$(rssh "ha host info --raw-json" 2>/dev/null || true)"
    host_name="$(printf '%s' "${hostinfo}" | jq -r '.data.hostname // empty' 2>/dev/null || true)"
    boot_us="$(printf '%s' "${hostinfo}" | jq -r '.data.boot_timestamp // empty' 2>/dev/null || true)"

    section 1 addon-state
    printf 'version=%s version_latest=%s state=%s watchdog=%s boot=%s hostname=%s\n' "${APP_VERSION}" \
        "${APP_VLATEST}" "${APP_STATE}" "${APP_WATCHDOG}" "${APP_BOOT}" "${APP_HOSTNAME}"
    printf 'avahi_hostname=%s avahi_use_ipv6=%s avahi_reflector=%s\n' "${AVAHI_HOSTNAME}" "${USE_IPV6}" "${REFLECTOR}"

    section 2 avahi-processes
    local procs
    procs="$(scan_avahi_processes)"
    printf '%s\n' "${procs:-(none found)}"
    local siblings=() name
    while IFS= read -r name; do
        [[ -n "${name}" && "${name}" != "${CONTAINER}" ]] && siblings+=("${name}")
    done < <(printf '%s\n' "${procs}" | grep 'avahi-daemon' | sed 's/: .*//' | sort -u || true)

    section 3 live-avahi-conf
    cexec grep -Ev '^[[:space:]]*(#|$)' /etc/avahi/avahi-daemon.conf 2>/dev/null || printf '(unreadable)\n'

    section 4 syslog-sink
    cexec ls -l /dev/log 2>&1 || true
    if cexec sh -c 'test -S /dev/log' >/dev/null 2>&1; then
        printf 'dev-log-live-socket: yes\n'
    else
        printf 'dev-log-live-socket: no\n'
        hint 4 "/dev/log does not resolve to a live socket in the cups container; avahi's syslog output (including" \
            "host-name conflict and rename messages) is discarded"
    fi

    section 5 daemon-dbus
    local d_state d_short d_fqdn
    d_state="$(dbus_get GetState 2>/dev/null | sed -n 's/^ *int32 \([0-9]*\).*/\1/p' || true)"
    d_short="$(dbus_get GetHostName 2>/dev/null | sed -n 's/^ *string "\(.*\)".*/\1/p' || true)"
    d_fqdn="$(dbus_get GetHostNameFqdn 2>/dev/null | sed -n 's/^ *string "\(.*\)".*/\1/p' || true)"
    printf 'GetState=%s GetHostName=%s GetHostNameFqdn=%s\n' "${d_state:-unreadable}" "${d_short:-unreadable}" \
        "${d_fqdn:-unreadable}"
    printf 'process-title: %s\n' "$(cexec ps -o args 2>/dev/null | grep '^avahi-daemon:' | head -1 || true)"
    if [[ -n "${d_short}" && "${d_short}" != "${AVAHI_HOSTNAME}" ]]; then
        hint 5 "the daemon runs as '${d_short}' but avahi_hostname is '${AVAHI_HOSTNAME}': the host-name claim was lost"
    fi

    section 6 service-instance-suffix
    local browse suffixes suffix
    browse="$(timeout 30 avahi-browse -t -p -k _ipp._tcp 2>/dev/null || true)"
    suffixes="$(printf '%s\n' "${browse}" | awk -F';' '$1 == "+" { print $4 }' | sed -e 's/\\032/ /g' -e 's/\\064/@/g' |
        sed -n 's/.*@ *//p' | sort -u || true)"
    printf 'instance suffix(es) after @: %s\n' "$(printf '%s' "${suffixes}" | tr '\n' ',' | sed 's/,$//')"
    printf 'daemon short host name: %s\n' "${d_short:-unreadable}"
    while IFS= read -r suffix; do
        if [[ -n "${suffix}" && -n "${d_short}" && "${suffix}" != "${d_short}" ]]; then
            hint 6 "service instance suffix '${suffix}' differs from the daemon host name '${d_short}': the" \
                "service was registered under a stale host name and never re-registered after avahi's rename"
        fi
    done <<<"${suffixes}"

    section 7 start-times
    local c started cups_epoch other_epoch
    started="$(rssh "docker inspect --format '{{.State.StartedAt}}' ${CONTAINER}" 2>/dev/null || true)"
    printf '%s: %s\n' "${CONTAINER}" "${started}"
    cups_epoch="$(date -u -d "${started}" +%s 2>/dev/null || true)"
    for c in "${siblings[@]}"; do
        local s
        s="$(rssh "docker inspect --format '{{.State.StartedAt}}' ${c}" 2>/dev/null || true)"
        printf '%s: %s\n' "${c}" "${s}"
        other_epoch="$(date -u -d "${s}" +%s 2>/dev/null || true)"
        if [[ -n "${cups_epoch}" && -n "${other_epoch}" ]]; then
            local delta=$((cups_epoch - other_epoch))
            [[ "${delta}" -lt 0 ]] && delta=$((-delta))
            if [[ "${delta}" -le 60 ]]; then
                hint 7 "${CONTAINER} and ${c} started ${delta}s apart: a cold-start probe race between sibling avahi" \
                    "daemons is plausible"
            fi
        fi
    done
    if [[ -n "${boot_us}" ]]; then
        boot_utc="$(date -u -d "@$((boot_us / 1000000))" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
        printf 'host boot (UTC): %s\n' "${boot_utc:-unreadable}"
    else
        printf 'host boot (UTC): unreadable\n'
    fi

    section 8 lan-names
    local n out
    for n in "${host_name:+${host_name}.local}" "${AVAHI_HOSTNAME}.local" "${d_fqdn}"; do
        [[ -n "${n}" ]] || continue
        for fam in 4 6; do
            out="$(timeout 8 avahi-resolve-host-name "-${fam}" "${n}" 2>/dev/null | awk '{ print $2; exit }' || true)"
            printf 'forward -%s %s -> %s\n' "${fam}" "${n}" "${out:-no answer}"
        done
    done
    printf 'reverse %s (INFO only) -> %s\n' "${HOST_IP}" \
        "$(timeout 8 avahi-resolve -a "${HOST_IP}" 2>/dev/null | awk '{ print $2; exit }' || true)"

    section 9 sibling-publish-config
    if [[ "${#siblings[@]}" -eq 0 ]]; then
        printf '(no sibling avahi containers found)\n'
    fi
    for c in "${siblings[@]}"; do
        local conf
        conf="$(rssh "docker exec ${c} grep -E '^(publish-addresses|publish-aaaa-on-ipv4|disable-publishing)' \
/etc/avahi/avahi-daemon.conf" 2>/dev/null || true)"
        printf '%s:\n%s\n' "${c}" "${conf:-  (none of the three keys set)}"
        if ! printf '%s\n' "${conf}" | grep -q '^publish-addresses=no'; then
            hint 9 "${c} does not set publish-addresses=no: a second publisher of the shared host IP's reverse" \
                "records is the documented conflict class"
        fi
    done
}

if [[ "${MODE}" == "diagnose" ]]; then
    [[ -n "${OUT}" ]] || OUT="${TMPDIR:-/tmp}/cups-mdns-diagnose-$(date +%s).log"
    diagnose | tee "${OUT}" | mask_stream
    exit 0
fi

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

# Step 6: the read-only checks. Prints the PASS/FAIL/INFO/SKIP lines and increments FAILS; the caller decides
# what the totals mean (--assert prints RESULT, --watch classifies per round).
run_checks() {
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

    # -k keeps the raw service type (`_ipp._tcp`) in field 5; without it avahi prints the friendly name from its type db.
    BROWSE_OUT="$(timeout 60 avahi-browse -t -r -p -k _ipp._tcp 2>/dev/null || true)"
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
}

fmt_mmss() {
    local secs="$1"
    [[ "${secs}" -ge 0 ]] || secs=0
    printf '%02d:%02d' $((secs / 60)) $((secs % 60))
}

iso_of() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'unknown'; }

read_started_at() { rssh "docker inspect --format '{{.State.StartedAt}}' ${CONTAINER}" 2>/dev/null || true; }

read_app_state() {
    rssh "ha apps info ${SLUG} --raw-json" 2>/dev/null | jq -r '.data.state // empty' 2>/dev/null || true
}

# Watch-only check: Avahi logs `Host name conflict, retrying with <name>-2` when it loses the claim to another
# announcer. Only lines since the container start count, so earlier boots in an accumulated log are ignored.
# Leaves the fetched log in LOG_TEXT for the first-failure context block.
check_host_name_conflict() {
    local lines count first
    if ! LOG_TEXT="$(rssh "docker logs --since ${STARTED_AT} ${CONTAINER} 2>&1")"; then
        LOG_TEXT=""
        fail host-name-conflict "could not read the container log since ${STARTED_AT}"
        return 0
    fi
    lines="$(printf '%s\n' "${LOG_TEXT}" | grep -a 'Host name conflict' || true)"
    if [[ -z "${lines}" ]]; then
        pass host-name-conflict "no 'Host name conflict' line in the container log since the container start"
        return 0
    fi
    count="$(printf '%s\n' "${lines}" | wc -l)"
    first="$(printf '%s\n' "${lines}" | head -1)"
    fail host-name-conflict "${count} 'Host name conflict' line(s) since the container start: ${first}"
    printf '%s\n' "${lines}" | sed -n '2,5p' | sed 's/^/  | /'
}

# Watch-only check: the premise of the observation is an add-on container that is never restarted.
check_continuity() {
    local state="$1" cur="$2"
    if [[ "${state}" != "started" ]]; then
        fail continuity "add-on state is '${state:-unreadable}', expected started (container StartedAt ${STARTED_AT})"
    elif [[ -z "${cur}" || "${cur}" != "${STARTED_AT}" ]]; then
        fail continuity "container StartedAt changed from ${STARTED_AT} to ${cur:-unreadable}: the container restarted"
    else
        pass continuity "container StartedAt unchanged (${STARTED_AT}), add-on state started"
    fi
}

# Per-round quiet check: no local container whose name or image mentions cups. Sets ROUND_QUIET to yes, NO:<names>
# or unknown.
check_quiet_round() {
    local ps names
    ROUND_QUIET="unknown"
    if [[ -z "${LOCAL_ENGINE}" ]]; then
        info quiet "no local container engine (docker/podman) on this workstation; per-round quiet check skipped"
        return 0
    fi
    if ! ps="$("${LOCAL_ENGINE}" ps --format '{{.Names}} {{.Image}}' 2>/dev/null)"; then
        info quiet "'${LOCAL_ENGINE} ps' failed; per-round quiet check skipped"
        return 0
    fi
    names="$(printf '%s\n' "${ps}" | awk 'tolower($0) ~ /cups/ { print $1 }' | sort -u | tr '\n' ',' | sed 's/,$//')"
    if [[ -z "${names}" ]]; then
        ROUND_QUIET="yes"
    else
        ROUND_QUIET="NO:${names}"
    fi
}

# Post-hoc check of the workstation's container events from the quiet-window start. Sets EVENTS_STATE
# (OK|UNVERIFIED|UNAVAILABLE) and EVENT_MATCHES (lines "<epoch> <action> <name> <image>" of cups containers that were
# created, started or restarted). OK means an empty answer really means "nothing happened": the engine keeps a
# persistent history (podman with the journald or file event logger), or the answer itself shows events dated close
# to the window start, so the history demonstrably reaches back that far.
check_local_events() {
    local since="$1" raw rc=0 version logger first
    EVENTS_STATE="UNAVAILABLE"
    EVENT_MATCHES=""
    [[ -n "${LOCAL_ENGINE}" ]] || return 0
    raw="$(timeout 60 "${LOCAL_ENGINE}" events --since "${since}" --until "$(date +%s)" --filter type=container \
        --format '{{json .}}' 2>/dev/null)" || rc=$?
    [[ "${rc}" -eq 0 ]] || return 0
    EVENT_MATCHES="$(printf '%s\n' "${raw}" | jq -R -r '
        fromjson? | select(type == "object")
        | (.Action // .Status // "") as $a
        | (.Actor.Attributes.name // .Name // "") as $n
        | (.Actor.Attributes.image // .Image // "") as $i
        | select(($a == "create" or $a == "start" or $a == "restart") and (($n + " " + $i) | test("cups"; "i")))
        | "\((.time // ((.timeNano // 0) / 1000000000) // 0) | floor) \($a) \($n) \($i)"' 2>/dev/null |
        sort -n || true)"
    version="$("${LOCAL_ENGINE}" --version 2>&1 || true)"
    logger="$("${LOCAL_ENGINE}" info --format '{{.Host.EventLogger}}' 2>/dev/null || true)"
    if grep -qi podman <<<"${version}" && [[ "${logger}" == "journald" || "${logger}" == "file" ]]; then
        EVENTS_STATE="OK"
        return 0
    fi
    first="$(printf '%s\n' "${raw}" | jq -R -r '
        fromjson? | select(type == "object") | ((.time // ((.timeNano // 0) / 1000000000) // 0) | floor)
        | select(. > 0)' 2>/dev/null | sort -n | head -1 || true)"
    if [[ -n "${first}" && $((first - since)) -le 900 ]]; then
        EVENTS_STATE="OK"
    else
        EVENTS_STATE="UNVERIFIED"
    fi
}

# --watch: repeat run_checks at fixed due times (start + n*interval, so the cadence does not drift), then classify.
watch_loop() {
    local rounds=$((WATCH_SECONDS / INTERVAL + 1)) n=1 now due t age cur cur_epoch cur_state prev verdict
    local watch_start window_start covers
    STARTED_AT="$(read_started_at)"
    STARTED_EPOCH="$(date -u -d "${STARTED_AT}" +%s 2>/dev/null || true)"
    [[ -n "${STARTED_EPOCH}" ]] || die "could not read the StartedAt of ${CONTAINER}"
    LOCAL_ENGINE=""
    local engine
    for engine in docker podman; do
        if command -v "${engine}" >/dev/null 2>&1; then
            LOCAL_ENGINE="${engine}"
            break
        fi
    done
    watch_start="$(date +%s)"
    case "${QUIET_SINCE}" in
    container-start) window_start="${STARTED_EPOCH}" ;;
    watch-start) window_start="${watch_start}" ;;
    *)
        if [[ "${QUIET_SINCE}" =~ ^[0-9]{9,}$ ]]; then
            window_start="${QUIET_SINCE}"
        else
            window_start="$(date -u -d "${QUIET_SINCE}" +%s)"
        fi
        ;;
    esac
    printf 'WATCH START: host=%s container=%s container-start=%s duration=%ss interval=%ss rounds=%s\n' "${HOST}" \
        "${CONTAINER}" "$(iso_of "${STARTED_EPOCH}")" "${WATCH_SECONDS}" "${INTERVAL}" "${rounds}"

    local -a r_failed=() r_quiet=() r_end=() r_age=()
    local first_fail="" first_fail_t="" first_fail_age="" restarts=0
    prev="${STARTED_AT}"
    while [[ "${n}" -le "${rounds}" ]]; do
        now="$(date +%s)"
        t=$((now - watch_start))
        cur="$(read_started_at)"
        cur_state="$(read_app_state)"
        cur_epoch="$(date -u -d "${cur}" +%s 2>/dev/null || true)"
        age=$((now - ${cur_epoch:-${STARTED_EPOCH}}))
        printf 'WATCH round=%s t=+%s age=+%s\n' "${n}" "$(fmt_mmss "${t}")" "$(fmt_mmss "${age}")"
        FAILS=0
        [[ -z "${cur}" || "${cur}" == "${prev}" ]] || restarts=$((restarts + 1))
        [[ -z "${cur}" ]] || prev="${cur}"
        check_continuity "${cur_state}" "${cur}"
        run_checks
        check_host_name_conflict
        check_quiet_round
        printf 'WATCH round=%s quiet=%s\n' "${n}" "${ROUND_QUIET}"
        if [[ "${FAILS}" -eq 0 ]]; then
            verdict="PASS"
            r_failed[n]=0
        else
            verdict="FAIL(${FAILS})"
            r_failed[n]=1
        fi
        printf 'WATCH round=%s verdict=%s\n' "${n}" "${verdict}"
        r_quiet[n]="${ROUND_QUIET}"
        r_age[n]="${age}"
        r_end[n]="$(date +%s)"
        if [[ "${FAILS}" -gt 0 && -z "${first_fail}" ]]; then
            first_fail="${n}"
            first_fail_t="${t}"
            first_fail_age="${age}"
            printf 'WATCH CONTEXT round=%s (container log since start, up to 40 matching lines)\n' "${n}"
            printf '%s\n' "${LOG_TEXT}" |
                grep -aE 'Host name conflict|Server startup complete|\[avahi-guard\]|Withdrawing|Registering' |
                head -40 | sed 's/^/  | /' || true
        fi
        if [[ "${n}" -lt "${rounds}" ]]; then
            due=$((watch_start + n * INTERVAL))
            now="$(date +%s)"
            [[ "${now}" -ge "${due}" ]] || sleep $((due - now))
        fi
        n=$((n + 1))
    done

    check_local_events "${window_start}"
    local ev_first="" ev_line quiet_violations=0 r
    if [[ -n "${EVENT_MATCHES}" ]]; then
        ev_first="$(printf '%s\n' "${EVENT_MATCHES}" | head -1 | cut -d' ' -f1)"
    fi

    # milestones: the first round at or beyond a container age decides that milestone
    local ms="" thr label verdict_ms
    for thr in 120 600 1800; do
        verdict_ms="NOT-REACHED"
        for ((r = 1; r <= rounds; r++)); do
            if [[ "${r_age[r]}" -ge "${thr}" ]]; then
                if [[ "${r_failed[r]}" -eq 0 ]]; then verdict_ms="PASS"; else verdict_ms="FAIL"; fi
                break
            fi
        done
        label="age+$((thr / 60))m"
        ms="${ms:+${ms} }${label}=${verdict_ms}"
    done
    printf 'WATCH MILESTONES: %s\n' "${ms}"

    covers="no"
    [[ "${window_start}" -gt "${STARTED_EPOCH}" ]] || covers="yes"
    printf 'WATCH QUIET-WINDOW: since=%s container-start=%s covers-container-start=%s events=%s\n' \
        "$(iso_of "${window_start}")" "$(iso_of "${STARTED_EPOCH}")" "${covers}" "${EVENTS_STATE}"
    while IFS= read -r ev_line; do
        [[ -n "${ev_line}" ]] || continue
        quiet_violations=$((quiet_violations + 1))
        printf 'WATCH QUIET-VIOLATION: local container event %s %s\n' "$(iso_of "${ev_line%% *}")" "${ev_line#* }"
    done <<<"${EVENT_MATCHES}"

    # classification: a round is quiet unless a cups container was running during it or a matching local event
    # happened at or before its end
    local failed_quiet=0 tainted=0
    for ((r = 1; r <= rounds; r++)); do
        if [[ "${r_quiet[r]}" == NO:* ]]; then
            quiet_violations=$((quiet_violations + 1))
            tainted=1
        elif [[ -n "${ev_first}" && "${ev_first}" -le "${r_end[r]}" ]]; then
            tainted=1
        elif [[ "${r_failed[r]}" -eq 1 ]]; then
            failed_quiet=1
        fi
    done
    [[ -z "${EVENT_MATCHES}" ]] || tainted=1
    local ff="none"
    if [[ -n "${first_fail}" ]]; then
        ff="round ${first_fail} t=+$(fmt_mmss "${first_fail_t}") age=+$(fmt_mmss "${first_fail_age}")"
    fi
    printf 'WATCH SUMMARY: rounds=%s duration=%s first-failure=%s quiet-violations=%s restarts=%s\n' "${rounds}" \
        "$(fmt_mmss $(($(date +%s) - watch_start)))" "${ff}" "${quiet_violations}" "${restarts}"

    if [[ "${failed_quiet}" -eq 1 ]]; then
        printf 'WATCH RESULT: FAIL\n'
        return 1
    fi
    if [[ "${tainted}" -eq 1 ]]; then
        printf 'WATCH RESULT: INVALID\n'
        return 3
    fi
    if [[ "${EVENTS_STATE}" != "OK" ]]; then
        printf 'WATCH RESULT: PASS-UNVERIFIED-QUIET\n'
        return 4
    fi
    printf 'WATCH RESULT: PASS\n'
    return 0
}

if [[ "${MODE}" == "watch" ]]; then
    watch_loop
    exit $?
fi

run_checks
if [[ "${FAILS}" -eq 0 ]]; then
    printf 'RESULT: PASS\n'
    exit 0
fi
printf 'RESULT: FAIL (%s failed)\n' "${FAILS}"
exit 1
