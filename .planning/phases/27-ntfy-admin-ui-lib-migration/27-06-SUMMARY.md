---
phase: 27-ntfy-admin-ui-lib-migration
plan: 06
subsystem: ntfy documentation and version
tags: [docs, changelog, versioning]
requires: [27-02, 27-03, 27-04]
provides:
  - DOCS, README and CHANGELOG describe the admin-ui based GUI
  - ntfy add-on version 2.37.0-2 (subpatch bump through make update-version)
affects: [27-07]
key-files:
  modified:
    - ntfy/DOCS.md
    - ntfy/README.md
    - ntfy/CHANGELOG.md
    - ntfy/config.yaml
decisions:
  - "Target version is 2.37.0-2, not 2.37.0-1 (see deviation 1)"
status: complete
metrics:
  completed: 2026-11-03
actuals:
  tokens: 2500
  tasks: 2
  commits: 2
plan_head_before: e074f84
plan_head_after: 92a9b13
---

# Phase 27 Plan 06: documentation and subpatch bump Summary

DOCS, README and CHANGELOG now describe the migrated GUI (language switch, theme, accepted look change, translated
errors, optional HA integration limits, CSP with the diagnostic `NTFY_GUI_CSP` switch), and the add-on moved from
2.37.0-1 to 2.37.0-2 through `make update-version`.

`actuals.tokens` is chars/4 over the changed text (about 54 added lines). `commits: 2` counts the two task commits
(`plan_head_before` is the merge commit of plan 27-04; the SUMMARY commit follows them).

## Tasks

| Task | Commit | Result |
| ---- | ------ | ------ |
| 1 docs | a9ec64a | DOCS "Admin GUI guide" intro, behaviour notes, new section "Home Assistant theme and layout (optional)", CSP in Security notes, troubleshooting bullet, credits; README feature bullet and credit sentence; CHANGELOG entry `## [2.37.0-2] - 2026-11-03` (Changed, Added, Fixed) above 2.36.0-0 |
| 2 bump | 92a9b13 | `ntfy/config.yaml` 2.37.0-1 to 2.37.0-2; build.yaml and README shield untouched |

## Verification

- Line length check (`awk 'length > 120 ...'`) prints 0 for all three documents; leak-guard grep prints 0 for each.
- `pre-commit run --files` on the three documents: prettier (reformatted DOCS.md once, re-staged), markdownlint passed.
- `./internal/update-version.py ntfy 2.37.0-2 --dry-run --no-tag` reported 1 of 3 files; `make update-version ADDON=ntfy
  VERSION=2.37.0-2 NO_TAG=yes` applied it; `git diff` showed exactly one changed line in `ntfy/config.yaml`.
- `make validate-versions` exits 0; `uv run --with pyyaml bash internal/verify-ntfy-registration.sh` prints "All ntfy
  registration checks passed"; `grep -c '^## \[2.37.0-2\]' ntfy/CHANGELOG.md` prints 1.
- `git tag --list 'ntfy/*'` empty before and after (no tag created); `ntfy/build.yaml` unchanged; no commit carries
  Co-Authored-By.

## Deviations from Plan

1. **[Version] 2.37.0-2 instead of 2.37.0-1.** The plan was written when `ntfy/config.yaml` said 2.37.0-0. Main and this
   branch already carry 2.37.0-1 (schema-11 fix, PR #88), so the next add-on-only bump is 2.37.0-2. Applied with
   `make update-version ADDON=ntfy VERSION=2.37.0-2 NO_TAG=yes` (approved by the user for Phase 27). The CHANGELOG entry
   header and the "Since version" sentence in DOCS name 2.37.0-2.
2. **[Baseline] Registration verify** no longer failed at baseline: commit 15d3639 relaxed the CHANGELOG gate to "non-empty
   file". The matching header was still added as the plan requires (`## [2.37.0-2]`).
3. **[Check] Diff base.** `git diff origin/main` style checks were run against the previous commit, since the feature
   branch is ahead of origin/main.
4. Plan commit ledger (protocol 0c) was not recorded before the first commit; the base e074f84 is the merge commit named
   in the task prompt.

No auth gates.

## Known Stubs

None.

## Threat Flags

None. Documentation only; the leak-guard grep finds no host names, tokens or user names.

## Self-Check: PASSED

- Files found: ntfy/DOCS.md, ntfy/README.md, ntfy/CHANGELOG.md, ntfy/config.yaml.
- Commits found: a9ec64a, 92a9b13 (ancestors of HEAD).
