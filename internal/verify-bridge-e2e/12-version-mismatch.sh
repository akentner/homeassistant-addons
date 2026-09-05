#!/usr/bin/env bash
# verify-bridge-e2e/12-version-mismatch.sh — Phase 14 SC-4: error_code = "version_below_min".
#
# Constructs a Provider whose `min_provider_version` exceeds what the
# Bridge's `schema_version` advertises. The Provider's Configure
# (terraform-provider-homeassistant/internal/provider/provider.go:160-189)
# surfaces a typed "version_below_min" diagnostic with the URL fragment
# `DOCS.md#troubleshooting-version` (kebab anchor = "version", NOT
# "version-below-min" — the captured file is named version.txt to match
# the anchor).
#
# This scenario is hard to provoke against a real Bridge without
# rebuilding either side with a stale version; we therefore capture
# the Bridge's /v1/version response and the Provider's expected
# diagnostic text, annotating the file `[not empirically observed]`
# when the live run cannot trigger the rejection.
#
# Per D-10: preflight failure → exit 0 with `skipped — <reason>`.

set -euo pipefail

SCRIPT_DIR_12="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR_12}/_lib.sh"

OUT_DIR="${TESTDATA_DIR}/diagnostics"
mkdir -p "${OUT_DIR}"
OUT_FILE="${OUT_DIR}/version.txt"

if ! preflight; then
    cat > "${OUT_FILE}" <<'EOF'
[not empirically observed — synthetic scenario per D-10]
scenario: 12-version-mismatch
skip_reason: preflight failed (tofu / Provider binary / /healthz missing)
expected_severity: Error
expected_error_code: version_below_min
expected_doc_anchor: DOCS.md#troubleshooting-version
expected_summary_text: "Bridge reports this Provider is too old: provider version <p> is below the Bridge's min_provider_version <m>."
remediation: rebuild the Provider with a version that satisfies the Bridge's
             min_provider_version, or downgrade the Bridge to a schema_version
             the current Provider supports.
EOF
    yellow "12-version-mismatch: skipped — preflight failed (see reasons above)"
    exit 0
fi

TOKEN="$(retrieve_bridge_token)" || exit 2

# Step 1: capture the Bridge's /v1/version response as a baseline. The
# Provider's typed "version_below_min" diagnostic is surfaced at
# Configure time when the Provider's own version < the Bridge's
# min_provider_version. Without rebuilding either side, we cannot
# force that condition; this scenario therefore captures the baseline
# and exits 0 with skipped annotation when the rejection doesn't fire.
HTTP_CODE=$(curl -sS -o "${OUT_FILE}" -w '%{http_code}' \
    --max-time 10 \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BRIDGE_URL}/v1/version" 2>/dev/null || echo "000")

if [[ "${HTTP_CODE}" != "200" ]]; then
    red "12-version-mismatch: FAIL — GET /v1/version returned HTTP ${HTTP_CODE}"
    exit 1
fi

# Confirm the response carries the fields the Provider's handshake
# checks (bridge_version, schema_version, min_provider_version,
# max_provider_version).
for FIELD in bridge_version schema_version min_provider_version max_provider_version; do
    if ! grep -q "\"${FIELD}\"" "${OUT_FILE}"; then
        red "12-version-mismatch: FAIL — /v1/version response missing field '${FIELD}'"
        exit 1
    fi
done

# Annotate: empirical rejection of the running Provider's version
# against the Bridge's min_provider_version requires either a
# Provider rebuild or a Bridge downgrade. Operators can verify the
# handshake by running `tofu apply` against a Provider binary built
# with a stale version; the captured baseline is the
# empirically-observed /v1/version response.
cat >> "${OUT_FILE}" <<'EOF'

[baseline observed — empirical version_below_min requires Provider rebuild or Bridge downgrade]
note: the running Provider was built with a version that satisfies the Bridge's
      min_provider_version; the rejection path is not triggered in this run.
      Operators can force it by rebuilding the Provider with a stale version
      (e.g. `git checkout 0.1.0 && make install-provider`).
EOF

yellow "12-version-mismatch: baseline observed — empirical version_below_min requires Provider rebuild"
exit 0
