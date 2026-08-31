#!/usr/bin/env bash
# spike-pitfalls10-backup-addon-config.sh — Phase 9 PITFALLS §10:
# does HA's backup integration cover files under /addon_config?
#
# Per CONTEXT.md D-16, the spike reuses any already-installed add-on that
# declares `map: addon_config:rw`. The plan's primary example was
# `authentik` (per authentik/config.yaml:17-20), but authentik is not
# installed on the H-1 target host haos-op3050-1 at execution time.
# Two of the repo's other add-ons are installed and have the same mount:
#   - gatus      → 72a005f5_gatus      (map: addon_config:rw)
#   - phone-logger → 72a005f5_phone-logger (map: addon_config:rw)
# The default target is phone-logger (closest in spirit to the bridge add-on
# we are testing). Pass the slug as $2 to override.
#
# PRE-APPROVED in /gsd-discuss-phase as the procedure. Read-mostly: the
# only host action is triggering a backup, which is a brief snapshot.
#
# Usage: ./internal/spike-pitfalls10-backup-addon-config.sh [haos-host [addon-slug]]
# Defaults: host=haos-op3050-1, slug=72a005f5_phone-logger
#
# Output: verbatim shell transcript at /tmp/spike-pitfalls10-<run-id>.log
# (also streamed to stdout).

set -euo pipefail

HOST="${1:-haos-op3050-1}"
ADDON_SLUG="${2:-72a005f5_phone-logger}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
TRANSCRIPT="/tmp/spike-pitfalls10-${RUN_ID}.log"
SENTINEL_NAME="phase9-sentinel-${RUN_ID}.txt"
SENTINEL_DATA="phase-9-sentinel-data-${RUN_ID}"

exec > >(tee -a "${TRANSCRIPT}") 2>&1

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
blue()   { printf '\033[0;34m%s\033[0m\n' "$*"; }

# Cleanup removes the sentinel from the add-on's /addon_config and the local
# backup tarball. The HA-side backup file at /backup/phase9-backup-*.tar is
# NOT cleaned up — HA backups are user-managed and the file name makes its
# test-artifact status obvious for manual cleanup.
cleanup() {
    local exit_code=$?
    yellow ""
    yellow "── Cleanup: removing sentinel + local backup copy ──"
    ssh "${HOST}" "rm -f /addon_configs/${ADDON_SLUG}/${SENTINEL_NAME}" >/dev/null 2>&1 || true
    rm -rf "${LOCAL_BACKUP:-/tmp/phase9-backup-${RUN_ID}.tar}" \
           "${BACKUP_DIR:-/tmp/phase9-backup-${RUN_ID}}" >/dev/null 2>&1 || true
    exit "${exit_code}"
}
trap cleanup EXIT

blue "================================================================"
blue "PITFALLS §10 SPIKE — Phase 9 backup integration vs /addon_config mount"
blue "================================================================"
blue "Host:         ${HOST}"
blue "Target slug:  ${ADDON_SLUG}"
blue "Run ID:       ${RUN_ID}"
blue "Transcript:   ${TRANSCRIPT}"
blue ""
blue "Read-mostly: only the add-on's writable /addon_config path is touched."
blue "Triggering an HA backup is a brief snapshot, not a destructive op."
blue ""

# Pre-flight: confirm the target add-on is installed AND has addon_config:rw
blue "── Pre-flight: verify target add-on has map: addon_config:rw ──"
ADDON_INFO="$(ssh "${HOST}" sudo ha apps info "${ADDON_SLUG}" 2>&1)" || {
    red "  ✗ Add-on ${ADDON_SLUG} not installed on ${HOST}"
    red "    Install an add-on with map: addon_config:rw and re-run, e.g.:"
    red "      ./internal/spike-pitfalls10-backup-addon-config.sh ${HOST} 72a005f5_phone-logger"
    echo "RESULT: inconclusive"
    exit 1
}
green "  ✓ Add-on ${ADDON_SLUG} found on ${HOST}"

# ── Step 1: create sentinel inside the target add-on container ──────────────────
# The add-on's /addon_config/ path is bind-mounted from the host at
# /addon_configs/<slug>/. Writing directly to the host path is equivalent to
# writing inside the container (the bind mount is bidirectional) and avoids
# the need for `ha apps stdin` (which is not implemented in the current `ha`
# CLI as of 2026-08; the SPIKE-09 alternative is the Supervisor REST API's
# /addons/<slug>/exec endpoint, which would require a SUPERVISOR_TOKEN).
blue ""
blue "── Step 1: write sentinel file under /addon_config inside ${ADDON_SLUG} ──"
SENTINEL_HOST_DIR="/addon_configs/${ADDON_SLUG}"
green "  ssh ${HOST} -- 'echo ${SENTINEL_DATA} > ${SENTINEL_HOST_DIR}/${SENTINEL_NAME}'"
ssh "${HOST}" "echo '${SENTINEL_DATA}' > ${SENTINEL_HOST_DIR}/${SENTINEL_NAME}"
green "  verifying sentinel exists on host at ${SENTINEL_HOST_DIR}/${SENTINEL_NAME}:"
ssh "${HOST}" "ls -la ${SENTINEL_HOST_DIR}/${SENTINEL_NAME}"
ssh "${HOST}" "cat ${SENTINEL_HOST_DIR}/${SENTINEL_NAME}"
green "Step 1 complete: sentinel file written on host (visible to add-on container via bind mount)."

