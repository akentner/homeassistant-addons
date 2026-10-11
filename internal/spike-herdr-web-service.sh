#!/usr/bin/env bash
# spike-herdr-web-service.sh - Phase 23 spike: does herdr-web-service work under a sub-path behind HA ingress?
#
# Proves, inside ONE throwaway container (never on the host):
#   patch applies at the pinned commit -> bun install --frozen-lockfile + bun run build -> production prune ->
#   herdr plugin link + herdr server (startup hook spawns the bun server) -> inner nginx (the add-on, :8099,
#   candidate /services/ block) behind an outer nginx emulating HA ingress (:8123, /api/hassio_ingress/TOKEN/)
#   -> relative redirect, assets, login, session cookie, gated API, WebSocket, CSP/HSTS, Host allow-list.
#
# The plugin is third-party code (reviewed in 23-PLUGIN-REVIEW.md, pin approved by the user). It is fetched, built
# and executed only inside the container; the host only runs docker and reads the output. No add-on or HA
# credentials are passed into the container (no -e of tokens, no mounts besides the patch and the inner script).
#
# Usage: bash internal/spike-herdr-web-service.sh
# Exit:  0 only if C1..C9 all report PASS.
# Env:   WS_PIN overrides the pinned sha (default: the PIN line of 23-PLUGIN-REVIEW.md)

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PHASE_DIR="${REPO_ROOT}/.planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux"
PATCH_FILE="${REPO_ROOT}/coding-assistants/patches/herdr-web-service-subpath.patch"
BUILD_YAML="${REPO_ROOT}/coding-assistants/build.yaml"

# herdr release used by the spike. The Dockerfile ARGs added in plan 23-05 are the source of truth;
# these constants only have to match them (re-check when 23-05 changes them).
HERDR_VERSION="0.9.3"
HERDR_SHA256_X86_64="18a8dc65f1c2fa485884344356dea1cfd911c6f06cf46fa78e193f4087f4dba7"
WS_REPO_URL="https://github.com/i-montes/herdr-web-service.git"
INGRESS_TOKEN="SPIKETOKEN"
FIXTURE_PASSWORD='Verify-Pass1!'

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()   { printf '\033[0;34m%s\033[0m\n' "$*"; }

FAIL=0
CONTAINER="spike-hws-$$"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/spike-hws.XXXXXX")"

# shellcheck disable=SC2317,SC2329 # invoked through the EXIT trap
cleanup() {
    local rc=$?
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    # only the directory this script created
    [ -n "${SCRATCH:-}" ] && [ -d "${SCRATCH}" ] && rm -rf "${SCRATCH}"
    exit "${rc}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------------------------------------------
# Candidate nginx block: the single source. It is mounted into the container (included by the inner nginx) and
# is printed verbatim for the spike document. Indented for pasting into the server block of nginx.conf.
# ---------------------------------------------------------------------------------------------------------------
CANDIDATE_BLOCK="$(cat <<'NGINX'
        # herdr-web-service (plugin on 127.0.0.1:7340), reached through HA ingress as <ingress>/services/
        # relative redirect: an absolute Location would leave the HA ingress prefix
        location = /services { absolute_redirect off; return 301 services/; }
        location /services/ {
            proxy_pass http://127.0.0.1:7340/;              # trailing slash strips the /services/ prefix
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host 127.0.0.1:7340;           # plugin allows only localhost/127.0.0.1/::1 hosts
            proxy_set_header Origin http://127.0.0.1:7340;  # /ws requires an allowed Origin (loopback only)
            proxy_set_header X-Forwarded-For "";            # HA ingress sends these; the plugin trusts them from a
            proxy_set_header X-Forwarded-Proto "";          # loopback peer and would turn cookies Secure / add HSTS
            proxy_hide_header Content-Security-Policy;      # plugin sends frame-ancestors 'none' (blocks the iframe)
            proxy_hide_header Strict-Transport-Security;    # never let it leak onto the HA origin
            add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'" always;
            proxy_read_timeout 86400;
            proxy_send_timeout 86400;
        }
NGINX
)"

# ---------------------------------------------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------------------------------------------
blue "== herdr-web-service sub-path spike (throwaway container) =="

