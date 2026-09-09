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
# WHERE THE REGISTRY PATH COMES FROM
# ----------------------------------
# From the `image:` VALUE in config.yaml, never from the directory name
# re-slugged (`-` -> `_`, the way _build-template.yml:107 derives it at build
# time). A re-derived slug would silently AGREE with a typo'd `image:` key and
# so mask exactly the bug that breaks the pull. The tag likewise comes from the
# `version:` VALUE — the same string _build-template.yml:78 reads as
# CONFIG_VERSION and pushes as the OCI tag at _build-template.yml:168, subpatch
# suffix included, and the same string the Supervisor asks ghcr for.
#
# THE TWO ANTI-SILENT-PASS SAFEGUARDS
# -----------------------------------
# SAFEGUARD 1 — a shallow clone is REFUSED (exit 2) on any path that consults
# git history. In a `--depth 1` clone the single grafted commit has no parent,
# so it appears to have introduced every string in the tree, and the
# `git log -S` grace lookup returns the HEAD commit's date for EVERY add-on.
# Measured in this repo: all 7 image-declaring add-ons reported the SAME
# 42-minute age, inside the default 45-minute window, so every one was
# grace-skipped and the guard exited 0 having probed NOTHING. That is worse
# than "finds nothing" because it is time-dependent: re-measured against a
# 63-minute-old HEAD the silent pass did not occur. Identical input, identical
# code, opposite verdict, decided only by the clock — and the failure mode is a
# GREEN check, which is the kind that teaches you to trust it. The refusal is
# therefore deterministic rather than left to Safeguard 2, which only fires in
# the first of those two measurements. This is the guard's own version of the
# bug it exists to catch.
#
# SAFEGUARD 2 — `passes == 0 && skips > 0` prints the warning glyph and says
# plainly that nothing was verified. Exit code stays 0 (the invariant is not
# violated) but the run must not look green-and-clean.
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
# --dry-run FIXTURE (the parser regression test)
# ----------------------------------------------
# `--dry-run` makes no network call, reads no git history, and applies NO grace
# window, so this output is reproducible even immediately after a version bump.
# Expected output as of 2026-09-09 — exactly 8 lines, one per declared
# image/arch pair (versions move, the SHAPE does not):
#
#   · coding-assistants ghcr.io/akentner/homeassistant-addons/amd64-coding_assistants:1.0.0-2
#   · coding-assistants ghcr.io/akentner/homeassistant-addons/aarch64-coding_assistants:1.0.0-2
#   · gatus ghcr.io/akentner/homeassistant-addons/amd64-gatus:5.36.0-11
#   · markdown-renderer ghcr.io/akentner/homeassistant-addons/amd64-markdown_renderer:1.1.0-23
#   · meridian ghcr.io/akentner/homeassistant-addons/amd64-meridian:1.68.0-0
#   · network-tools ghcr.io/akentner/homeassistant-addons/amd64-network_tools:0.5.0-1
#   · phone-logger ghcr.io/akentner/homeassistant-addons/amd64-phone_logger:1.0.6-0
#   · terraform-bridge ghcr.io/akentner/homeassistant-addons/amd64-terraform_bridge:0.3.0-0
#
# What each line of that fixture pins down:
#   - `gatus` and `meridian` yield ONLY amd64. Both carry four commented-out
#     arch entries (`# - aarch64`, `# - armhf`, `# - armv7`, `# - i386`) which
#     are inert and must never be probed.
#   - `network-tools` resolves despite indenting its `arch:` list with FOUR
#     spaces (network-tools/config.yaml:9-10), not two.
#   - `coding-assistants` yields TWO lines, one per active arch.
#   - `authentik`, `iac-runner` and `tools/test-addon` yield NOTHING: they
#     declare no top-level `image:` key, so the Supervisor builds them locally
#     and never pulls them. They are skipped by the image-key rule itself, so
#     there is no allowlist that can go stale.
#
# USAGE
#   ./internal/verify-image-availability.sh
#   ./internal/verify-image-availability.sh --dry-run
#   ./internal/verify-image-availability.sh --self-test
#   ./internal/verify-image-availability.sh --addon gatus --grace-minutes 0
#   ./internal/verify-image-availability.sh --probe TEMPLATE --probe-version V [--probe-arch A]
#   ./internal/verify-image-availability.sh --help

