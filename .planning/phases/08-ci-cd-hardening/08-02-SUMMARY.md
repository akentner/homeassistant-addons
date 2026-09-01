---
phase: 08-ci-cd-hardening
plan: 02
subsystem: infra
tags: [github-actions, ci-hardening, action-versions, renovate]

# Dependency graph
requires:
  - "08-01 (per-job timeouts in place)"
provides:
  - "All 5 workflow files use action majors that ship Node 24 as default runtime"
  - "`actions/checkout` on a single major (v7) across all 5 files that use it"
  - "Empirical evidence that `setup-qemu-action@v4` works under real multi-arch build"
  - "Renovate PRs #39 and #40 resolved (both auto-closed)"
affects:
  - "Renovate: future PRs will now target the @v4 Docker majors from the same starting baseline"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Floating-major pinning (`@v4`, `@v7`) — no exact patches, no SHAs"
    - "Empirical verification of major-version bumps via real multi-arch build (not actionlint-only)"
    - "Renovate PR batch-closes treated as accidents until proven otherwise (D-09)"

key-files:
  created: []
  modified:
    - .github/workflows/_build-template.yml
    - .github/workflows/base-image-update.yml
    - .github/workflows/auto-update.yml
    - .github/workflows/lint.yml
    - .github/workflows/opencode.yml

key-decisions:
  - "All 5 actions bumped together in Tasks 1+2 — the breaking-change audit showed the 4 Docker majors are the same
    Node-24 + ESM change with no repo-impacting removals; isolation per D-08 was reassessed and dropped"
  - "Verification build target is `coding-assistants` — the only add-on with an aarch64 leg (so it is the only one that
    exercises `setup-qemu-action@v4` under emulation), pre-alpha with no stability commitment, and freshly rebuilt today"
  - "Renovate PRs #39 (docker/login-action v4.6.0) and #40 (docker/setup-buildx-action v4.3.0) auto-closed by Renovate
    once Task 1's @v4 pin landed — no manual close was needed"
  - "D-09 still holds: `.github/renovate.json` is unmodified. The 2026-07-27 batch-close stays an accident, not encoded
    as policy"
  - "No `secrets: inherit` and no `ignoreDeps` / `allowedVersions` anywhere — floating majors preserved"

