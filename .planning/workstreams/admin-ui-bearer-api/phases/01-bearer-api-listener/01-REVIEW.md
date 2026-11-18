---
phase: 01-bearer-api-listener
reviewed: 2026-11-18T14:19:32Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - admin-ui/app/web/skeleton/__init__.py
  - admin-ui/app/web/skeleton/api.py
  - admin-ui/app/web/skeleton/server.py
  - admin-ui/app/web/skeleton/tokens.py
  - admin-ui/app/web/static/lib/VERSION
  - admin-ui/app/web/static/strings.de.mjs
  - admin-ui/app/web/static/strings.en.mjs
  - admin-ui/app/web/static/views/rules.mjs
  - admin-ui/tests/js/rules_view.test.mjs
  - admin-ui/tests/test_addon_scaffold.py
  - admin-ui/tests/test_api_server.py
  - admin-ui/tests/test_api_tokens.py
  - admin-ui/tests/test_docs.py
  - admin-ui/tests/test_ingress_characterisation.py
  - admin-ui/tests/test_rules_view.py
findings:
  critical: 0
  warning: 4
  info: 8
  total: 12
  necessity: 1
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-11-18T14:19:32Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

I reviewed the changes since `b03715d` in the bearer-gated API listener (`api.py`), the token verifiers
(`tokens.py`), the refactor of the ingress handler onto `_JsonHandler` (`server.py`), the R-16 rule wiring (strings,
rules view, DOCS tests) and the new test suites. I checked the behaviour against the locked decisions D-01..D-13 and
against R-16 in `admin-ui/DOCS.md`.

What holds up:

- **Gate:** No bypass found. `_dispatch` checks the token before `router.match` and `_read_body`. `__getattr__` sends
  every `do_*` method token to the gate. `send_error` turns parser errors into the same 401. HTTP/0.9 is handled. A
  duplicate `Authorization` header fails.
- **Timing:** Both verifiers hash the presented value and compare two 32-byte digests with `hmac.compare_digest`, so the
  comparison does not leak the secret or its length.
- **Logs:** `log_message` is silenced. `_ApiHeaders` hides `Authorization` and `Proxy-Authorization` from handlers.
  Neither `repr` shows a secret.
- **Ingress refactor:** No observable change found. The `ApiError`, mapper and traceback order is the same as before.
  CSP and mappers moved from closure variables to class attributes with the same values. The 501 for unknown methods
  and the stdlib `send_error` stay on the ingress handler. The golden matrix in `test_ingress_characterisation.py`
  pins status, header order and body.

The defects are on the edges. Each claim below was confirmed with a scratch probe (Python 3.14, not committed):

- **Token file:** A failure after `os.replace` can leave a hash on disk for a token nobody has (permanent lockout until
  the file is deleted). The "unreadable file raises `ValueError`" contract is not met.
- **Pre-auth slow clients:** They can hold handler threads indefinitely, despite the "slow clients are dropped" claim.
- **Unread bodies:** Bodies on non-body methods are never read, and the connection stays open (request desync).
- **Minor items:** Pre-auth `100 Continue`, Python version in the pre-auth `Server` header, `GeneratedToken` without
  `__slots__`, a stale `Request.public` contract, and a few style nits.

## Warnings

### WR-01: Directory fsync failure after `os.replace` leaves a hash nobody has a token for (lockout)

**File:** `admin-ui/app/web/skeleton/tokens.py:75-84` (called from `:109` and `:137`)
**Issue:** `_write_hash` runs `os.replace(tmp, path)` (line 75) and only then fsyncs the directory (lines 80-84). The
`try/except` covers only the replace, so an `OSError` from `os.open(path.parent)` or `os.fsync(dir_fd)` is raised
after the new hash is already in `path`. Two cases:

- **`rotate()` (line 137):** The exception skips `self._digest = digest`, so the old token keeps working in memory and
  the new plaintext is never returned. On disk the file now holds the hash of the lost token. After the next restart
  neither token works. This breaks the docstring promise "a failed write keeps the old token valid" (lines 91-92).
- **`load_or_create()` first start (line 109):** The plaintext is lost, but the file exists. Every later start loads it
  without an error and the API is locked out with no signal to the operator.

Probe: patching `os.fsync` to fail on directory fds gave this result: `rotate raised`, `old valid in memory: True`,
`old valid after restart: False`. `test_failed_replace_keeps_the_old_token` only patches `os.replace`, so this path is
not tested.

**Fix:** Treat the directory fsync as best effort once the replace has succeeded. The file content is already durable
through the file fsync, and the rename is what makes it visible:

```python
    os.replace(tmp, path)
except BaseException:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(tmp)
    raise
# Best effort: the replace already happened, so failing here would desync memory and disk
with contextlib.suppress(OSError):
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
```

Add a test that makes the directory fsync fail and asserts that the returned plaintext is valid after a reload.

### WR-02: `load_or_create` does not raise `ValueError` for unreadable paths and chmods whatever `path` points at

