---
phase: 03-management-gui
plan: 03
subsystem: ui
tags: [admin-ui, access-store, preact, confirm-dialog, pytest, node-test, docker]

requires:
  - phase: 03-management-gui
    provides: "03-01 GUI server/service/verify script, 03-02 accessread.read_entries_safe, 03-06 node harness and i18n key scan"
  - phase: 01-git-serving-core
    provides: "AccessStore (locked, add, revoke), HASH_RE, USER_RE, SOURCES, RESERVED_USERS, urls.store_urls"
provides:
  - "GuiService.access_list/add_user/user_urls/revoke_user/rotate_user (contract names from the plan interfaces)"
  - "routes GET api/access, POST api/access/{owner}/{repo}, GET .../{user}/urls, DELETE .../{user}, POST .../{user}/rotate"
  - "registered error codes repository_unknown, user_unknown, user_exists, hash_conflict, invalid_hash, invalid_user, user_reserved, access_unavailable; mappers for AccessError and AccessUnavailable (server.ACCESS_ERRORS)"
  - "views/access.mjs (ACCESS_POLL_MS = 15000) with add form, Show URLs, Rotate/Revoke ConfirmDialogs, protected rows, inactive group"
  - "model.mjs SOURCE_KEYS, isSource, sourceKind, USER_LABEL_RE, validUser, splitRepository"
  - "verify-script sections (10) Access: add through the GUI and (11) Access: revoke, rotate, system user"
affects: [03-04, 03-05, phase-04-api]

actuals:
  tokens: 22552 # chars/4 over the added lines of the realized diff (14 files)
  tasks: 3
  commits: 5
plan_head_before: a7161df6c9058b67e792fd75ccd3812a0d08995b
plan_head_after: 5b25d29a005c3b67a2b80b91701a190cfe8b84c5

tech-stack:
  added: []
  patterns:
    - "Every access write runs read_entries_safe inside the same AccessStore.locked() block before add/revoke (unreadable file -> 503, never replaced)"
    - "Rotate = pre-validation, revoke, add in one lock; compensation re-adds the old hash when add fails"
    - "Store URLs only in the add, URL and rotate responses; the polled list carries label/source/created/protected only"
    - "Type-to-confirm checked on the server with plain == on a str (no trim, no case folding)"

key-files:
  created:
    - marketplace-repo-proxy/app/web/static/views/access.mjs
    - marketplace-repo-proxy/tests/js/access.test.mjs
  modified:
    - marketplace-repo-proxy/app/web/service.py
    - marketplace-repo-proxy/app/web/server.py
    - marketplace-repo-proxy/app/web/static/app.mjs
    - marketplace-repo-proxy/app/web/static/model.mjs
    - marketplace-repo-proxy/app/web/static/strings.de.mjs
    - marketplace-repo-proxy/app/web/static/strings.en.mjs
    - marketplace-repo-proxy/tests/test_gui_service.py
    - marketplace-repo-proxy/tests/test_gui_server.py
    - marketplace-repo-proxy/tests/js/model.test.mjs
    - marketplace-repo-proxy/tests/js/i18n.test.mjs
    - marketplace-repo-proxy/tests/test_js.py
    - internal/verify-marketplace-repo-proxy-gui.sh

key-decisions:
  - "03-03: rotate resets created, keeps source and drops unknown fields of that one entry (revoke + add in one lock); a crash between the two writes fails closed"
  - "03-03: repository path segments are matched against configured specs case-insensitively without trimming (own lookup instead of Options.find, which strips)"
  - "03-03: revoke of an unconfigured repository uses the raw path repository (like the CLI); add, URLs and rotate need a configured repository"
  - "03-03: access error responses carry the code as message text, never the exception text; unregistered AccessError codes (e.g. invalid_source) become internal_error with only the type name logged"
  - "03-03: source badges show GUI, CLI, API and System in both languages (i18n allowlist extended for these loanwords)"

patterns-established:
  - "Access view keys ShowUrls by label and created, so a rotation drops URLs shown before it"
  - "Node view tests find rows by the label in the first cell and fail with assertions, not TypeErrors"

requirements-completed: [MRP-14]

