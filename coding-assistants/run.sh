#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

LOG_LEVEL=$(bashio::config 'log_level')
bashio::log.level "${LOG_LEVEL}"

# Persist /data directories for all coding assistants
mkdir -p \
    /data/claude \
    /data/.config/opencode \
    /data/.local/share/opencode

# Claude Code — symlink ~/.claude* into /data (does not honour XDG)
rm -rf /root/.claude
ln -s /data/claude/.claude /root/.claude 2>/dev/null || true
rm -f /root/.claude.json
ln -s /data/claude/.claude.json /root/.claude.json 2>/dev/null || true

# Write env profile (picked up by SSH login shells and ttyd/tmux via bash -l)
mkdir -p /etc/profile.d
: > /etc/profile.d/00-coding-assistants.sh
chmod +x /etc/profile.d/00-coding-assistants.sh

# XDG redirects — opencode (and other XDG-compliant tools) store data in /data
# Tool paths
cat >> /etc/profile.d/00-coding-assistants.sh << 'EOF'
export XDG_CONFIG_HOME="/data/.config"
export XDG_DATA_HOME="/data/.local/share"
export PATH="/root/.local/bin:/usr/local/bin:$PATH"
EOF

# Export for current process so ttyd/sshd children inherit them
export XDG_CONFIG_HOME="/data/.config"
export XDG_DATA_HOME="/data/.local/share"

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

# Start ttyd — web terminal via HA ingress (port 7681)
bashio::log.info "Starting web terminal on port 7681..."
ttyd \
    --port 7681 \
    --interface 0.0.0.0 \
    --writable \
    --client-option "fontSize=${FONT_SIZE}" \
    --client-option "theme=${THEME_JSON}" \
    tmux new-session -A -s main &

wait
