#!/bin/sh
set -e

# Generate nginx config + per-namespace index.html from HA options
python3 /app/generate_nginx.py

# Start nginx in foreground (PID 1) - HA restart policy handles crashes.
# Use -c /tmp/nginx.conf so nginx reads the config we just generated
# instead of the default /etc/nginx/nginx.conf (which listens on port 80).
exec nginx -c /tmp/nginx.conf -g 'daemon off;'
