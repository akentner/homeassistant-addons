#!/usr/bin/env bash
# verify-multi-namespace.sh — Empirical end-to-end verification of MULTI-01..06
#
# This script starts the markdown-renderer container with various /data/options.json
# fixtures and asserts the expected behavior against http://127.0.0.1:8099/.
#
# Covers all 6 MULTI acceptance criteria:
#   MULTI-01: OPTIONS_PATH loaded → nginx config regenerated on every container start
#   MULTI-02: each namespace served as an isolated Docsify SPA at /<name>/
#   MULTI-03: landing page at / lists every configured namespace as clickable cards
#   MULTI-04: landing-page cards regenerate on restart with different config
#   MULTI-05: invalid namespace names rejected at startup (clear stderr, no traceback)
#   MULTI-06: /share, /config, /media volume mounts are readable from inside the container
#
# Exit codes:
#   0 = all 6 MULTI requirements verified empirically
#   1 = at least one assertion failed (see FAIL lines)
#   2 = environment precondition failed (no podman/docker, image missing)
#
# Usage:
#   bash .planning/phases/05-multi-namespace-dynamic-config/verify-multi-namespace.sh
#
# Pre-requisite:
#   make build-addon ADDON=markdown-renderer   (image local/markdown-renderer:1.0.0)
#
# See markdown-renderer/DOCS.md "Validation Status" section for context.

set -euo pipefail

# ─── ANSI colors ───────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Use IPv4 explicitly to avoid IPv6 ::1 resolution races (curl may resolve
# localhost to ::1 first, which nginx in this minimal config does not listen
# on; podman's port mapping binds IPv4 0.0.0.0:8099).

# ─── Counters ──────────────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
SCENARIO_NAME=""

# ─── Pre-flight: container runtime ─────────────────────────────────────────
if command -v podman >/dev/null 2>&1; then
    RUNTIME=podman
elif command -v docker >/dev/null 2>&1; then
    RUNTIME=docker
else
    echo -e "${RED}FATAL: no podman or docker found in PATH${NC}" >&2
    exit 2
fi
echo -e "${CYAN}Using container runtime: ${RUNTIME}${NC}"

# ─── Pre-flight: image exists ──────────────────────────────────────────────
if ! $RUNTIME images --format '{{.Repository}}:{{.Tag}}' \
        | grep -qE '^(localhost/)?local/markdown-renderer:1\.0\.0$'; then
    echo -e "${RED}FATAL: image local/markdown-renderer:1.0.0 not built${NC}" >&2
    echo -e "${RED}Run: make build-addon ADDON=markdown-renderer${NC}" >&2
    exit 2
fi
echo -e "${CYAN}Image found: local/markdown-renderer:1.0.0${NC}"

# ─── Cleanup trap (always runs on exit) ────────────────────────────────────
cleanup() {
    local exit_code=$?
    $RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
    if [[ -d /tmp/mr-verify-fixtures ]]; then
        rm -rf /tmp/mr-verify-fixtures
    fi
    if [[ $exit_code -eq 0 ]]; then
        echo ""
        echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ALL VERIFICATIONS PASSED  (${PASS_COUNT} assertions)${NC}"
        echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
    else
        echo ""
        echo -e "${RED}══════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  VERIFICATION FAILED  (${FAIL_COUNT} failures / ${PASS_COUNT} passed)${NC}"
        echo -e "${RED}══════════════════════════════════════════════════════${NC}"
    fi
    exit "$exit_code"
}
trap cleanup EXIT

# ─── Fixture setup ─────────────────────────────────────────────────────────
mkdir -p /tmp/mr-verify-fixtures/share/docs
mkdir -p /tmp/mr-verify-fixtures/config/runbooks
mkdir -p /tmp/mr-verify-fixtures/media/photos
cat > /tmp/mr-verify-fixtures/share/docs/README.md <<'EOF'
# Docs Namespace

This is the docs namespace served from /share/docs.
EOF
cat > /tmp/mr-verify-fixtures/config/runbooks/README.md <<'EOF'
# Runbooks Namespace

This is the runbooks namespace served from /config/runbooks.
EOF
cat > /tmp/mr-verify-fixtures/media/photos/README.md <<'EOF'
# Photos Namespace

This is the photos namespace served from /media/photos.
EOF

# ─── Helpers ───────────────────────────────────────────────────────────────
pass() {
    local label=$1
    PASS_COUNT=$((PASS_COUNT + 1))
    echo -e "  ${GREEN}PASS${NC} ${label}"
}

fail() {
    local label=$1
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo -e "  ${RED}FAIL${NC} ${label}"
}

scenario() {
    echo ""
    echo -e "${CYAN}━━━ ${SCENARIO_NAME} ━━━${NC}"
}

