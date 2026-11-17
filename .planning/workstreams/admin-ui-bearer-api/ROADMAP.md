# Roadmap: admin-ui-bearer-api

## Overview

Add a bearer-token API listener to the admin-ui Python skeleton (`admin-ui/app/web/skeleton/`), next to the ingress
server, so add-ons can offer an IaC/provisioning REST API on a separate port without weakening the ingress gate (R-01).
First consumers: `marketplace-repo-proxy` (workstream `marketplace-repo-proxy`, Phase 4) and later the ntfy IaC API
(ROADMAP Phase 25 in the main checkout). Design context: `marketplace-repo-proxy/SPIKE.md`, section "Provisioning API
(IaC)".

Branch: `feat/admin-ui-bearer-api` (worktree `feat-admin-ui-bearer-api`). Changes only in `admin-ui/` plus the sync
output for consumers; consumer copies are never edited by hand (R-15).

## Phases

- [ ] **Phase 1: Bearer API listener** - Token-gated JSON API server in the skeleton, token sources, rule R-16, release

## Phase Details

### Phase 1: Bearer API listener

**Goal**: An add-on can serve a JSON API on its own port that only answers requests with a valid bearer token, using
the same `Router`, `Request`, `ApiError` and error codes as the ingress GUI.
**Depends on**: Nothing (first phase)
**Requirements**: AUB-01, AUB-02, AUB-03, AUB-04, AUB-05, AUB-06
**Success Criteria** (what must be TRUE):

1. A new skeleton entry point (for example `make_api_server(router, port, verifier, bind=...)`) serves only JSON routes
   of its own `Router`; without `Authorization: Bearer <valid token>` every method and path returns 401 with
   `WWW-Authenticate: Bearer` and code `unauthorized`, and static files, the index and the icon are never served.
2. The ingress server's behaviour is unchanged: all existing gate tests (R-01, public routes) pass untouched.
3. Two token verifiers exist and are tested: option token (constant-time compare against an add-on option) and
   generated token (256-bit, only its SHA-256 stored with mode 0600, plaintext returned once, rotation); neither ever
   logs the token or the `Authorization` header.
4. Rule R-16 is documented in `admin-ui/DOCS.md` with its enforcing tests, and the library reference lists the new
   public names (doc test green).
5. admin-ui version bumped via `make update-version`, `make sync-admin-ui` run for all consumers, consumer docker
   builds and `make check-admin-ui-sync`, `make check-admin-ui-rules`, `make test-admin-ui` green.

**Plans**: TBD

## Progress

| Phase                   | Plans Complete | Status      | Completed |
| ----------------------- | -------------- | ----------- | --------- |
| 1. Bearer API listener  | 0/TBD          | Not started | -         |
