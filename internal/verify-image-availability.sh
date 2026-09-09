#!/usr/bin/env bash
# Verify that every image this repository ADVERTISES can actually be pulled
# anonymously from ghcr.io, at the exact version its config.yaml declares.
#
# THE INVARIANT
# -------------
# For every add-on whose config.yaml declares a top-level `image:` key, an
# ANONYMOUSLY-PULLABLE manifest must exist at that image repository for the
# exact `version:` string in config.yaml, for every ACTIVE arch in its `arch:`
# list.
#
# WHY IT IS LIVE-BREAKING
# -----------------------
# When `image:` is present the Home Assistant Supervisor does NOT build the
# add-on locally — it pulls the prebuilt image from the registry, with no
# credentials at all. If no manifest exists at that exact tag the pull 404s and
# the add-on becomes uninstallable AND un-updatable. Nothing else in this repo
# notices: the store entry still advertises the new version, the lint suite is
# green, and the failure only surfaces when a user clicks "Install" or
# "Update". This guard turns that silent failure into a loud one.
#
# WHY THE PROBE IS ANONYMOUS, AND MUST STAY ANONYMOUS
# ---------------------------------------------------
# This script reads no credential from the environment (no registry PAT, no
# GITHUB_TOKEN, no docker credential helper) and the workflow that runs it
# grants no registry-scope permission. That is a CORRECTNESS condition, not
# least-privilege hygiene: an authenticated probe returns 200 for an image that
# is only pullable WITH credentials — which is exactly what the Supervisor
# cannot do — so an authenticated guard would certify a broken add-on as
# healthy. The only Authorization header this script ever sends is the
# anonymous pull token it fetches from ghcr's own token endpoint.
#
# THE THREE DISTINGUISHABLE GHCR STATES (all three measured 2026-09-09)
# ---------------------------------------------------------------------
# The 403 occurs at the TOKEN endpoint, not at the manifest endpoint:
#
#   repo path (ghcr.io/ stripped)                    tag                          token  manifest  verdict
#   home-assistant/amd64-base                        latest                       200    200       ok
#   home-assistant/amd64-base                        0.0.0-gsd-selftest-absent    200    404       missing
#   home-assistant/amd64-base-gsd-selftest-absent    latest                       403    (none)    denied
#
#   token 200 + manifest 200  -> ok       : the Supervisor can pull this.
#   token 200 + manifest 404  -> missing  : this version was never published.
#   token 403/401             -> denied   : not anonymously pullable. This is
#                                           AMBIGUOUS between a missing package
#                                           and a private package, because ghcr
#                                           does not distinguish the two for an
#                                           anonymous caller. Messages must not
#                                           claim to know which one it is.
#
# Anything else (5xx, 429, curl transport failure), still undecided after all
# retries, is `inconclusive` and exits 2 — never reported as a broken add-on,
# but still a failing run, because a guard that cannot run is not guarding.
#
# EXIT CONTRACT
# -------------
#   0  the invariant holds (or a deliberate skip / a clean --dry-run).
#   1  at least one violation: a missing or denied manifest, or a config.yaml
#      this script cannot interpret.
#   2  the guard could NOT run reliably: shallow clone, ghcr unreachable after
#      retries, a failed --self-test, or a bad argument.
#
# The 1-vs-2 split is the whole point: a network blip must never be reported as
# a broken add-on, and a guard that cannot check must never look green.
#
# USAGE
#   ./internal/verify-image-availability.sh --self-test
#   ./internal/verify-image-availability.sh --probe TEMPLATE --probe-version V [--probe-arch A]
#   ./internal/verify-image-availability.sh --help

set -euo pipefail

# Output vocabulary, matching internal/check-version-tags.sh exactly so both
# guards read alike. Every status line puts its glyph at column 1 followed by a
# single space; acceptance gates count glyphs anchored at column 1, so an
# indented status line reads as a missing one.
readonly GLYPH_PASS="✓"
readonly GLYPH_FAIL="❌"
readonly GLYPH_WARN="⚠️"
readonly GLYPH_AGG_FAIL="🚫"
readonly GLYPH_AGG_OK="✅"

readonly PROBE_MAX_ATTEMPTS=3
readonly SELFTEST_CONTROL_REPO="home-assistant/amd64-base"
readonly SELFTEST_ABSENT_TAG="0.0.0-gsd-selftest-absent"
readonly SELFTEST_ABSENT_REPO="home-assistant/amd64-base-gsd-selftest-absent"

