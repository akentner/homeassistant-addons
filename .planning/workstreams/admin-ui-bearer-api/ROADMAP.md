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

**Plans**: 5/6 plans executed (sequential waves 1-6)

Plans:

- [x] 01-01-PLAN.md — Tracer: bearer-gated GET with an option token end to end; ingress characterisation test; lib 0.10.0
- [x] 01-02-PLAN.md — Ingress handler on the shared JSON base, `serve(server, *more)`, complete API request handling
- [x] 01-03-PLAN.md — Gate on every method, parser error and credential variant; one byte-identical 401
- [x] 01-04-PLAN.md — `OptionToken` validation with the 16-character minimum (D-11), `GeneratedToken` (0600 SHA-256
      file, plaintext once, rotate), no secret in output
- [x] 01-05-PLAN.md — Package exports, library reference, rule R-16 in DOCS and the demo rules view
- [ ] 01-06-PLAN.md — admin-ui 0.4.0-0 via `make update-version`, lib 0.10.0 into all consumers via
      `make sync-admin-ui`, subpatch bump (`NO_TAG=yes`) for every consumer the sync changes, builds, checks

## Progress

| Phase                   | Plans Complete | Status      | Completed |
| ----------------------- | -------------- | ----------- | --------- |
| 1. Bearer API listener  | 5/6 | In Progress | -         |
