---
phase: 26-admin-ui-blueprint
plan: 01
subsystem: infra
tags: [ha-addon, ingress, python-stdlib, preact, htm, docker]
requires:
  - phase: 25-ntfy-addon
    provides: ntfy server gate, router, static whitelist, api.mjs and vendored Preact that were ported/copied
provides:
  - app.web.skeleton package (ApiError, ERROR_STATUS, Request, Router, Download, StaticFiles, INGRESS_REMOTE, is_ingress, make_handler, make_server) in its final module layout
  - demo health API and demo page (gate -> router -> api/health -> lib client -> Preact Badge)
  - lib seed (api.mjs verbatim from ntfy, ui.mjs subset, vendor/ pinned by sha256, VERSION 0.1.0)
  - admin-ui add-on shell (manifest without ports, Dockerfile, run.sh, README, CHANGELOG) at version 0.1.0
  - internal/verify-admin-ui-scaffold.sh Docker smoke test
affects: [26-02, 26-03, 26-04, 26-05, 26-06, 26-08, 26-10, 26-12]
actuals:
  tokens: 18000
  tasks: 3
  commits: 3
plan_head_before: 54acec725c8b999ceab4b1a92b63b13924b417eb
plan_head_after: 9a5c14f94f21497a6b4af5ce7852a5cc77bb68b6
tech-stack:
  added: []
  patterns:
    - "Python skeleton: stdlib only, relative imports only, copyable under another package name"
    - "Gate by peer address AND X-Ingress-Path, evaluated before routing for every method and path"
    - "Self-contained browser lib directory with vendored Preact/htm pinned by sha256"
key-files:
  created:
    - admin-ui/app/main.py
    - admin-ui/app/web/demo_api.py
    - admin-ui/app/web/skeleton/server.py
    - admin-ui/app/web/skeleton/static.py
    - admin-ui/app/web/skeleton/router.py
    - admin-ui/app/web/skeleton/errors.py
    - admin-ui/app/web/skeleton/ingress.py
    - admin-ui/app/web/static/app.mjs
    - admin-ui/app/web/static/lib/api.mjs
    - admin-ui/app/web/static/lib/ui.mjs
    - admin-ui/app/web/static/lib/vendor/preact-htm.mjs
    - admin-ui/config.yaml
    - admin-ui/Dockerfile
    - admin-ui/run.sh
    - internal/verify-admin-ui-scaffold.sh
  modified: []
key-decisions:
  - "StaticFiles(root) replaces ntfy's module-global STATIC_DIR so the skeleton has no module state"
  - "Non-ok health status maps to Badge kind warn (degraded and unknown values), error is reserved for ApiClientError"
  - "Test fixture serves with poll_interval 0.02 so server teardown costs milliseconds instead of 0.5 s per test"
patterns-established:
  - "Byte-for-byte shell cp for vendor/*, lib/api.mjs and fakedom.mjs (verified with cmp/sha256)"
  - "Node tests end with the process.exit hook so Preact timers cannot hang the runner"
requirements-completed: [D-01, D-03, D-04, D-10, D-15, D-16, PD-02, PD-04, PD-06, PD-10, PD-13]
coverage:
  - id: D1
    description: "Ingress gate: only Supervisor peer plus X-Ingress-Path reaches any path, every method; others get 403 ingress_only"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_tracer.py#test_gate_blocks_without_header, test_foreign_peer_is_blocked_even_with_header"
        status: pass
      - kind: integration
        ref: "bash internal/verify-admin-ui-scaffold.sh (steps 5 and 6)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Demo page renders the health as a Preact Badge through the lib client with a relative URL; hostile text stays a text node"
    requirement: "D-03"
    verification:
      - kind: unit
        ref: "admin-ui/tests/js/tracer.test.mjs"
        status: pass
    human_judgment: false
  - id: D3
    description: "Skeleton imports only stdlib or relative modules; vendored bundle byte-identical to ntfy's (sha256 72284e8e...)"
    requirement: "PD-10"
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_tracer.py#test_skeleton_imports_only_stdlib_or_relative, test_vendored_bundle_is_pinned"
        status: pass
    human_judgment: false
  - id: D4
    description: "admin-ui is a valid add-on (validators green, 3-file version sync 0.1.0 via make update-version, no ports, boot manual, panel_admin false) and its image builds and stops cleanly on SIGTERM"
    requirement: "PD-06"
    verification:
      - kind: unit
        ref: "admin-ui/tests/test_addon_scaffold.py"
        status: pass
      - kind: integration
        ref: "bash internal/verify-admin-ui-scaffold.sh"
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-11-02
status: complete
---

# Phase 26 Plan 01: Tracer and Add-on Shell Summary

**One request now travels the whole stack in the real image: Supervisor peer + X-Ingress-Path through a stdlib-only gate and router to `api/health`, the lib JSON client and a vendored-Preact Badge, with every other request answered 403 `ingress_only`.**

## Performance

- **Duration:** about 25 min
- **Completed:** 2026-11-02
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files created:** 34

