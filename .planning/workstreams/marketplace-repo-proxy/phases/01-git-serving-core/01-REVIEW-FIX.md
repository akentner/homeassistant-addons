---
phase: 01-git-serving-core
fixed_at: 2026-11-18T16:04:39Z
review_path: .planning/workstreams/marketplace-repo-proxy/phases/01-git-serving-core/01-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 4
skipped: 2
status: partial
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-11-18T16:04:39Z
**Source review:** .planning/workstreams/marketplace-repo-proxy/phases/01-git-serving-core/01-REVIEW.md
**Iteration:** 1

**Summary:**

- Findings in scope: 6 (CR-01, WR-01..WR-05; fix scope `critical_warning`)
- Fixed: 4 (CR-01, WR-02, WR-03, WR-05)
- Skipped: 2 (WR-01, WR-04: deferred by user decision 2026-11-18)
- Out of scope: IN-01..IN-07 (Info). They are not fixed and stay open in REVIEW.md. They are also deferred by the user
  decision of 2026-11-18.

**Verification:** Every fix was checked by re-reading the file, the regression tests were run against the pre-fix code
(they fail there) and the full suite was run after each commit:
`uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q`.
The suite went from 207 to 219 passed. The tests ran in the branch worktree `feat/marketplace-repo-proxy-v1`. No extra
review-fix worktree was created, as the orchestrator instructed, so the results can be reproduced from this checkout.
Docker and `internal/verify-marketplace-repo-proxy.sh` were not run; the orchestrator runs them.

## Fixed Issues

### CR-01: Branch change rewrites HEAD and refspec before the fetch succeeds, breaking the served mirror

**Files modified:** `marketplace-repo-proxy/app/gitops.py`, `marketplace-repo-proxy/tests/test_sync.py`,
`marketplace-repo-proxy/DOCS.md`
**Commit:** 3c461b6
**Status:** fixed: requires human verification (logic change in the fetch/configure order)
**Applied fix:**

- `gitops.fetch` now takes `url` and `branch` and fetches with an explicit refspec,
  `+refs/heads/{branch}:refs/heads/{branch}`. It no longer reads the refspec from `origin`, so `--prune` acts only
  inside that one refspec.
- For an existing repository, `ensure_and_fetch` fetches first and calls `configure_repo` only after the fetch
  succeeds. `configure_repo` moves HEAD and the stored refspec. A failed fetch therefore leaves HEAD, the refspec and
  the old ref untouched.
- New repositories are unchanged: they are still built in a temp dir and renamed after a good fetch.
- `status.json` keeps `head`, `addons` and `last_success` from the old branch. It reports the failure with the
  configured (new) `branch` and `not_found`.
- DOCS.md got one sentence: the mirror switches branches only after the new branch has been fetched.
- Regression test `test_failed_branch_change_keeps_serving_the_old_branch` uses only the local fixtures. It syncs
  `main`, then the missing branch `stabel`, and asserts:
    - status, head, addons and last_success as above;
    - HEAD is still `refs/heads/main` and resolves to the same commit;
    - only `refs/heads/main` exists;
    - the refspec is unchanged;
    - a `git clone` of the bare repository has the old `repository.yaml` and add-on.

  The test fails on the pre-fix code.

### WR-02: `^…$` validators accept a trailing newline (user label, hash, owner)

**Files modified:** `marketplace-repo-proxy/app/access.py`, `marketplace-repo-proxy/app/cli.py`,
`marketplace-repo-proxy/app/init.py`, `marketplace-repo-proxy/app/options.py`, `marketplace-repo-proxy/tests/test_access.py`,
`marketplace-repo-proxy/tests/test_options.py`
**Commit:** 5837d7a
**Applied fix:**

- Every `OWNER_RE`/`REPO_RE`/`BRANCH_RE`/`HASH_RE`/`USER_RE` `.match()` call in `app/` is now `.fullmatch()`. That is 12
  call sites.
