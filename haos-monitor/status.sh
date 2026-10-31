#!/bin/sh
# shellcheck disable=SC2154
# Prints the status JSON of one host (arg 1: slug), derived statelessly from its monitor log.
# Shared by the HTTP endpoint (status.cgi), the metrics endpoint and the MQTT publisher (mqtt.sh).
SLUG=${1:?usage: status.sh <slug>}
LOG="${LOGDIR:-/share/haos-monitor}/$SLUG.log"
PROBLEM_AGE=60 PROBLEM_IO_FULL10=30 PROBLEM_SDA_INFLIGHT=8 PROBLEM_DSTATE=1 PROBLEM_KMSG=1
# Kernel error lines (KERR) count when they are at most this many seconds older than the host uptime
KMSG_WINDOW=600
# D-state tasks waiting on these wchans are not disk stalls (e.g. short-lived runc) and do not count
DSTATE_IGNORE='^(anon_pipe_read|anon_pipe_write|pipe_read|pipe_write|worker_thread)$'
# The ext4 journal thread waits for its commit I/O for a few seconds now and then; that alone is not a stall
# (a real one also shows io_full10, other blocked tasks or kernel errors)
# shellcheck disable=SC1090
[ -r "${ENV_FILE:-/etc/haos-monitor.env}" ] && . "${ENV_FILE:-/etc/haos-monitor.env}"
FILTER='^[^ ]+ (SAMPLE|DISK|DSTATE|PROBE|BOOT|KERR) '

# The state file holds only the lines above, so a kernel log flood cannot push the samples out of the tail window
if [ -r "$LOG.state" ]; then
  data=$(tail -n 3000 "$LOG.state" 2>/dev/null | grep -E "$FILTER")
else
  data=$(tail -n 3000 "$LOG" 2>/dev/null | grep -E "$FILTER")
  if ! printf '%s\n' "$data" | grep -q ' SAMPLE '; then
    old=$(tail -n 3000 "$LOG.1" 2>/dev/null | grep -E "$FILTER")
    data=$(printf '%s\n%s\n' "$old" "$data")
  fi
fi

