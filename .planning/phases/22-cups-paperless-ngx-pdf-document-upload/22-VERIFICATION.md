---
phase: 22-cups-paperless-ngx-pdf-document-upload
verified: 2026-10-04T19:10:00Z
status: passed
score: 18/18 must-haves verified
covered_files:
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-01-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-01-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-03-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-03-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-04-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-04-SUMMARY.md
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
  - internal/verify-cups-upload-worker.py
covered_digest: "v2:sha256:6edc780e02da725b545fbefd74afd2eeb0f20efb88a32731336e7002023fcb1c"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 17/18
  gaps_closed:
    - "Truth 18: a document is recorded as sent/ only when paperless-ngx actually accepted the POST (CR-01), closed by plan 22-04"
  gaps_remaining: []
  regressions: []
advisory:
  - finding: "WR-09 (22-REVIEW.md, introduced by the 22-04 fix): _safe_redirect_target() calls urlsplit() on the Location header outside the try block; a malformed value such as 'http://[::1/x' raises ValueError out of upload_document() (docstring: 'Never raises'). attempt_and_route() has no handler, so no retry state is written and no exhaustion routing happens; the per-document handler in poll_once only logs a WARNING."
    category: other
    reason: "Reproduced this run: upload_document() against a stub answering 302 Location 'http://[::1/x' raised ValueError after exactly one POST. Consequence by code reading (poll_once -> is_due() True when no state file): the document is re-POSTed every 20 s, retry_count/retry_delay are ignored, and it never reaches failed/. Needs a broken proxy/SSO redirect with a malformed Location, which is rare. No false delivery (the PDF stays in processing/, never in sent/), nothing deleted, a WARNING is logged each cycle, cupsd and the physical queue are unaffected. Truth 5 holds for every failure mode its probes cover, so this does not falsify a declared truth. HUMAN DECISION REQUESTED: accept as advisory, or open a small follow-up (two-line try/except ValueError returning '(unparseable Location header)' plus a probe row)."
    evidence_status: "reproduced by direct execution against the real upload_document(); retry-loop consequence confirmed by code read of poll_once/is_due, not run end to end"
  - finding: "WR-04: D-15 'upload exhausted' WARNING prints the pre-disambiguation filename when a failed/ collision occurs."
    category: other
    reason: "Narrow precondition; exactly one WARNING and no deletion still hold. Unchanged by 22-04."
    evidence_status: "code read (upload-worker.py exhaustion branch of attempt_and_route)"
  - finding: "WR-03: retry-state field types not validated (TypeError on naive timestamp / null next_attempt_at)."
    category: other
    reason: "Needs hand-edited state; isolated to one document by the per-document try/except. Unchanged by 22-04."
    evidence_status: "code read (is_due, process_due_retry)"
  - finding: "WR-01: poll_once() has no file-age/settle check, so it can pick up a PDF cups-pdf is still writing or race the title sidecar."
    category: other
    reason: "Timing-dependent; D-11 fallback still guarantees an upload. Note the stricter 200 check does not help here because paperless-ngx returns the task id before consumption. Recommended follow-up: skip files younger than ~10 s."
    evidence_status: "code read (poll_once); race not reproduced"
  - finding: "WR-02: process_new_document() uses Path.replace() into processing/ and can clobber a same-named PDF waiting for retry."
    category: other
    reason: "Needs a container restart mid-retry plus an identical job title/id afterwards."
    evidence_status: "code read"
  - finding: "WR-05: no url/token validation when enabled; empty values dead-letter every document to failed/ after retry_count attempts."
    category: other
    reason: "Failures are visible (one WARNING each) and documents retained."
    evidence_status: "code read"
  - finding: "WR-06: success path unlinks sidecar and retry state before moving the PDF to sent/; a failing move re-uploads (duplicate)."
    category: other
    reason: "Needs a failing filesystem move after a successful upload."
    evidence_status: "code read"
  - finding: "WR-07 / IN-07: verifiers assert weakly (non-empty title only; redirect probe covers only Location /login/, not the sanitising, the 200-char cap, or a malformed Location, which is why WR-09 went undetected)."
    category: other
    reason: "Verifier-strength gaps, not product defects. The Location-sanitising behaviour was not re-tested by me beyond the /login/ case."
    evidence_status: "per 22-REVIEW.md plus reading the probe"
  - finding: "WR-08: paperless_upload.queue_name is not checked against printers[].name."
    category: other
    reason: "Requires the operator to pick identical names."
    evidence_status: "code read (unchanged since prior report)"
  - finding: "IN-08: only HTTP 200 counts as success; 201/202/204 are retried and eventually dead-lettered although the upload may have been accepted."
    category: other
    reason: "Deliberate, documented in DOCS.md and the docstring (22-04 design decision); verified by the host probe (202 and 204 rows return False)."
    evidence_status: "probe run plus code read"
  - finding: "IN-01..IN-06: cosmetic / informational (internal '(WR-05)' token in a log line, collision_tag edge, falsy-zero coercion, DOCS/docstring sidecar disagreement, world-writable stage dirs, avahi_guard_start comment)."
    category: other
    reason: "None touches a locked decision."
    evidence_status: "per 22-REVIEW.md"
