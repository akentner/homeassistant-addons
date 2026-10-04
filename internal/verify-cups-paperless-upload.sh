#!/usr/bin/env bash
# verify-cups-paperless-upload.sh -- Phase 22 tracer + retry-exhaustion verify
# script for the cups/ add-on's paperless_upload feature. Proves, end-to-end
# against a real built image and a real (stubbed) HTTP server:
#   1. the happy path: print -> cups-pdf queue -> PDF + title sidecar ->
#      upload-worker.py -> stub paperless-ngx server -> sent/ (D-01/D-02/D-10)
#   2. the D-07 disabled-by-default regression: no queue, no outbox, no
#      worker network activity when paperless_upload.enabled is false
#   3. the failure path: retry/backoff exhaustion -> failed/ + exactly one
#      WARNING log line, document + sidecar never deleted (D-09/D-15)
#   4. malformed-state and sent/failed collision resilience (CR-01/WR-02/
#      WR-05): a poisoned .retry.json never starves alphabetically-later
#      documents, a malformed .json title sidecar never stalls a document,
#      and a sent/failed filename collision is disambiguated, never
#      silently overwritten
#
# Mirrors internal/verify-cups-scaffold.sh (DATA_DIR + options.json fixture,
# docker build, docker run -v mount, trap cleanup, red/green/yellow helpers,
# FAIL accumulator, final PASS/FAIL summary with container logs on failure).
#
# Every container is started through internal/cups-test-isolation.sh (Plan 21-08, D-11): each fixture names a
# unique cups-vf-pl-* avahi_hostname and LAN multicast is switched off on the container's interfaces. The
# stub HTTP servers stay reachable via host.docker.internal (only the multicast flag is turned off). The earlier
# version announced the default `cups.local` on the real LAN and displaced the live add-on's host name.
# Do not run this verifier while a live proof is in progress (Plan 21-10).
#
# Usage: bash internal/verify-cups-paperless-upload.sh [--keep]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADDON_DIR="${REPO_ROOT}/cups"
# shellcheck source=internal/cups-test-isolation.sh
. "${SCRIPT_DIR}/cups-test-isolation.sh"

STAMP="$(date +%s)"
IMAGE_NAME="cups-paperless-verify:${STAMP}"
KEEP=0
[[ "${1:-}" == "--keep" ]] && KEEP=1

SCRATCH_DIR="$(mktemp -d)"
STUB_SERVER_PY="${SCRATCH_DIR}/stub_server.py"

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

FAIL=0
CONTAINERS_STARTED=()
STUB_PIDS=()

cleanup() {
    for pid in "${STUB_PIDS[@]:-}"; do
        if [[ -n "${pid}" ]]; then
            kill "${pid}" >/dev/null 2>&1 || true
        fi
    done
    if [[ "${KEEP}" == "0" ]]; then
        for c in "${CONTAINERS_STARTED[@]:-}"; do
            if [[ -n "${c}" ]]; then
                docker rm -f "${c}" >/dev/null 2>&1 || true
            fi
        done
        docker rmi "${IMAGE_NAME}" >/dev/null 2>&1 || true
        rm -rf "${SCRATCH_DIR}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

if [[ ! -d "${ADDON_DIR}" ]]; then
    red "cups/ add-on directory not found: ${ADDON_DIR}"
    exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
    red "docker not found in PATH"
    exit 2
fi

# --- Minimal stub paperless-ngx HTTP server (stdlib only) -------------------
# Records every POST's Authorization header + parsed "title" multipart field
# to a JSONL log, and responds 200 or 500 depending on a mode file the test
# can flip between scenarios without restarting the server.
cat > "${STUB_SERVER_PY}" <<'PYEOF'
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
LOG_PATH = sys.argv[2]
MODE_PATH = sys.argv[3]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        auth = self.headers.get("Authorization", "")
        content_type = self.headers.get("Content-Type", "")
        title = None
        boundary = None
        if "boundary=" in content_type:
            boundary = content_type.split("boundary=", 1)[1].strip().strip('"')
        if boundary:
            parts = body.split(("--" + boundary).encode())
            for part in parts:
                if b'name="title"' in part:
                    segment = part.split(b"\r\n\r\n", 1)
                    if len(segment) == 2:
                        title = segment[1].rstrip(b"\r\n--").decode(errors="replace")
                    break

        record = {"path": self.path, "authorization": auth, "title": title}
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")

        mode = "success"
        try:
            with open(MODE_PATH) as f:
                mode = f.read().strip() or "success"
        except OSError:
            pass

        if mode == "fail":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "stub forced failure"}')
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'"stub-task-uuid-0001"')


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
PYEOF