command -v docker >/dev/null 2>&1 || { red "docker not found"; exit 1; }
[ -s "${PATCH_FILE}" ] || { red "patch missing: ${PATCH_FILE}"; exit 1; }

if [ -z "${WS_PIN:-}" ]; then
    WS_PIN="$(sed -n 's/^PIN HERDR_WEB_SERVICE_REF \([0-9a-f]\{40\}\)$/\1/p' "${PHASE_DIR}/23-PLUGIN-REVIEW.md" | head -1)"
fi
[[ "${WS_PIN}" =~ ^[0-9a-f]{40}$ ]] || { red "no 40-char pin (PIN HERDR_WEB_SERVICE_REF in 23-PLUGIN-REVIEW.md)"; exit 1; }
if grep -q 'SCOPE-CHANGE D-05' "${PHASE_DIR}/23-PLUGIN-REVIEW.md"; then
    red "23-PLUGIN-REVIEW.md carries SCOPE-CHANGE D-05: herdr-web-service was not approved"
    exit 1
fi

BASE_IMAGE="$(awk '/^build_from:/{f=1;next} f && /amd64:/{gsub(/"/,"",$2); print $2; exit}' "${BUILD_YAML}")"
[ -n "${BASE_IMAGE}" ] || { red "build_from.amd64 not found in ${BUILD_YAML}"; exit 1; }

blue "pin:        ${WS_PIN}"
blue "base image: ${BASE_IMAGE}"
blue "herdr:      v${HERDR_VERSION}"

printf '%s\n' "${CANDIDATE_BLOCK}" > "${SCRATCH}/candidate.conf"
chmod 0644 "${SCRATCH}/candidate.conf"

# ---------------------------------------------------------------------------------------------------------------
# Inner script (runs inside the container only)
# ---------------------------------------------------------------------------------------------------------------
cat > "${SCRATCH}/inner.sh" <<'INNER'
#!/bin/bash
set -uo pipefail

export DEBIAN_FRONTEND=noninteractive
PLUGIN_DIR=/opt/herdr-plugins/herdr-web-service
OUT=/tmp/out
mkdir -p "${OUT}"

PASSED=0
FAILED=0
CHECK_OK=1
sub()   { echo "    - $*"; }
note()  { echo "NOTE $*"; }
finding() { echo "FINDING $*"; }
die()   { echo "FATAL: $*"; exit 2; }
start_check() { CHECK_OK=1; CHECK_ID="$1"; }
sub_fail() { CHECK_OK=0; echo "    - FAIL: $*"; }
sub_pass() { echo "    - ok: $*"; }
end_check() {
    if [ "${CHECK_OK}" = 1 ]; then
        echo "CHECK ${CHECK_ID} PASS $1"; PASSED=$((PASSED + 1))
    else
        echo "CHECK ${CHECK_ID} FAIL $1"; FAILED=$((FAILED + 1))
    fi
}

echo "== 1. toolchain =="
apt-get update -qq >/dev/null 2>&1 || die "apt-get update failed"
apt-get install -y -qq --no-install-recommends curl ca-certificates git nginx jq python3 unzip procps >/dev/null 2>&1 \
    || die "apt-get install failed"
curl -fsSL https://bun.sh/install | bash >/dev/null 2>&1 || die "bun install failed"
ln -sf /root/.bun/bin/bun /usr/local/bin/bun
ln -sf /root/.bun/bin/bun /usr/local/bin/bunx
finding "bun: $(bun --version)"
finding "nginx: $(nginx -v 2>&1)"

echo "== 2. herdr release binary (digest verified) =="
curl -fsSL -o /usr/local/bin/herdr \
    "https://github.com/herdrdev/herdr/releases/download/v${HERDR_VERSION}/herdr-linux-x86_64" || die "herdr download failed"
echo "${HERDR_SHA256}  /usr/local/bin/herdr" | sha256sum -c - || die "herdr digest mismatch"
chmod +x /usr/local/bin/herdr
finding "herdr: $(herdr --version 2>&1 | head -1)"

