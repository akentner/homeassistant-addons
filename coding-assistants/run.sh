#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

LOG_LEVEL=$(bashio::config 'log_level')
bashio::log.level "${LOG_LEVEL}"

# Persist /data directories for all coding assistants
mkdir -p \
    /data/claude \
    /data/.config/opencode \
    /data/.local/share/opencode

# Fish config persistence — copy defaults on first run, then symlink
if [[ ! -d /data/.config/fish ]]; then
    cp -a /root/.config/fish /data/.config/fish
    bashio::log.info "Initialized fish config in persistent storage"
fi
rm -rf /root/.config/fish
ln -s /data/.config/fish /root/.config/fish

# Claude Code — symlink ~/.claude* into /data (does not honour XDG)
rm -rf /root/.claude
ln -s /data/claude/.claude /root/.claude 2>/dev/null || true
rm -f /root/.claude.json
ln -s /data/claude/.claude.json /root/.claude.json 2>/dev/null || true

# Inject tool context into AI assistant configs (first run only)
TOOLS_MD="/etc/coding-assistants/TOOLS.md"
CLAUDE_MD="/data/claude/.claude/CLAUDE.md"
mkdir -p /data/claude/.claude
if [[ ! -f "${CLAUDE_MD}" ]] || ! grep -q "coding-assistants" "${CLAUDE_MD}" 2>/dev/null; then
    cat "${TOOLS_MD}" >> "${CLAUDE_MD}"
    bashio::log.info "Injected tool context into Claude Code CLAUDE.md"
fi

OPENCODE_JSON="/data/.config/opencode/opencode.json"
[[ -f "${OPENCODE_JSON}" ]] || echo '{}' > "${OPENCODE_JSON}"
if ! jq -e '.instructions' "${OPENCODE_JSON}" > /dev/null 2>&1; then
    tmp=$(mktemp)
    jq --rawfile inst "${TOOLS_MD}" '.instructions = [$inst]' "${OPENCODE_JSON}" > "${tmp}"
    cp "${tmp}" "${OPENCODE_JSON}"
    rm "${tmp}"
    bashio::log.info "Injected tool context into OpenCode instructions"
fi

# MCP server auto-registration — merge addon config into ~/.claude.json
CLAUDE_JSON="/data/claude/.claude.json"
[[ -f "${CLAUDE_JSON}" ]] || echo '{}' > "${CLAUDE_JSON}"
if jq -e '.mcp_servers | length > 0' /data/options.json > /dev/null 2>&1; then
    # Claude Code format: stdio → { type, command, args, env }  http → { type, url }
    MCP_OBJ=$(jq -c '
        .mcp_servers
        | map(
            if .type == "http" then
                { (.name): { type: "http", url: .url } }
            else
                { (.name): {
                    type: "stdio",
                    command: .command,
                    args: (.args // []),
                    env: ((.env // []) | map({ (.name): .value }) | add // {})
                  }
                }
            end
          )
        | add // {}
    ' /data/options.json)
    tmp=$(mktemp)
    jq --argjson mcp "${MCP_OBJ}" '.mcpServers = ($mcp + (.mcpServers // {}))' "${CLAUDE_JSON}" > "${tmp}"
    cp "${tmp}" "${CLAUDE_JSON}"
    rm "${tmp}"

    # OpenCode format: { name: { type, command: [...], enabled } }
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

    bashio::log.info "Registered $(echo "${MCP_OBJ}" | jq -r 'keys | length') MCP server(s) in Claude Code + OpenCode config"
fi

# Cleanup stale stdio MCP entries from manually-managed global claude config
GLOBAL_CLAUDE_JSON="/homeassistant/.claudecode/.claude.json"
if [[ -f "${GLOBAL_CLAUDE_JSON}" ]] && jq -e '.mcpServers' "${GLOBAL_CLAUDE_JSON}" > /dev/null 2>&1; then
    while IFS=$'\t' read -r name cmd; do
        if [[ -n "$cmd" ]] && ! command -v "$cmd" > /dev/null 2>&1; then
            bashio::log.warning "Removing stale MCP entry '${name}': command '${cmd}' not found"
            tmp=$(mktemp)
            jq --arg n "$name" 'del(.mcpServers[$n])' "${GLOBAL_CLAUDE_JSON}" > "${tmp}" \
                && cp "${tmp}" "${GLOBAL_CLAUDE_JSON}"
            rm -f "${tmp}"
        fi
    done < <(jq -r '
        .mcpServers | to_entries[]
        | select(.value.type != "http")
        | [.key, (.value.command // "")] | @tsv
    ' "${GLOBAL_CLAUDE_JSON}")
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
export PATH="/root/.local/bin:/usr/local/bin:$PATH"
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
export XDG_CONFIG_HOME="/data/.config"
export XDG_DATA_HOME="/data/.local/share"
export HA_URL
export HA_TOKEN

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
fish_add_path /root/.local/bin /usr/local/bin

# Tool integrations
zoxide init fish | source
atuin init fish | source
direnv hook fish | source
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

# Start ttyd — web terminal via HA ingress (port 7681)
bashio::log.info "Starting web terminal on port 7681..."
ttyd \
    --port 7681 \
    --interface 0.0.0.0 \
    --writable \
    --client-option "fontSize=${FONT_SIZE}" \
    --client-option "fontFamily=${FONT_FAMILY}" \
    --client-option "theme=${THEME_JSON}" \
    tmux new-session -A -s main -c /homeassistant &

wait
