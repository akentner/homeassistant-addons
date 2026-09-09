#!/usr/bin/env bash
#
# dispatch-builds.sh — create an explicit workflow_dispatch for every add-on
# whose files an automated version-bump commit touched.
#
# WHY THIS SCRIPT EXISTS
#
# Both bump workflows — .github/workflows/auto-update.yml (cron 06:00 UTC) and
# .github/workflows/base-image-update.yml (cron 07:00 UTC) — commit and push to
# main using the default GITHUB_TOKEN. GitHub creates NO new workflow runs for
# an event produced by that token. Every .github/workflows/build-<addon>.yml
# triggers on `push` to `main` with `paths: <addon>/**`, so none of them ever
# fires for an automated bump.
#
# Measured evidence (do not re-investigate — this is proven):
#   - commit d3682f6 ("chore(meridian): update to 1.68.0") produced ZERO
#     build-meridian runs;
#   - base-image commits aaf6084 and 08dee0b produced ZERO runs for either sha;
#   - ghcr.io amd64-meridian:1.68.0-0 answered HTTP 404 while
#     meridian/config.yaml already advertised that version — the add-on store
#     offered an update whose image does not exist, which the HA Supervisor
#     surfaces to the user as "Unknown error".
#
# workflow_dispatch is the documented exception: a dispatch event created with
# GITHUB_TOKEN DOES produce a run. So instead of relying on the push, each bump
# workflow calls this script to create one dispatch per changed add-on.
# See: https://docs.github.com/actions/using-workflows/triggering-a-workflow
#
# USAGE
#
#   Usage: internal/dispatch-builds.sh [addon ...]
#
# With arguments, the listed add-ons are dispatched. With no arguments, the
# add-on set is derived from the commits the caller just created.
#
# ENVIRONMENT
#
#   BASE_SHA  required in no-argument mode: the pre-bump HEAD. The candidate
#             set is `git diff --name-only "$BASE_SHA..HEAD"` reduced to first
#             path segments.
#   DRY_RUN   set to 1 to print the gh commands instead of running them.
#   REF       dispatch ref override. Falls back to GITHUB_REF_NAME, then to the
#             current branch name.
#
# OUTPUT CONTRACT (consumed by tests, and by quick item 260909-rln, which
# rewrites this script into a single batched dispatch and must preserve it)
#
#   stdout: exactly one line per candidate, `ADDON <name> <STATE>`, emitted in
#           `sort -u` order of the candidate names. <STATE> is one of
#           DISPATCHED, DRY_RUN, SKIPPED_NO_WORKFLOW, SKIPPED_BAD_NAME, FAILED.
#           In DRY_RUN mode a candidate that has a workflow additionally prints
#           the literal gh command, prefixed `DRY_RUN: `.
#   stderr: human INFO: / WARN: / ERROR: lines only.
#   exit:   0 when every candidate reached a non-FAILED state (skips included);
#           1 when any dispatch failed or BASE_SHA is required but unset.
#
set -euo pipefail

USAGE="Usage: internal/dispatch-builds.sh [addon ...]

With arguments: dispatch build-<addon>.yml for each named add-on.
Without arguments: derive the add-on set from git diff --name-only \$BASE_SHA..HEAD.

Environment:
  BASE_SHA  required without arguments — the pre-bump HEAD
  DRY_RUN   1 = print the gh commands instead of running them
  REF       dispatch ref override (default: \$GITHUB_REF_NAME, then current branch)"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    printf '%s\n' "$USAGE"
    exit 0
fi

if [ "$#" -gt 0 ]; then
    # sort -u dedupes: a dispatch builds the REF, not a commit, so two
    # dispatches for the same name are pure waste.
    candidates=$(printf '%s\n' "$@" | sort -u)
else
    if [ -z "${BASE_SHA:-}" ]; then
        echo "ERROR: BASE_SHA is unset and no add-on arguments were given" >&2
        printf '%s\n' "$USAGE" >&2
        exit 1
    fi

    # Plain command substitution, deliberately NOT `mapfile < <(git diff ...)`:
    # a process-substitution failure is invisible to `set -e` and would hand
    # back an empty candidate list plus a green run. Here a failing git diff
    # (bad BASE_SHA, shallow clone) aborts the script on this line instead.
    changed_files=$(git diff --name-only "${BASE_SHA}..HEAD")

    # The trailing `|| candidates=""` is mandatory: under `pipefail` grep's
    # no-match exit 1 becomes a failed assignment that `set -e` would abort on.
    candidates=$(printf '%s\n' "$changed_files" | cut -d/ -f1 | sort -u | grep -v '^$') || candidates=""
fi

if [ -z "$candidates" ]; then
    echo "INFO: no candidate add-ons — nothing to dispatch" >&2
    exit 0
fi

# The ref is MEASURED rather than hardcoded to main, so this script stays
# correct on a release branch or in a test checkout. A detached HEAD cannot be
# guessed, so it is a hard error telling the caller to set REF.
ref="${REF:-${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}}"
if [ -z "$ref" ] || [ "$ref" = "HEAD" ]; then
    echo "ERROR: cannot resolve a dispatch ref (detached HEAD?); set REF explicitly" >&2
    exit 1
fi

failed=0

# A here-string, deliberately not a pipe: `... | while read` runs the body in a
# subshell, so the `failed` counter set inside would be lost on exit.
while IFS= read -r addon; do
    [ -n "$addon" ] || continue

    # Defense-in-depth name-shape gate. The authoritative gate is the
    # workflow-file test below — an ill-formed name cannot resolve to an
    # existing .github/workflows/build-<name>.yml. This check exists so a
    # traversal-shaped path is rejected with an accurate message instead of
    # being reported as a merely missing workflow.
    if [[ ! "$addon" =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
        echo "ADDON $addon SKIPPED_BAD_NAME"
        echo "WARN: '$addon' is not a well-formed add-on directory name; skipping" >&2
        continue
    fi

    workflow="build-${addon}.yml"
    if [ ! -f ".github/workflows/${workflow}" ]; then
        echo "ADDON $addon SKIPPED_NO_WORKFLOW"
        echo "WARN: no .github/workflows/${workflow} for '$addon' — expected, not an error." >&2
        echo "WARN: either '$addon' is not an add-on directory at all (the common case: a bump" >&2
        echo "WARN: commit also touches .planning, internal, .github and root files), or the" >&2
        echo "WARN: add-on is built locally by the Supervisor because its config.yaml declares" >&2
        echo "WARN: no image: key — the LOCAL_BUILD_ADDONS concept in internal/check-version-tags.sh." >&2
        continue
    fi

    if [ "${DRY_RUN:-0}" = "1" ]; then
        echo "DRY_RUN: gh workflow run $workflow --ref $ref"
        echo "ADDON $addon DRY_RUN"
        continue
    fi

    # The `if` form is required: a bare call returning non-zero would abort the
    # loop under `set -e` before the remaining add-ons are dispatched.
    if gh workflow run "$workflow" --ref "$ref"; then
        echo "ADDON $addon DISPATCHED"
    else
        echo "ERROR: gh workflow run $workflow --ref $ref failed" >&2
        echo "ADDON $addon FAILED"
        failed=1
    fi
done <<< "$candidates"

# Exit non-zero on any failed dispatch. The push has already landed, so the
# repository now sits in exactly the broken state this script exists to
# prevent — a green run would hide it.
exit "$failed"