echo "== 3. plugin at the pinned commit + patch =="
mkdir -p "${PLUGIN_DIR}"
cd "${PLUGIN_DIR}" || die "cd plugin dir"
git init -q . && git remote add origin "${WS_REPO_URL}" || die "git init"
git fetch -q --depth 1 origin "${WS_PIN}" || die "git fetch of the pin failed"
git checkout -q --detach FETCH_HEAD || die "git checkout failed"
[ "$(git rev-parse HEAD)" = "${WS_PIN}" ] || die "HEAD does not equal the pin"
finding "checkout: $(git rev-parse HEAD)"
git apply --check /spike/patch.diff || die "git apply --check rejected the patch at the pinned commit"
git apply /spike/patch.diff || die "git apply failed"
echo "patch applied; diffstat:"
git diff --stat | sed 's/^/    /'
finding "patch touches server/: $(git diff --name-only | grep -c '^server/')"

echo "== 4. bun install --frozen-lockfile + bun run build =="
bun install --frozen-lockfile >"${OUT}/install.log" 2>&1 || { tail -20 "${OUT}/install.log"; die "bun install --frozen-lockfile failed"; }
tail -3 "${OUT}/install.log" | sed 's/^/    /'
bun run build >"${OUT}/build.log" 2>&1 || { tail -30 "${OUT}/build.log"; die "bun run build failed"; }
tail -8 "${OUT}/build.log" | sed 's/^/    /'
[ -f dist/index.html ] || die "dist/index.html missing after build"
finding "dist/index.html present; dist size: $(du -sh dist | cut -f1)"
finding "node_modules before prune: $(du -sm node_modules | cut -f1) MB"
finding "bun cache before removal: $(du -sm /root/.bun/install/cache 2>/dev/null | cut -f1) MB"
echo "built index.html:"
sed 's/^/    /' dist/index.html

echo "== 5. production prune =="
PRUNE_OK=1
rm -rf node_modules
bun install --frozen-lockfile --production >"${OUT}/prune.log" 2>&1 || PRUNE_OK=0
tail -3 "${OUT}/prune.log" | sed 's/^/    /'
rm -rf /root/.bun/install/cache
finding "node_modules after prune: $(du -sm node_modules 2>/dev/null | cut -f1) MB (prune exit ok=${PRUNE_OK})"
finding "bun cache after removal: $([ -d /root/.bun/install/cache ] && echo still present || echo gone)"

echo "== 6. herdr server + plugin startup hook =="
export XDG_CONFIG_HOME=/data/.config
export SHELL=/bin/sh
mkdir -p "${XDG_CONFIG_HOME}"
herdr plugin link "${PLUGIN_DIR}" 2>&1 | sed 's/^/    /'
CONFIG_DIR="$(herdr plugin config-dir imontes.herdr-web-service)"
finding "plugin config dir: ${CONFIG_DIR}"
( cd /tmp && nohup herdr server >"${OUT}/herdr-server.log" 2>&1 & )
HEALTH_UP=0
for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null http://127.0.0.1:7340/api/health 2>/dev/null; then HEALTH_UP=1; break; fi
    sleep 0.5
done
echo "--- herdr server log ---"; sed 's/^/    /' "${OUT}/herdr-server.log"
if [ "${HEALTH_UP}" != 1 ]; then
    echo "--- diagnostics ---"
    herdr plugin list 2>&1 | sed 's/^/    /' || true
    find /data /root -name 'server.log' -o -name 'server.pid' 2>/dev/null | sed 's/^/    /'
    die "the plugin startup hook did not bring up /api/health"
fi
finding "startup hook: /api/health answered on 127.0.0.1:7340 without a manual start"
finding "bun server process: $(pgrep -af 'server/index.ts' | head -1)"
STATE_PID="$(find /data /root -name server.pid 2>/dev/null | head -1)"
finding "plugin state dir (server.pid): ${STATE_PID:-not found}"
finding "plugin state dir listing: $(ls "$(dirname "${STATE_PID:-/nonexistent}")" 2>/dev/null | tr '\n' ' ')"
finding "scripts/bun.sh with a minimal PATH: $(cd "${PLUGIN_DIR}" && env -i PATH=/usr/local/bin:/usr/bin:/bin sh scripts/bun.sh --version 2>&1 | head -1)"
curl -sS http://127.0.0.1:7340/api/health | sed 's/^/FINDING health body: /'; echo

