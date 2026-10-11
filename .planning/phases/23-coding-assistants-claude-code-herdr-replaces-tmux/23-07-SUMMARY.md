---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 07
subsystem: infra
tags: [herdr, herdr-web-service, nginx, home-assistant-ingress, bashio, verify-harness]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-04: validated nginx block (VERDICT: GO); 23-06: patched herdr-web-service built in the image, startup hook serving 127.0.0.1:7340"
provides:
  - "herdr-web-service reachable at /services/ through the add-on nginx on the existing ingress port 8099 (no new port), spike-validated block copied verbatim"
  - "Services tab (lazy ./services/ iframe) in index.html and an Agent Web UI row in info.html"
  - "optional add-on option herdr_web_password (password?) that sets the web-service login through the plugin's own set-password over stdin on every start"
  - "harness scenarios services and services-auth (both part of all)"
affects: [23-08, 23-09]

actuals:
  tokens: 14000
  tasks: 2
  commits: 2

plan_head_before: 3700425ed2d2fd4e97e61eb46da4144135b141ff
plan_head_after: 0b8a03fc74803f68a83aad1ec7e060645162c7d5
commits: 2

tech-stack:
  added: []
  patterns:
    - "nginx rewrites Host/Origin to loopback values and empties X-Forwarded-For/-Proto so the plugin's allow-list accepts ingress traffic and never emits Secure cookies or HSTS"
    - "secret handed to a child process only via `printf '%s\\n' | cmd` stdin, env var scoped to the single command, shell variable unset afterwards"
    - "option is the source of truth on every start; a rejected value is a warning (D-07)"

key-files:
  created: []
  modified:
    - coding-assistants/nginx.conf
    - coding-assistants/index.html
    - coding-assistants/info.html
    - coding-assistants/config.yaml
    - coding-assistants/run.sh
    - internal/verify-coding-assistants.sh

key-decisions:
  - "Option name herdr_web_password, schema password? with no default (precedent mqtt_password); an empty or literal null value only logs an info line and leaves the login closed (503)"
  - "Failed logins per container are capped at two in the harness because all requests through nginx share the loopback client address and the plugin rate-limits per address"
  - "Removing the option later does not delete an existing auth file; the option is applied on every start only when present (to be documented in 23-08)"

requirements-completed: [D-05, D-07]

coverage:
  - id: E1
    description: "/services/ is proxied by the add-on nginx with the spike block byte-identical: relative 301, relative assets, exactly one CSP with frame-ancestors 'self', no HSTS, login 503 without password, WebSocket refused without session, plugin bound to loopback only, /terminal/ unchanged, Services tab on the landing page"
    requirement: D-05
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh plugins services (all PASS); diff of the nginx block against the spike document is empty"
        status: pass
    human_judgment: false
  - id: E2
    description: "herdr_web_password: wrong password 401, right password 204 with HttpOnly non-Secure hwv_session cookie, /api/session and /api/roster and the WebSocket gated by the cookie, auth.json mode 600 without plaintext, password in no log, hash survives container re-creation"
    requirement: D-05
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh services services-auth (container A)"
        status: pass
    human_judgment: false
  - id: E3
    description: "A password the plugin rejects is a warning naming the unmet rule, never the value; run.sh and nginx keep running; no option gives an info line and a closed login (503)"
    requirement: D-07
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh services-auth (containers B and C)"
        status: pass
    human_judgment: false
  - id: E4
    description: "The Services tab and the patched client work in a real browser behind real HA ingress (login page, roster, console without 404, cookie accepted inside the iframe)"
    requirement: D-05
    verification: []
    human_judgment: true
    rationale: "Only curl-level behaviour is proven; the React client is never executed by the harness. Belongs in 23-09 human verification (also 23-SPIKE-WEB-SERVICE.md open issue 2)."

duration: 70min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 07: herdr-web-service behind nginx at /services/ Summary

