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

BASH_BIN="$(command -v bash)"
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
    OUT="$(PATH="${LIVE_PATH:-${BIN}:${PATH}}" STUB_STATE="${STATE}" "${BASH_BIN}" "${LIVE_SCRIPT}" \
        --host stub-host --host-ip 192.0.2.10 "$@" 2>&1)"
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

# ---------------------------------------------------------------------------------------------------------------
# Fixture helpers for the classification tests.
# ---------------------------------------------------------------------------------------------------------------
# Docker-shaped container event (.Action / .Actor.Attributes.name|image) and podman-shaped event (.Status/.Name/.Image).
ev_docker() { # name epoch action [image]
    printf '{"Type":"container","Action":"%s","Actor":{"Attributes":{"name":"%s","image":"%s"}},"time":%s}\n' \
        "$3" "$1" "${4:-img}" "$2"
}
ev_podman() { # name epoch status [image]
    printf '{"Name":"%s","Image":"%s","Status":"%s","Type":"container","time":%s}\n' "$1" "${4:-img}" "$3" "$2"
}
iso_at() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }
plain_docker_engine() {
    printf 'Docker version 27.0.1, build abc\n' >"${STATE}/engine_version"
    rm -f "${STATE}/engine_logger"
}
# A container started SA seconds ago; prints the epoch.
start_container_ago() {
    local sa=$(($(date +%s) - $1))
    iso_at "${sa}" >"${STATE}/started_at"
    printf '%s' "${sa}"
}

# ---------------------------------------------------------------------------------------------------------------
section "test 1: first FAIL names round, time and container age, and prints the log context"
reset_state
printf '%s\n' '[avahi-guard] host name claimed: cups' 'Server startup complete.' 'unrelated noise' >"${STATE}/logs"
printf '2' >"${STATE}/fqdn_flip_after"
run_live --watch-seconds 2 --interval 1
expect_rc 1 "fqdn flips after round 2"
expect_out '^WATCH RESULT: FAIL$' "result FAIL"
expect_out '^FAIL daemon-fqdn:' "daemon-fqdn fails"
expect_out '^WATCH round=2 verdict=PASS$' "round 2 still passed"
expect_out '^WATCH round=3 verdict=FAIL\(1\)$' "round 3 is the first failing round"
expect_out '^WATCH SUMMARY: .*first-failure=round 3 t=\+00:0[2-4] age=\+0[0-9]:[0-9]{2}' \
    "summary names round 3, its t and age"
expect_out '^WATCH CONTEXT round=3' "context block header"
expect_out '\[avahi-guard\] host name claimed' "context block holds the guard log line"
expect_no_out 'unrelated noise' "context block filters unrelated log lines"

section "test 2: a non-quiet workstation makes the result INVALID, a quiet one FAIL"
reset_state
printf 'cups-vf-demo cups-guard-verify:1\n' >"${STATE}/local_ps"
printf '1' >"${STATE}/fqdn_flip_after"
run_live --watch-seconds 1 --interval 1
expect_rc 3 "local cups container running and a failing round"
expect_out '^WATCH round=1 quiet=NO:cups-vf-demo' "round 1 prints quiet=NO with the container name"
expect_out '^WATCH RESULT: INVALID$' "result INVALID"
reset_state
printf 'cups-vf-demo cups-guard-verify:1\n' >"${STATE}/local_ps"
run_live --watch-seconds 1 --interval 1
expect_rc 3 "local cups container running, all rounds passing"
expect_out '^WATCH RESULT: INVALID$' "passing but non-quiet is INVALID"
reset_state
printf 'homeassistant ghcr.io/home-assistant/x\n' >"${STATE}/local_ps"
run_live --watch-seconds 1 --interval 1
expect_rc 0 "an unrelated local container does not break the quiet check"
expect_out '^WATCH round=1 quiet=yes$' "round 1 prints quiet=yes"

section "test 3: post-hoc events cover the gap between the container start and the watch start"
reset_state
SA="$(start_container_ago 300)"
ev_docker cups-vf-demo "$((SA + 60))" create >"${STATE}/events_fixture"
run_live --watch-seconds 1 --interval 1
expect_rc 3 "create event 60 s after the container start, empty docker ps"
expect_out '^WATCH RESULT: INVALID$' "result INVALID"
expect_out '^WATCH QUIET-WINDOW: since=.* covers-container-start=yes' "quiet window covers the container start"
if grep -Eq -- "--since ${SA}( |\$)" "${STATE}/events_args.log" 2>/dev/null; then
    ok "docker events was queried --since the container StartedAt epoch"