echo "== 7. nginx: inner (add-on, :8099) and outer (HA ingress emulation, :8123) =="
cat > /tmp/inner.conf <<EOF
worker_processes 1;
error_log /tmp/nginx-inner.err warn;
pid /tmp/nginx-inner.pid;
daemon off;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log off;

    map \$http_upgrade \$connection_upgrade {
        default upgrade;
        ''      close;
    }

    server {
        listen 8099;
        server_name _;
        include /spike/candidate.conf;
    }
}
EOF
cat > /tmp/outer.conf <<EOF
worker_processes 1;
error_log /tmp/nginx-outer.err warn;
pid /tmp/nginx-outer.pid;
daemon off;
events { worker_connections 1024; }
http {
    access_log off;
    map \$http_upgrade \$connection_upgrade {
        default upgrade;
        ''      close;
    }
    server {
        listen 8123;
        server_name _;
        # emulates the HA ingress proxy: strips the token prefix, forwards Host, Origin and Cookie unchanged and
        # adds the X-Forwarded-* / X-Ingress-Path headers HA adds (worst case: https)
        location /api/hassio_ingress/${INGRESS_TOKEN}/ {
            proxy_pass http://127.0.0.1:8099/;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection \$connection_upgrade;
            proxy_set_header X-Forwarded-For \$remote_addr;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Ingress-Path /api/hassio_ingress/${INGRESS_TOKEN};
            proxy_read_timeout 86400;
            proxy_send_timeout 86400;
        }
    }
}
EOF
nginx -t -c /tmp/inner.conf 2>&1 | sed 's/^/    inner: /'
nginx -t -c /tmp/outer.conf 2>&1 | sed 's/^/    outer: /'
nginx -c /tmp/inner.conf >"${OUT}/nginx-inner.out" 2>&1 &
nginx -c /tmp/outer.conf >"${OUT}/nginx-outer.out" 2>&1 &
sleep 1.5

BASE="http://127.0.0.1:8123/api/hassio_ingress/${INGRESS_TOKEN}"
req() { curl -sS --max-time 20 -H 'Host: ha.invalid:8123' -H 'Origin: http://ha.invalid:8123' "$@"; }
status() { req -o /dev/null -w '%{http_code}' "$@"; }
first_line() { head -1 "$1" | tr -d '\r'; }
header_count() { grep -ic "^$2:" "$1" || true; }

echo
echo "== 8. checks (all through ${BASE}/services/) =="

# ---- C1 relative redirect
start_check C1
req -D "${OUT}/c1.h" -o /dev/null "${BASE}/services" || true
l1="$(first_line "${OUT}/c1.h")"; loc="$(grep -i '^location:' "${OUT}/c1.h" | tr -d '\r')"
case "${l1}" in *" 301 "*) sub_pass "status: ${l1}" ;; *) sub_fail "expected 301, got: ${l1}" ;; esac
if [ "${loc,,}" = "location: services/" ]; then sub_pass "${loc}"; else sub_fail "expected a relative 'Location: services/', got: ${loc}"; fi
end_check "GET /services -> 301 with relative Location"

# ---- C2 index + assets
start_check C2
req -D "${OUT}/idx.h" -o "${OUT}/idx.html" "${BASE}/services/" || true
l1="$(first_line "${OUT}/idx.h")"
case "${l1}" in *" 200 "*) sub_pass "index: ${l1}" ;; *) sub_fail "index: ${l1}" ;; esac
python3 -I - "${OUT}/idx.html" "${BASE}/services/" "${OUT}/asset-urls.txt" <<'PY' || CHECK_OK=0
import re, sys, urllib.parse
html = open(sys.argv[1], encoding="utf-8").read()
page = sys.argv[2]
refs = re.findall(r'\b(?:src|href)\s*=\s*["\']([^"\']*)["\']', html)
bad = [r for r in refs if r.startswith("/") or re.match(r"^[a-z][a-z0-9+.-]*:", r, re.I) and not r.startswith("data:")]
urls = [urllib.parse.urljoin(page, r) for r in refs if r and not r.startswith(("#", "data:"))]
open(sys.argv[3], "w").write("\n".join(urls) + "\n")
print(f"    - index references: {len(refs)} ({len(urls)} fetchable)")
for r in refs:
    print(f"        {r}")
if bad:
    print(f"    - FAIL: root-absolute or external src/href in the index: {bad}")
    sys.exit(1)
if not refs:
    print("    - FAIL: the index references no asset at all")
    sys.exit(1)
