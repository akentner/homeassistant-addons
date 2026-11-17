# Phase 1: Git serving core - Context

**Gathered:** 2026-11-17
**Status:** Ready for planning
**Source:** Discuss step skipped by instruction. Decisions are taken from `marketplace-repo-proxy/SPIKE.md` (section
"Decisions" is binding, the design sections are the agreed design). Items the spike does not answer are listed under
"Claude's Discretion" or "Open questions"; they are not decided here.

<domain>
## Phase Boundary

The add-on syncs the configured private GitHub repositories with a read-only PAT and serves them read-only over smart
HTTP under `/repo/<owner>/<repo>/<hash>`, one hash per user, without any GUI, API or Supervisor integration.

In scope: options schema (MRP-01), sync service (MRP-02), lighttpd + `git http-backend` (MRP-03), access store and
symlink tree (MRP-04), secret hygiene (MRP-05), `internal/verify-marketplace-repo-proxy.sh` against a local upstream
fixture (MRP-06).

Out of scope (later phases): `hassio_api`/`hassio_role`, self-registration, `local` system user, store reload
(Phase 2); ingress GUI, access-log sink, "last fetch" (Phase 3); provisioning API and its port (Phase 4); public URL
docs, HTTPS clone test, release and version decision (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Server
- **D-01:** Git is served by lighttpd + `git http-backend` (smart HTTP only). The lighttpd config from SPIKE.md
  ("Server: lighttpd + git http-backend") is the reference: `mod_rewrite`, `mod_alias`, `mod_setenv`, `mod_cgi`; empty
  docroot `/var/empty`; port `8080`; runs as user/group `lighttpd`; the alias to `git-http-backend` is mapped only
  inside the positive allow-list condition for `info/refs` and `git-upload-pack` under
  `/repo/<owner>/<repo>/<32 hex>/` (a negated `url.access-deny` block does not work, see SPIKE pitfall).
- **D-02:** Port `8080/tcp` stays unpublished by default (`8080/tcp: null`). No TLS inside the add-on.

### URL scheme
- **D-03:** Store URL path is `/repo/<owner>/<repo>/<hash>`; `<owner>` is the GitHub owner/organisation, `<repo>` the
  GitHub repository name, `<hash>` 32 lowercase hex chars. Unknown owner, repo or hash all give the same 404.
- **D-04:** Query parameters on the store URL are accepted and ignored, via the two `url.rewrite-once` rules from
  SPIKE.md. `#branch` is handled client-side (the Supervisor strips it before calling git) and must keep working.

### Access tokens and disk layout
- **D-05:** One access token (hash) per `(repository, user label)`: random 128 bit from `/dev/urandom`, 32 lowercase hex,
  generated once, persisted in `/data/access.json`. Random, not HMAC-derived.
- **D-06:** Disk layout: bare repository `/srv/git/repos/<owner>/<repo>.git` (written only by the sync service); one
  symlink per token `/srv/git/access/<owner>/<repo>/<hash> -> /srv/git/repos/<owner>/<repo>.git`;
  `GIT_PROJECT_ROOT=/srv/git/access`. Revoking removes the symlink and takes effect at the next request without a
  lighttpd reload. The symlink tree is rebuilt from `/data/access.json` at every start, so stray symlinks cannot
  survive.
- **D-07:** Each `access.json` entry carries repository, user label, hash, created timestamp and source
  (`gui`/`api`/`system`) (MRP-04).

### Upstream credential
- **D-08:** One fine-grained GitHub PAT (`Contents: read-only`) in the `github_token` option (schema type `password`).
  It is passed only at fetch time and only through the environment: `GIT_CONFIG_COUNT=1`,
  `GIT_CONFIG_KEY_0=http.extraHeader`, `GIT_CONFIG_VALUE_0="Authorization: Basic base64(x-access-token:<token>)"`.
  Never in a remote URL, never in a repository config, never in lighttpd's environment or process tree.
- **D-09:** 401/403 from upstream produce a clear log line and status code `auth_failed` (expired or revoked token),
  without the token.

### Sync
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

### Read-only guarantees
- **D-15:** Each bare repository sets `http.receivepack=false` and `http.getanyfile=false`. Repositories are owned by
  root and readable for `lighttpd`; `/etc/gitconfig` lists `safe.directory` for the repositories (otherwise git refuses
  with "dubious ownership"). Push and `git-receive-pack` are refused (403); dumb `info/refs` returns 403.

### Options
- **D-16:** Options schema (MRP-01): `github_token` (password), `sync_interval` (default 15, minimum 5), `public_url`
  (optional, empty = internal only), `repositories` (list of `{repository: owner/repo, branch: optional}`),
  `register_local` (default true), `api_enabled` (default false), `log_level`. `register_local` and `api_enabled` are
  schema-only in this phase; their behaviour comes in Phases 2 and 4. Users and hashes never appear in the options.

### Logging and secrets
- **D-17:** The PAT never appears in logs, the options export, a repository config, lighttpd's environment or the served
  data. No full hash ever appears in logs. The startup log lists user labels and **masked** store URLs only (MRP-05).
  Note: SPIKE.md "Read-only guarantees" item 6 says "log the store URLs once at startup"; MRP-05 is the later and stricter
  rule and wins.

### Tests
- **D-18:** Tests and `internal/verify-marketplace-repo-proxy.sh` use a local upstream fixture, never real GitHub. A
  test-only upstream override makes that possible; it must not be reachable through the add-on options in production.
- **D-19:** The verify script builds the image and proves ROADMAP Phase 1 success criteria 1-5 (clone, fetch after an
  upstream change, 404/403 matrix, query tolerance and `#branch`, revocation, secret hygiene).

### Interfaces for later phases
- **D-20:** `/data/status.json`, `/data/access.json` and the sync trigger file are contracts that the Phase 3 GUI and
  the Phase 4 API consume. Their schemas (field names, types, file locations, write semantics) are fixed and documented
  in this phase. `/data/access.json` is written atomically (temp file + rename) under one lock; in Phase 3 the GUI and
  the API share one service module for it in one Python process, so the Phase 1 writer must not conflict with that
  design.

### Repository rules (CLAUDE.md)
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

</decisions>

<specifics>
## Specific Ideas

- SPIKE.md "Observed responses" table is the expected 404/403/200 matrix for the verify script.
- The store hostname depends on the install source (this repository's CI image); the startup log should print the URL
  the local Supervisor would use. How the add-on learns its own hostname without `hassio_api` is a research item.
- Backups include `/data`, so a restore keeps the tokens and therefore the URLs; nothing token-related may live outside
  `/data`.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design and decisions
- `marketplace-repo-proxy/SPIKE.md` — binding "Decisions"; server config, URL scheme, access tokens, sync, read-only
  guarantees, upstream authentication, expected response matrix
- `marketplace-repo-proxy/GOAL.md` — goal, scope, success criteria
- `.planning/workstreams/marketplace-repo-proxy/REQUIREMENTS.md` — MRP-01 to MRP-06
- `.planning/workstreams/marketplace-repo-proxy/ROADMAP.md` — Phase 1 success criteria 1-6

### Repository rules
- `CLAUDE.md` — own-code exception, 3-file versioning, local docker build, verify-script concurrency
- `admin-ui/DOCS.md` — blueprint the Phase 3 GUI uses (constrains the access-store module shape, D-20)

### Existing scaffold
- `marketplace-repo-proxy/config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`, `README.md`, `CHANGELOG.md`,
  `translations/en.yaml`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `internal/verify-*.sh` scripts (for example `verify-ntfy-scaffold.sh`, `verify-secrets-sync-no-secret-leak.sh`,
  `verify-litellm-no-secret-leak.sh`): patterns for image build, container run and secret-leak checks.
- `admin-ui/app/` and `admin-ui/tests/`: Python stdlib server skeleton and pytest layout the Phase 3 GUI will use.

### Established Patterns
- Add-on tests run in CI via `.github/workflows/lint.yml` (pytest per add-on directory).
- `run.sh` uses bashio; `init: false` is already set, so s6-overlay is PID 1.

### Integration Points
- `marketplace-repo-proxy/` add-on directory (scaffold from PR #113).
- New `internal/verify-marketplace-repo-proxy.sh`.

</code_context>

<deferred>
## Deferred Ideas

- Supervisor integration, `local` system user, store reload (Phase 2).
- Access-log sink and "last fetch" (Phase 3).
- Provisioning API, bearer token (Phase 4).
- Public URL documentation, HTTPS clone test, version bump and stage decision (Phase 5).
- Per-repository deploy keys (SPIKE "Upstream authentication", later, optional).

</deferred>

---

*Phase: 01-git-serving-core*
*Context gathered: 2026-11-17 (from SPIKE.md, discuss step skipped)*
