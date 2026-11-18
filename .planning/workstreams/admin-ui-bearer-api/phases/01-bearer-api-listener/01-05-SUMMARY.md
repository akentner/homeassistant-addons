---
phase: 01-bearer-api-listener
plan: 05
subsystem: docs
tags: [admin-ui, skeleton, bearer, docs, rules, r-16, i18n, exports]
requires:
  - "01-01..01-04: make_api_server, TokenVerifier, OptionToken, GeneratedToken, OPTION_TOKEN_MIN_LENGTH, serve(server, *more)"
provides:
  - "Package-root exports: GeneratedToken, OptionToken, TokenVerifier, make_api_server (app.web.skeleton.__all__)"
  - "DOCS library reference rows api.py and tokens.py, serve(server, *more), four bearer-listener paragraphs"
  - "DOCS consumer recipe step 6 (optional provisioning API) and a plain-HTTP security note"
  - "Rule R-16 (status review) in DOCS, the demo rules view and both string tables"
  - "test_docs_r16_exposure_stays_a_review_item (pins the review status)"
affects: [01-06]
actuals:
  tokens: 9300
  tasks: 2
  commits: 2
plan_head_before: 57b772b4d14ed674646f1c361757627c076193a6
plan_head_after: 79846f5a9399e12fc0a3a445ea49a39d5433ae9d
tech-stack:
  added: []
  patterns:
    - "Doc/code drift guard: SKELETON_EXPORTS == __all__ (minus MAX_BODY) and every name mentioned in the library reference"
    - "Rule ripple in one commit: DOCS table, view RULES/TEXT, de/en strings and three count tests move together"
key-files:
  created: []
  modified:
    - admin-ui/app/web/skeleton/__init__.py
    - admin-ui/lib.lock
    - admin-ui/DOCS.md
    - admin-ui/tests/test_docs.py
    - admin-ui/tests/test_rules_view.py
    - admin-ui/app/web/static/views/rules.mjs
    - admin-ui/app/web/static/strings.de.mjs
    - admin-ui/app/web/static/strings.en.mjs
    - admin-ui/tests/js/rules_view.test.mjs
key-decisions:
  - "R-16 status review, pinned by test_docs_r16_exposure_stays_a_review_item: the exposure half lives in consumer manifests and has no automated check"
  - "OPTION_TOKEN_MIN_LENGTH stays importable from app.web.skeleton.tokens only; the package root exports the four names the plan lists"
requirements-completed: [AUB-05]
coverage:
  - id: D1
    description: "Package-root exports of the API listener and both verifiers, matching the documented export list"
    requirement: AUB-05
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_docs.py#test_docs_skeleton_public_names_match_the_package"
        status: pass
      - kind: command
        ref: "python3 -c \"...from app.web.skeleton import GeneratedToken, OptionToken, TokenVerifier, make_api_server, serve\""
        status: pass
    human_judgment: false
  - id: D2
    description: "Library reference, consumer recipe and security note for the bearer listener (D-02..D-09, D-11)"
    requirement: AUB-05
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_docs.py#test_docs_library_reference_documents_every_export"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/test_docs.py#test_docs_prose_lines_fit_120_columns"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/test_docs.py#test_docs_contains_no_secrets_or_real_hostnames"
        status: pass
    human_judgment: true
    rationale: "Tests prove names, line length and absence of secrets; whether the prose is accurate and sufficient for consumer authors is a review item"
  - id: D3
    description: "Rule R-16 in DOCS and the demo rules view (de, en), status review"
    requirement: AUB-05
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_docs.py#test_docs_r16_exposure_stays_a_review_item"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/test_rules_view.py#test_view_rule_ids_equal_docs_ids"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/test_rules_view.py#test_enforcing_paths_exist_in_the_repository"
        status: pass
      - kind: unit
        ref: "admin-ui/tests/js/rules_view.test.mjs"
        status: pass
    human_judgment: false
duration: 4min
completed: 2026-11-18
status: complete
---

# Phase 01 Plan 05: Package Exports, Library Reference and Rule R-16 Summary

**The bearer API listener is public lib API: `make_api_server`, `OptionToken`, `GeneratedToken` and `TokenVerifier`
import from the package root, and DOCS documents every name, argument, error, exposure rule and the `unauthorized`
hand-off. Blueprint rule R-16 (own port, bearer gate, no token no listener, unpublished port, explicit bind) is in the
DOCS table and the demo checklist with status `review`, and a new test keeps it from being marked `enforced`.**