start_stub_server() {
    # $1=port $2=log_path $3=mode_path -- starts in the background, returns
    # its PID on stdout.
    local port="$1" log_path="$2" mode_path="$3"
    : > "${log_path}"
    echo "success" > "${mode_path}"
    python3 "${STUB_SERVER_PY}" "${port}" "${log_path}" "${mode_path}" \
        > "${SCRATCH_DIR}/stub-${port}.out" 2>&1 &
    echo $!
}

wait_for_container_ready() {
    local container="$1"
    for _ in $(seq 1 40); do
        if docker exec "${container}" lpstat -r >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

wait_for_queue() {
    local container="$1" queue="$2"
    for _ in $(seq 1 30); do
        if docker exec "${container}" lpstat -v "${queue}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# --- Build the image once, shared by every scenario -------------------------
BUILD_FROM=$(grep -E '^\s*amd64:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*amd64: "(.*)"/\1/')
VERSION=$(grep -E '^\s*VERSION:' "${ADDON_DIR}/build.yaml" | sed -E 's/^\s*VERSION: "(.*)"/\1/')

yellow "Building ${IMAGE_NAME} from ${ADDON_DIR}/ (BUILD_FROM=${BUILD_FROM} VERSION=${VERSION})"
if ! docker build -t "${IMAGE_NAME}" \
    --build-arg "BUILD_FROM=${BUILD_FROM}" \
    --build-arg "VERSION=${VERSION}" \
    "${ADDON_DIR}" >"${SCRATCH_DIR}/build.log" 2>&1; then
    red "docker build failed -- see ${SCRATCH_DIR}/build.log"
    tail -60 "${SCRATCH_DIR}/build.log"
    exit 1
fi
green "image built"

# =============================================================================
# Scenario 1: happy path (D-01/D-02/D-05/D-10/D-11)
# =============================================================================
yellow "=== Scenario 1: happy path ==="

HAPPY_PORT=8791
HAPPY_LOG="${SCRATCH_DIR}/happy-requests.jsonl"
HAPPY_MODE="${SCRATCH_DIR}/happy-mode.txt"
HAPPY_STUB_PID=$(start_stub_server "${HAPPY_PORT}" "${HAPPY_LOG}" "${HAPPY_MODE}")
STUB_PIDS+=("${HAPPY_STUB_PID}")
sleep 1

HAPPY_CONTAINER="cups-paperless-verify-happy-${STAMP}"
CONTAINERS_STARTED+=("${HAPPY_CONTAINER}")
HAPPY_DATA_DIR="${SCRATCH_DIR}/happy-data"
mkdir -p "${HAPPY_DATA_DIR}"
cat > "${HAPPY_DATA_DIR}/options.json" <<JSON
{
  "avahi_reflector": false,
  "avahi_hostname": "$(cups_test_hostname pl-happy)",
  "printers": [],
  "log_level": "info",
  "paperless_upload": {
    "enabled": true,
    "queue_name": "verify-pdf-queue",
    "location": "",
    "url": "http://host.docker.internal:${HAPPY_PORT}",
    "token": "verify-fake-token",
    "timeout": 10,
    "retry_count": 2,
    "retry_delay": 2
  }
}
JSON

cups_isolated_run "${IMAGE_NAME}" --rm -d --name "${HAPPY_CONTAINER}" \
    --add-host=host.docker.internal:host-gateway \
    -v "${HAPPY_DATA_DIR}:/data" >/dev/null

if ! wait_for_container_ready "${HAPPY_CONTAINER}"; then
    red "cupsd did not become ready in the happy-path container"
    docker logs "${HAPPY_CONTAINER}" 2>&1 || true
    FAIL=1
else
    if wait_for_queue "${HAPPY_CONTAINER}" "verify-pdf-queue"; then
        green "PASS: verify-pdf-queue registered"
        # Polled: run.sh's UUID-fixup restarts cupsd shortly after the first readiness, so a single lpstat
        # right after wait_for_queue can hit the restart window and print nothing.
        DEVICE_URI=""
        for _ in $(seq 1 15); do
            DEVICE_URI=$(docker exec "${HAPPY_CONTAINER}" lpstat -v verify-pdf-queue 2>/dev/null || true)
            [[ -n "${DEVICE_URI}" ]] && break
            sleep 1
        done
        if echo "${DEVICE_URI}" | grep -qF "cups-pdf:/"; then
            green "PASS: verify-pdf-queue device uri is cups-pdf:/"
        else
            red "FAIL: verify-pdf-queue device uri unexpected: ${DEVICE_URI}"
            FAIL=1
        fi
    else
        red "FAIL: verify-pdf-queue did not register within timeout"
        docker logs "${HAPPY_CONTAINER}" 2>&1 || true
        FAIL=1
    fi

    docker exec "${HAPPY_CONTAINER}" sh -c 'echo "verify happy-path payload" > /tmp/happy.txt'
    docker exec "${HAPPY_CONTAINER}" lp -d verify-pdf-queue -t "Happy Path Title" /tmp/happy.txt >/dev/null

    HAPPY_SENT_SEEN=0
    for _ in $(seq 1 30); do
        if [[ -n "$(ls -A "${HAPPY_DATA_DIR}/paperless_upload/sent" 2>/dev/null)" ]]; then
            HAPPY_SENT_SEEN=1
            break
        fi
        sleep 1
    done

    if [[ "${HAPPY_SENT_SEEN}" == "1" ]]; then
        green "PASS: PDF appeared in sent/ within timeout"
    else
        red "FAIL: no PDF appeared in sent/ within timeout"
        docker logs "${HAPPY_CONTAINER}" 2>&1 || true
        FAIL=1
    fi

    HAPPY_REQUEST_COUNT=$(wc -l < "${HAPPY_LOG}" 2>/dev/null || echo 0)
    if [[ "${HAPPY_REQUEST_COUNT}" -ge 1 ]]; then
        green "PASS: stub server received at least one POST"
        LAST_REQUEST=$(tail -1 "${HAPPY_LOG}")
        if echo "${LAST_REQUEST}" | grep -qF '"authorization": "Token verify-fake-token"'; then
            green "PASS: Authorization: Token verify-fake-token header present"
        else
            red "FAIL: missing/incorrect Authorization header: ${LAST_REQUEST}"
            FAIL=1
        fi
        if echo "${LAST_REQUEST}" | python3 -c "
import json, sys
rec = json.loads(sys.stdin.readline())
title = rec.get('title')
sys.exit(0 if title else 1)
"; then
            green "PASS: title form field is non-empty"
        else
            red "FAIL: title form field missing/empty: ${LAST_REQUEST}"
            FAIL=1
        fi
        if echo "${LAST_REQUEST}" | grep -qF '"path": "/api/documents/post_document/"'; then
            green "PASS: POSTed to /api/documents/post_document/"
        else
            red "FAIL: unexpected path: ${LAST_REQUEST}"
            FAIL=1
        fi
    else
        red "FAIL: stub server received zero requests"
        FAIL=1
    fi

    # T-22-02: the fixture token must never appear verbatim in container logs.
    if docker logs "${HAPPY_CONTAINER}" 2>&1 | grep -qF "verify-fake-token"; then
        red "FAIL: the fixture token appears verbatim in container logs"
        FAIL=1
    else
        green "PASS: paperless_upload.token never appears in container logs"
    fi
fi

docker rm -f "${HAPPY_CONTAINER}" >/dev/null 2>&1 || true
kill "${HAPPY_STUB_PID}" >/dev/null 2>&1 || true

# =============================================================================
# Scenario 2: D-07 disabled-by-default regression
# =============================================================================
yellow "=== Scenario 2: disabled-by-default regression (D-07) ==="

DISABLED_CONTAINER="cups-paperless-verify-disabled-${STAMP}"
CONTAINERS_STARTED+=("${DISABLED_CONTAINER}")
DISABLED_DATA_DIR="${SCRATCH_DIR}/disabled-data"
mkdir -p "${DISABLED_DATA_DIR}"
cat > "${DISABLED_DATA_DIR}/options.json" <<JSON
{
  "avahi_hostname": "$(cups_test_hostname pl-disabled)",
  "avahi_reflector": false,
  "printers": [],
  "log_level": "info"
}
JSON

cups_isolated_run "${IMAGE_NAME}" --rm -d --name "${DISABLED_CONTAINER}" \
    -v "${DISABLED_DATA_DIR}:/data" >/dev/null

if ! wait_for_container_ready "${DISABLED_CONTAINER}"; then
    red "cupsd did not become ready in the disabled-fixture container"
    docker logs "${DISABLED_CONTAINER}" 2>&1 || true
    FAIL=1
else
    sleep 2
    if docker exec "${DISABLED_CONTAINER}" lpstat -v verify-pdf-queue >/dev/null 2>&1; then
        red "FAIL: verify-pdf-queue is registered despite paperless_upload being unset/disabled"
        FAIL=1
    else
        green "PASS: verify-pdf-queue not registered when paperless_upload is disabled"
    fi

    if [[ -d "${DISABLED_DATA_DIR}/paperless_upload" ]]; then
        red "FAIL: /data/paperless_upload was created despite paperless_upload being disabled"
        FAIL=1
    else
        green "PASS: /data/paperless_upload not created when paperless_upload is disabled"
    fi

    if docker exec "${DISABLED_CONTAINER}" grep -qE '^(Out|AnonDirName|PostProcessing|Label) ' /etc/cups/cups-pdf.conf 2>/dev/null; then
        red "FAIL: cups-pdf.conf carries active paperless_upload directives despite the feature being disabled"
        FAIL=1
    else
        green "PASS: cups-pdf.conf has no active paperless_upload directives when disabled"
    fi
fi

docker rm -f "${DISABLED_CONTAINER}" >/dev/null 2>&1 || true

# =============================================================================
# Scenario 3: retry/backoff exhaustion -> failed/ (D-09/D-15)
# =============================================================================
yellow "=== Scenario 3: retry/backoff exhaustion (D-09/D-15) ==="

FAIL_PORT=8793
FAIL_LOG="${SCRATCH_DIR}/fail-requests.jsonl"
FAIL_MODE="${SCRATCH_DIR}/fail-mode.txt"
FAIL_STUB_PID=$(start_stub_server "${FAIL_PORT}" "${FAIL_LOG}" "${FAIL_MODE}")
STUB_PIDS+=("${FAIL_STUB_PID}")
echo "fail" > "${FAIL_MODE}"
sleep 1

RETRY_CONTAINER="cups-paperless-verify-retry-${STAMP}"
CONTAINERS_STARTED+=("${RETRY_CONTAINER}")
RETRY_DATA_DIR="${SCRATCH_DIR}/retry-data"
mkdir -p "${RETRY_DATA_DIR}"
cat > "${RETRY_DATA_DIR}/options.json" <<JSON
{
  "avahi_reflector": false,
  "avahi_hostname": "$(cups_test_hostname pl-retry)",
  "printers": [],
  "log_level": "info",
  "paperless_upload": {
    "enabled": true,
    "queue_name": "verify-pdf-queue",
    "location": "",
    "url": "http://host.docker.internal:${FAIL_PORT}",
    "token": "verify-fake-token-2",
    "timeout": 10,
    "retry_count": 2,
    "retry_delay": 2
  }
}
JSON

cups_isolated_run "${IMAGE_NAME}" --rm -d --name "${RETRY_CONTAINER}" \
    --add-host=host.docker.internal:host-gateway \
    -v "${RETRY_DATA_DIR}:/data" >/dev/null

if ! wait_for_container_ready "${RETRY_CONTAINER}"; then
    red "cupsd did not become ready in the retry-exhaustion container"
    docker logs "${RETRY_CONTAINER}" 2>&1 || true
    FAIL=1
elif ! wait_for_queue "${RETRY_CONTAINER}" "verify-pdf-queue"; then
    red "FAIL: verify-pdf-queue did not register within timeout (retry-exhaustion container)"
    docker logs "${RETRY_CONTAINER}" 2>&1 || true
    FAIL=1
else
    docker exec "${RETRY_CONTAINER}" sh -c 'echo "verify retry-exhaustion payload" > /tmp/retry.txt'
    docker exec "${RETRY_CONTAINER}" lp -d verify-pdf-queue -t "Retry Exhaustion Title" /tmp/retry.txt >/dev/null

    # retry_count=2, retry_delay=2s -- exhaustion should land in failed/ well
    # within 60s (first attempt immediate, one retry ~2s later, plus poll
    # cadence and cupsd/filter overhead).
    RETRY_FAILED_SEEN=0
    for _ in $(seq 1 60); do
        if [[ -n "$(ls -A "${RETRY_DATA_DIR}/paperless_upload/failed" 2>/dev/null)" ]]; then
            RETRY_FAILED_SEEN=1
            break
        fi
        sleep 1
    done

    if [[ "${RETRY_FAILED_SEEN}" == "1" ]]; then
        green "PASS: document landed in failed/ after retry exhaustion"
    else
        red "FAIL: no document appeared in failed/ within timeout"
        docker logs "${RETRY_CONTAINER}" 2>&1 || true
        FAIL=1
    fi

    RETRY_PROCESSING_LEFTOVER=$(ls -A "${RETRY_DATA_DIR}/paperless_upload/processing" 2>/dev/null || true)
    if [[ -z "${RETRY_PROCESSING_LEFTOVER}" ]]; then
        green "PASS: processing/ is empty after retry exhaustion (no leftover retry-state files)"
    else
        red "FAIL: processing/ still has leftover files after retry exhaustion: ${RETRY_PROCESSING_LEFTOVER}"
        FAIL=1
    fi

    FAILED_PDF_COUNT=$(find "${RETRY_DATA_DIR}/paperless_upload/failed" -name '*.pdf' 2>/dev/null | wc -l)
    if [[ "${FAILED_PDF_COUNT}" -ge 1 ]]; then
        green "PASS: failed/ contains the PDF (never deleted)"
    else
        red "FAIL: failed/ does not contain a PDF"
        FAIL=1
    fi

    FAILED_SIDECAR_COUNT=$(find "${RETRY_DATA_DIR}/paperless_upload/failed" -name '*.json' 2>/dev/null | wc -l)
    if [[ "${FAILED_SIDECAR_COUNT}" -ge 1 ]]; then
        green "PASS: failed/ contains the title sidecar alongside the PDF"
    else
        yellow "NOTE: failed/ has no sidecar -- acceptable only if cups-pdf's PostProcessing hook did not run"
    fi

    RETRY_LOGS=$(docker logs "${RETRY_CONTAINER}" 2>&1)
    WARNING_COUNT=$(echo "${RETRY_LOGS}" | grep -c "WARNING: paperless-ngx upload exhausted" || true)
    if [[ "${WARNING_COUNT}" == "1" ]]; then
        green "PASS: exactly one 'WARNING: paperless-ngx upload exhausted' log line (D-15)"
    else
        red "FAIL: expected exactly 1 'WARNING: paperless-ngx upload exhausted' line, found ${WARNING_COUNT}"
        echo "${RETRY_LOGS}" | grep "WARNING: paperless-ngx upload exhausted" || true
        FAIL=1
    fi

    if echo "${RETRY_LOGS}" | grep -qF "verify-fake-token-2"; then
        red "FAIL: the fixture token appears verbatim in container logs (retry-exhaustion container)"
        FAIL=1
    else
        green "PASS: paperless_upload.token never appears in container logs (retry-exhaustion container)"
    fi
fi

docker rm -f "${RETRY_CONTAINER}" >/dev/null 2>&1 || true
kill "${FAIL_STUB_PID}" >/dev/null 2>&1 || true

# =============================================================================
# Scenario 4: malformed-state and sent/failed collision resilience
# (CR-01/WR-02/WR-05)
# =============================================================================
yellow "=== Scenario 4: malformed-state and sent/failed collision resilience (CR-01/WR-02/WR-05) ==="

RESIL_PORT=8794
RESIL_LOG="${SCRATCH_DIR}/resilience-requests.jsonl"
RESIL_MODE="${SCRATCH_DIR}/resilience-mode.txt"
RESIL_STUB_PID=$(start_stub_server "${RESIL_PORT}" "${RESIL_LOG}" "${RESIL_MODE}")
STUB_PIDS+=("${RESIL_STUB_PID}")
sleep 1

RESIL_CONTAINER="cups-paperless-verify-resilience-${STAMP}"
CONTAINERS_STARTED+=("${RESIL_CONTAINER}")
RESIL_DATA_DIR="${SCRATCH_DIR}/resilience-data"
mkdir -p "${RESIL_DATA_DIR}"
cat > "${RESIL_DATA_DIR}/options.json" <<JSON
{
  "avahi_reflector": false,
  "avahi_hostname": "$(cups_test_hostname pl-resil)",
  "printers": [],
  "log_level": "info",
  "paperless_upload": {
    "enabled": true,
    "queue_name": "verify-pdf-queue",
    "location": "",
    "url": "http://host.docker.internal:${RESIL_PORT}",
    "token": "verify-fake-token-4",
    "timeout": 10,
    "retry_count": 2,
    "retry_delay": 2
  }
}
JSON

cups_isolated_run "${IMAGE_NAME}" --rm -d --name "${RESIL_CONTAINER}" \
    --add-host=host.docker.internal:host-gateway \
    -v "${RESIL_DATA_DIR}:/data" >/dev/null

if ! wait_for_container_ready "${RESIL_CONTAINER}"; then
    red "cupsd did not become ready in the resilience container"
    docker logs "${RESIL_CONTAINER}" 2>&1 || true
    FAIL=1
else
    # This scenario injects files directly into the outbox and never calls
    # lp -- the cups-pdf queue itself does not need to exist -- so just wait
    # for generate_config.py's outbox-directory creation to have run.
    OUTBOX_READY=0
    for _ in $(seq 1 15); do
        if [[ -d "${RESIL_DATA_DIR}/paperless_upload/processing" && -d "${RESIL_DATA_DIR}/paperless_upload/sent" ]]; then
            OUTBOX_READY=1
            break
        fi
        sleep 1
    done

    if [[ "${OUTBOX_READY}" != "1" ]]; then
        red "FAIL: outbox directories were not created within timeout"
        docker logs "${RESIL_CONTAINER}" 2>&1 || true
        FAIL=1
    else
        PROCESSING_DIR="${RESIL_DATA_DIR}/paperless_upload/processing"
        SENT_DIR="${RESIL_DATA_DIR}/paperless_upload/sent"

        # CR-01 fixture: a poisoned (syntactically-valid, non-dict)
        # .retry.json alongside a PDF that sorts alphabetically FIRST.
        printf 'poison' > "${PROCESSING_DIR}/poison-aaa.pdf"
        printf '[]' > "${PROCESSING_DIR}/poison-aaa.retry.json"

        # A fresh document with no sidecar/retry-state that sorts
        # alphabetically AFTER poison-aaa -- exactly the document CR-01 said
        # would be permanently starved.
        printf 'normal' > "${PROCESSING_DIR}/zzz-normal.pdf"

        # WR-02 fixture: a malformed (syntactically-valid, non-dict) .json
        # title sidecar.
        printf 'badtitle' > "${PROCESSING_DIR}/badtitle-doc.pdf"
        printf '[]' > "${PROCESSING_DIR}/badtitle-doc.json"

        # WR-05 fixture: a pre-existing retained document in sent/ from a
        # prior container lifetime ...
        printf 'PRE-EXISTING-RETAINED-DOCUMENT' > "${SENT_DIR}/collide.pdf"
        # ... and a fresh document in processing/ whose filename collides
        # with it (simulating cupsd's job-ID counter resetting after a
        # restart, without needing an actual container restart).
        printf 'NEW-DOCUMENT-CONTENT' > "${PROCESSING_DIR}/collide.pdf"

        # CR-01 regression assertion: with the bug, zzz-normal.pdf would stay
        # stuck in processing/ forever because poison-aaa.pdf (sorting
        # before it) aborts every poll cycle. With the fix it converges
        # independently within two full POLL_INTERVAL_SECONDS=20 cycles plus
        # container/filter jitter.
        ZZZ_GONE=0
        for _ in $(seq 1 70); do
            if [[ ! -e "${PROCESSING_DIR}/zzz-normal.pdf" ]]; then
                ZZZ_GONE=1
                break
            fi
            sleep 1
        done

        if [[ "${ZZZ_GONE}" == "1" ]]; then
            green "PASS: zzz-normal.pdf converged out of processing/ despite poison-aaa's malformed retry state (CR-01)"
        else
            red "FAIL: zzz-normal.pdf is still stuck in processing/ -- CR-01 regression"
            docker logs "${RESIL_CONTAINER}" 2>&1 || true
            FAIL=1
        fi

        # WR-02 regression assertion: badtitle-doc.pdf must converge out of
        # processing/ into sent/ despite its malformed title sidecar.
        if [[ ! -e "${PROCESSING_DIR}/badtitle-doc.pdf" ]] \
            && [[ -n "$(find "${SENT_DIR}" -name 'badtitle-doc.pdf' 2>/dev/null)" ]]; then
            green "PASS: badtitle-doc.pdf converged to sent/ despite its malformed title sidecar (WR-02)"
        else
            red "FAIL: badtitle-doc.pdf did not converge to sent/ -- WR-02 regression"
            docker logs "${RESIL_CONTAINER}" 2>&1 || true
            FAIL=1
        fi

        # WR-05 core regression assertion: the pre-existing sent/collide.pdf
        # must be untouched byte-for-byte.
        if [[ "$(cat "${SENT_DIR}/collide.pdf" 2>/dev/null)" == "PRE-EXISTING-RETAINED-DOCUMENT" ]]; then
            green "PASS: pre-existing sent/collide.pdf was not silently overwritten (WR-05)"
        else
            red "FAIL: pre-existing sent/collide.pdf was overwritten -- WR-05 regression"
            docker logs "${RESIL_CONTAINER}" 2>&1 || true
            FAIL=1
        fi

        # The new arrival must have been disambiguated, not silently
        # dropped: exactly one other collide-*.pdf file now exists.
        COLLIDE_DISAMBIGUATED_COUNT=$(find "${SENT_DIR}" -name 'collide-*.pdf' 2>/dev/null | wc -l)
        if [[ "${COLLIDE_DISAMBIGUATED_COUNT}" == "1" ]]; then
            green "PASS: the colliding new document was disambiguated into exactly one collide-*.pdf file"
        else
            red "FAIL: expected exactly 1 disambiguated collide-*.pdf file, found ${COLLIDE_DISAMBIGUATED_COUNT}"
            docker logs "${RESIL_CONTAINER}" 2>&1 || true
            FAIL=1
        fi

        RESIL_LOGS=$(docker logs "${RESIL_CONTAINER}" 2>&1)
        COLLISION_WARNING_COUNT=$(echo "${RESIL_LOGS}" | grep -c "already exists -- moving to" || true)
        if [[ "${COLLISION_WARNING_COUNT}" -ge 1 ]]; then
            green "PASS: at least one 'already exists -- moving to' collision WARNING logged (WR-05)"
        else
            red "FAIL: no 'already exists -- moving to' collision WARNING found in container logs"
            echo "${RESIL_LOGS}"
            FAIL=1
        fi

        if echo "${RESIL_LOGS}" | grep -qF "verify-fake-token-4"; then
            red "FAIL: the fixture token appears verbatim in container logs (resilience container)"
            FAIL=1
        else
            green "PASS: paperless_upload.token never appears in container logs (resilience container)"
        fi
    fi
fi

docker rm -f "${RESIL_CONTAINER}" >/dev/null 2>&1 || true
kill "${RESIL_STUB_PID}" >/dev/null 2>&1 || true

if [[ "${FAIL}" == "1" ]]; then
    echo
    red "internal/verify-cups-paperless-upload.sh: FAILED"
    exit 1
fi

echo
green "internal/verify-cups-paperless-upload.sh: ALL CHECKS PASSED"
