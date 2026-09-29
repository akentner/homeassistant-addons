---
phase: 22-cups-paperless-ngx-pdf-document-upload
reviewed: 2026-09-29T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - cups/upload-worker.py
  - internal/verify-cups-paperless-upload.sh
  - cups/config.yaml
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-09-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

This is an incremental review of the 22-03 gap-closure plan (diff against `272f604`), which claimed to fix three
previously-flagged findings in `cups/upload-worker.py`:

- **CR-01** (malformed `.retry.json` stalling the retry queue for every alphabetically-later document)
- **WR-02** (malformed title sidecar breaking timestamp-fallback)
- **WR-05** (sent/failed filename collision silently overwriting a retained document)

**Verification result: all three original bugs are genuinely fixed.** I traced each fix by hand (isinstance(dict)
guards in `load_retry_state`/`read_title`, `is_due()` moved inside the same per-document `try` as
`process_due_retry()`, and the new `unique_destination()`/`_disambiguation_suffix()` helpers), compiled the file
(`python3 -m py_compile`), syntax-checked and shellchecked the verify script (clean), and manually walked Scenario 4's
new fixtures (`poison-aaa.*`, `zzz-normal.pdf`, `badtitle-doc.*`, `collide.pdf`) against the actual code paths they
exercise. CR-01's regression fixture (a malformed `.retry.json` sorting before a fresh document) and WR-05's
collision fixture (a pre-existing `sent/collide.pdf`) both correctly prove what they claim to prove.

However, the fix that resolves CR-01/WR-05 introduces **one new bug of its own** (WR-01 below): the final D-15
"upload exhausted" log line still reports the pre-disambiguation filename when a `failed/` collision occurs, so an
operator following that exact log line to `failed/<name>` will find a stale, unrelated document instead of the one
that just failed — undermining the stated purpose of the WR-05 fix ("a human triaging failed/ can still correlate a
colliding pair"). This exact combination (retry exhaustion **and** a collision in `failed/`) is not exercised by
either Scenario 3 (exhaustion, no collision) or Scenario 4 (collision, no exhaustion), so the new test suite cannot
catch it.

Separately, the CR-01 hardening only validates that the retry-state JSON is a dict at the top level; a well-formed
dict with a wrong-typed `attempts` or `next_attempt_at` field still raises an uncaught exception one level deeper
(WR-02 below), permanently stalling that single document (though, thanks to the CR-01 reordering, no longer starving
its siblings).

No critical/security findings. `cups/config.yaml`'s version bump (`0.1.0-14` → `0.1.0-15`) is a correct add-on-only
subpatch increment per this repo's 3-file versioning scheme (`build.yaml`'s `VERSION: "0.1.0"` and the README shield
badge `v0.1.0` correctly stay unchanged, since only the subpatch changed).

## Warnings

### WR-01: D-15 exhaustion log line reports the pre-disambiguation filename on a `failed/` collision

**File:** `cups/upload-worker.py:290-307`
**Issue:**

```python
if attempts >= retry_count:
    collision_tag = _disambiguation_suffix() if (FAILED / pdf_path.name).exists() else None
    pdf_path.replace(unique_destination(FAILED, pdf_path.name, tag=collision_tag))
    if sidecar_path.exists():
        sidecar_path.replace(unique_destination(FAILED, sidecar_path.name, tag=collision_tag))
    if retry_path.exists():
        retry_path.unlink()
    print(
        f"WARNING: paperless-ngx upload exhausted after {retry_count} attempts for "
        f"{pdf_path.name} -- moved to failed/, see failed/{pdf_path.name}",
        flush=True,
    )
```

