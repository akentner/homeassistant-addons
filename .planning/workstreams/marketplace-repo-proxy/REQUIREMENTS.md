# Requirements: marketplace-repo-proxy

Source of the design and its evidence: `marketplace-repo-proxy/SPIKE.md`.

## Phase 1: Git serving core

- [ ] **MRP-01**: Options schema: `github_token` (password), `sync_interval` (minutes, default 15, minimum 5),
  `public_url` (optional), `repositories` (list of `{repository: owner/repo, branch: optional}`), `register_local`
  (default true), `api_enabled` (default false), `log_level`.
- [ ] **MRP-02**: Sync service (own s6 service, only holder of the PAT): one bare repository per source created with
  `git init --bare` and an explicit fetch refspec for the configured branch (no `--mirror`, no push config), `HEAD` set
  to it, `fetch --prune`, PAT passed only via `GIT_CONFIG_*` environment, interval plus trigger file, status written to
  `/data/status.json` with stable codes (`ok`, `auth_failed`, `not_found`, `no_repository_yaml`).
- [x] **MRP-03**: lighttpd + `git http-backend` as unprivileged user: allow-list for `info/refs` and `git-upload-pack`
  under `/repo/<owner>/<repo>/<32 hex>/`, rewrite rules that accept and ignore query parameters, empty docroot,
  `http.getanyfile=false`, `http.receivepack=false`, `safe.directory` in `/etc/gitconfig`.
- [ ] **MRP-04**: Access store `/data/access.json` (repository, user label, hash, created, source `gui`/`api`/`system`),
  random 128-bit hashes, symlink tree `/srv/git/access/<owner>/<repo>/<hash>` rebuilt at every start.
- [x] **MRP-05**: Secret hygiene: PAT never in logs, repository config or lighttpd's environment; hashes never in logs
  (startup lists user labels and masked URLs only).
- [x] **MRP-06**: `internal/verify-marketplace-repo-proxy.sh`: builds the image, runs it against a local upstream fixture
  (test-only upstream override), proves clone, fetch, 404/403 matrix, query tolerance, revocation and secret hygiene.

## Phase 2: Supervisor integration

- [ ] **MRP-07**: `hassio_api: true`, `hassio_role: manager`; one Supervisor client module with an allow-list of method
  and path (`GET/POST /store/repositories`, `DELETE /store/repositories/{slug}`, `POST /store/reload`).
- [ ] **MRP-08**: Self-registration: system user `local` per repository; its internal URL is added to the store when
  `register_local` is true and it is missing.
- [ ] **MRP-09**: After a sync that changed refs, `POST /store/reload`, at most once per sync interval.
- [ ] **MRP-10**: Rotation/removal of the `local` user adds the new URL first and only then tries to remove the old
  repository; a refusal (installed add-ons) is reported, never forced.
- [ ] **MRP-11**: Live E2E on the production host with cleanup (test add-on and store repository removed afterwards).

## Phase 3: Management GUI

- [ ] **MRP-12**: Ingress GUI on the admin-ui lib and skeleton (`ingress_port` 8099, never published), rules R-01 to
  R-15, de/en strings, node and pytest tests in CI.
- [ ] **MRP-13**: Repositories view with sync status, last sync, HEAD short SHA, found add-ons, registration status and
  "Sync now".
- [ ] **MRP-14**: Access view: add user, revoke and rotate (type-to-confirm with the user label), internal and public
  store URLs as `CopyField`, source badge (`gui`/`api`/`system`).
- [ ] **MRP-15**: lighttpd access-log sink (`accesslog.filename = "|…"`): maps hash to user label, records last fetch,
  logs `fetch: <user> → <owner>/<repo>` only.
- [ ] **MRP-16**: Info view with setup steps (store URL, reverse proxy notes, rotation procedure).

## Phase 4: Provisioning API

- [ ] **MRP-17**: API listener from the admin-ui skeleton (workstream `admin-ui-bearer-api`) on port 8098, unpublished by
  default, enabled by `api_enabled`; token generated (256-bit), stored as SHA-256, shown once and rotatable in the GUI.
- [ ] **MRP-18**: Endpoints under `/api/v1` as in SPIKE.md: list repositories, list/get users, idempotent `PUT` with
  optional client-supplied hash (`409 hash_mismatch`), `DELETE`, `rotate`; stable error codes.
- [ ] **MRP-19**: DOCS.md: OpenTofu (generic REST/http provider) and Ansible `uri` examples, threat-model note.

## Phase 5: Public exposure and release

- [ ] **MRP-20**: `public_url` drives the public store URLs in GUI and API; DOCS.md covers Traefik and Cloudflare Tunnel
  (TLS at the proxy, no caching of `/repo/*`, no path logging, API port never routed publicly).
- [ ] **MRP-21**: HTTPS clone through the reverse proxy verified (shallow clone, fetch, `ls-remote`).
- [ ] **MRP-22**: Docs complete (DOCS.md, README.md, repo CLAUDE.md own-code exception list), version bump via
  `make update-version`, decision on `stage: experimental`.

## Out of scope

- HACS (uses the GitHub API, not git), private submodules, private container images (registry credentials stay a host
  setting).
- TLS inside the add-on.
