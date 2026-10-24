#!/bin/sh
# Host list for the UI: /api/hosts.json -> [{"slug":..,"name":..,"host":..}]
printf 'Content-Type: application/json\r\n\r\n'
jq -nR '[inputs | split("\t") | {slug: .[0], name: .[1], host: .[2]}]' < "${HOSTS_FILE:-/etc/haos-monitor.hosts}" 2>/dev/null || echo '[]'
