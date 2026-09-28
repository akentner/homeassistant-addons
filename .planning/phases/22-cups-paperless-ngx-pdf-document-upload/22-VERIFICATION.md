---
phase: 22-cups-paperless-ngx-pdf-document-upload
verified: 2026-09-28T21:15:00Z
status: gaps_found
score: 10/12 must-haves verified
covered_files:
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-01-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-01-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-PLAN.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-02-SUMMARY.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-CONTEXT.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-DISCUSSION-LOG.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-PATTERNS.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW-DISPOSITION.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/COVERAGE.md
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
covered_digest: "v2:sha256:6e3912ca1238f7f7989ceed8e7067819cd135004625d5a882c6e0827b9c258ab"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "If the original title cannot be recovered, the upload still proceeds using a timestamp-based fallback title — the upload is never skipped for a missing title (D-11)"
    status: partial
    reason: "read_title() (cups/upload-worker.py:90-112) only catches (OSError, ValueError, json.JSONDecodeError) around the sidecar parse. If the `.json` sidecar contains syntactically-valid JSON that is not an object (null, [], a bare string/number — reachable because the outbox is chmod 0o777 and writable by the resolved job user, not just this add-on's own hook script), `json.loads(...).get(\"title\")` raises an uncaught AttributeError. That exception fires before any request is sent and before any retry-state is written, so the document never reaches sent/ or failed/ — it is silently re-attempted every ~20s forever with no backoff, contradicting the literal 'never skipped' guarantee. This is code-review finding WR-02 (22-REVIEW.md), disposition still 'open' in 22-REVIEW-DISPOSITION.md."
    artifacts:
      - path: "cups/upload-worker.py"
        issue: "read_title() indexes a parsed JSON value with .get() without first checking isinstance(parsed, dict)"
    missing:
      - "Validate the parsed sidecar JSON is a dict before calling .get(\"title\") on it; fall back to the timestamp title on any non-dict/non-parseable content, per the fix already proposed in WR-02."
  - truth: "Once retry/backoff is exhausted, the document moves to failed/ (never deleted) and exactly one WARNING-level log line is emitted, visible via docker logs (D-15)"
    status: partial
    reason: "Confirmed by direct code read: is_due() (upload-worker.py:154-164) is called at upload-worker.py:297, OUTSIDE the per-document try/except that wraps process_due_retry() at upload-worker.py:299-302. If a `<basename>.retry.json` file ever contains valid-but-non-dict JSON (disk corruption, a partial/interrupted write, or any other local process exploiting the 0o777-writable processing/ directory), `state[\"next_attempt_at\"]` raises an uncaught TypeError (only KeyError/ValueError are caught) that propagates out of poll_once() entirely -- past the per-document guards -- and is only stopped by main()'s outer per-cycle try/except. Because sorted(PROCESSING.glob(\"*.pdf\")) is deterministic, every document that sorts alphabetically AFTER the poisoned file is silently skipped on every future poll cycle forever: never retried, never routed to failed/, and the only log line emitted is a generic 'poll cycle failed' with no filename. This directly contradicts the module's own documented per-document isolation design and the phase's resilience goal ('retry/backoff, never crash, never block cupsd or the physical printer' -- ROADMAP.md Phase 22 goal text). This is code-review finding CR-01 (Critical, 22-REVIEW.md), disposition still 'open' in 22-REVIEW-DISPOSITION.md, independently re-confirmed by this verification by reading the exact cited lines in the current working tree. A second, related concern (WR-05, also open) further threatens the literal 'never deleted' half of this same truth: because /etc/cups/ (and cupsd's own spool/job-id counter) is not persisted outside /data (confirmed at cups/generate_config.py:48/63/1118, cups/DOCS.md:297), cupsd's job IDs restart from a low number on every add-on restart, while sent/ and failed/ ARE under the persistent /data volume -- so a document with the same title printed in a later container lifetime can silently overwrite an already-retained sent/failed/ file via Path.replace()'s POSIX rename-clobber semantics (upload-worker.py:230/238-240), with no collision check and no log line."
    artifacts:
      - path: "cups/upload-worker.py"
        issue: "is_due() call at line 297 sits outside the try/except at lines 299-302; load_retry_state() does not validate the parsed JSON is a dict before it (or its caller) indexes it"
    missing:
      - "Move the is_due() call inside the same per-document try/except as process_due_retry() (or make load_retry_state()/is_due() reject non-dict parsed JSON explicitly), per CR-01's proposed fix."
      - "Add a destination-exists check (or a disambiguating suffix) before the final Path.replace() into sent/ and failed/, per WR-05's proposed fix, so a job-ID reset after restart cannot silently destroy an already-retained document."
