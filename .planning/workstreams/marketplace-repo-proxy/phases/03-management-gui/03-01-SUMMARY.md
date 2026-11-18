---
phase: 03-management-gui
plan: 01
subsystem: ui
tags: [admin-ui, ingress, s6, preact, pytest, docker, build-version]

requires:
  - phase: 01-git-serving-core
    provides: status.json contract, sync trigger file, Options/RepoSpec, Paths, logsetup.mask_hashes, verify script pattern
provides:
  - s6 longrun `gui` (python3 -m app.gui, ingress port 8099, no container environment)
  - app/web/service.py (VERSION_FILE, read_build_version, GuiConfig, load_gui_config, GuiService.overview/meta/request_sync)
  - app/web/server.py (STATIC_DIR, build_router, make_server with OSError mapper)
  - app/web/registration.py (FILE_NAME, REGISTRATION_STATES, read_registration over /data/supervisor.json)
  - routes GET api/overview, GET api/meta, POST api/sync (202)
  - static page (Topbar with version, Repositories view, de/en strings, model.mjs)
  - Dockerfile ARG BUILD_VERSION -> /opt/marketplace-repo-proxy/BUILD_VERSION
  - tests/guihelpers.py and the GUI pytest suite
  - internal/verify-marketplace-repo-proxy-gui.sh
affects: [03-02, 03-03, 03-04, 03-05, 03-06, phase-02-supervisor-registration]

actuals:
  tokens: 20261 # chars/4 over the hand-written diff; 62278 including the two generated admin-ui copies
  tasks: 2
  commits: 3
plan_head_before: ede1640b17018a73b021407adeb4f959b8160fff
plan_head_after: c2b0e3b46e98f45222fc44b22dd9737769dc1736

tech-stack:
  added: [admin-ui lib and skeleton 0.10.0 (vendored copy)]
  patterns:
    - "GUI keeps an Options copy with github_token='' and reads no environment variable"
    - "stdout/stderr wrapped with mask_hashes before the skeleton can print a traceback"
    - "Verify script derives every address from INGRESS_REMOTE in the skeleton copy"

key-files:
  created:
    - marketplace-repo-proxy/app/gui.py
    - marketplace-repo-proxy/app/web/__init__.py
    - marketplace-repo-proxy/app/web/registration.py
    - marketplace-repo-proxy/app/web/service.py
    - marketplace-repo-proxy/app/web/server.py
    - marketplace-repo-proxy/app/web/static/index.html
    - marketplace-repo-proxy/app/web/static/app.css
    - marketplace-repo-proxy/app/web/static/app.mjs
    - marketplace-repo-proxy/app/web/static/model.mjs
    - marketplace-repo-proxy/app/web/static/strings.de.mjs
    - marketplace-repo-proxy/app/web/static/strings.en.mjs
    - marketplace-repo-proxy/app/web/static/views/repositories.mjs
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/gui/{type,run,finish,dependencies.d/init}
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/gui
    - marketplace-repo-proxy/tests/guihelpers.py
    - marketplace-repo-proxy/tests/test_gui_service.py
    - marketplace-repo-proxy/tests/test_gui_server.py
    - marketplace-repo-proxy/tests/test_gui_manifest.py
    - internal/verify-marketplace-repo-proxy-gui.sh
  modified:
    - marketplace-repo-proxy/config.yaml
    - marketplace-repo-proxy/Dockerfile

key-decisions:
  - "03-01: shortSha accepts a 7-40 hex SHA and returns its first 12 characters, because status.json already stores the 12-character short SHA (Phase 1 contract)"
  - "03-01: statusKind keeps returning err; app.css adds .badge.err with the lib's error tokens"
  - "03-01: POST api/sync requires exactly the empty JSON object body; no body, non-object, unknown field or non-JSON content type is 400 bad_request"
  - "03-01: registration detail is masked with mask_hashes and cut to 200 characters in the service, not in the reader"

patterns-established:
  - "GUI service module composes Phase 1 readers (read_status, trigger file) without changing Phase 1 modules"
  - "Verify script sections are inserted before the final line '✓ GUI verify: all checks passed'"

requirements-completed: [MRP-12, MRP-13]

coverage:
  - id: D1
    description: "Ingress-only management page served by the gui s6 longrun; every non-ingress request gets 403 ingress_only"
    requirement: MRP-12
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_server.py#test_gate_matrix_without_header"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 5 ingress gate)"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET api/overview reports each configured repository with status, HEAD, add-ons and registration slot"
    requirement: MRP-13
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_overview_follows_options_order_and_case"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 6 page and overview)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Registration reader for /data/supervisor.json with the four D-19 states"
    requirement: MRP-13
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py -k registration"
        status: pass
    human_judgment: false
  - id: D4
    description: "Add-on version from BUILD_VERSION in api/meta and the top bar"
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py -k build_version"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 7)"
        status: pass
    human_judgment: false
  - id: D5
    description: "POST api/sync creates the trigger file and starts a sync cycle"
    requirement: MRP-13
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_server.py#test_sync_post_with_empty_object"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 9 Sync now)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Repositories view rendering and the top-bar version text in a browser inside HA"
    verification: []
    human_judgment: true
    rationale: "Node view tests are Plan 03-06; the visual result in the HA ingress panel needs a human look"

