#!/usr/bin/env bash
# cups-migration-suggestion.sh — read-only migration aid (D-13).
#
# Reads f1c878cb_cups's LIVE CUPS printer queues on haos-op3050-1 and prints a
# ready-to-paste `printers:` YAML snippet matching cups/config.yaml's exact
# options schema shape ({name, uri, enabled}).
#
# READ-ONLY CONTRACT
# -------------------
# This script issues ONLY `ha apps info` (Supervisor read) and `lpstat -v`
# (CUPS read, via `docker exec`) against the OLD add-on. It never calls
# `ha apps install` / `ha apps uninstall` / `ha apps restart`, or any other
# mutating Supervisor verb, anywhere. Pasting the printed suggestion into the
# new `cups` add-on's Options UI — and removing the old add-on — are both
# explicitly manual, human steps per D-13 and the phase's checkpoint gate.
#
# Usage: ./internal/cups-migration-suggestion.sh [haos-host [old-addon-slug]]
# Defaults: host=haos-op3050-1, slug=f1c878cb_cups
#
# Output contract: stdout carries ONLY the printers: YAML suggestion (or a
# single '# No printers found: ...' comment line when there is nothing to
# migrate) so it can be piped/redirected directly into a file or a YAML
# parser. All progress/diagnostic messages go to stderr.

set -euo pipefail

HOST="${1:-haos-op3050-1}"
OLD_SLUG="${2:-f1c878cb_cups}"

info() { printf '\033[0;34m%s\033[0m\n' "$*" >&2; }
ok() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
warn() { printf '\033[0;33m%s\033[0m\n' "$*" >&2; }

info "== cups-migration-suggestion: reading ${OLD_SLUG}'s live config on ${HOST} (read-only) =="

# Step 1: confirm the old add-on is still installed. Read-only Supervisor query.
# shellcheck disable=SC2029 # intentional: local vars expand client-side into the remote command, by design
if ! ssh "${HOST}" ha apps info "${OLD_SLUG}" >/dev/null 2>&1; then
    warn "  ${OLD_SLUG} is not installed on ${HOST} (or the host is unreachable) — nothing to migrate."
    echo "# No printers found: ${OLD_SLUG} is not installed on ${HOST}."
    exit 0
fi
ok "  * ${OLD_SLUG} found on ${HOST}"

# Step 2: discover the old add-on's running container name. HA Supervisor's
# container-naming prefix has changed across versions (this host currently
# names it app_<slug>, older/other hosts may use addon_<slug>) — discover it
# by filtering `docker ps` on the slug rather than assuming a fixed prefix, so
# this script keeps working across Supervisor naming changes. Read-only.
# The container list is captured first and filtered afterwards: piping ssh into
# a head/grep that exits early can SIGPIPE ssh, and under pipefail that discards
# a perfectly good result as soon as more than one container matches (IN-06).
CONTAINER=""
PS_OUT=""
# shellcheck disable=SC2029 # intentional: local vars expand client-side into the remote command, by design
PS_OUT="$(ssh "${HOST}" docker ps --format '{{.Names}}' 2>/dev/null)" || PS_OUT=""
CONTAINER="$(grep -m1 -F -- "${OLD_SLUG}" <<<"${PS_OUT}")" || CONTAINER=""
if [[ -z "${CONTAINER}" ]]; then
    warn "  No running container found for ${OLD_SLUG} on ${HOST} — nothing to migrate."
    echo "# No printers found: no running container for ${OLD_SLUG} on ${HOST}."
    exit 0
fi
ok "  * container: ${CONTAINER}"

# Step 3: read-only CUPS query — lpstat, never lpadmin, never a mutation.
LPSTAT_OUT=""
# shellcheck disable=SC2029 # intentional: local vars expand client-side into the remote command, by design
LPSTAT_OUT="$(ssh "${HOST}" docker exec "${CONTAINER}" lpstat -v 2>/dev/null)" || LPSTAT_OUT=""
if [[ -z "${LPSTAT_OUT}" ]]; then
    warn "  lpstat -v reported no printers registered on ${OLD_SLUG} — nothing to migrate."
    echo "# No printers found: ${OLD_SLUG} has no registered CUPS queues."
    exit 0
fi

# Escape a value for emission inside a double-quoted YAML scalar: backslash first, then double quote.
yaml_escape() {
    local value="${1//\\/\\\\}"
    printf '%s' "${value//\"/\\\"}"
}

# lpstat -v prints one line per queue: "device for <name>: <uri>"
FOUND=0
SOCKET_SEEN=0
SUGGESTION=""
while IFS= read -r line; do
    name="$(printf '%s' "${line}" | sed -nE 's/^device for ([^:]+): .*/\1/p')"
    uri="$(printf '%s' "${line}" | sed -nE 's/^device for [^:]+: (.*)$/\1/p')"
    if [[ -z "${name}" || -z "${uri}" ]]; then
        continue
    fi
    # The new add-on only registers queue names matching [A-Za-z0-9_-]{1,127} (PRINTER_NAME_RE in
    # generate_config.py); flag anything else instead of silently suggesting an entry it would drop.
    if ! [[ "${name}" =~ ^[A-Za-z0-9_-]{1,127}$ ]]; then
        SUGGESTION+="  # WARNING: the add-on skips queue names outside [A-Za-z0-9_-]{1,127};
  # rename \"$(yaml_escape "${name}")\" before using this entry.
"
        warn "  queue name '${name}' would be skipped by the add-on — rename it."
    fi
    if [[ "${uri}" == socket://* ]]; then
        SOCKET_SEEN=1
    fi
    SUGGESTION+="  - name: \"$(yaml_escape "${name}")\"
    uri: \"$(yaml_escape "${uri}")\"
    enabled: true
"
    FOUND=$((FOUND + 1))
done <<<"${LPSTAT_OUT}"

if [[ "${FOUND}" -eq 0 ]]; then
    warn "  lpstat -v output from ${OLD_SLUG} did not parse into any printer entries — nothing to migrate."
    echo "# No printers found: lpstat -v output from ${OLD_SLUG} did not match the expected" \
        "'device for NAME: URI' shape."
    exit 0
fi

printf 'printers:\n%s' "${SUGGESTION}"
if [[ "${SOCKET_SEEN}" -eq 1 ]]; then
    printf '%s\n' \
        "# NOTE: raw-socket (socket://) printers usually need 'driver: brlaser' plus a 'driver_model'" \
        "# search term (e.g. \"MFC-7460DN\"); 'location' is not migrated either." \
        "# See the 'Printer driver' section of cups/DOCS.md."
fi

info "== ${FOUND} printer(s) found. Paste the printers: block above into the new cups add-on's Options UI. =="
