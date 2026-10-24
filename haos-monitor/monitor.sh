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

# Samples, probes and kernel error lines are mirrored into a small state file (read by status.sh), so a kernel log
# flood in the main log cannot push them out of the tail window. Trimmed to its last 3000 lines when it exceeds 1 MB.
STATE_MAX_BYTES=1048576
_n=0
trim_state() {
  [ "$(wc -c < "$LOG.state")" -gt "$STATE_MAX_BYTES" ] || return 0
  tail -n 3000 "$LOG.state" > "$LOG.state.tmp" && mv "$LOG.state.tmp" "$LOG.state"
}

log() {
  ts=$(now)
  printf '%s %s\n' "$ts" "$*" >> "$LOG"
  case $* in
    SAMPLE*|DISK*|DSTATE*|PROBE*|BOOT*|KERR*)
      printf '%s %s\n' "$ts" "$*" >> "$LOG.state"
      _n=$((_n + 1))
      [ $((_n % 200)) -ne 0 ] || trim_state ;;
  esac
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
# when the data disk stalls. Reports D-state tasks with their wchan; for real
# (non-pipe) waits it also dumps the kernel stack from /proc/<pid>/stack.
# shellcheck disable=SC2016
REMOTE='
trap "kill 0" EXIT HUP
# Kernel log: every line as KMSG; level <= err or known failure texts additionally as KERR
kmsg_filter() {
  while IFS= read -r l; do
    printf "KMSG %s\n" "$l"
    p=${l%%,*}
    case $p in ""|*[!0-9]*) p=6 ;; esac
    if [ $((p & 7)) -le 3 ]; then printf "KERR %s\n" "$l"; continue; fi
    case $l in
      *"I/O error"*|*blk_update_request*|*"Buffer I/O"*|*"EXT4-fs error"*|*"EXT4-fs warning"*|\
      *"Out of memory"*|*oom-kill*|*"blocked for more than"*|*"soft lockup"*|*"self-detected stall"*|\
      *"reset"*"USB device"*|*uas*abort*|*xhci*died*|*"timed out"*|*"hung task"*)
        printf "KERR %s\n" "$l" ;;
    esac
  done
}
read -r up _ < /proc/uptime
echo "BOOT up=$up"
( cat /dev/kmsg | kmsg_filter ) &
n=0
dnow=""
while :; do
  n=$((n + 1))
  seen=$dnow
  dnow=""
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
      case $w in
        anon_pipe_*|pipe_*) ;;
        *)
          dnow="$dnow $pid "
          # first sight, then once a minute while the task stays blocked
          case $seen in *" $pid "*) [ $((n % 6)) -eq 0 ] || continue ;; esac
          if [ -r "$d/stack" ]; then
            while IFS= read -r s; do echo "DSTACK $pid $comm $s"; done < "$d/stack"
          fi ;;
      esac
    fi
  done
  sleep '"$INTERVAL"'
done
'

# Incident markers: problem 0->1, reasons change and 1->0 become greppable log lines
incidents() {
  prev=0 reasons_prev="" since=0
  while :; do
    sleep "$INTERVAL"
    s=$("${STATUS_SH:-/status.sh}" "$SLUG" 2>/dev/null) || continue
    cur=$(printf '%s' "$s" | jq -r '.problem' 2>/dev/null)
    case $cur in 0|1) ;; *) continue ;; esac
    reasons=$(printf '%s' "$s" | jq -r '.reasons')
    if [ "$cur" = 1 ] && [ "$prev" = 0 ]; then
      since=$(date +%s)
      log "INCIDENT start $(printf '%s' "$s" | jq -r '"reasons=\(.reasons) age=\(.age) io_full10=\(.io_full10) sda_inflight=\(.sda_inflight) dstate=\(.dstate) kmsg_errors=\(.kmsg_errors) tasks=[\(.dstate_tasks)] kmsg=[\(.kmsg_last)]"')"
    elif [ "$cur" = 1 ] && [ "$reasons" != "$reasons_prev" ]; then
      log "INCIDENT change reasons=$reasons"
    elif [ "$cur" = 0 ] && [ "$prev" = 1 ]; then
      log "INCIDENT end duration=$(($(date +%s) - since))s"
    fi
    prev=$cur reasons_prev=$reasons
  done
}

probe &
[ -z "${SLUG:-}" ] || incidents &

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
