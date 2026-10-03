#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

log() { echo "[run.sh] $*" >&2; }

# 1. Render /etc/avahi/avahi-daemon.conf, /etc/cups/cupsd.conf (LAN-reachability
#    scoping -- see generate_config.py's build_cupsd_conf docstring), and
#    /tmp/register-printers.sh from HA options (D-09: a generated template,
#    never a sed-patched static file). This must run before cupsd starts
#    below so cupsd reads the patched Listen/Location directives on its very
#    first startup, not the stock localhost-only defaults.
#    Any non-zero exit (invalid avahi_hostname, invalid JSON, unwritable path,
#    uncaught exception) is fatal: running avahi/cupsd with stock config would
#    publish an unconfigured service (CR-02). Nothing starts before this point.
if ! python3 /generate_config.py; then
    log "generate_config.py failed -- refusing to start"
    exit 1
fi

# 2. D-Bus + Avahi need their runtime dirs (mirrors network-tools/run.sh).
mkdir -p /var/run/dbus /var/run/avahi-daemon
# A container restart reuses this filesystem, so pid files of the previous run
# survive: dbus-daemon then refuses to start and avahi-daemon reports "Daemon
# already running on PID <n>" (a stale number that may even match an unrelated
# process in the new PID namespace). Nothing is running yet at this point.
rm -f /var/run/dbus/pid /var/run/dbus/dbus.pid /var/run/avahi-daemon/pid

# 3. System D-Bus -- required by avahi-daemon.
dbus-daemon --system --fork || log "dbus-daemon failed to start"

# 4. Avahi daemon reads the config generate_config.py just wrote. Started by
#    the startup guard (avahi-guard.sh): avahi runs in the foreground of a
#    background job so its own log lines reach this add-on's log, and this
#    step returns only after avahi reported a settled host name, so cupsd (step
#    6) cannot publish its DNS-SD records under a name avahi later abandons
#    (D-11). Never fatal: after bounded retries the guard continues under the
#    actual name with a loud ERROR (startup-only, no watchdog -- D-08).
if [ -f /tmp/avahi-guard.env ]; then
    # shellcheck source=/dev/null
    . /tmp/avahi-guard.env
fi
# shellcheck source=/dev/null
. /avahi-guard.sh
avahi_guard_start

# 5. Provision the optional CUPS web-admin login (`admin_username` /
#    `admin_password`), from the script generate_config.py already rendered
#    at step 1 (/tmp/provision-admin.sh -- validation lives there, alongside
#    every other option's defensive validation, since it reads /data/options.json
#    directly; this step just executes the result, mirroring how
#    /tmp/register-printers.sh is generated in step 1 and executed later).
#    Written as its own file (not present at all when admin_username/
#    admin_password are unset, the fail-safe default) rather than a plain
#    function here, so root cause: cupsd's `Require user @SYSTEM` checks
#    directly against /etc/shadow via crypt() (no PAM config in this image)
#    -- this container's filesystem is not persisted outside /data, so
#    /etc/passwd/shadow reset to the stock image on every restart/update,
#    meaning the account must be (re-)provisioned every single start, not
#    just once. Runs BEFORE cupsd starts below so a fresh cupsd process
#    reads a consistent /etc/shadow from its very first startup.
if [ -f /tmp/provision-admin.sh ]; then
    sh /tmp/provision-admin.sh || log "admin account provisioning reported an issue (see above)"
fi

# 6. Start cupsd (only reached once the avahi guard above has returned) in the foreground, backgrounded here so this script can
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

# 7. Register printers against the now-live cupsd. A short settle window is
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

# 8. Fix up each registered printer's UUID for stability across restarts.
#    Root cause: /etc/cups/ is not persisted outside /data, so cupsd
#    starts every single boot with a completely empty printers.conf --
#    lpadmin -m (step 7 above) always creates each printer "fresh" from
#    cupsd's own point of view, including a brand-new RANDOM printer-uuid
#    every restart. iOS/AirPrint caches discovered printers keyed by
#    UUID, so enough restarts leave multiple "ghost" duplicate entries in
#    iOS's print sheet for the same printer name. printers.conf must
#    never be edited while cupsd is running (the file's own generated
#    header says so verbatim; see apple/cups#2590 for the
#    corruption/crash risk), so this stops the already-running cupsd
#    first (same kill -TERM/wait mechanism as this script's own shutdown
#    trap below), runs the generated fixup script (present only when at
#    least one printer was actually registered -- mirrors the
#    /tmp/register-printers.sh / /tmp/provision-admin.sh presence-check
#    pattern above), and starts a fresh cupsd. Printer registration and
#    preset injection are NOT re-run here: printers.conf/PPDs are
#    otherwise untouched by this cycle, only the UUID line changes. See
#    cups/DOCS.md's Design notes for the accepted boot-time cost of this
#    extra start/stop/readiness-wait cycle.
if [ -f /tmp/fixup-printer-uuids.sh ]; then
    log "stopping cupsd to patch printer UUIDs (printers.conf must never be edited while cupsd is running)..."
    kill -TERM "$CUPSD_PID" 2>/dev/null
    wait "$CUPSD_PID"

    sh /tmp/fixup-printer-uuids.sh || log "printer UUID fixup reported an issue (see above)"

    log "restarting cupsd..."
    cupsd -f &
    CUPSD_PID=$!

    log "waiting for cupsd to accept connections (post-fixup restart)..."
    CUPSD_READY=0
    for _ in $(seq 1 30); do
        if lpstat -r >/dev/null 2>&1; then
            CUPSD_READY=1
            break
        fi
        sleep 1
    done
    if [ "$CUPSD_READY" = "1" ]; then
        log "cupsd is ready (post-fixup restart)"
    else
        log "cupsd did not become ready within 30s after the UUID-fixup restart"
    fi
