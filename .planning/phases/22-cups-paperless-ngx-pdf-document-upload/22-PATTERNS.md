# Phase 22: cups-paperless-ngx-pdf-document-upload - Pattern Map

**Mapped:** 2026-09-28
**Files analyzed:** 6 (all modifications within existing `cups/` add-on; no new files at top level except the
generated-at-runtime `cups-pdf.conf` / `PostProcessing` hook, which follow the existing generate-then-execute split)
**Analogs found:** 6 / 6 (all analogs are same-file precedents already inside `cups/`)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `cups/upload-worker.py` (new) | service (background worker) | event-driven / file-I/O (outbox polling + HTTP POST) | `cups/print-history-poller.py` | exact (structural precedent named explicitly in CONTEXT.md) |
| `cups/config.yaml` (modified — add `paperless_upload` block) | config | CRUD (options schema) | `cups/config.yaml` itself — `admin_username`/`admin_password` pair as `password?`-schema precedent | exact |
| `cups/generate_config.py` (modified — add `build_cups_pdf_conf()` + PostProcessing hook renderer) | config/utility (generator) | transform (options.json → rendered config/script files) | `build_admin_provisioning()` (lines 1054-1173) and `build_printer_registration()`/`build_brlaser_registration_snippet()` (lines 678-877) in the same file | exact |
| `cups/run.sh` (modified — launch worker, extend UUID fixup, execute new generated files) | orchestration/utility (entrypoint) | event-driven (sequenced startup steps) | itself — step 11 (`print-history-poller.py &`) and step 8 (UUID fixup) | exact |
| `cups/Dockerfile` (modified — add `cups-pdf`, `py3-requests` to `apk add`; `COPY` new script) | config (build) | batch (image build) | itself — existing `apk add` block + `COPY run.sh generate_config.py print-history-poller.py /` | exact |
| `cups/DOCS.md` (modified — document `paperless_upload` options) | docs | — | itself — existing options documentation sections | exact |

## Pattern Assignments

### `cups/upload-worker.py` (new background worker)

**Analog:** `cups/print-history-poller.py` (whole file, 180 lines)

**Module docstring / limitations-disclosure pattern** (lines 1-23):
```python
"""Poll cupsd for newly-completed print jobs and append one JSONL record
per job to /data/print-history.jsonl.

Deliberately lightweight (a periodic ... poll, NOT a ... listener, which
would be disproportionate for a single-printer home setup). State ... is
persisted to /data/print-history-state.json so a restart never replays
already-recorded jobs.
...
"""
```
Copy this shape: open with a one-paragraph "why this design, why not the fancier alternative" justification, then
document any known limitations up front (mirrors D-11/D-12/D-15's fallback and visibility behavior for the new
worker — document the sidecar-title fallback and the single-WARNING-per-failure behavior in the new worker's own
docstring the same way).

**Imports** (lines 25-31):
```python
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
```
New worker additionally needs `requests` (D-01) and likely `shutil` (moving files between outbox stages) — add to
this same import block, same ordering convention (stdlib alphabetical, then third-party).

**Atomic state/file persistence pattern** (lines 96-102):
```python
def save_last_seen_job_id(job_id: int) -> None:
    """Atomically persist `job_id` -- write to a temp file then rename, so
    a container killed mid-write never leaves a half-written state file
    behind."""
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps({"last_seen_job_id": job_id}))
    tmp_path.replace(STATE_PATH)
```
Apply this exact temp-file + `.replace()` idiom for: (a) moving a PDF+sidecar pair between outbox stages
(`incoming/` → `processing/` → `sent/`/`failed/` — use `Path.replace()` for the move itself, which is atomic within
the same filesystem/mount), and (b) any worker-side state file (e.g. retry-count-per-document bookkeeping) that
must survive a mid-write kill.

