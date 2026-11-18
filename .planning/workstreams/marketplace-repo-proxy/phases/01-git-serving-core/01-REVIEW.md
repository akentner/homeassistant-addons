---
phase: 01-git-serving-core
reviewed: 2026-11-18T14:36:26Z
depth: standard
files_reviewed: 39
files_reviewed_list:
  - .github/workflows/lint.yml
  - internal/verify-marketplace-repo-proxy.sh
  - marketplace-repo-proxy/Dockerfile
  - marketplace-repo-proxy/app/__init__.py
  - marketplace-repo-proxy/app/access.py
  - marketplace-repo-proxy/app/cli.py
  - marketplace-repo-proxy/app/gitops.py
  - marketplace-repo-proxy/app/init.py
  - marketplace-repo-proxy/app/jsonio.py
  - marketplace-repo-proxy/app/logsetup.py
  - marketplace-repo-proxy/app/options.py
  - marketplace-repo-proxy/app/paths.py
  - marketplace-repo-proxy/app/status.py
  - marketplace-repo-proxy/app/sync.py
  - marketplace-repo-proxy/app/urls.py
  - marketplace-repo-proxy/app/watch.py
  - marketplace-repo-proxy/config.yaml
  - marketplace-repo-proxy/rootfs/etc/lighttpd/marketplace-repo-proxy.conf
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/access-watch/run
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/access-watch/finish
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/init/up
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/lighttpd/run
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/lighttpd/finish
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/sync/run
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/sync/finish
  - marketplace-repo-proxy/rootfs/usr/local/bin/mrp
  - marketplace-repo-proxy/run.sh
  - marketplace-repo-proxy/tests/conftest.py
  - marketplace-repo-proxy/tests/upstream.py
  - marketplace-repo-proxy/tests/test_access.py
  - marketplace-repo-proxy/tests/test_cli.py
  - marketplace-repo-proxy/tests/test_gitops.py
  - marketplace-repo-proxy/tests/test_init.py
  - marketplace-repo-proxy/tests/test_logsetup.py
  - marketplace-repo-proxy/tests/test_options.py
  - marketplace-repo-proxy/tests/test_status.py
  - marketplace-repo-proxy/tests/test_sync.py
  - marketplace-repo-proxy/tests/test_urls.py
  - marketplace-repo-proxy/tests/test_watch.py
findings:
  critical: 1
  warning: 5
  info: 7
  total: 13
  necessity: 0
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-11-18T14:36:26Z
**Depth:** standard
**Files Reviewed:** 39
**Status:** issues_found

## Summary

Reviewed the marketplace-repo-proxy add-on at standard depth: Python app modules, s6 service scripts, lighttpd routing,
Dockerfile, config.yaml, the Docker verify script, the CI test job and the pytest suite. The suite passes
(207 passed, run locally with `uv run --with pytest --with pyyaml`). Docker and the verify script were not run.

The core security design holds up:

- The PAT reaches only the env dict of the sync service's git children. It never appears in argv, remote URLs or
  repository config.
- lighttpd and access-watch run without `with-contenv`.
- The lighttpd allow-list admits only `{hash}/info/refs` and `{hash}/git-upload-pack`. Behind it, git-http-backend
  refuses receive-pack and dumb HTTP.
- Hash links are made with an atomic `symlink` + `rename`. No log path writes a full hash.
- Public-repo hygiene is clean: only `example.*` placeholders, the public repository URL and the well-known Supervisor
  network addresses in SPIKE.md.

Defects found, all proven by running code:

