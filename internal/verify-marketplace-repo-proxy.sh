#!/usr/bin/env bash
# Docker end-to-end check of marketplace-repo-proxy against a local, auth-checking upstream fixture (never GitHub).
# Proves ROADMAP Phase 1 criteria 1-5 with one `✓`/`✗` line per check: clones of the upstream default branch and of a
# configured non-default branch, query and `#branch` tolerance, the 404/403 matrix, push refusal, an upstream change
# after `mrp sync`, revocation by CLI and by hand edit, status codes end to end and secret hygiene.
# Phase 2: self-registration of the `local` store URLs with a fake Supervisor container (network alias `supervisor`,
# tests/fake_supervisor.py) that clones every added URL through the proxy, like the real Supervisor (never a real one).
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
SUPERVISOR_FAKE="${PREFIX}-supervisor"
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
    docker rm -f "${PROXY}" "${UPSTREAM}" "${CLIENT}" "${SUPERVISOR_FAKE}" >/dev/null 2>&1 || true
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

# /data/supervisor.json reader, like field_of
reg_of() { # usage: reg_of <owner/repo> <key>
    docker exec "${PROXY}" python3 -I -c '
import json, sys
doc = json.load(open("/data/supervisor.json"))
for entry in doc.get("repositories", []):
    if entry.get("repository") == sys.argv[1]:
        value = entry.get(sys.argv[2])
        print("null" if value is None else str(value).lower() if isinstance(value, bool) else value)
        break
' "$1" "$2"
}
wait_reg() { # usage: wait_reg <seconds> <owner/repo> <expected registration>
    local limit="$1" repo="$2" want="$3" got="" i
    for ((i = 0; i < limit; i++)); do
        got="$(reg_of "${repo}" registration 2>/dev/null || true)"
        [ "${got}" = "${want}" ] && return 0
        sleep 1
    done
    fail "${repo}: supervisor.json registration is '${got}' after ${limit} s, expected '${want}'"
}
# Request log of the fake Supervisor (one JSON object per line; never a token or a URL)
fake_requests() { docker exec "${SUPERVISOR_FAKE}" cat /tmp/fake/requests.jsonl; }
# D-29 shape of /data/supervisor.json; prints "d29 ok" or the first violation
d29_check() {
    docker exec "${PROXY}" python3 -I -c '
import json, re, sys
doc = json.load(open("/data/supervisor.json"))
opts = json.load(open("/data/options.json"))
states = ("registered", "missing", "leftover", "error")
unsafe = re.compile(r"https?://|/repo/|[0-9a-fA-F]{32}|github_pat_|gh[pousr]_")
def bad(text):
    print(text)
    sys.exit(1)
repos = doc.get("repositories")
if not isinstance(repos, list):
    bad("repositories is not a list")
configured = [item["repository"] for item in opts.get("repositories", [])]
head = [e.get("repository", "").lower() if isinstance(e, dict) else "" for e in repos[: len(configured)]]
if head != [c.lower() for c in configured]:
    bad("the first entries are not the configured repositories in options order")
for index, entry in enumerate(repos):
    if not isinstance(entry, dict) or not isinstance(entry.get("repository"), str):
        bad(f"entry {index} has no repository string")
    value = entry.get("registration")
    if value not in states:
        bad(f"entry {index}: registration {value!r} is not one of the D-28 values")
    if "message" in entry:
        message = entry["message"]
        if not isinstance(message, str) or not message or unsafe.search(message):
            bad(f"entry {index}: message is empty, not a string or unsafe")
    if index >= len(configured) and entry.get("configured") is not False:
        bad(f"entry {index}: an extra entry is not marked configured: false")
print("d29 ok")
'
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
docker rm -f "${PROXY}" "${UPSTREAM}" "${CLIENT}" "${SUPERVISOR_FAKE}" >/dev/null 2>&1 || true
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
# Fake Supervisor (the proxy image: python3 + git); reached by the proxy only through the network alias `supervisor`
docker run -d --name "${SUPERVISOR_FAKE}" --network "${NET}" --network-alias supervisor \
    -v "${PWD}/${ADDON_DIR}/tests/fake_supervisor.py:/opt/fake/fake_supervisor.py:ro" \
    -e "FAKE_SUPERVISOR_TOKEN=${SUPERVISOR_SENTINEL}" \
    --entrypoint python3 "${IMAGE_TAG}" -I /opt/fake/fake_supervisor.py \
    --host 0.0.0.0 --port 80 --state-dir /tmp/fake --in-use-file /tmp/fake/in-use >/dev/null
wait_for 30 "fake Supervisor" docker exec "${SUPERVISOR_FAKE}" test -f /tmp/fake/store.json
ok "fake Supervisor runs (network alias supervisor)"
docker run -d --name "${PROXY}" --hostname "${PROXY}" --network "${NET}" \
    -v "${WORK}/data:/data" \
    -e "${OVERRIDE_VAR}=http://${UPSTREAM}:8080" \
    -e "SUPERVISOR_TOKEN=${SUPERVISOR_SENTINEL}" \
    -e "HASSIO_TOKEN=${SUPERVISOR_SENTINEL}" \
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

echo "==> (4b) self-registration with a fake Supervisor"
wait_reg 60 "${REPO}" registered
wait_reg 60 "${REPO_BRANCHED}" registered
ok "supervisor.json: ${REPO} and ${REPO_BRANCHED} registered"
for r in "${REPO_NO_META}" "${REPO_MISSING}"; do
    [ "$(reg_of "${r}" registration)" = "missing" ] || fail "${r}: registration is not missing"
    [ "$(reg_of "${r}" in_store)" = "false" ] || fail "${r}: in_store is not false"
done
ok "supervisor.json: ${REPO_NO_META} and ${REPO_MISSING} missing, not in the store (no ok sync, D-07)"
FAKE_STORE="$(docker exec "${SUPERVISOR_FAKE}" cat /tmp/fake/store.json)"
for pair in "${REPO}|Verify fixture" "${REPO_BRANCHED}|Verify fixture branched stable"; do
    r="${pair%%|*}"
    name="${pair#*|}"
    slug="$(reg_of "${r}" store_slug)"
    [[ "${slug}" =~ ^[0-9a-f]{8}$ ]] || fail "${r}: store_slug is not 8 hex"
    python3 -I -c '
import json, sys
doc = json.loads(sys.stdin.read())
names = {r["slug"]: r["name"] for r in doc["repositories"]}
sys.exit(0 if names.get(sys.argv[1]) == sys.argv[2] else 1)
' "${slug}" "${name}" <<<"${FAKE_STORE}" || fail "${r}: the fake store does not list ${slug} as '${name}'"
    ok "fake store lists ${r} as ${slug} '${name}' (cloned through the proxy)"
done
REQUESTS="$(fake_requests)"
python3 -I -c '
import collections, json, sys
lines = [json.loads(line) for line in sys.stdin.read().splitlines() if line.strip()]
if any(entry.get("auth") != "ok" for entry in lines):
    sys.exit("a request to the fake Supervisor without a valid token")
calls = collections.Counter((entry["method"], entry["path"]) for entry in lines)
if calls.pop(("POST", "/store/repositories"), 0) != 2:
    sys.exit("expected exactly 2 POST /store/repositories")
if calls.pop(("GET", "/store/repositories"), 0) < 1:
    sys.exit("expected at least 1 GET /store/repositories")
if calls:
    sys.exit("unexpected requests: " + ", ".join(f"{m} {p}" for m, p in calls))
' <<<"${REQUESTS}" || fail "fake Supervisor request log violates the allow-list expectations"
ok "fake Supervisor saw only the token, 2 POST and >=1 GET /store/repositories, nothing else"
LOGS="$(docker logs "${PROXY}" 2>&1)"
grep -qF "supervisor POST /store/repositories: 200" <<<"${LOGS}" || fail "no 'supervisor POST' log line"
grep -qF "store: ${REPO} registered as " <<<"${LOGS}" || fail "no 'store: ${REPO} registered as' log line"
ok "add-on log: supervisor POST /store/repositories: 200 and store: ${REPO} registered as ..."
[ "$(docker exec "${PROXY}" stat -c %a /data/supervisor.json)" = "600" ] || fail "/data/supervisor.json is not mode 600"
if docker exec "${PROXY}" grep -qE '/repo/[^ "]*[0-9a-f]{32}' /data/supervisor.json; then
    fail "a full store URL in /data/supervisor.json"
fi
ok "/data/supervisor.json: mode 600, no full store URL"
out="$(d29_check)" || fail "supervisor.json Phase 3 interface (D-29): ${out}"
ok "supervisor.json Phase 3 interface (D-29): ${out}"
# The two `local` hashes join the hash needles of step (14); never echoed
HASH_LOCAL="$(docker exec "${PROXY}" python3 -I -c '
import json, sys
doc = json.load(open("/data/access.json"))
for repo in sys.argv[1:]:
    local = [e for e in doc["entries"] if e["repository"] == repo and e["user"] == "local"]
    if len(local) != 1 or local[0].get("source") != "system":
        sys.exit(1)
    print(local[0]["hash"])
' "${REPO}" "${REPO_BRANCHED}")" || fail "cannot read the local access entries"
HASH_LOCAL_1="$(sed -n 1p <<<"${HASH_LOCAL}")"
HASH_LOCAL_2="$(sed -n 2p <<<"${HASH_LOCAL}")"
if ! [[ "${HASH_LOCAL_1}" =~ ^[0-9a-f]{32}$ && "${HASH_LOCAL_2}" =~ ^[0-9a-f]{32}$ ]]; then
    fail "local access entries have no valid hash"
fi
ok "access.json: one local entry (source system) per registered repository"
echo "✓ tracer: the fake Supervisor cloned both registered local store URLs"

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

echo "==> (12) expired token: restart with a wrong PAT"
WRONG_PAT="SENTINEL-WRONG-$RANDOM$RANDOM"
# The new options travel on stdin, never in an argv
options_json "${WRONG_PAT}" | docker exec -i "${PROXY}" python3 -I -c '
import os, sys
tmp = "/data/options.json.verify-tmp"
with open(tmp, "w") as fh:
    fh.write(sys.stdin.read())
os.replace(tmp, "/data/options.json")
'
docker restart "${PROXY}" >/dev/null
wait_field 90 "${REPO}" status auth_failed
ok "status.json: ${REPO} auth_failed after the restart with a wrong PAT"
expect_code 200 "dave after the restart (last good mirror keeps serving)" "$(refs_url "${URL_DAVE}")"
LOGS="$(docker logs "${PROXY}" 2>&1)"
grep -qF "sync ${REPO}: auth_failed" <<<"${LOGS}" || fail "no auth_failed warning for ${REPO} in the add-on log"
ok "add-on log has an auth_failed warning for ${REPO}"

echo "==> (13) startup log after the restart (masked URLs only)"
# Before the restart dave did not exist, so this line comes from the restart's init
if ! grep -qE -- "user dave -> http://${PROXY}:8080/repo/${REPO}/[0-9a-f]{4}… [|] public ${PUBLIC_URL}/repo/${REPO}/[0-9a-f]{4}…" \
    <<<"${LOGS}"; then
    fail "startup log lacks dave's masked internal and public URL"
fi
ok "startup log lists dave with masked internal and public URLs (4 hex chars + …)"

echo "==> (14) secret hygiene (PAT, hashes, environments)"
sync_idle() { [ "$(sync_state)" = "idle" ]; }
wait_for 60 "sync.state idle" sync_idle
ok "status.json: sync.state idle (no git child holds the auth environment)"
# Needles live in files and are read with grep -F -f, so no scanner ever has a secret in its argv (Pitfall 9)
NEEDLES_PAT="${WORK}/needles-pat"
NEEDLES_HASH="${WORK}/needles-hash"
(
    umask 077
    for p in "${PAT}" "${WRONG_PAT}"; do
        printf '%s\n' "${p}"
        printf 'x-access-token:%s' "${p}" | base64 -w0
        echo
    done >"${NEEDLES_PAT}"
    printf '%s\n' "${HASH_ALICE}" "${HASH_BOB}" "${HASH_CAROL}" "${HASH_DAVE}" "${HASH_ERIN}" \
        "${HASH_LOCAL_1}" "${HASH_LOCAL_2}" >"${NEEDLES_HASH}"
)
if [ "$(wc -l <"${NEEDLES_PAT}")" != "4" ] || [ "$(wc -l <"${NEEDLES_HASH}")" != "7" ]; then
    fail "needles files are incomplete"
fi
put_needles() { # usage: put_needles <container> <host file> <container path>; mode 0600 inside the container
    docker exec -i "$1" sh -c 'umask 077; cat > "$1"' sh "$3" <"$2"
}
put_needles "${PROXY}" "${NEEDLES_PAT}" /tmp/needles-pat
put_needles "${PROXY}" "${NEEDLES_HASH}" /tmp/needles-hash
printf '%s\n' "${SUPERVISOR_SENTINEL}" | docker exec -i "${PROXY}" sh -c 'umask 077; cat > /tmp/needles-supervisor'
printf 'app.watch\n' | docker exec -i "${PROXY}" sh -c 'umask 077; cat > /tmp/needles-probe'
put_needles "${CLIENT}" "${NEEDLES_PAT}" /tmp/needles-pat
[ "$(docker exec "${PROXY}" stat -c %a /tmp/needles-pat)" = "600" ] || fail "/tmp/needles-pat is not mode 0600"
ok "needles: 2 PATs + 2 base64 headers, 7 full hashes (files, mode 0600)"

LOGS="$(docker logs "${PROXY}" 2>&1)"
if grep -qF -f "${NEEDLES_PAT}" <<<"${LOGS}"; then fail "PAT or base64 PAT header in docker logs"; fi
ok "docker logs (stdout and stderr): no PAT, no base64 PAT header"
if grep -qF -f "${NEEDLES_HASH}" <<<"${LOGS}"; then fail "full access hash in docker logs"; fi
ok "docker logs: no full access hash (after 404 probes with valid-but-misplaced hashes)"
if grep -qE '/repo/[^ ]*[0-9a-f]{32}' <<<"${LOGS}" || grep -qE '/access/[^ ]*[0-9a-f]{32}' <<<"${LOGS}"; then
    fail "a 32-hex value after /repo/ or /access/ in docker logs"
fi
ok "docker logs: no 32-hex value after /repo/ or /access/"

rc=0
docker exec "${PROXY}" grep -rlaF -f /tmp/needles-pat /srv/git >/dev/null 2>&1 || rc=$?
[ "${rc}" = "1" ] || fail "PAT needle found under /srv/git (or the scan failed, grep exit ${rc})"
ok "/srv/git/** holds no PAT and no base64 PAT header"
repos="$(docker exec "${PROXY}" sh -c 'ls -d /srv/git/repos/*/*.git')"
[ "$(wc -l <<<"${repos}")" = "3" ] || fail "expected 3 bare repositories, found: $(tr '\n' ' ' <<<"${repos}")"
for r in ${repos}; do
    cfg="$(docker exec "${PROXY}" git --git-dir="${r}" config --local --list)" || fail "cannot read ${r}/config"
    if grep -qi 'authorization' <<<"${cfg}"; then fail "${r}: Authorization in the repository config"; fi
    if grep -qi 'mirror' <<<"${cfg}"; then fail "${r}: mirror setting in the repository config"; fi
    url="$(sed -n 's/^remote\.origin\.url=//p' <<<"${cfg}")"
    [ -n "${url}" ] || fail "${r}: no remote.origin.url"
    if [[ "${url}" == *@* ]]; then fail "${r}: remote.origin.url carries userinfo"; fi
    for want in remote.origin.pushurl=no-push://disabled http.receivepack=false http.getanyfile=false; do
        grep -qxF "${want}" <<<"${cfg}" || fail "${r}: ${want} missing"
    done
    ok "${r#/srv/git/repos/} config: no Authorization, no mirror, url without @, push disabled, receivepack/getanyfile off"
done
STATUS_JSON="$(docker exec "${PROXY}" cat /data/status.json)"
if grep -qF -f "${NEEDLES_PAT}" <<<"${STATUS_JSON}" || grep -qF -f "${NEEDLES_HASH}" <<<"${STATUS_JSON}"; then
    fail "PAT or full hash in /data/status.json"
fi
ok "/data/status.json holds no PAT and no full hash"
rc=0
docker exec "${CLIENT}" grep -rlaF -f /tmp/needles-pat /tmp/full /tmp/a /tmp/query /tmp/hashmain /tmp/erin /tmp/fresh \
    >/dev/null 2>&1 || rc=$?
[ "${rc}" = "1" ] || fail "PAT needle in the served clones (or the scan failed, grep exit ${rc})"
ok "served clones (working trees and .git) hold no PAT"

WATCH_PID="$(docker exec "${PROXY}" pgrep -f 'python3 -m app[.]watch' | head -n 1)"
SYNC_PID="$(docker exec "${PROXY}" pgrep -f 'python3 -m app[.]sync' | head -n 1)"
LIGHTTPD_PID="$(docker exec "${PROXY}" pgrep -x lighttpd | head -n 1)"
if [ -z "${WATCH_PID}" ] || [ -z "${SYNC_PID}" ] || [ -z "${LIGHTTPD_PID}" ]; then
    fail "a service process (app.watch, app.sync or lighttpd) is missing"
fi
hits="$(docker exec "${PROXY}" sh -c 'grep -laF -f /tmp/needles-pat /proc/[0-9]*/cmdline 2>/dev/null' || true)"
[ -z "${hits}" ] || fail "PAT needle in a process argv: ${hits}"
hits="$(docker exec "${PROXY}" sh -c 'grep -laF -f /tmp/needles-probe /proc/[0-9]*/cmdline 2>/dev/null' || true)"
grep -qxF "/proc/${WATCH_PID}/cmdline" <<<"${hits}" || fail "cmdline scan does not see the app.watch argv"
ok "no /proc/*/cmdline holds a PAT needle (positive control: the scan sees the app.watch argv)"
hits="$(docker exec --privileged "${PROXY}" sh -c 'grep -laF -f /tmp/needles-pat /proc/[0-9]*/environ 2>/dev/null' \
    || true)"
[ -z "${hits}" ] || fail "PAT needle in a process environment: ${hits}"
hits="$(docker exec --privileged "${PROXY}" sh -c \
    'grep -laF -f /tmp/needles-supervisor /proc/[0-9]*/environ 2>/dev/null' || true)"
grep -qxF "/proc/${SYNC_PID}/environ" <<<"${hits}" || fail "environ scan does not see the sync service's environment"
ok "no /proc/*/environ holds a PAT needle (positive control: the scan sees SUPERVISOR_TOKEN in sync's environment)"
LIGHTTPD_ENV="$(docker exec --privileged "${PROXY}" cat "/proc/${LIGHTTPD_PID}/environ" | tr '\0' '\n')" \
    || fail "cannot read lighttpd's environment"
if grep -qF -f "${NEEDLES_PAT}" <<<"${LIGHTTPD_ENV}"; then fail "PAT needle in lighttpd's environment"; fi
if grep -qF -- "${SUPERVISOR_SENTINEL}" <<<"${LIGHTTPD_ENV}"; then fail "SUPERVISOR_TOKEN in lighttpd's environment"; fi
if grep -qF -- "${OVERRIDE_VAR}" <<<"${LIGHTTPD_ENV}"; then fail "test override in lighttpd's environment"; fi
ok "lighttpd's environment: no PAT, no SUPERVISOR_TOKEN sentinel, no ${OVERRIDE_VAR}"
WATCH_ENV="$(docker exec --privileged "${PROXY}" cat "/proc/${WATCH_PID}/environ" | tr '\0' '\n')" \
    || fail "cannot read access-watch's environment"
if grep -qF -- "${SUPERVISOR_SENTINEL}" <<<"${WATCH_ENV}"; then fail "SUPERVISOR_TOKEN in app.watch's environment"; fi
if grep -qF -- "${OVERRIDE_VAR}" <<<"${WATCH_ENV}"; then fail "test override in app.watch's environment"; fi
ok "access-watch (app.watch) environment: no SUPERVISOR_TOKEN sentinel, no ${OVERRIDE_VAR}"

docker exec "${PROXY}" rm -f /tmp/needles-pat /tmp/needles-hash /tmp/needles-supervisor /tmp/needles-probe
docker exec "${CLIENT}" rm -f /tmp/needles-pat
rm -f "${NEEDLES_PAT}" "${NEEDLES_HASH}"
if docker exec "${PROXY}" sh -c 'ls /tmp/needles-* 2>/dev/null' | grep -q .; then fail "needles left in the proxy"; fi
ok "needles files removed from the containers and the host"

echo "✓ marketplace-repo-proxy Phase 1 verified (criteria 1-5)"
