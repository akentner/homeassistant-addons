# Roadmap: marketplace-repo-proxy

## Overview

Turn the `marketplace-repo-proxy` scaffold into a working add-on: it mirrors private GitHub add-on repositories with a
read-only PAT and serves them to HA Supervisors over smart HTTP under `/repo/<owner>/<repo>/<hash>`, with one hash per
user. It registers itself in the local store, has an ingress management page on the admin-ui blueprint, a provisioning
REST API for IaC, and can be published on a domain through a reverse proxy. Design and evidence:
`marketplace-repo-proxy/SPIKE.md` (merged in #113).

Branch: `feat/marketplace-repo-proxy-v1` (worktree `feat-repo-proxy`). Phase 4 depends on the sibling workstream
`admin-ui-bearer-api` (bearer listener in the admin-ui skeleton) being merged and released.

## Phases

- [ ] **Phase 1: Git serving core** - Options, sync service, lighttpd smart HTTP, access store with per-user hashes
- [ ] **Phase 2: Supervisor integration** - `hassio_role: manager`, self-registration, store reload, live E2E test
- [ ] **Phase 3: Management GUI** - Ingress page on admin-ui: repositories, users, hashes, sync now
- [ ] **Phase 4: Provisioning API** - Bearer-token REST API for IaC on its own port
- [ ] **Phase 5: Public exposure and release** - Public URLs via reverse proxy, HTTPS clone test, docs, release

## Phase Details

### Phase 1: Git serving core

**Goal**: The add-on syncs configured private repositories and serves them read-only over smart HTTP under
`/repo/<owner>/<repo>/<hash>`, one hash per user, without any GUI.
**Depends on**: Nothing (first phase)
**Requirements**: MRP-01, MRP-02, MRP-03, MRP-04, MRP-05, MRP-06
**Success Criteria** (what must be TRUE):

1. With a valid PAT and one configured repository, `git clone --depth 1` of a user's store URL from another container
   on the same network returns the configured branch, and an upstream push shows up after the next sync.
2. Unknown owner, repository or hash, `/repo/`, dumb-HTTP paths and the CGI path return 404 (or 403 for dumb
   `info/refs`); `git push` and `git-receive-pack` are refused.
3. Query parameters on the store URL are accepted and ignored; `#branch` works.
4. Removing a user's entry from `/data/access.json` revokes that URL at the next request; other users keep access.
5. The PAT never appears in logs, the bare repositories' config, lighttpd's environment or the served data; no full
   hash appears in logs.
6. `internal/verify-marketplace-repo-proxy.sh` builds the image and proves 1-5 against a local upstream fixture.

**Plans**: 6/6 plans executed

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — (wave 1) Tracer: one user clones one private repository end to end; `mrp users add`

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — (wave 2) Sync: failure classification, status.json contract, "Sync now" trigger and interval loop
- [x] 01-03-PLAN.md — (wave 2) Access lifecycle: revoke, `mrp` CLI, access-watch service for hand edits
- [x] 01-04-PLAN.md — (wave 2) Startup log with masked URLs, init failure policy, options/logging tests + CI job

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-05-PLAN.md — (wave 3) Full verify script: criteria 1-5 (branches, matrix, revocation, auth failure, secrets)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 01-06-PLAN.md — (wave 4) Docs (translations, DOCS.md, README, CHANGELOG [0.1.0-1]), SPIKE fixes, bump 0.1.0-1

### Phase 2: Supervisor integration

**Goal**: The local Supervisor gets the proxy's repositories automatically and sees upstream changes within minutes.
**Depends on**: Phase 1
**Requirements**: MRP-07, MRP-08, MRP-09, MRP-10, MRP-11
**Success Criteria** (what must be TRUE):

1. With `register_local: true` the internal store URL of the `local` system user appears in the HA store without manual
   steps, and its add-ons are listed.
2. After an upstream change and the next sync, the update is visible in the store without waiting for the 3-hour
   Supervisor reload.
3. Rotating or removing the `local` user never removes a store repository that installed add-ons still use; the
   leftover is reported.
4. Only the allow-listed Supervisor calls are made; `SUPERVISOR_TOKEN` never reaches lighttpd.
5. Live E2E on the production host: store add → install a test add-on → upstream change → update shown → cleanup
   (test add-on and store repository removed).

**Plans**: TBD

### Phase 3: Management GUI

**Goal**: An ingress page shows the published repositories and manages users and hashes.
**Depends on**: Phase 1 (Phase 2 for the registration status)
**Requirements**: MRP-12, MRP-13, MRP-14, MRP-15, MRP-16
**Success Criteria** (what must be TRUE):

1. The page runs on the admin-ui lib and skeleton (`make sync-admin-ui ADDON=marketplace-repo-proxy`), passes the
   rules scanner and its node/pytest tests in CI, de and en.
2. Repositories view shows sync status, last sync, HEAD and found add-ons; "Sync now" triggers a sync.
3. Access view adds a user (new hash), revokes and rotates (type-to-confirm, rotation warns about reinstalling) and shows
   internal and public store URLs to copy.
4. "Last fetch" per user is shown, fed by the lighttpd access-log sink, which never logs the hash.
5. The GUI port is never published; requests outside ingress get 403.

**Plans**: 1/6 plans executed

Plans:
**Wave 1**
- [x] 03-01-PLAN.md — (wave 1) Tracer: ingress page with the Repositories overview; s6 `gui`, gate, top-bar version
- [ ] 03-02-PLAN.md — (wave 1) Access-log sink programs and the `/data/last-fetch.json` contract

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 03-06-PLAN.md — (wave 2) Sync now, registration slot, node tests, admin-ui consumer wiring, CI

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 03-03-PLAN.md — (wave 3) Access view: add, revoke, rotate (type-to-confirm), store URLs, source badge

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 03-04-PLAN.md — (wave 4) Sink in the container (lighttpd pipe, s6 `fetchlog`), last fetch in the Access view

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 03-05-PLAN.md — (wave 5) Info view, DOCS/README/CHANGELOG, version bump from origin/main (last step)

### Phase 4: Provisioning API

**Goal**: IaC (OpenTofu, Ansible) can provision users per repository through a bearer-token REST API.
**Depends on**: Phase 3, workstream `admin-ui-bearer-api` (merged and synced)
**Requirements**: MRP-17, MRP-18, MRP-19
**Success Criteria** (what must be TRUE):

1. With `api_enabled: true` the API listens on its own unpublished port; without a valid bearer token every route
   returns 401.
2. `PUT /api/v1/repositories/{owner}/{repo}/users/{user}` is idempotent, accepts an optional client-supplied hash and
   returns `409 hash_mismatch` for a different hash; `GET`, `DELETE` and `rotate` behave as in SPIKE.md.
3. Users created via the API are marked as IaC-managed in the GUI.
4. DOCS.md shows OpenTofu and Ansible examples and a threat-model note.

**Plans**: TBD

### Phase 5: Public exposure and release

**Goal**: Store URLs work over HTTPS on a public domain through a reverse proxy, and the add-on is documented and
released.
**Depends on**: Phase 3
**Requirements**: MRP-20, MRP-21, MRP-22
**Success Criteria** (what must be TRUE):

1. With `public_url` set, GUI and API show public store URLs; the add-on itself stays plain HTTP.
2. A Supervisor (or `git clone --depth 1` with the same kwargs) clones through the reverse proxy over HTTPS; no
   caching, no path logging on the proxy side is documented and checked.
3. DOCS.md, README.md and the repo CLAUDE.md (own-code exception list) are complete; `stage: experimental` is removed
   or kept by explicit decision; version bumped via `make update-version`.

**Plans**: TBD

## Progress

| Phase                          | Plans Complete | Status      | Completed |
| ------------------------------ | -------------- | ----------- | --------- |
| 1. Git serving core            | 6/6 | In Progress | -         |
| 2. Supervisor integration      | 0/TBD          | Not started | -         |
| 3. Management GUI              | 1/6 | In Progress | -         |
| 4. Provisioning API            | 0/TBD          | Not started | -         |
| 5. Public exposure and release | 0/TBD          | Not started | -         |