set -euo pipefail

# Output vocabulary, matching internal/check-version-tags.sh exactly so both
# guards read alike. Every status line puts its glyph at column 1 followed by a
# single space; acceptance gates count glyphs anchored at column 1, so an
# indented status line reads as a missing one.
readonly GLYPH_PASS="✓"
readonly GLYPH_SKIP="⊘"
readonly GLYPH_FAIL="❌"
readonly GLYPH_WARN="⚠️"
readonly GLYPH_AGG_FAIL="🚫"
readonly GLYPH_AGG_OK="✅"
readonly GLYPH_DRY="·"

readonly PROBE_MAX_ATTEMPTS=3

# Default grace window. The measured worst-case build in this repo is 13m28s
# for aarch64 under QEMU, plus queue time. The false-alarm defence is NOT the
# cron schedule — humans push bumps at arbitrary times — it is a window dated
# from git history, per add-on.
readonly DEFAULT_GRACE_MINUTES=45

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

With no mode flag, scans every add-on in the repository.

Modes:
  --dry-run                   Resolve and print every declared image/arch pair
                              without any network call, git-history read, or
                              grace window. The parser regression check.
  --self-test                 Prove the ghcr probe in all three directions (ok,
                              missing, denied) against a third-party control
                              image. Exits 0 only if all three classify
                              correctly, 2 otherwise.
  --probe TEMPLATE            Probe a single image reference. Requires
                              --probe-version. TEMPLATE may contain the {arch}
                              placeholder.
  --probe-version VERSION     The OCI tag to ask for in --probe mode.
  --probe-arch ARCH           Arch substituted into TEMPLATE (default: amd64).

Scan options:
  --addon NAME                Restrict the scan to one add-on directory. An
                              unknown name exits 2, so a typo cannot look like
                              a clean run.
  --grace-minutes N           Skip an add-on whose current version string
                              landed less than N minutes ago (default: 45).
                              0 disables the window entirely.
  --summary-file PATH         Append a markdown summary suitable for
                              $GITHUB_STEP_SUMMARY.
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
# violation goes through here — --probe, --self-test and the full scan alike —
# so the annotation channel is never silently dropped by a mode that grew its
# own reporting. That matters because this guard mandates TWO failure channels
# (these annotations, and the workflow's if: failure() notify step), and the
# repo is green, so no scheduled run will ever walk the scan's violation path.
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

template_has_arch_placeholder() {
    case "$1" in
        *"{arch}"*) return 0 ;;
        *) return 1 ;;
    esac
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
            PROBE_RESULT="inconclusive"
            PROBE_DETAIL="ghcr token endpoint returned HTTP ${token_code} (attempt ${attempt}/${PROBE_MAX_ATTEMPTS})"
            backoff "$attempt"
            continue
        fi

        # Field-order independent, no JSON parser needed. The pattern requires a
        # literal double quote immediately before the key, so an
        # "access_token" field cannot false-match. A non-matching grep aborts
        # the script under `set -euo pipefail`, hence the trailing fallback —
        # which every grep/cut pipeline assignment in this file needs.
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

remediation_missing() {
    local addon="$1"
    local version="$2"
    printf '   %s\n' "The image was never published at this tag. Re-run the ${addon} build workflow, or push the"
    printf '   %s\n' "release tag that triggers it:  make release ADDON=${addon} VERSION=${version}"
}

remediation_denied() {
    printf '   %s\n' "ghcr does not distinguish a missing package from a private one for anonymous callers, so"
    printf '   %s\n' "BOTH need checking: that the package exists at all, and that its visibility is public."
    printf '   %s\n' "The Supervisor pulls with no credentials, so a private package is as broken as a missing one."
}

# ---------------------------------------------------------------------------
# config.yaml parsing
#
# grep/sed/awk only. The YAML query CLI is unusable here for two independent
# reasons documented in check-version-tags.sh's `image:` grep justification:
# HA config.yaml files
# carry custom tags that require its unsafe mode, and the build installed on
# this host has no eval subcommand at all.
# ---------------------------------------------------------------------------

