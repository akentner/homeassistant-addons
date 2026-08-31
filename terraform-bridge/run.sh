#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

bashio::log.info "Starting terraform-bridge (Phase 9 scaffold)..."

# The Bridge binary owns its own structured JSON logging via stdlib log/slog
# (slog.NewJSONHandler(os.Stdout, ...)). bashio does NOT capture the binary's
# stdout because `exec` replaces the parent process — see CONTEXT.md D-10.
exec /usr/bin/bridge "$@"