coverage:
  - id: D1
    description: "Adding a user in the Access view creates a gui entry with a new hash through AccessStore; its internal URL clones at once from a non-ingress client and the public URL carries the same hash"
    requirement: MRP-14
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_add_user_matches_repository_case_insensitively_and_stores_configured_case"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 10 Access: add through the GUI)"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET api/access lists configured repositories in options order and unconfigured ones as inactive, with label, source, created and protected, never a hash or URL; unreadable access.json answers 503 and is never renamed"
    requirement: MRP-14
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_access_list_groups_sorts_flags_and_never_carries_hash_or_url"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_server.py#test_unreadable_access_file_is_503_and_untouched"
        status: pass
    human_judgment: false
  - id: D3
    description: "Revoke and rotate with exact type-to-confirm; system users answer 409 protected; rotate is atomic for locked readers and compensates a failed add; revoked and rotated-away URLs answer 404 at once, the new URL clones"
    requirement: MRP-14
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_rotate_is_atomic_for_a_locked_reader_in_another_process"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_rotate_restores_the_old_hash_when_add_fails"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 11 Access: revoke, rotate, system user)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Access view: source badges, protected rows without destructive actions, inactive group with Revoke only, ConfirmDialogs with expected label and the rotation warning, URLs only in CopyField after an action, a11y audits clean"
    requirement: MRP-14
    verification:
      - kind: automated_ui
        ref: "node --test marketplace-repo-proxy/tests/js/access.test.mjs"
        status: pass
    human_judgment: false
  - id: D5
    description: "Look and wording of the Access view (dialogs, badges, German texts) inside the HA ingress panel"
    verification: []
    human_judgment: true
    rationale: "Node tests run on a fake DOM; layout, readability of the rotation warning and the German texts need a human look in the real panel"

duration: 14min
completed: 2026-11-19
status: complete
---

# Phase 3 Plan 03: Access View Summary

**Access view and API on Phase 1's AccessStore: add users (new hash, store URLs once in CopyField), on-demand URLs,
revoke and rotate behind exact type-to-confirm dialogs with the rotation warning, read-only system users and an
inactive group, proven in the container with clones (200) and revoked/rotated-away URLs (404)**

## Performance

- **Duration:** 14 min
- **Started:** 2026-11-18T23:34:39Z
- **Completed:** 2026-11-18T23:48:24Z
- **Tasks:** 3 (tracer + 2 TDD)
- **Files modified:** 14 (2 created, 12 modified)

## Accomplishments

- `GuiService.access_list/add_user/user_urls/revoke_user/rotate_user`: every read through `read_entries_safe`, every
  write inside one `AccessStore.locked()` block that checks the file first, so an unreadable `access.json` answers 503
  `access_unavailable` and stays byte-identical (no `.corrupt` rename).
- Rotation in one lock with pre-validation and compensation; a second process reading under the lock never saw the
  user missing or doubled during 50 rotations.
- Five ingress-only routes with strict JSON bodies; access error codes registered and mapped without exception text;
  OSError and unknown AccessError codes give `internal_error` without a traceback or hash.
- Access view: label as text, source badge from `SOURCE_KEYS`, relative creation time, Show/Hide URLs, add form with
  local label check, Rotate/Revoke `ConfirmDialog`s (`expected` = label, `danger`), protected badge, inactive group.
- Container proof: a GUI-added user clones at once; dave's URL 404 right after revoke; carol's old URL 404 and new URL
  clones right after rotate; `local` (system) gets 409 `protected` for both and keeps 200; no hash in `docker logs`,
  `api/access` or `api/overview`.

## Task Commits

1. **Task 1: tracer, add through the Access view with on-demand URLs** - `4f08b1f` (feat)
2. **Task 2 RED: revoke, rotate and access route matrix** - `0891a87` (test)
3. **Task 2 GREEN: revoke and rotate through the GUI API** - `caa6d4d` (feat)
4. **Task 3 RED: node tests for dialogs, protected and inactive rows** - `a225319` (test)
5. **Task 3 GREEN: dialogs, protected rows and inactive group in the view** - `5b25d29` (feat)

## Files Created/Modified

- `marketplace-repo-proxy/app/web/service.py` - access list, add, URLs, revoke, rotate; confirm and protected helpers
- `marketplace-repo-proxy/app/web/server.py` - `ACCESS_ERRORS` registration, mappers, strict body, five access routes
- `marketplace-repo-proxy/app/web/static/views/access.mjs` - Access view (new)
- `marketplace-repo-proxy/app/web/static/model.mjs` - `SOURCE_KEYS`, `isSource`, `sourceKind`, `USER_LABEL_RE`,
  `validUser`, `splitRepository`
- `marketplace-repo-proxy/app/web/static/app.mjs` - `access` in `VIEWS`
- `marketplace-repo-proxy/app/web/static/strings.{de,en}.mjs` - `view.access`, `mrp.access.*`, `mrp.source.*`, eight
  `errors.<code>` keys
- `marketplace-repo-proxy/tests/test_gui_service.py`, `test_gui_server.py` - 103 new cases (178 in the two files)
- `marketplace-repo-proxy/tests/js/access.test.mjs` (new), `model.test.mjs`, `i18n.test.mjs`, `tests/test_js.py`
- `internal/verify-marketplace-repo-proxy-gui.sh` - sections (10) and (11), needles file cleanup

## Decisions Made

See `key-decisions` in the frontmatter. Contract names from the plan's `<interfaces>` block are kept exactly; the
extra model export `isSource` exists because the i18n key scanner sanctions only `*_KEYS[...]` lookups, not a
fallback expression.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] i18n "real German" allowlist extended for the source badges**
- **Found during:** Task 1
- **Issue:** the badge texts GUI, CLI, API and System are identical in both languages, and `i18n.test.mjs` rejects
  identical texts outside an allowlist; that file is not in the plan's file list.
