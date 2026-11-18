---
phase: 01-git-serving-core
plan: 03
subsystem: infra
tags: [access-store, revoke, cli, watcher, s6-overlay, python]

requires:
  - "01-01: AccessStore (locked, load, add, reconcile), reconcile_tree, Paths, Options, urls.mask_hash/store_urls, mrp users add/reconcile"
provides:
  - "app/access.py: RESERVED_USERS, AccessStore.get, AccessStore.list_entries, AccessStore.revoke, add(specs=...), error codes user_reserved and hash_conflict"
  - "app/cli.py (mrp): users list [{owner/repo}], users add, users url, users revoke, sync, reconcile"
  - "app/watch.py: AccessWatcher(paths, specs, log, interval=1.0) with signature, poll_once, run_forever; main(argv=None, paths=None)"
  - "s6 longrun access-watch (no container environment), in the user bundle, depends on init"
affects: [01-04, 01-05, 03-gui, 04-api]

actuals:
  tokens: 13000
  tasks: 3
  commits: 6
plan_head_before: bb225033fd4f6d964fca79c51fd237fbbd1cab04
plan_head_after: c2d2b6f7e1e8e76e837a32af092a19955cb3177b

tech-stack:
  added: []
  patterns:
    - "Reads of access.json also hold the store lock, so the corrupt-file rename never races a writer"
    - "Revocation unlinks the hash's links in the same lock as the write; the watcher catches every other writer"
    - "File-signature polling (inode, mtime_ns, size) instead of inotify: stdlib only, one stat per second"
    - "Skipped access entries are logged as `access entry for {repository}/{user} skipped: {reason}`; invalid labels print as <invalid>"

key-files:
  created:
    - marketplace-repo-proxy/app/watch.py
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/access-watch/type
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/access-watch/run
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/access-watch/finish
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/access-watch/dependencies.d/init
    - marketplace-repo-proxy/rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/access-watch
    - marketplace-repo-proxy/tests/test_access.py
    - marketplace-repo-proxy/tests/test_watch.py
  modified:
    - marketplace-repo-proxy/app/access.py
    - marketplace-repo-proxy/app/cli.py
    - marketplace-repo-proxy/tests/test_cli.py

key-decisions:
  - "A client hash used by any entry is now hash_conflict (Plan 01 returned invalid_hash); invalid_hash stays for malformed values"
  - "RESERVED_USERS is matched case-insensitively (Local and LOCAL are reserved too) so no label can shadow Phase 2's system user"
  - "poll_once returns True only when a reconcile ran; a schema-2 file returns False, logs once per signature and keeps the links"
  - "The watcher keeps only the repository list and log level from the options and drops the Options object; it never registers or uses the PAT"
  - "mrp users url refuses an entry with a malformed hash (error: invalid_hash) instead of printing a URL that cannot work"

requirements-completed: [MRP-04, MRP-05]

