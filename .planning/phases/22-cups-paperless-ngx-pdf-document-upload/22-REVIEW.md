---
phase: 22-cups-paperless-ngx-pdf-document-upload
reviewed: 2026-10-04T19:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - cups/upload-worker.py
  - internal/verify-cups-upload-worker.py
  - internal/verify-cups-paperless-upload.sh
  - cups/DOCS.md
  - cups/config.yaml
findings:
  critical: 0
  warning: 9
  info: 8
  total: 17
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-10-04T19:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Incremental re-review of gap-closure plan 22-04 (`git diff a93bab6..HEAD`): redirect refusal and the HTTP 200 +
task-id success check in `upload_document()`, the new host-side probe `internal/verify-cups-upload-worker.py`, the new
verifier Scenario 5, the DOCS.md notes and the `0.1.0-17` bump. Prior findings were carried forward with their IDs and
re-checked against the current code (`22-REVIEW-DISPOSITION.md` consulted).

**CR-01 is resolved.** `requests.post(..., allow_redirects=False)` is in place, every 3xx returns False with a WARNING,
and success now requires HTTP 200 plus a non-empty JSON string body. I ran `internal/verify-cups-upload-worker.py`
locally against `requests` 2.34.2: ALL CHECKS PASSED (redirect matrix 301/302/303/307/308, body matrix, routing to
`failed/`/`sent/`). The probe asserts exactly one request reaches the stub, so it does detect a followed redirect.
Scenario 5 of the shell verifier is logically sound (fails closed when the stub log is missing).

The fix itself introduced one new defect: the log-safe redirect renderer can raise on a malformed `Location` header,
which escapes `upload_document()` (documented as never raising) and leaves the document in a permanent retry loop that
never counts attempts and never reaches `failed/` (new WR-09, reproduced). All 14 other prior findings (WR-01..WR-08,
IN-01..IN-06) are unchanged by this diff and still apply; line numbers below were refreshed.

## Resolved

### CR-01: HTTP redirects turn the upload into a GET and the worker records it as a success (RESOLVED)

**File:** `cups/upload-worker.py:273-319`
**Status:** fixed by 22-04. `allow_redirects=False` (line 279), 3xx branch (288-296), 200-only success with task-id
body check (298-312). Verified by running the host probe and by reading Scenario 5. No residual issue with the fix
itself other than WR-09 below.

## Warnings

### WR-09: Malformed `Location` header makes `_safe_redirect_target()` raise, the document then retries forever without ever being counted (NEW)

**File:** `cups/upload-worker.py:233`, `:288-296`, `:336`
**Issue:** `urlsplit(location)` raises `ValueError` for inputs such as `http://[::1/x` ("Invalid IPv6 URL"). The call
sits inside the f-string of the 3xx WARNING, outside the `try` that only wraps `requests.post`, so
`upload_document()` raises instead of returning False (its docstring promises "Never raises"). `attempt_and_route()`
has no handler, so the exception skips `save_retry_state()` and the exhaustion routing. The per-document handler in
`poll_once` only logs `WARNING: failed to retry a.pdf: Invalid IPv6 URL`. Reproduced: three consecutive
`attempt_and_route()` calls against a stub answering `302 Location: http://[::1/x` all raised `ValueError`, and the PDF
stayed in `processing/` with no retry state. Consequences: `is_due()` is True on every 20 s cycle, so the worker POSTs
the full PDF to paperless-ngx every 20 s indefinitely, `retry_count`/`retry_delay` are ignored, the document never
reaches `failed/`, and the useful "redirect ... set url to the final address" message is never printed. Reachable by
any broken proxy/SSO redirect, not only a hostile server.
**Fix:** make the renderer total:
```python
try:
    parts = urlsplit(location)
except ValueError:
    return "(unparseable Location header)"
```
Add a `Location: http://[::1/x` row to `check_redirect_matrix` in the probe asserting `upload_document()` returns False
and the WARNING is printed. Consider also moving `read_title()`/`int(timeout)` into the guarded region (see the same
"never raises" claim, which is already false for `pdf_path.open()` raising `OSError`).

