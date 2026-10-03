# shellcheck shell=bash
#
# avahi-guard.sh -- sourced library used by run.sh step 4 (never executed
# directly, hence no shebang and no top-level side effects).
#
# Why avahi runs in the foreground of a backgrounded job: this add-on's
# /dev/log is a dead symlink (no syslog daemon), so the previous
# `avahi-daemon --daemonize` start sent every avahi message -- including
# `Host name conflict, retrying with cups-2` -- to a sink nobody reads. Run
# undaemonized, avahi logs to stderr, which is the add-on log (`ha apps logs`).
#
# Why cupsd must wait for a settled claim: cupsd registers its DNS-SD
# records (the `_ipp._tcp` instance and its SRV target) under the host name avahi
# reports at that moment. When avahi later abandons that name after a
# conflict, the published service points at a host that no longer exists and the
# printer stops resolving from LAN clients (21-VERIFICATION truth #14). So
# run.sh starts cupsd only after avahi reported state "running" with an unchanged
# host name for AVAHI_GUARD_HOLD consecutive polls.
#
# Retry policy: a lost claim (running under another host name) stops avahi and
# starts it again, 3 attempts in total with a 30 s then 90 s backoff
# (AVAHI_GUARD_BACKOFFS). The cumulative wait before the last attempt reaches
# 120 s plus settle time, which outlasts the 120 s default TTL of mDNS host
# records, in case a peer or proxy still holds the previous instance's records.
# After the last attempt the guard logs a final ERROR and CONTINUES under the
# actual name, leaving avahi running: a stopped print server is worse than a
# renamed one, and a non-zero exit would only make the Supervisor watchdog
# restart-loop the add-on. The guard therefore never blocks forever and
# always returns 0.
#
# Scope: startup only. No watchdog or log monitor is added (D-08) and no
# add-on option exists for any of this (D-05); the AVAHI_GUARD_* environment
# variables below are tunables for tests, not configuration.
#
# Inputs (env): AVAHI_GUARD_ENV_PATH (default /tmp/avahi-guard.env, written by
# generate_config.py), AVAHI_GUARD_POLL, AVAHI_GUARD_SETTLE_TIMEOUT,
# AVAHI_GUARD_HOLD, AVAHI_GUARD_BACKOFFS.
# Outputs: AVAHI_PID (the running avahi-daemon job), AVAHI_GUARD_RESULT
# (claimed | degraded | unsettled) and a final `[avahi-guard] RESULT:` log line.

# Print "[avahi-guard] LEVEL: MESSAGE" to stderr (the add-on log).
_ag_log() {
    local level="$1"
    shift
    echo "[avahi-guard] ${level}: $*" >&2
}

# Source the validated expected host name written by generate_config.py.
avahi_guard_load_env() {
    local env_path="${AVAHI_GUARD_ENV_PATH:-/tmp/avahi-guard.env}"
    AVAHI_EXPECTED_HOSTNAME=""
    AVAHI_EXPECTED_FQDN=""
    if [ -f "$env_path" ]; then
        # shellcheck source=/dev/null
        . "$env_path"
    fi
    [ -n "${AVAHI_EXPECTED_FQDN:-}" ]
}

# Print "<state>|<fqdn>" from the avahi D-Bus API, or "down|" when the bus call
# fails. State 2 is AVAHI_SERVER_RUNNING.
avahi_guard_query() {
    local state_out fqdn_out state fqdn
    state_out=$(dbus-send --system --print-reply --dest=org.freedesktop.Avahi \
        / org.freedesktop.Avahi.Server.GetState 2>/dev/null) || {
        echo "down|"
        return 0
    }
    fqdn_out=$(dbus-send --system --print-reply --dest=org.freedesktop.Avahi \
        / org.freedesktop.Avahi.Server.GetHostNameFqdn 2>/dev/null) || {
        echo "down|"
        return 0
    }
    state=$(printf '%s\n' "$state_out" | sed -n 's/^[[:space:]]*int32[[:space:]]\{1,\}\([0-9]\{1,\}\).*/\1/p' | head -n 1)
    fqdn=$(printf '%s\n' "$fqdn_out" | sed -n 's/^[[:space:]]*string[[:space:]]\{1,\}"\(.*\)".*/\1/p' | head -n 1)
    if [ -z "$state" ]; then
        echo "down|"
        return 0
    fi
    echo "${state}|${fqdn}"
}

# Start avahi-daemon undaemonized as a background job; stderr is inherited.
avahi_guard_launch() {
    avahi-daemon &
    AVAHI_PID=$!
}