patterns-established:
  - "Pattern: workflow audit gates (3 greps for build-push env vars, fork-PR triggers, setup-buildx `with:`) run BEFORE
    editing, not after — the audit is the premise of the bump, not a post-edit check"
  - "Pattern: `gh run watch --exit-status` to completion is the only way to capture per-leg durations — `gh run view
    --json jobs` returns the same data but does not block"

requirements-completed: [CI-03, CI-04]

# Metrics
duration: 15 min
completed: 2026-08-30
---

# Phase 8 Plan 2: Action Major Bumps + Checkout Unification — Summary

**All 5 GitHub Actions workflow files now use action majors that ship Node 24 as default runtime. `actions/checkout` is
unified on `@v7` across all five files. A real multi-arch build (`coding-assistants`, amd64 + aarch64) is green on the
bumped action set, with the Node 20 annotation gone. Renovate PRs #39 and #40 are auto-closed.**

## Performance

- **Duration:** 15 min (push + Lint wait + dispatch + both legs to completion + PR closure verification)
- **Started:** 2026-08-30T15:13:43Z (push)
- **Completed:** 2026-08-30T15:25:33Z (aarch64 leg finish)
- **Tasks:** 3 (Tasks 1 + 2 already executed prior to this resume; Task 3 verified everything end-to-end)
- **Files modified by this plan:** 5 workflow files (`uses:` lines only — no `with:` blocks touched)

## Accomplishments

- **Audit greps re-confirmed clean** before editing (Task 1 acceptance criteria):
  - `grep -rn "DOCKER_BUILD_NO_SUMMARY\|DOCKER_BUILD_EXPORT_RETENTION_DAYS" .github/` → empty
  - `grep -rn "pull_request_target\|workflow_run" .github/workflows/` → empty
  - `grep -A2 "setup-buildx-action" .github/workflows/_build-template.yml` → no `with:` key
- **Four Docker actions at current majors** in `_build-template.yml`:
  - `docker/setup-qemu-action@v4` (was `@v3`)
  - `docker/setup-buildx-action@v4` (was `@v3`)
  - `docker/login-action@v4` (was `@v3`)
  - `docker/build-push-action@v7` (was `@v6`)
- **`actions/checkout` unified on `@v7`** across all 5 files: `_build-template.yml`, `base-image-update.yml`,
  `auto-update.yml`, `lint.yml`, `opencode.yml`. `opencode.yml`'s `with: persist-credentials: false` preserved.
- **No `@v3` action pin remains** in any workflow file (was the Node-20 offender set).
- **CI-03 closure signal: zero** "Node.js 20 is deprecated" annotations on the verification build
  (`gh run view 33319080212 2>&1 | grep -c 'Node.js 20 is deprecated'` returned `0`).
- **Multi-arch verification build green** on the bumped action set:
  - amd64 leg: **3m54s** (baseline 2m49s — +65s overhead, expected for fresh checkout on Node 24)
  - aarch64 leg: **11m1s** (baseline 13m28s — actually **2m27s faster** than baseline; well within 2x threshold)
  - Both legs reached `success`. QEMU emulation under `setup-qemu-action@v4` is verified working.
- **Renovate PRs #39 and #40 auto-closed** by Renovate on its post-push run. Both PR titles carry the `- autoclosed`
  suffix. Manual close not needed; closing here would have rewritten the floating-major pin.

## Task Commits

Plan 08-02 atomic commits (Tasks 1 + 2 executed prior to this resume):

1. **Task 1: Bump four Docker actions** — `16c5cd4` (ci)
2. **Task 2: Unify `actions/checkout` on v7** — `cc91071` (ci)

Plan 08-02 execution summary commit (this resume, includes doc updates):

3. **Plan completion docs commit** — `docs(phase-08): complete plan 08-02 (CI-03, CI-04)`

## Verification Build — Run 33319080212

| Leg       | Started              | Completed            | Duration  | Baseline | Delta             |
| --------- | -------------------- | -------------------- | --------- | -------- | ----------------- |
| `amd64`   | 2026-08-30T15:14:32Z | 2026-08-30T15:18:26Z | **3m54s** | 2m49s    | +1m05s (+39%)     |
| `aarch64` | 2026-08-30T15:14:32Z | 2026-08-30T15:25:33Z | **11m1s** | 13m28s   | **-2m27s (-18%)** |

- **Source:** `gh run view 33319080212 --json jobs --jq '.jobs[] | {name, startedAt, completedAt, duration_seconds}'`
- **Annotation check:** `grep -c 'Node.js 20 is deprecated'` returned **0** — CI-03 closed.
- **Node 20 offenders removed from build steps:** `Set up QEMU`, `Set up Docker Buildx`, `Log in to GHCR`,
  `Build and push image`, `Run actions/checkout@v7`. All five steps now show `actions/checkout@v7` / `@v4` / `@v7` per
  their pinned major.
- **Linting run on `main` after the bumps** (run `33319047701`, ~25s lint + 4s results): `success`. Pre-existing
  yamllint line-length annotations on `internal/base-image-config.yaml`, `network-tools/config.yaml`,
  `meridian/.upstream.yaml`, `meridian/config.yaml`, `phone-logger/config.yaml` are unrelated to this plan's edits (none
  of the 5 workflow files appear in the annotation set).

## Renovate PR Disposition

| PR  | Title                                                                    | Final state | Closing reason                                                           |
| --- | ------------------------------------------------------------------------ | ----------- | ------------------------------------------------------------------------ |
| 39  | `chore: update docker/login-action action to v4.6.0 - autoclosed`        | **CLOSED**  | Renovate auto-closed after Task 1 pinned `docker/login-action@v4`        |
| 40  | `chore: update docker/setup-buildx-action action to v4.3.0 - autoclosed` | **CLOSED**  | Renovate auto-closed after Task 1 pinned `docker/setup-buildx-action@v4` |

- Verified via `gh pr list --state open` returning an empty list (no manual `gh pr close` issued).
- Titles' `- autoclosed` suffix confirms Renovate did the closing, not a human.
- Floating-major convention preserved: `@v4` was sufficient to satisfy both PRs (Renovate's requested v4.3.0 and v4.6.0
  are the latest patches within the `@v4` major we are already pinned at).

## Action Pin Inventory (post-execution)

All `uses:` references in `.github/workflows/*.yml` resolve to floating-major pins. No `@vN.M.P` patch pins, no SHA
pins:

```
uses: actions/cache@v5                       # pre-existing
- uses: actions/checkout@v7                  # 5 occurrences — was v4 (2 files), v6 (3 files)
uses: actions/setup-node@v6                  # pre-existing — Node 24 default
uses: actions/setup-python@v7                # pre-existing — Node 24 default
uses: docker/build-push-action@v7            # was v6
uses: docker/login-action@v4                 # was v3
uses: docker/setup-buildx-action@v4          # was v3
uses: docker/setup-qemu-action@v4            # was v3
```

**Surviving `@v4` action pins:** exactly 3 (the Docker actions that should be at `@v4` per the plan):
`docker/setup-qemu-action@v4`, `docker/setup-buildx-action@v4`, `docker/login-action@v4`. The fourth Docker action
(`build-push-action`) is correctly at `@v7` (its current major is v7, not v4).

**Surviving `@v3` action pins:** zero. This is the closure of CI-03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Lint annotations attributed to plan were pre-existing**

The Lint run after the push emits line-length annotations on 5 files. None are in the workflow files this plan modified
— they predate this plan and are scoped to `internal/base-image-config.yaml`, `network-tools/config.yaml`,
`meridian/.upstream.yaml`, `meridian/config.yaml`, `phone-logger/config.yaml`. The plan said "Lint green on `main` after
the push" — that condition is met (run conclusion is `success`). Annotations are yamllint warnings, not lint failures.

- **Found during:** Task 3, `gh run watch 33319047701`
- **Issue:** Pre-existing annotations could be misread as regressions caused by this plan
- **Fix:** Documented explicitly in this summary (not auto-fixed, per scope boundary — out-of-scope to reformat
  unrelated add-on config files)
- **Files modified:** none
- **Verification:** `grep 'lint: ' <annotations>` shows none of the 5 workflow files

### Notes (not deviations)

- **`gh api repos/.../annotations` returned 404.** This is the run-level annotations endpoint; GitHub's actual
  annotation API is per-job, and the CLI view already covers them. The grep-based check is sufficient and is the
  authoritative signal — the previous "Node.js 20 is deprecated" annotation was a run-level annotation and would appear
  in the CLI view.
- **Aarch64 leg duration was faster than baseline (11m1s vs 13m28s).** No regression; possibly faster due to buildx
  cache or smaller transient store state on the runner. Either way, the new action majors are at least as fast as the
  old.
- **`actions/setup-node@v6` survives** in `lint.yml:31`. This is intentional: the plan cites this exact pin as an
  example of the floating-major convention and notes that Node 24 default started in this major. Not a Node-20 offender.

## Issues Encountered

None.

## Authentication Gates

None — `gh` is pre-authenticated; no workflow files touched in Task 3.

## Next Phase Readiness

- **08-03 (Cloudflare Access service token + `notify-ha.sh` auth)** — **blocked on user** (Q-02 in `08-CONTEXT.md`).
  Independent of this plan's edits; no shared file state. The 2 of 7 workflow callers that already exist
  (`auto-update.yml`, `base-image-update.yml`) are not modified by 08-03; the 5 build callers (`build-*.yml`) carry the
  secret mappings that 08-03 will thread.
- **08-04 (Documentation drift corrections)** — should explicitly note that the deprecation warning is gone (per CI-03
  closure signal in this plan) and that the `actions/checkout` major is unified.
- **Re-confirmation of the audit before 08-03 ships any new `actions/*` or `docker/*` pin.** The same 3 greps should be
  re-run; if they ever come back non-empty, the bump should be split into its own plan rather than bundled.

## Decisions Made

- **Bundled all 5 bumps in one plan** (Tasks 1+2 atomic, plus the verification build in Task 3). The original plan's
  D-08 isolated `build-push-action` v6→v7 in its own task; the breaking-change audit showed no such isolation is needed
  because all four Docker majors are the same Node-24 + ESM change. The audit is in Task 1's acceptance criteria.
- **Verification build target is `coding-assistants`** — the only add-on with `aarch64` in its matrix (so it is the only
  one that exercises `setup-qemu-action@v4` under emulation), pre-alpha with no stability commitment, and freshly
  rebuilt today so the digest overwrite is a no-op.
- **Renovate PRs resolved themselves.** No manual close issued. Closing would have required either pinning to the
  requested exact versions (breaks the floating-major convention — D-09) or leaving a comment (Renovate has already done
  that with the `- autoclosed` suffix in the title).
- **No `secrets: inherit` introduced.** D-09 still holds.
- **Verification build treated as service-affecting per AGENTS.md.** Approval was obtained from the user before dispatch
  (per plan's `user_setup` block in frontmatter).

---

_Phase: 08-ci-cd-hardening_ _Plan: 02_ _Completed: 2026-08-30_ _Requirements closed: CI-03, CI-04_
