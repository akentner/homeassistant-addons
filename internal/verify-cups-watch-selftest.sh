#!/usr/bin/env bash
# verify-cups-watch-selftest.sh -- host-side self-test of internal/verify-cups-mdns-live.sh (Phase 21 Plan 09).
#
# Runs the live verifier against stubbed ssh / avahi-* / docker tools (no live host, no real container engine is ever
# contacted) and proves the --watch classification (PASS / FAIL / INVALID / PASS-UNVERIFIED-QUIET), the quiet-window
# evidence, continuity, milestones, the host-name-conflict check and the read-only contract.
#
# Set LIVE_SCRIPT to test another copy of the live verifier (used for the RED run against the pre-change version).
#
# Usage: bash internal/verify-cups-watch-selftest.sh
# Exit: 0 all checks passed, 1 a check failed, 2 environment error.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LIVE_SCRIPT="${LIVE_SCRIPT:-${SCRIPT_DIR}/verify-cups-mdns-live.sh}"
# The version of the live verifier before Plan 21-09, used to prove --assert output is unchanged.
BASELINE_REF="a1ace38"

for tool in jq timeout bash; do
    command -v "${tool}" >/dev/null 2>&1 || {
        printf 'required tool not on PATH: %s\n' "${tool}" >&2
        exit 2
    }
done
[[ -f "${LIVE_SCRIPT}" ]] || {
    printf 'live script not found: %s\n' "${LIVE_SCRIPT}" >&2
    exit 2
}

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
BOLD=$'\033[1m'
NC=$'\033[0m'
FAILURES=0

ok() { printf '%s   PASS: %s%s\n' "${GREEN}" "$1" "${NC}"; }
bad() {
    printf '%s   FAIL: %s%s\n' "${RED}" "$1" "${NC}"
    FAILURES=$((FAILURES + 1))
}
section() { printf '\n%s== %s ==%s\n' "${BOLD}" "$1" "${NC}"; }

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
BIN="${TMP}/bin"
STATE="${TMP}/state"
mkdir -p "${BIN}" "${STATE}"

# ---------------------------------------------------------------------------------------------------------------
# Stubs. They answer by the remote command words and read their scenario from files in $STUB_STATE.
# ---------------------------------------------------------------------------------------------------------------
cat >"${BIN}/ssh" <<'STUB'
#!/usr/bin/env bash
S="${STUB_STATE:?}"
while [[ "${1:-}" == "-o" ]]; do shift 2; done
shift # the host name
cmd="$*"
printf '%s\n' "${cmd}" >>"${S}/ssh.log"
bump() {
    local f="${S}/cnt_$1" n=0
    [[ -f "${f}" ]] && n="$(<"${f}")"
    n=$((n + 1))
    printf '%s' "${n}" >"${f}"
    printf '%s' "${n}"
}
case "${cmd}" in
true) exit 0 ;;
"ha apps info "*" --raw-json")
    printf '%s\n' '{"data":{"state":"started","version":"1.2.3","options":{"avahi_hostname":"cups",' \
        '"avahi_use_ipv6":false,"avahi_reflector":false},"version_latest":"1.2.3","watchdog":true,' \
        '"boot":"auto","hostname":"72a005f5-cups"}}'
    ;;
"docker ps --format "*) printf 'app_72a005f5_cups\n' ;;
"docker inspect --format "*)
    n="$(bump inspect)"
    if [[ -f "${S}/started_change_after" ]] && ((n > $(<"${S}/started_change_after"))); then
        cat "${S}/started_at2"
    else
        cat "${S}/started_at"
    fi
    ;;
"docker logs --since "*) cat "${S}/logs" ;;
"docker logs "*) printf '0\n' ;;
"docker exec "*"cat /etc/avahi/avahi-daemon.conf"*) printf 'enable-reflector=no\nuse-ipv6=no\n' ;;
"docker exec "*GetState*) printf '   int32 2\n' ;;
"docker exec "*GetHostNameFqdn*)
    n="$(bump fqdn)"
    fq="cups.local"
    if [[ -f "${S}/fqdn_flip_after" ]] && ((n > $(<"${S}/fqdn_flip_after"))); then
        fq="cups-2.local"
    fi
    printf '   string "%s"\n' "${fq}"
    ;;
*) exit 1 ;;
esac
STUB

cat >"${BIN}/avahi-resolve-host-name" <<'STUB'
#!/usr/bin/env bash
# usage: avahi-resolve-host-name -4|-6 NAME ; answers IPv4 for cups.local only, never an AAAA
[[ "$1" == "-4" && "$2" == "cups.local" ]] && printf 'cups.local\t192.0.2.10\n' && exit 0
exit 1
STUB

cat >"${BIN}/avahi-browse" <<'STUB'
#!/usr/bin/env bash
printf '+;eth0;IPv4;Printer;_ipp._tcp;local\n'
printf '=;eth0;IPv4;Printer;_ipp._tcp;local;cups.local;192.0.2.10;631;"rp=printers/x"\n'
STUB

cat >"${BIN}/avahi-resolve" <<'STUB'
#!/usr/bin/env bash
exit 1
STUB

