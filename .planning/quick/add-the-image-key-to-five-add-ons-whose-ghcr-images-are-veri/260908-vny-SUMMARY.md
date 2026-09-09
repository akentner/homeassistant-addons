---
quick_id: 260908-vny
phase: quick-260908-vny
plan: 01
subsystem: addon-manifests
tags: [ha-addon, ghcr, supervisor, pre-push-hook, release-docs]
status: complete
requires: []
provides:
  - "Five add-ons declare a top-level `image:` key, so the HA Supervisor pulls prebuilt ghcr images instead of rebuilding"
  - "`LOCAL_BUILD_ADDONS` is a single-entry allowlist (`iac-runner`) that again matches the key-less set minus authentik"
  - "`.github/RELEASE.md` classifies all nine add-ons by image source and scopes the ghcr-404 consequence correctly"
affects:
  - gatus/config.yaml
  - markdown-renderer/config.yaml
  - phone-logger/config.yaml
  - meridian/config.yaml
  - terraform-bridge/config.yaml
  - internal/check-version-tags.sh
  - .github/RELEASE.md
tech_stack:
  added: []
  patterns:
    - "`image: \"ghcr.io/akentner/homeassistant-addons/{arch}-<underscore_slug>\"` placed immediately before `url:` (coding-assistants position)"
key_files:
  created: []
  modified:
    - gatus/config.yaml
    - markdown-renderer/config.yaml
    - phone-logger/config.yaml
    - meridian/config.yaml
    - terraform-bridge/config.yaml
    - internal/check-version-tags.sh
    - .github/RELEASE.md
decisions:
  - "No version bump anywhere — every advertised `config.yaml` version already had an anonymously pullable ghcr manifest, so the commit's own build re-publishes an existing tag rather than opening a window where the store advertises a version whose image is still building."
  - "terraform-bridge's `image:` key and its removal from `LOCAL_BUILD_ADDONS` landed in one commit, so the pre-push drift guard never had a push to warn on."
metrics:
  duration: ~13 min
  completed: 2026-09-09
actuals:
  tokens: 5200
  tasks: 3
  commits: 3
plan_head_before: a4a5d95f905d1c74651227879753e6a77fd47472
---

# Quick 260908-vny: Declare ghcr images for five add-ons Summary

