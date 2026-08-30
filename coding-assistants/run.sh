#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

LOG_LEVEL=$(bashio::config 'log_level')
bashio::log.level "${LOG_LEVEL}"

# Write MOTD with current addon version and tool versions
ADDON_VERSION=$(bashio::addon.version)
OPENCODE_VERSION=$(opencode --version 2>/dev/null | head -1)
MOTD_HA_URL=$(bashio::config 'ha_url')
cat > /etc/motd << EOF
Coding Assistants ${ADDON_VERSION}  |  opencode ${OPENCODE_VERSION}
HA: ${MOTD_HA_URL}
EOF

# Version info for web UI
printf '{"addon":"%s","opencode":"%s"}\n' \
    "${ADDON_VERSION}" "${OPENCODE_VERSION}" \
    > /opt/coding-assistants/versions.json

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

# Fish config persistence — copy defaults on first run, then symlink
if [[ ! -d /data/.config/fish ]]; then
    cp -a /root/.config/fish /data/.config/fish
    bashio::log.info "Initialized fish config in persistent storage"
fi
rm -rf /root/.config/fish
ln -s /data/.config/fish /root/.config/fish

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
    done < <(jq -c '.mycli.connections[]' /data/options.json)

    bashio::log.info "Registered ${CONNECTION_COUNT} mariadb-mcp server(s) in OpenCode config"

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

# Write env profile (picked up by SSH login shells and ttyd/tmux via bash -l)
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
# SSH: auto-attach to shared tmux session (enables web/SSH tmux sharing)
if [[ -n "$SSH_CONNECTION" ]] && [[ -z "$TMUX" ]]; then
    exec tmux new-session -A -s main -c /homeassistant
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

# SSH: auto-attach to shared tmux session
if set -q SSH_CONNECTION; and not set -q TMUX
    exec tmux new-session -A -s main -c /homeassistant
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
    tmux new-session -A -s main -c /homeassistant &

# Start nginx — serves landing page + proxies sub-services (port 8099 = ingress)
bashio::log.info "Starting nginx on port 8099..."
nginx &

wait
