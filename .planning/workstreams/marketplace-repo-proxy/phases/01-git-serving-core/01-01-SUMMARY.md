---
phase: 01-git-serving-core
plan: 01
subsystem: infra
tags: [s6-overlay, lighttpd, git-http-backend, python, access-store, docker-verify]

requires: []
provides:
  - "s6-rc services init (oneshot, run.sh), lighttpd and sync (longruns) in marketplace-repo-proxy/rootfs"
  - "lighttpd smart-HTTP allow-list config with CGI stderr dropped (server.breakagelog = /dev/null)"
  - "Python package app/ with the module contracts Plans 02-04 code against (paths, jsonio, options, logsetup, urls, gitops, access, sync, init, cli)"
  - "/data/access.json writer AccessStore (flock + atomic replace, add, reconcile) and the /srv/git/access symlink tree"
  - "mrp CLI: users add (prints internal/public store URL to stdout only), reconcile"
  - "internal/verify-marketplace-repo-proxy.sh tracer against a local auth-checking upstream fixture"
affects: [01-02, 01-03, 01-04, 01-05, 01-06]

actuals:
  tokens: 16400
  tasks: 2
  commits: 3
plan_head_before: fa35e5dc8c9aefd84cdb61311c6ce8305687c99b
plan_head_after: 0aaf22b

tech-stack:
  added: [git, git-daemon (git-http-backend), lighttpd, python3 (Alpine apk, base amd64-base:3.24)]
  patterns:
    - "s6-rc services under rootfs/etc/s6-overlay with user-bundles.d/user/contents.d"
    - "PAT only in a from-scratch git child env (GIT_CONFIG_COUNT/KEY_0/VALUE_0)"
    - "New bare repo built in a temp dir and renamed after the first successful fetch"
    - "Authorization = symlink existence under /srv/git/access (dirs 0711)"
    - "Store URLs printed by the CLI with print(), never through logging"