coverage:
  - id: D1
    description: "Revocation: AccessStore.revoke drops the entry and unlinks its symlink in one lock; other users of the repository keep their link; an unknown user returns False and writes nothing"
    requirement: MRP-04
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_access.py#test_revoke_removes_entry_and_link_while_other_user_keeps_access"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_access.py#test_revoke_of_unknown_user_returns_false_and_writes_nothing"
        status: pass
    human_judgment: false
  - id: D2
    description: "Store robustness: two concurrent store instances lose no entry; schema 2 refused by add/revoke/reconcile without writing; corrupt file moved aside without logging content; unknown keys and fields preserved; 0600 modes"
    requirement: MRP-04
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_access.py (concurrency, schema, corrupt, unknown-field and mode tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Reconcile invariant: exactly one link per valid configured entry, configured case, 0711 directories, stray files and links removed, idempotent (same inode)"
    requirement: MRP-04
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_access.py#test_reconcile_invariant_one_link_per_valid_configured_entry"
        status: pass
    human_judgment: false
  - id: D4
    description: "mrp CLI: users list (masked hashes, inactive marker, filter), users url, users revoke, sync trigger file, schema_unsupported, help text on secret URLs and rotation"
    requirement: MRP-04
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_cli.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "access-watch: a hand edit, a deletion or a corrupt file reaches the symlink tree at the next poll; schema 2 logged once with links kept; stop within one interval"
    requirement: MRP-04
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_watch.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "No full access hash in any access-path log line (store, reconcile, watcher) and no CLI output through logging"
    requirement: MRP-05
    verification:
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_access.py#test_reconcile_invariant_one_link_per_valid_configured_entry"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_watch.py#test_watcher_log_never_contains_a_full_hash"
        status: pass
      - kind: unit
        ref: "marketplace-repo-proxy/tests/test_cli.py#test_cli_output_never_reaches_logging"
        status: pass
    human_judgment: false
  - id: D7
    description: "access-watch runs in the built container without the container environment and revokes a hand edit within 5 s"
    requirement: MRP-04
    human_judgment: true
    rationale: "Plan 05 (wave 3) proves this in the built image; this plan must not build or start containers"

duration: 8min
completed: 2026-11-18
status: complete
---

# Phase 1 Plan 03: Access lifecycle (revoke, mrp CLI, access-watch) Summary

**`mrp users revoke` removes the entry and its symlink in one locked operation, so the URL is 404 at the next request
while other users keep access. `mrp users list/url` and `mrp sync` complete the operator CLI. A new `access-watch` s6
longrun reconciles every change to `/data/access.json` within about a second, including hand edits, deletion and a
corrupt file (fail closed), without ever seeing the container environment.**

## Performance

- **Duration:** about 8 min
- **Started:** 2026-11-18T13:51:22Z
- **Completed:** 2026-11-18T13:59Z
- **Tasks:** 3 (all TDD)
- **Files modified:** 11 (8 created, 3 modified)

## Accomplishments

- `AccessStore` gained `get`, `list_entries` (sorted deep copies), `revoke` and an optional `specs` on `add`, so the
  write and the reconcile share one lock. `RESERVED_USERS = {"local"}` is refused for every source except `system`. A
  client hash already in the file is `hash_conflict`.
- Reads now hold the store lock too. Before, a lock-free reader could rename a freshly written valid file to
  `access.json.corrupt` if it had read a corrupt version a moment earlier.
- `reconcile_tree` logs skipped entries by repository and user only. It replaces a symlinked or non-directory path
  level with a real 0711 directory, and a real directory sitting at a link path with the link.
- `revoke` unlinks the removed hash's links by walking real directories under the access root. It never builds a
  glob from file content, so a hand-edited hash such as `*` cannot unlink other users' links.
- `mrp`: `users list [{owner/repo}]` prints tab-separated `repository user source created masked-hash`, plus
  `(inactive)` for unconfigured repositories. `users url` prints the same `internal:`/`public:` lines as `add`.
  `users revoke` prints `revoked {user} from {repository}` and also works for unconfigured repositories. `sync` writes
  `{}` to the trigger file. The help epilog says that the full URL is a secret and that rotation means revoke plus
  add.
- `app/watch.py` plus the s6 longrun `access-watch` (`#!/bin/sh`, no `with-contenv`, `finish` throttles restarts,
  depends on `init`, listed in the user bundle).

## Task Commits

1. **Task 1: revoke, concurrent writers, bad data (TDD)**: RED `b21cc81` (test), GREEN `ef5558a` (feat)
2. **Task 2: mrp users list/url/revoke and sync (TDD)**: RED `08f16f4` (test), GREEN `82429b1` (feat)
3. **Task 3: access-watch service (TDD)**: RED `90f589d` (test), GREEN `c2d2b6f` (feat)

REFACTOR: none needed.

## TDD Gate Compliance

Each RED run used `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest <file> -q
--junitxml=<phase dir>/red-01-03-tN.xml`. The record went through `gsd-tools check tdd-red-evidence`, and the records
were moved out of the repository afterwards.

| Task | RED result | Target | Verdict | Semantic assessment |
| --- | --- | --- | --- | --- |
| 1 | exit 1, 24 tests, 16 failed | `test_reconcile_invariant_one_link_per_valid_configured_entry` | `RED_EVIDENCE_OK` (`target_test_failed`) | fails on `assert 'other-org/tools/dave' in caplog.text`: Plan 01 logged `... invalid hash: other-org/tools / dave`. The other failures are assertions against the RED stubs (`get`/`list_entries`/`revoke` returning None/[]/False, empty `RESERVED_USERS`) or the old `invalid_hash` code. The 8 passes cover Plan 01 behavior (uniqueness, concurrency, modes, schema refusal of add/reconcile) |
| 2 | exit 1, 28 tests, 13 failed | `test_users_revoke_removes_entry_and_link` | `RED_EVIDENCE_OK` (`target_test_failed`) | fails on `assert 2 == 0`: the `revoke` subcommand did not exist, so argparse exited with usage. No stub was needed. The passes are the Plan 01 tests plus the `hash_conflict`/`user_reserved` checks that Task 1 already satisfied |
| 3 | exit 1, 10 tests, 10 failed | `test_hand_edit_removing_an_entry_unlinks_it_at_the_next_poll` | `RED_EVIDENCE_OK` (`target_test_failed`) | fails on `assert False is True`: the stub `poll_once` never reconciles. Every failure is an assertion against the `app/watch.py` stub |

GREEN: the same files fully pass (24 / 28 / 10).

## Verification Results

| Command | Result |
| --- | --- |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 136 passed (87 before this plan) |
| same suite with `uv run --offline --python 3.12 ...` (CI runtime) | 136 passed |
| `pytest marketplace-repo-proxy/tests/test_access.py -q` (Task 1, needs at least 16) | 24 passed, incl. the invariant test |
| `pytest marketplace-repo-proxy/tests/test_cli.py -q` (Task 2, needs at least 12) | 28 passed |
| `pytest marketplace-repo-proxy/tests/test_watch.py -q` (Task 3, needs at least 5) | 10 passed |
| `shellcheck -s sh` on `access-watch/run` and `access-watch/finish` | clean |
| `pre-commit run --files` on all 11 plan files | exit 0, all hooks Passed or Skipped |

Acceptance greps: in `access.py`, `def revoke` 1, `RESERVED_USERS` 2 and `secrets.token_hex(16)` 1. In `cli.py`,
`import logging` 0, `"revoke"` 2 and `trigger_file` 1. `access-watch/run` starts with exactly `#!/bin/sh` and contains
`python3 -m app.watch` once. `type` is `longrun`. `run` and `finish` are staged as 100755, `type` as 100644. Key links:
`.revoke(` in `cli.py` and `.reconcile(` in `watch.py`. No image build, no container start, no verify script and no
Dockerfile change, as the plan requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RED commits carry interface stubs**

- **Found during:** Tasks 1 and 3 (RED)
- **Issue:** `get`, `list_entries`, `revoke`, `RESERVED_USERS`, `add(specs=)` and `app.watch` did not exist. Tests
  importing them would fail at collection (INVALID_RED).
- **Fix:** `b21cc81` and `90f589d` add signature stubs, so the targets fail on assertions. GREEN replaced all stubs.
  This is the same pattern as Plans 01 and 02.
- **Commits:** `b21cc81`, `90f589d`

**2. [Rule 1 - Bug] Lock-free reads could rename a valid file as corrupt**

- **Found during:** Task 1
- **Issue:** `load()` renames an unparsable file. A reader without the lock that read a corrupt version could rename
  the valid file a writer had just put in place. That would drop every user.
- **Fix:** `entries`, `get`, `list_entries` and `reconcile` read under the (reentrant) store lock.
- **Files:** `marketplace-repo-proxy/app/access.py`. **Commit:** `ef5558a`

**3. [Rule 2 - Missing critical] Path-safety hardening in revoke and reconcile (T-01-17, T-01-20)**

- **Found during:** Task 1
- **Issue:** a glob built from a hand-edited hash such as `*` would match every user's link. A symlink at the owner or
  repository level would let `chmod` and link creation follow it out of the access tree.
- **Fix:** `revoke` unlinks only HASH_RE-valid hashes, and only in real directories (no glob, no symlinked
  directories). `reconcile_tree` replaces a symlinked or non-directory level with a real 0711 directory, and a real
  directory at a link path with the link. The lock file gets an explicit `fchmod 0600`.
- **Tests:** `test_revoke_of_entry_with_glob_hash_unlinks_nothing_else`,
  `test_symlinked_directory_level_is_replaced_by_a_real_directory`
- **Commit:** `ef5558a`

**4. [Rule 1 - Bug] Watcher must not miss an edit made during its own reconcile**

- **Found during:** Task 3 (GREEN)
- **Issue:** recording the signature after the reconcile would swallow an edit that landed during it.
- **Fix:** `poll_once` records the signature taken before the reconcile. After a corrupt-file move, the next poll
  reconciles once more, which is harmless. An `OSError` during the reconcile is logged once per signature and retried
  at the next poll.
- **Commit:** `c2d2b6f`

### Interpretations within plan scope (not deviations)

- `hash_conflict` replaces Plan 01's `invalid_hash` for a client hash that another entry already uses. The behavior
  list requires this, and no existing test depended on the old code.
- Unconfigured-repository entries are logged at `debug` (`skipped: repository not configured`), because the watcher
  reconciles on every change and Plan 04's startup log counts them. Invalid repositories and hashes are logged at
  `warning`.
- `users list` prints `no users` when the store is empty. A hash that does not match HASH_RE is listed as `<invalid>`,
  never verbatim.
- `users url` for an unconfigured repository is `repository_unknown`, because the entry has no link and the URL could
  not work. `users revoke` falls back to the given repository string, so retired repositories can still be cleaned up.
- `watch.main` takes an optional `paths` argument for tests (additive; the production call is `main()`).

**Total deviations:** 4 auto-fixed (1 blocking, 2 bugs, 1 missing critical). **Impact:** no contract change. Every
name in the plan's artifacts list exists with the planned signature.

## Issues Encountered

None.

## Known Stubs

None. All RED stubs were replaced in the GREEN commits.

## Threat Flags

None. The watcher is a new process, but it has no new endpoint, no network access and no secret: it is the plan's own
T-01-17/T-01-23 mitigation. T-01-17 to T-01-23 are covered by the tests listed in `coverage` (D1-D6).

## Next Phase Readiness

- Plan 05 (wave 3) must prove `access-watch` in the built container: the process is present, its environment has no
  container secrets, and a hand edit of `/data/access.json` is revoked within 5 s.
- Phase 3 GUI and Phase 4 API: use `AccessStore(paths).add/get/list_entries/revoke(..., specs=options.repositories)`.
  The watcher also picks up writes from other processes.
- REQUIREMENTS.md: MRP-04 and MRP-05 are also declared by sibling plans. The shared-ID gate keeps them open until
  those plans finish.

## Self-Check: PASSED

- All 8 created and 3 modified key files exist on disk. Commits `b21cc81`, `ef5558a`, `08f16f4`, `82429b1`,
  `90f589d` and `c2d2b6f` are ancestors of HEAD.
