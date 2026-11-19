---
phase: 03-management-gui
reviewed: 2026-11-19T00:21:20Z
depth: standard
files_reviewed: 52
files_reviewed_list:
  - .github/workflows/lint.yml
  - internal/verify-marketplace-repo-proxy-gui.sh
  - Makefile
  - marketplace-repo-proxy/app/accessread.py
  - marketplace-repo-proxy/app/fetchlog.py
  - marketplace-repo-proxy/app/fetchsink.py
  - marketplace-repo-proxy/app/gui.py
  - marketplace-repo-proxy/app/lastfetch.py
  - marketplace-repo-proxy/app/web/__init__.py
  - marketplace-repo-proxy/app/web/registration.py
  - marketplace-repo-proxy/app/web/server.py
  - marketplace-repo-proxy/app/web/service.py
  - marketplace-repo-proxy/app/web/static/app.css
  - marketplace-repo-proxy/app/web/static/app.mjs
  - marketplace-repo-proxy/app/web/static/index.html
  - marketplace-repo-proxy/app/web/static/model.mjs
  - marketplace-repo-proxy/app/web/static/strings.de.mjs
  - marketplace-repo-proxy/app/web/static/strings.en.mjs
  - marketplace-repo-proxy/app/web/static/views/access.mjs
  - marketplace-repo-proxy/app/web/static/views/info.mjs
  - marketplace-repo-proxy/app/web/static/views/repositories.mjs
  - marketplace-repo-proxy/CHANGELOG.md
  - marketplace-repo-proxy/config.yaml
  - marketplace-repo-proxy/Dockerfile
  - marketplace-repo-proxy/DOCS.md
  - marketplace-repo-proxy/README.md
  - marketplace-repo-proxy/rootfs/etc/lighttpd/marketplace-repo-proxy.conf
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/dependencies.d/init
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/finish
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/run
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/fetchlog/type
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/gui/dependencies.d/init
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/gui/finish
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/gui/run
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/gui/type
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/fetchlog
  - marketplace-repo-proxy/rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/gui
  - marketplace-repo-proxy/tests/guihelpers.py
  - marketplace-repo-proxy/tests/js/a11y_audit.mjs
  - marketplace-repo-proxy/tests/js/access.test.mjs
  - marketplace-repo-proxy/tests/js/fakedom.mjs
  - marketplace-repo-proxy/tests/js/i18n.test.mjs
  - marketplace-repo-proxy/tests/js/info.test.mjs
  - marketplace-repo-proxy/tests/js/model.test.mjs
  - marketplace-repo-proxy/tests/js/repositories.test.mjs
  - marketplace-repo-proxy/tests/test_accessread.py
  - marketplace-repo-proxy/tests/test_fetchlog.py
  - marketplace-repo-proxy/tests/test_fetchsink.py
  - marketplace-repo-proxy/tests/test_gui_manifest.py
  - marketplace-repo-proxy/tests/test_gui_server.py
  - marketplace-repo-proxy/tests/test_gui_service.py
  - marketplace-repo-proxy/tests/test_js.py
findings:
  critical: 0
  warning: 2
  info: 8
  total: 10
  necessity: 1
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-11-19T00:21:20Z
**Depth:** standard
**Files Reviewed:** 52
**Status:** issues_found

## Summary

I reviewed the Phase 3 management GUI at standard depth. That covers the GUI server and service layer, the
registration reader, the fetch sink (forwarder, root receiver, last-fetch store), the Preact views and strings, the s6
services, the lighttpd and Dockerfile and config diffs, CI and Makefile wiring, the docs diffs, the GUI verify script
and the tests. I used the vendored admin-ui copies only to understand the API: the router's `unquote` of path params,
the body parsing, the ingress gate before static files and the order of the error mappers. I report no findings in
them. Both suites pass locally (node: 58 tests; pytest: 513 tests). Passing tests were not taken as evidence of
correctness.

The focus areas hold up well:

- Every route and every static asset passes the ingress gate first. No route is public.
- I found no path where a hash reaches a log line or an API response other than the add, rotate and URLs responses.
  The GUI's stdout and stderr go through `MaskedStream`. `fetchlog` logs only exception type names. The forwarder is
  silent.
- The privilege split matches the design: forwarder as `lighttpd`, receiver as root, socket `root:lighttpd 0620`. The
  verify script proves it in the container.
- `last-fetch.json` uses atomic replace and has a single writer.
- The views render text nodes only.

Both warnings are about the rotate and add write paths under the store lock. I reproduced both with small scripts
against the real `AccessStore`:

1. The rotate rollback reports a wrong error after a post-write failure: the rotation is persisted, but the client gets
   409 `user_exists`.
2. The "pre-read then write" guard does not close the WR-04 window. A load failure after the guard still wipes
   `access.json` down to one user, which contradicts DOCS.md:141.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Rotate rollback hides a post-write failure and returns 409 user_exists for a rotation that was persisted