### WR-01: Worker can pick up a PDF that cups-pdf is still writing, and can race the title-sidecar hook

**File:** `cups/upload-worker.py:376-387`, `:401-405`
**Issue:** `poll_once` globs `incoming/*.pdf` and moves/uploads every match immediately. cups-pdf creates the PDF at its
final name while ghostscript is still converting, and runs the `PostProcessing` hook (which writes the `.json`
sidecar) only after that. A poll in that window uploads a truncated PDF (paperless-ngx fails the consumption task
asynchronously while the HTTP call returns 200, so the worker records success) or moves the PDF before the sidecar
exists; the title then falls back to `Scan_<timestamp>` and the sidecar later sits in `incoming/` as an orphan nothing
removes. Still present; note the stricter 200 check does not help, because the task id is returned before consumption.
**Fix:** skip files that are not settled, e.g.
```python
MIN_FILE_AGE_SECONDS = 10
if time.time() - pdf_path.stat().st_mtime < MIN_FILE_AGE_SECONDS:
    continue
```
and optionally require a trailing `%%EOF` marker. Also sweep orphaned `incoming/*.json` older than a threshold.

### WR-02: `process_new_document` silently overwrites a same-named document that is still in `processing/`

**File:** `cups/upload-worker.py:383-385`
**Issue:** `pdf_path.replace(processing_pdf)` and `sidecar_path.replace(processing_sidecar)` use rename-clobber
semantics. cupsd's job-ID counter resets across a container restart (the reason `unique_destination()` exists for
`sent/`/`failed/`). A document waiting for its next retry in `processing/` when the container restarts is destroyed by
a new job with the same title and job ID, and the new document inherits the old `.retry.json` attempt count.
**Fix:** `pdf_path.replace(unique_destination(PROCESSING, pdf_path.name, tag=...))` with a shared tag for the sidecar and
retry state tied to the final name, or leave the file in `incoming/` (and log) while the destination exists.

### WR-03: Retry-state field types are not validated, one bad file stalls that document forever

**File:** `cups/upload-worker.py:216-220`, `:394`
**Issue:** `is_due` catches only `(KeyError, ValueError)`. A `next_attempt_at` that is `null`/a number raises
`TypeError`, and a timezone-naive ISO string makes `datetime.now(timezone.utc) >= next_attempt_at` raise `TypeError`.
`process_due_retry` does `int(state.get("attempts", 0) or 0)` and raises `ValueError` for a non-numeric string. The
per-document `try` keeps siblings alive, but the stuck document logs `WARNING: failed to retry ...` every 20 s forever
and never reaches `failed/`.
**Fix:**
```python
try:
    next_attempt_at = datetime.fromisoformat(state["next_attempt_at"])
    if next_attempt_at.tzinfo is None:
        next_attempt_at = next_attempt_at.replace(tzinfo=timezone.utc)
except (KeyError, ValueError, TypeError):
    return True
```
and wrap the `attempts` coercion in `try/except (TypeError, ValueError): prior_attempts = 0`.

### WR-04: Exhaustion WARNING names the pre-disambiguation filename

**File:** `cups/upload-worker.py:352-365`
**Issue:** the return value of `unique_destination()` is discarded and the D-15 line still prints
`see failed/{pdf_path.name}`. After a collision that path is the older, unrelated document.
**Fix:**
```python
final_pdf = unique_destination(FAILED, pdf_path.name, tag=collision_tag)
pdf_path.replace(final_pdf)
...
f"{pdf_path.name} -- moved to failed/, see failed/{final_pdf.name}"
```
Add a verifier case combining exhaustion with a pre-seeded `failed/` collision.

### WR-05: No validation of `url`/`token` when the feature is enabled; every document is dead-lettered silently

