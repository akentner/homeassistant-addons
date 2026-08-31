---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: opentofu-bridge
status: executing
stopped_at: Completed 09-01-PLAN.md (Bridge 4-file scaffold + Go module + chi + slog)
last_updated: "2026-08-31T12:45:39.338Z"
last_activity: 2026-08-31
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 4
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-31)

**Core value:** Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version
tracking. **Current focus:** Phase 09 — bridge-foundation-token-rotation-spike
`08-05-GAP-PLAN.md` remains ready to run whenever Cloudflare setup lands.

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

## Milestone v1.3 opentofu-bridge — PLANNING

Roadmap: 7 phases (9-15), 46 requirements mapped. Source: `research/SUMMARY.md` + `REQUIREMENTS.md`. Status:
roadmap approved; Phase 9 ready to plan. v1.3 runs in parallel with v1.2 Phase 8 gap-closure by explicit user decision.

| Phase | Name                                                 | Status      | Completed |
| ----- | ---------------------------------------------------- | ----------- | --------- |
| 9     | Bridge Foundation + Token Rotation Spike              | Not started | —         |
| 10    | Auth Layer + Structured Logging + Healthcheck         | Not started | —         |
| 11    | Bridge Read API                                      | Not started | —         |
| 12    | Bridge Write API + Critical-Addon Safety + Concurrency | Not started | —         |
| 13    | Provider + Resource + Data Sources + Schema Handshake | Not started | —         |
| 14    | Real-HA End-to-End Verification + Operator Docs        | Not started | —         |
| 15    | CI Hardening + Provider Install Workflow             | Not started | —         |

Phase dependency graph enforces: 9 → 10 → 11 → 12 → 13 → 14 → 15 (strictly serial). The empirical SUPERVISOR_TOKEN
rotation spike (H-1 from PITFALLS) is the first deliverable of Phase 9; it is the lowest-confidence item blocking
the rest.

## Current Position

Phase: 09 (bridge-foundation-token-rotation-spike) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-08-31

## Accumulated Context

### Key Decisions (v1.3)

| Decision                                                                | Rationale                                                                                                                                       |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 7 phases, not 10 — vertical slices, not horizontal layers               | Each phase produces a deployable, verifiable artifact; collapse read+write API into one phase was rejected (loses safety gate before write)    |
| Empirical SUPERVISOR_TOKEN rotation spike is Phase 9, not later         | H-1 is the lowest-confidence item; designing auth on top of unverified token behavior risks rework (per PITFALLS research)                        |
| Per-slug mutex goes in Phase 12, not Phase 13                           | Defense-in-depth for cross-host concurrent applies must exist BEFORE Provider surfaces destructive ops; STATE-03 paired with write endpoints    |
| Real-HA E2E gets its own phase (14), not folded into Provider (13)      | Phase-8 pattern: empirical verification against live HA host deserves its own validation gate; docs written from observed behavior, not theory   |
| Phase 15 (CI + install-provider) is intentionally thin                  | The CI work is substantial (new build workflow, new test workflow, install verification); TOFU-04 is the single REQ-ID; non-req deliverables carry the weight |
| `homeassistant_addon_repository` deferred to v1.4 (per existing decision) | PROJECT.md + REQUIREMENTS.md both record this; do NOT re-add in any v1.3 phase                                                                  |

### Research Flags (open questions for implementation — must resolve before/during Phase 9)

- **H-1: SUPERVISOR_TOKEN rotation across Supervisor restart** — LOW confidence; **must verify empirically in Phase 9
  spike** (before designing token refresh logic in Phase 10). Output: spike result documented in `09-SUMMARY.md`.

- **PITFALLS §10: HA backup integration with `addon_config` mount** — MEDIUM confidence; **verify in Phase 9 spike**.
  Affects whether the secondary state-copy mitigation in STATE-01 actually works.

- **Open Q-1 (deferred to v1.4): `homeassistant_addon_repository`** — confirmed out of scope; do NOT add mid-milestone.

- **Open Q-2 (resolved in FEATURES.md): `TypeMap<String>` for options in Phase 1** — Phase 13 uses static TypeMap<String>
  with server-side validation via `/options/validate`; dynamic typed schema is Phase 2.

- **Open Q-4 (resolved): `pwned` secrets surface as Provider warning** — not error; surfaced in Phase 13 Update flow.

- **Open Q-5 (resolved): `start = true` default** — Phase 13 schema; opt-out documented in `DOCS.md`.

- **Open Q-7 (resolved): plain HTTP on Tailscale for Phase 1** — TLS termination deferred; AUTH-07 binds `0.0.0.0:8124`
  with Tailscale-interface detection at startup.

