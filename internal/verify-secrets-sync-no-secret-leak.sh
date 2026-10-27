#!/usr/bin/env bash
# Verify the secrets-sync/ add-on never leaks secret values into logs, state.json or its API responses.
# Runs the image with synthetic (sentinel) credentials against an unreachable server, so the Bitwarden provider
# fails with an error code while every code path that could echo credentials is exercised.
# Requires the image from verify-secrets-sync-scaffold.sh. Manual invocation:
#   bash internal/verify-secrets-sync-no-secret-leak.sh
set -euo pipefail

IMAGE_TAG="secrets-sync-verify:local"
CONTAINER_NAME="secrets-sync-no-leak-verify"
WORK_DIR="$(mktemp -d)"
cleanup() {
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    # The container writes root-owned files (bw state); remove them from inside a container first
    docker run --rm --entrypoint sh -v "${WORK_DIR}:/w" "${IMAGE_TAG}" -c 'rm -rf /w/* /w/.[!.]*' >/dev/null 2>&1 || true
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

SENTINELS=(
    "SENTINEL-CLIENTID-7f3a91"
    "SENTINEL-CLIENTSECRET-b24c08"
    "SENTINEL-MASTERPW-e5d176"
)

mkdir -p "${WORK_DIR}/config" "${WORK_DIR}/addon_config" "${WORK_DIR}/data"
cat > "${WORK_DIR}/data/options.json" <<JSON
{"providers":["bitwarden"],"interval":60,"collision_policy":"error","shrink_guard_percent":50,"log_level":"debug",
 "bitwarden":{"server_url":"http://127.0.0.1:9","client_id":"${SENTINELS[0]}","client_secret":"${SENTINELS[1]}",
 "master_password":"${SENTINELS[2]}","organization_id":"","collection_id":"","key_style":"legacy",
 "notes_dir":"bitwarden"}}
JSON
# Pre-existing secrets.yaml must survive a failing provider
printf '# managed by Secrets Sync - do not edit\nkeep_me: "x"\n' > "${WORK_DIR}/config/secrets.yaml"

echo "==> Running ${IMAGE_TAG} with sentinel credentials"
docker run -d --name "${CONTAINER_NAME}" \
    -v "${WORK_DIR}/data:/data" -v "${WORK_DIR}/config:/config" -v "${WORK_DIR}/addon_config:/addon_config" \
    "${IMAGE_TAG}" >/dev/null

# Wait up to 45s for the web server and a first (failed) cycle
STATUS=""
for _ in $(seq 1 45); do
    STATUS="$(docker exec "${CONTAINER_NAME}" wget -q -O - http://127.0.0.1:8099/api/status.json 2>/dev/null || true)"
    if [ -n "${STATUS}" ] && ! printf '%s' "${STATUS}" | grep -q '"status": *"starting"'; then
        break
    fi
    sleep 1
done
[ -n "${STATUS}" ] || { echo "✗ /api/status.json never answered"; docker logs "${CONTAINER_NAME}" 2>&1 | tail -20; exit 1; }
echo "✓ /api/status.json answered"

# Exercise the other read endpoints too
HEALTH="$(docker exec "${CONTAINER_NAME}" wget -q -O - http://127.0.0.1:8099/api/health 2>&1 || true)"
# GET / is ingress only (Supervisor address + X-Ingress-Path); from inside the container it must be refused.
# The body of the refusal is still scanned; the rendered page is covered by tests/web.
INDEX="$(docker exec "${CONTAINER_NAME}" wget -S -O - http://127.0.0.1:8099/ 2>&1 || true)"
if printf '%s' "${INDEX}" | grep -q 'HTTP/1.[01] 200'; then
    echo "✗ GET / answered 200 without ingress headers (must be ingress only)"
    exit 1
fi
echo "✓ GET / refused without ingress"
LOGS="$(docker logs "${CONTAINER_NAME}" 2>&1)"
STATE_FILE="$(docker exec "${CONTAINER_NAME}" cat /data/state.json 2>/dev/null || true)"
ENV_DUMP="$(docker exec "${CONTAINER_NAME}" sh -c 'cat /proc/1/cmdline 2>/dev/null | tr "\0" " "; ps -eo args' 2>&1 || true)"
SECRETS_YAML="$(cat "${WORK_DIR}/config/secrets.yaml")"

check() { # $1 = label, $2 = haystack
    local s
    for s in "${SENTINELS[@]}"; do
        if printf '%s' "$2" | grep -qF -- "${s}"; then
            echo "✗ sentinel '${s}' found in ${1}"
            exit 1
        fi
    done
    echo "✓ no sentinel in ${1}"
}

check "container logs (log_level debug)" "${LOGS}"
check "/api/status.json" "${STATUS}"
check "/api/health" "${HEALTH}"
check "GET / response" "${INDEX}"
check "/data/state.json" "${STATE_FILE}"
check "process arguments (argv)" "${ENV_DUMP}"
check "secrets.yaml" "${SECRETS_YAML}"

# Failing provider must not destroy the last good file
grep -q 'keep_me' "${WORK_DIR}/config/secrets.yaml" || { echo "✗ last good secrets.yaml was overwritten"; exit 1; }
echo "✓ last good secrets.yaml kept"

# Process stayed alive (never exit on error)
[ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER_NAME}")" = "true" ] || { echo "✗ container exited"; exit 1; }
echo "✓ process keeps running while provider fails"

# Dedicated scan of everything under /data and /config for sentinels
for s in "${SENTINELS[@]}"; do
    if grep -rqF -- "${s}" "${WORK_DIR}/config" "${WORK_DIR}/addon_config" 2>/dev/null; then
        echo "✗ sentinel '${s}' found in /config or /addon_config"
        exit 1
    fi
    # options.json is the only allowed place under /data (HA owns it); bw state dir must be clean
    if [ -d "${WORK_DIR}/data/bw" ] && grep -rlF -- "${s}" "${WORK_DIR}/data" --exclude=options.json 2>/dev/null | grep -q .; then
        echo "✗ sentinel '${s}' persisted in /data outside options.json"
        exit 1
    fi
done
echo "✓ no sentinel persisted outside options.json"

echo ""
echo "All secrets-sync no-secret-leak verifications passed."
