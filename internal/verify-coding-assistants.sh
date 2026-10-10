#!/usr/bin/env bash
# verify-coding-assistants.sh -- Docker verify harness for the coding-assistants/ add-on (phase 23).
#
# Builds the add-on image once, then starts real containers that execute the real run.sh against a stub
# Supervisor API (bashio reads the add-on options from the Supervisor, not from /data/options.json), so every
# behaviour is proven against a running add-on instead of by reading code.
#
# This script BUILDS IMAGES AND STARTS CONTAINERS. Never run it in two worktrees at the same time (repo CLAUDE.md).
#
# Usage: bash internal/verify-coding-assistants.sh [--keep] [SCENARIO...]
#   --keep               keep containers, image and scratch dir for debugging
#   SCENARIO             one or more scenario names, a group prefix (e.g. `claude` = every claude-* scenario) or
#                        `all` (default)
#   CA_VERIFY_IMAGE=TAG  environment knob: reuse an existing image and skip the build (development loop only)
#   CA_VERIFY_DOCKER_ARGS  environment knob: extra `docker run` options for every container (development only)
#
# Scenarios:
#   claude-launcher  Claude Code seeded into /data/.local/share/claude/versions, launcher points into it,
#                    `claude --version` works from a login shell, versions.json carries the version
#   claude-state     ~/.claude state persistence (+ legacy migration), TOOLS.md block in CLAUDE.md rewritten on
#                    every start with user text preserved, seed/newest selection against real re-creations
#
# Container model: every add-on start is a NEW container on the same /data volume (Supervisor semantics), so a
# "restart" is `docker rm -f` followed by a fresh `docker run` (restart_ca), never `docker restart`. Containers
# use the image's own s6 /init entrypoint (`with-contenv bashio` needs it), never `--entrypoint bash`.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADDON_DIR="${REPO_ROOT}/coding-assistants"

STAMP="$(date +%s)"
IMAGE_NAME="${CA_VERIFY_IMAGE:-coding-assistants-verify:${STAMP}}"
REUSE_IMAGE=0
[[ -n "${CA_VERIFY_IMAGE:-}" ]] && REUSE_IMAGE=1
KEEP=0
# CA_VERIFY_DOCKER_ARGS: development knob, extra `docker run` options for every container (word-split), e.g. a
# `-v mutated-run.sh:/run.sh:ro` mount to prove that a check can fail.
read -r -a DEV_EXTRA_ARGS <<<"${CA_VERIFY_DOCKER_ARGS:-}"

SCRATCH_DIR="$(mktemp -d)"
STUB_PY="${SCRATCH_DIR}/stub_supervisor.py"

if [[ -t 1 ]]; then
    red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
    green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
    yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
else
    red() { printf '%s\n' "$*"; }
    green() { printf '%s\n' "$*"; }
    yellow() { printf '%s\n' "$*"; }
fi

FAIL=0
CONTAINERS=()
STUB_PIDS=()
declare -A CA_STUB_PORT=()
declare -A CA_DATA=()
declare -A CA_OPTS=()
declare -A CA_EXTRA=()

# Registered scenarios: NAME -> function scenario_<NAME with - replaced by _>
SCENARIOS=(claude-launcher claude-state)

cleanup() {
    local pid c
    for pid in "${STUB_PIDS[@]:-}"; do
        [[ -n "${pid}" ]] && kill "${pid}" >/dev/null 2>&1
    done
    if [[ "${KEEP}" == "0" ]]; then
        for c in "${CONTAINERS[@]:-}"; do
            [[ -n "${c}" ]] && docker rm -f "${c}" >/dev/null 2>&1
        done
        # Rootful engines leave root-owned files in the scratch dir; remove them through the image if needed.
        rm -rf "${SCRATCH_DIR}" >/dev/null 2>&1
        if [[ -d "${SCRATCH_DIR}" ]]; then
            docker run --rm --entrypoint sh -v "${SCRATCH_DIR}:/scratch" "${IMAGE_NAME}" \
                -c 'rm -rf /scratch/* /scratch/.[!.]*' >/dev/null 2>&1
            rm -rf "${SCRATCH_DIR}" >/dev/null 2>&1
        fi
        [[ "${REUSE_IMAGE}" == "0" ]] && docker rmi "${IMAGE_NAME}" >/dev/null 2>&1
    fi
    return 0
}
trap cleanup EXIT

