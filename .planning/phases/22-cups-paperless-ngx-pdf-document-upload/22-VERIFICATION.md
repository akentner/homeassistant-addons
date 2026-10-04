---
phase: 22-cups-paperless-ngx-pdf-document-upload
verified: 2026-10-04T18:10:00Z
status: gaps_found
score: 17/18 must-haves verified
covered_files:
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-01-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-01-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-03-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-03-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-CONTEXT.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-DISCUSSION-LOG.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-PATTERNS.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW-DISPOSITION.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/COVERAGE.md
  - cups/DOCS.md
  - cups/Dockerfile
  - cups/README.md
  - cups/avahi-guard.sh
  - cups/config.yaml
  - cups/generate_config.py
  - cups/run.sh
  - cups/translations/de.yaml
  - cups/translations/en.yaml
  - cups/upload-worker.py
  - internal/verify-cups-paperless-upload.sh
covered_digest: "v2:sha256:48ab1be97cdb5d1e40bf19234e288cd36ef0c91f1a17393cd198300e8e8419ac"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 17/17
  gaps_closed: []
  gaps_remaining: []
  regressions:
    - "New truth 18 (a document is recorded as sent only when paperless-ngx actually accepted the POST) was never checked by the previous report and fails (CR-01). It is a newly surfaced failure, not a regression of a previously passing truth: truths 1-17 all still pass."
gaps:
  - truth: "A document is recorded as `sent/` only when paperless-ngx actually accepted the POST (ROADMAP: a 'sent' status 'means task accepted'; core principle: the worker owns delivery)"
    status: failed
    reason: "upload_document() calls requests.post() with the default allow_redirects=True and treats any final 2xx as success. A 301/302/303 answer is converted by requests into a GET on the Location target; if that target answers 2xx (SSO/login page behind a reverse proxy, SPA index, API root) the worker logs 'uploaded ... to paperless-ngx', deletes the sidecar and retry state and moves the PDF to sent/ although paperless-ngx never received the document. No retry, no failed/ routing, no WARNING: the D-15 visibility mechanism is bypassed. Reproduced in this verification run against the real upload_document(): a stub answering POST with 302 -> /login/ and GET /login/ with 200 returned True. The PDF is retained in sent/ (not deleted), so this is a silent false delivery, not data destruction."
    artifacts:
      - path: "cups/upload-worker.py"
        issue: "lines 232-254: requests.post(...) without allow_redirects=False; success = 200 <= status < 300 with no check that the response is the paperless-ngx task-UUID body"
    missing:
      - "Pass allow_redirects=False to requests.post() and treat every 3xx as a failure (log the Location header so the operator can fix `url`)"
      - "Tighten the success check (HTTP 200 and a JSON-string task-id body, per the ROADMAP's documented response shape)"
      - "Add a verifier scenario (Scenario 5) where the stub answers the POST with 301/302 and assert the document does NOT reach sent/ but follows retry -> failed/"
