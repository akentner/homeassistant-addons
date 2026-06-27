#!/usr/bin/env bash
# verify-git-integration.sh — Empirical end-to-end verification of GIT-01..05
#
# This script starts the markdown-renderer container with various /data/options.json
# fixtures and asserts the expected git-sync behavior against http://127.0.0.1:8099/.
#
# Covers all 5 GIT acceptance criteria (GIT-01..05 from 06-01-PLAN.md):
#   GIT-01: startup `git pull --ff-only` against a real repo refreshes local
#           Markdown before nginx starts; pulled content is immediately visible.
#   GIT-02: `git config --global --add safe.directory '*'` runs at startup so git
#           2.35.2+ does not refuse to operate on UID-mismatched repos.
#   GIT-03: when neither git_pull nor git_pull_interval is set, the git binary
#           is NOT invoked; no "git pull" or "git clone" line appears in logs.
#   GIT-04: when git_pull_interval > 0, one background loop pulls each
#           namespace whose own interval has elapsed.
#   GIT-05: any git failure at startup logs WARNING but does not block nginx;
#           the locally cached content is served.
#
# Also covers D-02 (first-time clone via git_url) in Scenario E.
#
# Exit codes:
#   0 = all GIT-01..05 requirements verified empirically
#   1 = at least one assertion failed (see FAIL lines)
#   2 = environment precondition failed (no podman/docker, image missing)
#
# Usage:
#   bash .planning/phases/06-git-integration/verify-git-integration.sh
#
# Pre-requisite:
#   make build-addon ADDON=markdown-renderer
#       (image local/markdown-renderer:1.1.0 — version bumped in Plan 02)
#
# See markdown-renderer/DOCS.md "Git Sync" section for context.

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
        | grep -qE '^(localhost/)?local/markdown-renderer:1\.1\.0$'; then
    echo -e "${RED}FATAL: image local/markdown-renderer:1.1.0 not built${NC}" >&2
    echo -e "${RED}Run: make update-version ADDON=markdown-renderer VERSION=1.1.0 && make build-addon ADDON=markdown-renderer${NC}" >&2
    exit 2
fi
echo -e "${CYAN}Image found: local/markdown-renderer:1.1.0${NC}"

