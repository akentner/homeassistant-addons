#!/bin/sh
# shellcheck disable=SC2154
# Prints the status JSON of one host (arg 1: slug), derived statelessly from its monitor log.
# Shared by the HTTP endpoint (status.cgi) and the MQTT publisher (mqtt.sh).
SLUG=${1:?usage: status.sh <slug>}
LOG="${LOGDIR:-/share/haos-monitor}/$SLUG.log"
PROBLEM_AGE=60 PROBLEM_IO_FULL10=30 PROBLEM_SDA_INFLIGHT=8 PROBLEM_DSTATE=1
# D-state tasks waiting on these wchans are not disk stalls (e.g. short-lived runc) and do not count
DSTATE_IGNORE='^(anon_pipe_read|anon_pipe_write|pipe_read|pipe_write)$'
# shellcheck disable=SC1090
[ -r "${ENV_FILE:-/etc/haos-monitor.env}" ] && . "${ENV_FILE:-/etc/haos-monitor.env}"
FILTER='^[^ ]+ (SAMPLE|DISK|DSTATE|PROBE) '

data=$(tail -n 3000 "$LOG" 2>/dev/null | grep -E "$FILTER")
if ! printf '%s\n' "$data" | grep -q ' SAMPLE '; then
  old=$(tail -n 3000 "$LOG.1" 2>/dev/null | grep -E "$FILTER")
  data=$(printf '%s\n%s\n' "$old" "$data")
fi

vars=$(printf '%s\n' "$data" | awk -v ign="$DSTATE_IGNORE" '
function avg(s,   m) { if (match(s, /avg10=[0-9.]+/)) return substr(s, RSTART + 6, RLENGTH - 6); return -1 }
function val(s) { sub(/^[^=]*=/, "", s); return s }
{
  ts = $1; kind = $2
  if (kind == "SAMPLE") {
    sts = ts; dstate = 0; tasks = ""
    line = $0
    up = val($3); if (up !~ /^[0-9.]+$/) up = -1
    if (match(line, /load="[0-9.]+/)) load1 = substr(line, RSTART + 6, RLENGTH - 6)
    if (match(line, /io_some="[^"]*"/)) io_some = avg(substr(line, RSTART, RLENGTH))
    if (match(line, /io_full="[^"]*"/)) io_full = avg(substr(line, RSTART, RLENGTH))
    if (match(line, /mem_full="[^"]*"/)) mem_full = avg(substr(line, RSTART, RLENGTH))
  } else if (kind == "DISK") {
    v = val($4); if (v !~ /^[0-9]+$/) v = -1
    if ($3 == "sda") sda = v; else if ($3 == "mmcblk1") mmc = v
  } else if (kind == "DSTATE") {
    w = val($NF)
    if (w !~ ign) {
      dstate++
      c = ""
      for (i = 4; i < NF; i++) c = c (c == "" ? "" : " ") $i
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
flags=$(awk -v age="$age" -v io="${io_full10:--1}" -v sda="${sda_inflight:--1}" -v ds="${dstate:--1}" \
  -v pa="$PROBLEM_AGE" -v pio="$PROBLEM_IO_FULL10" -v ps="$PROBLEM_SDA_INFLIGHT" -v pd="$PROBLEM_DSTATE" \
  'BEGIN {
    a = (age >= pa); i = (io >= pio); s = (sda >= ps); d = (ds >= pd)
    r = ""
    if (a) r = r ",stale"
    if (i) r = r ",io_full10"
    if (s) r = r ",sda_inflight"
    if (d) r = r ",dstate"
    print a, i, s, d, (a || i || s || d) ? 1 : 0, (r == "" ? "none" : substr(r, 2))
  }')
# shellcheck disable=SC2086
set -- $flags
r_age=$1 r_io=$2 r_sda=$3 r_dstate=$4 problem=$5 reasons=$6

printf '{"age":%s,"up":%s,"load1":%s,"io_some10":%s,"io_full10":%s,"mem_full10":%s,' \
  "$age" "${up:--1}" "${load1:--1}" "${io_some10:--1}" "${io_full10:--1}" "${mem_full10:--1}"
printf '"sda_inflight":%s,"mmc_inflight":%s,"dstate":%s,"probe_age":%s,"ping":%s,"p22222":%s,"p1883":%s,"p8123":%s,"p4357":%s,"problem":%s,' \
  "${sda_inflight:--1}" "${mmc_inflight:--1}" "${dstate:--1}" "$probe_age" "${ping:--1}" \
  "${p22222:--1}" "${p1883:--1}" "${p8123:--1}" "${p4357:--1}" "$problem"
printf '"r_age":%s,"r_io":%s,"r_sda":%s,"r_dstate":%s,"reasons":"%s","dstate_tasks":"%s"}\n' \
  "$r_age" "$r_io" "$r_sda" "$r_dstate" "$reasons" "$dstate_tasks"
