#!/bin/sh
set -e

OPTIONS=/data/options.json
AVAIL_TOPIC="network-tools/arping/availability"

_opt() { python3 -c "import json; d=json.load(open('$OPTIONS')); print($1)" 2>/dev/null || echo "${2:-}"; }

INTERVAL=$(_opt "d.get('interval', 30)" 30)
PORT=$(_opt "d.get('port', 18080)" 18080)
MQTT_ENABLED=$(_opt "1 if d.get('mqtt_enabled') else ''" "")
MQTT_HOST=$(_opt "d.get('mqtt_host', 'core-mosquitto')" "core-mosquitto")
MQTT_PORT=$(_opt "d.get('mqtt_port', 1883)" 1883)
MQTT_USER=$(_opt "d.get('mqtt_username') or ''" "")
MQTT_PASS=$(_opt "d.get('mqtt_password') or ''" "")

mkdir -p /data/results /var/run/nginx /var/lib/nginx/tmp/client_body

sed "s/__PORT__/$PORT/" /etc/nginx/network-tools.conf > /tmp/nginx-network-tools.conf
nginx -c /tmp/nginx-network-tools.conf &

MQTT_WILL_PID=""

log() { echo "[run.sh] $*" >&2; }

mqtt_pub() {
    if [ -n "$MQTT_USER" ]; then
        mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" "$@"
    else
        mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" "$@"
    fi
}

mqtt_sub_will() {
    if [ -n "$MQTT_USER" ]; then
        mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" "$@"
    else
        mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" "$@"
    fi
}

if [ -n "$MQTT_ENABLED" ]; then
    # Keep a persistent connection so the broker fires the will on crash.
    # Single LWT subscription covers BOTH arp_loop and mdns_loop - both publish to AVAIL_TOPIC.
    mqtt_sub_will \
        --will-topic "$AVAIL_TOPIC" --will-payload "offline" --will-retain \
        -t "network-tools/arping/__keepalive" -q 1 &
    MQTT_WILL_PID=$!
    sleep 1
    mqtt_pub -t "$AVAIL_TOPIC" -m "online" -r
fi

cleanup() {
    if [ -n "$MQTT_ENABLED" ]; then
        mqtt_pub -t "$AVAIL_TOPIC" -m "offline" -r 2>/dev/null || true
    fi
    if [ -n "$MQTT_WILL_PID" ]; then kill "$MQTT_WILL_PID" 2>/dev/null || true; fi
}

# mdns global sleep = min(interval) over enabled monitors; default 60
MDNS_INTERVAL_GLOBAL=$(_opt "min((m.get('interval') or 60) for m in (d.get('mdns_monitors') or []) if m.get('enabled', True)) or 60" 60)

arp_loop() {
    while true; do
        python3 /usr/local/bin/arping_scan.py || log "arping_loop_failed (rc=$?)"
        sleep "$INTERVAL"
    done
}

mdns_loop() {
    while true; do
        python3 /usr/local/bin/mdns_scan.py || log "mdns_loop_failed (rc=$?)"
        sleep "$MDNS_INTERVAL_GLOBAL"
    done
}

arp_loop &
ARP_PID=$!

# mDNS discovery needs a running system D-Bus and an Avahi daemon - otherwise
# avahi-browse exits with "Failed to create client object: Daemon not running".
# Start them before mdns_loop. Failures are non-fatal: mdns_scan will log the
# error and the loop will retry on the next cycle.
mkdir -p /var/run/dbus /var/run/avahi-daemon
if [ -x /usr/bin/dbus-daemon ]; then
    dbus-daemon --system --fork 2>/dev/null || log "dbus-daemon failed to start"
fi
if [ -x /usr/sbin/avahi-daemon ]; then
    avahi-daemon --daemonize 2>/dev/null || log "avahi-daemon failed to start"
fi

if [ -f /usr/local/bin/mdns_scan.py ]; then
    mdns_loop &
    MDNS_PID=$!
else
    log "mdns_loop not started: /usr/local/bin/mdns_scan.py missing (mdns_monitors disabled)"
fi

trap 'kill "$ARP_PID" "$MDNS_PID" 2>/dev/null; cleanup' EXIT INT TERM

wait