human_verification: []
---

# Phase 22: cups-paperless-ngx-pdf-document-upload Verification Report

**Phase Goal:** Add a second, PDF-only virtual printer queue to the `cups` add-on (via `cups-pdf`), separate from and
non-disruptive to the existing physical Brother-MFC-7460DN queue, whose output is picked up by a decoupled background
worker and uploaded to a paperless-ngx instance's REST API. The worker must be resilient to paperless-ngx being
unreachable: retry/backoff, never crash, never block cupsd or the physical printer.

**Verified:** 2026-10-04T19:10:00Z
**Status:** passed
**Re-verification:** Yes, after gap-closure plan 22-04 (CR-01 redirect handling). The prior report (2026-10-04T18:10,
gaps_found 17/18) failed truth 18 only.

## Re-verification summary

Plan 22-04 changed `cups/upload-worker.py`, `internal/verify-cups-paperless-upload.sh`, `cups/DOCS.md`,
`cups/config.yaml` (0.1.0-16 -> 0.1.0-17) and added `internal/verify-cups-upload-worker.py`. `generate_config.py`,
`run.sh`, `Dockerfile`, `avahi-guard.sh`, `README.md` and the translations are unchanged since the prior verification
(`git diff 4467249 HEAD --stat`), so truths that depend only on them were regression-checked via the fresh end-to-end
probe rather than re-derived.

### Truth 18 (the previously failed gap): VERIFIED

I did not trust the summary. Evidence gathered in this run:

- Code read: `upload_document()` now calls `requests.post(..., allow_redirects=False)`. Any 3xx logs one WARNING
  (status, sanitised redirect target, "redirects are not followed; set paperless_upload.url to the final address") and
  returns False. Success requires `status_code == 200` AND `_is_task_id_body()` (response body parses as a non-empty
  JSON string). Every other 2xx, non-2xx, and 200 with a bad body returns False. `attempt_and_route()` is untouched, so
  the existing D-09 retry and D-15 single-WARNING behaviour is reused.
- Re-ran my own reproduction of the original CR-01 case against the real `upload_document()`: stub answers
  `POST -> 302 Location: /login/`, `GET /login/ -> 200`. Result now: `False`, request log `['POST']` (no GET followed),
  WARNING printed. Control case (stub answers POST with 200 and body `"abc-task"`): `True`, `INFO: uploaded ...`.
- Host-side probe `python3 internal/verify-cups-upload-worker.py`: exit 0, 50 PASS, 0 FAIL, "ALL CHECKS PASSED".
  It covers the 301/302/303/307/308 matrix, retry-to-`failed/` routing with exactly one `upload exhausted` line, and the
  body matrix (valid id, object, HTML, empty, empty/blank JSON string, 202, 204).
- RED-proof: the same probe against the pre-fix worker (`git show 4467249:cups/upload-worker.py`, via `--worker PATH`)
  exits 1, so the probe genuinely detects the defect.
- Real-image Docker verifier `bash internal/verify-cups-paperless-upload.sh`: exit 0, "ALL CHECKS PASSED", 31 PASS and
  0 FAIL across Scenarios 1-5. Scenario 5 (redirecting stub) asserts: PDF ends in `failed/`, `sent/` empty, no GET
  recorded, at least two POSTs, exactly one exhausted WARNING, redirect-refusal WARNING names `/login/`, no
  `INFO: uploaded` line, token absent from logs.
- Docs: `cups/DOCS.md` now states `sent/` means HTTP 200 with the task id, and lists "Redirects are not followed" and
  "`sent/` means accepted, not processed" under Known limitations.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With `paperless_upload.enabled` false (shipped default) the add-on behaves as before: no queue, no cups-pdf.conf, no outbox dirs, no worker activity (D-07) | ✓ VERIFIED | `config.yaml` options read this run: `enabled: False`. Docker verifier Scenario 2 passes. Worker `main()` returns after one INFO line when disabled. generate_config.py unchanged since last verified run. |