# Stop the avahi job: TERM, wait up to 10 s, KILL as the last resort, then give
# the goodbye packets a second to leave before any restart.
avahi_guard_stop() {
    local waited=0
    if [ -z "${AVAHI_PID:-}" ]; then
        return 0
    fi
    kill -TERM "$AVAHI_PID" 2>/dev/null
    while kill -0 "$AVAHI_PID" 2>/dev/null && [ "$waited" -lt 10 ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if kill -0 "$AVAHI_PID" 2>/dev/null; then
        kill -KILL "$AVAHI_PID" 2>/dev/null
    fi
    wait "$AVAHI_PID" 2>/dev/null
    AVAHI_PID=""
    sleep 1
}

# Poll until avahi is running under one unchanged host name for
# AVAHI_GUARD_HOLD consecutive polls. Prints the settled fqdn on stdout.
# Returns 0 settled, 1 timed out, 2 the avahi process exited.
avahi_guard_wait_settled() {
    local poll="${AVAHI_GUARD_POLL:-1}"
    local timeout="${AVAHI_GUARD_SETTLE_TIMEOUT:-30}"
    local hold="${AVAHI_GUARD_HOLD:-5}"
    local max_polls=$((timeout / poll))
    local i=0 streak=0 last="" result state fqdn

    [ "$max_polls" -lt 1 ] && max_polls=1
    while [ "$i" -lt "$max_polls" ]; do
        if [ -n "${AVAHI_PID:-}" ] && ! kill -0 "$AVAHI_PID" 2>/dev/null; then
            return 2
        fi
        result=$(avahi_guard_query)
        state="${result%%|*}"
        fqdn="${result#*|}"
        if [ "$state" = "2" ] && [ -n "$fqdn" ]; then
            if [ "$fqdn" = "$last" ]; then
                streak=$((streak + 1))
            else
                last="$fqdn"
                streak=1
            fi
            if [ "$streak" -ge "$hold" ]; then
                echo "$fqdn"
                return 0
            fi
        else
            last=""
            streak=0
        fi
        sleep "$poll"
        i=$((i + 1))
    done
    return 1
}

# Run the startup guard. Always returns 0 and always leaves avahi running.
avahi_guard_start() {
    local -a backoffs
    local attempts attempt=1 actual rc backoff
    local expected_fqdn timeout="${AVAHI_GUARD_SETTLE_TIMEOUT:-30}"

    AVAHI_GUARD_RESULT=""
    if ! avahi_guard_load_env; then
        _ag_log ERROR "no expected host name available (${AVAHI_GUARD_ENV_PATH:-/tmp/avahi-guard.env} missing or empty) -- starting avahi-daemon unguarded"
        avahi_guard_launch
        AVAHI_GUARD_RESULT="unsettled"
        echo "[avahi-guard] RESULT: ${AVAHI_GUARD_RESULT}" >&2
        return 0
    fi
    expected_fqdn="$AVAHI_EXPECTED_FQDN"

    read -r -a backoffs <<<"${AVAHI_GUARD_BACKOFFS-30 90}"
    attempts=$((1 + ${#backoffs[@]}))

    while :; do
        _ag_log INFO "attempt ${attempt}/${attempts}: starting avahi-daemon (expecting ${expected_fqdn})"
        avahi_guard_launch

        actual=$(avahi_guard_wait_settled)
        rc=$?
        if [ "$rc" -eq 0 ]; then
            if [ "$actual" = "$expected_fqdn" ]; then
                _ag_log INFO "hostname claimed: ${expected_fqdn} (attempt ${attempt}/${attempts})"
                AVAHI_GUARD_RESULT="claimed"
                break
            fi
            _ag_log ERROR "hostname lost: expected ${expected_fqdn} but avahi is running as ${actual} (attempt ${attempt}/${attempts})"
        else
            actual=""
            _ag_log ERROR "avahi did not reach the running state within ${timeout}s (attempt ${attempt}/${attempts})"
        fi

        if [ "$attempt" -lt "$attempts" ]; then
            backoff="${backoffs[$((attempt - 1))]}"
            _ag_log WARNING "retrying in ${backoff}s after stopping avahi (peers may still cache the previous records)"
            avahi_guard_stop
            sleep "$backoff"
            attempt=$((attempt + 1))
            continue
        fi

        _ag_log ERROR "giving up after ${attempts} attempts -- continuing as ${actual:-unknown}; the mDNS name differs from avahi_hostname=${AVAHI_EXPECTED_HOSTNAME}. Look for another responder claiming ${expected_fqdn} on the LAN (see DOCS.md, Avahi startup guard)"
        if [ -n "$actual" ]; then
            AVAHI_GUARD_RESULT="degraded"
        else
            AVAHI_GUARD_RESULT="unsettled"
        fi
        break
    done

    echo "[avahi-guard] RESULT: ${AVAHI_GUARD_RESULT}" >&2
    return 0
}
