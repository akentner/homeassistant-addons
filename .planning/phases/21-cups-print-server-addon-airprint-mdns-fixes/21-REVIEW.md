---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
reviewed: 2026-10-03T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - cups/Dockerfile
  - cups/build.yaml
  - cups/config.yaml
  - cups/generate_config.py
  - cups/print-history-poller.py
  - cups/run.sh
  - cups/upload-worker.py
  - cups/translations/de.yaml
  - cups/translations/en.yaml
  - cups/DOCS.md
  - cups/README.md
  - internal/base-image-config.yaml
  - internal/cups-migration-suggestion.sh
  - internal/verify-cups-paperless-upload.sh
  - internal/verify-cups-scaffold.sh
  - README.md
findings:
  critical: 3
  warning: 10
  info: 7
  total: 20
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-10-03
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Reviewed the new `cups/` add-on (Dockerfile, run.sh, generate_config.py, the two background workers, config/translations/docs)
and the three `internal/` helper scripts. Checks run: `make validate-versions` and `make validate-addons` pass, shellcheck
(`-e SC1091 -e SC2034`) is clean for run.sh and all three internal scripts. I also confirmed against the real
`amd64-base:3.24` image that `cups-pdf-3.0.2-r0` ships exactly one PPD (`cups-pdf.ppd`), that its `Label 2` means a
tailing `-job_#`, and that `PostProcessing` is "called with user privileges" -- so the core design assumptions hold.

The weak spots are operational: the print-history poller silently stops recording after the first container recreation,
`run.sh` does not honour the "refuse to start" contract of `generate_config.py`, and the upload worker can upload a
truncated PDF or mark a document as "sent" when it was never uploaded. Several validators and two verify scripts are
weaker than they look (the UUID-stability test cannot fail).

## Critical Issues

### CR-01: Print history silently stops recording after a container recreation (job-id counter reset)

**File:** `cups/print-history-poller.py:137-145` (state in `/data`, see also `:83-102`)
**Issue:** `poll_once()` only records jobs with `job_id > last_seen_job_id`, and `last_seen_job_id` is persisted in
`/data`. cupsd's own job-id counter is NOT persisted (this add-on's own premise, see DOCS "Printer UUIDs are stable...":
`/etc/cups/` and `/var/cache/cups/` are rebuilt on every Supervisor start; `upload-worker.py:38` even acknowledges "cupsd's
own job-ID counter resets across a container restart"). After a restart the next jobs get ids 1, 2, 3... while the
persisted `last_seen_job_id` is, say, 57. Every new job is `<= 57`, so nothing is recorded until the counter climbs past the
old maximum. The feature fails silently and indefinitely, with no log line.
**Fix:** Detect the reset and rebase. E.g. in `poll_once`:
```python
if jobs:
    current_max = max(j[1] for j in jobs)
    if current_max < last_seen_job_id:
        print(f"INFO: job-id counter reset detected ({current_max} < {last_seen_job_id}) -- rebasing", flush=True)
        last_seen_job_id = 0
        save_last_seen_job_id(0)
```
(also handle the empty-listing case by comparing against a persisted boot/start marker, or persist
`/var/cache/cups/job.cache` instead).

### CR-02: run.sh ignores a failed `generate_config.py`, so "Refusing to start" is not honoured

**File:** `cups/run.sh:12` (contract in `cups/generate_config.py:655-666`)
**Issue:** `build_avahi_conf()` calls `sys.exit(1)` on an invalid `avahi_hostname` and its docstring says refusing to start
is safer than writing an unsafe config. `run.sh` has no `set -e` and does not check the exit status of
`python3 /generate_config.py`, so the add-on carries on: avahi starts with the stock config (container hostname, no
`allow-interfaces`, i.e. exactly the rename-loop bug this add-on exists to fix), cupsd starts un-patched/localhost-only, no
printers are registered, `/tmp/cups-log-level.env` does not exist (`. /tmp/cups-log-level.env` at line 137 fails, then
`cupsctl LogLevel=""` is retried 5x). The same happens for any uncaught exception in generate_config (bad JSON in
options.json, unwritable path). The user sees a "running" add-on that does nothing useful.
**Fix:**
```sh
python3 /generate_config.py || { log "generate_config.py failed -- refusing to start"; exit 1; }
```

### CR-03: Upload worker can upload a truncated PDF (and never the sidecar title)

