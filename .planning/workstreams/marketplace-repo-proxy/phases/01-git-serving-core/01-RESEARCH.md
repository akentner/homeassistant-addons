# Phase 1: Git serving core - Research

**Researched:** 2026-11-17
**Domain:** HA add-on container (s6-overlay v3), lighttpd + `git http-backend` smart HTTP, git mirroring with a PAT,
JSON state contracts, Docker-based verification
**Confidence:** HIGH (core mechanics were reproduced in a throwaway prototype on `amd64-base:3.24` in this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Server
- **D-01:** Git is served by lighttpd + `git http-backend` (smart HTTP only). The lighttpd config from SPIKE.md
  ("Server: lighttpd + git http-backend") is the reference: `mod_rewrite`, `mod_alias`, `mod_setenv`, `mod_cgi`; empty
  docroot `/var/empty`; port `8080`; runs as user/group `lighttpd`; the alias to `git-http-backend` is mapped only
  inside the positive allow-list condition for `info/refs` and `git-upload-pack` under
  `/repo/<owner>/<repo>/<32 hex>/` (a negated `url.access-deny` block does not work, see SPIKE pitfall).
- **D-02:** Port `8080/tcp` stays unpublished by default (`8080/tcp: null`). No TLS inside the add-on.

#### URL scheme
- **D-03:** Store URL path is `/repo/<owner>/<repo>/<hash>`; `<owner>` is the GitHub owner/organisation, `<repo>` the
  GitHub repository name, `<hash>` 32 lowercase hex chars. Unknown owner, repo or hash all give the same 404.
- **D-04:** Query parameters on the store URL are accepted and ignored, via the two `url.rewrite-once` rules from
  SPIKE.md. `#branch` is handled client-side (the Supervisor strips it before calling git) and must keep working.

#### Access tokens and disk layout
- **D-05:** One access token (hash) per `(repository, user label)`: random 128 bit from `/dev/urandom`, 32 lowercase hex,
  generated once, persisted in `/data/access.json`. Random, not HMAC-derived.
- **D-06:** Disk layout: bare repository `/srv/git/repos/<owner>/<repo>.git` (written only by the sync service); one
  symlink per token `/srv/git/access/<owner>/<repo>/<hash> -> /srv/git/repos/<owner>/<repo>.git`;
  `GIT_PROJECT_ROOT=/srv/git/access`. Revoking removes the symlink and takes effect at the next request without a
  lighttpd reload. The symlink tree is rebuilt from `/data/access.json` at every start, so stray symlinks cannot
  survive.
- **D-07:** Each `access.json` entry carries repository, user label, hash, created timestamp and source
  (`gui`/`api`/`system`) (MRP-04).

#### Upstream credential
- **D-08:** One fine-grained GitHub PAT (`Contents: read-only`) in the `github_token` option (schema type `password`).
  It is passed only at fetch time and only through the environment: `GIT_CONFIG_COUNT=1`,
  `GIT_CONFIG_KEY_0=http.extraHeader`, `GIT_CONFIG_VALUE_0="Authorization: Basic base64(x-access-token:<token>)"`.
  Never in a remote URL, never in a repository config, never in lighttpd's environment or process tree.
- **D-09:** 401/403 from upstream produce a clear log line and status code `auth_failed` (expired or revoked token),
  without the token.

#### Sync
- **D-10:** One bare repository per source, created with `git init --bare` plus an explicit fetch refspec
  `+refs/heads/<branch>:refs/heads/<branch>` (configured branch; default: upstream default branch) and `HEAD` set to it.
  Not `git clone --mirror`; no `remote.origin.mirror`; `remote.origin.pushurl` set to an invalid value; no other refs
  (`refs/pull/*`, other branches).
- **D-11:** `git fetch --prune` (refs update after objects are in place, so concurrent `upload-pack` sees a consistent
  state).
- **D-12:** `sync_interval` in minutes, default 15, minimum 5. Besides the interval, the sync loop watches a trigger
  file (the Phase 3 GUI uses it for "Sync now").
- **D-13:** Sync runs as its own s6 service, separate from lighttpd; it is the only process holding the PAT.
- **D-14:** Sync state is written to `/data/status.json` with stable status codes `ok`, `auth_failed`, `not_found`,
  `no_repository_yaml` (MRP-02).

#### Read-only guarantees
- **D-15:** Each bare repository sets `http.receivepack=false` and `http.getanyfile=false`. Repositories are owned by
  root and readable for `lighttpd`; `/etc/gitconfig` lists `safe.directory` for the repositories (otherwise git refuses
  with "dubious ownership"). Push and `git-receive-pack` are refused (403); dumb `info/refs` returns 403.

#### Options
- **D-16:** Options schema (MRP-01): `github_token` (password), `sync_interval` (default 15, minimum 5), `public_url`
  (optional, empty = internal only), `repositories` (list of `{repository: owner/repo, branch: optional}`),
  `register_local` (default true), `api_enabled` (default false), `log_level`. `register_local` and `api_enabled` are
  schema-only in this phase; their behaviour comes in Phases 2 and 4. Users and hashes never appear in the options.

#### Logging and secrets
- **D-17:** The PAT never appears in logs, the options export, a repository config, lighttpd's environment or the served
  data. No full hash ever appears in logs. The startup log lists user labels and **masked** store URLs only (MRP-05).
  Note: SPIKE.md "Read-only guarantees" item 6 says "log the store URLs once at startup"; MRP-05 is the later and stricter
  rule and wins.

#### Tests
- **D-18:** Tests and `internal/verify-marketplace-repo-proxy.sh` use a local upstream fixture, never real GitHub. A
  test-only upstream override makes that possible; it must not be reachable through the add-on options in production.
- **D-19:** The verify script builds the image and proves ROADMAP Phase 1 success criteria 1-5 (clone, fetch after an
  upstream change, 404/403 matrix, query tolerance and `#branch`, revocation, secret hygiene).

#### Interfaces for later phases
- **D-20:** `/data/status.json`, `/data/access.json` and the sync trigger file are contracts that the Phase 3 GUI and
  the Phase 4 API consume. Their schemas (field names, types, file locations, write semantics) are fixed and documented
  in this phase. `/data/access.json` is written atomically (temp file + rename) under one lock; in Phase 3 the GUI and
  the API share one service module for it in one Python process, so the Phase 1 writer must not conflict with that
  design.

#### Repository rules (CLAUDE.md)
- **D-21:** HA base image only (`ghcr.io/home-assistant/amd64-base:3.24`); packages via `apk` (`git`, `lighttpd`, plus
  whatever the planner chooses below). Every Dockerfile change is verified with a local `docker build` before commit.
- **D-22:** Versions only via `make update-version`; never edit the 3 version files by hand.
- **D-23:** Docker verify scripts must not run in two worktrees at the same time.

### Claude's Discretion
- Language of the sync loop and the access-store writer (bash with `jq`, or Python). Python is already planned for the
  Phase 3 GUI (`apk add python3`), and D-20 favours one shared Python service module for `access.json`; the planner
  decides whether to introduce it in Phase 1.
- How users are created and revoked in Phase 1 (no GUI or API yet): for example a small CLI inside the container, or an
  `access.json` edit plus reconcile. ROADMAP criterion 4 requires that removing an entry revokes the URL at the next
  request.
- Exact `status.json` / `access.json` field names and the trigger file path, within D-07, D-14 and D-20. `status.json`
  should already carry what the Phase 3 Repositories view needs (status code, last sync, HEAD short SHA, add-ons found).
- Mechanism of the test-only upstream override within D-18 (for example an environment variable that only `docker run`
  can set; add-on options cannot set container environment).
- Masked URL format for the startup log.
- Whether the manual trigger via `stdin: true` + `hassio.addon_stdin` with `sync` (SPIKE "Sync") lands now or later.
- Layout of s6-overlay service definitions (the base image ships s6-overlay; `init: false` already set in config.yaml).

### Deferred Ideas (OUT OF SCOPE)
- Supervisor integration, `local` system user, store reload (Phase 2).
- Access-log sink and "last fetch" (Phase 3).
- Provisioning API, bearer token (Phase 4).
- Public URL documentation, HTTPS clone test, version bump and stage decision (Phase 5).
- Per-repository deploy keys (SPIKE "Upstream authentication", later, optional).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MRP-01 | Options schema (`github_token`, `sync_interval`, `public_url`, `repositories`, `register_local`, `api_enabled`, `log_level`) | "Options schema" pattern: exact Supervisor schema grammar read from source; `url?` empty-string pitfall; translations layout |
| MRP-02 | Sync service, own s6 service, only PAT holder, bare repo + refspec, `fetch --prune`, `GIT_CONFIG_*` env, interval + trigger, `status.json` codes | s6-rc layout (verified), git env builder, error-to-status mapping (messages reproduced), refs-changed detection, add-on discovery rule from Supervisor source, `status.json` schema |
| MRP-03 | lighttpd + `git http-backend` unprivileged, allow-list, query rewrite, empty docroot, `getanyfile=false`, `receivepack=false`, `safe.directory` | Verified config (with two corrections to the spike), `git-daemon` package, `safe.directory` path rule, response matrix reproduced |
| MRP-04 | `/data/access.json` (repository, user, hash, created, source), 128-bit random hashes, symlink tree rebuilt at start | `access.json` schema, lock + atomic write, reconcile algorithm, `0711` directory mode (verified), CLI design |
| MRP-05 | PAT never in logs/repo config/lighttpd env; hashes never in logs | **New finding:** `git http-backend` logs the requested repo path (contains the hash); fix `server.breakagelog = "/dev/null"` (verified). lighttpd env verified clean without `with-contenv` |
| MRP-06 | `internal/verify-marketplace-repo-proxy.sh` with local upstream fixture | Fixture design (lighttpd + `lighttpd-mod_auth` requiring the header, verified), offline run without Supervisor, scan list incl. base64 form of the PAT |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- HA base images only (`ghcr.io/home-assistant/...`); this add-on uses `amd64-base:3.24` (scaffold `build.yaml`).
- Any Dockerfile change that modifies packages, base images or build stages must pass a local `docker build` before
  commit.
- Versions only via `make update-version` / `internal/update-version.py`; never hand-edit `config.yaml` version,
  `build.yaml` `args.VERSION` or README badges. Own-code add-ons: version bumps are manual (but still via the tool).
- Every add-on directory needs `config.yaml`, `Dockerfile`, `run.sh` (enforced by `make validate-addons`,
  `Makefile:92` `for required_file in "config.yaml" "Dockerfile" "run.sh"; do`). Own-code add-ons have no
  `.upstream.yaml`.
- Stage by path (`git add marketplace-repo-proxy/ ...`), never `git add -A`. No `Co-Authored-By` lines.
- In an add-on worktree write only `.planning/quick/` and workstream files; never `STATE.md`/`state.json`/`ROADMAP.md`
  at repo level.
- Docker verify scripts (`internal/verify-*.sh`) must not run in two worktrees at the same time.
- Lint: YAML 2-space, 120-char lines; Markdown 120 chars (MD013 error), ATX headings; shellcheck with SC1091/SC2034
  ignored; `internal/` scripts `#!/bin/bash`-style with `set -e` (existing verify scripts use
  `#!/usr/bin/env bash` + `set -euo pipefail`).
- Python conventions: module docstring, type hints, `pathlib.Path`, `argparse` with `RawDescriptionHelpFormatter`,
  `if __name__ == '__main__': sys.exit(main())`, `flush=True` in containerized prints.
- Code comments in English; minimal.
- CI (`.github/workflows/lint.yml`): new jobs must be **appended at the end of the file** —
  `lint.yml:176-177` says verbatim: "Appended on purpose: zizmor.yml deferrals for this file are line-anchored, / so no
  line above this job may move." [VERIFIED: .github/workflows/lint.yml:176-177]

## Summary

The spike design holds. A throwaway prototype on `ghcr.io/home-assistant/amd64-base:3.24` (s6-overlay 3.2.3.2, git
2.54.1, lighttpd 1.4.85, Python 3.14.10) reproduced the whole Phase 1 path end to end: an s6-rc oneshot builds the
symlink tree, two longruns (`lighttpd`, `sync`) start after it, the sync fetches from a local upstream that **requires**
the `Authorization` header, and a client container clones `--depth 1`, clones with `?ref=main&tab=readme`, clones with
`--branch main`, runs `ls-remote --heads` and `fetch --update-shallow --depth 1`. After an upstream push and a trigger
file, the next clone showed the new commit. Revoking by removing the entry and reconciling gave 404 for that user and
200 for the other. The 404/403 matrix from SPIKE "Observed responses" matched.

The prototype also found three things the spike does not mention, and the plan has to cover them:

1. **`git-http-backend` is not in Alpine's `git` package.** It ships in `git-daemon`
   (`/usr/libexec/git-core/git-http-backend`). Install `git git-daemon lighttpd python3`.
2. **`cgi.assign` must be global.** Inside the URL condition it no longer matches after the PATH_INFO split, and every
   request gets 403. This is the same mechanism as the spike's `url.access-deny` pitfall. The spike config already has
   it global; keep it that way.
3. **`git http-backend` writes the requested path, including the hash, to stderr**
   (`Not a git repository: '/srv/git/access/<owner>/<repo>/<hash>'`), and lighttpd forwards that to the add-on log. A
   valid hash used under the wrong repository, or a revoked hash, would show up in full. `server.breakagelog =
   "/dev/null"` drops CGI stderr and keeps lighttpd's own error log; verified.

**Primary recommendation:** Write the add-on logic as a Python 3 stdlib package `marketplace-repo-proxy/app/` with an
`AccessStore` that Phase 3 can import, a `sync` service and a small `mrp` CLI. Run it under s6-rc: oneshot `init`,
longruns `lighttpd` and `sync`, bundled via `/etc/s6-overlay/user-bundles.d/user/contents.d/`. Read options from
`/data/options.json` directly, not through `bashio::config`. That call goes through the Supervisor API and fails in the
offline verify run. Prove everything with a two-container verify script (add-on plus an auth-checking upstream
fixture).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Option parsing and validation | Container init (Python, oneshot) | HA Supervisor schema | Supervisor validates types; the add-on re-validates owner/repo/branch before they become paths or refspecs |
| Upstream sync (PAT holder) | `sync` longrun (Python + git CLI) | — | D-13: only process with the PAT |
| Smart-HTTP serving | `lighttpd` longrun + `git http-backend` CGI | Filesystem (symlink tree) | D-01; lighttpd has a clean environment, no PAT, no Supervisor token |
| Access control (who may clone) | Filesystem symlink tree under `/srv/git/access` | `AccessStore` (`/data/access.json`) | D-06: authorization is "does the symlink exist"; revocation is unlink |
| Access store writes | `app.access` module (CLI now, GUI/API in Phase 3/4) | — | D-20: one module, one lock, atomic replace |
| Sync state | `/data/status.json` (single writer: `sync`) | — | Contract for Phase 3 |
| Sync trigger | Trigger file under `/run/marketplace-repo-proxy/` | — | Phase 3 GUI writes, `sync` consumes |
| Store URL host | Kernel hostname of the container | Supervisor `/addons/self/info` (Phase 2) | Supervisor sets the container hostname to the add-on hostname |

## Standard Stack

### Core (Alpine 3.24 packages, versions read in the base image this session)

| Package | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `git` | 2.54.1-r0 | git CLI for sync | [VERIFIED: apk in amd64-base:3.24] |
| `git-daemon` | 2.54.1-r0 | **contains `/usr/libexec/git-core/git-http-backend`** (also `git-daemon`, `git-shell`) | [VERIFIED: `apk info -L git-daemon`] the `git` package does **not** contain it |
| `lighttpd` | 1.4.85-r0 | HTTP server, CGI | [VERIFIED: apk]; `mod_rewrite`, `mod_alias`, `mod_setenv`, `mod_cgi` load from the base package |
| `python3` | 3.14.10-r1 | sync service, access store, CLI | [VERIFIED: apk]; 22 MiB installed; Phase 3 needs it anyway |

Installed sizes [VERIFIED: `apk info -s`]: git 6867 KiB, git-daemon 1297 KiB, lighttpd 880 KiB, python3 22 MiB, jq
343 KiB. Base image 72.6 MB; base + git + lighttpd + python3 + jq ≈ 143 MB.

Already in the base image [VERIFIED]: s6-overlay 3.2.3.2 (`/package/admin/s6-overlay-3.2.3.2`), bashio, busybox
(`inotifyd`, `flock`), `curl`. `lighttpd` user exists: `uid=100(lighttpd) gid=101(lighttpd)`.

### Supporting (fixture only, never in the add-on image)

| Package | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lighttpd-mod_auth` | 1.4.85 (same build) | Basic auth in the upstream fixture, so the fixture returns 401 without the header | Fixture image built by the verify script only [VERIFIED: `apk search`; `mod_auth.so` missing without it] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python stdlib | bash + `jq` | Smaller (no python3, ~22 MiB less), but Phase 3 brings python3 anyway; no pytest coverage; the access store would be written twice (bash now, Python in Phase 3), against D-20 |
| s6-rc services | ntfy-style `run.sh` that backgrounds processes | Repo precedent, but D-13 asks for its own s6 service, and s6 gives restart supervision and per-service environments (lighttpd without `with-contenv`) for free |
| Full-history mirror | Shallow mirror (`fetch --depth 1`) | Shallow serving works for the Supervisor pattern (verified), but a plain `git clone` of the store URL then silently gets a shallow repository, and the mirror carries a `shallow` file. Add-on repositories are small, so full history is simpler and fully compatible |
| Polling the trigger file | busybox `inotifyd` | inotify works without polling, but needs a dir watch plus a handler script per event and cannot be unit tested; 1 s polling of `stat()` is negligible |

**Installation (Dockerfile):**

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}
# git-daemon carries git-http-backend; python3 runs sync, access store and CLI
RUN apk add --no-cache git git-daemon lighttpd python3
```

## Package Legitimacy Audit

No language-ecosystem packages (npm/PyPI/crates) are installed. All packages are Alpine `apk` packages from the base
image's configured Alpine 3.24 repositories, resolved with `apk` inside `ghcr.io/home-assistant/amd64-base:3.24` this
session. The `gsd-tools package-legitimacy` seam covers npm/PyPI/crates only and does not apply.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| git | Alpine main | long-standing | n/a | git-scm.com | OK (distro) | Approved |
| git-daemon | Alpine main (subpackage of `git`) | long-standing | n/a | git-scm.com | OK (distro) | Approved |
| lighttpd | Alpine main | long-standing | n/a | lighttpd.net | OK (distro) | Approved |
| python3 | Alpine main | long-standing | n/a | python.org | OK (distro) | Approved |
| lighttpd-mod_auth | Alpine main (subpackage) | long-standing | n/a | lighttpd.net | OK (distro) | Approved (fixture image only) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

Pytest in CI uses the version already pinned in this repo (`pytest==9.1.1`, `pyyaml==6.0.3`), no new package.

## Architecture Patterns

### System Architecture Diagram

```text
                        container start (s6-overlay /init, PID 1, init: false)
                                         |
                                         v
                 [oneshot init]  reads /data/options.json, validates
                   - /etc/gitconfig safe.directory=/srv/git/repos/*
                   - chmod 0700 /data, mkdir /run/marketplace-repo-proxy
                   - rebuild /srv/git/access/** from /data/access.json (configured repos only)
                   - log user labels + MASKED store URLs (hostname from uname)
                                         |
                    +--------------------+---------------------+
                    v                                          v
   [longrun sync]  (with-contenv, Python)         [longrun lighttpd]  (NO with-contenv, clean env)
    loop: every sync_interval OR trigger file       :8080, user lighttpd, docroot /var/empty
      ls-remote --symref (PAT via GIT_CONFIG_*)      rewrite: drop query -> /repo/o/r/<h>/info/refs|git-upload-pack
      fetch --prune into /srv/git/repos/o/r.git      allow-list cond -> alias -> git-http-backend (CGI)
      classify -> status code                        CGI stderr -> /dev/null (breakagelog)
      write /data/status.json (atomic)                              |
    watcher: access.json changed -> reconcile                       v
                    |                               GIT_PROJECT_ROOT=/srv/git/access
                    v                               /srv/git/access/o/r/<hash> --symlink--> /srv/git/repos/o/r.git
   GitHub (or test override base URL)                               ^
                                                                    |
   mrp CLI (docker exec) --> AccessStore (flock + atomic replace) --+--> reconcile symlinks
   Supervisor / git client --HTTP--> lighttpd   (200 if symlink exists, 404 otherwise)
```

### Recommended Project Structure

```text
marketplace-repo-proxy/
├── config.yaml / build.yaml / Dockerfile / README.md / DOCS.md / CHANGELOG.md
├── run.sh                         # required file (make validate-addons); the s6 oneshot "init" body
├── translations/en.yaml (+ de.yaml)
├── rootfs/
│   ├── etc/lighttpd/marketplace-repo-proxy.conf
│   └── etc/s6-overlay/
│       ├── s6-rc.d/init/{type,up,dependencies.d/base}
│       ├── s6-rc.d/lighttpd/{type,run,finish,dependencies.d/init}
│       ├── s6-rc.d/sync/{type,run,finish,dependencies.d/init}
│       └── user-bundles.d/user/contents.d/{init,lighttpd,sync}
├── app/                            # Python package, imported as `app` (same convention as ntfy, secrets-sync)
│   ├── __init__.py
│   ├── paths.py                    # all file locations in one place (contract)
│   ├── options.py                  # load + validate /data/options.json
│   ├── access.py                   # AccessStore: load, add, revoke, lock, atomic write, reconcile
│   ├── status.py                   # status.json writer/reader, status codes
│   ├── gitops.py                   # git env builder, classify errors, inspect HEAD (sha, repository.yaml, add-ons)
│   ├── sync.py                     # service loop (python3 -m app.sync)
│   ├── init.py                     # oneshot body (python3 -m app.init)
│   ├── urls.py                     # store URL building + masking
│   ├── logsetup.py                 # log_level -> logging, one format
│   └── cli.py                      # `mrp` CLI (python3 -m app.cli)
└── tests/
    ├── conftest.py                 # sys.path insert of the add-on dir (ntfy pattern)
    └── test_*.py
```

Phase 3 adds `app/web/` (admin-ui skeleton via `make sync-admin-ui`) next to these modules. `rootfs/` lives in the
add-on directory because the Docker build context is the add-on directory (admin-ui DOCS "Distribution").

### Pattern 1: s6-rc services in s6-overlay 3.2.x

**What:** Services in `/etc/s6-overlay/s6-rc.d/<name>/`, bundled into `user` through
`/etc/s6-overlay/user-bundles.d/user/contents.d/<name>`. With s6-overlay 3.2.3.2, defining `user` inside `s6-rc.d` is
deprecated; the image's own `rc.init` prints a warning for it [VERIFIED: base image
`/package/admin/s6-overlay/etc/s6-linux-init/skel/rc.init` lines with
`bundledir="$profiledir/user-bundles.d"` and `warning: defining user bundles in $profiledir/s6-rc.d is deprecated,
please define them in $profiledir/user-bundles.d instead`]. The community Nginx Proxy Manager add-on migrated the same
way ("Migrate the user bundle to /etc/s6-overlay/user-bundles.d (#756)", 2026-08-25) [VERIFIED: GitHub API]. The base
image already contains `/etc/s6-overlay/user-bundles.d/user/type` (`bundle`).