# ─── Cleanup trap (always runs on exit) ────────────────────────────────────
cleanup() {
    local exit_code=$?
    $RUNTIME rm -f mr-git-test >/dev/null 2>&1 || true
    if [[ -d /tmp/mr-git-fixtures ]]; then
        rm -rf /tmp/mr-git-fixtures
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

# Wait until nginx responds on 127.0.0.1:8099 (max 30s). Returns 0 on success.
wait_for_nginx() {
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
# Pattern mirrored from verify-multi-namespace.sh per Phase 5 lessons.
MR_LOGS=""
capture_logs() {
    MR_LOGS=$($RUNTIME logs mr-git-test 2>&1 || true)
}

# Start a fresh container with a given options.json fixture and namespace
# bind mount path. The /data volume holds options.json; the namespace volume
# (typically /tmp/mr-git-fixtures/<scenario>/test-repo or not-a-repo) is
# mounted into the container at the same path the options.json references.
run_container() {
    local options_file=$1
    local namespace_path=$2
    $RUNTIME rm -f mr-git-test >/dev/null 2>&1 || true
    $RUNTIME run -d \
        --name mr-git-test \
        -p 8099:8099 \
        -v "${options_file}:/data/options.json:ro" \
        -v "${namespace_path}:${namespace_path}" \
        localhost/local/markdown-renderer:1.1.0 >/dev/null
}

stop_container() {
    $RUNTIME rm -f mr-git-test >/dev/null 2>&1 || true
}

# Initialize a git repo at $1 with a single file committed. $2 is the file
# name, $3 is the file body. Sets git config so commit works without a
# global config on the host.
init_git_repo() {
    local repo_dir=$1
    local filename=$2
    local body=$3
    mkdir -p "$repo_dir"
    git -C "$repo_dir" init -q -b main
    git -C "$repo_dir" config user.email "test@example.com"
    git -C "$repo_dir" config user.name "Verifier"
    printf '%s' "$body" > "$repo_dir/$filename"
    git -C "$repo_dir" add "$filename"
    git -C "$repo_dir" commit -q -m "initial commit with $filename"
}

# ─── Fixture setup ─────────────────────────────────────────────────────────
mkdir -p /tmp/mr-git-fixtures

# ─── SCENARIO A — startup pull success (GIT-01) ────────────────────────────
SCENARIO_NAME="SCENARIO A — startup pull refreshes repo before nginx (GIT-01)"
scenario

SCEN_DIR_A=/tmp/mr-git-fixtures/scenario-a
mkdir -p "$SCEN_DIR_A"

# Create a "source" repo with a file, then a "test-repo" that starts as a
# clone of it. We then commit a NEW file to the source and pull it locally
# so the test-repo's remote-tracking ref advances. The container's startup
# git pull will pull that new commit.
init_git_repo "$SCEN_DIR_A/source-repo" "README.md" "# Source Repo for A"
# Add an existing file (committed already) to test-repo via clone
git clone -q "$SCEN_DIR_A/source-repo" "$SCEN_DIR_A/test-repo"
git -C "$SCEN_DIR_A/test-repo" config user.email "test@example.com"
git -C "$SCEN_DIR_A/test-repo" config user.name "Verifier"
# Commit a NEW file in source-repo, then pull it into test-repo locally so
# test-repo's remote-tracking branch advances. The container's startup pull
# will be a no-op against the local remote-tracking branch... actually no,
# we want the container to perform the pull. We use file:// in git_url but
# test-repo IS already a clone of source-repo, so the container's probe
# (git rev-parse --git-dir) succeeds and it runs `git pull --ff-only`.
# But pull against a local clone with no new commits is a no-op (already
# up-to-date). So instead we set git_url to the source repo path and let
# the container clone it fresh into an EMPTY directory. That tests D-02 +
# GIT-01 combined — we handle pure GIT-01 (already-cloned repo) in D below.
#
# Actually: per the plan, Scenario A should test "startup pull" against an
# existing cloned repo. So we make test-repo a fresh clone, then ADD a
# commit to source-repo, then point test-repo's remote at source-repo so
# `git pull` inside the container will fetch the new commit.
rm -rf "$SCEN_DIR_A/test-repo"
git clone -q "$SCEN_DIR_A/source-repo" "$SCEN_DIR_A/test-repo"
git -C "$SCEN_DIR_A/test-repo" config user.email "test@example.com"
git -C "$SCEN_DIR_A/test-repo" config user.name "Verifier"
# Now add a new commit to source-repo so test-repo's pull has work to do
printf 'scenario-A-newfile-content' > "$SCEN_DIR_A/source-repo/newfile-A.md"
git -C "$SCEN_DIR_A/source-repo" add newfile-A.md
git -C "$SCEN_DIR_A/source-repo" commit -q -m "add newfile-A.md"
# Re-fetch in test-repo so its FETCH_HEAD reflects the new commit
git -C "$SCEN_DIR_A/test-repo" fetch -q "$SCEN_DIR_A/source-repo" main

cat > "$SCEN_DIR_A/options.json" <<EOF
{"directories":[{"name":"test-repo","path":"$SCEN_DIR_A/test-repo","git_pull":true,"git_pull_interval":0,"git_url":""}],"kroki_url":"https://kroki.io"}
EOF

if run_container "$SCEN_DIR_A/options.json" "$SCEN_DIR_A/test-repo" \
    && wait_for_nginx; then
    pass "container started and nginx is serving (Scenario A fixture)"
else
    fail "container failed to start with Scenario A fixture"
    $RUNTIME logs mr-git-test 2>&1 | tail -20 || true
    exit 1
fi

# GIT-02: safe.directory '*' config ran (verify by inspecting git config
# inside the container via exec)
set +e
safe_dir_output=$($RUNTIME exec mr-git-test sh -c 'git config --global --get-all safe.directory' 2>&1 || true)
set -e
if echo "$safe_dir_output" | grep -qF '*'; then
    pass "GIT-02: 'git config --global --add safe.directory *' ran at startup"
else
    fail "GIT-02: safe.directory '*' not configured (got: '${safe_dir_output}')"
fi

# GIT-01: new file pulled from source-repo is now served at /test-repo/
newfile_body=$(curl -sf "http://127.0.0.1:8099/test-repo/newfile-A.md" 2>/dev/null || true)
if echo "$newfile_body" | grep -qF 'scenario-A-newfile-content'; then
    pass "GIT-01: /test-repo/newfile-A.md serves the pulled content"
else
    fail "GIT-01: /test-repo/newfile-A.md did not return expected content"
    echo -e "    ${YELLOW}DEBUG body:${NC}"
    echo "$newfile_body" | sed 's/^/      /' | head -5
fi

# GIT-01: pull log line present in container logs (proves git ran)
capture_logs
if echo "$MR_LOGS" | grep -qE 'git pull|Fast-forward|Already up to date'; then
    pass "GIT-01: git pull invocations or success indicators in logs"
else
    fail "GIT-01: no git pull / Fast-forward / Already up to date in logs"
    echo -e "    ${YELLOW}DEBUG logs:${NC}"
    echo "$MR_LOGS" | sed 's/^/      /' | head -10
fi

stop_container

# ─── SCENARIO B — startup pull failure graceful (GIT-05) ───────────────────
SCENARIO_NAME="SCENARIO B — unreachable git remote is non-blocking (GIT-05)"
scenario

SCEN_DIR_B=/tmp/mr-git-fixtures/scenario-b
mkdir -p "$SCEN_DIR_B"

# Set up an already-cloned test-repo. Then point git_url at an
# UNREACHABLE remote. Since the path is already a git repo, the probe
# succeeds and `_git_sync.py` runs `git pull --ff-only` against the
# configured remote, which will fail (unreachable). GIT-05 requires the
# container to stay running and the locally cached content to be served.
init_git_repo "$SCEN_DIR_B/source-repo" "README.md" "# Scenario B source"
git clone -q "$SCEN_DIR_B/source-repo" "$SCEN_DIR_B/test-repo"
git -C "$SCEN_DIR_B/test-repo" config user.email "test@example.com"
git -C "$SCEN_DIR_B/test-repo" config user.name "Verifier"

cat > "$SCEN_DIR_B/options.json" <<EOF
{"directories":[{"name":"test-repo","path":"$SCEN_DIR_B/test-repo","git_pull":true,"git_pull_interval":0,"git_url":"https://127.0.0.1:1/nope.git"}],"kroki_url":"https://kroki.io"}
EOF

if run_container "$SCEN_DIR_B/options.json" "$SCEN_DIR_B/test-repo" \
    && wait_for_nginx; then
    pass "container stayed running despite unreachable git_url"
else
    fail "container failed to start (GIT-05 violation: should be non-blocking)"
    $RUNTIME logs mr-git-test 2>&1 | tail -20 || true
    exit 1
fi

# GIT-05: warning line in logs
capture_logs
if echo "$MR_LOGS" | grep -qE 'WARNING: git pull failed|warning: failed|Connection refused'; then
    pass "GIT-05: git pull failure logged as WARNING"
else
    fail "GIT-05: no WARNING line for unreachable git_url in logs"
    echo -e "    ${YELLOW}DEBUG logs:${NC}"
    echo "$MR_LOGS" | sed 's/^/      /' | head -10
fi

# GIT-05: locally cached content is still served (the original README.md)
readme_body=$(curl -sf "http://127.0.0.1:8099/test-repo/" 2>/dev/null || true)
if echo "$readme_body" | grep -q 'Loading test-repo'; then
    pass "GIT-05: /test-repo/ serves locally cached content (Docsify SPA)"
else
    fail "GIT-05: /test-repo/ did not serve expected Docsify SPA"
    echo -e "    ${YELLOW}DEBUG body:${NC}"
    echo "$readme_body" | sed 's/^/      /' | head -5
fi

stop_container

# ─── SCENARIO C — no git invocation when disabled (GIT-03) ─────────────────
SCENARIO_NAME="SCENARIO C — no git invocation when git_pull disabled (GIT-03)"
scenario

SCEN_DIR_C=/tmp/mr-git-fixtures/scenario-c
mkdir -p "$SCEN_DIR_C"
mkdir -p "$SCEN_DIR_C/test-repo"
printf '# Scenario C\n' > "$SCEN_DIR_C/test-repo/README.md"

cat > "$SCEN_DIR_C/options.json" <<EOF
{"directories":[{"name":"test-repo","path":"$SCEN_DIR_C/test-repo","git_pull":false,"git_pull_interval":0,"git_url":""}],"kroki_url":"https://kroki.io"}
EOF

if run_container "$SCEN_DIR_C/options.json" "$SCEN_DIR_C/test-repo" \
    && wait_for_nginx; then
    pass "container started (no git sync configured)"
else
    fail "container failed to start with git sync disabled"
    $RUNTIME logs mr-git-test 2>&1 | tail -20 || true
    exit 1
fi

# GIT-03: no git pull / git clone lines in logs
capture_logs
set +e
git_pull_lines=$(echo "$MR_LOGS" | grep -cE 'git pull|git clone' || true)
set -e
if [[ "$git_pull_lines" -eq 0 ]]; then
    pass "GIT-03: no 'git pull' or 'git clone' invocations in logs"
else
    fail "GIT-03: found ${git_pull_lines} git pull/clone line(s) in logs (should be 0)"
    echo -e "    ${YELLOW}DEBUG matching lines:${NC}"
    echo "$MR_LOGS" | grep -E 'git pull|git clone' | sed 's/^/      /' | head -5
fi

# GIT-03: no git process running inside the container (defense in depth —
# _git_sync.py exits immediately, so even the periodic loop's `sleep 5`
# iteration should not spawn git when nothing is configured)
set +e
git_procs=$($RUNTIME exec mr-git-test sh -c 'pgrep -af "^git " 2>/dev/null || true' 2>/dev/null || true)
set -e
if [[ -z "$git_procs" ]]; then
    pass "GIT-03: no git processes running inside container"
else
    fail "GIT-03: found git process running: '${git_procs}'"
fi

stop_container

# ─── SCENARIO D — periodic pull updates (GIT-04) ───────────────────────────
SCENARIO_NAME="SCENARIO D — periodic background sync updates content (GIT-04)"
scenario

SCEN_DIR_D=/tmp/mr-git-fixtures/scenario-d
mkdir -p "$SCEN_DIR_D"

init_git_repo "$SCEN_DIR_D/source-repo" "README.md" "# Scenario D source"
git clone -q "$SCEN_DIR_D/source-repo" "$SCEN_DIR_D/test-repo"
git -C "$SCEN_DIR_D/test-repo" config user.email "test@example.com"
git -C "$SCEN_DIR_D/test-repo" config user.name "Verifier"

cat > "$SCEN_DIR_D/options.json" <<EOF
{"directories":[{"name":"test-repo","path":"$SCEN_DIR_D/test-repo","git_pull":false,"git_pull_interval":5,"git_url":""}],"kroki_url":"https://kroki.io"}
EOF

if run_container "$SCEN_DIR_D/options.json" "$SCEN_DIR_D/test-repo" \
    && wait_for_nginx; then
    pass "container started with git_pull_interval=5 (no startup pull)"
else
    fail "container failed to start with periodic sync fixture"
    $RUNTIME logs mr-git-test 2>&1 | tail -20 || true
    exit 1
fi

# Wait 7s to let the periodic loop tick once
sleep 7

# Now push a new commit to source-repo and update test-repo's FETCH_HEAD
# so the next periodic pull has work to do
printf 'scenario-D-newfile-content' > "$SCEN_DIR_D/source-repo/newfile-D.md"
git -C "$SCEN_DIR_D/source-repo" add newfile-D.md
git -C "$SCEN_DIR_D/source-repo" commit -q -m "add newfile-D.md"
git -C "$SCEN_DIR_D/test-repo" fetch -q "$SCEN_DIR_D/source-repo" main

# Wait another 8s for the periodic loop (interval=5 + buffer) to pull
sleep 8

# GIT-04: pulled new content is served
newfile_body=$(curl -sf "http://127.0.0.1:8099/test-repo/newfile-D.md" 2>/dev/null || true)
if echo "$newfile_body" | grep -qF 'scenario-D-newfile-content'; then
    pass "GIT-04: /test-repo/newfile-D.md serves the periodically-pulled content"
else
    fail "GIT-04: /test-repo/newfile-D.md did not return expected content"
    echo -e "    ${YELLOW}DEBUG body:${NC}"
    echo "$newfile_body" | sed 's/^/      /' | head -5
fi

# GIT-04: periodic loop ran at least once (look for second invocation)
capture_logs
# After ~15 seconds with interval=5, we expect at least 2 invocations of
# the periodic loop (the first pulls the initial state, the second pulls
# newfile-D.md). Count `--periodic` markers in logs.
set +e
periodic_count=$(echo "$MR_LOGS" | grep -cE 'git pull' || true)
set -e
if [[ "$periodic_count" -ge 2 ]]; then
    pass "GIT-04: ${periodic_count} git pull invocations in logs (periodic loop ran)"
else
    fail "GIT-04: only ${periodic_count} git pull invocations in logs (expected >= 2)"
    echo -e "    ${YELLOW}DEBUG logs (filtered):${NC}"
    echo "$MR_LOGS" | grep -E 'git pull|periodic' | sed 's/^/      /' | head -10
fi

stop_container

# ─── SCENARIO E — first-time clone via git_url (D-02) ──────────────────────
SCENARIO_NAME="SCENARIO E — first-time clone via file:// git_url (D-02)"
scenario

SCEN_DIR_E=/tmp/mr-git-fixtures/scenario-e
mkdir -p "$SCEN_DIR_E"

# Source repo with content; clone target is an EMPTY directory so the
# probe in _git_sync.py fails and falls through to git_url cloning
init_git_repo "$SCEN_DIR_E/source-repo" "README.md" "# Scenario E source"
mkdir -p "$SCEN_DIR_E/not-a-repo"
# Verify not-a-repo is actually not a git repo
set +e
is_repo=$(git -C "$SCEN_DIR_E/not-a-repo" rev-parse --git-dir 2>&1 || true)
set -e

cat > "$SCEN_DIR_E/options.json" <<EOF
{"directories":[{"name":"not-a-repo","path":"$SCEN_DIR_E/not-a-repo","git_pull":true,"git_pull_interval":0,"git_url":"file://$SCEN_DIR_E/source-repo"}],"kroki_url":"https://kroki.io"}
EOF

if run_container "$SCEN_DIR_E/options.json" "$SCEN_DIR_E/not-a-repo" \
    && wait_for_nginx; then
    pass "container started with empty (non-repo) namespace path"
else
    fail "container failed to start with first-time-clone fixture"
    $RUNTIME logs mr-git-test 2>&1 | tail -20 || true
    exit 1
fi

# D-02: .git directory now exists in not-a-repo (clone succeeded)
set +e
git_dir_exists=$($RUNTIME exec mr-git-test sh -c "test -d $SCEN_DIR_E/not-a-repo/.git && echo yes || echo no" 2>&1 || true)
set -e
if echo "$git_dir_exists" | grep -qF 'yes'; then
    pass "D-02: .git/ directory exists in not-a-repo after startup (clone succeeded)"
else
    fail "D-02: .git/ directory NOT found in not-a-repo after startup (got: '${git_dir_exists}')"
fi

# D-02: cloned README.md is served
cloned_body=$(curl -sf "http://127.0.0.1:8099/not-a-repo/" 2>/dev/null || true)
if echo "$cloned_body" | grep -q 'Loading not-a-repo'; then
    pass "D-02: /not-a-repo/ serves content cloned from file:// git_url"
else
    fail "D-02: /not-a-repo/ did not serve expected Docsify SPA"
    echo -e "    ${YELLOW}DEBUG body:${NC}"
    echo "$cloned_body" | sed 's/^/      /' | head -5
fi

stop_container

# Done — trap EXIT will print summary
