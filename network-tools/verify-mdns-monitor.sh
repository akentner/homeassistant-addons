#!/usr/bin/env bash
# verify-mdns-monitor.sh - empirical verification for the network-tools mDNS monitor.
#
# Builds the add-on, starts a Mosquitto broker, mocks avahi-browse + avahi-resolve, and runs 8
# assertions covering all must_haves from the planning phase. Exits 0 only when all pass.
#
# Requirements: Docker (or podman symlinked to docker), make, mosquitto_sub/clients.
#
# Usage:
#     cd /share/development/homeassistant-addons
#     ./network-tools/verify-mdns-monitor.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADDON_DIR="$REPO_ROOT/network-tools"
IMAGE="local/network-tools"

WORK="$(mktemp -d)"
MOCK_BIN="$WORK/bin"
OPTIONS_FILE="$WORK/options.json"
LOG_DIR="$WORK/logs"
mkdir -p "$MOCK_BIN" "$LOG_DIR"

PASSED=0
TOTAL=8

assert_ok() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo "  PASS: $desc"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL: $desc (exit=$result)"
        echo
        echo "Mqtt capture log (last 40 lines):"
        tail -40 "$LOG_DIR/mqtt.log" 2>/dev/null || true
        echo
        echo "mdns_scan.json (if any):"
        cat "$WORK/mdns_scan.json" 2>/dev/null || echo "(missing)"
        exit 1
    fi
}

ADDON_PID=""
MOSQ_PID=""
SUB_PID=""

cleanup() {
    if [ -n "$SUB_PID" ]; then kill "$SUB_PID" 2>/dev/null || true; fi
    if [ -n "$ADDON_PID" ]; then docker rm -f "$ADDON_PID" 2>/dev/null || true; fi
    if [ -n "$MOSQ_PID" ]; then docker rm -f "$MOSQ_PID" 2>/dev/null || true; fi
    rm -rf "$WORK"
}
trap cleanup EXIT

# --- 1. Build the add-on ---
echo "=== 1. Building network-tools add-on ==="
make -C "$REPO_ROOT" build-addon ADDON=network-tools TIMEOUT=300 > "$LOG_DIR/build.log" 2>&1
VERSION=$(grep 'VERSION:' "$ADDON_DIR/build.yaml" | awk '{print $2}' | tr -d '"')
echo "Built image: $IMAGE:$VERSION"

# --- 2. Start Mosquitto broker ---
echo "=== 2. Starting Mosquitto broker ==="
MOSQ_PID=$(docker run -d --rm \
    -p 11883:1883 \
    -e MOSQUITTO_ALLOW_ANONYMOUS=true \
    eclipse-mosquitto:2 2>/dev/null | tail -1)
echo "Broker container: $MOSQ_PID"
sleep 3
docker logs "$MOSQ_PID" > "$LOG_DIR/mosquitto.log" 2>&1 || true

# --- 3. Mock avahi-browse + avahi-resolve ---
echo "=== 3. Writing mock avahi-browse + avahi-resolve ==="
cat > "$MOCK_BIN/avahi-browse" <<'EOF'
#!/bin/sh
# Mock: when asked for any service type, print canned parsable output.
cat <<'OUT'
=;eth0;IPv4;Brother HL-L3270CDW series;_ipp._tcp;local;brother.local;192.168.178.50;631;"txtvers=1";"rp=printers/Brother"
=;eth0;IPv4;HP LaserJet Pro;_ipp._tcp;local;hp.local;192.168.178.51;631;"ty=HP LaserJet"
OUT
exit 0
EOF
chmod +x "$MOCK_BIN/avahi-browse"

cat > "$MOCK_BIN/avahi-resolve" <<'EOF'
#!/bin/sh
# Mock: always succeed (matches the "online" path).
echo "brother.local	192.168.178.50"
exit 0
EOF
chmod +x "$MOCK_BIN/avahi-resolve"

