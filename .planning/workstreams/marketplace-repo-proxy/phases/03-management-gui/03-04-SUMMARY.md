---
phase: 03-management-gui
plan: 04
subsystem: infra
tags: [lighttpd, access-log, s6, last-fetch, preact, pytest, node-test, docker]

requires:
  - phase: 03-management-gui
    provides: "03-02 fetchsink/fetchlog/lastfetch programs, 03-03 GuiService.access_list, Access view and verify helpers"
provides:
  - "lighttpd access log piped only into app/fetchsink.py (`%m %U %>s`), appended with `server.modules +=`"
  - "s6 longrun fetchlog (root, #!/bin/sh, no container environment)"
  - "GET api/access user rows carry last_fetch (ISO 8601 UTC with Z or null) under the display rule last_fetch > created"
  - "Access view column `mrp.access.col.last_fetch` with `mrp.access.never`"
  - "verify-script sections (12) last fetch recorded, (13) last fetch in the GUI, (14) privileges, modes, hygiene, outage"
affects: [03-05, phase-04-api]

actuals:
  tokens: 5761 # chars/4 over the added lines of the realized diff (14 files, 23043 chars)
  tasks: 3
  commits: 4
plan_head_before: 212447d46d888509bfeb14f7cb8f03735bdf2460
plan_head_after: c951fb07be42c82e04328197b8c4fcde8ef15578

tech-stack:
  added: []
  patterns:
    - "GUI reads /data/last-fetch.json once per list call without a lock (single writer fetchlog) and never writes it"
    - "Display rule as plain string comparison of identical YYYY-MM-DDTHH:MM:SSZ values; same second counts as not newer"
    - "Verify scripts wait 2 s between creating/rotating a user and the clone that must show as its last fetch"

key-files:
  created:
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/type
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/run
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/finish
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/dependencies.d/init
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/fetchlog
  modified:
    - marketplace-repo-proxy/rootfs/etc/lighttpd/marketplace-repo-proxy.conf
    - marketplace-repo-proxy/app/web/service.py
    - marketplace-repo-proxy/app/web/static/views/access.mjs
    - marketplace-repo-proxy/app/web/static/strings.de.mjs
    - marketplace-repo-proxy/app/web/static/strings.en.mjs
    - marketplace-repo-proxy/tests/test_gui_manifest.py
    - marketplace-repo-proxy/tests/test_gui_service.py
    - marketplace-repo-proxy/tests/js/access.test.mjs
    - internal/verify-marketplace-repo-proxy-gui.sh

key-decisions:
  - "03-04: last_fetch is shown when the record is strictly newer than created or created is not a valid timestamp; same second means never"
  - "03-04: the Last fetch column appears in the active and the inactive tables (the server applies the same rule to inactive repositories)"
  - "03-04: German column texts are Letzter Abruf and nie"

patterns-established:
  - "Container hygiene scans also reject raw access-log records ((GET|POST) /path NNN) in docker logs"

requirements-completed: [MRP-15]

coverage:
  - id: D1
    description: "lighttpd pipes its access log (method, rewritten path, status only) into the forwarder; fetchlog runs as an s6 longrun; a clone of a GUI user's URL becomes that user's record in /data/last-fetch.json and one `fetch: erin → example-org/private-addons` line, with no hash in the file or log"
    requirement: MRP-15
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_manifest.py#test_lighttpd_access_log_goes_only_into_the_fetch_sink"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_manifest.py#test_fetchlog_service_files"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 12 Fetch sink: last fetch recorded)"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET api/access reports last_fetch per user under the display rule (rotation shows never until the new URL is used); invalid or missing last-fetch file means never and stays untouched"
    requirement: MRP-15
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_last_fetch_display_rule"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_gui_service.py#test_invalid_last_fetch_file_means_never_for_everyone_and_stays_untouched"
        status: pass
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 13 Fetch sink: last fetch in the GUI)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Access view Last fetch column: relative time against now_ms or never, header in active and inactive tables, a11y audits clean"
    requirement: MRP-15
    verification:
      - kind: automated_ui
        ref: "node --test marketplace-repo-proxy/tests/js/access.test.mjs"
        status: pass
    human_judgment: false
  - id: D4
    description: "Least privilege and hygiene in the container: forwarder as lighttpd, fetchlog as root, socket dir 710 and socket 620 root:lighttpd, /data 700, access.json and last-fetch.json 600, /srv/git/access 711, no PAT or SUPERVISOR_TOKEN in forwarder/GUI environments, no hash in logs/file/GUI, git keeps serving with fetchlog killed and s6 restarts it"
    requirement: MRP-15
    verification:
      - kind: e2e
        ref: "bash internal/verify-marketplace-repo-proxy-gui.sh (section 14 Fetch sink: privileges, modes, hygiene, outage)"
        status: pass
      - kind: e2e
        ref: "MRP_VERIFY_PREFIX=mrp-p3-regress bash internal/verify-marketplace-repo-proxy.sh"
        status: pass
    human_judgment: false
  - id: D5
    description: "Look of the Last fetch column and the German wording inside the HA ingress panel"
    verification: []
    human_judgment: true
    rationale: "Node tests run on a fake DOM; column width and wording need a human look in the real panel"

