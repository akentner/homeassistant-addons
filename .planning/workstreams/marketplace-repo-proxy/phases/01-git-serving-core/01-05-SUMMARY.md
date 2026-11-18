---
phase: 01-git-serving-core
plan: 05
subsystem: testing
tags: [docker-verify, e2e, lighttpd, git-http-backend, secret-hygiene, access-watch, status-json]

requires:
  - phase: 01-git-serving-core
    provides: "01-01 tracer verify script, s6 services, mrp users add; 01-02 status.json and trigger; 01-03 revoke, mrp sync, access-watch; 01-04 startup log"
provides:
  - "internal/verify-marketplace-repo-proxy.sh: one-command Docker proof of ROADMAP Phase 1 criteria 1-5 (86 checks) against a local auth-checking upstream fixture"
  - "Helpers field_of/status_of/head_of/wait_field (status.json), upstream_commit, csh (client container), expect_code (HTTP matrix), needle-file scanners"
  - "First container proof of mrp (add/--hash/revoke/sync), access-watch (running, clean environment, hand edit revoked within 5 s) and the startup log"
affects: [01-06, 02-supervisor-integration]

actuals:
  tokens: 8800
  tasks: 2
  commits: 2
plan_head_before: e07f966475c46cf74f0fb5f11d8323e4cabab5c2
plan_head_after: 15aeba7d281606c28cd464688f2c4d9499bae6d8

tech-stack:
  added: []
  patterns:
    - "Status waits read /data/status.json with python3 json inside the proxy, never bare-repo internals"
    - "Negative checks assert the failure reason (push: HTTP 403; branch clone: remote branch not found), not just a non-zero exit"
    - "Secret scans read needles from 0600 files (grep -F -f); every /proc scan has a positive control"
    - "Secrets travel to containers on stdin (options rewrite, needles), never in an argv"

key-files:
  created: []
  modified:
    - internal/verify-marketplace-repo-proxy.sh

key-decisions:
  - "01-05: /proc scans prove themselves with positive controls: the cmdline scan must find the app.watch argv, the environ scan must find SUPERVISOR_TOKEN in the sync service's environment"
  - "01-05: the wrong-PAT options rewrite and all needles reach the containers via stdin, so no secret appears in a process argv during the run"

patterns-established:
  - "expect_code <code> <label> <curl args>: labels never contain a hash, so the script's own output stays shareable"

requirements-completed: [MRP-03, MRP-05, MRP-06]

coverage:
  - id: D1
    description: "Criterion 1: upstream default branch (only main served although upstream has dev), configured non-default branch stable (ls-remote HEAD + refs/heads/stable at the upstream SHA, STABLE marker, --branch main fails), upstream change after mrp sync visible to fetch and fresh clone"
    requirement: MRP-06
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (steps 3-7, 9)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Criterion 2: 404/403 matrix (19 requests) and git push refused with HTTP 403"
    requirement: MRP-03
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (step 8)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Criterion 3: ?ref=main&tab=readme clone and info/refs, clone --branch main, ls-remote --heads only main, fetch --update-shallow --depth 1"
    requirement: MRP-03
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (steps 6, 8)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Criterion 4: mrp users revoke gives 404 at the next request (bob keeps 200); hand edit of access.json gives 404 within 5 s via access-watch (dave, erin keep 200)"
    requirement: MRP-06
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (step 10)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Criterion 5: no PAT/base64 header/full hash in docker logs, /srv/git, repo configs, status.json, clones, /proc cmdline/environ; lighttpd and access-watch environments clean"
    requirement: MRP-05
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (steps 11, 14)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Status codes end to end (ok, no_repository_yaml, not_found, auth_failed after restart with wrong PAT while the last good mirror serves) and the startup log with masked URLs"
    requirement: MRP-06
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (steps 4, 12, 13)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-18
status: complete
---

# Phase 1 Plan 05: Full Phase 1 Docker proof Summary

**`bash internal/verify-marketplace-repo-proxy.sh` now builds the image, starts an auth-checking upstream fixture with
four repositories and proves ROADMAP Phase 1 criteria 1-5 in 86 `✓` checks, ending with
`✓ marketplace-repo-proxy Phase 1 verified (criteria 1-5)`. It never contacts GitHub (criterion 6).**

## Performance

- **Duration:** about 8 min (excluding reading)
- **Started:** 2026-11-18T14:10:16Z
- **Completed:** 2026-11-18T14:18Z
- **Tasks:** 2
- **Files modified:** 1 (`internal/verify-marketplace-repo-proxy.sh`, 186 → 616 lines)

## Accomplishments

- Static guards before any Docker call: `8080/tcp: null`, `github_token` of type `password`, the override variable name
  absent from `config.yaml`, `build.yaml`, `Dockerfile` and `rootfs`, `server.breakagelog = "/dev/null"`, no
  `debug.*` lighttpd option, `#!/bin/sh` for the `lighttpd` and `access-watch` run scripts.
- Fixture: `example-org/private-addons` (main plus an upstream-only `dev`), `example-org/branched` (default `main`,
  configured `stable` with a `STABLE` marker), `example-org/no-meta` (no repository.yaml), `example-org/missing`
  (never created). `upstream_commit` pushes new commits inside the fixture.
