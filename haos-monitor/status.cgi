#!/bin/sh
# HTTP wrapper around status.sh: /cgi-bin/status[?host=<slug>] (default: first configured host)
HOSTS=/etc/haos-monitor.hosts
want=$(printf '%s' "$QUERY_STRING" | tr '&' '\n' | sed -n 's/^host=//p' | head -1 | tr -cd 'a-z0-9_')
first=$(head -1 "$HOSTS" 2>/dev/null | cut -f1)
slug=${want:-$first}

if [ -z "$slug" ] || ! cut -f1 "$HOSTS" 2>/dev/null | grep -qx "$slug"; then
  printf 'Status: 404 Not Found\r\nContent-Type: application/json\r\n\r\n{"error":"unknown host"}\n'
  exit 0
fi
printf 'Content-Type: application/json\r\n\r\n'
exec /status.sh "$slug"
