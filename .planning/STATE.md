---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: markdown-renderer
status: Ready to execute
last_updated: "2026-08-30T17:31:51.960Z"
progress:
  total_phases: 8
  completed_phases: 6
  total_plans: 19
  completed_plans: 15
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-27)

**Core value:** Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version
tracking. **Current focus:** Phase 08 — ci-cd-hardening

## Milestone v1.0 — COMPLETE

All 3 phases shipped. Archived to `.planning/milestones/v1.0-ROADMAP.md`.

| Phase | Name                 | Status   | Completed  |
| ----- | -------------------- | -------- | ---------- |
| 1     | Quality Fixes        | Complete | 2026-04-03 |
| 2     | Auto-Update Workflow | Complete | 2026-04-04 |
| 3     | Meridian Add-on      | Complete | 2026-04-04 |

## Milestone v1.1 — COMPLETE

Roadmap: 3 phases (4-6). All phases complete.

| Phase | Name                             | Status   | Completed  |
| ----- | -------------------------------- | -------- | ---------- |
| 4     | Scaffold + Ingress Validation    | Complete | 2026-06-27 |
| 5     | Multi-Namespace + Dynamic Config | Complete | 2026-06-27 |
| 6     | Git Integration                  | Complete | 2026-06-28 |

## Milestone v1.2 — PLANNED

Roadmap: 1 phase (8), 4 plans in 4 waves. Source: GitHub Actions audit 2026-08-30. Requirements CI-01..CI-10.

| Phase | Name              | Status  | Completed |
| ----- | ----------------- | ------- | --------- |
| 8     | CI/CD Hardening   | Planned | —         |

Plans are strictly serial: 08-01, 08-02 and 08-03 all modify `.github/workflows/_build-template.yml`, so only one may
write per wave. 08-04 documents the end state and therefore runs last.

| Plan  | Wave | Blocked on user                                                              |
| ----- | ---- | ---------------------------------------------------------------------------- |
| 08-01 | 1    | no                                                                           |
| 08-02 | 2    | approval for an image-overwriting verification build; PR #39/#40 disposition  |
| 08-03 | 3    | **yes** — Cloudflare service token + Access app + 2 GitHub secrets            |
| 08-04 | 4    | no                                                                           |

## Current Position

Phase: 08 (ci-cd-hardening) — EXECUTING (gap_closure pending)
Plan: 4 of 4 originally planned; **08-03 partial** (Tasks 2-4 done; Tasks 1+5 deferred to gap-closure plan `08-05-GAP-PLAN.md`)

**Progress bar**: `[████████░░] 89%` (15 of 17 effective plans complete; 1 gap-closure plan ready)

**Branch state:** `main...origin/main` clean; 15 commits on top of pre-phase `5c413aa` (all pushed). `08-03-SUMMARY.md` written as `status: partial`; `08-05-GAP-PLAN.md` written as `gap_closure: true`.

## Accumulated Context

### Key Decisions (v1.1)

| Decision                                      | Rationale                                                                                                            |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Docsify 4.13.1 over MkDocs                    | No build step; "edit file → refresh" works directly; MkDocs requires rebuild on every change                         |
| Mermaid UMD build (not ESM)                   | Self-contained; ESM bundle breaks when vendored due to dynamic import chains                                         |
| `basePath: window.location.pathname`          | HA Ingress strips the token server-side but browser URL retains it; static basePath breaks XHR                       |
| `generate_nginx.py` for config generation     | Mirrors phone-logger's `generate_config.py`; Python justified for structured JSON + template loops                   |
| CI/Quality gate extension folded into Phase 4 | ADD-01 ("consistent with existing add-ons") implies validate-versions.sh and make validate-addons cover new add-on   |
| `run.sh` must pass `-c /tmp/nginx.conf`       | Without it nginx reads default /etc/nginx/nginx.conf (port 80) instead of generator-written config (port 8099)       |
| `_ensure_nginx_tmp_dirs()` helper             | Minimal-fallback nginx config also needs temp dirs pre-created so master can start in non-root envs                  |
| `_git_sync.py` (Phase 6)                      | Mirrors generate_nginx.py pattern; in-memory `last_pull` dict; check=False everywhere — GIT-05 non-blocking contract |
| Single background `while true` in run.sh (P6) | One loop for all namespaces (D-08); per-namespace gating in Python; simpler signal handling than N parallel loops    |
| POSIX `TERM INT` trap (Phase 6)               | POSIX-sh portable form; SIGTERM/SIGINT and TERM/INT are aliases in POSIX `trap`; matches CONVENTIONS.md /bin/sh rule |
| `export HOME=/root` in run.sh (06-02)         | HA base image doesn't export `$HOME`; `git config --global` aborts with `fatal: $HOME not set` without it (GIT-02)   |
| Dockerfile COPY `_git_sync.py` (06-02)        | Plan 01 added the helper but didn't update the Dockerfile's COPY line; new file never made it into the built image   |
| INFO: log lines on git pull/clone success     | Pre-existing `subprocess.run(capture_output=True)` swallowed git's stdout; surfacing it lets operators verify pulls  |
| Bumped v1.0.0 → v1.1.0 in 06-02 (not 06-01)   | Per Phase 5 pattern: empirical verification may surface issues; minor bump clearer than subpatch for new feature     |