`unique_destination()` returns a *renamed* path when `failed/{pdf_path.name}` already exists (exactly the WR-05
collision case), but its return value is discarded — `pdf_path.replace(...)` moves the file to the disambiguated
name, while the very next `print()` still references the original `pdf_path.name` in `see failed/{pdf_path.name}`.
In the collision case that exact path does **not** exist under that name in `failed/` — it holds the *older*,
unrelated, already-retained document that caused the collision, not the one that just exhausted its retries. An
operator who follows this literal log line to triage the failure will look at the wrong file.

This is a genuine regression introduced by this same diff: before this change, `pdf_path.replace(FAILED /
pdf_path.name)` and the log line's `pdf_path.name` always referred to the same real destination, so this class of
bug could not occur. `unique_destination()` does emit its own, separate, correctly-named WARNING
(`"destination ... already exists -- moving to ..."`), so the correct filename is *somewhere* in the logs, but the
single line that D-15's own comment says is meant to be "exactly one WARNING-level line per exhausted-retry
document" is now misleading whenever a collision happens.

Neither `internal/verify-cups-paperless-upload.sh` Scenario 3 (exhaustion, no collision fixture) nor the new Scenario
4 (collision fixture, but the document succeeds on first upload and never exhausts retries) exercises retry
exhaustion **and** a `failed/` collision together, so this went uncaught by the added regression tests.

**Fix:** capture the actual destination path and use it in the log message:

```python
if attempts >= retry_count:
    collision_tag = _disambiguation_suffix() if (FAILED / pdf_path.name).exists() else None
    final_pdf_path = unique_destination(FAILED, pdf_path.name, tag=collision_tag)
    pdf_path.replace(final_pdf_path)
    if sidecar_path.exists():
        sidecar_path.replace(unique_destination(FAILED, sidecar_path.name, tag=collision_tag))
    if retry_path.exists():
        retry_path.unlink()
    print(
        f"WARNING: paperless-ngx upload exhausted after {retry_count} attempts for "
        f"{pdf_path.name} -- moved to failed/, see failed/{final_pdf_path.name}",
        flush=True,
    )
```

Consider also adding a Scenario 5 (or extending Scenario 4) that pre-seeds `failed/` with a colliding filename and
drives a document through full retry exhaustion (`retry_count`/`retry_delay` small, stub server permanently in
`fail` mode), then asserts the D-15 log line's `failed/<name>` substring matches a file that actually exists on
disk.

### WR-02: retry-state hardening validates the JSON is a dict but not its field types

**File:** `cups/upload-worker.py:214-217` (`is_due`), `:332-337` (`process_due_retry`)
**Issue:** `load_retry_state()` now correctly rejects a non-dict top-level JSON value (the original CR-01 bug), but a
syntactically-valid **dict** with a wrong-typed field still passes through untouched and blows up one level deeper,
outside of any `try/except` that treats it as "malformed, ignore":

```python
# process_due_retry, line 336:
prior_attempts = int(state.get("attempts", 0) or 0)
```

If `state == {"attempts": "not-a-number"}`, `"not-a-number" or 0` is truthy, so `int("not-a-number")` raises
`ValueError`. Similarly, in `is_due()`:

```python
# is_due, line 214:
next_attempt_at = datetime.fromisoformat(state["next_attempt_at"])
except (KeyError, ValueError):
    return True
```

only catches `KeyError`/`ValueError`. If `next_attempt_at` is present but not a string (e.g. a JSON number), the
resulting `TypeError: fromisoformat: argument must be str` is **not** caught here.

Because the CR-01 fix moved `is_due()`/`process_due_retry()` inside the same per-document `try/except Exception` in
`poll_once()`, this class of exception no longer stalls sibling documents — but it does permanently stall *that one*
document: the exception fires before `attempt_and_route()`/`save_retry_state()` can run, so the document never
advances toward `failed/`, and the outer `except` logs a fresh `WARNING: failed to retry ...` line every 20-second
poll cycle indefinitely. This requires a hand-edited or externally-corrupted `.retry.json` (this worker's own
`save_retry_state()` always writes well-typed fields via an atomic temp-file + `.replace()`, so it can't produce this
shape on its own) — a narrower precondition than CR-01's original "any malformed JSON", but still a real gap in the
"never gets permanently stuck" guarantee this same change set is meant to establish.

