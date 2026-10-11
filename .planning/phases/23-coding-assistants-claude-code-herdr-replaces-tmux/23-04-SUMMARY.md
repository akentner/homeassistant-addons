---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 04
subsystem: infra
tags: [herdr, herdr-web-service, nginx, ha-ingress, spike, bun, vite]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-PLUGIN-REVIEW.md approval and PIN HERDR_WEB_SERVICE_REF e9082b3 (plan 23-02)"
provides:
  - "coding-assistants/patches/herdr-web-service-subpath.patch: client-only sub-path patch that applies with git apply at the pinned commit"
  - "internal/spike-herdr-web-service.sh: re-runnable throwaway-container spike (emulated HA ingress, checks C1-C9)"
  - "23-SPIKE-WEB-SERVICE.md: VERDICT GO, validated nginx block, ordered Dockerfile build sequence, runtime findings"
affects: [23-06, 23-07, 23-09]

actuals:
  tokens: 18400
  tasks: 2
  commits: 3

plan_head_before: fc060492625a790aa109a47101b510164c727bd3
plan_head_after: 5b4bcced4074bf5bd927b2575eb78eb2fe242386
commits: 3

tech-stack:
  added: []
  patterns:
    - "third-party plugin code is fetched, patched, built and executed only inside a throwaway container; the host only runs docker"
    - "inner nginx (add-on) behind an outer nginx emulating HA ingress to prove sub-path behaviour without a real HA"

key-files:
  created:
    - coding-assistants/patches/herdr-web-service-subpath.patch
    - internal/spike-herdr-web-service.sh
    - .planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-SPIKE-WEB-SERVICE.md
  modified:
    - .pre-commit-config.yaml

key-decisions:
  - "VERDICT GO: herdr-web-service works under /services/ behind an emulated HA ingress with a client-only patch plus the validated nginx block (9/9 checks PASS)"
  - "X-Forwarded-For and X-Forwarded-Proto are emptied in the /services/ block (HA ingress sends them and the plugin trusts them from a loopback peer)"
  - "Service worker is removed and push reported as unsupported; web/public/sw.js is deleted by the patch"
  - "Production prune (bun install --frozen-lockfile --production) is safe: node_modules 148 MB -> 19 MB, server and login unaffected"

requirements-completed: [D-05, D-06]

coverage:
  - id: D1
    description: "Sub-path patch applies at the pinned commit; after bun install --frozen-lockfile and bun run build every asset, API and WebSocket URL is relative"
    requirement: D-05
    verification:
      - kind: command
        ref: "bash internal/spike-herdr-web-service.sh (git apply --check at the pin, C2, C3)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Through an emulated HA ingress the plugin serves redirect, assets, login (503/401/204), cookie-gated API, WebSocket 101, one CSP with frame-ancestors 'self', no HSTS, and keeps rejecting a spoofed Host"
    requirement: D-05
    verification:
      - kind: command
        ref: "bash internal/spike-herdr-web-service.sh (C1-C9, 9/9 PASS)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The real React app renders and works in a browser under the real HA ingress prefix"
    requirement: D-05
    verification: []
    human_judgment: true
    rationale: "The spike proves URLs and protocols with curl against an emulated ingress; nothing executed the SPA in a browser or against a real HA"
  - id: D4
    description: "Spike document starts with a single VERDICT line and carries the nginx block, build sequence, findings, check table and transcript"
    requirement: D-06
    verification:
      - kind: command
        ref: "grep VERDICT count == 1, first line VERDICT: GO, contains 'location /services/'"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 04: herdr-web-service sub-path spike Summary

**herdr-web-service runs under `/services/` behind an emulated HA ingress with a client-only build-time patch and a validated nginx block: 9/9 checks pass in a throwaway container, VERDICT: GO.**

## Performance

- **Duration:** about 15 min
- **Started:** 2026-10-11T16:22Z
- **Completed:** 2026-10-11T16:36Z
- **Tasks:** 2 (1 tracer, 1 auto)
- **Files modified:** 3 created for the plan, 1 extra (`.pre-commit-config.yaml`, see Deviations)

## Accomplishments

- Patch against pin `e9082b3` (9 files, +33/-118, nothing under `server/`): Vite `base: "./"`, `api/...` instead of
  `/api/...`, WebSocket URL from `new URL("ws", location.href)`, service worker removed (and `web/public/sw.js`
  deleted), relative icon, upload and manifest URLs.