print("    - ok: no root-absolute src/href attribute")
PY
while IFS= read -r u; do
    [ -n "${u}" ] || continue
    c="$(status "${u}")"
    if [ "${c}" = 200 ]; then sub_pass "200 ${u#"${BASE}"}"; else sub_fail "${c} ${u#"${BASE}"}"; fi
done < "${OUT}/asset-urls.txt"
# css url() references must be relative too (fonts/images)
css_bad="$(cat "${PLUGIN_DIR}"/dist/assets/*.css 2>/dev/null | grep -oE 'url\((["'"'"']?)/[^)]*' | head -5)"
if [ -z "${css_bad}" ]; then sub_pass "no root-absolute url() in the built CSS"; else sub_fail "root-absolute css url(): ${css_bad}"; fi
end_check "index 200, no root-absolute src/href, every referenced asset 200"

# ---- C3 built JS has no root-absolute string
start_check C3
python3 -I - "${PLUGIN_DIR}/dist" <<'PY' || CHECK_OK=0
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
pat = re.compile(r"""["'`]/(?:api/|ws["'`]|sw\.js|assets/|manifest|icon|apple-touch)""")
hits = []
files = list(root.rglob("*.js"))
for f in files:
    for m in pat.finditer(f.read_text(encoding="utf-8", errors="replace")):
        hits.append((f.name, m.group(0)))
print(f"    - scanned {len(files)} JS file(s)")
if hits:
    print(f"    - FAIL: root-absolute strings in built JS: {hits[:10]}")
    sys.exit(1)
print("    - ok: no quote-prefixed /api/, /ws, /sw.js, /assets/, /manifest, /icon string")
PY
end_check "built JS contains no root-absolute /api/, /ws, /sw.js string"

# ---- C4 login: 503 -> (set password) -> 401 -> 204 + cookie
start_check C4
sess0="$(req "${BASE}/services/api/session")"
echo "    - session before the password exists: ${sess0}"
c="$(status -X POST -H 'content-type: application/json' --data '{"password":"x","remember":false}' "${BASE}/services/api/auth/login")"
if [ "${c}" = 503 ]; then sub_pass "login before a password exists: 503"; else sub_fail "login before a password exists: ${c} (expected 503)"; fi
(
    cd "${PLUGIN_DIR}" && printf '%s\n' "${FIXTURE_PASSWORD}" | HERDR_PLUGIN_CONFIG_DIR="${CONFIG_DIR}" bun scripts/plugin.ts set-password
) >"${OUT}/setpw.log" 2>&1 && sub_pass "set-password via pipe: $(tr '\n' ' ' <"${OUT}/setpw.log" | cut -c1-120)" \
    || sub_fail "set-password failed: $(cat "${OUT}/setpw.log")"
[ -f "${CONFIG_DIR}/auth.json" ] && sub_pass "auth.json written in ${CONFIG_DIR}" || sub_fail "auth.json missing in ${CONFIG_DIR}"
finding "auth.json mode: $(stat -c '%a' "${CONFIG_DIR}/auth.json" 2>/dev/null)"
c="$(status -X POST -H 'content-type: application/json' --data '{"password":"Wrong-Pass9?","remember":false}' "${BASE}/services/api/auth/login")"
if [ "${c}" = 401 ]; then sub_pass "wrong password: 401"; else sub_fail "wrong password: ${c} (expected 401)"; fi
req -c "${OUT}/jar" -D "${OUT}/login.h" -o /dev/null -X POST -H 'content-type: application/json' \
    --data "{\"password\":\"${FIXTURE_PASSWORD}\",\"remember\":false}" "${BASE}/services/api/auth/login" || true
l1="$(first_line "${OUT}/login.h")"
case "${l1}" in *" 204 "*) sub_pass "right password: ${l1}" ;; *) sub_fail "right password: ${l1} (expected 204)" ;; esac
sc="$(grep -i '^set-cookie:' "${OUT}/login.h" | tr -d '\r')"
echo "    - ${sc%%=*}=<token redacted>${sc#*;}"
case "${sc}" in *hwv_session=*) sub_pass "Set-Cookie carries hwv_session" ;; *) sub_fail "no hwv_session cookie" ;; esac
case "${sc,,}" in *httponly*) sub_pass "cookie is HttpOnly" ;; *) sub_fail "cookie is not HttpOnly" ;; esac
case "${sc,,}" in *secure*) sub_fail "cookie is Secure (X-Forwarded-Proto leaked through)" ;; *) sub_pass "cookie has no Secure flag" ;; esac
end_check "login 503 before password, 401 wrong, 204 + HttpOnly cookie right"

