#!/usr/bin/env bash
# Docker end-to-end check of the marketplace-repo-proxy management page (Phase 3): the ingress gate seen from a real
# ingress peer, the overview of a repository synced from a local, auth-checking upstream fixture (never GitHub), the
# add-on version in the top bar, a token-free GUI process, the access actions (add, URLs, revoke, rotate, protected
# system user) and the fetch sink (lighttpd access log -> forwarder -> fetchlog -> last fetch per user).
# One `✓`/`✗` line per check. Builds the add-on image locally. Manual invocation:
#   bash internal/verify-marketplace-repo-proxy-gui.sh
# Optional env: MRP_GUI_VERIFY_PREFIX (container/network name prefix, must start with mrp-, default mrp-gui-verify),
# MRP_GUI_VERIFY_WORK (scratch dir).
# Starts containers: never run it in two worktrees at the same time.
# Every network address is derived at runtime from INGRESS_REMOTE in the vendored skeleton copy.
# Container snippets are single-quoted on purpose: "$1" expands in the container, not here.
# shellcheck disable=SC2016
set -euo pipefail

ADDON_DIR="marketplace-repo-proxy"
IMAGE_TAG="marketplace-repo-proxy-gui-verify:local"
FIXTURE_TAG="marketplace-repo-proxy-gui-fixture:local"
PHASE1_IMAGE="marketplace-repo-proxy-verify:local"
PREFIX="${MRP_GUI_VERIFY_PREFIX:-mrp-gui-verify}"
NET="${PREFIX}-net"
PROXY="${PREFIX}-proxy"
UPSTREAM="${PREFIX}-upstream"
INGRESS_CLIENT="${PREFIX}-ingress"
OUTSIDE_CLIENT="${PREFIX}-outside"
PAT="SENTINEL-PAT-$RANDOM$RANDOM"
SUPERVISOR_SENTINEL="SENTINEL-SUPERVISOR-$RANDOM$RANDOM"
OVERRIDE_VAR="MRP_TEST_UPSTREAM_BASE"
PUBLIC_URL="https://addons.example.invalid"
WORK="${MRP_GUI_VERIFY_WORK:-}"
REPO="example-org/private-addons"
INGRESS_HEADER="X-Ingress-Path: /api/hassio_ingress/verify"
SKELETON_INGRESS="${ADDON_DIR}/app/web/admin_ui/ingress.py"
VERSION_FILE="/opt/marketplace-repo-proxy/BUILD_VERSION"

fail() { echo "✗ $1"; exit 1; }
ok() { echo "✓ $1"; }

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
# usage: ykeys <file> <key>  (sorted keys of a mapping, comma-separated)
ykeys() {
    python3 -I - "$1" "$2" <<'PY'
import sys, yaml
class L(yaml.SafeLoader): pass
L.add_multi_constructor("!", lambda loader, suffix, node: None)
node = yaml.load(open(sys.argv[1]), Loader=L).get(sys.argv[2])
print(",".join(sorted(node)) if isinstance(node, dict) else "")
PY
}
# usage: jget <json text> <python expression over d>  (null, true/false like JSON)
jget() {
    python3 -I -c '
import json, sys
d = json.loads(sys.stdin.read())
v = eval(sys.argv[1])
print("null" if v is None else str(v).lower() if isinstance(v, bool) else v)
' "$2" <<<"$1"
}

echo "==> (0) pre-flight"
case "${PREFIX}" in
    mrp-*) ;;
    *) fail "MRP_GUI_VERIFY_PREFIX must start with mrp- so other verify runs see this one" ;;
esac
active="$(docker ps --format '{{.Names}}' | grep -E '^mrp-' || true)"
[ -z "${active}" ] || fail "another marketplace-repo-proxy verify run is active: ${active//$'\n'/ }"
active="$(docker ps --filter ancestor=marketplace-repo-proxy-verify:local --format '{{.Names}}')"
[ -z "${active}" ] || fail "another marketplace-repo-proxy verify run is active (${PHASE1_IMAGE}): ${active//$'\n'/ }"
ok "no other marketplace-repo-proxy verify run is active"
INGRESS_IP="$(sed -n 's/^INGRESS_REMOTE = "\(.*\)"$/\1/p' "${SKELETON_INGRESS}")"
[ -n "${INGRESS_IP}" ] || fail "INGRESS_REMOTE not found in ${SKELETON_INGRESS}"
IFS=. read -r O1 O2 O3 O4 <<<"${INGRESS_IP}"
for octet in "${O1}" "${O2}" "${O3}" "${O4:-x}"; do
    if ! [[ "${octet}" =~ ^[0-9]{1,3}$ ]] || [ "${octet}" -gt 255 ]; then
        fail "INGRESS_REMOTE is not an IPv4 address"
    fi
done
if [ $((O3 % 2)) -ne 0 ] || [ "${O3}" -ge 255 ]; then
    fail "INGRESS_REMOTE does not sit in the lower half of a /23"
fi
PREFIX_LOW="${O1}.${O2}.${O3}."
PREFIX_HIGH="${O1}.${O2}.$((O3 + 1))."
SUBNET="${PREFIX_LOW}0/23"
IP_RANGE="${PREFIX_HIGH}0/24"
GATEWAY="${PREFIX_LOW}1"
docker network rm "${NET}" >/dev/null 2>&1 || true
for net in $(docker network ls -q); do
    for subnet in $(docker network inspect --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' "${net}"); do
        case "${subnet}" in
            "${PREFIX_LOW}"* | "${PREFIX_HIGH}"*)
                fail "Docker network ${net} (${subnet}) overlaps the ingress test subnet ${SUBNET}; remove it first"
                ;;
        esac
    done
done
ok "test network ${SUBNET} (ip-range ${IP_RANGE}) derived from INGRESS_REMOTE, no overlapping Docker network"