Five add-ons now carry a top-level `image:` key pointing at the ghcr repository their build workflows already publish, so
the HA Supervisor pulls instead of rebuilding — and the two places that encoded "built locally, never pulled"
(`LOCAL_BUILD_ADDONS` and `.github/RELEASE.md`'s 404 rationale) were corrected in the same run so neither now lies.

## What Was Built

**Task 1 — tracer on gatus alone** (`f8c3296`)

`gatus/config.yaml` gained `image: "ghcr.io/akentner/homeassistant-addons/{arch}-gatus"` at column 0, double-quoted,
immediately before `url:` (the `coding-assistants` position). The anonymous GHCR manifest probe for `5.36.0-11` returned
HTTP 200 before the commit, proving the insertion point and the registry invariant against one file before repeating the
edit four times.

**Task 2 — remaining four manifests + allowlist correction** (`8ac7d6e`)

- `markdown-renderer` → `{arch}-markdown_renderer`, `phone-logger` → `{arch}-phone_logger`,
  `meridian` → `{arch}-meridian`, `terraform-bridge` → `{arch}-terraform_bridge`. Same column, same quoting, same
  position.
- `internal/check-version-tags.sh`: `terraform-bridge` removed from `LOCAL_BUILD_ADDONS`, leaving `iac-runner` as the
  only member. `is_local_build` and the in-loop drift guard are untouched.
- The rationale comment above the array previously claimed "six other add-ons also lack the key while publishing ghcr.io
  images via their build workflows". After this change only `authentik` does, so the clause was rewritten to name
  `authentik` in the singular with its single build workflow and to state no count at all. The reasoning (inferring the
  rule from the key's absence would cement a missing-key bug behind a guard that stopped complaining) and the
  `260908-pfq-PLAN.md` pointer both survive; the removed add-on is named nowhere in the comment.

**Task 3 — RELEASE.md** (`2c94feb`)

- The "## Tag schema" split table gained a fourth `Supervisor image source` column: `ghcr pull` for coding-assistants,
  gatus, markdown-renderer, meridian, network-tools, phone-logger, terraform-bridge; `local build` for authentik and
  iac-runner. All nine rows and both original columns kept, bold markers on the three active tag triggers kept. A
  sentence under the table states that the column reports presence of a top-level `image:` key and that this axis is
  independent of the tag-trigger split to its left.
- "### Why the split" keeps both commit-quoted bullets verbatim (`287c79f`, `60e7835`) and gains a closing paragraph
  separating the historical CI tag-trigger decision from the pull-versus-local-build axis.
- "### What this means operationally" no longer asserts one consequence for all six tag-trigger-disabled add-ons. The
  true parts stay (a tag push alone builds nothing; step 2's push to `main` fires the build via `paths:`), then the
  consequence splits: the ghcr 404 is scoped to `image:`-carrying add-ons, and authentik + iac-runner are named as the
  two the Supervisor builds locally, whose failure mode is a local build against whatever `main` holds. The 404 warning
  is scoped, not softened. The closing network-tools / terraform-bridge / iac-runner double-build paragraph is unchanged.
- Both `LOCAL_BUILD_ADDONS` descriptions (release-flow step 2 and the closing paragraph of "## Manual repair") now name
  `iac-runner` as the sole member while keeping the pointer that the array in `internal/check-version-tags.sh` is the
  source of truth for current membership.

## Verification Results

| Gate                                                  | Result                                                                            |
| ----------------------------------------------------- | --------------------------------------------------------------------------------- |
| Five manifests keyed with the right underscore slug   | pass                                                                              |
| Five `config.yaml` + five `build.yaml` versions frozen | pass — `git diff HEAD~3 HEAD` touches no version or badge line anywhere           |
| Anonymous GHCR manifest probe, all five               | http 200 (5.36.0-11, 1.1.0-23, 1.0.6-0, 1.66.0-0, 0.3.0-0)                        |
| `LOCAL_BUILD_ADDONS` array region                     | exactly one element, `iac-runner`; removed name absent                            |
| `is_local_build` + both drift-guard message lines     | present                                                                           |
| Derived key-less set                                  | exactly `authentik iac-runner`                                                    |
| Rationale comment                                     | names `authentik`, keeps `260908-pfq-PLAN.md`, no numeric-plural claim — `OK`     |
| `shellcheck -e SC1091 -e SC2034` + `bash -n`          | exit 0                                                                            |
| RELEASE.md python assertion block                     | `RELEASE.md checks passed` (4-column table, all nine rows, all token assertions)  |
| `python3 internal/validate-addon-config.py`           | exit 0                                                                            |
| `make validate-addons`                                | exit 0 (nine add-ons)                                                             |
| `make validate-versions`                              | exit 0 (incl. TOFU-05 bridge/provider cross-check)                                |
| `make lint`                                           | exit 0 — 21/21 hooks Passed, incl. both Docker-backed terraform-bridge hooks      |
| Scope boundary                                        | `git diff --name-only HEAD~3 HEAD` = exactly the seven declared files             |
| `authentik/**`, `iac-runner/**`                        | untouched                                                                         |

The Task 2 pre-commit run exercised `terraform-bridge scaffold verify` and `terraform-bridge no-token-leak` for real
(both perform a container build of the bridge); both Passed.

## Deviations from Plan

None — the plan executed exactly as written. No deviation rule fired, no auth gate was hit, no fix attempt was needed.

Prettier reflowed `.github/RELEASE.md` on the first hook pass as the plan predicted; the second pass Passed and the
python assertion block was run against the reflowed file, so the reflow is the committed state.

## Known Stubs

None. No stub pattern, placeholder text or unwired surface exists in the seven modified files.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern or schema change at a trust boundary was introduced beyond
the `image:` reference already covered by T-vny-01/T-vny-02 in the plan's threat model, both of which were mitigated
in-task: every advertised version was proven anonymously pullable (HTTP 200) before commit, no version string moved, and
removing terraform-bridge from the allowlist restores the pre-push tag-existence guard for it.

## Observations For The Operator

- `git status --short` carries pre-existing entries unrelated to this item: `.planning/WINDOWS.md` (modified before this
  run), plus untracked `.gsd/`, `amp`, `.planning/quick-batches/260908-vnx/`, `network-tools/.planning/quick/` and this
  item's own plan directory. None was staged or committed here.
- Nothing was pushed. On the next `git push`, the pre-push hook will now demand a `terraform-bridge/v0.3.0-0` (or
  `terraform-bridge/v0.3.0`) tag if a future push modifies `terraform-bridge/config.yaml` — that re-enabled requirement
  is the intended effect of the allowlist removal, not a regression. This push does not trip it: the hook only inspects
  add-on directories whose version files a push modifies, and no version file changed.
- `.github/RELEASE.md` line ~106 still says "The seven callers carry the comment", while only six workflow files contain
  `tag-trigger temporarily disabled`. That claim sits outside the sections this item scoped and was recorded as a
  known-stale claim in the plan; it remains a candidate follow-up.

## Self-Check: PASSED

- `gatus/config.yaml` FOUND, `markdown-renderer/config.yaml` FOUND, `phone-logger/config.yaml` FOUND,
  `meridian/config.yaml` FOUND, `terraform-bridge/config.yaml` FOUND, `internal/check-version-tags.sh` FOUND,
  `.github/RELEASE.md` FOUND.
- Commits `f8c3296`, `8ac7d6e`, `2c94feb` all present in `git log`; HEAD is `2c94feb` on `main`.
- `git diff --diff-filter=D HEAD~3 HEAD` reports no deletions.