deferred: []
advisory: []
human_verification: []
---

# Phase 22: cups-paperless-ngx-pdf-document-upload Verification Report

**Phase Goal:** Add a second, PDF-only virtual printer queue to the `cups` add-on (via `cups-pdf`), separate from and
non-disruptive to the existing physical Brother-MFC-7460DN queue, whose output is picked up by a decoupled background
worker and uploaded to a paperless-ngx instance's REST API. The worker must be resilient to paperless-ngx being
unreachable — retry/backoff, never crash, never block cupsd or the physical printer.

**Verified:** 2026-09-28T21:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Must-haves merged from both plans' frontmatter (`22-01-PLAN.md`, `22-02-PLAN.md`) — ROADMAP.md's Phase 22 entry has
no separate numbered "Success Criteria" list (its goal/decision text IS the contract), so the plan-level `must_haves`
are the full must-have set for this ad-hoc phase.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When `paperless_upload.enabled` is false (shipped default), the add-on behaves byte-for-byte as before — no cups-pdf queue, no cups-pdf.conf, no outbox dirs, no worker network activity (D-07) | ✓ VERIFIED | Independently re-ran `internal/verify-cups-paperless-upload.sh` Scenario 2: `verify-pdf-queue not registered`, `/data/paperless_upload not created`, `cups-pdf.conf has no active paperless_upload directives` — all PASS. Code: `build_cups_pdf_conf`/`build_cups_pdf_registration_snippet` both return `(None, None)`/`None` on disabled, and `main()` gates every write (conf, outbox mkdir, hook) behind the non-`None` check (`generate_config.py:1458-1477`). `upload-worker.py`'s own `load_paperless_config()` independently gates and exits before touching the filesystem. |
| 2 | When enabled, printing to the configured queue produces a PDF uploaded to `POST /api/documents/post_document/` with multipart `document` + `title`, `Authorization: Token <token>` (D-01/D-10) | ✓ VERIFIED | Scenario 1 PASS on all 6 assertions (queue registered, device URI, PDF in sent/, stub received POST, `Authorization: Token verify-fake-token` header present, non-empty `title` field, correct path). Verified myself via a fresh `bash internal/verify-cups-paperless-upload.sh` run (see Probe Execution below) — not just SUMMARY's claim. |
| 3 | If the original title cannot be recovered, upload proceeds with a timestamp fallback — never skipped for a missing title (D-11) | ✗ FAILED (edge case) | Happy-path scenarios only exercise the well-formed-sidecar case. Code-level defect confirmed by direct read of `cups/upload-worker.py:90-112`: a syntactically-valid-but-non-dict `.json` sidecar raises an uncaught `AttributeError` in `read_title()`, which is not one of D-11's two documented outcomes (deliver-with-real-title / deliver-with-fallback-title) — the document is instead retried forever with no backoff. See `gaps` entry above (= review finding WR-02, disposition `open`). |
| 4 | A PostProcessing hook failure never blocks or fails the underlying print job — cupsd and the physical printer queue are provably unaffected (D-13) | ✓ VERIFIED | `build_paperless_postprocess_hook()`'s generated script wraps the embedded `python3` invocation so a non-zero exit does not propagate (`generate_config.py` hook body, confirmed by reading the function); the hook only ever writes a best-effort title sidecar, never touches cupsd or the physical queue. `cups-pdf`'s own `PostProcessing` call is a fire-and-forget `system()` per the phase's own `<researched_correction>`, independently confirmed correct in 22-01-SUMMARY.md's deviation log (directive name fix). |
| 5 | Once retry/backoff is exhausted, the document moves to `failed/` (never deleted) and exactly one WARNING-level log line is emitted (D-15) | ✗ FAILED (edge case) | Scenario 3 (retry exhaustion against a stub forced to 500) PASSES for the well-formed-state path: document in `failed/`, sidecar alongside it, exactly one `WARNING: paperless-ngx upload exhausted` line, `processing/` empty afterward — confirmed by my own fresh run, not just SUMMARY's claim. However, the code-level poison-pill defect (CR-01) and the restart/job-ID-collision silent-overwrite defect (WR-05) both directly threaten the "never deleted" / "exactly one WARNING line" guarantees under realistic conditions the verify script's 3 scripted scenarios do not exercise. See `gaps` entry above. |
| 6 | The cups-pdf queue's printer UUID is stable across container restarts via the same fixup mechanism as physical printers (D-08) | ✓ VERIFIED | `generate_config.py:main()` appends `cups_pdf_queue_name` into `registered_printer_names` (line ~1430) BEFORE `build_printer_uuid_fixup_script(registered_printer_names)` is called — the fixup script is generic over every name in that list with zero cups-pdf-specific code, so D-08 coverage is structural, not incidental. 22-01-SUMMARY.md records an ad-hoc (not scripted) empirical restart test confirming a byte-identical UUID; I did not independently re-run a live restart test (would require a dedicated docker-restart harness not present in the committed verify script), so this rests on strong wiring evidence plus the executor's own empirical note rather than a re-run by me. |
| 7 | `paperless_upload.token` is never printed in plaintext to any add-on log output | ✓ VERIFIED (advisory) | All 3 scenarios assert the fixture token string never appears in `docker logs` — confirmed PASS in my own fresh run. Advisory: code-review finding WR-06 (open) correctly notes this only proves the two tested stub response bodies are safe, not that `upload_document()`'s unconditional `response.text.strip()[:200]` logging is safe against an arbitrary upstream/proxy echoing the `Authorization` header back in a response body — a real but currently-untriggered risk, not a demonstrated failure. |
| 8 | `cups/DOCS.md` documents every `paperless_upload` option with default + purpose, matching the existing Options table + Design notes convention | ✓ VERIFIED | `## Paperless-ngx PDF Upload` section present with a full 8-row field table (`enabled`, `queue_name`, `location`, `url`, `token`, `timeout`, `retry_count`, `retry_delay`), defaults byte-for-byte matching `cups/config.yaml`'s shipped `options.paperless_upload` block (`false`/`"PDF-to-DMS"`/`""`/`""`/`""`/`30`/`5`/`60`). |
| 9 | `cups/DOCS.md`'s Design notes record the corrected `PostProcessing` (not env-var) title-derivation mechanism | ✓ VERIFIED | `grep -n 'PostProcessing\|environment variable' cups/DOCS.md` shows the correction paragraph explicitly stating the 3-positional-argument model and explaining the title is derived from `$1`'s basename, not an env var. |
| 10 | `cups/README.md`'s Features list mentions the paperless-ngx upload capability | ✓ VERIFIED | One new bullet present (`grep -c 'paperless-ngx' cups/README.md` = 1), reuses the existing single `[docs]: DOCS.md` link (count = 1, no duplicate). |
| 11 | Re-running `internal/verify-cups-paperless-upload.sh` after documentation changes still passes | ✓ VERIFIED | Independently re-ran the full script myself against the current working tree (see Probe Execution below) — exit code 0, all 3 scenarios PASS. |
| 12 | `cups/config.yaml`'s version is bumped via `make update-version`, and `make validate-versions` confirms 3-file consistency | ✓ VERIFIED | `cups/config.yaml` shows `version: "0.1.0-14"`; `cups/build.yaml` VERSION=`0.1.0`; `cups/README.md` shield badge `v0.1.0` (base unchanged, only subpatch moved, as documented/expected). Independently re-ran `make validate-versions` myself — exits 0, "Version validation passed for all add-ons!" including `cups`. |

