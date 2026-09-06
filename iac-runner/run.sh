#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

bashio::log.info "Starting iac-runner (Phase 16 scaffold)..."

# The runner binary owns its own structured JSON logging via stdlib log/slog
# (slog.NewJSONHandler(os.Stdout, ...)). bashio does NOT capture the binary's
# stdout because `exec` replaces the parent process — see terraform-bridge
# run.sh for the same pattern.
exec /usr/bin/runner "$@"