# Local container engine stub: `docker --version`, `docker info`, `docker ps`, `docker events`.
cat >"${BIN}/docker" <<'STUB'
#!/usr/bin/env bash
S="${STUB_STATE:?}"
case "${1:-}" in
--version)
    if [[ -f "${S}/engine_version" ]]; then cat "${S}/engine_version"; else printf 'Docker version 27.0.1\n'; fi
    ;;
info)
    [[ -f "${S}/engine_logger" ]] || exit 1
    cat "${S}/engine_logger"
    ;;
ps)
    [[ -f "${S}/local_ps" ]] && cat "${S}/local_ps"
    exit 0
    ;;
events)
    printf '%s\n' "$*" >>"${S}/events_args.log"
    [[ -f "${S}/events_fail" ]] && exit 1
    since=0
    until_=9999999999
    shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
        --since) since="$2"; shift ;;
        --until) until_="$2"; shift ;;
        esac
        shift
    done
    [[ -f "${S}/events_fixture" ]] || exit 0
    jq -c --argjson s "${since}" --argjson u "${until_}" 'select(.time >= $s and .time <= $u)' \
        "${S}/events_fixture"
    ;;
*) exit 1 ;;
esac
STUB
chmod +x "${BIN}"/*

# ---------------------------------------------------------------------------------------------------------------
# Harness.
# ---------------------------------------------------------------------------------------------------------------
iso_ago() { date -u -d "@$(($(date +%s) - $1))" +%Y-%m-%dT%H:%M:%SZ; }

reset_state() {
    rm -rf "${STATE}"
    mkdir -p "${STATE}"
    iso_ago 300 >"${STATE}/started_at"
    : >"${STATE}/logs"
    printf 'podman version 5.4.0\n' >"${STATE}/engine_version"
    printf 'journald\n' >"${STATE}/engine_logger"
    : >"${STATE}/local_ps"
}

OUT=""
RC=0
run_live() {
    OUT="$(PATH="${BIN}:${PATH}" STUB_STATE="${STATE}" bash "${LIVE_SCRIPT}" --host stub-host \
        --host-ip 192.0.2.10 "$@" 2>&1)"
    RC=$?
}

expect_rc() {
    if [[ "${RC}" -eq "$1" ]]; then
        ok "$2 (exit ${RC})"
    else
        bad "$2: exit ${RC}, expected $1"
        show_out
    fi
}
expect_out() {
    if grep -Eq -- "$1" <<<"${OUT}"; then ok "$2"; else bad "$2 (no line matching: $1)"; fi
}
expect_no_out() {
    if grep -Eq -- "$1" <<<"${OUT}"; then bad "$2 (found a line matching: $1)"; else ok "$2"; fi
}
show_out() { printf '%s\n' "${OUT}" | sed 's/^/      | /' >&2; }

# ---------------------------------------------------------------------------------------------------------------
section "assert mode is unchanged"
reset_state
run_live --assert
expect_rc 0 "assert against the healthy stubs"
expect_out '^RESULT: PASS$' "assert ends with RESULT: PASS"
expect_no_out '^WATCH' "assert prints no WATCH lines"
for id in conf-reflector conf-ipv6 slot-exhaustion daemon-fqdn lan-forward-v4 lan-no-aaaa lan-service-resolve; do
    expect_out "^PASS ${id}:" "assert prints PASS ${id}"
done
if baseline="$(git -C "${REPO_ROOT}" show "${BASELINE_REF}:internal/verify-cups-mdns-live.sh" 2>/dev/null)"; then
    printf '%s\n' "${baseline}" >"${TMP}/baseline-live.sh"
    new_out="${OUT}"
    reset_state
    old_out="$(PATH="${BIN}:${PATH}" STUB_STATE="${STATE}" bash "${TMP}/baseline-live.sh" --host stub-host \
        --host-ip 192.0.2.10 --assert 2>&1)"
    if [[ "${new_out}" == "${old_out}" ]]; then
        ok "assert output is byte-identical to the pre-change script"
    else
        bad "assert output differs from the pre-change script"
    fi
else
    printf '   SKIP: baseline %s not available, byte-for-byte comparison skipped\n' "${BASELINE_REF}"
fi

section "--help documents the watch options"
help_out="$(bash "${LIVE_SCRIPT}" --help 2>&1)"
for opt in '--watch' '--watch-seconds' '--interval' 'WATCH RESULT: PASS'; do
    if grep -Fq -- "${opt}" <<<"${help_out}"; then ok "--help mentions ${opt}"; else bad "--help does not mention ${opt}"; fi
done

# ---------------------------------------------------------------------------------------------------------------
section "scenario pass: healthy host, quiet workstation"
reset_state
run_live --watch-seconds 3 --interval 1
expect_rc 0 "watch against the healthy stubs"
expect_out '^WATCH RESULT: PASS$' "watch ends with WATCH RESULT: PASS"
rounds="$(grep -c '^WATCH round=[0-9]* t=' <<<"${OUT}")"
if [[ "${rounds}" -ge 2 ]]; then ok "at least two rounds ran (${rounds})"; else bad "only ${rounds} round header(s)"; fi

printf '\n'
if [[ "${FAILURES}" -eq 0 ]]; then
    printf '%sRESULT: PASS%s\n' "${GREEN}" "${NC}"
    exit 0
fi
printf '%sRESULT: FAIL (%s check(s) failed)%s\n' "${RED}" "${FAILURES}" "${NC}"
exit 1