**When to use:** Always for this add-on (D-13).

**Behaviour verified in the prototype:**

- Order: `init` (oneshot, `dependencies.d/base`) completes before `sync` and `lighttpd` start (both
  `dependencies.d/init`).
- Output of the oneshot and of both longruns reaches `docker logs` (container stdout/stderr), which is what the HA
  add-on log shows.
- A longrun whose `run` uses `#!/bin/sh` (no `with-contenv`) gets only `SHLVL`, `PATH`, `PWD`. A container env var
  (`SUPERVISOR_TOKEN=SENTINEL…`) did **not** reach lighttpd; with `#!/command/with-contenv sh` it reached `sync`.
- Base image env: `S6_BEHAVIOUR_IF_STAGE2_FAILS=2`, so a failing oneshot stops the container (`haltwith` in `rc.init`).
  `S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0`, so a hanging oneshot hangs the start forever. Keep `init` offline and fast.
- No `CMD`: without one, the container runs until stopped, and s6 restarts crashed longruns.

**Example (files are literal):**

```text
s6-rc.d/init/type                 oneshot
s6-rc.d/init/up                   /etc/s6-overlay/s6-rc.d/init/run
s6-rc.d/init/run                  -> copy of run.sh (see below)
s6-rc.d/init/dependencies.d/base  (empty)
s6-rc.d/lighttpd/type             longrun
s6-rc.d/lighttpd/dependencies.d/init
s6-rc.d/sync/type                 longrun
s6-rc.d/sync/dependencies.d/init
user-bundles.d/user/contents.d/{init,lighttpd,sync}   (empty files)
```

