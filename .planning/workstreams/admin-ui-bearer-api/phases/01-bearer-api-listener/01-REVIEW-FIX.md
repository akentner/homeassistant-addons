---
phase: 01-bearer-api-listener
fixed_at: 2026-11-18T15:06:35Z
review_path: .planning/workstreams/admin-ui-bearer-api/phases/01-bearer-api-listener/01-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
committed: 4
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-11-18T15:06:35Z
**Source review:** .planning/workstreams/admin-ui-bearer-api/phases/01-bearer-api-listener/01-REVIEW.md
**Iteration:** 1

**Summary:**

- Findings in scope: 4 (WR-01..WR-04; IN-01..IN-08 out of scope by decision)
- Fixed and verified: 4, each test-first (the regression test failed before the fix)
- Committed: 4, one commit per finding (see "Commits" below)
- Skipped: 0

## Commits

The `check-admin-ui-sync` pre-commit hook rejects a skeleton change while the consumer copies still carry the old
skeleton under the same lib version 0.10.0. The hook was not bypassed. Each finding was committed by the orchestrator
together with its consumer re-sync (`make sync-admin-ui`, no consumer version bump, lib 0.10.0 is unpublished):

- `14bab2f` fix(01): WR-01 keep plaintext and memory in step when the directory fsync fails
- `7fa9e34` fix(01): WR-02 raise ValueError for unreadable and non-regular token paths, never chmod them
- `5dad5b7` fix(01): WR-03 drop slow-drip clients on the API port and cap its connections
- `14ee978` fix(01): WR-04 close API connections whose GET/HEAD/OPTIONS carries a body, strict Content-Length

The full admin-ui suite passed before each commit (465, 468, 474, 479 passed).

## Fixed Issues

### WR-01: Directory fsync failure after `os.replace` leaves a hash nobody has a token for (lockout)

**Files modified:** `admin-ui/app/web/skeleton/tokens.py`, `admin-ui/tests/test_api_tokens.py`, `admin-ui/lib.lock`
**Commit:** `14bab2f`
**Applied fix:** `_write_hash` treats the directory fsync after a successful `os.replace` as best effort
(`contextlib.suppress(OSError)` around `os.open` + `os.fsync` + `os.close` of the directory). A failure before the
replace still raises and keeps the old token, so the `rotate()` contract holds. Test
`test_failed_directory_sync_never_locks_out[open|fsync]`: after the first start and after a rotate, the returned
plaintext verifies after a reload, and the old one does not.

### WR-02: `load_or_create` does not raise `ValueError` for unreadable paths and chmods whatever `path` points at

**Files modified:** `admin-ui/app/web/skeleton/tokens.py`, `admin-ui/tests/test_api_tokens.py`, `admin-ui/DOCS.md`,
`admin-ui/lib.lock`
**Commit:** `7fa9e34`
**Applied fix:** Code now matches the documented `ValueError` contract. The path is opened once with
`O_RDONLY | O_NOFOLLOW | O_NONBLOCK`. `FileNotFoundError` still creates the token. Any other `OSError` (mode 000,
symlink including a dangling one, I/O error) raises `ValueError ... from None`, so no path appears in the message or
chain. `fstat` rejects anything that is not a regular file (directory, FIFO). Up to 128 bytes are read through the fd.
The mode is tightened to 0600 with `os.fchmod(fd)` only after the content is valid. The class docstring and the DOCS
token paragraph now describe this. Tests: `test_malformed_file_with_loose_mode_is_not_chmodded`,
`test_unreadable_file_raises_value_error_and_stays_untouched` (skipped as root),
`test_non_regular_paths_raise_value_error_and_stay_untouched` (directory, FIFO, symlink, dangling symlink).

### WR-03: Unauthenticated slow-drip clients hold handler threads indefinitely

**Files modified:** `admin-ui/app/web/skeleton/api.py`, `admin-ui/tests/test_api_server.py`, `admin-ui/DOCS.md`,
`admin-ui/lib.lock`
**Commit:** `5dad5b7`
**Status:** fixed: requires human verification (timing and concurrency logic)
**Applied fix:**