| 2 | When enabled, printing to the queue yields a PDF uploaded via `POST /api/documents/post_document/` with multipart `document` + `title` and `Authorization: Token <token>` (D-01/D-10) | ✓ VERIFIED | Scenario 1 passes against the real image with the stub now speaking the real body shape; direct run of `upload_document()` returns True for HTTP 200 + task-id string. |
| 3 | Unrecoverable title falls back to a timestamp title, including for a non-dict JSON sidecar (D-11) | ✓ VERIFIED | `read_title()` unchanged in logic; fallback title `Scan_2026-10-04_...` seen in this run's direct repro; Scenario 4 passes. |
| 4 | A PostProcessing hook failure never blocks or fails the print job (D-13) | ✓ VERIFIED | Hook generator untouched; Scenario 1 prints a real job end to end; worker remains a separate backgrounded process. (Hook unit-run was done in the prior verification on unchanged code.) |
| 5 | After retry/backoff exhaustion the document moves to `failed/` (never deleted), exactly one WARNING (D-15) | ✓ VERIFIED | Scenario 3 (6 PASS), Scenario 5 and host-probe routing checks all show PDF in `failed/` and exactly one exhausted WARNING. Caveat: WR-09 malformed-Location path bypasses exhaustion (advisory). |
| 6 | The cups-pdf queue's UUID is stable across restarts via the same fixup as physical printers (D-08) | ✓ VERIFIED (structural) | `generate_config.py` and `run.sh` unchanged since the prior structural check; no live restart test. |
| 7 | `paperless_upload.token` is never printed to add-on logs | ✓ VERIFIED | Token-absent assertion passes in all 5 Docker scenarios and in every host-probe case (including the new redirect, bad-body and 202/204 rows). |
| 8 | `cups/DOCS.md` documents every `paperless_upload` option with default and purpose | ✓ VERIFIED | Section present and extended by 22-04 (prettier-reflowed, content intact). |
| 9 | DOCS Design notes record the corrected `PostProcessing` mechanism | ✓ VERIFIED | Unchanged section. |
| 10 | `README.md` Features mentions paperless-ngx upload | ✓ VERIFIED | File unchanged since prior verification. |
| 11 | `internal/verify-cups-paperless-upload.sh` passes | ✓ VERIFIED | Fresh run: exit 0, ALL CHECKS PASSED (31 PASS, 0 FAIL, 5 scenarios). shellcheck clean. |
| 12 | Version bump with 3-file sync | ✓ VERIFIED | `make validate-versions` passes; cups `config.yaml` is `0.1.0-17`. |
| 13 | Non-dict `.json` sidecar degrades to timestamp title | ✓ VERIFIED | Code unchanged; Scenario 4 passes. |
| 14 | Non-dict/malformed `.retry.json` does not abort the `processing/` scan | ✓ VERIFIED | `is_due()` still inside the per-document try/except in `poll_once`; Scenario 4 passes. |
| 15 | Same-name collision into `sent/`/`failed/` never overwrites a retained file | ✓ VERIFIED | `unique_destination()` call sites unchanged; Scenario 4 passes. |
| 16 | Scenarios 1-3 still pass after the 22-03 fixes and Phase 21 rework | ✓ VERIFIED | Fresh Docker run, no FAIL lines. |
| 17 | Scenario 4 proves the three 22-03 fixes against a real built image | ✓ VERIFIED | Fresh Docker run, no FAIL lines. |
| 18 | A document is recorded as `sent/` only when paperless-ngx actually accepted the POST | ✓ VERIFIED | See "Truth 18" section: direct repro, 50-check host probe (RED against pre-fix worker), Scenario 5 on a real image. |

**Score:** 18/18 truths verified (0 present-but-behavior-unverified)

### D-01..D-15 accounting