**Score:** 10/12 truths verified (2 FAILED as edge-case gaps; 0 present-but-behavior-unverified)

### Requirements Coverage

Per the task framing, this phase's requirement IDs (D-01..D-15) are tracked ONLY in `22-CONTEXT.md` and both plans'
SUMMARY frontmatter (`requirements-completed:` / `coverage:`), never in `.planning/REQUIREMENTS.md`'s checkbox
tables. Confirmed: `grep -n "Phase 22\|cups-pdf\|paperless" .planning/REQUIREMENTS.md` returns zero matches — no
D-01..D-15 IDs, no Phase-22 section, appear anywhere in that file. This is a known, pre-existing phase-scaffolding
gap (this phase is "ad-hoc" per its own ROADMAP heading, not sourced from a REQUIREMENTS.md milestone slice), already
flagged by 22-02's own executor per the task brief. **Not treated as a verification failure** — documented here per
instruction, not actionable within this phase's scope.

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| D-01..D-15 | 22-01-PLAN.md, 22-02-PLAN.md | See CONTEXT.md decisions | See Observable Truths #1-12 above | Not present in REQUIREMENTS.md (known gap, out of scope) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `cups/upload-worker.py` | Background outbox worker | ✓ VERIFIED (with defects) | Exists, substantive, wired (launched from `run.sh`, PID-tracked, killed in shutdown trap). Functionally complete for the happy/failure paths tested; contains the CR-01/WR-02/WR-05 defects noted above. |
| `cups/generate_config.py` (`build_cups_pdf_conf`, `build_paperless_postprocess_hook`, `build_cups_pdf_registration_snippet`) | Three new functions | ✓ VERIFIED | All three present (`grep -n` confirms), wired into `main()` in the correct order relative to `registered_printer_names`/UUID fixup. |
| `cups/config.yaml` (paperless_upload options + schema) | New option block | ✓ VERIFIED | `options.paperless_upload` + `schema.paperless_upload` present, `token` typed `password?`. |
| `internal/verify-cups-paperless-upload.sh` | Dedicated verify harness | ✓ VERIFIED | 476 lines, 3 scenarios, independently re-run by this verification with exit code 0. |
| `cups/DOCS.md` | Feature docs | ✓ VERIFIED | New subsection + Design notes paragraph present, defaults cross-checked byte-for-byte against config.yaml. |
| `cups/README.md` | Features bullet | ✓ VERIFIED | One bullet, reuses existing docs link. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `build_cups_pdf_registration_snippet()`'s `queue_name` | `build_printer_uuid_fixup_script()`'s `registered_printer_names` | Appended in `main()` before the fixup script is generated | ✓ WIRED | Confirmed at `generate_config.py` main(): snippet appended to `register_script`, `queue_name` appended to `registered_printer_names`, BOTH before `build_printer_uuid_fixup_script(registered_printer_names)` is called. |
| PostProcess hook's derived title | `.json` sidecar → `upload-worker.py`'s title read → paperless-ngx's `title` field | Sidecar written by hook, read by `read_title()`, sent as multipart `data={"title": title}` | ✓ WIRED (with WR-02 edge-case defect) | End-to-end path confirmed structurally and empirically (Scenario 1's non-empty title assertion passed against a real print job). The malformed-sidecar edge case (non-dict JSON) is not handled per WR-02 — see gaps. |
| `run.sh` → `upload-worker.py` | Backgrounded process, PID tracked, killed in shutdown trap | Same pattern as `print-history-poller.py` | ✓ WIRED | `python3 /upload-worker.py &` + `UPLOAD_WORKER_PID=$!` + `kill -TERM "$UPLOAD_WORKER_PID"` in the trap, confirmed via `grep`. |