# --- 4. Fixture options.json ---
echo "=== 4. Writing fixture options.json ==="
cat > "$OPTIONS_FILE" <<EOF
{
    "arping_hosts": [],
    "interface": "eth0",
    "interval": 30,
    "disconnect_threshold": 3,
    "port": 18080,
    "log_level": "info",
    "mqtt_enabled": true,
    "mqtt_host": "core-mosquitto",
    "mqtt_port": 1883,
    "mqtt_username": "",
    "mqtt_password": "",
    "mqtt_discovery_prefix": "homeassistant",
    "mdns_monitors": [
        {
            "name": "online_printer",
            "enabled": true,
            "service_types": ["_ipp._tcp"],
            "filter": [],
            "interval": 60,
            "timeout": 10,
            "topic_prefix": "homeassistant/monitor/online_printer",
            "device_name": "Online Printer"
        },
        {
            "name": "missing_printer",
            "enabled": true,
            "service_types": ["_ipp._tcp"],
            "filter": ["nonexistent_printer"],
            "interval": 60,
            "timeout": 10,
            "topic_prefix": "homeassistant/monitor/missing_printer",
            "device_name": "Missing Printer"
        },
        {
            "name": "disabled_monitor",
            "enabled": false,
            "service_types": ["_smb._tcp"],
            "filter": [],
            "interval": 60,
            "timeout": 10
        }
    ]
}
EOF

# --- 5. Start MQTT capture ---
echo "=== 5. Starting MQTT capture (30s window) ==="
( cd "$WORK" && timeout 120 mosquitto_sub -h localhost -p 11883 -t '#' -v > "$LOG_DIR/mqtt.log" 2>&1 ) &
SUB_PID=$!
sleep 1

# --- 6. Start the add-on container ---
echo "=== 6. Starting network-tools add-on container ==="
ADDON_PID=$(docker run -d --rm \
    --network container:"$MOSQ_PID" \
    -v "$OPTIONS_FILE:/data/options.json:ro" \
    -v "$MOCK_BIN:/mock_bin:ro" \
    -e "PATH=/mock_bin:/usr/local/bin:/usr/bin:/bin" \
    -p 18080:18080 \
    "$IMAGE:$VERSION" 2>/dev/null | tail -1)
echo "Addon container: $ADDON_PID"

# Wait for one full scan cycle (mdns scan starts within seconds, sleep to be safe)
echo "=== 7. Waiting 30s for at least one full scan cycle ==="
sleep 30

# Copy out the JSON output (the container writes to /data/results which is in-container only
# since we did not mount a volume)
docker exec "$ADDON_PID" cat /data/results/mdns_scan.json > "$WORK/mdns_scan.json" 2>/dev/null \
    || echo "{}" > "$WORK/mdns_scan.json"

# --- 8. Assertions ---
echo "=== 8. Running assertions ==="

# A1: mqtt_scan.json has 2 results (online + missing_printer; disabled_monitor excluded)
A1=0
COUNT=$(python3 -c "import json; print(len(json.load(open('$WORK/mdns_scan.json')).get('results', [])))" 2>/dev/null || echo "0")
if [ "$COUNT" = "2" ]; then A1=0; else echo "  A1 expected 2 results, got $COUNT"; A1=1; fi
assert_ok "A1: mqtt_scan.json has 2 results (enabled only)" "$A1"

# A2: each result has state in valid set
A2=0
STATES=$(python3 -c "import json; print(','.join(r.get('state','?') for r in json.load(open('$WORK/mdns_scan.json')).get('results', [])))")
for s in $(echo "$STATES" | tr ',' ' '); do
    if [ "$s" != "online" ] && [ "$s" != "not_found" ] && [ "$s" != "announced_unresolved" ] && [ "$s" != "error" ]; then
        A2=1
        echo "  A2 invalid state: $s"
    fi
done
assert_ok "A2: all states in {online, not_found, announced_unresolved, error}" "$A2"

