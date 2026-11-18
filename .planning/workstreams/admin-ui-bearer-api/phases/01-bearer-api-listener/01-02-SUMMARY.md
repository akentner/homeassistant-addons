---
phase: 01-bearer-api-listener
plan: 02
subsystem: api
tags: [admin-ui, skeleton, http.server, bearer, refactor, serve, ipaddress]

requires:
  - "01-01: _JsonHandler, make_api_server tracer, golden ingress matrix"
provides:
  - "GuiHandler(_JsonHandler): one JSON stack for ingress and API (helpers inherited, _fail/_respond)"
  - "serve(server, *more): extra servers in daemon threads, one SIGTERM/SIGINT stops all, every socket closed"
  - "make_api_server: ValueError('bind must be an IPv4 address') and ValueError('public routes are not allowed on the API router') before any socket"
  - "ApiHandler.timeout = 30 (A4); ingress handler timeout stays None"
affects: [01-03, 01-04, 01-05, 01-06]

actuals:
  tokens: 6138
  tasks: 2
  commits: 2
plan_head_before: 7197f94658ad8a8fb572f92f99c950a90997bf62
plan_head_after: 015db87b8d6095d92fc14eabe4bf53d41a7bc26a

tech-stack:
  added: []
  patterns:
    - "serve(server, *more): shutdown() only for extra servers whose thread was started (BaseServer.shutdown blocks otherwise)"
    - "API-only validation lives in make_api_server / ApiHandler, never in the shared _JsonHandler"

key-files:
  created: []
  modified:
    - admin-ui/app/web/skeleton/server.py
    - admin-ui/app/web/skeleton/api.py
    - admin-ui/tests/test_api_server.py
    - admin-ui/lib.lock

key-decisions:
  - "serve() starts the extra threads inside try and skips shutdown/join for threads that never started, so a failing Thread.start still closes every socket"
  - "bind validation catches TypeError/ValueError from ipaddress.ip_address and rejects IPv6; the message names no value"

requirements-completed: []
requirements-partial: [AUB-01]

coverage:
  - id: D1
    description: "GuiHandler on the shared base; golden ingress matrix and six existing suites unchanged and green"
    requirement: AUB-01
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_ingress_characterisation.py#test_ingress_response_is_unchanged"
        status: pass
    human_judgment: false
  - id: D2
    description: "serve(gui, api) runs and stops both servers with one SIGTERM; sockets closed also when the first raises"
    requirement: AUB-01
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_serve_real_gui_and_api_servers_stop_together"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/test_api_server.py#test_serve_closes_every_server_when_the_first_raises"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-04 on the API port: JSON errors, no static/index/icon, body rules, MAX_BODY boundary, Content-Length parsing, headers without CSP/CORS"
    requirement: AUB-01
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_max_body_boundary"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_headers_on_every_api_response"
        status: pass
    human_judgment: false
  - id: D4
    description: "Public routes and non-IPv4 binds refused before any socket; two listeners and 20 concurrent requests"
    requirement: AUB-01
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_api_server.py#test_bind_must_be_an_ipv4_literal"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_concurrent_requests_get_their_own_status"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-11-18
status: complete
---

# Phase 01 Plan 02: Shared JSON Stack, serve() for Several Servers and Complete API Request Handling Summary

**Ingress `GuiHandler` now runs on the shared `_JsonHandler` with byte-identical responses, `serve(gui, api)` runs both
listeners with one SIGTERM, and `make_api_server` refuses non-IPv4 binds and public routes before binding, with a 30 s
socket timeout and every D-04 rule pinned by tests on the API port.**

## Performance

- **Duration:** about 4 min (2026-11-18T08:19:53Z to 2026-11-18T08:23:40Z)
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- `server.py`: `class GuiHandler(_JsonHandler)`; its own `protocol_version`, `log_message`, `_send`, `_json`, `_error`,
  `_read_body` removed; the two `except` clauses replaced by `self._fail(exc)`, result rendering by
  `self._respond(result)`; gate, raw-path public check and static branch unchanged; `server_version`, `csp`, `mappers`
  assigned after the class statement. No `timeout`, no `__getattr__` on the ingress handler.
- `server.py`: `serve(server, *more)`: stop handler shuts down every server in a daemon thread; extra servers run
  `serve_forever` in daemon threads; `finally` shuts down and joins (5 s) every started extra server, then calls
  `server_close()` on all. `serve(server)` alone behaves as before (`app/main.py` unchanged).
- `api.py`: `make_api_server` checks verifier -> IPv4 literal bind -> no public route, all before any socket;
  `ApiHandler.timeout = 30`.
- `test_api_server.py`: 17 new tests (3 serve, 14 request handling); `build_api_router(echo_calls=None)` gained echo,
  nothing, download, boom, protected, foreign and whoami routes.

## Task Commits

1. **Task 1: Ingress handler on the shared JSON base and serve() for several servers** - `db759ce` (refactor)
2. **Task 2: Complete API request handling with IPv4 bind, no public routes and a socket timeout** - `015db87` (feat)

