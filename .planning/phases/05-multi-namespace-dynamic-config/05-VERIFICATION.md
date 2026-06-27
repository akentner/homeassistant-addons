---
phase: 05-multi-namespace-dynamic-config
verified: 2026-06-27T19:05:00Z
status: passed
score: 7/7 must-haves verified
---

# Phase 5: Multi-Namespace Dynamic Config Verification Report

**Phase Goal:** Close out Phase 5 by empirically verifying the multi-namespace behavior already structurally implemented
in Phase 4 (MULTI-01..06) and documenting it in user-facing docs.

**Verified:** 2026-06-27T19:05:00Z **Status:** PASSED

## Verification Method

This is an **initial verification** (no previous VERIFICATION.md existed). Must-haves were loaded from PLAN frontmatter
(7 truths, 2 artifacts, 3 key links). Each item was verified at the artifact (existence + substantive + wired),
data-flow, key-link, anti-pattern, and behavioral-spot-check levels.

The empirical end-to-end verifier (`verify-multi-namespace.sh`) was executed against a freshly-built
`local/markdown-renderer:1.0.0` image inside podman; all 35 assertions passed.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                         | Status     | Evidence                                                                                                                                           |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | A running markdown-renderer container with 2+ namespace fixtures serves each namespace as an isolated Docsify SPA at `/<name>/`               | ✓ VERIFIED | SCENARIO A passes — `/docs/`, `/runbooks/`, `/photos/` each return unique `Loading <name>...` HTML bodies                                          |
| 2   | Landing page at `/` lists all configured namespaces as clickable cards and regenerates after a restart with different config                  | ✓ VERIFIED | SCENARIO A passes (3 cards hrefs+h2), SCENARIO B passes (restart → only `/only/` card, no stale `/docs/` card)                                     |
| 3   | An invalid namespace name causes the container to exit non-zero with a clear stderr message naming the bad name                               | ✓ VERIFIED | SCENARIO C (4 invalid fixtures: slash, empty, reserved_docsify, uppercase) — each exits with `ERROR: namespace name`, no Traceback                 |
| 4   | Volume mounts `/share`, `/config`, `/media` are readable from inside the container; namespace files from each mount are served without errors | ✓ VERIFIED | SCENARIO A MULTI-06 assertions — `index.html` with `basePath = window.location.pathname` served from each of 3 ns                                  |
| 5   | Edge cases (duplicate names, empty list, missing options.json) all handled gracefully without uncaught tracebacks                             | ✓ VERIFIED | SCENARIO D (duplicate → exit + clear error), SCENARIO E (empty list → running + 503, no options.json → running + 503)                              |
| 6   | DOCS.md documents landing page regeneration + reserved-name rules + multi-source `/share+/config+/media` example                              | ✓ VERIFIED | DOCS.md lines 32-86: `## Multi-Namespace Behavior`, `### Namespace Name Rules`, `### Reading from /share, /config, /media`, `## Validation Status` |
| 7   | `make check-all` exits 0 after Phase 5 docs changes; no regression in pre-commit pipeline                                                     | ✓ VERIFIED | `make check-all` exited 0 (validate-versions, yamllint, shellcheck, validate-dockerfile-args all pass)                                             |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact                                                                       | Expected                                                            | Status     | Details                                                                                                         |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------- |
| `.planning/phases/05-multi-namespace-dynamic-config/verify-multi-namespace.sh` | Empirical end-to-end verifier covering all 6 MULTI requirements     | ✓ VERIFIED | 466 lines, executable (-rwxr-xr-x), `set -euo pipefail`, EXIT trap, MULTI-01..06 referenced, runs to completion |
| `markdown-renderer/DOCS.md`                                                    | Multi-namespace behavior + reserved names + landing-page regen note | ✓ VERIFIED | 105 lines (49→105, +56). All required sections present (verified by grep below)                                 |

### DOCS.md content checks

```
✓ ## Multi-Namespace Behavior (line 32)
✓ ### Namespace Name Rules (line 41) — regex ^[a-z0-9][a-z0-9-]{0,62}$
✓ Reserved names listed: _docsify, api, data, share, config, media (line 47)
✓ Empty-list 503: "no directories configured" (line 54)
✓ Duplicate-name error: "duplicate directory name 'docs'" (line 51)
✓ ### Reading from /share, /config, /media (line 56)
✓ ## Validation Status (line 75) — references verifier script
```

