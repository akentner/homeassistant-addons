#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# PID 1: renders server.yml, runs ntfy and the admin GUI, bootstraps the admin once auth.db exists.
# ntfy dying ends the container (the Supervisor restarts it); the GUI is restarted on its own.
# Option values are never echoed here; secrets reach the CLI via environment only.

DATA_DIR="${NTFY_DATA_DIR:-/data}"
export NTFY_OPTIONS="${NTFY_OPTIONS:-${DATA_DIR}/options.json}"
export NTFY_CONFIG_FILE="${DATA_DIR}/server.yml"
export NTFY_AUTH_FILE="${DATA_DIR}/auth.db"
NTFY_ADDON_VERSION="$(bashio::app.version 2>/dev/null || bashio::addon.version 2>/dev/null || echo unknown)"
export NTFY_ADDON_VERSION

umask 077
cd /opt/ntfy-gui || exit 1

if [ ! -s "${NTFY_OPTIONS}" ]; then
    echo "[run] ${NTFY_OPTIONS} missing or empty" >&2
    exit 1
fi

if ! python3 -m app.render_config; then
    echo "[run] render_config failed" >&2
    exit 1
fi

gui_loop() {
    local child=0
    trap '[ "${child}" -ne 0 ] && kill -TERM "${child}" 2>/dev/null; exit 0' TERM INT
    while true; do
        python3 -m app.gui &
        child=$!
        wait "${child}"
        child=0
        echo "[run] GUI exited, restarting in 2s" >&2
        sleep 2 &
        wait $!
    done
}

ntfy serve &
NTFY_PID=$!
# The ntfy CLI needs auth.db, which only the running server creates: bootstrap waits for it in the background.
# Bootstrap problems must not stop notification delivery.
python3 -m app.bootstrap &
gui_loop &
GUI_PID=$!

# shellcheck disable=SC2317,SC2329  # invoked through the trap below
shutdown() {
    kill -TERM "${GUI_PID}" "${NTFY_PID}" 2>/dev/null
    wait
    exit 0
}
trap shutdown TERM INT

wait "${NTFY_PID}"
rc=$?
echo "[run] ntfy exited (code ${rc}), stopping" >&2
kill -TERM "${GUI_PID}" 2>/dev/null
wait "${GUI_PID}" 2>/dev/null
exit 1
