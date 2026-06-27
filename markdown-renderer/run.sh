#!/bin/sh
set -e

# HOME must be set for `git config --global` (GIT-02). The HA base image
# does not export HOME by default, and `git config --global` aborts with
# `fatal: $HOME not set` if HOME is unset, which would prevent the add-on
# from starting. /root is the conventional home for the container's root
# user; git writes its global config to $HOME/.gitconfig.
export HOME=/root

# Allow git to operate on repos owned by a different UID (GIT-02).
# Required for git 2.35.2+ when /share, /config, or /media mounts
# have different ownership than the container's root user.
git config --global --add safe.directory '*'

# Generate nginx config + per-namespace index.html from HA options.
python3 /app/generate_nginx.py

# One-shot git pull at startup (GIT-01). Runs after generate_nginx.py
# so any new index.html reflects the freshly-pulled Markdown. Git
# errors are logged as warnings by _git_sync.py but never block
# startup (GIT-05).
python3 /app/_git_sync.py

# Periodic background git sync (GIT-04). One loop for all namespaces;
# _git_sync.py --periodic iterates each namespace and respects its own
# git_pull_interval (D-08). Sleep 5s as the minimum floor; _git_sync.py
# is a no-op for namespaces whose own interval has not yet elapsed.
# The PID is captured so the trap below can kill the loop cleanly.
GIT_SYNC_PID=""
while true; do
    sleep 5
    python3 /app/_git_sync.py --periodic || true
done &
GIT_SYNC_PID=$!

# Signal handling (D-11): on SIGTERM/SIGINT (HA Supervisor restart or
# add-on stop), kill the background git-sync loop before exec hands
# off PID 1 to nginx. Without this, the loop becomes orphaned and
# continues pulling against a stopped add-on.
trap 'kill "$GIT_SYNC_PID" 2>/dev/null || true; exit 0' TERM INT

# Start nginx in foreground (PID 1) - HA restart policy handles crashes.
# Use -c /tmp/nginx.conf so nginx reads the config we just generated
# instead of the default /etc/nginx/nginx.conf (which listens on port 80).
exec nginx -c /tmp/nginx.conf -g 'daemon off;'