advisory:
  - finding: "WR-04 (22-REVIEW.md, previously WR-01 advisory): D-15 'upload exhausted' WARNING prints the pre-disambiguation filename when a failed/ collision occurs (`see failed/<name>` while the file landed at `failed/<name>-<tag>.pdf`)."
    category: other
    reason: "Narrow precondition (exhaustion AND same-named failed/ collision). The literal D-15 truth holds: exactly one WARNING, document never deleted; a second correctly named WARNING comes from unique_destination()."
    evidence_status: "confirmed by direct code read (upload-worker.py:294-307); no automated regression test"
  - finding: "WR-03 (22-REVIEW.md): retry-state field types not validated (is_due() catches KeyError/ValueError only; naive ISO timestamp or null next_attempt_at raises TypeError; process_due_retry() int() on a non-numeric attempts)."
    category: other
    reason: "Needs hand-edited/corrupted state; the worker's own writer cannot produce it. Failure is isolated to that one document by the per-document try/except (no sibling starvation, truth 14 still holds). The stuck document logs a WARNING every 20 s and never reaches failed/."
    evidence_status: "confirmed by direct code read (upload-worker.py:207-217, 332-337)"
  - finding: "WR-01 (22-REVIEW.md): poll_once() globs incoming/*.pdf with no file-age/settle check, so it can pick up a PDF cups-pdf is still writing (truncated upload recorded as success because paperless-ngx answers 200 and fails the consumption task asynchronously) or move the PDF before the title sidecar exists (title falls back to Scan_<ts>, orphan sidecar left in incoming/)."
    category: other
    reason: "Timing-dependent (20 s poll vs. a short ghostscript conversion window). D-11 timestamp fallback still guarantees the upload is never skipped. Not exercised by the stub-based probe. Recommended: skip files with mtime younger than ~10 s."
    evidence_status: "confirmed by direct code read (upload-worker.py:343-347); race not reproduced"
  - finding: "WR-02 (22-REVIEW.md): process_new_document() uses Path.replace() into processing/, clobbering a same-named PDF still waiting for retry there (cupsd's job-ID counter resets across restarts). Same defect class as the closed WR-05 for sent//failed/."
    category: other
    reason: "Requires restart while a document is mid-retry AND an identical title/job-id afterwards. The clobbered document had not yet been declared failed, so the literal D-15 'failed is never deleted' truth is not violated."
    evidence_status: "confirmed by direct code read (upload-worker.py:318-329)"
  - finding: "WR-05 (22-REVIEW.md): no validation of url/token when enabled; empty url/token dead-letters every printed document to failed/ after retry_count attempts."
    category: other
    reason: "Failures are visible (one WARNING per document, D-15) and documents are retained, so the phase's resilience contract holds; the UX is poor on misconfiguration."
    evidence_status: "confirmed by direct code read (upload-worker.py:81-91, 227-246)"
  - finding: "WR-06 (22-REVIEW.md): success path unlinks sidecar and retry state before moving the PDF to sent/; if the move raises, the next cycle re-uploads (duplicate in paperless-ngx)."
    category: other
    reason: "Needs a failing filesystem move after a successful upload."
    evidence_status: "confirmed by direct code read (upload-worker.py:278-284)"
  - finding: "WR-07 (22-REVIEW.md): the verifier asserts only a non-empty title, so a broken title-recovery mechanism (D-10) would still pass; Scenario 3 downgrades a missing sidecar to a NOTE."
    category: other
    reason: "Verifier-strength gap, not a product defect: this run unit-checked the generated hook directly (title 'Happy_Path_Title' recovered from 'Happy_Path_Title-job_7.pdf', `-job_N` suffix stripped, exit 0 even when the sidecar cannot be written)."
    evidence_status: "confirmed by direct read of the verifier and by running the generated hook this run"
  - finding: "WR-08 (22-REVIEW.md): paperless_upload.queue_name is not checked against printers[].name; a collision re-points the physical queue at cups-pdf:/."
    category: other
    reason: "Requires the operator to choose an identical name for both. Previously recorded as WR-04 (pre-existing)."
    evidence_status: "confirmed by direct code read (generate_config.py:1005-1012, 1520-1525)"
  - finding: "IN-01..IN-06 (22-REVIEW.md): internal '(WR-05)' token in a runtime log line, collision_tag edge case, falsy-zero coercion of numeric options, DOCS/docstring disagreement about the sidecar on success (+ stale Dockerfile 'stdlib json only' comment), world-writable stage dirs / no TLS verify option, avahi_guard_start final-attempt comment."
    category: other
    reason: "Informational / cosmetic; none touches a locked decision."
    evidence_status: "per 22-REVIEW.md; spot-confirmed IN-01, IN-03, IN-04 in the current files"
human_verification: []
---

# Phase 22: cups-paperless-ngx-pdf-document-upload Verification Report

**Phase Goal:** Add a second, PDF-only virtual printer queue to the `cups` add-on (via `cups-pdf`), separate from and
non-disruptive to the existing physical Brother-MFC-7460DN queue, whose output is picked up by a decoupled background
worker and uploaded to a paperless-ngx instance's REST API. The worker must be resilient to paperless-ngx being
unreachable: retry/backoff, never crash, never block cupsd or the physical printer.

**Verified:** 2026-10-04T18:10:00Z
**Status:** gaps_found
**Re-verification:** Yes. The prior report (2026-10-03, passed 17/17) went stale because Phase 21 touched covered files
(`cups/run.sh`, `generate_config.py`, `config.yaml`, `Dockerfile`, `README.md`, `DOCS.md`, new `avahi-guard.sh`, the
verifier script). This run re-checks that none of those changes broke a Phase 22 truth, re-runs the Docker-backed probe,
weighs the new code review (`22-REVIEW.md`: 1 critical, 8 warnings, 6 info), and regenerates the fingerprint with
`gsd_run query verification.fingerprint` (`avahi-guard.sh` added to `covered_files`).