cleanup() {
    docker rm -f "${PROXY}" "${UPSTREAM}" "${INGRESS_CLIENT}" "${OUTSIDE_CLIENT}" >/dev/null 2>&1 || true
    docker network rm "${NET}" >/dev/null 2>&1 || true
    # data is root-owned: remove it through the image itself
    if [ -n "${WORK}" ] && [ -d "${WORK}" ]; then
        docker run --rm -v "${WORK}:/w" --entrypoint sh "${IMAGE_TAG}" -c 'rm -rf /w/data' >/dev/null 2>&1 || true
        rm -f "${WORK}"/needles-*
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

# /data/status.json readers (json module inside the proxy; booleans print as true/false, null as null)
field_of() { # usage: field_of <owner/repo> <key>
    docker exec "${PROXY}" python3 -I -c '
import json, sys
doc = json.load(open("/data/status.json"))
for entry in doc.get("repositories", []):
    if entry.get("repository") == sys.argv[1]:
        value = entry.get(sys.argv[2])
        print("null" if value is None else str(value).lower() if isinstance(value, bool) else value)
        break
' "$1" "$2"
}
sync_field() { # usage: sync_field <key>
    docker exec "${PROXY}" python3 -I -c '
import json, sys
value = json.load(open("/data/status.json")).get("sync", {}).get(sys.argv[1])
print("null" if value is None else value)
' "$1"
}
wait_field() { # usage: wait_field <seconds> <owner/repo> <key> <expected>
    local limit="$1" repo="$2" key="$3" want="$4" got="" i
    for ((i = 0; i < limit; i++)); do
        got="$(field_of "${repo}" "${key}" 2>/dev/null || true)"
        [ "${got}" = "${want}" ] && return 0
        sleep 1
    done
    fail "${repo}: status.json ${key} is '${got}' after ${limit} s, expected '${want}'"
}

# GUI request from a client container. Sets GUI_CODE, GUI_HEADERS and GUI_BODY.
# usage: gui_call <client> <path> [curl args...]
gui_call() {
    local client="$1" path="$2"
    shift 2
    GUI_CODE="$(docker exec "${client}" curl -s -D /tmp/gui-headers -o /tmp/gui-body -w '%{http_code}' "$@" \
        "http://${PROXY}:8099/${path}" || true)"
    GUI_HEADERS="$(docker exec "${client}" cat /tmp/gui-headers 2>/dev/null | tr -d '\r' || true)"
    GUI_BODY="$(docker exec "${client}" cat /tmp/gui-body 2>/dev/null || true)"
}
# usage: ingress_get <path>  (ingress client with the header; fails unless 200)
ingress_get() {
    gui_call "${INGRESS_CLIENT}" "$1" -H "${INGRESS_HEADER}"
    [ "${GUI_CODE}" = "200" ] || fail "ingress GET $1: HTTP ${GUI_CODE}, expected 200"
}
no_store() { grep -qix 'cache-control: no-store' <<<"${GUI_HEADERS}"; }

echo "==> (1) static checks"
CONFIG="${ADDON_DIR}/config.yaml"
S6="${ADDON_DIR}/rootfs/etc/s6-overlay"
[ "$(yget "${CONFIG}" ingress)" = "True" ] || fail "config.yaml: ingress is not true"
[ "$(yget "${CONFIG}" ingress_port)" = "8099" ] || fail "config.yaml: ingress_port is not 8099"
ok "config.yaml: ingress true, ingress_port 8099"
[ "$(ykeys "${CONFIG}" ports)" = "8080/tcp" ] || fail "config.yaml: ports lists more than 8080/tcp (8099 must stay unpublished)"
ok "config.yaml: ports lists only 8080/tcp (8099 never published)"
[ "$(head -n 1 "${S6}/s6-rc.d/gui/run")" = "#!/bin/sh" ] || fail "gui/run does not start with #!/bin/sh"
grep -qF 'python3 -m app.gui' "${S6}/s6-rc.d/gui/run" || fail "gui/run does not start python3 -m app.gui"
ok "gui/run: #!/bin/sh (no container environment), runs python3 -m app.gui"
[ -f "${S6}/user-bundles.d/user/contents.d/gui" ] || fail "gui is not in the user bundle"
ok "gui is listed in the user bundle"
[ "$(grep -cx 'ARG BUILD_VERSION' "${ADDON_DIR}/Dockerfile")" = "1" ] || fail "Dockerfile: not exactly one ARG BUILD_VERSION"
ok "Dockerfile declares ARG BUILD_VERSION once"
ADDON_VERSION="$(yget "${CONFIG}" version)"
[[ "${ADDON_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9]+$ ]] || fail "config.yaml version '${ADDON_VERSION}' is not X.Y.Z-N"
ok "add-on version ${ADDON_VERSION} (config.yaml)"

echo "==> (2) docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    --build-arg BUILD_VERSION="${ADDON_VERSION}" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"
ok "image built with BUILD_VERSION=${ADDON_VERSION}"
docker build -t "${FIXTURE_TAG}" - >/dev/null <<EOF
FROM ${IMAGE_TAG}
RUN apk add --no-cache lighttpd-mod_auth
EOF
ok "fixture image built (lighttpd-mod_auth)"

echo "==> (3) network and upstream fixture"
docker rm -f "${PROXY}" "${UPSTREAM}" "${INGRESS_CLIENT}" "${OUTSIDE_CLIENT}" >/dev/null 2>&1 || true
docker network create --subnet "${SUBNET}" --ip-range "${IP_RANGE}" --gateway "${GATEWAY}" "${NET}" >/dev/null
# The PAT is the fixture's basic-auth password; it reaches only the fixture container.
docker run -d --name "${UPSTREAM}" --network "${NET}" -e FIXTURE_PAT="${PAT}" --entrypoint sh "${FIXTURE_TAG}" -c '
set -e
repo=/srv/upstream/example-org/private-addons.git
mkdir -p /srv/upstream/example-org
git init -q --bare --initial-branch=main "$repo"
git init -q --initial-branch=main /tmp/private-addons
cd /tmp/private-addons
printf "name: GUI verify fixture\n" > repository.yaml
mkdir -p demo
printf "name: Demo\nslug: demo\nversion: \"1.0.0\"\n" > demo/config.yaml
git add repository.yaml demo/config.yaml
git -c user.name=fixture -c user.email=fixture commit -q -m "fixture: initial"
git push -q "$repo" main
cd /
git config --system --add safe.directory "/srv/upstream/*"
printf "x-access-token:%s\n" "$FIXTURE_PAT" > /etc/lighttpd/upstream.users
chmod 0644 /etc/lighttpd/upstream.users
cat > /etc/lighttpd/upstream.conf <<CONF
server.modules = ("mod_auth", "mod_authn_file", "mod_alias", "mod_setenv", "mod_cgi")
server.document-root = "/var/empty"
server.port = 8080
server.username = "lighttpd"
server.groupname = "lighttpd"
server.pid-file = ""
auth.backend = "plain"
auth.backend.plain.userfile = "/etc/lighttpd/upstream.users"
auth.require = ("/" => ("method" => "basic", "realm" => "upstream", "require" => "valid-user"))
alias.url = ("/" => "/usr/libexec/git-core/git-http-backend/")
cgi.assign = ("" => "")
setenv.set-environment = ("GIT_PROJECT_ROOT" => "/srv/upstream", "GIT_HTTP_EXPORT_ALL" => "1")
CONF
exec lighttpd -D -f /etc/lighttpd/upstream.conf
' >/dev/null
UPSTREAM_REFS="http://localhost:8080/${REPO}.git/info/refs?service=git-upload-pack"
wait_for 30 "upstream fixture" docker exec "${UPSTREAM}" curl -4 -s -o /dev/null "${UPSTREAM_REFS}"
code="$(docker exec "${UPSTREAM}" curl -4 -s -o /dev/null -w '%{http_code}' "${UPSTREAM_REFS}")"
[ "${code}" = "401" ] || fail "upstream without credentials returned ${code}, expected 401"
ok "upstream fixture requires the PAT (401 without it)"
FIXTURE_HEAD="$(docker exec "${UPSTREAM}" git --git-dir="/srv/upstream/${REPO}.git" rev-parse refs/heads/main)"
[[ "${FIXTURE_HEAD}" =~ ^[0-9a-f]{40}$ ]] || fail "fixture main is not a commit"
ok "upstream ${REPO} main at ${FIXTURE_HEAD:0:12}"

echo "==> (4) proxy and clients"
if [ -z "${WORK}" ]; then WORK="$(mktemp -d)"; else mkdir -p "${WORK}"; fi
mkdir -p "${WORK}/data"
python3 -I - "${PAT}" "${PUBLIC_URL}" "${REPO}" >"${WORK}/data/options.json" <<'PY'
import json, sys
pat, public_url, repo = sys.argv[1:4]
print(json.dumps({
    "github_token": pat,
    "sync_interval": 5,
    "public_url": public_url,
    "repositories": [{"repository": repo}],
    "register_local": True,
    "api_enabled": False,
    "log_level": "debug",
}))
PY
# The ingress client takes the ingress address first; auto-assigned addresses come from the upper /24 only.
docker run -d --name "${INGRESS_CLIENT}" --network "${NET}" --ip "${INGRESS_IP}" --entrypoint sh "${IMAGE_TAG}" \
    -c 'exec sleep infinity' >/dev/null
docker run -d --name "${PROXY}" --hostname "${PROXY}" --network "${NET}" \
    -v "${WORK}/data:/data" \
    -e "${OVERRIDE_VAR}=http://${UPSTREAM}:8080" \
    -e "SUPERVISOR_TOKEN=${SUPERVISOR_SENTINEL}" \
    "${IMAGE_TAG}" >/dev/null
docker run -d --name "${OUTSIDE_CLIENT}" --network "${NET}" --entrypoint sh "${IMAGE_TAG}" \
    -c 'exec sleep infinity' >/dev/null
ip_of() { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1"; }
[ "$(ip_of "${INGRESS_CLIENT}")" = "${INGRESS_IP}" ] || fail "ingress client did not get the ingress address"
for c in "${OUTSIDE_CLIENT}" "${PROXY}"; do
    [ "$(ip_of "${c}")" != "${INGRESS_IP}" ] || fail "${c} got the ingress address"
done
ok "ingress client holds the ingress address; outside client and proxy do not"
wait_field 90 "${REPO}" status ok
ok "status.json: ${REPO} ok (real sync against the fixture)"
wait_for 30 "management page" docker exec "${INGRESS_CLIENT}" curl -sf -o /dev/null -H "${INGRESS_HEADER}" \
    "http://${PROXY}:8099/"
ok "gui service answers on 8099"

echo "==> (5) ingress gate"
gui_call "${OUTSIDE_CLIENT}" "" -H "${INGRESS_HEADER}"
[ "${GUI_CODE}" = "403" ] || fail "outside client with header: HTTP ${GUI_CODE}, expected 403"
[ "$(jget "${GUI_BODY}" 'd.get("error")')" = "ingress_only" ] || fail "outside client: body is not ingress_only"
ok "outside client with X-Ingress-Path: 403 ingress_only"
gui_call "${OUTSIDE_CLIENT}" "api/overview" -H "${INGRESS_HEADER}"
[ "${GUI_CODE}" = "403" ] || fail "outside client api/overview: HTTP ${GUI_CODE}, expected 403"
ok "outside client api/overview: 403"
gui_call "${INGRESS_CLIENT}" ""
[ "${GUI_CODE}" = "403" ] || fail "ingress client without header: HTTP ${GUI_CODE}, expected 403"
gui_call "${INGRESS_CLIENT}" "api/overview"
[ "${GUI_CODE}" = "403" ] || fail "ingress client api/overview without header: HTTP ${GUI_CODE}, expected 403"
ok "ingress client without X-Ingress-Path: 403"
code="$(docker exec "${PROXY}" curl -4 -s -o /dev/null -w '%{http_code}' -H "${INGRESS_HEADER}" \
    "http://localhost:8099/api/overview" || true)"
[ "${code}" = "403" ] || fail "request from inside the proxy container: HTTP ${code}, expected 403"
ok "request from inside the proxy container with X-Ingress-Path: 403"

echo "==> (6) page and overview through ingress"
for path in "" static/app.mjs static/views/repositories.mjs static/vendor/admin-ui/base.css; do
    ingress_get "${path}"
done
ok "ingress client: index, app.mjs, views/repositories.mjs and base.css 200"
ingress_get "api/overview"
no_store || fail "api/overview lacks Cache-Control: no-store"
[ "$(jget "${GUI_BODY}" 'd["status_available"]')" = "true" ] || fail "api/overview: status_available is not true"
[ "$(jget "${GUI_BODY}" 'd["repositories"][0]["repository"]')" = "${REPO}" ] || fail "api/overview: first row is not ${REPO}"
[ "$(jget "${GUI_BODY}" 'd["repositories"][0]["status"]')" = "ok" ] || fail "api/overview: status is not ok"
# status.json stores the 12-character short SHA of the served commit (Phase 1 contract)
[ "$(jget "${GUI_BODY}" 'd["repositories"][0]["head"]')" = "${FIXTURE_HEAD:0:12}" ] || fail "api/overview: head differs"
[ "$(jget "${GUI_BODY}" '"demo" in d["repositories"][0]["addons"]')" = "true" ] || fail "api/overview: demo missing"
[ "$(jget "${GUI_BODY}" 'd["repositories"][0]["registration"]')" = "null" ] || fail "api/overview: registration set"
ok "api/overview: ${REPO} ok, head ${FIXTURE_HEAD:0:12}, add-on demo, no-store"
if grep -qF -- "${PAT}" <<<"${GUI_BODY}"; then fail "PAT in api/overview"; fi
ok "api/overview holds no PAT"

echo "==> (7) version in the top bar"
image_version="$(docker exec "${PROXY}" cat "${VERSION_FILE}")"
[ "${image_version}" = "${ADDON_VERSION}" ] || fail "image ${VERSION_FILE} is '${image_version}', expected ${ADDON_VERSION}"
ok "image ${VERSION_FILE} holds ${ADDON_VERSION}"
ingress_get "api/meta"
no_store || fail "api/meta lacks Cache-Control: no-store"
[ "$(jget "${GUI_BODY}" 'd["version"]')" = "${ADDON_VERSION}" ] || fail "api/meta version differs from ${ADDON_VERSION}"
ok "top bar version: api/meta reports the config.yaml version"

echo "==> (8) GUI process environment"
GUI_PID="$(docker exec "${PROXY}" pgrep -f 'python3 -m app[.]gui' | head -n 1)"
SYNC_PID="$(docker exec "${PROXY}" pgrep -f 'python3 -m app[.]sync' | head -n 1)"
if [ -z "${GUI_PID}" ] || [ -z "${SYNC_PID}" ]; then fail "app.gui or app.sync process missing"; fi
# needles reach the container on stdin only, never in an argv
docker exec -i "${PROXY}" sh -c 'cat > /tmp/needles-pat' <<<"${PAT}"
docker exec -i "${PROXY}" sh -c 'cat > /tmp/needles-supervisor' <<<"${SUPERVISOR_SENTINEL}"
environ_has() { # usage: environ_has <needles file> <pid>; exit 0 hit, 1 none, 2 unreadable
    docker exec --privileged "${PROXY}" sh -c 'test -r "/proc/$2/environ" || exit 2; grep -qaF -f "$1" "/proc/$2/environ"' \
        sh "$1" "$2"
}
rc=0
environ_has /tmp/needles-pat "${GUI_PID}" || rc=$?
[ "${rc}" = "1" ] || fail "GUI environment: PAT found or unreadable (rc ${rc})"
rc=0
environ_has /tmp/needles-supervisor "${GUI_PID}" || rc=$?
[ "${rc}" = "1" ] || fail "GUI environment: SUPERVISOR_TOKEN sentinel found or unreadable (rc ${rc})"
rc=0
environ_has /tmp/needles-supervisor "${SYNC_PID}" || rc=$?
[ "${rc}" = "0" ] || fail "positive control: SUPERVISOR_TOKEN sentinel not seen in the sync environment (rc ${rc})"
ok "GUI environment holds neither the PAT nor SUPERVISOR_TOKEN (positive control: sentinel found in sync's)"
docker exec "${PROXY}" rm -f /tmp/needles-pat /tmp/needles-supervisor

ok "tracer: overview through ingress end to end"

echo "==> (9) Sync now"
SYNC_BEFORE="$(sync_field last_started)"
[ "$(sync_field state)" = "idle" ] || fail "sync is not idle before Sync now"
gui_call "${INGRESS_CLIENT}" "api/sync" -X POST -H "${INGRESS_HEADER}"
[ "${GUI_CODE}" = "400" ] || fail "POST api/sync without body: HTTP ${GUI_CODE}, expected 400"
[ "$(jget "${GUI_BODY}" 'd.get("error")')" = "bad_request" ] || fail "POST api/sync without body: not bad_request"
ok "POST api/sync without body: 400 bad_request"
gui_call "${INGRESS_CLIENT}" "api/sync" -X POST -H "${INGRESS_HEADER}" -H 'Content-Type: application/json' -d '{}'
[ "${GUI_CODE}" = "202" ] || fail "POST api/sync with {}: HTTP ${GUI_CODE}, expected 202"
[ "$(jget "${GUI_BODY}" 'd["requested"]')" = "true" ] || fail "POST api/sync with {}: requested is not true"
ok "POST api/sync with {}: 202 requested"
sync_requested_cycle() {
    [ "$(sync_field reason)" = "request" ] && [ "$(sync_field last_started)" != "${SYNC_BEFORE}" ]
}
wait_for 30 "a sync cycle with reason request" sync_requested_cycle
ok "status.json: sync.reason request, last_started advanced past ${SYNC_BEFORE}"
echo "==> (10) Access: add through the GUI"
# Hashes the GUI hands out go into a 0600 needles file on the host; logs and list bodies are checked against it.
NEEDLES_HASH="${WORK}/needles-hash"
(umask 077 && : >"${NEEDLES_HASH}")
# usage: gui_json <method> <path> <json body>  (ingress client with the header, JSON body)
gui_json() {
    gui_call "${INGRESS_CLIENT}" "$2" -X "$1" -H "${INGRESS_HEADER}" -H 'Content-Type: application/json' -d "$3"
}
# usage: expect_error <code> <error> <label>  (checks GUI_CODE and the error field of GUI_BODY)
expect_error() {
    [ "${GUI_CODE}" = "$1" ] || fail "$3: HTTP ${GUI_CODE}, expected $1"
    [ "$(jget "${GUI_BODY}" 'd.get("error")')" = "$2" ] || fail "$3: error is not $2"
    ok "$3: $1 $2"
}
ingress_get "static/views/access.mjs"
ok "ingress client: views/access.mjs 200"
gui_json POST "api/access/${REPO}" '{"user":"carol"}'
[ "${GUI_CODE}" = "201" ] || fail "POST api/access/${REPO} carol: HTTP ${GUI_CODE}, expected 201"
no_store || fail "add response lacks Cache-Control: no-store"
URL_CAROL="$(jget "${GUI_BODY}" 'd["urls"]["internal"]')"
PUBLIC_CAROL="$(jget "${GUI_BODY}" 'd["urls"].get("public")')"
HASH_CAROL="${URL_CAROL##*/}"
printf '%s\n' "${HASH_CAROL}" >>"${NEEDLES_HASH}"
if ! [[ "${HASH_CAROL}" =~ ^[0-9a-f]{32}$ ]] || [ "${URL_CAROL}" != "http://${PROXY}:8080/repo/${REPO}/${HASH_CAROL}" ]; then
    fail "add carol: urls.internal is not http://${PROXY}:8080/repo/${REPO}/<32 hex>"
fi
[ "${PUBLIC_CAROL}" = "${PUBLIC_URL}/repo/${REPO}/${HASH_CAROL}" ] || fail "add carol: urls.public is not ${PUBLIC_URL}/repo/${REPO}/<same hash>"
[ "$(jget "${GUI_BODY}" 'd["source"]')" = "gui" ] || fail "add carol: source is not gui"
ok "POST api/access/${REPO} carol: 201, source gui, internal URL on ${PROXY}:8080 and public URL with the same new hash"
docker exec -w /tmp "${OUTSIDE_CLIENT}" sh -ec 'rm -rf carol; git clone -q --depth 1 "$1" carol; test -f carol/repository.yaml' \
    sh "${URL_CAROL}" || fail "git clone --depth 1 of carol's GUI URL failed or repository.yaml missing"
ok "outside client clones carol's GUI-added store URL at once (repository.yaml present)"
ingress_get "api/access"
no_store || fail "api/access lacks Cache-Control: no-store"
[ "$(jget "${GUI_BODY}" '[(u["source"], u["protected"]) for r in d["repositories"] if r["repository"] == "'"${REPO}"'" for u in r["users"] if u["user"] == "carol"]')" = "[('gui', False)]" ] \
    || fail "api/access: carol is not listed once with source gui and protected false"
if grep -Eq '[0-9a-f]{32}' <<<"${GUI_BODY}"; then fail "api/access holds a 32-hex run"; fi
if grep -qF 'http' <<<"${GUI_BODY}"; then fail "api/access holds a URL"; fi
ok "api/access lists carol (source gui, not protected) without any hash or URL"
ingress_get "api/access/${REPO}/carol/urls"
no_store || fail "api/access/${REPO}/carol/urls lacks Cache-Control: no-store"
[ "$(jget "${GUI_BODY}" 'd["internal"]')" = "${URL_CAROL}" ] || fail "URL route: internal URL differs from the add response"
ok "GET api/access/${REPO}/carol/urls: 200, same internal URL, no-store"
gui_json POST "api/access/${REPO}" '{"user":"carol"}'
expect_error 409 user_exists "second add of carol"
gui_json POST "api/access/${REPO}" '{"user":"local"}'
expect_error 400 user_reserved "add of the reserved label local"
gui_json POST "api/access/example-org/unknown" '{"user":"carol"}'
expect_error 404 repository_unknown "add to the unconfigured repository example-org/unknown"
docker logs "${PROXY}" 2>&1 | grep -qF "gui: added user carol to ${REPO}" || fail "add-on log lacks the add line for carol"
if docker logs "${PROXY}" 2>&1 | grep -qF -f "${NEEDLES_HASH}"; then fail "an access hash appears in the add-on log"; fi
ok "add-on log names carol and ${REPO} but holds no access hash"
echo "==> (11) Access: revoke, rotate, system user"
# usage: refs_code <store URL>  (HTTP status of the smart info/refs request from the outside client)
refs_code() {
    docker exec "${OUTSIDE_CLIENT}" curl -s -o /dev/null -w '%{http_code}' "$1/info/refs?service=git-upload-pack" || true
}
# Phase 2's system user, seeded through the real store inside the proxy (the GUI must never touch it)
HASH_LOCAL="$(docker exec -w /opt/marketplace-repo-proxy "${PROXY}" python3 -c '
from app.access import AccessStore
from app.options import load_options
from app.paths import Paths
paths = Paths.default()
options = load_options(paths.options_file)
entry = AccessStore(paths).add("example-org/private-addons", "local", source="system", specs=options.repositories)
print(entry["hash"])
')"
printf '%s\n' "${HASH_LOCAL}" >>"${NEEDLES_HASH}"
[[ "${HASH_LOCAL}" =~ ^[0-9a-f]{32}$ ]] || fail "seeding the system user local failed"
URL_LOCAL="http://${PROXY}:8080/repo/${REPO}/${HASH_LOCAL}"
[ "$(refs_code "${URL_LOCAL}")" = "200" ] || fail "system user local: info/refs is not 200 after seeding"
ok "system user local seeded through AccessStore (source system), its URL answers 200"
gui_json POST "api/access/${REPO}" '{"user":"dave"}'
[ "${GUI_CODE}" = "201" ] || fail "POST api/access/${REPO} dave: HTTP ${GUI_CODE}, expected 201"
URL_DAVE="$(jget "${GUI_BODY}" 'd["urls"]["internal"]')"
printf '%s\n' "${URL_DAVE##*/}" >>"${NEEDLES_HASH}"
[ "$(refs_code "${URL_DAVE}")" = "200" ] || fail "dave: info/refs is not 200 after the add"
ok "dave added through the GUI, info/refs 200"
gui_call "${INGRESS_CLIENT}" "api/access/${REPO}/dave" -X DELETE -H "${INGRESS_HEADER}"
expect_error 400 confirmation_required "DELETE dave without body"
gui_json DELETE "api/access/${REPO}/dave" '{"confirm":"Dave"}'
expect_error 400 confirmation_required "DELETE dave with confirm Dave"
[ "$(refs_code "${URL_DAVE}")" = "200" ] || fail "dave lost access after a refused revoke"
gui_json DELETE "api/access/${REPO}/dave" '{"confirm":"dave"}'
[ "${GUI_CODE}" = "204" ] || fail "DELETE dave with confirm dave: HTTP ${GUI_CODE}, expected 204"
[ "$(refs_code "${URL_DAVE}")" = "404" ] || fail "dave's URL still answers after the revoke"
ok "DELETE dave with the exact confirm: 204, dave's info/refs 404 at once"
gui_json DELETE "api/access/${REPO}/dave" '{"confirm":"dave"}'
expect_error 404 user_unknown "second revoke of dave"
gui_json POST "api/access/${REPO}/carol/rotate" '{"confirm":"Carol"}'
expect_error 400 confirmation_required "rotate carol with confirm Carol"
gui_json POST "api/access/${REPO}/carol/rotate" '{"confirm":"carol"}'
[ "${GUI_CODE}" = "200" ] || fail "rotate carol: HTTP ${GUI_CODE}, expected 200"
URL_CAROL_NEW="$(jget "${GUI_BODY}" 'd["urls"]["internal"]')"
printf '%s\n' "${URL_CAROL_NEW##*/}" >>"${NEEDLES_HASH}"
if [ "${URL_CAROL_NEW}" = "${URL_CAROL}" ] || ! [[ "${URL_CAROL_NEW##*/}" =~ ^[0-9a-f]{32}$ ]]; then
    fail "rotate carol: no new 32-hex hash in the response"
fi
[ "$(jget "${GUI_BODY}" 'd["source"]')" = "gui" ] || fail "rotate carol: source is not kept"
[ "$(refs_code "${URL_CAROL}")" = "404" ] || fail "carol's old URL still answers after the rotation"
ok "rotate carol: 200, new hash, source kept, old URL info/refs 404 at once"
docker exec -w /tmp "${OUTSIDE_CLIENT}" sh -ec 'rm -rf carol-new; git clone -q --depth 1 "$1" carol-new; test -f carol-new/repository.yaml' \
    sh "${URL_CAROL_NEW}" || fail "git clone of carol's rotated URL failed"
ok "outside client clones carol's rotated URL at once"
gui_json DELETE "api/access/${REPO}/local" '{"confirm":"local"}'
expect_error 409 protected "DELETE of the system user local"
gui_json POST "api/access/${REPO}/local/rotate" '{"confirm":"local"}'
expect_error 409 protected "rotate of the system user local"
[ "$(refs_code "${URL_LOCAL}")" = "200" ] || fail "system user local lost access"
ingress_get "api/access"
[ "$(jget "${GUI_BODY}" '[(u["user"], u["source"], u["protected"]) for r in d["repositories"] for u in r["users"]]')" = "[('carol', 'gui', False), ('local', 'system', True)]" ] \
    || fail "api/access: users are not exactly carol (gui) and local (system, protected)"
ok "system user local untouched (URL 200) and listed as protected; dave gone"
if grep -qF -f "${NEEDLES_HASH}" <<<"${GUI_BODY}"; then fail "api/access holds an access hash"; fi
ingress_get "api/overview"
if grep -qF -f "${NEEDLES_HASH}" <<<"${GUI_BODY}"; then fail "api/overview holds an access hash"; fi
ok "api/access and api/overview hold no access hash"
LOGS="$(docker logs "${PROXY}" 2>&1)"
grep -qF "gui: rotated user carol of ${REPO}" <<<"${LOGS}" || fail "add-on log lacks the rotate line for carol"
grep -qF "gui: revoked user dave from ${REPO}" <<<"${LOGS}" || fail "add-on log lacks the revoke line for dave"
if grep -qF -f "${NEEDLES_HASH}" <<<"${LOGS}"; then fail "an access hash appears in the add-on log"; fi
if grep -Eq '/(repo|access)/[^[:space:]]*[0-9a-f]{32}' <<<"${LOGS}"; then fail "the add-on log holds a 32-hex run after /repo/ or /access/"; fi
ok "add-on log names the actions but holds no access hash and no 32-hex run after /repo/ or /access/"
echo "==> (12) Fetch sink: last fetch recorded"
gui_json POST "api/access/${REPO}" '{"user":"erin"}'
[ "${GUI_CODE}" = "201" ] || fail "POST api/access/${REPO} erin: HTTP ${GUI_CODE}, expected 201"
URL_ERIN="$(jget "${GUI_BODY}" 'd["urls"]["internal"]')"
printf '%s\n' "${URL_ERIN##*/}" >>"${NEEDLES_HASH}"
[[ "${URL_ERIN##*/}" =~ ^[0-9a-f]{32}$ ]] || fail "add erin: urls.internal does not end in a 32-hex hash"
ok "erin added through the GUI"
# usage: clone_as <name> <store URL>  (git clone --depth 1 from the outside client)
clone_as() {
    docker exec -w /tmp "${OUTSIDE_CLIENT}" sh -ec 'rm -rf "$1"; git clone -q --depth 1 "$2" "$1"; test -f "$1/repository.yaml"' \
        sh "$1" "$2"
}
# the GUI shows a fetch only when it is strictly newer than created (second resolution, section 13)
sleep 2
clone_as erin "${URL_ERIN}" || fail "git clone --depth 1 of erin's GUI URL failed"
ok "outside client clones erin's store URL"
# usage: last_fetch_of <user>  (last_fetch of <user> for REPO in /data/last-fetch.json, parsed on the host; "" if none)
last_fetch_of() {
    docker exec "${PROXY}" cat /data/last-fetch.json | python3 -I -c '
import json, sys
doc = json.load(sys.stdin)
for entry in doc.get("entries", []):
    if entry.get("repository") == sys.argv[1] and entry.get("user") == sys.argv[2]:
        print(entry.get("last_fetch") or "")
        break
' "${REPO}" "$1"
}
erin_recorded() { [[ "$(last_fetch_of erin)" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]; }
wait_for 15 "erin's last fetch in /data/last-fetch.json" erin_recorded
ok "/data/last-fetch.json records erin's last fetch of ${REPO} ($(last_fetch_of erin))"
LOGS="$(docker logs "${PROXY}" 2>&1)"
grep -qF "fetch: erin → ${REPO}" <<<"${LOGS}" || fail "add-on log lacks 'fetch: erin → ${REPO}'"
ok "add-on log: fetch: erin → ${REPO}"
LAST_FETCH_DOC="$(docker exec "${PROXY}" cat /data/last-fetch.json)"
if grep -qF -f "${NEEDLES_HASH}" <<<"${LAST_FETCH_DOC}"; then fail "an access hash appears in /data/last-fetch.json"; fi
if grep -qF -f "${NEEDLES_HASH}" <<<"${LOGS}"; then fail "an access hash appears in the add-on log"; fi
ok "/data/last-fetch.json and the add-on log hold no access hash"
echo "==> (13) Fetch sink: last fetch in the GUI"
TS_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'
# usage: erin_last_fetch  (erin's last_fetch for REPO in the current GUI_BODY of GET api/access; "missing" if absent)
erin_last_fetch() {
    jget "${GUI_BODY}" 'next((u.get("last_fetch") for r in d["repositories"] if r["repository"] == "'"${REPO}"'" for u in r["users"] if u["user"] == "erin"), "missing")'
}
ingress_get "api/access"
ERIN_SHOWN="$(erin_last_fetch)"
[[ "${ERIN_SHOWN}" =~ ${TS_RE} ]] || fail "GET api/access: erin's last_fetch is '${ERIN_SHOWN}', expected a timestamp"
ok "GET api/access shows erin's last fetch (${ERIN_SHOWN})"
gui_json POST "api/access/${REPO}/erin/rotate" '{"confirm":"erin"}'
[ "${GUI_CODE}" = "200" ] || fail "rotate erin: HTTP ${GUI_CODE}, expected 200"
URL_ERIN_NEW="$(jget "${GUI_BODY}" 'd["urls"]["internal"]')"
printf '%s\n' "${URL_ERIN_NEW##*/}" >>"${NEEDLES_HASH}"
if [ "${URL_ERIN_NEW}" = "${URL_ERIN}" ] || ! [[ "${URL_ERIN_NEW##*/}" =~ ^[0-9a-f]{32}$ ]]; then
    fail "rotate erin: no new 32-hex hash in the response"
fi
ingress_get "api/access"
[ "$(erin_last_fetch)" = "null" ] || fail "after the rotation erin's last_fetch is '$(erin_last_fetch)', expected null"
ok "after rotating erin, GET api/access shows erin's last_fetch null (never) until the new URL is used"
# the record must be strictly newer than the rotation's created (second resolution)
sleep 2
clone_as erin-new "${URL_ERIN_NEW}" || fail "git clone --depth 1 of erin's rotated URL failed"
ok "outside client clones erin's rotated URL"
erin_fetch_lines() { docker logs "${PROXY}" 2>&1 | grep -cF "fetch: erin → ${REPO}" || true; }
erin_shown_again() {
    gui_call "${INGRESS_CLIENT}" "api/access" -H "${INGRESS_HEADER}"
    [ "${GUI_CODE}" = "200" ] && [[ "$(erin_last_fetch)" =~ ${TS_RE} ]] && [ "$(erin_fetch_lines)" -ge 2 ]
}
wait_for 15 "erin's last fetch after the rotation" erin_shown_again
ok "erin's last fetch after the rotation: GET api/access shows $(erin_last_fetch); 'fetch: erin → ${REPO}' logged $(erin_fetch_lines) times"
echo "==> (14) Fetch sink: privileges, modes, hygiene, outage"
# usage: pid_of <pgrep -f pattern>  (first matching pid inside the proxy, "" if none)
pid_of() { docker exec "${PROXY}" pgrep -f "$1" | head -n 1 || true; }
FWD_PID="$(pid_of 'app/fetchsink[.]py')"
FETCHLOG_PID="$(pid_of 'python3 -m app[.]fetchlog')"
if [ -z "${FWD_PID}" ] || [ -z "${FETCHLOG_PID}" ]; then fail "forwarder (app/fetchsink.py) or fetchlog process missing"; fi
[ "$(docker exec "${PROXY}" stat -c %U "/proc/${FWD_PID}")" = "lighttpd" ] || fail "the forwarder does not run as lighttpd"
ok "forwarder app/fetchsink.py runs as lighttpd (pid ${FWD_PID})"
[ "$(docker exec "${PROXY}" stat -c %U "/proc/${FETCHLOG_PID}")" = "root" ] || fail "fetchlog does not run as root"
ok "fetchlog (python3 -m app.fetchlog) runs as root (pid ${FETCHLOG_PID})"
# usage: mode_is <path> <stat format> <expected>
mode_is() { [ "$(docker exec "${PROXY}" stat -c "$2" "$1")" = "$3" ]; }
mode_is /run/mrp-fetch '%a %U:%G' '710 root:lighttpd' || fail "/run/mrp-fetch is not 710 root:lighttpd"
mode_is /run/mrp-fetch/fetch.sock '%a %U:%G' '620 root:lighttpd' || fail "/run/mrp-fetch/fetch.sock is not 620 root:lighttpd"
ok "socket directory /run/mrp-fetch 710 root:lighttpd, fetch.sock 620 root:lighttpd"
mode_is /data %a 700 || fail "/data is not 700"
mode_is /data/access.json %a 600 || fail "/data/access.json is not 600"
mode_is /data/last-fetch.json %a 600 || fail "/data/last-fetch.json is not 600"
mode_is /srv/git/access %a 711 || fail "/srv/git/access is not 711"
ok "/data 700, access.json 600, last-fetch.json 600, /srv/git/access 711 (no permission widened)"
GUI_PID="$(pid_of 'python3 -m app[.]gui')"
SYNC_PID="$(pid_of 'python3 -m app[.]sync')"
if [ -z "${GUI_PID}" ] || [ -z "${SYNC_PID}" ]; then fail "app.gui or app.sync process missing"; fi
docker exec -i "${PROXY}" sh -c 'umask 077; cat > /tmp/needles-pat' <<<"${PAT}"
docker exec -i "${PROXY}" sh -c 'umask 077; cat > /tmp/needles-supervisor' <<<"${SUPERVISOR_SENTINEL}"
for pid in "${FWD_PID}" "${GUI_PID}"; do
    for needles in /tmp/needles-pat /tmp/needles-supervisor; do
        rc=0
        environ_has "${needles}" "${pid}" || rc=$?
        [ "${rc}" = "1" ] || fail "environment of pid ${pid}: ${needles#/tmp/needles-} needle found or unreadable (rc ${rc})"
    done
done
rc=0
environ_has /tmp/needles-supervisor "${SYNC_PID}" || rc=$?
[ "${rc}" = "0" ] || fail "positive control: SUPERVISOR_TOKEN sentinel not seen in the sync environment (rc ${rc})"
ok "forwarder and GUI environments hold neither the PAT nor SUPERVISOR_TOKEN (positive control: sentinel in sync's)"
docker exec "${PROXY}" rm -f /tmp/needles-pat /tmp/needles-supervisor
# carol (before and after rotation), local, dave, erin (before and after rotation)
[ "$(grep -cE '^[0-9a-f]{32}$' "${NEEDLES_HASH}")" = "6" ] || fail "the needles file does not hold the 6 hashes of this run"
[ "$(stat -c %a "${NEEDLES_HASH}")" = "600" ] || fail "the needles file is not mode 600"
ok "needles file holds all 6 full hashes used by this run (mode 600)"
# usage: no_leak_in_logs  (docker logs, stdout and stderr: no needle, no 32-hex run after /repo/ or /access/, no raw
# access-log record)
no_leak_in_logs() {
    LOGS="$(docker logs "${PROXY}" 2>&1)"
    if grep -qF -f "${NEEDLES_HASH}" <<<"${LOGS}"; then fail "an access hash appears in the add-on log"; fi
    if grep -Eq '/(repo|access)/[^[:space:]]*[0-9a-f]{32}' <<<"${LOGS}"; then
        fail "the add-on log holds a 32-hex run after /repo/ or /access/"
    fi
    if grep -Eq '(GET|POST) /[^[:space:]]* [0-9]{3}' <<<"${LOGS}"; then fail "the add-on log holds a raw access-log record"; fi
}
no_leak_in_logs
ok "docker logs: no access hash, no 32-hex run after /repo/ or /access/, no raw access-log record"
LAST_FETCH_DOC="$(docker exec "${PROXY}" cat /data/last-fetch.json)"
if grep -qF -f "${NEEDLES_HASH}" <<<"${LAST_FETCH_DOC}"; then fail "an access hash appears in /data/last-fetch.json"; fi
if grep -Eq '[0-9a-f]{32}' <<<"${LAST_FETCH_DOC}"; then fail "/data/last-fetch.json holds a 32-hex run"; fi
ok "/data/last-fetch.json: no access hash and no 32-hex run at all"
for path in api/access api/overview; do
    ingress_get "${path}"
    if grep -qF -f "${NEEDLES_HASH}" <<<"${GUI_BODY}"; then fail "${path} holds an access hash"; fi
done
ok "GET api/access and api/overview hold no access hash"
docker exec "${PROXY}" pkill -f 'python3 -m app[.]fetchlog' || fail "pkill of fetchlog failed"
[ "$(refs_code "${URL_ERIN_NEW}")" = "200" ] || fail "info/refs of erin's URL is not 200 with fetchlog killed"
clone_as erin-outage "${URL_ERIN_NEW}" || fail "git clone --depth 1 failed with fetchlog killed"
ok "with fetchlog killed, info/refs (200) and a clone of erin's URL still work"
fetchlog_back() {
    local pid
    pid="$(pid_of 'python3 -m app[.]fetchlog')"
    [ -n "${pid}" ] && [ "${pid}" != "${FETCHLOG_PID}" ] && mode_is /run/mrp-fetch/fetch.sock '%a %U:%G' '620 root:lighttpd'
}
wait_for 30 "s6 to restart fetchlog with a fresh socket" fetchlog_back
ok "s6 restarted fetchlog (new pid $(pid_of 'python3 -m app[.]fetchlog')) with fetch.sock 620 root:lighttpd"
no_leak_in_logs
ok "docker logs after the outage: no access hash, no 32-hex run after /repo/ or /access/, no raw access-log record"
echo "✓ GUI verify: all checks passed"