# All four media types must be offered. An index-only Accept header 404s a
# single-arch image that is genuinely present, which would report a healthy
# add-on as broken.
readonly OCI_ACCEPT="application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"

# probe_manifest communicates through these rather than stdout, so a probe can
# never accidentally inject a line into output whose shape the acceptance gates
# assert on.
PROBE_RESULT=""
PROBE_DETAIL=""
PROBE_TMP=""

cleanup() {
    if [ -n "$PROBE_TMP" ] && [ -f "$PROBE_TMP" ]; then
        rm -f "$PROBE_TMP"
    fi
    return 0
}
trap cleanup EXIT

usage() {
    cat <<'USAGE'
Verify that every advertised add-on image is anonymously pullable from ghcr.io
at the exact version its config.yaml declares.

Usage:
  verify-image-availability.sh [options]

Modes:
  --self-test                 Prove the ghcr probe in all three directions (ok,
                              missing, denied) against a third-party control
                              image. Exits 0 only if all three classify
                              correctly, 2 otherwise.
  --probe TEMPLATE            Probe a single image reference. Requires
                              --probe-version. TEMPLATE may contain the {arch}
                              placeholder.
  --probe-version VERSION     The OCI tag to ask for in --probe mode.
  --probe-arch ARCH           Arch substituted into TEMPLATE (default: amd64).
  -h, --help                  Show this help and exit 0.

Exit codes:
  0  invariant holds
  1  violation (missing / denied manifest, or an uninterpretable config.yaml)
  2  guard could not run reliably (shallow clone, network, failed self-test,
     bad argument)
USAGE
}

# Under GitHub Actions a violation must also become an annotation. Locally that
# would just be noise, so it is gated on the variable being set and non-empty.
emit_error_annotation() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        printf '::error::%s\n' "$1"
    fi
}

# The ONE shared violation-reporting path. Every mode that can report a
# violation goes through here, so the annotation channel is never silently
# dropped by a mode that grew its own reporting.
report_violation() {
    printf '%s %s\n' "$GLYPH_FAIL" "$1"
    emit_error_annotation "$1"
}

# resolve_ref TEMPLATE ARCH -- substitute the arch placeholder. Parameter
# expansion, not an echo|sed pipeline: CI runs shellcheck with NO -e flags and
# SC2001 is excluded for workflow files only. A template with no placeholder is
# a legal single-arch HA image reference and is used verbatim.
resolve_ref() {
    local template="$1"
    local arch="$2"
    printf '%s\n' "${template//\{arch\}/$arch}"
}

# A config.yaml value flows straight into a curl URL, so validate before
# requesting. Anchored allowlist: a stray @, ?, ; or whitespace must be refused,
# not requested.
is_valid_ref() {
    local ref="$1"
    [[ "$ref" =~ ^ghcr\.io/[A-Za-z0-9._/-]+$ ]]
}