vars=$(printf '%s\n' "$data" | awk -v ign="$DSTATE_IGNORE" -v kwin="$KMSG_WINDOW" '
function avg(s,   m) { if (match(s, /avg10=[0-9.]+/)) return substr(s, RSTART + 6, RLENGTH - 6); return -1 }
function val(s) { sub(/^[^=]*=/, "", s); return s }
function reboot_check(u,   k) {
  if (u ~ /^[0-9.]+$/) {
    if (prev_up != "" && u + 1 < prev_up) { for (k in kts) { delete kts[k]; delete kmsg[k] } }
    prev_up = u + 0
  }
}
{
  ts = $1; kind = $2
  if (kind == "SAMPLE") {
    sts = ts; dstate = 0; tasks = ""
    line = $0
    up = val($3); if (up !~ /^[0-9.]+$/) up = -1
    reboot_check(up)
    if (match(line, /load="[0-9.]+/)) load1 = substr(line, RSTART + 6, RLENGTH - 6)
    if (match(line, /io_some="[^"]*"/)) io_some = avg(substr(line, RSTART, RLENGTH))
    if (match(line, /io_full="[^"]*"/)) io_full = avg(substr(line, RSTART, RLENGTH))
    if (match(line, /mem_full="[^"]*"/)) mem_full = avg(substr(line, RSTART, RLENGTH))
  } else if (kind == "BOOT") {
    reboot_check(val($3))
  } else if (kind == "KERR") {
    line = $0; sub(/^[^ ]+ KERR /, "", line)
    split(line, a, ",")
    if (a[2] !~ /^[0-9]+$/ || a[3] !~ /^[0-9]+$/ || (a[2] in kts)) next
    kts[a[2]] = a[3] / 1000000
    kmsg[a[2]] = substr(line, index(line, ";") + 1)
  } else if (kind == "DISK") {
    v = val($4); if (v !~ /^[0-9]+$/) v = -1
    if ($3 == "sda") sda = v; else if ($3 == "mmcblk1") mmc = v
  } else if (kind == "DSTATE") {
    w = val($NF)
    c = ""
    for (i = 4; i < NF; i++) c = c (c == "" ? "" : " ") $i
    if (w !~ ign && !(c ~ /^\(jbd2\// && w == "__wait_on_buffer")) {
      dstate++
      t = $3 " " c ":" w
      gsub(/[^A-Za-z0-9 ():._\/-]/, "", t)
      tasks = tasks (tasks == "" ? "" : "; ") t
    }
  } else if (kind == "PROBE") {
    pts = ts
    ping = (val($3) == "ok") ? 1 : 0
    for (i = 4; i <= NF; i++) {
      split($i, kv, "=")
      o = (kv[2] == "open") ? 1 : 0
      if (kv[1] == "22222") p22222 = o; else if (kv[1] == "1883") p1883 = o
      else if (kv[1] == "8123") p8123 = o; else if (kv[1] == "4357") p4357 = o
    }
  }
}
END {
  cnt = 0; lastt = -1; last = ""
  for (k in kts) {
    d = up - kts[k]
    if (up >= 0 && d >= -1 && d <= kwin) {
      cnt++
      if (kts[k] > lastt) { lastt = kts[k]; last = kmsg[k] }
    }
  }
  gsub(/[^A-Za-z0-9 ():._\/=,-]/, "", last)
  last = substr(last, 1, 120)
  print "sts=" sts
  print "pts=" pts
  print "up=" (up == "" ? -1 : up)
  print "load1=" (load1 == "" ? -1 : load1)
  print "io_some10=" (io_some == "" ? -1 : io_some)
  print "io_full10=" (io_full == "" ? -1 : io_full)
  print "mem_full10=" (mem_full == "" ? -1 : mem_full)
  print "sda_inflight=" (sda == "" ? -1 : sda)
  print "mmc_inflight=" (mmc == "" ? -1 : mmc)
  print "dstate=" (sts == "" ? -1 : dstate + 0)
  print "dstate_tasks=\047" tasks "\047"
  print "kmsg_errors=" (sts == "" || up < 0 ? -1 : cnt)
  print "kmsg_last=\047" last "\047"
  print "ping=" (ping == "" ? -1 : ping)
  print "p22222=" (p22222 == "" ? -1 : p22222)
  print "p1883=" (p1883 == "" ? -1 : p1883)
  print "p8123=" (p8123 == "" ? -1 : p8123)
  print "p4357=" (p4357 == "" ? -1 : p4357)
}')
# awk only emits key=value with values matched against numeric/timestamp patterns above
eval "$vars" 2>/dev/null

now=$(date -u +%s)
age_of() {
  [ -n "$1" ] || { echo 999999; return; }
  t=$(date -u -d "$(printf '%s' "$1" | sed 's/T/ /; s/Z$//')" +%s 2>/dev/null) || { echo 999999; return; }
  echo $((now - t))
}
age=$(age_of "$sts")
probe_age=$(age_of "$pts")

# one flag per problem component; reasons lists the ones that fired
flags=$(awk -v age="$age" -v io="${io_full10:--1}" -v sda="${sda_inflight:--1}" -v ds="${dstate:--1}" -v km="${kmsg_errors:--1}" \
  -v pa="$PROBLEM_AGE" -v pio="$PROBLEM_IO_FULL10" -v ps="$PROBLEM_SDA_INFLIGHT" -v pd="$PROBLEM_DSTATE" -v pk="$PROBLEM_KMSG" \
  'BEGIN {
    a = (age >= pa); i = (io >= pio); s = (sda >= ps); d = (ds >= pd); k = (km >= pk)
    r = ""
    if (a) r = r ",stale"
    if (i) r = r ",io_full10"
    if (s) r = r ",sda_inflight"
    if (d) r = r ",dstate"
    if (k) r = r ",kmsg"
    print a, i, s, d, k, (a || i || s || d || k) ? 1 : 0, (r == "" ? "none" : substr(r, 2))
  }')
# shellcheck disable=SC2086
set -- $flags
r_age=$1 r_io=$2 r_sda=$3 r_dstate=$4 r_kmsg=$5 problem=$6 reasons=$7

# Public-key fingerprint and type of this host's key (hosts file columns 5 and 6, written by run.sh).
# The tr filter keeps only characters a fingerprint or type can contain, so the JSON strings stay safe.
key_fp=$(awk -F'\t' -v s="$SLUG" '$1 == s {print $5; exit}' "${HOSTS_FILE:-/etc/haos-monitor.hosts}" 2>/dev/null | tr -cd 'A-Za-z0-9+/:=_-')
key_type=$(awk -F'\t' -v s="$SLUG" '$1 == s {print $6; exit}' "${HOSTS_FILE:-/etc/haos-monitor.hosts}" 2>/dev/null | tr -cd 'A-Za-z0-9_-')

printf '{"age":%s,"up":%s,"load1":%s,"io_some10":%s,"io_full10":%s,"mem_full10":%s,' \
  "$age" "${up:--1}" "${load1:--1}" "${io_some10:--1}" "${io_full10:--1}" "${mem_full10:--1}"
printf '"sda_inflight":%s,"mmc_inflight":%s,"dstate":%s,"probe_age":%s,"ping":%s,"p22222":%s,"p1883":%s,"p8123":%s,"p4357":%s,"problem":%s,' \
  "${sda_inflight:--1}" "${mmc_inflight:--1}" "${dstate:--1}" "$probe_age" "${ping:--1}" \
  "${p22222:--1}" "${p1883:--1}" "${p8123:--1}" "${p4357:--1}" "$problem"
printf '"r_age":%s,"r_io":%s,"r_sda":%s,"r_dstate":%s,"r_kmsg":%s,"reasons":"%s","dstate_tasks":"%s","kmsg_errors":%s,"kmsg_last":"%s","key_fp":"%s","key_type":"%s"}\n' \
  "$r_age" "$r_io" "$r_sda" "$r_dstate" "$r_kmsg" "$reasons" "$dstate_tasks" "${kmsg_errors:--1}" "$kmsg_last" \
  "$key_fp" "$key_type"
