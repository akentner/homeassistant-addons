#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# ── Signal trap (per D-10, authentik/iac-runner precedent) ──────────────────
# Trap installed BEFORE postgres init so SIGTERM during init still drains cleanly.
# _on_term is invoked when bashio/bash sends SIGTERM during HA Supervisor restart;
# we forward to litellm (PID1 after exec) and wait up to 30s for graceful drain.
_on_term() {
    bashio::log.notice "litellm.term.received — graceful drain (30s)..."
    if [ -n "${LITELLM_PID:-}" ] && kill -0 "${LITELLM_PID}" 2>/dev/null; then
        kill -TERM "${LITELLM_PID}" 2>/dev/null || true
        # Wait up to 30s for graceful exit
        for _ in $(seq 1 30); do
            if ! kill -0 "${LITELLM_PID}" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        # If still alive after 30s, force-kill
        if kill -0 "${LITELLM_PID}" 2>/dev/null; then
            bashio::log.warning "litellm.term.timeout — forcing exit"
            kill -KILL "${LITELLM_PID}" 2>/dev/null || true
        fi
    fi
    exit 0
}
_on_hup() {
    bashio::log.notice "litellm.log_reopen — forwarding SIGHUP to litellm"
    if [ -n "${LITELLM_PID:-}" ] && kill -0 "${LITELLM_PID}" 2>/dev/null; then
        # LiteLLM treats SIGHUP as log-reopen since 1.39; verified in Plan 04 E2E
        kill -HUP "${LITELLM_PID}" 2>/dev/null || true
    fi
}
trap _on_term TERM
trap _on_hup HUP

# ── Options ──────────────────────────────────────────────────────────────────
LOG_LEVEL=$(bashio::config 'log_level' 'info')
export LITELLM_LOG="${LOG_LEVEL^^}"

# ── Master/Salt-Key lifecycle (D-11, D-12) ──────────────────────────────────
MASTER_KEY_FILE=/data/.litellm_master_key
MASTER_KEY=$(bashio::config 'master_key' '')
if [ -z "${MASTER_KEY}" ] && [ -f "${MASTER_KEY_FILE}" ]; then
    MASTER_KEY=$(cat "${MASTER_KEY_FILE}")
fi
if [ -z "${MASTER_KEY}" ]; then
    # One-time UX: log the plaintext so the operator can copy it into secrets.yaml.
    # On subsequent restarts the file check above catches the persisted key silently.
    bashio::log.notice "Generating master_key — copy from this log line to secrets.yaml as 'litellm_master_key:'"
    MASTER_KEY="sk-$(openssl rand -hex 32)"
    bashio::log.notice "litellm_master_key=${MASTER_KEY}"
    echo "${MASTER_KEY}" > "${MASTER_KEY_FILE}"
    chmod 600 "${MASTER_KEY_FILE}"
fi
export LITELLM_MASTER_KEY="${MASTER_KEY}"

SALT_KEY_FILE=/data/.litellm_salt_key
SALT_KEY=$(bashio::config 'salt_key' '')
if [ -z "${SALT_KEY}" ] && [ -f "${SALT_KEY_FILE}" ]; then
    SALT_KEY=$(cat "${SALT_KEY_FILE}")
fi
if [ -z "${SALT_KEY}" ]; then
    bashio::log.notice "Generating salt_key — copy from this log line to secrets.yaml as 'litellm_salt_key:'"
    SALT_KEY="$(openssl rand -hex 32)"
    bashio::log.notice "litellm_salt_key=${SALT_KEY}"
    echo "${SALT_KEY}" > "${SALT_KEY_FILE}"
    chmod 600 "${SALT_KEY_FILE}"
fi
export LITELLM_SALT_KEY="${SALT_KEY}"

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

# ── Postgres tuning (D-15, D-16) ────────────────────────────────────────────
# Apply operator-supplied tuning via /data/postgresql/litellm-tuning.conf +
# `pg_ctl reload` (SIGHUP-reloadable settings apply immediately).
SHARED_BUFFERS=$(bashio::config 'postgres.shared_buffers' '64MB')
LOG_MIN_DURATION=$(bashio::config 'postgres.log_min_duration_statement' '1000')
NEW_MAX_CONNECTIONS=$(bashio::config 'postgres.max_connections' '20')

PG_TUNING_CONF="${PG_DATA}/litellm-tuning.conf"
cat > "${PG_TUNING_CONF}" <<EOF
# litellm-tuning.conf — applied by /run.sh on every startup.
# Generated by HA Supervisor add-on options (postgres.* keys).
# pg_ctl reload applies SIGHUP-reloadable settings (shared_buffers,
# log_min_duration_statement) immediately; max_connections needs a restart.
shared_buffers = ${SHARED_BUFFERS}
log_min_duration_statement = ${LOG_MIN_DURATION}
effective_cache_size = 256MB
work_mem = 4MB
max_connections = ${NEW_MAX_CONNECTIONS}
EOF
chown postgres:postgres "${PG_TUNING_CONF}"

# On first init, append the include_if_exists directive to postgresql.conf so
# the tuning.conf is loaded by postgres on each startup. Idempotent: only
# append when the directive is not yet present (handles edge cases where
# initdb was run without the directive — e.g. upgrade from a prior litellm version).
if ! grep -q "include_if_exists = 'litellm-tuning.conf'" "${PG_DATA}/postgresql.conf" 2>/dev/null; then
    echo "include_if_exists = 'litellm-tuning.conf'" >> "${PG_DATA}/postgresql.conf"
    chown postgres:postgres "${PG_DATA}/postgresql.conf"
fi

# Apply SIGHUP-reloadable settings immediately
su -s /bin/bash postgres -c "${PG_BIN}/pg_ctl -D ${PG_DATA} reload"
bashio::log.info "postgres.tuning.applied shared_buffers=${SHARED_BUFFERS} log_min_duration_statement=${LOG_MIN_DURATION}"

# Detect max_connections change — if the operator changed it, the new value
# requires a Postgres restart (not SIGHUP-reloadable).
CURRENT_MAX_CONNECTIONS=$(su -s /bin/bash postgres -c "psql -h 127.0.0.1 -tAc 'SHOW max_connections'" 2>/dev/null | tr -d ' ' || echo "?")
if [ "${CURRENT_MAX_CONNECTIONS}" != "${NEW_MAX_CONNECTIONS}" ]; then
    bashio::log.warning "postgres.tuning.max_connections=${NEW_MAX_CONNECTIONS} requires restart — current value remains ${CURRENT_MAX_CONNECTIONS}"
fi

# ── LiteLLM environment (exported BEFORE generate_config.py so it sees them) ─
export DATABASE_URL="postgresql://litellm:${PG_PASS}@127.0.0.1:5432/litellm"
export LITELLM_MASTER_KEY
export LITELLM_SALT_KEY

# ── Synthesize LiteLLM YAML from HA options.json (D-17) ──────────────────────
python3 /app/generate_config.py

# ── Start LiteLLM (background + wait — preserves signal-trap forwarding) ─────
# We use background + wait instead of `exec` so the signal trap above can forward
# SIGTERM/SIGHUP to the captured ${LITELLM_PID}. `exec` replaces the shell with
# litellm, losing the trap; background + wait keeps the shell alive as PID1 and
# lets the trap deliver signals to the captured PID. This is the standard bash
# idiom for signal-trapped daemon supervision without s6-overlay.
bashio::log.info "Starting LiteLLM on :4000..."
litellm --config /data/litellm_config.yaml &
LITELLM_PID=$!
wait "${LITELLM_PID}"
