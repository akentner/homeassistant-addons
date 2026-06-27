#!/bin/sh
set -e

# Generate nginx config + per-namespace index.html from HA options
python3 /app/generate_nginx.py

# Start nginx in foreground (PID 1) - HA restart policy handles crashes
exec nginx -g 'daemon off;'
