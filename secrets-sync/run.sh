#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# Maps option secrets to environment variables (never argv) and starts the app.
# Non-secret options are read by the app itself from /data/options.json.
set -e

export SS_OPTIONS="${SS_OPTIONS:-/data/options.json}"
export SS_SECRETS_FILE="${SS_SECRETS_FILE:-/config/secrets.yaml}"
export SS_FILES_DIR="${SS_FILES_DIR:-/config/secrets_files}"
export SS_STATE_FILE="${SS_STATE_FILE:-/data/state.json}"
export SS_DATA_DIR="${SS_DATA_DIR:-/data}"
export SS_PORT="${SS_PORT:-8099}"
export SS_AGE_KEY_FILE="${SS_AGE_KEY_FILE:-/addon_config/age.key}"
export BITWARDENCLI_APPDATA_DIR="${BITWARDENCLI_APPDATA_DIR:-/data/bw}"

if [ ! -s "${SS_OPTIONS}" ]; then
    echo "[run] ${SS_OPTIONS} missing or empty" >&2
    exit 1
fi

umask 077
mkdir -p "${BITWARDENCLI_APPDATA_DIR}"

# Secrets reach the app (and bw) via env only; jq/bashio never echo them
if bashio::config.exists 'bitwarden.client_id'; then
    BW_CLIENTID="$(bashio::config 'bitwarden.client_id')"
    BW_CLIENTSECRET="$(bashio::config 'bitwarden.client_secret')"
    BW_PASSWORD="$(bashio::config 'bitwarden.master_password')"
    export BW_CLIENTID BW_CLIENTSECRET BW_PASSWORD
fi

# Level is set by the app from options.json (log_level); never log option values here
umask 022
cd /opt/secrets-sync
exec python3 -m app.main
