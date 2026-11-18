---
phase: 01-bearer-api-listener
plan: 01
subsystem: api
tags: [admin-ui, skeleton, http.server, bearer, hmac, sha256, characterisation-test]

requires: []
provides:
  - "make_api_server(router, port, verifier, *, bind, server_version='AdminUiApi', error_mappers=None) in admin-ui/app/web/skeleton/api.py"
  - "TokenVerifier protocol and OptionToken (SHA-256 digest only, hmac.compare_digest, redacted repr) in admin-ui/app/web/skeleton/tokens.py"
  - "Private shared base _JsonHandler (csp, mappers, log_message, _send, _json, _error, _read_body, _fail, _respond) in server.py"
  - "Golden ingress matrix admin-ui/tests/test_ingress_characterisation.py (21 literal cases) as the safety net for plan 02"
  - "Lib VERSION 0.10.0 with a fresh admin-ui/lib.lock"
affects: [01-02, 01-03, 01-04, 01-05, 01-06, marketplace-repo-proxy phase 4, ntfy phase 25]

actuals:
  tokens: 6505
  tasks: 2
  commits: 2
plan_head_before: b03715d2be13092f011166da628ddfebb5a59b91
plan_head_after: 8fff7fb0b0734bcc8410e645646c831faf34dc46

tech-stack:
  added: []
  patterns:
    - "Second listener = own ThreadingHTTPServer + own handler subclass of _JsonHandler, never a second gate in GuiHandler"
    - "Gate first: bearer check before urlsplit, router.match and body read; one fixed 401 byte string"
    - "Error codes needed only by optional features are registered lazily (register_error_code in make_api_server)"
    - "Characterisation tests record literals once from a scratch script outside the repo, never computed in-test"

key-files:
  created:
    - admin-ui/app/web/skeleton/api.py
    - admin-ui/app/web/skeleton/tokens.py
    - admin-ui/tests/test_api_server.py
    - admin-ui/tests/test_ingress_characterisation.py
  modified:
    - admin-ui/app/web/skeleton/server.py
    - admin-ui/app/web/static/lib/VERSION
    - admin-ui/lib.lock

key-decisions:
  - "ClassVar imported on its own `from typing import ClassVar` line so server.py keeps zero deleted lines against the phase base"
  - "OptionToken re-raises the non-ASCII ValueError `from None`, so the chained UnicodeEncodeError (which carries the value) never reaches a traceback"
  - "AUB-01..AUB-04 are only partially delivered (tracer path); their REQUIREMENTS.md checkboxes stay open until plans 02-04"

patterns-established:
  - "_ApiHeaders wraps _PublicHeaders by composition and additionally hides authorization/proxy-authorization"
  - "Handler-class attributes that depend on factory arguments (server_version, mappers) are assigned after the class statement"

requirements-completed: []
requirements-partial: [AUB-01, AUB-02, AUB-03, AUB-04]

coverage:
  - id: D1
    description: "Valid option bearer token on GET /api/ping answers 200 JSON with no-store, nosniff, same-origin and no CSP"
    requirement: AUB-01
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_valid_token_reaches_the_route"
        status: pass
    human_judgment: false
  - id: D2
    description: "Missing, wrong and Basic credentials get the byte-identical 401 with WWW-Authenticate: Bearer and Connection: close"
    requirement: AUB-02
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_missing_wrong_or_basic_credentials_get_the_identical_401"
        status: pass
    human_judgment: false
  - id: D3
    description: "API handlers never see the Authorization header and get Request.public == True"
    requirement: AUB-04
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_api_server.py#test_handler_never_sees_the_authorization_header"
        status: pass
    human_judgment: false
  - id: D4
    description: "No verifier -> ValueError before binding; bind is keyword-only without default"
    requirement: AUB-03
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_api_server.py#test_no_verifier_refuses_before_binding"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/test_api_server.py#test_bind_has_no_default"
        status: pass
    human_judgment: false
  - id: D5
    description: "unauthorized is absent from the import-time ERROR_STATUS and registered as 401 by make_api_server"
    requirement: AUB-01
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_api_server.py#test_unauthorized_is_not_in_the_import_time_error_table"
        status: pass
    human_judgment: false
  - id: D6
    description: "Ingress server status, ordered headers and body bytes pinned for 21 cases against the unmodified GuiHandler"
    verification:
      - kind: integration
        ref: "admin-ui/tests/test_ingress_characterisation.py#test_ingress_response_is_unchanged"
        status: pass
    human_judgment: false
  - id: D7
    description: "Lib 0.10.0 with a fresh lock; consumers only WARN behind"
    verification:
      - kind: other
        ref: "python3 internal/sync-admin-ui.py --check"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-11-18
status: complete
---