# probe_manifest REPO_PATH TAG -- REPO_PATH is the image reference with the
# leading ghcr.io/ stripped. Sets PROBE_RESULT to one of
# ok / missing / denied / inconclusive, and PROBE_DETAIL to a human-readable
# reason. Always returns 0; the caller branches on PROBE_RESULT.
#
# The bearer token is never echoed, never written to a summary, and no shell
# tracing is enabled anywhere in this file: on a public repo the Actions log is
# world-readable.
probe_manifest() {
    local repo_path="$1"
    local tag="$2"
    local attempt=0
    local token_code token_body token manifest_code

    PROBE_RESULT="inconclusive"
    PROBE_DETAIL="no attempt completed"

    if [ -z "$PROBE_TMP" ]; then
        PROBE_TMP=$(mktemp)
    fi

    while [ "$attempt" -lt "$PROBE_MAX_ATTEMPTS" ]; do
        attempt=$((attempt + 1))

        # Anonymous pull token. curl is invoked WITHOUT follow-redirects, for
        # the reason notify-ha.sh:38-41 documents for this repo: following the
        # redirect fetches an auth-proxy page that answers 200, and the caller
        # reports success while nothing real was reached. The same hazard
        # applies to a hijacked or proxied registry host.
        token_code=$(curl -sS -o "$PROBE_TMP" -w '%{http_code}' \
            --connect-timeout 10 --max-time 30 \
            "https://ghcr.io/token?scope=repository:${repo_path}:pull&service=ghcr.io" \
            2>/dev/null) || token_code="000"
        token_body=$(cat "$PROBE_TMP" 2>/dev/null) || token_body=""

        if [ "$token_code" = "401" ] || [ "$token_code" = "403" ]; then
            PROBE_RESULT="denied"
            PROBE_DETAIL="ghcr refused an anonymous pull token (HTTP ${token_code}); the package is not anonymously pullable, and ghcr does not tell an anonymous caller whether it is missing or private"
            return 0
        fi

        if is_retryable "$token_code"; then
            PROBE_DETAIL="ghcr token endpoint returned HTTP ${token_code} (attempt ${attempt}/${PROBE_MAX_ATTEMPTS})"
            PROBE_RESULT="inconclusive"
            backoff "$attempt"
            continue
        fi

        # Field-order independent, no JSON parser needed. The pattern requires a
        # literal double quote immediately before the key, so an
        # "access_token" field cannot false-match. A non-matching grep aborts
        # the script under `set -euo pipefail`, hence the trailing fallback.
        token=$(printf '%s' "$token_body" | grep -o '"token":"[^"]*"' | cut -d'"' -f4) || token=""

        if [ -z "$token" ]; then
            PROBE_RESULT="denied"
            PROBE_DETAIL="ghcr issued no anonymous pull token (token endpoint HTTP ${token_code}); the package is not anonymously pullable, and ghcr does not tell an anonymous caller whether it is missing or private"
            return 0
        fi

        manifest_code=$(curl -sS -o /dev/null -w '%{http_code}' \
            --connect-timeout 10 --max-time 30 \
            -H "Authorization: Bearer ${token}" \
            -H "Accept: ${OCI_ACCEPT}" \
            "https://ghcr.io/v2/${repo_path}/manifests/${tag}" \
            2>/dev/null) || manifest_code="000"

        case "$manifest_code" in
            200)
                PROBE_RESULT="ok"
                PROBE_DETAIL="manifest present (HTTP 200)"
                return 0
                ;;
            404)
                PROBE_RESULT="missing"
                PROBE_DETAIL="no manifest at this tag (HTTP 404); this version was never published to the registry"
                return 0
                ;;
            401 | 403)
                PROBE_RESULT="denied"
                PROBE_DETAIL="ghcr refused the manifest to an anonymous caller (HTTP ${manifest_code}); ghcr does not tell an anonymous caller whether the package is missing or private"
                return 0
                ;;
        esac

        # A 404 and a 403 are answers, not blips, and are handled above without
        # a retry. Only transport failures, 5xx and 429 reach here.
        PROBE_RESULT="inconclusive"
        PROBE_DETAIL="ghcr manifest endpoint returned HTTP ${manifest_code} (attempt ${attempt}/${PROBE_MAX_ATTEMPTS})"
        backoff "$attempt"
    done

    return 0
}

# Retry only on transport failure, 5xx or 429.
is_retryable() {
    local code="$1"
    if [ "$code" = "000" ] || [ "$code" = "429" ]; then
        return 0
    fi
    if [ "${code:0:1}" = "5" ]; then
        return 0
    fi
    return 1
}

# Exponential backoff, 1s/2s/4s as notify-ha.sh:32-36 documents; only the first
# PROBE_MAX_ATTEMPTS-1 delays are ever used.
backoff() {
    local attempt="$1"
    if [ "$attempt" -lt "$PROBE_MAX_ATTEMPTS" ]; then
        sleep $((2 ** (attempt - 1)))
    fi
    return 0
}

# probe_ref REF TAG -- validate, probe, and report a single fully resolved
# reference. Sets PROBE_RESULT. Returns 0 when the reference was probeable,
# 1 when it was refused as uninterpretable.
probe_ref() {
    local ref="$1"
    local tag="$2"

    if ! is_valid_ref "$ref"; then
        report_violation "uninterpretable image reference '${ref}': expected a plain ghcr.io/<path> value made of [A-Za-z0-9._/-]"
        return 1
    fi

    probe_manifest "${ref#ghcr.io/}" "$tag"
    return 0
}