# ── Step 2: trigger HA backup ───────────────────────────────────────────────────
blue ""
blue "── Step 2: trigger HA backup integration ──"
BACKUP_NAME="phase9-backup-${RUN_ID}.tar"
green "  ssh ${HOST} sudo ha backups new --name phase9-${RUN_ID} --app ${ADDON_SLUG}"
ssh "${HOST}" sudo ha backups new --name "phase9-${RUN_ID}" --app "${ADDON_SLUG}" 2>&1 || {
    red "  ✗ Backup creation returned non-zero — see 'ha backups list' and 'ha supervisor logs'"
    echo "RESULT: inconclusive"
    exit 1
}
sleep 5
green "  verifying backup appears in 'ha backups list':"
ssh "${HOST}" sudo ha backups list 2>&1 | grep "phase9-${RUN_ID}" || {
    red "  ✗ Backup phase9-${RUN_ID} not visible in 'ha backups list'"
    echo "RESULT: inconclusive"
    exit 1
}
green "Step 2 complete: HA backup created and visible."

# ── Step 3: pull backup tarball locally and inspect ────────────────────────────
blue ""
blue "── Step 3: download backup tarball and inspect contents ──"
# The backup file slug is auto-generated by HA; we look it up via 'ha backups list'
# by finding the entry whose `name:` matches our --name argument, then reading
# the `slug:` field from the same YAML record.
BACKUP_SLUG="$(ssh "${HOST}" sudo ha backups list 2>&1 | awk -v name="phase9-${RUN_ID}" '
    $0 ~ "name: " name {found=1; next}
    found && /slug:/ {print $2; exit}
    found && /^[^ ]/ {found=0}
')"
if [[ -z "${BACKUP_SLUG}" ]]; then
    red "  ✗ Could not find slug for backup phase9-${RUN_ID}"
    echo "RESULT: inconclusive"
    exit 1
fi
BACKUP_FILE="${BACKUP_SLUG}.tar"
LOCAL_BACKUP="/tmp/${BACKUP_FILE}"
green "  resolved slug: ${BACKUP_SLUG} → file: ${BACKUP_FILE}"
green "  rsync -av ${HOST}:/backup/${BACKUP_FILE} ${LOCAL_BACKUP}"
rsync -av "${HOST}:/backup/${BACKUP_FILE}" "${LOCAL_BACKUP}" 2>&1 | tail -3
BACKUP_DIR="/tmp/phase9-backup-${RUN_ID}"
mkdir -p "${BACKUP_DIR}"
green "  tar -xf '${LOCAL_BACKUP}' -C '${BACKUP_DIR}'"
tar -xf "${LOCAL_BACKUP}" -C "${BACKUP_DIR}" 2>&1
green "  backup root contents (first 30 entries):"
ls "${BACKUP_DIR}" | head -30
green "Step 3 complete: backup unpacked locally."

# ── Step 4: search for the sentinel under any backup path ──────────────────────
# The HA backup structure is: top-level backup tar contains per-addon tar.gz
# files (one per add-on) PLUS a backup.json manifest. The actual add-on data
# (including /addon_config contents when symlinked into /data) lives INSIDE
# the per-addon tar.gz. So we have to extract each per-addon tar.gz and grep
# recursively across the extracted tree to find the sentinel data string.
blue ""
blue "── Step 4: search backup for sentinel file (recursive unpack + grep) ──"
EXTRACTED_DIR="${BACKUP_DIR}/extracted"
mkdir -p "${EXTRACTED_DIR}"
green "  extracting all per-addon tar.gz files into ${EXTRACTED_DIR}"
for tgz in "${BACKUP_DIR}"/*.tar.gz; do
    [[ -e "${tgz}" ]] || continue
    base="$(basename "${tgz}" .tar.gz)"
    mkdir -p "${EXTRACTED_DIR}/${base}"
    tar -xzf "${tgz}" -C "${EXTRACTED_DIR}/${base}" 2>/dev/null || true
done
green "  grepping extracted tree for sentinel data string:"
if grep -r -- "${SENTINEL_DATA}" "${EXTRACTED_DIR}" 2>/dev/null; then
    RESULT="addon_config_backed_up"
    green ""
    green "  ✓ Sentinel FOUND in backup tarball."
    green ""
    green "RESULT: ${RESULT}"
    blue ""
    blue "  D-19 implication: Phase 13 STATE-01 mitigation (map: addon_config:rw)"
    blue "  works as designed — secondary state files ARE included in HA backups."
    blue "  Phase 13 may rely on this for the secondary state-copy mitigation."
else
    RESULT="addon_config_not_backed_up"
    yellow ""
    yellow "  ✗ Sentinel NOT FOUND anywhere in the backup tarball."
    yellow ""
    yellow "RESULT: ${RESULT}"
    blue ""
    blue "  D-19 implication: Phase 13 cannot rely on addon_config:rw for backup"
    blue "  coverage. Must add an explicit secondary-state-copy endpoint"
    blue "  (POST /v1/state/export + POST /v1/state/import per PITFALLS ST-3),"
    blue "  OR drop the mitigation entirely and rely on DOCS.md warning + the"
    blue "  per-resource state-push approach."
fi

echo ""
echo "TRANSCRIPT DONE: ${TRANSCRIPT}"
echo "RESULT: ${RESULT}"