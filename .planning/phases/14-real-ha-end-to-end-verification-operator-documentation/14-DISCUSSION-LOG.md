# Phase 14: Real-HA End-to-End Verification + Operator Documentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents. Decisions are captured in
> CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-05 **Phase:** 14-real-ha-end-to-end-verification-operator-documentation **Areas discussed:** host
choice, test target add-on, error-code coverage, docs depth, test-addon implementation, verify-script structure, docs
split, state safety

---

## 1. Host choice

| Option                       | Description                                                                              | Selected |
| ---------------------------- | ---------------------------------------------------------------------------------------- | -------- |
| ha-nextgen only              | Fresh, non-production host. No risk to running add-ons.                                  |          |
| haos-op3050-1 only           | Production host with running add-ons. AGENTS.md Live-System rule argues against.         |          |
| Both, ha-nextgen first       | Use ha-nextgen first then re-run on haos-op3050-1 against a non-critical add-on.         |          |
| ha-nextgen IST haos-op3050-1 | Same physical host; `ha-nextgen` is Tailscale hostname, `haos-op3050-1` is LAN identity. | ✓        |

**User's choice:** ha-nextgen IST haos-op3050-1 — clarified that they are the same physical machine. **Notes:** Single
host with dual hostname; use whichever hostname is convenient per call (Tailscale from outside, LAN from inside).

## 2. Test target add-on

| Option                                                         | Description                                                                  | Selected |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------- |
| Purpose-built tiny test add-on                                 | Minimal stub add-on (no-op Busybox); mirrors Phase 9 bridge-fixture pattern. | ✓        |
| core_ssh or similar non-critical core add-on                   | Real but unprotected. AGENTS.md Live-System rule uncomfortable.              |          |
| User-installed add-on like core_mosquitto (in critical_addons) | Exercise the 403 but can't actually install through Provider.                |          |

**User's choice:** Purpose-built tiny test add-on. **Notes:** Recommended path; hermetic, no risk to real add-ons.

## 3. Error-code coverage

| Option                            | Description                                                                                 | Selected |
| --------------------------------- | ------------------------------------------------------------------------------------------- | -------- |
| Targeted scenarios per error_code | One scenario per error_code in BRIDGE-09 + Phase 12 additions; capture diagnostic verbatim. | ✓        |
| Natural-error-only                | Document only organic failures. SC-5 "every error code" almost certainly fails.             |          |
| Hybrid                            | Organic + targeted for the five most-likely codes; skip rare ones with explicit annotation. |          |

**User's choice:** Targeted scenarios per error_code. **Notes:** Recommended path; matches SC-5 "every error code"
exactly.

## 4. Documentation depth

| Option                                                            | Description                                                      | Selected |
| ----------------------------------------------------------------- | ---------------------------------------------------------------- | -------- |
| Expand DOCS.md substantially; add a new README.md install section | Full operator reference in DOCS.md; 1-page install in README.md. | ✓        |
| Minimal — only patch DOCS.md with observed issues                 | Leave skeleton; just add troubleshooting section. SC-5 gap.      |          |
| Full rewrite of both Bridge and Provider DOCS.md                  | Rewrite both to uniform template.                                |          |

**User's choice:** Expand DOCS.md substantially; add a new README.md install section. **Notes:** Recommended path;
mirrors existing repo add-on pattern.

## 5. Test add-on implementation

| Option                                        | Description                                                          | Selected |
| --------------------------------------------- | -------------------------------------------------------------------- | -------- |
| Add-on in this repo under `tools/test-addon/` | Sibling of test-bridge-fixture; local-build via HA's local pipeline. | ✓        |
| Reuse an existing add-on                      | Public add-on already on host. Coupling risk.                        |          |
| External test add-on in a sibling repo        | Cleaner hygiene; cross-repo dependency.                              |          |

**User's choice:** Add-on in this repo under `tools/test-addon/`. **Notes:** Recommended path; hermetic to the repo.

## 6. Verify script structure

| Option                                          | Description                                                                          | Selected |
| ----------------------------------------------- | ------------------------------------------------------------------------------------ | -------- |
| One script per error_code                       | Mirrors verify-bridge-no-token-leak.sh style; captured diagnostic per testdata file. | ✓        |
| Single shell script with all scenarios in order | Easier to invoke; harder to rerun individual scenarios.                              |          |
| Go test files alongside Bridge package          | Strong tooling fit; requires live Supervisor inside test.                            |          |

**User's choice:** One script per error_code. **Notes:** Recommended path; traceability between observation and source
scenario.

## 7. Docs split

| Option                                                       | Description                            | Selected |
| ------------------------------------------------------------ | -------------------------------------- | -------- |
| README.md = 1-page install + token; DOCS.md = full reference | Mirrors phone-logger's existing split. | ✓        |
| Everything in DOCS.md; skip README.md                        | Less work; SC-5 calls out both files.  |          |
| Full content in both files                                   | Heavy duplication; drift risk.         |          |

**User's choice:** README.md = 1-page install + token; DOCS.md = full reference. **Notes:** Recommended path; existing
repo convention.

## 8. State safety during E2E

| Option                                                  | Description                                                                   | Selected |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- | -------- |
| Snapshot /data before, restore on exit                  | Per-scenario snapshot via `.bak.<scenario>`; fingerprint via /v1/state/index. | ✓        |
| Wipe-and-rebuild state for each scenario                | Simpler; typo destroys work.                                                  |          |
| Backup only happy-path state; rely on Provider re-apply | Risk of stuck *.tfstate.lock that /v1/state/index SKIPS.                      |          |

**User's choice:** Snapshot /data before, restore on exit. **Notes:** Recommended path; per-scenario granularity.

---

## the agent's Discretion

Captured in CONTEXT.md §"the agent's Discretion" (D-12 README.md wording; test-addon dummy schema options; _lib.sh
structure; 99-cleanup.sh invocation discipline; /healthz response body documentation).

## Deferred Ideas

Captured in CONTEXT.md §"Deferred Ideas" (TLS termination, Provider Actions, homeassistant_addon_repository resource,
Provider-side state-file introspection, multi-arch builds, CSRF preflight, auto-rotation cadence, install_job_timeout
per-slug overrides, AddOnInfo field coverage).

No new ideas were raised during discussion that aren't already in the Phase 12/13 CONTEXT's deferred sections.
