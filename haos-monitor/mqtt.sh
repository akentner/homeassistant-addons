#!/bin/sh
# MQTT discovery + state publisher for ONE host (args: slug name). Never exits; retries on broker errors.
# Env: MQTT_HOST MQTT_PORT MQTT_USER MQTT_PASSWORD MQTT_PREFIX MQTT_CLEAR INTERVAL
SLUG=$1
NAME=$2
BASE="haos-monitor/$SLUG"
STATE="$BASE/state"
AVAIL="$BASE/availability"
DEV="haos_monitor_$SLUG"
EXPIRE=$((INTERVAL * 3))

# Broker connection; the password is only ever passed as an argument, never echoed
mq() {
  if [ -n "$MQTT_USER" ]; then
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -u "$MQTT_USER" -P "$MQTT_PASSWORD" "$@"
  else
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" "$@"
  fi
}

# kind|field|name|unit|device_class|state_class|enabled
ENTITIES='sensor|age|Age|s|duration|measurement|true
sensor|io_full10|I/O full pressure|%||measurement|true
sensor|sda_inflight|sda in-flight I/O|||measurement|true
sensor|dstate|D-state tasks|||measurement|true
sensor|kmsg_errors|Kernel errors (10 min)|||measurement|true
sensor|load1|Load 1m|||measurement|true
sensor|up|Uptime|s|duration|measurement|true
sensor|io_some10|I/O some pressure|%||measurement|false
sensor|mem_full10|Memory full pressure|%||measurement|false
sensor|mmc_inflight|mmc in-flight I/O|||measurement|false
sensor|probe_age|Probe age|s|duration|measurement|false
binary_sensor|ping|Ping||connectivity||true
binary_sensor|p22222|SSH host||connectivity||true
binary_sensor|p1883|MQTT port||connectivity||true
binary_sensor|p8123|Home Assistant port||connectivity||true
binary_sensor|p4357|Observer port||connectivity||true
binary_sensor|problem|Problem||problem||true'

config_json() {
  jq -nc --arg attrs "$PROBLEM_ATTRS" --arg kind "$1" --arg f "$2" --arg n "$3" --arg u "$4" --arg dc "$5" --arg sc "$6" --arg en "$7" \
    --arg dev "$DEV" --arg devname "HAOS Monitor $NAME" --arg state "$STATE" --arg avail "$AVAIL" \
    --argjson exp "$EXPIRE" '
    {name: $n, unique_id: ($dev + "_" + $f), default_entity_id: ($kind + "." + $dev + "_" + $f),
     has_entity_name: true, state_topic: $state, value_template: ("{{ value_json." + $f + " }}"),
     availability_topic: $avail, expire_after: $exp, enabled_by_default: ($en == "true"),
     device: {identifiers: [$dev], name: $devname, manufacturer: "akentner", model: "haos-monitor"}}
    + (if $kind == "binary_sensor" then {payload_on: "1", payload_off: "0"} else {} end)
    + (if $f == "problem" then {json_attributes_topic: $state, json_attributes_template: $attrs} else {} end)
    + (if $u != "" then {unit_of_measurement: $u} else {} end)
    + (if $dc != "" then {device_class: $dc} else {} end)
    + (if $sc != "" then {state_class: $sc} else {} end)'
}

# Attributes of the problem sensor: which component fired, plus the values behind it
PROBLEM_ATTRS="{{ {'reasons': value_json.reasons, 'stale': value_json.r_age == 1, 'io_full': value_json.r_io == 1, 'sda_inflight_high': value_json.r_sda == 1, 'dstate_tasks_found': value_json.r_dstate == 1, 'kmsg_found': value_json.r_kmsg == 1, 'kmsg_errors': value_json.kmsg_errors, 'kmsg_last': value_json.kmsg_last, 'dstate_tasks': value_json.dstate_tasks, 'age': value_json.age, 'io_full10': value_json.io_full10, 'sda_inflight': value_json.sda_inflight, 'dstate': value_json.dstate} | tojson }}"

topic() { echo "$MQTT_PREFIX/$1/$DEV/$2/config"; }

publish_discovery() {
  printf '%s\n' "$ENTITIES" | while IFS='|' read -r kind field name unit dc sc en; do
    config_json "$kind" "$field" "$name" "$unit" "$dc" "$sc" "$en" |
      mq -q 1 -r -t "$(topic "$kind" "$field")" -s || exit 1
  done
}

clear_discovery() {
  printf '%s\n' "$ENTITIES" | while IFS='|' read -r kind field _; do
    mq -q 1 -r -n -t "$(topic "$kind" "$field")"
  done
  mq -q 1 -r -n -t "$AVAIL"
}

if [ "$MQTT_CLEAR" = true ]; then
  until clear_discovery; do sleep 10; done
  echo "[mqtt:$SLUG] retained discovery topics cleared; publisher idle (disable mqtt_clear_discovery to resume)" >&2
  while :; do sleep 3600; done
fi

while :; do
  if publish_discovery; then
    ( while :; do /status.sh "$SLUG" | tr -d '\n'; echo; sleep "$INTERVAL"; done ) |
      mq -q 1 -l -t "$STATE" --will-topic "$AVAIL" --will-payload offline --will-retain &
    spid=$!
    sleep 2
    mq -q 1 -r -t "$AVAIL" -m online
    wait "$spid"
    echo "[mqtt:$SLUG] state connection ended, retrying" >&2
  else
    echo "[mqtt:$SLUG] broker unreachable, retrying" >&2
  fi
  sleep 10
done
