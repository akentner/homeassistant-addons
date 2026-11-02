#!/usr/bin/env bash
# Verify the admin-ui/ add-on in a real image: manifest, build, ingress gate by peer address, the whole demo (page,
# every view file, API CRUD, error codes, identity echo, response headers), vendored runtime and clean SIGTERM shutdown.
# Manual invocation: bash internal/verify-admin-ui-scaffold.sh
# Optional env: ADMIN_UI_VERIFY_PREFIX (container name prefix, default admin-ui-verify).
# Builds an image and starts containers: never run it in two worktrees at the same time.
set -euo pipefail

ADDON_DIR="admin-ui"
IMAGE_TAG="admin-ui-verify:local"
PREFIX="${ADMIN_UI_VERIFY_PREFIX:-admin-ui-verify}"
MAIN="${PREFIX}-main"
GATE="${PREFIX}-gate"
APP_MJS="${ADDON_DIR}/app/web/static/app.mjs"
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

echo "==> Step 5b: the whole demo through the ingress header"
JSON=(-H "Content-Type: application/json")
# jfield <json> <python expression over d>  -> prints the value; fails the run on a bad document
jfield() { python3 -I -c 'import json, sys; d = json.loads(sys.argv[1]); print(eval(sys.argv[2]))' "$1" "$2"; }

gui "${MAIN}" / "${INGRESS[@]}"
grep -q "<div id=\"app\"" <<<"${BODY}" || fail "demo page lacks the app mount point"

# every view named in the demo VIEWS list must be served as javascript, no more and no less
views="$(python3 -I - "${APP_MJS}" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
block = re.search(r"export const VIEWS = \[(.*?)\];", text, re.S).group(1)
print(" ".join(re.findall(r'id: "([a-z-]+)"', block)))
PY
)"
[ -n "${views}" ] || fail "no views found in app.mjs"
for view in ${views}; do
    ctype="$(docker exec "${MAIN}" curl -s -o /dev/null -w '%{http_code} %{content_type}' "${INGRESS[@]}" \
        "http://127.0.0.1:8099/static/views/${view}.mjs")"
    case "${ctype}" in "200 "*javascript*) ;; *) fail "views/${view}.mjs: ${ctype}" ;; esac
done
ctype="$(docker exec "${MAIN}" curl -s -o /dev/null -w '%{http_code} %{content_type}' "${INGRESS[@]}" \
    http://127.0.0.1:8099/static/lib/base.css)"
case "${ctype}" in "200 text/css"*) ;; *) fail "base.css: ${ctype}" ;; esac
echo "✓ demo page, base.css and the view files (${views}) served with the right types"

gui "${MAIN}" /api/items "${INGRESS[@]}"
[ "${STATUS}" = "200" ] || fail "GET api/items: ${STATUS}"
[ "$(jfield "${BODY}" 'sorted(i["name"] for i in d["items"])')" = "['alpha', 'beta', 'locked']" ] || fail "seed items: ${BODY}"

gui "${MAIN}" /api/items "${INGRESS[@]}" "${JSON[@]}" -X POST -d '{"name":"gamma","note":"smoke"}'
[ "${STATUS}" = "201" ] || fail "POST api/items: ${STATUS} ${BODY}"
new_id="$(jfield "${BODY}" 'd["id"]')"
gui "${MAIN}" /api/items "${INGRESS[@]}" "${JSON[@]}" -X POST -d '{"name":"gamma","note":"again"}'
{ [ "${STATUS}" = "409" ] && [ "$(jfield "${BODY}" 'd["error"]')" = "conflict" ]; } || fail "duplicate POST: ${STATUS} ${BODY}"
gui "${MAIN}" "/api/items/${new_id}" "${INGRESS[@]}" -X DELETE
{ [ "${STATUS}" = "400" ] && [ "$(jfield "${BODY}" 'd["error"]')" = "confirmation_required" ]; } || fail "DELETE without confirm: ${STATUS} ${BODY}"
gui "${MAIN}" "/api/items/${new_id}?confirm=gamma" "${INGRESS[@]}" -X DELETE
[ "${STATUS}" = "204" ] || fail "DELETE with confirm: ${STATUS} ${BODY}"
echo "✓ CRUD: seeded list, create 201, duplicate 409 conflict, delete 400 confirmation_required then 204"

gui "${MAIN}" /api/fail/teapot "${INGRESS[@]}"
{ [ "${STATUS}" = "418" ] && [ "$(jfield "${BODY}" 'd["error"]')" = "teapot" ]; } || fail "fail/teapot: ${STATUS} ${BODY}"
gui "${MAIN}" /api/fail/boom "${INGRESS[@]}"
[ "${STATUS}" = "500" ] || fail "fail/boom status ${STATUS}"
[ "$(jfield "${BODY}" 'd["error"]')" = "internal_error" ] || fail "fail/boom body: ${BODY}"
if grep -qi "secret detail\|RuntimeError\|Traceback" <<<"${BODY}"; then fail "fail/boom leaks exception text"; fi
echo "✓ error codes: 418 teapot, 500 internal_error without exception text"

gui "${MAIN}" /api/whoami "${INGRESS[@]}" -H "X-Remote-User-Name: smoke-user"
[ "$(jfield "${BODY}" 'd["user"]["name"]')" = "smoke-user" ] || fail "whoami echo: ${BODY}"
gui "${MAIN}" /api/whoami "${INGRESS[@]}"
[ "$(jfield "${BODY}" 'd["user"]')" = "None" ] || fail "whoami without identity headers: ${BODY}"
echo "✓ whoami echoes the identity header and is null without it"

hdrs="$(docker exec "${MAIN}" curl -s -o /dev/null -D - "${INGRESS[@]}" http://127.0.0.1:8099/ | tr -d '\r')"
grep -qi "^content-security-policy:.*script-src 'self'" <<<"${hdrs}" || fail "index lacks a CSP with script-src 'self'"
if grep -qi "^x-frame-options:" <<<"${hdrs}"; then fail "index carries X-Frame-Options (HA frames the page)"; fi
grep -qi "^x-content-type-options: nosniff" <<<"${hdrs}" || fail "index lacks nosniff"
echo "✓ CSP present with script-src 'self', no X-Frame-Options"

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
