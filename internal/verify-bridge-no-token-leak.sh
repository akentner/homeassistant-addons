#!/usr/bin/env bash
# verify-bridge-no-token-leak.sh — Phase 9+10+15 no-token-leak invariant (D-12 + AUTH-05 + OPS-01).
#
# Runs the Bridge container with a fake SUPERVISOR_TOKEN in the env,
# captures stdout for ~10 seconds, and asserts:
#   1. The captured output contains NONE of: SUPERVISOR_TOKEN, Bearer,
#      bridge_token (Phase 9 D-12 boundary check; AUTH-01 + AUTH-05).
#   2. The fake token value itself is absent from stdout (S-1).
#   3. The bridge plaintext is absent from stdout (Phase 15 hardening —
#      the previous CF-02 exactly-once-emission invariant was
#      deliberately downgraded to zero emissions; the plaintext now
#      surfaces only in /data/initial-token).
#   4. The actor_token_fp field in bridge.token.issued equals SHA-256[8]
#      of the plaintext read from /data/initial-token — positive control
#      that the fingerprint helper agrees with a fresh SHA-256 AND that
#      the on-disk file actually contains the same token the hash was
#      derived from.
#   5. The bridge.token.issued record carries a "preview" field whose
#      value is first3+"..."+last3 of the plaintext, and a "path" field
#      pointing at /data/initial-token — proves the new log shape is in
#      place without leaking the token.
#   6. A GET / produced an OPS-01 request-log record carrying the
#      mandatory fields (route, method).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BRIDGE_DIR="${REPO_ROOT}/terraform-bridge"

IMAGE_NAME="terraform-bridge:leak-$(date +%s)"
CONTAINER_NAME="terraform-bridge-leak-test"
FAKE_TOKEN="phase-9-fake-supervisor-token-do-not-use-in-prod"

# A real, host-backed /data so the container has genuine persistent
# storage (matching Supervisor's per-addon /data mount) instead of
# relying on the image or docker-run to provide one. Also carries an
# explicit bind_address + bind_allowed_subnets override: this smoke
# test asserts token-leak/AUTH-05/OPS-01 invariants, NOT the
# bind_address=auto Tailscale auto-detection (that has its own unit
# tests in internal/auth/bind_test.go) — no CI runner has a
# tailscale* interface, so "auto" would always fail bind resolution
# before the bridge ever reaches the token store. 127.0.0.1 +
# 127.0.0.0/8 satisfies ResolveBindAddress's explicit-IP +
# bind_allowed_subnets path without needing Tailscale or
# --network host.
DATA_DIR="$(mktemp -d)"
cat > "${DATA_DIR}/options.json" <<'JSON'
{"bind_address":"127.0.0.1","bind_allowed_subnets":["127.0.0.0/8"]}
JSON

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }

cleanup() {
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    docker rmi  "${IMAGE_NAME}"       >/dev/null 2>&1 || true
    rm -rf "${DATA_DIR}"              >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ ! -d "${BRIDGE_DIR}" ]]; then
    red "Bridge directory not found: ${BRIDGE_DIR}"
    exit 2
fi

BRIDGE_VERSION="$(grep -E '^[[:space:]]*VERSION:' "${BRIDGE_DIR}/build.yaml" | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/')"

docker build -t "${IMAGE_NAME}" \
             --build-arg "BRIDGE_VERSION=${BRIDGE_VERSION}" \
             "${BRIDGE_DIR}" >/dev/null 2>&1

# Run with a fake SUPERVISOR_TOKEN and the /data override above. The
# bridge binds to 127.0.0.1 only (see options.json above), so the GET
# / touch below runs via `docker exec` (inside the container's own
# network namespace) rather than through a host-mapped port — nothing
# listens on an externally-reachable interface by design (bind_address
# 0.0.0.0 is always refused; see PITFALLS S-4).
docker run --rm -d --name "${CONTAINER_NAME}" \
           -e "SUPERVISOR_TOKEN=${FAKE_TOKEN}" \
           -v "${DATA_DIR}:/data" \
           "${IMAGE_NAME}"
sleep 2
docker exec "${CONTAINER_NAME}" curl -sS --max-time 5 "http://127.0.0.1:8124/" >/dev/null 2>&1 || true
sleep 8

# Pull the plaintext token out of the container before it stops
# (docker run --rm removes it on exit). The Bridge writes the plaintext
# to /data/initial-token on first start so operators can configure
# their Provider without the token ever passing through a log stream.
INITIAL_TOKEN=$(docker exec "${CONTAINER_NAME}" cat /data/initial-token 2>/dev/null | tr -d '\n' || true)
if [[ -z "${INITIAL_TOKEN}" ]]; then
    red "   FAIL: could not read /data/initial-token from running container"
    docker logs "${CONTAINER_NAME}" 2>&1 | tail -20 || true
    exit 1
fi

CAPTURED=$(docker logs "${CONTAINER_NAME}" 2>&1)
echo "   captured ${#CAPTURED} bytes of container output"