**File:** `marketplace-repo-proxy/app/web/service.py:339-345`

**Issue:** The rollback assumes that `store.add` either succeeds or fails before it writes. But `AccessStore.add`
(access.py:196-199) first replaces `access.json` atomically and then runs `reconcile_tree`, which can raise `OSError`
(symlink creation, `os.replace`, `rmtree`). When that happens:

- The new entry with the new hash is already in the file.
- The `except` branch calls `store.add(..., hash_=old_hash)`. It raises `AccessError("user_exists")` from inside the
  handler, so the original `OSError` survives only as `__context__`.
- The client gets HTTP 409 with the text "A user with this label already exists for this repository".
- The old URL is dead (revoked), the rotation is persisted, and the new URLs are never shown.
- The symlink tree may lack the new link until `access-watch` reconciles.

The docstring promises "When `add` fails after the revoke, the old hash is re-added and the error re-raised". That is
false for this case.

`test_rotate_restores_the_old_hash_when_add_fails` only covers a failure on entry to `add`, before the write.

Reproduced by patching `app.access.reconcile_tree` to raise `OSError` on its second call: `rotate_user` raised
`AccessError user_exists` with an `OSError` context, and the stored hash had changed.

**Fix:** Before you roll back, check whether the write already happened, and always re-raise the original error:

```python
store.revoke(spec.slug, user, specs=specs)
try:
    new = store.add(spec.slug, user, source=source, specs=specs)
except Exception:
    current = next((e for e in read_entries_safe(store) if _matches(e, spec.key, user)), None)
    if current is None and isinstance(old_hash, str) and HASH_RE.fullmatch(old_hash):
        try:
            store.add(spec.slug, user, source=source, hash_=old_hash, specs=specs)
        except Exception:
            LOG.error("rotate rollback failed for %s of %s", _label(user), spec.slug)
    raise
```

Add a test where `reconcile_tree` fails after the write.

### WR-02: The pre-read guard does not prevent `AccessStore.load()` from moving `access.json` aside and writing a one-user file

**File:** `marketplace-repo-proxy/app/web/service.py:274-276, 307-314, 329-341` (claim in `marketplace-repo-proxy/DOCS.md:141`)

**Issue:** `add_user`, `revoke_user` and `rotate_user` first call `read_entries_safe(store)` under the lock. The service
docstring says that this way "an unreadable file is refused instead of replaced by a file holding only the new user".
But each write then calls `AccessStore.add` or `AccessStore.revoke`, which re-read the file through `load()`. On any
`OSError` or `ValueError`, `load()` renames `access.json` to `access.json.corrupt` and returns an empty document. Two
cases get past the guard:

- A transient read error between the guard and `load()`.
- A non-atomic hand edit (for example `nano` truncating and rewriting in place) that lands in that window. Hand edits
  take no lock, and DOCS.md invites them.

In both cases, `add` writes an `access.json` that holds only the new user, and every other user loses access.

`rotate_user` makes it worse. It ignores the `False` return of `store.revoke` (line 339), so it carries on into `add`
on the emptied store. Rotate also runs `load()` twice: once in `revoke`, once in `add`.

Reproduced: three users, then `add_user("dave")` with one injected `OSError` in `app.access.read_json`. Result:
`access.json` held only `['dave']`, and `access.json.corrupt` had been created.

The window is narrow, and the old data survives in `.corrupt`, so this is a WARNING rather than a BLOCKER. But it is
exactly the WR-04 risk that this phase claims to close for GUI writes, and DOCS.md:141 states "nothing is changed" as a
guarantee.

**Fix:** Keep `app/access.py` unchanged (D-10). In the GUI, use a store subclass whose `load()` fails closed without
renaming, and check the return value of `revoke`:

```python
class _GuiStore(AccessStore):
    def load(self) -> dict[str, Any]:
        try:
            doc = read_json(self.paths.access_file)
        except (OSError, ValueError):
            raise AccessUnavailable() from None
        if doc is None:
            return {"schema": SCHEMA, "entries": []}
        if not _valid_shape(doc) or doc["schema"] > SCHEMA:
            raise AccessUnavailable()
        return doc

def _store(self) -> AccessStore:
    return _GuiStore(self.paths)
...
if not store.revoke(spec.slug, user, specs=specs):
    raise AccessError("user_unknown")
```

Alternatively, narrow the DOCS.md:141 claim and record the residual risk under the Phase 1 WR-04 deferral.

## Info

### IN-01: fetchlog stops recording fetches after one transient access.json read failure until the file changes

**File:** `marketplace-repo-proxy/app/fetchlog.py:129-141`

