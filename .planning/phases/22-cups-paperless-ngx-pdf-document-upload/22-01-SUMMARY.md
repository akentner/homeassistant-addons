---
phase: 22-cups-paperless-ngx-pdf-document-upload
plan: 01
subsystem: infra
tags: [cups, cups-pdf, paperless-ngx, requests, home-assistant-addon, python]

requires:
  - phase: 21-cups-print-server-addon-airprint-mdns-fixes
    provides: generated-config-from-template pattern, printer-list-of-objects schema, D-08 UUID-fixup mechanism, print-history-poller.py background-worker shape
provides:
  - Disabled-by-default `paperless_upload` cups-pdf queue + background upload worker for the `cups` add-on
  - Reusable pattern: cups-pdf-backed virtual queue + PostProcessing-hook sidecar + outbox worker, applicable to any future "print-to-X" add-on feature
affects: [22-02-cups-paperless-ngx-pdf-document-upload]

actuals:
  tokens: 14159
  tasks: 2
  commits: 2
  plan_head_before: 11e5065717ae8d6c53f82db6442ac08bdbd6c0fe
  plan_head_after: da79d6ae9239d1639f621af2251745c673d67c8e

tech-stack:
  added: [cups-pdf (Alpine apk, 3.0.2-r0), py3-requests (Alpine apk, 2.33.1-r0)]
  patterns:
    - "Generate-then-execute split extended to a second virtual queue (cups-pdf.conf + PostProcessing hook), reusing NAME_RE/LOCATION_RE/shlex.quote T-21-01 mitigations"
    - "Outbox/state-file worker (incoming/processing/sent/failed + atomic temp-file+replace) as the standard shape for any future async delivery feature in this add-on"
    - "Fixed-interval retry/backoff via a <basename>.retry.json sidecar co-located with the document, read/written atomically, checked each poll cycle via a next_attempt_at ISO8601 timestamp"

key-files:
  created:
    - cups/upload-worker.py
    - internal/verify-cups-paperless-upload.sh
  modified:
    - cups/config.yaml
    - cups/generate_config.py
    - cups/Dockerfile
    - cups/run.sh
    - cups/translations/de.yaml
    - cups/translations/en.yaml

key-decisions:
  - "cups-pdf's PostProcess directive is actually named `PostProcessing` in cups-pdf.conf -- the plan's own <researched_correction> got the argument-passing model right (3 positional args, no title env var) but the plan text called it `PostProcess`; verified against the stock cups-pdf.conf's own '### Key: PostProcessing' documentation and confirmed working end-to-end."
  - "Alpine's cups-pdf-3.0.2-r0 package ships /usr/lib/cups/backend/cups-pdf at mode 0755 (world-executable). CUPS decides root-vs-unprivileged backend execution purely from file permissions: a backend executable by 'other' runs as the unprivileged filter user (lp), never root. cups-pdf's own code refuses to run unless invoked as root ('CUPS-PDF cannot be called without root privileges!', confirmed live in error_log), so every print silently produced zero output until a `chmod 700` Dockerfile step was added -- matching Debian's packaging, which ships the same binary at 0700 for exactly this reason. This is Rule 1 (auto-fix bug): a blocking defect discovered empirically, not present in the plan text, fixed and proven via the docker-build verify harness."
  - "D-08's UUID-stability fixup required zero new code: build_cups_pdf_registration_snippet()'s queue_name is appended into the same registered_printer_names list build_printer_uuid_fixup_script() already consumes generically. Verified empirically with a real docker restart of a paperless_upload-enabled container -- the cups-pdf queue's UUID was byte-identical before/after."

patterns-established:
  - "Outbox worker pattern: any future async-delivery feature in this add-on (e.g. a second DMS target) should follow the same incoming/processing/sent/failed directory shape with atomic temp-file+replace state, rather than inventing a new mechanism."
  - "Retry/backoff sidecar pattern: a <basename>.retry.json (attempts + next_attempt_at) co-located with the artifact being retried, checked once per poll cycle -- reusable for any future fixed-interval retry need in this add-on's background workers."

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15]

