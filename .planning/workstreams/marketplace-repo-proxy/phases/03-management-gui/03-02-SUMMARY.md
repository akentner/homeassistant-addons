---
phase: 03-management-gui
plan: 02
subsystem: infra
tags: [lighttpd, access-log, unix-socket, last-fetch, pytest, privacy]

requires:
  - phase: 01-git-serving-core
    provides: AccessStore (reentrant locked(), HASH_RE, USER_RE, SCHEMA), jsonio (atomic_write_json, read_json, utc_timestamp), options (load_options, parse_repository), logsetup.setup_logging, Paths
provides:
  - app/accessread.py (AccessUnavailable, read_entries_safe, file_signature) - non-renaming locked read of access.json, also for the GUI in 03-03
  - app/lastfetch.py (SCHEMA, FILE_NAME = "last-fetch.json", LastFetchRecord, last_fetch_path, read_last_fetch, write_last_fetch) - D-21 contract
  - app/fetchsink.py (SOCKET_PATH, LINE_RE, MAX_LINE, main) - piped lighttpd access logger, stdlib only, silent
  - app/fetchlog.py (SOCKET_DIR, SOCKET_PATH, SOCKET_GROUP, DATAGRAM_RE, MAX_DATAGRAM, LOG_INTERVAL, bind_socket, parse_datagram, AccessMap, FetchRecorder, make_handler, serve_forever, main) - root receiver
  - socket /run/mrp-fetch/fetch.sock (dir root:lighttpd 0710, socket root:lighttpd 0620)
  - log line format `fetch: {user} → {owner}/{repo}`
affects: [03-03, 03-04, 03-05]

actuals:
  tokens: 13313 # chars/4 over the seven new files (53251 chars)
  tasks: 2
  commits: 3
plan_head_before: 8eaf2dad8c4528350107b938359ad01d26272537
plan_head_after: e67be5f3d0a068f356e58f186a19bfe2cd6ce714

tech-stack:
  added: []
  patterns:
    - "Frequent readers of access.json use read_entries_safe (store lock, no rename) instead of AccessStore.load()"
    - "Forwarder runs as a standalone file under python3 -I: stdlib only, stdout/stderr to /dev/null, per-line exception swallowing"
    - "Receiver throttle state (hash -> last log time) in memory only; file keyed by (repository, user), never a hash"

key-files:
  created:
    - marketplace-repo-proxy/app/accessread.py
    - marketplace-repo-proxy/app/lastfetch.py
    - marketplace-repo-proxy/app/fetchsink.py
    - marketplace-repo-proxy/app/fetchlog.py
    - marketplace-repo-proxy/tests/test_accessread.py
    - marketplace-repo-proxy/tests/test_fetchsink.py
    - marketplace-repo-proxy/tests/test_fetchlog.py
  modified: []

key-decisions:
  - "03-02: FetchRecorder.record takes an optional keyword `pairs` (current access pairs) so the write at a logged fetch can prune removed users; the interface contract record(repository, user, hash_) is unchanged"
  - "03-02: fetchsink drops access records longer than 512 bytes before decoding/matching (MAX_LINE); a valid record is about 200 bytes"
  - "03-02: AccessMap records the access.json signature also when the file is unavailable, so an invalid file is read once per change (one content-free error line per signature), never in a loop"
  - "03-02: make_handler(access_map, recorder) is the datagram handler shared by main and the tests (extra export)"

patterns-established:
  - "Socket tests bind in tempfile.mkdtemp(prefix='mrpf') (AF_UNIX 107-byte limit), never below tmp_path"
  - "Autouse caplog fixture asserts no 32-hex run in any log record of the receiver tests"

requirements-completed: [MRP-15]

coverage:
  - id: D1
    description: "A successful upload-pack POST line fed to the real forwarder under python3 -I becomes one last-fetch entry and one `fetch:` log line, with no forwarder output and no hash anywhere"
    requirement: MRP-15
    verification:
      - kind: integration
        ref: "marketplace-repo-proxy/tests/test_fetchlog.py#test_tracer_upload_pack_line_becomes_one_record_and_one_log_line"
        status: pass
    human_judgment: false
  - id: D2
    description: "Forwarder forwards only `POST …/git-upload-pack 200`, drops every other line, never prints, never blocks with an absent, full or refusing receiver"
    requirement: MRP-15
    verification:
      - kind: integration
        ref: "marketplace-repo-proxy/tests/test_fetchsink.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Receiver: strict datagram format, hash map with case-insensitive repository match, rebuild on signature change, unavailable state without rename, per-hash 60 s throttle, tick/flush, pruning, fixed D-21 layout, bad contract file kept, socket modes and ownership, main SIGTERM and options error"
    requirement: MRP-15
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_fetchlog.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Non-destructive locked read of access.json (missing -> [], bad/newer -> AccessUnavailable, file untouched, deep copies)"
    requirement: MRP-15
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_accessread.py"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-18
status: complete
---

