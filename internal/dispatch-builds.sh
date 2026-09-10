#!/usr/bin/env bash
#
# dispatch-builds.sh — create ONE explicit workflow_dispatch of build.yml
# naming every add-on whose files an automated version-bump commit touched.
#
# WHY THIS SCRIPT EXISTS
#
# Both bump workflows — .github/workflows/auto-update.yml (cron 06:00 UTC) and
# .github/workflows/base-image-update.yml (cron 07:00 UTC) — commit and push to
# main using the default GITHUB_TOKEN. GitHub creates NO new workflow runs for
# an event produced by that token. .github/workflows/build.yml triggers on
# `push` to `main` with a manifest-path filter, so it never fires for an
# automated bump. (Before build.yml this was nine separate build-<addon>.yml
# callers, each filtered on `<addon>/**`; the same limitation applied to all.)
#
# Measured evidence (do not re-investigate — this is proven):
#   - commit d3682f6 ("chore(meridian): update to 1.68.0") produced ZERO
#     build runs for meridian;
#   - base-image commits aaf6084 and 08dee0b produced ZERO runs for either sha;
#   - ghcr.io amd64-meridian:1.68.0-0 answered HTTP 404 while
#     meridian/config.yaml already advertised that version — the add-on store
#     offered an update whose image does not exist, which the HA Supervisor
#     surfaces to the user as "Unknown error".
#
# workflow_dispatch is the documented exception: a dispatch event created with
# GITHUB_TOKEN DOES produce a run. So instead of relying on the push, each bump
# workflow calls this script, which creates a single dispatch whose `addons`
# input lists every changed add-on.
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
#   DRY_RUN   set to 1 to print the gh command instead of running it.
#   REF       dispatch ref override. Falls back to GITHUB_REF_NAME, then to the
#             current branch name.
#
# OUTPUT CONTRACT (consumed by tests)
#
#   stdout: exactly one line per candidate, `ADDON <name> <STATE>`, emitted in
#           `sort -u` order of the candidate names. <STATE> is one of
#           DISPATCHED, DRY_RUN, SKIPPED_NO_WORKFLOW, SKIPPED_BAD_NAME, FAILED.
#           In DRY_RUN mode the single gh command that would have run is
#           additionally printed once, prefixed `DRY_RUN: `, naming every
#           dispatchable candidate. Nothing is printed when no candidate is
#           dispatchable.
#   stderr: human INFO: / WARN: / ERROR: lines only.
#   exit:   0 when every candidate reached a non-FAILED state (skips included);
#           1 when the dispatch failed or BASE_SHA is required but unset.
#
# Because one dispatch carries one outcome, every dispatchable candidate shares
# DISPATCHED or shares FAILED. SKIPPED_NO_WORKFLOW keeps its name but now means
# "no add-on manifest at that path".
#
set -euo pipefail

USAGE="Usage: internal/dispatch-builds.sh [addon ...]

With arguments: dispatch build.yml once, with the named add-ons as its addons input.
Without arguments: derive the add-on set from git diff --name-only \$BASE_SHA..HEAD.

Environment:
  BASE_SHA  required without arguments — the pre-bump HEAD
  DRY_RUN   1 = print the gh command instead of running it
  REF       dispatch ref override (default: \$GITHUB_REF_NAME, then current branch)"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    printf '%s\n' "$USAGE"
    exit 0
fi

if [ "$#" -gt 0 ]; then
    # sort -u dedupes: a dispatch builds the REF, not a commit, so naming the
    # same add-on twice in one addons list is pure waste.
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
    #
    # Deliberately UNFILTERED, even though build.yml's paths: filter is
    # narrower. The asymmetry is safe in one direction only: this script is
    # MORE eager than the trigger (a README-only bump path still produces a
    # dispatch), never less, so no build can be missed.
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