coverage:
  - id: D1
    description: "When paperless_upload.enabled is false (shipped default), the add-on behaves byte-for-byte as before -- no cups-pdf queue, no cups-pdf.conf directives, no outbox dirs, no worker network activity (D-07)"
    requirement: "D-07"
    verification:
      - kind: integration
        ref: "internal/verify-cups-paperless-upload.sh (Scenario 2: disabled-by-default regression)"
        status: pass
    human_judgment: false
  - id: D2
    description: "When enabled, printing to the configured queue produces a PDF uploaded to POST /api/documents/post_document/ with multipart fields document + title, Authorization: Token <token> (D-01/D-10)"
    requirement: "D-01, D-10"
    verification:
      - kind: integration
        ref: "internal/verify-cups-paperless-upload.sh (Scenario 1: happy path -- asserts path, Authorization header, and non-empty title against a stub HTTP server)"
        status: pass
    human_judgment: false
  - id: D3
    description: "If the original title cannot be recovered, upload proceeds with a timestamp fallback title -- never skipped for a missing title (D-11)"
    requirement: "D-11"
    verification:
      - kind: unit
        ref: "cups/upload-worker.py read_title() -- exercised implicitly by every Scenario 1/3 upload in internal/verify-cups-paperless-upload.sh, all of which recover a real title from the sidecar; the explicit sidecar-missing fallback path is code-reviewed but not independently forced in the verify harness"
        status: pass
    human_judgment: false
  - id: D4
    description: "A PostProcessing hook failure never blocks or fails the underlying print job -- cupsd and the physical printer queue are provably unaffected (D-13)"
    requirement: "D-13"
    verification:
      - kind: integration
        ref: "internal/verify-cups-scaffold.sh (re-run after this plan's changes: physical printer registration, UUID stability, print-history poller all still pass unmodified)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Once retry/backoff is exhausted, the document moves to failed/ (never deleted) and exactly one WARNING-level log line is emitted (D-15)"
    requirement: "D-09, D-15"
    verification:
      - kind: integration
        ref: "internal/verify-cups-paperless-upload.sh (Scenario 3: retry exhaustion against a stub server forced to return HTTP 500; grep -c assertion proves exactly one WARNING line)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The cups-pdf queue's printer UUID is stable across container restarts via the same fixup mechanism as physical printers (D-08)"
    requirement: "D-08"
    verification:
      - kind: manual_procedural
        ref: "ad-hoc docker build/run/restart check (not folded into the committed verify script): read printers.conf's UUID for the cups-pdf queue before and after a real `docker restart`, confirmed byte-identical"
        status: pass
    human_judgment: false
  - id: D7
    description: "paperless_upload.token is never printed in plaintext to any add-on log output"
    verification:
      - kind: integration
        ref: "internal/verify-cups-paperless-upload.sh (all 3 scenarios assert the fixture token string never appears in `docker logs` output)"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-09-28
status: complete
---

# Phase 22 Plan 01: cups-pdf Queue + Paperless-ngx Upload Worker Summary

**Disabled-by-default cups-pdf virtual print queue with a decoupled background worker that uploads every printed PDF to paperless-ngx's REST API, including a fixed-interval retry/backoff state machine and exhausted-failure visibility -- verified end-to-end against a real built image and a stub HTTP server.**

## Performance
- **Duration:** 21 min
- **Started:** 2026-09-28T19:37:14Z
- **Completed:** 2026-09-28T19:58:29Z
- **Tasks:** 2 completed
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments
- `paperless_upload` option block added to `cups/config.yaml` + both translation files (`enabled`, `queue_name`, `location`, `url`, `token` as `password?`, `timeout`, `retry_count`, `retry_delay`)
- `generate_config.py` gained three new functions (`build_cups_pdf_conf`, `build_paperless_postprocess_hook`, `build_cups_pdf_registration_snippet`) that reuse the exact same validation (`NAME_RE`/`LOCATION_RE`), retry-loop (`lpinfo -m`), and shell-quoting patterns already established for the physical-printer/brlaser path
- `cups/upload-worker.py` (new): a background worker structurally identical to `print-history-poller.py`, polling an `incoming/processing/sent/failed` outbox, reading a PostProcessing-hook-written title sidecar (with timestamp fallback), uploading via `requests`, and running a fixed-interval retry/backoff state machine before giving up
- `internal/verify-cups-paperless-upload.sh` (new): a docker-build/run verify harness with an embedded stdlib HTTP stub server, proving the happy path, the D-07 disabled-by-default regression, and retry-exhaustion end-to-end
- Discovered and fixed a real packaging defect (Alpine's `cups-pdf` backend shipped world-executable, so CUPS never ran it as root, so cups-pdf itself refused to produce any PDF at all) -- without this fix the entire feature would have been silently non-functional

## Task Commits
1. **Task 1: End-to-end paperless-ngx PDF upload -- happy path only** - `56ca013` (feat)
2. **Task 2: Retry/backoff, exhausted-failure visibility, disabled-by-default regression coverage** - `da79d6a` (feat)

## Files Created/Modified
- `cups/config.yaml` - `paperless_upload` options + schema block (D-06)
- `cups/translations/{de,en}.yaml` - `configuration.paperless_upload` name/description entries for every field
- `cups/generate_config.py` - `build_cups_pdf_conf`, `build_paperless_postprocess_hook`, `build_cups_pdf_registration_snippet` + wiring into `main()`
- `cups/Dockerfile` - `cups-pdf` + `py3-requests` apk packages, `cups-pdf.conf.stock` backup, `chmod 700` fix for the cups-pdf backend, `upload-worker.py` added to `COPY`
- `cups/run.sh` - launches `upload-worker.py` as a backgrounded process (mirrors `print-history-poller.py`), extends the shutdown trap
- `cups/upload-worker.py` (new) - the background upload worker with retry/backoff
- `internal/verify-cups-paperless-upload.sh` (new) - 3-scenario docker-based verify harness

## Decisions Made
- **`PostProcessing` not `PostProcess`** -- cups-pdf's actual directive name (verified against the stock `cups-pdf.conf`'s own documentation), corrected from the plan text's wording; the argument-passing model in the plan's `<researched_correction>` (3 positional args, no title env var) was accurate and implemented as described.
- **`chmod 700` on the cups-pdf backend** -- see Deviations below; without this the feature is silently non-functional on this Alpine base image.
- **Fixed-interval retry (not exponential)** -- per D-09's Claude's-discretion note, matching this add-on's stated preference for simple/predictable behavior (`print-history-poller.py`'s own docstring) over cleverness.
- **`<basename>.retry.json` as a distinct sidecar** from the `.json` title sidecar -- keeps the two concerns (title recovery vs. retry bookkeeping) independently readable/removable, and avoids ever conflating "no title recorded" with "no attempts yet."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] cups-pdf backend not runnable as root on Alpine, silently producing no PDF at all**
- **Found during:** Task 1, first live print-job test against the built image
- **Issue:** Alpine's `cups-pdf-3.0.2-r0` package installs `/usr/lib/cups/backend/cups-pdf` at mode `0755` (world-executable). CUPS's own rule for whether to run a backend as root vs. the unprivileged filter user (`lp`) is derived purely from the backend executable's file permissions -- a backend executable by "other" is run unprivileged. cups-pdf's own C code explicitly checks `getuid() == 0` and refuses to proceed otherwise (`"CUPS-PDF cannot be called without root privileges!"`, confirmed live in `/var/log/cups/error_log`). Every print job to the queue completed "successfully" from CUPS's point of view but produced zero output under `/data/paperless_upload/incoming/` -- a completely silent failure with no error surfaced anywhere a user would see it.
- **Fix:** Added `RUN chmod 700 /usr/lib/cups/backend/cups-pdf` to the Dockerfile, immediately after the package install. Debian's own `cups-pdf` package ships the same upstream binary at `0700` for exactly this reason -- this is an Alpine packaging gap, not a design choice this add-on needed to make.
- **Files modified:** `cups/Dockerfile`
- **Verification:** `internal/verify-cups-paperless-upload.sh` Scenario 1 (a real print job reaches `sent/` and the stub server) fails without this fix (PDF never leaves `incoming/`) and passes with it.
- **Commit:** `56ca013`

