---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 02
subsystem: infra
tags: [supply-chain, herdr, plugin-review, package-legitimacy, human-gate]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: 23-RESEARCH.md pins and package legitimacy audit for the three herdr plugins
provides:
  - 23-PLUGIN-REVIEW.md static review dossier (execution, network, filesystem, secrets, licence) for the three pinned herdr plugins
  - Human approval of all three plugins at the reviewed pins, recorded as machine-readable PIN lines
  - Package-legitimacy verdict for vite 8.3.4 and @vitejs/plugin-react 6.1.2 (too-new, false-positive class, approved)
  - Edit list of root-absolute client URLs in herdr-web-service for the later sub-path spike (23-04)
affects: [23-04, 23-06, 23-07]

actuals:
  tokens: 8500
  tasks: 3
  commits: 2

plan_head_before: 73cc149072e730bae8d17c3fad05b48d092f3702
plan_head_after: 3a411b7cf60af0a29a1b40bd17ae67ea7098ffd5
commits: 2

key-files:
  created:
    - .planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-PLUGIN-REVIEW.md

key-decisions:
  - "All three herdr plugins approved at the research pins (user answer `approved: all`, 2026-10-11): subagent-watch c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8, web-service e9082b3fb969064e89153a8c6b2170366982f7f9, claude-limits 9c0c9a1931ac91f9d865031e2dc58d66a7d1b594"
  - "Accepted risk: herdr-claude-limits has no licence file and is redistributed in the public ghcr.io image"
  - "Accepted risk: subagent-watch stays at the older pin although upstream main is 10 commits ahead (security and viewer fixes); the weaker paths are inactive because the add-on never runs the setup action"
  - "vite 8.3.4 and @vitejs/plugin-react 6.1.2 (too-new) accepted as build-time dependencies from the plugin's own bun.lock"

requirements-completed: [D-06]

coverage:
  - id: D1
    description: "Static, file:line-referenced review dossier for all three pinned plugin commits; each pin verified by fetching it (git rev-parse HEAD equals the pin); nothing installed or executed"
    requirement: D-06
    verification:
      - kind: other
        ref: "grep -c '^## Plugin: ' 23-PLUGIN-REVIEW.md == 3; each section carries EXECUTION SURFACE / NETWORK SURFACE / FILESYSTEM WRITES / SECRETS / LICENCE"
        status: pass
    human_judgment: false
  - id: D2
    description: "A human approved each plugin, the claude-limits licence gap, the root execution surface and the two too-new npm packages"
    requirement: D-06
    verification:
      - kind: human
        ref: "checkpoint:human-verify gate=blocking-human, answer `approved: all`"
        status: pass
    human_judgment: true
    rationale: "Supply-chain and licence acceptance are a human decision by design"
  - id: D3
    description: "Decision section is final and machine-readable: exactly one PIN line per plugin with a 40-char SHA, no PENDING, no SCOPE-CHANGE line (web-service approved)"
    requirement: D-06
    verification:
      - kind: other
        ref: "grep -E '^PIN HERDR_[A-Z_]+_REF [0-9a-f]{40}$' 23-PLUGIN-REVIEW.md -> 3 matches; no PENDING after '## Decision'"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 02: herdr plugin supply-chain gate Summary

**Static review dossier for the three third-party herdr plugins (subagent-watch, web-service, claude-limits) at commit-SHA pins, human-approved with `approved: all`, and recorded as three machine-readable `PIN HERDR_*_REF <sha>` lines for plans 23-04, 23-06 and 23-07.**

## Performance

- **Duration:** about 40 min including the human gate
- **Started:** 2026-10-10
- **Completed:** 2026-10-11
- **Tasks:** 3 (2 auto, 1 blocking-human checkpoint)
- **Files modified:** 1 (created), only inside the phase directory

## Accomplishments

- Each pin was fetched (`git fetch --depth 1 origin <sha>`, detached checkout) into its own `mktemp -d` and `git rev-parse HEAD`
  matched all three pins; nothing was installed, built or executed.
- Per plugin: manifest, file inventory, execution surface, network surface, filesystem writes, secrets and licence with
  file:line references. Key findings: subagent-watch has no network, credentials or startup hook; web-service binds
  `127.0.0.1:7340` behind Host/Origin allow-lists and an argon2id password gate, and is effectively full terminal control
  once signed in; claude-limits reads the Claude OAuth token and sends it only to `api.anthropic.com`.
- web-service npm review: 220 locked packages with integrity hashes, no `trustedDependencies`, only `fsevents` has an
  install script (macOS-only); `vite` 8.3.4 and `@vitejs/plugin-react` 6.1.2 flagged `too-new` but SLSA-attested,
  very high traffic, build-time only.
- Edit list of root-absolute client URLs (`api.ts`, `roster.ts`, `main.tsx`, `InstallBanner.tsx`, `ChatView.tsx`,
  `index.html`, `manifest.webmanifest`, `sw.js`) prepared for the 23-04 sub-path spike.
- Decision section finalised with date 2026-10-11, the verbatim answer and three PIN lines.

## Task Commits

1. **Task 1: fetch pinned commits, write static review dossier** - `bfd5e1f` (docs)
2. **Task 2: human review gate** - no commit (checkpoint, answer `approved: all`)
3. **Task 3: record decision as machine-readable pins** - `3a411b7` (docs)

## Files Created/Modified

- `.planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-PLUGIN-REVIEW.md` - dossier and Decision section

## Decisions Made

See `key-decisions`. Approved pins:

```text
PIN HERDR_SUBAGENT_WATCH_REF c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8
PIN HERDR_WEB_SERVICE_REF e9082b3fb969064e89153a8c6b2170366982f7f9
PIN HERDR_CLAUDE_LIMITS_REF 9c0c9a1931ac91f9d865031e2dc58d66a7d1b594
```

## Accepted Risks

- claude-limits: no licence file, redistribution in a public image is not permitted by the author (accepted by the user).
- subagent-watch: pinned 10 commits behind upstream `main` (`c9cf753`); re-pin would require a diff review first.
- web-service and the others run as root with HA/Supervisor tokens in the herdr server environment; mitigated by the
  password gate, loopback bind, commit pins and (in 23-06) runtime failure isolation per D-07.

## Deviations from Plan

None - plan executed exactly as written. The `gsd_run query package-legitimacy check` tool accepts package names only
(not `name@version`); the dossier records this and applies the by-name verdict because `latest` equals the locked version.

## Issues Encountered

None.

## Known Stubs

None.

## Threat Flags

None - this plan adds no code or network surface; it only records the gate for T-23-12, T-23-13, T-23-14 and T-23-SC.

## Next Phase Readiness

Plans 23-04 (spike: web-service approved, so the precondition holds, no SCOPE-CHANGE line) and 23-06 (Dockerfile ARG
defaults and `build.yaml` mirror from the three PIN lines) can proceed. 23-07 keeps D-05 (`/services/` ingress) in scope.

## Self-Check: PASSED

- FOUND: 23-PLUGIN-REVIEW.md with three PIN lines and no PENDING
- FOUND commits: bfd5e1f, 3a411b7
