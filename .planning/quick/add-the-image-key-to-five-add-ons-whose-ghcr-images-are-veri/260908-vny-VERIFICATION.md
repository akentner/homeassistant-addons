---
phase: quick-260908-vny
verified: 2026-09-09T17:05:00Z
status: human_needed
score: 9/10 must-haves verified
covered_files:
  - .github/RELEASE.md
  - .planning/quick/add-the-image-key-to-five-add-ons-whose-ghcr-images-are-veri/260908-vny-PLAN.md
  - .planning/quick/add-the-image-key-to-five-add-ons-whose-ghcr-images-are-veri/260908-vny-SUMMARY.md
  - gatus/config.yaml
  - internal/check-version-tags.sh
  - markdown-renderer/config.yaml
  - meridian/config.yaml
  - phone-logger/config.yaml
  - terraform-bridge/config.yaml
covered_digest: "v1:sha256:eec4e20b82d2748395a169cc6442ee524bff8b0552a662bbe5be5ec2d157ae20"
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth: "The HA Supervisor pulls the prebuilt ghcr image for the five add-ons instead of rebuilding the Dockerfile locally."
    test: "On a live HA host, reload the add-on store and install or update one of the five (e.g. gatus 5.36.0-11 or terraform-bridge 0.3.0-0). Watch the Supervisor log."
    expected: "The log shows an image pull from ghcr.io/akentner/homeassistant-addons/amd64-<slug>:<version> and no local `docker build` / `Build image` step. Install/update completes."
    why_human: "This is a state transition on an external system (Supervisor build path -> pull path). Everything statically checkable is verified — key present, value correct, manifest anonymously pullable (HTTP 200), CI publish target identical — but no test in this repo exercises the Supervisor's own decision. Precedent evidence only: coding-assistants and network-tools already run this exact pattern in production."
human_verification:
  - test: "Install/update one of the five add-ons on a live HA host and read the Supervisor log."
    expected: "Image pulled from ghcr, no local build."
    why_human: "External service (HA Supervisor + ghcr) runtime behavior — see behavior_unverified_items."
  - test: "DECISION before the next `git push`: the pre-push hook now blocks the push because of markdown-renderer, not because of anything this item got wrong."
    expected: "Operator picks one: (a) `git tag -a markdown-renderer/v1.1.0-23 -m 'markdown-renderer: 1.1.0-23' && git push origin markdown-renderer/v1.1.0-23` then push the branch, or (b) `git push --no-verify`. Verified by running the hook against `origin/main..HEAD`: it prints `❌ markdown-renderer: no matching tag for version '1.1.0-23'` and exits 1. Root cause is pre-existing version/tag drift (only `markdown-renderer/v1.1.0-21` exists, and legacy `v1.1.0` never existed); this item merely put markdown-renderer into the hook's modified-add-on set by editing its config.yaml. The guard's underlying concern is not real here — the 1.1.0-23 image IS anonymously pullable (HTTP 200)."
    why_human: "Requires a judgment call about creating/pushing a release tag; a verifier must not push tags."
---

# Quick 260908-vny: Declare ghcr images for five add-ons — Verification Report

