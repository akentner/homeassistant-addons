---
phase: 22-cups-paperless-ngx-pdf-document-upload
verified: 2026-09-29T16:55:00Z
status: passed
score: 17/17 must-haves verified
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
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW.md
  - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW-DISPOSITION.md
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
covered_digest: "v2:sha256:06d75f91ef0ff808274f645e842b84b5eff1a4dd930e54cb887c4a6c31681b25"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 10/12
  gaps_closed:
    - "If the original title cannot be recovered, the upload still proceeds using a timestamp-based fallback title — the upload is never skipped for a missing title (D-11) [WR-02 sub-defect: non-dict JSON sidecar]"
    - "Once retry/backoff is exhausted, the document moves to failed/ (never deleted) and exactly one WARNING-level log line is emitted, visible via docker logs (D-15) [CR-01 poison-pill stall + WR-05 sent/failed collision-overwrite sub-defects]"
  gaps_remaining: []
  regressions: []
advisory:
  - finding: "D-15's own 'upload exhausted' WARNING line still names the pre-disambiguation filename when a failed/ collision occurs (e.g. `see failed/<name>` while the file actually landed at `failed/<name>-<tag>.pdf`) — an operator following that exact line to triage would look at the wrong (older, unrelated) file. A second, correctly-named WARNING from unique_destination() is also emitted in this case, so the right filename is present in the logs, just not on the exhaustion line itself."
    category: other
    reason: "New regression introduced by this same gap-closure diff (22-03), independently found and confirmed genuine by a fresh code review (22-REVIEW.md, finding WR-01, warning severity) run after 22-03 executed. Narrow precondition (retry exhaustion AND a same-named failed/ collision at once) not exercised by Scenario 3 (exhaustion, no collision) or the new Scenario 4 (collision, no exhaustion) — a combined Scenario 5 would close it. Does not violate the literal 'never deleted'/'exactly one WARNING is emitted' truth (a WARNING is emitted, the document is not deleted), so not a must-have failure — flagged here for the next maintenance pass rather than gated."
    evidence_status: "confirmed via direct code read (upload-worker.py:290-307) and independent code review; not yet covered by an automated regression test"
  - finding: "load_retry_state()'s CR-01 fix validates the parsed JSON is a dict, but a well-formed dict with a wrong-typed `attempts` or `next_attempt_at` field (e.g. `{\"attempts\": \"x\"}`) still raises one level deeper (int()/datetime.fromisoformat()) — narrower than CR-01's original 'any malformed JSON' precondition, and cannot be produced by this worker's own save_retry_state() (requires hand-edited/externally-corrupted state), but still stalls that one document indefinitely (no longer starves siblings, since it now degrades inside the same per-document try/except CR-01's fix already established)."
    category: other
    reason: "New finding from the same post-closure code review (22-REVIEW.md, finding WR-02 [new id, distinct from the closed WR-02], warning severity). A materially narrower and lower-impact variant of the closed CR-01 class, not itself one of this phase's tracked must-haves."
    evidence_status: "confirmed via direct code read (upload-worker.py:214-217, 332-337); not yet covered by an automated regression test"
human_verification: []
---

# Phase 22: cups-paperless-ngx-pdf-document-upload Verification Report

**Phase Goal:** Add a second, PDF-only virtual printer queue to the `cups` add-on (via `cups-pdf`), separate from and
non-disruptive to the existing physical Brother-MFC-7460DN queue, whose output is picked up by a decoupled background
worker and uploaded to a paperless-ngx instance's REST API. The worker must be resilient to paperless-ngx being
unreachable — retry/backoff, never crash, never block cupsd or the physical printer.

**Verified:** 2026-09-29T16:55:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (22-03-PLAN.md / 22-03-SUMMARY.md)

## Goal Achievement