- Criterion 1: status.json reaches `ok`/`ok`/`no_repository_yaml`/`not_found`, `branch_source` is `configured` for
  `stable` and `upstream_default` for private-addons. `ls-remote --heads` lists only `refs/heads/main`. For the
  configured branch `ls-remote` lists exactly `HEAD` and `refs/heads/stable` at the upstream SHA, a clone checks out
  `stable` with its marker and `--branch main` fails with "Remote branch main not found". After an upstream push and
  `mrp sync`, `head` and `refs_changed` update within 30 s, and both a fetch and a fresh clone see the new commit.
- Criterion 2: the full RESEARCH Pattern 3 matrix (3 × 200, 14 × 404 including the dangling-link user carol and both
  traversal forms, 2 × 403). `git push` fails with HTTP 403.
- Criterion 3: clones with `?ref=main&tab=readme`, with `--branch main` (the Supervisor's `#main` form), and
  `fetch --update-shallow --depth 1` work. A clone without `--depth` is not shallow.
- Criterion 4: `mrp users revoke` gives 404 on the very next request while bob keeps 200. A hand edit of
  `/data/access.json` (json rewrite plus `os.replace`) gives 404 for bob within 5 s; dave and erin keep 200.
- Status codes: after a restart with a wrong PAT, private-addons becomes `auth_failed`, the log has the warning, and
  dave's URL still returns 200 from the last good mirror.
- Startup log (Plan 04, positive control): after the restart the log lists
  `user dave -> http://mrp-verify-proxy:8080/repo/example-org/private-addons/xxxx… | public https://addons.example.invalid/...xxxx…`.
- Criterion 5: needles (both PATs, their base64 `x-access-token:` headers, five full hashes) are read from 0600 files.
  None of them is in `docker logs`, `/srv/git/**`, `/data/status.json` or the served clones. No log line has a 32-hex
  value after `/repo/` or `/access/`. Every bare repo config has no `Authorization`, no `mirror`, a URL without
  userinfo, `pushurl=no-push://disabled`, `http.receivepack=false` and `http.getanyfile=false`. No `/proc/*/cmdline`
  and (with `docker exec --privileged`) no `/proc/*/environ` holds a PAT needle. lighttpd's environment has no PAT, no
  `SUPERVISOR_TOKEN` sentinel and no override variable; the `app.watch` environment has neither of the last two.
- First container proofs of Plans 01-04: `mrp users add` (with and without `--hash`), `mrp users revoke`, `mrp sync`,
  the running `access-watch` longrun with a clean environment, and init's reconcile of the seeded `access.json` user.

## Task Commits

1. **Task 1: clone, query tolerance, #branch, 404/403 matrix, push refusal, upstream change, revocation:** `ff2962c`
   (test)
2. **Task 2: auth-failure handling and secret hygiene:** `15aeba7` (test)

## Verification Results

| Command | Result |
| --- | --- |
| `bash internal/verify-marketplace-repo-proxy.sh` (Task 1 version, 3 runs) | exit 0, 66 `✓`, 0 `✗` |
| `bash internal/verify-marketplace-repo-proxy.sh` (final) | exit 0, 86 `✓`, 0 `✗`, last line `✓ marketplace-repo-proxy Phase 1 verified (criteria 1-5)` |
| `docker build` of the add-on image (inside the script) | succeeded; no Dockerfile change in this plan |
| `shellcheck internal/verify-marketplace-repo-proxy.sh` | clean |
| `pre-commit run --files internal/verify-marketplace-repo-proxy.sh` (incl. gitleaks) | all hooks Passed or Skipped |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 207 passed |
| Leftovers after every run | no `mrp-verify-*` container or network; work dir and needles removed |

Acceptance greps: `mrp users revoke` 4, `update-shallow` 3, `example-org/branched` 2, `refs/heads/stable` 4,
`app.watch` 9, `never run it in two worktrees at the same time` 1, `docker exec --privileged` 4, `needles` 22,
`auth_failed` 4, `user dave -> ` 1. The file has 616 lines (min 300) and 16 `status.json` references.

## Decisions Made

- `/proc` scans carry positive controls: the cmdline scan must list the `app.watch` process and the environ scan must
  list the sync service (which gets `SUPERVISOR_TOKEN` through `with-contenv`). A scan that reads nothing fails.
- The wrong-PAT options file and all needle files reach the containers on stdin, so no secret is in any argv.
- Negative checks also assert the reason: `git push` must fail with `returned error: 403`, and `clone --branch main`
  of the stable-only URL must fail with `Remote branch main not found`.

## Deviations from Plan

None - plan executed exactly as written. No product file under `marketplace-repo-proxy/` changed: every check passed
against the code from Plans 01-04.

Additions within plan scope (not deviations):

- Extra checks beyond the listed ones: init's link for the seeded user (mode 0711 access root), the upstream `dev` and
  `HEAD -> main` sanity checks, the override WARNING, and the bare-repo count (3).
- `# shellcheck disable=SC2016` applies to the whole file, because the `csh` snippets are single-quoted on purpose
  (`$1` expands in the client container).

## Issues Encountered

- The pre-commit shellcheck version flags SC2015 (`A && B || C`), which the host shellcheck did not. Rewritten as an
  `if` before the Task 1 commit.

## Known Stubs

None.

## Next Phase Readiness

- Phase 1 criteria 1-6 are proven by one command. Plan 06 (docs, wave 4) can reference the script and its final line.
- Phase 2 (Supervisor integration on the production host) still has to exercise the Supervisor's own `#branch` parsing
  and the add-on hostname in a live store; this script proves the `git clone --branch` call it makes.

## Self-Check: PASSED

- `internal/verify-marketplace-repo-proxy.sh` exists (616 lines). Commits `ff2962c` and `15aeba7` are ancestors of
  HEAD.
