---
phase: 04-scaffold-ingress-validation
plan: 02
subsystem: markdown-renderer
tags: [add-on-runtime, ingress, nginx, multi-namespace, validation, kroki]
dependency_graph:
  requires:
    - phase: 04-scaffold-ingress-validation
      plan: 01
      provides:
        "Single-namespace generator skeleton (INDEX_HTML_TEMPLATE, NGINX_NAMESPACE_BLOCK_TEMPLATE, config.yaml
        directories schema)"
  provides:
    - "Public multi-namespace validation API (validate_namespace, validate_directories) raising ValueError"
    - "Public render_namespace_blocks / render_landing_html helpers exposing per-ns config shape"
    - "Resilient nginx -t validation: tmp dir relocation under /tmp so non-root dev envs succeed"
    - "frozenset RESERVED_NAMES + VALID_NAME_RE constant matching plan's required symbol names"
  affects: [05-multi-namespace-dynamic-config, 06-git-integration]
tech-stack:
  added: []
  patterns:
    - "Public/validate-API + private/_validate-wrapper split (ValueError → SystemExit → return 1)"
    - "nginx temp dir relocation (client_body_temp_path etc. → /tmp/nginx-tmp/) for portable nginx -t"
    - "Reserved-name check before regex check (actionable error for users picking _docsify etc.)"
    - "Frozen set for immutable validation blocklist"
key-files:
  created: []
  modified:
    - markdown-renderer/generate_nginx.py
key-decisions:
  - "Public API contract (validate_namespace, validate_directories, render_namespace_blocks, render_landing_html) added
    on top of Plan 01's private helpers rather than renaming them — backwards compatible + testable"
  - "Reserved-name check runs before regex check so users who pick _docsify etc. see an actionable error message"
  - "nginx temp paths relocated to /tmp/nginx-tmp/ so `nginx -t` succeeds in non-root dev environments (Plan 01 SUMMARY
    noted this as a known environmental gap; this plan fixes it)"
  - "main() catches ValueError from validate_directories and returns 1 — keeps run.sh / HA Supervisor exit-code
    semantics clean (no uncaught tracebacks)"
  - "VALID_NAME_RE kept as primary constant; NAME_RE retained as alias for any external caller that imported the Plan 01
    name"
requirements-completed:
  - INGRESS-04
  - INGRESS-05
  - MULTI-02
  - MULTI-03
  - MULTI-04
  - MULTI-05
metrics:
  duration: "~15 min"
  completed_date: "2026-06-27"
---

# Phase 4 Plan 2: Multi-Namespace Generator Validation Summary

**Multi-namespace generator API contract (validate_namespace, validate_directories, render_namespace_blocks,
render_landing_html) with nginx -t portability fix**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-27T13:17:31Z
- **Completed:** 2026-06-27T13:31:00Z
- **Tasks:** 1 (single-task plan)
- **Files modified:** 1 (markdown-renderer/generate_nginx.py, +165/-50)

## Accomplishments

- Added the public validation API required by the plan: `validate_namespace(name)` and `validate_directories(list)`
  raising `ValueError`, with reserved-name check before regex check for actionable error messages
- Extracted per-namespace nginx block rendering into `render_namespace_blocks(namespaces)` and landing-page rendering
  into `render_landing_html(namespaces)` — both exposed as public helpers so unit tests can assert on per-ns shape
  directly without going through `_render_nginx`
- Promoted `RESERVED_NAMES` to `frozenset` and added `VALID_NAME_RE` constant (matching the plan's required symbol
  names) while keeping `NAME_RE` as a backwards-compatible alias for Plan 01 callers
- Fixed the `nginx -t` portability gap noted in Plan 01 SUMMARY: relocated all nginx temp dirs (`client_body_temp_path`,
  `proxy_temp_path`, `fastcgi_temp_path`, `uwsgi_temp_path`, `scgi_temp_path`) under `/tmp/nginx-tmp/` and pre-create
  the directories in `main()` before invoking `nginx -t` — `nginx -t` now returns 0 in non-root dev environments