```sh
#!/bin/sh
# s6-rc.d/lighttpd/run - deliberately NOT with-contenv: lighttpd and its CGI see no container secrets
exec lighttpd -D -f /etc/lighttpd/marketplace-repo-proxy.conf
```

```sh
#!/command/with-contenv sh
# s6-rc.d/sync/run - needs container env (TZ, test override, SUPERVISOR_TOKEN in Phase 2)
cd /opt/marketplace-repo-proxy || exit 1
exec python3 -m app.sync
```

`finish` scripts: lighttpd should halt the container on a non-signal failure (community pattern, below), so HA shows
the add-on as stopped and the watchdog can restart it. For `sync`, let s6 restart it (serving continues while sync
crashes); add a short `sleep` in `finish` to avoid a tight restart loop.

```bash
#!/command/with-contenv bashio
# Community pattern (hassio-addons/addon-nginx-proxy-manager nginx/finish): take the container down when the service fails
exit_code_container=$(</run/s6-linux-init-container-results/exitcode)
exit_code_service="${1}"
exit_code_signal="${2}"
if [[ "${exit_code_service}" -eq 256 ]]; then
  [[ "${exit_code_container}" -eq 0 ]] && echo $((128 + exit_code_signal)) > /run/s6-linux-init-container-results/exitcode
  [[ "${exit_code_signal}" -eq 15 ]] && exec /run/s6/basedir/bin/halt
elif [[ "${exit_code_service}" -ne 0 ]]; then
  [[ "${exit_code_container}" -eq 0 ]] && echo "${exit_code_service}" > /run/s6-linux-init-container-results/exitcode
  exec /run/s6/basedir/bin/halt
fi
```

[VERIFIED: GitHub API, hassio-addons/addon-nginx-proxy-manager `proxy-manager/rootfs/etc/s6-overlay/s6-rc.d/nginx/finish`]

**`run.sh` requirement:** `make validate-addons` requires `run.sh`. Recommended: `run.sh` becomes the oneshot body
(`COPY run.sh /etc/s6-overlay/s6-rc.d/init/run`), a thin `#!/command/with-contenv sh` that does
`cd /opt/marketplace-repo-proxy && exec python3 -m app.init`. Remove `CMD ["/run.sh"]` from the Dockerfile.

### Pattern 2: Options without the Supervisor API

`bashio::config` does **not** read `/data/options.json`; it calls the Supervisor API:
`bashio::app.config` → `response=$(bashio::api.supervisor GET "/addons/self/options/config" false)` [VERIFIED: base
image `/usr/lib/bashio/apps.sh:644-669`]. In the offline verify run (no Supervisor) it fails. The repo's own add-ons
already avoid it: ntfy and secrets-sync read `/data/options.json` in Python (`secrets-sync/run.sh`:
`export SS_OPTIONS="${SS_OPTIONS:-/data/options.json}"`).

**Use:** `app/options.py` loads `/data/options.json` with `json`, validates, and returns a frozen dataclass. No bashio
in Python paths. Shell scripts may still use `bashio::log.*` (no API call), but Python logging covers everything.

### Pattern 3: lighttpd config (spike config, verified, with hardening)