TDD: both tasks' tests were written first and ran red (Task 1: `3 failed, 6 passed`; Task 2: `3 failed, 20 passed`,
the failing ones being public route, IPv4 bind and timeout, the other 11 D-04 tests already held through the shared
base), then green. Test and implementation went into one commit per task as the plan prescribes (drift hook needs the
skeleton change and `lib.lock` together).

## Verification (exact commands and results)

| Command | Result |
| --- | --- |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_ingress_characterisation.py admin-ui/tests/test_skeleton_server.py admin-ui/tests/test_public_routes.py admin-ui/tests/test_tracer.py admin-ui/tests/test_static_cache.py admin-ui/tests/test_demo_api.py admin-ui/tests/test_api_server.py -q` (Task 1) | `244 passed` |
| `grep -c` `class GuiHandler(_JsonHandler):` / `def _send(` / `def serve(server: ThreadingHTTPServer, \*more: ThreadingHTTPServer) -> None:` in server.py | `1` / `1` / `1` |
| `out=$(python3 internal/sync-admin-ui.py --check) && printf '%s\n' "$out" \| grep -qx "OK admin-ui lock: 0.10.0"` (after each task) | rc 0 |
| `git diff --quiet "$(git merge-base HEAD origin/main)" -- test_skeleton_server.py test_public_routes.py test_tracer.py test_static_cache.py test_demo_api.py` | rc 0 |
| `git log --format=%H -- admin-ui/tests/test_ingress_characterisation.py \| wc -l` | `1` (only `8fff7fb`) |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 1) | `417 passed` |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q` (Task 2) | `23 passed` (5 repeated runs, all `23 passed`) |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q -k "public_route or ipv4_literal or two_listeners or concurrent"` | `4 passed, 19 deselected` |
| `test "$(grep -cE 'timeout[ ]=[ ]30' admin-ui/app/web/skeleton/api.py)" = "1" && grep -q "ipaddress" admin-ui/app/web/skeleton/api.py` | rc 0 |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 2) | `431 passed` |
| pre-commit hooks on both commits (drift check, secrets scan, version validation) | passed |

## Files Created/Modified

- `admin-ui/app/web/skeleton/server.py` - GuiHandler on `_JsonHandler`; `serve(server, *more)`
- `admin-ui/app/web/skeleton/api.py` - IPv4 bind and public-route validation; `timeout = 30`
- `admin-ui/tests/test_api_server.py` - serve tests and API request-handling tests
- `admin-ui/lib.lock` - regenerated twice by `python3 internal/sync-admin-ui.py`

## Decisions Made

- `serve()` starts the extra threads inside the `try` and guards shutdown/join with `thread.ident is not None`; see
  deviation 1.
- The 65537-byte case reuses the exact 65536-byte body with one extra space, so only the length differs.
- The CORS header test uses the reserved origin `https://example.invalid` (RFC 2606), no real host.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Robustness] serve() closes every socket also when starting an extra thread fails**
- **Found during:** Task 1
- **Issue:** The plan starts the extra threads before `try`; a failing `Thread.start()` (for example no more threads)
  would then skip `finally` and leak every socket, and an unconditional `shutdown()` on a server whose thread never
  started blocks forever (RESEARCH Pattern 6).
- **Fix:** threads start inside `try`; `finally` calls `shutdown()` and `join()` only for threads with an `ident`, then
  `server_close()` on every server. Observable behaviour in all planned cases is unchanged.
- **Files modified:** `admin-ui/app/web/skeleton/server.py`
- **Commit:** `db759ce`

**2. [Process] AUB-01 not marked complete**
- AUB-01 still gets parts in later plans (strict parser in 03, token checks in 04, docs/export in 05); kept in
  `requirements-partial`, `requirements.mark-complete` not run, consistent with plan 01.

---

**Total deviations:** 2 (1 Rule 2 robustness, 1 tracking). **Impact:** no scope creep, planned signatures unchanged.

## Issues Encountered

None.

## Known Stubs

None. `make_api_server` is still not exported from the package root (plan 05).

## Threat Flags

None. No new surface beyond the plan's threat model (T-01-06..T-01-11 mitigated as planned).

## User Setup Required

None.

## Next Phase Readiness

- Plan 03 can replace `_bearer_token` with the strict parser; `ApiHandler` and its tests are in place.
- Lib stays 0.10.0; consumers stay WARN behind until plan 06 runs `make sync-admin-ui`.

---
*Phase: 01-bearer-api-listener*
*Completed: 2026-11-18*

## Self-Check: PASSED

- FOUND: `admin-ui/app/web/skeleton/server.py`, `admin-ui/app/web/skeleton/api.py`, `admin-ui/tests/test_api_server.py`,
  this SUMMARY
- FOUND commits: `db759ce`, `015db87` (ancestors of HEAD); `git rev-list --count 7197f94..015db87` = 2
