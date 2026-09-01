---
phase: 08-ci-cd-hardening
plan: 04
subsystem: infra
tags: [docs, github-actions, webhook, cloudflare-access, renovate, secrets-contract]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Per-job timeout-minutes in 5 workflow files (values + comments this plan documents)"
  - phase: 08-02
    provides: "Floating-major action pins + Renovate close-mechanic evidence this plan references"
  - phase: 08-03
    provides: "notify-ha.sh CF-Access auth + 3xx fail-fast + 4 secrets in callers (the SHAPE the docs describe)"
provides:
  - "9 documentation drift instances corrected across README, AGENTS, WEBHOOK_SETUP, RELEASE, DEVELOPMENT"
  - "Three conventions written down: timeout policy, action-pinning, 4-secret contract"
  - "Cloudflare Access service-token prerequisite documented with two-directional --resolve verification recipe"
  - "In-workflow comment pointer '# tag-trigger temporarily disabled (see .github/RELEASE.md)' now resolves to real
    content"
affects:
  - "Future plans touching CI/webhook/auth — they inherit the documented conventions and the documented failure modes
    (HA returns 200 for any webhook ID, CF Access is the only transport auth)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Doc corrections describe the intended end state of waves 1-3, not the verified one — if 08-03 Task 5 surfaces
      discrepancies, those get a separate fix-up pass"
    - "Empirical-basis comments adjacent to each cap (aarch64 13m28s, etc.) are the durable record; the docs section
      mirrors them as a table so a future maintainer can re-derive the number rather than guess"
    - "Least-privilege prohibitions are written down verbatim because a planning error was caught only because the
      sentence existed (D-03 reversal in 08-03)"

key-files:
  created: []
  modified:
    - README.md
    - AGENTS.md
    - docs/WEBHOOK_SETUP.md
    - docs/DEVELOPMENT.md
    - .github/RELEASE.md

key-decisions:
  - "Describe the build trigger as `paths:`-on-`main` via the per-addon caller + reusable template, NOT as a tag push —
    for 6 of 7 add-ons that is what actually fires builds today; .github/RELEASE.md carries the per-addon tag-trigger
    detail"
  - "DELETE the false HA_WEBHOOK_SECRET / X-HA-Signature paragraph rather than convert it to a 'coming soon' promise —
    the false claim is the kind of forward-looking speculation that produced the original defect"
  - "Document the Cloudflare Access section with a two-directional --resolve verification recipe (negative probe 302
    without CF headers, positive probe 200 with) so a fresh maintainer can diagnose the class of failure without
    repeating the audit"
  - "Warn explicitly that HA returns 200 for ANY webhook ID — a 200 proves Access was traversed, not that HA processed
    the event; verify via last_triggered or Developer Tools → Events"
  - "Preserve the secrets: inherit prohibition verbatim (least privilege wording) and the Trigger Pitfalls section
    untouched — both reversed planning errors this phase made (D-03, D-08) and both are the guardrails that worked"
  - "Use the literal string `tag-trigger` so the in-workflow comment's pointer resolves to real content; six workflow
    files carry the comment `# tag-trigger temporarily disabled (see .github/RELEASE.md)`"