**File:** `cups/upload-worker.py:84-94`, `:266-286`; `cups/generate_config.py:874-886`
**Issue:** `enabled: true` with the shipped defaults (`url: ""`, `token: ""`) is accepted. `requests.post("/api/...")`
raises `MissingSchema` (a `RequestException`), so every print job burns `retry_count` attempts and lands in `failed/`,
which is never retried. One misconfiguration at enable time permanently dead-letters every document printed until the
operator notices a per-document WARNING. With the new redirect refusal this class grows: an `http://` URL in front of
an http-to-https redirect now also dead-letters every document (documented in DOCS.md, but still only discoverable per
document).
**Fix:** in `load_paperless_config` (and/or `build_cups_pdf_conf`) check that `url` has an `http(s)` scheme and a host
and that `token` is non-empty; on failure log one clear `ERROR: paperless_upload.url/token missing` line and either do
not register the queue or keep documents in `incoming/` instead of consuming retry attempts.

### WR-06: Success path deletes sidecar and retry state before the PDF is moved, so a failure re-uploads the document

**File:** `cups/upload-worker.py:336-342`
**Issue:** after a successful upload the order is: unlink sidecar, unlink retry state, then
`pdf_path.replace(unique_destination(SENT, ...))`. If the final move raises (full/read-only volume, permission
change), the PDF stays in `processing/` with no retry state, `is_due` returns True on the next cycle, and the same
document is uploaded again, producing duplicates in paperless-ngx on every cycle while the move keeps failing. The
title is also gone for the re-upload.
**Fix:** move the PDF to `sent/` first, then remove the sidecar and retry state (or move the sidecar to `sent/` too,
which is what DOCS.md claims, see IN-04).

### WR-07: Verifier cannot detect a broken title-recovery mechanism

**File:** `internal/verify-cups-paperless-upload.sh:127`, `:313`, Scenario 3
**Issue:** the happy-path title assertion only checks `title` is non-empty. The `Scan_<timestamp>` fallback (and an
un-stripped `...-job_1` title) also satisfies it, so the PostProcessing hook / `Label 2` / filename-derived title
(D-10..D-13, the core of the phase) can be completely broken and the script still prints PASS. Scenario 3 downgrades a
missing sidecar in `failed/` to a yellow NOTE. The stub's `rstrip(b"\r\n--")` also eats trailing hyphens from the
recorded title, so an exact comparison needs that fixed first. Scenario 5 added in 22-04 does not assert on the title
either.
**Fix:** assert the recorded title equals the expected derived title, assert it does not start with `Scan_` and does not
match `-job_[0-9]+$`, make the missing sidecar in Scenario 3 a FAIL, and strip only the trailing `\r\n` in the stub.

### WR-08: `paperless_upload.queue_name` can collide with a `printers[]` name

