---
phase: 22-cups-paperless-ngx-pdf-document-upload
reviewed: 2026-10-04T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - cups/DOCS.md
  - cups/Dockerfile
  - cups/README.md
  - cups/avahi-guard.sh
  - cups/config.yaml
  - cups/generate_config.py
  - cups/run.sh
  - cups/upload-worker.py
  - internal/verify-cups-paperless-upload.sh
findings:
  critical: 1
  warning: 8
  info: 6
  total: 15
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-10-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Full re-review of the phase 22 paperless-ngx upload path (`upload-worker.py`, `generate_config.py` paperless sections,
`run.sh`, `Dockerfile`, the verifier) plus the diff `e88bb63..HEAD` (phase 21 avahi-guard work, the `REGISTER_FAILED`
registration rework, the verifier's isolation wrapper). This overwrites the earlier 22-03 incremental report.

The phase 21 changes do not break the upload path itself: `run.sh` still starts `upload-worker.py` after the cupsd
UUID-fixup restart, `avahi-guard.sh` is copied into the image, the cups-pdf queue snippet is now correctly appended to
`register-printers.sh` before the `exit "$REGISTER_FAILED"` trailer, and the verifier's `cups_isolated_run` wrapper
keeps the `host.docker.internal` stub servers reachable. One side effect to be aware of: cupsd (and so the whole
upload path) can now start up to roughly 4-5 minutes late when avahi cannot settle (30 s settle, 30 s backoff, 30 s,
90 s backoff, 30 s). The design documents this.

The main problem is in the worker itself. One defect is a **BLOCKER**: a redirecting paperless-ngx endpoint makes the
worker report a successful upload that never happened (reproduced locally against `requests` 2.34.2, see CR-01). The
rest are data-loss and robustness gaps (in-flight file pickup, `processing/` clobbering, a double-upload window on
success) and a verifier that cannot detect the title-recovery mechanism failing.

Three findings from the previous report are still present in the current code, so they are carried forward and
re-verified here: the exhaustion log line (WR-04), retry-state field types (WR-03) and the falsy-zero coercion
(IN-03). The internal `(WR-05)` token is also still in a runtime log string (IN-01).

## Critical Issues

### CR-01: HTTP redirects turn the upload into a GET and the worker records it as a success

**File:** `cups/upload-worker.py:232-254`
**Issue:** `requests.post()` is called with the default `allow_redirects=True`, and success is defined purely as
`200 <= response.status_code < 300`. For a 301/302/303 answer `requests` rewrites the POST into a GET on the redirect
target and drops the body. If that target answers 2xx (a login page, an SPA index, the API root), the worker logs
`uploaded ... to paperless-ngx`, deletes the sidecar and retry state, and moves the PDF to `sent/`. The document never
reached paperless-ngx and nothing indicates this. A typical trigger is `url: "http://paperless:8000"` in front of a
reverse proxy that redirects http to https, or a trailing-slash/`APPEND_SLASH` redirect.

Reproduced locally: a server answering `POST /api/documents/post_document/` with `301 Location: /login/` and `GET
/login/` with 200 produced `200 GET http://127.0.0.1:<port>/login/ <html>login</html>` from the exact `requests.post`
call shape used here.

paperless-ngx's `post_document` answers 200 with the consumption task UUID as a bare JSON string, so a stronger success
check is cheap.

**Fix:**
```python
response = requests.post(
    f"{url}{PAPERLESS_ENDPOINT}",
    headers={"Authorization": f"Token {token}"},
    files={"document": (pdf_path.name, fh, "application/pdf")},
    data={"title": title},
    timeout=timeout,
    allow_redirects=False,   # a redirect must surface as a failure, never be followed as a GET
)
...
if response.status_code == 200 and _looks_like_task_id(response):
    ...
```
with `_looks_like_task_id` accepting a JSON string body (UUID). Treat any 3xx as a failure and log the `Location`
header so the operator can fix `url`. Add a verifier scenario where the stub answers 301.

## Warnings

### WR-01: Worker can pick up a PDF that cups-pdf is still writing, and can race the title-sidecar hook

**File:** `cups/upload-worker.py:343-347`, `:318-329`
**Issue:** `poll_once` globs `incoming/*.pdf` and moves/uploads every match immediately. cups-pdf creates the PDF at
its final name while ghostscript is still converting, and runs the `PostProcessing` hook (which writes the `.json`
sidecar) only after that. A poll that lands in that window (multi-second for large documents) either uploads a
truncated PDF (paperless-ngx then fails the consumption task asynchronously while the HTTP call returns 200, so the
worker records success) or moves the PDF before the sidecar exists. In the second case the title falls back to
`Scan_<timestamp>` and the sidecar later appears in `incoming/` as an orphan that no code ever removes.
**Fix:** skip files that are not settled, e.g.
```python
MIN_FILE_AGE_SECONDS = 10
if time.time() - pdf_path.stat().st_mtime < MIN_FILE_AGE_SECONDS:
    continue
```
and optionally require a trailing `%%EOF` marker. Also sweep orphaned `incoming/*.json` older than a threshold.

### WR-02: `process_new_document` silently overwrites a same-named document that is still in `processing/`

**File:** `cups/upload-worker.py:325-327`
**Issue:** `pdf_path.replace(processing_pdf)` and `sidecar_path.replace(processing_sidecar)` use rename-clobber
semantics. The code itself notes that cupsd's job-ID counter resets across a container restart, which is the same
reason `unique_destination()` exists for `sent/` and `failed/`. A document that is still waiting for its next retry in
`processing/` when the container restarts (typical when the paperless host is down at the same time) is destroyed by a
new job with the same title and job ID. The old PDF is lost, and the new document inherits the old `.retry.json`
attempt count. This is the same defect class as the already-fixed WR-05, in the one move that was missed.
**Fix:** `pdf_path.replace(unique_destination(PROCESSING, pdf_path.name, tag=...))`, using a shared tag for the sidecar
and keeping the retry state tied to the final name. Alternatively skip the move (log and leave in `incoming/`) while
the destination exists.

### WR-03: Retry-state field types are not validated, one bad file stalls that document forever

**File:** `cups/upload-worker.py:213-217`, `:336`
**Issue:** `is_due` catches only `(KeyError, ValueError)`. A `next_attempt_at` that is `null`/a number raises
`TypeError`, and a timezone-naive ISO string makes `datetime.now(timezone.utc) >= next_attempt_at` raise `TypeError`.
`process_due_retry` does `int(state.get("attempts", 0) or 0)` and raises `ValueError` for a non-numeric string. The
per-document `try` in `poll_once` keeps siblings alive, but the stuck document logs `WARNING: failed to retry ...`
every 20 s forever and never reaches `failed/`. (Carried over unchanged from the previous report.)
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

**File:** `cups/upload-worker.py:294-307`
**Issue:** the return value of `unique_destination()` is discarded and the D-15 line still prints
`see failed/{pdf_path.name}`. When a collision occurred, that path is the older, unrelated document. (Carried over;
still unfixed in the current code.)
**Fix:**
```python
final_pdf = unique_destination(FAILED, pdf_path.name, tag=collision_tag)
pdf_path.replace(final_pdf)
...
f"{pdf_path.name} -- moved to failed/, see failed/{final_pdf.name}"
```
Also add a verifier case that combines exhaustion with a pre-seeded `failed/` collision.

### WR-05: No validation of `url`/`token` when the feature is enabled; every document is dead-lettered silently

**File:** `cups/upload-worker.py:81-91`, `:227-246`; `cups/generate_config.py:874-886`
**Issue:** `enabled: true` with the shipped defaults (`url: ""`, `token: ""`) is accepted. `requests.post("/api/...")`
raises `MissingSchema` (a `RequestException`), so every print job burns `retry_count` attempts and lands in `failed/`.
`failed/` is never retried (documented), so one misconfiguration at enable time permanently dead-letters every
document printed until the operator notices a per-document WARNING. The worker's only startup line is
`upload worker started`.
**Fix:** in `load_paperless_config` (and/or `build_cups_pdf_conf`) check that `url` has an `http(s)` scheme and a
host and that `token` is non-empty; on failure log one clear `ERROR: paperless_upload.url/token missing` line and
either do not register the queue or keep documents in `incoming/` instead of consuming retry attempts.

### WR-06: Success path deletes sidecar and retry state before the PDF is moved, so a failure re-uploads the document

**File:** `cups/upload-worker.py:278-284`
**Issue:** after a successful upload the order is: unlink sidecar, unlink retry state, then
`pdf_path.replace(unique_destination(SENT, ...))`. If the final move raises (full or read-only volume, permission
change), the PDF stays in `processing/` with no retry state, `is_due` returns True on the next cycle, and the same
document is uploaded again, producing duplicates in paperless-ngx (and again on every cycle while the move keeps
failing). Also the title is gone for the re-upload.
**Fix:** move the PDF to `sent/` first, then remove the sidecar and retry state (or move the sidecar to `sent/` too,
which is what DOCS.md currently claims, see IN-04).

### WR-07: Verifier cannot detect a broken title-recovery mechanism

**File:** `internal/verify-cups-paperless-upload.sh:288-298`, `:461-466`
**Issue:** the happy-path title assertion only checks `title` is non-empty. The worker's `Scan_<timestamp>` fallback
(and an un-stripped `...-job_1` title) also satisfies it, so the PostProcessing hook / `Label 2` / filename-derived
title (D-10..D-13, the core of the phase) can be completely broken and the script still prints PASS. Scenario 3 goes
further and downgrades a missing sidecar in `failed/` to a yellow NOTE. The stub's `rstrip(b"\r\n--")` also eats
trailing hyphens from the recorded title, so an exact comparison needs that fixed first.
**Fix:** assert the recorded title equals the expected derived title (`Happy_Path_Title` or whatever cups-pdf's
`preparetitle()` produces for `-t "Happy Path Title"`), assert it does not start with `Scan_` and does not match
`-job_[0-9]+$`, and make the missing sidecar in Scenario 3 a FAIL. Strip only the trailing `\r\n` in the stub.

### WR-08: `paperless_upload.queue_name` can collide with a `printers[]` name

**File:** `cups/generate_config.py:1005-1012`, `:1520-1525`
**Issue:** `queue_name` is validated for charset only. If it equals a physical printer's `name`, both `lpadmin -p
<name>` calls run against the same queue: the later cups-pdf registration re-points the physical queue at
`cups-pdf:/`, so prints silently go to paperless-ngx instead of paper (and the name is added twice to
`registered_printer_names`).
**Fix:** in `main()`, reject (log a WARNING and skip the cups-pdf queue) when `queue_name in registered_printer_names`.

## Info

### IN-01: Internal finding ID "(WR-05)" appears in a runtime log line

**File:** `cups/upload-worker.py:158-163`
**Issue:** the string `... already-retained document (WR-05)` is printed to the add-on log; the token is meaningless
to users. Carried over, still present.
**Fix:** keep the reference in the docstring only.

### IN-02: Shared `collision_tag` only holds when the PDF itself collides

**File:** `cups/upload-worker.py:294-297`
**Issue:** `collision_tag` is derived only from `(FAILED / pdf_path.name).exists()`; a sidecar-only collision gets an
unrelated tag, contradicting the comment about correlating pairs. Carried over.
**Fix:** also test `(FAILED / sidecar_path.name).exists()`, or soften the comment.

### IN-03: Falsy-zero coercion of numeric options

**File:** `cups/upload-worker.py:229`, `:287-288`
**Issue:** `int(config.get("retry_count", 5) or 5)` (and `timeout`, `retry_delay`) turns an explicit `0` into the
default, although the schema allows `0`. A whitespace-only title is also truthy, so `read_title` can return `""`
after `.strip()`. Carried over.
**Fix:** use an explicit `None` check, and strip before the `if not title` test.

### IN-04: DOCS.md and the worker docstring disagree about the sidecar on success

**File:** `cups/DOCS.md:141-142`, `cups/upload-worker.py:28-29` vs `:279-280`
**Issue:** docs and module docstring say the PDF and sidecar end up in `sent/`; the code deletes the sidecar and moves
only the PDF. The Dockerfile comment at line 9 ("python3: runs generate_config.py (stdlib json only...)") is also
stale now that `py3-requests` is installed for the worker.
**Fix:** align code or text (moving the sidecar to `sent/` would also fix WR-06's ordering concern).

### IN-05: Stage directories are all `0o777`, no sticky bit, and `https` verification cannot be configured

**File:** `cups/generate_config.py:1560-1563`, `cups/upload-worker.py:234`
**Issue:** only `incoming/` needs to be writable by the unprivileged cups-pdf job user; `processing/`, `sent/` and
`failed/` are touched only by the root worker yet are also world-writable (and none has the sticky bit), exposing
retained documents. Separately, `requests` verifies TLS with no `verify`/CA option, so a self-signed paperless-ngx
dead-letters every document (the retry exhaustion path hides the cause behind a generic exception text).
**Fix:** `incoming/` `0o1777`, the others `0o755`; add an optional `verify_ssl` (or CA bundle) option.

### IN-06: `avahi_guard_start` claims it always leaves avahi running

**File:** `cups/avahi-guard.sh:25-29`, `:204-210`
**Issue:** if avahi has exited (`avahi_guard_wait_settled` rc 2) on the final attempt, the guard logs
`giving up ... continuing` and returns with `AVAHI_PID` pointing at a dead process, contradicting the header comment.
cupsd then starts without any avahi daemon (printer not advertised) while the result line says `unsettled`. Not on the
upload path, but it determines whether the paperless queue is advertised.
**Fix:** relaunch avahi once more in that branch, or correct the comment and log that avahi is not running.

---

_Reviewed: 2026-10-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
