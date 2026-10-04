# shellcheck shell=bash
#
# cups-test-isolation.sh -- sourced library for every local verifier that starts the cups add-on image
# (internal/verify-cups-*.sh). Never executed directly, hence no shebang and no top-level side effects.
#
# Why it exists (Phase 21 Plan 08, D-11): the live add-on lost its fixed host name `cups.local` because our own
# local test containers announced it on the real LAN. The Phase 22 paperless verifier ran containers with the
# add-on default `avahi_hostname: "cups"`; podman's pasta networking bridges container multicast to the real LAN,
# so the live avahi saw a unique-record conflict and renamed itself (journal timing: container start 09:14:55,
# `Host name conflict, retrying with cups-2` at 09:14:57). A test container must never be able to do that again.
#
# Two layers, both enforced here:
#   1. Refusal: every container start validates the mounted /data/options.json first and refuses (exit 2, docker
#      never called) unless it carries an explicit avahi_hostname other than the add-on default `cups`.
#   2. Isolation: containers run with NET_ADMIN and switch `multicast` off on every interface except `lo` before
#      the add-on starts. avahi then joins no mDNS group on any real interface, so no packet reaches the LAN, yet
#      it still reaches the running state with its configured name and unicast traffic (host.docker.internal
#      stub servers) is untouched. `--network none` was rejected: it breaks the cupsd Listen assertion.
#      cups_lan_run is the only non-isolated entry point; it is for scenarios that must see real mDNS and still
#      enforces the unique-name rule.
#
# Do not run the verifiers that use this library while a live proof is in progress (Plan 21-10).
#
# API (IMAGE is the image reference, DOCKER_RUN_OPTIONS are plain `docker run` options incl. the -v /data mount):
#   cups_test_hostname TAG                      -> prints cups-vf-<TAG>-<STAMP>
#   cups_isolated_run  IMAGE [OPTIONS...]       -> isolated, runs the image's own CMD (/run.sh) via a wrapper
#   cups_isolated_bash IMAGE SCRIPT [OPTIONS...] -> isolated, bash entrypoint, runs SCRIPT after muting
#   cups_lan_run       IMAGE [OPTIONS...]       -> NOT isolated, unique-name rule only
#
# Environment: CUPS_TEST_STAMP (default: epoch seconds), CUPS_TEST_TIMEOUT (seconds; wraps docker run in
# `timeout`), CUPS_TEST_MUTE_SNIPPET (TEST-ONLY knob: replaces the multicast-off snippet; set it to `:` to prove
# the isolation assertions can fail).

CUPS_TEST_STAMP="${CUPS_TEST_STAMP:-$(date +%s)}"

# POSIX sh fragment executed inside the container before the add-on starts (must not expand on the host).
# shellcheck disable=SC2016
CUPS_TEST_MUTE_SNIPPET=${CUPS_TEST_MUTE_SNIPPET-'for _cups_if in /sys/class/net/*; do _cups_if=${_cups_if##*/}; [ "$_cups_if" = lo ] || ip link set "$_cups_if" multicast off; done'}

# cups_test_hostname TAG -- unique throwaway host name; never equals the live name `cups`.
cups_test_hostname() {
    local tag="${1:-}"
    if [[ ! "${tag}" =~ ^[a-z0-9-]{1,20}$ ]]; then
        echo "ERROR: cups_test_hostname: TAG must match [a-z0-9-]{1,20}, got '${tag}'" >&2
        return 2
    fi
    local name="cups-vf-${tag}-${CUPS_TEST_STAMP}"
    if ((${#name} > 63)); then
        echo "ERROR: cups_test_hostname: '${name}' exceeds 63 characters" >&2
        return 2
    fi
    printf '%s\n' "${name}"
}

# _cups_test_refuse REASON -- print the refusal line and return 2.
_cups_test_refuse() {
    echo "ERROR: refusing to start a cups test container: $1" >&2
    return 2
}

# _cups_test_check_data_mount OPTIONS... -- validate the options.json behind the /data mount.
_cups_test_check_data_mount() {
    local src="" prev="" word
    for word in "$@"; do
        case "${prev}" in
            -v | --volume)
                [[ "${word}" == *:/data || "${word}" == *:/data:* ]] && src="${word%%:/data*}"
                ;;
        esac
        case "${word}" in
            --volume=*:/data | --volume=*:/data:*)
                word="${word#--volume=}"
                src="${word%%:/data*}"
                ;;
        esac
        prev="${word}"
    done
    if [[ -z "${src}" ]]; then
        _cups_test_refuse "no -v SRC:/data mount, the add-on would run with the default host name 'cups'"
        return 2
    fi
    if [[ ! -f "${src}/options.json" ]]; then
        _cups_test_refuse "${src}/options.json does not exist, the add-on would run with the default host name 'cups'"
        return 2
    fi
    local status=0
    python3 -c '
import json, sys
try:
    with open(sys.argv[1]) as handle:
        data = json.load(handle)
except (OSError, ValueError):
    sys.exit(3)
value = data.get("avahi_hostname") if isinstance(data, dict) else None
if not isinstance(value, str):
    sys.exit(4)
if value in ("", "cups"):
    sys.exit(5)
' "${src}/options.json" 2>/dev/null || status=$?
    case "${status}" in
        0) return 0 ;;
        3) _cups_test_refuse "${src}/options.json is not valid JSON" ;;
        4) _cups_test_refuse "${src}/options.json has no string avahi_hostname (default 'cups' would be announced)" ;;
        *) _cups_test_refuse "avahi_hostname in ${src}/options.json is empty or the default 'cups'" ;;
    esac
    return 2
}

# _cups_test_docker_run ARGS... -- the single `docker run` call site; honours CUPS_TEST_TIMEOUT.
_cups_test_docker_run() {
    if [[ -n "${CUPS_TEST_TIMEOUT:-}" ]]; then
        timeout "${CUPS_TEST_TIMEOUT}" docker run "$@"
    else
        docker run "$@"
    fi
}

# cups_isolated_run IMAGE [DOCKER_RUN_OPTIONS...]
cups_isolated_run() {
    local image="$1"
    shift
    _cups_test_check_data_mount "$@" || return $?
    # The CMD override keeps the image's own /init entrypoint (s6 environment that `with-contenv bashio` needs).
    _cups_test_docker_run --cap-add NET_ADMIN "$@" "${image}" sh -c "${CUPS_TEST_MUTE_SNIPPET}; exec /run.sh"
}

# cups_isolated_bash IMAGE SCRIPT [DOCKER_RUN_OPTIONS...]
cups_isolated_bash() {
    local image="$1" script="$2"
    shift 2
    _cups_test_check_data_mount "$@" || return $?
    _cups_test_docker_run --cap-add NET_ADMIN --entrypoint bash "$@" "${image}" -c "${CUPS_TEST_MUTE_SNIPPET}; ${script}"
}

# cups_lan_run IMAGE [DOCKER_RUN_OPTIONS...] -- NOT isolated: announces its unique throwaway name on the LAN.
cups_lan_run() {
    local image="$1"
    shift
    _cups_test_check_data_mount "$@" || return $?
    _cups_test_docker_run "$@" "${image}"
}