# ---- C5 session reporting + gated API
start_check C5
echo "    - session, no cookie (before the password was set): ${sess0}"
printf '%s' "${sess0}" | jq -e '.setup_required == true' >/dev/null 2>&1 \
    && sub_pass "setup_required true before a password exists" || sub_fail "setup_required not true before a password exists"
s_cookie="$(req -b "${OUT}/jar" "${BASE}/services/api/session")"
s_anon="$(req "${BASE}/services/api/session")"
printf '%s' "${s_cookie}" | jq -e '.authenticated == true' >/dev/null 2>&1 \
    && sub_pass "authenticated true with the cookie" || sub_fail "authenticated not true with the cookie: ${s_cookie}"
printf '%s' "${s_anon}" | jq -e '.authenticated == false' >/dev/null 2>&1 \
    && sub_pass "authenticated false without the cookie" || sub_fail "authenticated not false without the cookie: ${s_anon}"
c="$(status -b "${OUT}/jar" "${BASE}/services/api/roster")"
if [ "${c}" = 200 ]; then sub_pass "gated /api/roster with the cookie: 200"; else sub_fail "gated /api/roster with the cookie: ${c}"; fi
c="$(status "${BASE}/services/api/roster")"
if [ "${c}" = 401 ]; then sub_pass "gated /api/roster without the cookie: 401"; else sub_fail "gated /api/roster without the cookie: ${c}"; fi
end_check "session ungated (setup_required / authenticated), /api/roster gated"

# ---- C6 WebSocket
start_check C6
ws_try() {
    # $1 = output file, rest = extra curl args; a timeout after the 101 is expected
    local f="$1"; shift
    req --http1.1 --max-time 3 -N -D "${f}" -o /dev/null \
        -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' \
        -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' "$@" "${BASE}/services/ws" || true  # gitleaks:allow (RFC 6455 example nonce)
}
ws_try "${OUT}/ws-cookie.h" -b "${OUT}/jar"
ws_try "${OUT}/ws-anon.h"
l_c="$(first_line "${OUT}/ws-cookie.h")"; l_a="$(first_line "${OUT}/ws-anon.h")"
case "${l_c}" in *" 101 "*) sub_pass "with the cookie: ${l_c}" ;; *) sub_fail "with the cookie: ${l_c:-<no response>} (expected 101)" ;; esac
case "${l_a}" in *" 101 "*) sub_fail "without the cookie: ${l_a} (must be refused)" ;; *) sub_pass "without the cookie refused: ${l_a:-<no response>}" ;; esac
end_check "WebSocket upgrade 101 with the cookie, refused without"

# ---- C7 headers on the index
start_check C7
n_csp="$(header_count "${OUT}/idx.h" content-security-policy)"
csp="$(grep -i '^content-security-policy:' "${OUT}/idx.h" | tr -d '\r')"
if [ "${n_csp}" = 1 ]; then sub_pass "exactly one Content-Security-Policy header"; else sub_fail "${n_csp} Content-Security-Policy headers"; fi
echo "    - ${csp}"
case "${csp}" in *"frame-ancestors 'self'"*) sub_pass "frame-ancestors 'self'" ;; *) sub_fail "frame-ancestors 'self' missing" ;; esac
case "${csp}" in *"'none'"*"frame-ancestors"*|*"frame-ancestors 'none'"*) sub_fail "frame-ancestors 'none' present" ;; *) sub_pass "no frame-ancestors 'none'" ;; esac
n_hsts="$(header_count "${OUT}/idx.h" strict-transport-security)"
if [ "${n_hsts}" = 0 ]; then sub_pass "no Strict-Transport-Security header"; else sub_fail "Strict-Transport-Security present"; fi
# the authenticated login response must not leak it either
n_hsts2="$(header_count "${OUT}/login.h" strict-transport-security)"
if [ "${n_hsts2}" = 0 ]; then sub_pass "no Strict-Transport-Security on the login response"; else sub_fail "Strict-Transport-Security on the login response"; fi
end_check "one CSP header with frame-ancestors 'self', no HSTS"

