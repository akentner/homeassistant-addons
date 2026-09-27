#!/usr/bin/env bash
# Regression test for the update-version.py tag-timing bug (260927-r2j /
# 260927-vbk incidents, documented in .planning/quick/): create_and_push_tag()
# used to run in the same invocation as the version-file edits, before any
# commit existed for them, so the annotated tag always pointed at the PRE-bump
# commit. This proves, against a real throwaway git repo (no Docker, no
# network, no origin remote required), that:
#
#   1. Tagging is DEFERRED while the version files it just wrote are still
#      uncommitted (the exact precondition that caused both incidents).
#   2. Once committed, a re-run creates the tag pointing at the commit that
#      ACTUALLY contains the bumped version.
#
# UPDATE_VERSION_PY may be overridden to point at an alternate copy of the
# script (e.g. a pre-fix scratch copy) to prove this test fails against the
# old buggy behavior. Defaults to this repo's own internal/update-version.py.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

red()    { echo -e "${RED}$*${NC}"; }
green()  { echo -e "${GREEN}$*${NC}"; }
yellow() { echo -e "${YELLOW}$*${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_VERSION_PY="${UPDATE_VERSION_PY:-${SCRIPT_DIR}/update-version.py}"
FAIL=0

WORK_DIR="$(mktemp -d)"
# shellcheck disable=SC2317 # intentional: only invoked indirectly via `trap ... EXIT` below
cleanup() {
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

if [[ ! -f "${UPDATE_VERSION_PY}" ]]; then
    red "FAIL: UPDATE_VERSION_PY not found at ${UPDATE_VERSION_PY}"
    exit 1
fi

yellow "Testing ${UPDATE_VERSION_PY}"
yellow "Setting up throwaway git repo at ${WORK_DIR}..."
cd "${WORK_DIR}"
git init -q
git config user.email "test@example.invalid"
git config user.name "verify-update-version-tag-timing"
git config commit.gpgsign false

mkdir fakeaddon
cat > fakeaddon/config.yaml <<'EOF'
name: "Fake Addon"
version: "1.0.0-0"
slug: fakeaddon
EOF
cat > fakeaddon/build.yaml <<'EOF'
build_from:
  amd64: "ghcr.io/home-assistant/amd64-base:3.20"
args:
  VERSION: "1.0.0"
EOF
cat > fakeaddon/README.md <<'EOF'
# Fake Addon

[release-shield]: https://img.shields.io/badge/version-v1.0.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.0.0
EOF

git add -A
git commit -q -m "initial state: fakeaddon at 1.0.0-0"
INITIAL_SHA="$(git rev-parse HEAD)"
yellow "Initial commit: ${INITIAL_SHA}"

echo ""
yellow "Step 1: run update-version.py WITHOUT committing the result..."
set +e
STEP1_OUTPUT="$(python3 "${UPDATE_VERSION_PY}" fakeaddon 1.0.0-1 --no-push 2>&1)"
STEP1_EXIT=$?
set -e
echo "${STEP1_OUTPUT}"

if [[ "${STEP1_EXIT}" -ne 0 ]]; then
    red "FAIL: update-version.py exited ${STEP1_EXIT} on the first (uncommitted) run -- expected 0"
    FAIL=1
fi

if echo "${STEP1_OUTPUT}" | grep -qi "refusing to tag"; then
    green "PASS: script refused to tag while version files are uncommitted"
else
    red "FAIL: script did not report refusing to tag on a dirty working tree"
    FAIL=1
fi

if git rev-parse --verify "refs/tags/fakeaddon/v1.0.0-1" >/dev/null 2>&1; then
    red "FAIL: tag fakeaddon/v1.0.0-1 exists after the uncommitted run -- this is the exact bug"
    FAIL=1
else
    green "PASS: no tag was created while the bump was uncommitted"
fi

CURRENT_SHA="$(git rev-parse HEAD)"
if [[ "${CURRENT_SHA}" != "${INITIAL_SHA}" ]]; then
    red "FAIL: HEAD moved without an explicit commit -- test setup assumption violated"
    FAIL=1
fi

echo ""
yellow "Step 2: commit the version-bump files, then re-run (idempotent)..."
git add fakeaddon
git commit -q -m "chore: update fakeaddon to v1.0.0-1"
BUMP_SHA="$(git rev-parse HEAD)"
yellow "Bump commit: ${BUMP_SHA}"

set +e
STEP2_OUTPUT="$(python3 "${UPDATE_VERSION_PY}" fakeaddon 1.0.0-1 --no-push 2>&1)"
STEP2_EXIT=$?
set -e
echo "${STEP2_OUTPUT}"

if [[ "${STEP2_EXIT}" -ne 0 ]]; then
    red "FAIL: update-version.py exited ${STEP2_EXIT} on the second (clean) run -- expected 0"
    FAIL=1
fi

if git rev-parse --verify "refs/tags/fakeaddon/v1.0.0-1" >/dev/null 2>&1; then
    green "PASS: tag fakeaddon/v1.0.0-1 now exists"
else
    red "FAIL: tag fakeaddon/v1.0.0-1 was not created on the clean re-run"
    FAIL=1
fi

TAG_SHA="$(git rev-parse "fakeaddon/v1.0.0-1^{commit}" 2>/dev/null || echo "MISSING")"
if [[ "${TAG_SHA}" == "${BUMP_SHA}" ]]; then
    green "PASS: tag points at the bump commit (${BUMP_SHA}), not the stale initial commit"
else
    red "FAIL: tag points at ${TAG_SHA}, expected the bump commit ${BUMP_SHA}"
    FAIL=1
fi

# The exact assertion that would have caught both real incidents: the tagged
# commit's config.yaml must actually contain the target version.
TAGGED_CONFIG_VERSION="$(git show "${TAG_SHA}:fakeaddon/config.yaml" 2>/dev/null | grep '^version:' | head -1 || true)"
if echo "${TAGGED_CONFIG_VERSION}" | grep -q '1.0.0-1'; then
    green "PASS: the tagged commit's config.yaml actually contains 1.0.0-1"
else
    red "FAIL: the tagged commit's config.yaml reads '${TAGGED_CONFIG_VERSION}', not 1.0.0-1"
    FAIL=1
fi

echo ""
if [[ "${FAIL}" == "1" ]]; then
    red "SOME CHECKS FAILED"
    exit 1
fi

green "ALL CHECKS PASSED"
exit 0