**File:** `cups/generate_config.py:1005-1012`, `:1520-1525` (not changed by 22-04, carried forward)
**Issue:** `queue_name` is validated for charset only. If it equals a physical printer's `name`, both `lpadmin -p
<name>` calls run against the same queue: the later cups-pdf registration re-points the physical queue at `cups-pdf:/`,
so prints silently go to paperless-ngx instead of paper (and the name is added twice to `registered_printer_names`).
**Fix:** in `main()`, reject (log a WARNING and skip the cups-pdf queue) when `queue_name in registered_printer_names`.

## Info

### IN-01: Internal finding ID "(WR-05)" appears in a runtime log line

**File:** `cups/upload-worker.py:161-166`
**Issue:** the string `... already-retained document (WR-05)` is printed to the add-on log; the token is meaningless to
users. Still present.
**Fix:** keep the reference in the docstring only.

### IN-02: Shared `collision_tag` only holds when the PDF itself collides

**File:** `cups/upload-worker.py:349-352`
**Issue:** `collision_tag` is derived only from `(FAILED / pdf_path.name).exists()`; a sidecar-only collision gets an
unrelated tag, contradicting the comment about correlating pairs.
**Fix:** also test `(FAILED / sidecar_path.name).exists()`, or soften the comment.

### IN-03: Falsy-zero coercion of numeric options

**File:** `cups/upload-worker.py:268`, `:345-346`
**Issue:** `int(config.get("retry_count", 5) or 5)` (and `timeout`, `retry_delay`) turns an explicit `0` into the
default, although the schema allows `0`. A whitespace-only title is also truthy, so `read_title` can return `""` after
`.strip()`.
**Fix:** use an explicit `None` check, and strip before the `if not title` test.

### IN-04: DOCS.md and the worker docstring disagree about the sidecar on success

**File:** `cups/DOCS.md:141-142`, `cups/upload-worker.py:28-31` vs `:337-340`
**Issue:** docs (re-edited by 22-04 but the claim kept) and the module docstring say the PDF and sidecar end up in
`sent/`; the code deletes the sidecar and moves only the PDF. The Dockerfile comment about "stdlib json only" is also
stale now that `py3-requests` is installed.
**Fix:** align code or text (moving the sidecar to `sent/` would also address WR-06's ordering concern).

### IN-05: Stage directories are all `0o777`, no sticky bit, and TLS verification cannot be configured

**File:** `cups/generate_config.py:1560-1563`, `cups/upload-worker.py:273-280`
**Issue:** only `incoming/` needs to be writable by the unprivileged cups-pdf job user; `processing/`, `sent/` and
`failed/` are root-only yet world-writable, exposing retained documents. `requests` verifies TLS with no `verify`/CA
option, so a self-signed paperless-ngx dead-letters every document. The redirect-refusal rule makes this more visible
because the documented remedy is "use the https:// URL".
**Fix:** `incoming/` `0o1777`, the others `0o755`; add an optional `verify_ssl` (or CA bundle) option.

### IN-06: `avahi_guard_start` claims it always leaves avahi running

**File:** `cups/avahi-guard.sh:25-29`, `:204-210` (not in 22-04 scope, carried forward)
**Issue:** if avahi has exited on the final attempt, the guard logs `giving up ... continuing` and returns with
`AVAHI_PID` pointing at a dead process, contradicting the header comment.
**Fix:** relaunch avahi once more in that branch, or correct the comment and log that avahi is not running.

### IN-07: Probe does not exercise `_safe_redirect_target()` redaction or edge inputs (NEW)

**File:** `internal/verify-cups-upload-worker.py:165-180`
**Issue:** the only `Location` value used is `/login/`. The function exists to drop query strings, fragments and
userinfo from log output, and to cap length, yet none of that is asserted: a regression that logs
`https://user:secret@host/login?token=...` verbatim would still pass. The same gap hid WR-09. The script is also a manual
tool outside pre-commit/`make check-all`, so a regression is only caught if someone remembers to run it.
**Fix:** add `Location` rows such as `https://user:pw@sso.example/login?state=abc#frag` (assert `pw`, `state=abc` and
`frag` absent, `sso.example/login` present), a 500-character path (assert the 200-character cap), an empty `Location`
(assert `(no Location header)`) and the malformed IPv6 value from WR-09.

### IN-08: Success is now HTTP 200 only; other 2xx answers are retried and eventually dead-lettered although the upload may be accepted (NEW)

**File:** `cups/upload-worker.py:298-319`
**Issue:** 201/202/204 from paperless-ngx (or a proxy in front of it) now count as failures. If the server actually
queued the document, the worker re-POSTs it up to `retry_count` times (paperless-ngx rejects the duplicates by checksum)
and finally parks a delivered document in `failed/` with a WARNING that suggests manual upload. The behaviour is
deliberate and documented (DOCS.md, docstring), and the 200 branch is split into two consecutive `if` blocks that
could be one if/else, but the trade-off is not called out as such for operators of non-standard proxies.
**Fix:** acceptable as designed; optionally log the non-200 2xx case with a distinct message ("2xx other than 200,
treated as not accepted") so it is distinguishable from an error status, and restructure the two 200 branches into one.

---

_Reviewed: 2026-10-04T19:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