```lighttpd
# /etc/lighttpd/marketplace-repo-proxy.conf
server.modules = ("mod_rewrite", "mod_alias", "mod_setenv", "mod_cgi")
server.document-root = "/var/empty"
server.port = 8080
server.username = "lighttpd"
server.groupname = "lighttpd"
server.pid-file = ""
# lighttpd's own errors go to stderr (no server.errorlog set); CGI stderr is dropped because git http-backend
# writes the requested repository path - which contains the access hash - to stderr (MRP-05)
server.breakagelog = "/dev/null"
url.rewrite-once = (
  # optional hardening (verified): everything outside /repo/ becomes a plain 404 ("/" would otherwise be 403)
  "^/(?!repo/)" => "/__not_found",
  "^(/repo/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]{32})\?.*/info/refs&service=git-upload-pack$"
    => "$1/info/refs?service=git-upload-pack",
  "^(/repo/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]{32})\?.*/git-upload-pack$" => "$1/git-upload-pack"
)
$HTTP["url"] =~ "^/repo/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]{32}/(info/refs|git-upload-pack)$" {
  alias.url = ("/repo/" => "/usr/libexec/git-core/git-http-backend/")
}
# MUST stay global: inside the condition above it stops matching after the PATH_INFO split (403 for everything)
cgi.assign = ("" => "")
setenv.set-environment = ("GIT_PROJECT_ROOT" => "/srv/git/access", "GIT_HTTP_EXPORT_ALL" => "1")
```

Observed in the prototype (all [VERIFIED: local prototype run]):

| Request | Status |
|---------|--------|
| `/repo/<o>/<r>/<hash>/info/refs?service=git-upload-pack` | 200 |
| same with `?ref=main&tab=readme` before the git suffix | 200 (clone OK) |
| second user's hash | 200; after unlinking its symlink: 404 |
| unknown hash; valid hash under another `<repo>` | 404 |
| `/repo/`, `/repo/<o>/<r>/`, `<hash>/HEAD`, `<hash>/objects/info/packs`, `<hash>/config` | 404 |
| `<hash>/info/refs` (dumb HTTP) | 403 |
| `<hash>/info/refs?service=git-receive-pack`, `git push` | 403 |
| `POST <hash>/git-receive-pack` (with body) | 404 (not in allow-list) |
| `POST` with no body | 411 from lighttpd (send `--data-binary 0000` in tests) |
| `/usr/libexec/git-core/git-http-backend`, `../`-traversal (`--path-as-is`), `%2e%2e` | 404 |
| `/` | 403 without the extra rewrite rule, 404 with it |
| `GET .../info/refs%00` | 400 |

Do **not** map `log_level: debug` to any `debug.*` lighttpd option: `debug.log-request-handling` prints the full
Request-URI (seen in the prototype), which contains the hash.

### Pattern 4: Disk layout, ownership, symlinks

- Bare repos `root:root`, default modes (dirs 755, files 644) - readable for `lighttpd`.
- `/srv/git/access`, `/srv/git/access/<owner>`, `/srv/git/access/<owner>/<repo>`: `root:root` mode **0711**.
  Verified: `git http-backend` (as `lighttpd`) still follows `<hash>` symlinks (200), but
  `ls /srv/git/access/example-org/private-addons/` as `lighttpd` gives `Permission denied`. A compromised CGI therefore
  cannot list the other users' hashes.
- `safe.directory` is matched against the **resolved** repository path, not the symlink path. Verified: no entry →
  500; `/srv/git/access/*` → 500; `/srv/git/repos/*` → 200. Use
  `git config --system --replace-all safe.directory '/srv/git/repos/*'` in `init` (the `/*` prefix form works on git
  2.54).
- `GIT_PROJECT_ROOT` symlink to a target outside the root: works (SPIKE claim confirmed, 200).
- `chmod 0700 /data` in `init`: in the prototype `options.json` (PAT) and `access.json` (all hashes) were readable by
  the `lighttpd` user. With 0700 a compromised CGI cannot read them. Files written by the add-on use `umask 077`.
- Create a new bare repo **outside** its final path (e.g. `/srv/git/repos/<owner>/.<repo>.git.tmp`), configure it, do
  the first fetch, then `os.rename()` into place. Otherwise http-backend serves an empty repository between
  `git init` and the first fetch, and a Supervisor clone in that window fails. Until the rename, the symlinks dangle and
  give a clean 404.

### Pattern 5: Sync with the PAT in the git child environment only

```python
# app/gitops.py (sketch)
import base64

def auth_env(token: str, allow_protocol: str) -> dict[str, str]:
    """Environment for one git call; the token is only ever in this dict, never in argv or config files."""
    header = "Authorization: Basic " + base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",                    # stable stderr for classification
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",       # sync runs as root on root-owned repos: no safe.directory needed
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ALLOW_PROTOCOL": allow_protocol,   # "https" in production
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": header,
    }
```

The env dict is built from scratch, so stray `GIT_TRACE*` / `GIT_CURL_VERBOSE` from the container env can never be
active. The same approach exists in this repo: `secrets-sync/app/providers/gitsource.py:110-115` sets `"LC_ALL": "C"`,
`"GIT_TERMINAL_PROMPT": "0"`, `"GIT_CONFIG_NOSYSTEM": "1"`, `"GIT_CONFIG_GLOBAL": "/dev/null"`,
`"GIT_ALLOW_PROTOCOL": _allowed_protocols()` [VERIFIED: file read this session]. Verified in the prototype: the PAT
(raw and base64 header form) was in no `/proc/*/environ` or `/proc/*/cmdline` of a long-lived process (Python built
the env dict only for the git child), not in `/srv/git`, not in `docker logs`, not in the cloned data.

**Sync cycle per repository:**

1. `git ls-remote --symref <url> HEAD` (auth env). Parse `ref: refs/heads/<b>\tHEAD` if no branch is configured. An
   empty upstream repository returns rc 0 with **no output** (verified) → `not_found` ("no default branch").
   For a configured branch: `git ls-remote --exit-code <url> refs/heads/<b>` → rc 2 if missing (verified).
2. If the bare repo is missing: temp dir, `git init --bare -q`, then `git config`:
   `remote.origin.url <url>`, `remote.origin.fetch +refs/heads/<b>:refs/heads/<b>`,
   `remote.origin.pushurl <invalid>`, `http.receivepack false`, `http.getanyfile false`; `git symbolic-ref HEAD
   refs/heads/<b>`; fetch; rename into place.
3. Existing repo: set the refspec and `HEAD` again on every cycle (branch may change through options or upstream
   default). Delete refs other than `refs/heads/<b>` (`git for-each-ref` + `git update-ref -d`), because
   `fetch --prune` only prunes inside the refspec.
4. Snapshot `git for-each-ref --format='%(refname) %(objectname)'` + `git symbolic-ref HEAD` before and after
   `git fetch --prune --no-tags origin` → `refs_changed`.
5. Inspect HEAD without a checkout (run as root, no auth env):
   - `git rev-parse --short=12 HEAD` → `head`
   - `git ls-tree --name-only HEAD` contains `repository.yaml|yml|json` → else `no_repository_yaml`
   - add-ons: `git ls-tree -r --name-only HEAD`, keep paths whose basename is `config.yaml|yml|json` and where no path
     part starts with `.` or equals `rootfs`, report the parent directory. This mirrors the Supervisor exactly:
     `path.glob("**/config.*")`, skipping `part.startswith(".") or part == "rootfs"`, suffix in
     `FILE_SUFFIX_CONFIGURATION` [VERIFIED: supervisor `supervisor/store/data.py:151-165` at `e610ca8`].
6. Keep git maintenance out of the authenticated call: `-c maintenance.auto=false -c gc.auto=0` on fetch, then
   `git maintenance run --auto` without the auth env. A detached auto-gc would otherwise inherit `GIT_CONFIG_VALUE_0`.
7. Add timeouts: `-c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60` and a `subprocess` timeout (e.g. 600 s).

**Error classification (stderr with `LC_ALL=C`; messages reproduced this session):**

| Observed stderr | Source | Status |
|-----------------|--------|--------|
| `fatal: could not read Username for '<host>': terminal prompts disabled` | 401 with a wrong/expired token (local fixture **and** real github.com with a fake token) | `auth_failed` |
| `fatal: unable to access '<url>': The requested URL returned error: 403` | 403 (e.g. SSO-blocked token, local fixture) | `auth_failed` |
| `fatal: repository '<url>/' not found` | 404 (local fixture) | `not_found` |
| `fatal: couldn't find remote ref refs/heads/<b>` / ls-remote rc 2 / empty ls-remote | branch or default branch missing | `not_found` |
| `fatal: unable to access '<url>': Could not resolve host: ...` and anything else | network/other | `fetch_failed` (proposed, see Open Questions) |

Important: real github.com returns **401 for a nonexistent repository without credentials and for any invalid token,
even on a public repository** (curl: `401` in all three probes, git: `could not read Username`). So a bad token is
always `auth_failed`, never `not_found`. A *valid* token without access to the repository yields GitHub's
`Repository not found` (404) → `not_found` [ASSUMED: could not be tested without a real token].

### Pattern 6: Store URL host without `hassio_api`

The Supervisor runs every add-on container with `hostname=self.app.hostname` unless `host_uts` is set
(`hostname = None if self.uts_mode else self.app.hostname`), and `hostname` is `self.slug.replace("_", "-")`
[VERIFIED: supervisor `supervisor/docker/app.py:719-727` and `supervisor/apps/model.py:253-255` at commit `e610ca8`,
the commit the spike tested]. For a repository add-on the slug is `<repo-hash>_marketplace_repo_proxy`, so the
container hostname is `72a005f5-marketplace-repo-proxy`, the name the spike resolved through the `hassio` DNS. The same
name is registered in the Supervisor DNS (`dns.add_host(ipv4=..., names=[self.app.hostname])`, same file).

