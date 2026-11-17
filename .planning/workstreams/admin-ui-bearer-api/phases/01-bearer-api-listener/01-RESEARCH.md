# Phase 1: Bearer API listener - Research

**Researched:** 2026-11-17
**Domain:** Python stdlib HTTP server (`http.server`), bearer-token auth, admin-ui skeleton distribution and release
**Confidence:** HIGH (all in-repo claims read this session; stdlib behaviour probed on Python 3.12.15 and 3.14.10)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Placement and separation
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

#### Request handling
- **D-04:** JSON only, stable error codes (R-14 style), `Cache-Control: no-store`, the existing `MAX_BODY` limit, the
  same body rules as the ingress server; no static files, no index, no icon, no CORS.
- **D-05:** The bearer check runs first for every method and path, including unknown paths, `HEAD` and `OPTIONS`.
  Missing, malformed or wrong token all give the identical `401` response with code `unauthorized` and
  `WWW-Authenticate: Bearer`.

#### Tokens
- **D-06:** Generated token (proxy model, like the retired `terraform-bridge` add-on): 256-bit random from `secrets`,
  generated on first start, only its SHA-256 stored in a file with mode `0600` (the proxy will use `/data/api-token`),
  plaintext available exactly once after creation or rotation, rotatable, never logged and never written to stdout.
- **D-07:** Option token (ntfy Phase 25 model): the token value comes from an add-on `password` option and is compared
  in constant time (`hmac.compare_digest`).
- **D-08:** No token, no API: an empty or missing token disables the API, and the listener refuses to start rather
  than listen unauthenticated. (The consumer-level `api_enabled` option, default `false`, is consumer work.)
- **D-09:** No secret in logs: the request log never contains the `Authorization` header or a token value.

#### Release
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

### Deferred Ideas (OUT OF SCOPE)
- Proxy endpoints and `api_enabled` option: workstream `marketplace-repo-proxy`, Phase 4.
- ntfy IaC API and the update of Phase 25's text to reference this listener: main checkout.
- Management-page display and rotation button for the generated token: consumer GUI work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID     | Description (REQUIREMENTS.md)                                                                                   | Research Support                                                                                                  |
| ------ | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| AUB-01 | Skeleton API server on own port + bind, reusing `Router`, `Request`, `ApiError`, `ERROR_STATUS`, API headers; JSON only, `no-store`, `MAX_BODY`, no static, no CORS | Pattern 1 (shared `_JsonHandler` base), Pattern 2 (`make_api_server`), Pitfall 1 (`ERROR_STATUS` must not grow at import) |
| AUB-02 | Bearer gate on every method and path incl. unknown paths, `HEAD`, `OPTIONS`; identical 401 for all failures      | Pattern 3 (gate + `__getattr__` for any method + `send_error` override), Pitfalls 2-5, probe results              |
| AUB-03 | `OptionToken` (`compare_digest`) and `GeneratedToken` (256-bit, SHA-256 file 0600, plaintext once, `rotate()`); no token -> refuse to start | Pattern 4 (verifiers), Pattern 5 (atomic 0600 write), Pitfall 6 (`compare_digest` TypeError)                     |
| AUB-04 | No secret in logs: never the `Authorization` header or token values; generated token never on stdout             | Pitfall 7 (log paths in `http.server`/`socketserver`), header view hiding `Authorization`, `capfd` tests          |
| AUB-05 | Rule R-16 in DOCS.md with enforcing tests; library reference; `test_docs.py` and lib contract test green          | "R-16 ripple" table (6 files move together), test_docs format                                                     |
| AUB-06 | Release: `make update-version`, `make sync-admin-ui`, consumer docker builds, sync/rules/test checks green        | "Release mechanics" section: consumer list, lib vs add-on version, pre-commit drift hook ordering, build commands |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Ask before critical tasks (version bumps, CI changes); challenge risky approaches. [VERIFIED: CLAUDE.md "Behavior Guidelines"]
- No `Co-Authored-By` / AI attribution lines in commits or PRs. [VERIFIED: CLAUDE.md "Git Commit Conventions"]
- One add-on per branch, stage by path (`git add <addon>/ ...`), never `git add -A`. This phase legitimately stages
  `admin-ui/` plus the sync output in `coding-assistants/`, `haos-monitor/`, `ntfy/`, `secrets-sync/`. [VERIFIED: CLAUDE.md]
- In an add-on worktree write only `.planning/quick/` and workstream files; never `STATE.md`/`ROADMAP.md` of the main
  `.planning/`. Main `.planning/ROADMAP.md` Phase 25 is read only. [VERIFIED: CLAUDE.md, CONTEXT.md]
- Versions never by hand: `make update-version`. `admin-ui` and `haos-monitor` are own code (no `.upstream.yaml`,
  manual bumps). [VERIFIED: CLAUDE.md "Exception: haos-monitor and admin-ui"]
- `admin-ui` lib is distributed by `make sync-admin-ui`; consumer copies are never edited by hand. [VERIFIED: CLAUDE.md]
- Local `docker build` before committing Dockerfile changes (this phase changes no Dockerfile; D-10 still asks for
  builds of every consumer whose image content changes). [VERIFIED: CLAUDE.md, CONTEXT.md D-10]
- Docker verify scripts (`internal/verify-*.sh`) must not run in two worktrees at the same time. [VERIFIED: CLAUDE.md]
- HA base images only; Python scripts: module docstring, type hints, `pathlib`, 120-char lines. [VERIFIED: CLAUDE.md]
- Public repo: no hostnames, IPs (except the existing ingress peer constant), e-mails, personal names, tokens in files.
  `test_docs.py:27` enforces a `FORBIDDEN` list on DOCS.md. [VERIFIED: admin-ui/tests/test_docs.py:27]

## Summary

The skeleton is a small stdlib package (`admin-ui/app/web/skeleton/`, 576 lines) whose ingress handler lives in a
closure in `make_handler` (`server.py:56-184`). The bearer listener fits as a new module (`api.py`) plus a token module
(`tokens.py`), with the JSON response helpers (`_send`, `_json`, `_error`, `_read_body`, result rendering, exception
mapping) lifted into a module-level base class that both handlers inherit. A characterisation test of the ingress
responses, written before the refactor, makes "observable behaviour identical" provable. `serve()` gains `*more`
servers so one process runs ingress and API with one signal handler.

Three non-obvious findings drive the plan. (1) `unauthorized` must **not** be added to the static `ERROR_STATUS` dict:
ntfy pins the import-time table literally (13 entries) and checks an `errors.<code>` string for every entry, so a
static entry breaks ntfy's consumer tests after sync. Register it inside `make_api_server` instead. (2) Plain
`BaseHTTPRequestHandler` answers unknown methods (`TRACE`, `FOO`) with an HTML 501 **before** any gate, and parser
errors with HTML 400/414/505 that reflect input; on Python 3.14 an HTTP/0.9 `GET /x` reaches `do_GET` with
`self.headers = {}` (a dict, no `get_all`). The API handler needs a `__getattr__` for `do_*`, a `send_error` override
and dict-tolerant header access. (3) Adding rule R-16 ripples into six files (DOCS table, two Python tests, the demo
rules view, two string tables, one node test), because the demo GUI mirrors the rule table.

Release: the repo practice is one lib version per source change. Bump the lib `VERSION` to `0.10.0` and refresh the
lock in the **first** commit that touches skeleton sources (the non-strict pre-commit drift hook then only warns
"behind"), finish with `make release-admin-ui-lib VERSION=0.10.0` (syncs all four consumers, strict check, all tests),
and bump the admin-ui add-on with `make update-version ADDON=admin-ui VERSION=0.4.0 NO_TAG=yes`. Four consumers are
registered; three package the Python skeleton, `coding-assistants` packages only the static lib.

**Primary recommendation:** New modules `skeleton/api.py` + `skeleton/tokens.py`, shared `_JsonHandler` base in
`server.py` guarded by a pre-refactor characterisation test, lazy `register_error_code("unauthorized", 401)` in
`make_api_server`, lib `0.10.0`, admin-ui `0.4.0-0`, no consumer add-on version bumps (no consumer behaviour change).

