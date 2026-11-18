---
phase: 01-bearer-api-listener
plan: 03
subsystem: api
tags: [admin-ui, skeleton, http.server, bearer, authorization, gate, hardening]

requires:
  - "01-02: ApiHandler on _JsonHandler, _unauthorized/_dispatch, make_api_server validation, timeout = 30"
provides:
  - "ApiHandler.__getattr__: every do_<METHOD> lookup (TRACE, CONNECT, PROPFIND, FOO, lowercase get) -> _dispatch"
  - "ApiHandler.send_error: parser errors (400/414/431/505) answer the identical 401, no request text reflected"
  - "HTTP/0.9 rule in _dispatch: always the 401 body only, on 3.12 and 3.14"
  - "_verified(verifier, token): verifier exceptions are a silent failed check"
  - "_bearer_token(headers) strict: exactly one Authorization value via get_all, Bearer case-insensitive, 1*SP, printable ASCII token"
  - "raw()/normalised()/_request()/_reference_401() raw-socket helpers in test_api_server.py"
affects: [01-04, 01-05, 01-06]

actuals:
  tokens: 4200
  tasks: 2
  commits: 2
plan_head_before: 6addda0e86fe7981c7696ce624c39c23e6ebd9e2
plan_head_after: 049f1137ba69e70bf18d5d959ccccee78287061f

tech-stack:
  added: []
  patterns:
    - "Gate before the stdlib: __getattr__ for do_* plus a send_error override, so no stdlib HTML path exists on the API port"
    - "Identical-401 proof by byte comparison of normalised raw responses (Date and Server dropped)"

key-files:
  created: []
  modified:
    - admin-ui/app/web/skeleton/api.py
    - admin-ui/tests/test_api_server.py
    - admin-ui/lib.lock

key-decisions:
  - "Malformed requests get the 401, not a JSON 400 (flagged assumption A5, one method override to reverse)"
  - "_bearer_token rejects two Authorization headers whichever one is valid; a token is printable ASCII 0x21..0x7E only"

requirements-completed: [AUB-02]

coverage:
  - id: D1
    description: "Every method token, parser error and HTTP/0.9 request ends in the 401; unknown method with the token is a JSON 405"
    requirement: AUB-02
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_unknown_methods_reach_the_gate"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_parser_errors_answer_401"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_http09_gets_only_the_401_body"
        status: pass
    human_judgment: false
  - id: D2
    description: "8 methods x 6 paths x 21 failure variants give one normalised 401; HEAD same headers, empty body"
    requirement: AUB-02
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_every_failure_gets_the_identical_401"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_head_failures_have_the_same_headers_and_no_body"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_401_header_order_is_fixed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Token only from the Authorization header; accepted scheme spellings; raising verifier fails closed silently"
    requirement: AUB-02
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_token_only_from_the_authorization_header"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_accepted_spellings"
        status: pass
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_raising_verifier_is_a_failed_check"
        status: pass
    human_judgment: false
  - id: D4
    description: "Unread body with a wrong token: one 401 with Connection: close, no second request parsed"
    requirement: AUB-02
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_unread_body_closes_the_connection"
        status: pass
    human_judgment: false

duration: 2min (continuation, Task 2 only)
completed: 2026-11-18
status: complete
---

# Phase 01 Plan 03: Every Path Through the Bearer Gate and One Byte-Identical 401 Summary

**The API port now has no stdlib bypass. Unknown or lowercase method tokens, parser errors (400/414/431/505) and HTTP/0.9
requests all end in the one fixed 401. A strict `get_all`-based Authorization parser makes every missing, malformed,
duplicated, misplaced or wrong credential byte-identical across 8 methods x 6 paths x 21 variants. A raising verifier
fails closed without any output.**

## Performance

- **Duration:** Task 1 by the first executor (interrupted, see deviation 1); continuation for Task 2 about 2 min
  (2026-11-18T13:38:45Z to 2026-11-18T13:40:29Z)
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- `api.py` (Task 1): `ApiHandler.__getattr__` returns `_dispatch` for every `do_*` name and raises `AttributeError`
  otherwise. The `send_error` override ignores its arguments and calls `_unauthorized()`. `_dispatch` starts with the
  `request_version == "HTTP/0.9"` rule. The module-level `_verified()` wraps `verifier.verify` and turns any exception
  into False.
- `api.py` (Task 2): `_bearer_token` rewritten:
  - no `get_all` (3.14 HTTP/0.9 dict) -> None
  - exactly one `Authorization` value, stripped of SP/HTAB
  - the scheme must be `bearer` (any case) and have a space separator
  - `lstrip(" ")` on the rest
  - the token must be non-empty and every character in 0x21..0x7E
  - the whole parse sits in try/except returning None
- `test_api_server.py`: the helpers `raw`, `normalised`, `_request`, `_reference_401` plus 11 new tests (5 in Task 1,
  6 in Task 2). Every token is generated at test time and the only address is 127.0.0.1.

## Task Commits

1. **Task 1: Any method token, parser error or HTTP/0.9 request ends in the 401** - `9b6817c` (feat; committed by the
   orchestrator after the first executor was interrupted, see deviation 1)
2. **Task 2: Strict Authorization parsing and one byte-identical 401 for every failed credential** - `049f113` (feat)