**Issue:** `_refresh` stores the signature before it reads. When `read_entries_safe` raises `AccessUnavailable`, the
map is cleared and `_seen` keeps the signature. As long as `access.json` stays unchanged, no lookup retries the read.
So a single transient `OSError` disables last-fetch recording until a user is added or revoked or `fetchlog`
restarts, which can be days. The effect is limited to the displayed "last fetch", but it fails silently: one error
line, then nothing.

**Fix:** In the error branch, retry an unchanged signature after a back-off (for example 60 s). Keep the "one error
line per signature" rule for the log.

### IN-02: Fresh URLs of a user stay on screen after that user is revoked

**File:** `marketplace-repo-proxy/app/web/static/views/access.mjs:389-393`

**Issue:** `onRevoked` closes the dialog and reloads the list but leaves the `fresh` state alone. After "Add user" or
"Rotate" followed by "Revoke" of the same user, the card keeps showing "New store URLs for {user}" with copy fields
holding a dead URL.

**Fix:** In `onRevoked`, add `if (fresh && fresh.repository === ask.repository && fresh.user === ask.user) setFresh(null);`.

### IN-03: Rotate is offered for entries with a missing or unknown `source` but always fails with a misleading error

**File:** `marketplace-repo-proxy/app/web/service.py:335-337`, `marketplace-repo-proxy/app/web/static/views/access.mjs:161-173`

**Issue:** For a hand-edited entry without a valid `source`, the view shows the "Unknown source" badge and a Rotate
button (`RowActions` hides it only for `protected`). The server refuses with `invalid_user`, which the page shows as
"The user label is not valid", although the label is valid.

**Fix:** Either hide Rotate when `!isSource(entry.source)` or return a dedicated code (for example `invalid_source`)
with its own string. Another option is to rotate with the source `gui`.

### IN-04: Add-form input ids can collide between repositories

**File:** `marketplace-repo-proxy/app/web/static/views/access.mjs:187`

**Issue:** `access-add-${owner}-${repo}` gives the same id for `a-b/c` and `a/b-c`, because both segments may contain
`-`. That makes duplicate ids, so label `for` and `aria-describedby` point to the wrong input. The a11y test checks
uniqueness with one repository only.

**Fix:** Use a separator that cannot appear in a segment, for example `access-add-${owner}--${repo}` (`--` is still
ambiguous). Better: use the row index or an encoded form such as `access-add-${owner}~${repo}`.

### IN-05: The forwarder silences only Python-level streams, not file descriptors 1 and 2

**File:** `marketplace-repo-proxy/app/fetchsink.py:83-85`

**Issue:** `sys.stdout` and `sys.stderr` are replaced, but fds 1 and 2 still point to lighttpd's stderr, which is the
add-on log. Interpreter-level output (fatal errors, `faulthandler`, C-level warnings) bypasses the replacement. I found
no current path that would print a record. This is defense in depth for the "never prints anything" claim.

**Fix:** After opening devnull, add `os.dup2(devnull.fileno(), 1); os.dup2(devnull.fileno(), 2)`.

### IN-06: Node tests run twice in CI

**File:** `.github/workflows/lint.yml:321-325`, `marketplace-repo-proxy/tests/test_js.py:15-21`

**Issue:** The new "GUI unit tests (node)" step runs `node --test`. The pytest step then runs `test_js.py`, which runs
the same node suite again, because Node is now installed in the job.

**Fix:** Drop one of the two. For example, set an environment variable in CI that `test_js.py` skips on, or remove the
separate node step.

### IN-07: Forced `process.exit` in `test.after` hides leaked timers or handles

**File:** `marketplace-repo-proxy/tests/js/access.test.mjs:368` (same in `repositories.test.mjs:364`, `info.test.mjs:126`, `i18n.test.mjs:170`)

**Issue:** The unref'd 300 ms `process.exit` ends the test process even when a poll interval or a pending promise
leaks. A view that fails to clean up `usePoll` on unmount would pass silently.

**Fix:** Unmount every rendered tree (most tests already call `render(null, root)`) and let the process exit on its
own. If a forced exit is still needed, fail when it triggers (`process.exitCode ||= 1` plus a message).

### IN-08: Impossible-state guard: `request_sync` creates the run directory that `init` already guarantees

**File:** `marketplace-repo-proxy/app/web/service.py:360-362`

**Category:** necessity

**Issue:** The `gui` longrun depends on `init` (`rootfs/etc/s6-overlay/s6-rc.d/gui/dependencies.d/init`), and `init`
creates `/run/marketplace-repo-proxy` with mode 0700 (`app/init.py:94-95`). In production the directory exists before
the GUI starts. Whether anything removes it at runtime is a judgment call, so this is Info. Tests with `Paths.under`
may rely on the branch.

**Fix:** Keep it if tests need it. Otherwise drop the branch and let `atomic_write_json` fail with `OSError`, which is
already mapped to `internal_error`.

---

_Reviewed: 2026-11-19T00:21:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
