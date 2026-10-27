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
SS_ADDON_VERSION="$(bashio::app.version 2>/dev/null || bashio::addon.version 2>/dev/null || echo unknown)"
export SS_ADDON_VERSION
export SS_GIT_DEPLOY_KEY="${SS_GIT_DEPLOY_KEY:-/addon_config/deploy_key}"
export BITWARDENCLI_APPDATA_DIR="${BITWARDENCLI_APPDATA_DIR:-/data/bw}"

if [ ! -s "${SS_OPTIONS}" ]; then
    echo "[run] ${SS_OPTIONS} missing or empty" >&2
    exit 1
fi

umask 077
mkdir -p "${BITWARDENCLI_APPDATA_DIR}"

# Secrets reach the app (and bw) via env only. python reads options.json (works without the Supervisor API) and
# prints quoted export statements; values never touch argv or the log
eval "$(python3 -I - "${SS_OPTIONS}" <<'PY'
import json, shlex, sys
opts = json.load(open(sys.argv[1]))
bw, sops = opts.get("bitwarden") or {}, opts.get("sops") or {}
for var, src, key in (
    ("BW_CLIENTID", bw, "client_id"),
    ("BW_CLIENTSECRET", bw, "client_secret"),
    ("BW_PASSWORD", bw, "master_password"),
    ("SS_GIT_USERNAME", sops, "git_username"),
    ("SS_GIT_TOKEN", sops, "git_token"),
):
    if src.get(key):
        print(f"export {var}={shlex.quote(str(src[key]))}")
PY
)"

# Level is set by the app from options.json (log_level); never log option values here
umask 022
cd /opt/secrets-sync
exec python3 -m app.main