# Phase 01 Plan 01: Bearer API Listener Tracer Summary

**Bearer-gated `make_api_server` (explicit bind, option token as SHA-256 digest compared with `hmac.compare_digest`, one
fixed 401) wired end to end over a real socket through a new shared `_JsonHandler`, plus a 21-case literal golden
matrix of the untouched ingress server.**

## Performance

- **Duration:** about 4 min of execution (tracked from 2026-11-18T08:13:13Z to 2026-11-18T08:16:46Z for the code work)
- **Started:** 2026-11-18T08:13:13Z
- **Completed:** 2026-11-18
- **Tasks:** 2/2
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments

- `admin-ui/app/web/skeleton/api.py`: `make_api_server(router, port, verifier, *, bind, server_version="AdminUiApi",
  error_mappers=None)`; `bind` has no default (D-03); no verifier -> `ValueError` before any socket (D-08); lazy
  `register_error_code("unauthorized", 401)` (Pitfall 1); `ApiHandler(_JsonHandler)` gates first for every bound method
  (D-05), then `router.match`, body read, `Request(..., headers=_ApiHeaders(...), public=True)`, `_fail`/`_respond`.
- `admin-ui/app/web/skeleton/tokens.py`: `TokenVerifier` protocol and `OptionToken` keeping only the SHA-256 digest,
  constant-time compare of equal-length digests, non-ASCII presented tokens -> `False`, `repr` redacted (D-07, D-09).
- `admin-ui/app/web/skeleton/server.py`: additive private `_JsonHandler` (88 added lines, 0 deleted); `GuiHandler`,
  `make_handler`, `_PublicHeaders`, `make_server`, `serve` untouched (D-02).
- `admin-ui/tests/test_ingress_characterisation.py`: 21 cases (gate 403 GET/HEAD/OPTIONS/static, 200 JSON, params,
  204, download, 201, index with CSP + ETag, static 200, static 304 via `If-None-Match`, 404, 405, 413, bad JSON,
  chunked 400 via `Transfer-Encoding`, 500, mapped 409, `ApiError` 409, public route) pinned as literals.
- Lib `VERSION` 0.10.0 (D-13) and `admin-ui/lib.lock` refreshed lock-only; no consumer copy touched.

## Task Commits

1. **Task 1: End-to-end bearer-gated GET with an option token (tracer)** - `0186f1f` (feat)
2. **Task 2: Characterisation test that pins the ingress server's responses** - `8fff7fb` (test)

TDD for Task 1: tests were written first and ran red (`ModuleNotFoundError: No module named 'app.web.skeleton.api'`),
then green after the implementation. Test and implementation went into one commit as the plan prescribes ("Commit
server.py, api.py, tokens.py, VERSION, lib.lock and test_api_server.py together"), because the pre-commit drift hook
needs the skeleton change, `VERSION` and lock in the same commit.

Tracer feedback gate (Task 1): no `blocking-human` gate, `<verify>` is automated-only; re-run end to end before Task 2,
all green -> expanded.

## Verification (exact commands and results)

| Command | Result |
| --- | --- |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py -q` | `6 passed` |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 1) | `392 passed` |
| `out=$(python3 internal/sync-admin-ui.py --check) && printf '%s\n' "$out" \| grep -qx "OK admin-ui lock: 0.10.0"` | rc 0; 8 consumer lines `WARN ... behind (copy 0.9.1, source 0.10.0)` |
| `git diff --numstat "$(git merge-base HEAD origin/main)" -- admin-ui/app/web/skeleton/server.py` | `88 0` (zero deleted lines) |
| `python3 -c "... inspect bind KEYWORD_ONLY, no default; 'unauthorized' not in ERROR_STATUS ..."` | `ok` |
| `grep -c "^class _JsonHandler(BaseHTTPRequestHandler):" admin-ui/app/web/skeleton/server.py` | `1` |
| `grep -c "class ApiHandler(_JsonHandler):" admin-ui/app/web/skeleton/api.py` | `1` |
| `git diff --quiet <base> -- admin-ui/app/web/skeleton/errors.py admin-ui/app/web/skeleton/__init__.py` | rc 0 |
| `git status --porcelain -- '*/app/web/admin_ui' '*/app/web/static/vendor/admin-ui'` | empty |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_ingress_characterisation.py -q` | `22 passed` (21 matrix cases + 1 matrix-size test) |
| `s=$(git status --porcelain -- admin-ui/app/web/skeleton) && test -z "$s"` | rc 0 |
| `grep -c` `If-None-Match` / `Transfer-Encoding` / `getheaders()` in the characterisation test | `1` / `2` / `1`; no `_send`, `_JsonHandler`, `make_handler` |
| `git diff --quiet <base> -- test_skeleton_server.py test_public_routes.py test_tracer.py test_static_cache.py test_demo_api.py` | rc 0 |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 2) | `414 passed` |
| pre-commit hooks on both commits (incl. drift check, secrets scan, version validation) | passed |