**Fix:** validate/py coerce the specific fields defensively, e.g.:

```python
try:
    prior_attempts = int(state.get("attempts", 0) or 0)
except (TypeError, ValueError):
    prior_attempts = 0
```

and in `is_due()`:

```python
try:
    next_attempt_at = datetime.fromisoformat(state["next_attempt_at"])
except (KeyError, ValueError, TypeError):
    return True
```

## Info

### IN-01: internal finding ID "(WR-05)" leaks into a production log line

**File:** `cups/upload-worker.py:158-163`
**Issue:**

```python
print(
    f"WARNING: destination {candidate} already exists -- moving to "
    f"{stem}{tag}{suffix} instead to avoid silently overwriting an already-retained "
    "document (WR-05)",
    flush=True,
)
```

This message reaches `docker logs`/`ha addons logs` for real end users of this add-on. "(WR-05)" is an internal
planning/review-finding ID from this repo's `.planning/` artifacts and is meaningless to anyone without access to
this phase's planning history. Other similar in-code references (`D-15`, `CR-01`) in this file are confined to
source comments, not printed strings — this is the only one that ships into the runtime log output.

**Fix:** drop the parenthetical from the printed string (keep it in the docstring/comment only):

```python
print(
    f"WARNING: destination {candidate} already exists -- moving to "
    f"{stem}{tag}{suffix} instead to avoid silently overwriting an already-retained document",
    flush=True,
)
```

### IN-02: `collision_tag` sharing between PDF and sidecar is only reliable when the PDF itself collides

**File:** `cups/upload-worker.py:290-297`
**Issue:** the stated intent (comment at line 291-293) is that PDF and sidecar share one `collision_tag` "so a human
triaging failed/ later can still correlate a colliding pair by their identical disambiguation suffix." But
`collision_tag` is derived solely from `(FAILED / pdf_path.name).exists()`. If only the sidecar's destination name
independently collides (the PDF's does not), `collision_tag` stays `None`, and `unique_destination()` for the
sidecar generates its own fresh tag — which is fine functionally (still disambiguated, still logged) but means the
"shared tag for correlation" guarantee only actually holds in the case where the PDF collides. In practice PDF and
sidecar share a stem, so this asymmetric collision is unlikely (both would typically appear/disappear together), but
worth a one-line comment caveat if this is meant to be a strict guarantee.

**Fix:** either compute `collision_tag` from `(FAILED / pdf_path.name).exists() or (FAILED / sidecar_path.name).exists()`,
or soften the comment to note the guarantee only applies to the common case.

### IN-03: pre-existing falsy-zero coercion bug in numeric option parsing (out of this diff's scope)

**File:** `cups/upload-worker.py:227-229`, `:287-289` (unchanged by this diff, noted for completeness)
**Issue:** `int(config.get("retry_count", 5) or 5)` (and the equivalent for `timeout`/`retry_delay`) silently
replaces an explicit `0` with the fallback default, because `0 or 5` evaluates to `5` in Python. `cups/config.yaml`'s
schema (`retry_count: "int?"`, etc.) permits `0` as a legitimate value (e.g. "fail immediately, no retries"), but an
admin who configures `retry_count: 0` would unknowingly get 5 retries instead. This line is untouched by the 22-03
diff (present identically at `272f604`), so it's not a regression from this change, but it sits directly adjacent to
code this change modified and is worth flagging for a future pass. Not counted against this phase's pass/fail.

**Fix (if picked up later):** `int(config.get("retry_count", 5))` with an explicit `None`-check instead of the `or`
fallback, e.g. `v = config.get("retry_count"); retry_count = int(v) if v is not None else 5`.

---

_Reviewed: 2026-09-29T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
