#!/bin/sh
# haos-monitor: stream kernel log + I/O stall indicators from the HA-backup
# host (HAOS host SSH) to a local log, and probe its ports from outside.
# POSIX sh (Alpine busybox ash). Remote side uses shell builtins only, so it
# keeps working while /mnt/data is stalled.
set -u

HOST="${TARGET_HOST:-192.168.178.9}"
PORT="${TARGET_PORT:-22222}"
LOGDIR="${LOGDIR:-/logs}"
LOG="${LOG_FILE:-$LOGDIR/haos-monitor.log}"
MAX_BYTES="${MAX_BYTES:-20971520}"
INTERVAL="${INTERVAL:-10}"
KEY="${KEY_FILE:-/dev/shm/monitor_key}"

mkdir -p "$LOGDIR"
umask 077
if [ -n "${SSH_KEY_B64:-}" ]; then
  printf '%s' "$SSH_KEY_B64" | base64 -d > "$KEY"
  chmod 600 "$KEY"
fi
[ -r "$KEY" ] || { echo "no usable key at $KEY" >&2; exit 1; }
umask 022

now() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

rotate() {
  [ -f "$LOG" ] || return 0
  size=$(wc -c < "$LOG")
  [ "$size" -gt "$MAX_BYTES" ] || return 0
  i=4
  while [ "$i" -ge 1 ]; do
    [ -f "$LOG.$i" ] && mv "$LOG.$i" "$LOG.$((i + 1))"
    i=$((i - 1))
  done
  mv "$LOG" "$LOG.1"
}

log() {
  printf '%s %s\n' "$(now)" "$*" >> "$LOG"
  rotate
}

# Outside view: independent of the SSH session, correlates with Gatus.
probe() {
  while :; do
    p=down
    ping -c1 -W1 "$HOST" > /dev/null 2>&1 && p=ok
    t=""
    for port in 22222 1883 8123 4357; do
      if nc -z -w2 "$HOST" "$port" > /dev/null 2>&1; then
        t="$t $port=open"
      else
        t="$t $port=closed"
      fi
    done
    log "PROBE ping=$p$t"
    sleep "$INTERVAL"
  done
}

# Runs on the host. Builtins only (no forks except sleep) so it still works
# when the data disk stalls. Reports D-state tasks with their wchan.
# shellcheck disable=SC2016
REMOTE='
trap "kill 0" EXIT HUP
( cat /dev/kmsg | while IFS= read -r l; do printf "KMSG %s\n" "$l"; done ) &
while :; do
  read -r up _ < /proc/uptime
  { read -r io_some; read -r io_full; } < /proc/pressure/io
  { read -r mem_some; read -r mem_full; } < /proc/pressure/memory
  read -r la < /proc/loadavg
  echo "SAMPLE up=$up load=\"$la\" io_some=\"$io_some\" io_full=\"$io_full\" mem_full=\"$mem_full\""
  while read -r _ _ name _ _ _ _ _ _ _ _ infl _; do
    case $name in sda|mmcblk1) echo "DISK $name inflight=$infl" ;; esac
  done < /proc/diskstats
  for d in /proc/[0-9]*; do
    { read -r pid comm state _ < "$d/stat"; } 2>/dev/null || continue
    if [ "$state" = D ]; then
      w=""
      read -r w < "$d/wchan" 2>/dev/null
      echo "DSTATE $pid $comm wchan=$w"
    fi
  done
  sleep '"$INTERVAL"'
done
'

probe &

log "START host=$HOST:$PORT interval=${INTERVAL}s"
while :; do
  log "CONNECT"
  ssh -T -i "$KEY" \
    -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none \
    -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=${KNOWN_HOSTS:-/tmp/known_hosts}" \
    -p "$PORT" "root@$HOST" "$REMOTE" 2>&1 |
    while IFS= read -r line; do log "$line"; done
  log "DISCONNECT"
  sleep 5
done
