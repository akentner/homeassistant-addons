#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Ensure .claude directory exists on persistent volume
mkdir -p /data/claude/.claude

# Symlink /root/.claude and /root/.claude.json to /data/claude so credentials survive container restarts
# rm -rf required: ln -sf cannot replace an existing directory, only files
rm -rf /root/.claude
ln -s /data/claude/.claude /root/.claude
rm -f /root/.claude.json
ln -s /data/claude/.claude.json /root/.claude.json

# If credentials missing: keep container running so docker exec works, then poll for credentials
if [[ ! -f /data/claude/.claude.json ]]; then
    bashio::log.warning "Claude credentials not found. Container stays running for interactive login."
    bashio::log.warning ""
    ADDON_SLUG=$(curl -sf -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
        http://supervisor/addons/self/info | grep -o '"slug":"[^"]*"' | cut -d'"' -f4)
    CONTAINER_NAME="addon_${ADDON_SLUG}"
    bashio::log.warning "One-time setup — run these commands in the Terminal & SSH add-on:"
    bashio::log.warning "  docker exec -it ${CONTAINER_NAME} sh"
    bashio::log.warning "  claude"
    bashio::log.warning ""
    bashio::log.warning "After completing the OAuth flow, Meridian starts automatically."

    # Keep container alive and poll — no restart needed after claude login
    while [[ ! -f /data/claude/.claude.json ]]; do
        bashio::log.debug "Check for credentials... not found yet"
        sleep 10
    done

    bashio::log.info "Credentials found. Starting Meridian..."
fi

# Read add-on configuration
MERIDIAN_LOG_LEVEL=$(bashio::config 'log_level')
MERIDIAN_PORT=$(bashio::config 'port')

# Bind to all interfaces so LAN and Tailscale can reach the proxy (per D-08)
MERIDIAN_HOST="0.0.0.0"

export MERIDIAN_LOG_LEVEL
export MERIDIAN_PORT
export MERIDIAN_HOST

bashio::log.info "Starting Meridian proxy on port ${MERIDIAN_PORT}..."

# Start nginx as ingress frontend (port 8099 -> meridian 3456)
nginx
bashio::log.info "nginx ingress proxy started on port 8099"

# Hand off to S6 — exec replaces shell process; HA restart policy handles recovery
exec meridian