1. **Branch-change bug (BLOCKER).** `configure_repo` moves the bare repository's `HEAD` and refspec *before* the fetch
   succeeds. A typo in the `branch` option therefore breaks the served mirror, which contradicts DOCS.md:157 ("the
   mirror is only replaced by a successful fetch").
2. **Unadvertised objects can be fetched (WARNING).** Protocol v2 upload-pack lets any URL holder fetch an
   unadvertised object by SHA. That includes objects of pruned branches and force-pushed-away history, which breaks the
   "only this one branch is served" guarantee.
3. **Validators accept a trailing newline (WARNING).** The `^...$` validators (user label, hash, owner) use
   `re.match`, so a trailing `\n` passes.
4. **`public_url` userinfo is logged (WARNING).** Credentials in `public_url` reach the add-on log unmasked.
5. **`access.json` is renamed away too readily (WARNING).** The store renames the file aside on any read failure,
   including transient `OSError`s and partial in-place writes, and overwrites an earlier `.corrupt` copy.
6. **Revocations are not durable (WARNING).** Atomic writes do not fsync the directory, so a revocation may not
   survive a power loss.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Branch change rewrites HEAD and refspec before the fetch succeeds, breaking the served mirror

**File:** `marketplace-repo-proxy/app/gitops.py:320-325` (with `configure_repo` at `136-152`)
**Issue:** For an existing bare repository, `ensure_and_fetch` calls `configure_repo(final, url, branch)` first. That
call rewrites `remote.origin.fetch` and runs `git symbolic-ref HEAD refs/heads/{branch}`. Only then does it fetch. If
the fetch fails, the served repository keeps the old `refs/heads/<old>` ref, but `HEAD` now points at a ref that does
not exist. Triggers include a mistyped `branch` option, a branch not yet pushed upstream, or an expired token at the
same moment. Clones from the Supervisor then get "remote HEAD refers to nonexistent ref, unable to checkout" and an
empty working tree.

`status.json` still shows the old `head` and `addons`, and DOCS.md:157 promises: "the mirror is only replaced by a
successful fetch". Reproduced with the test fixtures: a sync on `main`, then a sync with `RepoSpec("o", "r", "stabel")`,
leaves `{'refs/heads/main': '9dbe…', 'HEAD': 'refs/heads/stabel'}`. No test covers a failed fetch after a branch change.
`test_branch_change_moves_head_and_drops_the_old_ref` only covers the success path.

**Fix:** Fetch the new branch with an explicit refspec first. Change `HEAD` and the stored refspec only after the fetch
succeeds:

```python
def ensure_and_fetch(paths, spec, url, branch, env):
    final = paths.repo_dir(spec.owner, spec.name)
    if final.exists():
        refspec = f"+refs/heads/{branch}:refs/heads/{branch}"
        result = run_git([*_fetch_args(final), "fetch", "--prune", "--no-tags", url, refspec], env)
        if result.returncode == 0:
            configure_repo(final, url, branch)  # HEAD/refspec move only after a good fetch
        return result
    ...
```

Alternatively, snapshot `HEAD` and `remote.origin.fetch` before `configure_repo` and restore them when the fetch fails.
Add a regression test that syncs `main`, then syncs a missing branch, and asserts that `HEAD` still resolves.

## Warnings

### WR-01: Protocol v2 serves unadvertised objects by SHA, defeating "only this one branch is served"

**File:** `marketplace-repo-proxy/app/gitops.py:286-298`, `marketplace-repo-proxy/app/sync.py:93-96`
**Issue:** `prune_foreign_refs` deletes foreign refs but leaves their objects in the pack. Force-pushed-away upstream
history also stays, because `fetch --prune` with `+` only moves the ref. Git's protocol v2 `fetch` command accepts any
`want <oid>` that exists in the repository. It does not check that the oid is advertised, and
`uploadpack.allowAnySHA1InWant=false` has no effect there.

Verified locally with git 2.56.1: after `update-ref -d refs/heads/secret`, a `git -c protocol.version=2 fetch
file://…/srv.git <secret-sha>` succeeds. git-http-backend runs the same `upload-pack --stateless-rpc` code. Any holder
of a store URL who knows a SHA can therefore download content from:

- a branch that was served before a branch switch, or
- history the upstream deliberately rewrote away, such as a removed leaked credential.

`run_maintenance` (`maintenance run --auto`) does not reliably prune unreachable objects, and the default prune expiry
is 2 weeks.

**Fix:** After `prune_foreign_refs` removed refs, or after a non-fast-forward update, drop unreachable objects right
away. Run this with the local environment:

```python
run_git([*git_dir, "-c", "gc.reflogExpire=now", "-c", "gc.reflogExpireUnreachable=now",
         "gc", "--prune=now", "--quiet"], local_env())
```

Alternatively, run `repack -a -d` followed by `prune --expire=now`. Detect the non-fast-forward update by comparing
the old and new ref oids with `merge-base --is-ancestor`. Then document the remaining guarantee precisely.

### WR-02: `^…$` validators accept a trailing newline (user label, hash, owner)

**File:** `marketplace-repo-proxy/app/access.py:29-30,168,174,280`, `marketplace-repo-proxy/app/options.py:15-17,64`
**Issue:** In Python, `re.match` with `$` also matches before a final `\n`. Verified:

- `USER_RE.match("alice\n")`, `HASH_RE.match("a"*32 + "\n")` and `OWNER_RE.match("evil\n")` are all truthy.
- `parse_repository("evil\n/repo")` returns `('evil\n', 'repo')`.

The consequences:

- A user label with a newline can be stored through `AccessStore.add`. It is printed verbatim in the startup log at
  `init.py:69` (log-line forging) and in `revoked …`.
- A hand-edited hash ending in `\n` passes `reconcile_tree` and becomes a link name containing a newline.
- `parse_repository` is the add-on's own re-validation, which `options.py:1` calls strict. It lets a newline-bearing
  owner into filesystem paths and the remote URL.

The Supervisor schema currently blocks the owner case, but `AccessStore` is explicitly the writer API for the Phase 3/4
GUI and API. Those phases bring untrusted HTTP input, and the regexes are the trust boundary.

**Fix:** Use `fullmatch` (or `\Z`) everywhere these patterns guard input:

```python
HASH_RE = re.compile(r"[0-9a-f]{32}")
USER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
...
if not isinstance(user, str) or not USER_RE.fullmatch(user): ...
```

Apply the same to `OWNER_RE`, `REPO_RE` and `BRANCH_RE` in `options.py`, and to the `HASH_RE.match` calls in `cli.py`
and `init.py`. Add tests with trailing `\n` inputs.

### WR-03: Credentials in `public_url` are written unmasked to the add-on log

**File:** `marketplace-repo-proxy/app/options.py:86-95`, `marketplace-repo-proxy/app/init.py:70-71`
**Issue:** `_public_url` accepts any http(s) URL with a host, including userinfo:
`_public_url("https://user:secret@proxy.example.invalid", [])` returns it unchanged. The Supervisor's `url?` schema
accepts it too. A reverse proxy with basic auth in front of the add-on makes such a value plausible. `log_startup` then
logs `public {options.public_url}/repo/…` at INFO level for every user. `masked_store_url` masks only the hash, not the
base, so the password lands in the add-on log. `resolve_upstream` rejects userinfo for exactly this reason
(`gitops.py:68-69`), but `public_url` has no equivalent check.

**Fix:** Reject userinfo, query and fragment in `_public_url`, mirroring `resolve_upstream`:

```python
parts = urlsplit(url)
if (parts.scheme in ("http", "https") and parts.hostname and "@" not in parts.netloc
        and not parts.query and not parts.fragment):
    return url
```

### WR-04: `access.json` is renamed to `.corrupt` on transient read errors and partial writes; an earlier `.corrupt` is overwritten

**File:** `marketplace-repo-proxy/app/access.py:106-125`, `marketplace-repo-proxy/app/watch.py:51-52`
**Issue:** `load()` maps every `OSError` from `read_json` to "corrupt", not only invalid JSON. That covers EIO, EMFILE,
ENOMEM and an `IsADirectoryError`. It then `os.replace`s the file to `access.json.corrupt`.

`load()` also runs from the read-only watcher every time the file signature changes. DOCS.md:207 asks for atomic hand
edits, but in-place editors and shell redirection (`> access.json`) truncate first. The watcher can then read an empty
or half-written file, and two things happen:

- The live file is renamed away while the editor's open descriptor keeps writing into `access.json.corrupt`, so the
  operator's edit ends up in the moved file.
- `os.replace` overwrites any earlier `access.json.corrupt`. A second event destroys the only copy of the earlier user
  list.

The next `mrp users add` then creates a fresh file holding only the new entry. Every existing URL stops working, and the
data survives only in a file that the next corruption event overwrites.

**Fix:**

- Treat only `ValueError` (and `UnicodeDecodeError`) as corrupt. Let `OSError` propagate. The watcher already retries
  on `OSError`.
- Require two consecutive reads with the same bad content, or a signature unchanged for over 1 s, before moving the
  file aside.
- Never overwrite an existing `.corrupt` file:

```python
target = path.with_name(f"{path.name}.corrupt.{utc_timestamp().replace(':', '')}")
os.replace(path, target)
```

### WR-05: Atomic JSON writes do not fsync the directory, so a revocation can be lost on power failure

**File:** `marketplace-repo-proxy/app/jsonio.py:12-29`
**Issue:** `atomic_write_json` fsyncs the temp file but not `path.parent` after `os.replace`. On ext4 (HA OS) the rename
is only durable at the next journal commit, about 5 s by default. A `mrp users revoke`, which `revoke()` calls via this
function, followed by a power loss in that window brings the revoked entry back. The next boot's `init` then re-links
the revoked user. For an access-control file, revocations need to be durable.

**Fix:**

```python
os.replace(tmp, path)
dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(dir_fd)
finally:
    os.close(dir_fd)
```

## Info

### IN-01: Failed upstream-default probes overwrite the known branch with `null` in status.json

**File:** `marketplace-repo-proxy/app/sync.py:79-83`, `marketplace-repo-proxy/app/status.py:141-145`
**Issue:** `Outcome(*classify(probe))` and `Outcome("not_found", NO_DEFAULT_BRANCH_MESSAGE)` carry `branch=None`.
`record()` writes that `None` over the previously known upstream default branch. After every `auth_failed` probe, the
GUI therefore shows no branch, although the mirror still serves one.
**Fix:** Keep `entry["branch"]` when `branch is None and branch_source == "upstream_default"`, or pass the last known
branch from the previous status entry.

### IN-02: `mrp users add` writes the entry, then can die with a traceback before printing the URL

**File:** `marketplace-repo-proxy/app/access.py:196-199`, `marketplace-repo-proxy/app/cli.py:182-187`
**Issue:** `add()` persists `access.json` before `reconcile_tree`. An `OSError` from the tree (for example during
`symlink_to` or `os.replace`) is not caught in `cli.main`, so the operator gets a Python traceback, no URL and exit 1.
The user still exists, so a retry fails with `user_exists`. The documented error contract is `error: <code>`.
**Fix:** Catch `OSError` in `cli.main` and print `error: io_error`. Optionally tell the operator to run `mrp users url`.

### IN-03: `github_token` is not stripped

**File:** `marketplace-repo-proxy/app/options.py:130,136`
**Issue:** A PAT pasted with trailing whitespace or a newline goes verbatim into the `Authorization` header. The result
is a confusing `auth_failed`, or a header containing a raw newline that curl may reject.
**Fix:** `github_token=token.strip() if isinstance(token, str) else ""`.

### IN-04: `sync_interval` has no upper bound

**File:** `marketplace-repo-proxy/app/options.py:131-137`, `marketplace-repo-proxy/config.yaml:26`
**Issue:** `int(5,)` and `max(MIN_INTERVAL, interval)` accept any huge value. `end_cycle` computes
`utc_timestamp(wall + interval*60)`, and `time.gmtime` raises `OverflowError`/`OSError` for absurd values. That exception
escapes `run_cycle_once`'s `finally`, so s6 restarts sync every ~3 s, and each restart runs a full startup fetch.
**Fix:** Clamp the value, for example `min(interval, 7 * 24 * 60)`, and use `int(5,10080)` in the schema.

### IN-05: Dead code: `gitops.default_branch` and `AccessStore.entries`

**File:** `marketplace-repo-proxy/app/gitops.py:131-133`, `marketplace-repo-proxy/app/access.py:127-129`
**Issue:** Neither function is called from `app/` or `tests/`; `sync.py` uses `ls_remote_head` directly.
`entries()` returns shallow references into the loaded document, unlike `list_entries()`, which deep-copies. A future
caller would get mutable internals.
**Fix:** Remove both, or make `entries()` delegate to `list_entries()`.

### IN-06: `init.py` docstring overstates the failure policy

**File:** `marketplace-repo-proxy/app/init.py:4-6,92-109`
**Issue:** The docstring says that only invalid options and an unknown schema are fatal. In fact, `chmod`/`mkdir`
of `data_dir`, `run_dir`, `repos_root` and `access_root`, and `gitconfig_file.parent.mkdir`, all run outside any
`try`. Any `OSError` there ends init with a traceback, and the container halts because the base image sets
`S6_BEHAVIOUR_IF_STAGE2_FAILS=2`.
**Fix:** Wrap the directory setup in `try/except OSError` and log the type only, or correct the docstring to say these
failures are fatal.

### IN-07: Leftover temp files with hashes and orphaned bare repositories are never cleaned up

**File:** `marketplace-repo-proxy/app/jsonio.py:15`, `marketplace-repo-proxy/app/gitops.py:306-317`
**Issue:**

- A crash between `mkstemp` and `os.replace` leaves `/data/.access.json.*.tmp` files with full hashes. Nothing removes
  them, although they are mode 0600 and never served.
- Bare repositories of repositories removed from `repositories`, or renamed only by case, stay under
  `/srv/git/repos` indefinitely with their private content.
- Empty `access/{owner}/{repo}` directories are also never pruned.

None of these are served, but they outlive the configuration.
**Fix:**

- In `init`, delete `/data/.access.json.*.tmp` and `/data/.status.json.*.tmp`.
- Optionally log, or remove, bare repositories that no configured repository references.

---

_Reviewed: 2026-11-18T14:36:26Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