## Performance

- **Duration:** about 4 min (2026-11-18T13:51:28Z to 2026-11-18T13:55Z)
- **Tasks:** 2/2
- **Files modified:** 9 (none created)

## Accomplishments

- `__init__.py` (Task 1): imports `make_api_server` from `.api` and `GeneratedToken`, `OptionToken`, `TokenVerifier`
  from `.tokens`. `__all__` keeps its grouping: `GeneratedToken` and `OptionToken` after `Download`, `TokenVerifier`
  after `StaticFiles`, `make_api_server` before `make_handler`. The docstring has the new wording.
- DOCS library reference (Task 1):
  - the `server.py` row lists `serve(server, *more)`; new rows `api.py` and `tokens.py`
  - four paragraphs after "Handler results are":
    - listener and exposure: own port and router, `ValueError` cases, `bind` without a default, `0.0.0.0` plus `null`
      under `ports`, `host_network` for LAN or Tailscale, never ingress or a public proxy
    - gate and responses: identical 401 with `WWW-Authenticate: Bearer` and `Connection: close`, the header view,
      JSON only, the 30-second idle timeout, `serve(gui_server, api_server)`
    - the `unauthorized` / `errors.unauthorized` hand-off for consumers that pin `ERROR_STATUS`
    - token sources: "at least 16 characters long (`OPTION_TOKEN_MIN_LENGTH`)", SHA-256 with `hmac.compare_digest`,
      the 0600 `sha256 <hex>` file, plaintext once, malformed file handling, no secret in logs
- DOCS consumer recipe step 6 "Optional provisioning API" (the rules-scanner step is now 7), plus a security note on
  bearer tokens over plain HTTP.
- R-16 (Task 2):
  - DOCS row with 4 cells. Enforced by: `test_api_server.py`, `test_api_tokens.py`; port exposure by review. Status:
    `review`.
  - `RULES` and `TEXT` entries in `rules.mjs`, and `demo.rules.r16.title` / `.how` in de and en.
  - Rule counts 15 to 16 in `test_docs.py`, `test_rules_view.py` and `rules_view.test.mjs` (7 summary regexes). The
    spike tables (S1..S15, `spike_view.test.mjs`) are unchanged.
- `test_docs_r16_exposure_stays_a_review_item`: R-16 status `review`, and the enforced-by cell names both test files.

## Task Commits

1. **Task 1: Package-root exports and the library reference for the API listener**: `3ac6b7f` (feat)
2. **Task 2: Rule R-16 in the blueprint table and in the demo rules view**: `79846f5` (feat)

TDD: each task's tests were changed first and run red:

- Task 1: the four names were added to `SKELETON_EXPORTS`, giving `2 failed, 15 passed`
  (`test_docs_library_reference_documents_every_export`, `test_docs_skeleton_public_names_match_the_package`).
- Task 2: pytest gave `3 failed, 19 passed` (rule table, the new R-16 test, view ids). `rules_view.test.mjs` gave
  `# pass 1`, `# fail 5`.

Each task's tests and sources share one commit. Task 1 needs the skeleton change and `lib.lock` together (drift hook).
In Task 2 the cross-checking tests compare DOCS and the view with each other.

## Verification (exact commands and results)