In the prototype (`docker run --hostname 72a005f5-marketplace-repo-proxy`), both `uname -n` and `$HOSTNAME` returned
that name inside the s6 oneshot [VERIFIED: local]. **Use `socket.gethostname()`** (kernel UTS name, independent of
env). Evidence level: source-verified plus local Docker; not yet observed on the production host. The Phase 2 live E2E
should confirm it. Cross-check alternative: `GET /addons/self/info` is in the Supervisor's `api_bypass` list
(`r"|/addons/self/(?!security|update)[^/]+"`), so every add-on may call it without `hassio_api` [VERIFIED:
`supervisor/api/middleware/security.py` v1 patterns], but it needs the Supervisor and is unusable offline.

Internal URL: `http://<hostname>:8080/repo/<owner>/<repo>/<hash>`. If `public_url` is set, Phase 1 may also log the
masked public form `<public_url without trailing slash>/repo/<owner>/<repo>/<masked>` (Phase 5 owns the full feature).

### Pattern 7: Access store (shared with Phase 3)

```python
# app/access.py (sketch) - one class, used by the CLI now and by GUI + API (one process) in Phase 3/4
import fcntl, json, os, secrets, tempfile
from contextlib import contextmanager

@contextmanager
def locked(lock_path):
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)   # per open file description: also excludes threads that open their own fd
        yield
    finally:
        os.close(fd)

def atomic_write_json(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".access.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise

def new_hash() -> str:
    return secrets.token_hex(16)   # 128 bit from the OS CSPRNG (/dev/urandom), 32 lowercase hex
```

Rules:

- Every read-modify-write holds the lock. Readers may read without it (atomic replace).
- After every write: reconcile the symlinks under the same lock (create missing, unlink stale).
- Unknown top-level keys and unknown entry fields are preserved on write (forward compatibility). If `schema` is higher
  than the code knows → refuse to write, log an error.
- Reconcile only creates symlinks for repositories that are configured in the options. Entries for unconfigured
  repositories stay in `access.json` (they come back when the repository is re-added) and are counted in the startup
  log.
- Reconcile builds paths only from validated `owner`/`repo` and from hashes matching `^[0-9a-f]{32}$`; anything else in
  `access.json` is skipped with a log line that does not contain the hash.

### Anti-Patterns to Avoid

- **`bashio::config` in services:** needs the Supervisor API; breaks the offline verify run.
- **`with-contenv` on the lighttpd run script:** would import `SUPERVISOR_TOKEN` (Phase 2) and the test override into
  lighttpd and its CGI.
- **`python3 -I -m app.x` or `python3 -P -m app.x`:** verified: `No module named 'app'` (safe-path mode drops the cwd).
  Use `cd /opt/marketplace-repo-proxy && exec python3 -m app.x` (ntfy pattern) with `PYTHONDONTWRITEBYTECODE=1`,
  `PYTHONUNBUFFERED=1`.
- **`cgi.assign` inside the `$HTTP["url"]` condition:** 403 for everything (verified).
- **`git clone --mirror`:** sets `remote.origin.mirror=true` (D-10).
- **Token in URL (`https://x-access-token:<pat>@github.com/...`):** lands in `remote.origin.url` and in error messages.
- **Logging git stderr verbatim at info:** acceptable for the upstream URL (no secret), but pass it through one
  sanitiser that also masks any `[0-9a-f]{32}` and strips `Authorization` lines.
- **Python 3.13+ only syntax/features:** CI runs Python 3.12 (`python-version: '3.12'`), the container 3.14. Code must
  run on both.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Smart HTTP protocol | Python `upload-pack` wrapper | `git http-backend` via lighttpd CGI | Protocol v2, shallow, `--update-shallow` all handled; verified |
| Random tokens | `random`, uuid4, time-based | `secrets.token_hex(16)` | CSPRNG, exact format required by D-05 |
| Atomic JSON write | open(path, "w") + dump | temp file in same dir + `fsync` + `os.replace` | Crash-safe, readers never see half files |
| Cross-process lock | PID files, `os.O_EXCL` lock files | `fcntl.flock` on a lock file | Released automatically when the process dies |
| Process supervision | bash `wait`/`trap` loops (ntfy `run.sh`) | s6-rc longruns | Restart, ordering, per-service env |
| Upstream auth | credential helper, `.netrc`, URL userinfo | `GIT_CONFIG_COUNT` + `http.extraHeader` env | Nothing written to disk, nothing in argv (D-08) |
| Add-on discovery | own heuristics | Supervisor's rule (`**/config.*`, skip `.*` and `rootfs`) | Matches what the store will show |

**Key insight:** every piece of this add-on already exists as a stock tool; the add-on's own code is glue (options →
git calls → JSON files → symlinks). Keep it that way, so the security properties come from well-tested components.

## Interface Contracts (D-20)

All files are UTF-8 JSON, written by `atomic_write_json` (mode 0600), timestamps ISO 8601 UTC with `Z`
(`2026-11-17T20:45:11Z`). Field names below are the proposal; Phase 3/4 may add fields but must not rename them.

### `/data/access.json` (owner: `app.access.AccessStore`; lock `/run/marketplace-repo-proxy/access.lock`)

```json
{
  "schema": 1,
  "entries": [
    {
      "repository": "example-org/private-addons",
      "user": "alice",
      "hash": "<32 lowercase hex>",
      "created": "2026-11-17T20:45:11Z",
      "source": "gui"
    }
  ]
}
```

- `repository`: `owner/repo` exactly as configured (case kept); uniqueness of `(repository.lower(), user)`.
- `user`: label, `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (URL-safe for the Phase 4 path `/users/{user}`). `local` is
  reserved for Phase 2's system user.
- `hash`: `^[0-9a-f]{32}$`, unique across the whole file.
- `source`: `gui` | `api` | `system` (D-07). See Open Question 1 for CLI-created users.
- Missing file = no entries. Not stored here: "last fetch" (Phase 3 sink writes its own file, so the per-fetch writes
  never contend with this lock).

### `/data/status.json` (single writer: `sync`; no lock, atomic replace)

```json
{
  "schema": 1,
  "updated": "2026-11-17T20:45:11Z",
  "sync": {
    "state": "idle",
    "last_started": "2026-11-17T20:45:05Z",
    "last_finished": "2026-11-17T20:45:11Z",
    "next_due": "2026-11-17T21:00:11Z",
    "interval_minutes": 15,
    "reason": "interval"
  },
  "repositories": [
    {
      "repository": "example-org/private-addons",
      "branch": "main",
      "branch_source": "upstream_default",
      "status": "ok",
      "message": "",
      "last_attempt": "2026-11-17T20:45:06Z",
      "last_success": "2026-11-17T20:45:06Z",
      "last_change": "2026-11-17T20:45:06Z",
      "head": "f9003aeb1cb1",
      "addons": ["demo"],
      "refs_changed": true
    }
  ]
}
```

- `sync.state`: `idle` | `running`. `sync.reason`: `startup` | `interval` | `request`.
- `repositories` is a list in options order. `status`: `pending` (configured, never attempted), `ok`, `auth_failed`,
  `not_found`, `no_repository_yaml`, `fetch_failed` (the last and `pending` are additions, see Open Question 2).
- `message`: one sanitised line for humans (no token, no hash). `head`: 12-char short SHA or `null`. `branch_source`:
  `configured` | `upstream_default`. `last_success` and `head` keep the last good values when a later sync fails,
  because the bare repo still serves them.
- `refs_changed` refers to the last attempt; Phase 2 uses it for `POST /store/reload`.

### Sync trigger: `/run/marketplace-repo-proxy/sync.request`

- Any root process in the container (CLI now, GUI in Phase 3) creates the file (content ignored; write `{}`).
- The sync loop checks for it every second while idle, **unlinks it before** starting a full cycle (all
  repositories). A request arriving during a running cycle causes exactly one more cycle afterwards (coalescing).
- The interval timer restarts after every cycle, whatever started it.
- `/run` keeps runtime IPC out of backups. `init` creates the directory with mode 0700.

## Users in Phase 1: `mrp` CLI plus a reconcile watcher

Recommendation (both parts):

1. **CLI** `/usr/local/bin/mrp` → `python3 -m app.cli`, run via `docker exec`:
   - `mrp users list [<owner/repo>]` — labels, created, source, masked hash
   - `mrp users add <owner/repo> <user> [--hash <32hex>]` — prints the store URL(s) **to the terminal only**
   - `mrp users revoke <owner/repo> <user>` — removes the entry, unlinks the symlink in the same locked operation →
     the next request is 404
   - `mrp users url <owner/repo> <user>` — prints the full URL on explicit request
   - `mrp sync` — creates the trigger file; `mrp reconcile` — rebuilds the symlinks
2. **Watcher** in the `sync` service: a thread that `stat()`s `/data/access.json` every second
   (`st_mtime_ns`, `st_ino`, `st_size`) and reconciles under the lock when it changes. Hand edits and future writers
   are covered within about 1 s; the thread keeps running while a long fetch blocks the sync thread.

This satisfies ROADMAP criterion 4 literally: removing the entry (by CLI, immediately; by hand edit, within ~1 s)
revokes that URL, other symlinks are untouched. Production use in Phase 1 needs host access
(`docker exec addon_<slug> mrp ...`); document it as interim in DOCS.md, the GUI replaces it in Phase 3.

`stdin: true` + `hassio.addon_stdin`: **defer**. s6 longruns do not get the container's stdin. Only a `CMD` does, and
if the `CMD` exits, s6 halts the container. The trigger file and the CLI cover Phase 1 and Phase 3.

## Test-only upstream override (D-18)

- Environment variable `MRP_TEST_UPSTREAM_BASE` (e.g. `http://mrp-upstream:8080`), read only by `app.sync` at start.
  Repository URL = `<base>/<owner>/<repo>.git`; default base `https://github.com`.
