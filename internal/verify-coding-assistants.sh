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
#   drift            (static, no Docker) build.yaml args mirror the Dockerfile ARG defaults 1:1; a deliberately
#                    changed copy must FAIL the comparison (negative control)
#   herdr-core       herdr server owned by run.sh (workspace main at /homeassistant, fish panes with the add-on
#                    environment, respawn after kill -9), two concurrent clients share ONE session, a missing
#                    server degrades to a plain fish shell
#   herdr-attach     SSH login hooks (bash + fish) and the ttyd command go through coding-assistants-attach, the
#                    escape variables keep scripted/nested shells out, a real sshd round trip lands in herdr, no
#                    herdr config.toml is written, the previous multiplexer is gone from image and code
#   surface          versions.json carries claude and herdr, MOTD shows herdr, info.html has the version rows,
#                    backup_exclude lists the herdr runtime files, no previous-multiplexer text in TOOLS.md/info.html
#   plugins          the approved herdr plugins (23-PLUGIN-REVIEW.md) are registered at their pinned checkouts, a broken
#                    plugin directory only yields a warning (D-07), no herdr config.toml / Claude settings.json is
#                    written (D-02, D-04), claude-limits' poller starts without credentials, subagent-watch's launcher
#                    works (setup --dry-run), the patched web-service answers /api/health through its startup hook,
#                    serves a relative-URL client and refuses login (503) while no password exists
#   services         herdr-web-service behind the add-on nginx at /services/ (ingress-style Host/Origin headers): relative
#                    301, relative assets, exactly one CSP with frame-ancestors 'self', no HSTS, login closed (503)
#                    without a password, WebSocket refused without a session, Services tab on the landing page,
#                    /terminal/ unchanged, the plugin bound to loopback only
#   services-auth    the herdr_web_password option through nginx: wrong password 401, right one 204 with an HttpOnly
#                    cookie, session/roster/WebSocket gated by that cookie, hash file mode 600 without plaintext,
#                    password in no log, hash survives a container re-creation; a rejected password is a warning
#                    that names the unmet rule and never the value; no option keeps the login closed (503)
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
SCENARIOS=(claude-launcher claude-state claude-auth mcp-servers mcp-integrations drift herdr-core herdr-attach surface
    plugins services services-auth)
# Scenarios that need neither Docker nor the image: when only these are selected the image build is skipped.
STATIC_SCENARIOS=(drift)

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

NEEDS_IMAGE=0
for s in "${SELECTED[@]}"; do
    [[ " ${STATIC_SCENARIOS[*]} " == *" ${s} "* ]] || NEEDS_IMAGE=1
done
for tool in jq python3; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        red "${tool} not found in PATH"
        exit 2
    fi
done
if [[ "${NEEDS_IMAGE}" == "1" ]] && ! command -v docker >/dev/null 2>&1; then
    red "docker not found in PATH"
    exit 2
fi
if [[ ! -d "${ADDON_DIR}" ]]; then
    red "coding-assistants/ add-on directory not found: ${ADDON_DIR}"
    exit 2
fi

# --- Image build (mirrors CI, which forwards only the standard build args) --------------------------------------
if [[ "${NEEDS_IMAGE}" == "0" ]]; then
    REUSE_IMAGE=1 # nothing built, nothing to remove in cleanup
    yellow "Only static scenarios selected -- image build skipped"
elif [[ "${REUSE_IMAGE}" == "1" ]]; then
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

# =============================================================================
# Scenario drift (static: no container, no image)
# =============================================================================
# CI forwards only the standard build args, so the herdr pins live as Dockerfile ARG defaults and are mirrored in
# build.yaml `args:`. Every build.yaml arg except VERSION must equal the Dockerfile default, and every Dockerfile
# `ARG HERDR_*=` default must exist in build.yaml.