fi

# 9. Map HA log_level option to a cupsctl LogLevel value. Sourced from the
#    file generate_config.py already rendered at step 1 (LOG_LEVEL +
#    CUPS_LOG_LEVEL) instead of calling `bashio::config 'log_level'`
#    directly here -- that call requires a live round-trip to the
#    Supervisor API with no local-file fallback, an unnecessary fragility
#    for a value already resolved once at step 1 exactly like every other
#    option in this add-on (see generate_config.py's build_log_level_env).
# shellcheck source=/dev/null
. /tmp/cups-log-level.env
# Same transient "Unable to connect to server: Bad file descriptor" race as
# step 7's lpadmin retry loop above -- cupsd's admin interface can still
# briefly reject the very first connection right after the post-fixup
# restart's own readiness poll (step 8) succeeds. cupsctl has no side effect
# on failure (it just leaves LogLevel at its previous value), so retrying is
# safe.
CUPSCTL_OK=0
for _ in $(seq 1 5); do
    if cupsctl LogLevel="$CUPS_LOG_LEVEL"; then
        CUPSCTL_OK=1
        break
    fi
    sleep 1
done
[ "$CUPSCTL_OK" = "1" ] || log "cupsctl LogLevel failed after retries (see above)"

# 10. Tail cupsd's own file-based logs into this add-on's own stdout so
#     `ha apps logs`/`docker logs` actually surface cupsd's logging --
#     today nothing does this: cupsd's error_log/access_log under
#     /var/log/cups/ are invisible outside the container. error_log is
#     always tailed; access_log is ADDITIONALLY tailed only at the most
#     verbose 'debug' tier (the level used for live diagnosis sessions).
#     `-F` retries across a missing/not-yet-created or rotated file
#     rather than exiting.
tail -n +1 -F /var/log/cups/error_log 2>/dev/null &
ERROR_LOG_TAIL_PID=$!
ACCESS_LOG_TAIL_PID=""
if [ "$LOG_LEVEL" = "debug" ]; then
    tail -n +1 -F /var/log/cups/access_log 2>/dev/null &
    ACCESS_LOG_TAIL_PID=$!
fi

# 11. Background: poll cupsd for newly-completed print jobs and persist a
#     simple JSONL history to /data/print-history.jsonl (see
#     print-history-poller.py's own module docstring for the documented
#     lpstat-text-output limitations). Started here rather than gated on
#     this script's own readiness poll -- the poller does its own
#     retry/backoff if cupsd is not yet reachable.
python3 /print-history-poller.py &
PRINT_HISTORY_POLLER_PID=$!

# 11b. Background: the optional paperless-ngx upload worker (paperless_upload
#      option block, disabled by default -- D-07). Started unconditionally,
#      same as step 11 above, rather than gated on a generated marker file
#      here -- the worker does its own gating on paperless_upload.enabled by
#      reading /data/options.json directly (mirrors this add-on's existing
#      convention of every background process reading its own config), so it
#      logs one INFO line and exits immediately when the feature is off.
#      Decoupled from cupsd's own lifecycle exactly like step 11's poller: a
#      hung/unreachable paperless-ngx can only stall this worker's own loop,
#      never cupsd or the physical printer queue (D-13).
python3 /upload-worker.py &
UPLOAD_WORKER_PID=$!

# 12. Forward termination signals to cupsd and wait on it -- the container
#     stays alive exactly as long as cupsd does. Per D-08: no watchdog for
#     the legacy-unicast reflector slot-exhaustion error is added here --
#     with enable-reflector=no (the shipped default) that failure class
#     cannot occur. Also stops the log-tail, print-history-poller, and
#     upload-worker background processes so container shutdown stays clean.
cleanup() {
    kill -TERM "$CUPSD_PID" 2>/dev/null
    kill -TERM "$ERROR_LOG_TAIL_PID" 2>/dev/null
    if [ -n "$ACCESS_LOG_TAIL_PID" ]; then
        kill -TERM "$ACCESS_LOG_TAIL_PID" 2>/dev/null
    fi
    kill -TERM "$PRINT_HISTORY_POLLER_PID" 2>/dev/null
    kill -TERM "$UPLOAD_WORKER_PID" 2>/dev/null
    # Stop avahi last so its goodbye packets still go out on shutdown.
    if [ -n "${AVAHI_PID:-}" ]; then
        avahi_guard_stop
    fi
}
trap cleanup TERM INT
wait "$CUPSD_PID"
