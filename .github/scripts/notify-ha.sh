#!/usr/bin/env bash
# Notify Home Assistant via inbound webhook.
#
# Posts a JSON payload to <HA_BASE_URL>/api/webhook/<HA_WEBHOOK_ID> which
# triggers the matching `webhook` automation in HA (event name:
# `webhook_<HA_WEBHOOK_ID>`).
#
# The webhook is unprotected (no HMAC) — set HA_WEBHOOK_ID to a long,
# unguessable value if you don't want random visitors triggering it.
# Anyone with the URL can fire events. Acceptable for a private HA
# behind a reverse proxy; not acceptable for public exposure.
#
# Required env (set in GitHub Actions):
#   HA_BASE_URL       - e.g. https://ha-nextgen.akentner.de (no trailing slash)
#   HA_WEBHOOK_ID     - the webhook_id configured in HA (use a long random string)
#
# Args (or env):
#   $1 EVENT    - "started" or "finished" (defaults to env NOTIFY_EVENT)
#   $2 PAYLOAD  - JSON body string (defaults to env NOTIFY_PAYLOAD)
#
# Behavior:
#   - 3 retries with exponential backoff (1s, 2s, 4s)
#   - 10s connect timeout per attempt
#   - never blocks the workflow: webhook failure logs a warning but
#     always exits 0 so a flaky HA does not break the build.
set -u

EVENT="${1:-${NOTIFY_EVENT:-finished}}"
PAYLOAD="${2:-${NOTIFY_PAYLOAD:-{}}}"

if [[ -z "${HA_BASE_URL:-}" || -z "${HA_WEBHOOK_ID:-}" ]]; then
    echo "::notice::HA_BASE_URL or HA_WEBHOOK_ID not set, skipping HA notification"
    exit 0
fi

URL="${HA_BASE_URL%/}/api/webhook/${HA_WEBHOOK_ID}"

ATTEMPT=0
MAX_ATTEMPTS=3
LAST_ERR=""

while (( ATTEMPT < MAX_ATTEMPTS )); do
    ATTEMPT=$((ATTEMPT + 1))

    HTTP_CODE=$(curl -sS -o /tmp/ha_notify_resp.txt -w "%{http_code}" \
        --connect-timeout 10 --max-time 30 \
        -X POST "$URL" \
        -H "Content-Type: application/json" \
        -H "X-GitHub-Event: build" \
        -H "X-GitHub-Delivery: ${NOTIFY_DELIVERY_ID:-local}-$$-${ATTEMPT}" \
        -d "$PAYLOAD" 2>/tmp/ha_notify_err.txt || echo "000")

    if [[ "$HTTP_CODE" =~ ^2 ]]; then
        echo "::notice::HA notification OK (${EVENT}, HTTP ${HTTP_CODE})"
        exit 0
    fi

    LAST_ERR="attempt ${ATTEMPT} returned HTTP ${HTTP_CODE}: $(head -c 200 /tmp/ha_notify_err.txt 2>/dev/null)"
    echo "::warning::HA notification ${LAST_ERR}"

    if (( ATTEMPT < MAX_ATTEMPTS )); then
        sleep $((2 ** (ATTEMPT - 1)))
    fi
done

echo "::warning::HA notification failed after ${MAX_ATTEMPTS} attempts: ${LAST_ERR}"
echo "::warning::Build continues regardless of HA notification status."
exit 0
