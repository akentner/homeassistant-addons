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
# Optional env (set in GitHub Actions, omitted when unset):
#   CF_ACCESS_CLIENT_ID      - Cloudflare Access service-token Client ID
#   CF_ACCESS_CLIENT_SECRET  - Cloudflare Access service-token Client Secret
#
# When HA_BASE_URL sits behind Cloudflare Access (a GitHub runner always takes
# the public path and gets a 302 to the Access login), set both CF vars and
# the script will authenticate at the edge via a Service Auth policy. When
# either is unset the headers are omitted entirely so LAN / split-horizon
# callers keep working unauthenticated.
#
# Args (or env):
#   $1 EVENT    - "started" or "finished" (defaults to env NOTIFY_EVENT)
#   $2 PAYLOAD  - JSON body string (defaults to env NOTIFY_PAYLOAD)
#
# Behavior:
#   - 3 retries with exponential backoff (1s, 2s, 4s) for transient failures
#   - 3xx (auth-proxy redirect) fails fast — not retried, not transient
#   - 10s connect timeout per attempt
#   - never blocks the workflow: webhook failure logs a warning but
#     always exits 0 so a flaky HA does not break the build.
#
# NOTE: curl is invoked WITHOUT follow-redirects. Following the redirect would
# fetch the Cloudflare Access login page, which returns 200 — the script would
# report success while HA received nothing. Do NOT add follow-redirects to
# this script.
set -u

EVENT="${1:-${NOTIFY_EVENT:-finished}}"
PAYLOAD="${2:-${NOTIFY_PAYLOAD:-{}}}"

if [[ -z "${HA_BASE_URL:-}" || -z "${HA_WEBHOOK_ID:-}" ]]; then
    echo "::notice::HA_BASE_URL or HA_WEBHOOK_ID not set, skipping HA notification"
    exit 0
fi

URL="${HA_BASE_URL%/}/api/webhook/${HA_WEBHOOK_ID}"

# Cloudflare Access service token (optional). Required when HA_BASE_URL points
# at a hostname behind Cloudflare Access — a GitHub runner always resolves the
# public IP and hits the Access edge, which answers an unauthenticated POST
# with a 302 to the login page. Omitted entirely when unset so LAN /
# split-horizon callers keep working unauthenticated.
CF_HEADERS=()
if [[ -n "${CF_ACCESS_CLIENT_ID:-}" && -n "${CF_ACCESS_CLIENT_SECRET:-}" ]]; then
    CF_HEADERS+=(-H "CF-Access-Client-Id: ${CF_ACCESS_CLIENT_ID}")
    CF_HEADERS+=(-H "CF-Access-Client-Secret: ${CF_ACCESS_CLIENT_SECRET}")
    echo "::notice::HA notification auth mode: cloudflare access service-token"
else
    echo "::notice::HA notification auth mode: unauthenticated (CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET not set)"
fi

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
        "${CF_HEADERS[@]+"${CF_HEADERS[@]}"}" \
        -d "$PAYLOAD" 2>/tmp/ha_notify_err.txt || echo "000")

    if [[ "$HTTP_CODE" =~ ^2 ]]; then
        echo "::notice::HA notification OK (${EVENT}, HTTP ${HTTP_CODE})"
        exit 0
    fi

    # An auth-proxy redirect is structurally never transient. Fail fast with an
    # actionable message instead of burning three retries on a permanent
    # misconfiguration (D-04).
    if [[ "$HTTP_CODE" =~ ^3 ]]; then
        echo "::warning::HA notification got HTTP ${HTTP_CODE} — an auth proxy redirected the request instead of passing it to HA."
        echo "::warning::This is not transient; retrying will not help. Check the Cloudflare Access policy for ${URL%/*}/* and that CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET are set."
        echo "::warning::Build continues regardless of HA notification status."
        exit 0
    fi

    # Diagnostics: curl writes the HTTP body to -o (ha_notify_resp.txt) and
    # stderr to ha_notify_err.txt. On a 5xx the body is usually the
    # informative bit; on a connect failure stderr is all we have. Prefer the
    # body, fall back to stderr (D-05).
    ERR_DETAIL=$(head -c 200 /tmp/ha_notify_resp.txt 2>/dev/null)
    [[ -z "$ERR_DETAIL" ]] && ERR_DETAIL=$(head -c 200 /tmp/ha_notify_err.txt 2>/dev/null)
    LAST_ERR="attempt ${ATTEMPT} returned HTTP ${HTTP_CODE}: ${ERR_DETAIL}"
    echo "::warning::HA notification ${LAST_ERR}"

    if (( ATTEMPT < MAX_ATTEMPTS )); then
        sleep $((2 ** (ATTEMPT - 1)))
    fi
done

echo "::warning::HA notification failed after ${MAX_ATTEMPTS} attempts: ${LAST_ERR}"
echo "::warning::Build continues regardless of HA notification status."
exit 0