# --- Scenario selection --------------------------------------------------------------------------------------------
valid_scenarios() { printf '%s ' "${SCENARIOS[@]}" all; echo; }

# expand_scenario NAME -> prints the registered scenario names it stands for (exit 2 when unknown)
expand_scenario() {
    local want="$1" s found=0
    if [[ "${want}" == "all" ]]; then
        printf '%s\n' "${SCENARIOS[@]}"
        return 0
    fi
    for s in "${SCENARIOS[@]}"; do
        if [[ "${s}" == "${want}" || "${s}" == "${want}-"* ]]; then
            printf '%s\n' "${s}"
            found=1
        fi
    done
    [[ "${found}" == "1" ]]
}

SELECTED=()
REQUESTED=()
for arg in "$@"; do
    case "${arg}" in
        --keep) KEEP=1 ;;
        *) REQUESTED+=("${arg}") ;;
    esac
done
[[ ${#REQUESTED[@]} -eq 0 ]] && REQUESTED=(all)
for want in "${REQUESTED[@]}"; do
    if ! expanded_out=$(expand_scenario "${want}"); then
        echo "unknown scenario: ${want}; valid: $(valid_scenarios)" >&2
        exit 2
    fi
    mapfile -t expanded <<<"${expanded_out}"
    for s in "${expanded[@]}"; do
        [[ " ${SELECTED[*]:-} " == *" ${s} "* ]] || SELECTED+=("${s}")
    done
done

for tool in docker jq python3; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        red "${tool} not found in PATH"
        exit 2
    fi
done
if [[ ! -d "${ADDON_DIR}" ]]; then
    red "coding-assistants/ add-on directory not found: ${ADDON_DIR}"
    exit 2
fi

# --- Image build (mirrors CI, which forwards only the standard build args) --------------------------------------
if [[ "${REUSE_IMAGE}" == "1" ]]; then
    yellow "Reusing image ${IMAGE_NAME} (CA_VERIFY_IMAGE) -- build skipped"
else
    BUILD_FROM=$(grep -E '^\s*amd64:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*amd64: "(.*)"/\1/')
    VERSION=$(grep -E '^\s*VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*VERSION: "(.*)"/\1/')
    yellow "Building ${IMAGE_NAME} from ${ADDON_DIR}/ (BUILD_FROM=${BUILD_FROM} VERSION=${VERSION})"
    if ! docker build -t "${IMAGE_NAME}" \
        --build-arg "BUILD_FROM=${BUILD_FROM}" \
        --build-arg "VERSION=${VERSION}" \
        "${ADDON_DIR}" >"${SCRATCH_DIR}/build.log" 2>&1; then
        red "docker build failed -- see ${SCRATCH_DIR}/build.log"
        tail -60 "${SCRATCH_DIR}/build.log"
        KEEP=1
        exit 1
    fi
    green "image built"
fi

# --- Stub Supervisor -------------------------------------------------------------------------------------------------
# bashio::config -> GET /addons/self/options/config, bashio::addon.version -> GET /addons/self/info. The options
# file (argv[2]) is re-read on every request so a scenario can change options between restarts.
cat >"${STUB_PY}" <<'PYEOF'
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT_FILE = sys.argv[1]
OPTIONS_FILE = sys.argv[2]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _handle(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        path = self.path.split("?", 1)[0]
        data = {}
        if self.command == "GET" and path == "/addons/self/options/config":
            with open(OPTIONS_FILE) as handle:
                data = json.load(handle)
        elif self.command == "GET" and re.fullmatch(r"/addons/[^/]+/info", path):
            data = {"version": "1.0.0-verify", "slug": "coding_assistants"}
        body = json.dumps({"result": "ok", "data": data}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_DELETE = _handle


server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
with open(PORT_FILE, "w") as handle:
    handle.write(str(server.server_address[1]))
server.serve_forever()
PYEOF

# --- Helpers -----------------------------------------------------------------------------------------------------
ca_cname() { printf 'ca-verify-%s-%s' "${STAMP}" "$1"; }

# write_options FILE [JQ_FILTER] -- base options object, optionally modified by a jq filter
write_options() {
    local file="$1" filter="${2:-.}"
    jq -n '{
        log_level: "info", authorized_keys: [], terminal_font_size: 16, terminal_theme: "default",
        terminal_font_family: "monospace", ha_url: "http://homeassistant:8123", ha_token: "verify-ha-token",
        zigbee2mqtt: {enabled: false}, mycli: {enabled: false, connections: []},
        mcp_servers: [], env_vars: [], bash_aliases: []
    }' | jq "${filter}" >"${file}"
}

# start_ca NAME DATA_DIR OPTIONS_FILE [EXTRA_DOCKER_ARGS...]
start_ca() {
    local name="$1" data="$2" opts="$3"
    shift 3
    local cname ha_dir port_file i
    cname="$(ca_cname "${name}")"
    mkdir -p "${data}"
    if [[ "$(realpath "${opts}")" != "$(realpath -m "${data}/options.json")" ]]; then
        cp "${opts}" "${data}/options.json"
    fi
    ha_dir="$(dirname "${data}")/homeassistant-${name}"
    mkdir -p "${ha_dir}"

    if [[ -z "${CA_STUB_PORT[${name}]:-}" ]]; then
        port_file="${SCRATCH_DIR}/stub-${name}.port"
        rm -f "${port_file}"
        python3 "${STUB_PY}" "${port_file}" "${data}/options.json" >"${SCRATCH_DIR}/stub-${name}.out" 2>&1 &
        STUB_PIDS+=("$!")
        for i in $(seq 1 50); do
            [[ -s "${port_file}" ]] && break
            sleep 0.2
        done
        CA_STUB_PORT[${name}]="$(cat "${port_file}" 2>/dev/null)"
    fi

    CA_DATA[${name}]="${data}"
    CA_OPTS[${name}]="${opts}"
    CA_EXTRA[${name}]="$(printf '%s\n' "$@")"

    CONTAINERS+=("${cname}")
    docker run -d --name "${cname}" \
        --add-host=host.docker.internal:host-gateway \
        -e "SUPERVISOR_API=http://host.docker.internal:${CA_STUB_PORT[${name}]}" \
        -e SUPERVISOR_TOKEN=verify-supervisor-token \
        -v "${data}:/data" \
        -v "${ha_dir}:/homeassistant" \
        "${DEV_EXTRA_ARGS[@]}" \
        "$@" \
        "${IMAGE_NAME}" >/dev/null
}

# wait_ca NAME -- nginx starts last in run.sh, so a 200 on versions.json proves run.sh reached its end
wait_ca() {
    local cname i
    cname="$(ca_cname "$1")"
    for i in $(seq 1 120); do
        if docker exec "${cname}" curl -fsS http://127.0.0.1:8099/versions.json >/dev/null 2>&1; then
            return 0
        fi
        if [[ "$(docker inspect -f '{{.State.Running}}' "${cname}" 2>/dev/null)" != "true" ]]; then
            red "FAIL: container ${1} exited before nginx answered"
            docker logs "${cname}" 2>&1 | tail -60
            FAIL=1
            return 1
        fi
        sleep 1
    done
    red "FAIL: container ${1} did not become ready within 120 s"
    docker logs "${cname}" 2>&1 | tail -60
    FAIL=1
    return 1
}

# restart_ca NAME -- new container on the same /data (Supervisor semantics), same parameters as before
restart_ca() {
    local name="$1" extra=()
    docker rm -f "$(ca_cname "${name}")" >/dev/null 2>&1
    if [[ -n "${CA_EXTRA[${name}]}" ]]; then
        mapfile -t extra <<<"${CA_EXTRA[${name}]}"
    fi
    start_ca "${name}" "${CA_DATA[${name}]}" "${CA_OPTS[${name}]}" "${extra[@]}"
}

ca_exec() { docker exec "$(ca_cname "$1")" "${@:2}"; }
ca_logs() { docker logs "$(ca_cname "$1")" 2>&1; }

# ca_pid NAME COMM -- first PID whose /proc/PID/comm equals COMM (procps may be absent in the image)
ca_pid() {
    # shellcheck disable=SC2016
    ca_exec "$1" sh -c 'for d in /proc/[0-9]*; do
        if [ "$(cat "$d/comm" 2>/dev/null)" = "$1" ]; then echo "${d#/proc/}"; break; fi
    done' sh "$2"
}

# ca_environ NAME PID -- the process environment, one VAR=value per line
# shellcheck disable=SC2016
ca_environ() { ca_exec "$1" sh -c 'tr "\0" "\n" < "/proc/$1/environ"' sh "$2"; }

pass() { green "PASS: $*"; }
fail() {
    red "FAIL: $*"
    FAIL=1
}

# assert_eq DESC ACTUAL EXPECTED
assert_eq() {
    if [[ "$2" == "$3" ]]; then pass "$1"; else fail "$1 (expected '$3', got '$2')"; fi
}
# assert_match DESC ACTUAL REGEX
assert_match() {
    if [[ "$2" =~ $3 ]]; then pass "$1"; else fail "$1 (expected match of '$3', got '$2')"; fi
}
# assert_ok DESC CMD... / assert_fail DESC CMD...
assert_ok() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then pass "${desc}"; else fail "${desc} (command failed: $*)"; fi
}
assert_fail() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then fail "${desc} (command unexpectedly succeeded: $*)"; else pass "${desc}"; fi
}

# =============================================================================
# Scenario claude-launcher
# =============================================================================
scenario_claude_launcher() {
    local data="${SCRATCH_DIR}/launcher/data" opts out ver link versions_json json_ver
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}"
    start_ca launcher "${data}" "${opts}"
    wait_ca launcher || return 0

    out=$(ca_exec launcher bash -lc 'claude --version')
    ver="${out%% *}"
    assert_match "claude --version works in a login shell and starts with a semver" "${ver}" '^[0-9]+\.[0-9]+\.[0-9]+'

    link=$(ca_exec launcher readlink /root/.local/bin/claude)
    assert_match "launcher points into the persistent versions directory" "${link}" \
        '^/data/\.local/share/claude/versions/'
    assert_ok "launcher target exists and is executable" ca_exec launcher test -x "${link}"
    # shellcheck disable=SC2016
    assert_eq "XDG_DATA_HOME in a login shell" "$(ca_exec launcher bash -lc 'echo $XDG_DATA_HOME')" \
        "/data/.local/share"

    versions_json=$(ca_exec launcher curl -fsS http://127.0.0.1:8099/versions.json)
    json_ver="$(jq -r '.claude' <<<"${versions_json}" 2>/dev/null)"
    assert_match "versions.json carries a claude semver" "${json_ver}" '^[0-9]+\.[0-9]+\.[0-9]+'
    assert_eq "versions.json claude field equals the launcher version" "${json_ver}" "${ver}"
}

# =============================================================================
# Scenario claude-state
# =============================================================================
# ca_count NAME PATTERN FILE -- number of lines matching PATTERN (grep -c, never fails)
ca_count() { ca_exec "$1" grep -c -- "$2" "$3" || true; }

# claude_block_equals_tools NAME -- the span between the markers equals coding-assistants/TOOLS.md
claude_block_equals_tools() {
    diff -B <(ca_exec "$1" sed -n '/^<!-- coding-assistants:begin -->$/,/^<!-- coding-assistants:end -->$/p' \
        /data/.claude/CLAUDE.md | sed '1d;$d') "${ADDON_DIR}/TOOLS.md"
}

# claude_write_fake_version NAME VERSION -- executable stub "claude" inside the persistent versions dir
claude_write_fake_version() {
    # shellcheck disable=SC2016
    ca_exec "$1" sh -c 'printf "#!/bin/sh\necho \"%s (Claude Code)\"\n" "$1" > "/data/.local/share/claude/versions/$1" \
        && chmod +x "/data/.local/share/claude/versions/$1"' sh "$2"
}

scenario_claude_state() {
    local data="${SCRATCH_DIR}/state/data" opts note1 note2 seed link
    mkdir -p "${data}/claude/.claude"
    opts="${data}/options.json"
    write_options "${opts}"

    # Stage 1: legacy volume (/data/claude/.claude*) with a user CLAUDE.md holding a stale block
    printf 'legacy\n' >"${data}/claude/.claude/legacy.txt"
    printf 'USER-NOTE-1\n<!-- coding-assistants:begin -->\nstale\n<!-- coding-assistants:end -->\n' \
        >"${data}/claude/.claude/CLAUDE.md"
    printf '{"legacyKey":true}\n' >"${data}/claude/.claude.json"
    start_ca state "${data}" "${opts}"
    wait_ca state || return 0

    assert_ok "legacy .claude content was migrated" ca_exec state test -f /data/.claude/legacy.txt
    assert_eq "legacy .claude.json was migrated" "$(ca_exec state jq -r '.legacyKey' /data/.claude.json)" "true"
    assert_eq "/root/.claude points to /data/.claude" "$(ca_exec state readlink /root/.claude)" "/data/.claude"
    assert_eq "/root/.claude.json points to /data/.claude.json" "$(ca_exec state readlink /root/.claude.json)" \
        "/data/.claude.json"
    assert_eq "/data/.claude mode is 700" "$(ca_exec state stat -c %a /data/.claude)" "700"
    assert_eq "/data/.claude.json mode is 600" "$(ca_exec state stat -c %a /data/.claude.json)" "600"
    assert_ok "CLAUDE.md block equals TOOLS.md" claude_block_equals_tools state
    assert_eq "stale block text is gone" "$(ca_count state '^stale$' /data/.claude/CLAUDE.md)" "0"
    assert_eq "USER-NOTE-1 appears exactly once" "$(ca_count state '^USER-NOTE-1$' /data/.claude/CLAUDE.md)" "1"
    assert_ok "legacy .claude file still exists" ca_exec state test -f /data/claude/.claude/legacy.txt
    assert_ok "legacy .claude.json still exists" ca_exec state test -f /data/claude/.claude.json

    # Stage 2: user text after the block survives a re-creation; the block is rewritten, not duplicated
    ca_exec state sh -c 'echo USER-NOTE-2 >> /data/.claude/CLAUDE.md'
    restart_ca state
    wait_ca state || return 0
    note1="$(ca_count state '^USER-NOTE-1$' /data/.claude/CLAUDE.md)"
    note2="$(ca_count state '^USER-NOTE-2$' /data/.claude/CLAUDE.md)"
    assert_eq "USER-NOTE-1 still appears exactly once after a restart" "${note1}" "1"
    assert_eq "USER-NOTE-2 appears exactly once after a restart" "${note2}" "1"
    assert_eq "exactly one begin marker after a restart" \
        "$(ca_count state '^<!-- coding-assistants:begin -->$' /data/.claude/CLAUDE.md)" "1"
    assert_ok "CLAUDE.md block still equals TOOLS.md after a restart" claude_block_equals_tools state

    # Stage 3: a newer persisted version wins over the image seed
    claude_write_fake_version state 99.0.0
    restart_ca state
    wait_ca state || return 0
    link="$(ca_exec state readlink /root/.local/bin/claude)"
    assert_match "launcher targets the newer persisted version" "${link}" '/99\.0\.0$'
    assert_eq "claude --version prints the persisted version" \
        "$(ca_exec state bash -lc 'claude --version' | head -n 1 | cut -d' ' -f1)" "99.0.0"

    # Stage 4: a strictly newer image seed is copied in when the persisted set is older
    seed="$(docker run --rm --entrypoint sh "${IMAGE_NAME}" -c 'ls /opt/claude-initial' | head -n 1)"
    ca_exec state sh -c 'rm -rf /data/.local/share/claude/versions/* /data/.local/share/claude/versions/.[!.]*'
    claude_write_fake_version state 0.0.1
    restart_ca state
    wait_ca state || return 0
    link="$(ca_exec state readlink /root/.local/bin/claude)"
    assert_eq "launcher targets the image seed version" "${link}" "/data/.local/share/claude/versions/${seed}"
    assert_ok "seed binary was copied into the persistent versions dir" \
        ca_exec state test -x "/data/.local/share/claude/versions/${seed}"
    assert_ok "older persisted 0.0.1 was left in place" ca_exec state test -f /data/.local/share/claude/versions/0.0.1
}

# --- Dispatcher --------------------------------------------------------------------------------------------------
for scenario in "${SELECTED[@]}"; do
    yellow "=== Scenario ${scenario} ==="
    "scenario_${scenario//-/_}"
done

if [[ "${FAIL}" == "1" ]]; then
    echo
    red "internal/verify-coding-assistants.sh: FAILED"
    exit 1
fi

echo
green "internal/verify-coding-assistants.sh: ALL CHECKS PASSED"
