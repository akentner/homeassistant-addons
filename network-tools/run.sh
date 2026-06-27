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
    # Keep a persistent connection so the broker fires the will on crash
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
trap cleanup EXIT INT TERM

python3 /usr/local/bin/arping_scan.py

while true; do
    sleep "$INTERVAL"
    python3 /usr/local/bin/arping_scan.py
done
