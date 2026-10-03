---
phase: 22-cups-paperless-ngx-pdf-document-upload
verified: 2026-10-03T11:07:00Z
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
covered_digest: "v2:sha256:fbef125c736db7fcda10f643dd21f4bc43205f9eacf1945b5b246016c776425a"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 17/17
  gaps_closed: []
  gaps_remaining: []
  regressions: []
advisory:
  - finding: "D-15's 'upload exhausted' WARNING line still names the pre-disambiguation filename when a failed/ collision occurs (`see failed/<name>` while the file landed at `failed/<name>-<tag>.pdf`). A second, correctly-named WARNING from unique_destination() is also emitted."
    category: other
    reason: "Carried forward from the post-22-03 code review (22-REVIEW.md WR-01). Narrow precondition (retry exhaustion AND a same-named failed/ collision). Does not violate the literal D-15 truth (one WARNING emitted, document never deleted)."
    evidence_status: "confirmed via direct code read this run (upload-worker.py:290-307); no automated regression test"
  - finding: "load_retry_state() rejects non-dict JSON but not a dict with wrong-typed `attempts` / `next_attempt_at`; is_due() catches only KeyError/ValueError, process_due_retry() uses int(...)."
    category: other
    reason: "Carried forward from 22-REVIEW.md WR-02 (new id). Requires hand-edited/corrupted state; the worker's own writer cannot produce it. Failure is isolated to that one document by the per-document try/except (no sibling starvation)."
    evidence_status: "confirmed via direct code read this run (upload-worker.py:207-217, 332-337); no automated regression test"
human_verification: []
---

# Phase 22: cups-paperless-ngx-pdf-document-upload Verification Report

**Phase Goal:** Add a second, PDF-only virtual printer queue to the `cups` add-on (via `cups-pdf`), separate from and
non-disruptive to the existing physical Brother-MFC-7460DN queue, whose output is picked up by a decoupled background
worker and uploaded to a paperless-ngx instance's REST API. The worker must be resilient to paperless-ngx being
unreachable: retry/backoff, never crash, never block cupsd or the physical printer.

**Verified:** 2026-10-03T11:07:00Z
**Status:** passed
**Re-verification:** Yes. The previous report (2026-09-29, passed 17/17) was stale because two covered files changed
afterwards: `cups/DOCS.md` (commit e1483b2, Phase 21 filled the "Migrating from f1c878cb_cups" section) and
`COVERAGE.md` (commit 3b30600, reshaped to a 3-column matrix). This run re-checks that neither change contradicts a
Phase 22 truth, re-runs the Docker-backed probe, and regenerates `covered_files` / `covered_digest` with
`gsd_run query verification.fingerprint`.

## What changed since the last verification (evidence)

| File | Last commit | Changed since previous verification? | Check |
|---|---|---|---|
| `cups/upload-worker.py` | 82a93a5 (2026-09-29 18:23) | No | `git log -1` predates the previous verification |
| `cups/generate_config.py`, `cups/run.sh`, `cups/Dockerfile`, `cups/translations/*.yaml` | 56ca013 (22-01) | No | `git log -1` |
| `cups/config.yaml`, `internal/verify-cups-paperless-upload.sh` | 79423a4 (22-03) | No | `git log -1` |
| `cups/README.md` | 690e1df (22-02) | No | `git log -1` |
| `cups/DOCS.md` | e1483b2 (2026-10-02) | **Yes** | Diff read: only the final "Migrating from f1c878cb_cups" section changed (placeholder replaced by a 5-step migration runbook). Sections `## Paperless-ngx PDF Upload` (line 111) and the paperless paragraph in `## Design notes` (lines 319-343, including the `PostProcessing` correction) are intact. The runbook only discusses `printers[]`, mDNS/Avahi and `brlaser`. It never mentions cups-pdf, `paperless_upload` or the worker, so nothing in it contradicts a Phase 22 truth. |
| `COVERAGE.md` | 3b30600 (2026-10-02) | **Yes** | Diff read: the former 4-column table (Capability / surface / Decision / Reason) was folded into 3 columns (surface text moved into the Capability cell). All 13 rows keep identical INTEGRATE / OPT-OUT decisions and reasons: 3 INTEGRATE (upload, title, token auth), 10 OPT-OUT. No decision in D-01..D-15 is affected. |
| `git status` | n/a | n/a | Working tree has no uncommitted changes under `cups/` or `internal/` (only untracked `.bg-shell/`, `.mcp.json`) |

