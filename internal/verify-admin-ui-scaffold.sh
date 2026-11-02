#!/usr/bin/env bash
# Verify the admin-ui/ add-on tracer in a real image: manifest, build, ingress gate by peer address, vendored runtime
# and clean SIGTERM shutdown.
# Manual invocation: bash internal/verify-admin-ui-scaffold.sh
# Optional env: ADMIN_UI_VERIFY_PREFIX (container name prefix, default admin-ui-verify).
# Builds an image and starts containers: never run it in two worktrees at the same time.
set -euo pipefail

ADDON_DIR="admin-ui"
IMAGE_TAG="admin-ui-verify:local"
PREFIX="${ADMIN_UI_VERIFY_PREFIX:-admin-ui-verify}"
MAIN="${PREFIX}-main"
GATE="${PREFIX}-gate"
VENDOR_FILE="${ADDON_DIR}/app/web/static/lib/vendor/preact-htm.mjs"
LIB_VERSION_FILE="${ADDON_DIR}/app/web/static/lib/VERSION"

fail() { echo "✗ $1"; exit 1; }

# python3 + PyYAML behaves the same on every machine (HA tags tolerated)
# usage: yget <file> <dotted.path>  (prints "null" for a missing key)
yget() {
    python3 -I - "$1" "$2" <<'PY'
import sys, yaml
class L(yaml.SafeLoader): pass
L.add_multi_constructor("!", lambda loader, suffix, node: None)
node = yaml.load(open(sys.argv[1]), Loader=L)
for part in sys.argv[2].split("."):
    node = node.get(part) if isinstance(node, dict) else None
print("null" if node is None else len(node) if isinstance(node, list) else node)
PY
}

cleanup() {
    docker rm -f "${MAIN}" "${GATE}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# usage: gui <container> <path> [curl-arg...]  -> leaves the HTTP status in $STATUS and the body in $BODY
gui() {
    local container="$1" path="$2"
    shift 2
    local out
    out="$(docker exec "${container}" curl -s --path-as-is -w '\n%{http_code}' "$@" "http://127.0.0.1:8099${path}")" || true
    BODY="${out%$'\n'*}"
    STATUS="${out##*$'\n'}"
}
INGRESS=(-H "X-Ingress-Path: /api/hassio_ingress/test")

expect_gated() { # usage: expect_gated <description>; checks STATUS/BODY of the last gui call
    if [ "${STATUS}" != "403" ] || ! grep -q "ingress_only" <<<"${BODY}"; then fail "$1: ${STATUS}"; fi
}

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

echo "==> Step 1: manifest checks"
[ "$(yget "${ADDON_DIR}/config.yaml" ports)" = "null" ] || fail "config.yaml must not publish ports"
[ "$(yget "${ADDON_DIR}/config.yaml" host_network)" = "False" ] || fail "host_network must be false"
[ "$(yget "${ADDON_DIR}/config.yaml" boot)" = "manual" ] || fail "boot must be manual"
[ "$(yget "${ADDON_DIR}/config.yaml" panel_admin)" = "False" ] || fail "panel_admin must be false"
[ ! -e "${ADDON_DIR}/.upstream.yaml" ] || fail "${ADDON_DIR}/.upstream.yaml must not exist"
echo "✓ no published port, bridge network, boot manual, panel_admin false, no .upstream.yaml"

echo "==> Step 2: docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"
echo "✓ image built from ${ADDON_DIR}"

echo "==> Step 3: start containers"
docker rm -f "${MAIN}" "${GATE}" >/dev/null 2>&1 || true
docker run -d --name "${MAIN}" -e ADMIN_UI_INGRESS_REMOTE=127.0.0.1 "${IMAGE_TAG}" >/dev/null
docker run -d --name "${GATE}" "${IMAGE_TAG}" >/dev/null
wait_for 30 "main container" bash -c "docker exec ${MAIN} curl -fsS -H 'X-Ingress-Path: /x' http://127.0.0.1:8099/api/health"
wait_for 30 "gate container" bash -c "docker exec ${GATE} curl -s -o /dev/null http://127.0.0.1:8099/api/health"
echo "✓ both containers answer"

echo "==> Step 5: ingress peer with header (override remote 127.0.0.1)"
for path in / /api/health /static/app.mjs /static/lib/api.mjs; do
    gui "${MAIN}" "${path}" "${INGRESS[@]}"
    [ "${STATUS}" = "200" ] || fail "${path} status ${STATUS} with ingress header"
done
gui "${MAIN}" /api/health "${INGRESS[@]}"
lib_version="$(tr -d '\n' <"${LIB_VERSION_FILE}")"
python3 -I - "${BODY}" "${lib_version}" <<'PY' || fail "api/health content"
import json, sys
h = json.loads(sys.argv[1])
assert h["status"] == "ok", h
assert h["lib_version"] == sys.argv[2], h
PY
grep -q '"status": "ok"' <<<"${BODY}" || fail "api/health lacks \"status\": \"ok\""
gui "${MAIN}" /static/lib/vendor/preact-htm.mjs "${INGRESS[@]}"
[ "${STATUS}" = "200" ] || fail "vendored bundle status ${STATUS}"
# hash the raw bytes inside the container (command substitution would strip a trailing newline)
served="$(docker exec "${MAIN}" sh -c "curl -s -H 'X-Ingress-Path: /x' http://127.0.0.1:8099/static/lib/vendor/preact-htm.mjs | sha256sum" | cut -d' ' -f1)"
[ "${served}" = "$(sha256sum "${VENDOR_FILE}" | cut -d' ' -f1)" ] || fail "served Preact bundle differs from the repo file"
gui "${MAIN}" /static/lib/VERSION "${INGRESS[@]}"
[ "${STATUS}" = "404" ] || fail "/static/lib/VERSION status ${STATUS}, expected 404"
echo "✓ index, health (lib ${lib_version}) and static files served; vendored Preact unchanged; VERSION hidden"

for path in / /static/app.mjs /api/health /nope; do
    gui "${MAIN}" "${path}"
    expect_gated "${path} without header"
done
echo "✓ 403 ingress_only without the X-Ingress-Path header"

echo "==> Step 6: foreign peer with header (default remote 172.30.32.2)"
for path in / /static/app.mjs /api/health /static/lib/vendor/preact-htm.mjs /nope; do
    gui "${GATE}" "${path}" "${INGRESS[@]}"
    expect_gated "${path} from foreign peer"
done
echo "✓ 403 ingress_only even with the header: the peer address is checked"

echo "==> Step 7: SIGTERM"
start="$(date +%s)"
docker stop -t 10 "${MAIN}" >/dev/null || fail "docker stop failed"
elapsed=$(($(date +%s) - start))
[ "${elapsed}" -lt 10 ] || fail "docker stop took ${elapsed} s (killed after the timeout)"
code="$(docker inspect -f '{{.State.ExitCode}}' "${MAIN}")"
[ "${code}" = "0" ] || fail "container exit code ${code} after SIGTERM, expected 0"
echo "✓ container stopped in ${elapsed} s with exit code 0"

echo ""
echo "All admin-ui scaffold verifications passed."