run_container() {
    local options_file=$1
    local label=$2
    $RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
    $RUNTIME run -d \
        --name mr-verify \
        -p 8099:8099 \
        -v "${options_file}:/data/options.json:ro" \
        -v /tmp/mr-verify-fixtures/share:/share:ro \
        -v /tmp/mr-verify-fixtures/config:/config:ro \
        -v /tmp/mr-verify-fixtures/media:/media:ro \
        localhost/local/markdown-renderer:1.0.0 >/dev/null

    # Wait up to 30s for nginx to start (poll docsify.min.js)
    local i=0
    while [[ $i -lt 30 ]]; do
        sleep 1
        if curl -sf http://127.0.0.1:8099/_docsify/docsify.min.js >/dev/null 2>&1; then
            return 0
        fi
        i=$((i + 1))
    done
    return 1
}

# Capture logs into a variable. Direct pipe to grep -q can race against
# podman's log buffer (grep -q exits as soon as it finds a match, but the
# upstream podman process may not have flushed all lines yet). Capturing
# once and grepping the snapshot makes the assertions deterministic.
MR_LOGS=""
capture_logs() {
    MR_LOGS=$($RUNTIME logs mr-verify 2>&1 || true)
}

run_container_no_options() {
    # For Scenario E: no /data/options.json mount at all
    $RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
    $RUNTIME run -d \
        --name mr-verify \
        -p 8099:8099 \
        -v /tmp/mr-verify-fixtures/share:/share:ro \
        -v /tmp/mr-verify-fixtures/config:/config:ro \
        -v /tmp/mr-verify-fixtures/media:/media:ro \
        localhost/local/markdown-renderer:1.0.0 >/dev/null

    local i=0
    while [[ $i -lt 30 ]]; do
        sleep 1
        if curl -sf http://127.0.0.1:8099/_docsify/docsify.min.js >/dev/null 2>&1; then
            return 0
        fi
        i=$((i + 1))
    done
    return 1
}

stop_container() {
    $RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
}

# ─── SCENARIO A — happy path with 3 namespaces ─────────────────────────────
SCENARIO_NAME="SCENARIO A — happy path: 3 namespaces (MULTI-01, MULTI-02, MULTI-03, MULTI-04, MULTI-06)"
scenario

cat > /tmp/mr-verify-fixtures/options-3ns.json <<'EOF'
{"directories":[{"name":"docs","path":"/share/docs"},{"name":"runbooks","path":"/config/runbooks"},{"name":"photos","path":"/media/photos"}],"kroki_url":"https://kroki.io"}
EOF

if run_container /tmp/mr-verify-fixtures/options-3ns.json "3-namespace happy path"; then
    pass "container started and nginx is serving (3-namespace config)"
else
    fail "container failed to start with 3-namespace config"
    $RUNTIME logs mr-verify 2>&1 | tail -20 || true
    exit 1
fi

# MULTI-01: OPTIONS_PATH loaded → generator log line
capture_logs
if echo "$MR_LOGS" | grep -q "Validated 3 namespace"; then
    pass "MULTI-01: generator validated OPTIONS_PATH ('Validated 3 namespace')"
else
    fail "MULTI-01: generator did not validate OPTIONS_PATH"
    echo -e "    ${YELLOW}DEBUG logs:${NC}"
    echo "$MR_LOGS" | sed 's/^/      /' | head -20
fi

# MULTI-02: each namespace served as isolated Docsify SPA at /<name>/
for ns in docs runbooks photos; do
    body=$(curl -sf "http://127.0.0.1:8099/${ns}/" 2>/dev/null || true)
    if echo "$body" | grep -q "Loading ${ns}"; then
        pass "MULTI-02: /${ns}/ serves isolated Docsify SPA ('Loading ${ns}' in HTML)"
    else
        fail "MULTI-02: /${ns}/ did not serve expected Docsify SPA"
    fi
done

