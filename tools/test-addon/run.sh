#!/usr/bin/sh
# run.sh — Test Add-on no-op entrypoint.
#
# This add-on exists so the Provider can install + configure + start + stop +
# uninstall a real HA add-on during the Phase 14 verify suite without touching
# any production add-on on the host. The container process sleeps forever so
# Supervisor observes `started: true`; nothing observable happens beyond the
# startup log line.

set -e

bashio::log.info "test-addon started (Phase 14 verify suite target, no-op)"

exec sleep infinity