## Verdict on the code review's CR-01

**CR-01 breaks a must-have truth, so the status is `gaps_found`.** Reasoning:

- The ROADMAP's locked design (Phase 22 section) states "A 'sent' status in this add-on's own outbox bookkeeping means
  'task accepted'", and the phase's core principle is that the worker owns delivery. A document that sits in `sent/`
  although paperless-ngx never received it falsifies that contract. I treat it as new must-have truth 18.
- I reproduced it rather than trusting the review: `upload_document()` imported from `cups/upload-worker.py`, against a
  local stub answering `POST` with `302 Location: /login/` and `GET /login/` with `200`, logged
  `INFO: uploaded a.pdf to paperless-ngx` and returned `True`.
- It bypasses the resilience machinery the goal demands (no retry/backoff, no `failed/`, no D-15 WARNING), so the
  operator gets a false positive instead of a signal. The trigger is a plausible deployment (paperless-ngx behind an
  SSO/login or http-to-https proxy answering 3xx to a 2xx page). A plain http->https 301 to the same path would end in
  a GET to `post_document/`, which paperless-ngx answers with 405, so that sub-case fails loudly; the silent case needs
  the redirect target to return 2xx.
- Mitigating facts (why it is one gap and not a wider failure): the PDF is retained in `sent/` (never deleted, so
  nothing is destroyed), and it only manifests under a misconfigured/proxied URL. The fix is two lines plus one probe
  scenario.

The eight warnings were each judged against the 15 locked decisions and the 17 existing truths; none of them falsifies a
declared truth (details in `advisory:`).

## Phase 21 changes: effect on Phase 22

