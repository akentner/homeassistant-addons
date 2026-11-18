#!/usr/bin/env bash
# Docker end-to-end check of marketplace-repo-proxy against a local, auth-checking upstream fixture (never GitHub).
# Proves ROADMAP Phase 1 criteria 1-5 with one `✓`/`✗` line per check: clones of the upstream default branch and of a
# configured non-default branch, query and `#branch` tolerance, the 404/403 matrix, push refusal, an upstream change
# after `mrp sync`, revocation by CLI and by hand edit, status codes end to end and secret hygiene.
# Builds the add-on image locally (D-21). Manual invocation: bash internal/verify-marketplace-repo-proxy.sh
# Optional env: MRP_VERIFY_PREFIX (container/network name prefix, default mrp-verify), MRP_VERIFY_WORK (scratch dir).
# Starts containers: never run it in two worktrees at the same time.
# csh snippets are single-quoted on purpose: "$1" expands in the client container, not here.
# shellcheck disable=SC2016
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
SUPERVISOR_SENTINEL="SENTINEL-SUPERVISOR-$RANDOM$RANDOM"
OVERRIDE_VAR="MRP_TEST_UPSTREAM_BASE"
PUBLIC_URL="https://addons.example.invalid"
WORK="${MRP_VERIFY_WORK:-}"
REPO="example-org/private-addons"
REPO_BRANCHED="example-org/branched"
REPO_NO_META="example-org/no-meta"
REPO_MISSING="example-org/missing"

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