**File:** `admin-ui/app/web/skeleton/tokens.py:106-116`
**Issue:**

- **Wrong exception type:** The class docstring (lines 91-92) promises: "An unreadable or malformed file raises
  ValueError and is left untouched". In practice an unreadable file (mode 000, other owner) raises `PermissionError`,
  and a directory at `path` raises `IsADirectoryError`. Probe output: `unreadable -> PermissionError`,
  `directory -> IsADirectoryError`. A consumer that follows the contract and catches `ValueError` to "keep the API off"
  crashes the add-on instead.
- **The path is modified first:** Lines 111-112 run `os.chmod(path, 0o600)` before the content is validated.
  `chmod` follows symlinks and works on directories. In the probe, a directory at `path` was left at mode `0o600`
  (made untraversable) before the read failed. A symlink at `path` changes the mode of its target. That contradicts
  "left untouched".

**Fix:** Open once with `O_NOFOLLOW`, check that the result is a regular file, and map `OSError` to the documented
`ValueError`. Tighten the mode only after the content has been validated, and do it through the fd:

```python
try:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
except FileNotFoundError:
    ...  # create path (as today)
except OSError as exc:
    raise ValueError("API token file is unreadable: fix or delete it and restart") from None
try:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("API token path is not a regular file")
    data = os.read(fd, 128)
    match = ...  # validate data
    if stat.S_IMODE(st.st_mode) & 0o077:
        os.fchmod(fd, 0o600)
finally:
    os.close(fd)
```

`from None` keeps the path out of a chained traceback, if path privacy matters.

### WR-03: Unauthenticated slow-drip clients hold handler threads indefinitely; the "slow clients are dropped" claim is false

**File:** `admin-ui/app/web/skeleton/api.py:92-94`, `:151-154`
**Issue:** `timeout = 30` becomes a socket timeout per `recv`, not a deadline for the request. A client that sends one
byte of the request line or headers every 29 seconds never trips it. `readline(65537)` keeps reading, and the thread
stays parked before the gate ever runs. `_ApiServer` is a plain `ThreadingHTTPServer` with no connection limit, so
anyone who can reach the port (LAN or Tailscale, per R-16) can use up threads and memory without a token. Probe: with
the handler timeout patched to 1 s, a client sending one byte every 0.8 s was still connected after 6.4 s. The code
comment ("idle or slow clients are dropped") and DOCS ("Idle sockets time out after 30 seconds") claim more than the
code does. The API port is the one surface meant for exposure beyond the container, which makes this more than a
performance note.

**Fix:** Enforce a deadline for the whole request head, and limit concurrent connections. For example:

- Override `handle_one_request` (or `setup`) to set a `threading.Timer` / deadline that shuts down the socket if the
  request head has not been parsed within N seconds.
- Bound concurrency in `_ApiServer.process_request` with a `threading.BoundedSemaphore`. Close new connections at once
  when it is exhausted.
- Fix the comment and the DOCS sentence so they describe the real guarantee.

### WR-04: Bodies on non-body methods are never read, and the connection stays alive (request desync)

**File:** `admin-ui/app/web/skeleton/api.py:127`, `:141`; `admin-ui/app/web/skeleton/server.py:98-117`
**Issue:** `_read_body` runs only for `BODY_METHODS`. A `GET`, `HEAD` or `OPTIONS` with `Content-Length: N` gets a
successful response with keep-alive, and its N body bytes are then parsed as the next request on the connection.
Probe: one authenticated `GET /api/ping` whose body was an authenticated `POST /api/del` produced two responses and
two handler calls (`calls: ['/api/ping', 'POST /api/del']`).

The smuggled request still needs its own token, so this is not a gate bypass. It does break the request/response
pairing, though, as soon as an operator puts a connection-pooling TLS proxy in front of the port. DOCS explicitly
suggests that set-up. With such a proxy, responses can be delivered to the wrong client.

The ingress handler has the same inherited behaviour, and so do two other quirks of the shared `_read_body`:

- `int()` accepts `+5`, ` 5 ` and `1_0` as `Content-Length`.
- With duplicate `Content-Length` headers, the first one silently wins.

**Fix:** In `_dispatch`, after the gate, close the connection when a non-body method carries a body:

```python
if self.command not in BODY_METHODS and (
    self.headers.get("Transfer-Encoding") or (self.headers.get("Content-Length") or "0") != "0"
):
    self.close_connection = True
```

Also make `_read_body` strict: reject more than one `Content-Length` (`len(self.headers.get_all("Content-Length") or
[]) > 1`) and accept only `^[0-9]{1,7}$`. If you also change the ingress handler, update the golden matrix in the same
commit.

## Info

### IN-01: `Expect: 100-continue` is answered before the bearer check

