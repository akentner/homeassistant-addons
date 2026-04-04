#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Ensure .claude directory exists on persistent volume
mkdir -p /data/.claude

# Symlink /root/.claude to /data/.claude so OAuth token survives container restarts
ln -sf /data/.claude /root/.claude

# If credentials missing: start claude login (prints OAuth URL to stdout/stderr -> HA logs)
if [[ ! -f /data/.claude/.claude.json ]]; then
    bashio::log.info "Claude credentials not found. Starting OAuth login..."
    bashio::log.info "Check the add-on logs for an OAuth URL, open it in your browser to authenticate."

    # Run claude login in background — it prints the OAuth URL and waits for browser completion
    # Claude Max OAuth does not require interactive TTY; URL appears in logs
    claude login &
    LOGIN_PID=$!

    # Poll until credentials file appears (up to 10 minutes, check every 5 seconds)
    TIMEOUT=600
    ELAPSED=0
    while [[ ! -f /data/.claude/.claude.json ]]; do
        sleep 5
        ELAPSED=$((ELAPSED + 5))
        if [[ $ELAPSED -ge $TIMEOUT ]]; then
            bashio::log.error "OAuth login timed out after ${TIMEOUT}s. Restart the add-on to try again."
            kill "$LOGIN_PID" 2>/dev/null || true
            exit 1
        fi
        bashio::log.info "Waiting for OAuth completion... (${ELAPSED}s elapsed)"
    done

    bashio::log.info "Credentials found. Proceeding to start Meridian."
    # Give claude login a moment to finalise writing, then kill the process if still running
    sleep 2
    kill "$LOGIN_PID" 2>/dev/null || true
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
exec meridian