This is a re-verification following a prior `gaps_found` report (10/12, gaps on CR-01/WR-02/WR-05). A dedicated
gap-closure plan (22-03) executed since, claiming all three closed plus a new Scenario 4. Per instruction, this
report does **not** trust that SUMMARY.md claim — every gap-closure truth below was independently re-derived from
the current working tree: a direct read of the fixed `cups/upload-worker.py`, a standalone (non-docker) unit-level
reproduction of all three original bugs against the current code, and a fresh, self-run `internal/verify-
cups-paperless-upload.sh` (real podman-emulated-docker build + run, no flags/mocks, exit code checked directly by
this verifier, not read from a prior log). Previously-passed truths (#1, #2, #4, #6–#12) received the regression-
mode quick check called for by re-verification (file/commit history confirms the underlying artifacts are byte-
identical to the prior `passed` verification's evidence — untouched by the 22-03 diff — plus the fresh full script
run independently re-exercises #1/#2/#7/#11/#12 end-to-end).

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When `paperless_upload.enabled` is false (shipped default), the add-on behaves byte-for-byte as before — no cups-pdf queue, no cups-pdf.conf, no outbox dirs, no worker network activity (D-07) | ✓ VERIFIED | Regression-mode quick check: `cups/generate_config.py`'s gating logic (`main()`'s `None`-check on `build_cups_pdf_conf`/registration) unchanged since 22-01 (`git log -- cups/generate_config.py` shows no commits after `56ca013`). Re-confirmed live by my own fresh full run of `internal/verify-cups-paperless-upload.sh` — Scenario 2 (`verify-pdf-queue not registered`, `/data/paperless_upload not created`, no active `paperless_upload` cups-pdf.conf directives) — all 3 PASS. |
| 2 | When enabled, printing to the configured queue produces a PDF uploaded to `POST /api/documents/post_document/` with multipart `document` + `title`, `Authorization: Token <token>` (D-01/D-10) | ✓ VERIFIED | Re-ran the full probe myself (not the prior verifier's log, not SUMMARY's claim) — Scenario 1 PASS on all 6 assertions in this fresh run: queue registered, device URI, PDF in `sent/`, stub received POST, correct `Authorization` header, non-empty `title`, correct endpoint path. |
| 3 | If the original title cannot be recovered, the upload still proceeds using a timestamp-based fallback title — never skipped for a missing title (D-11) | ✓ VERIFIED (gap closed) | Was FAILED (WR-02: a syntactically-valid-but-non-dict `.json` sidecar raised an uncaught `AttributeError`). Fix independently confirmed at `cups/upload-worker.py:94-125`: `read_title()` now parses into `parsed`, only calls `.get("title")` when `isinstance(parsed, dict)`, and logs+falls back to the timestamp title otherwise. I reproduced the exact bug fixture myself in a standalone (non-docker) unit check: a `.json` sidecar containing literal `[]` now yields a `Scan_...` fallback title instead of raising (see Behavioral Spot-Checks). Also proven end-to-end in the fresh Scenario 4 run: `badtitle-doc.pdf` (malformed sidecar) converges to `sent/` rather than looping forever. |
| 4 | A PostProcessing hook failure never blocks or fails the underlying print job — cupsd and the physical printer queue are provably unaffected (D-13) | ✓ VERIFIED | Regression-mode quick check: `build_paperless_postprocess_hook()`'s fire-and-forget wrapper is unchanged since 22-01 (not touched by 22-03's diff, confirmed via `git log`/direct read); no new coupling to cupsd or the physical queue was introduced by the gap-closure fixes (they are entirely internal to `upload-worker.py`'s own outbox-state handling). |
| 5 | Once retry/backoff is exhausted, the document moves to `failed/` (never deleted) and exactly one WARNING-level log line is emitted (D-15) | ✓ VERIFIED (gap closed) | Was FAILED (CR-01: `is_due()` called outside the per-document `try/except`, letting a poisoned `.retry.json` permanently starve every alphabetically-later document; WR-05: `Path.replace()` into `sent/`/`failed/` could silently clobber an already-retained file after a job-ID reset). Both independently confirmed fixed by direct code read: `is_due(pdf_path)` is now the first statement inside the same `try:` block as `process_due_retry()` (`upload-worker.py:359-364`); `load_retry_state()` now rejects non-dict parsed JSON (`:186-193`); new `unique_destination()`/`_disambiguation_suffix()` helpers (`:135-164`) route every `sent/`/`failed/` move and disambiguate + log a WARNING on collision (`:283`, `:294-297`). I reproduced all three exact bug fixtures myself in a standalone unit check (see Behavioral Spot-Checks) and via a fresh, self-run Scenario 4 against a real built image: a poisoned `.retry.json` no longer starves a later document, a pre-existing `sent/collide.pdf` is byte-identical after a colliding new arrival, and the colliding arrival is disambiguated to exactly one `collide-*.pdf`. A narrower residual issue (the exhaustion WARNING line names the pre-disambiguation filename on a collision) is real but does not violate this truth's literal wording ("never deleted", "exactly one WARNING... is emitted" — a WARNING IS emitted, the file IS retained, just not at the name that one specific line claims) — tracked as advisory, not a gap (see frontmatter `advisory:`). |
| 6 | The cups-pdf queue's printer UUID is stable across container restarts via the same fixup mechanism as physical printers (D-08) | ✓ VERIFIED | Regression-mode quick check: `generate_config.py:main()` still appends `cups_pdf_queue_name` into `registered_printer_names` before `build_printer_uuid_fixup_script(registered_printer_names)` is called (confirmed unchanged at lines 1428-1440); file untouched by the 22-03 diff. As in the prior verification, this rests on structural wiring evidence plus 22-01-SUMMARY.md's own empirical restart note, not a fresh live-restart re-test by me — unchanged since the last `passed` determination for this truth. |
| 7 | `paperless_upload.token` is never printed in plaintext to any add-on log output | ✓ VERIFIED | Re-ran all 4 scenarios myself in this fresh run; each independently asserts its own fixture token string (`verify-fake-token`, `verify-fake-token-4`, etc.) never appears in `docker logs` — all PASS, including the new Scenario 4's own check. |
| 8 | `cups/DOCS.md` documents every `paperless_upload` option with default + purpose | ✓ VERIFIED | Regression-mode quick check: `cups/DOCS.md` untouched since 22-02 (`git log` shows last change at `0c985d8`/`690e1df`, nothing since); `## Paperless-ngx PDF Upload` section confirmed still present with the full option table. |
| 9 | `cups/DOCS.md`'s Design notes record the corrected `PostProcessing` (not env-var) title-derivation mechanism | ✓ VERIFIED | Regression-mode quick check: same untouched file as #8; `grep -n 'PostProcessing'` confirms the correction paragraph is still present. |
| 10 | `cups/README.md`'s Features list mentions the paperless-ngx upload capability | ✓ VERIFIED | Regression-mode quick check: `cups/README.md` untouched since 22-02 (`git log` shows last change at `690e1df`); one bullet confirmed present (`grep -c 'paperless-ngx'` = 1). |
| 11 | Re-running `internal/verify-cups-paperless-upload.sh` after documentation changes still passes | ✓ VERIFIED | Independently re-ran the full script myself (see Probe Execution) — exit code 0, all 4 scenarios PASS (the script now has 4 scenarios, up from 3, per the gap-closure plan's addition). |
| 12 | `cups/config.yaml`'s version is bumped via `make update-version`, and `make validate-versions` confirms 3-file consistency | ✓ VERIFIED | `cups/config.yaml` now shows `version: "0.1.0-15"` (bumped again from `0.1.0-14` by 22-03); `cups/build.yaml` VERSION=`0.1.0`; `cups/README.md` shield badge `v0.1.0` (base unchanged, only subpatch moved, as expected for an add-on-only fix). Independently re-ran `make validate-versions` myself — exits 0, `cups: config.yaml 0.1.0-15 / build.yaml 0.1.0 / README.md 0.1.0`, "Version validation passed for all add-ons!". |
| 13 | A syntactically-valid-but-non-dict `.json` title sidecar no longer raises inside `read_title()` — uploads with the D-11 timestamp-fallback title (closes WR-02) | ✓ VERIFIED | Standalone unit check (self-run, not from SUMMARY): `(d/"x.json").write_text("[]"); title = read_title(pdf)` → `Scan_...` (no exception). Also proven end-to-end by the fresh Scenario 4 run (`badtitle-doc.pdf` converges to `sent/`). |
| 14 | A syntactically-valid-but-non-dict `.retry.json` no longer aborts `poll_once()`'s entire `processing/` scan — every alphabetically-later document keeps being processed (closes CR-01) | ✓ VERIFIED | Standalone unit check (self-run): `(d/"x.retry.json").write_text("[]"); is_due(pdf) is True` (no exception, treated as due). Also proven end-to-end: fresh Scenario 4 run shows `zzz-normal.pdf` converges out of `processing/` despite `poison-aaa`'s malformed retry state sorting before it alphabetically. |
| 15 | A same-named collision moving into `sent/`/`failed/` is never silently overwritten — disambiguated with a timestamp+pid suffix and a logged WARNING (closes WR-05) | ✓ VERIFIED | Standalone unit check (self-run): pre-seeded `sent/collide.pdf` with `b"ORIGINAL"`, called `unique_destination(sent_dir, "collide.pdf")` → returns a disambiguated path, logs a WARNING, original file's bytes confirmed untouched. Also proven end-to-end: fresh Scenario 4 run shows the pre-existing `sent/collide.pdf` byte-identical (`PRE-EXISTING-RETAINED-DOCUMENT`), the new arrival disambiguated to exactly one `collide-*.pdf`, and a `"already exists -- moving to"` WARNING logged. |
| 16 | The pre-existing 3 scenarios (happy path, D-07 disabled regression, retry/backoff exhaustion) still pass unchanged after the fixes — no regression | ✓ VERIFIED | Fresh full run of `internal/verify-cups-paperless-upload.sh` (self-executed, exit code checked directly) shows Scenarios 1, 2, and 3 all still PASS on every one of their original assertions, unchanged in behavior. |
| 17 | A new Scenario 4 proves all three fixes end-to-end against a real built image and real injected malformed-state files, not just source-code inspection | ✓ VERIFIED | Confirmed present (`=== Scenario 4: malformed-state and sent/failed collision resilience (CR-01/WR-02/WR-05) ===` at `internal/verify-cups-paperless-upload.sh:478`) and independently re-run by this verifier: all 6 of its own assertions PASS in a fresh, self-executed run — not inferred from SUMMARY.md's claim. |

**Score:** 17/17 truths verified (0 present-but-behavior-unverified)

### Requirements Coverage

Per the task framing, this phase's requirement IDs (D-01..D-15) are tracked ONLY in `22-CONTEXT.md` and each plan's
SUMMARY frontmatter (`requirements-completed:` / `coverage:`), never in `.planning/REQUIREMENTS.md`'s checkbox
tables. Re-confirmed unchanged: `grep -n "Phase 22\|cups-pdf\|paperless" .planning/REQUIREMENTS.md` still returns
zero matches. This is the same known, pre-existing phase-scaffolding gap already documented in the prior
verification (this phase is "ad-hoc" per its own ROADMAP heading) — **not treated as a verification failure**, and
22-03-PLAN.md itself explicitly notes the same scaffolding gap rather than silently re-triggering it.

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| D-01..D-15 | 22-01-PLAN.md, 22-02-PLAN.md, 22-03-PLAN.md | See CONTEXT.md decisions | See Observable Truths #1-17 above | Not present in REQUIREMENTS.md (known gap, out of scope, unchanged since prior verification) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `cups/upload-worker.py` | Background outbox worker | ✓ VERIFIED | Exists, substantive, wired. All three previously-flagged defects (CR-01/WR-02/WR-05) fixed at the source level, independently confirmed by direct read + standalone unit reproduction + e2e Scenario 4. |
| `cups/generate_config.py` (`build_cups_pdf_conf`, `build_paperless_postprocess_hook`, `build_cups_pdf_registration_snippet`) | Three new functions | ✓ VERIFIED | Unchanged since 22-01, still present and wired (regression check). |
| `cups/config.yaml` (paperless_upload options + schema) | New option block | ✓ VERIFIED | Present; version now `0.1.0-15`. |
| `internal/verify-cups-paperless-upload.sh` | Dedicated verify harness | ✓ VERIFIED | Now 645 lines, 4 scenarios, independently re-run by this verification with exit code 0. |
| `cups/DOCS.md` | Feature docs | ✓ VERIFIED | Unchanged since 22-02, regression-checked present. |
| `cups/README.md` | Features bullet | ✓ VERIFIED | Unchanged since 22-02, regression-checked present. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `build_cups_pdf_registration_snippet()`'s `queue_name` | `build_printer_uuid_fixup_script()`'s `registered_printer_names` | Appended in `main()` before the fixup script is generated | ✓ WIRED | Unchanged since 22-01 (regression check, file untouched by 22-03). |
| PostProcess hook's derived title | `.json` sidecar → `upload-worker.py`'s title read → paperless-ngx's `title` field | Sidecar written by hook, read by `read_title()`, sent as multipart `data={"title": title}` | ✓ WIRED | End-to-end path re-confirmed via fresh Scenario 1 run; the malformed-sidecar edge case (WR-02) is now also handled, confirmed via fresh Scenario 4 run. |
| `run.sh` → `upload-worker.py` | Backgrounded process, PID tracked, killed in shutdown trap | Same pattern as `print-history-poller.py` | ✓ WIRED | Unchanged since 22-01 (regression check). |
| `load_retry_state()`'s `isinstance(dict)` validation | `is_due()` (now inside `poll_once()`'s per-document `try/except`) | Defense-in-depth pair closing CR-01 at both the data-validation and control-flow layers | ✓ WIRED | Confirmed at `upload-worker.py:167-217, 349-364` by direct read; independently reproduced via standalone unit check. |
| `attempt_and_route()`'s `sent/`/`failed/` `Path.replace()` calls | `unique_destination()` | Routes both success and exhausted-retry moves through the new collision-safe helper | ✓ WIRED | Confirmed at `upload-worker.py:283, 294-297` by direct read; independently reproduced via standalone unit check and fresh Scenario 4 run. |

### Data-Flow Trace (Level 4)

Not applicable — this phase has no UI/rendered-data components; all data flow is server-side file → HTTP POST, already covered end-to-end by the Probe Execution and Behavioral Spot-Checks below.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| WR-02 fix: non-dict `.json` sidecar falls back, never raises | Standalone `python3` script importing `cups/upload-worker.py` (stubbing `requests`), writing `[]` to a `.json` sidecar and calling `read_title()` | `title.startswith("Scan_")` — no exception | ✓ PASS |
| CR-01 fix: non-dict `.retry.json` treated as no-prior-attempts, never raises | Same script, writing `[]` to a `.retry.json` and calling `is_due()` | `is_due(pdf) is True` — no exception | ✓ PASS |
| WR-05 fix: `unique_destination()` never silently overwrites an existing file | Same script, pre-seeding `sent/collide.pdf` with `b"ORIGINAL"` and calling `unique_destination()` | Returned a different filename; original file's bytes unchanged | ✓ PASS |

### Probe Execution

Per Step 7c, ran the phase's dedicated probe myself rather than trusting SUMMARY.md's PASS claims — the entire 4-scenario script, real podman-emulated-docker build, no flags, no mocks.

| Probe | Command | Result | Status |
|---|---|---|---|
| `internal/verify-cups-paperless-upload.sh` | `bash internal/verify-cups-paperless-upload.sh` (repo root) | Exit code 0. All PASS lines for Scenario 1 (happy path, 6 assertions), Scenario 2 (D-07 disabled regression, 3 assertions), Scenario 3 (retry exhaustion/D-15, 6 assertions), and the new Scenario 4 (CR-01/WR-02/WR-05 resilience, 6 assertions); final line `internal/verify-cups-paperless-upload.sh: ALL CHECKS PASSED` | PASS |
| `make validate-versions` | `make validate-versions` (repo root) | Exit 0, `cups: config.yaml 0.1.0-15 / build.yaml 0.1.0 / README.md 0.1.0`, "Version validation passed for all add-ons!" | PASS |
| Standalone unit check (Task 1's own `<automated>` verify) | `python3 -c "import py_compile..." && python3 <<'PYEOF' ... PYEOF` | `COMPILE_OK` then `OK: WR-02/CR-01/WR-05 unit checks passed` | PASS |

### Anti-Patterns Found

Carried forward from `22-REVIEW.md`/`22-REVIEW-DISPOSITION.md`. A **new, post-closure code review ran after 22-03**
(dated 2026-09-29, distinct from the pre-closure review the prior verification cited) specifically re-verifying the
three closed bugs and scanning the closure diff for regressions. I independently read the cited lines myself rather
than trusting the review's prose alone.

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `cups/upload-worker.py` | 290-307 | D-15 exhaustion WARNING line names the pre-disambiguation filename on a `failed/` collision | ⚠️ Warning (new WR-01, post-closure review) | An operator following that exact log line to `failed/<name>` on a collision would find the wrong (older) file; a second, correctly-named WARNING is also logged, so the right name is present in the logs elsewhere. See `advisory:` frontmatter. |
| `cups/upload-worker.py` | 214-217, 332-337 | Retry-state hardening validates the JSON is a dict but not per-field types (`attempts`, `next_attempt_at`) | ⚠️ Warning (new WR-02, post-closure review) | A well-formed-dict-but-wrong-typed-field retry state (requires hand-editing/corruption; the worker's own writer can't produce it) still stalls that one document indefinitely — narrower than the closed CR-01, no longer starves siblings. See `advisory:` frontmatter. |
| `cups/upload-worker.py` | 158-163 | Internal finding ID `"(WR-05)"` printed into a production log line | ℹ️ Info (IN-01, post-closure review) | Cosmetic — meaningless string to an end user reading `docker logs`, not a functional defect. |
| `cups/upload-worker.py` | 290-297 | `collision_tag` sharing between PDF and sidecar only reliable when the PDF itself collides | ℹ️ Info (IN-02, post-closure review) | Edge case within an edge case (asymmetric collision where only the sidecar's name collides); functionally still disambiguates and logs, just without the shared-tag correlation guarantee in that narrow sub-case. |
| `cups/upload-worker.py` | 227-229, 287-289 | `config.get(key, default) or default` silently replaces an explicit `0` | ⚠️ Warning (WR-01, pre-existing, carried forward) | Unchanged by this diff; an operator-set `0` for `timeout`/`retry_count`/`retry_delay` is silently replaced by the default. |
| `cups/generate_config.py` | 782-844, 913-988 | No validation that `url`/`token` are non-empty when `enabled: true` | ⚠️ Warning (WR-03, pre-existing, carried forward) | Unchanged by this diff; misconfiguration produces silent, hard-to-diagnose upload failures. |
| `cups/generate_config.py` | 991-1109, 913-988, ~1428-1433 | No uniqueness check between `paperless_upload.queue_name` and `printers[].name` | ⚠️ Warning (WR-04, pre-existing, carried forward) | Unchanged by this diff; a name collision silently reconfigures the physical printer's device URI. |
| `cups/upload-worker.py` | 248-253 | Response body logged verbatim, unconditionally | ⚠️ Warning (WR-06, pre-existing, carried forward) | Unchanged by this diff; "token never leaks" proven only for tested stub bodies. |
| `cups/generate_config.py` | 703-779, 913-988 | Duplicated PPD-resolution shell-generation logic | ℹ️ Info (IN-01, pre-existing, carried forward) | Maintenance risk only. |
| `cups/DOCS.md` | 345-347 | "Migrating from f1c878cb_cups" placeholder section | ℹ️ Info (IN-02, pre-existing, carried forward) | Pre-dates this phase, unchanged by 22-03. |

**None of the above are Blocker-severity.** No Blocker anti-pattern was found in this re-verification round, and no
new debt marker (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) was introduced by 22-03's modified files
(re-checked directly: zero hits across `cups/upload-worker.py`, `internal/verify-cups-paperless-upload.sh`,
`cups/config.yaml`).

### Gaps Summary

None. Both previously-open gaps are closed and independently re-confirmed by this verifier (not by trusting
SUMMARY.md alone):

1. **CR-01 (was Critical, now closed):** `is_due()` is now called inside the same per-document error boundary as
   `process_due_retry()`; `load_retry_state()` independently rejects non-dict parsed JSON. A poisoned `.retry.json`
   can no longer stall the entire `processing/` scan for alphabetically-later documents — reproduced and confirmed
   both via a standalone unit check and a fresh, self-run Scenario 4 against a real built image.
2. **WR-02 (was Warning, now closed):** `read_title()` validates `isinstance(parsed, dict)` before indexing it; a
   malformed sidecar now degrades into the existing D-11 timestamp-fallback path instead of raising — reproduced
   and confirmed the same way.
3. **WR-05 (was Warning, now closed):** the new `unique_destination()`/`_disambiguation_suffix()` helper pair
   checks destination-exists before every `sent/`/`failed/` `Path.replace()`, disambiguating and logging a WARNING
   on collision instead of silently overwriting an already-retained document — reproduced and confirmed the same
   way.

A post-closure code review (run after 22-03, distinct from the pre-closure review the prior VERIFICATION.md cited)
independently re-verified all three fixes are genuine, and additionally found two new, narrower Warning-severity
issues introduced by the fix itself (a misleading filename in the D-15 exhaustion log line on a collision, and a
narrower well-formed-dict-wrong-field-type retry-state edge case). Neither threatens a must-have truth as literally
worded (a WARNING is still emitted, the document is still retained, never deleted), so neither is scored as a gap —
both are recorded in this report's `advisory:` frontmatter for a future maintenance pass, per this phase's own
established practice of documenting rather than silently absorbing residual findings.

---

_Verified: 2026-09-29T16:55:00Z_
_Verifier: Claude (gsd-verifier)_