# PASS 1 — classify every candidate before anything is dispatched.
#
# One dispatch carries one outcome, so the loop can no longer print as it goes:
# a candidate's final state is not known until the single gh call has run.
# These two arrays are the parallel name/state lists; they stay in the `sort -u`
# order of the input, and nothing re-sorts them at print time. That ordering is
# CONTRACT, not cosmetics — quick item 260909-rln's GATE-G2-3 and 260909-rlj's
# GATE-T1-5 both assert it, and re-sorting late would hide an ordering bug
# rather than prevent one.
names=()
states=()
addon_list=""

# A here-string, deliberately not a pipe: `... | while read` runs the body in a
# subshell, so the arrays built inside would be lost on exit.
while IFS= read -r addon; do
    [ -n "$addon" ] || continue

    # Defense-in-depth name-shape gate. The authoritative gate is the manifest
    # test below — an ill-formed name cannot resolve to an existing add-on
    # directory. This check exists so a traversal-shaped path is rejected with
    # an accurate message instead of being reported as a missing manifest.
    if [[ ! "$addon" =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
        names+=("$addon")
        states+=("SKIPPED_BAD_NAME")
        echo "WARN: '$addon' is not a well-formed add-on directory name; skipping" >&2
        continue
    fi

    # An add-on directory is config.yaml + build.yaml + Dockerfile, all three.
    # That is the definition .github/workflows/lint.yml, the release target in
    # Makefile and internal/check-version-tags.sh already use, and using the
    # identical triple is what keeps this script from ever being MORE
    # restrictive than build.yml's own derivation: a script that skipped an
    # add-on build.yml would have accepted is a silently missing image, whereas
    # the reverse is only a harmless no-op run.
    if [ ! -f "${addon}/config.yaml" ] || [ ! -f "${addon}/build.yaml" ] || [ ! -f "${addon}/Dockerfile" ]; then
        names+=("$addon")
        states+=("SKIPPED_NO_WORKFLOW")
        echo "WARN: '$addon' is not an add-on directory (no config.yaml + build.yaml +" >&2
        echo "WARN: Dockerfile triple) — expected, not an error. The common case: a bump" >&2
        echo "WARN: commit also touches .planning, internal, .github and root files." >&2
        continue
    fi

    names+=("$addon")
    states+=("PENDING")
    if [ -z "$addon_list" ]; then
        addon_list="$addon"
    else
        addon_list="${addon_list},${addon}"
    fi
done <<< "$candidates"

# PASS 2 — one dispatch for every dispatchable candidate, or none at all.
failed=0
resolved=""

if [ -n "$addon_list" ]; then
    if [ "${DRY_RUN:-0}" = "1" ]; then
        echo "DRY_RUN: gh workflow run build.yml --ref $ref -f addons=$addon_list"
        resolved="DRY_RUN"
    # The `if` form is required: a bare call returning non-zero would abort the
    # script under `set -e` before the resolved states can be printed.
    elif gh workflow run build.yml --ref "$ref" -f addons="$addon_list"; then
        resolved="DISPATCHED"
    else
        echo "ERROR: gh workflow run build.yml --ref $ref -f addons=$addon_list failed" >&2
        resolved="FAILED"
        failed=1
    fi
else
    # Not merely a no-op worth skipping: an EMPTY addons input means "build
    # every add-on" in build.yml, so dispatching an empty list would turn a
    # zero-add-on bump into nine full builds. gh must not be reached at all.
    echo "INFO: no dispatchable add-on among the candidates — not dispatching" >&2
fi

# PASS 3 — print the contract lines in the order pass 1 recorded them.
for i in "${!names[@]}"; do
    if [ "${states[$i]}" = "PENDING" ]; then
        echo "ADDON ${names[$i]} ${resolved}"
    else
        echo "ADDON ${names[$i]} ${states[$i]}"
    fi
done

# Exit non-zero on a failed dispatch. The push has already landed, so the
# repository now sits in exactly the broken state this script exists to
# prevent — a green run would hide it.
exit "$failed"
