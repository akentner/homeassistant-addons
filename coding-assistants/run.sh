#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

LOG_LEVEL=$(bashio::config 'log_level')
bashio::log.level "${LOG_LEVEL}"

# Persist /data directories for all coding assistants
mkdir -p \
    /data/.config/opencode \
    /data/.local/share/opencode

# Git config persistence — copy on first run, then symlink
if [[ -f /root/.gitconfig ]] && [[ ! -f /data/.gitconfig ]]; then
    cp /root/.gitconfig /data/.gitconfig
fi
rm -f /root/.gitconfig
ln -sf /data/.gitconfig /root/.gitconfig

TOOLS_MD="/etc/coding-assistants/TOOLS.md"
OPENCODE_JSON="/data/.config/opencode/opencode.json"
[[ -f "${OPENCODE_JSON}" ]] || echo '{}' > "${OPENCODE_JSON}"
tmp=$(mktemp)
jq --rawfile inst "${TOOLS_MD}" '.instructions = [$inst]' "${OPENCODE_JSON}" > "${tmp}"
cp "${tmp}" "${OPENCODE_JSON}"
rm "${tmp}"
bashio::log.info "Updated tool context in OpenCode instructions"

# Opencode binary persistence — first start copies the bundled binary into /data,
# then symlinks /root/.opencode/bin → /data/opencode/bin. The official installer writes
# upgrades to $HOME/.opencode/bin, so routing that path through /data keeps user-initiated
# `opencode upgrade` invocations across container rebuilds.
mkdir -p /data/opencode/bin
if [[ ! -e /data/opencode/bin/opencode ]]; then
    cp /opt/opencode-initial/opencode /data/opencode/bin/opencode
    chmod +x /data/opencode/bin/opencode
    bashio::log.info "Initialized opencode binary in persistent storage"
fi
rm -rf /root/.opencode/bin
ln -s /data/opencode/bin /root/.opencode/bin

# Claude Code binary persistence — the native installer layout is kept, rooted in /data. The updater honours
# XDG_DATA_HOME=/data/.local/share (exported further below) and writes new versions to
# /data/.local/share/claude/versions, so `claude update` only takes effect when the launcher
# /root/.local/bin/claude points INTO that directory. Hence the launcher is re-created on every start and points
# at the newest persisted version; the image seed in /opt/claude-initial is copied in only when it is strictly
# newer (rebuilds never downgrade and never lose an update). Absolute paths only: the XDG exports come later.
# bashio runs this script with errexit + pipefail: pipelines that may legitimately yield nothing end in `|| true`.
CLAUDE_VERSIONS_DIR="/data/.local/share/claude/versions"
mkdir -p "${CLAUDE_VERSIONS_DIR}" /root/.local/bin
CLAUDE_SEED=$(find /opt/claude-initial -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | head -n 1) || true
if [[ -z "${CLAUDE_SEED}" ]]; then
    bashio::log.warning "No Claude Code seed in /opt/claude-initial — skipping Claude Code launcher setup"
else
    CLAUDE_NEWEST=$(find "${CLAUDE_VERSIONS_DIR}" -maxdepth 1 -type f -perm /u+x -printf '%f\n' \
        | grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -n 1) || true
    if [[ -z "${CLAUDE_NEWEST}" ]] \
        || [[ "$(printf '%s\n%s\n' "${CLAUDE_SEED}" "${CLAUDE_NEWEST}" | sort -V | tail -n 1)" != "${CLAUDE_NEWEST}" ]]; then
        cp -a "/opt/claude-initial/${CLAUDE_SEED}" "${CLAUDE_VERSIONS_DIR}/.${CLAUDE_SEED}.tmp"
        mv -f "${CLAUDE_VERSIONS_DIR}/.${CLAUDE_SEED}.tmp" "${CLAUDE_VERSIONS_DIR}/${CLAUDE_SEED}"
        CLAUDE_NEWEST="${CLAUDE_SEED}"
        bashio::log.info "Seeded Claude Code ${CLAUDE_SEED} into persistent storage"
    fi
    ln -sfn "${CLAUDE_VERSIONS_DIR}/${CLAUDE_NEWEST}" /root/.local/bin/claude
    bashio::log.info "Claude Code ${CLAUDE_NEWEST} ready"
fi

# Claude Code state persistence — ~/.claude and ~/.claude.json are symlinks into /data so credentials, settings
# and Claude's own rewrites land on the volume. One-time migration of the legacy layout (/data/claude/.claude*):
# copy only when the new path is absent; the legacy files are never deleted.
if [[ ! -e /data/.claude && -d /data/claude/.claude ]]; then
    cp -a /data/claude/.claude /data/.claude
    bashio::log.info "Migrated legacy /data/claude/.claude to /data/.claude"