# Phase 3 Plan 02: Access-Log Sink Summary

**Silent stdlib forwarder (`python3 -I`, uid lighttpd) plus root receiver that maps access hashes to users over a
private AF_UNIX datagram socket and writes the D-21 contract `/data/last-fetch.json` and a throttled
`fetch: user → owner/repo` line, never a hash**

## Performance

- **Duration:** 8 min
- **Started:** 2026-11-18T21:38:45Z
- **Completed:** 2026-11-18T21:46Z
- **Tasks:** 2
- **Files modified:** 7 (all new)

## Accomplishments

- `app/fetchsink.py`: redirects stdout/stderr to `/dev/null`, forwards only
  `POST /repo/{owner}/{repo}/{32 hex}/git-upload-pack 200` as `{owner} {repo} {hash}` over a non-blocking socket,
  swallows every error per line and reads to the end of input (exit 0).
- `app/fetchlog.py`: binds `/run/mrp-fetch/fetch.sock` (dir 0710, socket 0620, root:lighttpd when run as root, umask
  0177 during bind), validates datagrams strictly, maps hashes through a signature-cached `AccessMap`, records through
  `FetchRecorder` (one line and one write per hash per 60 s, dirty values written by `tick` after 60 s and on
  SIGTERM/SIGINT, pruning of removed pairs except while `access.json` is unavailable).
- `app/lastfetch.py`: the fixed D-21 contract (schema 1, `updated`, sorted `entries` with exactly `repository`, `user`,
  `last_fetch`; mode 0600 via `atomic_write_json`; `read_last_fetch` never raises, never renames).
- `app/accessread.py`: `read_entries_safe` under the store lock, `AccessUnavailable` instead of the WR-04 rename.

## Task Commits

1. **Task 1: tracer forwarder → socket → receiver → file** - `a168903` (feat)
2. **Task 2 RED: sink behaviour tests** - `9d22696` (test)
3. **Task 2 GREEN: oversized-line bound in the forwarder** - `e67be5f` (fix)

## Verification

- `pytest test_accessread.py test_fetchsink.py test_fetchlog.py`: 88 passed (Python 3.14 and 3.12).
- Phase 1 suite plus sink tests (GUI tests ignored per plan): 310 passed.
- `python3 -I app/fetchsink.py /nonexistent/sock < /dev/null`: exit 0, no output.
- `grep -cE '^(from app|import app)' app/fetchsink.py` = 0; `grep -c 'run/marketplace-repo-proxy' app/fetchlog.py`
  = 0; no `print`/`sys.std*.write` in either program.
- `git diff --stat <merge-base> -- app/access.py app/paths.py app/init.py app/watch.py app/cli.py rootfs/etc/lighttpd`:
  empty.
- `pre-commit run --files <7 files>`: exit 0.

## TDD Gate Compliance

- Task 2 (`tdd="true"`): RED commit `9d22696` precedes GREEN commit `e67be5f`. RED evidence: 1 failed, 87 passed
  (`test_drops_everything_else_silently[huge]`: the forwarder forwarded a 100 kB line).
- Most Task 2 tests were green at RED time because Task 1's action specified the full module behaviour (not only the
  tracer path). This is the expected "behaviour already exists" case, not a wrong test; each such test was checked to
  assert the plan's `<behavior>` item.

## Decisions Made

See `key-decisions` in the frontmatter. The contract names from the plan's `<interfaces>` block are kept exactly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Forwarder line-length bound**
- **Found during:** Task 2 (RED)
- **Issue:** `LINE_RE` allows owner/repo of any length, so a 100 kB access record was forwarded as a datagram.
- **Fix:** `MAX_LINE = 512`; longer lines are skipped before decoding and matching.
- **Files modified:** marketplace-repo-proxy/app/fetchsink.py
- **Commit:** e67be5f

**2. [Rule 2 - Correctness] Pruning at the logged write**
- **Found during:** Task 1
- **Issue:** the interface `record(repository, user, hash_)` has no access to the current pairs, but every write must
  prune removed users (truth D-21).
- **Fix:** optional keyword `pairs=None` on `record`; `make_handler` passes `access_map.pairs()`. Existing positional
  contract unchanged.
- **Files modified:** marketplace-repo-proxy/app/fetchlog.py
- **Commit:** a168903

---

**Total deviations:** 2 auto-fixed (both Rule 2). **Impact:** no contract change for Plans 03-03/03-04.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 03-03 can use `app.accessread.read_entries_safe` and `app.lastfetch.read_last_fetch`.
- Plan 03-04 adds the lighttpd `mod_accesslog` lines (`|exec /usr/bin/python3 -I .../app/fetchsink.py`, format
  `%m %U %>s`) and the s6 longrun `fetchlog` (`python3 -m app.fetchlog`), then proves the chain in the container.

## Self-Check: PASSED

- All 7 created files exist; commits a168903, 9d22696, e67be5f are ancestors of HEAD.