TDD for Task 2: tests written first and run red (`3 failed, 31 passed`). The failures were the identical-401 matrix,
the HEAD matrix and the header order, all caused by duplicate `Authorization` headers: the plan-01 parser read only the
first value, so `valid+wrong` and `valid+valid` got 200. The strict parser turned all three green. The other three new
tests (accepted spellings, token only from Authorization, unread body) already held through the plan-01 parser and the
`close_connection` on every 401; they now pin that behaviour. Test and implementation share one commit per task, as in
plans 01-02, because the drift hook needs the skeleton change and `lib.lock` together.

## Verification (exact commands and results)

| Command | Result |
| --- | --- |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q` (Task 1, per orchestrator) | `28 passed` on 3.14 and with `--python 3.12` |
| `grep -c` `def __getattr__` / `def send_error` / `def _verified` / `request_version == "HTTP/0.9"` in api.py; `def __getattr__` in server.py (Task 1) | `1` / `1` / `1` / `1`; `0` |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 1, per orchestrator) | `436 passed` |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q` (Task 2) | `34 passed` |
| `uv run --python 3.12 --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q` (Task 2) | `34 passed` |
| same with `-k "identical_401 or head_failures or accepted_spellings or header_order or only_from_the_authorization or unread_body"`, 3.14 and 3.12 | `7 passed, 27 deselected` each (see deviation 2) |
| `grep -c 'get_all("Authorization")' admin-ui/app/web/skeleton/api.py` | `1` |
| `grep -c "parse_qs" admin-ui/app/web/skeleton/api.py` | `1` |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 2) | `442 passed` |
| `python3 internal/sync-admin-ui.py` then `--check` | `UPDATED admin-ui/lib.lock (version 0.10.0)`, `OK admin-ui lock: 0.10.0` (consumers WARN behind, expected until plan 06) |
| pre-commit hooks on `049f113` (lock drift check, secrets scan, version validation) | passed |

## Files Created/Modified

- `admin-ui/app/web/skeleton/api.py` - `__getattr__`, `send_error`, HTTP/0.9 rule, `_verified`, strict `_bearer_token`
- `admin-ui/tests/test_api_server.py` - raw-socket helpers, gate matrix and identical-401 tests
- `admin-ui/lib.lock` - skeleton hash regenerated after each task by `python3 internal/sync-admin-ui.py`

## Decisions Made

- The token character set is 0x21..0x7E rather than strict `b64token`, so option passwords with arbitrary printable
  characters still work (RESEARCH Pattern 3).
- The `last char changed` variant replaces the last character with `0`, or with `1` when the last character is already
  `0`, so it always differs from TOKEN.
- The non-ASCII variant sends the raw UTF-8 bytes of `ä` (the request is encoded as latin-1 strings carrying those
  bytes), so the server sees the `Ã¤` decoding the research probe described.

## Deviations from Plan

### Auto-fixed Issues

**1. [Process - Interruption] Task 1 committed by the orchestrator, plan finished by a continuation executor**
- **Found during:** Task 1
- **Issue:** An API auth error terminated the first executor in the middle of Task 1, before it committed.
- **Fix:** The orchestrator checked the uncommitted Task 1 work against the plan and committed it as `9b6817c` (verify
  results in the table above). This continuation executor confirmed `9b6817c` exists and that the plan ledger base is
  `6addda0`, then ran Task 2 test-first and wrote this SUMMARY. Task 1 was not redone.
- **Files modified:** none beyond the plan's files
- **Commit:** `9b6817c`

**2. [Process - Verify filter] The Task 2 `-k` acceptance filter selects 7 tests, not 6**
- **Found during:** Task 2 verification
- **Issue:** `identical_401` also matches the plan-01 test `test_missing_wrong_or_basic_credentials_get_the_identical_401`.
- **Fix:** none needed. All 6 new tests are among the 7 that passed. No test was renamed, so plan 01's names stay
  stable.
- **Commit:** n/a

---

**Total deviations:** 2 (both process). **Impact:** no code deviation, planned signatures and behaviour as written.

## Issues Encountered

None in Task 2.

## Known Stubs

None. `make_api_server` is still not exported from the package root (plan 05).

## Threat Flags

None. No surface beyond the plan's threat model. T-01-12..T-01-16 are mitigated as planned, and T-01-SC needs nothing:
no package was added.

## User Setup Required

None.

## Next Phase Readiness

- AUB-02 is complete: every method, path, parser error and credential variant gets one identical 401 with
  `WWW-Authenticate: Bearer`.
- Plan 04 can build on `_verified` and the raw-socket helpers (`raw`, `normalised`, `_request`) for the "token never
  logged" checks.
- Lib stays 0.10.0; consumers stay WARN behind until plan 06 runs `make sync-admin-ui`.

---
*Phase: 01-bearer-api-listener*
*Completed: 2026-11-18*

## Self-Check: PASSED

- FOUND: `admin-ui/app/web/skeleton/api.py`, `admin-ui/tests/test_api_server.py`, `admin-ui/lib.lock`, this SUMMARY
- FOUND commits: `9b6817c`, `049f113` (ancestors of HEAD); `git rev-list --count 6addda0..049f113` = 2