## Goal Achievement

### Observable Truths

Docker was available (`/usr/bin/docker` is a podman emulation, same as the previous run), so the full probe was re-run
rather than relying on earlier evidence.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | With `paperless_upload.enabled` false (shipped default), the add-on behaves as before: no cups-pdf queue, no cups-pdf.conf directives, no outbox dirs, no worker activity (D-07) | ✓ VERIFIED | `config.yaml` ships `enabled: false`. Fresh probe Scenario 2: 3/3 PASS (queue not registered, `/data/paperless_upload` not created, no active `paperless_upload` directives in cups-pdf.conf). `upload-worker.py` `main()` returns after one INFO line when `load_paperless_config()` is None. |
| 2 | When enabled, printing to the queue yields a PDF uploaded via `POST /api/documents/post_document/` with multipart `document` + `title` and `Authorization: Token <token>` (D-01/D-10) | ✓ VERIFIED | Fresh probe Scenario 1: queue registered, device URI `cups-pdf:/`, PDF in `sent/`, stub received POST, Token header present, non-empty `title`, correct endpoint path (all PASS). Matches `upload-worker.py:234-240`. |
| 3 | If the original title cannot be recovered, upload proceeds with a timestamp fallback title (D-11), including for a non-dict JSON sidecar | ✓ VERIFIED | `read_title()` (`upload-worker.py:94-125`) guards with `isinstance(parsed, dict)`. Re-ran my own standalone unit check this run: sidecar `[]` gives `Scan_...`, `{"title":"  Hello  "}` gives `Hello`, a 500-char title is capped to 128 (D-14). Scenario 4 `badtitle-doc.pdf` converges to `sent/`. |
| 4 | A PostProcessing hook failure never blocks or fails the print job; cupsd and the physical queue are unaffected (D-13) | ✓ VERIFIED | `generate_config.py` unchanged since 22-01. The worker is a separate backgrounded process (`run.sh:179-192`, killed in the shutdown trap). Scenario 1 shows a real cups-pdf job printed end-to-end. The best-effort hook code was not re-read in depth this run; this truth rests on the unchanged 22-01 artifact plus the earlier evidence. |
| 5 | After retry/backoff exhaustion the document moves to `failed/` (never deleted) and exactly one WARNING is emitted (D-15) | ✓ VERIFIED | Fresh probe Scenario 3: 6/6 PASS (lands in `failed/`, PDF and sidecar retained, `processing/` clean, exactly one "upload exhausted" line, token not logged). Code at `upload-worker.py:290-307`; `is_due()` is inside the per-document try/except (`:359-364`). Known narrow advisory only (see frontmatter). |
| 6 | The cups-pdf queue's printer UUID is stable across restarts via the same fixup as physical printers (D-08) | ✓ VERIFIED (structural) | `generate_config.py:1428-1440` appends `cups_pdf_queue_name` to `registered_printer_names` before `build_printer_uuid_fixup_script(...)`. File unchanged since 22-01. No live container restart test was run this verification; it rests on structural wiring plus the empirical restart note in 22-01-SUMMARY.md from the earlier run. |
| 7 | `paperless_upload.token` is never printed in plaintext to add-on logs | ✓ VERIFIED | All 4 fresh probe scenarios assert their fixture token is absent from `docker logs` (PASS). Caveat (existing advisory WR-06): the response body is logged verbatim (truncated to 200 chars), so this is proven only for the tested stub responses. |
| 8 | `cups/DOCS.md` documents every `paperless_upload` option with default and purpose | ✓ VERIFIED | `## Paperless-ngx PDF Upload` (line 111) has the table covering all 8 fields (`enabled`, `queue_name`, `location`, `url`, `token`, `timeout`, `retry_count`, `retry_delay`), plus outbox lifecycle and known limitations. Intact after the e1483b2 edit. |
| 9 | `cups/DOCS.md` Design notes record the corrected `PostProcessing` title-derivation mechanism | ✓ VERIFIED | Lines 319-343: paragraph on the `PostProcessing` (not `PostProcess`) directive, positional args, and the `Label 2` suffix stripping. Intact. |
| 10 | `cups/README.md` Features mentions paperless-ngx upload | ✓ VERIFIED | `grep -c paperless-ngx cups/README.md` returns 1; file unchanged since 690e1df. |
| 11 | Re-running `internal/verify-cups-paperless-upload.sh` still passes | ✓ VERIFIED | Re-run this verification: exit 0, "ALL CHECKS PASSED" (see Probe Execution). |
| 12 | `cups/config.yaml` version bumped and 3-file consistency holds | ✓ VERIFIED | `make validate-versions` exits OK; cups is `0.1.0-15` in `config.yaml`, `0.1.0` in `build.yaml` and `README.md`. |
| 13 | Non-dict `.json` title sidecar degrades to the timestamp title (WR-02 closed) | ✓ VERIFIED | Unit check plus Scenario 4 assertion 2 (this run). |
| 14 | Non-dict/malformed `.retry.json` no longer aborts the `processing/` scan (CR-01 closed) | ✓ VERIFIED | Unit check: `is_due()` returns True for both `[]` and `{bad`. Scenario 4 assertion 1: `zzz-normal.pdf` converges despite `poison-aaa` sorting first. |
| 15 | A same-name collision into `sent/`/`failed/` never overwrites the retained file (WR-05 closed) | ✓ VERIFIED | Unit check: `unique_destination()` returns a suffixed name, logs WARNING, original bytes unchanged. Scenario 4 assertions 3-5 PASS. |
| 16 | Scenarios 1-3 still pass unchanged after the 22-03 fixes | ✓ VERIFIED | Fresh run: 8 + 3 + 6 PASS lines. |
| 17 | Scenario 4 proves the three fixes end-to-end against a real built image | ✓ VERIFIED | Fresh run: 6/6 PASS. |