## Accomplishments

- Skeleton package `app.web.skeleton` in the final module layout (`errors router static ingress server`) with ntfy
  behaviour preserved: gate first for every method and path, `Cache-Control` per kind, `nosniff`, generic
  `500 internal_error` with the traceback on stdout only, no `X-Frame-Options` on static files.
- Lib seed: `api.mjs`, `vendor/*` and `fakedom.mjs` copied byte-for-byte from ntfy; `ui.mjs` re-exports the Preact
  hooks and defines `Badge`; `lib/VERSION` is `0.1.0`; `vendor/README.txt` now points at the admin-ui rule checks.
- Demo page `static/app.mjs` loads `get("health")` once and renders a Badge (`ok`, `warn`, `error`, `muted` while
  loading); the demo imports the lib via public exports only (PD-02).
- Add-on shell: manifest without `ports`, `boot: manual`, `panel_admin: false`; Dockerfile on the HA base image with
  `apk add python3` only; version `0.1.0-0` / `0.1.0` / `v0.1.0` written by `make update-version ... NO_TAG=yes
  NO_PUSH=yes`.
- `internal/verify-admin-ui-scaffold.sh` proves in the image: header-only is not enough (default peer gets 403 even
  with the header), vendored bundle sha256 equals the repo file, `/static/lib/VERSION` is 404, `docker stop` exits 0 in
  3 s.

## Task Commits

1. **Task 1: Tracer, gate to health badge** - `57807be` (feat)
2. **Task 2: Add-on manifest, Dockerfile, scaffold tests** - `ce821be` (feat)
3. **Task 3: Docker smoke script** - `9a5c14f` (feat)

## Verification Results

- `pytest admin-ui/tests -q`: 55 passed (tracer 40, scaffold 14, node suite 1; node tracer test 3 subtests)
- `node --test admin-ui/tests/js/tracer.test.mjs`: 3 pass, 0 fail
- `./internal/validate-versions.sh`, `validate-addon-config.py`, `validate-dockerfile-args.sh`: green
- `hadolint` (plan ignore list) and `shellcheck -e SC1091 -e SC2034` on the verify script: clean
- Local `docker build` of `admin-ui`: ok (mandatory before the Dockerfile commit)
- `bash internal/verify-admin-ui-scaffold.sh`: exit 0, no `admin-ui-verify*` container left afterwards
- `cmp` of `lib/api.mjs` and `tests/js/fakedom.mjs` against ntfy: identical; `preact-htm.mjs` sha256 `72284e8e...fd7`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Prettier reformatted `admin-ui/CHANGELOG.md` in the pre-commit hook**
- **Found during:** Task 2 commit
- **Issue:** the markdown prose wrap differed by one line break, the hook failed and modified the file
- **Fix:** staged the hook's rewrite and re-ran the commit (no content change)
- **Files modified:** `admin-ui/CHANGELOG.md`
- **Commit:** `ce821be`

**2. [Rule 1 - Bug] Test server teardown took 0.5 s per test**
- **Found during:** Task 1 verification (41 tests took 19 s)
- **Issue:** `serve_forever()` default poll interval made `shutdown()` wait up to 0.5 s
- **Fix:** the `serve` fixture passes `poll_interval=0.02` (suite now 1.2 s)
- **Files modified:** `admin-ui/tests/conftest.py`
- **Commit:** `57807be`

**3. [Rule 2 - Missing critical] `config.yaml` description trimmed below 120 columns**
- **Found during:** Task 2
- **Fix:** shortened the description so yamllint's 120-column warning does not fire
- **Files modified:** `admin-ui/config.yaml`
- **Commit:** `ce821be`

Otherwise the plan was executed as written. Tracer feedback gate (auto): `<verify>` re-run after the tracer commit,
green, expansion continued.

## Known Stubs

None. `demo_api.py` intentionally registers health only; plan 26-02 extends it (documented in the plan).
`README.md` links `DOCS.md`, which plan 26-12 creates.

## Threat Flags

None beyond the plan's register (T-26-01..T-26-05 mitigated as specified: peer plus header gate, segment regex and
extension whitelist with containment, sha256-pinned vendor bundle, generic 500, HA base image with no build-time
downloads).

## Open Points

- `docker build` prints `[Warning] One or more build-args [VERSION] were not consumed`: the plan's Dockerfile declares
  no `ARG VERSION` while the verify script passes it (as specified). Harmless; plan 26-12 may drop either side.
- `ntfy`/CI wiring of `admin-ui/tests` into `lint.yml` is deliberately not part of this plan (plan 26-09 checkpoint).

## Self-Check: PASSED

- Files: all 34 files of `files_modified` are tracked (`git ls-files admin-ui internal/verify-admin-ui-scaffold.sh`)
- Commits `57807be`, `ce821be`, `9a5c14f` are ancestors of HEAD; `commits: 3` measured from the plan ledger
- STATE.md, ROADMAP.md and state.json untouched
