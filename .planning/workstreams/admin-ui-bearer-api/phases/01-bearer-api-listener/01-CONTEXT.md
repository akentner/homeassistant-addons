# Phase 1: Bearer API listener - Context

**Gathered:** 2026-11-17
**Status:** Ready for planning
**Source:** No discuss step. Decisions are taken from `marketplace-repo-proxy/SPIKE.md` (section "Decisions" is binding,
section "Provisioning API (IaC)" gives the detail), the workstream `REQUIREMENTS.md` (AUB-01..AUB-06) and the success
criteria of Phase 25 "ntfy IaC API" in the main `.planning/ROADMAP.md` (read only).

<domain>
## Phase Boundary

A second, separate server entry point in the admin-ui Python skeleton (`admin-ui/app/web/skeleton/`) that serves a JSON
API on its own port and answers only requests with a valid bearer token. It reuses `Router`, `Request`, `ApiError`,
`ERROR_STATUS` and the API security headers of the ingress server. The phase delivers the listener, two token
verifiers, rule R-16 in `admin-ui/DOCS.md` with enforcing tests, and the release (admin-ui version bump, sync to all
consumers, consumer docker builds, checks green).

Not in this phase: any consumer endpoint (proxy `/api/v1/repositories/...`, ntfy `/v1/state`), consumer wiring of the
listener, add-on options such as `api_enabled`, the management-page UI that shows the generated token once.

</domain>

<decisions>
## Implementation Decisions