FAIL=0
for PATTERN in 'SUPERVISOR_TOKEN' 'Bearer' 'bridge_token'; do
    if echo "${CAPTURED}" | grep -F -q -- "${PATTERN}"; then
        red "   FAIL: pattern '${PATTERN}' found in container stdout"
        echo "${CAPTURED}" | grep -F -- "${PATTERN}" | head -3
        FAIL=1
    else
        echo "   PASS: no '${PATTERN}' in stdout"
    fi
done

# Also verify the fake token itself (not just the variable name) doesn't
# appear.  PITFALLS S-1 calls this out specifically.
if echo "${CAPTURED}" | grep -F -q -- "${FAKE_TOKEN}"; then
    red "   FAIL: fake token value found in container stdout"
    echo "${CAPTURED}" | grep -F -- "${FAKE_TOKEN}" | head -3
    FAIL=1
else
    echo "   PASS: fake token value not present in stdout"
fi

# Phase 15 strengthening (AUTH-05 hardening): the plaintext token must
# NEVER appear in stdout. The previous CF-02 exactly-once invariant was
# deliberately downgraded — the plaintext now surfaces only via the
# chmod-600 /data/initial-token file, which is the operator's manual
# retrieval path. Second emissions would leak the token to any
# downstream log shipper (HA Cloud, Loki, journald, …).
if echo "${CAPTURED}" | grep -F -q -- "${INITIAL_TOKEN}"; then
    red "   FAIL: bridge plaintext found in container stdout (was previously CF-02 once, now must be 0)"
    echo "${CAPTURED}" | grep -F -- "${INITIAL_TOKEN}" | head -3
    FAIL=1
else
    echo "   PASS: bridge plaintext absent from stdout (Phase 15 hardening)"
fi

# Phase 15 positive controls on the new log shape (preview + path fields):
ISSUED_RECORD=$(echo "${CAPTURED}" | grep -F '"msg":"bridge.token.issued"' || true)
if [[ -z "${ISSUED_RECORD}" ]]; then
    red "   FAIL: no bridge.token.issued record in stdout"
    FAIL=1
else
    ACTOR_FP=$(echo "${ISSUED_RECORD}" | grep -oE '"actor_token_fp":"[^"]*"' | head -1 | sed 's/^"actor_token_fp":"//; s/"$//')
    PREVIEW=$(echo "${ISSUED_RECORD}" | grep -oE '"preview":"[^"]*"' | head -1 | sed 's/^"preview":"//; s/"$//')
    PATH_FIELD=$(echo "${ISSUED_RECORD}" | grep -oE '"path":"[^"]*"' | head -1 | sed 's/^"path":"//; s/"$//')
    if [[ -z "${ACTOR_FP}" ]]; then
        red "   FAIL: bridge.token.issued record missing actor_token_fp field"
        FAIL=1
    else
        EXPECTED_FP=$(printf '%s' "${INITIAL_TOKEN}" | sha256sum | cut -c1-16)
        if [[ "${EXPECTED_FP}" = "${ACTOR_FP}" ]]; then
            echo "   PASS: actor_token_fp matches SHA-256[8] of /data/initial-token (positive control)"
        else
            red "   FAIL: actor_token_fp (${ACTOR_FP}) != SHA-256[8](initial-token) (${EXPECTED_FP})"
            FAIL=1
        fi
    fi
    if [[ -z "${PREVIEW}" ]]; then
        red "   FAIL: bridge.token.issued record missing preview field"
        FAIL=1
    else
        TOKEN_LEN=${#INITIAL_TOKEN}
        if (( TOKEN_LEN > 6 )); then
            EXPECTED_PREVIEW="${INITIAL_TOKEN:0:3}...${INITIAL_TOKEN: -3}"
        else
            EXPECTED_PREVIEW="${INITIAL_TOKEN}"
        fi
        if [[ "${PREVIEW}" = "${EXPECTED_PREVIEW}" ]]; then
            echo "   PASS: preview field is first3+'...'+last3 of initial-token"
        else
            red "   FAIL: preview (${PREVIEW}) != first3+'...'+last3 of initial-token (${EXPECTED_PREVIEW})"
            FAIL=1
        fi
    fi
    if [[ "${PATH_FIELD}" != "/data/initial-token" ]]; then
        red "   FAIL: path field = ${PATH_FIELD}, want /data/initial-token"
        FAIL=1
    else
        echo "   PASS: path field points at /data/initial-token"
    fi
fi

# OPS-01 record check: confirm RequestLogger emitted a JSON line for GET /
# carrying the route= and method= fields. The Authorization header value
# is asserted-absent upstream by the SUPERVISOR_TOKEN/Bearer pattern checks.
if echo "${CAPTURED}" | grep -q '"msg":"http.request"' \
   && echo "${CAPTURED}" | grep -q '"route":"/"' \
   && echo "${CAPTURED}" | grep -q '"method":"GET"'; then
    echo "   PASS: GET / produced an OPS-01 request-log record"
else
    red "   FAIL: no OPS-01 request-log record found for GET /"
    FAIL=1
fi

if (( FAIL == 1 )); then
    red "verify-bridge-no-token-leak: FAIL"
    exit 1
fi

green "verify-bridge-no-token-leak: PASS"