**Never-crash polling loop pattern** (lines 163-176):
```python
def main() -> None:
    last_seen_job_id = load_last_seen_job_id()
    while last_seen_job_id is None:
        last_seen_job_id = establish_baseline()
        if last_seen_job_id is None:
            time.sleep(POLL_INTERVAL_SECONDS)

    while True:
        try:
            last_seen_job_id = poll_once(last_seen_job_id)
        except Exception as exc:  # noqa: BLE001 -- must never crash this loop
            print(f"WARNING: print-history poll cycle failed: {exc}", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
```
Copy verbatim shape for the upload worker's main loop: scan `incoming/`, move each found doc to `processing/`,
attempt upload with `requests`, on success delete sidecar + move to `sent/` (or delete outright per D-15's
"never delete a failed doc" — sent/ retention policy is Claude's discretion during planning), on exhausted
retries move to `failed/` and emit exactly one `print(f"WARNING: ...", flush=True)` line (matches D-15).
`except Exception` must wrap the whole per-document handling cycle, not just the HTTP call, so one malformed
sidecar/PDF never kills the loop for every other queued document.

**Logging convention** (used throughout, e.g. lines 140, 159, 174):
```python
print(f"INFO: recorded completed job {printer}-{job_id} (user={user})", flush=True)
print(f"WARNING: lpstat invocation failed: {exc}", flush=True)
```
`print(..., flush=True)` with an `INFO:`/`WARNING:` prefix is this add-on's entire logging convention (no logging
module, no structured logging) — background processes' stdout is not redirected in `run.sh`, so this reaches
`docker logs`/`ha apps logs` automatically (per CONTEXT.md's Reusable Assets note). Use identically in the new
worker: `INFO:` for each successful upload, `WARNING:` for the one-line-per-exhausted-failure per D-15.

**Sidecar/title read pattern (new — no direct analog, compose from the atomic-write idiom above):**
```python
# Read the PostProcessing hook's best-effort sidecar; never fail the upload
# just because the sidecar is missing or malformed (D-11/D-13).
sidecar_path = pdf_path.with_suffix(".json")
title = None
if sidecar_path.exists():
    try:
        title = json.loads(sidecar_path.read_text()).get("title")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"WARNING: could not read sidecar {sidecar_path}: {exc} -- falling back to timestamp title", flush=True)
if not title:
    title = f"Scan_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
```
This mirrors `load_last_seen_job_id()`'s try/except-and-degrade-gracefully shape (lines 83-93) applied to a
different file.

---

### `cups/config.yaml` (add `paperless_upload` block)

**Analog:** existing `admin_username`/`admin_password` pair (same file, lines 28-29 options / 38-39 schema)

**Options defaults pattern** (lines 23-31):
```yaml
options:
  ...
  admin_username: ""
  admin_password: ""
  printers: []
  log_level: "warning"
```

**Schema pattern, including `password?` type** (lines 33-47):
```yaml
schema:
  ...
  admin_username: "str?"
  admin_password: "password?"
  printers:
    - name: str
      uri: str
      enabled: bool?
      location: str?
      driver: "list(generic|brlaser)?"
      driver_model: str?
  log_level: "list(debug|info|warning|error)?"
```
Apply directly to D-06's dedicated top-level `paperless_upload` block:
```yaml
options:
  paperless_upload:
    enabled: false
    queue_name: "PDF-to-DMS"
    location: ""
    url: ""
    token: ""
    timeout: 30
    retry_count: 5
    retry_delay: 60
schema:
  paperless_upload:
    enabled: "bool?"
    queue_name: "str?"
    location: "str?"
    url: "str?"
    token: "password?"
    timeout: "int?"
    retry_count: "int?"
    retry_delay: "int?"
```
Note the nested-object schema shape already used for `printers[]`'s list-of-objects (lines 40-46) confirms HA's
schema supports nested dict blocks like `paperless_upload` directly (not just lists) — no precedent risk here.

---

### `cups/generate_config.py` (add `build_cups_pdf_conf()` + PostProcessing hook renderer + registration wiring)

**Analog A — options validation + fail-safe-None-return pattern:** `build_admin_provisioning()` (lines 1054-1173)

**Core shape to copy** (lines 1093-1128, abbreviated):
```python
def build_cups_pdf_conf(options: dict) -> str | None:
    """... Returns None (writing nothing) when paperless_upload.enabled is
    false (D-07) -- generate_config.py never registers the queue, no
    cups-pdf.conf is generated, nothing appears via Avahi."""
    upload = options.get("paperless_upload") or {}
    enabled = bool(upload.get("enabled", False))
    if not enabled:
        return None

    queue_name = str(upload.get("queue_name", "PDF-to-DMS") or "PDF-to-DMS")
    if not NAME_RE.match(queue_name):
        print(
            f"WARNING: paperless_upload.queue_name {queue_name!r} failed validation -- must "
            f"match {NAME_RE.pattern}, cups-pdf queue not registered",
            flush=True,
        )
        return None
    # ... shlex.quote every value before embedding in any generated shell/conf text (T-21-01 mitigation)
```
Reuses the file's own `NAME_RE` (printer-name validation, referenced at line 798) — do not invent a new regex for
`queue_name`; it must satisfy the same constraint `lpadmin -p` accepts.

**Analog B — deferred-to-runtime-script pattern (PPD/model resolution deferred into generated shell):**
`build_brlaser_registration_snippet()` (lines 678-754) — the exact same reason applies to cups-pdf: its own
`CUPS-PDF.ppd` is registered via `lpadmin -m` against a live cupsd, so the queue-registration call belongs in
`/tmp/register-printers.sh` (extend `build_printer_registration()`, lines 757-877) or a small addition alongside
it — not resolved in Python at generate time, before cupsd exists.

**Analog C — validated, quoted registration entry loop:** `build_printer_registration()` (lines 757-877) — the
new `cups-pdf` queue's registration (with `location` from D-04) should be appended into the *same*
`register-printers.sh` this function already builds (or a second script executed right after it), reusing the
existing `location`-validation branch (lines 814-821) verbatim for `paperless_upload.location`.

**Analog D — secret handling convention:** `.planning/phases/20-litellm-addon/20-CONTEXT.md` D-11/D-12/D-25
(persistent-secret-file pattern) — apply the same `password?`-schema handling already used for `admin_password` in
this very file (never echoed to logs, `shlex.quote`'d before any shell embedding) to `paperless_upload.token`,
which the worker reads directly from `/data/options.json` (no need to persist it separately — the worker can call
its own `load_options()`-equivalent, mirroring `load_options()` at line 619).

**PostProcessing hook script (new — model after `build_brlaser_registration_snippet`'s "render a small standalone
script for later execution" shape, lines 726-754):** a short POSIX-`sh` (or `python3 -c`) script assigned as
cups-pdf's `PostProcessing` command in the generated `cups-pdf.conf`, invoked by cupsd with the job's title in an
environment variable; writes the sidecar JSON best-effort (never non-zero-exits — D-13: must not block/fail
printing).

---

### `cups/run.sh` (launch worker, extend UUID fixup, execute new generated artifacts)

**Analog:** step 11's background-launch + step 12's trap (lines 170-186) and step 8's "extend an existing list"
UUID fixup (lines 82-127, esp. the `registered_names` list already flowing from `generate_config.py` into
`fixup-printer-uuids.sh`)

**Background worker launch pattern** (lines 170-177):
```sh
# 11. Background: poll cupsd for newly-completed print jobs and persist a
#     simple JSONL history to /data/print-history.jsonl (see
#     print-history-poller.py's own module docstring ...).
python3 /print-history-poller.py &
PRINT_HISTORY_POLLER_PID=$!
```
Add an identical step (e.g. step 11b) for the new worker:
```sh
python3 /upload-worker.py &
UPLOAD_WORKER_PID=$!
```

**Shutdown trap pattern** (line 185):
```sh
trap 'kill -TERM "$CUPSD_PID" 2>/dev/null; kill -TERM "$ERROR_LOG_TAIL_PID" 2>/dev/null; [ -n "$ACCESS_LOG_TAIL_PID" ] && kill -TERM "$ACCESS_LOG_TAIL_PID" 2>/dev/null; kill -TERM "$PRINT_HISTORY_POLLER_PID" 2>/dev/null' TERM INT
```
Extend to also `kill -TERM "$UPLOAD_WORKER_PID" 2>/dev/null`.

**UUID-fixup extension (D-08):** the fixup already operates on a `registered_names` list built once in
`generate_config.py` (returned from `build_printer_registration()`, line 757, consumed at line 1200's
`build_printer_uuid_fixup_script(registered_printer_names)`) — D-08 just requires the cups-pdf queue's name to be
appended into that same list when registered, no new `run.sh` logic needed at all; `run.sh`'s step 8 (lines
82-127) is already generic over "every registered printer" and requires zero changes.

---

### `cups/Dockerfile` (add packages + COPY new script)

**Analog:** existing `apk add` block (lines 22-29) and its per-package justification-comment convention (lines
5-21), plus the `COPY` line (line 38)

```dockerfile
RUN apk add --no-cache \
    cups \
    cups-filters \
    avahi \
    avahi-tools \
    dbus \
    python3 \
    brlaser
...
COPY run.sh generate_config.py print-history-poller.py /
```
Add `cups-pdf` and `py3-requests` to the `apk add` list (confirmed present in the 3.24 repos per CONTEXT.md), with
a comment block matching the existing per-package justification style (see `brlaser`'s comment, lines 10-21, as
the template — cite package name, version, why it's needed, and which option gates its use). Add
`upload-worker.py` to the `COPY` line alongside the other two Python scripts.

---

## Shared Patterns

### Logging convention (applies to all new Python code)
**Source:** `cups/print-history-poller.py` (throughout, e.g. lines 60, 140, 159, 174)
```python
print(f"INFO: recorded completed job {printer}-{job_id} (user={user})", flush=True)
print(f"WARNING: lpstat invocation failed: {exc}", flush=True)
```
No logging module anywhere in this add-on — plain `print(..., flush=True)` with an `INFO:`/`WARNING:` string
prefix is the entire convention. Apply identically in `upload-worker.py` and in any new `generate_config.py`
functions.

### Atomic file writes / moves
**Source:** `cups/print-history-poller.py:96-102` (`save_last_seen_job_id`)
```python
tmp_path = STATE_PATH.with_suffix(".tmp")
tmp_path.write_text(json.dumps({"last_seen_job_id": job_id}))
tmp_path.replace(STATE_PATH)
```
Apply to: worker state persistence, and to moving PDF+sidecar pairs between outbox stage directories.

### Shell-injection-safe generation (T-21-01 mitigation)
**Source:** `cups/generate_config.py` — `build_printer_registration()` (lines 785-877), `build_admin_provisioning()`
(lines 1130-1131)
```python
quoted_user = shlex.quote(username)
quoted_pass = shlex.quote(password)
```
Every value from `options.json` that gets embedded into a generated shell script or `.conf` file must be
`shlex.quote()`'d (or validated against a strict regex like `NAME_RE`/`LOCATION_RE` first) — never raw
f-string-interpolated. Apply to `queue_name`, `location`, and any embedded env values in the PostProcessing hook.

### Fail-safe default (feature fully off unless explicitly enabled)
**Source:** `cups/generate_config.py` — `build_admin_provisioning()` returning `None` when unset (lines 1096-1097)
```python
if not username and not password:
    return None
```
Directly matches D-07's requirement: `build_cups_pdf_conf()` must return `None`/write nothing when
`paperless_upload.enabled` is false, so existing installs see zero change.

### Generate-then-execute split
**Source:** `cups/run.sh` step 1 (`python3 /generate_config.py`) executing scripts rendered by
`cups/generate_config.py`'s `main()` (lines 1176 onward: writes `/tmp/register-printers.sh`,
`/tmp/provision-admin.sh`, `/tmp/fixup-printer-uuids.sh`, `/tmp/cups-log-level.env`), each later `sh`-executed (or
sourced) by `run.sh` only once cupsd is confirmed ready. Any file requiring a live cupsd (queue registration,
PPD resolution) must follow this same split — never executed directly inside `generate_config.py`.

## No Analog Found

None — every file in scope for this phase is a modification of, or a structurally-identical new sibling to, an
existing file already inside `cups/`; CONTEXT.md's canonical_refs explicitly names the direct precedent for each.

## Metadata

**Analog search scope:** `cups/` add-on directory only (single add-on modified this phase; no cross-add-on search
needed — CONTEXT.md's canonical_refs already named every relevant file).
**Files scanned:** `cups/config.yaml`, `cups/run.sh`, `cups/generate_config.py` (1220 lines, targeted reads of
lines 678-877 and 1054-1220), `cups/print-history-poller.py` (180 lines, read whole), `cups/Dockerfile`,
`cups/DOCS.md` (existence confirmed, not deep-read — its structure is a docs precedent, not a code pattern).
**Pattern extraction date:** 2026-09-28