duration: 8min
completed: 2026-11-19
status: complete
---

# Phase 3 Plan 04: Fetch Sink in the Container and Last Fetch in the GUI Summary

**lighttpd now pipes `%m %U %>s` records only into the silent forwarder, the new root s6 longrun `fetchlog` records
fetches, and the Access view shows each user's last fetch (reset to "never" by a rotation until the new URL is used),
proven in the container with privilege, mode, hygiene and outage checks plus a green Phase 1 regression run**

## Performance

- **Duration:** 8 min
- **Started:** 2026-11-18T23:52:19Z
- **Completed:** 2026-11-19T00:00:28Z
- **Tasks:** 3 (tracer, TDD, verify)
- **Files modified:** 14 (5 created, 9 modified)

## Accomplishments

- Four lines appended to the lighttpd config (comment, `server.modules += ("mod_accesslog")`, piped
  `accesslog.filename` to `python3 -I .../app/fetchsink.py`, `accesslog.format = "%m %U %>s"`); no existing line
  changed, `lighttpd/run` untouched, no Dockerfile change.
- New s6 longrun `fetchlog` (`#!/bin/sh`, root, no container environment, `sleep 3` finish, bundle entry).
- `GuiService.access_list` adds `last_fetch` to every user row from one `read_last_fetch(self.paths)` per call, keyed
  `(repository.lower(), user)`, shown only when newer than `created`.
- Access view: "Last fetch" column after "Created" in both tables; `formatRelative(toMs(last_fetch), lang, now_ms)` or
  `mrp.access.never`.
- Container proof: erin's clone shows up in `/data/last-fetch.json` and as `fetch: erin → example-org/private-addons`;
  after rotating erin the GUI shows null, after a clone with the new URL a timestamp again and a second `fetch:` line;
  forwarder as `lighttpd`, `fetchlog` as `root`, modes unchanged, no hash anywhere, git serving survives a killed
  `fetchlog`, s6 restarts it with a fresh 620 socket.

## Task Commits

1. **Task 1: tracer, access log into the sink and fetchlog service** - `89532db` (feat)
2. **Task 2 RED: last fetch tests (service and view)** - `0618db9` (test)
3. **Task 2 GREEN: last fetch in the Access list and view** - `7098673` (feat)
4. **Task 3: container proof of privileges, modes, hygiene, outage** - `c951fb0` (test)

## Files Created/Modified

- `marketplace-repo-proxy/rootfs/etc/lighttpd/marketplace-repo-proxy.conf` - four appended access-log lines
- `marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/{type,run,finish,dependencies.d/init}` and
  `user-bundles.d/user/contents.d/fetchlog` - new longrun (run/finish mode 100755)
- `marketplace-repo-proxy/app/web/service.py` - `_shown_last_fetch`, `last_fetch` in `_user_row`, one read per list
- `marketplace-repo-proxy/app/web/static/views/access.mjs` - `LastFetchCell`, column in active and inactive tables
- `marketplace-repo-proxy/app/web/static/strings.{de,en}.mjs` - `mrp.access.col.last_fetch`, `mrp.access.never`
- `marketplace-repo-proxy/tests/test_gui_manifest.py` - lighttpd lines, forbidden placeholders, fetchlog files
- `marketplace-repo-proxy/tests/test_gui_service.py` - 17 new cases, two existing row assertions gain `last_fetch`
- `marketplace-repo-proxy/tests/js/access.test.mjs` - Last fetch column test, a11y fixture with `last_fetch`
- `internal/verify-marketplace-repo-proxy-gui.sh` - sections (12), (13), (14), header comment

## Decisions Made

See `key-decisions` in the frontmatter. The contract `last_fetch: str | null` on the user rows of `GET api/access` is
kept exactly as the plan's `<interfaces>` block states.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] verify section (12) waits 2 s before erin's first clone**
- **Found during:** Task 2 (first container run of section 13)
- **Issue:** erin was added and cloned within the same second, so `last_fetch == created` and the display rule
  correctly reported null; section 13's first check ("last_fetch non-null") failed.
- **Fix:** `sleep 2` before the clone in section 12, the same as the plan prescribes before the post-rotation clone.
- **Files modified:** `internal/verify-marketplace-repo-proxy-gui.sh`
- **Verification:** GUI verify 62 ✓ / 0 ✗, then 74 ✓ / 0 ✗ with section 14
- **Committed in:** `7098673`

