---
phase: 03-management-gui
plan: 05
subsystem: ui
tags: [preact, admin-ui, i18n, node-test, docs, release]

requires:
  - phase: 03-management-gui
    provides: "03-01 shell (VIEWS, loadView, App, top bar version), 03-06 node harness and i18n key scan, 03-03 Access view, 03-02/03-04 fetch sink and last-fetch file"
provides:
  - "Info view (`views/info.mjs`): third navigation entry `info`, static setup, reverse proxy and rotation text from `mrp.info.*`"
  - "DOCS.md `## Management page`, `### /data/last-fetch.json` contract, fetch-sink security notes, GUI verify script"
  - "README.md management-page mention; CHANGELOG.md section `## [0.1.0-2] - 2026-11-19`"
  - "Add-on version 0.1.0-2 (config.yaml only, through make update-version, no tag)"
affects: [phase-04-api, phase-05-reverse-proxy, manager-merge]

actuals:
  tokens: 6270 # chars/4 over the added lines of the realized diff (10 files, 25079 chars)
  tasks: 3
  commits: 4
plan_head_before: 966c54804b84314cd3b92639582d67114dfbe194
plan_head_after: e9996f63736447989558b156ea70721c1d18380f

tech-stack:
  added: []
  patterns:
    - "Static view: every text a literal tt(\"...\") call, so the i18n key scan sees each key; no list of keys in data"

key-files:
  created:
    - marketplace-repo-proxy/app/web/static/views/info.mjs
    - marketplace-repo-proxy/tests/js/info.test.mjs
  modified:
    - marketplace-repo-proxy/app/web/static/app.mjs
    - marketplace-repo-proxy/app/web/static/strings.de.mjs
    - marketplace-repo-proxy/app/web/static/strings.en.mjs
    - marketplace-repo-proxy/tests/test_js.py
    - marketplace-repo-proxy/DOCS.md
    - marketplace-repo-proxy/README.md
    - marketplace-repo-proxy/CHANGELOG.md
    - marketplace-repo-proxy/config.yaml

key-decisions:
  - "03-05: German navigation title of the Info view is Anleitung (real German, so the i18n identical-text allowlist stays unchanged)"
  - "03-05: Phase 3 ships as 0.1.0-2 (origin/main had 0.1.0-1 and no new add-on commits at both fetches; no rebase)"

patterns-established:
  - "Docs follow the code: DOCS.md last-fetch rules were written from app/lastfetch.py and app/fetchlog.py, not from SUMMARYs"

requirements-completed: [MRP-16, MRP-15]

coverage:
  - id: D1
    description: "Info view is the third navigation entry and shows three static cards (setup, reverse proxy, rotation) in English and German, with no button, input, link or request; re-rendering gives identical text"
    requirement: MRP-16
    verification:
      - kind: automated_ui
        ref: "node --test marketplace-repo-proxy/tests/js/info.test.mjs"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/js/i18n.test.mjs#used keys: every literal key in app.mjs, model.mjs and views/*.mjs resolves and no key is dynamic"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_js.py#test_node_unit_tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "DOCS.md documents the management page, the /data/last-fetch.json contract (D-21) and the fetch-sink security model; no stale future-work wording; README and CHANGELOG updated; translations unchanged"
    requirement: MRP-15
    verification:
      - kind: other
        ref: "Task 2 docs gate (prints docs-ok) and pre-commit run --files DOCS.md README.md CHANGELOG.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "Version bump to 0.1.0-2 through make update-version NO_TAG=yes as the last add-on commit, changelog commit right before it, no tag"
    verification:
      - kind: other
        ref: "Task 3 verify commands (print bump-ok and bump-commit-ok)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Wording and layout of the Info view and the German texts inside the real HA ingress panel"
    verification: []
    human_judgment: true
    rationale: "Node tests run on a fake DOM; readability of the three cards and the German phrasing need a human look in the panel"