**File:** `admin-ui/app/web/skeleton/api.py:114-123` (stdlib `parse_request` -> `handle_expect_100`)
**Issue:** `BaseHTTPRequestHandler.parse_request` sends `HTTP/1.1 100 Continue` before `do_*` runs. An unauthenticated
client is therefore invited to upload its body before it gets the 401. Probe: `HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 401`.
Nothing leaks, but it breaks "gate first, nothing before the token is valid" and makes unauthenticated uploads cheaper.
**Fix:** Override `handle_expect_100` in `ApiHandler` to `return True` without sending anything. The client then sends
the body or waits, and the 401 with `Connection: close` follows.

### IN-02: Unauthenticated responses disclose the Python version in `Server`

**File:** `admin-ui/app/web/skeleton/api.py:146`, `:168`
**Issue:** `version_string()` returns `server_version + " " + sys_version`, so every pre-auth 401 carries
`AdminUiApi Python/3.x.y`. That gives free fingerprinting on a port meant for LAN or Tailscale exposure.
**Fix:** In `ApiHandler`, set `sys_version = ""` or override `version_string()` to return only `server_version`.

### IN-03: `GeneratedToken` keeps the pending plaintext in an instance `__dict__`

**File:** `admin-ui/app/web/skeleton/tokens.py:87-100`
**Issue:** `OptionToken` is deliberately slotted, and a test asserts `not hasattr(token, "__dict__")`. `GeneratedToken`
has no `__slots__`, so `vars(token)`, `pickle`, or a traceback formatter that renders locals or attributes exposes
`_pending` (the plaintext) until it is taken. The two verifiers treat the secret differently.
**Fix:** Add `__slots__ = ("_path", "_digest", "_pending", "_lock")` and extend `test_repr_hides_secrets` with a
`__dict__` check.

### IN-04: `Request.public=True` on the API port contradicts the documented meaning of `public`

**File:** `admin-ui/app/web/skeleton/api.py:135` (contract in `admin-ui/app/web/skeleton/router.py:75-77`)
**Issue:** The `Request` comment still says `public` is true "only possible on routes registered with public=True".
API requests now set `public=True` on routes that are not public. A handler cannot tell an unauthenticated public GUI
request from a bearer-authenticated API request. That fails closed today, but the contract text is stale, and a
consumer that shares a handler between both routers has no signal.
**Fix:** Update the `Request.public` comment, or add an explicit field (for example `via: Literal["ingress", "public",
"bearer"]`).

### IN-05: Full tracebacks from handlers on the API port go to stdout, while `handle_error` prints only the class

**File:** `admin-ui/app/web/skeleton/api.py:138-139` -> `admin-ui/app/web/skeleton/server.py:128-129`
**Issue:** `_ApiServer.handle_error` drops the message because it "could carry request data". The far more common path,
an exception in a consumer handler, still prints the full `traceback.format_exc()` with its message. The tests assert
that `"secret detail"` reaches stdout. Provisioning payloads (credentials for repositories or ntfy users) are exactly
the request data that consumer exceptions tend to quote. This is documented, so it is not a contract breach, but the two
log policies are inconsistent.
**Fix:** Pick one policy for the API port. For example, let `ApiHandler._fail` print the type plus the traceback frames
without the exception message, or document that handlers must not quote request data in exceptions.

### IN-06: Necessity (impossible-state guard): `hasattr(headers, "get_all")` / `isinstance(values[0], str)` in `_bearer_token`

**File:** `admin-ui/app/web/skeleton/api.py:60-64`
**Category:** necessity
**Issue:** `_bearer_token` is called only from `_dispatch` (line 120), after the HTTP/0.9 branch has returned. For every
other request, `BaseHTTPRequestHandler.parse_request` has set `self.headers` to an `http.client.HTTPMessage`, which
always has `get_all` and always returns `str` values. The header values cross a trust boundary, but the container type
and the value type do not. The outer `try/except Exception` already makes any surprise fail closed. This rests on
reading the stdlib, so it is Info.
**Fix:** Optionally drop the two type guards and keep the `try/except` as the single fail-closed net.

### IN-07: The API listener can die silently while the GUI keeps running

**File:** `admin-ui/app/web/skeleton/server.py:233-237`
**Issue:** Extra servers run `serve_forever` in daemon threads, and nothing watches them. If a `more` server's loop
raises (for example a selector or fd error), only the default thread excepthook prints to stderr. The process and the
GUI stay up, and nothing signals that the API is gone, so a supervisor restart never happens.
**Fix:** Wrap the extra `serve_forever` in a function that, on an exception, prints the class name and triggers `stop()`
for all servers. A partial outage then becomes a visible restart.

### IN-08: Style nits in changed lines

**File:** `admin-ui/tests/test_docs.py:63-73`; `admin-ui/app/web/skeleton/server.py:18-19`
**Issue:**

- `test_docs.py` has three blank lines before `test_docs_r16_exposure_stays_a_review_item` and only one after it
  (PEP 8: two).
- `server.py` imports from `typing` on two lines (`from typing import Any, Callable` and `from typing import
  ClassVar`).

**Fix:** Normalise to two blank lines, and merge the imports into `from typing import Any, Callable, ClassVar`.

---

_Reviewed: 2026-11-18T14:19:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
