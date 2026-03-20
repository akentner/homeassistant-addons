#!/bin/sh
set -e

[ -n "$TZ" ] && export TZ

# Generate AppConfig-compatible YAML from HA options.json
uv run --no-dev python /app/generate_config.py

# Start application
export PHONE_LOGGER_CONFIG=/tmp/phone-logger-config.yaml
exec uv run --no-dev python -m src.main