**2. [Rule 2 - Correctness] Last fetch column also in the inactive table**
- **Found during:** Task 2
- **Issue:** the plan's behaviour gives inactive repositories `last_fetch` by the same rule, but only names "a column
  after Created"; without it in the inactive table the value would be computed and never shown.
- **Fix:** the column is added to both column definitions; the node test expects two headers.
- **Files modified:** `marketplace-repo-proxy/app/web/static/views/access.mjs`
- **Committed in:** `7098673`

**3. [Rule 2 - Correctness] extra hygiene checks in section (14)**
- **Found during:** Task 3
- **Issue:** the prohibition also forbids raw access-log lines in the add-on log, and the needles file must be 600.
- **Fix:** `docker logs` is scanned for `(GET|POST) /path NNN` records (before and after the outage) and the needles
  file mode is checked.
- **Files modified:** `internal/verify-marketplace-repo-proxy-gui.sh`
- **Committed in:** `c951fb0`

### Notes

- The node test uses a 5-minute offset ("5 minutes ago"): the vendored `formatRelative` prints "now" below 45 s, so
  the plan's example text "5 seconds ago" cannot occur.

---

**Total deviations:** 3 auto-fixed (1 bug in the verify script, 2 correctness). **Impact:** no contract change.

## TDD Gate Compliance

- Task 2 (`tdd="true"`): RED `0618db9` before GREEN `7098673`.
- RED evidence (pytest JUnit XML, 114 tests, 17 failed): `gsd-tools check tdd-red-evidence` = `RED_EVIDENCE_OK`,
  target `test_last_fetch_is_none_without_last_fetch_file` failed with `KeyError: 'last_fetch'`. Semantic assessment:
  all 17 failures are the missing `last_fetch` field (including two existing exact-row assertions extended with
  `last_fetch: None`); no collection, import or fixture fault.
- RED evidence (node TAP, 14 tests, 1 failed): `RED_EVIDENCE_OK`, target "last fetch column: a timestamp renders
  relative to now_ms, null and a missing value render never" failed on `0 !== 2` (no Last fetch header). Semantic
  assessment: the planned column is missing; the a11y test passed at RED because extra row fields do not change the
  existing markup.
- No refactor commit. Task 3's commit uses `test(...)` because it changes only the verify script.

## Verification Results

- `uv run ... pytest marketplace-repo-proxy/tests -q`: 513 passed (494 before this plan).
- `node --test marketplace-repo-proxy/tests/js/*.test.mjs`: 53 pass, 0 fail (i18n parity included).
- `make check-admin-ui-rules`: exit 0.
- `flock ~/.cache/mrp/verify.lock bash internal/verify-marketplace-repo-proxy-gui.sh` (final clean run on the
  committed tree, `docker ps` showed no `mrp-` container inside the lock): exit 0, 74 ✓, 0 ✗, including
  `✓ add-on log: fetch: erin → example-org/private-addons`, `✓ forwarder app/fetchsink.py runs as lighttpd`,
  `✓ socket directory /run/mrp-fetch 710 root:lighttpd, fetch.sock 620 root:lighttpd` and
  `✓ GUI verify: all checks passed`.
- `flock ... MRP_VERIFY_PREFIX=mrp-p3-regress bash internal/verify-marketplace-repo-proxy.sh`: exit 0, 86 ✓, 0 ✗.
- `docker ps -a | grep -cE '^mrp-(gui-verify|p3-regress)'`: 0 after both runs.
- lighttpd diff vs merge-base: 0 removed, 4 added; last line `accesslog.format = "%m %U %>s"`;
  `server.breakagelog = "/dev/null"` once.
- Dockerfile diff vs merge-base: 0 removed, 3 added (Plan 03-01's `BUILD_VERSION` block only).
- `git diff --stat <merge-base> -- s6-rc.d/{lighttpd,sync,init,access-watch}`: empty.
- `git ls-files -s fetchlog/run fetchlog/finish`: 100755 twice.
- `grep -c 'read_last_fetch(' service.py` = 1; `grep -cE 'write_last_fetch|atomic_write_json\(.*last' service.py` = 0.
- `grep -c 'pkill -f'` = 1, `grep -c '710 root:lighttpd'` = 2, IPv4 pattern count 0, `bash -n` and `shellcheck` clean
  for the GUI verify script.

## Issues Encountered

None besides deviation 1.

## Known Stubs

None.

## Threat Flags

None. The new surface (access-log pipe, socket, last-fetch file, `last_fetch` field) is the plan's threat register
T-03-23 to T-03-28, each proven by a container check.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-05 documents the access-log sink in DOCS.md "Security notes" (T-01-02 now "access log only into the sink"),
  the `/data/last-fetch.json` contract, the `fetchlog` service and the "never until the new URL is used" rule.

---
*Phase: 03-management-gui*
*Completed: 2026-11-19*

## Self-Check: PASSED

- Created files exist; commits `89532db`, `0618db9`, `7098673`, `c951fb0` are ancestors of HEAD.