# ---- C8 the plugin's Host allow-list is intact when reached directly
start_check C8
c="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' -H 'Host: evil.invalid' http://127.0.0.1:7340/api/session)"
case "${c}" in 4??) sub_pass "direct request with Host: evil.invalid: ${c}" ;; *) sub_fail "direct request with Host: evil.invalid: ${c} (expected 4xx)" ;; esac
c="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:7340/api/session)"
if [ "${c}" = 200 ]; then sub_pass "direct request with the loopback Host: ${c}"; else sub_fail "direct request with the loopback Host: ${c}"; fi
end_check "plugin rejects a spoofed Host when reached directly"

# ---- C9 production prune
start_check C9
if [ "${PRUNE_OK}" = 1 ]; then sub_pass "bun install --frozen-lockfile --production succeeded"; else sub_fail "production install failed: $(tail -3 "${OUT}/prune.log")"; fi
[ -f "${PLUGIN_DIR}/dist/index.html" ] && sub_pass "dist/index.html present after the prune" || sub_fail "dist/index.html missing after the prune"
sub_pass "the whole run above used the pruned node_modules ($(du -sm "${PLUGIN_DIR}/node_modules" | cut -f1) MB), server healthy, login and WebSocket worked"
end_check "production prune keeps the server startable"

echo
echo "== summary =="
echo "RESULT passed=${PASSED} failed=${FAILED}"
[ "${FAILED}" = 0 ] && [ "${PASSED}" = 9 ] && exit 0
exit 1
INNER
chmod 0644 "${SCRATCH}/inner.sh"

# ---------------------------------------------------------------------------------------------------------------
# Run the container: read-only mounts, no host credentials in the environment
# ---------------------------------------------------------------------------------------------------------------
blue "== running the throwaway container ${CONTAINER} =="
docker run --rm --name "${CONTAINER}" \
    --security-opt no-new-privileges \
    --entrypoint /bin/bash \
    -e HERDR_VERSION="${HERDR_VERSION}" \
    -e HERDR_SHA256="${HERDR_SHA256_X86_64}" \
    -e WS_REPO_URL="${WS_REPO_URL}" \
    -e WS_PIN="${WS_PIN}" \
    -e INGRESS_TOKEN="${INGRESS_TOKEN}" \
    -e FIXTURE_PASSWORD="${FIXTURE_PASSWORD}" \
    -v "${SCRATCH}/inner.sh:/spike/inner.sh:ro" \
    -v "${SCRATCH}/candidate.conf:/spike/candidate.conf:ro" \
    -v "${PATCH_FILE}:/spike/patch.diff:ro" \
    "${BASE_IMAGE}" /spike/inner.sh 2>&1 | tee "${SCRATCH}/run.log"
CONTAINER_RC="${PIPESTATUS[0]}"

# ---------------------------------------------------------------------------------------------------------------
# Verdict on the host: nine PASS lines, no FAIL, clean container exit
# ---------------------------------------------------------------------------------------------------------------
echo
blue "== check table =="
n_pass=0
for id in C1 C2 C3 C4 C5 C6 C7 C8 C9; do
    line="$(grep -E "^CHECK ${id} (PASS|FAIL) " "${SCRATCH}/run.log" | tail -1)"
    case "${line}" in
        *" PASS "*) green "  ${line#CHECK }"; n_pass=$((n_pass + 1)) ;;
        *" FAIL "*) red "  ${line#CHECK }"; FAIL=1 ;;
        *) red "  ${id} did not report (the container stopped early)"; FAIL=1 ;;
    esac
done
[ "${CONTAINER_RC}" = 0 ] || { red "container exit code ${CONTAINER_RC}"; FAIL=1; }
[ "${n_pass}" = 9 ] || FAIL=1

echo
blue "== candidate nginx block (single source, validated above) =="
printf '%s\n' "${CANDIDATE_BLOCK}"

echo
if [ "${FAIL}" = 0 ]; then
    green "SPIKE RESULT: PASS (${n_pass}/9)"
else
    red "SPIKE RESULT: FAIL (${n_pass}/9 passed)"
fi
exit "${FAIL}"
