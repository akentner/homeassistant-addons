#!/bin/bash
# Refresh every SHA256 pin of the coding-assistants add-on on a Renovate branch (used by
# .github/workflows/refresh-pins.yml, runnable locally). Renovate only bumps the *_VERSION values in build.yaml; this
# script (idempotent) runs the three pin scripts, checks the Dockerfile/build.yaml mirror (scenario `drift`) and, when
# the PR carries version bumps relative to BASE_REF and has no add-on version bump yet, bumps the add-on subpatch
# (make update-version --no-tag equivalent) and adds a CHANGELOG entry.
#
# Usage: BASE_REF=origin/main internal/refresh-pins-ci.sh      (needs gh with GH_TOKEN, curl, python3)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
BASE_REF="${BASE_REF:-origin/main}"
ADDON="coding-assistants"

internal/update-tool-pins.sh
internal/update-codex-pins.sh
internal/update-opencode-pins.sh
internal/verify-coding-assistants.sh drift

# Pairs "KEY old new" for every *_VERSION arg of build.yaml that differs from BASE_REF (VERSION itself excluded)
version_changes() {
    local key old new
    while IFS= read -r key; do
        old="$(git show "${BASE_REF}:${ADDON}/build.yaml" | sed -nE "s/^  ${key}: \"([^\"]+)\"\$/\1/p")"
        new="$(sed -nE "s/^  ${key}: \"([^\"]+)\"\$/\1/p" "${ADDON}/build.yaml")"
        [[ -n "${old}" && "${old}" != "${new}" ]] && echo "${key} ${old} ${new}"
    done < <(sed -nE 's/^  ([A-Z0-9_]+_VERSION): .*/\1/p' "${ADDON}/build.yaml")
    return 0
}

config_version() { sed -nE 's/^version: "([^"]+)"$/\1/p'; }

changes="$(version_changes)"
base_cfg="$(git show "${BASE_REF}:${ADDON}/config.yaml" | config_version)"
cur_cfg="$(config_version <"${ADDON}/config.yaml")"

if [[ -n "${changes}" && "${cur_cfg}" == "${base_cfg}" ]]; then
    [[ "${base_cfg}" =~ ^([0-9]+\.[0-9]+\.[0-9]+)-([0-9]+)$ ]] || { echo "unexpected add-on version '${base_cfg}'" >&2; exit 1; }
    next="${BASH_REMATCH[1]}-$((BASH_REMATCH[2] + 1))"
    ./internal/update-version.py "${ADDON}" "${next}" --no-tag

    entries=""
    while read -r key old new; do
        name="${key%_VERSION}"
        name="$(tr '[:upper:]_' '[:lower:] ' <<<"${name}")"
        entries+="- ${name} ${old} → ${new} (SHA256 pin refreshed)."$'\n'
    done <<<"${changes}"
    NEXT="${next}" ENTRIES="${entries}" DATE="$(date -u +%F)" python3 -I - <<'PY'
import os
from pathlib import Path

path = Path("coding-assistants/CHANGELOG.md")
text = path.read_text()
marker = "## [Unreleased]\n"
section = f"\n## [{os.environ['NEXT']}] - {os.environ['DATE']}\n\n### Changed\n\n{os.environ['ENTRIES']}"
if f"## [{os.environ['NEXT']}]" not in text:
    path.write_text(text.replace(marker, marker + section, 1))
PY
    echo "Add-on version bumped to ${next}"
else
    echo "No add-on version bump needed (changes: ${changes:-none}, base ${base_cfg}, current ${cur_cfg})"
fi
