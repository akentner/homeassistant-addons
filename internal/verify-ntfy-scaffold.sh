#!/usr/bin/env bash
# Verify the ntfy/ add-on tracer in a real image: build, options -> admin, ingress gate, PID 1 supervision.
# Manual invocation: bash internal/verify-ntfy-scaffold.sh
# Optional env: NTFY_VERIFY_PREFIX (container name prefix, default ntfy-verify), NTFY_VERIFY_WORK (scratch dir).
# Starts containers: do not run it in two worktrees at the same time.
set -euo pipefail

ADDON_DIR="ntfy"
IMAGE_TAG="ntfy-verify:local"
PREFIX="${NTFY_VERIFY_PREFIX:-ntfy-verify}"
MAIN="${PREFIX}-main"
GATE="${PREFIX}-gate"
SENTINEL="sentinel-pw-$RANDOM$RANDOM"
WORK="${NTFY_VERIFY_WORK:-}"

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
    # data is root-owned: remove it through the image itself
    if [ -n "${WORK}" ] && [ -d "${WORK}" ]; then
        docker run --rm -v "${WORK}:/w" --entrypoint sh "${IMAGE_TAG}" -c 'rm -rf /w/data-* /w/*.json' >/dev/null 2>&1 || true
        rmdir "${WORK}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# usage: gui <container> <path> [header-flag...]  -> prints "<status>" and leaves the body in $BODY
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

echo "==> Manifest checks"
[ "$(yget "${ADDON_DIR}/config.yaml" host_network)" = "False" ] || fail "host_network must be false"
[ "$(yget "${ADDON_DIR}/config.yaml" ports.8000/tcp)" = "null" ] || fail "ports 8000/tcp must be null"
! grep -q "listen_port" "${ADDON_DIR}/config.yaml" || fail "config.yaml must not have listen_port"
echo "✓ bridge network, port 8000 unpublished, no listen_port"

echo "==> docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"
docker run --rm --entrypoint ntfy "${IMAGE_TAG}" --version | grep -q "ntfy version $(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    || fail "ntfy --version differs from build.yaml VERSION"
echo "✓ image built, ntfy version matches"

if [ -z "${WORK}" ]; then WORK="$(mktemp -d)"; else mkdir -p "${WORK}"; fi
for name in main gate; do
    mkdir -p "${WORK}/data-${name}"
    python3 -I - "${WORK}/data-${name}/options.json" "${SENTINEL}" <<'PY'
import json, sys
json.dump({"admin_user": "admin", "admin_password": sys.argv[2], "base_url": "http://localhost"}, open(sys.argv[1], "w"))
PY
done

echo "==> Start containers"
docker rm -f "${MAIN}" "${GATE}" >/dev/null 2>&1 || true
docker run -d --name "${MAIN}" -v "${WORK}/data-main:/data" -e NTFY_INGRESS_REMOTE=127.0.0.1 "${IMAGE_TAG}" >/dev/null
docker run -d --name "${GATE}" -v "${WORK}/data-gate:/data" "${IMAGE_TAG}" >/dev/null
wait_for 60 "ntfy health" bash -c "docker exec ${MAIN} curl -fsS http://127.0.0.1:8000/v1/health | grep -q '\"healthy\":true'"
wait_for 60 "GUI health" bash -c "docker exec ${MAIN} curl -fsS -H 'X-Ingress-Path: /x' http://127.0.0.1:8099/api/health"
wait_for 60 "GUI (gate container)" bash -c "docker exec ${GATE} curl -s -o /dev/null http://127.0.0.1:8099/api/health"
echo "✓ ntfy and GUI answer"

echo "==> API through the gate"
gui "${MAIN}" /api/health "${INGRESS[@]}"
[ "${STATUS}" = "200" ] || fail "api/health status ${STATUS}"
python3 -I - "${BODY}" <<'PY' || fail "api/health content"
import json, sys
h = json.loads(sys.argv[1])
assert h["ntfy"]["healthy"] is True, h
assert h["db"]["schema_version"] == 10 and h["db"]["supported"] is True, h
PY
gui "${MAIN}" /api/users "${INGRESS[@]}"
[ "${STATUS}" = "200" ] || fail "api/users status ${STATUS}"
python3 -I - "${BODY}" <<'PY' || fail "admin missing from api/users"
import json, sys
users = {u["name"]: u for u in json.loads(sys.argv[1])["users"]}
assert users["admin"]["role"] == "admin", users
PY
echo "✓ health (schema 10) and admin user"

for path in / /static/app.mjs /static/app.css; do
    gui "${MAIN}" "${path}" "${INGRESS[@]}"
    [ "${STATUS}" = "200" ] || fail "${path} status ${STATUS} with ingress header"
done
gui "${MAIN}" /static/app.mjs "${INGRESS[@]}"
grep -q "api/health" <<<"${BODY}" || fail "app.mjs does not use relative api/health"
echo "✓ frontend shell served"

echo "==> Ingress gate"
for path in / /static/app.mjs /api/health /api/users /nope; do
    gui "${MAIN}" "${path}"
    expect_gated "${path} without header"
    gui "${GATE}" "${path}" "${INGRESS[@]}"
    expect_gated "${path} from foreign peer"
done
echo "✓ 403 ingress_only without header and from a peer other than 172.30.32.2"
for path in "/static/../etc/passwd" "/static/%2e%2e/etc/passwd" "/static/..%2f..%2fetc/passwd"; do
    gui "${MAIN}" "${path}" "${INGRESS[@]}"
    [ "${STATUS}" != "200" ] || fail "${path} answered 200"
done
echo "✓ path traversal blocked"

echo "==> Secrets"
[ "$(docker exec "${MAIN}" stat -c %a /data/server.yml)" = "600" ] || fail "server.yml is not mode 600"
docker exec "${MAIN}" grep -q "^base-url" /data/server.yml || fail "server.yml has no base-url"
docker exec "${MAIN}" grep -q "^auth-file" /data/server.yml || fail "server.yml has no auth-file"
! docker exec "${MAIN}" grep -q "${SENTINEL}" /data/server.yml || fail "password in server.yml"
! docker logs "${MAIN}" 2>&1 | grep -q "${SENTINEL}" || fail "password in container logs"
! docker exec "${MAIN}" cat /proc/1/cmdline | tr '\0' ' ' | grep -q "${SENTINEL}" || fail "password in PID 1 cmdline"
echo "✓ no password in server.yml, logs or PID 1 cmdline"

echo "==> Supervision"
docker exec "${MAIN}" pkill -f "python3 -m app.gui" || fail "GUI process not found"
wait_for 10 "GUI restart" bash -c "docker exec ${MAIN} curl -fsS -H 'X-Ingress-Path: /x' http://127.0.0.1:8099/api/health"
[ "$(docker inspect -f '{{.State.Running}}' "${MAIN}")" = "true" ] || fail "container stopped after GUI kill"
echo "✓ GUI restarted, container kept running"
docker exec "${MAIN}" pkill -x ntfy || fail "ntfy process not found"
code="$(timeout 20 docker wait "${MAIN}")" || fail "container did not stop within 20 s after ntfy was killed"
[ "${code}" != "0" ] || fail "container exited 0 after ntfy was killed"
echo "✓ ntfy death stops the container (exit ${code})"

echo ""
echo "All ntfy scaffold verifications passed."
