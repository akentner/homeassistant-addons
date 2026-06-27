---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: markdown-renderer
status: planning
last_updated: "2026-06-27T14:49:11.737Z"
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 4
  completed_plans: 3
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-27)

**Core value:** Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version
tracking. **Current focus:** Phase 05 — Multi-Namespace + Dynamic Config

## Milestone v1.0 — COMPLETE

All 3 phases shipped. Archived to `.planning/milestones/v1.0-ROADMAP.md`.

| Phase | Name                 | Status   | Completed  |
| ----- | -------------------- | -------- | ---------- |
| 1     | Quality Fixes        | Complete | 2026-04-03 |
| 2     | Auto-Update Workflow | Complete | 2026-04-04 |
| 3     | Meridian Add-on      | Complete | 2026-04-04 |

## Milestone v1.1 — IN PROGRESS

Roadmap: 3 phases (4-6). Roadmap written; planning starts at Phase 4.

| Phase | Name                             | Status      | Completed  |
| ----- | -------------------------------- | ----------- | ---------- |
| 4     | Scaffold + Ingress Validation    | Complete    | 2026-06-27 |
| 5     | Multi-Namespace + Dynamic Config | Not started | —          |
| 6     | Git Integration                  | Not started | —          |

## Current Position

**Phase**: 5 — Multi-Namespace + Dynamic Config **Plan**: — (not started) **Status**: Awaiting `/gsd:plan-phase 5`
**Progress**: 1/3 phases complete

**Progress bar**: `███░░░░░░░` 33%

## Accumulated Context

### Key Decisions (v1.1)

| Decision                                      | Rationale                                                                                                          |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Docsify 4.13.1 over MkDocs                    | No build step; "edit file → refresh" works directly; MkDocs requires rebuild on every change                       |
| Mermaid UMD build (not ESM)                   | Self-contained; ESM bundle breaks when vendored due to dynamic import chains                                       |
| `basePath: window.location.pathname`          | HA Ingress strips the token server-side but browser URL retains it; static basePath breaks XHR                     |
| `generate_nginx.py` for config generation     | Mirrors phone-logger's `generate_config.py`; Python justified for structured JSON + template loops                 |
| CI/Quality gate extension folded into Phase 4 | ADD-01 ("consistent with existing add-ons") implies validate-versions.sh and make validate-addons cover new add-on |

### Research Flags (open questions for implementation)

- **CSP / unsafe-eval** (Phase 6): Does HA Supervisor override `Content-Security-Policy` headers set in nginx? Verify
  empirically against meridian in production before committing to CSP approach for Mermaid.

- **Mermaid inline hook vs plugin** (Phase 4): Validate `mermaid.run()` in `doneEach` lifecycle hook targets fenced code
  blocks correctly; fallback: `Leward/mermaid-docsify` v2.0.1.

- **Kroki base64+deflate encoding** (Phase 4): The Kroki HTTP API requires zlib-compressed + base64-encoded source.
  Browser-native `pako` library is ~45KB minified — verify whether vendoring is acceptable or if `CompressionStream` API
  (modern browsers, no library) suffices for HA's recent Chromium versions.

- **share:rw vs share:ro** (Phase 5): git pull writes to `.git`; namespaces with `git_pull: true` require `rw` mounts;
  document this constraint in DOCS.md.

### Todos

- [ ] Run `make validate-addons` after Phase 4 scaffold is in place
- [ ] Empirically verify `window.location.pathname` basePath in actual HA Ingress during Phase 4

### Blockers

None.

## Quick Tasks Completed

| #          | Description                                                                        | Date       | Commit  | Directory                                                                                                           |
| ---------- | ---------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| 260404-ksc | Add Claude and GSD best-practice entries to .gitignore                             | 2026-04-04 | a0a9402 | [260404-ksc-add-claude-and-gsd-best-practice-entries](./quick/260404-ksc-add-claude-and-gsd-best-practice-entries/) |
| 260404-o5b | Simplify meridian Dockerfile to single-stage npm + oauth polling run.sh            | 2026-04-04 | 19af0b3 | [260404-o5b-meridian-dockerfile-vereinfachen-mehrstu](./quick/260404-o5b-meridian-dockerfile-vereinfachen-mehrstu/) |
| 260404-rsj | Meridian Ingress nginx reverse proxy fuer path rewriting                           | 2026-04-04 | 9407184 | [260404-rsj-meridian-ingress-nginx-reverse-proxy-fue](./quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue/) |
| 260404-s1t | Meridian: expose all upstream config options in config.yaml and run.sh             | 2026-04-04 | 3ed58d3 | [260404-s1t-meridian-alle-upstream-config-optionen-i](./quick/260404-s1t-meridian-alle-upstream-config-optionen-i/) |
| 260502-0kw | coding-assistants: make args and env optional in mcp_servers schema                | 2026-05-02 | 1f17a3b | [260502-0kw-coding-assistants-config-yaml-make-args-](./quick/260502-0kw-coding-assistants-config-yaml-make-args-/) |
| 260507-vjm | Integriere MCP2ZigBee2MQTT in coding-assistants                                    | 2026-05-07 | 0afa2db | [260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass](./quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass/) |
| 260507-w85 | coding-assistants: dedizierter zigbee2mqtt Config-Block mit auto-MCP-Registrierung | 2026-05-07 | e4d1bc4 | [260507-w85-coding-assistants-dedizierter-zigbee2mqt](./quick/260507-w85-coding-assistants-dedizierter-zigbee2mqt/) |

---

_State initialized: 2026-04-04_ _Milestone v1.0 archived: 2026-04-04_ _Milestone v1.1 roadmap written: 2026-06-27_ _Last
activity: 2026-06-27 — v1.1 roadmap defined (3 phases, 20 requirements)_
