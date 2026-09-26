#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

log() { echo "[run.sh] $*" >&2; }

# 1. Render /etc/avahi/avahi-daemon.conf + /tmp/register-printers.sh from HA
#    options (D-09: a generated template, never a sed-patched static file).
python3 /generate_config.py

# 2. D-Bus + Avahi need their runtime dirs (mirrors network-tools/run.sh).
mkdir -p /var/run/dbus /var/run/avahi-daemon

# 3. System D-Bus -- required by avahi-daemon.
dbus-daemon --system --fork || log "dbus-daemon failed to start"

# 4. Avahi daemon reads the config generate_config.py just wrote. Non-fatal:
#    a failure here must not crash the whole add-on before cupsd even starts
#    (mirrors network-tools/run.sh's exact incantation).
avahi-daemon --daemonize || log "avahi-daemon failed to start"

# 5. Start cupsd in the foreground, backgrounded here so this script can
#    finish printer registration and log-level setup before waiting on it.
cupsd -f &
CUPSD_PID=$!

log "waiting for cupsd to accept connections..."
CUPSD_READY=0
for _ in $(seq 1 30); do
    if lpstat -r >/dev/null 2>&1; then
        CUPSD_READY=1
        break
    fi
    sleep 1
done
if [ "$CUPSD_READY" = "1" ]; then
    log "cupsd is ready"
else
    log "cupsd did not become ready within 30s -- attempting printer registration anyway"
fi

# 6. Register printers against the now-live cupsd. A short settle window is
#    needed even after lpstat -r reports the scheduler up: cupsd's admin
#    interface (used by lpadmin) can still transiently reject the very first
#    connection right after readiness is first observed. Retry a few times
#    with a brief pause -- lpadmin is idempotent, so retrying after a
#    transient failure is safe.
if [ -f /tmp/register-printers.sh ]; then
    REG_OK=0
    for _ in $(seq 1 5); do
        if sh /tmp/register-printers.sh; then
            REG_OK=1
            break
        fi
        sleep 1
    done
    [ "$REG_OK" = "1" ] || log "printer registration failed after retries (see above)"
fi

# 7. Map HA log_level option to a cupsctl LogLevel value.
LOG_LEVEL=$(bashio::config 'log_level')
case "$LOG_LEVEL" in
    debug) CUPS_LOG_LEVEL="debug" ;;
    warning) CUPS_LOG_LEVEL="warn" ;;
    error) CUPS_LOG_LEVEL="error" ;;
    *) CUPS_LOG_LEVEL="info" ;;
esac
cupsctl LogLevel="$CUPS_LOG_LEVEL" || log "cupsctl LogLevel failed"

# 8. Forward termination signals to cupsd and wait on it -- the container
#    stays alive exactly as long as cupsd does. Per D-08: no watchdog for the
#    legacy-unicast reflector slot-exhaustion error is added here -- with
#    enable-reflector=no (the shipped default) that failure class cannot occur.
trap 'kill -TERM "$CUPSD_PID" 2>/dev/null' TERM INT
wait "$CUPSD_PID"