fi
if [[ ! -e /data/.claude.json && -f /data/claude/.claude.json ]]; then
    cp -a /data/claude/.claude.json /data/.claude.json
    bashio::log.info "Migrated legacy /data/claude/.claude.json to /data/.claude.json"
fi
mkdir -p /data/.claude
chmod 700 /data/.claude
[[ -f /data/.claude.json ]] || echo '{}' > /data/.claude.json
chmod 600 /data/.claude.json
rm -rf /root/.claude /root/.claude.json
ln -s /data/.claude /root/.claude
ln -s /data/.claude.json /root/.claude.json

# Tool context for Claude Code — TOOLS.md is injected into the user-level /data/.claude/CLAUDE.md as a marked block
# that is rewritten on every start; all text outside the markers is preserved. Placed after the state persistence
# above so a legacy volume is migrated before /data/.claude is first used. Block-level HTML comments are stripped
# before injection into Claude's context, so the markers cost no tokens.
python3 - <<'PYEOF'
import pathlib
import re

BEGIN = "<!-- coding-assistants:begin -->"
END = "<!-- coding-assistants:end -->"

tools = pathlib.Path("/etc/coding-assistants/TOOLS.md").read_text()
if not tools.endswith("\n"):
    tools += "\n"
block = BEGIN + "\n" + tools + "\n" + END + "\n"

target = pathlib.Path("/data/.claude/CLAUDE.md")
content = target.read_text() if target.exists() else ""
span = re.compile(
    r"^" + re.escape(BEGIN) + r"[ \t]*\n.*?^" + re.escape(END) + r"[ \t]*(?:\n|\Z)",
    re.DOTALL | re.MULTILINE,
)
if not content.strip():
    content = block
elif span.search(content):
    # Function replacement: backslashes in TOOLS.md must never be read as group references.
    content = span.sub(lambda _match: block, content, count=1)
else:
    content = content.rstrip("\n") + "\n\n" + block
target.write_text(content)
PYEOF
bashio::log.info "Updated tool context in Claude Code CLAUDE.md"

# Write MOTD with current addon version and tool versions (absolute launcher path: PATH is not extended yet)
ADDON_VERSION=$(bashio::addon.version)
CLAUDE_VERSION=$(/root/.local/bin/claude --version 2>/dev/null | head -n 1 | cut -d' ' -f1) || true
OPENCODE_VERSION=$(opencode --version 2>/dev/null | head -1)
MOTD_HA_URL=$(bashio::config 'ha_url')
cat > /etc/motd << EOF
Coding Assistants ${ADDON_VERSION}  |  claude ${CLAUDE_VERSION}  |  opencode ${OPENCODE_VERSION}
HA: ${MOTD_HA_URL}
EOF

# Version info for web UI
printf '{"addon":"%s","claude":"%s","opencode":"%s"}\n' \
    "${ADDON_VERSION}" "${CLAUDE_VERSION}" "${OPENCODE_VERSION}" \
    > /opt/coding-assistants/versions.json

# Fish config persistence — copy defaults on first run, then symlink
if [[ ! -d /data/.config/fish ]]; then
    cp -a /root/.config/fish /data/.config/fish
    bashio::log.info "Initialized fish config in persistent storage"
fi
rm -rf /root/.config/fish
ln -s /data/.config/fish /root/.config/fish

# claude_mcp_merge JSON_OBJECT — merge MCP servers into Claude Code's user-scope config (/data/.claude.json).
# Argument: one JSON object mapping server name to a Claude-format entry. Only `.mcpServers` is assigned, so every
# other key (oauthAccount, projects, ...) passes through untouched, and the add-on defaults sit on the LEFT of the
# object addition so entries that already exist (user edits, earlier starts) win. The result is copied back with
# `cp` (never `mv`: the file is the target of the ~/.claude.json symlink) and ONLY when jq succeeded and produced
# output; otherwise the file stays byte-identical, because a blind copy of a failed jq run would wipe all of
# Claude's auth and project state. Returns 1 after a warning (callers must test it: run.sh runs under errexit).
# Entry contents carry secrets and are never logged, only counts.
claude_mcp_merge() {
    local target="/data/.claude.json" tmp count
    [[ -f "${target}" ]] || echo '{}' > "${target}"
    tmp=$(mktemp)
    count=$(jq -r 'length' <<< "$1" 2>/dev/null) || count="?"
    if jq --argjson add "$1" '.mcpServers = ($add + (.mcpServers // {}))' "${target}" > "${tmp}" 2>/dev/null \
        && [[ -s "${tmp}" ]]; then
        cp "${tmp}" "${target}"
        rm -f "${tmp}"
        return 0
    fi
    bashio::log.warning "Could not merge MCP servers (${count} entries) into ${target}; leaving it untouched"
    rm -f "${tmp}"
    return 1
}