**Score:** 17/17 truths verified (0 present-but-behavior-unverified)

No ROADMAP success-criteria array or REQUIREMENTS.md IDs exist for this ad-hoc phase. The 15 locked decisions
(D-01..D-15) in `22-CONTEXT.md` were the contract. No `must_haves.prohibitions` are declared in any PLAN.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `cups/upload-worker.py` | Background outbox worker | ✓ VERIFIED | 388 lines, substantive, wired from `run.sh` and the Dockerfile `COPY`; py_compile OK |
| `cups/generate_config.py` (`build_cups_pdf_conf`, `build_paperless_postprocess_hook`, `build_cups_pdf_registration_snippet`) | Queue, hook and registration generators | ✓ VERIFIED | Present (lines 782, 847, 913), called from `main()` (1430, 1462, 1475) |
| `cups/config.yaml` | `paperless_upload` options and schema | ✓ VERIFIED | `enabled: false` default, `token: "password?"`, 8 fields |
| `cups/Dockerfile` | `cups-pdf` + `py3-requests` installed, worker copied | ✓ VERIFIED | lines 44-45, 71-73 |
| `internal/verify-cups-paperless-upload.sh` | Docker-backed verify harness | ✓ VERIFIED | 4 scenarios; shellcheck clean with the repo's ignores |
| `cups/DOCS.md`, `cups/README.md` | Feature docs | ✓ VERIFIED | See truths 8-10 |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `cups_pdf_queue_name` | `build_printer_uuid_fixup_script()` | appended in `main()` before the fixup call | ✓ WIRED |
| PostProcessing hook | `.json` sidecar | `read_title()` | ✓ WIRED (Scenario 1 title non-empty; malformed case Scenario 4) |
| `run.sh` | `upload-worker.py` | `python3 /upload-worker.py &`, PID in the shutdown trap | ✓ WIRED |
| `is_due()` / `load_retry_state()` | per-document try/except in `poll_once()` | `upload-worker.py:359-364` | ✓ WIRED |
| `attempt_and_route()` moves | `unique_destination()` | `:283`, `:295`, `:297` | ✓ WIRED |

### Data-Flow Trace (Level 4)