- Inert in production: HA add-on options cannot set container environment; the Supervisor only passes the
  `environment:` map from `config.yaml` (author-controlled) plus its own variables (`app_env = ...
  dict(self.app.environment or {})`, then `TZ`, socket path, token [VERIFIED: supervisor `docker/app.py:226-249`]).
  `config.yaml` must never declare it.
- When set: validate scheme `http|https`, no userinfo, no query/fragment; log one `WARNING` at start ("test upstream
  override active: <base>"); set `GIT_ALLOW_PROTOCOL` to the override's scheme (production: `https` only); and expose
  `"upstream_override": true` in `status.json` so it is visible.
- PAT exposure: the override host does receive the `Authorization` header. That is the point of the test, because it
  proves the header is sent. It is not a privilege gain: anyone who can set container env (host root / Docker access)
  can already read `/data/options.json`. Never put the variable into `config.yaml`, `build.yaml` or the Dockerfile
  (`ENV`). The verify script greps `config.yaml`, `Dockerfile` and `rootfs/` for the variable name outside `app/`.
- Redirects: git's default `http.followRedirects=initial` and curl drop a custom `Authorization` header on a cross-host
  redirect [ASSUMED: curl behaviour since 7.58.0 (CVE-2018-1000007), not re-tested here].

## Options schema (MRP-01)

Supervisor grammar [VERIFIED: supervisor `supervisor/apps/options.py:31-44`]:
`r"|int(?:\((?P<i_min>-?\d+)?,(?P<i_max>-?\d+)?\))?"`, `r"|password(?:\((?P<p_min>\d+)?,(?P<p_max>\d+)?\))?"`,
`r"|url"`, `r"|match\((?P<match>.*)\)"`, `r"|list\((?P<list>.+)\)"`, `r")\??$"`. So `int(5,)`, `password`, `url?`,
`match(...)?`, `list(a|b)` are valid. A key that is present is always validated (`_validate_typed`); only a
**missing** key may be optional (`_check_missing_options`: `if isinstance(miss_schema, str) and
miss_schema.endswith("?"): continue`). Therefore **`public_url: ""` with `url?` fails validation** (`vol.Url()("")`):
leave `public_url` out of `options:` defaults.

Recommended `config.yaml` additions (keep the existing keys; `log_level` stays
`"list(debug|info|warning|error)"` as in the scaffold, `config.yaml:20`):

```yaml
options:
  github_token: ""
  sync_interval: 15
  repositories: []
  register_local: true
  api_enabled: false
  log_level: "info"
schema:
  github_token: "password"
  sync_interval: "int(5,)"
  public_url: "url?"
  repositories:
    - repository: "match(^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/(?!\\.\\.?$)[A-Za-z0-9._-]{1,100}$)"
      branch: "match(^[A-Za-z0-9._/-]{1,200}$)?"
  register_local: "bool"
  api_enabled: "bool"
  log_level: "list(debug|info|warning|error)"
```

- The regex style follows `iac-runner/config.yaml` (list of dicts with `branch: "str?"`, `match(...)` with `\\`
  escapes). The `repository` regex rejects `.`/`..` as repo names (they would become paths); the add-on re-validates in
  Python (also rejects a `.git` suffix, duplicates case-insensitively) and runs `git check-ref-format --branch` on
  `branch`.
- Empty `github_token` with repositories configured: no crash, status `auth_failed` with message
  `github_token is empty`.
- `password` values are hashed by the Supervisor for its pwned-password check (`self.pwned.add(hashlib.sha1(...))` in
  `_validate_typed`) [VERIFIED: options.py:167-169]. Only a SHA-1 is kept; the range-query mechanism is
  [ASSUMED]. `!secret` references work (`value.startswith("!secret ")`); `/data/options.json` then holds the resolved
  value [VERIFIED: options.py:136-145 comment "Persisting callers keep the reference; write_options resolves it
  again"].

`translations/en.yaml` (existing format: `configuration: <key>: name/description`; nested list fields via `fields:`
as in `secrets-sync/translations/en.yaml`):

```yaml
configuration:
  github_token:
    name: GitHub token
    description: Fine-grained personal access token with read-only "Contents" access to the repositories below. Never
      logged.
  sync_interval:
    name: Sync interval (minutes)
    description: Minutes between two syncs (minimum 5).
  public_url:
    name: Public URL
    description: Optional base URL behind a reverse proxy, e.g. https://addons.example.com. Leave empty for internal
      access only.
  repositories:
    name: Repositories
    description: Private GitHub repositories to serve.
    fields:
      repository:
        name: Repository
        description: GitHub repository as owner/repo.
      branch:
        name: Branch
        description: Optional branch; empty uses the repository's default branch.
  register_local:
    name: Register in the local store
    description: Add the internal store URL to this Home Assistant's add-on store (from a later version).
  api_enabled:
    name: Provisioning API
    description: Enable the provisioning API for IaC tools (from a later version).
  log_level:
    name: Log level
    description: Verbosity of the add-on log. Tokens and access hashes are never logged.
```

Recommend adding `translations/de.yaml` too (cups, ntfy, secrets-sync, haos-monitor ship both).

## Masked URL format (startup log)

`http://72a005f5-marketplace-repo-proxy:8080/repo/example-org/private-addons/3f9c…` — the first 4 hex characters plus
`…`. That is 16 bits disclosed, 112 bits remain, and it is enough to tell users apart in the log. One line per user:
`alice → http://…/repo/example-org/private-addons/3f9c…`. The full URL is printed only by `mrp users add|url` to the
terminal.

## Runtime State Inventory

Not a rename/refactor phase. Omitted.

## Common Pitfalls

### Pitfall 1: `git-http-backend` missing at runtime
**What goes wrong:** lighttpd maps to `/usr/libexec/git-core/git-http-backend`, which does not exist → 404/500.
**Why:** On Alpine 3.24 the binary is in `git-daemon`, not `git` (verified; the spike's `apk add git lighttpd` is
incomplete).
**How to avoid:** `apk add git git-daemon lighttpd python3`; the verify script asserts the file exists.

### Pitfall 2: Hash leaks through CGI stderr
**What goes wrong:** `Not a git repository: '/srv/git/access/<o>/<r>/<hash>'` lands in the add-on log for unknown,
revoked or cross-repo hashes (verified with a valid hash under another repo).
**How to avoid:** `server.breakagelog = "/dev/null"`. Never enable lighttpd `debug.*`.
**Warning signs:** verify script: `docker logs` must contain no `[0-9a-f]{32}` after `/access/` or `/repo/` and none
of the test hashes (exact `grep -F`), also after deliberate 404 requests with valid-but-misplaced hashes.

### Pitfall 3: `cgi.assign` inside the condition
**What goes wrong:** 403 for every git request; lighttpd re-evaluates conditions after splitting PATH_INFO
(debug log: `NOT handling file as static file, pathinfo forbidden`).
**How to avoid:** keep `cgi.assign = ("" => "")` global; the empty docroot makes that safe.

### Pitfall 4: `safe.directory` on the wrong path
**What goes wrong:** 500 for every request. git checks the resolved path (`/srv/git/repos/...`), not the symlink.
**How to avoid:** `safe.directory = /srv/git/repos/*` in `/etc/gitconfig` (written by `init`, idempotent with
`--replace-all`).

### Pitfall 5: Empty repository served during first sync
**What goes wrong:** Supervisor clones an empty repo between `git init` and the first fetch.
**How to avoid:** init + first fetch in a temp dir, then rename.

### Pitfall 6: Stale refs after a branch change
**What goes wrong:** Old branch ref stays (outside the refspec, so `--prune` ignores it); `HEAD` may point to it.
**How to avoid:** re-set refspec and `HEAD` every cycle, delete non-matching refs.

### Pitfall 7: Classifying `auth_failed` by HTTP code only
**What goes wrong:** git never prints "401"; with `GIT_TERMINAL_PROMPT=0` it prints `could not read Username ...
terminal prompts disabled`.
**How to avoid:** match the stderr table above with `LC_ALL=C`; unit-test every row against a local fixture.

### Pitfall 8: Offline run fails at `bashio::config`
**What goes wrong:** container exits or logs "Failed to get addon config from Supervisor API" in the verify run.
**How to avoid:** Python reads `/data/options.json`.

### Pitfall 9: Secret scan matches itself
**What goes wrong:** a `docker exec sh -c '... grep <PAT> /proc/*/environ'` finds the PAT in its own environment or
argv (happened in this research).
**How to avoid:** pass needles via a file (`grep -F -f /tmp/needles`), skip `$$` and its children. Scan for the raw
PAT **and** `base64("x-access-token:<PAT>")`. Reading lighttpd's `/proc/<pid>/environ` needs
`docker exec --privileged` (the process dropped privileges; root without `CAP_SYS_PTRACE` gets `Permission denied`).

### Pitfall 10: CI job placement
**What goes wrong:** adding a job in the middle of `lint.yml` shifts lines and breaks line-anchored zizmor deferrals.
**How to avoid:** append the new `marketplace-repo-proxy` job at the end of `lint.yml` (like `admin-ui`,
`secrets-sync`, `ntfy`).

### Pitfall 11: `public_url: ""`
**What goes wrong:** the Supervisor rejects the options (`url` validator on an empty string).
**How to avoid:** no default for `public_url`; the code treats missing/empty as "internal only".

## Code Examples

### Reconcile (sketch)

```python
# app/access.py
import os, re
from pathlib import Path

HASH_RE = re.compile(r"^[0-9a-f]{32}$")

def reconcile(entries, configured: set[str], access_root: Path, repos_root: Path) -> int:
    """Make the symlink tree equal to the configured entries; returns the number of links."""
    want: dict[Path, Path] = {}
    for e in entries:
        repo = e["repository"]
        if repo.lower() not in configured or not HASH_RE.match(e["hash"]):
            continue
        owner, name = repo.split("/", 1)
        want[access_root / owner / name / e["hash"]] = repos_root / owner / f"{name}.git"
    for link, target in want.items():
        link.parent.mkdir(mode=0o711, parents=True, exist_ok=True)
        if not link.is_symlink() or os.readlink(link) != str(target):
            tmp = link.with_name(f".{link.name}.tmp")
            if tmp.is_symlink():
                tmp.unlink()
            tmp.symlink_to(target)
            os.replace(tmp, link)          # atomic swap, never a missing link for a valid user
    for dirpath, dirnames, filenames in os.walk(access_root):
        for n in filenames + dirnames:
            p = Path(dirpath) / n
            if p.is_symlink() and p not in want:
                p.unlink()
    return len(want)
```

`os.makedirs(mode=0o711)` is subject to the umask; `chmod` the three directory levels explicitly after creation.

### Verify-script skeleton (conventions from `internal/verify-ntfy-e2e.sh`, `verify-secrets-sync-no-secret-leak.sh`)

```bash
#!/usr/bin/env bash
# Docker end-to-end check of marketplace-repo-proxy against a local upstream fixture (ROADMAP Phase 1 criteria 1-5).
# Manual invocation: bash internal/verify-marketplace-repo-proxy.sh
# Starts containers: never run it in two worktrees at the same time.
set -euo pipefail

ADDON_DIR="marketplace-repo-proxy"
IMAGE_TAG="marketplace-repo-proxy-verify:local"
FIXTURE_TAG="marketplace-repo-proxy-fixture:local"
PREFIX="${MRP_VERIFY_PREFIX:-mrp-verify}"
NET="${PREFIX}-net"
PROXY="${PREFIX}-proxy"           # started with --hostname 72a005f5-marketplace-repo-proxy
UPSTREAM="${PREFIX}-upstream"
PAT="SENTINEL-PAT-$RANDOM$RANDOM"
fail() { echo "✗ $1"; exit 1; }
# cleanup trap: docker rm -f, docker network rm, root-owned data removed through the image (ntfy pattern)
```

Steps the script must cover (each with a `✓`/`✗` line):

1. `docker build` with `BUILD_FROM`/`VERSION` from `build.yaml` (`yget` helper as in `verify-ntfy-e2e.sh`); fixture
   image `FROM ${IMAGE_TAG}` + `apk add --no-cache lighttpd-mod_auth`.
2. Network; fixture container (`--entrypoint sh`): bare repo `example-org/private-addons.git` with `repository.yaml`
   and one add-on dir, a second empty repo; lighttpd with `mod_auth` basic `x-access-token:<PAT>`; assert `curl`
   without header → 401.
3. `options.json` (sentinel PAT, `log_level: debug`, one good repo, one missing repo), `access.json` with two users
   (or created via `mrp users add`); proxy with `-e MRP_TEST_UPSTREAM_BASE=http://${UPSTREAM}:8080`,
   `-e SUPERVISOR_TOKEN=<sentinel>` (proves lighttpd does not get it).
4. Wait for `status.json` `ok` / `not_found`; then from a client container (same image, `--entrypoint sh`):
   `clone --depth 1`, clone with `?ref=main&tab=readme`, `clone --branch main` (the `#main` form), `ls-remote --heads`,
   `fetch --update-shallow --depth 1`.
5. Status matrix with `curl --path-as-is` (table in Pattern 3); `git push` refused.
6. Upstream commit in the fixture → `mrp sync` (trigger) → wait for new `head` in `status.json` → client fetch shows
   it.
7. Revocation: `mrp users revoke` → 404 for that hash, 200 for the other; then a hand edit of `access.json` → 404
   within 5 s.
8. Auth failure: restart with a wrong PAT → `auth_failed`, no PAT/base64 in logs.
9. Secret hygiene: needles (PAT, base64 header, both full hashes, SUPERVISOR_TOKEN sentinel) in `docker logs`,
   `/srv/git/**` (incl. every `config`), `status.json`, served data (client clone incl. `.git`), all
   `/proc/*/cmdline`; PAT + base64 in all `/proc/*/environ` (`--privileged`); lighttpd's environ contains neither the
   PAT nor `SUPERVISOR_TOKEN` nor `MRP_TEST_UPSTREAM_BASE`; `remote.origin.url` has no userinfo; no
   `/repo/.../[0-9a-f]{32}` and no `/access/.../[0-9a-f]{32}` in logs after deliberate 404 probes.
10. Static checks: `MRP_TEST_UPSTREAM_BASE` absent from `config.yaml`, `Dockerfile`, `rootfs/`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `/etc/s6-overlay/s6-rc.d/user/contents.d/` | `/etc/s6-overlay/user-bundles.d/user/contents.d/` | s6-overlay 3.2.x (in base image 3.2.3.2) | Old path still works but logs a deprecation warning |
| `/etc/services.d`, `/etc/cont-init.d` (s6 v2 style) | s6-rc oneshot/longrun | s6-overlay v3 | Legacy dirs still run via `legacy-*` oneshots; do not use for new code |
| `bashio::config` reading a file | Supervisor API call | bashio (current) | Offline tests must not use it |

**Deprecated/outdated:** Python `http.server.CGIHTTPRequestHandler` / `cgi` module (removed in 3.13) — do not build a
fixture on it; use lighttpd [ASSUMED: from Python release notes, not re-checked].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A valid PAT without access to a repo gets GitHub `Repository not found` (404) → `not_found` | Pattern 5 | Status shows `fetch_failed`/`auth_failed` instead of `not_found`; message text only, no security impact |
| A2 | The container hostname on the production host equals `<repo-hash>-marketplace-repo-proxy` | Pattern 6 | Startup log prints a wrong host; confirm in Phase 2 live E2E (source-verified, so low risk) |
| A3 | curl drops custom `Authorization` on cross-host redirects | Override | Only relevant if GitHub redirected to another host; keep `followRedirects` default |
| A4 | `chmod 0700 /data` is harmless for the Supervisor (backups/options writes run as root) | Pattern 4 | If the Supervisor needed other perms, options updates or backups could fail; verify in Phase 2 live run |
| A5 | The HA add-on log shows container stdout/stderr of all s6 services | Pattern 1 | Repo-wide convention; only `docker logs` was verified here |
| A6 | Supervisor pwned check uses a k-anonymity range query | Options | PAT hash prefix leaves the host; accepted, same as every `password` option |
| A7 | Python `cgi` / `CGIHTTPRequestHandler` removed | State of the Art | Only matters if someone builds a Python fixture |

## Open Questions (RESOLVED)

All four items are resolved **provisionally** by the orchestrator as plan assumptions A-1, A-2, A-4 and A-5 (each
plan's "Assumptions" section). None is confirmed by the user yet; each must be confirmed before execution. A-3 (no
version bump) and A-6 (`stdin` trigger deferred) resolve items outside this list.

1. **`source` value for CLI-created users** (MRP-04 / D-07 allow `gui`, `api`, `system`). (RESOLVED — provisional A-1,
   pending user confirmation before execution)
   - What we know: Phase 1 has no GUI/API; Phase 2's `system` user is label `local`.
   - Recommendation: add `cli` as a fourth value (additive, GUI shows a badge). Alternative within D-07: CLI writes
     `system`, which conflates operator-created users with the auto-managed `local` user.
   - Resolution pointer: A-1 adopts `cli` (Plans 01-01, 01-03, 01-06 "Assumptions").
2. **Additional status codes** beyond D-14's four. (RESOLVED — provisional A-2, pending user confirmation before
   execution)
   - Recommendation: add `pending` (configured, not yet attempted) and `fetch_failed` (network/other errors). Without
     them, DNS failures or timeouts would have to be shown as one of the four codes, which would be wrong. Branch
     missing / empty upstream → `not_found` with a message. Additive to D-14.
   - Resolution pointer: A-2 adds `pending` and `fetch_failed` (Plans 01-02, 01-06 "Assumptions").
3. **Startup URL with `public_url`** in Phase 1: print masked public URLs too, or only internal? Recommendation: both
   (masked), cheap; Phase 5 owns the documentation. (RESOLVED — provisional A-4, pending user confirmation before
   execution)
   - Resolution pointer: A-4 prints both, masked (Plan 01-04 "Assumptions").
4. **Container stop on `init` failure** (`S6_BEHAVIOUR_IF_STAGE2_FAILS=2`): recommendation: fail only on unreadable
   options or an invalid `access.json` schema version; invalid repository entries are logged and skipped. Planner's
   call. (RESOLVED — provisional A-5, pending user confirmation before execution)
   - Resolution pointer: A-5 adopts the recommendation (Plan 01-04 "Assumptions").

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | build + verify script | ✓ | 29.9.3 (legacy builder warns; buildx missing) | — |
| `ghcr.io/home-assistant/amd64-base:3.24` | image | ✓ (local, 3 weeks old) | Alpine 3.24.3, s6-overlay 3.2.3.2 | pull |
| Network for `apk add` during build | Dockerfile, fixture image | ✓ (used this session) | — | — |
| python3 + pytest on host | unit tests | ✓ python3 on host; pytest via `uv run --with pytest` | — | CI job |
| GitHub (real) | — | not needed | — | fixture only (D-18) |

**Missing dependencies with no fallback:** none.

## Validation Architecture

(`workflow.nyquist_validation` is `false` in `.planning/config.json`; this section is included because the
orchestrator asked for it.)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (CI pin), Python 3.12 in CI, 3.14 in the image |
| Config file | none; `marketplace-repo-proxy/tests/conftest.py` adds the add-on dir to `sys.path` (ntfy pattern) |
| Quick run command | `uv run --with pytest==9.1.1 python3 -m pytest marketplace-repo-proxy/tests -q` |
| Full suite command | quick run + `bash internal/verify-marketplace-repo-proxy.sh` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MRP-01 | options load/validate (regexes, `.git` suffix, duplicates, empty token, missing `public_url`) | unit | `pytest marketplace-repo-proxy/tests/test_options.py -q` | ❌ Wave 0 |
| MRP-01 | config.yaml schema keys/defaults match the code's expectations | unit (PyYAML) | `pytest .../test_config_yaml.py -q` | ❌ Wave 0 |
| MRP-02 | sync against local bare repos via `file://`/`http` fixture: create, refspec, pushurl, HEAD, prune other refs, refs_changed, head/addons/repository.yaml, error classification table | unit/integration (real git, tmp dirs) | `pytest .../test_sync.py .../test_gitops.py -q` | ❌ Wave 0 |
| MRP-02 | trigger coalescing, interval restart | unit (fake clock) | `pytest .../test_sync_loop.py -q` | ❌ Wave 0 |
| MRP-03 | lighttpd matrix, query tolerance, `#branch`, push refused | e2e (Docker) | `bash internal/verify-marketplace-repo-proxy.sh` | ❌ Wave 0 |
| MRP-04 | add/revoke/rotate-free hash uniqueness, lock, atomic write, unknown-field preservation, reconcile (stale links removed, unconfigured repos skipped, 0711) | unit | `pytest .../test_access.py -q` | ❌ Wave 0 |
| MRP-05 | git env never contains token outside `GIT_CONFIG_VALUE_0`; log sanitiser masks 32-hex; masked URL format | unit | `pytest .../test_secrets.py -q` | ❌ Wave 0 |
| MRP-05/06 | end-to-end secret hygiene scans | e2e | verify script | ❌ Wave 0 |

Unit tests run with real `git` (present on GitHub runners and dev hosts). For HTTP error paths without Docker, tests
can use `git -c protocol.file.allow=always` and `file://` URLs for success paths; the 401/404 stderr rows come from the
verify script's fixture (or a tiny `http.server` that returns fixed status codes for `info/refs`, which is enough for
classification).

