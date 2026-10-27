#!/usr/bin/env bash
# Verify the secrets-sync/ add-on never leaks secret values into logs, state.json or its API responses.
# Runs the image with synthetic (sentinel) credentials against an unreachable server, so the Bitwarden provider
# fails with an error code while every code path that could echo credentials is exercised.
# Requires the image from verify-secrets-sync-scaffold.sh. Manual invocation:
#   bash internal/verify-secrets-sync-no-secret-leak.sh
set -euo pipefail

IMAGE_TAG="secrets-sync-verify:local"
CONTAINER_NAME="secrets-sync-no-leak-verify"
GIT_CONTAINER_NAME="secrets-sync-no-leak-verify-git"
WORK_DIR="$(mktemp -d)"
cleanup() {
    docker rm -f "${CONTAINER_NAME}" "${GIT_CONTAINER_NAME}" >/dev/null 2>&1 || true
    # The container writes root-owned files (bw state); remove them from inside a container first
    docker run --rm --entrypoint sh -v "${WORK_DIR}:/w" "${IMAGE_TAG}" -c 'rm -rf /w/* /w/.[!.]*' >/dev/null 2>&1 || true
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

SENTINELS=(
    "SENTINEL-CLIENTID-7f3a91"
    "SENTINEL-CLIENTSECRET-b24c08"
    "SENTINEL-MASTERPW-e5d176"
    "SENTINEL-GITTOKEN-91c0de"
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

# ---------------------------------------------------------------------------------------------------------------
# Phase 2: SOPS git source (local file:// repository, no network) with a sentinel https token in the options
# ---------------------------------------------------------------------------------------------------------------
echo "==> Phase 2: SOPS git source + change check"
GW="${WORK_DIR}/git"
mkdir -p "${GW}/data" "${GW}/config" "${GW}/addon_config" "${GW}/repos"

# Create an age key, a SOPS-encrypted file and a git repository inside the image (root-owned, like the app runs)
docker run --rm --entrypoint sh -v "${GW}:/w" "${IMAGE_TAG}" -c '
    set -e
    age-keygen -o /w/addon_config/age.key >/dev/null 2>&1
    chmod 600 /w/addon_config/age.key
    PUB="$(age-keygen -y /w/addon_config/age.key)"
    git init -q -b main /w/repos/secrets
    cd /w/repos/secrets
    printf "db:\n  password: first-value\nplain: hello\n" > secrets.sops.yaml
    sops --encrypt --age "${PUB}" --in-place secrets.sops.yaml
    git add secrets.sops.yaml
    git -c user.name=t -c user.email=t@t commit -q -m init
' || { echo "✗ could not create test repository"; exit 1; }

# The https token is set although the repository is a local file:// URL; it must never show up anywhere
cat > "${GW}/data/options.json" <<JSON
{"providers":["sops"],"interval":60,"check_interval":30,"collision_policy":"error","shrink_guard_percent":50,
 "log_level":"debug","usage_scan":"off",
 "sops":{"source":"git","file":"/config/secrets.sops.yaml","flatten_separator":"_",
 "git_url":"file:///repos/secrets","git_branch":"main","git_path":"secrets.sops.yaml",
 "git_username":"x-access-token","git_token":"${SENTINELS[3]}"}}
JSON

docker run -d --name "${GIT_CONTAINER_NAME}" -e SS_GIT_ALLOW_PROTOCOL=file \
    -v "${GW}/data:/data" -v "${GW}/config:/config" -v "${GW}/addon_config:/addon_config" \
    -v "${GW}/repos:/repos" "${IMAGE_TAG}" >/dev/null

gstatus() { docker exec "${GIT_CONTAINER_NAME}" wget -q -O - http://127.0.0.1:8099/api/status.json 2>/dev/null || true; }
gsecrets() { docker exec "${GIT_CONTAINER_NAME}" cat /config/secrets.yaml 2>/dev/null || true; }

# First sync: clone, decrypt, write
GOT=""
for _ in $(seq 1 60); do
    GOT="$(gsecrets)"
    printf '%s' "${GOT}" | grep -q 'db_password.*first-value' && break
    sleep 1
done
printf '%s' "${GOT}" | grep -q 'db_password.*first-value' || {
    echo "✗ first git sync did not write db_password"; gstatus; docker logs "${GIT_CONTAINER_NAME}" 2>&1 | tail -15; exit 1; }
echo "✓ git source synced (clone + sops decrypt)"

# New commit: the change check (30 s) must start a sync well before the 60 s interval
docker run --rm --entrypoint sh -v "${GW}:/w" "${IMAGE_TAG}" -c '
    set -e
    cd /w/repos/secrets
    PUB="$(age-keygen -y /w/addon_config/age.key)"
    printf "db:\n  password: second-value\nplain: hello\n" > secrets.sops.yaml
    sops --encrypt --age "${PUB}" --in-place secrets.sops.yaml
    git -c user.name=t -c user.email=t@t commit -q -am change
' || { echo "✗ could not commit change"; exit 1; }
CHANGED_AT="$(date +%s)"
GOT=""
for _ in $(seq 1 75); do
    GOT="$(gsecrets)"
    printf '%s' "${GOT}" | grep -q 'db_password.*second-value' && break
    sleep 1
done
printf '%s' "${GOT}" | grep -q 'db_password.*second-value' || {
    echo "✗ change was not picked up"; gstatus; docker logs "${GIT_CONTAINER_NAME}" 2>&1 | tail -15; exit 1; }
echo "✓ change picked up after $(( $(date +%s) - CHANGED_AT )) s"
GSTATUS="$(gstatus)"
printf '%s' "${GSTATUS}" | grep -q 'source_changed' && echo "✓ event source_changed recorded" ||
    echo "! source_changed event not in status (interval fallback may have won the race)"

GLOGS="$(docker logs "${GIT_CONTAINER_NAME}" 2>&1)"
GSTATE="$(docker exec "${GIT_CONTAINER_NAME}" cat /data/state.json 2>/dev/null || true)"
GPROCS="$(docker exec "${GIT_CONTAINER_NAME}" sh -c 'ps -eo args' 2>&1 || true)"
check "git container logs (log_level debug)" "${GLOGS}"
check "git /api/status.json" "${GSTATUS}"
check "git /data/state.json" "${GSTATE}"
check "git process arguments (argv)" "${GPROCS}"
# The URL of the repository must not be logged at info level either
if printf '%s' "${GLOGS}" | grep -v ' DEBUG ' | grep -qF 'file:///repos/secrets'; then
    echo "✗ git URL logged above debug level"
    exit 1
fi
echo "✓ git URL not logged above debug level"
# Neither the repository checkout cache nor the persisted data may contain the token
if docker exec "${GIT_CONTAINER_NAME}" grep -rqF -- "${SENTINELS[3]}" /data/git /data/known_hosts 2>/dev/null; then
    echo "✗ token persisted in the git cache"
    exit 1
fi
echo "✓ token not persisted in git cache"

echo ""
echo "All secrets-sync no-secret-leak verifications passed."
