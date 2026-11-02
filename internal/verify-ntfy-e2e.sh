#!/usr/bin/env bash
# Docker end-to-end run of the ntfy add-on against a real ntfy server: build, start, drive the GUI API and ntfy.
# Manual invocation: bash internal/verify-ntfy-e2e.sh
# Optional env: NTFY_E2E_PREFIX (container name prefix, default ntfy-e2e), NTFY_E2E_WORK (scratch dir).
# Starts a container: never run it together with internal/verify-ntfy-scaffold.sh or in a second worktree.
set -euo pipefail

ADDON_DIR="ntfy"
IMAGE_TAG="ntfy-verify:local"
PREFIX="${NTFY_E2E_PREFIX:-ntfy-e2e}"
CONTAINER="${PREFIX}-main"
WORK="${NTFY_E2E_WORK:-}"

fail() { echo "✗ $1"; exit 1; }

# usage: yget <file> <dotted.path>  (HA tags tolerated)
yget() {
    python3 -I - "$1" "$2" <<'PY'
import sys, yaml
class L(yaml.SafeLoader): pass
L.add_multi_constructor("!", lambda loader, suffix, node: None)
node = yaml.load(open(sys.argv[1]), Loader=L)
for part in sys.argv[2].split("."):
    node = node.get(part) if isinstance(node, dict) else None
print("null" if node is None else node)
PY
}

cleanup() {
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    # data is root-owned: remove it through the image itself
    if [ -n "${WORK}" ] && [ -d "${WORK}" ]; then
        docker run --rm -v "${WORK}:/w" --entrypoint sh "${IMAGE_TAG}" -c 'rm -rf /w/data' >/dev/null 2>&1 || true
        rmdir "${WORK}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

wait_for() { # usage: wait_for <seconds> <description> <command...>
    local limit="$1" what="$2"
    shift 2
    local i
    for ((i = 0; i < limit; i++)); do
        if "$@" >/dev/null 2>&1; then return 0; fi
        sleep 1
    done
    fail "timeout waiting for ${what}"
}

echo "==> docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"

if [ -z "${WORK}" ]; then WORK="$(mktemp -d)"; else mkdir -p "${WORK}"; fi
DATA="${WORK}/data"
mkdir -p "${DATA}"
# sentinel passwords: the driver scans logs, files and payloads for them
python3 -I - "${DATA}/options.json" <<'PY'
import json, sys
json.dump(
    {
        "admin_user": "root",
        "admin_password": "sentinel-admin-pw",
        "base_url": "http://localhost",
        "behind_proxy": True,
        "auth_default_access": "deny-all",
        "backup_keep": 4,
        "baseline_users": [
            {"username": "homeassistant", "password": "sentinel-ha-pw", "topic": "ha_topic", "write_access": True},
            {"username": "akentner", "password": "sentinel-ak-pw", "topic": "ha_topic", "write_access": False},
        ],
    },
    open(sys.argv[1], "w"),
)
PY

echo "==> Start container ${CONTAINER}"
docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
docker run -d --name "${CONTAINER}" -v "${DATA}:/data" -e NTFY_INGRESS_REMOTE=127.0.0.1 "${IMAGE_TAG}" >/dev/null
wait_for 60 "ntfy health" bash -c "docker exec ${CONTAINER} curl -fsS http://127.0.0.1:8000/v1/health | grep -q '\"healthy\":true'"
wait_for 60 "GUI health" bash -c "docker exec ${CONTAINER} curl -fsS -H 'X-Ingress-Path: /x' http://127.0.0.1:8099/api/health"
wait_for 60 "bootstrap" bash -c "docker logs ${CONTAINER} 2>&1 | grep -q '^\[bootstrap\] done'"

echo "==> Scenario driver"
python3 -I internal/verify-ntfy-e2e.py --container "${CONTAINER}" --data-dir "${DATA}" --image "${IMAGE_TAG}"
