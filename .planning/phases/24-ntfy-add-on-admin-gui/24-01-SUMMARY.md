---
phase: 24-ntfy-add-on-admin-gui
plan: 01
subsystem: infra
tags: [ntfy, home-assistant-addon, ingress, python-stdlib, docker]
requires: []
provides:
  - ntfy/ add-on skeleton (image builds, runs ntfy on 8000 and the GUI on 8099 under one PID 1)
  - frozen shared contract (ntfy/app/contract.py, C1-C13) for plans 24-02..24-11
  - ingress-gated HTTP server with Router and API auto-registration seam
  - auth.db v10 test fixture builder and pytest path setup
affects: [24-02, 24-03, 24-04, 24-05, 24-06, 24-07, 24-08, 24-09, 24-10, 24-11]
actuals:
  tasks: 3
  commits: 3
key-files:
  created:
    - ntfy/config.yaml
    - ntfy/build.yaml
    - ntfy/Dockerfile
    - ntfy/run.sh
    - ntfy/app/contract.py
    - ntfy/app/web/server.py
    - internal/verify-ntfy-scaffold.sh
key-decisions:
  - "Bootstrap runs after `ntfy serve` starts (waits for auth.db), not before it (see Deviations)"
requirements-completed: [D-01, D-02, D-03, D-04, D-10, D-16, D-18]
completed: 2026-11-02
---

# Phase 24 Plan 01: ntfy add-on tracer and shared contract Summary

Tracer through every layer, proven by a real `docker build` and run, plus the frozen contract for waves 2-4.

## Commits

- `c1ef524` feat(ntfy): add add-on tracer (options to admin to ingress-gated GUI)
- `065fd2f` feat(ntfy): freeze shared contract and add test scaffolding
- `c6e41b8` feat(ntfy): add version scaffold, upstream tracking and render/gate tests

## Verification

- `bash internal/verify-ntfy-scaffold.sh` passes (run twice, containers `ntfy-w1-*`): build, `ntfy version 2.36.0`,
  health with schema 10, admin from options in `api/users`, 403 `ingress_only` for all routes without header and from a
  foreign peer, traversal blocked, `server.yml` mode 600 and no sentinel in file, logs or PID 1 cmdline, GUI kill gives
  a restart within 10 s, ntfy kill stops the container with exit 1.
- `pytest ntfy/tests`: 29 passed.
- `make validate-versions`, `make validate-addons`, `validate-addon-config.py ntfy`, `validate-dockerfile-args.sh`,
  shellcheck, yamllint, hadolint (strict ignore set, local binary), pre-commit on all committed files: green.
- `make update-version ADDON=ntfy VERSION=2.36.0 NO_TAG=yes` reports "Already at target version"; config.yaml and
  build.yaml unchanged.

## Deviations

1. **Bootstrap order (plan said: before `ntfy serve`).** The ntfy CLI refuses to run while auth.db does not exist
   (`auth-file does not exist; please start the server at least once to create it`); the spike's assumption was wrong.
   `run.sh` now starts `ntfy serve` first and runs `python3 -m app.bootstrap` in the background; `bootstrap` waits up to
   60 s for a readable auth.db with schema 10 (`wait_for_auth_db`). Bootstrap failure still never blocks delivery.
   Plans 24-09 (apply_options) and 24-11 must expect the admin/baseline to appear a moment after start, not before.
2. `internal/verify-ntfy-scaffold.sh` accepts `NTFY_VERIFY_PREFIX` and `NTFY_VERIFY_WORK` (defaults `ntfy-verify` and a
   mktemp dir) so parallel work can use its own container names and scratch directory.
3. `GET /` is served as `text/html` outside the `/static/` extension whitelist (the contract lists no `html`
   extension); `run.sh` carries `# shellcheck disable=SC2317,SC2329` for the trap-invoked `shutdown` (older
   shellcheck in pre-commit reports SC2317).
4. Executed inline in the worktree, not through a spawned gsd-executor: the harness isolation hook would have put the
   executor in a separate worktree, which conflicts with the manager's rules (commits on feat/ntfy-addon, worktrees
   only under `_worktrees/`). STATE.md, ROADMAP.md and state.json were not touched.

## Open points for waves 2-4

- `AuthDb.list_users()` has no `include_hash` yet and `AuthReader` is only structurally matched (24-02 completes it).
- The `/icon` route serves `static/icon.png`, which does not exist yet (index.html hides the broken image); 24-05 or
  24-10 should add icon.png/logo.png.
- DOCS.md, CHANGELOG.md, translations, root README entry and `internal/base-image-config.yaml` block are not part of
  this plan (see spike ntfy-image section 1); `make validate-addons` does not require them.
- `bashio::app.version` logs two ERROR lines per start outside the Supervisor (plain docker run); harmless.