**Item Goal:** Add `image:` to five add-ons whose ghcr images are verified-public and version-matched so the HA
Supervisor pulls instead of rebuilding; drop `terraform-bridge` from `LOCAL_BUILD_ADDONS`; correct the now-false
`.github/RELEASE.md` 404 claim. No version bump anywhere.
**Verified:** 2026-09-09T17:05:00Z
**Status:** human_needed
**Re-verification:** No — initial verification
**Commits inspected:** `f8c3296`, `8ac7d6e`, `2c94feb` (range `a4a5d95..2c94feb`). `dc544d1` (authentik, sibling item
`260908-vnz`) sits on top of the range and was excluded from scope attribution.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                            | Status                         | Evidence                                                                                                                                                                                                                                                                        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | All five add-ons declare a top-level `image: ghcr.io/akentner/homeassistant-addons/{arch}-<slug>` with `<slug>` = dir name, hyphens → underscores | ✓ VERIFIED                     | `yaml.safe_load` of all five: `{arch}-gatus`, `{arch}-markdown_renderer`, `{arch}-phone_logger`, `{arch}-meridian`, `{arch}-terraform_bridge`. All at column 0, double-quoted, immediately before `url:` — the `coding-assistants/config.yaml:11` position. Diff shows +1 line per file, nothing else. |
| 2   | Every advertised `config.yaml` version resolves to an **anonymously** pullable GHCR manifest (HTTP 200) for the `amd64` arch these five build     | ✓ VERIFIED                     | Live probe, repo derived from the committed `image:` value (not hardcoded): gatus 5.36.0-11 → 200, markdown-renderer 1.1.0-23 → 200, phone-logger 1.0.6-0 → 200, meridian 1.66.0-0 → 200, terraform-bridge 0.3.0-0 → 200. Token fetched with no credentials; `curl` without `-n`/`-L`. All five `arch: [amd64]`, so no unpublished arch is advertised. |
| 3   | No version string changed in any `config.yaml`, `build.yaml` or `README.md` anywhere in the repo                                                   | ✓ VERIFIED                     | `git diff a4a5d95..2c94feb -- '*/config.yaml' '*/build.yaml' '*/README.md' README.md` filtered for version/badge/`vN.N` tokens → **NONE**. Over the wider `a4a5d95..HEAD` no `build.yaml` and no `README.md` is touched at all, and no `^[+-]version:` line exists in any config diff. `make validate-versions` re-prints the unchanged 3-file sets. |
| 4   | `LOCAL_BUILD_ADDONS` holds exactly one entry, `iac-runner`                                                                                        | ✓ VERIFIED                     | `internal/check-version-tags.sh:74-76` — array body is one element, `iac-runner`. Diff removes exactly the `terraform-bridge` line. No comment/marker inside the array region.                                                                                                    |
| 5   | `is_local_build` and the `image:`-key drift guard survive and still **enforce** the tag requirement for an allowlisted add-on that gains `image:`  | ✓ VERIFIED (behavioral)        | Static: helper at `:84-92`, guard at `:118-141`, warn branch has no `continue` so it falls through to enforcement. Behavioral (isolated scratch git repo, real repo untouched): allowlisted **without** key → `⊘ ... release tag not required`, exit 0; allowlisted **with** key → `⚠️ ... Enforcing the tag requirement despite the allowlist entry` **and** `❌ no matching tag`, exit **1**. |
| 6   | Rationale comment names `authentik` in the singular, states no numeric plural of other key-less add-ons, keeps the `260908-pfq-PLAN.md` pointer    | ✓ VERIFIED                     | `:64-70` — "authentik also lacks the key while publishing ghcr.io images via its build workflow"; pointer intact at `:69`; no numeric-plural phrase. Asserted against the derived set, not the prose: key-less add-ons = exactly `authentik iac-runner`, and `authentik/**` does have `build-authentik.yml`. |
| 7   | `.github/RELEASE.md` section assertions resolve real ATX headings with fenced code excluded (no fence-truncated slice)                              | ✓ VERIFIED                     | Verified by reading the committed file directly rather than trusting the plan's parser: `## Tag schema`, `### Why the split`, `### What this means operationally`, `## Standard release flow`, `## Manual repair` all present as real headings; the asserted content is physically inside each section.        |
| 8   | RELEASE.md states the ghcr-404 consequence only for `image:`-carrying add-ons and names the local-build failure mode separately                     | ✓ VERIFIED + factually true    | `RELEASE.md:80-93`: 404 bullet lists exactly the seven key-carrying add-ons; second bullet names `authentik` and `iac-runner` as locally built with "a missing ghcr tag cannot produce a pull 404 for them at all". The 404 warning is scoped, not deleted. New 4th column `Supervisor image source` classifies all nine rows and matches the derived key-less set exactly. Tag-trigger column re-derived from the nine workflow files: active only for iac-runner, network-tools, terraform-bridge — so "the six add-ons with the tag-trigger disabled" is arithmetically true. |
| 9   | `make validate-versions`, `make validate-addons` and `make lint` all exit 0                                                                        | ✓ VERIFIED                     | Run by the verifier, explicit exit codes: `validate-versions exit=0`, `validate-addons exit=0` (nine add-ons), `make lint` → 21/21 hooks Passed, `MAKE_LINT_EXIT=0` (includes both Docker-backed terraform-bridge hooks). Plus `shellcheck -e SC1091 -e SC2034` = 0, `bash -n` = 0, `validate-addon-config.py` = 0. `git status --untracked-files=no` after the lint run shows no new tracked-file drift. |
| 10  | (Item goal outcome) The HA Supervisor **pulls** these five instead of rebuilding locally                                                            | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Key present + value correct + manifest anonymously pullable + CI publish target identical (see key links). But the Supervisor's own build-vs-pull decision is a state transition on an external system that nothing in this repo exercises. Routed to human verification. |

**Score:** 9/10 truths verified · 1 present, behavior-unverified · **0 failed**

### Required Artifacts