duration: 6min
completed: 2026-11-19
status: complete
---

# Phase 3 Plan 05: Info View, Docs and Release Summary

**Static Info view (setup, reverse proxy, rotation) as the third navigation entry, DOCS.md with the management page,
the `/data/last-fetch.json` contract and the fetch-sink security model, and the release bump to 0.1.0-2 through
`make update-version` without a tag**

## Performance

- **Duration:** 6 min
- **Started:** 2026-11-19T00:04:07Z
- **Completed:** 2026-11-19T00:10Z
- **Tasks:** 3 (tracer, docs, release)
- **Files modified:** 10 (2 created, 8 modified)

## Accomplishments

- `views/info.mjs`: three `card` sections; setup (copy from the Access view, add in the store dialog, one host name per
  HA instance, internal URL only on the own instance, URLs are secrets), reverse proxy (TLS at the proxy, port 8080, no
  caching of `/repo/*`, no path logging, detailed guides not in this version), rotation (back up, rotate, remove the old
  repository, add the new URL and reinstall, restore). No import of `api.mjs`, no state.
- `app.mjs` `VIEWS` gains `{ id: "info", titleKey: "view.info" }`; strings `view.info` (Info / Anleitung) and 19
  `mrp.info.*` keys in both tables.
- `tests/js/info.test.mjs`: app with `#/info` (nav order Repositories, Access, Info; only the shell's `api/meta`
  request), English and German texts, re-render identity with zero requests, no controls, a11y audits clean.
- DOCS.md: Overview, new `## Management page` (Repositories, Access, Info, access to the page), "Managing users",
  "Sync and status", Contracts intro and `access.json` write rule, new `### /data/last-fetch.json`, Security notes (fetch
  sink, management page, files), Development (GUI verify script).
- README.md mentions the page (Open Web UI); CHANGELOG.md `## [0.1.0-2] - 2026-11-19` with Added and Changed.
- `config.yaml` `version: "0.1.0-2"`; build.yaml and the README badge keep `0.1.0`.

## Task Commits

1. **Task 1: Info view (tracer)** - `0466c06` (feat)
2. **Task 2: docs for the management page, last-fetch contract and fetch sink** - `8f44c3c` (docs)
3. **Task 3a: changelog heading for 0.1.0-2** - `e5f14dd` (docs)
4. **Task 3b: bump to 0.1.0-2** - `e9996f6` (chore)

## Files Created/Modified

- `marketplace-repo-proxy/app/web/static/views/info.mjs` - Info view (new)
- `marketplace-repo-proxy/app/web/static/app.mjs` - `info` entry in `VIEWS`
- `marketplace-repo-proxy/app/web/static/strings.{de,en}.mjs` - `view.info`, `mrp.info.*`
- `marketplace-repo-proxy/tests/js/info.test.mjs` - node tests (new)
- `marketplace-repo-proxy/tests/test_js.py` - `FILES` gains `info`
- `marketplace-repo-proxy/DOCS.md`, `README.md`, `CHANGELOG.md` - documentation
- `marketplace-repo-proxy/config.yaml` - `version: "0.1.0-2"` (make update-version)

## Release

- `BASE` = `0.1.0-1` (`origin/main:marketplace-repo-proxy/config.yaml`, fetched before Task 2 and again right before
  the bump), `NEXT` = `0.1.0-2`.
- `git log --oneline HEAD..origin/main -- marketplace-repo-proxy/` was empty at both fetches: no rebase happened.
- Dry run: `Would update config.yaml: 0.1.0-1 → 0.1.0-2`, no change for build.yaml and README.md, `Would update 1/3
  files`.
- `make update-version ADDON=marketplace-repo-proxy VERSION=0.1.0-2 NO_TAG=yes`, then `make validate-versions`: passed.
- No tag `marketplace-repo-proxy/v0.1.0-2` locally or on origin; nothing pushed.

