#!/bin/sh
# Last incident lines of one host for the UI: /api/incidents.json?host=<slug> -> ["<log line>", ...]
HOSTS=${HOSTS_FILE:-/etc/haos-monitor.hosts}
slug=$(printf '%s' "$QUERY_STRING" | tr '&' '\n' | sed -n 's/^host=//p' | head -1 | tr -cd 'a-z0-9_')

if [ -z "$slug" ] || ! cut -f1 "$HOSTS" 2>/dev/null | grep -qx "$slug"; then
  printf 'Status: 404 Not Found\r\nContent-Type: application/json\r\n\r\n{"error":"unknown host"}\n'
  exit 0
fi
printf 'Content-Type: application/json\r\n\r\n'
grep ' INCIDENT ' "${LOGDIR:-/share/haos-monitor}/$slug.log" 2>/dev/null | tail -n 10 | cut -c1-400 | jq -nR '[inputs]'
