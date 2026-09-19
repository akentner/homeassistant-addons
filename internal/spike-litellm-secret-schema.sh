#!/usr/bin/env bash
# Empirical spike: validate `password?` schema + `!secret` default interaction on HA Supervisor.
# D-35 — Audit H4 risk mitigation. Pre-Plan-02 this spike confirmed the schema parser accepts
# the combination. Retrospectively, Plan 02's run.sh commits to this approach; the spike remains
# valuable as a regression test for future HA-OS upgrades.
#
# Manual invocation: bash internal/spike-litellm-secret-schema.sh
# Output: /tmp/spike-litellm-secret-schema.out (operator reviews manually)
set -euo pipefail

SPIKE_DIR="/tmp/spike-litellm-secret-schema"
SPIKE_OUT="/tmp/spike-litellm-secret-schema.out"

rm -rf "${SPIKE_DIR}"
mkdir -p "${SPIKE_DIR}"

cat > "${SPIKE_DIR}/config.yaml" <<'EOF'
name: "Spike Add-on (litellm-secret-schema)"
description: "Empirical spike for password? + !secret combination (D-35)"
version: "0.0.1-0"
slug: "spike_litellm_secret_schema"
init: false
arch:
  - amd64
startup: "application"
boot: "manual"

options:
  master_key: !secret spike_test_secret

schema:
  master_key: "password?"
EOF

cat > "${SPIKE_DIR}/build.yaml" <<'EOF'
build_from:
  amd64: "ghcr.io/home-assistant/amd64-base-debian:trixie"

args:
  VERSION: "0.0.1"
EOF

cat > "${SPIKE_DIR}/Dockerfile" <<'EOF'
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
FROM ${BUILD_FROM}
CMD ["/bin/sh", "-c", "echo spike-running && sleep 3600"]
EOF

cat > "${SPIKE_DIR}/run.sh" <<'EOF'
#!/usr/bin/with-contenv bashio
set -e
bashio::log.info "Spike running"
exec sleep 3600
EOF
chmod +x "${SPIKE_DIR}/run.sh"

cat > "${SPIKE_DIR}/README.md" <<'EOF'
# Spike Add-on

Empirical spike for `password?` + `!secret` combination (D-35).
EOF

cat > "${SPIKE_DIR}/DOCS.md" <<'EOF'
# Spike DOCS

No operator-facing documentation.
EOF

echo "==> Spike add-on created at ${SPIKE_DIR}" | tee "${SPIKE_OUT}"
echo "" | tee -a "${SPIKE_OUT}"
echo "==> Files:" | tee -a "${SPIKE_OUT}"
# shellcheck disable=SC2012
ls -la "${SPIKE_DIR}" | tee -a "${SPIKE_OUT}"
echo "" | tee -a "${SPIKE_OUT}"
echo "==> Validation:" | tee -a "${SPIKE_OUT}"

if python3 internal/validate-addon-config.py "${SPIKE_DIR}" 2>&1 | tee -a "${SPIKE_OUT}"; then
    echo "" | tee -a "${SPIKE_OUT}"
    echo "==> VALIDATOR PASSED" | tee -a "${SPIKE_OUT}"
    echo "    Schema validator accepted the password? + !secret combination." | tee -a "${SPIKE_OUT}"
    echo "    Plan 02's run.sh logic (Master-Key lifecycle) is safe to proceed." | tee -a "${SPIKE_OUT}"
    echo "" | tee -a "${SPIKE_OUT}"
    echo "==> NEXT STEP for full empirical validation:" | tee -a "${SPIKE_OUT}"
    echo "    1. Copy ${SPIKE_DIR} to a real HA-OS instance" | tee -a "${SPIKE_OUT}"
    echo "    2. Add the local repo URL to HA Settings → Add-ons → Add-on Store" | tee -a "${SPIKE_OUT}"
    echo "    3. Install the 'Spike Add-on (litellm-secret-schema)' add-on" | tee -a "${SPIKE_OUT}"
    echo "    4. Verify HA Supervisor accepts the options without rejecting the !secret default" | tee -a "${SPIKE_OUT}"
    echo "    5. Update DOCS.md §Spike Result with the install result" | tee -a "${SPIKE_OUT}"
else
    echo "" | tee -a "${SPIKE_OUT}"
    echo "==> VALIDATOR FAILED" | tee -a "${SPIKE_OUT}"
    echo "    Schema validator rejected the password? + !secret combination." | tee -a "${SPIKE_OUT}"
    echo "    Plan 02's run.sh logic would NOT be safe — find an alternative (e.g. use" | tee -a "${SPIKE_OUT}"
    echo "    'str?' instead of 'password?' for the schema, or use a different !secret pattern)." | tee -a "${SPIKE_OUT}"
    exit 1
fi

echo ""
echo "Spike output written to ${SPIKE_OUT}"