**herdr-web-service is proxied at /services/ through the existing ingress port with the spike-validated nginx block, gets a Services tab, and its login is driven by the optional `herdr_web_password` add-on option (piped to the plugin's `set-password` over stdin); proven end-to-end by the `services` and `services-auth` harness scenarios.**

## Performance

- **Duration:** about 70 min across two executors (the first was cut off with Task 2 uncommitted; this one re-proved
  and committed it)
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- nginx.conf: the `/services/` block from `23-SPIKE-WEB-SERVICE.md` copied verbatim after `/terminal/` (diff against the
  spike block is empty): relative `301 services/`, `proxy_pass http://127.0.0.1:7340/`, Host/Origin forced to loopback,
  X-Forwarded-* emptied, plugin CSP and HSTS hidden, one replacement CSP with `frame-ancestors 'self'`.
- index.html: `Services` tab button, lazy `frameServices` iframe (`data-src="./services/"`), `services` entry in the
  `iframes` map. info.html: `Agent Web UI -> Ingress -> /services/` row.
- config.yaml: `herdr_web_password: password?` (no default).
- run.sh: block between the plugin link loop and the `herdr server` start. Skips when the plugin directory is absent,
  logs an info line when the option is empty/`null`, otherwise resolves `herdr plugin config-dir
  imontes.herdr-web-service`, `mkdir -p`, and runs the plugin's `set-password` with `printf '%s\n' "$PW" |
  HERDR_PLUGIN_CONFIG_DIR=... sh scripts/bun.sh scripts/plugin.ts set-password`, capturing combined output; success is
  an info line, failure a warning containing only the plugin's output (unmet rules). All password-bearing variables are
  unset afterwards; no xtrace in the block.
- Harness: scenario `services` (proxy path against the real add-on nginx) and `services-auth` (containers A, B, C as
  planned, including the re-creation on the same /data).

## Task Commits

1. **Task 1: nginx /services/ block, Services tab and info row, `services` scenario** - `3f90e63` (feat)
2. **Task 2: `herdr_web_password` option, run.sh set-password flow, `services-auth` scenario** - `0b8a03f` (feat)

## Verification

- `bash internal/verify-coding-assistants.sh plugins services services-auth`: ALL CHECKS PASSED, exit 0 (67 PASS,
  fresh image build).
- `bash internal/verify-coding-assistants.sh drift claude mcp herdr-core herdr-attach surface`: 125 PASS, exit 0.
- shellcheck (run.sh, harness) clean; yamllint on config.yaml shows only a pre-existing relaxed-profile
  line-length warning (line 81, not in this plan's change; the repository profile reports none); all pre-commit hooks
  green on commit (version, config schema, secrets scan, line endings).
- All acceptance greps of both tasks pass; `set-password` (run.sh:604) precedes the `herdr server` block (run.sh:614+).
- The Dockerfile did not change in this plan, so no separate Dockerfile build was needed beyond the harness build.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verification run failed with "No space left on device" (environment)**
- **Found during:** Task 2 verification
- **Issue:** the first `services-auth` run failed for container C (`cp: error writing /data/opencode/bin/opencode`) because
  `/tmp` is a 7.7 GB tmpfs and a stale harness scratch directory from the cut-off session
  (`/tmp/akentner/tmp.D4iUwwovZe`, about 5 GB, one 424 MB data copy per old scenario) filled it. Not a code defect: all
  assertions up to that point passed.
- **Fix:** re-ran with `TMPDIR=/var/tmp/ca-verify-23-07` (disk, 91 GB free); all green. Removal of the stale directory
  was denied by the permission layer (outside the authorised cleanup), so it is still there.
- **Files modified:** none

**2. [Process] Cleanup of stale harness artifacts from the cut-off run**
- Removed containers `ca-verify-1791745177-*` and image `ca-verify-2307:dev` (explicitly authorised); nothing else
  touched.

**Total deviations:** 1 blocking environment issue, 0 code changes beyond the plan. **Impact:** none on scope.

## Authentication Gates

None.

## Issues Encountered

- The 5 GB stale scratch directory `/tmp/akentner/tmp.D4iUwwovZe` (tmpfs) remains; delete it manually
  (`rm -rf` as the owning user, or `podman unshare rm -rf` if it holds subuid-owned files) before the next harness run
  from the default TMPDIR, or run the harness with `TMPDIR` on disk.
- Login sessions live in the plugin STATE dir (ephemeral): after an add-on restart the user logs in again; only the
  password hash persists (verified by the re-creation check).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-23-23 (cookie-gated session and WebSocket asserted through nginx), T-23-24 (single CSP with `frame-ancestors 'self'`), T-23-25 (no HSTS, cookie not Secure) and T-23-26 (password never in argv, auth file or logs; asserted after start and after re-creation, including the rejected `short1!` value) are mitigated as planned. T-23-27 and T-23-28 are accepted as documented in the plan and belong in the 23-08 docs.

## Next Phase Readiness

- 23-08 documents: the `herdr_web_password` option (applied on every start; removing it does not delete the existing
  auth file; 6+ characters with a symbol, a number and an uppercase letter), the /services/ path, the ephemeral session
  vs persistent hash, `hwv_session` cookie scope (Path=/, HttpOnly, SameSite=Strict, also sent to HA paths on the same
  origin) and the root-shell blast radius (T-23-27).
- 23-09 human verification: open the Services tab in real HA ingress, log in, see the roster, check the browser console.

## Self-Check: PASSED

- FOUND: coding-assistants/nginx.conf, coding-assistants/index.html, coding-assistants/info.html,
  coding-assistants/config.yaml, coding-assistants/run.sh, internal/verify-coding-assistants.sh
- FOUND commits: 3f90e63, 0b8a03f