Not applicable: no rendered UI. The file to HTTP POST flow is exercised end-to-end by Scenario 1.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `read_title()` non-dict sidecar, trim, 128 cap | standalone Python importing `cups/upload-worker.py` with `requests` stubbed | `UNIT OK` | ✓ PASS |
| `is_due()` on `[]` and `{bad` retry state | same script | returns True, no exception | ✓ PASS |
| `unique_destination()` no overwrite | same script | suffixed name, original intact | ✓ PASS |
| Python compile | `python3 -m py_compile cups/upload-worker.py cups/generate_config.py` | OK | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| `internal/verify-cups-paperless-upload.sh` | `bash internal/verify-cups-paperless-upload.sh` (repo root, Docker emulated by podman, no flags) | exit 0 in ~110 s. Scenario 1: 8 PASS. Scenario 2: 3 PASS. Scenario 3: 6 PASS. Scenario 4: 6 PASS. Final line "ALL CHECKS PASSED" | PASS |
| `make validate-versions` | repo root | exit 0, "Version validation passed for all add-ons!" | PASS |
| `shellcheck -e SC1091 -e SC2034 internal/verify-cups-paperless-upload.sh cups/run.sh` | repo root | clean | PASS |

### Requirements Coverage

D-01..D-15 are tracked only in `22-CONTEXT.md` and the plan/summary frontmatter, never in `.planning/REQUIREMENTS.md`
(ad-hoc phase, known and unchanged). Not a verification failure.

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| D-01..D-15 | 22-01, 22-02, 22-03 | ✓ SATISFIED | Truths 1-17 above. D-02 (Avahi advertisement) and D-08 (UUID fixup) rest on structural wiring, not a live re-test this run. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `cups/upload-worker.py` | 290-307 | D-15 WARNING names pre-disambiguation filename on `failed/` collision | ⚠️ Warning (advisory, WR-01) | See frontmatter |
| `cups/upload-worker.py` | 207-217, 332-337 | Retry-state per-field type not validated | ⚠️ Warning (advisory, WR-02) | See frontmatter |
| `cups/upload-worker.py` | 227-229, 287-289 | `config.get(k, d) or d` replaces explicit `0` | ⚠️ Warning (pre-existing) | Operator-set 0 silently defaulted |
| `cups/generate_config.py` | 782-988 | No non-empty check on `url`/`token` when enabled | ⚠️ Warning (pre-existing WR-03) | Silent upload failures on misconfiguration |
| `cups/generate_config.py` | 913-1109, 1428-1433 | No uniqueness check between `queue_name` and `printers[].name` | ⚠️ Warning (pre-existing WR-04) | Collision would reconfigure the physical printer |
| `cups/upload-worker.py` | 248-260 | Response body logged verbatim (truncated) | ⚠️ Warning (pre-existing WR-06) | Token-leak proof is stub-specific |
| `cups/upload-worker.py` | 158-163, 290-297 | Internal ID "(WR-05)" in a log line; collision-tag sharing edge case | ℹ️ Info | Cosmetic / edge |
| `cups/generate_config.py` | 129 | `tailXXXX.ts.net` in an example hostname comment | ℹ️ Info | Not a debt marker (illustrative hostname); file unchanged since 22-01 |

No Blocker found. No `TBD/FIXME/TODO/HACK/PLACEHOLDER` marker in covered implementation files. The earlier DOCS.md
migration-placeholder info item is now resolved by e1483b2.

The 22-REVIEW-DISPOSITION.md bookkeeping still lists all 10 findings as `open`, including CR-01/WR-02/WR-05 that 22-03
closed. It was recorded before the closure and is stale, but it is process metadata, not a goal gap.

### Human Verification Required

None. Real-device AirPrint/iOS behavior and a real paperless-ngx instance were never in this phase's automated
scope; the probe uses a stub paperless server.

### Gaps Summary

None. The two post-closure advisories (WR-01 log-line filename on failed/ collision, WR-02 wrong-typed retry-state
fields) are narrow, non-blocking, and recorded in the `advisory:` frontmatter for a later maintenance pass. Phase goal
achieved: a separate cups-pdf queue, a decoupled worker, a Token-authenticated multipart upload, retry/backoff to
`failed/`, and a default-off path that leaves existing installs untouched.

---

_Verified: 2026-10-03T11:07:00Z_
_Verifier: Claude (gsd-verifier)_
