#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# ── Python environment ────────────────────────────────────────────────────────
export VIRTUAL_ENV=/ak-root/.venv
export PATH="/ak-root/.venv/bin:$PATH"
export PYTHONPATH=/

# ── HA add-on options ─────────────────────────────────────────────────────────
LOG_LEVEL=$(bashio::config 'log_level' 'info')
TIMEZONE=$(bashio::config 'timezone' 'Europe/Berlin')
export TZ="${TIMEZONE}"

# ── Persistent secrets (generated once, stable across restarts) ───────────────
PG_PASS_FILE=/data/.pg_password
SECRET_KEY_FILE=/data/.secret_key

if [ ! -f "${PG_PASS_FILE}" ]; then
    bashio::log.info "Generating PostgreSQL password..."
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40 > "${PG_PASS_FILE}"
fi
PG_PASS=$(cat "${PG_PASS_FILE}")

if [ ! -f "${SECRET_KEY_FILE}" ]; then
    bashio::log.info "Generating authentik secret key..."
    tr -dc 'A-Za-z0-9!@#%^&*()-_+=' < /dev/urandom | head -c 60 > "${SECRET_KEY_FILE}"
fi
AUTHENTIK_SECRET_KEY=$(cat "${SECRET_KEY_FILE}")
export AUTHENTIK_SECRET_KEY

# ── PostgreSQL setup ──────────────────────────────────────────────────────────
PG_VERSION=$(find /usr/lib/postgresql/ -maxdepth 1 -mindepth 1 -type d | sort -V | tail -1 | xargs basename)
PG_BIN="/usr/lib/postgresql/${PG_VERSION}/bin"
PG_DATA="/data/postgresql"

mkdir -p "${PG_DATA}"
chown postgres:postgres "${PG_DATA}"

if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    bashio::log.info "Initializing PostgreSQL ${PG_VERSION} database..."
    su -s /bin/bash postgres -c "${PG_BIN}/initdb -D ${PG_DATA} --encoding=UTF8 --locale=C"
    echo "host authentik authentik 127.0.0.1/32 md5" >> "${PG_DATA}/pg_hba.conf"
fi

bashio::log.info "Starting PostgreSQL..."
su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl -D ${PG_DATA} -o '-h 127.0.0.1' -l /data/postgresql.log start"

until su -s /bin/bash postgres -c "${PG_BIN}/pg_isready -h 127.0.0.1" 2>/dev/null; do
    sleep 1
done
bashio::log.info "PostgreSQL ready."

# Create database and user on first start
su -s /bin/bash postgres \
    -c "psql -h 127.0.0.1 -tAc \"SELECT 1 FROM pg_roles WHERE rolname='authentik'\"" 2>/dev/null \
    | grep -q 1 || {
    bashio::log.info "Creating authentik PostgreSQL user and database..."
    su -s /bin/bash postgres -c "psql -h 127.0.0.1 -c \"CREATE USER authentik WITH PASSWORD '${PG_PASS}';\""
    su -s /bin/bash postgres -c "psql -h 127.0.0.1 -c \"CREATE DATABASE authentik OWNER authentik;\""
}

# ── Valkey (Redis-compatible) ─────────────────────────────────────────────────
bashio::log.info "Starting Valkey..."
valkey-server --daemonize yes --save "" --loglevel warning --bind 127.0.0.1

until valkey-cli -h 127.0.0.1 ping 2>/dev/null | grep -q PONG; do
    sleep 1
done
bashio::log.info "Valkey ready."

# ── Authentik environment variables ──────────────────────────────────────────
export AUTHENTIK_REDIS__HOST=127.0.0.1
export AUTHENTIK_REDIS__PORT=6379
export AUTHENTIK_POSTGRESQL__HOST=127.0.0.1
export AUTHENTIK_POSTGRESQL__PORT=5432
export AUTHENTIK_POSTGRESQL__NAME=authentik
export AUTHENTIK_POSTGRESQL__USER=authentik
export AUTHENTIK_POSTGRESQL__PASSWORD="${PG_PASS}"
export AUTHENTIK_POSTGRESQL__SSLMODE=disable
export AUTHENTIK_LOG_LEVEL="${LOG_LEVEL}"
export AUTHENTIK_ERROR_REPORTING__ENABLED=false
export AUTHENTIK_DISABLE_UPDATE_CHECK=true
export PROMETHEUS_MULTIPROC_DIR=/tmp/authentik_prometheus_tmp
mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
chown authentik:authentik "${PROMETHEUS_MULTIPROC_DIR}"

if bashio::config.true 'disable_startup_wizard'; then
    export AUTHENTIK_DISABLE_STARTUP_WIZARD=true
fi

# Email configuration (only when host is provided)
EMAIL_HOST=$(bashio::config 'email_host' '')
if [ -n "${EMAIL_HOST}" ]; then
    export AUTHENTIK_EMAIL__HOST="${EMAIL_HOST}"
    AUTHENTIK_EMAIL__PORT=$(bashio::config 'email_port' '587')
    export AUTHENTIK_EMAIL__PORT
    AUTHENTIK_EMAIL__FROM=$(bashio::config 'email_from' '')
    export AUTHENTIK_EMAIL__FROM
    AUTHENTIK_EMAIL__USERNAME=$(bashio::config 'email_username' '')
    export AUTHENTIK_EMAIL__USERNAME
    AUTHENTIK_EMAIL__PASSWORD=$(bashio::config 'email_password' '')
    export AUTHENTIK_EMAIL__PASSWORD
    if bashio::config.true 'email_use_tls'; then
        export AUTHENTIK_EMAIL__USE_TLS=true
    else
        export AUTHENTIK_EMAIL__USE_TLS=false
    fi
fi

# ── Shared directories for authentik ─────────────────────────────────────────
mkdir -p /data/media /data/certs
chown -R authentik:authentik /data/media /data/certs
ln -sfn /data/media /media
ln -sfn /data/certs /certs

# ── Start authentik server (Go binary — serves web UI and API on :9000/:9443) ─
bashio::log.info "Starting authentik server on :9000..."
runuser -u authentik -- /usr/bin/authentik-server &

# ── Start authentik worker (Rust binary — handles background tasks) ───────────
bashio::log.info "Starting authentik worker..."
exec runuser -u authentik -- /usr/bin/authentik worker