### Key Link Verification

| From                                                     | To                                                | Via                                                                                                  | Status  | Details                                                                                                          |
| -------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------- |
| podman container (local/markdown-renderer:1.0.0)         | http://localhost:8099 endpoints                   | OPTIONS_PATH at /data/options.json + fixtures at /share/docs /config/runbooks /media/photos          | ✓ WIRED | All SCENARIO A curl probes (`127.0.0.1:8099/<ns>/`) returned 200 with isolated Docsify SPA HTML                  |
| markdown-renderer/generate_nginx.py validate_directories | container stderr on bad input                     | `$RUNTIME logs mr-verify` shows `ERROR: namespace name` for all 4 invalid fixtures                   | ✓ WIRED | SCENARIO C: every fixture produced "ERROR: namespace name '...'" line, no Traceback                              |
| markdown-renderer/run.sh                                 | /tmp/nginx.conf regeneration on container restart | `python3 /app/generate_nginx.py` runs on every container start, then `exec nginx -c /tmp/nginx.conf` | ✓ WIRED | `exec nginx -c /tmp/nginx.conf -g 'daemon off;'` (run.sh line 10); SCENARIO A+B confirm per-restart regeneration |

### Data-Flow Trace (Level 4)

| Artifact                   | Data Variable   | Source                                                                   | Produces Real Data                                                      | Status    |
| -------------------------- | --------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------- | --------- |
| `markdown-renderer/run.sh` | /tmp/nginx.conf | `python3 /app/generate_nginx.py` (writes nginx.conf + per-ns index.html) | Yes — generator output rendered into running container, served via curl | ✓ FLOWING |
| Landing page `/`           | cards list      | `generate_nginx.py::render_landing_html(namespaces)`                     | Yes — 3 fixture cards (docs/runbooks/photos) appear in served HTML      | ✓ FLOWING |
| Per-namespace `/<name>/`   | index.html body | `generate_nginx.py::_render_namespace_index(ns, kroki_url)`              | Yes — each ns has unique `name_display`, `name_json`, basePath          | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior                                                                       | Command                                                                      | Result                                                                                    | Status |
| ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------ |
| Empirical verifier exits 0 with "ALL VERIFICATIONS PASSED" against fresh image | `make build-addon ADDON=markdown-renderer && bash verify-multi-namespace.sh` | Exit 0; "ALL VERIFICATIONS PASSED (35 assertions)"                                        | ✓ PASS |
| `make check-all` exits 0 after Phase 5 docs + code changes                     | `make check-all`                                                             | Exit 0; all 5 add-ons pass version validation; yamllint+shellcheck+dockerfile-args all OK | ✓ PASS |
| `markdown-renderer/run.sh` uses generated config (not default port-80 config)  | `exec nginx -c /tmp/nginx.conf -g 'daemon off;'`                             | Line 10 confirmed; SCENARIO A on port 8099 proves -c flag works                           | ✓ PASS |
| `generate_nginx.py` minimal-fallback creates tmp dirs (no nginx emerg mkdir)   | `_write_minimal_nginx` calls `_ensure_nginx_tmp_dirs()` (lines 420, 502)     | SCENARIO E (empty list + missing options.json) → container stays running with 503         | ✓ PASS |
| All 6 MULTI requirements empirically asserted in verifier                      | `grep -c "MULTI-0[1-6]" verify-multi-namespace.sh`                           | MULTI-01: 4 lines, MULTI-02: 4 lines, MULTI-03: 4, MULTI-04: 4, MULTI-05: 4, MULTI-06: 4  | ✓ PASS |
| No orphan `mr-verify` containers after verifier completes (EXIT trap)          | `podman ps -a --filter name=mr-verify --format '{{.Names}}'`                 | Empty (cleanup trap worked)                                                               | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                          | Status      | Evidence                                                                                                                                              |
| ----------- | ----------- | ---------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| MULTI-01    | 05-01       | Multiple directories as list of objects in HA options, each with name+path                           | ✓ SATISFIED | SCENARIO A: 3-namespace fixture loaded, generator logged "Validated 3 namespace(s): docs, runbooks, photos"                                           |
| MULTI-02    | 05-01       | Each configured directory served as independent Docsify SPA at `/name/`                              | ✓ SATISFIED | SCENARIO A: curl /docs/ /runbooks/ /photos/ each return isolated `Loading <name>...` HTML                                                             |
| MULTI-03    | 05-01       | Landing page at `/` lists all configured namespaces as clickable cards                               | ✓ SATISFIED | SCENARIO A: hrefs + h2 for all 3; SCENARIO B: regenerates to single 'only' card after config change                                                   |
| MULTI-04    | 05-01       | generate_nginx.py reads /data/options.json, generates /tmp/nginx.conf + per-ns index.html on startup | ✓ SATISFIED | SCENARIO A: "Generated nginx config for 3 namespace(s)" log; SCENARIO B: regenerates on config change                                                 |
| MULTI-05    | 05-01       | Namespace name validation rejects empty/non-URI-safe/reserved names with clear error                 | ✓ SATISFIED | SCENARIO C: 4 invalid fixtures (slash/empty/reserved_docsify/uppercase) → exit + ERROR: namespace name, no Traceback; SCENARIO D: duplicates rejected |
| MULTI-06    | 05-01       | /share, /config, /media supported as namespace directory sources                                     | ✓ SATISFIED | SCENARIO A: 3 volume mounts each serve index.html with `basePath = window.location.pathname`                                                          |