- **Open Q-8 (resolved): `UseStateForUnknown()` default** — applied to `state` attribute in Phase 13.

### Todos

- [ ] Phase 9: Run empirical SUPERVISOR_TOKEN rotation spike against ha-nextgen (or haos-op3050-1) — PITFALLS H-1
- [ ] Phase 9: Verify HA backup integration includes `/data` mounted via `addon_config:rw` — PITFALLS §10
- [ ] Phase 9: Extend `internal/validate-versions.sh` to enforce Bridge `build.yaml` == Provider `build.yaml` semver
- [ ] Phase 9: Scaffold `terraform-bridge/` 4-file pattern + `terraform-provider-homeassistant/` Go module

### Blockers

- **Phase 8 gap-closure (`08-05-GAP-PLAN.md`) remains blocked** on user Cloudflare setup (Q-02 from 08-CONTEXT).
  v1.3 Phase 9-15 runs in parallel per explicit user decision.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
| ----- | ---- | -------- | ----- | ----- |
| 06    | 01   | 19 min   | 3     | 4     |
| 06    | 02   | 36 min   | 3     | 9     |
| Phase 08 P01 | 2 min | 3 tasks | 5 files |
| Phase 08 P02 | 15 | 3 tasks | 5 files |
| Phase 08 P04 | 25 | 4 tasks | 5 files |
| Phase 09 P01 | 40 | 3 tasks | 15 files |

## Quick Tasks Completed

| #             | Description                                                                        | Date       | Commit  | Directory                                                                                                           |
| ------------- | ---------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| 260404-ksc    | Add Claude and GSD best-practice entries to .gitignore                             | 2026-04-04 | a0a9402 | [260404-ksc-add-claude-and-gsd-best-practice-entries](./quick/260404-ksc-add-claude-and-gsd-best-practice-entries/) |
| 260404-o5b    | Simplify meridian Dockerfile to single-stage npm + oauth polling run.sh            | 2026-04-04 | 19af0b3 | [quick/260404-o5b-meridian-dockerfile-vereinfachen-mehrstu](./quick/260404-o5b-meridian-dockerfile-vereinfachen-mehrstu/) |
| 260404-rsj    | Meridian Ingress nginx reverse proxy fuer path rewriting                           | 2026-04-04 | 9407184 | [quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue](./quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue/) |
| 260404-s1t    | Meridian: expose all upstream config options in config.yaml and run.sh             | 2026-04-04 | 3ed58d3 | [quick/260404-s1t-meridian-alle-upstream-config-optionen-i](./quick/260404-s1t-meridian-alle-upstream-config-optionen-i/) |
| 260502-0kw    | coding-assistants: make args and env optional in mcp_servers schema                | 2026-05-02 | 1f17a3b | [quick/260502-0kw-coding-assistants-config-yaml-make-args-](./quick/260502-0kw-coding-assistants-config-yaml-make-args-/) |
| 260507-vjm    | Integriere MCP2ZigBee2MQTT in coding-assistants                                    | 2026-05-07 | 0afa2db | [quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass](./quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass/) |
| 260507-w85    | coding-assistants: dedizierter zigbee2mqtt Config-Block mit auto-MCP-Registrierung | 2026-05-07 | e4d1bc4 | [quick/260507-w85-coding-assistants-dedizierter-zigbee2mqt](./quick/260507-w85-coding-assistants-dedizierter-zigbee2mqt/) |
| 260628-eqo3yb | network-tools: Icon + Flap-Detection (disconnect_threshold, consecutive_failures)  | 2026-06-28 | 7f53c82 | [quick/260628-eqo3yb-network-tools-icon-flap-detection](./quick/260628-eqo3yb-network-tools-icon-flap-detection/)         |

## Session Continuity

Last session: 2026-08-31T12:45:39.335Z
Stopped at: Completed 09-01-PLAN.md (Bridge 4-file scaffold + Go module + chi + slog)
to proceed to `/gsd-plan-phase 9`
Resume file: None

---

_State initialized: 2026-04-04_ _Milestone v1.0 archived: 2026-04-04_ _Milestone v1.1 roadmap written: 2026-06-27_
_Milestone v1.2 (Phase 8, CI/CD Hardening) planned: 2026-08-30 from a GitHub Actions audit — 4 plans, requirements
CI-01..CI-10, nothing executed yet_
_Milestone v1.3 opentofu-bridge roadmap written: 2026-08-31 — 7 phases (9-15), 46 requirements mapped across TOFU/
AUTH/BRIDGE/PROV/STATE/LIFE/OPS — Phase 9 ready to plan_