All 15 decisions remain satisfied as in the prior report; 22-04 touches D-01 (success classification), D-09 (retry reuse)
and D-15 (single WARNING) only by tightening `upload_document()`'s return value, and each is re-evidenced by the host
probe and Scenarios 3 and 5. No REQUIREMENTS.md IDs map to this ad-hoc phase (no orphaned requirements).

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `cups/upload-worker.py` | ✓ VERIFIED | Substantive, wired from `run.sh`/Dockerfile (unchanged), py_compile OK, CR-01 fixed. WR-09 advisory. |
| `internal/verify-cups-upload-worker.py` | ✓ VERIFIED | New, executable, 278 lines, 50 checks, RED against pre-fix worker, `--worker PATH` option works. Manual tool (not in pre-commit). |
| `internal/verify-cups-paperless-upload.sh` | ✓ VERIFIED | Scenario 5 present and passing; shellcheck clean. |
| `cups/DOCS.md`, `cups/config.yaml` | ✓ VERIFIED | Redirect/`sent/` semantics documented; version 0.1.0-17 with 3-file sync. |
| `generate_config.py`, `run.sh`, `Dockerfile`, `avahi-guard.sh`, `README.md`, translations | ✓ VERIFIED | Unchanged since the prior verification. |

### Key Link Verification

| From | To | Status |
|---|---|---|
| `upload_document()` return value | `sent/` routing in `attempt_and_route()` | ✓ WIRED: True only for HTTP 200 + task-id string; redirects return False and flow into retry then `failed/` (Scenario 5) |
| `requests.post` | no redirect follow | ✓ `allow_redirects=False` at the call site |
| `run.sh` -> `upload-worker.py` | background process | ✓ unchanged and intact |
| `cups_pdf_queue_name` -> UUID fixup | `generate_config.py` | ✓ unchanged and intact |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| 302 -> /login/ (CR-01) not followed | repro script importing `upload-worker.py`, stub POST 302, GET 200 | `False`, requests `['POST']` | ✓ PASS |
| HTTP 200 + task id accepted | same stub, POST 200 `"abc-task"` | `True` | ✓ PASS |
| Malformed Location (WR-09) | stub POST 302 `Location: http://[::1/x` | `ValueError: Invalid IPv6 URL` raised out of `upload_document()` | ✗ advisory (see frontmatter) |
| Compile | `python3 -m py_compile` on worker, generate_config, probe | OK | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| `internal/verify-cups-upload-worker.py` | `python3 internal/verify-cups-upload-worker.py` | exit 0, 50 PASS, 0 FAIL | PASS |
| same, pre-fix worker | `... --worker <worktree copy of 4467249:cups/upload-worker.py>` | exit 1 | PASS (RED proven) |
| `internal/verify-cups-paperless-upload.sh` | `bash internal/verify-cups-paperless-upload.sh` | exit 0, 31 PASS, 0 FAIL, ALL CHECKS PASSED | PASS |
| `make validate-versions` | repo root | "Version validation passed for all add-ons!" | PASS |
| `shellcheck -e SC1091 -e SC2034` | verifier, `run.sh`, `avahi-guard.sh` | clean | PASS |

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK` markers in the files changed by 22-04.

| File | Pattern | Severity | Impact |
|---|---|---|---|
| `cups/upload-worker.py` (`_safe_redirect_target`, `upload_document`) | `urlsplit()` outside any try; "Never raises" docstring false for malformed Location (and for `pdf_path.open()` OSError) | ⚠️ Warning (WR-09) | Document re-POSTed every 20 s in that case, bypasses retry cap; no false delivery |
| `cups/upload-worker.py` (`poll_once`) | no settle/age check | ⚠️ Warning (WR-01) | Possible truncated upload |
| `cups/upload-worker.py` | WR-02, WR-03, WR-04, WR-05, WR-06 | ⚠️ Warning | Narrow-precondition defects, unchanged |
| `cups/generate_config.py` | WR-08 name collision | ⚠️ Warning | Operator error only |
| verifiers | WR-07, IN-07 | ⚠️ Warning | Test-strength gaps |

`22-REVIEW-DISPOSITION.md` is current: CR-01 `fixed`; the 17 other findings are `open` by design.

### Human Verification Required

None. Real paperless-ngx behind a real proxy, AirPrint clients and live mDNS remain outside automated scope (the probes
use a stub server speaking the documented response shape).

### Gaps Summary

No blocking gaps. The only must-have that failed previously (truth 18 / CR-01) is closed with direct, reproduced
evidence, and no regression was found in truths 1-17. One fix-introduced defect (WR-09) is flagged as the top advisory
with a human-decision request: it does not falsify a declared truth and produces no false delivery or data loss, but it
does let a document ride an unbounded 20-second re-POST loop when a proxy sends a malformed `Location` header. It is a
two-line fix and is the best candidate for a follow-up together with WR-01.

---

_Verified: 2026-10-04T19:10:00Z_
_Verifier: Claude (gsd-verifier)_