# Anchored at column 1 and requiring a non-blank value, so an indented sub-key,
# a commented-out line, or an empty value cannot satisfy it. `image` is a
# top-level key in the HA add-on manifest, so the anchor is exact.
parse_image() {
    local cfg="$1"
    grep -E '^image:[[:space:]]*[^[:space:]]' "$cfg" | head -1 \
        | sed -E "s/^image:[[:space:]]*//; s/[[:space:]]+\$//; s/^[\"']//; s/[\"']\$//" || true
}

# Anchored at column 1, tolerant of quoted and unquoted values, head -1.
parse_version() {
    local cfg="$1"
    grep -E '^version:[[:space:]]*[^[:space:]]' "$cfg" | head -1 \
        | sed -E "s/^version:[[:space:]]*//; s/[[:space:]]+\$//; s/^[\"']//; s/[\"']\$//" || true
}

# parse_archs handles the three shapes present in / possible for this repo:
#   (a) block form, 2-space indent (7 add-ons)
#   (b) block form, 4-space indent (network-tools/config.yaml:9-10)
#   (c) inline flow form, `arch: [amd64, aarch64]`
#
# In the block form a line matching ^arch: with only optional whitespace after
# the colon opens the block; leading-whitespace + `-` + a bare token is an
# entry; a line starting at column 1 with a character that is neither
# whitespace nor a comment marker ends the block. An indented commented-out
# entry never matches the entry pattern because the character after the indent
# is the comment marker, not `-` — which is why gatus and meridian yield ONLY
# amd64 despite their four inert arch lines.
parse_archs() {
    local cfg="$1"
    local inline inner

    inline=$(grep -E '^arch:[[:space:]]*\[' "$cfg" | head -1) || inline=""
    if [ -n "$inline" ]; then
        inner=${inline#*[}
        inner=${inner%%]*}
        printf '%s\n' "$inner" | tr ',' '\n' | sed -E 's/[^A-Za-z0-9._-]//g' | grep -v '^$' || true
        return 0
    fi

    awk '
        /^arch:[ \t]*$/ { inblock = 1; next }
        inblock == 1 {
            if ($0 ~ /^[^ \t#]/) { inblock = 0; next }
            if ($0 ~ /^[ \t]+-[ \t]*[^ \t#-]/) {
                entry = $0
                sub(/^[ \t]+-[ \t]*/, "", entry)
                gsub(/[^A-Za-z0-9._-]/, "", entry)
                if (entry != "") { print entry }
            }
        }
    ' "$cfg"
}

# Every config.yaml at depth 2 or 3 from the repo root. Depth 3 is required for
# tools/test-addon/config.yaml — the same reasoning validate-versions.sh:83-88
# records. The live HA `config/` directory is pruned, as is `.claude/`, which
# holds full working-tree copies in agent worktrees. Sorted, so output order is
# stable run to run.
discover_addons() {
    find . -mindepth 2 -maxdepth 3 \
        \( -path './.git' -o -path './config' -o -path './node_modules' -o -path './.claude' \) -prune -o \
        -type f -name config.yaml -print 2>/dev/null \
        | sed -E 's#^\./##; s#/config\.yaml$##' \
        | sort
}

repo_root() {
    local root
    root=$(git rev-parse --show-toplevel 2>/dev/null) || root=""
    if [ -z "$root" ]; then
        root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
    fi
    printf '%s\n' "$root"
}

# Age in minutes of the commit that introduced the add-on's CURRENT version
# string. Prints -1 when no such commit can be found, which deliberately reads
# as "old enough to probe": the safe direction is to check, not to skip.
version_age_minutes() {
    local addon="$1"
    local version="$2"
    local ts now

    ts=$(git log -1 --format=%ct -S"$version" -- "$addon/config.yaml" 2>/dev/null) || ts=""
    if [ -z "$ts" ]; then
        printf '%s\n' "-1"
        return 0
    fi

    now=$(date +%s)
    printf '%s\n' "$(( (now - ts) / 60 ))"
}

# SAFEGUARD 1. Scoped to the paths that actually consult git history — the bare
# scan, --addon, --grace-minutes, --summary-file. NOT --help, --dry-run,
# --self-test or --probe: none of those reads the history, and a --help that
# exited 2 in a shallow checkout would be plainly wrong. See the header for the
# measured mechanism.
require_full_history() {
    local shallow
    shallow=$(git rev-parse --is-shallow-repository 2>/dev/null) || shallow="unknown"

    if [ "$shallow" != "true" ]; then
        return 0
    fi

    printf '%s %s\n' "$GLYPH_AGG_FAIL" "refusing to run: this is a shallow clone, so the per-add-on grace window cannot be evaluated."
    printf '   %s\n' "In a depth-1 clone the single grafted commit has no parent, so it appears to have introduced"
    printf '   %s\n' "every string in the tree: the 'git log -S' grace lookup then returns the HEAD commit's date for"
    printf '   %s\n' "EVERY add-on. While HEAD is younger than the grace window that grace-skips all of them and the"
    printf '   %s\n' "guard exits 0 having probed nothing at all — a green check that verified nothing."
    printf '   %s\n' "Fix: check out with full history (actions/checkout with fetch-depth: 0), or run --dry-run,"
    printf '   %s\n' "--self-test or --probe, none of which reads git history."
    return 2
}

summary_init() {
    local file="$1"
    if [ -z "$file" ]; then
        return 0
    fi
    # Appended, not truncated: $GITHUB_STEP_SUMMARY is shared with other steps.
    {
        printf '%s\n' "## Add-on image availability (anonymous ghcr.io pull)"
        printf '\n'
        printf '%s\n' "| add-on | reference | verdict |"
        printf '%s\n' "| ------ | --------- | ------- |"
    } >> "$file"
    return 0
}

# No bearer token ever reaches the summary: only the add-on name, the reference
# and the verdict are written.
summary_row() {
    local file="$1"
    if [ -z "$file" ]; then
        return 0
    fi
    printf '| %s | %s | %s |\n' "$2" "$3" "$4" >> "$file"
    return 0
}

summary_footer() {
    local file="$1"
    if [ -z "$file" ]; then
        return 0
    fi
    {
        printf '\n'
        printf '%s\n' "$2"
    } >> "$file"
    return 0
}

# --dry-run: resolve and print one line per declared image/arch pair. No network
# call, no git-history read, and NO grace window — every declared pair is
# printed regardless of how recently its version string landed, which is what
# keeps the 8-line fixture in the header reproducible immediately after a bump,
# and why this mode is exempt from Safeguard 1. Nothing else is printed: no
# header, no aggregate, no skip lines.
run_dry_run() {
    local root addon cfg image version arch ref
    local addons=()
    local archs=()

    root=$(repo_root)
    cd "$root" || return 2

    mapfile -t addons < <(discover_addons)

    for addon in ${addons[@]+"${addons[@]}"}; do
        cfg="$addon/config.yaml"
        image=$(parse_image "$cfg")
        if [ -z "$image" ]; then
            continue
        fi

        version=$(parse_version "$cfg")
        if [ -z "$version" ]; then
            continue
        fi

        archs=()
        mapfile -t archs < <(parse_archs "$cfg")

        if ! template_has_arch_placeholder "$image"; then
            printf '%s %s %s\n' "$GLYPH_DRY" "$addon" "${image}:${version}"
            continue
        fi

        for arch in ${archs[@]+"${archs[@]}"}; do
            ref=$(resolve_ref "$image" "$arch")
            printf '%s %s %s\n' "$GLYPH_DRY" "$addon" "${ref}:${version}"
        done
    done

    return 0
}

run_scan() {
    local only_addon="$1"
    local grace_minutes="$2"
    local summary_file="$3"
    local root addon cfg image version arch ref age
    local addons=()
    local archs=()
    local probe_archs=()
    local passes=0
    local skips=0
    local violations=0
    local inconclusives=0
    local found=0
    local rc=0

    root=$(repo_root)
    cd "$root" || return 2

    # SAFEGUARD 1 — before any config parsing or network call on this path.
    if ! require_full_history; then
        return 2
    fi

    mapfile -t addons < <(discover_addons)

    if [ -n "$only_addon" ]; then
        for addon in ${addons[@]+"${addons[@]}"}; do
            if [ "$addon" = "$only_addon" ]; then
                found=1
            fi
        done
        if [ "$found" -eq 0 ]; then
            printf '%s\n' "unknown add-on '${only_addon}': no such add-on directory with a config.yaml" >&2
            return 2
        fi
    fi

    printf '%s\n' "🔍 Verifying that every advertised add-on image is anonymously pullable from ghcr.io..."
    summary_init "$summary_file"

    for addon in ${addons[@]+"${addons[@]}"}; do
        if [ -n "$only_addon" ] && [ "$addon" != "$only_addon" ]; then
            continue
        fi

        cfg="$addon/config.yaml"
        image=$(parse_image "$cfg")

        if [ -z "$image" ]; then
            printf '%s %s\n' "$GLYPH_SKIP" "${addon}: no top-level 'image:' key — the Supervisor builds this add-on locally and never pulls it, so there is no manifest to verify"
            skips=$((skips + 1))
            summary_row "$summary_file" "$addon" "_(built locally by the Supervisor)_" "skipped"
            continue
        fi

        version=$(parse_version "$cfg")
        if [ -z "$version" ]; then
            report_violation "${addon}: declares image '${image}' but has no parseable top-level 'version:' key — this config.yaml cannot be interpreted, so the tag the Supervisor would pull is unknown"
            violations=$((violations + 1))
            summary_row "$summary_file" "$addon" "$image" "uninterpretable config.yaml"
            continue
        fi

        archs=()
        mapfile -t archs < <(parse_archs "$cfg")

        # `image:` present AND the parsed arch list empty. Never "arch list
        # empty" alone — that is also true of the add-ons with no `image:` key,
        # which must skip and are handled above.
        if [ "${#archs[@]}" -eq 0 ]; then
            report_violation "${addon}: declares image '${image}' but its 'arch:' list has no active entries — it advertises a pulled image that no host architecture can ever pull, so its store entry is unusable"
            violations=$((violations + 1))
            summary_row "$summary_file" "$addon" "$image" "no active arch"
            continue
        fi

        if [ "$grace_minutes" -gt 0 ]; then
            age=$(version_age_minutes "$addon" "$version")
            if [ "$age" -ge 0 ] && [ "$age" -lt "$grace_minutes" ]; then
                printf '%s %s\n' "$GLYPH_SKIP" "${addon}: version '${version}' landed ${age} minute(s) ago, inside the ${grace_minutes}-minute grace window — the build that publishes its image may still be running"
                skips=$((skips + 1))
                summary_row "$summary_file" "$addon" "${image}:${version}" "skipped (${age}m old, grace ${grace_minutes}m)"
                continue
            fi
        fi

        probe_archs=()
        if template_has_arch_placeholder "$image"; then
            probe_archs=("${archs[@]}")
        else
            # A template without the placeholder is a legal single-arch HA image
            # reference: probe it once, not once per declared arch.
            probe_archs=("${archs[0]}")
        fi

        for arch in "${probe_archs[@]}"; do
            ref=$(resolve_ref "$image" "$arch")

            if ! probe_ref "$ref" "$version"; then
                violations=$((violations + 1))
                summary_row "$summary_file" "$addon" "$ref" "uninterpretable reference"
                continue
            fi

            case "$PROBE_RESULT" in
                ok)
                    printf '%s %s\n' "$GLYPH_PASS" "${addon} ${ref}:${version} is anonymously pullable"
                    passes=$((passes + 1))
                    summary_row "$summary_file" "$addon" "\`${ref}:${version}\`" "ok"
                    ;;
                missing)
                    report_violation "${addon} ${ref}:${version} has no anonymously-pullable manifest — ${PROBE_DETAIL}"
                    remediation_missing "$addon" "$version"
                    violations=$((violations + 1))
                    summary_row "$summary_file" "$addon" "\`${ref}:${version}\`" "MISSING (404)"
                    ;;
                denied)
                    report_violation "${addon} ${ref}:${version} is not anonymously pullable — ${PROBE_DETAIL}"
                    remediation_denied
                    violations=$((violations + 1))
                    summary_row "$summary_file" "$addon" "\`${ref}:${version}\`" "DENIED (missing or private)"
                    ;;
                *)
                    printf '%s %s\n' "$GLYPH_WARN" "${addon} ${ref}:${version} could not be classified — ${PROBE_DETAIL}"
                    inconclusives=$((inconclusives + 1))
                    summary_row "$summary_file" "$addon" "\`${ref}:${version}\`" "inconclusive"
                    ;;
            esac
        done
    done

    local aggregate
    if [ "$violations" -gt 0 ]; then
        aggregate="${GLYPH_AGG_FAIL} image-availability check FAILED: ${violations} declared image/arch pair(s) are not anonymously pullable at the version config.yaml advertises. Affected add-ons are uninstallable and un-updatable from the store."
        rc=1
    elif [ "$inconclusives" -gt 0 ]; then
        aggregate="${GLYPH_AGG_FAIL} image-availability check could NOT be completed: ${inconclusives} pair(s) still undecided after ${PROBE_MAX_ATTEMPTS} attempts. This is NOT a report that any add-on is broken — the guard could not run reliably, and a guard that cannot run is not guarding."
        rc=2
    else
        aggregate="${GLYPH_AGG_OK} image-availability check passed: ${passes} declared image/arch pair(s) verified anonymously pullable, ${skips} skipped."
        rc=0
    fi
    printf '%s\n' "$aggregate"

    # SAFEGUARD 2 — the invariant is not violated, so the exit code stays as
    # computed above, but the run must not look green-and-clean when it
    # verified nothing at all.
    if [ "$passes" -eq 0 ] && [ "$skips" -gt 0 ]; then
        printf '%s %s\n' "$GLYPH_WARN" "no image was verified in this run: ${skips} add-on(s) were skipped and not a single manifest was probed. Whatever this run reported, it checked nothing."
    fi

    summary_footer "$summary_file" "$aggregate"
    return "$rc"
}