### Placement and separation
- **D-01:** The bearer-gated listener lives in the admin-ui skeleton next to the ingress server, so every GUI (proxy,
  ntfy) reuses it. It is a change in `admin-ui/` only, with its own version bump, tests and `make sync-admin-ui`.
  Consumer copies are never edited by hand (R-15). (SPIKE "Decisions": "The bearer-token listener for the provisioning
  API goes into the admin-ui skeleton.")
- **D-02:** The bearer listener is a second, separate server with its own port. The ingress gate (R-01), the
  `public=True` escape hatch and all existing gate and public-route tests stay unchanged; the API is never served by the
  ingress server and never through `public=True` routes.
- **D-03:** The API port is unpublished by default and is never routed through ingress or a public reverse proxy
  (Cloudflare, Traefik) by default; publishing it for LAN/Tailscale runs is the operator's choice. The listener takes a
  bind address so a consumer can bind to a LAN/Tailscale address (ntfy Phase 25 criterion 4). This becomes rule R-16.

### Request handling
- **D-04:** JSON only, stable error codes (R-14 style), `Cache-Control: no-store`, the existing `MAX_BODY` limit, the
  same body rules as the ingress server; no static files, no index, no icon, no CORS.
- **D-05:** The bearer check runs first for every method and path, including unknown paths, `HEAD` and `OPTIONS`.
  Missing, malformed or wrong token all give the identical `401` response with code `unauthorized` and
  `WWW-Authenticate: Bearer`.

### Tokens
- **D-06:** Generated token (proxy model, like the retired `terraform-bridge` add-on): 256-bit random from `secrets`,
  generated on first start, only its SHA-256 stored in a file with mode `0600` (the proxy will use `/data/api-token`),
  plaintext available exactly once after creation or rotation, rotatable, never logged and never written to stdout.
- **D-07:** Option token (ntfy Phase 25 model): the token value comes from an add-on `password` option and is compared
  in constant time (`hmac.compare_digest`).
- **D-08:** No token, no API: an empty or missing token disables the API, and the listener refuses to start rather
  than listen unauthenticated. (The consumer-level `api_enabled` option, default `false`, is consumer work.)
- **D-09:** No secret in logs: the request log never contains the `Authorization` header or a token value.

### Release
- **D-10:** Release follows the repo rules: admin-ui version only via `make update-version`, consumer copies only via
  `make sync-admin-ui`, a local `docker build` for every consumer whose image content changes, then
  `make check-admin-ui-sync`, `make check-admin-ui-rules` and `make test-admin-ui` green. Docker verify scripts are not
  run in parallel with other worktrees.

### Claude's Discretion
- Public names and signatures (for example `make_api_server(router, port, verifier, bind=...)`, a verifier protocol,
  class names `OptionToken` / `GeneratedToken`), module layout (new module vs. extension of `server.py`), and how the
  shared request/response code is factored between the two handlers, as long as the ingress handler's observable
  behaviour stays identical.
- How `unauthorized` (401) enters the error table (`ERROR_STATUS` entry vs. `register_error_code`).
- Default bind address, provided it is explicit in the API and documented in R-16.
- Whether the lib version (`lib.lock`, `make release-admin-ui-lib`) moves together with the admin-ui add-on version;
  follow the existing Distribution section of `admin-ui/DOCS.md`.

</decisions>

<specifics>
## Specific Ideas

- First consumer: `marketplace-repo-proxy` provisioning API on port `8098`, prefix `/api/v1`, generated token stored as
  SHA-256 in `/data/api-token`, plaintext shown once on the management page. Second consumer: ntfy Phase 25 with an
  option token and an optional LAN/Tailscale bind.
- GUI and provisioning API of the proxy run in the same Python process (shared service module, one lock), so the
  listener must run alongside the ingress server in one process (separate `ThreadingHTTPServer`, separate thread).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design and decisions
- `marketplace-repo-proxy/SPIKE.md` — section "Provisioning API (IaC)" (listener, token, endpoints) and "Decisions"
  (binding).
- `.planning/workstreams/admin-ui-bearer-api/REQUIREMENTS.md` — AUB-01..AUB-06.
- `.planning/workstreams/admin-ui-bearer-api/ROADMAP.md` — Phase 1 success criteria.
- `.planning/ROADMAP.md` — Phase 25 "ntfy IaC API" success criteria (read only, do not edit).

### Blueprint rules and library contract
- `admin-ui/DOCS.md` — rules R-01..R-15, library reference (Python skeleton table), consumer recipe, distribution and
  release.
- `admin-ui/tests/test_docs.py` — checks that every public name appears in DOCS.md and the rule table format.
- `admin-ui/tests/test_sync.py`, `internal/sync-admin-ui.py` — sync, stamp, lock and drift check.

### Code
- `admin-ui/app/web/skeleton/server.py` — ingress handler, `_send`, `_json`, `_read_body`, `serve`.
- `admin-ui/app/web/skeleton/router.py`, `errors.py`, `headers.py`, `__init__.py`.
- `admin-ui/tests/test_skeleton_server.py`, `admin-ui/tests/test_public_routes.py` — gate tests that must stay
  unchanged and green.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Router` / `Request` / `Download`: route table and request object, reused unchanged by the API listener.
- `ApiError`, `ERROR_STATUS`, `register_error_code`: stable error codes; `unauthorized` (401) is new.
- `security_headers("api", csp)`: API headers (`nosniff`, `Referrer-Policy`), no CSP on API responses.
- `make_handler._read_body`: body limit, JSON content-type check, chunked rejection.
- `serve(server)`: SIGTERM/SIGINT shutdown for one server; two servers in one process need a pattern for both.

### Established Patterns
- `log_message` is silenced in the ingress handler; tracebacks go to stdout only.
- Error responses close the connection because the body may be unread.

### Integration Points
- `app.web.skeleton` is delivered to consumers as `app.web.admin_ui` by `make sync-admin-ui`.

</code_context>

<deferred>
## Deferred Ideas

- Proxy endpoints and `api_enabled` option: workstream `marketplace-repo-proxy`, Phase 4.
- ntfy IaC API and the update of Phase 25's text to reference this listener: main checkout.
- Management-page display and rotation button for the generated token: consumer GUI work.

</deferred>

---

*Phase: 01-bearer-api-listener*
*Context gathered: 2026-11-17 from SPIKE.md decisions (discuss step skipped by instruction)*