- **Fix:** added the four `mrp.source.*` keys to the allowlist (loanwords, like `mrp.status.ok`).
- **Files modified:** `marketplace-repo-proxy/tests/js/i18n.test.mjs`
- **Verification:** node suite green
- **Committed in:** `4f08b1f`

**2. [Rule 3 - Blocking] verify-script cleanup removes the needles file**
- **Found during:** Task 1
- **Issue:** the new hash needles file lives in `${WORK}`, so the existing cleanup's `rmdir` would leave the scratch
  directory behind.
- **Fix:** `rm -f "${WORK}"/needles-*` before `rmdir` (same as the Phase 1 script).
- **Files modified:** `internal/verify-marketplace-repo-proxy-gui.sh`
- **Committed in:** `4f08b1f`

**3. [Rule 2 - Correctness] own case-insensitive spec lookup without trimming**
- **Found during:** Task 1
- **Issue:** `Options.find` strips whitespace, so a path segment with a leading space would still match; the plan's
  encoding edge requires matching without trimming.
- **Fix:** `GuiService._spec` compares `spec.key == repository.lower()` directly.
- **Files modified:** `marketplace-repo-proxy/app/web/service.py`
- **Committed in:** `4f08b1f`

**4. [Rule 2 - Correctness] Show URLs remount after a rotation**
- **Found during:** Task 3
- **Issue:** URLs opened with "Show URLs" before a rotation would stay on screen with the dead hash.
- **Fix:** the cell is keyed by label and `created` (rotation resets `created`).
- **Files modified:** `marketplace-repo-proxy/app/web/static/views/access.mjs`
- **Committed in:** `5b25d29`

---

**Total deviations:** 4 auto-fixed (2 blocking, 2 correctness). **Impact on plan:** no contract change; `model.mjs` and
`app.mjs` were completed in Task 1 (tracer), so Task 3 changed only the view and the strings.

## TDD Gate Compliance

- Task 2: RED `0891a87` before GREEN `caa6d4d`. RED evidence (JUnit XML, 178 tests, 52 failed):
  `gsd-tools check tdd-red-evidence` = `RED_EVIDENCE_OK`, target `test_revoke_with_exact_confirm_removes_entry_and_link`
  failed on `assert (404 == 204)` (DELETE route missing). Semantic assessment: every failure is the missing revoke /
  rotate feature (404/405 on the routes, `AttributeError` on the missing service methods); no collection, import or
  fixture fault.
- Task 3: RED `a225319` before GREEN `5b25d29`. RED evidence (TAP, 13 tests, 7 failed): `RED_EVIDENCE_OK`, target
  "rotate dialog: type-to-confirm with the label, ..." failed on the assertion `button "undefined" present` (no Rotate
  button and no rotate strings yet). Semantic assessment: the seven failures are the planned dialog, protected-row and
  inactive-group behaviour; the six passing tests cover Task 1's tracer behaviour (list, add form, Show URLs, errors).
  The model tests passed at RED because Task 1 implemented the model helpers the tracer needed.
- No refactor commits.

## Verification Results

- `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy-gui.sh`: exit 0, 53 `✓`, 0 `✗` (final run
  on `5b25d29`), including `✓ outside client clones carol's GUI-added store URL at once`,
  `✓ DELETE of the system user local: 409 protected` and `✓ GUI verify: all checks passed`. Precondition (no `mrp-`
  container) checked inside the lock before every run.
- `pytest test_gui_service.py test_gui_server.py -q`: 178 passed. Whole add-on suite: 494 passed.
- `node --test marketplace-repo-proxy/tests/js/*.test.mjs`: 52 pass, 0 fail.
- `make check-admin-ui-sync check-admin-ui-rules`: exit 0; `pytest tests/test_js.py`: 1 passed (not skipped).
- `grep -c 'source="gui"' service.py` = 1, `grep -c 'read_entries_safe(' service.py` = 5,
  `grep -c '"/api/access/{owner}/{repo}/{user}/rotate"' server.py` = 1, `grep -c 'public=True' server.py` = 0,
  `grep -c 'expected=' views/access.mjs` = 2, `grep -c '"access"' tests/test_js.py` = 1.
- `git diff --stat $(git merge-base HEAD origin/main) -- app/access.py app/paths.py`: empty.
- `pre-commit run --files` on every changed file: passed.

## Issues Encountered

None.

## Known Stubs

None. Last fetch per user is Plan 03-04 (extends `access_list`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-04 can add `last_fetch` to the user rows of `access_list` and a column to the view.
- Plan 03-05 documents rotation (created reset, source kept, unknown entry fields dropped, crash fails closed) and the
  GUI access actions in DOCS.md.

---
*Phase: 03-management-gui*
*Completed: 2026-11-19*

## Self-Check: PASSED

- Created files exist; commits `4f08b1f`, `0891a87`, `caa6d4d`, `a225319`, `5b25d29` are ancestors of HEAD.