# --self-test: prove the classifier in ALL THREE directions against
# ghcr.io/home-assistant/{arch}-base -- a third-party control image that is
# public, permanent, and already a build_from dependency of every add-on here,
# so the self-test never depends on this repo's own possibly-broken packages.
#
# This exists because the repo is GREEN: no scheduled run will walk a violation
# path, so a passing scan proves nothing on its own. It is only meaningful
# because the classifier was just proven to distinguish all three states.
self_test_direction() {
    local repo_path="$1"
    local tag="$2"
    local want="$3"

    probe_manifest "$repo_path" "$tag"

    if [ "$PROBE_RESULT" = "$want" ]; then
        printf '%s %s\n' "$GLYPH_PASS" "self-test: ghcr.io/${repo_path}:${tag} classified '${want}' as expected"
        return 0
    fi

    report_violation "self-test: ghcr.io/${repo_path}:${tag} classified '${PROBE_RESULT}' but '${want}' was expected (${PROBE_DETAIL})"
    return 1
}

run_self_test() {
    local failed=0

    printf '%s\n' "🔍 Self-testing the ghcr probe in all three directions against a third-party control image..."

    if ! self_test_direction "$SELFTEST_CONTROL_REPO" "latest" "ok"; then
        failed=1
    fi
    if ! self_test_direction "$SELFTEST_CONTROL_REPO" "$SELFTEST_ABSENT_TAG" "missing"; then
        failed=1
    fi
    if ! self_test_direction "$SELFTEST_ABSENT_REPO" "latest" "denied"; then
        failed=1
    fi

    if [ "$failed" -ne 0 ]; then
        printf '%s %s\n' "$GLYPH_AGG_FAIL" "self-test failed — the probe cannot classify ghcr responses correctly, so it cannot be trusted to guard anything. Not reporting on any add-on."
        return 2
    fi

    printf '%s %s\n' "$GLYPH_AGG_OK" "self-test passed: ok, missing and denied are each detected correctly."
    return 0
}

run_probe() {
    local template="$1"
    local version="$2"
    local arch="$3"
    local ref

    ref=$(resolve_ref "$template" "$arch")

    if ! probe_ref "$ref" "$version"; then
        return 1
    fi

    case "$PROBE_RESULT" in
        ok)
            printf '%s %s\n' "$GLYPH_PASS" "${ref}:${version} is anonymously pullable (${PROBE_DETAIL})"
            return 0
            ;;
        missing)
            report_violation "${ref}:${version} has no anonymously-pullable manifest — ${PROBE_DETAIL}"
            printf '   %s\n' "Remediation: re-run the add-on's build workflow, or push the <addon>/v<version> tag that triggers it."
            return 1
            ;;
        denied)
            report_violation "${ref}:${version} is not anonymously pullable — ${PROBE_DETAIL}"
            printf '   %s\n' "Remediation: ghcr does not distinguish missing from private for anonymous callers, so check BOTH that the package exists and that its visibility is public."
            return 1
            ;;
        *)
            printf '%s %s\n' "$GLYPH_WARN" "${ref}:${version} could not be classified — ${PROBE_DETAIL}"
            printf '%s %s\n' "$GLYPH_AGG_FAIL" "guard could not run reliably; this is NOT a report that the add-on is broken."
            return 2
            ;;
    esac
}

main() {
    local mode=""
    local probe_template=""
    local probe_version=""
    local probe_arch="amd64"
    local rc

    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h | --help)
                usage
                return 0
                ;;
            --self-test)
                mode="self-test"
                shift
                ;;
            --probe)
                mode="probe"
                if [ "$#" -lt 2 ]; then
                    printf '%s\n' "--probe requires an image reference template" >&2
                    usage >&2
                    return 2
                fi
                probe_template="$2"
                shift 2
                ;;
            --probe-version)
                if [ "$#" -lt 2 ]; then
                    printf '%s\n' "--probe-version requires a value" >&2
                    usage >&2
                    return 2
                fi
                probe_version="$2"
                shift 2
                ;;
            --probe-arch)
                if [ "$#" -lt 2 ]; then
                    printf '%s\n' "--probe-arch requires a value" >&2
                    usage >&2
                    return 2
                fi
                probe_arch="$2"
                shift 2
                ;;
            *)
                printf '%s\n' "unrecognised argument: $1" >&2
                usage >&2
                return 2
                ;;
        esac
    done

    case "$mode" in
        self-test)
            rc=0
            run_self_test || rc=$?
            return "$rc"
            ;;
        probe)
            if [ -z "$probe_version" ]; then
                printf '%s\n' "--probe requires --probe-version" >&2
                usage >&2
                return 2
            fi
            rc=0
            run_probe "$probe_template" "$probe_version" "$probe_arch" || rc=$?
            return "$rc"
            ;;
        *)
            printf '%s\n' "no mode selected" >&2
            usage >&2
            return 2
            ;;
    esac
}

main "$@"