**File:** `cups/upload-worker.py:343-345`, `:318-329`
**Issue:** `poll_once` globs `INCOMING/*.pdf` and immediately renames each match into `processing/` and uploads it. cups-pdf
writes the final file directly via ghostscript (`-sOutputFile=<final path>`), then runs the `PostProcessing` hook (which
writes the `.json` title sidecar) afterwards. Nothing prevents the 20-second poll from landing while ghostscript is still
writing (a few seconds for a multi-page job, i.e. a double-digit percentage of jobs) or between PDF completion and sidecar
creation. Consequences: (a) a partial PDF is POSTed, paperless-ngx returns 2xx (it accepts the task and fails later), and
the document is moved to `sent/` -- it is never retried; (b) the sidecar arrives after the PDF was moved, so the title
silently falls back to `Scan_<timestamp>` and the late sidecar is orphaned in `incoming/` forever.
**Fix:** Only pick up files that are stable. Minimum: skip PDFs whose mtime is younger than a few poll-seconds
(`time.time() - pdf.stat().st_mtime < 5`) and wait for the sidecar for a short grace window (or treat "sidecar missing and
PDF younger than ~10s" as not-ready). Better: have the hook write a `.ready` marker last and key pickup on it.

## Warnings

### WR-01: Plaintext admin password written to a world-readable script and never removed

**File:** `cups/generate_config.py:1373-1407` (written at `:1448-1451`, mode 0755)
**Issue:** `/tmp/provision-admin.sh` embeds `shlex.quote(password)` and is `chmod 0o755` and left on disk for the whole
container lifetime. cupsd runs print filters/backends as the unprivileged `lp` user and cups-pdf hooks as `nobody`; any of
them (e.g. a compromised filter parsing a hostile print job) can read the `lpadmin`-group admin credential. The docs
promise the password is "never written to logs" but not that it is kept off disk.
**Fix:** `admin_script_path.chmod(0o700)` (root-only) and have `run.sh` `rm -f /tmp/provision-admin.sh` right after
executing it. Same hardening is advisable for `/tmp/register-printers.sh` only if it ever carries secrets (it does not today).

### WR-02: A redirecting paperless-ngx URL turns a failed upload into a "success"

**File:** `cups/upload-worker.py:234-261`
**Issue:** `requests.post()` follows redirects by default. A typical `http://paperless:8000` -> `https://` 301/302
converts the POST into a GET; the target answers 200 (HTML), `upload_document` logs "uploaded" and returns True, and the PDF
is moved to `sent/`. Nothing reached paperless-ngx and nothing is retried. The `Authorization` header is also dropped on a
cross-host redirect.
**Fix:** `requests.post(..., allow_redirects=False)` and treat any non-2xx (including 3xx) as failure, logging the
`Location` so the operator can fix `url`.

### WR-03: Numeric options are unbounded and unvalidated; `url`/`token` are never checked at startup

**File:** `cups/config.yaml:63-65`; `cups/upload-worker.py:227-229, 287-288`; `cups/generate_config.py:1462-1465`
**Issue:** `timeout`, `retry_count`, `retry_delay` are plain `int?`. A negative `timeout` makes `requests` raise a plain
`ValueError`, which is NOT a `requests.RequestException`, so it escapes `upload_document`, `attempt_and_route` never records
state, and the document is re-attempted every 20 s forever with a WARNING each cycle. `0` is silently replaced by the
default through `x or default`. With `paperless_upload.enabled: true` and an empty `url`/`token`, `requests` raises
`MissingSchema` (a RequestException) and every document burns through its retries (~5 min) and lands in `failed/` with only
a log line -- nothing warns at startup that the feature is unusable.
**Fix:** Constrain the schema (`timeout: "int(1,)?"`, `retry_count: "int(1,)?"`, `retry_delay: "int(1,)?"`), catch
`Exception` (or `(requests.RequestException, ValueError)`) in `upload_document`, and in `generate_config.py` print a WARNING
when `enabled` is true but `url` or `token` is empty / `url` lacks an `http(s)://` scheme.

### WR-04: `$`-anchored validation regexes accept a trailing newline

**File:** `cups/generate_config.py:109, 121, 192, 225, 243` (used with `.match`)
**Issue:** In Python `^...$` matches before a trailing `\n`, so `NAME_RE.match("cups\n")` is truthy (verified).
`avahi_hostname`, `queue_name` (never `.strip()`ped), and `admin_username` can therefore carry a newline into a generated
file/argv. It does not allow multi-line directive injection (only one trailing `\n` is possible) but it defeats the stated
"newline-injection closed" guarantee and produces a bad `host-name=` / `lpadmin -p 'name\n'` that fails at runtime. The
printer-name case is made worse by WR-09 (one failing `lpadmin` aborts the whole script).
**Fix:** Use `.fullmatch()` (or `\Z`) for every one of these patterns.

### WR-05: `NAME_RE` is used as the CUPS queue-name charset but rejects underscores (and the migration script feeds it such names)

**File:** `cups/generate_config.py:105-109, 1032-1037`; `internal/cups-migration-suggestion.sh:74-83`
**Issue:** The comment claims NAME_RE "matches lpadmin's own accepted queue-name charset". It does not: CUPS accepts
underscores and most other printable characters (everything except space, `/`, `#`, TAB). Underscore-named queues
(`Brother_MFC_7460DN`, `HP_LaserJet`) are the norm. The regex was designed for avahi host-names (no underscores) and is
reused for `printers[].name` and `paperless_upload.queue_name`, so such printers are skipped with a WARNING. The migration
helper prints whatever `lpstat -v` reports without any validation, so the suggested snippet can contain entries the new
add-on will drop.
**Fix:** Introduce a separate `PRINTER_NAME_RE = r"[A-Za-z0-9_-]{1,127}"` (fullmatch) for queue names, keep `NAME_RE` for
the avahi hostname, and have the migration script flag/rename names that do not match.

### WR-06: Print history misses jobs that complete out of id order (multi-printer setups)

**File:** `cups/print-history-poller.py:137-145`
**Issue:** The cursor is "highest id seen". Job ids are global across printers; job 5 on a slow/queued printer can complete
after job 6 on a fast one. Once 6 is recorded, 5 is `<= last_seen` and is never recorded. The add-on explicitly supports
multiple printers.
**Fix:** Track the set of already-recorded ids (persisted, pruned to ids still present in the `lpstat` listing) instead of a
max cursor.

### WR-07: UUID-stability test in verify-cups-scaffold.sh cannot fail

**File:** `internal/verify-cups-scaffold.sh:447-448` (and the surrounding block `:424-534`)
**Issue:** The comment says `docker restart` "reproduces the original bug path". It does not: `docker restart` keeps the
container's writable layer, so `/etc/cups/printers.conf` (with its UUID) survives and the UUID is unchanged even if the
whole fixup mechanism were deleted. The bug is triggered by Supervisor re-creating the container. The test passes
vacuously and gives false confidence in D-08.
**Fix:** `docker stop` + `docker rm` + `docker run` again with the same `-v ${DATA_DIR}:/data`, and additionally assert the
UUID equals `uuid.uuid5(PRINTER_UUID_NAMESPACE, name)`.

### WR-08: paperless verify script's title/sidecar assertions are satisfied by the failure path

**File:** `internal/verify-cups-paperless-upload.sh:273-283, 446-451`
**Issue:** The "title form field is non-empty" check also passes for the `Scan_<timestamp>` fallback, so a broken
PostProcessing hook / title recovery (CR-03 scenario b) passes. The sidecar-in-`failed/` check degrades to a yellow NOTE
(never sets `FAIL=1`). The happy path prints a job titled "Happy Path Title" but never asserts the recovered title
(`Happy_Path_Title` or similar).
**Fix:** Assert the stub received a title that contains `Happy` and does not start with `Scan_`; make the sidecar check a
hard FAIL.

### WR-09: One failing `lpadmin` aborts registration of every later printer and the cups-pdf queue

**File:** `cups/generate_config.py:1016` (`set -e`), `:1100-1106`; `cups/run.sh:70-80`
**Issue:** The generated `register-printers.sh` starts with `set -e`; `lpadmin` rejecting one entry (malformed URI that
passes the scheme allowlist, `http` scheme, a trailing-newline name per WR-04, etc.) exits the script, the rest of the
printers and the paperless queue are never registered, and `run.sh` just re-runs the same failing script 5 times.
**Fix:** Drop `set -e` for the per-printer calls and use `lpadmin ... || echo "WARNING: registration of <name> failed" >&2`
per entry, returning non-zero at the end only if you still want run.sh's retry.

### WR-10: Root upload worker follows symlinks inside a world-writable (0777) outbox

**File:** `cups/generate_config.py:1467-1472`; `cups/upload-worker.py:233, 283, 325`
**Issue:** The stage directories are `0o777` and the worker runs as root. Any local unprivileged process (cups filters run
as `lp`, cups-pdf hooks as `nobody`) can drop `incoming/x.pdf -> /data/options.json`; the worker then uploads the file (token
and admin password included) to the configured paperless-ngx instance and moves/replaces entries as root.
**Fix:** `if pdf_path.is_symlink() or not pdf_path.is_file(): continue` (and the same for sidecars) before processing;
open with `os.open(..., O_NOFOLLOW)`. Consider `1777` (sticky) instead of `0777` so unprivileged users cannot rename/delete
each other's files.

## Info

### IN-01: Docs disagree with code

**File:** `cups/DOCS.md:141-142, 35-37`
**Issue:** DOCS says the sidecar/retry-state files "move" to `sent/` on success; `upload-worker.py:279-282` deletes both.
DOCS lists supported URI schemes as `ipp, ipps, socket, usb, dnssd, lpd`; `ALLOWED_URI_SCHEMES`
(`generate_config.py:112`) also allows `http`.
**Fix:** Align docs with code (or vice versa).

### IN-02: Duplicated registration snippet builders and doubled warnings

**File:** `cups/generate_config.py:703-779, 913-988, 782-844`
**Issue:** `build_brlaser_registration_snippet` and `build_cups_pdf_registration_snippet` are ~25 near-identical lines of shell
generation; `build_cups_pdf_conf` and `build_cups_pdf_registration_snippet` both re-validate `queue_name`, so an invalid
value logs the same WARNING twice. If `queue_name` equals a `printers[].name` the cups-pdf queue silently overwrites the
physical printer's registration. The file is also ~1480 lines with docstrings several times larger than the code.
**Fix:** Extract one `_ppd_lookup_register_snippet(search_term, name, uri, location)`; validate `paperless_upload` once in a
helper; reject a `queue_name` that collides with a configured printer name.

### IN-03: `usb://` URIs are accepted/documented but the add-on cannot reach USB devices

**File:** `cups/config.yaml` (no `usb: true`), `cups/DOCS.md:49-51`
**Issue:** HA only passes `/dev/bus/usb` into add-ons that declare `usb: true`. The `usb` scheme is allowlisted and has a
docs example, but a registered USB queue could never print.
**Fix:** Add `usb: true` (and `udev: true` if needed) or drop `usb` from the allowlist/docs.

### IN-04: Line-length / lint

**File:** `cups/run.sh:198` (274 chars), `internal/cups-migration-suggestion.sh:52, 88` (122 chars)
**Issue:** Violates the repo's 120-char convention. ruff (default+strict probe) also flags `subprocess.run` without
`check=False` (`print-history-poller.py:53`).
**Fix:** Wrap the trap into a `cleanup()` function; shorten the two strings.

### IN-05: Nested option translations may not be applied

**File:** `cups/translations/en.yaml:33-73`, `cups/translations/de.yaml:35-77`
**Issue:** `enabled`, `queue_name`, ... are nested directly under `paperless_upload:` next to its `name`/`description`.
Supervisor/frontend add-on translations are keyed per top-level option; I could not confirm nested field support and no
other add-on in this repo uses it (unverified, check in the HA UI). `printers[]` sub-fields have no translations at all.
**Fix:** Verify rendering in the HA add-on config page; if unsupported, fold the field help into the parent `description`.

### IN-06: Migration helper silently downgrades printers and has a pipefail/SIGPIPE edge

**File:** `internal/cups-migration-suggestion.sh:52, 74-83`
**Issue:** Only `{name, uri, enabled}` are emitted: `location` and `driver: brlaser` are lost, so migrating a socket-attached
Brother printer reintroduces the endless-blank-pages bug unless the user reads the docs. Line 52 pipes `grep | head -1`
under `set -o pipefail` with `|| CONTAINER=""`; when more than one container matches, grep can get SIGPIPE, the pipeline
returns non-zero and a valid result is discarded. URIs containing `"` or `\` would break the emitted YAML.
**Fix:** Print a trailing comment reminding about `driver`/`driver_model` for `socket://` URIs, use `grep -m1 -F`, and emit
YAML-escaped values.

### IN-07: Operational edge cases in run.sh / cupsd scoping

**File:** `cups/run.sh:46-198`, `cups/generate_config.py:580`, `cups/generate_config.py:1226-1235`
**Issue:** (a) The TERM/INT trap is only installed at step 12; as PID 1 the script ignores SIGTERM during boot (which now
includes the whole stop/patch/restart fixup cycle), so `docker stop`/Supervisor stop waits for the SIGKILL timeout.
(b) `Listen <ip>:631` is bound to the IP seen at start; a DHCP change leaves cupsd unreachable until restart.
(c) `/admin` uses Basic auth over plain HTTP on the LAN (`DefaultEncryption` is not changed), so the admin password is
sent in clear text; DOCS mentions LAN reachability but not this.
**Fix:** Install the trap right after step 1; document (b)/(c) or add `Listen` on the loopback + `DefaultEncryption Required`
for `/admin`.

---

_Reviewed: 2026-10-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
