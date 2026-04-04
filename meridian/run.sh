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

# Create workdir if it does not exist
MERIDIAN_WORKDIR=$(bashio::config 'workdir')
mkdir -p "${MERIDIAN_WORKDIR}"

# Numeric / string options — always export
MERIDIAN_MAX_CONCURRENT=$(bashio::config 'max_concurrent')
MERIDIAN_MAX_SESSIONS=$(bashio::config 'max_sessions')
MERIDIAN_MAX_STORED_SESSIONS=$(bashio::config 'max_stored_sessions')
MERIDIAN_IDLE_TIMEOUT_SECONDS=$(bashio::config 'idle_timeout_seconds')
MERIDIAN_TELEMETRY_SIZE=$(bashio::config 'telemetry_size')
MERIDIAN_SONNET_MODEL=$(bashio::config 'sonnet_model')
MERIDIAN_DEFAULT_AGENT=$(bashio::config 'default_agent')

export MERIDIAN_WORKDIR
export MERIDIAN_MAX_CONCURRENT
export MERIDIAN_MAX_SESSIONS
export MERIDIAN_MAX_STORED_SESSIONS
export MERIDIAN_IDLE_TIMEOUT_SECONDS
export MERIDIAN_TELEMETRY_SIZE
export MERIDIAN_SONNET_MODEL
export MERIDIAN_DEFAULT_AGENT

# Boolean options — upstream treats presence of var as enabled (unset = disabled)
if bashio::config.true 'passthrough'; then
    export MERIDIAN_PASSTHROUGH=true
fi
if bashio::config.true 'no_file_changes'; then
    export MERIDIAN_NO_FILE_CHANGES=true
fi

bashio::log.info "Starting Meridian proxy on port ${MERIDIAN_PORT}..."

# Start nginx as ingress frontend (port 8099 -> meridian 3456)
nginx
bashio::log.info "nginx ingress proxy started on port 8099"

# Hand off to S6 — exec replaces shell process; HA restart policy handles recovery
exec meridian