### Key Decisions (v1.2)

| Decision                                                            | Rationale                                                                                                                                       |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Cloudflare Access **service token**, not a Bypass policy            | The webhook has no HMAC; `notify-ha.sh` itself says "not acceptable for public exposure". Bypass would be a downgrade from today's protected state |
| Separate path-scoped Access app for `/api/webhook/*`                | Cloudflare matches the most specific path first, so the hostname-wide app and its human policies stay untouched                                  |
| **Reversed** D-03: named secret mappings, NOT `secrets: inherit`     | `docs/DEVELOPMENT.md:113-115` already forbids `inherit` for least privilege. The planning error was caught only because that sentence exists      |
| `notify-ha.sh` fails fast on `3xx`                                  | An auth-proxy redirect is structurally never transient; 3 retries wasted time and buried the signal                                             |
| Diagnostics must read the response **body** file                    | Existing code read curl's stderr, which is empty on a 302 — that is why the annotation was `HTTP 302:` with nothing after the colon               |
| Never add `-L` to the notify curl                                   | Following the redirect fetches the Access login page, which returns 200 — the script would report success while HA received nothing               |
| Per-job timeouts sized ~3x observed p100                            | A 45-minute cap on a 40-second lint job is not a cap. aarch64 measured 13m28s vs amd64 2m49s                                                     |
| Bump all 5 actions together                                         | Breaking-change audit showed all four Docker majors are the same Node-24 + ESM change; the removals do not apply to this repo                    |
| No `ignoreDeps` in `.github/renovate.json`                          | The 2026-07-27 batch-close was an accident, not policy; suppressing Renovate would encode the accident as intent                                 |
| Verification builds treated as service-affecting                     | Per `docs/DEVELOPMENT.md` "Trigger Pitfalls" — a dispatch pushes images to GHCR and fires HA webhooks; needs explicit approval                    |
| Bundled all 5 action bumps in one plan (08-02)                       | The original D-08 isolated `build-push-action` v6→v7; the audit showed the same Node-24 + ESM change across all four Docker majors, so isolation added risk without value |
| Verification build target = `coding-assistants`                      | Only add-on with an aarch64 leg (so it is the only one exercising `setup-qemu-action@v4`); pre-alpha with no stability commitment; freshly rebuilt so the digest overwrite is no-op |
| PRs #39/#40 auto-closed by Renovate                                  | Both target `@v4` major-only patches (`login-action` v4.6.0, `setup-buildx-action` v4.3.0); once Task 1's `@v4` pin landed, Renovate satisfied them and auto-closed. No manual close needed — closing would have rewritten the floating-major convention (D-09) |
| Aarch64 leg 11m1s vs baseline 13m28s                                  | `-2m27s` (-18%) — QEMU emulation is faster on `setup-qemu-action@v4` than the v3 baseline, well within the 2x regression threshold                       |
| Build trigger described as `paths:`-on-`main`, NOT tag-push (08-04) | For 6 of 7 add-ons the tag-trigger is commented out today, so describing it as a tag push would have been the next round of drift. RELEASE.md carries the per-addon tag-trigger detail |
| DELETE the false HA_WEBHOOK_SECRET / X-HA-Signature claim (08-04)   | A speculative "coming soon" promise is how the original false claim came about. The webhook has no HMAC; Cloudflare Access is the only transport protection. If HMAC is wanted later, that is a separate plan |
| Renovate close-suppresses-forever trap recorded as a convention (08-04) | The 2026-07-27 accidental batch-close permanently suppressed 3 versions; recorded in DEVELOPMENT.md so future maintainers know that closing a bump PR is a policy decision, not a no-op |

### Research Flags (open questions for implementation)

- **CSP / unsafe-eval** (Phase 6): Does HA Supervisor override `Content-Security-Policy` headers set in nginx? Verify
  empirically against meridian in production before committing to CSP approach for Mermaid.

- **Mermaid inline hook vs plugin** (Phase 4): Validate `mermaid.run()` in `doneEach` lifecycle hook targets fenced code
  blocks correctly; fallback: `Leward/mermaid-docsify` v2.0.1.

- **Kroki base64+deflate encoding** (Phase 4): The Kroki HTTP API requires zlib-compressed + base64-encoded source.
  Browser-native `pako` library is ~45KB minified — verify whether vendoring is acceptable or if `CompressionStream` API
  (modern browsers, no library) suffices for HA's recent Chromium versions.

- **share:rw vs share:ro** (Phase 5): git pull writes to `.git`; namespaces with `git_pull: true` require `rw` mounts.
  Confirmed in Phase 5: `map: share:rw config:rw media:rw` already in `config.yaml`.

### Todos

