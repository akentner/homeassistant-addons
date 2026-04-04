#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Ensure .claude directory exists on persistent volume
mkdir -p /data/.claude

# Symlink /root/.claude to /data/.claude so OAuth token survives container restarts
ln -sf /data/.claude /root/.claude

# Check for Claude credentials — required to start
if [[ ! -f /data/.claude/.claude.json ]]; then
    bashio::log.error "Claude credentials not found at /data/.claude/.claude.json"
    bashio::log.error ""
    bashio::log.error "To authenticate, follow these steps:"
    bashio::log.error "  1. Install the 'Terminal & SSH' add-on from the HA add-on store"
    bashio::log.error "  2. Open the terminal and run: docker exec -it \$(docker ps -qf name=meridian) sh"
    bashio::log.error "  3. Inside the container run: claude login"
    bashio::log.error "  4. Complete the OAuth flow in your browser"
    bashio::log.error "  5. Restart this add-on"
    exit 1
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

# Hand off to S6 — exec replaces shell process; HA restart policy handles recovery
exec node "${WORKING_DIR}/dist/cli.js"