| Change | Check | Result |
|---|---|---|
| `run.sh` reworked (avahi guard, stale pid cleanup, `generate_config.py` failure is fatal) | Read in full. `upload-worker.py` still launched at step 11b after the cupsd UUID-fixup restart; PID in `cleanup()` trap | Worker wiring intact. Side effect (noted in review, design-documented): cupsd, hence the upload path, can start up to ~4-5 min late when avahi cannot settle |
| `avahi-guard.sh` added | `COPY run.sh avahi-guard.sh ...` in Dockerfile; sourced in `run.sh:43` | Intact; shellcheck clean |
| `generate_config.py` registration rework (`REGISTER_FAILED`, per-printer tolerance) | Ran `build_printer_registration()` with the cups-pdf snippet | Snippet is appended before `exit "$REGISTER_FAILED"`; queue name flows into `registered_printer_names` |
| `config.yaml` bumped to `0.1.0-16`, `README.md`/`DOCS.md` Phase 21 edits | `make validate-versions` OK; `paperless_upload` block with 8 fields, `token: "password?"`, `enabled: false` unchanged; DOCS section `## Paperless-ngx PDF Upload` (line 111) and the PostProcessing note (line 320+) intact; README mentions paperless-ngx | Intact |
| `internal/verify-cups-paperless-upload.sh` routed through `cups_isolated_run` | Probe re-run end to end | All scenarios pass (see Probe Execution) |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With `paperless_upload.enabled` false (shipped default) the add-on behaves as before: no queue, no cups-pdf.conf, no outbox dirs, no worker activity (D-07) | ✓ VERIFIED | `config.yaml` ships `enabled: false`. Fresh probe Scenario 2: 3/3 PASS. This run: `build_cups_pdf_conf({enabled:false})` and `build_cups_pdf_registration_snippet({})` both return None. `main()` of the worker returns after one INFO line when disabled. |
| 2 | When enabled, printing to the queue yields a PDF uploaded via `POST /api/documents/post_document/` with multipart `document` + `title` and `Authorization: Token <token>` (D-01/D-10) | ✓ VERIFIED | Fresh probe Scenario 1: queue registered, device URI `cups-pdf:/`, PDF in `sent/`, stub got POST with Token header, non-empty `title`, correct path. Code at `upload-worker.py:232-240`. (Direct, non-redirecting server only: see truth 18.) |
| 3 | Unrecoverable title falls back to a timestamp title, including for a non-dict JSON sidecar (D-11) | ✓ VERIFIED | `read_title()` `upload-worker.py:94-125` (isinstance dict guard, fallback, 128 cap). Scenario 4 `badtitle-doc.pdf` converges to `sent/`. This run's redirect repro also showed the `Scan_2026-10-04_...` fallback title in use. |
| 4 | A PostProcessing hook failure never blocks or fails the print job (D-13) | ✓ VERIFIED | Ran the generated hook this run: writes `{"title": "Happy_Path_Title"}` for `Happy_Path_Title-job_7.pdf`, and with an unwritable destination the Python block raises but the script still exits 0 (`) \|\| true` + `exit 0`). Worker is a separate backgrounded process (`run.sh:210`). Scenario 1 prints a real job end to end. |
| 5 | After retry/backoff exhaustion the document moves to `failed/` (never deleted), exactly one WARNING (D-15) | ✓ VERIFIED | Scenario 3: 6/6 PASS (PDF + sidecar in `failed/`, `processing/` clean, exactly one "upload exhausted" line, token absent). Narrow WR-04 advisory only. |
| 6 | The cups-pdf queue's UUID is stable across restarts via the same fixup as physical printers (D-08) | ✓ VERIFIED (structural) | `generate_config.py:1520-1531` appends `cups_pdf_queue_name` to `registered_printer_names` before `build_printer_uuid_fixup_script(...)`; run.sh step 8 executes it. No live restart test this run. |
| 7 | `paperless_upload.token` is never printed to add-on logs | ✓ VERIFIED | All 4 probe scenarios assert the fixture token is absent from container logs. Caveat (WR-06-type, pre-existing): response body logged verbatim (truncated to 200 chars), so proven for the stub responses only. |
| 8 | `cups/DOCS.md` documents every `paperless_upload` option with default and purpose | ✓ VERIFIED | `## Paperless-ngx PDF Upload` at line 111, all 8 fields. |
| 9 | DOCS Design notes record the corrected `PostProcessing` mechanism | ✓ VERIFIED | `DOCS.md:320-337`. |
| 10 | `README.md` Features mentions paperless-ngx upload | ✓ VERIFIED | `grep -c paperless-ngx cups/README.md` = 1 (line 18). |
| 11 | `internal/verify-cups-paperless-upload.sh` passes | ✓ VERIFIED | Re-run: exit 0, "ALL CHECKS PASSED" (24 PASS lines). |
| 12 | Version bump with 3-file sync | ✓ VERIFIED | `make validate-versions` OK; cups `0.1.0-16` / `0.1.0`. |
| 13 | Non-dict `.json` sidecar degrades to timestamp title (WR-02 of 22-03 closed) | ✓ VERIFIED | Code + Scenario 4 assertion 2. |
| 14 | Non-dict/malformed `.retry.json` does not abort the `processing/` scan (CR-01 of 22-03 closed) | ✓ VERIFIED | `is_due()` inside the per-document try/except (`:359-364`); `load_retry_state()` rejects non-dict; Scenario 4 assertion 1. |
| 15 | Same-name collision into `sent/`/`failed/` never overwrites a retained file (WR-05 of 22-03 closed) | ✓ VERIFIED | `unique_destination()` at `:283/:295/:297`; Scenario 4 assertions 3-5. |
| 16 | Scenarios 1-3 still pass after the 22-03 fixes and Phase 21 rework | ✓ VERIFIED | Fresh run: 8 + 3 + 6 PASS. |
| 17 | Scenario 4 proves the three 22-03 fixes against a real built image | ✓ VERIFIED | Fresh run: 6/6 PASS. |
| 18 | A document is recorded as `sent/` only when paperless-ngx actually accepted the POST (ROADMAP: "'sent' means task accepted") | ✗ FAILED | CR-01 confirmed and reproduced (see verdict above and `gaps:`). |

**Score:** 17/18 truths verified (0 present-but-behavior-unverified)

### D-01..D-15 accounting (22-CONTEXT.md; no REQUIREMENTS.md IDs exist for this ad-hoc phase)

