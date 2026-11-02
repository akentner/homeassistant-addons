---
phase: quick-261102-swd
plan: 01
subsystem: haos-monitor
tags: [admin-ui, preact, python-skeleton, ingress-gate, two-ports, docker, ci]
requires:
  - admin-ui lib and skeleton 0.5.0 (make sync-admin-ui)
  - haos-monitor status.sh, hosts file and logs (unchanged)
provides:
  - haos-monitor GUI server on the admin-ui skeleton (internal port 8100, ingress gate, no public route)
  - Preact status page (German/English, light/dark) with one card per host
  - haos-monitor CI job and make test-haos-monitor
  - haos-monitor 0.7.0-0
affects:
  - haos-monitor/Dockerfile, run.sh, config.yaml (ingress_port 8100)
  - .github/workflows/lint.yml (pure append), Makefile
tech-stack:
  added: [python3 (apk, stdlib only), vendored admin-ui lib 0.5.0 and skeleton 0.5.0]
  patterns: [two ports (ingress GUI plus busybox machine endpoints), status.sh as the single data producer, text-node-only rendering]
key-files:
  created:
    - haos-monitor/app/ (hosts.py, status.py, incidents.py, main.py, web/server.py, web/static/**, generated web/admin_ui and web/static/vendor/admin-ui)
    - haos-monitor/tests/ (7 pytest modules, tests/js with 4 node suites, verbatim fakedom.mjs and a11y_audit.mjs)
    - haos-monitor/.dockerignore
    - .planning/quick/261102-swd-haos-monitor-admin-ui/261102-swd-verify.sh
  modified:
    - haos-monitor/Dockerfile, run.sh, config.yaml, build.yaml, README.md, DOCS.md, CHANGELOG.md
    - README.md, Makefile, .github/workflows/lint.yml
  deleted:
    - haos-monitor/index.html
key-decisions:
  - "status.sh stays the only data producer (argv list, minimal env, 10 s timeout, 64 KiB cap); one aggregate GET api/overview without request parameters"
  - "No public routes: machine endpoints stay on busybox httpd 8099, the GUI server answers 403 ingress_only to everything without ingress"
  - "Server clock (now_ms) drives boot time and the Updated line, never the browser clock"
duration: not recorded
completed: 2026-11-02
status: complete
commits: 4
plan_head_before: 106a02d5417389fd94ad7c36bc0d9d299ec639a5
plan_head_after: 334d992439edf392e97748577fc3b9b7e288b361
actuals:
  tokens: 39000
  tasks: 11
  commits: 5
---

# Phase quick-261102-swd Plan 01: haos-monitor on the admin-ui blueprint stack Summary

The haos-monitor status page is rebuilt as a Preact page on the synced admin-ui lib, served by a small Python server
(skeleton 0.5.0) behind the ingress gate on the internal port 8100, while `/api/status.json`, `/cgi-bin/status`,
`/api/metrics.txt`, `/cgi-bin/metrics`, `/api/hosts.json` and `/api/incidents.json` stay on busybox httpd 8099 exactly as
before (version 0.7.0-0).

`commits:`, `plan_head_before:` and `plan_head_after:` in the frontmatter are the measured triple at the time this file
was written (`git rev-list --count 106a02d..334d992` is 4). The fifth commit, the verify script together with this
SUMMARY, follows `plan_head_after`; `actuals.commits` counts it.

## Commits (branch `worktree-agent-a5355e69ac6972ae2`, no push, no tag)

| # | Hash      | Message                                                                  |
| - | --------- | ------------------------------------------------------------------------ |
| 1 | `37771aa` | feat(haos-monitor): add the GUI server on the admin-ui skeleton          |
| 2 | `b43d758` | feat(haos-monitor): rebuild the status page on the admin-ui Preact lib   |
| 3 | `cf0259e` | feat(haos-monitor): serve the GUI behind the ingress gate on port 8100   |
| 4 | `334d992` | feat(haos-monitor): CI job, docs and version 0.7.0-0                     |
| 5 | see below | test(haos-monitor): staged verification for the admin-ui migration       |

Commit 5 contains the verify script and this SUMMARY; its hash is in the orchestrator report (it cannot contain itself).

## What was built

- Wave 1 (commit 1): `make sync-admin-ui ADDON=haos-monitor` produced both copies (lib and skeleton 0.5.0); `hosts.py`
  (slug `fullmatch [a-z0-9_]+`, first duplicate wins, control characters stripped), `status.py` (argv list, minimal
  environment `PATH`/`LOGDIR`/`HOSTS_FILE`/`ENV_FILE`, timeout, 64 KiB cap, whitelist of 22 numeric and 5 text fields),
  `incidents.py` (bounded backward block scan, 24 MiB cap), `web/server.py` (`GET /api/overview`, no public route,
  `hosts_unavailable` 503) and `main.py` (`python3 -m app.main`, port 8100). 191 pytest tests.
- Wave 2 (commit 2): `model.mjs`, German and English strings (key and placeholder parity enforced), `HostCard`,
  `Overview` with `useOverview` (10 s poll, overlap guard, last data kept on errors), `app.mjs`, `index.html`, token-only
  `app.css`. 47 node tests plus static-tree pytest checks.
- Wave 3 (commit 3): Dockerfile with `python3` and the app, `.dockerignore`, `run.sh` supervises the GUI next to httpd,
  `ingress_port: 8100` (`ports` unchanged), `index.html` removed, scaffold test. Local docker build, hadolint and
  `make validate-dockerfiles` passed before the commit; the container smoke showed the gated GUI on 8100 next to the
  unchanged 8099 endpoints.
- Wave 4 (commit 4): lint.yml job `haos-monitor` appended (first 244 lines byte-identical to the base), `make
  test-haos-monitor`, DOCS (Architecture, Web UI, Development), CHANGELOG `[0.7.0]`, READMEs, version 0.7.0-0 / 0.7.0 /
  v0.7.0 through `make update-version ADDON=haos-monitor VERSION=0.7.0 NO_TAG=yes` (no tag created).
- Wave 5 (commit 5): `261102-swd-verify.sh` (stages static, server, frontend, ci, docker).

## Verification results

Full run of `261102-swd-verify.sh` (no stage argument) on the final tree, base `40fab86`, exit 0:

| Stage    | Result | Notes                                                                                                         |
| -------- | ------ | ------------------------------------------------------------------------------------------------------------- |
| static   | OK     | no diff in admin-ui/secrets-sync; 8 legacy files byte-identical; five `OK` sync lines; config 8100/8099/0.7.0-0 |
| server   | OK     | pytest haos-monitor/tests (216 passed); informational run of the status contract in ubuntu (mawk, dash): pass |
| frontend | OK     | node 47 passed; `make test-admin-ui` still green; rules scanner clean                                          |
| ci       | OK     | job `haos-monitor` last after `secrets-sync`, read-only permissions, `lint-results.needs` untouched           |
| docker   | OK     | new and baseline image built, hadolint, parity on 8099, gate on 8100, overview content, leak guard, supervision |

`STAGE docker OK` and `ALL STAGES OK` were seen from the full run. Final gate: `make test-haos-monitor` (47 node, 216
pytest), `make test-admin-ui` (inside the verify run), `make check-admin-ui-sync check-admin-ui-rules validate-versions
validate-dockerfiles` green, `pre-commit run --from-ref 40fab86 --to-ref HEAD` (all hooks including gitleaks, zizmor,
actionlint, hadolint, shellcheck, prettier, markdownlint) green. Every commit passed its hooks (no `--no-verify`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree did not start at 106a02d**
- **Found during:** start. The isolated worktree was created from `40fab86`; the plan file was missing.
- **Fix:** `git merge --ff-only 106a02d` (a pure fast-forward, nothing rewritten). The five commits therefore sit on the
  agent branch `worktree-agent-a5355e69ac6972ae2`, not on `feat/haos-monitor-admin-ui` (that branch is checked out in
  another worktree). The orchestrator must fast-forward or merge it.

**2. [Rule 1 - Bug] `docker run -e` does not reach `run.sh` in this base image**
- **Found during:** Task 7 smoke. With the HA base image's s6 init a plain `#!/bin/sh` CMD does not inherit the container
  environment, so `-e HAOS_MONITOR_INGRESS_REMOTE=127.0.0.1` had no effect (403 even with the header).
- **Fix:** smoke and the verify docker stage start both containers with `--entrypoint sh -c '<export>; exec /run.sh'`
  (export only for the new image). `run.sh` stays `#!/bin/sh` as planned; production is unaffected (the override is a test
  variable).
- **Related finding (no action):** the Dockerfile `ENV` lines (`PYTHONUNBUFFERED`, `PYTHONPATH`) are likewise not visible
  to the s6-started `run.sh`. The GUI does not depend on them (`cd /opt/haos-monitor-gui` plus `-m`, explicit flushes).

**3. [Rule 1 - Bug] i18n scanner flagged `tt(row.labelKey)`**
- **Issue:** the plan wants literal `labelKey:` properties in the model tables, but rendering them calls `tt(row.labelKey)`,
  which the dynamic-key rule rejects. **Fix:** the scanner in `tests/js/i18n.test.mjs` sanctions exactly
  `<name>.labelKey` / `<name>.titleKey` arguments (the literals are scanned where they are spelled out); everything else
  non-literal still fails, with positive and negative scanner samples.

**4. [Rule 3 - Blocking] Status runner uses `Popen` instead of `subprocess.run(capture_output=True)`**
- To enforce the 64 KiB cap while reading (not after buffering everything) and to kill the whole process group on a
  timeout (`start_new_session`), stdout is read through a selector loop. Behaviour matches the plan (argv list, no shell,
  `DEVNULL` stdin, timeout, cap, strict UTF-8, minimal environment); `stderr` goes to `DEVNULL`.

**5. [Rule 3 - Blocking] Verify script adjustments**
- The baseline page has `id="hosts"` (the plan said `id="app"`, which only the new page has); the check uses `id="hosts"`.
- Incident parity compares the first INCIDENT line without its timestamp (log timestamps differ per container) instead of
  demanding identical files.
- Found while hardening: a `grep` with a pattern starting with `-----` was parsed as an option and made the PEM-marker
  checks vacuous; fixed with `--`, and the script now proves the scanner on a seeded marker.

**6. [Process] Tests-first order**
- Task 1 followed the tracer flow (tests red, sync, green). For Tasks 2 and 3 the hardened modules were written before
  their test files, then the tests were written and passed on the first run; this is a TDD-order deviation, not a
  coverage gap (hostile slugs, injection safety, minimal environment, timeout, size cap, contract with the real
  `status.sh` are all tested).

## Auth gates

None.

## Known Stubs

None. No placeholder text, hardcoded empty data flowing to the UI or skipped tests.

## Threat Flags

None beyond the plan's register. The new listener on 8100 is the planned, gated surface (T-261102-01); no new public
route, endpoint with parameters or file access beyond the hosts file and the logs.

## Deferred / out of scope

- `make docker-build-check` reports DL3008 warnings for `authentik/Dockerfile` and `litellm/Dockerfile` (apt-get pins).
  Both are untouched, pre-existing and unrelated; haos-monitor passes hadolint with the repository ignore list.
- The `Error: Bad file descriptor` line during start is already in the baseline logs (verify script reports it as info);
  not caused by this change.
- `internal/base-image-config.yaml` still does not list haos-monitor (follow-up, finding P-09).

## Stale statements in admin-ui/DOCS.md (not edited, P-11)

Editing them would rebuild and re-version the admin-ui add-on for a text change. To fix in a follow-up:

- "Migration paths > secrets-sync": migrated by PR #87 (skeleton, Preact, tests in CI, public routes).
- "Migration paths > haos-monitor": done here; the ingress gate is used, no public routes, two ports.
- "Follow-up": "First consumer of `public=True`: the secrets-sync manager", "secrets-sync rewrite on Preact/htm" and
  "haos-monitor rebuild on the blueprint stack" are done.
- "Follow-up": "Run the ntfy and secrets-sync frontend tests in CI" is now only open for ntfy (secrets-sync and haos-monitor
  have CI jobs). "ntfy switch-over" and "Add `haos-monitor` to `internal/base-image-config.yaml`" remain valid.

## Lib needs

None found. The blueprint lib and skeleton were used unchanged (0.5.0); `git diff 40fab86 -- admin-ui secrets-sync` is
empty. One note for the lib's own test scanner: it flags `tt(item.titleKey)`-style calls in consumer code, which this add-on
sanctions only for `labelKey`/`titleKey` properties in its own scanner.

## Self-Check: PASSED

- Created files exist: `haos-monitor/app/main.py`, `haos-monitor/app/hosts.py`, `haos-monitor/app/status.py`,
  `haos-monitor/app/incidents.py`, `haos-monitor/app/web/server.py`, `haos-monitor/app/web/static/app.mjs`,
  `haos-monitor/app/web/static/views/host-card.mjs`, `haos-monitor/tests/test_addon_scaffold.py`,
  `.planning/quick/261102-swd-haos-monitor-admin-ui/261102-swd-verify.sh`.
- Commits 37771aa, b43d758, cf0259e and 334d992 are ancestors of HEAD.