- [x] Bump `markdown-renderer/config.yaml` to `1.0.0-1` and run `make update-version` so the run.sh + generate_nginx.py
      bug fixes ship in the published add-on version (DONE — bumped to `1.1.0-0` as part of 06-02 which included
      git-sync + run.sh/Dockerfile/\_git_sync.py bug fixes)

- [x] Run `make validate-addons` after Phase 4 scaffold is in place (DONE — passes)
- [ ] Empirically verify `window.location.pathname` basePath in actual HA Ingress during Phase 4 (deferred to user)

### Blockers

Phase 8 cannot complete without user action:

- **08-03 is blocked** on the Cloudflare side (Q-02): service token, path-scoped Access application, and the two GitHub
  secrets `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`. Unassigned — user dashboard vs. agent via API not decided.

- **08-02 Task 3 and 08-03 Task 5** need approval for a verification build that overwrites published ghcr.io images.

Open questions carried in `.planning/phases/08-ci-cd-hardening/08-CONTEXT.md`:

- **Q-02**: who performs the Cloudflare Zero Trust configuration
- **Q-03**: `07-tolaria-add-on-scaffold` — 3 plans + CONTEXT from 2026-07-30, no SUMMARYs, absent from ROADMAP and STATE.
  Abandoned or paused? Phase 8 sidestepped it rather than renumbering

- **Q-04**: `Build Markdown Renderer` and `Build Meridian` have never run — no push has touched their paths since
  creation. Validate via `workflow_dispatch` (~3 min each)?

- **HMAC**: 08-04 will *delete* the false `HA_WEBHOOK_SECRET` claim rather than implement it. If payload signing is
  actually wanted, that is a separate plan (script + HA-side verification)

Also unresolved, discovered during the audit but out of scope: milestone v1.1 is marked complete but was never archived
via `/gsd-complete-milestone` — `REQUIREMENTS.md` still carries the v1.1 title while now also holding the CI section.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
| ----- | ---- | -------- | ----- | ----- |
| 06    | 01   | 19 min   | 3     | 4     |
| 06    | 02   | 36 min   | 3     | 9     |
| Phase 08 P01 | 2 min | 3 tasks | 5 files |
| Phase 08 P02 | 15 | 3 tasks | 5 files |
| Phase 08 P04 | 25 | 4 tasks | 5 files |

## Quick Tasks Completed

| #             | Description                                                                        | Date       | Commit  | Directory                                                                                                           |
| ------------- | ---------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| 260404-ksc    | Add Claude and GSD best-practice entries to .gitignore                             | 2026-04-04 | a0a9402 | [260404-ksc-add-claude-and-gsd-best-practice-entries](./quick/260404-ksc-add-claude-and-gsd-best-practice-entries/) |
| 260404-o5b    | Simplify meridian Dockerfile to single-stage npm + oauth polling run.sh            | 2026-04-04 | 19af0b3 | [260404-o5b-meridian-dockerfile-vereinfachen-mehrstu](./quick/260404-o5b-meridian-dockerfile-vereinfachen-mehrstu/) |
| 260404-rsj    | Meridian Ingress nginx reverse proxy fuer path rewriting                           | 2026-04-04 | 9407184 | [260404-rsj-meridian-ingress-nginx-reverse-proxy-fue](./quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue/) |
| 260404-s1t    | Meridian: expose all upstream config options in config.yaml and run.sh             | 2026-04-04 | 3ed58d3 | [260404-s1t-meridian-alle-upstream-config-optionen-i](./quick/260404-s1t-meridian-alle-upstream-config-optionen-i/) |
| 260502-0kw    | coding-assistants: make args and env optional in mcp_servers schema                | 2026-05-02 | 1f17a3b | [260502-0kw-coding-assistants-config-yaml-make-args-](./quick/260502-0kw-coding-assistants-config-yaml-make-args-/) |
| 260507-vjm    | Integriere MCP2ZigBee2MQTT in coding-assistants                                    | 2026-05-07 | 0afa2db | [260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass](./quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass/) |
| 260507-w85    | coding-assistants: dedizierter zigbee2mqtt Config-Block mit auto-MCP-Registrierung | 2026-05-07 | e4d1bc4 | [260507-w85-coding-assistants-dedizierter-zigbee2mqt](./quick/260507-w85-coding-assistants-dedizierter-zigbee2mqt/) |
| 260628-eqo3yb | network-tools: Icon + Flap-Detection (disconnect_threshold, consecutive_failures)  | 2026-06-28 | 7f53c82 | [260628-eqo3yb-network-tools-icon-flap-detection](./quick/260628-eqo3yb-network-tools-icon-flap-detection/)         |

## Session Continuity

Last session: 2026-08-30T17:31:51.956Z

---

_State initialized: 2026-04-04_ _Milestone v1.0 archived: 2026-04-04_ _Milestone v1.1 roadmap written: 2026-06-27_
_Milestone v1.2 (Phase 8, CI/CD Hardening) planned: 2026-08-30 from a GitHub Actions audit — 4 plans, requirements
CI-01..CI-10, nothing executed yet_
