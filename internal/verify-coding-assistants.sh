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
#   claude-auth      claude_code_oauth_token / anthropic_api_key exported into the ttyd process environment only
#                    when set and non-empty; never written to profile files or logs
#   mcp-servers      `mcp_servers` option merged into /data/.claude.json `.mcpServers` (existing entries win, other
#                    keys survive, a corrupt file is never clobbered, no secret in the log); OpenCode unchanged
#   mcp-integrations zigbee2mqtt (explicit env) and mariadb-<name> wrapper entries in .mcpServers, user edits win
#                    across a container re-creation, no MQTT/database secret in either container log
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
SCENARIOS=(claude-launcher claude-state claude-auth mcp-servers mcp-integrations)

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

# =============================================================================
# Scenario claude-auth
# =============================================================================
# Fixture values deliberately do not look like real provider keys (keeps secret scanners quiet).
CA_OAUTH_FIXTURE="verify-oauth-token-value"
CA_APIKEY_FIXTURE="verify-api-key-value"

# claude_auth_env_count NAME PID VAR -- number of VAR=... lines in the process environment
claude_auth_env_count() { ca_environ "$1" "$2" | grep -c "^$3=" || true; }

scenario_claude_auth() {
    local data opts pid env logs

    # Container A: both options set
    data="${SCRATCH_DIR}/auth-a/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" ".claude_code_oauth_token=\"${CA_OAUTH_FIXTURE}\" | .anthropic_api_key=\"${CA_APIKEY_FIXTURE}\""
    start_ca auth-a "${data}" "${opts}"
    if wait_ca auth-a; then
        pid="$(ca_pid auth-a ttyd)"
        if [[ -z "${pid}" ]]; then
            fail "ttyd process not found in container A"
        else
            env="$(ca_environ auth-a "${pid}")"
            assert_ok "ttyd environment has CLAUDE_CODE_OAUTH_TOKEN with the option value" \
                grep -qxF "CLAUDE_CODE_OAUTH_TOKEN=${CA_OAUTH_FIXTURE}" <<<"${env}"
            assert_ok "ttyd environment has ANTHROPIC_API_KEY with the option value" \
                grep -qxF "ANTHROPIC_API_KEY=${CA_APIKEY_FIXTURE}" <<<"${env}"
        fi
        assert_eq "oauth token value is absent from /etc/profile.d/00-coding-assistants.sh" \
            "$(ca_count auth-a "${CA_OAUTH_FIXTURE}" /etc/profile.d/00-coding-assistants.sh)" "0"
        assert_eq "api key value is absent from /etc/profile.d/00-coding-assistants.sh" \
            "$(ca_count auth-a "${CA_APIKEY_FIXTURE}" /etc/profile.d/00-coding-assistants.sh)" "0"
        assert_eq "oauth token value is absent from the fish conf.d file" \
            "$(ca_count auth-a "${CA_OAUTH_FIXTURE}" /data/.config/fish/conf.d/00-coding-assistants.fish)" "0"
        assert_eq "api key value is absent from the fish conf.d file" \
            "$(ca_count auth-a "${CA_APIKEY_FIXTURE}" /data/.config/fish/conf.d/00-coding-assistants.fish)" "0"
        logs="$(ca_logs auth-a)"
        assert_eq "neither secret value appears in the container log" \
            "$(grep -c -e "${CA_OAUTH_FIXTURE}" -e "${CA_APIKEY_FIXTURE}" <<<"${logs}" || true)" "0"
    fi

    # Containers B1 / B2: options absent, then empty strings -- nothing may be exported, not even empty
    local variant filter
    for variant in absent empty; do
        data="${SCRATCH_DIR}/auth-b-${variant}/data"
        mkdir -p "${data}"
        opts="${data}/options.json"
        filter="."
        [[ "${variant}" == "empty" ]] && filter='.claude_code_oauth_token="" | .anthropic_api_key=""'
        write_options "${opts}" "${filter}"
        start_ca "auth-b-${variant}" "${data}" "${opts}"
        wait_ca "auth-b-${variant}" || continue
        pid="$(ca_pid "auth-b-${variant}" ttyd)"
        if [[ -z "${pid}" ]]; then
            fail "ttyd process not found in container B (${variant})"
            continue
        fi
        assert_eq "no CLAUDE_CODE_OAUTH_TOKEN in the ttyd environment (options ${variant})" \
            "$(claude_auth_env_count "auth-b-${variant}" "${pid}" CLAUDE_CODE_OAUTH_TOKEN)" "0"
        assert_eq "no ANTHROPIC_API_KEY in the ttyd environment (options ${variant})" \
            "$(claude_auth_env_count "auth-b-${variant}" "${pid}" ANTHROPIC_API_KEY)" "0"
    done
}