duration: 10min
completed: 2026-11-18
status: complete
---

# Phase 3 Plan 01: Management GUI tracer Summary

**Ingress-only management page (s6 `gui` on 8099, admin-ui 0.10.0) that lists every configured repository with its
sync state from status.json, shows the build-time add-on version from `api/meta` in the top bar, reads Phase 2's
`/data/supervisor.json` registration states and triggers "Sync now" through `POST api/sync`, proven in the container**

## Performance

- **Duration:** about 10 min of execution (measured from the start mark after the reading pass)
- **Started:** 2026-11-18T21:25:51Z
- **Completed:** 2026-11-18T21:36:30Z
- **Tasks:** 2 (tracer + TDD)
- **Files modified:** 54 (24 hand-written, 30 generated by `make sync-admin-ui`)

## Accomplishments

- s6 longrun `gui` runs `python3 -m app.gui` from a plain `#!/bin/sh` script; its `/proc/<pid>/environ` holds neither
  the PAT nor the `SUPERVISOR_TOKEN` sentinel (positive control: sentinel found in sync's environment).
- The skeleton gate answers 403 `ingress_only` to the outside client, to the ingress client without `X-Ingress-Path`
  and to a request from inside the proxy; only the real ingress peer with the header gets the page and the API.
- `api/overview` reports the fixture repository `ok` with the served HEAD and the `demo` add-on after a real sync.
- `api/meta` and the image file report the `config.yaml` version passed as `BUILD_VERSION`; without it no version.
- `POST api/sync` with `{}` answers 202 and starts a cycle with `sync.reason` `request`.
- 80 GUI pytest cases (38 for registration, build version and meta) plus the green Phase 1 suite (302 total).

## Task Commits

1. **Task 1: tracer, page through ingress with overview and version** - `9fab709` (feat)
2. **Task 2 RED: failing tests for Sync now plus overview, registration, version and gate** - `b2bbfa8` (test)
3. **Task 2 GREEN: Sync now through POST api/sync** - `c2b0e3b` (feat)

## Files Created/Modified

- `marketplace-repo-proxy/app/gui.py` - s6 entry, MaskedStream wrapper, `GUI_PORT`, `main`
- `marketplace-repo-proxy/app/web/service.py` - token-free config, overview, meta, request_sync, build version reader
- `marketplace-repo-proxy/app/web/server.py` - router (`/api/overview`, `/api/meta`, `/api/sync`), OSError mapper
- `marketplace-repo-proxy/app/web/registration.py` - isolated `/data/supervisor.json` reader (D-19)
- `marketplace-repo-proxy/app/web/static/*` - page shell, Repositories view, model, de/en strings, CSS
- `marketplace-repo-proxy/app/web/admin_ui/`, `.../static/vendor/admin-ui/` - generated by `make sync-admin-ui`
- `marketplace-repo-proxy/rootfs/etc/s6-overlay/...gui` - service declaration and bundle entry
- `marketplace-repo-proxy/config.yaml` - five ingress/panel lines, 8099 not under `ports`
- `marketplace-repo-proxy/Dockerfile` - appended `ARG BUILD_VERSION` block (3 lines)
- `marketplace-repo-proxy/tests/guihelpers.py`, `test_gui_{service,server,manifest}.py` - GUI suite
- `internal/verify-marketplace-repo-proxy-gui.sh` - container proof (gate, overview, version, environ, Sync now)

## Interface for Phase 2

Phase 3's reader (`app/web/registration.py`, `read_registration(paths)`) assumes this layout of `/data/supervisor.json`
(D-19):

- A JSON object written by Phase 2's single writer with atomic replace, mode 0600. Phase 3 reads it as root without a
  lock and never writes, renames or deletes it.
- `repositories`: a list with one object per repository: `repository` = `owner/repo` (matched case-insensitively
  against the configured repositories), `registration` = one of `registered`, `missing`, `leftover`, `error`, and an
  optional `message` (the GUI masks 32-hex runs and shows at most 200 characters).
- Every other top-level key and every other entry key is ignored. A missing or unreadable file, a repository without an
  entry, a second entry for the same repository and any other state value mean "no data" (the first entry wins).
- Phase 2's current plans use the states `registered`, `pending`, `disabled`, `failed`; until Phase 2 writes D-19's
  four states into `registration`, the GUI shows no registration data (whichever phase merges second aligns).

Version file (D-30): `/opt/marketplace-repo-proxy/BUILD_VERSION`, written by the Dockerfile from the build argument
`BUILD_VERSION`; the GUI accepts only `X.Y.Z-N` (at most 32 characters).

## Decisions Made

- `shortSha` accepts 7-40 hex characters (see deviation 1).
- `statusKind` returns `err` as specified; `app.css` styles `.badge.err` with `var(--err)` because the lib only has
  `.badge.error`.
- The verify script installs its cleanup trap only after the pre-flight, so a refused run never removes the containers
  of a parallel run with the same prefix.
- The upstream fixture commits with `user.email=fixture` (no e-mail address in the public repo).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HEAD shown as "-" because status.json already stores a short SHA**
- **Found during:** Task 1 (first verify run: `api/overview: head differs`)
- **Issue:** The plan specified `shortSha` for a 40-hex string and a verify check against the fixture's full SHA, but
  Phase 1's `inspect_head` writes `--short=12` into `status.json` (DOCS.md contract), so the view would never show HEAD.
- **Fix:** `shortSha` accepts a 7-40 hex SHA and returns its first 12 characters; the verify script compares with
  `${FIXTURE_HEAD:0:12}`.
- **Files modified:** `marketplace-repo-proxy/app/web/static/model.mjs`, `internal/verify-marketplace-repo-proxy-gui.sh`
- **Verification:** verify script green; node smoke import of `model.mjs`
- **Committed in:** `9fab709`

**2. [Rule 1 - Bug] RED test called `Router.routes` as a property**
- **Found during:** Task 2 GREEN
- **Issue:** `test_no_public_route` iterated `router.routes`, which is a method in the skeleton (TypeError in RED).
- **Fix:** call `router.routes()`.
- **Files modified:** `marketplace-repo-proxy/tests/test_gui_server.py`
- **Verification:** 80 GUI tests pass
- **Committed in:** `c2b0e3b`

**3. [Rule 3 - Blocking] shellcheck SC2015 in the pre-commit hook**
- **Found during:** Task 1 commit
- **Issue:** `A && B || fail` lines rejected by the hook (info severity).
- **Fix:** rewritten as `if` statements; verify script re-run green before the commit.
- **Files modified:** `internal/verify-marketplace-repo-proxy-gui.sh`
- **Committed in:** `9fab709`

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** No scope change; the `shortSha` widening keeps the 40-hex case of the interface.

## TDD Gate Compliance

- RED `b2bbfa8`: target `test_sync_post_with_empty_object` failed on `assert 404 == 202` (route not registered);
  `gsd-tools check tdd-red-evidence` on the JUnit XML report: `RED_EVIDENCE_OK` (8 failed, 72 passed). Semantic
  assessment: all 8 failures are the missing Sync now feature, except `test_no_public_route`, whose TypeError was a test
  defect fixed in GREEN (deviation 2).
- GREEN `c2b0e3b`: 80 passed. No refactor commit (nothing to clean up).

## Verification Results

- `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy-gui.sh`: exit 0, 30 `✓` lines, including
  `✓ top bar version: api/meta reports the config.yaml version`, `✓ tracer: overview through ingress end to end`,
  `✓ POST api/sync without body: 400 bad_request`, `✓ status.json: sync.reason request, ...` and the final
  `✓ GUI verify: all checks passed`.
- `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest test_gui_service.py
  test_gui_server.py test_gui_manifest.py -q`: 80 passed; `-k "registration or build_version or meta"`: 38 passed.
- Phase 1 suite (with the three Plan 03-02 files ignored): 302 passed.
- `make check-admin-ui-sync check-admin-ui-rules`, `make validate-versions`, hadolint (rule set of
  `make docker-build-check`), `pre-commit run --files` on all changed files: green.
- config.yaml diff vs merge base: 0 removed, 5 added lines; Dockerfile: 0 removed, 3 added; build.yaml, access.py,
  paths.py, lighttpd config and the init/lighttpd/sync/access-watch services unchanged; conftest.py unchanged.

## Issues Encountered

None beyond the deviations above.

## Known Stubs

None. The registration column, the Sync now button and the 2 s poll are deliberately Plan 03-06 (scope note of the
plan); the API already carries the data.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 03-06, 03-03, 03-04 and 03-05 can extend `service.py`, `server.py`, the strings, the view and the verify script
  (insert sections before the final line).
- Manager: pass the "Interface for Phase 2" section to the Phase 2 owner (state vocabulary differs today).

---
*Phase: 03-management-gui*
*Completed: 2026-11-18*

## Self-Check: PASSED
