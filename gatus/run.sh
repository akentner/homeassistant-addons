#!/bin/sh
set -e

# Generate Gatus config from HA options + user config
python3 /generate_config.py

# Apply timezone if configured
TZ_OPT=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('timezone',''))" 2>/dev/null || true)
[ -n "$TZ_OPT" ] && export TZ="$TZ_OPT"

# Apply log level
LOG_LEVEL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('log_level','info'))" 2>/dev/null || echo "info")
export GATUS_LOG_LEVEL="$LOG_LEVEL"

export GATUS_CONFIG_PATH=/tmp/gatus-config.yaml

# NGINX proxies ingress port 8099 → Gatus on 8080, injecting <base href> via sub_filter
mkdir -p /var/run /var/lib/nginx/tmp/client_body
nginx -g "daemon off;" -c /etc/nginx/gatus-nginx.conf &

exec /usr/local/bin/gatus
