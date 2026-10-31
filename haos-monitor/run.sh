#!/bin/sh
set -e

OPTS=/data/options.json
HOSTS=/etc/haos-monitor.hosts
ENVF=/etc/haos-monitor.env

INTERVAL=$(jq -r '.interval' "$OPTS")
cat > "$ENVF" <<EOT
INTERVAL=$INTERVAL
PROBLEM_AGE=$(jq -r '.problem_age' "$OPTS")
PROBLEM_IO_FULL10=$(jq -r '.problem_io_full10' "$OPTS")
PROBLEM_SDA_INFLIGHT=$(jq -r '.problem_sda_inflight' "$OPTS")
PROBLEM_DSTATE=$(jq -r '.problem_dstate' "$OPTS")
PROBLEM_KMSG=$(jq -r '.problem_kmsg' "$OPTS")
EOT

# Rebuild a PEM key from the options value: the UI may flatten newlines (spaces, CR, literal \n)
write_key() { # $1 = raw key, $2 = target file
  HDR=$(printf '%s' "$1" | grep -o -- '-----BEGIN [A-Z ]*-----' | head -1)
  FTR=$(printf '%s' "$1" | grep -o -- '-----END [A-Z ]*-----' | head -1)
  [ -n "$HDR" ] && [ -n "$FTR" ] || return 1
  BODY=$(printf '%s' "$1" | sed 's/-----BEGIN[^-]*-----//; s/-----END[^-]*-----//; s/\\n//g' | tr -d ' \r\n\t')
  umask 077
  { echo "$HDR"; printf '%s' "$BODY" | fold -w 70; echo; echo "$FTR"; } > "$2"
  umask 022
}

# Fingerprint of a written key file; never lets the key or its comment leave this function
key_fingerprint() { # $1 = key file; sets KEY_FP and KEY_TYPE
  KEY_FP=invalid
  KEY_TYPE=
  # -P '' and stdin from /dev/null: a passphrase-protected key fails fast instead of prompting
  KFL=$(ssh-keygen -y -P '' -f "$1" 2>/dev/null </dev/null | ssh-keygen -l -E sha256 -f - 2>/dev/null) || KFL=
  KFP=$(printf '%s' "$KFL" | awk '{print $2; exit}')
  if printf '%s' "$KFP" | grep -Eq '^SHA256:[A-Za-z0-9+/]+$'; then
    KEY_FP=$KFP
    KFT=$(printf '%s' "$KFL" | sed -n 's/.*(\([^()]*\))$/\1/p')
    if printf '%s' "$KFT" | grep -Eq '^[A-Za-z0-9_-]+$'; then KEY_TYPE=$KFT; fi
  fi
  return 0
}

export LOGDIR=/share/haos-monitor
mkdir -p "$LOGDIR"
: > "$HOSTS"
COUNT=$(jq -r '.hosts | length' "$OPTS")
i=0
while [ "$i" -lt "$COUNT" ]; do
  NAME=$(jq -r ".hosts[$i].name" "$OPTS")
  HOST=$(jq -r ".hosts[$i].host" "$OPTS")
  PORT=$(jq -r ".hosts[$i].port // 22222" "$OPTS")
  SLUG=$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '_')
  i=$((i + 1))

  if cut -f1 "$HOSTS" | grep -qx "$SLUG"; then
    echo "[run] host '$NAME': duplicate slug '$SLUG', skipped" >&2
    continue
  fi
  KEY_FILE=/dev/shm/monitor_key_$SLUG
  if ! write_key "$(jq -r ".hosts[$((i - 1))].ssh_private_key" "$OPTS")" "$KEY_FILE"; then
    echo "[run] host '$NAME': ssh_private_key missing or malformed, skipped" >&2
    continue
  fi
  key_fingerprint "$KEY_FILE"
  if [ "$KEY_FP" = invalid ]; then
    echo "[run] host '$NAME': ssh key invalid (ssh-keygen cannot read it: damaged, truncated or passphrase-protected)" >&2
  else
    echo "[run] host '$NAME': ssh key $KEY_TYPE $KEY_FP" >&2
  fi
  # Hosts file columns: slug, name, host, port, key fingerprint, key type
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$SLUG" "$NAME" "$HOST" "$PORT" "$KEY_FP" "$KEY_TYPE" >> "$HOSTS"

  # Supervised, isolated per-host monitor; a crash only restarts that host
  (
    export TARGET_HOST="$HOST" TARGET_PORT="$PORT" KEY_FILE INTERVAL SLUG
    export LOG_FILE="$LOGDIR/$SLUG.log" KNOWN_HOSTS="/tmp/known_hosts_$SLUG"
    while :; do /monitor.sh || true; sleep 5; done
  ) &

  (
    export MQTT_HOST MQTT_PORT MQTT_USER MQTT_PASSWORD MQTT_PREFIX MQTT_CLEAR INTERVAL
    MQTT_HOST=$(jq -r '.mqtt_host' "$OPTS")
    MQTT_PORT=$(jq -r '.mqtt_port' "$OPTS")
    MQTT_USER=$(jq -r '.mqtt_user' "$OPTS")
    MQTT_PASSWORD=$(jq -r '.mqtt_password' "$OPTS")
    MQTT_PREFIX=$(jq -r '.mqtt_discovery_prefix' "$OPTS")
    MQTT_CLEAR=$(jq -r '.mqtt_clear_discovery' "$OPTS")
    exec /mqtt.sh "$SLUG" "$NAME"
  ) &
done

[ -s "$HOSTS" ] || { echo "no usable host configured" >&2; exit 1; }

httpd -p 8099 -h /www -c /etc/httpd.conf
# Children are supervised individually; keep the container running regardless
while :; do sleep 3600; done