- Spike script: one container from the amd64 HA Debian base image installs bun, nginx and the digest-checked herdr
  0.9.3 binary, applies the patch, builds, prunes to production dependencies, links the plugin, starts `herdr server`
  (the plugin's startup hook brings up the bun server on its own), then runs an inner nginx (add-on) behind an outer
  nginx emulating HA ingress and checks C1-C9.
- Findings 23-06 and 23-07 can copy: ordered build sequence, nginx block, state dir
  (`/root/.local/state/herdr/plugins/imontes.herdr-web-service/`, outside `/data`), config dir
  (`$XDG_CONFIG_HOME/herdr/plugins/config/imontes.herdr-web-service`, `auth.json` mode 600, picked up without restart),
  `node_modules` 148 MB -> 19 MB after the prune, `dist/` 784 KB, bun cache 153 MB to remove.

## Task Commits

1. **Task 1 (tracer): patch and spike script** - `d7d82aa` (feat); preceded by `4c20b19` (chore, hook exclusion needed to
   keep the patch byte-exact)
2. **Task 2: spike document with verdict** - `5b4bcce` (docs)

Tracer gate: the tracer `<verify>` was re-run end to end after the final script edit (9/9 PASS) before Task 2; no
checkpoint was required (automated verify only, `gate` not `blocking-human`).

## Files Created/Modified

- `coding-assistants/patches/herdr-web-service-subpath.patch` - sub-path client patch, applied with `git apply` by 23-06
- `internal/spike-herdr-web-service.sh` - throwaway-container spike, shellcheck-clean, executable
- `.planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-SPIKE-WEB-SERVICE.md` - verdict and reusable facts
- `.pre-commit-config.yaml` - `trailing-whitespace` and `end-of-file-fixer` skip `*/patches/*.patch`

## Decisions Made

See `key-decisions`. The residual exposure of the nginx Host/Origin rewrite (T-23-17) is documented in the spike
document (Open issues item 4); it matches the existing `/terminal/` path and keeps the plugin password, the HttpOnly
SameSite=Strict cookie, the WebSocket cookie requirement and HA ingress admin authentication in force.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pre-commit whitespace hooks rewrote the patch**
- **Found during:** Task 1 commit
- **Issue:** `trailing-whitespace` stripped the single-space blank context lines of the patch, leaving a file that is
  no longer byte-exact (and that 23-09's `pre-commit run --files ... patch` would rewrite again)
- **Fix:** `exclude: ^[^/]+/patches/.*\.patch$` on `trailing-whitespace` and `end-of-file-fixer`; patch regenerated
  byte-exact; separate `chore(23-04)` commit so the task commit holds only the plan's files
- **Files modified:** `.pre-commit-config.yaml`
- **Commit:** `4c20b19`

**2. [Rule 1 - Bug] C3 flagged the unused service worker file**
- **Found during:** first spike run (8/9)
- **Issue:** `web/public/sw.js` is copied into `dist/` and carries root-absolute `/api/`, `/ws`, `/assets/` strings
- **Fix:** the patch deletes `web/public/sw.js` (nothing registers it any more); C3 stays as strict as specified
- **Commit:** `d7d82aa`

**3. [Rule 2 - Missing critical] HA ingress forwarding headers**
- **Found during:** Task 1 design
- **Issue:** the plan said "do not set X-Forwarded-*", but HA ingress sends them and nginx forwards them; the plugin
  trusts them from a loopback peer (Secure cookie, HSTS, rate-limit key)
- **Fix:** outer nginx sends `X-Forwarded-For`, `X-Forwarded-Proto https` and `X-Ingress-Path` like HA; the block
  empties the first two. The unmitigated case was derived from source, not run (spike document, Open issues item 1)
- **Commit:** `d7d82aa`

**4. [Rule 3 - Blocking] lint gates on the spike script**
- **Issue:** repo pre-commit shellcheck (0.10.0.1) reports SC2317 on the trap handler where the local shellcheck reports
  SC2329; gitleaks flagged the RFC 6455 example `Sec-WebSocket-Key`
- **Fix:** `# shellcheck disable=SC2317,SC2329` on the cleanup function; `# gitleaks:allow` on that line
- **Commit:** `d7d82aa`

### Smaller adjustments (no rule needed)

- The pinned checkout is fetched inside the container, not on the host and mounted read-only (stricter than the plan:
  the host never touches plugin code). The patch, inner script and nginx block are mounted read-only.
- `manifest.webmanifest` made relative and `alerts.ts` `supported()` forced to `false` (otherwise
  `navigator.serviceWorker.ready` would hang when notifications are enabled).

**Total deviations:** 4 auto-fixed (1 bug, 1 missing critical, 2 blocking). **Impact:** none on scope; one extra
repo-config file touched (`.pre-commit-config.yaml`) so a byte-exact patch can live in the repo.

## Issues Encountered

None beyond the deviations. Open items for later plans are in the spike document: no real browser or real HA ingress
was used (belongs in the 23-09 human verification), `rm -rf .git` after the build is untested (23-06 plugins scenario
re-proves it), and the plugin state dir lives outside `/data`.

## Known Stubs

None.

## Threat Flags

None. The plugin ran only inside a throwaway container with read-only mounts and no host credentials (T-23-15, T-23-18);
the patch is applied with `git apply --check` + `git apply` against the exact pin (T-23-16); the Host/Origin rewrite
(T-23-17) is covered by C4-C6 and C8 and documented as residual exposure.

## Next Phase Readiness

Verdict is GO, so 23-06 (Dockerfile web-service step) and 23-07 (nginx `/services/` block, password option, harness
scenario `services`) can proceed. 23-06 copies the build sequence and the patch; 23-07 copies the nginx block verbatim.

## Self-Check: PASSED

- FOUND: coding-assistants/patches/herdr-web-service-subpath.patch, internal/spike-herdr-web-service.sh,
  23-SPIKE-WEB-SERVICE.md (first line `VERDICT: GO`)
- FOUND commits: 4c20b19, d7d82aa, 5b4bcce
- Acceptance criteria re-run: patch non-empty with `diff --git`, 0 `b/server/` entries, shellcheck exit 0, spike exit 0 with
  nine PASS lines, document checks pass