## Architectural Responsibility Map

| Capability                              | Primary Tier                         | Secondary Tier             | Rationale                                                                                     |
| --------------------------------------- | ------------------------------------ | -------------------------- | --------------------------------------------------------------------------------------------- |
| Bearer gate (401 for everything)        | API / Backend (`skeleton/api.py`)    | —                          | Must run before routing in the request handler; nothing outside the process can enforce it    |
| Token verification (option, generated)  | API / Backend (`skeleton/tokens.py`) | Storage (`/data` hash file) | Constant-time compare in process; only the SHA-256 is persisted                              |
| Routing, `Request`, error codes         | API / Backend (existing `router.py`, `errors.py`) | —             | Reused unchanged; a separate `Router` instance per listener                                   |
| JSON response/body rules                | API / Backend (`server.py` base class) | —                        | Shared by ingress and API handler so headers and body limits cannot drift                     |
| Exposure (port unpublished, bind)       | Consumer manifest (`config.yaml ports: null`) | API (`bind` argument) | The skeleton only binds; publication is HA add-on config, documented by R-16                  |
| Showing the plaintext once              | Consumer GUI (deferred)              | API (`take_plaintext()`)   | Skeleton exposes it in memory once; display is consumer work                                  |

## Standard Stack

### Core

| Library / module                         | Version                    | Purpose                                         | Why Standard                                                                                                      |
| ---------------------------------------- | -------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `http.server` (`ThreadingHTTPServer`, `BaseHTTPRequestHandler`) | stdlib, CI 3.12, images 3.14 | Second listener                       | Skeleton is "Standard library only, relative imports only" [VERIFIED: admin-ui/DOCS.md:55-56, test_tracer.py:118-131] |
| `secrets.token_urlsafe(32)`              | stdlib                     | 256-bit token, 43 URL-safe chars                | `return base64.urlsafe_b64encode(tok).rstrip(b'=').decode('ascii')` [VERIFIED: /usr/lib/python3.14/secrets.py:60-71; probe printed length 43] |
| `hashlib.sha256`                         | stdlib                     | Stored token hash, fixed-length compare inputs  | Already used by the skeleton (`static.py`)                                                                        |
| `hmac.compare_digest`                    | stdlib                     | Constant-time compare                           | Docstring: "a and b must both be of the same type: either str (ASCII only), or any bytes-like object" [VERIFIED: local `hmac.compare_digest.__doc__`] |
| `tempfile.mkstemp` + `os.replace`        | stdlib                     | Atomic hash-file write with mode 0600           | `fd = _os.open(file, flags, 0o600)` [VERIFIED: /usr/lib/python3.14/tempfile.py:256]                                |

### Supporting (test only, already used)

| Tool                         | Version (CI)        | Purpose                     | When to Use                                                     |
| ---------------------------- | ------------------- | --------------------------- | --------------------------------------------------------------- |
| pytest                       | `pytest==9.1.1`     | Python suites               | `make test-admin-ui` [VERIFIED: .github/workflows/lint.yml:200] |
| pyyaml                       | `pyyaml==6.0.3`     | Scaffold/docs tests         | same                                                            |
| node test runner             | Node 22             | Lib + demo view tests       | `node --test admin-ui/tests/js/*.test.mjs`                      |

### Alternatives Considered

| Instead of                          | Could Use                                 | Tradeoff                                                                                                 |
| ----------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Shared base class in `server.py`    | Duplicate ~60 lines of helpers in `api.py`, `server.py` untouched except `serve` | Zero risk to the ingress handler, but two copies of the body/header rules that can drift. Use only if the characterisation test cannot be made to pass. |
| `serve(server, *more)`              | New name `serve_all(servers)`             | Extra public name and doc row; `serve(*more)` is backward compatible with the existing `serve(fake)` test |
| Lazy `register_error_code` in `make_api_server` | Static `"unauthorized": 401` in `ERROR_STATUS` | Static entry breaks ntfy consumer tests (Pitfall 1)                                       |

**Installation:** none. No external package is added (stdlib only).

## Package Legitimacy Audit

No external packages are installed by this phase. The skeleton stays stdlib-only (enforced by
`test_tracer.py::test_skeleton_imports_only_stdlib_or_relative`). pytest/pyyaml are existing, pinned test tools.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
| ------- | -------- | --- | --------- | ----------- | ------- | ----------- |
| (none)  | —        | —   | —         | —           | —       | —           |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Existing Code Facts (verbatim, read this session)

`errors.py:7-17` [VERIFIED: admin-ui/app/web/skeleton/errors.py:7-17]

```python
ERROR_STATUS: dict[str, int] = {
    "bad_request": 400,
    "confirmation_required": 400,
    "ingress_only": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "protected": 409,
    "payload_too_large": 413,
    "internal_error": 500,
}
```

`register_error_code(code: str, status: int) -> None` at `errors.py:35`: re-registering the same pair is a no-op,
`_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")`, status must be `400 <= status <= 599`. [VERIFIED: errors.py:32-45]

`headers.py:16-24` [VERIFIED]: `def security_headers(kind: str, csp: str | None) -> dict[str, str]:` returns
`"X-Content-Type-Options": "nosniff"`, `"Referrer-Policy": "same-origin"`, and the CSP only for `kind in ("html",
"static")`.

`server.py` [VERIFIED: admin-ui/app/web/skeleton/server.py]:

- `:26-27` `MAX_BODY = 65536`, `BODY_METHODS = ("POST", "PUT", "PATCH", "DELETE")`
- `:31` `_IDENTITY_PREFIXES = ("x-remote-user-", "x-ingress-")`; `:34-53` `_PublicHeaders` (header view hiding them)
- `:56-64` `make_handler(router, static, *, ingress_remote=INGRESS_REMOTE, server_version="AdminUi", csp=DEFAULT_CSP,
  error_mappers=None)`
- `:67-71` `class GuiHandler(BaseHTTPRequestHandler)`, `protocol_version = "HTTP/1.1"`, `log_message` returns (silenced)
- `:73-94` `_send(status, body, ctype, cache="no-store", extra=None, kind="api")` header order: `Content-Type`,
  `Content-Length`, `Cache-Control`, security headers, `extra`, then `Connection: close` if `self.close_connection`;
  body skipped for `HEAD`. `csp` comes from the closure (`security_headers(kind, csp)` at `:86`).
- `:99-102` `_error` sets `close_connection = True` ("The request body may be unread")
- `:104-123` `_read_body`: rejects `Transfer-Encoding`, invalid/negative `Content-Length` (`bad_request`),
  `> MAX_BODY` (`payload_too_large`), non-`application/json` content type, invalid JSON
- `:125-134` gate: `self._json(403, {"error": "ingress_only"})` with `close_connection = True`
- `:160-170` exception mapping: `ApiError` -> `_error`; mapped foreign exceptions; else
  `print(traceback.format_exc(), flush=True)` and `ApiError("internal_error", "internal error")`
- `:171-179` result rendering: `None` -> 204, `Download` -> attachment, tuple -> `(status, payload)`, else 200 JSON
- `:181` `do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _dispatch`
- `:187-200` `make_server(router, static, port, *, ingress_remote=INGRESS_REMOTE, host="0.0.0.0", csp=DEFAULT_CSP,
  error_mappers=None)`, `server.daemon_threads = True`
- `:203-215` `serve(server)`: SIGTERM/SIGINT -> `threading.Thread(target=server.shutdown, daemon=True).start()`,
  `finally: server.server_close()`

