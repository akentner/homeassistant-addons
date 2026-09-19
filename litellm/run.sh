#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# ── Signal trap (Plan 02 expands the handler body with master/salt persistence + log-reopen) ─
_on_term() {
    bashio::log.info "Received SIGTERM — graceful drain (30s)..."
    # Plan 02: forward to litellm PID + drain in-flight requests
    sleep 1
}
_on_hup() {
    bashio::log.notice "Received SIGHUP — log-reopen (placeholder; Plan 02 wires litellm log-reopen)"
}
trap _on_term TERM
trap _on_hup HUP

# ── Options ──────────────────────────────────────────────────────────────────
LOG_LEVEL=$(bashio::config 'log_level' 'info')
export LITELLM_LOG="${LOG_LEVEL^^}"

# ── PostgreSQL password (persistent; chmod 600; idempotent) ────────────────────
PG_PASS_FILE=/data/.pg_password
if [ ! -f "${PG_PASS_FILE}" ]; then
    bashio::log.info "Generating PostgreSQL password..."
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40 > "${PG_PASS_FILE}"
    chmod 600 "${PG_PASS_FILE}"
fi
PG_PASS=$(cat "${PG_PASS_FILE}")

# ── PostgreSQL setup (mirrors authentik/run.sh lines 33-61) ───────────────────
PG_VERSION=$(find /usr/lib/postgresql/ -maxdepth 1 -mindepth 1 -type d | sort -V | tail -1 | xargs basename)
PG_BIN="/usr/lib/postgresql/${PG_VERSION}/bin"
PG_DATA=/data/postgresql

mkdir -p "${PG_DATA}"
chown postgres:postgres "${PG_DATA}"

if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    bashio::log.info "Initializing PostgreSQL ${PG_VERSION} database..."
    su -s /bin/bash postgres -c "${PG_BIN}/initdb -D ${PG_DATA} --encoding=UTF8 --locale=C"
    echo "host litellm litellm 127.0.0.1/32 md5" >> "${PG_DATA}/pg_hba.conf"
fi

bashio::log.info "Starting PostgreSQL..."
su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl -D ${PG_DATA} -o '-h 127.0.0.1' -l /data/postgresql.log start"

until su -s /bin/bash postgres -c "${PG_BIN}/pg_isready -h 127.0.0.1" 2>/dev/null; do
    sleep 1
done
bashio::log.info "PostgreSQL ready."

# Create database and user on first start (idempotent)
su -s /bin/bash postgres \
    -c "psql -h 127.0.0.1 -tAc \"SELECT 1 FROM pg_roles WHERE rolname='litellm'\"" 2>/dev/null \
    | grep -q 1 || {
    bashio::log.info "Creating litellm PostgreSQL user and database..."
    su -s /bin/bash postgres -c "psql -h 127.0.0.1 -c \"CREATE USER litellm WITH PASSWORD '${PG_PASS}';\""
    su -s /bin/bash postgres -c "psql -h 127.0.0.1 -c \"CREATE DATABASE litellm OWNER litellm;\""
}

# ── LiteLLM environment ──────────────────────────────────────────────────────
export DATABASE_URL="postgresql://litellm:${PG_PASS}@127.0.0.1:5432/litellm"

# ── Synthesize LiteLLM YAML from HA options.json (Python helper; Plan 02 expands) ─
python3 /app/generate_config.py

# ── Start LiteLLM (PID1, foreground) ─────────────────────────────────────────
bashio::log.info "Starting LiteLLM on :4000..."
exec litellm --config /data/litellm_config.yaml