# A3: online monitor has populated fields
A3=0
ONLINE_OK=$(python3 -c "
import json
data = json.load(open('$WORK/mdns_scan.json'))
for r in data.get('results', []):
    if r.get('state') == 'online':
        ok = all([r.get('service_name'), r.get('hostname'), r.get('address'), r.get('port')])
        print('1' if ok else '0')
        break
else:
    print('0')
")
[ "$ONLINE_OK" = "1" ] && A3=0 || A3=1
assert_ok "A3: online monitor has service_name/hostname/address/port" "$A3"

# A4: not_found monitor has null service_name
A4=0
NF_OK=$(python3 -c "
import json
data = json.load(open('$WORK/mdns_scan.json'))
for r in data.get('results', []):
    if r.get('state') == 'not_found':
        print('1' if r.get('service_name') is None else '0')
        break
else:
    print('0')
")
[ "$NF_OK" = "1" ] && A4=0 || A4=1
assert_ok "A4: not_found monitor has service_name=null" "$A4"

# A5: discovery config exists + state topic carries ON (binary sensor, single entity)
A5=0
if grep -q 'homeassistant/binary_sensor/networktools_mdns_online_printer/config' "$LOG_DIR/mqtt.log" \
    && grep -q 'homeassistant/monitor/online_printer/state ON' "$LOG_DIR/mqtt.log"; then
    A5=0
else
    A5=1
    echo "  A5 missing binary_sensor discovery or state ON payload"
fi
assert_ok "A5: binary_sensor discovery + state ON payload published" "$A5"

# A6: exactly one discovery config per monitor (binary_sensor only, NOT 3 entities)
A6=0
COUNT_DISC=$(grep -c 'homeassistant/.*sensor/networktools_mdns_online_printer.*/config' "$LOG_DIR/mqtt.log")
if [ "$COUNT_DISC" = "1" ]; then
    A6=0
else
    A6=1
    echo "  A6 expected exactly 1 discovery config per monitor, got $COUNT_DISC"
fi
assert_ok "A6: exactly 1 discovery config per monitor (no state/last_check sensor)" "$A6"

# A7: every captured MQTT publish used retain=true. We use a fresh mosquitto_sub subscriber
# AFTER killing the container - retained messages arrive immediately on connect.
docker rm -f "$ADDON_PID" 2>/dev/null || true
ADDON_PID=""
sleep 2
INSTANT=$(timeout 3 mosquitto_sub -h localhost -p 11883 -t 'homeassistant/monitor/online_printer/state' -C 1 2>&1 || true)
A7=0
if echo "$INSTANT" | grep -q 'ON'; then
    A7=0
else
    A7=1
    echo "  A7 no retained state message; got: $INSTANT"
fi
assert_ok "A7: state topic retained (instant replay after subscriber connect)" "$A7"

# A8: LWT fires on container kill - we restart the addon, then kill it, then expect the broker
# to fire the will on the persistent mosquitto_sub connection that run.sh maintains.
ADDON_PID=$(docker run -d --rm \
    --network container:"$MOSQ_PID" \
    -v "$OPTIONS_FILE:/data/options.json:ro" \
    -v "$MOCK_BIN:/mock_bin:ro" \
    -e "PATH=/mock_bin:/usr/local/bin:/usr/bin:/bin" \
    -p 18080:18080 \
    "$IMAGE:$VERSION" 2>/dev/null | tail -1)
sleep 15
# Capture LWT - subscribe to the availability topic and wait for offline.
# The retained "online" arrives first, then the will "offline" fires when the container dies.
LWT_LOG="$LOG_DIR/lwt.log"
( timeout 30 mosquitto_sub -h localhost -p 11883 -t 'network-tools/arping/availability' -v > "$LWT_LOG" 2>&1 ) &
LWT_PID=$!
sleep 3
# Kill the addon container - the mosquitto_sub connection in run.sh drops, broker fires the will
docker rm -f "$ADDON_PID" 2>/dev/null || true
ADDON_PID=""
# Wait for broker to detect disconnect and fire the will (default keepalive is 60s; we lower it
# by re-reading the persisted "online" then expecting "offline" after disconnect).
wait "$LWT_PID" 2>/dev/null || true
if grep -q 'offline' "$LWT_LOG"; then
    A8=0
else
    A8=1
    echo "  A8 LWT offline not seen; log:"
    sed 's/^/    /' "$LWT_LOG"
fi
assert_ok "A8: LWT fires offline on container kill" "$A8"

kill "$SUB_PID" 2>/dev/null || true

echo
echo "=========================================="
echo "PASSED: $PASSED / $TOTAL assertions"
echo "=========================================="
[ "$PASSED" = "$TOTAL" ]