# =============================================================================
# Scenario mcp-servers
# =============================================================================
# Fixture values deliberately do not look like real credentials (keeps secret scanners quiet).
CA_MCP_URL_SECRET="private_verify_secret"
CA_MCP_API_KEY="verify-api-key"
CA_MCP_SERVERS_FIXTURE='[
    {"name":"ha-mcp","type":"http","url":"http://ha-mcp.invalid:9583/private_verify_secret"},
    {"name":"fff","type":"stdio","command":"/usr/local/bin/fff-mcp"},
    {"name":"with-extras","type":"stdio","command":"node","args":["/opt/x/index.js","--flag"],
     "env":[{"name":"API_KEY","value":"verify-api-key"}]}
]'

# json_check DESC JSON JQ_EXPR -- PASS when `jq -e EXPR` is truthy on JSON
json_check() {
    if jq -e "$3" <<<"$2" >/dev/null 2>&1; then pass "$1"; else fail "$1 (jq: $3)"; fi
}

# ca_sha256 NAME FILE -- sha256 of a file inside the container
ca_sha256() { ca_exec "$1" sha256sum "$2" | cut -d' ' -f1; }

scenario_mcp_servers() {
    local data opts cj oc logs seed_sha

    # Container A: pre-seeded Claude state with a user-edited ha-mcp entry
    data="${SCRATCH_DIR}/mcp-a/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" ".mcp_servers=${CA_MCP_SERVERS_FIXTURE}"
    printf '%s' '{"oauthAccount":{"emailAddress":"verify@example.invalid"},"projects":{"/homeassistant":{"allowedTools":[]}},"mcpServers":{"ha-mcp":{"type":"http","url":"http://user-edited.invalid/"}}}' \
        >"${data}/.claude.json"
    start_ca mcp-a "${data}" "${opts}"
    if wait_ca mcp-a; then
        cj="$(ca_exec mcp-a cat /data/.claude.json)"
        json_check "A: oauthAccount survived" "${cj}" '.oauthAccount.emailAddress == "verify@example.invalid"'
        json_check "A: projects survived" "${cj}" '.projects["/homeassistant"].allowedTools == []'
        json_check "A: user-edited ha-mcp entry wins over the add-on default" "${cj}" \
            '.mcpServers["ha-mcp"].url == "http://user-edited.invalid/"'
        json_check "A: fff entry has Claude's stdio shape" "${cj}" \
            '.mcpServers.fff == {"type":"stdio","command":"/usr/local/bin/fff-mcp","args":[],"env":{}}'
        json_check "A: with-extras carries args and env" "${cj}" \
            '.mcpServers["with-extras"].args == ["/opt/x/index.js","--flag"] and .mcpServers["with-extras"].env.API_KEY == "verify-api-key"'
        assert_ok "A: /root/.claude.json is still a symlink" ca_exec mcp-a test -L /root/.claude.json
        assert_eq "A: /data/.claude.json mode is 600" "$(ca_exec mcp-a stat -c %a /data/.claude.json)" "600"

        oc="$(ca_exec mcp-a cat /data/.config/opencode/opencode.json)"
        json_check "A: OpenCode still registers fff and with-extras" "${oc}" \
            '.mcp | has("fff") and has("with-extras")'
        json_check "A: OpenCode still skips the http server" "${oc}" '.mcp | has("ha-mcp") | not'
        json_check "A: OpenCode fff command unchanged" "${oc}" '.mcp.fff.command == ["/usr/local/bin/fff-mcp"]'

        logs="$(ca_logs mcp-a)"
        assert_eq "A: no MCP secret in the container log" \
            "$(grep -c -e "${CA_MCP_URL_SECRET}" -e "${CA_MCP_API_KEY}" <<<"${logs}" || true)" "0"
    fi

    # Container B: fresh volume, no pre-seed
    data="${SCRATCH_DIR}/mcp-b/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" ".mcp_servers=${CA_MCP_SERVERS_FIXTURE}"
    start_ca mcp-b "${data}" "${opts}"
    if wait_ca mcp-b; then
        cj="$(ca_exec mcp-b cat /data/.claude.json)"
        json_check "B: ha-mcp gets the add-on default http entry" "${cj}" \
            '.mcpServers["ha-mcp"] == {"type":"http","url":"http://ha-mcp.invalid:9583/private_verify_secret"}'
        json_check "B: exactly three servers registered" "${cj}" '.mcpServers | length == 3'
    fi

    # Container C: corrupt .claude.json must stay byte-identical and must not stop run.sh
    data="${SCRATCH_DIR}/mcp-c/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" ".mcp_servers=${CA_MCP_SERVERS_FIXTURE}"
    printf '%s' '{not json' >"${data}/.claude.json"
    seed_sha="$(sha256sum "${data}/.claude.json" | cut -d' ' -f1)"
    start_ca mcp-c "${data}" "${opts}"
    if wait_ca mcp-c; then
        assert_eq "C: corrupt .claude.json is byte-identical after the start" \
            "$(ca_sha256 mcp-c /data/.claude.json)" "${seed_sha}"
        logs="$(ca_logs mcp-c)"
        assert_eq "C: the failed merge is logged as a warning" \
            "$(grep -c 'WARNING.*Could not merge MCP servers' <<<"${logs}" || true)" "1"
        assert_eq "C: no MCP secret in the container log" \
            "$(grep -c -e "${CA_MCP_URL_SECRET}" -e "${CA_MCP_API_KEY}" <<<"${logs}" || true)" "0"
        pass "C: run.sh still reached its end (nginx answered)"
    fi
}