## Verification Results

- `node --test marketplace-repo-proxy/tests/js/*.test.mjs`: 58 tests, 58 pass, 0 fail (53 before this plan).
- `make check-admin-ui-sync check-admin-ui-rules`: exit 0; `pytest tests/test_js.py`: 1 passed (not skipped).
- `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q`:
  513 passed (run before the bump).
- `grep -cE '\b(get|post|put|patch|del|request)\(' views/info.mjs` = 0; `grep -c 'id: "info"' app.mjs` = 1;
  `grep -c '"info"' tests/test_js.py` = 1.
- Docs gate: `docs-ok`; `pre-commit run --files DOCS.md README.md CHANGELOG.md`: passed (prettier reflowed only the
  edited paragraphs); `grep -c '"last_fetch"' DOCS.md` = 1 (baseline 0); IPv4/e-mail count over the added doc lines
  = 0; `git diff --stat <merge-base> -- marketplace-repo-proxy/translations` empty; `grep -c 'mrp users' DOCS.md` = 16
  (baseline 13).
- Task 3: `bump-ok`, `bump-commit-ok`; the bump commit diff is exactly `-version: "0.1.0-1"` / `+version: "0.1.0-2"`;
  `git log -2 --format=%s -- marketplace-repo-proxy/` shows the bump first and the changelog commit second;
  `git status --porcelain -- marketplace-repo-proxy/` empty.
- Tracer gate: Task 1's `<verify>` is automated-only and was re-run green before Task 2.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

### Operator override

**1. [Operator rule] No rebase path (replaces D-28's rebase instruction)**
- The branch is already pushed and force-push is forbidden, so the plan's `git pull --rebase` was not used. Instead
  `git fetch origin main` ran before Task 2 and right before the bump, with the rule to stop before the bump if
  `origin/main` had new add-on commits. Both checks were empty, so the bump went ahead as planned.
- Because no rebase happened, the conditional post-rebase runs of Task 3 step 2 (GUI verify script, Phase 1 verify
  script) were not required and not run; no Docker build or container run happened in this plan (no Dockerfile or
  rootfs change).

### Auto-fixed Issues

**2. [Rule 1 - Bug] Further stale DOCS.md statements corrected**
- **Found during:** Task 2
- **Issue:** Beyond the sentences the plan names, DOCS.md said that the full URL is printed only by `mrp` ("Store URLs"
  and "Security notes"), that `mrp sync` is the only manual sync trigger, that a leaked URL is revoked with `mrp`
  only, and the `access.json` `created` row did not say that a page rotation resets it. All contradicted the built
  code.
- **Fix:** each sentence now names the management page as well; the `created` row states the rotation reset.
- **Files modified:** `marketplace-repo-proxy/DOCS.md`
- **Committed in:** `8f44c3c`

### Notes

- The plan's privacy check writes the docs diff to `/tmp/mrp-p3-docs.diff`; it was written to the session scratchpad
  instead (environment rule for temporary files). Same command, same result (0 matches).
- German navigation title "Anleitung" instead of "Info": the i18n test rejects identical German and English texts
  outside an allowlist, and the allowlist file is not in this plan's file list.

---

**Total deviations:** 1 operator override, 1 auto-fixed (doc correctness). **Impact:** no scope change.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 is complete on the branch with version 0.1.0-2; the manager pushes, merges and tags after the squash merge.
- If Phase 2 merges first, its version (expected 0.1.0-2) collides with this bump; the manager then bumps again to the
  next free subpatch at merge time.
- Open for the manager: Q-4 (rotate in both phases) and the `/data/supervisor.json` layout alignment (03-01 "Interface
  for Phase 2").

---
*Phase: 03-management-gui*
*Completed: 2026-11-19*

## Self-Check: PASSED

- Created files exist; commits `0466c06`, `8f44c3c`, `e5f14dd`, `e9996f6` are ancestors of HEAD.