All 6 MULTI-\* requirements in PLAN frontmatter accounted for, all satisfied with implementation evidence. No orphaned
requirements.

### README.md Manual HA Ingress Test Checklist — count verification

| #   | Item                                          | Status |
| --- | --------------------------------------------- | ------ |
| 1   | Ingress panel                                 | ✓      |
| 2   | Single namespace renders                      | ✓      |
| 3   | Mermaid diagrams                              | ✓      |
| 4   | No CDN requests                               | ✓      |
| 5   | Auto-update pin                               | ✓      |
| 6   | Kroki diagram render                          | ✓      |
| 7   | Kroki URL override                            | ✓      |
| 8   | **Multi-namespace landing page** (Phase 5)    | ✓      |
| 9   | **Invalid namespace name rejected** (Phase 5) | ✓      |
| 10  | **Volume mounts serve files** (Phase 5)       | ✓      |

**Total: 10 items** (≥10 as required). H1 description also updated with "Multiple namespaces can be configured and are
served as isolated Docsify SPAs under separate URLs." (README line 6-7).

### Anti-Patterns Found

| File   | Line | Pattern | Severity | Impact |
| ------ | ---- | ------- | -------- | ------ |
| (none) | —    | —       | —        | —      |

No TODO/FIXME/placeholder/empty-return/Traceback strings in run.sh or generate_nginx.py. No hardcoded empty data. No
props with hardcoded empty values. Clean.

### Behavioral Spot-Checks Detail (verifier raw output)

```
━━━ SCENARIO A — happy path: 3 namespaces (MULTI-01, MULTI-02, MULTI-03, MULTI-04, MULTI-06) ━━━
  PASS container started and nginx is serving (3-namespace config)
  PASS MULTI-01: generator validated OPTIONS_PATH ('Validated 3 namespace')
  PASS MULTI-02: /docs/ serves isolated Docsify SPA ('Loading docs' in HTML)
  PASS MULTI-02: /runbooks/ serves isolated Docsify SPA ('Loading runbooks' in HTML)
  PASS MULTI-02: /photos/ serves isolated Docsify SPA ('Loading photos' in HTML)
  PASS MULTI-03: landing page lists all 3 namespace cards (hrefs)
  PASS MULTI-03: landing page renders <h2> for each namespace
  PASS MULTI-04: generate_nginx.py ran ('Generated nginx config for 3 namespace')
  PASS MULTI-04: vendored /_docsify/docsify.min.js served (200)
  PASS MULTI-06: /docs/ served index.html with window.location.pathname basePath
  PASS MULTI-06: /runbooks/ served index.html with window.location.pathname basePath
  PASS MULTI-06: /photos/ served index.html with window.location.pathname basePath

━━━ SCENARIO B — landing page regenerates on config change (MULTI-03/04) ━━━
  PASS container restarted with 1-namespace config
  PASS landing page shows only the new 'only' card
  PASS landing page no longer shows stale 'docs' card (regenerated, no cache)

━━━ SCENARIO C — invalid namespace names rejected (MULTI-05) ━━━
  PASS invalid name 'slash': container exited (refused to start)
  PASS invalid name 'slash': clear ERROR message in logs
  PASS invalid name 'slash': no Python traceback (graceful error)
  PASS invalid name 'empty': container exited (refused to start)
  PASS invalid name 'empty': clear ERROR message in logs
  PASS invalid name 'empty': no Python traceback (graceful error)
  PASS invalid name 'reserved_docsify': container exited (refused to start)
  PASS invalid name 'reserved_docsify': clear ERROR message in logs
  PASS invalid name 'reserved_docsify': no Python traceback (graceful error)
  PASS invalid name 'uppercase': container exited (refused to start)
  PASS invalid name 'uppercase': clear ERROR message in logs
  PASS invalid name 'uppercase': no Python traceback (graceful error)

━━━ SCENARIO D — duplicate names rejected (MULTI-05) ━━━
  PASS duplicate names: container exited
  PASS duplicate names: 'duplicate directory name' error in logs
  PASS duplicate names: no Python traceback

━━━ SCENARIO E — empty list + missing options.json (graceful degradation) ━━━
  PASS empty list: container stays running (graceful degradation)
  PASS empty list: GET / returns 503 with 'no directories configured'
  PASS missing options.json: container starts anyway
  PASS missing options.json: vendored assets still served
  PASS missing options.json: GET / returns 503 with helpful message

══════════════════════════════════════════════════════
  ALL VERIFICATIONS PASSED  (35 assertions)
══════════════════════════════════════════════════════
```