| Command | Result |
| --- | --- |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_docs.py -q` (Task 1) | `17 passed` |
| `python3 -c "import sys; sys.path.insert(0, 'admin-ui'); from app.web.skeleton import GeneratedToken, OptionToken, TokenVerifier, make_api_server, serve; print('ok')"` | `ok` |
| `python3 internal/sync-admin-ui.py` then `out=$(python3 internal/sync-admin-ui.py --check) && printf '%s\n' "$out" \| grep -qx "OK admin-ui lock: 0.10.0"` | `UPDATED admin-ui/lib.lock (version 0.10.0)`, exit 0 |
| `grep -c "make_api_server" admin-ui/app/web/skeleton/__init__.py` | `2` |
| `OPTION_TOKEN_MIN_LENGTH` between "## Library reference" and "## Consumer recipe" | DOCS lines 67 and 104 |
| `sed -n '/^## Library reference/,/^## Consumer recipe/p' admin-ui/DOCS.md \| tr -s ' \n' '  ' \| grep -c 'at least 16 characters'` | `1` |
| `grep -n "host_network"` / `grep -n "errors.unauthorized"` on DOCS.md | line 89 / line 100 |
| `pre-commit run prettier --files admin-ui/DOCS.md` + `pre-commit run markdownlint-cli2 --files admin-ui/DOCS.md` | Passed (after prettier re-padded the tables once) |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (after Task 1) | `462 passed` |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_docs.py admin-ui/tests/test_rules_view.py -q` (Task 2) | `22 passed` |
| `node --test admin-ui/tests/js/*.test.mjs` (lib_contract included) | `# tests 322`, `# pass 322`, `# fail 0`, exit 0 |
| `make check-admin-ui-rules` | exit 0 |
| `grep -c "^\| R-16 \|" admin-ui/DOCS.md` | `1` |
| `grep -c "range(1, 17)"` / `grep -c "range(1, 16)"` on test_docs.py | `1` / `1` |
| `grep -c '"demo.rules.r16.title"'` on strings.de.mjs / strings.en.mjs | `1` / `1` |
| `grep -c 'id: "R-16", status: "review"' admin-ui/app/web/static/views/rules.mjs` | `1` |
| `git diff --quiet "$(git merge-base HEAD origin/main)" -- admin-ui/tests/js/spike_view.test.mjs` | exit 0 |
| `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q` (plan verification) | `463 passed` |
| `python3 internal/sync-admin-ui.py --check` (plan verification) | `OK admin-ui lock: 0.10.0` |
| pre-commit hooks on both commits (drift check, secrets scan, versioning, prettier, markdownlint) | passed |
| privacy scan of each staged diff (addresses, hostnames, e-mail, JWT-like strings) | only `0.0.0.0` and the existing ingress peer in R-01 |

`--check` still prints `WARN ... behind (copy 0.9.1, source 0.10.0)` for the four consumers. That was already the
case before this plan; plan 06 syncs the consumers.

## Files Created/Modified

- `admin-ui/app/web/skeleton/__init__.py`: four new re-exports and the new docstring
- `admin-ui/lib.lock`: skeleton hash refreshed by `python3 internal/sync-admin-ui.py` (Task 1 only)
- `admin-ui/DOCS.md`: library reference rows and paragraphs, consumer recipe step, security note, R-16 row
- `admin-ui/tests/test_docs.py`: `SKELETON_EXPORTS` with the four names, rule range 17,
  `test_docs_r16_exposure_stays_a_review_item`
- `admin-ui/tests/test_rules_view.py`: rule range 17
- `admin-ui/app/web/static/views/rules.mjs`: R-16 in `RULES` and `TEXT`
- `admin-ui/app/web/static/strings.de.mjs`, `strings.en.mjs`: `demo.rules.r16.title`, `demo.rules.r16.how`
- `admin-ui/tests/js/rules_view.test.mjs`: 16 rules, 16 checkboxes, "N of 16" summaries

## Decisions Made

- The token-source paragraph says "printable ASCII without spaces", which matches the 0x21..0x7E check in `tokens.py`.
  The plan only said "printable ASCII".
- The `Connection: close` claim is backed by the code: `_unauthorized` sets `close_connection`, and the shared `_send`
  then emits the header (`server.py:84-85`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Convention] Module docstring wrapped to two lines**

- **Found during:** Task 1
- **Issue:** On one line, the plan's docstring text is 143 columns. Every other skeleton file stays within the repo's
  120-column Python convention (CLAUDE.md).
- **Fix:** Same words, wrapped after "(stdlib only,".
- **Files modified:** `admin-ui/app/web/skeleton/__init__.py`
- **Commit:** `3ac6b7f`

**Total deviations:** 1 auto-fixed (cosmetic). **Impact:** none on behaviour or the export contract.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None. The plan adds no new network, auth or file surface, only re-exports, docs and demo strings.

## Next Phase Readiness

Ready for 01-06 (consumer sync and release). Notes for it:

- `OPTION_TOKEN_MIN_LENGTH` is documented but not re-exported from the package root, because the plan's export list
  names four classes and functions only. Consumers can import it from `app.web.admin_ui.tokens`.
- A consumer that adopts the listener and pins `ERROR_STATUS` (ntfy) needs `unauthorized` (401) and an
  `errors.unauthorized` string. DOCS now records that hand-off.
- Flagged assumption E10 / A8 still needs human confirmation at verification. R-16's exposure half (port unpublished
  by default, never behind ingress or a public proxy) has no automated check until a consumer manifest exists.

## Self-Check: PASSED

- FOUND: all 9 modified files listed under key-files
- FOUND commits: 3ac6b7f, 79846f5 (ancestors of HEAD; `git rev-list --count 57b772b..HEAD` = 2)