patterns-established:
  - "Pattern: doc corrections land LAST in a phase, after the code they describe is committed — D-11 holds"
  - "Pattern: per-addon state tables in docs mirror a reproducible grep sweep — `grep -c '^    tags:'
    .github/workflows/build-*.yml` is the verification command for the RELEASE.md table"
  - "Pattern: Renovate close-suppresses-forever trap is recorded as a convention, not just a one-time lesson — every
    closed bump PR is now an explicit policy question"

requirements-completed: [CI-09, CI-10]

# Metrics
duration: 25 min
completed: 2026-08-30
---

# Phase 8 Plan 4: Documentation Drift Correction — Summary

**Nine documentation drift instances corrected across five documents; three conventions this phase established
(timeouts, action pinning, 4-secret contract) recorded with their derivations; the in-workflow tag-trigger pointer now
resolves to real content.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-30T16:00:00Z
- **Completed:** 2026-08-30T16:25:00Z
- **Tasks:** 4
- **Files modified:** 5 (README.md, AGENTS.md, docs/WEBHOOK_SETUP.md, docs/DEVELOPMENT.md, .github/RELEASE.md)

## Nine drift instances — resolutions

| #   | Location                        | Original claim (drift)                                                          | Resolution                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| --- | ------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `README.md:138-139`             | `build.yml` builds on a `v*` tag                                                | Replaced with real trigger: `build-<addon>.yml` → `_build-template.yml` on `push` to `main` touching `<addon>/**`; tag is `<addon>/v<version>`                                                                                                                                                                                                                                                                                                                            |
| 2   | `README.md:173`                 | Inline Makefile comment "creates and pushes the `v<version>` git tag"           | Now reads "creates and pushes the `<addon>/v<version>` git tag"                                                                                                                                                                                                                                                                                                                                                                                                           |
| 3   | `AGENTS.md:111-113`             | Same `build.yml` + `v*` claim                                                   | Same correction as #1, in the "What this does" paragraph                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 4   | `AGENTS.md:117-118`             | Pre-push hook "matching `v<version>` tag"                                       | Now reads "matching `<addon>/v<version>` tag"                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 5   | `docs/WEBHOOK_SETUP.md:3`       | `build.yml`, `build-network-tools.yml`                                          | Replaced with the seven per-addon `build-<addon>.yml` callers via reusable template; both `started` and `finished` notify steps                                                                                                                                                                                                                                                                                                                                           |
| 6   | `docs/WEBHOOK_SETUP.md:71-73`   | `HA_WEBHOOK_SECRET` is supported in the script + `X-HA-Signature` guidance      | **DELETED entirely.** `notify-ha.sh` contains no such env/header. Replaced with honest statement: webhook has no HMAC; Cloudflare Access is the only transport protection                                                                                                                                                                                                                                                                                                 |
| 7   | `docs/WEBHOOK_SETUP.md:96,116`  | `"workflow": "Build & Release"`                                                 | Now `"Build Coding Assistants"` (real workflow name, consistent with `"addon": "coding-assistants"`)                                                                                                                                                                                                                                                                                                                                                                      |
| 8   | `docs/WEBHOOK_SETUP.md:100,120` | `"ref": "refs/tags/v1.0.0"`                                                     | Default `"refs/heads/main"`; mention `refs/tags/<addon>/v<version>` as the tag-triggered alternative (cite RELEASE.md for which add-ons have it enabled)                                                                                                                                                                                                                                                                                                                  |
| 9   | `.github/RELEASE.md:31-36`      | Every caller triggers on `main` push AND `<addon>/v*` tag, "built exactly once" | Replaced with a 7-row table matching the live `grep -c '^    tags:' .github/workflows/build-*.yml` sweep; only network-tools has an active `tags:` block. Captured rationale from `287c79f` (24 stale tags, ~30 min rebuilds, ghcr.io overwrites) and `60e7835` (network-tools re-enabled because it had just 2 tags, `v0.4.0` already near-current). Operational consequence documented: for 6 of 7 add-ons, the commit push to `main` is what builds, not the tag push. |

## Three conventions written down

**A. Timeout policy** (`docs/DEVELOPMENT.md` → "Job Timeouts" subsection):

| Workflow                | Job            | Cap | Derived from            |
| ----------------------- | -------------- | --- | ----------------------- |
| `_build-template.yml`   | `build`        | 45  | aarch64 QEMU leg 13m28s |
| `auto-update.yml`       | `update`       | 20  | observed 8-28s          |
| `base-image-update.yml` | `update`       | 15  | observed 11-15s         |
| `lint.yml`              | `lint`         | 15  | observed 37-45s         |
| `lint.yml`              | `lint-results` | 5   | reporting only          |
| `opencode.yml`          | `opencode`     | 30  | no baseline; ceiling    |

Invariant: `grep -rh 'timeout-minutes:' .github/workflows/*.yml | wc -l` must equal the number of jobs (6). A new job
that ships without a cap is a regression — it would inherit the 360-minute default.

**B. Action-pinning convention** (`docs/DEVELOPMENT.md` → "Action Pinning" subsection):

Floating-major pins (`@v7`, `@v4`, `@v6`) — never exact patch versions, never commit SHAs. Renovate closes a PR → that
exact version is never re-offered. The 2026-07-27 batch-close permanently suppressed `actions/checkout` v7.0.1,
`docker/build-push-action` v7.3.0, and `docker/setup-qemu-action` v4.2.0; the Node 20 deprecation warning would have
persisted indefinitely without the manual bumps in 08-02. If a bump is unwanted, record why in a comment; if it is
wanted later, apply by hand or reopen the branch. `.github/renovate.json` carries no `ignoreDeps` / `allowedVersions`
entries, by design — the accident is not encoded as policy.

**C. 4-secret contract** (`docs/DEVELOPMENT.md` → "Secrets Contract" subsection):

| Secret                    | Required | Notes                                     |
| ------------------------- | -------- | ----------------------------------------- |
| `HA_BASE_URL`             | yes      | Public HA URL; no trailing slash          |
| `HA_WEBHOOK_ID`           | yes      | Random value; see `docs/WEBHOOK_SETUP.md` |
| `CF_ACCESS_CLIENT_ID`     | optional | Needed when HA is behind CF Access        |
| `CF_ACCESS_CLIENT_SECRET` | optional | Needed when HA is behind CF Access        |

`notify-ha.sh` reads the two `CF_ACCESS_*` secrets at runtime and adds the matching `CF-Access-Client-Id` /
`CF-Access-Client-Secret` request headers to the POST only when both are set. When either is unset the headers are
omitted entirely, so LAN / split-horizon callers keep working unauthenticated.

The `secrets: inherit` prohibition in this section is preserved verbatim — that sentence is the one that reversed D-03
during 08-03 planning. Weakening it would remove the guardrail that worked.

## Repo-wide sweep results

```
$ grep -rn 'build\.yml' --include='*.md' .
(only .planning/ references — those quote it as evidence, which is correct)

$ grep -rqE 'HA_WEBHOOK_SECRET|X-HA-Signature' docs/
(zero hits)

$ grep -c '^    tags:' .github/workflows/build-*.yml
.github/workflows/build-authentik.yml:0
.github/workflows/build-coding-assistants.yml:0
.github/workflows/build-gatus.yml:0
.github/workflows/build-markdown-renderer.yml:0
.github/workflows/build-meridian.yml:0
.github/workflows/build-network-tools.yml:1   ← only active tag-trigger
.github/workflows/build-phone-logger.yml:0
```

The `.github/RELEASE.md` tag-trigger state table matches this sweep exactly. Verified `tag-trigger`, `287c79f`,
`60e7835`, and `network-tools` are all present in the file; the false "built exactly once, regardless" sentence is gone.

## Task Commits

Each task was committed atomically with `--no-verify` per parallel-executor protocol (5 new commits total):

1. **Task 1: Correct build-trigger and tag-schema claims** — `aa8ab45` (docs)
   - README.md + AGENTS.md: 19 line edits total, two localized corrections per file
   - 404 consequence preserved in both files
2. **Task 2: Rewrite WEBHOOK_SETUP.md** — `96b0300` (docs)
   - 5 changes: opening trigger reference, deleted HMAC paragraph, added Cloudflare Access section, fixed payload
     examples, updated failure handling; extended troubleshooting with the "200 proves nothing" trap
3. **Task 3: Document real tag-trigger state in RELEASE.md** — `bde105c` (docs)
   - Replaced 6 lines of false claim with a 7-row state table + rationale from both commits + re-enabling procedure
4. **Task 4: DEVELOPMENT.md timeout policy + action pinning + 4-secret contract** — `0c67f10` (docs)
   - Extended Secrets Contract from 2 to 4 secrets; added Job Timeouts and Action Pinning subsections between Secrets
     Contract and Trigger Pitfalls; preserved the `secrets: inherit` prohibition and Trigger Pitfalls verbatim

**Plan metadata:** included in the final docs commit with the SUMMARY, STATE, ROADMAP, REQUIREMENTS updates.

## Files Created/Modified

- `README.md` — 9 lines changed; corrected tag schema + build trigger in the 3-file versioning bullet + Makefile comment
- `AGENTS.md` — 10 lines changed; same correction in "What this does" + pre-push hook paragraphs
- `docs/WEBHOOK_SETUP.md` — 129 insertions / 18 deletions; full rewrite per PLAN action (a)-(e)
- `docs/DEVELOPMENT.md` — 68 insertions / 1 deletion; Secrets Contract extended, Job Timeouts and Action Pinning added
- `.github/RELEASE.md` — 54 insertions / 6 deletions; tag-trigger state table + rationale + re-enabling procedure

## Decisions Made

- **Build trigger described as `paths:`-on-`main`, not tag-push.** For 6 of 7 add-ons the tag-trigger is commented out
  today, so describing it as a tag push would have been the next round of drift. RELEASE.md carries the per-addon
  tag-trigger detail; the high-level docs describe what actually fires builds.
- **DELETE the HMAC paragraph rather than convert to "coming soon".** A speculative promise is how the original false
  claim came about. If HMAC support is actually wanted, that is a separate plan with its own scope.
- **Verification recipe uses `--resolve` against the public IP.** A local `curl` from the LAN reaches HA directly via
  split-horizon DNS (192.168.178.3); a GitHub runner takes the public path (188.114.96.3/188.114.97.3). The recipe
  forces the runner's path so the test is meaningful.
- **`secrets: inherit` prohibition preserved byte-identical.** The sentence is the convention that reversed D-03 during
  08-03 planning; weakening it would remove the guardrail that caught the planning error.
- **Trigger Pitfalls unchanged.** It is accurate, and its warning that a representative dispatch is service-affecting
  (pushes images + fires webhooks) is the reason 08-02 and 08-03 gated verification builds on explicit approval.
- **`tag-trigger` is a literal string in the document.** Six workflow files carry the comment
  `# tag-trigger temporarily disabled (see .github/RELEASE.md)`. Making the term findable is what makes the pointer
  resolve to real content.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Trimmed Secrets Contract table notes to satisfy markdownlint MD013 line-length**

The initial Secrets Contract table had long Notes cells (e.g., "Cloudflare Access service-token Client ID; required when
HA is behind Cloudflare Access" at 68 chars). With the project's `.markdownlint.json` setting `MD013.line_length: 120`,
the wider rows tripped the rule on rows 122-124. After the trim the table is consistent at 78 chars per row. The same
warning behaviour in MD060 (table column alignment) was avoided by keeping the Notes column uniform. `markdownlint-cli2`
returns 0 issues on the final file. The functional content of each cell is preserved; only the abbreviations
(`CF Access` instead of `Cloudflare Access`, `WEBHOOK_SETUP.md` instead of ` docs/WEBHOOK_SETUP.md`) change.

- **Found during:** Task 4, first markdownlint run on DEVELOPMENT.md
- **Issue:** Long Notes cells in the new Secrets table + L178 `#40` interpreted as heading
- **Fix:** Shortened Notes column entries to fit 120-char limit consistently across all 4 rows; wrapped the `#40`
  reference in backticks so markdownlint does not treat it as a level-1 heading
- **Files modified:** docs/DEVELOPMENT.md (table content + minor text wrap on L177-178)
- **Verification:** `npx markdownlint-cli2 docs/DEVELOPMENT.md` returns 0 issues; no line > 120 chars outside tables
- **Committed in:** `0c67f10` (Task 4 commit)

**Total deviations:** 1 auto-fixed (Rule 1 - markdownlint table alignment + line-length). **Impact on plan:**
Negligible. No semantic content lost; the trimmed prose reads identically.

## Issues Encountered

- **`make lint-markdown` and `make check-all` not runnable in this sandbox.** Both require `pre-commit` (and the
  underlying yamllint, actionlint, shellcheck, hadolint binaries) which are not installed. The 08-01 SUMMARY notes the
  same sandbox limitation and explains that the orchestrator's required gates (actionlint + yamllint on modified
  workflow files) all pass cleanly. For this docs-only plan, `markdownlint-cli2` invoked via `npx` is the authoritative
  Markdown check and returns 0 issues on all 5 modified files (and across the entire repo: 32 files, 0 issues). Per the
  08-01 note, this is the same sandbox gap, not a regression.

## Next Phase Readiness

- **08-03 Task 5 (Cloudflare Access verification probes)** — this plan does NOT depend on it and does not block it. If
  Task 5 surfaces discrepancies with the docs written here, those get fixed in a separate pass. The docs describe the
  intended end state of waves 1-3.
- **Phase 8 completion** — with CI-09 and CI-10 closed by this plan, every requirement (CI-01..CI-10) is satisfied
  either by code (waves 1-3) or by docs (wave 4). The remaining open work is Q-04 (validate never-run
  `Build Markdown Renderer` and `Build Meridian` workflows) — out of scope per 08-CONTEXT.md.
- **Wave-4 push** — all 5 wave-4 commits are atomic and self-contained; the push lands pure docs (no build-affecting
  changes). The combined wave-3a + wave-4 push is ~8 commits ahead of `origin/main` after Task 5 of 08-03 (whenever it
  runs).

---

_Phase: 08-ci-cd-hardening_ _Plan: 04_ _Completed: 2026-08-30_ _Requirements closed: CI-09, CI-10_

---

## Self-Check: PASSED

All 5 task commits present in `git log` (aa8ab45 / 96b0300 / bde105c / 0c67f10 / 9e48a34). SUMMARY.md exists at
`.planning/phases/08-ci-cd-hardening/08-04-SUMMARY.md`. `git status -sb` shows `main...origin/main` clean. Repo-wide
`build.yml` and `HA_WEBHOOK_SECRET` sweeps return zero hits outside `.planning/`.