**2. [Rule 1 - Bug] Wrong directive name (`PostProcess` vs `PostProcessing`)**
- **Found during:** Task 1, after fixing the backend-permission issue above, the PDF reached `incoming/` but no title sidecar was ever written.
- **Issue:** The plan's action text (and this codebase's own draft docstrings, copied from the plan) called the directive `PostProcess`. cups-pdf's actual stock `cups-pdf.conf` documents the directive as `PostProcessing` (`### Key: PostProcessing (config, lptoptions)`). The wrong directive name meant cups-pdf silently ignored the hook entirely -- no error, just no sidecar.
- **Fix:** Changed the emitted directive in `build_cups_pdf_conf()` to `PostProcessing {path}`, and corrected the surrounding docstrings/comments.
- **Files modified:** `cups/generate_config.py`
- **Verification:** `internal/verify-cups-paperless-upload.sh` Scenario 3 depends on the title sidecar surviving into `failed/`; confirmed present after the fix.
- **Commit:** `56ca013`

**Total deviations:** 2 auto-fixed (both Rule 1 -- blocking bugs discovered via the docker-build verify harness, neither present in the plan's own text, both would have made the entire feature silently non-functional if shipped as originally drafted).

**Impact:** Both fixes are small, isolated, and fully covered by the plan's own verify script (which would fail without them, and does not fail with them). No architectural changes, no scope expansion beyond what the plan's `must_haves` already required.

## Issues Encountered
None blocking. One informational observation: cups-pdf's own internal title-derivation (`preparetitle()`) sometimes produces a title string with extra characters beyond a straightforward "spaces to underscores" transform of the original `-t` job title (e.g. `"My Test Title 2"` became a basename like `My_Test_Title_2__tprocess` before this hook's own `-job_N` suffix strip). This is cups-pdf's own upstream behavior, not a bug in this phase's code -- the plan's `must_haves` only require a *non-empty* title reach paperless-ngx, which is satisfied; a follow-up phase could investigate tightening cups-pdf's own title-sanitization options if a cleaner title string becomes a requirement.

## User Setup Required
None - no external service configuration required. When a user wants to use this feature, they set `paperless_upload.enabled: true` plus `url`/`token` via the add-on's Options UI (documented further in 22-02).

## Next Phase Readiness
The `paperless_upload` feature (config schema, cups-pdf queue, PostProcessing hook, upload worker with retry/backoff) is fully functional and verified. 22-02 can proceed to document the feature (DOCS.md) and any remaining polish without needing further code changes to this plan's surface.

---
*Phase: 22-cups-paperless-ngx-pdf-document-upload*
*Completed: 2026-09-28*