### Human Verification Required

None. All items verified programmatically with deterministic output. The empirical verifier exercises the actual
container runtime behavior end-to-end. The remaining user-facing test (the 10-item Manual HA Ingress Test Checklist) is
intended for the end user to run inside a live Home Assistant instance, which is by design out of scope for sandbox
verification.

## Orchestrator-Specified Items (Spot-Check)

| #   | Item                                                                                         | Status     | Evidence                                                                                                                                                              |
| --- | -------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `verify-multi-namespace.sh` exists, executable, asserts all 6 MULTI                          | ✓ VERIFIED | File exists `-rwxr-xr-x`, 466 lines, references MULTI-01..06 in 24+ places, exited 0 with "ALL VERIFICATIONS PASSED (35 assertions)"                                  |
| 2   | `markdown-renderer/run.sh` passes `-c /tmp/nginx.conf` to nginx (bug fix)                    | ✓ VERIFIED | `exec nginx -c /tmp/nginx.conf -g 'daemon off;'` (run.sh line 10); commit `ca0122e` ("fix(05-01): use generated nginx config...") made this change                    |
| 3   | `markdown-renderer/generate_nginx.py` has minimal-config tmp-dirs branch (helper extraction) | ✓ VERIFIED | `_ensure_nginx_tmp_dirs()` helper at line 396; called from both `_write_minimal_nginx` (line 420) and `main()` (line 502); commit `ca0122e`                           |
| 4   | `markdown-renderer/DOCS.md` has new sections explaining multi-namespace behavior             | ✓ VERIFIED | `## Multi-Namespace Behavior` (line 32), `### Namespace Name Rules` (line 41), `### Reading from /share, /config, /media` (line 56), `## Validation Status` (line 75) |
| 5   | `markdown-renderer/README.md` Manual HA Ingress Test Checklist extended (≥10 items)          | ✓ VERIFIED | 10 items present (items 1-7 from Phase 4 + items 8/9/10 added in Phase 5); H1 description updated to mention multi-namespace                                          |
| 6   | All 6 MULTI-\* requirements in REQUIREMENTS.md marked complete                               | ✓ VERIFIED | `grep` shows all 6 lines start with `- [x] **MULTI-0X**:`                                                                                                             |

## Gaps Summary

No gaps found. Phase goal fully achieved. The 6 MULTI acceptance criteria are not just structurally present from Phase 4
— they are empirically verified in a running container by `verify-multi-namespace.sh` (35 assertions across 5 scenarios,
all passing). The DOCS.md + README.md user-facing documentation accurately reflects the verified behavior, and
`make check-all` passes clean.

The plan also discovered and fixed two latent runtime bugs (run.sh missing `-c /tmp/nginx.conf`, and
`_write_minimal_nginx` not creating nginx tmp dirs) during empirical verification; both fixes are documented in the
SUMMARY.md deviation log and committed (`ca0122e`).

---

_Verified: 2026-06-27T19:05:00Z_ _Verifier: the agent (gsd-verifier)_