# MCP server auto-registration — merge addon config into OpenCode's opencode.json
if jq -e '.mcp_servers | length > 0' /data/options.json > /dev/null 2>&1; then
    # OpenCode format: { name: { type: "local", command: [...], enabled } }
    OPENCODE_JSON="/data/.config/opencode/opencode.json"
    [[ -f "${OPENCODE_JSON}" ]] || echo '{}' > "${OPENCODE_JSON}"
    MCP_OBJ_OC=$(jq -c '
        .mcp_servers
        | map(select(.type != "http"))
        | map({ (.name): { type: "local", command: ([.command] + (.args // [])), enabled: true } })
        | add // {}
    ' /data/options.json)
    tmp=$(mktemp)
    jq --argjson mcp "${MCP_OBJ_OC}" '.mcp = ($mcp + (.mcp // {}))' "${OPENCODE_JSON}" > "${tmp}"
    cp "${tmp}" "${OPENCODE_JSON}"
    rm "${tmp}"

    MCP_COUNT=$(jq -r '.mcp_servers | length' /data/options.json)
    bashio::log.info "Registered ${MCP_COUNT} MCP server(s) in OpenCode config"

    # Claude Code format (user scope, /data/.claude.json): http -> { type, url }; everything else -> stdio with
    # args and an env object. Existing entries win (see claude_mcp_merge).
    MCP_OBJ_CLAUDE=$(jq -c '
        .mcp_servers
        | map(if .type == "http"
              then { (.name): { type: "http", url: .url } }
              else { (.name): { type: "stdio", command: .command, args: (.args // []),
                                env: ((.env // []) | map({ (.name): .value }) | add // {}) } }
              end)
        | add // {}
    ' /data/options.json)
    if claude_mcp_merge "${MCP_OBJ_CLAUDE}"; then
        bashio::log.info "Registered $(jq -r 'length' <<< "${MCP_OBJ_CLAUDE}") MCP server(s) in Claude Code config"
    fi
fi

# Zigbee2MQTT MCP auto-registration — registers the dedicated MCP server when enabled
if bashio::config.true 'zigbee2mqtt.enabled'; then
    Z2M_BROKER_URL=$(bashio::config 'zigbee2mqtt.mqtt_broker_url')
    Z2M_USERNAME=$(bashio::config 'zigbee2mqtt.mqtt_username')
    Z2M_PASSWORD=$(bashio::config 'zigbee2mqtt.mqtt_password')
    Z2M_BASE_TOPIC=$(bashio::config 'zigbee2mqtt.mqtt_base_topic')
    Z2M_DB_PATH=$(bashio::config 'zigbee2mqtt.db_path')
    Z2M_LOG_LEVEL=$(bashio::config 'zigbee2mqtt.log_level')

    # Build env object for the MCP server command
    Z2M_ENV_JSON=$(jq -n \
        --arg broker "${Z2M_BROKER_URL}" \
        --arg user "${Z2M_USERNAME}" \
        --arg pass "${Z2M_PASSWORD}" \
        --arg topic "${Z2M_BASE_TOPIC}" \
        --arg db "${Z2M_DB_PATH}" \
        --arg log "${Z2M_LOG_LEVEL}" \
        '{
            MQTT_BROKER_URL: $broker,
            MQTT_USERNAME: $user,
            MQTT_PASSWORD: $pass,
            MQTT_BASE_TOPIC: $topic,
            DB_PATH: $db,
            LOG_LEVEL: $log
        }')

    # Register in OpenCode opencode.json
    OPENCODE_JSON="/data/.config/opencode/opencode.json"
    [[ -f "${OPENCODE_JSON}" ]] || echo '{}' > "${OPENCODE_JSON}"
    tmp=$(mktemp)
    jq '.mcp["zigbee2mqtt"] = {
            type: "local",
            command: ["node", "/opt/mcp2zigbee2mqtt/dist/index.js"],
            enabled: true
        }' "${OPENCODE_JSON}" > "${tmp}"
    cp "${tmp}" "${OPENCODE_JSON}"
    rm "${tmp}"

    bashio::log.info "Registered zigbee2mqtt MCP server in OpenCode config"

    # Claude Code (user scope): the entry carries an explicit env object. Claude's stdio servers are not guaranteed
    # to inherit the add-on environment, and the MQTT_* exports appended to the profile files below are lost again
    # when those files are rewritten later in this script (the OpenCode entry silently depends on them).
    Z2M_OBJ_CLAUDE=$(jq -n --argjson env "${Z2M_ENV_JSON}" '{
        zigbee2mqtt: {
            type: "stdio",
            command: "node",
            args: ["/opt/mcp2zigbee2mqtt/dist/index.js"],
            env: $env
        }
    }')
    if claude_mcp_merge "${Z2M_OBJ_CLAUDE}"; then
        bashio::log.info "Registered zigbee2mqtt MCP server in Claude Code config"
    fi

    # Inject MQTT env vars into profile scripts for use by other tools
    {
        printf 'export MQTT_BROKER_URL=%q\n' "${Z2M_BROKER_URL}"
        printf 'export MQTT_USERNAME=%q\n' "${Z2M_USERNAME}"
        printf 'export MQTT_PASSWORD=%q\n' "${Z2M_PASSWORD}"
        printf 'export MQTT_BASE_TOPIC=%q\n' "${Z2M_BASE_TOPIC}"
    } >> /etc/profile.d/00-coding-assistants.sh

    # Fish config — append MQTT env vars
    FISH_CONF="/data/.config/fish/conf.d/00-coding-assistants.fish"
    {
        printf 'set -x MQTT_BROKER_URL %s\n' "${Z2M_BROKER_URL}"
        printf 'set -x MQTT_USERNAME %s\n' "${Z2M_USERNAME}"
        printf 'set -x MQTT_PASSWORD %s\n' "${Z2M_PASSWORD}"
        printf 'set -x MQTT_BASE_TOPIC %s\n' "${Z2M_BASE_TOPIC}"
    } >> "${FISH_CONF}"
fi

# mycli / MariaDB auto-configuration — writes /data/.myclirc, generates per-connection
# mcp-server-mysql wrapper scripts, registers them in OpenCode, and exports
# default-connection env vars (MYCLI_*) to /etc/profile.d/00-coding-assistants.sh.
# Fish env var append happens later (after FISH_CONF is built).
if bashio::config.true 'mycli.enabled'; then
    # Validate: connections must be a non-empty array
    if ! jq -e '.mycli.connections | type == "array" and length > 0' /data/options.json > /dev/null 2>&1; then
        bashio::exit.nok "mycli.enabled=true but mycli.connections is empty or not an array"
    fi

    # Validate: no duplicate connection names
    if [[ "$(jq -r '[.mycli.connections[].name] | group_by(.) | map(select(length > 1)) | length' /data/options.json)" != "0" ]]; then
        bashio::exit.nok "mycli.connections has duplicate connection names"
    fi

    # Validate: connection names match a safe shell-suffix + JSON-key charset
    while IFS= read -r n; do
        if ! [[ "${n}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
            bashio::exit.nok "mycli connection name '${n}' must match [a-zA-Z0-9_-]+"
        fi
    done < <(jq -r '.mycli.connections[].name' /data/options.json)

    # Resolve default connection name (explicit `mycli.default` or fall back to first)
    MYCLI_DEFAULT=$(bashio::config 'mycli.default')
    if [[ -z "${MYCLI_DEFAULT}" || "${MYCLI_DEFAULT}" == "null" ]]; then
        MYCLI_DEFAULT=$(jq -r '.mycli.connections[0].name' /data/options.json)
        bashio::log.info "mycli.default not set — using first connection: '${MYCLI_DEFAULT}'"
    elif ! jq -e --arg n "${MYCLI_DEFAULT}" '.mycli.connections[] | select(.name == $n)' /data/options.json > /dev/null 2>&1; then
        bashio::exit.nok "mycli.default='${MYCLI_DEFAULT}' does not match any connection name"
    fi

    CONNECTION_COUNT=$(jq -r '.mycli.connections | length' /data/options.json)

    # Write /data/.myclirc with [client] default + [alias_<name>] per connection
    python3 - "${MYCLI_DEFAULT}" > /data/.myclirc <<'PYEOF'
import configparser, json, pathlib, sys
default_name = sys.argv[1]
cfg = json.loads(pathlib.Path("/data/options.json").read_text())["mycli"]
connections = cfg["connections"]
p = configparser.ConfigParser()
default_conn = next(c for c in connections if c["name"] == default_name)
client = {
    "host": default_conn["host"],
    "port": str(default_conn.get("port") or 3306),
    "user": default_conn["username"],
}
if default_conn.get("password"):
    client["password"] = default_conn["password"]
if default_conn.get("database"):
    client["database"] = default_conn["database"]
p["client"] = client
for c in connections:
    sect = f"alias_{c['name']}"
    p[sect] = {
        "host": c["host"],
        "port": str(c.get("port") or 3306),
        "user": c["username"],
    }
    if c.get("password"):
        p[sect]["password"] = c["password"]
    if c.get("database"):
        p[sect]["database"] = c["database"]
p.write(sys.stdout)
PYEOF
    chmod 600 /data/.myclirc
    bashio::log.info "Wrote /data/.myclirc with ${CONNECTION_COUNT} connection(s); default='${MYCLI_DEFAULT}'"

    # Per connection: generate env-baked wrapper script + register as MCP server
    CLAUDE_MARIADB_COUNT=0
    while IFS= read -r entry; do
        name=$(echo "${entry}" | jq -r '.name')
        host=$(echo "${entry}" | jq -r '.host')
        port=$(echo "${entry}" | jq -r '.port // 3306')
        user=$(echo "${entry}" | jq -r '.username')
        password=$(echo "${entry}" | jq -r '.password // ""')
        database=$(echo "${entry}" | jq -r '.database // ""')
        mcp_name="mariadb-${name}"
        mcp_script="/usr/local/bin/${mcp_name}"

        # Wrapper script: set env then exec mcp-server-mysql. printf %q handles single quotes safely.
        {
            printf '#!/bin/bash\n'
            printf 'set -e\n'
            printf 'export MYSQL_HOST=%q\n' "${host}"
            printf 'export MYSQL_PORT=%q\n' "${port}"
            printf 'export MYSQL_USER=%q\n' "${user}"
            [[ -n "${password}" ]] && printf 'export MYSQL_PASSWORD=%q\n' "${password}"
            [[ -n "${database}" ]] && printf 'export MYSQL_DATABASE=%q\n' "${database}"
            printf 'exec mcp-server-mysql "$@"\n'
        } > "${mcp_script}"
        chmod 700 "${mcp_script}"

        # Register in OpenCode (opencode.json → mcp)
        OPENCODE_JSON="/data/.config/opencode/opencode.json"
        [[ -f "${OPENCODE_JSON}" ]] || echo '{}' > "${OPENCODE_JSON}"
        tmp=$(mktemp)
        jq --arg n "${mcp_name}" --arg cmd "${mcp_script}" \
            '.mcp[$n] = { type: "local", command: [$cmd], enabled: true }' "${OPENCODE_JSON}" > "${tmp}"
        cp "${tmp}" "${OPENCODE_JSON}"
        rm "${tmp}"

        # Register in Claude Code (/data/.claude.json → mcpServers); the wrapper bakes in MYSQL_*, so env stays empty
        if claude_mcp_merge "$(jq -cn --arg n "${mcp_name}" --arg cmd "${mcp_script}" \
            '{ ($n): { type: "stdio", command: $cmd, args: [], env: {} } }')"; then
            CLAUDE_MARIADB_COUNT=$((CLAUDE_MARIADB_COUNT + 1))
        fi
    done < <(jq -c '.mycli.connections[]' /data/options.json)

    bashio::log.info "Registered ${CONNECTION_COUNT} mariadb-mcp server(s) in OpenCode config"
    bashio::log.info "Registered ${CLAUDE_MARIADB_COUNT} mariadb-mcp server(s) in Claude Code config"

    # Stash default-connection values for the late fish append (below)
    MYCLI_DEFAULT_HOST=$(jq -r --arg n "${MYCLI_DEFAULT}" '.mycli.connections[] | select(.name == $n) | .host' /data/options.json)
    MYCLI_DEFAULT_PORT=$(jq -r --arg n "${MYCLI_DEFAULT}" '.mycli.connections[] | select(.name == $n) | (.port // 3306)' /data/options.json)
    MYCLI_DEFAULT_USER=$(jq -r --arg n "${MYCLI_DEFAULT}" '.mycli.connections[] | select(.name == $n) | .username' /data/options.json)
    MYCLI_DEFAULT_PWD=$(jq -r --arg n "${MYCLI_DEFAULT}" '.mycli.connections[] | select(.name == $n) | (.password // "")' /data/options.json)
    MYCLI_DEFAULT_DB=$(jq -r --arg n "${MYCLI_DEFAULT}" '.mycli.connections[] | select(.name == $n) | (.database // "")' /data/options.json)

    # Inject MYCLI_* env vars into /etc/profile.d/00-coding-assistants.sh (bash login shells)
    {
        printf 'export MYCLI_HOST=%q\n' "${MYCLI_DEFAULT_HOST}"
        printf 'export MYCLI_PORT=%q\n' "${MYCLI_DEFAULT_PORT}"
        printf 'export MYCLI_USER=%q\n' "${MYCLI_DEFAULT_USER}"
        [[ -n "${MYCLI_DEFAULT_PWD}" ]] && printf 'export MYCLI_PASSWORD=%q\n' "${MYCLI_DEFAULT_PWD}"
        [[ -n "${MYCLI_DEFAULT_DB}" ]] && printf 'export MYCLI_DATABASE=%q\n' "${MYCLI_DEFAULT_DB}"
    } >> /etc/profile.d/00-coding-assistants.sh
fi

# Write env profile (picked up by SSH login shells)
mkdir -p /etc/profile.d
: > /etc/profile.d/00-coding-assistants.sh
chmod +x /etc/profile.d/00-coding-assistants.sh

# XDG redirects — opencode (and other XDG-compliant tools) store data in /data
# Tool paths
HA_URL=$(bashio::config 'ha_url')
HA_TOKEN=$(bashio::config 'ha_token')

{
    cat << 'EOF'
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export XDG_CONFIG_HOME="/data/.config"
export XDG_DATA_HOME="/data/.local/share"
export PATH="/root/.opencode/bin:/root/.local/bin:/usr/local/bin:$PATH"
EOF
    printf 'export HA_URL=%q\n' "${HA_URL}"
    printf 'export HA_TOKEN=%q\n' "${HA_TOKEN}"
    printf 'export SUPERVISOR_TOKEN=%q\n' "${SUPERVISOR_TOKEN}"
    cat << 'EOF'
# SSH: attach to the shared herdr session (SSH and the web terminal end in the same session). Only for interactive
# SSH logins: HERDR_ENV marks a shell inside a herdr pane (never nest), CODING_ASSISTANTS_NO_ATTACH is the escape
# hatch (also set by the wrapper's plain-shell fallback), a non-terminal stdin is a scripted login.
if [[ -n "$SSH_CONNECTION" ]] && [[ -z "$HERDR_ENV" ]] && [[ -z "$CODING_ASSISTANTS_NO_ATTACH" ]] && [[ -t 0 ]]; then
    exec coding-assistants-attach
fi
EOF
} > /etc/profile.d/00-coding-assistants.sh

# Inject user-configured bash aliases
if jq -e '.bash_aliases | length > 0' /data/options.json > /dev/null 2>&1; then
    while IFS= read -r entry; do
        alias_name=$(echo "$entry" | jq -r '.name')
        alias_cmd=$(echo "$entry" | jq -r '.command')
        printf "alias %s=%q\n" "$alias_name" "$alias_cmd" >> /etc/profile.d/00-coding-assistants.sh
    done < <(jq -c '.bash_aliases[]' /data/options.json)
fi

# Export for current process so ttyd/sshd children inherit them
export PATH="/root/.opencode/bin:/root/.local/bin:/usr/local/bin:$PATH"
export XDG_CONFIG_HOME="/data/.config"
export XDG_DATA_HOME="/data/.local/share"
export HA_URL
export HA_TOKEN
export SUPERVISOR_TOKEN

# Claude Code authentication from the optional add-on password options. Exported into THIS process environment
# only, so ttyd, sshd and everything they spawn inherit them; never written to /etc/profile.d, the fish conf.d file
# (persistent in /data) or a log line. An unset option reads as "null" (and an empty one as ""): exporting an empty
# ANTHROPIC_API_KEY would switch Claude into API-key mode with an empty key, so only real values are exported.
# Precedence in Claude Code when both are set: ANTHROPIC_API_KEY beats CLAUDE_CODE_OAUTH_TOKEN.
CLAUDE_AUTH_OAUTH=$(bashio::config 'claude_code_oauth_token') || CLAUDE_AUTH_OAUTH=""
if [[ -n "${CLAUDE_AUTH_OAUTH}" && "${CLAUDE_AUTH_OAUTH}" != "null" ]]; then
    export CLAUDE_CODE_OAUTH_TOKEN="${CLAUDE_AUTH_OAUTH}"
    bashio::log.info "Exported CLAUDE_CODE_OAUTH_TOKEN from the add-on options"
fi
CLAUDE_AUTH_API_KEY=$(bashio::config 'anthropic_api_key') || CLAUDE_AUTH_API_KEY=""
if [[ -n "${CLAUDE_AUTH_API_KEY}" && "${CLAUDE_AUTH_API_KEY}" != "null" ]]; then
    export ANTHROPIC_API_KEY="${CLAUDE_AUTH_API_KEY}"
    bashio::log.info "Exported ANTHROPIC_API_KEY from the add-on options"
fi
unset CLAUDE_AUTH_OAUTH CLAUDE_AUTH_API_KEY

# Inject user-configured env vars
if jq -e '.env_vars | length > 0' /data/options.json > /dev/null 2>&1; then
    while IFS= read -r entry; do
        name=$(echo "$entry" | jq -r '.name')
        val=$(echo "$entry" | jq -r '.value')
        printf 'export %s=%q\n' "$name" "$val" >> /etc/profile.d/00-coding-assistants.sh
        # Also export for the current process (ttyd inherits this)
        declare -x "$name=$val"
    done < <(jq -c '.env_vars[]' /data/options.json)
fi

# Fish config — write runtime env to conf.d (overwritten each start)
FISH_CONF="/data/.config/fish/conf.d/00-coding-assistants.fish"
mkdir -p /data/.config/fish/conf.d
{
    cat << 'EOF'
set -x LANG en_US.UTF-8
set -x LC_ALL en_US.UTF-8
set -x XDG_CONFIG_HOME /data/.config
set -x XDG_DATA_HOME /data/.local/share
set -U fish_user_paths (string match -rv '^/homeassistant/(bin|scripts/bin)' $fish_user_paths)
fish_add_path /root/.opencode/bin /root/.local/bin /usr/local/bin

# Tool integrations
zoxide init fish | source
atuin init fish | source
direnv hook fish | source

function fish_greeting
    cat /etc/motd
end
EOF
    printf 'set -x HA_URL %s\n' "${HA_URL}"
    printf 'set -x HA_TOKEN %s\n' "${HA_TOKEN}"
    printf 'set -x SUPERVISOR_TOKEN %s\n' "${SUPERVISOR_TOKEN}"
    cat << 'EOF'

# SSH: attach to the shared herdr session (same guards as the bash profile hook; panes have HERDR_ENV=1)
if set -q SSH_CONNECTION; and not set -q HERDR_ENV; and not set -q CODING_ASSISTANTS_NO_ATTACH; and status is-interactive
    exec coding-assistants-attach
end
EOF
} > "${FISH_CONF}"

# User-configured bash_aliases → fish aliases
if jq -e '.bash_aliases | length > 0' /data/options.json > /dev/null 2>&1; then
    while IFS= read -r entry; do
        alias_name=$(echo "$entry" | jq -r '.name')
        alias_cmd=$(echo "$entry" | jq -r '.command')
        printf "alias %s %q\n" "$alias_name" "$alias_cmd" >> "${FISH_CONF}"
    done < <(jq -c '.bash_aliases[]' /data/options.json)
fi

# User-configured env_vars → fish
if jq -e '.env_vars | length > 0' /data/options.json > /dev/null 2>&1; then
    while IFS= read -r entry; do
        name=$(echo "$entry" | jq -r '.name')
        val=$(echo "$entry" | jq -r '.value')
        printf 'set -x %s %s\n' "$name" "$val" >> "${FISH_CONF}"
    done < <(jq -c '.env_vars[]' /data/options.json)
fi

# Fish config — append MYCLI_* env vars for default connection (set in mycli block above)
if [[ -n "${MYCLI_DEFAULT:-}" ]]; then
    {
        printf 'set -x MYCLI_HOST %s\n' "${MYCLI_DEFAULT_HOST}"
        printf 'set -x MYCLI_PORT %s\n' "${MYCLI_DEFAULT_PORT}"
        printf 'set -x MYCLI_USER %s\n' "${MYCLI_DEFAULT_USER}"
        [[ -n "${MYCLI_DEFAULT_PWD}" ]] && printf 'set -x MYCLI_PASSWORD %s\n' "${MYCLI_DEFAULT_PWD}"
        [[ -n "${MYCLI_DEFAULT_DB}" ]] && printf 'set -x MYCLI_DATABASE %s\n' "${MYCLI_DEFAULT_DB}"
    } >> "${FISH_CONF}"
fi

# Set bash as login shell for root so SSH sessions source /etc/profile.d/*
if ! grep -q 'root:.*:/bin/bash' /etc/passwd; then
    sed -i '/^root:/s|:[^:]*$|:/bin/bash|' /etc/passwd
fi

# SSH setup — persist host keys in /data/ssh across restarts
mkdir -p /data/ssh
for key_type in rsa ecdsa ed25519; do
    key_file="/data/ssh/ssh_host_${key_type}_key"
    if [[ ! -f "${key_file}" ]]; then
        bashio::log.info "Generating SSH host key: ${key_type}"
        ssh-keygen -t "${key_type}" -f "${key_file}" -N "" -q
    fi
done

# Write authorized keys from addon config (one key per list entry)
mkdir -p /root/.ssh
chmod 700 /root/.ssh
jq -r '.authorized_keys[]?' /data/options.json > /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

KEY_COUNT=$(wc -l < /root/.ssh/authorized_keys)
if [[ "${KEY_COUNT}" -eq 0 ]]; then
    bashio::log.warning "No SSH authorized_keys configured — SSH login will be impossible."
fi

# herdr server -- started HERE (after every export above, the env_vars injection and the fish conf) and never by a
# client: the server's environment becomes the environment of every pane, so panes get PATH (/root/.local/bin),
# HA_URL/HA_TOKEN/SUPERVISOR_TOKEN and the Claude auth variables. SHELL/LANG/LC_ALL are set for this one command only.
# Respawn loop (D-07): a crashed or stopped server (`herdr server stop` therefore acts as a restart) must not leave
# SSH and the web terminal without a session; clients fall back to a plain fish shell meanwhile. `|| rc=$?` keeps
# errexit from ending the loop.
mkdir -p /data/.config/herdr
(
    cd /homeassistant || cd /
    while true; do
        rc=0
        SHELL=/usr/bin/fish LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 herdr server || rc=$?
        bashio::log.warning "herdr server exited (status ${rc}), restarting in 3 s"
        sleep 3
    done
) &

HERDR_UP=0
for _ in $(seq 1 50); do
    if herdr status --json 2>/dev/null | jq -e '.server.running == true' > /dev/null 2>&1; then
        HERDR_UP=1
        break
    fi
    sleep 0.2
done
if [[ "${HERDR_UP}" == "1" ]]; then
    # Workspace `main` (cwd /homeassistant) exists before the first client attaches.
    coding-assistants-attach --ensure \
        || bashio::log.warning "Could not create the herdr workspace 'main' (clients will retry)"
    bashio::log.info "herdr server is running"
else
    bashio::log.warning "herdr server did not answer within 10 s (clients fall back to a plain fish shell until it does)"
fi

# Start sshd (background)
bashio::log.info "Starting SSH server on port 2222..."
/usr/sbin/sshd -D -f /etc/ssh/sshd_config &

# ttyd theme mapping
THEME=$(bashio::config 'terminal_theme')
case "${THEME}" in
    solarized-dark)
        THEME_JSON='{"background":"#002b36","foreground":"#839496","cursor":"#839496","black":"#073642","red":"#dc322f","green":"#859900","yellow":"#b58900","blue":"#268bd2","magenta":"#d33682","cyan":"#2aa198","white":"#eee8d5"}'
        ;;
    solarized-light)
        THEME_JSON='{"background":"#fdf6e3","foreground":"#657b83","cursor":"#657b83","black":"#073642","red":"#dc322f","green":"#859900","yellow":"#b58900","blue":"#268bd2","magenta":"#d33682","cyan":"#2aa198","white":"#eee8d5"}'
        ;;
    monokai)
        THEME_JSON='{"background":"#272822","foreground":"#f8f8f2","cursor":"#f8f8f0","black":"#272822","red":"#f92672","green":"#a6e22e","yellow":"#f4bf75","blue":"#66d9ef","magenta":"#ae81ff","cyan":"#a1efe4","white":"#f8f8f2"}'
        ;;
    tomorrow-night)
        THEME_JSON='{"background":"#1d1f21","foreground":"#c5c8c6","cursor":"#c5c8c6","black":"#1d1f21","red":"#cc6666","green":"#b5bd68","yellow":"#f0c674","blue":"#81a2be","magenta":"#b294bb","cyan":"#8abeb7","white":"#c5c8c6"}'
        ;;
    zenburn)
        THEME_JSON='{"background":"#3f3f3f","foreground":"#dcdccc","cursor":"#dcdccc","black":"#1e2320","red":"#cc9393","green":"#7f9f7f","yellow":"#e3ceab","blue":"#dfaf8f","magenta":"#dc8cc3","cyan":"#93e0e3","white":"#dcdccc"}'
        ;;
    *)
        THEME_JSON='{}'
        ;;
esac

FONT_SIZE=$(bashio::config 'terminal_font_size')
FONT_FAMILY=$(bashio::config 'terminal_font_family')

# Start opencode server (port 4096)
bashio::log.info "Starting opencode server on port 4096..."
opencode serve --port 4096 --hostname 0.0.0.0 &

# Start ttyd — web terminal, bound to localhost (nginx proxies /terminal/)
bashio::log.info "Starting web terminal on port 7681 (localhost)..."
ttyd \
    --port 7681 \
    --interface 127.0.0.1 \
    --base-path /terminal/ \
    --writable \
    --client-option "fontSize=${FONT_SIZE}" \
    --client-option "fontFamily=${FONT_FAMILY}" \
    --client-option "theme=${THEME_JSON}" \
    coding-assistants-attach &

# Start nginx — serves landing page + proxies sub-services (port 8099 = ingress)
bashio::log.info "Starting nginx on port 8099..."
nginx &

wait
