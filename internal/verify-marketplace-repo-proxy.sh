#!/usr/bin/env bash
# Docker end-to-end check of marketplace-repo-proxy against a local, auth-checking upstream fixture (never GitHub).
# Tracer version: one configured private repository, one user in /data/access.json, one --depth 1 clone of that
# user's store URL from a second container, and no PAT or full access hash in the add-on log.
# Manual invocation: bash internal/verify-marketplace-repo-proxy.sh
# Optional env: MRP_VERIFY_PREFIX (container/network name prefix, default mrp-verify), MRP_VERIFY_WORK (scratch dir).
# Starts containers: never run it in two worktrees at the same time.
set -euo pipefail

ADDON_DIR="marketplace-repo-proxy"
IMAGE_TAG="marketplace-repo-proxy-verify:local"
FIXTURE_TAG="marketplace-repo-proxy-fixture:local"
PREFIX="${MRP_VERIFY_PREFIX:-mrp-verify}"
NET="${PREFIX}-net"
PROXY="${PREFIX}-proxy"
UPSTREAM="${PREFIX}-upstream"
CLIENT="${PREFIX}-client"
PAT="SENTINEL-PAT-$RANDOM$RANDOM"
WORK="${MRP_VERIFY_WORK:-}"
REPO="example-org/private-addons"

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
    docker rm -f "${PROXY}" "${UPSTREAM}" "${CLIENT}" >/dev/null 2>&1 || true
    docker network rm "${NET}" >/dev/null 2>&1 || true
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

echo "==> (1) docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"
docker run --rm --entrypoint test "${IMAGE_TAG}" -x /usr/libexec/git-core/git-http-backend \
    || fail "git-http-backend missing in the image"
echo "✓ image built, git-http-backend present"

echo "==> (2) fixture image"
docker build -t "${FIXTURE_TAG}" - >/dev/null <<EOF
FROM ${IMAGE_TAG}
RUN apk add --no-cache lighttpd-mod_auth
EOF
echo "✓ fixture image built (lighttpd-mod_auth)"

echo "==> (3) network and upstream fixture"
docker rm -f "${PROXY}" "${UPSTREAM}" "${CLIENT}" >/dev/null 2>&1 || true
docker network rm "${NET}" >/dev/null 2>&1 || true
docker network create "${NET}" >/dev/null
# The PAT is the fixture's basic-auth password; it reaches only the fixture container
docker run -d --name "${UPSTREAM}" --network "${NET}" -e FIXTURE_PAT="${PAT}" --entrypoint sh "${FIXTURE_TAG}" -c '
set -e
repo=/srv/upstream/example-org/private-addons.git
mkdir -p /srv/upstream/example-org
git init -q --bare --initial-branch=main "$repo"
git init -q --initial-branch=main /tmp/work
cd /tmp/work
printf "name: Verify fixture\n" > repository.yaml
mkdir demo
printf "name: Demo\nslug: demo\nversion: \"1.0.0\"\n" > demo/config.yaml
git add repository.yaml demo/config.yaml
git -c user.name=fixture -c user.email=fixture@example.invalid commit -q -m "fixture: initial"
git push -q "$repo" main
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
UPSTREAM_REFS="http://127.0.0.1:8080/example-org/private-addons.git/info/refs?service=git-upload-pack"
wait_for 30 "upstream fixture" docker exec "${UPSTREAM}" curl -s -o /dev/null "${UPSTREAM_REFS}"
code="$(docker exec "${UPSTREAM}" curl -s -o /dev/null -w '%{http_code}' "${UPSTREAM_REFS}")"
[ "${code}" = "401" ] || fail "upstream without credentials returned ${code}, expected 401"
echo "✓ upstream fixture requires the PAT (401 without it)"

echo "==> (4) proxy with one repository and one user"
if [ -z "${WORK}" ]; then WORK="$(mktemp -d)"; else mkdir -p "${WORK}"; fi
mkdir -p "${WORK}/data"
HASH="$(python3 -I -c 'import secrets; print(secrets.token_hex(16))')"
python3 -I - "${WORK}/data" "${PAT}" "${HASH}" "${REPO}" <<'PY'
import json, sys, time
data, pat, hash_, repo = sys.argv[1:5]
options = {
    "github_token": pat,
    "sync_interval": 5,
    "repositories": [{"repository": repo}],
    "register_local": True,
    "api_enabled": False,
    "log_level": "debug",
}
access = {
    "schema": 1,
    "entries": [
        {
            "repository": repo,
            "user": "alice",
            "hash": hash_,
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "cli",
        }
    ],
}
json.dump(options, open(f"{data}/options.json", "w"))
json.dump(access, open(f"{data}/access.json", "w"))
PY
docker run -d --name "${PROXY}" --hostname "${PROXY}" --network "${NET}" \
    -v "${WORK}/data:/data" \
    -e MRP_TEST_UPSTREAM_BASE="http://${UPSTREAM}:8080" \
    "${IMAGE_TAG}" >/dev/null
BARE="/srv/git/repos/${REPO}.git"
wait_for 90 "first sync (refs/heads/main in the bare repository)" \
    docker exec "${PROXY}" git --git-dir="${BARE}" rev-parse --verify -q refs/heads/main
echo "✓ sync fetched the upstream default branch into ${BARE}"

echo "==> (5) access symlink tree"
LINK="/srv/git/access/${REPO}/${HASH}"
docker exec "${PROXY}" test -L "${LINK}" || fail "access symlink missing"
target="$(docker exec "${PROXY}" readlink -f "${LINK}")"
[ "${target}" = "${BARE}" ] || fail "access symlink resolves to ${target}, expected ${BARE}"
mode="$(docker exec "${PROXY}" stat -c %a /srv/git/access)"
[ "${mode}" = "711" ] || fail "/srv/git/access has mode ${mode}, expected 711"
URL="http://${PROXY}:8080/repo/${REPO}/${HASH}"
echo "✓ init linked the user's hash to the bare repository (access root 0711)"

echo "==> (6) clone from a second container"
docker run --rm --name "${CLIENT}" --network "${NET}" --entrypoint sh "${IMAGE_TAG}" -c '
set -e
cd /tmp
git clone -q --depth 1 "$1" clone
test -f clone/repository.yaml
' sh "${URL}" || fail "git clone --depth 1 of the store URL failed or repository.yaml is missing"
echo "✓ git clone --depth 1 of the store URL returned repository.yaml"

echo "==> (7) secret hygiene in the add-on log"
LOGS="$(docker logs "${PROXY}" 2>&1)"
B64="$(printf 'x-access-token:%s' "${PAT}" | base64 -w0)"
if grep -qF -- "${PAT}" <<<"${LOGS}"; then fail "PAT found in the add-on log"; fi
if grep -qF -- "${B64}" <<<"${LOGS}"; then fail "base64 PAT header found in the add-on log"; fi
if grep -qF -- "${HASH}" <<<"${LOGS}"; then fail "full access hash found in the add-on log"; fi
grep -q "test upstream override active" <<<"${LOGS}" || fail "missing WARNING for the test upstream override"
echo "✓ add-on log holds neither the PAT nor the full hash"

echo "✓ tracer: one user cloned one repository end to end"