main() {
    local mode="scan"
    local probe_template=""
    local probe_version=""
    local probe_arch="amd64"
    local only_addon=""
    local summary_file=""
    local grace_minutes="$DEFAULT_GRACE_MINUTES"
    local rc

    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h | --help)
                usage
                return 0
                ;;
            --dry-run)
                mode="dry-run"
                shift
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
            --addon)
                if [ "$#" -lt 2 ]; then
                    printf '%s\n' "--addon requires an add-on directory name" >&2
                    usage >&2
                    return 2
                fi
                only_addon="$2"
                shift 2
                ;;
            --grace-minutes)
                if [ "$#" -lt 2 ]; then
                    printf '%s\n' "--grace-minutes requires a value" >&2
                    usage >&2
                    return 2
                fi
                if ! printf '%s' "$2" | grep -qE '^[0-9]+$'; then
                    printf '%s\n' "--grace-minutes must be a non-negative integer, got '$2'" >&2
                    return 2
                fi
                grace_minutes="$2"
                shift 2
                ;;
            --summary-file)
                if [ "$#" -lt 2 ]; then
                    printf '%s\n' "--summary-file requires a path" >&2
                    usage >&2
                    return 2
                fi
                summary_file="$2"
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
        dry-run)
            rc=0
            run_dry_run || rc=$?
            return "$rc"
            ;;
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
            rc=0
            run_scan "$only_addon" "$grace_minutes" "$summary_file" || rc=$?
            return "$rc"
            ;;
    esac
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
            remediation_missing "${ref##*/}" "$version"
            return 1
            ;;
        denied)
            report_violation "${ref}:${version} is not anonymously pullable — ${PROBE_DETAIL}"
            remediation_denied
            return 1
            ;;
        *)
            printf '%s %s\n' "$GLYPH_WARN" "${ref}:${version} could not be classified — ${PROBE_DETAIL}"
            printf '%s %s\n' "$GLYPH_AGG_FAIL" "guard could not run reliably; this is NOT a report that the add-on is broken."
            return 2
            ;;
    esac
}

main "$@"