# build_yaml_args FILE -- the `args:` block as KEY<TAB>VALUE lines (quotes stripped)
build_yaml_args() {
    awk '
        /^args:/ { in_args = 1; next }
        in_args && /^[^[:space:]#]/ { in_args = 0 }
        in_args && /^[[:space:]]+[A-Za-z0-9_]+:/ {
            line = $0
            sub(/^[[:space:]]+/, "", line)
            key = substr(line, 1, index(line, ":") - 1)
            value = substr(line, index(line, ":") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            gsub(/^"|"$/, "", value)
            printf "%s\t%s\n", key, value
        }' "$1"
}

# drift_compare BUILD_YAML DOCKERFILE -- prints every mismatch, returns 1 when there is at least one
drift_compare() {
    local build_yaml="$1" dockerfile="$2" rc=0 key value default keys=""
    while IFS=$'\t' read -r key value; do
        keys="${keys} ${key} "
        [[ "${key}" == "VERSION" ]] && continue
        default="$(grep -E "^ARG ${key}=" "${dockerfile}" | head -n 1 | cut -d= -f2-)"
        if [[ -z "${default}" ]]; then
            echo "drift: build.yaml arg ${key} has no 'ARG ${key}=' default in the Dockerfile"
            rc=1
        elif [[ "${default}" != "${value}" ]]; then
            echo "drift: ${key} differs (build.yaml '${value}', Dockerfile '${default}')"
            rc=1
        fi
    done < <(build_yaml_args "${build_yaml}")
    while IFS= read -r key; do
        [[ "${keys}" == *" ${key} "* ]] || {
            echo "drift: Dockerfile ARG ${key} has no key in build.yaml args"
            rc=1
        }
    done < <(grep -E '^ARG HERDR_[A-Z0-9_]+=' "${dockerfile}" | sed -E 's/^ARG ([A-Z0-9_]+)=.*/\1/')
    return "${rc}"
}

scenario_drift() {
    local by="${ADDON_DIR}/build.yaml" df="${ADDON_DIR}/Dockerfile" tmp="${SCRATCH_DIR}/drift"
    mkdir -p "${tmp}"
    if out="$(drift_compare "${by}" "${df}")"; then
        pass "build.yaml args mirror the Dockerfile ARG defaults"
    else
        fail "build.yaml and the Dockerfile ARG defaults drifted: ${out}"
    fi
    local key
    for key in HERDR_VERSION HERDR_SHA256_X86_64 HERDR_SHA256_AARCH64 HERDR_SUBAGENT_WATCH_REF HERDR_WEB_SERVICE_REF \
        HERDR_CLAUDE_LIMITS_REF; do
        assert_eq "build.yaml carries the pin ${key}" \
            "$(build_yaml_args "${by}" | grep -c "^${key}"$'\t')" "1"
    done
    assert_match "plugin pins are full 40-character commit SHAs" \
        "$(build_yaml_args "${by}" | awk -F'\t' '$1 ~ /_REF$/ { print $2 }' | tr '\n' ' ')" '^([0-9a-f]{40} )+$'

    # Negative controls: the comparison must fail on a changed value and on a pin missing from build.yaml.
    sed -E 's/^(  HERDR_VERSION: ").*(")$/\10.0.0-drift\2/' "${by}" >"${tmp}/changed-value.yaml"
    if drift_compare "${tmp}/changed-value.yaml" "${df}" >/dev/null; then
        fail "negative control: a changed HERDR_VERSION did not fail the drift check"
    else
        pass "negative control: a changed HERDR_VERSION fails the drift check"
    fi
    grep -v '^  HERDR_SHA256_AARCH64:' "${by}" >"${tmp}/missing-key.yaml"
    if drift_compare "${tmp}/missing-key.yaml" "${df}" >/dev/null; then
        fail "negative control: a pin missing from build.yaml did not fail the drift check"
    else
        pass "negative control: a pin missing from build.yaml fails the drift check"
    fi
}

# =============================================================================
# Scenario herdr-core
# =============================================================================
# ca_pty_probe CONTAINER SECONDS COUNT CMD... -- run CMD COUNT times concurrently, each in its own pseudo-terminal
# (120 columns by 40 rows) inside the container, let them run for SECONDS, then print one line per client:
#   comm=<comm of the pty child after the wait> alive=<0|1> bytes=<bytes read> text=<first 400 printable chars>
# and kill the children. The script is piped to `docker exec -i` (stdin of the exec is the script, the children get
# the pty as stdin).
CA_PTY_PROBE_PY='
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import time

seconds = float(sys.argv[1])
count = int(sys.argv[2])
cmd = sys.argv[3:]
winsize = struct.pack("HHHH", 40, 120, 0, 0)

clients = []
for _ in range(count):
    pid, fd = pty.fork()
    if pid == 0:
        fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
        os.environ.setdefault("TERM", "xterm-256color")
        try:
            os.execvp(cmd[0], cmd)
        except OSError as exc:
            os.write(2, ("exec failed: %s\n" % exc).encode())
            os._exit(127)
    clients.append({"pid": pid, "fd": fd, "open": True, "data": b""})

end = time.time() + seconds
while time.time() < end:
    fds = [c["fd"] for c in clients if c["open"]]
    if not fds:
        time.sleep(0.2)
        continue
    ready, _, _ = select.select(fds, [], [], 0.2)
    for client in clients:
        if client["open"] and client["fd"] in ready:
            try:
                chunk = os.read(client["fd"], 65536)
            except OSError:
                chunk = b""
            if chunk:
                client["data"] += chunk
            else:
                client["open"] = False

for client in clients:
    pid = client["pid"]
    try:
        with open("/proc/%d/comm" % pid) as handle:
            comm = handle.read().strip()
    except OSError:
        comm = "gone"
    done, _ = os.waitpid(pid, os.WNOHANG)
    alive = 1 if done == 0 else 0
    text = []
    for char in client["data"].decode("utf-8", "replace"):
        if char == "\n":
            text.append("\\n")
        elif " " <= char <= "~":
            text.append(char)
        if len(text) >= 400:
            break
    print("comm=%s alive=%d bytes=%d text=%s" % (comm, alive, len(client["data"]), "".join(text)[:400]), flush=True)

for client in clients:
    for sig in (signal.SIGKILL,):
        try:
            os.killpg(client["pid"], sig)
        except OSError:
            try:
                os.kill(client["pid"], sig)
            except OSError:
                pass
    try:
        os.waitpid(client["pid"], 0)
    except OSError:
        pass
'

ca_pty_probe() {
    local container="$1" seconds="$2" count="$3"
    shift 3
    printf '%s' "${CA_PTY_PROBE_PY}" | docker exec -i "${container}" python3 -I - "${seconds}" "${count}" "$@"
}

# probe_field LINE FIELD -- value of comm|alive|bytes from a ca_pty_probe line
probe_field() { sed -nE "s/^.*\b$2=([^ ]*).*$/\1/p" <<<"$1" | head -n 1; }
# probe_text LINE -- everything after "text="
probe_text() { sed -nE 's/^.* text=(.*)$/\1/p' <<<"$1"; }

# ca_herdr NAME ARGS... -- herdr CLI with the add-on's config dir (docker exec does not carry run.sh's exports)
ca_herdr() { ca_exec "$1" env XDG_CONFIG_HOME=/data/.config herdr "${@:2}"; }

# herdr_server_pid NAME -- PID of the `herdr server` process (comm herdr, command line contains "server")
herdr_server_pid() {
    # shellcheck disable=SC2016
    ca_exec "$1" sh -c 'for d in /proc/[0-9]*; do
        if [ "$(cat "$d/comm" 2>/dev/null)" = herdr ] && tr "\0" " " < "$d/cmdline" 2>/dev/null | grep -q server; then
            echo "${d#/proc/}"; break
        fi
    done'
}

# herdr_count NAME -- number of processes whose comm is herdr (server plus attached clients)
herdr_count() {
    # shellcheck disable=SC2016
    ca_exec "$1" sh -c 'n=0; for d in /proc/[0-9]*; do
        [ "$(cat "$d/comm" 2>/dev/null)" = herdr ] && n=$((n + 1))
    done; echo "$n"'
}

# herdr_wait_server NAME [NOT_PID] -- wait up to 20 s for a running server (with a pid different from NOT_PID)
herdr_wait_server() {
    local i pid
    for i in $(seq 1 40); do
        if [[ "$(ca_herdr "$1" status --json 2>/dev/null | jq -r '.server.running' 2>/dev/null)" == "true" ]]; then
            pid="$(herdr_server_pid "$1")"
            if [[ -n "${pid}" && "${pid}" != "${2:-}" ]]; then
                return 0
            fi
        fi
        sleep 0.5
    done
    return 1
}

# herdr_main_workspaces NAME -- number of workspaces labelled main
herdr_main_workspaces() {
    ca_herdr "$1" workspace list 2>/dev/null | jq '[.result.workspaces[] | select(.label == "main")] | length'
}

scenario_herdr_core() {
    local data opts want_ver out ws_count ws_id pane_id pane_json i pid1 pid2 expected got line1 line2 text
    data="${SCRATCH_DIR}/herdr-core/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" ".claude_code_oauth_token=\"${CA_OAUTH_FIXTURE}\""
    start_ca herdr-core "${data}" "${opts}"
    wait_ca herdr-core || return 0

    want_ver="$(build_yaml_args "${ADDON_DIR}/build.yaml" | awk -F'\t' '$1 == "HERDR_VERSION" { print $2 }')"
    assert_eq "herdr --version shows the build.yaml pin" "$(ca_exec herdr-core herdr --version | cut -d' ' -f2)" \
        "${want_ver}"

    out="$(ca_herdr herdr-core status --json)"
    json_check "herdr server is running" "${out}" '.server.running == true'
    json_check "herdr socket lives under /data/.config/herdr/" "${out}" \
        '.server.socket | startswith("/data/.config/herdr/")'

    out="$(ca_herdr herdr-core workspace list)"
    ws_count="$(jq '.result.workspaces | length' <<<"${out}")"
    assert_eq "exactly one workspace exists before the first client" "${ws_count}" "1"
    assert_eq "that workspace is labelled main" "$(jq -r '.result.workspaces[0].label' <<<"${out}")" "main"
    ws_id="$(jq -r '.result.workspaces[0].workspace_id' <<<"${out}")"
    pane_json="$(ca_herdr herdr-core pane list)"
    pane_id="$(jq -r --arg ws "${ws_id}" '[.result.panes[] | select(.workspace_id == $ws or (.pane_id | startswith($ws + ":")))][0].pane_id' <<<"${pane_json}")"
    assert_eq "root pane of main has cwd /homeassistant" \
        "$(jq -r --arg p "${pane_id}" '.result.panes[] | select(.pane_id == $p) | .cwd' <<<"${pane_json}")" \
        "/homeassistant"

    # The pane environment is the server's environment: fish panes, the add-on exports, PATH with the launcher.
    ca_exec herdr-core rm -f /tmp/pane-env.txt
    ca_herdr herdr-core pane run "${pane_id}" \
        "string join '|' \$SHELL \$HA_URL \$HERDR_ENV \$CLAUDE_CODE_OAUTH_TOKEN (command -v claude) > /tmp/pane-env.txt" \
        >/dev/null 2>&1
    expected="/usr/bin/fish|http://homeassistant:8123|1|${CA_OAUTH_FIXTURE}|/root/.local/bin/claude"
    got=""
    for i in $(seq 1 30); do
        got="$(ca_exec herdr-core cat /tmp/pane-env.txt 2>/dev/null || true)"
        [[ -n "${got}" ]] && break
        sleep 0.5
    done
    assert_eq "pane environment (SHELL|HA_URL|HERDR_ENV|oauth token|claude path)" "${got}" "${expected}"

    # Respawn: kill -9 the server, run.sh's loop must bring up a different one within 20 s.
    pid1="$(herdr_server_pid herdr-core)"
    if [[ -z "${pid1}" ]]; then
        fail "could not find the herdr server process"
    else
        ca_exec herdr-core kill -9 "${pid1}"
        if herdr_wait_server herdr-core "${pid1}"; then
            pid2="$(herdr_server_pid herdr-core)"
            pass "server respawned within 20 s (pid ${pid1} -> ${pid2})"
        else
            fail "no new herdr server within 20 s after kill -9 of pid ${pid1}"
        fi
        assert_match "the respawn is logged as a warning" "$(ca_logs herdr-core)" 'WARNING.*herdr server exited'
    fi

    # Shared session: empty the session, then two simultaneous clients through the wrapper. Both must stay alive in
    # herdr, share ONE session and leave exactly one workspace main (the flock in the wrapper).
    for ws_id in $(ca_herdr herdr-core workspace list 2>/dev/null | jq -r '.result.workspaces[].workspace_id'); do
        ca_herdr herdr-core workspace close "${ws_id}" >/dev/null 2>&1
    done
    assert_eq "the session is empty before the clients attach" \
        "$(ca_herdr herdr-core workspace list | jq '.result.workspaces | length')" "0"
    out="$(ca_pty_probe "$(ca_cname herdr-core)" 6 2 coding-assistants-attach)"
    line1="$(sed -n 1p <<<"${out}")"
    line2="$(sed -n 2p <<<"${out}")"
    for i in 1 2; do
        line="${line1}"
        [[ "${i}" == "2" ]] && line="${line2}"
        assert_eq "client ${i} is alive" "$(probe_field "${line}" alive)" "1"
        assert_eq "client ${i} runs herdr" "$(probe_field "${line}" comm)" "herdr"
        if [[ "$(probe_field "${line}" bytes)" -gt 0 ]] 2>/dev/null; then
            pass "client ${i} produced output"
        else
            fail "client ${i} produced no output (${line})"
        fi
    done
    assert_eq "exactly one workspace main after two concurrent first clients" "$(herdr_main_workspaces herdr-core)" "1"
    assert_eq "no other workspace was created" \
        "$(ca_herdr herdr-core workspace list | jq '.result.workspaces | length')" "1"

    # Fallback: no server answers (empty config dir) -> message and a plain fish shell, never a dead terminal.
    out="$(ca_pty_probe "$(ca_cname herdr-core)" 14 1 env XDG_CONFIG_HOME=/tmp/no-herdr-here coding-assistants-attach)"
    text="$(probe_text "${out}")"
    assert_match "fallback message is shown" "${text}" 'herdr server is not running, starting a plain fish shell'
    assert_eq "fallback shell is fish" "$(probe_field "${out}" comm)" "fish"
    assert_eq "fallback shell stays alive" "$(probe_field "${out}" alive)" "1"
}

# =============================================================================
# Scenario herdr-attach
# =============================================================================
# legacy_multiplexer_sweep FILE... -- case-insensitive whole-word search for the previous multiplexer. Shell scripts
# are searched without their comment lines (a comment may explain what was removed); every other file in full.
# Prints each hit, returns 1 when there is at least one.
legacy_multiplexer_sweep() {
    local file hits rc=0
    for file in "$@"; do
        if [[ "${file}" == *.sh ]]; then
            hits="$(grep -v '^[[:space:]]*#' "${file}" | grep -niw 'tmux' || true)"
        else
            hits="$(grep -niw 'tmux' "${file}" || true)"
        fi
        if [[ -n "${hits}" ]]; then
            echo "${file}: ${hits}"
            rc=1
        fi
    done
    return "${rc}"
}

scenario_herdr_attach() {
    local data opts cname pid cmdline out line sweep_out bg_out baseline during
    data="${SCRATCH_DIR}/herdr-attach/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}"
    start_ca herdr-attach "${data}" "${opts}"
    wait_ca herdr-attach || return 0
    cname="$(ca_cname herdr-attach)"

    # No client has attached yet: the add-on itself must not have written a herdr config (D-02, herdr defaults only).
    assert_fail "no herdr config.toml exists before any client attached" \
        ca_exec herdr-attach test -e /data/.config/herdr/config.toml

    assert_eq "profile.d hook calls the wrapper" \
        "$(ca_count herdr-attach 'exec coding-assistants-attach' /etc/profile.d/00-coding-assistants.sh)" "1"
    assert_eq "fish conf hook calls the wrapper" \
        "$(ca_count herdr-attach 'exec coding-assistants-attach' /data/.config/fish/conf.d/00-coding-assistants.fish)" "1"

    pid="$(ca_pid herdr-attach ttyd)"
    if [[ -z "${pid}" ]]; then
        fail "ttyd process not found"
    else
        # shellcheck disable=SC2016
        cmdline="$(ca_exec herdr-attach sh -c 'tr "\0" " " < "/proc/$1/cmdline"' sh "${pid}")"
        assert_match "ttyd command line ends in coding-assistants-attach" "${cmdline}" 'coding-assistants-attach $'
    fi
    assert_ok "the web terminal answers through nginx" \
        ca_exec herdr-attach curl -fsS -o /dev/null http://127.0.0.1:8099/terminal/

    # Login-hook guards, exercised with a real login shell in a pseudo-terminal: only an interactive SSH login
    # without the escape variables is captured by the wrapper (the client replaces the login shell: comm herdr).
    out="$(ca_pty_probe "${cname}" 5 1 env "SSH_CONNECTION=127.0.0.1 1 127.0.0.1 2222" bash -l)"
    assert_eq "SSH login shell is replaced by the herdr client" "$(probe_field "${out}" comm)" "herdr"
    out="$(ca_pty_probe "${cname}" 5 1 env "SSH_CONNECTION=127.0.0.1 1 127.0.0.1 2222" CODING_ASSISTANTS_NO_ATTACH=1 bash -l)"
    assert_eq "CODING_ASSISTANTS_NO_ATTACH keeps the login shell" "$(probe_field "${out}" comm)" "bash"
    out="$(ca_pty_probe "${cname}" 5 1 env "SSH_CONNECTION=127.0.0.1 1 127.0.0.1 2222" HERDR_ENV=1 bash -l)"
    assert_eq "HERDR_ENV (inside a pane) keeps the login shell" "$(probe_field "${out}" comm)" "bash"
    out="$(ca_pty_probe "${cname}" 5 1 bash -l)"
    assert_eq "a login shell without SSH_CONNECTION is not captured" "$(probe_field "${out}" comm)" "bash"

    # Real sshd round trip: the profile hook must start a herdr client next to the server.
    ca_exec herdr-attach sh -c 'rm -f /tmp/verify-ssh-key /tmp/verify-ssh-key.pub \
        && ssh-keygen -q -t ed25519 -N "" -f /tmp/verify-ssh-key \
        && cat /tmp/verify-ssh-key.pub >> /root/.ssh/authorized_keys'
    baseline="$(herdr_count herdr-attach)"
    bg_out="${SCRATCH_DIR}/herdr-attach-ssh.out"
    ca_pty_probe "${cname}" 8 1 ssh -tt -p 2222 -i /tmp/verify-ssh-key -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1 >"${bg_out}" 2>&1 &
    local probe_pid=$!
    sleep 5
    during="$(herdr_count herdr-attach)"
    wait "${probe_pid}"
    line="$(cat "${bg_out}")"
    if [[ "${during}" -gt "${baseline}" ]]; then
        pass "ssh login started a second herdr process (${baseline} -> ${during}) through the profile hook"
    else
        fail "ssh login did not start a herdr client (herdr processes ${baseline} -> ${during}): ${line}"
    fi
    if [[ "$(probe_field "${line}" bytes)" -gt 0 ]] 2>/dev/null; then
        pass "ssh round trip produced output"
    else
        fail "ssh round trip produced no output (${line})"
    fi

    # The previous multiplexer is gone: image and repository.
    assert_fail "the previous multiplexer is not installed in the image" \
        ca_exec herdr-attach sh -c 'command -v tmux'
    assert_fail "its system-wide config file is not in the image" ca_exec herdr-attach test -e /etc/tmux.conf
    assert_fail "its config file is gone from the repository" test -e "${ADDON_DIR}/tmux.conf"
    if sweep_out="$(legacy_multiplexer_sweep "${ADDON_DIR}/Dockerfile" "${ADDON_DIR}/nginx.conf" "${ADDON_DIR}/run.sh")"; then
        pass "no mention of the previous multiplexer in Dockerfile, nginx.conf and run.sh (code lines)"
    else
        fail "leftover of the previous multiplexer: ${sweep_out}"
    fi
}

# =============================================================================
# Scenario surface
# =============================================================================
# yaml_list_has FILE KEY ENTRY -- the top-level YAML list KEY in FILE contains the quoted entry ENTRY
yaml_list_has() {
    awk -v key="$2" '
        $0 ~ "^" key ":" { in_list = 1; next }
        in_list && /^[^[:space:]-]/ { in_list = 0 }
        in_list { print }' "$1" | grep -qxF "  - \"$3\""
}

scenario_surface() {
    local data opts want_ver vj entry
    want_ver="$(build_yaml_args "${ADDON_DIR}/build.yaml" | awk -F'\t' '$1 == "HERDR_VERSION" { print $2 }')"

    # Static: info.html rows and script, backup_exclude, legacy-multiplexer sweep over the user-visible files.
    for entry in 'id="v-claude"' 'id="v-herdr"' 'v.claude' 'v.herdr'; do
        assert_ok "info.html contains ${entry}" grep -qF -- "${entry}" "${ADDON_DIR}/info.html"
    done
    for entry in '.config/herdr/*.sock' '.config/herdr/*.log' '.config/herdr/session-snapshots/*' \
        '.local/share/claude/*'; do
        assert_ok "backup_exclude contains ${entry}" yaml_list_has "${ADDON_DIR}/config.yaml" backup_exclude "${entry}"
    done
    assert_ok "TOOLS.md mentions herdr" grep -qw herdr "${ADDON_DIR}/TOOLS.md"
    if entry="$(legacy_multiplexer_sweep "${ADDON_DIR}/Dockerfile" "${ADDON_DIR}/nginx.conf" "${ADDON_DIR}/run.sh" \
        "${ADDON_DIR}/TOOLS.md" "${ADDON_DIR}/info.html")"; then
        pass "no mention of the previous multiplexer in Dockerfile, nginx.conf, run.sh, TOOLS.md, info.html"
    else
        fail "leftover of the previous multiplexer: ${entry}"
    fi

    # Runtime: versions.json and MOTD of a real container.
    data="${SCRATCH_DIR}/surface/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}"
    start_ca surface "${data}" "${opts}"
    wait_ca surface || return 0
    vj="$(ca_exec surface curl -fsS http://127.0.0.1:8099/versions.json)"
    json_check "versions.json has a non-empty claude field" "${vj}" '(.claude | length) > 0'
    json_check "versions.json herdr field equals the build.yaml pin (${want_ver})" "${vj}" \
        ".herdr == \"${want_ver}\""
    assert_ok "/etc/motd shows the herdr version" ca_exec surface grep -q "herdr ${want_ver}" /etc/motd
}

# =============================================================================
# Scenario plugins
# =============================================================================
# State directory of a plugin (follows $HOME, not XDG_CONFIG_HOME: inside the container filesystem, not /data)
CA_PLUGIN_STATE_DIR="/root/.local/state/herdr/plugins"

# plugin_ids NAME -- sorted, comma-joined ids of the plugins registered in the running herdr server
plugin_ids() {
    ca_herdr "$1" plugin list --json 2>/dev/null | jq -r '.result.plugins[].plugin_id' | sort | paste -sd, -
}

# wait_for NAME SECONDS CMD... -- run CMD inside the container once per second until it succeeds
wait_for() {
    local name="$1" seconds="$2" i
    shift 2
    for i in $(seq 1 "${seconds}"); do
        if ca_exec "${name}" "$@" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

scenario_plugins() {
    local data opts broken out logs ids actions

    data="${SCRATCH_DIR}/plugins/data"
    broken="${SCRATCH_DIR}/plugins/zz-broken"
    mkdir -p "${data}" "${broken}"
    opts="${data}/options.json"
    write_options "${opts}"
    # A syntactically invalid manifest: `herdr plugin link` must fail for it and run.sh must carry on (D-07).
    printf 'id = "zz.broken"\n[[actions\nthis is = not toml "\n' >"${broken}/herdr-plugin.toml"
    start_ca plugins "${data}" "${opts}" -v "${broken}:/opt/herdr-plugins/zz-broken:ro"
    wait_ca plugins || return 0

    # D-02 / D-04 invariants, checked first: the add-on itself writes neither a herdr config nor Claude settings.
    assert_fail "no herdr config.toml exists after the start" ca_exec plugins test -e /data/.config/herdr/config.toml
    assert_fail "no Claude settings.json exists after the start" ca_exec plugins test -e /data/.claude/settings.json

    # Registration: exactly the approved set, the broken directory is not part of it.
    ids="$(plugin_ids plugins)"
    assert_eq "registered plugins are exactly the approved set" "${ids}" \
        "imontes.herdr-web-service,martin.claude-limits,subagent.watch"
    logs="$(ca_logs plugins)"
    assert_match "the broken plugin directory only logged a link warning" "${logs}" \
        'WARNING.*herdr plugin link failed for /opt/herdr-plugins/zz-broken'

    # D-07 isolation: nginx answered (wait_ca), herdr and the terminal are healthy despite the broken plugin.
    out="$(ca_herdr plugins status --json)"
    json_check "herdr server is running" "${out}" '.server.running == true'
    assert_ok "the web terminal answers through nginx" \
        ca_exec plugins curl -fsS -o /dev/null http://127.0.0.1:8099/terminal/

    # subagent-watch: actions are registered, the Node launcher works, the dry-run writes nothing.
    actions="$(ca_herdr plugins plugin action list 2>/dev/null \
        | jq -r '.result.actions[] | select(.plugin_id == "subagent.watch") | .action_id' | sort | paste -sd, -)"
    assert_eq "subagent.watch registers the actions open, remove and setup" "${actions}" "open,remove,setup"
    assert_ok "subagent-watch setup --dry-run runs through the Node launcher (exit 0)" \
        ca_exec plugins sh -c 'cd /opt/herdr-plugins/herdr-subagent-watch && sh bin/run.sh scripts/setup.mjs --dry-run'
    assert_fail "the dry-run did not create a herdr config.toml" ca_exec plugins test -e /data/.config/herdr/config.toml
    assert_fail "the dry-run did not create a config.toml under the default path either" \
        ca_exec plugins test -e /root/.config/herdr/config.toml
    assert_fail "the dry-run did not create a Claude settings.json" ca_exec plugins test -e /data/.claude/settings.json

    # claude-limits: the startup hook started the poller although no credentials exist; everything stays usable.
    assert_fail "no Claude credentials file exists" ca_exec plugins test -e /data/.claude/.credentials.json
    if wait_for plugins 20 test -s "${CA_PLUGIN_STATE_DIR}/martin.claude-limits/poller.pid"; then
        pass "claude-limits startup hook ran (poller.pid exists)"
    else
        fail "claude-limits poller.pid did not appear within 20 s"
    fi
    assert_match "the claude-limits poller reports the missing credentials and keeps running" \
        "$(ca_exec plugins cat "${CA_PLUGIN_STATE_DIR}/martin.claude-limits/poller.log" 2>/dev/null)" \
        'no Claude Code credentials found'
    assert_ok "the claude-limits poller process is alive" \
        ca_exec plugins sh -c "kill -0 \$(cat ${CA_PLUGIN_STATE_DIR}/martin.claude-limits/poller.pid)"
    assert_ok "herdr still answers after the plugin startup hooks" ca_herdr plugins status --json
    assert_ok "the web terminal still answers" \
        ca_exec plugins curl -fsS -o /dev/null http://127.0.0.1:8099/terminal/
    assert_fail "still no herdr config.toml at the end" ca_exec plugins test -e /data/.config/herdr/config.toml
    assert_fail "still no Claude settings.json at the end" ca_exec plugins test -e /data/.claude/settings.json

    # herdr-web-service (patched and built in the image): the startup hook brought the server up on loopback.
    if wait_for plugins 30 curl -fsS http://127.0.0.1:7340/api/health; then
        pass "web-service /api/health answers on 127.0.0.1:7340 (startup hook ran)"
    else
        fail "web-service /api/health did not answer within 30 s"
    fi
    assert_ok "web-service server.pid exists" \
        ca_exec plugins test -s "${CA_PLUGIN_STATE_DIR}/imontes.herdr-web-service/server.pid"
    assert_ok "built client dist/index.html exists" \
        ca_exec plugins test -f /opt/herdr-plugins/herdr-web-service/dist/index.html
    assert_fail "the pinned checkout carries no .git directory" \
        ca_exec plugins test -e /opt/herdr-plugins/herdr-web-service/.git
    out="$(ca_exec plugins curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:7340/ 2>/dev/null)"
    assert_eq "web-service index answers 200" "${out}" "200"
    out="$(ca_exec plugins curl -sS http://127.0.0.1:7340/ 2>/dev/null)"
    assert_ok "the index HTML references its assets" grep -q 'assets/' <<<"${out}"
    assert_fail "the index HTML has no root-absolute src= or href= attribute" grep -qE '(src|href)="/' <<<"${out}"
    out="$(ca_exec plugins curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' \
        -H 'Host: 127.0.0.1:7340' -H 'Origin: http://127.0.0.1:7340' \
        --data '{"password":"verify-not-a-password","remember":false}' http://127.0.0.1:7340/api/auth/login 2>/dev/null)"
    assert_eq "login answers 503 while no password exists (closed until herdr_web_password is set)" "${out}" "503"
    yellow "INFO: image size $(docker image inspect --format '{{.Size}}' "${IMAGE_NAME}" 2>/dev/null) bytes (${IMAGE_NAME})"
}

# =============================================================================
# Scenario services
# =============================================================================
# The ingress-style request headers: HA ingress forwards the browser's Host and Origin, nginx must override both with
# loopback values (the plugin's allow-list only accepts those).
CA_INGRESS_HEADERS=(-H 'Origin: http://ha.invalid:8123' -H 'Host: ha.invalid:8123')
# The upgrade nonce is 16 fixed bytes, base64-encoded at runtime (a literal would trip the secret scanner).
CA_WS_HEADERS=(--http1.1 --max-time 3 -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13'
    -H "Sec-WebSocket-Key: $(printf 'verify-ws-nonce-' | base64)")

# ca_ingress NAME CURL_ARGS... -- curl inside the container, through the add-on nginx, with ingress-style headers
ca_ingress() {
    local name="$1"
    shift
    ca_exec "${name}" curl -sS "${CA_INGRESS_HEADERS[@]}" "$@"
}

# ca_ingress_headers NAME PATH [CURL_ARGS...] -- the response headers (CR stripped) of a request to /PATH, body dropped
ca_ingress_headers() {
    local name="$1" path="$2"
    shift 2
    ca_ingress "${name}" -o /dev/null -D - "$@" "http://127.0.0.1:8099${path}" | tr -d '\r'
}

# ca_ingress_status NAME PATH [CURL_ARGS...] -- the HTTP status code of a request to /PATH
ca_ingress_status() {
    local name="$1" path="$2"
    shift 2
    ca_ingress "${name}" -o /dev/null -w '%{http_code}' "$@" "http://127.0.0.1:8099${path}"
}

# ca_ws_status NAME PATH [CURL_ARGS...] -- the status code of a WebSocket upgrade request (curl stays attached after a
# 101 and is ended by --max-time, so the status line is read from the headers, not from -w)
ca_ws_status() {
    local name="$1" path="$2"
    shift 2
    ca_ingress "${name}" "${CA_WS_HEADERS[@]}" -o /dev/null -D - "$@" "http://127.0.0.1:8099${path}" 2>/dev/null \
        | tr -d '\r' | awk 'NR == 1 { print $2 }'
}

# The asset probe runs INSIDE the container (python3 -I): fetch the index, collect every src/href, resolve each against
# the page URL and fetch it. Prints `index=S refs=N bad=M absolute=K` and one `BAD <url> <status>` line per failure.
services_asset_probe_py() {
    cat <<'PYEOF'
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

BASE = "http://127.0.0.1:8099/services/"
HEADERS = {"Origin": "http://ha.invalid:8123", "Host": "ha.invalid:8123"}


def fetch(url):
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("src", "href") and value:
                self.refs.append(value)


status, html = fetch(BASE)
parser = Refs()
parser.feed(html)
bad = 0
absolute = 0
for ref in parser.refs:
    if ref.startswith("/"):
        absolute += 1
    code, _ = fetch(urljoin(BASE, ref))
    if code != 200:
        bad += 1
        print("BAD", urljoin(BASE, ref), code)
print("index=%d refs=%d bad=%d absolute=%d" % (status, len(parser.refs), bad, absolute))
PYEOF
}

# services_loopback_only NAME -- succeeds when port 7340 listens on 127.0.0.1 and on no wildcard address
services_loopback_only() {
    local name="$1" listing
    if ca_exec "${name}" sh -c 'command -v ss' >/dev/null 2>&1; then
        listing="$(ca_exec "${name}" ss -ltn)"
        grep -qE '(^|[[:space:]])127\.0\.0\.1:7340([[:space:]]|$)' <<<"${listing}" || return 1
        ! grep -qE '(^|[[:space:]])(0\.0\.0\.0|\*|\[::\]):7340([[:space:]]|$)' <<<"${listing}"
    else
        yellow "INFO: ss not available, checking /proc/net/tcp instead"
        listing="$(ca_exec "${name}" sh -c 'cat /proc/net/tcp /proc/net/tcp6')"
        grep -qE '0100007F:1CAC [0-9A-F]+:0000 0A' <<<"${listing}" || return 1
        ! grep -qiE '^ *[0-9]+: (0{8}|0{32}):1CAC ' <<<"${listing}"
    fi
}

scenario_services() {
    local data opts out hdr body

    data="${SCRATCH_DIR}/services/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}"
    start_ca services "${data}" "${opts}"
    wait_ca services || return 0

    # The plugin's startup hook brings the server up shortly after herdr; wait before the first request through nginx.
    if wait_for services 30 curl -fsS http://127.0.0.1:7340/api/health; then
        pass "web-service /api/health answers on 127.0.0.1:7340"
    else
        fail "web-service /api/health did not answer within 30 s"
        return 0
    fi

    # Relative redirect: an absolute Location would leave the HA ingress prefix.
    hdr="$(ca_ingress_headers services /services)"
    assert_match "GET /services returns 301" "$(head -n 1 <<<"${hdr}")" ' 301 '
    assert_match "the redirect Location is the relative services/" "${hdr}" $'(^|\n)[Ll]ocation: services/(\n|$)'

    # Index and assets: everything resolves relative to /services/ and answers 200 (Host/Origin spoof included).
    out="$(ca_exec services python3 -I -c "$(services_asset_probe_py)")"
    assert_match "GET /services/ returns 200, every referenced asset resolves and answers 200" "${out}" \
        'index=200 refs=[1-9][0-9]* bad=0 absolute=0'
    [[ "${out}" == *BAD* ]] && yellow "${out}"

    # Headers: exactly one CSP that allows framing by the landing page, no HSTS from the plugin.
    hdr="$(ca_ingress_headers services /services/)"
    assert_eq "exactly one Content-Security-Policy header" "$(grep -ci '^content-security-policy:' <<<"${hdr}")" "1"
    assert_match "the CSP carries frame-ancestors 'self'" "${hdr}" "frame-ancestors 'self'"
    assert_fail "the CSP has no frame-ancestors 'none'" grep -qi "frame-ancestors 'none'" <<<"${hdr}"
    assert_fail "no Strict-Transport-Security header on the index" grep -qi '^strict-transport-security:' <<<"${hdr}"

    # Closed login without a password (503), and no Strict-Transport-Security on the login response either.
    out="$(ca_ingress services -o /dev/null -D - -X POST -H 'content-type: application/json' \
        --data '{"password":"verify-not-a-password","remember":false}' \
        http://127.0.0.1:8099/services/api/auth/login | tr -d '\r')"
    assert_match "login answers 503 while no password exists" "$(head -n 1 <<<"${out}")" ' 503 '
    assert_fail "no Strict-Transport-Security header on the login response" grep -qi '^strict-transport-security:' \
        <<<"${out}"

    # An unauthenticated WebSocket upgrade must not get through.
    out="$(ca_ws_status services /services/ws)"
    if [[ -n "${out}" && "${out}" != "101" ]]; then
        pass "unauthenticated WebSocket upgrade to /services/ws is refused (${out})"
    else
        fail "unauthenticated WebSocket upgrade to /services/ws was not refused (status '${out}')"
    fi

    # Landing page and the terminal regression.
    body="$(ca_exec services curl -fsS http://127.0.0.1:8099/)"
    assert_match "the landing page has the Services tab" "${body}" "show\('services', this\)"
    assert_match "the landing page lazy-loads ./services/ in an iframe" "${body}" 'data-src="\./services/"'
    assert_eq "GET /terminal/ still answers 200" "$(ca_ingress_status services /terminal/)" "200"

    # The plugin is reachable only through nginx: loopback bind (the add-on publishes only 2222 and 4096).
    if services_loopback_only services; then
        pass "port 7340 is bound to 127.0.0.1 only"
    else
        fail "port 7340 is not bound to 127.0.0.1 only"
    fi
}

# =============================================================================
# Scenario services-auth
# =============================================================================
# Throwaway fixture password; it satisfies the plugin's rules (6+ characters, symbol, number, uppercase letter).
CA_WEB_PASSWORD='Verify-Pass1!'
CA_WEB_CONFIG_DIR="/data/.config/herdr/plugins/config/imontes.herdr-web-service"

# services_login NAME PASSWORD -- login through nginx; prints the response headers (CR stripped)
services_login() {
    local body
    body="$(jq -cn --arg p "$2" '{password: $p, remember: false}')"
    ca_ingress "$1" -o /dev/null -D - -X POST -H 'content-type: application/json' --data "${body}" \
        http://127.0.0.1:8099/services/api/auth/login | tr -d '\r'
}

# services_wait_health NAME -- wait until /services/api/health answers through nginx
services_wait_health() {
    wait_for "$1" 30 curl -fsS "${CA_INGRESS_HEADERS[@]}" http://127.0.0.1:8099/services/api/health
}

# services_first_status HEADERS -- the status code of the first response line
services_first_status() { head -n 1 <<<"$1" | awk '{ print $2 }'; }

scenario_services_auth() {
    local data opts hdr cookie logs out

    # --- Container A: a valid password ------------------------------------------------------------------------
    data="${SCRATCH_DIR}/services-auth/a/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" ". + {herdr_web_password: \"${CA_WEB_PASSWORD}\"}"
    start_ca svcauth-a "${data}" "${opts}"
    wait_ca svcauth-a || return 0
    if services_wait_health svcauth-a; then
        pass "A: /services/api/health answers through nginx"
    else
        fail "A: /services/api/health did not answer within 30 s"
        return 0
    fi

    # At most two failed logins per container: every request through nginx shares the loopback client address.
    hdr="$(services_login svcauth-a 'Wrong-Pass9?')"
    assert_eq "A: a wrong password is refused with 401" "$(services_first_status "${hdr}")" "401"
    hdr="$(services_login svcauth-a "${CA_WEB_PASSWORD}")"
    assert_eq "A: the right password returns 204" "$(services_first_status "${hdr}")" "204"
    assert_match "A: Set-Cookie carries hwv_session" "${hdr}" $'(^|\n)[Ss]et-[Cc]ookie: hwv_session='
    assert_match "A: the session cookie is HttpOnly" "${hdr}" $'[Ss]et-[Cc]ookie: hwv_session=[^\n]*; HttpOnly'
    assert_fail "A: the session cookie is not Secure (nginx clears X-Forwarded-Proto)" \
        grep -qi '^set-cookie:.*; secure' <<<"${hdr}"
    cookie="$(sed -nE 's/^[Ss]et-[Cc]ookie: (hwv_session=[^;]+).*/\1/p' <<<"${hdr}" | head -n 1)"
    if [[ -z "${cookie}" ]]; then
        fail "A: no session cookie could be extracted, the authenticated checks are skipped"
        return 0
    fi

    out="$(ca_ingress svcauth-a -H "Cookie: ${cookie}" http://127.0.0.1:8099/services/api/session)"
    json_check "A: /api/session reports authenticated with the cookie" "${out}" '.authenticated == true'
    out="$(ca_ingress svcauth-a http://127.0.0.1:8099/services/api/session)"
    json_check "A: /api/session reports not authenticated without the cookie" "${out}" '.authenticated == false'
    assert_eq "A: the gated /api/roster answers 200 with the cookie" \
        "$(ca_ingress_status svcauth-a /services/api/roster -H "Cookie: ${cookie}")" "200"
    assert_eq "A: the gated /api/roster answers 401 without the cookie" \
        "$(ca_ingress_status svcauth-a /services/api/roster)" "401"
    assert_eq "A: the WebSocket upgrade with the cookie returns 101" \
        "$(ca_ws_status svcauth-a /services/ws -H "Cookie: ${cookie}")" "101"
    out="$(ca_ws_status svcauth-a /services/ws)"
    if [[ -n "${out}" && "${out}" != "101" ]]; then
        pass "A: the WebSocket upgrade without the cookie is refused (${out})"
    else
        fail "A: the WebSocket upgrade without the cookie was not refused (status '${out}')"
    fi

    # The hash is persistent and private; the plaintext exists nowhere on disk or in the log.
    assert_eq "A: the auth file in the plugin config dir has mode 600" \
        "$(ca_exec svcauth-a stat -c '%a' "${CA_WEB_CONFIG_DIR}/auth.json" 2>/dev/null)" "600"
    assert_fail "A: the plaintext password is not in the plugin config dir" \
        ca_exec svcauth-a grep -rqF -- "${CA_WEB_PASSWORD}" "${CA_WEB_CONFIG_DIR}"
    logs="$(ca_logs svcauth-a)"
    assert_match "A: run.sh logged that the login password was set" "${logs}" 'herdr-web-service login password set'
    assert_fail "A: the plaintext password is not in the container log" grep -qF -- "${CA_WEB_PASSWORD}" <<<"${logs}"

    # Re-creation on the same /data: the hash survives, the login works again without any new step.
    restart_ca svcauth-a
    wait_ca svcauth-a || return 0
    if services_wait_health svcauth-a; then
        hdr="$(services_login svcauth-a "${CA_WEB_PASSWORD}")"
        assert_eq "A: after a container re-creation the same password still returns 204" \
            "$(services_first_status "${hdr}")" "204"
    else
        fail "A: /services/api/health did not answer within 30 s after the re-creation"
    fi
    assert_fail "A: the plaintext password is not in the log after the re-creation either" \
        grep -qF -- "${CA_WEB_PASSWORD}" <<<"$(ca_logs svcauth-a)"

    # --- Container B: a password the plugin rejects (no uppercase letter) -------------------------------------
    data="${SCRATCH_DIR}/services-auth/b/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}" '. + {herdr_web_password: "short1!"}'
    start_ca svcauth-b "${data}" "${opts}"
    wait_ca svcauth-b || return 0
    logs="$(ca_logs svcauth-b)"
    assert_match "B: a rejected password is a warning" "${logs}" 'WARNING.*herdr-web-service rejected herdr_web_password'
    assert_match "B: the warning names the unmet rule (uppercase letter)" "${logs}" '[Uu]pper'
    assert_fail "B: the rejected password is not in the container log" grep -qF -- 'short1!' <<<"${logs}"
    assert_ok "B: nginx still answers (the weak password did not stop run.sh)" \
        ca_exec svcauth-b curl -fsS -o /dev/null http://127.0.0.1:8099/terminal/
    if services_wait_health svcauth-b; then
        hdr="$(services_login svcauth-b "${CA_WEB_PASSWORD}")"
        assert_eq "B: the login stays closed (503)" "$(services_first_status "${hdr}")" "503"
    else
        fail "B: /services/api/health did not answer within 30 s"
    fi

    # --- Container C: no option at all -----------------------------------------------------------------------
    data="${SCRATCH_DIR}/services-auth/c/data"
    mkdir -p "${data}"
    opts="${data}/options.json"
    write_options "${opts}"
    start_ca svcauth-c "${data}" "${opts}"
    wait_ca svcauth-c || return 0
    assert_match "C: the log says the login is disabled until herdr_web_password is set" "$(ca_logs svcauth-c)" \
        'login is disabled until the add-on option herdr_web_password is set'
    if services_wait_health svcauth-c; then
        hdr="$(services_login svcauth-c "${CA_WEB_PASSWORD}")"
        assert_eq "C: the login answers 503" "$(services_first_status "${hdr}")" "503"
    else
        fail "C: /services/api/health did not answer within 30 s"
    fi
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