| ID | Decision | Status | Evidence |
|----|----------|--------|----------|
| D-01 | `py3-requests` for the multipart POST + Token auth | ✓ SATISFIED | `Dockerfile` apk list incl. `py3-requests`; worker uses `requests.post(files=..., headers=Token)`. (Redirect handling is the CR-01 gap, not D-01 itself.) |
| D-02 | Queue Avahi/AirPrint-advertised via the same registration path | ✓ SATISFIED (structural) | Registered through `register-printers.sh` via `lpadmin ... -E`; no live mDNS check this run (cups shares queues through the same cupsd/Avahi path as the physical printer). |
| D-03 | `queue_name` configurable, default `PDF-to-DMS` | ✓ SATISFIED | `config.yaml` default; `PRINTER_NAME_RE` validation in both builders. |
| D-04 | `location` configurable | ✓ SATISFIED | `config.yaml`; `-L` arg with `LOCATION_RE` validation. |
| D-05 | Single shared outbox dir | ✓ SATISFIED | `Out` + `AnonDirName` both `/data/paperless_upload/incoming` in `build_cups_pdf_conf`. |
| D-06 | Dedicated `paperless_upload` block, 8 fields | ✓ SATISFIED | `config.yaml` options + schema. |
| D-07 | Fully skipped when disabled | ✓ SATISFIED | Truth 1. |
| D-08 | UUID fixup covers every registered printer | ✓ SATISFIED (structural) | Truth 6. |
| D-09 | Sensible defaults (timeout 30, retry_count 5, retry_delay 60), documented | ✓ SATISFIED | `config.yaml`; DOCS table. |
| D-10 | Title from the original job title | ✓ SATISFIED | Hook derives title from cups-pdf's job-title-based filename; unit-run this run. Verifier only asserts non-empty (WR-07 advisory). |
| D-11 | Timestamp fallback, upload never skipped | ✓ SATISFIED | Truth 3. |
| D-12 | Sidecar handoff mechanism | ✓ SATISFIED | Hook writes `<basename>.json` atomically; worker reads it; deleted after success (docs disagree, IN-04). |
| D-13 | Hook best-effort, never blocks printing | ✓ SATISFIED | Truth 4. |
| D-14 | Trim + length-cap only | ✓ SATISFIED | 128-char cap in both hook and `read_title()`. |
| D-15 | One WARNING per exhausted document | ✓ SATISFIED | Truth 5 (WR-04 narrow advisory). |

All 15 IDs accounted for; none is BLOCKED by itself. The one failed truth (18) comes from the ROADMAP delivery contract
rather than from a single D-ID.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `cups/upload-worker.py` | Background outbox worker | ⚠️ PARTIAL | 387 lines, substantive, wired from `run.sh:210` and Dockerfile `COPY`; py_compile OK; success classification defect (CR-01) |
| `cups/generate_config.py` (`build_cups_pdf_conf`, `build_paperless_postprocess_hook`, `build_cups_pdf_registration_snippet`) | Generators | ✓ VERIFIED | Lines 844, 909, 975; called from `main()` (1520, 1554, 1567) |
| `cups/config.yaml` | Options + schema | ✓ VERIFIED | `enabled: false`, `token: "password?"` |
| `cups/Dockerfile` | `cups-pdf`, `py3-requests`, worker + guard copied, backend chmod 700 | ✓ VERIFIED | |
| `internal/verify-cups-paperless-upload.sh` | Docker harness, 4 scenarios | ✓ VERIFIED | shellcheck clean; no scenario for redirects (needed for gap 18) |
| `cups/DOCS.md`, `cups/README.md` | Docs | ✓ VERIFIED | Truths 8-10 |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `cups_pdf_queue_name` | `build_printer_uuid_fixup_script()` | appended in `main()` before the fixup call | ✓ WIRED |
| PostProcessing hook | `.json` sidecar -> `read_title()` | `cups-pdf.conf` `PostProcessing` directive | ✓ WIRED |
| `run.sh` | `upload-worker.py` | `python3 /upload-worker.py &`, PID in `cleanup()` | ✓ WIRED |
| `is_due()` / `load_retry_state()` | per-document try/except | `upload-worker.py:359-364` | ✓ WIRED |
| `attempt_and_route()` | `unique_destination()` | `:283`, `:295`, `:297` | ✓ WIRED |
| `upload_document()` result | `sent/` routing | `if upload_document(...)` at `:278` | ⚠️ PARTIAL: result true for a followed redirect (CR-01) |

### Data-Flow Trace (Level 4)