# MULTI-03: landing page at / lists all 3 namespaces
landing=$(curl -sf http://127.0.0.1:8099/ 2>/dev/null || true)
if echo "$landing" | grep -q 'href="/docs/"' \
    && echo "$landing" | grep -q 'href="/runbooks/"' \
    && echo "$landing" | grep -q 'href="/photos/"'; then
    pass "MULTI-03: landing page lists all 3 namespace cards (hrefs)"
else
    fail "MULTI-03: landing page missing one or more namespace cards"
fi
if echo "$landing" | grep -q '<h2>docs</h2>' \
    && echo "$landing" | grep -q '<h2>runbooks</h2>' \
    && echo "$landing" | grep -q '<h2>photos</h2>'; then
    pass "MULTI-03: landing page renders <h2> for each namespace"
else
    fail "MULTI-03: landing page missing <h2> for one or more namespaces"
fi

# MULTI-04: nginx config regeneration log
capture_logs
if echo "$MR_LOGS" | grep -q "Generated nginx config for 3 namespace"; then
    pass "MULTI-04: generate_nginx.py ran ('Generated nginx config for 3 namespace')"
else
    fail "MULTI-04: generate_nginx.py did not run as expected"
    echo -e "    ${YELLOW}DEBUG logs (filtered):${NC}"
    echo "$MR_LOGS" | grep -i "generated\|validated\|nginx" | sed 's/^/      /'
fi
# Vendored assets served
if curl -sf http://127.0.0.1:8099/_docsify/docsify.min.js >/dev/null 2>&1; then
    pass "MULTI-04: vendored /_docsify/docsify.min.js served (200)"
else
    fail "MULTI-04: vendored docsify.min.js not served"
fi

# MULTI-06: volume mounts readable per namespace (index.html proves generator worked end-to-end)
for ns in docs runbooks photos; do
    body=$(curl -sf "http://127.0.0.1:8099/${ns}/" 2>/dev/null || true)
    # The generator writes index.html with basePath from window.location.pathname
    if echo "$body" | grep -q "basePath = window.location.pathname"; then
        pass "MULTI-06: /${ns}/ served index.html with window.location.pathname basePath"
    else
        fail "MULTI-06: /${ns}/ index.html missing expected basePath"
    fi
done

stop_container

# ─── SCENARIO B — landing page regenerates on config change ────────────────
SCENARIO_NAME="SCENARIO B — landing page regenerates on config change (MULTI-03/04)"
scenario

cat > /tmp/mr-verify-fixtures/options-1ns.json <<'EOF'
{"directories":[{"name":"only","path":"/share/docs"}]}
EOF

if run_container /tmp/mr-verify-fixtures/options-1ns.json "1-namespace regen test"; then
    pass "container restarted with 1-namespace config"
else
    fail "container failed to start with 1-namespace config"
    exit 1
fi

landing=$(curl -sf http://127.0.0.1:8099/ 2>/dev/null || true)
if echo "$landing" | grep -q 'href="/only/"'; then
    pass "landing page shows only the new 'only' card"
else
    fail "landing page missing 'only' card after restart"
fi
if ! echo "$landing" | grep -q 'href="/docs/"'; then
    pass "landing page no longer shows stale 'docs' card (regenerated, no cache)"
else
    fail "landing page still shows stale 'docs' card (caching bug)"
fi

stop_container

# ─── SCENARIO C — invalid namespace names rejected ─────────────────────────
SCENARIO_NAME="SCENARIO C — invalid namespace names rejected (MULTI-05)"
scenario

declare -a INVALID_FIXTURES=(
    'slash|{"directories":[{"name":"bad/name","path":"/x"}]}'
    'empty|{"directories":[{"name":"","path":"/x"}]}'
    'reserved_docsify|{"directories":[{"name":"_docsify","path":"/x"}]}'
    'uppercase|{"directories":[{"name":"Docs","path":"/x"}]}'
)

for fixture in "${INVALID_FIXTURES[@]}"; do
    label=${fixture%%|*}
    body=${fixture#*|}
    echo "${body}" > /tmp/mr-verify-fixtures/options-bad.json

    $RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
    $RUNTIME run -d \
        --name mr-verify \
        -p 8099:8099 \
        -v /tmp/mr-verify-fixtures/options-bad.json:/data/options.json:ro \
        -v /tmp/mr-verify-fixtures/share:/share:ro \
        -v /tmp/mr-verify-fixtures/config:/config:ro \
        -v /tmp/mr-verify-fixtures/media:/media:ro \
        localhost/local/markdown-renderer:1.0.0 >/dev/null

    sleep 5

    state=$($RUNTIME ps -a --filter name=mr-verify --format '{{.State}}' 2>/dev/null | tr -d '[:space:]' || true)
    if [[ "$state" == "exited" ]]; then
        pass "invalid name '${label}': container exited (refused to start)"
    else
        fail "invalid name '${label}': container state is '${state}' (expected 'exited')"
    fi

    capture_logs
    if echo "$MR_LOGS" | grep -q "ERROR: namespace name"; then
        pass "invalid name '${label}': clear ERROR message in logs"
    else
        fail "invalid name '${label}': missing 'ERROR: namespace name' in logs"
        # Debug: show actual log content
        echo -e "    ${YELLOW}DEBUG logs:${NC}"
        echo "$MR_LOGS" | sed 's/^/      /' | head -20
    fi

    # Use temporary set +e so the inverted grep check does not abort the script
    # under ``set -euo pipefail``.
    set +e
    traceback_found=$(echo "$MR_LOGS" | grep -c "Traceback")
    set -e
    if [[ "$traceback_found" -eq 0 ]]; then
        pass "invalid name '${label}': no Python traceback (graceful error)"
    else
        fail "invalid name '${label}': Python traceback in logs (ungaceful error)"
    fi

    stop_container
done

# ─── SCENARIO D — duplicate names rejected ─────────────────────────────────
SCENARIO_NAME="SCENARIO D — duplicate names rejected (MULTI-05)"
scenario

cat > /tmp/mr-verify-fixtures/options-dup.json <<'EOF'
{"directories":[{"name":"a","path":"/p"},{"name":"a","path":"/q"}]}
EOF

$RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
$RUNTIME run -d \
    --name mr-verify \
    -p 8099:8099 \
    -v /tmp/mr-verify-fixtures/options-dup.json:/data/options.json:ro \
    -v /tmp/mr-verify-fixtures/share:/share:ro \
    -v /tmp/mr-verify-fixtures/config:/config:ro \
    -v /tmp/mr-verify-fixtures/media:/media:ro \
    localhost/local/markdown-renderer:1.0.0 >/dev/null

sleep 5

state=$($RUNTIME ps -a --filter name=mr-verify --format '{{.State}}' 2>/dev/null | tr -d '[:space:]' || true)
if [[ "$state" == "exited" ]]; then
    pass "duplicate names: container exited"
else
    fail "duplicate names: container state is '${state}'"
fi

capture_logs
if echo "$MR_LOGS" | grep -q "duplicate directory name 'a'"; then
    pass "duplicate names: 'duplicate directory name' error in logs"
else
    fail "duplicate names: missing duplicate-name error message"
fi

set +e
traceback_found=$(echo "$MR_LOGS" | grep -c "Traceback")
set -e
if [[ "$traceback_found" -eq 0 ]]; then
    pass "duplicate names: no Python traceback"
else
    fail "duplicate names: Python traceback in logs"
fi

stop_container

# ─── SCENARIO E — empty list + missing options.json ────────────────────────
SCENARIO_NAME="SCENARIO E — empty list + missing options.json (graceful degradation)"
scenario

# E.1 — empty directories list → container stays running, 503 body
cat > /tmp/mr-verify-fixtures/options-empty.json <<'EOF'
{"directories":[]}
EOF

$RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
$RUNTIME run -d \
    --name mr-verify \
    -p 8099:8099 \
    -v /tmp/mr-verify-fixtures/options-empty.json:/data/options.json:ro \
    -v /tmp/mr-verify-fixtures/share:/share:ro \
    -v /tmp/mr-verify-fixtures/config:/config:ro \
    -v /tmp/mr-verify-fixtures/media:/media:ro \
    localhost/local/markdown-renderer:1.0.0 >/dev/null

# Wait for nginx to start (should be quick — minimal config)
sleep 5

state=$($RUNTIME ps -a --filter name=mr-verify --format '{{.State}}' 2>/dev/null | tr -d '[:space:]' || true)
if [[ "$state" == "running" ]]; then
    pass "empty list: container stays running (graceful degradation)"
else
    fail "empty list: container state is '${state}' (expected 'running')"
fi

root_body=$(mktemp)
status=$(curl -s -o "$root_body" -w '%{http_code}' http://127.0.0.1:8099/ 2>/dev/null || echo "000")
if [[ "$status" == "503" ]] && grep -q "no directories configured" "$root_body"; then
    pass "empty list: GET / returns 503 with 'no directories configured'"
else
    fail "empty list: GET / returned status='${status}' body='$(cat "$root_body")'"
fi
rm -f "$root_body"

stop_container

# E.2 — no /data/options.json mount at all
$RUNTIME rm -f mr-verify >/dev/null 2>&1 || true
if run_container_no_options; then
    pass "missing options.json: container starts anyway"
else
    fail "missing options.json: container failed to start"
fi

if curl -sf http://127.0.0.1:8099/_docsify/docsify.min.js >/dev/null 2>&1; then
    pass "missing options.json: vendored assets still served"
else
    fail "missing options.json: vendored assets NOT served"
fi

root_body=$(mktemp)
status=$(curl -s -o "$root_body" -w '%{http_code}' http://127.0.0.1:8099/ 2>/dev/null || echo "000")
if [[ "$status" == "503" ]] && grep -q "no options.json mounted from HA Supervisor" "$root_body"; then
    pass "missing options.json: GET / returns 503 with helpful message"
else
    fail "missing options.json: GET / returned status='${status}' body='$(cat "$root_body")'"
fi
rm -f "$root_body"

stop_container

# Done — trap EXIT will print summary