# =============================================================================
# Scenario mcp-integrations
# =============================================================================
CA_MQTT_PASS_FIXTURE="verify-mqtt-pass"
CA_DB_PASS_FIXTURE="verify-db-pass"

scenario_mcp_integrations() {
    local data opts cj oc logs1 logs2
    data="${SCRATCH_DIR}/mcpi/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" '
        .zigbee2mqtt = {enabled: true, mqtt_broker_url: "mqtt://mqtt.invalid:1883", mqtt_username: "verify-mqtt-user",
            mqtt_password: "verify-mqtt-pass", mqtt_base_topic: "z2m-verify", db_path: "/data/zigbee2mqtt-mcp.db",
            log_level: "info"}
        | .mycli = {enabled: true, default: "homeassistant", connections: [
            {name: "homeassistant", host: "db.invalid", port: 3306, username: "verify-db-user",
             password: "verify-db-pass", database: "verify"},
            {name: "analytics", host: "db.invalid", port: 3306, username: "verify-db-user",
             password: "verify-db-pass", database: "verify"}]}
        | .mcp_servers = []'
    start_ca mcpi "${data}" "${opts}"
    wait_ca mcpi || return 0

    cj="$(ca_exec mcpi cat /data/.claude.json)"
    json_check "zigbee2mqtt command and args" "${cj}" \
        '.mcpServers.zigbee2mqtt.type == "stdio" and .mcpServers.zigbee2mqtt.command == "node"
         and .mcpServers.zigbee2mqtt.args == ["/opt/mcp2zigbee2mqtt/dist/index.js"]'
    json_check "zigbee2mqtt carries an explicit env object with the MQTT values" "${cj}" \
        '.mcpServers.zigbee2mqtt.env.MQTT_PASSWORD == "verify-mqtt-pass"
         and .mcpServers.zigbee2mqtt.env.MQTT_BASE_TOPIC == "z2m-verify"
         and .mcpServers.zigbee2mqtt.env.DB_PATH == "/data/zigbee2mqtt-mcp.db"'
    local conn
    for conn in homeassistant analytics; do
        json_check "mariadb-${conn} is a stdio entry pointing at its wrapper" "${cj}" \
            ".mcpServers[\"mariadb-${conn}\"].type == \"stdio\" and .mcpServers[\"mariadb-${conn}\"].command == \"/usr/local/bin/mariadb-${conn}\""
        assert_ok "wrapper script mariadb-${conn} exists and is executable" ca_exec mcpi test -x "/usr/local/bin/mariadb-${conn}"
    done

    oc="$(ca_exec mcpi cat /data/.config/opencode/opencode.json)"
    json_check "OpenCode still has zigbee2mqtt and both mariadb entries" "${oc}" \
        '.mcp | has("zigbee2mqtt") and has("mariadb-homeassistant") and has("mariadb-analytics")'

    # User edits win across a container re-creation (written through a temp file + cp, like run.sh does)
    ca_exec mcpi sh -c 'jq ".mcpServers[\"mariadb-analytics\"].command = \"user-edited\"
        | .mcpServers.zigbee2mqtt.env.MQTT_BASE_TOPIC = \"user-topic\"" /data/.claude.json > /tmp/edit.json \
        && cp /tmp/edit.json /data/.claude.json'
    logs1="$(ca_logs mcpi)"
    restart_ca mcpi
    wait_ca mcpi || return 0
    cj="$(ca_exec mcpi cat /data/.claude.json)"
    json_check "edited mariadb-analytics command survived the re-creation" "${cj}" \
        '.mcpServers["mariadb-analytics"].command == "user-edited"'
    json_check "edited zigbee2mqtt MQTT_BASE_TOPIC survived the re-creation" "${cj}" \
        '.mcpServers.zigbee2mqtt.env.MQTT_BASE_TOPIC == "user-topic"'
    json_check "unedited entries are still present after the re-creation" "${cj}" \
        '.mcpServers | has("mariadb-homeassistant") and has("zigbee2mqtt")'

    logs2="$(ca_logs mcpi)"
    assert_eq "no MQTT/database secret in the first container log" \
        "$(grep -c -e "${CA_MQTT_PASS_FIXTURE}" -e "${CA_DB_PASS_FIXTURE}" <<<"${logs1}" || true)" "0"
    assert_eq "no MQTT/database secret in the second container log" \
        "$(grep -c -e "${CA_MQTT_PASS_FIXTURE}" -e "${CA_DB_PASS_FIXTURE}" <<<"${logs2}" || true)" "0"
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
