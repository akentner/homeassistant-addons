---
phase: "14"
slug: real-ha-end-to-end-verification-operator-documentation
status: validated
nyquist_compliant: false
wave_0_complete: true
created: "2026-10-03"
---

# Phase 14 — Validation Strategy

> Written retroactively to satisfy health check W009. Nyquist validation is intentionally disabled for this project
> (`workflow.nyquist_validation: false` in `.planning/config.json`), and `14-RESEARCH.md` skipped its Validation
> Architecture section for that reason. This file records that decision; it does not add new tests.

## Test Infrastructure

| Property | Value |
| --- | --- |
| **Framework** | Bash scenario scripts against a live Home Assistant host (no unit-test framework) |
| **Config file** | none |
| **Quick run command** | `make lint` (pre-commit + shellcheck, per `TESTING.md`) |
| **Full suite command** | `internal/verify-bridge-e2e/00-happy-path.sh` plus scenarios `01`..`12`, then `99-cleanup.sh` |
| **Runtime** | Live-HA run is operator-driven; not executed in CI |

## Validation Approach

- Static gate: pre-commit hooks and shellcheck over the new scripts (`make lint`).
- Empirical gate: 12 per-`error_code` scenarios under `internal/verify-bridge-e2e/` (shared helpers in `_lib.sh`)
  and the test add-on under `tools/test-addon/`.
- The live-HA run was deferred to operator runtime: the preflight returned 1 in the authoring environment (no `tofu`,
  no Provider binary, `/healthz` unreachable) — see `14-03-SUMMARY.md`.

## Manual-Only Verifications

| Behavior | Why manual | Command |
| --- | --- | --- |
| Full apply/destroy cycle against real HA | Needs live HA host, `tofu`, Provider binary | `internal/verify-bridge-e2e/00-happy-path.sh` |
| 12 `error_code` scenarios | Same live-HA prerequisites | `internal/verify-bridge-e2e/01-*.sh` .. `12-*.sh` |

## Validation Sign-Off

- [x] Static lint gate defined
- [x] Empirical scenarios exist for every Bridge `error_code`
- [ ] Live-HA run executed and captured — **outstanding**

**Approval:** validation intentionally skipped (nyquist disabled); `nyquist_compliant: false` until the live run is done.