else
    bad "docker events --since is not the StartedAt epoch ${SA}: $(cat "${STATE}/events_args.log" 2>/dev/null)"
fi
# A failing round that comes after the matching event is not a quiet round.
printf '0' >"${STATE}/fqdn_flip_after"
run_live --watch-seconds 1 --interval 1
expect_rc 3 "failing rounds after a matching event are INVALID, not FAIL"

section "test 3b: --quiet-since moves the window"
reset_state
SA="$(start_container_ago 300)"
ev_docker cups-vf-demo "$((SA + 60))" create >"${STATE}/events_fixture"
run_live --watch-seconds 1 --interval 1 --quiet-since "$((SA + 120))"
expect_rc 0 "an epoch later than the event hides it"
expect_out "^WATCH QUIET-WINDOW: since=$(iso_at "$((SA + 120))") .*covers-container-start=no events=OK$" \
    "window opens at the given epoch and does not cover the container start"
ev_podman cups-vf-demo "$((SA + 60))" start localhost/cups-x >"${STATE}/events_fixture"
run_live --watch-seconds 1 --interval 1 --quiet-since "$((SA - 30))"
expect_rc 3 "an epoch earlier than StartedAt finds a podman-shaped event"
expect_out 'covers-container-start=yes' "earlier window covers the container start"
run_live --watch-seconds 1 --interval 1 --quiet-since "$(iso_at "$((SA - 30))")"
expect_rc 3 "an ISO timestamp is accepted for --quiet-since"
run_live --watch-seconds 1 --interval 1 --quiet-since watch-start
expect_rc 0 "watch-start does not reach back to the event"
expect_out 'covers-container-start=no' "watch-start does not cover the container start"
run_live --watch-seconds 1 --interval 1 --quiet-since nonsense
expect_rc 2 "an unparsable --quiet-since is a usage error"

section "test 4: continuity -- a restarted container is a FAIL"
reset_state
printf '2' >"${STATE}/started_change_after"
iso_ago 10 >"${STATE}/started_at2"
run_live --watch-seconds 2 --interval 1
expect_rc 1 "StartedAt changes between rounds"
expect_out '^FAIL continuity:' "continuity line"
expect_out '^WATCH SUMMARY: .*restarts=[1-9]' "summary counts the restart"

section "test 5: milestones"
reset_state
start_container_ago 180 >/dev/null
run_live --watch-seconds 1 --interval 1
expect_out '^WATCH MILESTONES: age\+2m=PASS age\+10m=NOT-REACHED age\+30m=NOT-REACHED$' "3-minute-old container"
reset_state
start_container_ago 720 >/dev/null
run_live --watch-seconds 1 --interval 1
expect_out '^WATCH MILESTONES: age\+2m=PASS age\+10m=PASS age\+30m=NOT-REACHED$' "12-minute-old container"
reset_state
start_container_ago 180 >/dev/null
printf '0' >"${STATE}/fqdn_flip_after"
run_live --watch-seconds 1 --interval 1
expect_out '^WATCH MILESTONES: age\+2m=FAIL age\+10m=NOT-REACHED' "a failing first round at the milestone"

section "test 6: host-name-conflict check"
reset_state
printf 'avahi-daemon[12]: Host name conflict, retrying with cups-2\n' >"${STATE}/logs"
run_live --watch-seconds 1 --interval 1
expect_rc 1 "conflict line in the container log"
expect_out '^FAIL host-name-conflict:.*Host name conflict, retrying with cups-2' "FAIL names the matching line"
if grep -Fq "docker logs --since $(cat "${STATE}/started_at") " "${STATE}/ssh.log"; then
    ok "the log is read --since the container StartedAt"
else
    bad "no 'docker logs --since <StartedAt>' command seen"
fi
reset_state
run_live --watch-seconds 1 --interval 1
expect_out '^PASS host-name-conflict:' "a clean log passes the conflict check"