- The patterns themselves are unchanged, so the regex documented in DOCS.md still describes them.
- New tests:
    - `test_trailing_newline_in_user_or_hash_is_invalid`: `add` rejects `invalid_user` and `invalid_hash`.
    - `test_reconcile_skips_a_hash_with_a_trailing_newline`: no link is made, and the log shows `<invalid>`, not the raw
      label.
    - `test_validators_reject_a_trailing_newline`: covers `_valid_branch`.
    - A new `"evil\n/repo"` case in `test_invalid_repository_is_rejected`.

### WR-03: Credentials in `public_url` are written unmasked to the add-on log

**Files modified:** `marketplace-repo-proxy/app/options.py`, `marketplace-repo-proxy/tests/test_options.py`,
`marketplace-repo-proxy/tests/test_init.py`, `marketplace-repo-proxy/DOCS.md`
**Commit:** 391fbea
**Applied fix:**

- `_public_url` now rejects these inputs, mirroring `resolve_upstream`:
    - userinfo (`@` in the netloc);
    - a query, or a `?` anywhere;
    - a fragment, or a `#` anywhere.
- The rejection message is the constant `PUBLIC_URL_REJECTED`. It never contains the value.
- DOCS.md got one sentence on this.
- New tests:
    - four rejection cases in `test_public_url_is_normalised_or_rejected`;
    - `test_credentials_in_public_url_never_reach_the_log`: runs `init` with a `user:secret@` public URL and asserts
      that neither part reaches the log, that no `| public` line is written and that the warning is logged.

### WR-05: Atomic JSON writes do not fsync the directory, so a revocation can be lost on power failure

**Files modified:** `marketplace-repo-proxy/app/jsonio.py`, `marketplace-repo-proxy/tests/test_status.py`
**Commit:** fb64173
**Applied fix:**

- `atomic_write_json` calls `_fsync_dir(path.parent)` after `os.replace`. It opens the directory with
  `O_RDONLY | O_DIRECTORY` and fsyncs it.
- This is best effort. An `OSError` on open or fsync is ignored, because the new file is already in place and the write
  must not be reported as failed. This covers platforms and filesystems that refuse a directory fsync.
- New tests:
    - `test_atomic_write_fsyncs_the_directory_after_the_rename`: the file is fsynced, then the directory. This test
      fails on the pre-fix code.
    - `test_atomic_write_survives_a_platform_that_refuses_directory_fsync`: the directory fsync raises `EINVAL`, the
      write still succeeds and no temp file is left.
- DOCS.md is unchanged; it does not describe durability.

## Skipped Issues

### WR-01: Protocol v2 serves unadvertised objects by SHA, defeating "only this one branch is served"

**File:** `marketplace-repo-proxy/app/gitops.py:286-298`, `marketplace-repo-proxy/app/sync.py:93-96`
**Reason:** deferred: user decision 2026-11-18
**Original issue:** After refs are pruned, their objects stay in the pack. So do objects of history that was
force-pushed away. Protocol v2 `fetch` serves any existing object by SHA, so any URL holder who knows a SHA can
download them. Suggested fix: run `gc --prune=now` with the reflog expired after pruning or after a non-fast-forward
update.

### WR-04: `access.json` is renamed to `.corrupt` on transient read errors and partial writes; an earlier `.corrupt` is overwritten

**File:** `marketplace-repo-proxy/app/access.py:106-125`, `marketplace-repo-proxy/app/watch.py:51-52`
**Reason:** deferred: user decision 2026-11-18
**Original issue:** `load()` treats every `OSError` as corruption and moves the file aside. The watcher can do this
in the middle of a non-atomic hand edit. Each move also overwrites the earlier `access.json.corrupt`, so a second
event destroys the only copy of an earlier user list. Suggested fix:

- treat only `ValueError` and `UnicodeDecodeError` as corruption;
- debounce before moving the file aside;
- add a timestamp to the `.corrupt` name.

## Observation (not fixed, out of scope)

`_public_url` and `resolve_upstream` call `urlsplit(...)`, and `_public_url` then reads `.hostname`. Both can raise
`ValueError` on malformed input such as `http://[x`. `resolve_upstream` catches this; `_public_url` does not. This was
not part of any finding and was left unchanged, as the user's scope decision requires. A follow-up could check it.

---

_Fixed: 2026-11-18T16:04:39Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