key-files:
  created:
    - marketplace-repo-proxy/app/paths.py
    - marketplace-repo-proxy/app/jsonio.py
    - marketplace-repo-proxy/app/options.py
    - marketplace-repo-proxy/app/logsetup.py
    - marketplace-repo-proxy/app/gitops.py
    - marketplace-repo-proxy/app/access.py
    - marketplace-repo-proxy/app/sync.py
    - marketplace-repo-proxy/app/init.py
    - marketplace-repo-proxy/app/urls.py
    - marketplace-repo-proxy/app/cli.py
    - marketplace-repo-proxy/rootfs/etc/lighttpd/marketplace-repo-proxy.conf
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/{init,lighttpd,sync}/*
    - marketplace-repo-proxy/rootfs/usr/local/bin/mrp
    - marketplace-repo-proxy/tests/conftest.py
    - marketplace-repo-proxy/tests/test_urls.py
    - marketplace-repo-proxy/tests/test_cli.py
    - internal/verify-marketplace-repo-proxy.sh
  modified:
    - marketplace-repo-proxy/config.yaml
    - marketplace-repo-proxy/Dockerfile
    - marketplace-repo-proxy/run.sh

key-decisions:
  - "AccessStore.locked() is reentrant per thread (a nested flock on a second fd in one process would deadlock), so users add stores the entry and reconciles under one lock"
  - "sync sets umask 022 itself so bare repositories stay readable for the lighttpd user; init runs under umask 077 and sets /srv/git 0755, /srv/git/repos 0755, /etc/gitconfig 0644 explicitly"
  - "A --hash value already used by another entry is refused as invalid_hash; an unreadable options.json in the CLI prints error: options_invalid"
  - "A user label starting with '-' is taken as the positional user (argparse nargs='?' plus parse_known_args), so it reaches validation and fails as invalid_user instead of a usage error"

patterns-established:
  - "RED stubs: new modules get signature stubs in the test commit so RED fails on assertions, not import errors"

requirements-completed: [MRP-01, MRP-03, MRP-04, MRP-05]

coverage:
  - id: D1
    description: "Tracer: one user clones one private repository (--depth 1, upstream default branch, repository.yaml) through sync, access.json, symlink and lighttpd; PAT and full hash absent from the add-on log"
    requirement: MRP-03
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh"
        status: pass
    human_judgment: false
  - id: D2
    description: "Options schema in config.yaml (github_token password, sync_interval int(5,), public_url url?, repositories, register_local, api_enabled, log_level), no stdin key"
    requirement: MRP-01
    verification:
      - kind: other
        ref: "make validate-addons validate-versions && python3 internal/validate-addon-config.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "mrp users add stores a cli entry with a token_hex(16) hash, links it under the same lock and prints internal/public URLs to stdout only"
    requirement: MRP-04
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_cli.py"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_urls.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "PAT only in the git child environment; redactor and hash masking in the log formatter"
    requirement: MRP-05
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy.sh (step 7 log scan for PAT, base64 header, full hash)"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-11-18
status: complete
---

# Phase 1 Plan 01: Git serving core tracer and `mrp users add` Summary

**s6-supervised lighttpd + git-http-backend serves a PAT-synced bare repository under `/repo/{owner}/{repo}/{hash}`.
A second container clones it `--depth 1` from a local auth-checking fixture. `mrp users add` stores a random 128-bit
hash, links it and prints the store URL to stdout only.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-11-18T08:13:18Z
- **Completed:** 2026-11-18T08:26Z
- **Tasks:** 2 (tracer + TDD task)
- **Files modified:** 34 (31 created, 3 modified)

## Accomplishments

- Tracer green on the first run and again at the tracer feedback gate:
  `bash internal/verify-marketplace-repo-proxy.sh` builds the image locally and starts the auth-checking upstream
  fixture, which answers 401 without the PAT. The proxy syncs the upstream default branch `main`, init links the
  hand-seeded `access.json` user under `/srv/git/access` (mode 711) and `git clone --depth 1` from a client container
  returns `repository.yaml`. The add-on log holds neither the PAT nor its base64 header form nor the full hash.
- Module contracts from the plan `<interfaces>` block exist with exactly those names (paths, jsonio, options,
  logsetup, urls, gitops, access, sync, init, cli).
- `mrp users add` / `mrp reconcile` with 18 passing unit tests (5 URL, 13 CLI).

## Task Commits

1. **Task 1: tracer, one user clones one private repository end to end:** `b655c2c` (feat)
2. **Task 2: `mrp users add` with store URL output (TDD):**
   - RED: `a87da40` (test). Failing tests plus interface stubs.
   - GREEN: `0aaf22b` (feat). REFACTOR: none needed.

## TDD Gate Compliance

- RED `a87da40`: `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest
  marketplace-repo-proxy/tests -q --junitxml=...`. Exit 1, 18 tests, 18 failed, all with `AssertionError`. Target
  `test_users_add_prints_internal_url_and_links`. Classifier `gsd-tools check tdd-red-evidence` returned
  `RED_EVIDENCE_OK` (`target_test_failed`).
- semanticAssessment: the target ran and failed on `assert 1 == 0`, because the stub `cli.main` returns 1 and does not
  implement `users add`. That is the planned missing behaviour, not a collection, import or fixture fault.
- GREEN `0aaf22b`: same command, 18 passed.

## Verification Results

| Command | Result |
| --- | --- |
| `bash internal/verify-marketplace-repo-proxy.sh` (2 runs: before the Task 1 commit and at the tracer gate) | exit 0, all 7 steps `✓`, final tracer line |
| `make validate-addons validate-versions` and `python3 internal/validate-addon-config.py` | exit 0 |
| `shellcheck -s sh` on run.sh, lighttpd/sync `run`+`finish` and `mrp`; `shellcheck` on the verify script | clean |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 18 passed |
| `pre-commit run --files` on all 34 plan files | 0 failed |
| `docker build` + `docker run --entrypoint mrp ... --help` / `reconcile` (smoke, Task 2) | OK, `0 access links` |

All Task 1 and Task 2 acceptance greps pass. Results: Dockerfile package line 1, `COPY run.sh` 1, `^CMD` 0. config.yaml
password/int/`8080/tcp: null`/version 1 each. build.yaml and README unchanged, no `stdin` key. `breakagelog` 1, global
`cgi.assign` 1, shebangs exact. The override name appears in no manifest or rootfs file and once in `gitops.py`.
`gitops.py` has `GIT_CONFIG_VALUE_0` twice and `os.environ` 0 times. File modes are 100755 for the scripts.
`token_hex(16)` appears once, `cli.py` has no `import logging`, the Dockerfile is unchanged in Task 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RED commit carries interface stubs**

- **Found during:** Task 2 (RED)
- **Issue:** `app.urls`, `app.cli`, `new_hash` and `AccessStore.add` did not exist. Tests importing them would fail at
  collection, and tdd.md rejects that as INVALID_RED.
- **Fix:** the `test(01-01)` commit adds signature stubs that return empty or wrong values, so every test fails on its
  assertion. GREEN replaced all stubs.
- **Files:** `marketplace-repo-proxy/app/{urls,cli,access}.py`
- **Commit:** `a87da40`

**2. [Rule 1 - Bug] Nested `AccessStore.locked()` would deadlock**

- **Found during:** Task 2 (GREEN)
- **Issue:** `users add` must add and reconcile in one locked operation. `add()` and `reconcile()` each take the lock,
  and a second `flock` on a new fd in the same process blocks forever.
- **Fix:** `locked()` tracks the lock depth per thread and only the outermost level opens and flocks the lock file.
- **Files:** `marketplace-repo-proxy/app/access.py`
- **Commit:** `0aaf22b`

**3. [Rule 1 - Bug] A user label starting with `-` was a usage error, not `invalid_user`**

- **Found during:** Task 2 (GREEN, `test_invalid_user_label_is_refused`)
- **Fix:** `user` is `nargs="?"`, `main` uses `parse_known_args` and takes a single leftover argument as the label.
  Missing or extra arguments still exit 2.
- **Files:** `marketplace-repo-proxy/app/cli.py`
- **Commit:** `0aaf22b`

**4. [Rule 2 - Missing critical] Explicit modes for lighttpd-readable paths**

- **Found during:** Task 1
- **Issue:** init runs under umask 077 (plan). Without explicit modes, `/srv/git` and `/etc/gitconfig` would be
  unreadable for the `lighttpd` user. That breaks `safe.directory` and traversal. The umask of the sync longrun is not
  controlled by the plan, and bare repositories must stay readable.
- **Fix:** init sets `/srv/git` and `/srv/git/repos` to 0755 and `/etc/gitconfig` to 0644. sync sets `umask 022`.
- **Files:** `marketplace-repo-proxy/app/init.py`, `marketplace-repo-proxy/app/sync.py`
- **Commit:** `b655c2c`

**Total deviations:** 4 auto-fixed (1 blocking, 2 bugs, 1 missing critical). **Impact:** none on contracts. The names
and signatures in `<interfaces>` are unchanged.

### Additions within plan scope (not deviations)

- `SafeFormatter` scrubs registered secrets before it masks hashes, so a secret containing a 32-hex run is still
  scrubbed in full.
- The sync redactor registers the raw PAT, the full header value and the base64 part on its own.
- init logs one info line `access links: N (hostname H)`. It holds no hash and no URL. The full startup log is still
  Plan 04's job.
- `AccessStore.add` refuses a `--hash` that another entry already uses (`invalid_hash`). A generated hash is re-drawn
  on collision. The CLI prints `error: options_invalid` for unreadable options.

## Issues Encountered

- Executor process slip during Task 2: running `source` on the gsd-run resolver *markdown* file started an interactive
  `bash` that waited on stdin. The executor killed its own three hung shell processes. The working tree and the repo
  were unaffected (git status unchanged), and the RED evidence was then recorded with a direct command.
- `docker build` prints the legacy-builder deprecation warning (buildx missing on the host). The build itself is
  unaffected.

## Known Stubs

None. The RED stubs from `a87da40` were all replaced in `0aaf22b`.

## Next Phase Readiness

- Ready for 01-02 (status.json, trigger file, error classification), 01-03 (CLI list/url/revoke/sync) and 01-04
  (startup log, init failure policy, options/logsetup tests, CI job).
- Requirement IDs MRP-01/03/04/05 are also declared by sibling plans. The shared-ID gate (`requirements.ready-ids`)
  keeps them open until those plans finish.

## Self-Check: PASSED

- All key files exist on disk. Commits `b655c2c`, `a87da40` and `0aaf22b` are ancestors of HEAD.