- The per-read timeout stays at 30 s (`READ_TIMEOUT`, `ApiHandler.timeout`).
- New `_DeadlineReader` (an `io.RawIOBase` under the handler's `rfile`) adds a per-request deadline (`REQUEST_DEADLINE`
  = 30 s, `ApiHandler.request_deadline`). The clock starts at the first byte of each request and covers the line, the
  headers and the body.
- Each `recv` waits at most `min(per-read, remaining)`. A missed deadline raises `TimeoutError`, which the stdlib
  `handle_one_request` turns into a silent close.
- A body that times out inside `_dispatch` also closes without a response or traceback (separate `except TimeoutError`
  before the handler call). Handler exceptions still go through `_fail` unchanged.
- `_ApiServer` caps open connections at `MAX_CONNECTIONS` = 32 with a `BoundedSemaphore`. A further connection is closed
  in `process_request` before a thread starts. The slot is released in `process_request_thread`, or if starting the
  thread fails.
- The code comment and the DOCS sentence now state the real guarantees.

**Tests:** `test_api_read_limits`, `test_slow_drip_request_head_is_dropped_at_the_deadline`,
`test_slow_drip_body_is_dropped_without_a_traceback`, `test_idle_connection_closes_after_the_read_timeout`,
`test_deadline_starts_at_the_first_byte_of_each_request` (keep-alive idle time does not count against the deadline) and
`test_connections_beyond_the_cap_are_closed_at_once`. The tests use a 2 s per-read timeout and a 1 s deadline. The three
behavioural tests failed before the fix, and the idle and keep-alive tests pin semantics that must be kept. They were run
three times in a row without flakes.

### WR-04: Bodies on non-body methods are never read, and the connection stays alive (request desync)

**Files modified:** `admin-ui/app/web/skeleton/api.py`, `admin-ui/tests/test_api_server.py`, `admin-ui/DOCS.md`,
`admin-ui/lib.lock`
**Commit:** `14ee978`
**Applied fix:** Only the API handler changed. `server.py`, the shared `_read_body` and every ingress test are untouched.

- After the gate, a `GET`, `HEAD` or `OPTIONS` that announces a body (any `Transfer-Encoding`, or a `Content-Length`
  other than 0) sets `close_connection`. The response then carries `Connection: close`, and the unread bytes are never
  parsed as a second request.
- `ApiHandler._read_body` accepts exactly one `Content-Length` of plain ASCII digits (surrounding blanks allowed), then
  delegates to the shared implementation. `+2`, `1_0` and duplicate headers give 400 `bad_request`. Oversized values
  still give 413.
- DOCS: one sentence notes the stricter API body rules.

**Tests:** `test_body_on_a_non_body_method_closes_the_connection[GET|HEAD|OPTIONS]` (Content-Length and chunked framing,
smuggled POST never reaches the handler), `test_non_body_method_without_a_body_keeps_the_connection` and
`test_content_length_must_be_one_plain_number`.

## Verification

All gates ran in the herdr worktree checkout `feat/admin-ui-bearer-api`, not in an isolated temporary worktree (none was
created by instruction), so the results can be reproduced from that tree.

- `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests -q`: 479 passed (baseline before the fixes: 463)
- `uv run --python 3.12 --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_api_server.py admin-ui/tests/test_api_tokens.py -q`:
  70 passed
- `uv run --with pytest --with pyyaml python3 -m pytest admin-ui/tests/test_docs.py -q`: 18 passed
- `test_ingress_characterisation.py`, `test_skeleton_server.py` and `test_public_routes.py` are unmodified (no diff) and
  pass (179 passed together with `test_docs.py`)
- `pre-commit run prettier` and `markdownlint-cli2` on `admin-ui/DOCS.md` pass, and the changed lines are at most 120
  characters
- `python3 internal/sync-admin-ui.py --check` after the per-finding consumer re-sync: OK, no drift
- Privacy check of each diff: no hostnames, no IPs other than loopback and 0.0.0.0, no e-mail addresses, names or real
  tokens

---

_Fixed: 2026-11-18T15:06:35Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