cleanup() {
    docker rm -f "${PROXY}" "${UPSTREAM}" "${CLIENT}" >/dev/null 2>&1 || true
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
status_of() { field_of "$1" status; }
head_of() { field_of "$1" head; }
sync_state() {
    docker exec "${PROXY}" python3 -I -c '
import json
print(json.load(open("/data/status.json")).get("sync", {}).get("state"))
'
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

# Commits <file> with <content> to the upstream main branch inside the fixture; prints the new full SHA
upstream_commit() { # usage: upstream_commit <owner/repo> <file> <content>
    docker exec "${UPSTREAM}" sh -c '
set -e
w="$(mktemp -d)"
git clone -q "/srv/upstream/$1.git" "$w"
cd "$w"
printf "%s\n" "$3" > "$2"
git add "$2"
git -c user.name=fixture -c user.email=fixture@example.invalid commit -q -m "fixture: add $2"
git push -q origin HEAD:main
git rev-parse HEAD
cd /
rm -rf "$w"
' sh "$1" "$2" "$3"
}

# Shell snippet in the client container, cwd /tmp: csh <script> [args...]
csh() {
    local script="$1"
    shift
    docker exec -w /tmp "${CLIENT}" sh -ec "${script}" sh "$@"
}

# HTTP status of a request from the client container (no URL normalisation, so traversal reaches the server)
http_code() { docker exec "${CLIENT}" curl -s --path-as-is -o /dev/null -w '%{http_code}' "$@"; }
expect_code() { # usage: expect_code <code> <label> <curl args...>; labels never contain a hash
    local want="$1" label="$2" got
    shift 2
    got="$(http_code "$@" || true)"
    [ "${got}" = "${want}" ] || fail "${label}: HTTP ${got}, expected ${want}"
    ok "${label}: ${want}"
}
refs_url() { printf '%s/info/refs?service=git-upload-pack' "$1"; }

# "internal: <url>" line of `mrp users add|url` output
internal_url() { sed -n 's/^internal: //p' <<<"$1"; }
public_url() { sed -n 's/^public: //p' <<<"$1"; }

echo "==> (0) static checks"
CONFIG="${ADDON_DIR}/config.yaml"
LIGHTTPD_CONF="${ADDON_DIR}/rootfs/etc/lighttpd/marketplace-repo-proxy.conf"
S6="${ADDON_DIR}/rootfs/etc/s6-overlay/s6-rc.d"
[ "$(yget "${CONFIG}" "ports.8080/tcp")" = "null" ] || fail "ports.8080/tcp is published by default (D-02)"
grep -qE '^  8080/tcp: null$' "${CONFIG}" || fail "ports.8080/tcp is not declared as null (D-02)"
ok "config.yaml: 8080/tcp declared and not published (null)"
[ "$(yget "${CONFIG}" schema.github_token)" = "password" ] || fail "schema.github_token is not of type password"
ok "config.yaml: github_token has schema type password"
if grep -rqF -- "${OVERRIDE_VAR}" "${CONFIG}" "${ADDON_DIR}/build.yaml" "${ADDON_DIR}/Dockerfile" \
    "${ADDON_DIR}/rootfs"; then
    fail "test upstream override name found in a manifest, the Dockerfile or rootfs (D-18)"
fi
ok "test upstream override absent from config.yaml, build.yaml, Dockerfile and rootfs"
grep -qxF 'server.breakagelog = "/dev/null"' "${LIGHTTPD_CONF}" || fail "lighttpd config lacks server.breakagelog"
ok "lighttpd drops CGI stderr (server.breakagelog = /dev/null)"
if grep -qE '^[[:space:]]*debug\.' "${LIGHTTPD_CONF}"; then fail "lighttpd config sets a debug.* option"; fi
ok "lighttpd config sets no debug.* option"
for svc in lighttpd access-watch; do
    [ "$(head -n 1 "${S6}/${svc}/run")" = "#!/bin/sh" ] || fail "${svc}/run does not start with #!/bin/sh"
done
ok "lighttpd/run and access-watch/run start with #!/bin/sh (no with-contenv)"

echo "==> (1) docker build"
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"
docker run --rm --entrypoint test "${IMAGE_TAG}" -x /usr/libexec/git-core/git-http-backend \
    || fail "git-http-backend missing in the image"
ok "image built, git-http-backend present"

echo "==> (2) fixture image"
docker build -t "${FIXTURE_TAG}" - >/dev/null <<EOF
FROM ${IMAGE_TAG}
RUN apk add --no-cache lighttpd-mod_auth
EOF
ok "fixture image built (lighttpd-mod_auth)"

echo "==> (3) network and upstream fixture"
docker rm -f "${PROXY}" "${UPSTREAM}" "${CLIENT}" >/dev/null 2>&1 || true
docker network rm "${NET}" >/dev/null 2>&1 || true
docker network create "${NET}" >/dev/null
# The PAT is the fixture's basic-auth password; it reaches only the fixture container.
# private-addons: default branch main plus an upstream-only branch dev (DEV file) that must never be served.
# branched: default branch main, configured branch stable (STABLE marker); the upstream HEAD stays refs/heads/main.
# no-meta: one commit without repository.yaml. missing: never created.
docker run -d --name "${UPSTREAM}" --network "${NET}" -e FIXTURE_PAT="${PAT}" --entrypoint sh "${FIXTURE_TAG}" -c '
set -e
ci() { git -c user.name=fixture -c user.email=fixture@example.invalid commit -q -m "$1"; }
demo() { mkdir -p demo; printf "name: Demo\nslug: demo\nversion: \"1.0.0\"\n" > demo/config.yaml; }
mkdir -p /srv/upstream/example-org

repo=/srv/upstream/example-org/private-addons.git
git init -q --bare --initial-branch=main "$repo"
git init -q --initial-branch=main /tmp/private-addons
cd /tmp/private-addons
printf "name: Verify fixture\n" > repository.yaml
demo
git add repository.yaml demo/config.yaml
ci "fixture: initial"
git checkout -q -b dev
printf "dev only\n" > DEV
git add DEV
ci "fixture: dev branch"
git push -q "$repo" main dev

repo=/srv/upstream/example-org/branched.git
git init -q --bare --initial-branch=main "$repo"
git init -q --initial-branch=main /tmp/branched
cd /tmp/branched
printf "name: Verify fixture branched main\n" > repository.yaml
demo
git add repository.yaml demo/config.yaml
ci "fixture: branched main"
git checkout -q -b stable
printf "name: Verify fixture branched stable\n" > repository.yaml
printf "stable\n" > STABLE
git add repository.yaml STABLE
ci "fixture: branched stable"
git push -q "$repo" main stable

repo=/srv/upstream/example-org/no-meta.git
git init -q --bare --initial-branch=main "$repo"
git init -q --initial-branch=main /tmp/no-meta
cd /tmp/no-meta
printf "no repository.yaml in this repository\n" > README
git add README
ci "fixture: no repository.yaml"
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
UPSTREAM_REFS="http://127.0.0.1:8080/example-org/private-addons.git/info/refs?service=git-upload-pack"
wait_for 30 "upstream fixture" docker exec "${UPSTREAM}" curl -s -o /dev/null "${UPSTREAM_REFS}"
code="$(docker exec "${UPSTREAM}" curl -s -o /dev/null -w '%{http_code}' "${UPSTREAM_REFS}")"
[ "${code}" = "401" ] || fail "upstream without credentials returned ${code}, expected 401"
ok "upstream fixture requires the PAT (401 without it)"
docker exec "${UPSTREAM}" git --git-dir="/srv/upstream/${REPO}.git" rev-parse -q --verify refs/heads/dev >/dev/null \
    || fail "upstream ${REPO} has no dev branch"
ok "upstream ${REPO} has main and dev (only main may be served)"
STABLE_SHA="$(docker exec "${UPSTREAM}" git --git-dir="/srv/upstream/${REPO_BRANCHED}.git" rev-parse refs/heads/stable)"
[ "$(docker exec "${UPSTREAM}" git --git-dir="/srv/upstream/${REPO_BRANCHED}.git" symbolic-ref HEAD)" \
    = "refs/heads/main" ] || fail "upstream ${REPO_BRANCHED} HEAD is not refs/heads/main"
ok "upstream ${REPO_BRANCHED} has default main and branch stable (${STABLE_SHA:0:12})"

echo "==> (4) proxy: four repositories, alice seeded in access.json"
if [ -z "${WORK}" ]; then WORK="$(mktemp -d)"; else mkdir -p "${WORK}"; fi
mkdir -p "${WORK}/data"
HASH_ALICE="$(python3 -I -c 'import secrets; print(secrets.token_hex(16))')"
# usage: options_json <pat>  (prints options.json; the same repositories in every run)
options_json() {
    python3 -I - "$1" "${PUBLIC_URL}" "${REPO}" "${REPO_BRANCHED}" "${REPO_NO_META}" "${REPO_MISSING}" <<'PY'
import json, sys
pat, public_url, repo, branched, no_meta, missing = sys.argv[1:7]
print(json.dumps({
    "github_token": pat,
    "sync_interval": 5,
    "public_url": public_url,
    "repositories": [
        {"repository": repo},
        {"repository": branched, "branch": "stable"},
        {"repository": no_meta},
        {"repository": missing},
    ],
    "register_local": True,
    "api_enabled": False,
    "log_level": "debug",
}))
PY
}
options_json "${PAT}" >"${WORK}/data/options.json"
python3 -I - "${WORK}/data" "${HASH_ALICE}" "${REPO}" <<'PY'
import json, sys, time
data, hash_, repo = sys.argv[1:4]
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
json.dump(access, open(f"{data}/access.json", "w"))
PY
docker run -d --name "${PROXY}" --hostname "${PROXY}" --network "${NET}" \
    -v "${WORK}/data:/data" \
    -e "${OVERRIDE_VAR}=http://${UPSTREAM}:8080" \
    -e "SUPERVISOR_TOKEN=${SUPERVISOR_SENTINEL}" \
    "${IMAGE_TAG}" >/dev/null
wait_field 90 "${REPO}" status ok
ok "status.json: ${REPO} ok"
wait_field 90 "${REPO_BRANCHED}" status ok
ok "status.json: ${REPO_BRANCHED} ok"
wait_field 90 "${REPO_NO_META}" status no_repository_yaml
ok "status.json: ${REPO_NO_META} no_repository_yaml"
wait_field 90 "${REPO_MISSING}" status not_found
ok "status.json: ${REPO_MISSING} not_found"
[ "$(field_of "${REPO_BRANCHED}" branch)" = "stable" ] || fail "${REPO_BRANCHED}: branch is not stable"
[ "$(field_of "${REPO_BRANCHED}" branch_source)" = "configured" ] || fail "${REPO_BRANCHED}: branch_source not configured"
ok "status.json: ${REPO_BRANCHED} branch stable, branch_source configured"
[ "$(field_of "${REPO}" branch_source)" = "upstream_default" ] || fail "${REPO}: branch_source not upstream_default"
ok "status.json: ${REPO} branch_source upstream_default"
docker exec "${PROXY}" pgrep -f 'python3 -m app[.]watch' >/dev/null || fail "access-watch (app.watch) is not running"
ok "access-watch longrun (python3 -m app.watch) is running"
LINK="/srv/git/access/${REPO}/${HASH_ALICE}"
docker exec "${PROXY}" test -L "${LINK}" || fail "init did not link the seeded user"
[ "$(docker exec "${PROXY}" readlink -f "${LINK}")" = "/srv/git/repos/${REPO}.git" ] \
    || fail "seeded user's link does not resolve to the bare repository"
[ "$(docker exec "${PROXY}" stat -c %a /srv/git/access)" = "711" ] || fail "/srv/git/access is not mode 711"
ok "init linked the seeded user to the bare repository (access root 0711)"

echo "==> (5) users through mrp"
URL_ALICE="http://${PROXY}:8080/repo/${REPO}/${HASH_ALICE}"
out="$(docker exec "${PROXY}" mrp users add "${REPO}" bob)" || fail "mrp users add bob failed"
URL_BOB="$(internal_url "${out}")"
HASH_BOB="${URL_BOB##*/}"
[[ "${URL_BOB}" =~ ^http://${PROXY}:8080/repo/${REPO}/[0-9a-f]{32}$ ]] || fail "mrp users add printed no internal URL"
[ "$(public_url "${out}")" = "${PUBLIC_URL}/repo/${REPO}/${HASH_BOB}" ] || fail "mrp users add printed no public URL"
ok "mrp users add (bob) printed the internal and the public store URL"
HASH_DAVE="$(python3 -I -c 'import secrets; print(secrets.token_hex(16))')"
out="$(docker exec "${PROXY}" mrp users add "${REPO}" dave --hash "${HASH_DAVE}")" || fail "mrp users add dave failed"
URL_DAVE="$(internal_url "${out}")"
[ "${URL_DAVE}" = "http://${PROXY}:8080/repo/${REPO}/${HASH_DAVE}" ] || fail "--hash was not used for dave"
ok "mrp users add --hash (dave) uses the client-supplied hash"
out="$(docker exec "${PROXY}" mrp users add "${REPO_MISSING}" carol)" || fail "mrp users add carol failed"
URL_CAROL="$(internal_url "${out}")"
HASH_CAROL="${URL_CAROL##*/}"
[[ "${HASH_CAROL}" =~ ^[0-9a-f]{32}$ ]] || fail "mrp users add printed no URL for carol"
ok "mrp users add (carol) for the configured but never synced ${REPO_MISSING}"
out="$(docker exec "${PROXY}" mrp users add "${REPO_BRANCHED}" erin)" || fail "mrp users add erin failed"
URL_ERIN="$(internal_url "${out}")"
HASH_ERIN="${URL_ERIN##*/}"
[[ "${HASH_ERIN}" =~ ^[0-9a-f]{32}$ ]] || fail "mrp users add printed no URL for erin"
ok "mrp users add (erin) for ${REPO_BRANCHED}"

echo "==> (6) clones of the upstream default branch from a client container"
docker run -d --name "${CLIENT}" --network "${NET}" --entrypoint sh "${IMAGE_TAG}" -c 'exec sleep infinity' >/dev/null
csh 'git clone -q --depth 1 "$1" a && test -f a/repository.yaml && test -f a/demo/config.yaml' "${URL_ALICE}" \
    || fail "git clone --depth 1 failed or repository.yaml / demo/config.yaml missing"
ok "git clone --depth 1 of the store URL has repository.yaml and demo/config.yaml"
csh 'git clone -q --depth 1 "$1?ref=main&tab=readme" query && test -f query/repository.yaml' "${URL_ALICE}" \
    || fail "clone of the store URL with ?ref=main&tab=readme failed"
ok "git clone of the store URL with ?ref=main&tab=readme works"
csh 'git clone -q --depth 1 --branch main "$1" hashmain && test "$(git -C hashmain rev-parse --abbrev-ref HEAD)" = main' \
    "${URL_ALICE}" || fail "git clone --branch main (the #main form) failed"
ok "git clone --depth 1 --branch main (Supervisor form of #main) works"
heads="$(csh 'git ls-remote --heads "$1"' "${URL_ALICE}")" || fail "git ls-remote --heads failed"
if [ "$(wc -l <<<"${heads}")" != "1" ] || [ "$(cut -f2 <<<"${heads}")" != "refs/heads/main" ]; then
    fail "ls-remote --heads lists $(cut -f2 <<<"${heads}" | tr '\n' ' '), expected only refs/heads/main"
fi
ok "ls-remote --heads lists only refs/heads/main (upstream dev is not served)"
csh 'cd a && git fetch -q --update-shallow --depth 1 origin && test "$(git rev-parse --is-shallow-repository)" = true' \
    || fail "git fetch --update-shallow --depth 1 failed"
ok "git fetch --update-shallow --depth 1 works in the shallow clone"
csh 'git clone -q "$1" full && test "$(git -C full rev-parse --is-shallow-repository)" = false' "${URL_ALICE}" \
    || fail "full clone failed or is shallow"
ok "a clone without --depth is a full (non-shallow) repository"

echo "==> (7) configured non-default branch (${REPO_BRANCHED}, branch stable)"
refs="$(csh 'git ls-remote "$1"' "${URL_ERIN}")" || fail "git ls-remote of ${REPO_BRANCHED} failed"
expected="$(printf '%s\tHEAD\n%s\trefs/heads/stable' "${STABLE_SHA}" "${STABLE_SHA}")"
[ "${refs}" = "${expected}" ] || fail "ls-remote lists '$(cut -f2 <<<"${refs}" | tr '\n' ' ')', expected HEAD and \
refs/heads/stable at the upstream stable SHA"
ok "ls-remote lists exactly HEAD and refs/heads/stable, both at the upstream stable SHA"
if grep -q 'refs/heads/main' <<<"${refs}"; then fail "ls-remote of ${REPO_BRANCHED} lists refs/heads/main"; fi
ok "ls-remote of ${REPO_BRANCHED} lists no refs/heads/main"
csh 'git clone -q --depth 1 "$1" erin' "${URL_ERIN}" || fail "git clone --depth 1 of ${REPO_BRANCHED} failed"
[ "$(csh 'git -C erin rev-parse --abbrev-ref HEAD')" = "stable" ] || fail "clone of ${REPO_BRANCHED} is not on stable"
ok "git clone --depth 1 of ${REPO_BRANCHED} checks out stable"
csh 'test -f erin/STABLE' || fail "clone of ${REPO_BRANCHED} has no STABLE marker"
[ "$(csh 'git -C erin rev-parse HEAD')" = "${STABLE_SHA}" ] || fail "clone of ${REPO_BRANCHED} is not at the stable SHA"
ok "clone of ${REPO_BRANCHED} has the STABLE marker at the upstream stable SHA"
if out="$(csh 'git clone -q --depth 1 --branch main "$1" erin-main' "${URL_ERIN}" 2>&1)"; then
    fail "git clone --branch main of ${REPO_BRANCHED} succeeded"
fi
grep -q 'Remote branch main not found' <<<"${out}" || fail "git clone --branch main failed for another reason"
ok "git clone --branch main of ${REPO_BRANCHED} fails: remote branch main not found (only stable is served)"

echo "==> (8) request matrix"
BASE="http://${PROXY}:8080"
UNKNOWN_HASH="$(python3 -I -c 'import secrets; print(secrets.token_hex(16))')"
expect_code 200 "smart info/refs (alice)" "$(refs_url "${URL_ALICE}")"
expect_code 200 "info/refs with ?ref=main&tab=readme before the git suffix" \
    "${URL_ALICE}?ref=main&tab=readme/info/refs&service=git-upload-pack"
expect_code 200 "smart info/refs (bob)" "$(refs_url "${URL_BOB}")"
expect_code 404 "unknown hash" "$(refs_url "${BASE}/repo/${REPO}/${UNKNOWN_HASH}")"
expect_code 404 "alice's hash under ${REPO_NO_META}" "$(refs_url "${BASE}/repo/${REPO_NO_META}/${HASH_ALICE}")"
expect_code 404 "unknown owner" "$(refs_url "${BASE}/repo/unknown-org/private-addons/${HASH_ALICE}")"
expect_code 404 "/repo/" "${BASE}/repo/"
expect_code 404 "/repo/${REPO}/" "${BASE}/repo/${REPO}/"
expect_code 404 "{hash}/HEAD" "${URL_ALICE}/HEAD"
expect_code 404 "{hash}/objects/info/packs" "${URL_ALICE}/objects/info/packs"
expect_code 404 "{hash}/config" "${URL_ALICE}/config"
expect_code 404 "POST {hash}/git-receive-pack" -X POST --data-binary 0000 \
    -H 'Content-Type: application/x-git-receive-pack-request' "${URL_ALICE}/git-receive-pack"
expect_code 404 "git-http-backend path" "${BASE}/usr/libexec/git-core/git-http-backend"
expect_code 404 "../ traversal" "${URL_ALICE}/../../../../srv/git/repos/${REPO}.git/config"
expect_code 404 "%2e%2e traversal" "${URL_ALICE}/%2e%2e/%2e%2e/%2e%2e/%2e%2e/srv/git/repos/${REPO}.git/config"
expect_code 404 "/" "${BASE}/"
expect_code 404 "carol (configured, never synced: dangling link)" "$(refs_url "${URL_CAROL}")"
expect_code 403 "dumb {hash}/info/refs" "${URL_ALICE}/info/refs"
expect_code 403 "info/refs?service=git-receive-pack" "${URL_ALICE}/info/refs?service=git-receive-pack"
csh 'cd full && printf "push\n" > PUSHED && git add PUSHED
git -c user.name=client -c user.email=client@example.invalid commit -q -m push' || fail "local commit in the clone failed"
if out="$(csh 'cd full && git push -q origin HEAD:main' 2>&1)"; then
    fail "git push through the proxy succeeded"
fi
grep -q 'returned error: 403' <<<"${out}" || fail "git push failed, but not with HTTP 403"
ok "git push through the proxy is refused (HTTP 403)"

echo "==> (9) upstream change reaches the store after mrp sync"
NEW_SHA="$(upstream_commit "${REPO}" UPDATED "update ${RANDOM}")"
[[ "${NEW_SHA}" =~ ^[0-9a-f]{40}$ ]] || fail "upstream commit failed"
[ "$(docker exec "${PROXY}" mrp sync)" = "sync requested" ] || fail "mrp sync did not request a sync"
ok "upstream pushed ${NEW_SHA:0:12}; mrp sync requested a cycle"
wait_field 30 "${REPO}" head "${NEW_SHA:0:12}"
[ "$(field_of "${REPO}" refs_changed)" = "true" ] || fail "${REPO}: refs_changed is not true after the update"
ok "status.json: ${REPO} head ${NEW_SHA:0:12}, refs_changed true"
[ "$(csh 'cd a && git fetch -q origin && git rev-parse refs/remotes/origin/main')" = "${NEW_SHA}" ] \
    || fail "fetch in the existing clone does not show the new commit"
ok "fetch in the existing clone shows the new commit"
csh 'git clone -q --depth 1 "$1" fresh && test -f fresh/UPDATED' "${URL_ALICE}" \
    || fail "fresh clone does not contain the new file"
ok "a fresh clone contains the new file"

echo "==> (10) revocation"
[ "$(docker exec "${PROXY}" mrp users revoke "${REPO}" alice)" = "revoked alice from ${REPO}" ] \
    || fail "mrp users revoke alice failed"
ok "mrp users revoke ${REPO} alice"
expect_code 404 "alice at the next request after mrp users revoke" "$(refs_url "${URL_ALICE}")"
expect_code 200 "bob keeps access" "$(refs_url "${URL_BOB}")"
# Hand edit (not through mrp): drop bob's entry with a json rewrite and an atomic replace
docker exec "${PROXY}" python3 -I -c '
import json, os, sys
path = "/data/access.json"
doc = json.load(open(path))
doc["entries"] = [e for e in doc["entries"] if (e.get("repository"), e.get("user")) != (sys.argv[1], sys.argv[2])]
tmp = path + ".verify-tmp"
with open(tmp, "w") as fh:
    json.dump(doc, fh)
os.chmod(tmp, 0o600)
os.replace(tmp, path)
' "${REPO}" bob
revoked=""
for _ in $(seq 1 10); do
    if [ "$(http_code "$(refs_url "${URL_BOB}")" || true)" = "404" ]; then revoked=yes; break; fi
    sleep 0.5
done
[ -n "${revoked}" ] || fail "bob still served 5 s after the hand edit of /data/access.json"
ok "bob: 404 within 5 s of a hand edit of /data/access.json (access-watch)"
expect_code 200 "dave keeps access" "$(refs_url "${URL_DAVE}")"
expect_code 200 "erin keeps access" "$(refs_url "${URL_ERIN}")"

echo "==> (11) add-on log after the matrix"
LOGS="$(docker logs "${PROXY}" 2>&1)"
if grep -qF -- "${PAT}" <<<"${LOGS}"; then fail "PAT found in the add-on log"; fi
for h in "${HASH_ALICE}" "${HASH_BOB}" "${HASH_CAROL}" "${HASH_DAVE}" "${HASH_ERIN}"; do
    if grep -qF -- "${h}" <<<"${LOGS}"; then fail "full access hash found in the add-on log"; fi
done
grep -q "test upstream override active" <<<"${LOGS}" || fail "missing WARNING for the test upstream override"
ok "add-on log holds neither the PAT nor a full hash; override WARNING present"

echo "✓ marketplace-repo-proxy criteria 1-4 verified"
