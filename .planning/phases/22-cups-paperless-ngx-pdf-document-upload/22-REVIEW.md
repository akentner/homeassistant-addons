---
phase: 22-cups-paperless-ngx-pdf-document-upload
reviewed: 2026-09-28T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - cups/DOCS.md
  - cups/Dockerfile
  - cups/README.md
  - cups/config.yaml
  - cups/generate_config.py
  - cups/run.sh
  - cups/translations/de.yaml
  - cups/translations/en.yaml
  - cups/upload-worker.py
  - internal/verify-cups-paperless-upload.sh
findings:
  critical: 1
  warning: 6
  info: 2
  total: 9
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-09-28T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the `cups-pdf` → paperless-ngx upload feature (`upload-worker.py`, the `build_cups_pdf_*`/`build_paperless_postprocess_hook` additions in `generate_config.py`, the Dockerfile's `chmod 700` fix, and the associated docs/verify script) at standard depth.

The 3-file version sync (`config.yaml` 0.1.0-14 / `build.yaml` 0.1.0 / `README.md` v0.1.0) is correct, the D-07 disabled-by-default gating is implemented consistently on both the config-generation and worker sides, and `shlex.quote`/argv-array construction is used correctly everywhere user-controlled strings are embedded into generated shell scripts.

However, the retry/backoff state machine in `upload-worker.py` has a real robustness bug: `is_due()` is called **outside** the per-document `try/except` in the `processing/` polling loop, so a single malformed retry-state file becomes a poison pill that can silently stall the entire upload pipeline — directly contradicting this file's own stated per-document-isolation design goal. There are also several `config.get(key, default) or default` sites that silently discard a legitimately-configured `0` value, a sidecar-parsing path that can raise an uncaught exception despite being documented as "never raises," a missing uniqueness check between `paperless_upload.queue_name` and `printers[].name`, and a plausible silent-overwrite path in the outbox's `sent/`/`failed/` retention caused by CUPS job IDs resetting on every restart (a root cause this same phase's code already documents for the printer-UUID bug, but does not account for here).

The empirical "the token never appears in logs" claim (verified in `internal/verify-cups-paperless-upload.sh`) is real but narrower than it sounds — it only proves the token doesn't leak through the two tested response bodies, not that the response-body logging in `upload_document()` is safe in general.

## Critical Issues

### CR-01: `is_due()` runs outside per-document error isolation — one corrupted retry-state file can silently stall the entire upload queue

**File:** `cups/upload-worker.py:292-302`
**Issue:**

```python
for pdf_path in sorted(PROCESSING.glob("*.pdf")):
    # ...
    if not is_due(pdf_path):
        continue
    try:
        process_due_retry(pdf_path, config)
    except Exception as exc:  # noqa: BLE001 -- must never crash this loop
        print(f"WARNING: failed to retry {pdf_path.name}: {exc}", flush=True)
```

`is_due()` (`upload-worker.py:154-164`) calls `load_retry_state()`, which does no schema validation at all:

```python
def load_retry_state(pdf_path: Path) -> dict | None:
    ...
    try:
        return json.loads(state_path.read_text())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        ...
        return None
```

If a `*.retry.json` file happens to contain *valid JSON that is not a dict* (`null`, `[]`, `"x"`, a bare number — e.g. from disk corruption, an interrupted/partial third-party edit, or simply because the `processing/` directory is created `chmod 0o777` and is writable by any local process per `generate_config.py:1467-1472`), `json.loads()` succeeds and returns something other than a `dict`. `is_due()` then does:

```python
try:
    next_attempt_at = datetime.fromisoformat(state["next_attempt_at"])
except (KeyError, ValueError):
    return True
```

`state["next_attempt_at"]` on a `list`/`str`/`None`/`int` raises `TypeError`, which is **not** caught by `(KeyError, ValueError)`. Because this call happens *before* the `try:` block that wraps `process_due_retry(...)`, the `TypeError` propagates all the way out of `poll_once()` and is only caught by `main()`'s outer loop:

```python
while True:
    try:
        poll_once(config)
    except Exception as exc:
        print(f"WARNING: upload-worker poll cycle failed: {exc}", flush=True)
    time.sleep(POLL_INTERVAL_SECONDS)
```

The practical effect: `sorted(PROCESSING.glob("*.pdf"))` is deterministic, so every document that sorts *after* the poisoned file is silently skipped on **every single poll cycle forever** (not just the current one) — the malformed file is never fixed up, never routed to `failed/`, and never logged as the actual culprit (only a generic "poll cycle failed" line is emitted, with no filename). This directly contradicts the module's own stated architecture ("a `while True` poll loop wrapped in a broad `except Exception` **per document** so one malformed document never kills the loop for the rest" — module docstring, lines 6-9) and can indefinitely stall the whole outbox with a single bad file.

**Fix:** Move the `is_due()` call inside the same per-document `try/except`, and/or make `load_retry_state()`/`is_due()` defensively validate that the parsed value is a `dict` before indexing it:

```python
for pdf_path in sorted(PROCESSING.glob("*.pdf")):
    try:
        if not is_due(pdf_path):
            continue
        process_due_retry(pdf_path, config)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: failed to retry {pdf_path.name}: {exc}", flush=True)
```

and in `load_retry_state`:

```python
parsed = json.loads(state_path.read_text())
if not isinstance(parsed, dict):
    raise ValueError(f"retry state is not an object: {parsed!r}")
return parsed
```

## Warnings

### WR-01: `config.get(key, default) or default` silently discards a legitimately-configured `0`

**File:** `cups/upload-worker.py:176`, `cups/upload-worker.py:234-235`
**Issue:**

```python
timeout = int(config.get("timeout", 30) or 30)
...
retry_count = int(config.get("retry_count", 5) or 5)
retry_delay = int(config.get("retry_delay", 60) or 60)
```

`0` is falsy in Python, so an operator who explicitly sets `retry_count: 0` (fail fast, no retries) or `retry_delay: 0` (retry immediately, no backoff) has that explicit value silently replaced by the default (`5`/`60`) instead. `config.yaml`'s schema (`"int?"`, no min/max) permits `0` as a valid user-supplied value, so this is reachable, not just theoretical.

**Fix:** Use an explicit `None` check instead of `or`:

```python
raw_timeout = config.get("timeout")
timeout = int(raw_timeout) if raw_timeout is not None else 30
```

(repeat for `retry_count`/`retry_delay`).

### WR-02: `read_title()` can raise despite its own "never raises" contract

**File:** `cups/upload-worker.py:90-112`
**Issue:**

```python
def read_title(pdf_path: Path) -> str:
    """... Never raises, never skips the upload for a missing/malformed sidecar (D-13) ..."""
    sidecar_path = pdf_path.with_suffix(".json")
    title = None
    if sidecar_path.exists():
        try:
            title = json.loads(sidecar_path.read_text()).get("title")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            ...
```

If the sidecar file contains valid JSON that is not an object (`null`, `[]`, `"x"`, a number), `json.loads(...)` succeeds and `.get("title")` raises `AttributeError`/similar, which is **not** in the caught exception tuple. Because this specific caller path (`process_new_document`/`process_due_retry`) *is* wrapped by a per-document `try/except` in `poll_once`, this doesn't poison other documents (unlike CR-01), but it does silently break the documented "the upload must never be skipped just because a title could not be recovered" guarantee for that one document: the exception fires before any retry-state write, so the document is retried every ~20s indefinitely with no backoff and never reaches `sent/` or `failed/`.

**Fix:** Validate the parsed type before calling `.get()`:

```python
parsed = json.loads(sidecar_path.read_text())
title = parsed.get("title") if isinstance(parsed, dict) else None
```

### WR-03: No validation that `url`/`token` are set when `paperless_upload.enabled: true`

**File:** `cups/generate_config.py:782-844` (`build_cups_pdf_conf`), `cups/generate_config.py:913-988` (`build_cups_pdf_registration_snippet`)
**Issue:** Both functions gate only on `enabled` and `queue_name` validity. Neither checks that `upload.get("url")`/`upload.get("token")` are non-empty. If an operator flips `enabled: true` without setting `url`/`token` (an easy mistake — the DOCS/translation text says "when enabled, set url and token at minimum" but nothing enforces it), the queue is registered and `upload-worker.py` starts, then `upload_document()` builds a request against `""` + `/api/documents/post_document/"` (a schema-less relative URL), which fails with a generic `requests.RequestException`, gets retried per the normal backoff, and every document silently ends up in `failed/` with no actionable log message pointing at the actual root cause (missing config).

**Fix:** Add an explicit check in `build_cups_pdf_conf`/`build_cups_pdf_registration_snippet` (or a shared validation helper) that logs a clear `WARNING: paperless_upload.enabled is true but url/token is empty` and refuses to register the queue, mirroring the existing fail-safe-None-return pattern used for invalid `queue_name`.

### WR-04: No uniqueness check between `paperless_upload.queue_name` and `printers[].name`

**File:** `cups/generate_config.py:991-1109` (`build_printer_registration`), `cups/generate_config.py:913-988` (`build_cups_pdf_registration_snippet`), `cups/generate_config.py:1428-1433` (`main`)
**Issue:** `build_printer_registration()` validates each `printers[]` entry's `name` against `NAME_RE` in isolation; `build_cups_pdf_registration_snippet()` validates `queue_name` against the same `NAME_RE` in isolation. Nothing cross-checks the two. If an operator's `queue_name` (default `"PDF-to-DMS"`, but user-configurable) collides with an existing `printers[].name`, both `lpadmin -p <name> ...` calls target the *same* CUPS queue — the second call silently reconfigures the first printer's device URI to `cups-pdf:/`, breaking the physical printer. It also causes `registered_printer_names` (passed to `build_printer_uuid_fixup_script`) to contain the duplicate name twice, and the generated `fixups` dict literal (`generate_config.py:1237-1239`) silently keeps only the *last* of the two colliding `name: uuid` entries (ordinary Python dict-literal duplicate-key semantics), so one of the two printers' UUID stability fix is silently dropped.

**Fix:** Build the combined name set once (`printers[].name` ∪ `queue_name`) and warn+skip on any duplicate before generating either script.

### WR-05: Outbox `sent/`/`failed/` moves silently overwrite same-named files across add-on restarts

**File:** `cups/upload-worker.py:230`, `cups/upload-worker.py:238-240`
**Issue:**

```python
pdf_path.replace(SENT / pdf_path.name)
...
pdf_path.replace(FAILED / pdf_path.name)
if sidecar_path.exists():
    sidecar_path.replace(FAILED / sidecar_path.name)
```

`Path.replace()` silently overwrites an existing destination file (POSIX rename semantics) — there is no collision check. The PDF's filename uniqueness relies entirely on cups-pdf's `Label 2` `-job_<id>` suffix (`generate_config.py:802-806`), where `<id>` is cupsd's own job ID counter. This same file already documents, for the unrelated printer-UUID bug, that `/etc/cups/` is **not** persisted outside `/data` and that cupsd therefore starts every boot with completely fresh state (`generate_config.py:1112-1141`, `cups/DOCS.md:297-302`) — the same root cause applies to cupsd's job-ID counter and spool state (also not under `/data`), so job IDs restart from a low number after every add-on restart. `sent/` and `failed/` **are** under `/data` and therefore persist across restarts. Two documents with the same title printed in different container lifetimes can therefore generate the identical `<title>-job_<N>.pdf` filename, and the second `replace()` will silently destroy the first (already-uploaded, or still-pending-triage-in-`failed/`) retained copy with no warning logged.

**Fix:** Before the final `replace()`, check `destination.exists()` and disambiguate (e.g. append a timestamp/`os.getpid()` suffix) rather than relying solely on the per-lifetime job ID for uniqueness.

### WR-06: Upload response body is logged verbatim; the "token never leaks" verification does not generalize

**File:** `cups/upload-worker.py:195-208`, `internal/verify-cups-paperless-upload.sh:290-296,458-463`
**Issue:** Every upload attempt logs `response.text.strip()[:200]!r` on both success and failure paths, unconditionally. `internal/verify-cups-paperless-upload.sh` confirms the fixture token string never appears in `docker logs` — but it only exercises two specific stub response bodies (`{"task_id": "..."}` and `{"error": "stub forced failure"}`), neither of which ever contains the token. This proves the *tested* scenarios are safe, not that response-body logging is safe in general: a misconfigured/incompatible `url` (e.g. pointing at a reverse proxy, a WAF, or a paperless-ngx instance behind an auth gateway that emits a debug error page including the request's headers) could echo the `Authorization: Token <token>` header back in its response body, which would then be logged verbatim. The phase's own framing ("the executor claims this was verified empirically") overstates what the test actually proves.

**Fix:** Either scrub the logged response body of anything resembling `Token <token>`/the configured token value before logging, or narrow the log line to a fixed-size character class / truncate more aggressively and drop response body logging entirely for non-JSON content types. At minimum, document in `DOCS.md` that response-body logging is best-effort and not guaranteed secret-free against arbitrary upstream/proxy behavior.

## Info

### IN-01: Duplicated PPD-resolution shell-script generation between `build_brlaser_registration_snippet` and `build_cups_pdf_registration_snippet`

**File:** `cups/generate_config.py:703-779`, `cups/generate_config.py:913-988`
**Issue:** The two functions render nearly byte-identical shell (retry loop of up to 5×1s `lpinfo -m` calls, `grep -iF --` match, zero/multi-match warning-and-skip logic) differing only in variable names and the search term source (`driver_model` vs. the fixed `PAPERLESS_UPLOAD_PPD_SEARCH_TERM`). This is a maintenance risk — a future fix to the retry/match logic in one function is easy to forget in the other.
**Fix:** Factor the shared shell-template generation into one helper parameterized by `(search_term, lpadmin_argv_suffix, label)`.

### IN-02: `DOCS.md`'s "Migrating from f1c878cb_cups" section is a placeholder with no content

**File:** `cups/DOCS.md:345-347`
**Issue:**

```
## Migrating from f1c878cb_cups

See the rollout runbook — filled in by a later plan.
```

This ships in the live docs with no actual guidance and no link to said runbook — a user hitting this heading gets nothing actionable.
**Fix:** Either fill in the section before shipping this phase, or mark it clearly as `(TODO, tracked in <phase/issue>)` so readers don't mistake it for an oversight.

---

_Reviewed: 2026-09-28T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