Not a UI phase. File-to-HTTP flow exercised end to end by Scenario 1 (real cups-pdf job -> sidecar -> multipart POST to
the stub). The only failing flow is "which responses count as accepted" (gap 18).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Redirect treated as success (CR-01) | python script importing `upload-worker.py`, stub: POST -> 302 /login/, GET /login/ -> 200 | `INFO: uploaded a.pdf to paperless-ngx ...` and `upload_document -> True` | ✗ FAIL (confirms the gap) |
| Generated hook derives title | `sh hook.sh Happy_Path_Title-job_7.pdf u u` | sidecar `{"title": "Happy_Path_Title"}`, rc 0 | ✓ PASS |
| Generated hook on unwritable path | `sh hook.sh /nonexistent/dir/x-job_1.pdf u u` | traceback inside python block, script rc 0 | ✓ PASS (D-13) |
| Disabled builders return None | python call on `generate_config.py` | `None`, `(None, None)` | ✓ PASS (D-07) |
| Python compile | `python3 -m py_compile cups/upload-worker.py cups/generate_config.py` | OK | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| `internal/verify-cups-paperless-upload.sh` | `bash internal/verify-cups-paperless-upload.sh` (repo root, podman-emulated Docker) | exit 0 in ~105 s; Scenario 1: 8 PASS, 2: 3 PASS, 3: 6 PASS, 4: 6 PASS, "ALL CHECKS PASSED" | PASS |
| `make validate-versions` | repo root | "Version validation passed for all add-ons!" | PASS |
| `shellcheck -e SC1091 -e SC2034 internal/verify-cups-paperless-upload.sh cups/run.sh cups/avahi-guard.sh` | repo root | clean | PASS |

Note: the probe passing does not contradict gap 18; it simply has no redirecting-stub scenario.

### Requirements Coverage

D-01..D-15 live only in `22-CONTEXT.md` and the plan frontmatter (ad-hoc phase, known and unchanged); table above.
No ORPHANED requirements: `.planning/REQUIREMENTS.md` maps nothing to Phase 22.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `cups/upload-worker.py` | 232-254 | `requests.post()` follows redirects; 2xx-only success check | 🛑 Blocker (CR-01) | Silent false delivery, gap 18 |
| `cups/upload-worker.py` | 343-347 | No settle/age check on `incoming/*.pdf` | ⚠️ Warning (WR-01) | Possible truncated upload / lost title |
| `cups/upload-worker.py` | 318-329 | `Path.replace()` into `processing/` can clobber | ⚠️ Warning (WR-02) | Rare data loss of a pending retry |
| `cups/upload-worker.py` | 207-217, 332-337 | Retry-state types unvalidated | ⚠️ Warning (WR-03) | One document stuck |
| `cups/upload-worker.py` | 294-307 | WARNING names pre-disambiguation filename | ⚠️ Warning (WR-04) | Misleading log on collision |
| `cups/upload-worker.py`, `generate_config.py` | 81-91, 874-886 | No url/token validation when enabled | ⚠️ Warning (WR-05) | Silent-ish dead-lettering |
| `cups/upload-worker.py` | 278-284 | Sidecar/state removed before the PDF move | ⚠️ Warning (WR-06) | Possible duplicate upload |
| `internal/verify-cups-paperless-upload.sh` | 288-298, 461-466 | Non-empty title assertion only | ⚠️ Warning (WR-07) | Verifier cannot detect D-10 regression |
| `cups/generate_config.py` | 1005-1012, 1520-1525 | No `queue_name` vs `printers[].name` collision check | ⚠️ Warning (WR-08) | Operator-error collision re-points physical queue |
| `cups/generate_config.py` | 148 | `tailXXXX.ts.net` in an example comment | ℹ️ Info | Illustrative hostname, not a debt marker |

No `TBD`/`FIXME`/`TODO`/`HACK` debt markers in the covered implementation files. The review dispositions in
`22-REVIEW-DISPOSITION.md` are all still `open`; that file needs updating after the gap-closure plan.

### Human Verification Required

None. Real paperless-ngx, real AirPrint clients and live mDNS behavior were never in the automated scope (the probe uses
a stub server).

### Gaps Summary

One gap blocks the phase: the worker can record a document as delivered (`sent/`) when paperless-ngx never accepted it,
because redirects are followed and any resulting 2xx counts as success (CR-01, reproduced here). Everything else in the
phase goal holds under fresh evidence: the PDF-only queue is optional and fully skipped by default, the physical queue
and cupsd are untouched, the worker is a decoupled process, retry/backoff routes to `failed/` with one WARNING,
the token is never logged, and the Phase 21 rework did not break the upload path. Suggested closure plan
(`/gsd-plan-phase --gaps`): set `allow_redirects=False`, treat 3xx as failure with the `Location` logged, tighten the
success check to the task-UUID body, add a redirect-stub Scenario 5 to the verifier, and in the same pass fix the cheap
neighbors WR-01 (settle check), WR-02 and WR-06 (move ordering/uniqueness), WR-04 and WR-03 (they live in the same
function).

---

_Verified: 2026-10-04T18:10:00Z_
_Verifier: Claude (gsd-verifier)_