### Probe Execution

Per Step 7c, ran the phase's dedicated probe myself rather than trusting SUMMARY.md's PASS claims.

| Probe | Command | Result | Status |
|---|---|---|---|
| `internal/verify-cups-paperless-upload.sh` | `bash internal/verify-cups-paperless-upload.sh` (run from repo root, real docker build+run, no flags/mocks) | Exit code 0. All 18 individual PASS assertions across Scenario 1 (happy path), Scenario 2 (D-07 disabled regression), Scenario 3 (retry exhaustion/D-15) printed `PASS`; final line `internal/verify-cups-paperless-upload.sh: ALL CHECKS PASSED` | PASS |
| `make validate-versions` | `make validate-versions` (repo root) | Exit 0, `cups: config.yaml 0.1.0-14 / build.yaml 0.1.0 / README.md 0.1.0`, "Version validation passed for all add-ons!" | PASS |

Note: the probe's 3 scripted scenarios do not exercise the CR-01 (corrupted `.retry.json`) or WR-02 (corrupted `.json` title sidecar) edge cases — those are code-level defects confirmed by direct source inspection, not by an automated test that currently exists in this repo.

### Anti-Patterns Found

Carried forward from `22-REVIEW.md` / `22-REVIEW-DISPOSITION.md` (all disposition `open` — none fixed, skipped, or
deferred since the review ran). I independently re-read and confirmed the cited code for CR-01, WR-01, WR-02, WR-05
myself (see line-level evidence in the `gaps` section and table below); WR-03/WR-04/WR-06/IN-01/IN-02 are taken as
correctly characterized by the review on inspection of the same files.

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `cups/upload-worker.py` | 292-302 | `is_due()` called outside the per-document `try/except` in the `processing/` retry loop | 🛑 Blocker (CR-01) | A non-dict `.retry.json` silently and permanently stalls every alphabetically-later document — confirmed via direct code read, causes gap #2 above |
| `cups/upload-worker.py` | 90-112 | `read_title()` calls `.get("title")` on parsed JSON without an `isinstance(dict)` check | ⚠️ Warning (WR-02) | A non-dict `.json` sidecar breaks the "never skipped" title-fallback guarantee for that document — causes gap #1 above |
| `cups/upload-worker.py` | 174-176, 234-235 | `config.get(key, default) or default` | ⚠️ Warning (WR-01) | An operator-set `0` for `timeout`/`retry_count`/`retry_delay` is silently replaced by the default |
| `cups/generate_config.py` | 782-844, 913-988 | No validation that `url`/`token` are non-empty when `enabled: true` | ⚠️ Warning (WR-03) | Misconfiguration produces silent, hard-to-diagnose upload failures rather than a clear warning |
| `cups/generate_config.py` | 991-1109, 913-988, ~1428-1433 | No uniqueness check between `paperless_upload.queue_name` and `printers[].name` | ⚠️ Warning (WR-04) | A name collision silently reconfigures the physical printer's device URI to `cups-pdf:/` |
| `cups/upload-worker.py` | 230, 238-240 | `Path.replace()` into `sent/`/`failed/` with no destination-exists check | ⚠️ Warning (WR-05) | Job-ID reset after a container restart (cupsd's own state is not persisted, confirmed at `generate_config.py:48/63/1118`) can silently overwrite an already-retained document — compounds gap #2 above |
| `cups/upload-worker.py` | 195-208 | Response body logged verbatim, unconditionally | ⚠️ Warning (WR-06) | "Token never leaks" is proven only for the two tested stub bodies, not in general |
| `cups/generate_config.py` | 703-779, 913-988 | Duplicated PPD-resolution shell-generation logic | ℹ️ Info (IN-01) | Maintenance risk, not a functional defect |
| `cups/DOCS.md` | 345-347 | "Migrating from f1c878cb_cups" section is a content-free placeholder | ℹ️ Info (IN-02) | Pre-dates this phase (21-03's migration section), out of Phase 22's own scope, but still shipping with no content |

No new `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` debt markers were introduced by this phase's modified files
(checked directly: zero hits across `cups/upload-worker.py`, `cups/generate_config.py`, `cups/config.yaml`,
`cups/Dockerfile`, `cups/run.sh`, `cups/DOCS.md`, `cups/README.md`, `internal/verify-cups-paperless-upload.sh`,
`cups/translations/{de,en}.yaml`). IN-02's placeholder text uses prose ("filled in by a later plan"), not a literal
debt marker, and predates this phase — not gated here.

### Gaps Summary

Two of the phase's must-have truths (D-11's "never skipped for a missing title" and D-15's "moves to failed/ (never
deleted) ... exactly one WARNING line") are **not fully achieved** in edge cases that the phase's own verify script
does not exercise:

1. **CR-01 (Critical, still open):** `upload-worker.py`'s retry-state read (`is_due()`) is not inside the
   per-document error boundary the module's own docstring claims covers "one malformed document" — a corrupted or
   unexpectedly-shaped `.retry.json` file silently and permanently stalls every alphabetically-later document in
   `processing/`, contradicting the phase's stated resilience goal ("retry/backoff, never crash, never block cupsd
   or the physical printer" — ROADMAP.md). The worker process itself does not crash and cupsd is unaffected, but the
   upload pipeline's own resilience promise for the affected subset of documents is not met.
2. **WR-02 (Warning, still open), compounding gap #1's theme:** a malformed title sidecar similarly breaks D-11's
   literal "never skipped" guarantee (the document is retried forever with no backoff, never converging to
   `sent/`/`failed/`).
3. **WR-05 (Warning, still open):** because cupsd's job-ID counter is not persisted across restarts while `sent/`/
   `failed/` are, a same-titled document printed in a later container lifetime can silently overwrite an
   already-retained file — undermining D-15's literal "never deleted" guarantee.

All three are pre-existing, disposition-`open` findings from `22-REVIEW.md`/`22-REVIEW-DISPOSITION.md` — this
verification independently re-confirmed the root-cause code for CR-01, WR-02, and WR-05 by direct inspection of the
current working tree (not by trusting the review's prose alone), and additionally re-ran the phase's own verify
script and `make validate-versions` myself rather than relying on SUMMARY.md's claims.

Everything else — the D-07 disabled-by-default regression, the D-01/D-02/D-05/D-08/D-10/D-13 happy-path mechanics,
the D-09/D-15 retry-exhaustion happy path, token-never-logged (tested scenarios), and the full Plan 02 documentation
+ version-bump deliverables — is genuinely implemented, wired, and independently re-verified working in this
codebase, not just claimed in the SUMMARYs.

**This looks like it needs a small, targeted closure plan, not a re-litigation of the phase's design.** The three
gaps share one root cause category (defensive validation of untrusted/possibly-corrupted state files under a
0o777-writable outbox) and one architecturally-adjacent cause (job-ID-based filename uniqueness not surviving
restarts) — CR-01's and WR-02's fixes are both small, already spelled out verbatim in 22-REVIEW.md, and WR-05's fix
is a straightforward destination-exists check before the two `Path.replace()` calls.

---

_Verified: 2026-09-28T21:15:00Z_
_Verifier: Claude (gsd-verifier)_