### Sampling Rate

- **Per task commit:** quick pytest run.
- **Per wave merge:** quick run + `docker build` of the add-on.
- **Phase gate:** pytest + verify script green; `make lint validate-addons validate-versions`.

### Wave 0 Gaps

- [ ] `marketplace-repo-proxy/tests/conftest.py` + test files above
- [ ] CI: new job `marketplace-repo-proxy` **appended at the end** of `.github/workflows/lint.yml` (checkout with
      `persist-credentials: false`, Python 3.12, `pip install 'pytest==9.1.1' 'pyyaml==6.0.3'`,
      `python -m pytest marketplace-repo-proxy/tests -q`)

## Security Domain

### Applicable ASVS Categories (L1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Process separation (sync holds PAT; lighttpd clean env, unprivileged); read-only by design (token scope, no push config, receivepack off) |
| V2 Authentication | yes (capability URL) | 128-bit `secrets.token_hex(16)` per user; upstream PAT via header only |
| V3 Session Management | no | stateless git requests |
| V4 Access Control | yes | Symlink existence = authorization; uniform 404; revocation by unlink; `0711` dirs prevent hash enumeration |
| V5 Input Validation | yes | Supervisor schema regexes + Python re-validation of owner/repo/branch/user/hash; lighttpd allow-list regex; `git check-ref-format` |
| V6 Cryptography | yes | `secrets` module only; no custom crypto |
| V7 Error Handling and Logging | yes | `server.breakagelog=/dev/null`; sanitiser for git stderr; masked URLs; never `GIT_TRACE*` or lighttpd `debug.*` |
| V8 Data Protection | yes | `/data` 0700, written files 0600, `access.lock`/trigger in `/run` (0700) |
| V9 Communications | partially | Internal plain HTTP by design (D-02); TLS at reverse proxy in Phase 5; upstream `GIT_ALLOW_PROTOCOL=https` |
| V12 Files and Resources | yes | Empty docroot; CGI only via alias; symlink targets fixed; temp-dir-then-rename for new repos |
| V14 Configuration | yes | `http.receivepack=false`, `http.getanyfile=false`, invalid `pushurl`, no `remote.origin.mirror` |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hash leak via logs (CGI stderr, debug logs) | Information disclosure | `breakagelog=/dev/null`; no lighttpd debug; sanitiser; verify-script scan |
| PAT leak via env/argv/config/URL | Information disclosure | Env only in git child; built-from-scratch env; lighttpd without `with-contenv`; scans of `/proc`, `/srv/git`, logs |
| PAT leak via test override | Information disclosure | Env-only switch, not settable via options; loud warning; status flag; static grep in verify |
| Path traversal via option values (`..`, `/`) | Tampering | Regex in schema + Python; paths built only from validated parts |
| Hash enumeration by a compromised CGI | Information disclosure | `0711` access dirs; `/data` 0700 |
| Push/write through the proxy | Tampering | receive-pack refused (403), allow-list, read-only PAT |
| Dumb-HTTP file read (config, packs) | Information disclosure | `getanyfile=false` (403), allow-list (404) |
| Stale symlink after restore/edit | Elevation (revoked user regains access) | Full rebuild at start + watcher reconcile |
| Hash brute force | Spoofing | 128-bit space; uniform 404 |
| Slow/hung upstream | DoS (sync) | lowSpeed limits + subprocess timeout; serving unaffected |
| Backup contains PAT and hashes | Information disclosure | Inherent to HA backups (options.json too); document in DOCS.md |

