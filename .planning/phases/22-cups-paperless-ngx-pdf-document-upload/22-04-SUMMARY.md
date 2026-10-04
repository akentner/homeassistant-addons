---
phase: 22-cups-paperless-ngx-pdf-document-upload
plan: 04
subsystem: infra
tags: [cups, paperless-ngx, redirects, gap-closure, verification, ha-addon]
status: complete

requires:
  - phase: 22-03
    provides: upload-worker.py retry/failed routing, Scenarios 1-4 of internal/verify-cups-paperless-upload.sh
provides:
  - upload_document() refuses every HTTP 3xx (allow_redirects=False) and logs a sanitized Location
  - Success defined as HTTP 200 plus a non-empty JSON-string task id (CR-01 / 22-VERIFICATION.md truth 18 closed)
  - internal/verify-cups-upload-worker.py host-side probe (RED-proven against the pre-fix worker)
  - Scenario 5 (redirect refusal) in the Docker verifier; stub speaks the real paperless-ngx body shape
affects: [cups add-on maintenance, 22-VERIFICATION.md re-verification]

actuals:
  tokens: 9500
  tasks: 3
  commits: 3
  plan_head_before: 9c0750bab1617534acf62f9a9cd3ef42b7b937f7
  plan_head_after: 17d35532bde1071d1858c2bd0f9510a3d955482b

tech-stack:
  added: []
  patterns:
    - "Probe-first verification: a host-side stdlib stub + real requests, with --worker PATH so RED is repeatable against git show <rev>:file"
    - "Log only scheme/host/path of an untrusted Location header (no query, fragment, userinfo), capped at 200 chars"

key-files:
  created:
    - internal/verify-cups-upload-worker.py
  modified:
    - cups/upload-worker.py
    - internal/verify-cups-paperless-upload.sh
    - cups/DOCS.md
    - cups/config.yaml
    - .planning/phases/22-cups-paperless-ngx-pdf-document-upload/22-REVIEW-DISPOSITION.md

key-decisions:
  - "attempt_and_route() deliberately untouched: the success boolean is fixed at its single source, upload_document(), so D-09 retry and D-15 single-WARNING behavior is reused unchanged"
  - "No UUID pattern enforced on the task id (Celery implementation detail); a non-empty JSON string is enough to reject login HTML, objects and empty bodies"
  - "Version bumped with NO_TAG=yes NO_PUSH=yes: a cups/v... tag triggers an image build, which is the operator's release decision"

requirements-completed: [D-01, D-09, D-15]

duration: ~25min
completed: 2026-10-04
---

# Phase 22 Plan 04: Redirect Refusal (CR-01 gap closure) Summary

**upload_document() now refuses all HTTP 3xx answers and counts only HTTP 200 with a task-id JSON string as success, so a redirect to a login page can no longer file a document under sent/; proven by a host-side probe that fails against the pre-fix worker and by a new real-image Scenario 5.**

## Accomplishments

- `cups/upload-worker.py`: `requests.post(..., allow_redirects=False)`; new 3xx branch logs one WARNING with the HTTP status, a sanitized redirect target (`_safe_redirect_target()`: scheme, host/port, path only, 200-char cap, `(no Location header)` marker) and "redirects are not followed; set paperless_upload.url to the final address"; new `_is_task_id_body()` plus a 200-with-bad-body WARNING ("returned HTTP 200 but the response body is not a task id"); every non-200 2xx falls into the existing generic non-success WARNING. Docstrings updated. `attempt_and_route()`, `poll_once()` and `process_*` are untouched.
- `internal/verify-cups-upload-worker.py` (new, executable, manual tool, not in pre-commit): redirect matrix 301/302/303/307/308 (exactly one request, the POST; WARNING names status, "redirect", `/login/`; token absent), retry-to-`failed/` routing with exactly one `upload exhausted` line, response-body matrix (valid id, object, HTML, empty, empty/blank JSON string, 202, 204) and sent/failed routing for a valid and a rejected body.
- `internal/verify-cups-paperless-upload.sh`: stub success body is now the bare JSON string `"stub-task-uuid-0001"`, stub gained `redirect` mode and GET recording (and a `"method"` key on POST records); Scenario 5 added (failed/ holds the PDF, sent/ empty, zero GET, at least two POST, exactly one exhausted WARNING, redirect-refusal WARNING naming `/login/`, no `INFO: uploaded` line, token absent).
- `cups/DOCS.md`: `sent/` means HTTP 200 with the consumption-task id; Known limitations gained "Redirects are not followed" and "`sent/` means accepted, not processed".
- `cups/config.yaml` 0.1.0-16 -> 0.1.0-17 via `make update-version ... NO_TAG=yes NO_PUSH=yes`. 22-REVIEW-DISPOSITION.md: CR-01 set to `fixed`.

## Task Commits

1. Task 1 (tracer): `3ffbf09` fix(22-04): refuse paperless-ngx redirects and prove it with a host-side probe
2. Task 2: `8a98342` fix(22-04): require HTTP 200 with a task-id JSON string for a successful upload
3. Task 3: `17d3553` fix(22-04): add redirect-refusal Scenario 5, document HTTP 200 success, bump cups to 0.1.0-17

## RED / GREEN evidence

- Task 1 RED: probe against the unmodified worker exited 1 with 18 FAIL lines (every 3xx followed: POST then GET /login/ for 301/302/303, POST then POST /login/ for 307/308; 302 routing put the PDF in sent/). After the fix: `ALL CHECKS PASSED`; against `git show 4467249:cups/upload-worker.py` the probe still exits 1.
- Task 2 RED: with body-matrix checks added, the Task 1 worker failed 15 checks (JSON object, HTML, empty body, empty and blank JSON string, 202, 204, rejected-body routing). After the fix: `ALL CHECKS PASSED`; pre-fix worker still exits 1.
- Task 3: `bash internal/verify-cups-paperless-upload.sh` against a freshly built image: 5 scenarios, 0 FAIL lines, `ALL CHECKS PASSED`.
- `shellcheck -e SC1091 -e SC2034` on the verifier, `make validate-versions`, `python3 internal/validate-addon-config.py cups` and `pre-commit run --files` on all touched files: all pass.

## Deviations from Plan

None - plan executed as written. Notes: prettier re-wrapped one DOCS.md bullet on the first commit attempt (the commit was aborted by the hook, the reflowed file was staged, and the identical commit was made); the Task 3 commit therefore carries the prettier-wrapped text.

## Known Stubs

None.

## Threat Flags

None. The threat register (T-22-09 .. T-22-12) mitigations are implemented as planned; no new network surface was introduced.

## Operator follow-ups

- No tag was created and nothing was pushed. To release 0.1.0-17 and trigger the image build, the operator runs the repo's tagging step, e.g. `git tag cups/v0.1.0-17 && git push origin cups/v0.1.0-17` (or re-run `make update-version ADDON=cups VERSION=0.1.0-17` without `NO_TAG`/`NO_PUSH`).
- Re-run the phase verifier (`/gsd-verify-work` or the verifier agent): truth 18 should now score verified (18/18). The advisory findings WR-01..WR-08 and IN-01..IN-06 remain `open` by design.

## Self-Check: PASSED

- FOUND: cups/upload-worker.py, internal/verify-cups-upload-worker.py, internal/verify-cups-paperless-upload.sh, cups/DOCS.md, cups/config.yaml
- FOUND commits: 3ffbf09, 8a98342, 17d3553