| Artifact                       | Expected                                          | Status     | Details                                                                                                     |
| ------------------------------ | ------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| `gatus/config.yaml`            | `image:` key, version frozen at 5.36.0-11         | ✓ VERIFIED | line 12; +1 line diff only                                                                                  |
| `markdown-renderer/config.yaml`| `image:` key, version frozen at 1.1.0-23          | ✓ VERIFIED | line 8; +1 line diff only                                                                                   |
| `phone-logger/config.yaml`     | `image:` key, version frozen at 1.0.6-0           | ✓ VERIFIED | line 10; +1 line diff only                                                                                  |
| `meridian/config.yaml`         | `image:` key, version frozen at 1.66.0-0          | ✓ VERIFIED | line 12; +1 line diff only                                                                                  |
| `terraform-bridge/config.yaml` | `image:` key, version frozen at 0.3.0-0           | ✓ VERIFIED | line 8; +1 line diff only                                                                                   |
| `internal/check-version-tags.sh`| single-entry allowlist, helper + guard intact     | ✓ VERIFIED | -1 array line, -3/+3 comment lines; nothing else. Behaviorally exercised.                                   |
| `.github/RELEASE.md`           | 4-column table, scoped 404, single-entry allowlist| ✓ VERIFIED | +58/-21; both `LOCAL_BUILD_ADDONS` descriptions (`:137-140`, `:181-183`) name `iac-runner` and keep the "array is the source of truth" pointer. |
| `authentik/**`, `iac-runner/**`| untouched by this item                            | ✓ VERIFIED | Not in `git diff --name-only a4a5d95..2c94feb`. Neither gained an `image:` key. (`authentik/Dockerfile` + `run.sh` changed in the *later* sibling commit `dc544d1`, item `260908-vnz`.) |

### Key Link Verification

| From                                       | To                                              | Via                                                                                     | Status  | Details                                                                                                                                                                                                       |
| ------------------------------------------ | ----------------------------------------------- | --------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| five `config.yaml` `image:` values         | `.github/workflows/_build-template.yml` publish | `${IMAGE_BASE}/${matrix.arch}-${slug}:${CONFIG_VERSION}`                                | ✓ WIRED | `:151` `IMAGE_BASE: ghcr.io/akentner/homeassistant-addons`, `:107` slug = `addon-name \| tr '-' '_'`, `:168` tag = `CONFIG_VERSION` = `config.yaml`'s subpatch version (`:78`). Byte-identical to the committed keys. |
| `terraform-bridge` gaining `image:`        | its removal from `LOCAL_BUILD_ADDONS`           | same commit                                                                             | ✓ WIRED | Both land in `8ac7d6e`. No intermediate commit has the key while the allowlist still lists it, so the drift warning never had a push to fire on.                                                                |
| RELEASE.md `Supervisor image source` column| actual `image:` presence in the nine configs    | column lookup                                                                           | ✓ WIRED | Column re-derived from disk: `ghcr pull` rows = the seven with a key, `local build` rows = `authentik`, `iac-runner`. Exact match, zero drift.                                                                  |

### Behavioral Spot-Checks

| Behavior                                                     | Command                                                                       | Result                                                                       | Status |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------ |
| Anonymous ghcr manifest for each advertised version          | token fetch + `GET /v2/<repo>/manifests/<version>` (repo derived from the key) | 200 ×5                                                                        | ✓ PASS |
| Drift guard enforces when an allowlisted add-on gains `image:`| hook fed a synthetic pre-push ref line in an isolated scratch repo            | warn printed **and** `❌ no matching tag` **and** exit 1                      | ✓ PASS |
| Allowlist skip path still works for a key-less allowlisted add-on | same, without the `image:` line                                           | `⊘ ... release tag not required`, exit 0                                      | ✓ PASS |
| Hook against the real `origin/main..HEAD`                     | `printf 'refs/heads/main <HEAD> refs/heads/main <origin/main>' \| bash internal/check-version-tags.sh` | authentik ✓, gatus ✓, iac-runner ⊘, **markdown-renderer ❌**, meridian ✓, phone-logger ✓, terraform-bridge ✓ → exit 1 | ⚠️ see Warnings |
| `make lint` (21 hooks, incl. 2 real terraform-bridge builds) | `make lint`                                                                    | 21/21 Passed, exit 0                                                          | ✓ PASS |
| `make validate-versions` / `make validate-addons`            | both targets                                                                   | exit 0 / exit 0                                                               | ✓ PASS |
| `shellcheck -e SC1091 -e SC2034` + `bash -n`                 | on `internal/check-version-tags.sh`                                            | exit 0 / exit 0                                                               | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists in this repo and the plan declares none. Step 7c: SKIPPED (no probes declared or
discoverable). The pre-push hook dry-run above is the equivalent runnable check and was executed.

### Anti-Patterns Found

