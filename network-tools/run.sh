#!/bin/sh
set -e

INTERVAL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('interval', 30))" 2>/dev/null || echo 30)
PORT=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('port', 8080))" 2>/dev/null || echo 8080)

mkdir -p /data/results /var/run/nginx /var/lib/nginx/tmp/client_body

sed "s/__PORT__/$PORT/" /etc/nginx/network-tools.conf > /tmp/nginx-network-tools.conf
nginx -c /tmp/nginx-network-tools.conf &

# Initial scan before loop starts
python3 /usr/local/bin/arping_scan.py

while true; do
    sleep "$INTERVAL"
    python3 /usr/local/bin/arping_scan.py
done