## Docs, CHANGELOG, version (question 12)

- **No version bump in Phase 1.** Phases 1-5 share `feat/marketplace-repo-proxy-v1`; CI builds images only on push to
  `main` (`build.yml` `on: push: branches: - main`), so nothing is published from this branch. ROADMAP Phase 5 /
  MRP-22 owns the bump via `make update-version`. The scaffold stays `0.1.0-0` (`config.yaml:3`
  `version: "0.1.0-0"`, `build.yaml:5` `VERSION: "0.1.0"`).
- `CHANGELOG.md`: add a `## [Unreleased]` section with Phase 1 entries (convention exists in `network-tools` and
  `gatus`).
- `DOCS.md`: options table (all MRP-01 keys, noting `register_local`/`api_enabled` take effect later), Phase 1 user
  management via `mrp` CLI (interim), the contracts section (or a link to it), and a security note (backups contain
  PAT and hashes). `README.md`: replace "Status: scaffold" text; badges untouched.
- Update the `description` in `config.yaml` (drop "(scaffold)") only in the version-bump commit or leave it for
  Phase 5. It is not a version field, but changing it on the branch is harmless.

## Sources

### Primary (HIGH confidence)
- Local prototype on `ghcr.io/home-assistant/amd64-base:3.24` (this session): s6-rc layout, env isolation, lighttpd
  matrix, CGI stderr leak + `breakagelog` fix, `safe.directory` path rule, `0711` dirs, shallow vs full mirror, git
  error messages, Python `-I -m` failure, package contents and sizes.
- Base image files: `/package/admin/s6-overlay/etc/s6-linux-init/skel/rc.init`, `/usr/lib/bashio/apps.sh`,
  `/usr/lib/bashio/config.sh`.
- home-assistant/supervisor @ `e610ca8` (via GitHub API): `supervisor/docker/app.py` (hostname, environment),
  `supervisor/apps/model.py` (hostname), `supervisor/apps/options.py` (schema grammar, optional keys),
  `supervisor/store/data.py` (add-on discovery), `supervisor/api/middleware/security.py` (api_bypass).
- hassio-addons/addon-nginx-proxy-manager (GitHub API): `user-bundles.d` layout, oneshot/longrun/finish scripts.
- Repo files read: scaffold, SPIKE.md, GOAL.md, CONTEXT, REQUIREMENTS, ROADMAP, `internal/verify-*.sh` (ntfy,
  secrets-sync, litellm), `secrets-sync/app/providers/gitsource.py`, `iac-runner/config.yaml`, `ntfy/tests/conftest.py`,
  `.github/workflows/lint.yml`, `Makefile`, `admin-ui/DOCS.md`.

### Secondary (MEDIUM confidence)
- lighttpd wiki `Mod_cgi` (CGI stderr goes to `server.breakagelog`; option list).
- github.com behaviour probed anonymously with a fake token against a nonexistent repository and a public repository.

### Tertiary (LOW confidence)
- Items in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (packages, paths and versions read in the image)
- Architecture (s6, lighttpd, symlinks, env isolation): HIGH (prototype)
- Sync/error mapping: HIGH for fixture messages, MEDIUM for GitHub's "valid token, no access" case
- Hostname: MEDIUM-HIGH (source + local; production confirmation in Phase 2)
- Contracts: proposal (no prior art to verify against); fields derived from Phase 3 needs in SPIKE/REQUIREMENTS

**Research date:** 2026-11-17
**Valid until:** 2026-12-17 (base image tag and Supervisor move monthly)