section "test 7: read-only contract"
reset_state
printf '%s\n' 'Host name conflict, retrying with cups-2' >"${STATE}/logs"
printf '1' >"${STATE}/fqdn_flip_after"
run_live --watch-seconds 2 --interval 1
allow='^(true|ha apps info [A-Za-z0-9_]+ --raw-json|docker ps --format .*|docker inspect --format .*|docker logs .*|docker exec [A-Za-z0-9_]+ .*)$'
deny='(^|[ ;|&])(ha (apps|addons|core|supervisor|host) (restart|reboot|update|start|stop|install|uninstall|rebuild)|docker (restart|stop|start|kill|rm|run))( |$)|SetHostName|lpadmin|cupsctl'
violations=0
while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    if ! grep -Eq -- "${allow}" <<<"${line}" || grep -Eq -- "${deny}" <<<"${line}"; then
        bad "remote command outside the read-only whitelist: ${line}"
        violations=$((violations + 1))
    fi
done <"${STATE}/ssh.log"
[[ "${violations}" -eq 0 ]] && ok "every remote command is a whitelisted reader"
printf '      remote command shapes seen:\n'
sed -E 's/^(docker exec) [^ ]+ ([^ ]+).*/\1 <container> \2/; s/^(docker (ps|inspect|logs)( --since)?) .*/\1 .../; s/^(ha apps info) .*/\1 <slug> --raw-json/' \
    "${STATE}/ssh.log" | sort -u | sed 's/^/        /'

section "test 8: events history verification"
reset_state
run_live --watch-seconds 1 --interval 1
expect_rc 0 "(a) podman with the journald event logger, empty events"
expect_out 'events=OK$' "(a) events=OK"
expect_out '^WATCH RESULT: PASS$' "(a) WATCH RESULT: PASS"
reset_state
plain_docker_engine
run_live --watch-seconds 1 --interval 1
expect_rc 4 "(b) plain docker engine, empty events"
expect_out 'events=UNVERIFIED$' "(b) events=UNVERIFIED"
expect_out '^WATCH RESULT: PASS-UNVERIFIED-QUIET$' "(b) PASS-UNVERIFIED-QUIET"
expect_no_out '^WATCH RESULT: PASS$' "(b) no closing PASS line"
reset_state
: >"${STATE}/events_fail"
run_live --watch-seconds 1 --interval 1
expect_rc 4 "(c) events command fails"
expect_out 'events=UNAVAILABLE$' "(c) events=UNAVAILABLE"
expect_no_out '^WATCH RESULT: PASS$' "(c) no closing PASS line"
reset_state
plain_docker_engine
SA="$(start_container_ago 300)"
ev_docker homeassistant "$((SA + 100))" start ghcr.io/home-assistant/x >"${STATE}/events_fixture"
run_live --watch-seconds 1 --interval 1
expect_rc 0 "(d) plain docker engine with a non-cups event near the window start"
expect_out 'events=OK$' "(d) events=OK"
reset_state
NOENG="${TMP}/bin-noengine"
mkdir -p "${NOENG}"
for t in ssh avahi-resolve-host-name avahi-browse avahi-resolve; do cp "${BIN}/${t}" "${NOENG}/${t}"; done
for t in bash env jq timeout sed awk grep head tail tr sort uniq date sleep cat cut wc mktemp; do
    src="$(command -v "${t}" 2>/dev/null)" && ln -sf "${src}" "${NOENG}/${t}"
done
LIVE_PATH="${NOENG}" run_live --watch-seconds 1 --interval 1
expect_rc 4 "(e) no docker or podman binary"
expect_out 'events=UNAVAILABLE$' "(e) events=UNAVAILABLE"
expect_out '^INFO quiet:.*no local container engine' "(e) the per-round quiet check is an INFO line"
unset LIVE_PATH

section "test 9: precedence"
reset_state
plain_docker_engine
printf '1' >"${STATE}/fqdn_flip_after"
run_live --watch-seconds 1 --interval 1
expect_rc 1 "a failing quiet round is FAIL even with unverified events"
reset_state
plain_docker_engine
printf 'cups-vf-demo cups-guard-verify:1\n' >"${STATE}/local_ps"
run_live --watch-seconds 1 --interval 1
expect_rc 3 "a non-quiet round is INVALID even with unverified events"

printf '\n'
if [[ "${FAILURES}" -eq 0 ]]; then
    printf '%sRESULT: PASS%s\n' "${GREEN}" "${NC}"
    exit 0
fi
printf '%sRESULT: FAIL (%s check(s) failed)%s\n' "${RED}" "${FAILURES}" "${NC}"
exit 1