`router.py` [VERIFIED]: `Request` dataclass `:22-45` with `public: bool = False` (`:32`, comment "Such a request carries
no ingress identity: never trust identity headers there."); `Router.is_public(method, path)` `:80-85`;
`Router.routes()` `:87-88`; `Router.match` raises `ApiError("not_found")` / `ApiError("method_not_allowed")` `:90-111`.

`ingress.py:7` `INGRESS_REMOTE = "172.30.32.2"` [VERIFIED].

`__init__.py:10-26` `__all__` = `"DEFAULT_CSP", "ERROR_STATUS", "INGRESS_REMOTE", "ApiError", "Download", "Request",
"Router", "StaticFiles", "ingress_user", "is_ingress", "make_handler", "make_server", "register_error_code",
"security_headers", "serve"` [VERIFIED: admin-ui/app/web/skeleton/__init__.py:10-26].

## Architecture Patterns

### System Architecture Diagram

```text
                       one consumer process (e.g. proxy GUI + provisioning API)
 HA ingress (peer 172.30.32.2) ──> :8099 make_server ──> GuiHandler._dispatch ──> ingress gate (R-01, 403)
                                                                │                   │ pass
                                                                │                   v
                                                                │           static whitelist / Router A ──> handlers ──┐
                                                                │                                                       │
 IaC client (LAN/Tailscale,     ──> :<api port> make_api_server ──> ApiHandler._dispatch (any method via __getattr__)  │
 port unpublished by default)        bind=<explicit>                │                                                   │
                                                                    v                                                   │
                                     parse Authorization (exactly one header, "Bearer" case-insensitive, 1*SP, token)  │
                                                                    │ fail (missing/malformed/wrong/parser error)       │
                                                                    ├──> identical 401 {"error":"unauthorized"} +       │
                                                                    │    WWW-Authenticate: Bearer, Connection: close    │
                                                                    v ok                                                │
                                     verifier.verify(token)  (OptionToken | GeneratedToken: sha256 + compare_digest)   │
                                                                    v                                                   │
                                     Router B (own instance, no public routes) ──> handlers ──> shared service module ─┘
                                                                    v                               (one lock, /data)
                                     _JsonHandler helpers: _read_body (MAX_BODY, JSON only), _respond, _error (no-store,
                                     nosniff, Referrer-Policy, no CSP, no CORS)
 serve(gui_server, api_server): main thread runs gui_server, api_server in a daemon thread; SIGTERM shuts down both.
```

### Recommended Project Structure

```text
admin-ui/app/web/skeleton/
├── __init__.py   # + GeneratedToken, OptionToken, make_api_server in __all__
├── api.py        # NEW: _make_api_handler (private), make_api_server
├── tokens.py     # NEW: TokenVerifier (Protocol, optional public), OptionToken, GeneratedToken
├── server.py     # _JsonHandler base (private), GuiHandler inherits it; serve(server, *more)
├── errors.py     # unchanged (no static "unauthorized" entry)
├── headers.py, ingress.py, router.py, static.py   # unchanged
admin-ui/tests/
├── test_ingress_characterisation.py  # NEW, written BEFORE the refactor (golden header/body matrix)
├── test_api_server.py                # NEW: gate matrix, raw-socket cases, routing, body rules, serve(*more), logs
└── test_api_tokens.py                # NEW: OptionToken, GeneratedToken (file mode, once, rotate, corrupt, threads)
```

### Pattern 1: Shared JSON handler base (keeps the ingress handler byte-identical)

**What:** Move the methods that do not depend on ingress (`log_message`, `_send`, `_json`, `_error`, `_read_body`,
plus two new helpers `_respond(result)` and `_call(fn)`) from the `GuiHandler` closure into a private module-level class
`_JsonHandler(BaseHTTPRequestHandler)` in `server.py`. The only closure value they use is `csp`; make it a class
attribute set on the subclass. `GuiHandler._dispatch` keeps its gate and static code verbatim and calls the shared
helpers.

**When to use:** Required so the API handler reuses the exact header order, body rules and exception mapping.

**How to prove "unchanged":** Before touching `server.py`, add `test_ingress_characterisation.py` that records, for a
matrix (gate 403, `HEAD` gate 403, 200 JSON, 204, `Download`, static 200 + 304, 404, 405, 413, 400 chunked, 500 with
mapper and without), the **ordered** header list (minus `Date`, `Server`) and the body bytes, and asserts them as
literals. Commit it green against the old code; it must stay green after the refactor. Existing gate tests
(`test_skeleton_server.py`, `test_public_routes.py`, `test_tracer.py`, `test_static_cache.py`, `test_demo_api.py`)
stay untouched.

```python
# Source: derived from admin-ui/app/web/skeleton/server.py:67-179 (shape only; names are the proposal)
class _JsonHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    csp: str | None = None  # set by the subclass factory; api responses never carry a CSP anyway
    mappers: dict[type[Exception], Callable[[Exception], ApiError]] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send(self, status, body, ctype, cache="no-store", extra=None, kind="api") -> None:
        ...  # body of server.py:82-94 unchanged, `csp` -> `self.csp`

    def _json(self, status: int, payload: Any) -> None: ...   # server.py:96-97
    def _error(self, exc: ApiError) -> None: ...               # server.py:99-102
    def _read_body(self) -> Any: ...                           # server.py:104-123

    def _respond(self, result: Any) -> None: ...               # server.py:171-179 moved verbatim
```

### Pattern 2: `make_api_server` (new public entry point)

```python
# Proposal (signature is Claude's discretion per CONTEXT.md)
def make_api_server(
    router: Router,
    port: int,
    verifier: TokenVerifier,
    *,
    bind: str,                       # required keyword: no default, the consumer states its exposure (R-16)
    server_version: str = "AdminUiApi",
    error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None = None,
) -> ThreadingHTTPServer:
    if verifier is None or not callable(getattr(verifier, "verify", None)):
        raise ValueError("no token: the API stays off")          # D-08, before any socket is bound
    if any(router.is_public(m, p) for m, p in router.routes()):
        raise ValueError("public routes are not allowed on the API router")  # D-02
    register_error_code("unauthorized", 401)                      # lazy, idempotent (Pitfall 1)
    handler = _make_api_handler(router, verifier, server_version=server_version, error_mappers=error_mappers)
    server = ThreadingHTTPServer((bind, port), handler)
    server.daemon_threads = True
    return server
```

- `bind` required: the most explicit form of "explicit in the API". Inside a bridge-network add-on the consumer passes
  `"0.0.0.0"` and controls exposure with `ports: {"<port>/tcp": null}` (HA: "A host port of `null` (or no value) means
  the port is off by default; the user can turn it on." [CITED: contributors.home-assistant.io/apps/reference/configuration]).
  A LAN/Tailscale address only exists inside the container with `host_network: true` (default `false`, same source).
- `ThreadingHTTPServer` is IPv4 (`address_family = socket.AF_INET` [VERIFIED: /usr/lib/python3.14/socketserver.py:440]);
  an IPv6 `bind` fails at bind time. Document IPv4 only (or validate with `ipaddress` and raise `ValueError`).
- Handler `timeout = 30` (seconds) on the API handler class only: `StreamRequestHandler` applies it with
  `self.connection.settimeout(self.timeout)` [VERIFIED: socketserver.py:803-812]. The ingress handler stays unchanged.
  The value 30 is [ASSUMED].

### Pattern 3: The API handler and its gate

```python
def _make_api_handler(router, verifier, *, server_version, error_mappers):
    class ApiHandler(_JsonHandler):
        timeout = 30
        mappers = dict(error_mappers or {})

        def __getattr__(self, name: str) -> Any:
            # Any method token (TRACE, CONNECT, PROPFIND, FOO) reaches the gate instead of the stdlib HTML 501
            if name.startswith("do_"):
                return self._dispatch
            raise AttributeError(name)

        def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
            # Parser errors (400/414/431/505) never reach a method: answer them with the identical 401
            self._unauthorized()

        def _unauthorized(self) -> None:
            self.close_connection = True
            self._send(401, UNAUTHORIZED_BODY, "application/json; charset=utf-8",
                       extra={"WWW-Authenticate": "Bearer"})

        def _dispatch(self) -> None:
            token = _bearer_token(self.headers)       # None for missing/malformed/duplicate/non-ASCII
            if token is None or not verifier.verify(token):
                self._unauthorized()
                return
            ...  # urlsplit, router.match, _read_body for BODY_METHODS, Request(..., headers=_ApiHeaders(self.headers),
                 # public=True), handler call through the shared exception mapping, _respond(result)

    ApiHandler.server_version = server_version
    return ApiHandler
```

`UNAUTHORIZED_BODY` is one fixed byte string (proposal: `{"error": "unauthorized", "message": "unauthorized"}` via
`json.dumps(..., sort_keys=True)`), so "identical response for all failure cases" is a byte comparison in the test.
`WWW-Authenticate: Bearer` without `error="invalid_token"` is RFC-compatible: for a request without credentials "the
resource server SHOULD NOT include an error code" and `invalid_token` is only a SHOULD for bad tokens
[CITED: rfc-editor.org/rfc/rfc6750 section 3.1]; RFC 9110 requires that a 401 "MUST send a WWW-Authenticate header
field containing at least one challenge" [CITED: rfc-editor.org/rfc/rfc9110 section 11.6.1].

`_bearer_token(headers)` rules:

- `values = headers.get_all("Authorization") if hasattr(headers, "get_all") else None` — on Python 3.14 an HTTP/0.9
  request has `self.headers = {}` [VERIFIED: /usr/lib/python3.14/http/server.py:403-405]. Exactly one value, else fail.
- Strip leading/trailing SP/HTAB ("A field value does not include leading or trailing whitespace" [CITED: RFC 9110
  5.5]; Python keeps trailing spaces — probe showed `'bEaReR    tok   '`).
- `scheme, _, rest = value.partition(" ")`; `scheme.lower() == "bearer"` (auth-scheme is "a case-insensitive token"
  [CITED: RFC 9110 11.1]); `rest.lstrip(" ")` (RFC 6750 grammar `credentials = "Bearer" 1*SP b64token` [CITED: RFC
  6750 2.1]).
- Credential must be non-empty and every char in `0x21..0x7E` (superset of `b64token`, so arbitrary option passwords
  work). This rejects obs-fold (`'Bearer\r\n tok'` was delivered verbatim by the parser in the probe), inner spaces and
  latin-1-decoded non-ASCII bytes (`'Bearer Ã¤abc'` in the probe).
- Never raise: any exception inside parsing or `verify` means "fail" (an exception escaping `handle()` is printed to
  stderr by `socketserver`).

`_ApiHeaders`: a header view like `_PublicHeaders` (`server.py:34-53`) that additionally hides `authorization`. Pass it
as `Request.headers` with `public=True`, so handlers never see the token and never trust `X-Remote-User-*` /
`X-Ingress-*` on the API port. Generalise `_PublicHeaders` with an optional `hidden` prefix tuple defaulting to
`_IDENTITY_PREFIXES` (no behaviour change for the ingress handler).

### Pattern 4: Token verifiers

```python
class TokenVerifier(Protocol):
    def verify(self, presented: str) -> bool: ...


class OptionToken:
    """Token from an add-on `password` option; only its SHA-256 is kept in memory."""

    def __init__(self, value: str | None) -> None:
        if not value or any(not 0x21 <= ord(c) <= 0x7E for c in value):
            raise ValueError("option token missing or not printable ASCII")   # never echo the value
        self._digest = hashlib.sha256(value.encode("ascii")).digest()

    def verify(self, presented: str) -> bool:
        try:
            candidate = hashlib.sha256(presented.encode("ascii")).digest()
        except (UnicodeEncodeError, AttributeError):
            return False
        return hmac.compare_digest(candidate, self._digest)   # equal length bytes: no length leak

    def __repr__(self) -> str:
        return "OptionToken(<redacted>)"
```

`GeneratedToken` (proposal):

| Member                                   | Behaviour                                                                                                     |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `GeneratedToken.load_or_create(path)`    | File missing: `secrets.token_urlsafe(32)`, write hash (Pattern 5), keep plaintext pending. File present and valid: load digest, no plaintext. Malformed: `ValueError` (API stays off; recovery = delete the file, next start creates a new one). Group/other bits set: `os.chmod(path, 0o600)`. |
| `take_plaintext() -> str \| None`         | Returns the pending plaintext once, then `None` (lock-protected). Lost on restart by design: rotate to get a new one. |
| `rotate() -> str`                        | New token, atomic write, then swap the in-memory digest; returns the plaintext (that is the one time) and clears any pending one. Write failure: raise, old token stays valid. |
| `verify(presented) -> bool`              | `hmac.compare_digest(sha256(presented.encode("ascii")).hexdigest(), stored_hex)`; non-ASCII -> `False`.        |
| `__repr__`                               | `GeneratedToken(<path>)` without digest or plaintext.                                                         |

File format proposal: one line `sha256 <64 lowercase hex>\n` (same `key value` style as `LIB.stamp`), parsed strictly
(`^sha256 [0-9a-f]{64}\n?$`). Thread safety: one `threading.Lock` around `rotate`, `take_plaintext` and the digest
swap; `verify` reads the current digest reference (immutable `str`).

### Pattern 5: Atomic write with mode 0600

```python
def _write_hash(path: Path, digest_hex: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")  # created 0o600
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as handle:
            handle.write(f"sha256 {digest_hex}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)            # same directory: atomic rename, mode of the temp file is kept
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
```

`mkstemp` opens with `0o600` [VERIFIED: tempfile.py:256]; a umask can only remove bits, so the result is never wider.
The temp file must be in the target directory (`os.replace` across file systems fails).

### Pattern 6: Two servers in one process

```python
def serve(server: ThreadingHTTPServer, *more: ThreadingHTTPServer) -> None:
    """Run until SIGTERM or SIGINT; `more` servers run in daemon threads and stop with the first."""
    servers = (server, *more)

    def stop(_signum: int, _frame: FrameType | None) -> None:
        for srv in servers:
            threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threads = [threading.Thread(target=srv.serve_forever, daemon=True) for srv in more]
    for thread in threads:
        thread.start()
    try:
        server.serve_forever()
    finally:
        for srv in more:
            srv.shutdown()           # safe: each thread was started above
        for thread in threads:
            thread.join(timeout=5)
        for srv in servers:
            srv.server_close()
```

With no `more`, the behaviour equals today's `serve` and `test_serve_installs_handlers_and_always_closes`
(`test_skeleton_server.py:295-330`) stays green untouched. `BaseServer.shutdown()` waits on an event that only
`serve_forever` sets when it exits [VERIFIED: socketserver.py:207, 225, 245, 254-255], so `shutdown()` on a server whose
`serve_forever` never started blocks forever: only call it for servers whose thread was started. `serve` must run on
the main thread (signal handlers); `haos-monitor/app/main.py:62` already documents that.

### Anti-Patterns to Avoid

- **Static `"unauthorized": 401` in `ERROR_STATUS`:** breaks ntfy consumer tests (Pitfall 1).
- **Routing the API through `make_server` / `public=True`:** violates D-02; `make_api_server` rejects routers with
  public routes.
- **`@dataclass` verifiers or f-strings with the token in exception messages:** the default `repr` or a message ends up
  in a traceback on stdout (`server.py:168`) or stderr (`socketserver.handle_error`).
- **Comparing `str` tokens with `compare_digest` directly:** `TypeError` for non-ASCII (Pitfall 6) and a length leak.
- **Sharing one `Router` between ingress and API:** the API router must be its own instance (success criterion 1).

## Don't Hand-Roll

| Problem                         | Don't Build                         | Use Instead                                   | Why                                                       |
| ------------------------------- | ----------------------------------- | --------------------------------------------- | --------------------------------------------------------- |
| Random token                    | `random`, `uuid4`, own base64       | `secrets.token_urlsafe(32)`                   | CSPRNG, 256 bits, URL-safe, fits `b64token`               |
| Constant-time compare           | `==`, loops                         | `hmac.compare_digest` on equal-length digests | Timing-safe; hashing first removes the length leak        |
| Private temp file               | `open(path, "w")` + `chmod`         | `tempfile.mkstemp` (0o600) + `os.replace`     | No window where the file is world-readable or half-written |
| Body parsing / limits           | A second `_read_body`               | Shared `_JsonHandler._read_body`              | Same `MAX_BODY`, chunked and content-type rules (D-04)    |
| Error codes                     | Ad-hoc JSON dicts in handlers       | `ApiError` + `register_error_code`            | R-14 stable codes                                         |

**Key insight:** every security property here already exists in the stdlib or in the skeleton; the work is wiring and
proving it, not new primitives.

## Common Pitfalls

### Pitfall 1: `unauthorized` in the static `ERROR_STATUS` breaks ntfy after sync

**What goes wrong:** ntfy's consumer tests pin the import-time table: `assert c.ERROR_STATUS == { ... }` (13 entries
incl. ntfy's 4 own codes) and `assert len(c.ERROR_STATUS) == 13` [VERIFIED: ntfy/tests/test_contract.py:118-142], and
every code needs an `errors.<code>` string: `sorted(c for c in contract.ERROR_STATUS if f"errors.{c}" not in
keys[lang])` must be empty [VERIFIED: ntfy/tests/test_registry.py:166]. `make release-admin-ui-lib` runs those tests
(`Makefile:113-116`, `test-admin-ui-consumers` `:128-133`) and CI runs them in the admin-ui job
(`.github/workflows/lint.yml:211-222`).
**How to avoid:** keep `errors.py` unchanged; call `register_error_code("unauthorized", 401)` inside `make_api_server`.
The gate writes its fixed body directly, like the ingress gate does (`server.py:133`). `haos-monitor` only asserts its
own code (`haos-monitor/tests/test_server.py:102`). Hand-off note for ntfy Phase 25: once ntfy calls
`make_api_server` in a test, its literal C8 table needs `unauthorized` and `errors.unauthorized` strings.
**Warning signs:** `ntfy/tests/test_contract.py` failing with 14 entries.

### Pitfall 2: Unknown methods bypass the gate with an HTML 501

**What goes wrong:** `handle_one_request` calls `send_error(501)` when `do_<METHOD>` is missing. Probe on 3.12.15 and
3.14.10 (plain handler): `TRACE: b"HTTP/1.1 501 Unsupported method ('TRACE')` ... `Content-Type: text/html`. The same
happens on the ingress server today (out of scope, behaviour must stay).
**How to avoid:** `__getattr__` returning `_dispatch` for `do_*` (probe with it: `TRACE` and `FOO` -> `401
Unauthorized` with `WWW-Authenticate: Bearer`).

### Pitfall 3: Parser errors bypass the gate and reflect input

**What goes wrong:** malformed lines get HTML `400 Bad HTTP/0.9 request type ('\x00\x01')`, `505 Invalid HTTP version
(9.9)`, `414 URI Too Long` (3.14) / `414 Request-URI Too Long` (3.12) from `send_error`, before any gate; on 3.12 some
of them are sent without a status line (request version still `HTTP/0.9`). [VERIFIED: probe output, both versions]
**How to avoid:** override `send_error` in the API handler only, emitting the identical 401. No reason phrase from the
request is ever reflected (`send_response(401)` uses the standard phrase).

### Pitfall 4: HTTP/0.9 requests

**What goes wrong:** `GET /x\r\n\r\n` reaches `do_GET` with `request_version == "HTTP/0.9"`; on 3.14 `self.headers` is
`{}` (no `get_all`, the first probe crashed with `AttributeError: 'dict' object has no attribute 'get_all'`), and every
response is body-only (no status line, no headers) because `send_response_only`/`send_header` skip output for 0.9
[VERIFIED: http/server.py:572, 586, 600].
**How to avoid:** dict-tolerant header access (`hasattr(headers, "get_all")`); the 0.9 caller gets only the fixed 401
body, which leaks nothing. Test it with a raw socket.

### Pitfall 5: Keep-alive after an unread body

**What goes wrong:** a `POST` with a body that fails auth leaves the body in the socket; the next request on the
keep-alive connection would parse the body as a request line.
**How to avoid:** `close_connection = True` on every 401 (same as the ingress gate `server.py:132` and `_error`
`server.py:101`); the shared `_send` then adds `Connection: close`.

### Pitfall 6: `hmac.compare_digest` raises on non-ASCII `str`

**What goes wrong:** `hmac.compare_digest("ä", "a")` -> `TypeError comparing strings with non-ASCII characters is not
supported` [VERIFIED: probe on 3.14]. Header values are decoded as latin-1, so a client sending UTF-8 bytes produces
non-ASCII `str` (probe: `'Bearer Ã¤abc'`). Unequal lengths "could theoretically reveal information about the types and
lengths" [VERIFIED: docstring].
**How to avoid:** `.encode("ascii")` inside `try` (failure -> `False`), compare SHA-256 digests (fixed length).

### Pitfall 7: Secrets reaching stdout/stderr

**What goes wrong:** paths that print: `log_message` (silenced via the base class), `log_error` (calls `log_message`,
silenced), `server.py:168` traceback on unexpected handler exceptions, `socketserver.handle_error` traceback to stderr
for exceptions escaping `handle()`, `repr()` of verifier objects, `ValueError` messages that include the value.
**How to avoid:** handlers never see `Authorization` (`_ApiHeaders`), gate and verifiers never raise, verifiers have a
redacting `__repr__`, error messages never interpolate token values, `GeneratedToken` prints nothing.
**Warning signs:** a test with `capfd` (fd-level, catches thread output and C-level writes) finding the token string.

### Pitfall 8: Pre-commit drift hook blocks intermediate commits

**What goes wrong:** the installed pre-commit hook runs `python3 internal/sync-admin-ui.py --check` (non-strict) on any
commit touching `admin-ui/app/web/skeleton/.+` or the lock [VERIFIED: .pre-commit-config.yaml:165-170; hook installed].
A skeleton edit without a lock refresh fails "lock: stale" (`sync-admin-ui.py:241-243`); a lock refresh with the same
version and unsynced consumers fails "same version ... different hash" (`:221-223`).
**How to avoid:** in the **first** commit that touches skeleton sources, write `0.10.0` into
`admin-ui/app/web/static/lib/VERSION` and run `python3 internal/sync-admin-ui.py` (no args = lock only); consumers are
then "behind" -> `WARN`, exit 0 (`:225-227`). Refresh the lock in every later skeleton commit. Precedent: `a752ee7`
(public routes) changed `skeleton/`, `lib/VERSION` and `lib.lock` without touching consumers.
**Warning signs:** `FAIL admin-ui lock: stale`.

### Pitfall 9: `make update-version` pushes a tag by default

**What goes wrong:** "By default the script creates and pushes the tag `<addon>/v<version>` to origin."
[VERIFIED: .claude/skills/update-version/SKILL.md]
**How to avoid:** `make update-version ADDON=admin-ui VERSION=0.4.0 NO_TAG=yes` (`Makefile` passes `--no-tag`).

### Pitfall 10: R-16 ripples into six files

The demo GUI mirrors the rule table, and three tests pin the count 15:

| File                                              | Current (verbatim)                                                                         | Change                                  |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------- |
| `admin-ui/DOCS.md` rules table                    | rows `R-01`..`R-15`, 4 cells                                                               | add `R-16` row                          |
| `admin-ui/tests/test_docs.py:51`                  | `assert ids == [f"R-{n:02d}" for n in range(1, 16)]`                                       | `range(1, 17)`                          |
| `admin-ui/tests/test_rules_view.py:36`            | `... == [f"R-{n:02d}" for n in range(1, 16)]`                                              | `range(1, 17)`                          |
| `admin-ui/app/web/static/views/rules.mjs:10-26, 29-45` | `RULES` and `TEXT` end at `R-15`                                                      | add `R-16` entries (status equal to DOCS) |
| `admin-ui/app/web/static/strings.{de,en}.mjs:164-165` | last keys `demo.rules.r15.title` / `.how`                                              | add `demo.rules.r16.title` / `.how` (de + en) |
| `admin-ui/tests/js/rules_view.test.mjs:57, 65-108` | `Array.from({ length: 15 }, ...)`, `/0 of 15/` ... `/2 of 15/`                            | 16                                      |

`test_rules_view.py:45-49` requires every `enforcedBy` path to exist, so the new test files must exist first.
`RULE_STATUS = {"enforced", "review", "unverified"}` [VERIFIED: test_docs.py:25]; each row needs 4 non-empty cells
[VERIFIED: test_docs.py:52-55]. These are demo static files, not the lib (`static/lib/`), so they do not change the
lib hash.

## Code Examples

### Test fixture following the existing pattern

Existing pattern [VERIFIED: admin-ui/tests/test_skeleton_server.py:86-106, conftest.py:40-58]: server on port `0`,
`host="127.0.0.1"`, `serve_forever(poll_interval=0.02)` in a daemon thread, teardown `shutdown()`, `server_close()`,
`join(timeout=5)`; `http.client.HTTPConnection` per call; raw `putrequest`/`putheader` for chunked and bad
`Content-Length` (`:155-167`).

```python
@pytest.fixture
def api(tmp_path: Path) -> Iterator[Callable[..., Client]]:
    servers: list[Any] = []

    def _start(router: Router | None = None, verifier: Any = None, **kwargs: Any) -> Client:
        httpd = make_api_server(router or build_api_router(), 0, verifier or OptionToken(TOKEN), bind="127.0.0.1",
                                **kwargs)
        thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        servers.append((httpd, thread))
        return Client(httpd.server_address[1])

    yield _start
    for httpd, thread in servers:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def raw(port: int, data: bytes) -> bytes:
    """Send raw bytes (TRACE, HTTP/0.9, obs-fold, duplicate or non-ASCII Authorization) and read until close."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(data)
        chunks = []
        while chunk := sock.recv(65536):
            chunks.append(chunk)
    return b"".join(chunks)
```

### Identical-401 assertion

```python
def normalised(resp_bytes: bytes) -> bytes:
    head, _, body = resp_bytes.partition(b"\r\n\r\n")
    lines = [ln for ln in head.split(b"\r\n") if not ln.lower().startswith((b"date:", b"server:"))]
    return b"\r\n".join(lines) + b"\r\n\r\n" + body

# For every (method, path, auth variant) failure: collect normalised(raw(...)); assert len(set(results)) == 1
# (HEAD separately: same headers, empty body).
```

### "Token never logged"

```python
def test_token_never_reaches_stdout_or_stderr(api, capfd: pytest.CaptureFixture[str]) -> None:
    ...  # run the full gate matrix with TOKEN, "Bearer " + TOKEN, a wrong token, a handler that raises,
         # GeneratedToken.load_or_create(tmp) + rotate()
    out, err = capfd.readouterr()
    for secret in (TOKEN, f"Bearer {TOKEN}", generated_plaintext):
        assert secret not in out and secret not in err
```

`capsys` swaps `sys.stdout`/`sys.stderr` (sees server threads too); `capfd` additionally catches fd-level writes and is
the stronger check. The existing suite uses `capsys` for the traceback assertion (`test_skeleton_server.py:215-222`).

## Release mechanics (answers to planner questions 1 and 2)

### Registered consumers

`discover_consumers` registers every top-level directory (except `admin-ui`, dot dirs, symlinks) that has
`app/web/static/vendor/admin-ui/LIB.stamp` or `app/web/admin_ui/LIB.stamp` [VERIFIED: internal/sync-admin-ui.py:149-156].
Current stamps (all `version 0.9.1`, lock `version 0.9.1`) [VERIFIED: LIB.stamp files, admin-ui/lib.lock]:

| Consumer            | Image copies `app/web/admin_ui`?                                                                 | Image content changes with this phase?                         | Local build                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `admin-ui` (source) | yes: `COPY app/ ./app/` [VERIFIED: admin-ui/Dockerfile:10]                                        | yes (skeleton, lib VERSION)                                    | `make build-addon ADDON=admin-ui`                                                             |
| `haos-monitor`      | yes: `COPY app/ /opt/haos-monitor-gui/app/` [VERIFIED: haos-monitor/Dockerfile:11]                | yes                                                            | `make build-addon ADDON=haos-monitor`                                                         |
| `ntfy`              | yes: `COPY app/ ./app/` [VERIFIED: ntfy/Dockerfile:24]                                            | yes                                                            | `make build-addon ADDON=ntfy` (needs `VERSION` build arg: Dockerfile `ARG VERSION` has no default; `build-addon` passes it from build.yaml; downloads the ntfy release) |
| `secrets-sync`      | yes: `COPY app/ /opt/secrets-sync/app/` [VERIFIED: secrets-sync/Dockerfile:12]                    | yes                                                            | `make build-addon ADDON=secrets-sync` (`BW_CLI_VERSION` has an ARG default; npm install)       |
| `coding-assistants` | no: only `COPY app/web/static/ /opt/coding-assistants/static/` [VERIFIED: coding-assistants/Dockerfile:352]; DOCS: "the synchronized Python skeleton is not used or packaged" [VERIFIED: coding-assistants/DOCS.md:430] | only if the lib `VERSION` changes (`vendor/admin-ui/VERSION` and `LIB.stamp` are under `app/web/static/`) | `make build-addon ADDON=coding-assistants TIMEOUT=1800` (heavy: herdr, opencode, codex downloads) |

`make build-addon` passes `BUILD_FROM` (first `amd64:` value of build.yaml), `VERSION` (build.yaml `args.VERSION`) and
the `BUILD_*` args and tags `local/<addon>:<config version>` [VERIFIED: Makefile `build-addon` target]. Base images
present locally: `ghcr.io/home-assistant/amd64-base:3.24`, `amd64-base-debian:bookworm`. Run builds sequentially, not
in parallel with another worktree.

### Lib version vs add-on version

- **Add-on version** (`admin-ui/config.yaml` `0.3.2-0`, `build.yaml` `VERSION: "0.3.2"`, README badge): changed only by
  `make update-version`; pinned additionally by `EXPECTED_VERSION = "0.3.2"` [VERIFIED: admin-ui/tests/test_addon_scaffold.py:17],
  which must be edited by hand (precedent `e2e6f9d`), plus a `CHANGELOG.md` entry.
- **Lib version** (`admin-ui/app/web/static/lib/VERSION` `0.9.1`, `lib.lock`, every `LIB.stamp`): changed by
  `make release-admin-ui-lib VERSION=X.Y.Z` (`sync-admin-ui.py --release`, then `check-admin-ui-rules test-admin-ui
  test-admin-ui-consumers`) [VERIFIED: Makefile:113-116]. DOCS: "The library version is independent of the demo add-on
  version" [VERIFIED: admin-ui/DOCS.md "Shared library release"].
- **Does a skeleton-only change require a lib bump?** The drift check alone would pass after a same-version
  `make sync-admin-ui` (copies then match the new hash; `check_part` only fails same version + different hash,
  `sync-admin-ui.py:221-224`). But `--release` refuses a reused version with changed sources ("source changed: release
  a newer lib version instead of reusing this version", `:266-269`), DOCS says "reusing a version with changed sources
  fail[s]", and every past skeleton change bumped the lib (`a752ee7` public routes, `aef2869` "lib 0.7.1"). Recommend
  lib `0.10.0` (new public API) and admin-ui `0.4.0` (minor feature) [version numbers ASSUMED, need confirmation].
- **STRICT and test_sync:** `test_sync.py` runs on a `tmp_path` copy of the real sources and bumps versions itself; it
  does not require a real bump. CI runs `make check-admin-ui-sync STRICT=yes` [VERIFIED: lint.yml:209], so the final
  pushed state must have every consumer at the source version (behind = FAIL under STRICT).
- **CI and consumer tests:** CI's admin-ui job runs node + pytest for admin-ui, the strict drift check, and the ntfy,
  Secrets Sync web, HAOS Monitor and Coding Assistants consumer tests [VERIFIED: lint.yml:178-222]; locally
  `make test-admin-ui-consumers` does the same [VERIFIED: Makefile:128-133]. CI uses Python 3.12
  [VERIFIED: lint.yml:192]; the local `python3` and the add-on images are 3.14.10 [VERIFIED: `python3 --version`,
  `docker run ... local/admin-ui:gallery-check python3 --version`].
- **Consumer add-on bumps in practice:** mixed. `172a1af` "chore(admin-ui): sync lib 0.7.1 into consumers" (skeleton
  change) synced without any consumer version bump; `e2e6f9d` (visible toast change) bumped `haos-monitor` 0.8.2 ->
  0.8.3, `secrets-sync` 0.7.5 -> 0.7.6, `ntfy` `2.37.2-5` -> `2.37.2-6` with changelog entries; `228b3d5`, `6a7f20c`,
  `b231666` bumped ntfy subpatches per lib release; `f71f523` (coding-assistants 1.3.2-0) registered that consumer as
  part of its own release [VERIFIED: git log/show]. Recommendation: no consumer bumps in this phase, because no consumer
  calls the new code and their runtime behaviour is unchanged (precedent `172a1af`). The consumer that wires the
  listener bumps itself in its own phase. [ASSUMED: needs user confirmation, DOCS says "bump each affected add-on with
  `make update-version` according to its release policy" before shipping images]

### Recommended release order

1. First skeleton commit: lib `VERSION` -> `0.10.0`, `python3 internal/sync-admin-ui.py` (lock only).
2. Every later skeleton commit: lock refresh again.
3. Release task: `make update-version ADDON=admin-ui VERSION=0.4.0 NO_TAG=yes`, `EXPECTED_VERSION = "0.4.0"`,
   CHANGELOG `## [0.4.0-0] - <date>` (also repair the missing `## [0.3.1-0]` heading: line 16 currently reads
   `- 2026-11-05` [VERIFIED: admin-ui/CHANGELOG.md:16]), then `make release-admin-ui-lib VERSION=0.10.0` (same version
   as current is allowed when the lock matches, `sync-admin-ui.py:266-269`), then `make sync-admin-ui` (idempotent,
   must print only "up to date"), `make check-admin-ui-sync STRICT=yes`, `make check-admin-ui-rules`,
   `make test-admin-ui`, `make validate-versions`.
4. Builds: `admin-ui`, `haos-monitor`, `ntfy`, `secrets-sync`, `coding-assistants` (sequential).
5. Commit sources, lock and all consumer copies together, staged by path.

## Rules checker and docs test (answers to planner questions 3 and 4)

- `check-admin-ui-rules.py` scans only `.mjs`, `.html`, `.css` below static trees (`_shipped`, lines 79-87:
  `if name.endswith((".mjs", ".html", ".css"))`) [VERIFIED: internal/check-admin-ui-rules.py:79-87]. No Python file is
  scanned; no rule about `print`/logging exists. Adding demo strings and `rules.mjs` entries must keep keys literal
  (R-06) and add no storage keys.
- `test_docs.py`: `SKELETON_EXPORTS` must contain every new public name, and
  `assert set(declared) == set(SKELETON_EXPORTS) - {"MAX_BODY"}` compares it with `__all__` [VERIFIED:
  test_docs.py:156-159, 192-202]; each name must appear as a whole word in the "Library reference" section
  (`_mentions`, `:166-179`); prose lines <= 120 columns, table rows exempt (`:93-97`); no forbidden patterns (`:100-103`).
- `lib_contract.test.mjs` covers only browser lib modules (`const LIB = new URL("../../app/web/static/lib/", ...)`) and
  does not touch the Python skeleton [VERIFIED: admin-ui/tests/js/lib_contract.test.mjs:8]. It stays green as long as
  no lib `.mjs` changes.
- `test_tracer.py:118-131` requires stdlib or single-level relative imports in every `skeleton/*.py`.
- Proposed R-16 row: "The bearer API runs on its own server and port (`make_api_server`), never through the ingress
  server or a `public=True` route. Every method and path needs `Authorization: Bearer <token>`, otherwise an identical
  401 `unauthorized` with `WWW-Authenticate: Bearer`. No token, no listener. The port is unpublished by default and is
  never routed through ingress or a public reverse proxy; the bind address is explicit." Enforced by:
  `admin-ui/tests/test_api_server.py`, `admin-ui/tests/test_api_tokens.py`. Status: `review` (the gate is automated;
  "unpublished by default, not behind a public proxy" lives in consumer manifests and is a review item). Use
  `enforced` only if a test also scans consumer manifests, which has no consumer to check yet.

## State of the Art

| Old Approach                                          | Current Approach                                       | When Changed           | Impact                                                    |
| ----------------------------------------------------- | ------------------------------------------------------ | ---------------------- | --------------------------------------------------------- |
| HTTP/0.9 requests got parsed headers                  | 3.14: `self.headers = {}` for HTTP/0.9                 | between 3.12 and 3.14  | Header access must tolerate a dict [VERIFIED: probe]      |
| `414 Request-URI Too Long`                            | `414 URI Too Long`                                     | 3.12 -> 3.14           | Do not assert stdlib reason phrases in tests              |
| RFC 7235 auth framework                               | RFC 9110 sections 11.x                                 | 2022                   | Same rules; cite RFC 9110                                 |

**Deprecated/outdated:** none relevant.

## Assumptions Log

| #  | Claim                                                                                                   | Section            | Risk if Wrong                                                     |
| -- | ------------------------------------------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------------- |
| A1 | Lib version `0.10.0` and admin-ui `0.4.0-0` are the right numbers                                        | Release mechanics  | Cosmetic; wrong numbers are a version-bump redo                   |
| A2 | No consumer add-on version bumps in this phase                                                          | Release mechanics  | Images built by CI carry unchanged versions with changed content  |
| A3 | `bind` as a required keyword argument (no default)                                                      | Pattern 2          | API ergonomics only                                               |
| A4 | API handler `timeout = 30` s                                                                            | Pattern 2          | Too short for slow IaC clients on large bodies (64 KiB max: low)  |
| A5 | Parser errors answered with the identical 401 instead of a JSON 400                                     | Pattern 3          | Slightly less helpful errors for authenticated clients with malformed requests |
| A6 | Malformed token file -> `ValueError`, no auto-regeneration; recovery by deleting the file               | Pattern 4          | Consumer GUI (deferred) may want a reset method                   |
| A7 | Option token must be printable ASCII without spaces; minimum length not enforced (see Open Questions)    | Pattern 4          | Weak option tokens accepted                                       |
| A8 | R-16 status `review`                                                                                    | Rules checker      | Doc test accepts any of the three statuses; only wording risk     |
| A9 | API requests get `Request.public = True` (no ingress identity)                                         | Pattern 3          | A shared handler relying on `public` semantics could misjudge     |

## Open Questions (RESOLVED)

The user answered questions 1 and 2 and the version numbers on 2026-11-17 (01-CONTEXT.md "Release values", D-11 to
D-13); question 3 is settled by the locked decision D-10. No plan has a checkpoint for any of them. The version numbers
(Assumptions Log A1) are decided as D-13: lib 0.10.0, admin-ui 0.4.0-0 via
`make update-version ADDON=admin-ui VERSION=0.4.0 NO_TAG=yes`.

1. **Consumer version bumps.** RESOLVED (decided by the user 2026-11-17, D-12)
   - What we know: precedent exists both ways (`172a1af` none, `e2e6f9d` all).
   - Unclear: whether the user wants CI to publish new consumer images for a not-yet-used skeleton addition.
   - Recommendation: no bumps now (A2).
   - Resolution: no consumer version bump in this phase (D-12, plan label A1); consumer copies are refreshed only
     through `make sync-admin-ui`. 01-06 task 2 syncs, 01-06 checks that no consumer version file changed.
2. **Minimum length for option tokens.** RESOLVED (decided by the user 2026-11-17, D-11)
   - What we know: ntfy Phase 25 uses a `password` option; brute force over the network is limited by request cost.
   - Recommendation: enforce at least 16 characters in `OptionToken` with a `ValueError` (message without the value).
   - Resolution: 16 characters (`OPTION_TOKEN_MIN_LENGTH = 16`, D-11, plan label A2; supersedes "minimum length not
     enforced" in A7; also binds ntfy Phase 25). 01-04 task 1 implements it, 01-05 documents it, 01-06 names it in the
     CHANGELOG.
3. **`coding-assistants` docker build.** RESOLVED (locked decision D-10, applied in 01-06 task 2; no checkpoint)
   - What we know: only `vendor/admin-ui/VERSION` and `LIB.stamp` change in its image; the build is long.
   - Recommendation: build it anyway (D-10 is literal), with `TIMEOUT=1800`.
   - Resolution: D-10 requires a local build for every consumer whose image content changes, which includes
     `coding-assistants`; 01-06 task 2 builds it in the background with `TIMEOUT=1800`.

## Environment Availability

| Dependency                          | Required By               | Available | Version                       | Fallback                                               |
| ----------------------------------- | ------------------------- | --------- | ----------------------------- | ------------------------------------------------------ |
| python3                             | skeleton, tests           | ✓         | 3.14.10                       | —                                                      |
| Python 3.12 (CI parity)             | compatibility check       | ✓ (uv)    | 3.12.15 via `uv run --python 3.12` | —                                                  |
| uv                                  | `make test-admin-ui`      | ✓         | 0.13.4                        | PyPI timed out once in this sandbox; `uv run --offline --with pytest --with pyyaml ...` worked from cache |
| node                                | node suites               | ✓         | v22.23.5                      | —                                                      |
| docker                              | consumer builds           | ✓         | 29.9.3                        | —                                                      |
| HA base images                      | builds                    | ✓ local   | `amd64-base:3.24`, `amd64-base-debian:bookworm` | pull                                 |
| Network (GitHub/npm downloads)      | ntfy, secrets-sync, coding-assistants builds | not verified | —            | run builds where network is available                  |

Baseline measured this session: `make check-admin-ui-sync STRICT=yes` all OK at 0.9.1; `check-admin-ui-rules` exit 0;
pytest `386 passed`; node `# tests 322`, `# pass 322`, `# fail 0`.

## Test map per requirement

| Req    | Behaviour                                                                                              | Test (new unless noted)                                                     | Command                                                                       |
| ------ | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| AUB-01 | Valid token: routes, params, 404/405 JSON, body rules (413, chunked, content type), `no-store`, `nosniff`, no CSP, no `Access-Control-*`, `/`, `/icon`, `/static/*` are 404 even with a token, public-route router rejected, `bind` honoured | `test_api_server.py` | `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q` |
| AUB-01 | Ingress output byte-identical                                                                         | `test_ingress_characterisation.py` + untouched existing suites               | `... -m pytest admin-ui/tests -q`                                             |
| AUB-02 | Matrix methods (incl. `HEAD`, `OPTIONS`, `TRACE`, `FOO`) x paths x auth variants -> one normalised 401; raw cases: HTTP/0.9, malformed line, overlong URI, duplicate/obs-fold/non-ASCII `Authorization`; scheme case and extra spaces accepted with the valid token | `test_api_server.py` | same |
| AUB-03 | `OptionToken` empty/None/non-ASCII rejected; `make_api_server(..., None, ...)` raises before binding; `GeneratedToken` 43-char token, file `0o600` after create and rotate, file content only `sha256 <hex>`, plaintext once, rotate invalidates old token, malformed file raises, concurrent verify during rotate | `test_api_tokens.py` | `... -m pytest admin-ui/tests/test_api_tokens.py -q` |
| AUB-04 | `capfd` shows no token / `Authorization` value after full matrix, handler exception and token lifecycle; `repr()` redacts; handler `Request.headers` has no `Authorization` | `test_api_server.py`, `test_api_tokens.py` | same |
| AUB-05 | R-16 row, exports, rules view                                                                         | `test_docs.py`, `test_rules_view.py`, `rules_view.test.mjs` (updated counts) | `make test-admin-ui` |
| AUB-06 | Lock, copies, versions                                                                                 | `test_sync.py` (unchanged), `make check-admin-ui-sync STRICT=yes`, `make validate-versions`, consumer suites | `make release-admin-ui-lib VERSION=0.10.0` |

Run the new suites also under CI's Python: `uv run --python 3.12 --with pytest --with pyyaml python3 -m pytest
admin-ui/tests -q`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category              | Applies | Standard Control                                                                                  |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------- |
| V2 Authentication          | yes     | 256-bit `secrets` token or option token; SHA-256 + `hmac.compare_digest`; no plaintext at rest    |
| V3 Session Management      | no      | Stateless bearer per request, no cookies                                                          |
| V4 Access Control          | yes     | Gate before routing for every method/path; separate port and router; no `public=True` on the API |
| V5 Input Validation        | yes     | Shared `_read_body` (`MAX_BODY`, JSON only, no chunked), strict `Authorization` parsing           |
| V6 Cryptography            | yes     | stdlib only (`secrets`, `hashlib`, `hmac`); never hand-rolled                                     |
| V7 Error Handling/Logging  | yes     | Silenced request log, no token in messages/repr, tracebacks only for handler bugs                 |
| V9 Communications          | partial | No TLS in the listener (plain HTTP); exposure limited to unpublished port / LAN / Tailscale (R-16) |

### Known Threat Patterns

| Pattern                                         | STRIDE                 | Standard Mitigation                                                 |
| ----------------------------------------------- | ---------------------- | ------------------------------------------------------------------- |
| Token brute force / timing                      | Spoofing               | 256-bit token, digest compare, identical 401                        |
| Response differences leak validity              | Information disclosure | One fixed 401 byte string for every failure                         |
| Method/parser paths before the gate             | Elevation              | `__getattr__` for `do_*`, `send_error` override                     |
| Token in logs/tracebacks                        | Information disclosure | Hidden header, redacting `repr`, no interpolation, `capfd` tests    |
| Plaintext token sniffed on the LAN              | Information disclosure | Port unpublished by default; Tailscale or reverse proxy is operator choice (documented in R-16 / Security notes) |
| Slowloris on the API port                       | Denial of service      | Handler `timeout`; ingress port is unpublished anyway               |
| Hash file readable by others                    | Information disclosure | `mkstemp` 0o600 + `os.replace`; hash of a 256-bit token is not reversible |

## Sources

### Primary (HIGH confidence)
- In-repo files read this session: `admin-ui/app/web/skeleton/*.py`, `admin-ui/tests/{conftest,test_skeleton_server,
  test_public_routes,test_docs,test_sync,test_rules_view,test_tracer,test_addon_scaffold,test_demo_api,
  test_static_rules}.py`, `admin-ui/tests/js/{lib_contract,rules_view}.test.mjs`, `admin-ui/DOCS.md`,
  `admin-ui/CHANGELOG.md`, `internal/sync-admin-ui.py`, `internal/check-admin-ui-rules.py`, `Makefile`,
  `.pre-commit-config.yaml`, `.github/workflows/lint.yml`, consumer Dockerfiles/build.yaml/config.yaml,
  `ntfy/tests/test_contract.py`, `ntfy/tests/test_registry.py`, `marketplace-repo-proxy/SPIKE.md`, `.planning/ROADMAP.md`
  Phase 25, git history (`a752ee7`, `aef2869`, `172a1af`, `e2e6f9d`, `f71f523`).
- Local CPython sources: `/usr/lib/python3.14/{http/server.py,socketserver.py,tempfile.py,secrets.py}`.
- Probe script run on CPython 3.12.15 and 3.14.10 (unknown methods, HTTP/0.9, parser errors, header parsing,
  `compare_digest`).

### Secondary (MEDIUM confidence)
- RFC 6750 sections 2.1 and 3.1 (rfc-editor.org), RFC 9110 sections 5.5, 11.1, 11.6.1 (rfc-editor.org).
- HA add-on configuration reference, `ports` and `host_network` (contributors.home-assistant.io).

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib only, verified in local sources and by probes on both Python versions.
- Architecture: HIGH - derived from the read skeleton code; the base-class refactor is guarded by a characterisation test.
- Pitfalls: HIGH - each one reproduced by probe or read from the file that triggers it.
- Release mechanics: HIGH for the mechanics, MEDIUM for the version/bump policy (A1, A2 need confirmation).

**Research date:** 2026-11-17
**Valid until:** 2026-12-17 (stable domain; re-check consumer list and lib version if `main` moves before execution)
