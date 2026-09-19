#!/usr/bin/env bash
# Verify the litellm/ add-on Postgres reset procedure (DOCS.md §Backup & Restore) works end-to-end.
# Manual invocation: bash internal/verify-litellm-postgres-reset.sh
set -euo pipefail

IMAGE_TAG="litellm-verify:local"
CONTAINER_NAME="litellm-reset-verify"
SYNTHETIC_OPTIONS='{"log_level":"info","master_key":"","salt_key":"","providers":{},"models":[],"postgres":{"shared_buffers":"64MB","max_connections":20,"log_min_duration_statement":1000}}'

# Materialize synthetic options.json before docker run so the mount below has a real file to bind
echo "${SYNTHETIC_OPTIONS}" > /tmp/litellm-verify-options.json

# Step 1: Start the container once to populate /data/postgresql
echo "==> Step 1: initial start populates /data/postgresql"
docker run --rm --name "${CONTAINER_NAME}" \
    -v /tmp/litellm-verify-data:/data \
    -v /tmp/litellm-verify-options.json:/data/options.json:ro \
    "${IMAGE_TAG}" > /tmp/litellm-verify-initial.log 2>&1 &
CONTAINER_PID=$!

# Wait for "PostgreSQL ready."
for _ in $(seq 1 60); do
    if grep -q 'PostgreSQL ready' /tmp/litellm-verify-initial.log 2>/dev/null; then
        break
    fi
    sleep 1
done

docker kill "${CONTAINER_NAME}" 2>/dev/null || true
wait "${CONTAINER_PID}" 2>/dev/null || true

if ! grep -q 'PostgreSQL ready' /tmp/litellm-verify-initial.log; then
    echo "✗ initial start did not produce 'PostgreSQL ready.' log line"
    exit 1
fi
echo "✓ initial start: PostgreSQL ready."

# Step 2: rm -rf /data/postgresql (simulates operator running DOCS.md reset procedure)
echo "==> Step 2: rm -rf /data/postgresql (DOCS.md reset procedure)"
rm -rf /tmp/litellm-verify-data/postgresql
if [ -d /tmp/litellm-verify-data/postgresql ]; then
    echo "✗ /data/postgresql still exists after rm -rf"
    exit 1
fi
echo "✓ /data/postgresql removed"

# Step 3: Restart the container — initdb runs fresh
echo "==> Step 3: restart — initdb runs fresh"
docker run --rm --name "${CONTAINER_NAME}" \
    -v /tmp/litellm-verify-data:/data \
    -v /tmp/litellm-verify-options.json:/data/options.json:ro \
    "${IMAGE_TAG}" > /tmp/litellm-verify-reset.log 2>&1 &
CONTAINER_PID=$!

# Wait for "PostgreSQL ready." again
for _ in $(seq 1 60); do
    if grep -q 'PostgreSQL ready' /tmp/litellm-verify-reset.log 2>/dev/null; then
        break
    fi
    sleep 1
done

docker kill "${CONTAINER_NAME}" 2>/dev/null || true
wait "${CONTAINER_PID}" 2>/dev/null || true

if ! grep -q 'PostgreSQL ready' /tmp/litellm-verify-reset.log; then
    echo "✗ reset start did not produce 'PostgreSQL ready.' log line"
    exit 1
fi

# Verify initdb log line fired (proves fresh initdb, not stale cluster)
if ! grep -q 'Initializing PostgreSQL' /tmp/litellm-verify-reset.log; then
    echo "✗ initdb did not run after rm -rf (fresh cluster expected)"
    exit 1
fi
echo "✓ reset: initdb ran fresh, PostgreSQL ready."

# Cleanup
rm -rf /tmp/litellm-verify-data /tmp/litellm-verify-options.json /tmp/litellm-verify*.log

echo ""
echo "All litellm Postgres reset verifications passed."
