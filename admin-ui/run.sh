#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# PID 1: runs the demo admin GUI (python3 -m app.main). SIGTERM is handled by the Python process itself.

ADMIN_UI_VERSION="$(bashio::app.version 2>/dev/null || bashio::addon.version 2>/dev/null || echo unknown)"
export ADMIN_UI_VERSION

cd /opt/admin-ui || exit 1
exec python3 -m app.main