The literal values were recorded with a throwaway script in the session scratch directory (outside the repository),
run twice with identical output, then copied into the test.

## Files Created/Modified

- `admin-ui/app/web/skeleton/api.py` - bearer-gated API server entry point, handler, header view, token parser
- `admin-ui/app/web/skeleton/tokens.py` - `TokenVerifier` protocol and `OptionToken`
- `admin-ui/app/web/skeleton/server.py` - shared `_JsonHandler` base (additive only)
- `admin-ui/app/web/static/lib/VERSION` - `0.10.0`
- `admin-ui/lib.lock` - regenerated by `python3 internal/sync-admin-ui.py`
- `admin-ui/tests/test_api_server.py` - six tracer tests over a real socket
- `admin-ui/tests/test_ingress_characterisation.py` - golden ingress matrix

## Decisions Made

- `from typing import ClassVar` added as a separate import line: extending the existing `from typing import Any,
  Callable` line would count as a deleted line and break the "zero deleted lines in server.py" invariant.
- `_bearer_token` additionally returns `None` when the header value is not a `str` (covers the HTTP/0.9 `{}` headers
  case early); behaviour otherwise exactly as specified, the strict parser follows in plan 03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] OptionToken suppresses the exception chain for non-ASCII values**
- **Found during:** Task 1
- **Issue:** Raising `ValueError` inside `except UnicodeEncodeError` chains the original exception, whose `.object`
  attribute and traceback text carry the option value (D-09, Pitfall 7).
- **Fix:** `raise ValueError("option token must be printable ASCII without spaces") from None`.
- **Files modified:** `admin-ui/app/web/skeleton/tokens.py`
- **Committed in:** `0186f1f`

**2. [Process] AUB-01..AUB-04 not marked complete in the workstream REQUIREMENTS.md**
- **Issue:** The plan lists AUB-01..04, but it delivers only their tracer path; plans 02-04 complete them (phase
  coverage table). Checking the boxes now would overstate the state.
- **Fix:** `requirements-completed: []`, `requirements-partial` lists the four IDs; `requirements.mark-complete` not run.

**3. [Additive] Characterisation file has one extra test**
- `test_matrix_covers_every_response_kind` asserts at least 20 uniquely named cases, so the pytest count is 22.

---

**Total deviations:** 3 (1 Rule 2 security, 1 tracking, 1 additive test). **Impact:** no scope creep, no change to
the planned public signature.

## Issues Encountered

- The first scratch capture run failed with `ModuleNotFoundError: No module named 'pytest'` (bare `python3`;
  `test_skeleton_server` imports pytest); rerun via `uv run --with pytest --with pyyaml` succeeded.
- `state.advance-plan` refused (`plan_position_unreadable`): the workstream STATE.md had no `Total Plans in Phase` /
  `Progress:` lines. Added `**Total Plans in Phase:** 6` and a `**Progress:**` line under `## Progress` (Rule 3), then
  re-ran `advance-plan` (now plan 2 of 6) and `update-progress`. Root `.planning/` tracking files were not touched.

## Known Stubs

None. `_bearer_token` (lenient parser) and `OptionToken` (no printable-range or minimum-length check) are intentionally
minimal per the plan; plan 03 replaces the parser, plan 04 adds the token checks. `make_api_server` is not yet exported
from the package root (plan 05, together with the DOCS library reference and `test_docs.py`).

## Threat Flags

None beyond the plan's threat model: the new network surface (`make_api_server`) is covered by T-01-01..T-01-05; no
consumer starts the listener yet.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can refactor `GuiHandler` onto `_JsonHandler`; `test_ingress_characterisation.py` must stay green unchanged.
- Every later skeleton commit must refresh `admin-ui/lib.lock` (lib stays 0.10.0, consumers stay WARN behind until
  plan 06 runs `make sync-admin-ui`).
- Hand-off unchanged: ntfy pins its `ERROR_STATUS` literally; it needs `unauthorized` only once it calls
  `make_api_server`.

---
*Phase: 01-bearer-api-listener*
*Completed: 2026-11-18*

## Self-Check: PASSED

- FOUND: `admin-ui/app/web/skeleton/api.py`, `admin-ui/app/web/skeleton/tokens.py`, `admin-ui/tests/test_api_server.py`,
  `admin-ui/tests/test_ingress_characterisation.py`, this SUMMARY
- FOUND commits: `0186f1f`, `8fff7fb` (ancestors of HEAD); `git rev-list --count b03715d..8fff7fb` = 2