- Refactored `main()` to catch `ValueError` from `validate_directories` and return 1 cleanly, replacing the previous
  `sys.exit(1)` pattern (which would have caused uncaught tracebacks under run.sh exit-code propagation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add multi-namespace iteration + name validation to generate_nginx.py** - `a1b1a9e` (feat)

## Files Created/Modified

- `markdown-renderer/generate_nginx.py` - Generator script: added public validation/render API, relocated nginx temp
  dirs under /tmp for portable `nginx -t`, refactored main() to return 1 on ValueError instead of SystemExit

## Decisions Made

- **Public/private split instead of rename.** Plan 02 required specific public symbol names (`validate_namespace`,
  `validate_directories`, `render_namespace_blocks`, `render_landing_html`). Plan 01 already had private helpers
  (`_validate_namespaces`, `_render_nginx`, `_render_landing`) doing the same work. Renaming the private helpers would
  break any external caller that imported them. Added the public helpers as new functions and kept the private helpers
  as thin shells (`_render_landing = render_landing_html` plus a wrapper `_validate_namespaces` that translates
  `ValueError` → `SystemExit(1)`).
- **Reserved-name check before regex check.** `_docsify` does not match the regex (starts with `_`), so without
  reordering, users who picked a reserved name would see a confusing regex-mismatch error. Reordering makes the error
  actionable: "name '\_docsify' is reserved (conflicts with [...])".
- **nginx temp dir relocation.** Plan 01 SUMMARY documented `nginx -t` failing in non-root dev environments with
  `mkdir() "/var/lib/nginx/client-body" failed (13: Permission denied)` even though the syntax was valid. This plan
  fixes the gap by setting all 5 `*_temp_path` directives to `/tmp/nginx-tmp/*` and pre-creating those directories in
  `main()` before `nginx -t`. The add-on container runs as root and works without this fix, but the fix is portable
  across both environments.
- **`validate_directories` raises `ValueError`; `main()` translates to return 1.** The plan's contract specifies
  `ValueError` as the public exception type (verifiable in unit tests). `main()` catches it and returns 1, which run.sh
  / HA Supervisor interpret as a clean exit failure. `sys.exit(1)` would also work but produces an uncaught-traceback
  warning in some HA Supervisor versions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made `nginx -t` succeed in non-root dev environments**

- **Found during:** Task 1 (running the plan's two-namespace dry-run)
- **Issue:** Plan 01 SUMMARY documented that `nginx -t -c /tmp/nginx.conf` fails with
  `mkdir() "/var/lib/nginx/client-body" failed (13: Permission denied)` in non-root environments because nginx tries to
  create its temp directories under `/var/lib/nginx/` by default. The dry-run returned `rc=1` instead of the expected
  `rc=0`, blocking the plan's verify step.
- **Fix:** Added `client_body_temp_path`, `proxy_temp_path`, `fastcgi_temp_path`, `uwsgi_temp_path`, `scgi_temp_path`
  directives pointing at `/tmp/nginx-tmp/*` in both `_render_nginx` (full template) and `_write_minimal_nginx`
  (fallback). `main()` now pre-creates those 5 directories before invoking `nginx -t`.
- **Files modified:** `markdown-renderer/generate_nginx.py`
- **Verification:** Two-namespace fixture dry-run now returns `rc=0`;
  `nginx: the configuration file /tmp/nginx.conf syntax is ok` confirmed via subprocess stdout; all 15 grep assertions
  on generated artifacts pass.
- **Committed in:** `a1b1a9e` (part of task commit)

**2. [Rule 2 - Missing Critical] Added public API wrapper functions**

- **Found during:** Task 1 (planning the edits against Plan 01's existing private helpers)
- **Issue:** Plan 02's verify block asserts on `validate_namespace`, `validate_directories`, `render_namespace_blocks`,
  `render_landing_html`, `RESERVED_NAMES == frozenset(...)`, and
  `VALID_NAME_RE.pattern == r'^[a-z0-9][a-z0-9-]{0,62}$'`. Plan 01 shipped private helpers (`_validate_namespaces`,
  `_render_nginx`, `_render_landing`) and a `set` literal for `RESERVED_NAMES` — none of the public symbols required by
  the plan existed.
- **Fix:** Added the 4 public functions (`validate_namespace`, `validate_directories`, `render_namespace_blocks`,
  `render_landing_html`) as wrappers around / extractions of the existing private helpers. Promoted `RESERVED_NAMES` to
  `frozenset` and added `VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")` as primary constant (kept
  `NAME_RE = VALID_NAME_RE` as backwards-compatible alias).
- **Files modified:** `markdown-renderer/generate_nginx.py`
- **Verification:** All 4 public symbols importable; `RESERVED_NAMES` is a `frozenset` of exactly the 6 expected names;
  `VALID_NAME_RE.pattern` matches the regex string exactly (including the `$` anchor).
- **Committed in:** `a1b1a9e` (part of task commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical) **Impact on plan:** Both deviations necessary for
plan's verify step to pass and for the generator's public API contract to match the plan's required symbol names. No
scope creep beyond what Plan 02 explicitly specified.

## Issues Encountered

- **`/data` is root-owned in the executor environment.** The plan's verify command writes to
  `OPTIONS_PATH = Path("/data/options.json")` directly, but `/data` doesn't exist or isn't writable for non-root
  processes. Resolved by overriding `OPTIONS_PATH` to `/tmp/mr-options.json` for the dry-run (same workaround Plan 01
  SUMMARY used). The production code path is unchanged — `/data/options.json` is the correct HA Supervisor mount path at
  runtime.
- **`.pre-commit-config.yaml` validate-versions hook runs all add-ons.** The commit hook ran
  `Validate Add-on Versioning` and `Validate Add-on config.yaml Schema` against all 5 add-ons including
  `markdown-renderer`. Both passed without changes (the schema/manifest from Plan 01 is still correct).

## Verification Results

All plan verify steps pass:

| Check                                                                                                   | Result                          |
| ------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Symbols: `validate_namespace`, `validate_directories`, `render_namespace_blocks`, `render_landing_html` | All 4 present + correct types   |
| `RESERVED_NAMES == frozenset({'_docsify','api','data','share','config','media'})`                       | Match                           |
| `VALID_NAME_RE.pattern == r'^[a-z0-9][a-z0-9-]{0,62}$'`                                                 | Match                           |
| `validate_namespace('docs')` passes                                                                     | OK                              |
| `validate_namespace('')` raises `ValueError("namespace name cannot be empty")`                          | OK                              |
| `validate_namespace('Docs')` raises `ValueError` (regex mismatch)                                       | OK                              |
| `validate_namespace('_docsify')` raises `ValueError` with reserved msg                                  | OK                              |
| `validate_directories([{a},{a}])` raises `ValueError("duplicate ...")`                                  | OK                              |
| `validate_directories([{a},{b}])` returns validated list                                                | OK                              |
| Two-namespace dry-run (`main()` with docs + runbooks)                                                   | `rc=0`, `nginx -t` passes       |
| `/tmp/nginx.conf` contains `absolute_redirect off` (INGRESS-04)                                         | Present                         |
| `/tmp/nginx.conf` contains `location = /docs { return 301 /docs/; }`                                    | Present                         |
| `/tmp/nginx.conf` contains `location = /runbooks { return 301 /runbooks/; }`                            | Present                         |
| `/tmp/nginx.conf` contains `location /docs/ { alias /tmp/docroots/docs/; }`                             | Present                         |
| `/tmp/nginx.conf` contains `location /runbooks/ { alias /tmp/docroots/runbooks/; }`                     | Present                         |
| `/tmp/docroots/{docs,runbooks}/index.html` exist                                                        | Both present                    |
| Per-ns `index.html` contains `window.location.pathname` (INGRESS-02)                                    | Both namespaces                 |
| Per-ns `index.html` contains `../_docsify/docsify.min.js` (INGRESS-03)                                  | Both namespaces                 |
| Per-ns `index.html` contains `hook.doneEach` (INGRESS-05)                                               | Both namespaces                 |
| `/tmp/landing/index.html` exists + links to `/docs/` and `/runbooks/`                                   | Both links present              |
| Invalid reserved name (`_docsify`) returns `rc != 0`                                                    | `rc=1`, "reserved" error logged |
| `pre-commit run check-executables-have-shebangs`                                                        | Passed (chmod +x retained)      |

## Requirements Coverage

| Req ID     | How Addressed                                                                                                                                                                |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| INGRESS-04 | `absolute_redirect off` in `http {}` block + per-ns `location = /<ns> { return 301 /<ns>/; }`                                                                                |
| INGRESS-05 | `hook.doneEach` → `mermaid.run()` lifecycle hook reused per namespace from Plan 01 INDEX_HTML_TEMPLATE                                                                       |
| MULTI-02   | Per-namespace `location /<name>/ { alias /tmp/docroots/<name>/; try_files ... }` rendered per entry                                                                          |
| MULTI-03   | `/tmp/landing/index.html` listing all namespaces as `<a class="card" href="/<name>/">` cards                                                                                 |
| MULTI-04   | `generate_nginx.py` reads OPTIONS_PATH + writes NGINX_CONF_PATH + per-ns index.html + landing; `main()` runs `nginx -t -c` and returns 1 on validation or `nginx -t` failure |
| MULTI-05   | Public `validate_namespace` + `validate_directories` enforcing regex `^[a-z0-9][a-z0-9-]{0,62}$` + reserved blocklist + duplicate detection                                  |

## Known Stubs / Deferred Items

None — all generator code paths exercised by the dry-run test produce complete, valid output. The `_validate_namespaces`
private wrapper remains in place as a thin shell around `validate_directories` for backwards compatibility with Plan 01
verification paths; it's not a stub.

## Next Phase

Phase 5 (Multi-Namespace + Dynamic Config) will:

1. Validate multi-namespace behavior in actual HA Ingress (not just generator dry-run)
2. Verify volume mounting for `/share`, `/config`, `/media` works end-to-end
3. Document any empirical adjustments needed for the Mermaid `doneEach` hook targeting fenced code blocks (per D-07:
   fallback to Leward/mermaid-docsify v2.0.1 if needed)
4. Verify CSP / unsafe-eval behavior for Mermaid v11 (research flag in STATE.md)

## Self-Check: PASSED

- `markdown-renderer/generate_nginx.py` exists at expected path (`git status` shows only this file modified)
- Commit `a1b1a9e` present in `git log` (`git log --oneline -3` shows the feat(04-02) commit on top of Plan 01)
- Module imports cleanly (`python3 -m py_compile` passes; `import generate_nginx` succeeds)
- All public API symbols (`validate_namespace`, `validate_directories`, `render_namespace_blocks`,
  `render_landing_html`) accessible from the module
- `RESERVED_NAMES` is a `frozenset` of the 6 expected names
- `VALID_NAME_RE.pattern` matches `^[a-z0-9][a-z0-9-]{0,62}$` exactly
- Two-namespace fixture dry-run produces `/tmp/nginx.conf` (passes `nginx -t`), per-namespace index.html files (both
  containing `window.location.pathname` + relative `_docsify/` scripts + `hook.doneEach` Mermaid hook), and a landing
  page linking to both namespaces