| File                             | Line | Pattern | Severity | Impact |
| -------------------------------- | ---- | ------- | -------- | ------ |
| —                                | —    | none    | —        | No `TBD`/`FIXME`/`XXX` and no `TODO`/`HACK`/`PLACEHOLDER` in any of the seven modified files. No stub, empty-return or hardcoded-empty pattern is applicable to a manifest key. |

### Warnings (not must-have violations)

1. **⚠️ The next `git push` is blocked by `markdown-renderer`, and this item is the proximate cause.** Editing
   `markdown-renderer/config.yaml` puts that add-on into the pre-push hook's modified set, and its advertised version
   `1.1.0-23` has no matching tag (`markdown-renderer/v1.1.0-21` is the newest; the legacy `v1.1.0` form never existed).
   Verified by running the hook: exit 1. This is **pre-existing version/tag drift**, not a defect introduced here, and
   the guard's actual concern is absent — the `1.1.0-23` image is anonymously pullable (HTTP 200). Escalated as a human
   decision, not a gap: creating and pushing a release tag is not a verifier action.
2. **ℹ️ `.git/hooks/pre-push` is a stale copy** — it still contains `terraform-bridge` in `LOCAL_BUILD_ADDONS` (dated
   before this item). `internal/check-version-tags.sh` is the tracked source of truth and is correct; run
   `./internal/setup-hooks.sh` to resync. Harmless today: the stale copy is only more permissive for terraform-bridge,
   and `terraform-bridge/v0.3.0-0` exists locally and on origin either way. Out of the item's stated scope.
3. **ℹ️ Known-stale claim confirmed still stale:** `.github/RELEASE.md:126` says "The seven callers carry the comment",
   but only six workflow files contain `# tag-trigger temporarily disabled` (authentik, coding-assistants, gatus,
   markdown-renderer, meridian, phone-logger — re-counted from disk). The plan explicitly recorded this as out of scope
   and a follow-up candidate; it is not a regression from this item.

### Requirements Coverage

No `requirements:` field in the plan frontmatter and no `.planning/REQUIREMENTS.md` mapping for a quick item. N/A.

### Deferred Items

None. This is a standalone quick-batch item, not part of a phased milestone with later phases that could absorb a gap.

### Human Verification Required

#### 1. Confirm the Supervisor actually pulls

**Test:** On a live HA host, reload the add-on store and install/update one of the five (gatus 5.36.0-11 or
terraform-bridge 0.3.0-0 are the cheapest). Watch the Supervisor log.
**Expected:** A pull of `ghcr.io/akentner/homeassistant-addons/amd64-<slug>:<version>` and **no** local build step;
install/update succeeds.
**Why human:** The build-vs-pull decision happens inside the Supervisor on an external host. Every statically checkable
precondition is verified (key present, value byte-identical to the CI publish target, manifest anonymously pullable),
and `coding-assistants` + `network-tools` already prove the pattern in production — but no test here exercises the
transition itself.

#### 2. Decide how to get past the pre-push hook

**Test:** Before pushing, choose either
`git tag -a markdown-renderer/v1.1.0-23 -m 'markdown-renderer: 1.1.0-23' && git push origin markdown-renderer/v1.1.0-23`
(closes the drift properly) or `git push --no-verify` (defers it).
**Expected:** Branch push completes. Note the ghcr image for `1.1.0-23` already exists, so no 404 risk either way.
**Why human:** Creating/pushing a release tag is an operator decision with remote side effects.

### Gaps Summary

No gaps. Every must-have in the plan frontmatter is verified against the codebase, and the two properties flagged as
most load-bearing both hold under independent re-derivation:

- **Registry safety:** all five advertised versions return HTTP 200 for an anonymous manifest fetch, with the repository
  path derived from the committed `image:` value rather than assumed, so none of the five can be bricked on pull.
- **Version freeze:** not one `version:`, `VERSION:` or README badge line moved anywhere in the repo across the item's
  three commits — no window where the store advertises an unbuilt version.

The allowlist change is correct and, unlike the SUMMARY's static claim, was verified *behaviorally*: the drift guard
still warns **and** enforces, and the skip path still skips. RELEASE.md's rewritten prose is factually true, not merely
edited — the new `Supervisor image source` column matches the on-disk key-less set exactly, the tag-trigger column
matches the nine workflow files, and the 404 consequence is scoped to the seven pulling add-ons with the local-build
failure mode stated separately for `authentik` and `iac-runner`.

Status is `human_needed` solely because the goal's end state (the Supervisor pulling) is observable only on a live HA
host, plus one escalated push decision that this item surfaced but did not cause.

---

_Verified: 2026-09-09T17:05:00Z_
_Verifier: Claude (gsd-verifier)_
