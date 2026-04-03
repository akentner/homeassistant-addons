# Roadmap: Home Assistant Add-ons Repository

_Milestone 1 — CI fixes, auto-update workflow, and Meridian add-on_

## Overview

| #   | Phase                | Goal                                                          | Requirements                                                   | Plans |
| --- | -------------------- | ------------------------------------------------------------- | -------------------------------------------------------------- | ----- |
| 1   | Quality Fixes        | 2/2 | Complete   | 2026-04-03 |
| 2   | Auto-Update Workflow | Daily upstream version checking commits to main automatically | AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05                    | TBD   |
| 3   | Meridian Add-on      | Claude Max proxy add-on installable from the repository       | MER-01, MER-02, MER-03, MER-04, MER-05, MER-06, MER-07, MER-08 | TBD   |

## Phase 1: Quality Fixes

**Goal:** All pre-commit hooks pass cleanly on the existing codebase with no excluded tools or incorrect documentation.
**Requirements:** FIX-01, FIX-02, FIX-03

### Success Criteria

1. Running `make lint` on the repository passes without errors for all add-ons, including `phone-logger`
2. The `phone-logger/DOCS.md` adapter example shows `type: fritz_callmonitor` and matches the actual adapter name used
   in code
3. `hadolint` runs as part of `make lint` and produces no suppressed-by-disabling errors on any Dockerfile

### Plans

**Plans:** 2/2 plans complete

Plans:

- [x] 01-01-PLAN.md — Extend validate-versions hook to phone-logger and fix DOCS.md adapter type (FIX-01, FIX-02)
- [x] 01-02-PLAN.md — Re-enable hadolint in pre-commit with correct ignore rules (FIX-03)

---

## Phase 2: Auto-Update Workflow

**Goal:** A daily GitHub Actions workflow detects upstream releases and commits version updates to main without manual
intervention. **Requirements:** AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05

### Success Criteria

1. Triggering the workflow manually (`workflow_dispatch`) when an add-on is already up to date produces no commit and
   exits successfully
2. After an upstream project publishes a new release, the next scheduled run updates all three version files
   (`config.yaml`, `build.yaml`, `README.md`) and pushes a commit to main within 24 hours
3. The workflow run log shows which add-ons were checked, which were updated, and which were skipped — with no
   credentials beyond the default `GITHUB_TOKEN`
4. Two consecutive scheduled runs on an already-updated repository produce no additional commits

### Plans

TBD

---

## Phase 3: Meridian Add-on

**Goal:** The Meridian Claude Max proxy is installable as a Home Assistant add-on, persists credentials across restarts,
and exposes port 3456 to the local network. **Requirements:** MER-01, MER-02, MER-03, MER-04, MER-05, MER-06, MER-07,
MER-08

### Success Criteria

1. The add-on installs and starts from the repository without errors when Claude credentials are already present in
   `/data/.claude`
2. When credentials are absent, the add-on fails to start and the HA log shows actionable instructions for running
   `claude login` via the terminal add-on
3. After `claude login` is completed and the add-on is restarted, sending a request to
   `http://<ha-host>:3456/v1/messages` returns a valid Anthropic-compatible response
4. Restarting the add-on container does not require re-authentication — the OAuth token survives restarts via the
   `/data` volume
5. Running `make update-version ADDON=meridian VERSION=x.y.z` or the auto-update workflow correctly updates all three
   version files for meridian

### Plans

TBD

---

## Progress

| Phase                   | Plans Complete | Status      | Completed |
| ----------------------- | -------------- | ----------- | --------- |
| 1. Quality Fixes        | 0/2            | Not started | -         |
| 2. Auto-Update Workflow | 0/?            | Not started | -         |
| 3. Meridian Add-on      | 0/?            | Not started | -         |
